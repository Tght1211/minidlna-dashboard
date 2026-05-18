"""On-demand video thumbnail generation via ffmpeg, cached on disk."""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "minidlna-dashboard" / "thumbs"
POSTER_CACHE_DIR = Path.home() / ".cache" / "minidlna-dashboard" / "posters"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
# Cap concurrent ffmpeg invocations: external USB/Thunderbolt drives thrash
# badly when many seek+read jobs run in parallel.
MAX_CONCURRENT = 3
_ffmpeg_slots = threading.BoundedSemaphore(MAX_CONCURRENT)

_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(detail_id: int) -> threading.Lock:
    with _locks_guard:
        lk = _locks.get(detail_id)
        if lk is None:
            lk = threading.Lock()
            _locks[detail_id] = lk
        return lk


def thumb_path(detail_id: int, width: int = 320) -> Path:
    if width >= 1024:
        return POSTER_CACHE_DIR / f"{detail_id}.jpg"
    return CACHE_DIR / f"{detail_id}.jpg"


def has_thumb(detail_id: int, width: int = 320) -> bool:
    p = thumb_path(detail_id, width=width)
    return p.exists() and p.stat().st_size > 0


def ensure_thumb(detail_id: int, source_path: str, *, is_image: bool = False,
                 seek: float = 5.0, width: int = 320) -> Path | None:
    """Generate thumbnail if missing. Works for video (uses seek+frame) and
    image (no seek, just resize). Returns path or None on failure."""
    p = thumb_path(detail_id, width=width)
    if has_thumb(detail_id, width=width):
        return p
    if not Path(source_path).exists():
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock_for((detail_id, width)):
        if has_thumb(detail_id, width=width):
            return p
        tmp = p.with_name(f".{detail_id}.partial.jpg")

        def _build(use_seek: bool) -> list[str]:
            cmd = [FFMPEG, "-y", "-nostdin", "-loglevel", "error"]
            if use_seek and not is_image:
                cmd += ["-ss", f"{seek}"]
            cmd += [
                "-i", source_path,
                "-frames:v", "1",
                "-update", "1",
                "-vf", f"scale={width}:-2:flags=lanczos",
                "-q:v", "5",
                "-f", "image2",
                str(tmp),
            ]
            return cmd

        def _run(use_seek: bool) -> bool:
            with _ffmpeg_slots:
                try:
                    r = subprocess.run(_build(use_seek), capture_output=True, text=True, timeout=30)
                except (subprocess.TimeoutExpired, OSError):
                    return False
                return r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0

        # For images, never seek; for video try seek first, fall back without.
        if is_image:
            ok = _run(use_seek=False)
        else:
            ok = _run(use_seek=True) or _run(use_seek=False)
        if not ok:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            return None
        tmp.rename(p)
        return p


def cache_stats() -> dict[str, int]:
    if not CACHE_DIR.exists():
        return {"count": 0, "bytes": 0}
    count = 0
    total = 0
    for p in CACHE_DIR.glob("*.jpg"):
        try:
            total += p.stat().st_size
            count += 1
        except OSError:
            pass
    return {"count": count, "bytes": total}
