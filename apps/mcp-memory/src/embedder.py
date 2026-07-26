import os
import sys
import json
import pickle
import threading
import numpy as np

FAISS_AVAILABLE = False
MODEL = None
INDEX = None
ID_MAP = {}
NEXT_POS = 0
_MODEL_LOCK = threading.Lock()
_MODEL_LOADED = False

INDEX_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".faiss_index.pkl")
EMBED_DIM = 384
MODEL_LOAD_TIMEOUT = 30  # seconds


def _load_model_sync():
    """Load sentence-transformer model (blocking, called from thread)."""
    global MODEL
    from sentence_transformers import SentenceTransformer
    MODEL = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")


def _lazy_load_model():
    global MODEL, _MODEL_LOADED
    if MODEL is not None:
        return True
    if _MODEL_LOADED:
        return MODEL is not None

    with _MODEL_LOCK:
        if MODEL is not None:
            return True
        if _MODEL_LOADED:
            return MODEL is not None

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("[embedder] sentence-transformers not installed", file=sys.stderr)
            _MODEL_LOADED = True
            return False

        # Try to load the model with a timeout to prevent hanging on download
        thread = threading.Thread(target=_load_model_sync, daemon=True)
        thread.start()
        thread.join(timeout=MODEL_LOAD_TIMEOUT)

        if thread.is_alive():
            print(f"[embedder] Model load timed out after {MODEL_LOAD_TIMEOUT}s — download may be slow or blocked. Vector search disabled.", file=sys.stderr)
            _MODEL_LOADED = True
            return False

        _MODEL_LOADED = True
        return MODEL is not None


def _lazy_load_faiss():
    global FAISS_AVAILABLE
    if FAISS_AVAILABLE:
        return True
    try:
        import faiss
        FAISS_AVAILABLE = True
        return True
    except ImportError:
        print("[embedder] faiss-cpu not installed", file=sys.stderr)
        return False


def _get_index():
    global INDEX
    if INDEX is not None:
        return INDEX
    if not _lazy_load_faiss():
        return None
    import faiss
    INDEX = faiss.IndexFlatIP(EMBED_DIM)
    return INDEX


def encode(text: str) -> np.ndarray:
    if not _lazy_load_model():
        return None
    vec = MODEL.encode(text, normalize_embeddings=True)
    return np.array([vec], dtype=np.float32)


def add(text: str, memory_id: str) -> bool:
    global NEXT_POS, ID_MAP
    idx = _get_index()
    if idx is None:
        return False
    vec = encode(text)
    if vec is None:
        return False
    idx.add(vec)
    ID_MAP[NEXT_POS] = memory_id
    NEXT_POS += 1
    _save_index()
    return True


def remove(memory_id: str) -> bool:
    global ID_MAP
    to_remove = [pos for pos, mid in ID_MAP.items() if mid == memory_id]
    if not to_remove:
        return False
    for pos in to_remove:
        del ID_MAP[pos]
    rebuild()
    return True


def search(query: str, k: int = 10) -> list[tuple[str, float]]:
    idx = _get_index()
    if idx is None or idx.ntotal == 0:
        return []
    vec = encode(query)
    if vec is None:
        return []
    scores, indices = idx.search(vec, min(k, idx.ntotal))
    results = []
    for score, pos in zip(scores[0], indices[0]):
        if pos == -1:
            continue
        mid = ID_MAP.get(int(pos))
        if mid:
            results.append((mid, float(score)))
    return results


def rebuild(texts: list[tuple[str, str]] = None):
    global INDEX, ID_MAP, NEXT_POS
    if not _lazy_load_faiss():
        return
    import faiss
    INDEX = faiss.IndexFlatIP(EMBED_DIM)
    ID_MAP = {}
    NEXT_POS = 0
    if texts:
        for memory_id, text in texts:
            vec = encode(text)
            if vec is not None:
                INDEX.add(vec)
                ID_MAP[NEXT_POS] = memory_id
                NEXT_POS += 1
    _save_index()


def _save_index():
    data = {"id_map": ID_MAP, "next_pos": NEXT_POS}
    try:
        with open(INDEX_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print(f"[embedder] save index failed: {e}", file=sys.stderr)


def _load_index():
    global ID_MAP, NEXT_POS
    try:
        if os.path.exists(INDEX_FILE):
            with open(INDEX_FILE, "rb") as f:
                data = pickle.load(f)
            ID_MAP = data.get("id_map", {})
            NEXT_POS = data.get("next_pos", 0)
    except Exception as e:
        print(f"[embedder] load index failed: {e}", file=sys.stderr)


def status() -> dict:
    _lazy_load_model()
    _lazy_load_faiss()
    idx = _get_index()
    return {
        "available": FAISS_AVAILABLE and MODEL is not None,
        "index_size": idx.ntotal if idx else 0,
        "dimension": EMBED_DIM,
    }
