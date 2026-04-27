"""Resolve and validate server-side scan directories."""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


def resolve_scan_directory(settings: Settings, root_index: int, subpath: str) -> Path:
    roots = settings.roots_list()
    if root_index < 0 or root_index >= len(roots):
        raise ValueError(f"root_index must be 0..{len(roots) - 1}")
    root = roots[root_index].resolve()
    if not root.is_dir():
        raise ValueError(f"Configured root is not a directory: {root}")
    rel = subpath.strip().replace("\\", "/").lstrip("/")
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Resolved path escapes allowed root") from exc
    if not candidate.is_dir():
        raise ValueError(f"Not a directory: {candidate}")
    return candidate
