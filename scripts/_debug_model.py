from __future__ import annotations

import traceback
from pathlib import Path

from PIL import Image

from multimodal_memory.embed import embed_text, get_model


def main() -> None:
    m = get_model()
    print("type", type(m))
    print("modules", len(m))
    inner = m[0]
    print("module0", type(inner))
    for name in (
        "processor",
        "image_processor",
        "tokenizer",
        "modality",
        "default_task",
        "model",
    ):
        val = getattr(inner, name, "MISSING")
        print(name, type(val).__name__ if val is not None else None, repr(val)[:120])

    try:
        v = embed_text("a red apple", as_query=True)
        print("text_ok", len(v), v[:3])
    except Exception:
        traceback.print_exc()

    tmp = Path("/tmp/_dbg_red.png")
    Image.new("RGB", (64, 64), (200, 30, 30)).save(tmp)
    try:
        vec = m.encode_document(Image.open(tmp))
        print("st_image_ok", getattr(vec, "shape", len(vec)))
    except Exception:
        traceback.print_exc()

    try:
        vec = m.encode_document(str(tmp))
        print("st_path_ok", getattr(vec, "shape", len(vec)))
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
