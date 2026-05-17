"""Read and write minidlna.conf."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CONF_PATH = Path.home() / ".config" / "minidlna" / "minidlna.conf"

_MEDIA_DIR_RE = re.compile(r"^\s*media_dir\s*=\s*(?:([APVapv]+)\s*,\s*)?(.+?)\s*$")


@dataclass
class MediaDir:
    types: str  # "" (all) or any combo of A, V, P
    path: str

    @property
    def label(self) -> str:
        if not self.types:
            return "全部"
        m = {"A": "音频", "V": "视频", "P": "图片"}
        return " + ".join(m.get(c.upper(), c) for c in self.types)


def read_text() -> str:
    return CONF_PATH.read_text(encoding="utf-8")


def parse_media_dirs() -> list[MediaDir]:
    out: list[MediaDir] = []
    for line in read_text().splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = _MEDIA_DIR_RE.match(line)
        if m:
            types = (m.group(1) or "").upper()
            out.append(MediaDir(types=types, path=m.group(2)))
    return out


def parse_kv(key: str) -> str | None:
    for line in read_text().splitlines():
        if line.lstrip().startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip()
    return None


def append_media_dir(path: str, types: str = "") -> None:
    """Append a media_dir line; types is '' or any of A/V/P combined."""
    types = "".join(c for c in types.upper() if c in "AVP")
    line = f"media_dir={types + ',' if types else ''}{path}\n"
    text = read_text()
    if not text.endswith("\n"):
        text += "\n"
    CONF_PATH.write_text(text + line, encoding="utf-8")


def remove_media_dir(path: str) -> bool:
    """Remove first media_dir line whose path matches."""
    lines = read_text().splitlines(keepends=True)
    new: list[str] = []
    removed = False
    for line in lines:
        if not removed:
            m = _MEDIA_DIR_RE.match(line)
            if m and m.group(2) == path:
                removed = True
                continue
        new.append(line)
    if removed:
        CONF_PATH.write_text("".join(new), encoding="utf-8")
    return removed


def log_tail(n: int = 80) -> str:
    candidates = [
        Path("/opt/homebrew/var/log/minidlnad.log"),
        Path.home() / ".cache" / "minidlna" / "minidlna.log",
        Path("/usr/local/var/log/minidlnad.log"),
    ]
    log = next((p for p in candidates if p.exists()), None)
    if not log:
        return ""
    try:
        with log.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 16384))
            data = f.read().decode("utf-8", errors="replace")
        return "\n".join(data.splitlines()[-n:])
    except OSError:
        return ""
