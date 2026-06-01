"""Runtime Gemini API key management."""

from __future__ import annotations

import os
import re
from pathlib import Path

from config.settings import PROJECT_ROOT

_ENV_PATH = PROJECT_ROOT / ".env"
_KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


def current_api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None


def mask_api_key(key: str) -> str:
    key = key.strip()
    if len(key) <= 8:
        return "••••"
    return f"{key[:4]}…{key[-4:]}"


def set_api_key(key: str) -> None:
    cleaned = key.strip()
    if not cleaned:
        raise ValueError("API key cannot be empty")

    os.environ["GEMINI_API_KEY"] = cleaned
    os.environ.pop("GOOGLE_API_KEY", None)
    _persist_env_key(cleaned)


def _persist_env_key(key: str) -> None:
    lines: list[str] = []
    if _ENV_PATH.is_file():
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()

    updated_gemini = False
    updated_google = False
    out: list[str] = []
    for line in lines:
        if re.match(r"^\s*GEMINI_API_KEY\s*=", line):
            out.append(f"GEMINI_API_KEY={key}")
            updated_gemini = True
            continue
        if re.match(r"^\s*GOOGLE_API_KEY\s*=", line):
            out.append(f"GOOGLE_API_KEY=")
            updated_google = True
            continue
        out.append(line)

    if not updated_gemini:
        out.append(f"GEMINI_API_KEY={key}")
    elif not updated_google:
        pass

    _ENV_PATH.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
