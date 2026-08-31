"""Local jina-embeddings-v5-omni-small helpers (text, image, video)."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEFAULT_MODEL_ID = "jinaai/jina-embeddings-v5-omni-small"
DEFAULT_DIM = 1024
_QUERY_TASKS = frozenset({"RETRIEVAL_QUERY", "QUERY"})

_load_lock = threading.Lock()
_infer_lock = threading.Lock()
_model: Any = None
_device: str | None = None
_load_error: str | None = None


def configured_model_id() -> str:
    return os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL_ID).strip() or DEFAULT_MODEL_ID


def configured_modality() -> str:
    return os.environ.get("EMBEDDING_MODALITY", "vision").strip() or "vision"


def configured_truncate_dim() -> int | None:
    raw = os.environ.get("EMBEDDING_TRUNCATE_DIM", "").strip()
    return int(raw) if raw.isdigit() else None


def resolve_device() -> str:
    override = os.environ.get("EMBEDDING_DEVICE", "auto").strip().lower()
    if override and override not in {"auto", ""}:
        return override
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def is_loaded() -> bool:
    return _model is not None


def load_error() -> str | None:
    return _load_error


def get_model() -> Any:
    global _model, _device, _load_error
    if _model is not None:
        return _model
    with _load_lock:
        if _model is not None:
            return _model
        _load_error = None
        model_id = configured_model_id()
        device = resolve_device()
        modality = configured_modality()
        logger.info("Loading %s on %s (modality=%s)", model_id, device, modality)
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(
                model_id,
                trust_remote_code=True,
                device=device,
                model_kwargs={
                    "default_task": "retrieval",
                    "modality": modality,
                },
            )
            _device = device
            logger.info("Embedding model ready on %s", device)
        except Exception as e:
            _load_error = str(e)
            logger.exception("Failed to load embedding model")
            raise
        return _model


def ensure_model_loaded() -> dict[str, Any]:
    get_model()
    return model_status()


def model_status() -> dict[str, Any]:
    dim_raw = os.environ.get("EMBEDDING_VECTOR_DIM", str(DEFAULT_DIM)).strip()
    vector_dim = int(dim_raw) if dim_raw.isdigit() else DEFAULT_DIM
    return {
        "model": configured_model_id(),
        "loaded": _model is not None,
        "device": _device or resolve_device(),
        "vector_dim": vector_dim,
        "modality": configured_modality(),
        "truncate_dim": configured_truncate_dim(),
        "error": _load_error,
    }


def _as_query(task_type: str | None, default: bool) -> bool:
    if task_type is None:
        return default
    return task_type.strip().upper() in _QUERY_TASKS


def _as_list(vec: Any) -> list[float]:
    arr = np.asarray(vec, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr[0]
    return arr.reshape(-1).tolist()


def _encode(payload: Any, *, as_query: bool, truncate_dim: int | None) -> list[float]:
    model = get_model()
    kwargs: dict[str, Any] = {"convert_to_numpy": True}
    if truncate_dim is not None:
        kwargs["truncate_dim"] = truncate_dim
    encode_fn = model.encode_query if as_query else model.encode_document
    with _infer_lock:
        vec = encode_fn(payload, **kwargs)
    return _as_list(vec)


def embed_text(
    text: str,
    *,
    as_query: bool = True,
    truncate_dim: int | None = None,
    task_type: str | None = None,
    output_dimensionality: int | None = None,
) -> list[float]:
    dim = output_dimensionality if output_dimensionality is not None else truncate_dim
    return _encode(
        text,
        as_query=_as_query(task_type, as_query),
        truncate_dim=dim,
    )


def embed_file(
    path: Path,
    *,
    modality: str = "image",
    as_query: bool = False,
    truncate_dim: int | None = None,
    task_type: str | None = None,
    output_dimensionality: int | None = None,
) -> list[float]:
    dim = output_dimensionality if output_dimensionality is not None else truncate_dim
    query = _as_query(task_type, as_query)
    path = Path(path)
    kind = (modality or "image").lower()
    if kind == "image":
        from multimodal_memory.images import open_image

        with open_image(path) as im:
            payload = im.convert("RGB").copy()
        try:
            return _encode(payload, as_query=query, truncate_dim=dim)
        finally:
            payload.close()
    return _encode(str(path), as_query=query, truncate_dim=dim)


def embed_document_file(
    path: Path,
    modality: str = "image",
    *,
    truncate_dim: int | None = None,
) -> list[float]:
    return embed_file(
        path,
        modality=modality,
        as_query=False,
        truncate_dim=truncate_dim,
    )
