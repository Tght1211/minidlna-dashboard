"""Read-only access to minidlna's files.db."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / ".cache" / "minidlna" / "files.db"


def _connect() -> sqlite3.Connection:
    uri = f"file:{DB_PATH}?mode=ro&immutable=0&cache=shared"
    conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def _q(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with _connect() as c:
        return list(c.execute(sql, params))


def counts() -> dict[str, int]:
    rows = _q(
        "SELECT CASE "
        "WHEN MIME LIKE 'audio/%' THEN 'audio' "
        "WHEN MIME LIKE 'video/%' THEN 'video' "
        "WHEN MIME LIKE 'image/%' THEN 'image' "
        "ELSE 'other' END AS kind, COUNT(*) AS n "
        "FROM DETAILS WHERE MIME IS NOT NULL GROUP BY kind"
    )
    out = {"audio": 0, "video": 0, "image": 0, "other": 0}
    for r in rows:
        out[r["kind"]] = r["n"]
    out["total"] = sum(out.values())
    return out


def total_size() -> int:
    row = _q("SELECT COALESCE(SUM(SIZE),0) AS s FROM DETAILS WHERE SIZE IS NOT NULL")
    return int(row[0]["s"]) if row else 0


def recent(limit: int = 12, kind: str | None = None) -> list[dict[str, Any]]:
    where = "WHERE MIME IS NOT NULL"
    params: tuple = ()
    if kind in ("audio", "video", "image"):
        where += " AND MIME LIKE ?"
        params = (f"{kind}/%",)
    rows = _q(
        f"SELECT ID, TITLE, PATH, SIZE, DURATION, RESOLUTION, MIME, TIMESTAMP, ALBUM_ART "
        f"FROM DETAILS {where} ORDER BY TIMESTAMP DESC LIMIT ?",
        params + (limit,),
    )
    return [dict(r) for r in rows]


def item(detail_id: int) -> dict[str, Any] | None:
    rows = _q("SELECT * FROM DETAILS WHERE ID = ?", (detail_id,))
    return dict(rows[0]) if rows else None


def search(query: str, limit: int = 100) -> list[dict[str, Any]]:
    like = f"%{query}%"
    rows = _q(
        "SELECT ID, TITLE, PATH, ARTIST, ALBUM, MIME, DURATION, SIZE, RESOLUTION, ALBUM_ART "
        "FROM DETAILS WHERE MIME IS NOT NULL AND ("
        "TITLE LIKE ? OR ARTIST LIKE ? OR ALBUM LIKE ? OR PATH LIKE ?) "
        "ORDER BY TIMESTAMP DESC LIMIT ?",
        (like, like, like, like, limit),
    )
    return [dict(r) for r in rows]


def _bucket_for(path: str, media_roots: list[str]) -> str:
    """Group a file by the first sub-directory under its configured media_dir.
    Falls back to the file's own dirname if no root matches."""
    for root in sorted(media_roots, key=len, reverse=True):
        root_n = root.rstrip("/")
        if path == root_n or path.startswith(root_n + "/"):
            rest = path[len(root_n) + 1 :] if path != root_n else ""
            parts = rest.split("/", 1)
            if len(parts) > 1:
                return f"{root_n}/{parts[0]}"
            # file sits directly inside the media_dir
            return root_n
    return os.path.dirname(path)


def folders(kind: str, media_roots: list[str] | None = None) -> list[dict[str, Any]]:
    """Group items into top-level buckets — one per immediate sub-directory of
    each configured media_dir. Loose files sitting directly in a media_dir all
    share that media_dir's bucket."""
    mime_filter = f"{kind}/%"
    rows = _q(
        "SELECT PATH, SIZE, ID FROM DETAILS WHERE MIME LIKE ? AND PATH IS NOT NULL",
        (mime_filter,),
    )
    roots = media_roots or []
    buckets: dict[str, dict[str, Any]] = {}
    for r in rows:
        bucket = _bucket_for(r["PATH"], roots)
        display = os.path.basename(bucket) or bucket
        b = buckets.setdefault(bucket, {
            "folder": bucket,
            "display": display,
            "count": 0,
            "size": 0,
            "sample_id": r["ID"],
        })
        b["count"] += 1
        b["size"] += int(r["SIZE"] or 0)
    return sorted(buckets.values(), key=lambda x: x["folder"])


def items_in_folder(folder: str, kind: str, limit: int = 5000) -> list[dict[str, Any]]:
    """Return all items recursively under `folder` (so a date bucket includes
    Camera01/02/03 leaves all together)."""
    like = f"{folder.rstrip('/')}/%"
    rows = _q(
        "SELECT ID, TITLE, PATH, SIZE, DURATION, RESOLUTION, MIME, ALBUM_ART "
        "FROM DETAILS WHERE MIME LIKE ? AND PATH LIKE ? "
        "ORDER BY PATH LIMIT ?",
        (f"{kind}/%", like, limit),
    )
    return [dict(r) for r in rows]


def all_items(kind: str, limit: int = 5000) -> list[dict[str, Any]]:
    rows = _q(
        "SELECT ID, TITLE, PATH, SIZE, DURATION, RESOLUTION, MIME, ALBUM_ART "
        "FROM DETAILS WHERE MIME LIKE ? ORDER BY PATH LIMIT ?",
        (f"{kind}/%", limit),
    )
    return [dict(r) for r in rows]


def album_art_path(album_art_id: int) -> str | None:
    if not album_art_id:
        return None
    rows = _q("SELECT PATH FROM ALBUM_ART WHERE ID = ?", (album_art_id,))
    return rows[0]["PATH"] if rows else None


def db_size() -> int:
    try:
        return DB_PATH.stat().st_size
    except OSError:
        return 0


def file_extension(path: str | None, mime: str | None) -> str:
    if path:
        _, ext = os.path.splitext(path)
        if ext:
            return ext.lstrip(".").lower()
    if mime and "/" in mime:
        return mime.split("/", 1)[1]
    return "bin"
