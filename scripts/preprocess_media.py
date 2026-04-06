"""Prepare embed targets: original images, video clips (<= API max length), thumbnails."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image  # noqa: E402

from config.settings import (  # noqa: E402
    CLIPS_DIR,
    EMBED_MANIFEST_NAME,
    FRAMES_DIR,
    METADATA_DIR,
    THUMBNAILS_DIR,
    VIDEO_EMBED_MAX_SECONDS,
    VIDEO_STRIP_AUDIO_ON_CLIPS,
    ensure_output_dirs,
)

try:
    import cv2
except ImportError:
    cv2 = None


def _safe_stem(name: str, max_len: int = 64) -> str:
    cleaned = re.sub(r"[^\w\-.]+", "_", name, flags=re.UNICODE)
    return cleaned[:max_len] or "media"


def _read_manifest(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _embed_id(parts: str) -> str:
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:20]


def _guess_mime(path: Path) -> str:
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
    if ext in {".mp4", ".m4v"}:
        return "video/mp4"
    if ext == ".mov":
        return "video/quicktime"
    if ext == ".webm":
        return "video/webm"
    if ext == ".mkv":
        return "video/x-matroska"
    return "application/octet-stream"


def _thumbnail(src: Path, dest: Path, max_side: int) -> bool:
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            im.save(dest, "JPEG", quality=88, optimize=True)
    except OSError:
        return False
    return dest.is_file()


def _ffprobe_duration(video: Path) -> float | None:
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    r = subprocess.run(
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
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        return None
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _ffmpeg_segment(
    src: Path,
    dest: Path,
    start_sec: float,
    duration_sec: float,
    *,
    strip_audio: bool,
) -> bool:
    exe = shutil.which("ffmpeg")
    if not exe or duration_sec <= 0:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
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
    r = subprocess.run(cmd, capture_output=True, timeout=600)
    return r.returncode == 0 and dest.is_file()


def _ffmpeg_frame(video: Path, dest: Path, time_sec: float) -> bool:
    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
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
        capture_output=True,
        timeout=300,
    )
    return r.returncode == 0 and dest.is_file()


def _frames_cv2(video: Path, dest_paths: list[Path]) -> int:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="JSONL manifest from build_manifest.py",
    )
    parser.add_argument(
        "--thumb-max",
        type=int,
        default=512,
        help="Longest side for image thumbnails (pixels).",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=float,
        default=None,
        help=(
            "Max length of each derived video clip for embedding "
            f"(default: {VIDEO_EMBED_MAX_SECONDS} from env VIDEO_EMBED_MAX_SECONDS)."
        ),
    )
    parser.add_argument(
        "--video-poster",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Save one JPEG poster per video under thumbnails (for you, not sent to embed).",
    )
    parser.add_argument(
        "--fallback-frames",
        type=int,
        default=0,
        help=(
            "If ffmpeg is missing, sample this many frames per video and embed those "
            "JPEGs instead (worse than real video clips)."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite thumbnails, posters, and derived clips.",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=None,
        help="Process at most this many video sources (cost control).",
    )
    args = parser.parse_args()
    chunk_sec = float(args.chunk_seconds or VIDEO_EMBED_MAX_SECONDS)
    if chunk_sec <= 0:
        print("--chunk-seconds must be positive")
        sys.exit(1)

    ensure_output_dirs()
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    embed_manifest_path = METADATA_DIR / EMBED_MANIFEST_NAME
    artifact_path = METADATA_DIR / "preprocess_artifacts.jsonl"

    rows = _read_manifest(args.manifest)
    videos_done = 0
    ffmpeg_ok = _ffmpeg_available()

    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None  # type: ignore[assignment]

    iterator = rows
    if tqdm:
        iterator = tqdm(rows, desc="preprocess")

    with (
        embed_manifest_path.open("w", encoding="utf-8") as emb_f,
        artifact_path.open("w", encoding="utf-8") as art_f,
    ):
        for row in iterator:
            src = Path(row["path"])
            if not src.is_file():
                continue
            fid = row["id"]
            stem = _safe_stem(src.stem)
            record: dict = {
                "id": fid,
                "source": str(src),
                "kind": row["kind"],
                "warnings": [],
            }

            if row["kind"] == "image":
                dest = THUMBNAILS_DIR / f"{fid}_{stem}.jpg"
                if args.force or not dest.is_file():
                    _thumbnail(src, dest, args.thumb_max)
                if dest.is_file():
                    record["thumbnail_path"] = str(dest)

                mime = _guess_mime(src)
                eid = _embed_id(f"img|{src.resolve()}|{mime}")
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

            elif row["kind"] == "video":
                if args.max_videos is not None and videos_done >= args.max_videos:
                    record["warnings"].append("skipped: --max-videos reached")
                    art_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    continue

                duration = _ffprobe_duration(src) if ffmpeg_ok else None
                poster = THUMBNAILS_DIR / f"{fid}_{stem}_poster.jpg"
                if args.video_poster and duration and duration > 0:
                    t_poster = min(1.0, duration / 2.0)
                    if args.force or not poster.is_file():
                        _ffmpeg_frame(src, poster, t_poster)
                    if poster.is_file():
                        record["poster_path"] = str(poster)

                use_fallback = not ffmpeg_ok or duration is None
                if use_fallback and args.fallback_frames > 0:
                    record["warnings"].append(
                        "ffmpeg/ffprobe unavailable or duration unknown; using frame JPEGs"
                    )
                    n = max(1, args.fallback_frames)
                    dests = [
                        FRAMES_DIR / f"{fid}_{stem}_f{i:03d}.jpg" for i in range(n)
                    ]
                    if args.force or not all(p.is_file() for p in dests):
                        if ffmpeg_ok and duration:
                            for t, outp in zip(
                                [
                                    duration * (i + 1) / (n + 1)
                                    for i in range(n)
                                ],
                                dests,
                            ):
                                if args.force or not outp.is_file():
                                    _ffmpeg_frame(src, outp, t)
                        else:
                            _frames_cv2(src, dests)
                    for p in dests:
                        if not p.is_file():
                            continue
                        eid = _embed_id(f"frame|{p.resolve()}")
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
                    record["frame_paths"] = [str(p) for p in dests if p.is_file()]
                    if record["frame_paths"]:
                        videos_done += 1
                    art_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    continue

                if use_fallback:
                    record["warnings"].append(
                        "skipped video: need ffmpeg/ffprobe for clip mode "
                        "(install ffmpeg or pass --fallback-frames N)"
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
                        mime = _guess_mime(src)
                        eid = _embed_id(f"vidwhole|{clip_path}|{mime}")
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
                        record["embed_mode"] = "whole_file"
                        break

                    out_clip = CLIPS_DIR / f"{fid}_{stem}_c{i:04d}.mp4"
                    if args.force or not out_clip.is_file():
                        _ffmpeg_segment(
                            src,
                            out_clip,
                            start,
                            seg_len,
                            strip_audio=VIDEO_STRIP_AUDIO_ON_CLIPS,
                        )
                    if not out_clip.is_file():
                        record["warnings"].append(
                            f"failed clip segment i={i} start={start}"
                        )
                        continue
                    clip_paths.append(str(out_clip.resolve()))
                    eid = _embed_id(f"vidclip|{out_clip.resolve()}")
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
                    record["embed_mode"] = "chunked_clips"

                record["clip_paths"] = clip_paths
                if clip_paths or record.get("embed_mode") == "whole_file":
                    videos_done += 1

            art_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote embed targets: {embed_manifest_path}")
    print(f"Wrote artifact index: {artifact_path}")


if __name__ == "__main__":
    main()
