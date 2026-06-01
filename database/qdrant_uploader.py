import os
import uuid
from typing import Any, Dict, List, Union, Optional

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

# =========================
# Load ENV
# =========================

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_TOKEN = os.getenv("QDRANT_TOKEN")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "asnany_blog_articles")

QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", 120))
QDRANT_UPSERT_BATCH_SIZE = int(os.getenv("QDRANT_UPSERT_BATCH_SIZE", 8))

# IMPORTANT:
# Qdrant Point IDs officially support: int (u64) or UUID (string form).
# If embedder gives a non-UUID string like "12_3", we deterministically convert it to UUID.
QDRANT_ID_NAMESPACE = os.getenv(
    "QDRANT_ID_NAMESPACE",
    "6ba7b811-9dad-11d1-80b4-00c04fd430c8",  # uuid.NAMESPACE_URL
)

if not QDRANT_URL:
    raise RuntimeError("QDRANT_URL is not set in .env")

# =========================
# Client
# =========================

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_TOKEN,
    timeout=QDRANT_TIMEOUT,
    check_compatibility=False,
)

# =========================
# Helpers
# =========================

def _normalize_point_id(raw_id: Any) -> Union[int, str]:
    """
    Qdrant supports numeric IDs and UUID IDs.
    If we receive an arbitrary string (e.g. "123_4"), convert it deterministically to UUIDv5.
    """
    if isinstance(raw_id, int):
        return raw_id

    # Allow passing UUID object
    if isinstance(raw_id, uuid.UUID):
        return str(raw_id)

    # Strings: accept UUID strings, else convert deterministically
    if isinstance(raw_id, str):
        s = raw_id.strip()
        if not s:
            raise ValueError("Point id is empty")

        try:
            return str(uuid.UUID(s))
        except Exception:
            ns = uuid.UUID(QDRANT_ID_NAMESPACE)
            # include collection name to avoid accidental cross-collection collisions
            return str(uuid.uuid5(ns, f"{QDRANT_COLLECTION}:{s}"))

    # Fallback: stringify then UUIDv5
    ns = uuid.UUID(QDRANT_ID_NAMESPACE)
    return str(uuid.uuid5(ns, f"{QDRANT_COLLECTION}:{str(raw_id)}"))


def _extract_vector(point: Dict[str, Any]) -> Dict[str, List[float]]:
    """
    Accepts either:
      - point["vectors"] (our internal shape)
      - point["vector"]  (alternative)
    Must contain the named vector: "embedding_text"
    """
    vec = point.get("vectors") or point.get("vector")
    if not isinstance(vec, dict):
        raise ValueError("Point vector must be a dict of named vectors")

    if "embedding_text" not in vec:
        raise ValueError("Named vector 'embedding_text' is missing in point vectors")

    emb = vec["embedding_text"]
    if not isinstance(emb, list) or not emb:
        raise ValueError("embedding_text vector must be a non-empty list")

    return vec  # keep the whole named-vectors dict


# =========================
# Collection Utils
# =========================

def ensure_collection(vector_size: int) -> None:
    """
    Ensures collection exists and matches the expected named vector config.
    """
    if client.collection_exists(QDRANT_COLLECTION):
        # Optional safety: ensure size matches if we can read it
        try:
            info = client.get_collection(QDRANT_COLLECTION)
            vectors = info.config.params.vectors  # type: ignore[attr-defined]
            # vectors could be a dict (named vectors) or VectorParams (single)
            existing_size: Optional[int] = None

            if isinstance(vectors, dict) and "embedding_text" in vectors:
                existing_size = getattr(vectors["embedding_text"], "size", None)
            else:
                existing_size = getattr(vectors, "size", None)

            if existing_size is not None and int(existing_size) != int(vector_size):
                raise RuntimeError(
                    f"Qdrant collection '{QDRANT_COLLECTION}' exists but vector size mismatch: "
                    f"expected {vector_size}, found {existing_size}. "
                    f"Use a new collection name or recreate the collection."
                )
        except Exception:
            # If we can't read config for any reason, don't block uploads here.
            pass
        return

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config={
            "embedding_text": models.VectorParams(
                size=int(vector_size),
                distance=models.Distance.COSINE,
            ),
        },
    )

    print(f"✅ Created collection: {QDRANT_COLLECTION}")


# =========================
# Upload Core
# =========================

def upload_embeddings(points_data: List[Dict[str, Any]]) -> None:
    """
    Upserts points in batches.
    - Supports deterministic conversion of non-UUID string IDs into UUIDv5 (safe + stable).
    - Expects named vector "embedding_text".
    """
    if not points_data:
        print("⚠️ No embeddings to upload")
        return

    first_vec = _extract_vector(points_data[0])["embedding_text"]
    vector_size = len(first_vec)

    # Safety: validate all points have same vector length
    for p in points_data:
        v = _extract_vector(p)["embedding_text"]
        if len(v) != vector_size:
            raise ValueError("Inconsistent vector sizes in points_data")

    ensure_collection(vector_size)

    total = len(points_data)

    for i in range(0, total, QDRANT_UPSERT_BATCH_SIZE):
        batch = points_data[i : i + QDRANT_UPSERT_BATCH_SIZE]

        client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=[
                models.PointStruct(
                    id=_normalize_point_id(p.get("id")),
                    vector=_extract_vector(p),
                    payload=p.get("payload") or {},
                )
                for p in batch
            ],
            wait=True,
        )

        print(f"⬆️ Uploaded {min(i + QDRANT_UPSERT_BATCH_SIZE, total)}/{total}")

    print("✅ All embeddings uploaded")