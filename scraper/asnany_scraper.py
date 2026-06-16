import csv
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Union
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, unquote, quote

import requests
from bs4 import BeautifulSoup

from database.dashboard_logger import log_event

BASE_URL = "https://blog.asnany.net"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Article RAG Bot)"
}

# 0 = scrape until no more pages / 404
TOTAL_PAGES = 0

# Safer default path (independent of current working directory)
DEFAULT_OUTPUT_CSV = Path(__file__).resolve().parent / "articles.csv"

FIELDNAMES = ["title", "url", "content"]


# ----------------------
# URL Normalization
# ----------------------
_TRACKING_PARAMS_PREFIXES = ("utm_",)
_TRACKING_PARAMS_EXACT = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
}


def normalize_url(raw_url: str) -> str:
    """
    Normalize URLs so we don't treat trivial variants as different articles.
    - Lowercase scheme+host
    - Decode percent-encoding then re-encode canonically (fixes %D9 vs %d9 mismatch)
    - Remove fragments (#...)
    - Drop tracking query params (utm_*, fbclid, gclid, ...)
    - Normalize trailing slash (keep '/' only for root)
    """
    if not raw_url:
        return ""

    raw_url = raw_url.strip()
    if not raw_url:
        return ""

    p = urlparse(raw_url)

    scheme = (p.scheme or "https").lower()
    netloc = (p.netloc or "").lower()

    # Decode percent-encoding fully, then re-encode with lowercase hex.
    # This normalizes %D9%8A == %d9%8a == ي so any variant compares equal.
    # safe='/' preserves path separators; other reserved chars stay encoded.
    path = p.path or "/"
    path = quote(unquote(path), safe="/:@!$&'()*+,;=")
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # filter query params
    q = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        k_l = (k or "").lower()
        if any(k_l.startswith(pref) for pref in _TRACKING_PARAMS_PREFIXES):
            continue
        if k_l in _TRACKING_PARAMS_EXACT:
            continue
        q.append((k, v))

    query = urlencode(q, doseq=True)

    # no fragment
    return urlunparse((scheme, netloc, path, "", query, ""))


# ----------------------
# CSV Helpers
# ----------------------
def ensure_csv_ready(csv_path: Union[str, Path]) -> Path:
    """
    Ensure the CSV exists and has a header.
    - If file doesn't exist -> create + write header
    - If file exists but empty -> write header
    """
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    needs_header = (not csv_path.exists()) or (csv_path.exists() and csv_path.stat().st_size == 0)

    if needs_header:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()

    return csv_path


def load_known_urls_from_csv(csv_path: Union[str, Path]) -> Set[str]:
    """
    Legacy CSV-based known URL loader.
    Kept for standalone/backwards-compatible use.
    Production pipeline uses load_known_urls_from_db() instead.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return set()

    known: Set[str] = set()
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            u = normalize_url((row or {}).get("url", "") or "")
            if u:
                known.add(u)
    return known


def append_article_to_csv(csv_path: Union[str, Path], article: Dict[str, str]) -> None:
    """
    Append ONE article row to the CSV and flush immediately for safety.
    """
    csv_path = Path(csv_path)

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(
            {
                "title": article.get("title", "").strip(),
                "url": article.get("url", "").strip(),
                "content": article.get("content", "").strip(),
            }
        )
        f.flush()


# ----------------------
# Scraping
# ----------------------
def scrape_article(url: str) -> Dict[str, str]:
    """
    Scrape ONE article page and return {title,url,content}.
    """
    res = requests.get(url, headers=HEADERS, timeout=30)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    h1 = soup.find("h1", class_="wp-block-post-title")
    if not h1:
        raise ValueError("H1 title not found")

    title = h1.get_text(strip=True)

    content_div = soup.find("div", class_="entry-content")
    if not content_div:
        raise ValueError("Entry content not found")

    paragraphs: List[str] = []
    for tag in content_div.find_all(["p", "h2", "h3", "ul", "ol"], recursive=True):
        text = tag.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)

    content = "\n".join(paragraphs)

    return {
        "title": title,
        "url": url,
        "content": content,
    }


def get_article_links_from_page(page: int) -> List[str]:
    """
    Get article URLs from the listing page.
    Page 1 = BASE_URL
    Page N = BASE_URL/page/N/
    """
    if page == 1:
        url = BASE_URL
    else:
        url = f"{BASE_URL}/page/{page}/"

    res = requests.get(url, headers=HEADERS, timeout=30)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    links: List[str] = []
    for a in soup.select("h2.wp-block-post-title a"):
        href = a.get("href")
        if href:
            links.append(href.strip())

    # dedupe while preserving order
    seen = set()
    out: List[str] = []
    for l in links:
        if l not in seen:
            seen.add(l)
            out.append(l)

    return out


def scrape_all_articles(
    known_urls: Optional[Set[str]] = None,
    *,
    csv_path: Union[str, Path] = DEFAULT_OUTPUT_CSV,
    total_pages: int = TOTAL_PAGES,
    sleep_seconds: float = 0.3,
    on_article: Optional[Callable[[Dict[str, str]], None]] = None,
    write_csv: bool = True,
) -> int:
    """
    Incremental scraping:
    - known_urls: URLs already scraped (normalized). Any new URL will be scraped.
    - csv_path: CSV destination (used only when write_csv=True)
    - total_pages: 0 means "until pages end", else scrape 1..total_pages
    - on_article: optional callback called with the article dict after scraping.
                  Production pipeline passes insert_blog_article here.
    - write_csv: if True, appends each new article to CSV (legacy/standalone mode).
                 Set to False in production pipeline (MySQL is the source of truth).
    - Returns number of newly processed articles.
    """
    if known_urls is None:
        known_urls = set()

    if write_csv:
        csv_path = ensure_csv_ready(csv_path)

    new_count = 0
    page = 1

    log_event(
        "scraper_started",
        f"Scraping started, pages={'unlimited' if total_pages==0 else total_pages}",
    )

    while True:
        if total_pages != 0 and page > total_pages:
            break

        print(f"🔍 Page {page}")

        try:
            links = get_article_links_from_page(page)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                # Normal end-of-pages for WordPress pagination — not a failure
                print(f"📭 Page {page} returned 404, no more pages.")
                break
            print(f"⛔ Page {page} HTTP error {status}: {e}")
            log_event("scraper_failed", f"Page {page} HTTP error {status}: {e}")
            break
        except requests.RequestException as e:
            print(f"⛔ Failed to fetch page {page}: {e}")
            log_event("scraper_failed", f"Failed to fetch page {page}: {e}")
            break

        if not links:
            print(f"📭 No articles found on page {page}, stopping.")
            break

        for link in links:
            norm = normalize_url(link)
            if not norm:
                continue

            # ✅ Decision BEFORE scraping the article page
            if norm in known_urls:
                continue

            try:
                print(f"   → Scraping {link}")
                article = scrape_article(link)

                # Store the normalized URL in known_urls to avoid duplicates in same run
                known_urls.add(norm)

                # Write to CSV if enabled (legacy/standalone mode)
                if write_csv:
                    append_article_to_csv(csv_path, article)

                # Call the on_article callback if provided (production: insert_blog_article)
                if on_article is not None:
                    on_article(article)

                new_count += 1
                time.sleep(sleep_seconds)

            except Exception as e:
                print(f"❌ Failed {link}: {e}")

        page += 1

    print(f"\n✅ New articles processed: {new_count}")
    log_event("scraper_completed", f"Scraping completed, {new_count} new articles")
    return new_count


# ----------------------
# Standalone Run
# ----------------------
if __name__ == "__main__":
    csv_path = DEFAULT_OUTPUT_CSV
    existing = load_known_urls_from_csv(csv_path)
    print(f"📄 Known URLs in CSV: {len(existing)}")

    scrape_all_articles(existing, csv_path=csv_path, write_csv=True)