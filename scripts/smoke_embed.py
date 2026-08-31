"""Quick check that the local Jina encoder loads and returns 1024-d vectors."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_memory.embed import embed_file, embed_text, ensure_model_loaded


def main() -> None:
    status = ensure_model_loaded()
    print(f"loaded={status['loaded']} device={status['device']} model={status['model']}")
    query = embed_text("a red apple on a table", as_query=True)
    tmp = PROJECT_ROOT / "_smoke_red.png"
    Image.new("RGB", (64, 64), (200, 30, 30)).save(tmp)
    try:
        doc = embed_file(tmp, modality="image", as_query=False)
    finally:
        tmp.unlink(missing_ok=True)
    qn = float(np.linalg.norm(query))
    dn = float(np.linalg.norm(doc))
    sim = float(np.dot(query, doc) / (qn * dn)) if qn and dn else 0.0
    print(f"query_dim={len(query)} image_dim={len(doc)} cosine={sim:.4f}")
    if len(query) != 1024 or len(doc) != 1024:
        raise SystemExit("expected 1024-d embeddings")
    print("SMOKE OK")


if __name__ == "__main__":
    main()
