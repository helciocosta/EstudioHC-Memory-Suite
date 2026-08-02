import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _reload_embedder():
    import importlib
    import embedder
    return importlib.reload(embedder)


def test_index_save_load_roundtrip_json():
    embedder = _reload_embedder()
    embedder.ID_MAP = {0: "mem-1", 1: "mem-2"}
    embedder.NEXT_POS = 2
    with tempfile.TemporaryDirectory() as tmp:
        embedder.INDEX_FILE = os.path.join(tmp, ".faiss_index.json")
        embedder._save_index()
        assert os.path.exists(embedder.INDEX_FILE)
        embedder.ID_MAP = {}
        embedder.NEXT_POS = 0
        embedder._load_index()
        assert embedder.ID_MAP == {0: "mem-1", 1: "mem-2"}
        assert embedder.NEXT_POS == 2
        with open(embedder.INDEX_FILE) as f:
            data = json.load(f)
        assert data["next_pos"] == 2


def test_nao_existe_import_pickle():
    embedder = _reload_embedder()
    with open(embedder.__file__) as f:
        assert "pickle" not in f.read()