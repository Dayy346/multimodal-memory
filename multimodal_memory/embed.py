"""Gemini multimodal embedding helpers."""

from __future__ import annotations

import os

from google import genai
from google.genai import types


def get_client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY")
    return genai.Client(api_key=key)


def embed_config(
    *,
    task_type: str | None,
    output_dimensionality: int | None,
) -> types.EmbedContentConfig | None:
    if task_type is None and output_dimensionality is None:
        return None
    return types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=output_dimensionality,
    )


def embed_text(
    client: genai.Client,
    model: str,
    text: str,
    *,
    task_type: str | None = "RETRIEVAL_QUERY",
    output_dimensionality: int | None = None,
) -> list[float]:
    cfg = embed_config(
        task_type=task_type,
        output_dimensionality=output_dimensionality,
    )
    response = client.models.embed_content(
        model=model,
        contents=text,
        config=cfg,
    )
    return list(response.embeddings[0].values)


def embed_bytes(
    client: genai.Client,
    model: str,
    data: bytes,
    mime: str,
    *,
    task_type: str | None = "RETRIEVAL_DOCUMENT",
    output_dimensionality: int | None = None,
) -> list[float]:
    cfg = embed_config(
        task_type=task_type,
        output_dimensionality=output_dimensionality,
    )
    response = client.models.embed_content(
        model=model,
        contents=[
            types.Content(
                parts=[types.Part.from_bytes(data=data, mime_type=mime)],
            )
        ],
        config=cfg,
    )
    return list(response.embeddings[0].values)
