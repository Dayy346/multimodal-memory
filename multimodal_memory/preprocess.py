"""Thumbnails, posters, video clips, and embed_manifest.jsonl from a scan manifest."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
from pathlib import Path

from multimodal_memory.images import write_thumbnail_jpeg

from config.settings import (
    CLIPS_DIR as DEFAULT_CLIPS_DIR,
    FFMPEG_CLIP_TRY_COPY,
    FFMPEG_FRAME_TIMEOUT_SEC,
    FFMPEG_SEGMENT_TIMEOUT_SEC,
    FFPROBE_TIMEOUT_SEC,
    FRAMES_DIR as DEFAULT_FRAMES_DIR,
    THUMBNAILS_DIR as DEFAULT_THUMBNAILS_DIR,
    VIDEO_EMBED_MAX_SECONDS,
    VIDEO_STRIP_AUDIO_ON_CLIPS,
    ensure_output_dirs,
)

try:
    import cv2
except ImportError:
    cv2 = None


def safe_stem(name: str, max_len: int = 64) -> str:
    cleaned = re.sub(r"[^\w\-.]+", "_", name, flags=re.UNICODE)
    return cleaned[:max_len] or "media"


def read_manifest_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def read_embed_manifest_jsonl(path: Path) -> list[dict]:
    return read_manifest_jsonl(path)


def embed_row_id(parts: str) -> str:
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:20]


def guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime:
        return mime
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    if ext in {".heic", ".heif"}:
        return "image/heic"
    if ext in {".mp4", ".m4v"}:
        return "video/mp4"
    if ext == ".mov":
        return "video/quicktime"
    if ext == ".webm":
        return "video/webm"
    if ext == ".mkv":
        return "video/x-matroska"
    return "application/octet-stream"


def write_thumbnail(src: Path, dest: Path, max_side: int) -> bool:
    return write_thumbnail_jpeg(src, dest, max_side)


def _run_subprocess(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def _unlink_if_exists(path: Path) -> None:
    if path.is_file():
        path.unlink(missing_ok=True)


def ffprobe_duration(video: Path) -> float | None:
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    r = _run_subprocess(
        [
            exe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        timeout=FFPROBE_TIMEOUT_SEC,
    )
    if r is None or r.returncode != 0:
        return None
    try:
        return float(r.stdout.decode("utf-8", errors="replace").strip())
    except ValueError:
        return None


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _ffmpeg_segment_copy(
    exe: str,
    src: Path,
    dest: Path,
    start_sec: float,
    duration_sec: float,
    *,
    strip_audio: bool,
    timeout: int,
) -> bool:
    cmd = [
        exe,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(max(0.0, start_sec)),
        "-i",
        str(src),
        "-t",
        str(duration_sec),
        "-c:v",
        "copy",
    ]
    if strip_audio:
        cmd.append("-an")
    cmd.extend(["-movflags", "+faststart", str(dest)])
    r = _run_subprocess(cmd, timeout=timeout)
    ok = r is not None and r.returncode == 0 and dest.is_file()
    if not ok:
        _unlink_if_exists(dest)
    return ok


def _ffmpeg_segment_encode(
    exe: str,
    src: Path,
    dest: Path,
    start_sec: float,
    duration_sec: float,
    *,
    strip_audio: bool,
    timeout: int,
) -> bool:
    cmd = [
        exe,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(max(0.0, start_sec)),
        "-i",
        str(src),
        "-t",
        str(duration_sec),
    ]
    if strip_audio:
        cmd.append("-an")
    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    r = _run_subprocess(cmd, timeout=timeout)
    ok = r is not None and r.returncode == 0 and dest.is_file()
    if not ok:
        _unlink_if_exists(dest)
    return ok


def ffmpeg_segment(
    src: Path,
    dest: Path,
    start_sec: float,
    duration_sec: float,
    *,
    strip_audio: bool,
) -> str | None:
    exe = shutil.which("ffmpeg")
    if not exe or duration_sec <= 0:
        return "ffmpeg missing or invalid duration"
    dest.parent.mkdir(parents=True, exist_ok=True)
    timeout = FFMPEG_SEGMENT_TIMEOUT_SEC
    if FFMPEG_CLIP_TRY_COPY and _ffmpeg_segment_copy(
        exe, src, dest, start_sec, duration_sec, strip_audio=strip_audio, timeout=timeout
    ):
        return None
    if _ffmpeg_segment_encode(
        exe, src, dest, start_sec, duration_sec, strip_audio=strip_audio, timeout=timeout
    ):
        return None
    if FFMPEG_CLIP_TRY_COPY:
        return f"clip encode failed after {timeout}s (copy and libx264)"
    return f"clip encode failed after {timeout}s"


def ffmpeg_frame(video: Path, dest: Path, time_sec: float) -> bool:
    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = _run_subprocess(
        [
            exe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(max(0.0, time_sec)),
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(dest),
        ],
        timeout=FFMPEG_FRAME_TIMEOUT_SEC,
    )
    ok = r is not None and r.returncode == 0 and dest.is_file()
    if not ok:
        _unlink_if_exists(dest)
    return ok


def frames_cv2(video: Path, dest_paths: list[Path]) -> int:
    if cv2 is None:
        return 0
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return 0
    n = len(dest_paths)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if count <= 0:
        cap.release()
        return 0
    written = 0
    for i, outp in enumerate(dest_paths):
        idx = max(0, min(count - 1, int((i + 1) * count / (n + 1)) - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        outp.parent.mkdir(parents=True, exist_ok=True)
        if cv2.imwrite(str(outp), frame):
            written += 1
    cap.release()
    return written


def _write_embed_line(f, row: dict) -> None:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_preprocess(
    manifest_path: Path,
    *,
    embed_manifest_path: Path,
    artifact_path: Path,
    thumb_max: int = 512,
    chunk_seconds: float | None = None,
    video_poster: bool = True,
    fallback_frames: int = 0,
    force: bool = False,
    max_videos: int | None = None,
    skip_thumbnails: bool = False,
    skip_videos: bool = False,
    progress_callback=None,
    use_global_output_dirs: bool = True,
    thumbnails_dir: Path | None = None,
    frames_dir: Path | None = None,
    clips_dir: Path | None = None,
) -> dict:
    """Build embed_manifest and preprocess artifacts. Returns counts."""
    chunk_sec = float(chunk_seconds or VIDEO_EMBED_MAX_SECONDS)
    if chunk_sec <= 0:
        raise ValueError("chunk_seconds must be positive")

    thumbs_base = thumbnails_dir or DEFAULT_THUMBNAILS_DIR
    frames_base = frames_dir or DEFAULT_FRAMES_DIR
    clips_base = clips_dir or DEFAULT_CLIPS_DIR

    if use_global_output_dirs:
        ensure_output_dirs()
        embed_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        embed_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        thumbs_base.mkdir(parents=True, exist_ok=True)
        frames_base.mkdir(parents=True, exist_ok=True)
        clips_base.mkdir(parents=True, exist_ok=True)

    rows = read_manifest_jsonl(manifest_path)
    videos_done = 0
    ffmpeg_ok = ffmpeg_available()
    embed_lines = 0
    processed = 0
    total_rows = len(rows)
    log_every = max(1, total_rows // 20) if total_rows else 1

    with (
        embed_manifest_path.open("w", encoding="utf-8") as emb_f,
        artifact_path.open("w", encoding="utf-8") as art_f,
    ):
        for row in rows:
            processed += 1
            if progress_callback and (
                processed == 1 or processed % log_every == 0 or processed == total_rows
            ):
                progress_callback(processed, total_rows)
            src = Path(row["path"])
            if not src.is_file():
                continue
            fid = row["id"]
            stem = safe_stem(src.stem)
            record: dict = {
                "id": fid,
                "source": str(src),
                "kind": row["kind"],
                "warnings": [],
            }

            if row["kind"] == "image":
                if not skip_thumbnails:
                    dest = thumbs_base / f"{fid}_{stem}.jpg"
                    if force or not dest.is_file():
                        write_thumbnail(src, dest, thumb_max)
                    if dest.is_file():
                        record["thumbnail_path"] = str(dest)

                mime = guess_mime(src)
                eid = embed_row_id(f"img|{src.resolve()}|{mime}")
                _write_embed_line(
                    emb_f,
                    {
                        "embed_id": eid,
                        "asset_id": fid,
                        "modality": "image",
                        "path": str(src.resolve()),
                        "mime_type": mime,
                        "source_path": str(src.resolve()),
                        "t_start_sec": None,
                        "t_end_sec": None,
                    },
                )
                embed_lines += 1

            elif row["kind"] == "video":
                if skip_videos or (max_videos is not None and max_videos <= 0):
                    record["warnings"].append("skipped: videos disabled for this run")
                    art_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    continue
                if max_videos is not None and videos_done >= max_videos:
                    record["warnings"].append("skipped: max_videos reached")
                    art_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    continue

                duration = ffprobe_duration(src) if ffmpeg_ok else None
                poster = thumbs_base / f"{fid}_{stem}_poster.jpg"
                if video_poster and duration and duration > 0:
                    t_poster = min(1.0, duration / 2.0)
                    if force or not poster.is_file():
                        ffmpeg_frame(src, poster, t_poster)
                    if poster.is_file():
                        record["poster_path"] = str(poster)

                use_fallback = not ffmpeg_ok or duration is None
                if use_fallback and fallback_frames > 0:
                    record["warnings"].append(
                        "ffmpeg/ffprobe unavailable or duration unknown; using frame JPEGs"
                    )
                    n = max(1, fallback_frames)
                    dests = [
                        frames_base / f"{fid}_{stem}_f{i:03d}.jpg" for i in range(n)
                    ]
                    if force or not all(p.is_file() for p in dests):
                        if ffmpeg_ok and duration:
                            for t, outp in zip(
                                [duration * (i + 1) / (n + 1) for i in range(n)],
                                dests,
                            ):
                                if force or not outp.is_file():
                                    ffmpeg_frame(src, outp, t)
                        else:
                            frames_cv2(src, dests)
                    for p in dests:
                        if not p.is_file():
                            continue
                        eid = embed_row_id(f"frame|{p.resolve()}")
                        _write_embed_line(
                            emb_f,
                            {
                                "embed_id": eid,
                                "asset_id": fid,
                                "modality": "image",
                                "path": str(p.resolve()),
                                "mime_type": "image/jpeg",
                                "source_path": str(src.resolve()),
                                "t_start_sec": None,
                                "t_end_sec": None,
                                "note": "fallback_frame",
                            },
                        )
                        embed_lines += 1
                    record["frame_paths"] = [str(p) for p in dests if p.is_file()]
                    if record["frame_paths"]:
                        videos_done += 1
                    art_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    continue

                if use_fallback:
                    record["warnings"].append(
                        "skipped video: need ffmpeg/ffprobe for clip mode "
                        "(install ffmpeg or pass fallback_frames)"
                    )
                    art_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    continue

                assert duration is not None
                n_chunks = max(1, int((duration + chunk_sec - 1e-9) // chunk_sec))
                clip_paths: list[str] = []

                for i in range(n_chunks):
                    start = i * chunk_sec
                    seg_len = min(chunk_sec, max(0.0, duration - start))
                    if seg_len <= 0.05:
                        continue
                    end_t = start + seg_len

                    if duration <= chunk_sec + 0.05:
                        clip_path = src.resolve()
                        mime = guess_mime(src)
                        eid = embed_row_id(f"vidwhole|{clip_path}|{mime}")
                        _write_embed_line(
                            emb_f,
                            {
                                "embed_id": eid,
                                "asset_id": fid,
                                "modality": "video",
                                "path": str(clip_path),
                                "mime_type": mime,
                                "source_path": str(src.resolve()),
                                "t_start_sec": 0.0,
                                "t_end_sec": round(duration, 3),
                                "whole_source_file": True,
                            },
                        )
                        embed_lines += 1
                        record["embed_mode"] = "whole_file"
                        break

                    out_clip = clips_base / f"{fid}_{stem}_c{i:04d}.mp4"
                    if force or not out_clip.is_file():
                        seg_err = ffmpeg_segment(
                            src,
                            out_clip,
                            start,
                            seg_len,
                            strip_audio=VIDEO_STRIP_AUDIO_ON_CLIPS,
                        )
                        if seg_err:
                            record["warnings"].append(
                                f"failed clip segment i={i} start={start}: {seg_err}"
                            )
                    if not out_clip.is_file():
                        continue
                    clip_paths.append(str(out_clip.resolve()))
                    eid = embed_row_id(f"vidclip|{out_clip.resolve()}")
                    _write_embed_line(
                        emb_f,
                        {
                            "embed_id": eid,
                            "asset_id": fid,
                            "modality": "video",
                            "path": str(out_clip.resolve()),
                            "mime_type": "video/mp4",
                            "source_path": str(src.resolve()),
                            "t_start_sec": round(start, 3),
                            "t_end_sec": round(end_t, 3),
                            "whole_source_file": False,
                        },
                    )
                    embed_lines += 1
                    record["embed_mode"] = "chunked_clips"

                record["clip_paths"] = clip_paths
                if clip_paths or record.get("embed_mode") == "whole_file":
                    videos_done += 1

            art_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "embed_manifest_lines": embed_lines,
        "manifest_assets": len(rows),
        "embed_manifest_path": str(embed_manifest_path),
        "artifact_path": str(artifact_path),
    }
