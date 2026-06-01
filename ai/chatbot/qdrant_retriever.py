import os
from typing import List, Optional, TypedDict

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# =========================
# Load ENV
# =========================

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_TOKEN = os.getenv("QDRANT_TOKEN")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION")

RETRIEVER_TOP_K = int(os.getenv("RETRIEVER_TOP_K", 5))

HF_MODEL = os.getenv("HF_MODEL")
HF_TOKEN = os.getenv("HF_TOKEN")

QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", 60))

if not QDRANT_URL:
    raise RuntimeError("QDRANT_URL is not set in .env")

if not QDRANT_COLLECTION:
    raise RuntimeError("QDRANT_COLLECTION is not set in .env")

if not HF_MODEL:
    raise RuntimeError("HF_MODEL is not set in .env")

# =========================
# Qdrant Client
# =========================

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_TOKEN,
    timeout=QDRANT_TIMEOUT,
    check_compatibility=False,
)

# =========================
# HF Model (lazy)
# =========================

_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("🧠 Loading query embedding model...")
        _model = SentenceTransformer(HF_MODEL, token=HF_TOKEN)
    return _model


# =========================
# Types
# =========================

class RetrievedChunk(TypedDict):
    blog_id: int
    chunk_text: str
    chunk_index: int
    score: float


# =========================
# Retriever (Chunks)
# =========================

def retrieve_chunks(query: str, *, top_k: Optional[int] = None) -> List[RetrievedChunk]:
    """
    - Embed user query (E5 format)
    - Query Qdrant using named vector "embedding_text"
    - Return chunks with: blog_id + chunk_text (+ chunk_index + score)
    """
    q = (query or "").strip()
    if not q:
        return []

    k = int(top_k) if top_k is not None else RETRIEVER_TOP_K
    if k <= 0:
        k = 5

    model = get_model()

    query_embedding = model.encode(
        f"query: {q}",
        normalize_embeddings=True,
    ).tolist()

    resp = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_embedding,
        using="embedding_text",
        limit=k,
        with_payload=True,
        with_vectors=False,
    )

    out: List[RetrievedChunk] = []

    for p in (resp.points or []):
        payload = p.payload or {}

        blog_id = payload.get("blog_id")
        chunk_text = payload.get("chunk_text")
        chunk_index = payload.get("chunk_index", -1)

        # لازم الاتنين دول موجودين
        if blog_id is None or not isinstance(chunk_text, str) or not chunk_text.strip():
            continue

        try:
            blog_id_int = int(blog_id)
        except Exception:
            continue

        try:
            chunk_index_int = int(chunk_index)
        except Exception:
            chunk_index_int = -1

        score_val = float(getattr(p, "score", 0.0) or 0.0)

        out.append(
            {
                "blog_id": blog_id_int,
                "chunk_text": chunk_text.strip(),
                "chunk_index": chunk_index_int,
                "score": score_val,
            }
        )

    return out


# =========================
# Backward-compatible helper (optional)
# =========================

def retrieve_article_ids(query: str) -> List[int]:
    """
    Old behavior (kept so the project doesn't break immediately):
    - Uses retrieve_chunks()
    - Returns unique blog_id list (deduped, order preserved)
    """
    chunks = retrieve_chunks(query)
    seen = set()
    ids: List[int] = []
    for c in chunks:
        bid = c["blog_id"]
        if bid not in seen:
            seen.add(bid)
            ids.append(bid)
    return ids