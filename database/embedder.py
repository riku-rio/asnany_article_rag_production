import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from database.db import get_connection

# =========================
# Load ENV
# =========================

load_dotenv()

HF_MODEL = os.getenv("HF_MODEL")
HF_TOKEN = os.getenv("HF_TOKEN")

# Batch size for SentenceTransformer.encode
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", 64))

# Chunking config (optional ENV overrides)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 200))

if not HF_MODEL:
    raise RuntimeError("HF_MODEL is not set in .env")

# =========================
# Load HF Model (lazy)
# =========================

_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("🧠 Loading embedding model...")
        _model = SentenceTransformer(HF_MODEL, token=HF_TOKEN)
    return _model


# =========================
# Chunking
# =========================

def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    length = len(text)

    # safety
    if chunk_size <= 0:
        chunk_size = 800
    if overlap < 0:
        overlap = 0
    if overlap >= chunk_size:
        overlap = max(chunk_size // 4, 0)

    while start < length:
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


def _iter_unembedded_articles(conn) -> List[Dict[str, Any]]:
    """
    Fetch all articles where is_embedded = 0 from MySQL.
    Returns a list of dicts with keys: id, title, content.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, title, content
            FROM blog
            WHERE is_embedded = 0
            ORDER BY id ASC;
            """
        )
        return cursor.fetchall()


# =========================
# Embedder Core
# =========================

def embed_blog_articles() -> List[Dict[str, Any]]:
    """
    Incremental embedder:
    - Reads ONLY articles where is_embedded = 0
    - Chunks content
    - Creates E5-compatible passage embeddings
    - Uses deterministic point IDs: "<blog_id>_<chunk_index>"
    - Returns Qdrant-ready points

    NOTE:
    - This function does NOT update is_embedded.
      Marking articles as embedded must happen AFTER successful upload to Qdrant
      (per-article) in the pipeline layer.
    """

    conn = get_connection()

    try:
        rows = _iter_unembedded_articles(conn)

        if not rows:
            print("⚠️ No new (unembedded) blog articles found")
            return []

        model = get_model()

        passages: List[str] = []
        meta: List[Tuple[int, int, str]] = []  # (blog_id, chunk_index, chunk_body)

        skipped_empty = 0

        for r in rows:
            blog_id = int(r["id"])
            title = (r["title"] or "").strip()
            content = (r["content"] or "").strip()

            if not title or not content:
                skipped_empty += 1
                continue

            chunks = chunk_text(content)

            # If content is too short or chunking returned empty
            if not chunks:
                skipped_empty += 1
                continue

            for idx, chunk in enumerate(chunks):
                passages.append(f"passage: {title}\n\n{chunk}")
                meta.append((blog_id, idx, chunk))

        if not passages:
            print("⚠️ No chunks prepared for embedding (all empty/invalid?)")
            return []

        vectors = model.encode(
            passages,
            batch_size=EMBED_BATCH_SIZE,
            show_progress_bar=True,
            normalize_embeddings=True,
        )

        points: List[Dict[str, Any]] = []

        for (blog_id, chunk_index, chunk_body), vec in zip(meta, vectors):
            point_id = f"{blog_id}_{chunk_index}"

            points.append(
                {
                    "id": point_id,
                    "vectors": {
                        "embedding_text": vec.tolist(),
                    },
                    "payload": {
                        "blog_id": blog_id,
                        "chunk_index": chunk_index,
                        "chunk_text": chunk_body,
                    },
                }
            )

        print(f"✅ Prepared {len(points)} chunk embeddings (articles: {len(rows)}, skipped: {skipped_empty})")
        return points

    finally:
        conn.close()