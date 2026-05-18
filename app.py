"""minidlna-dashboard — Flask app."""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

from lib import config, db, status, thumbs, watcher

# Ensure logs flush immediately under launchd (no TTY).
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["JSON_AS_ASCII"] = False
app.jinja_env.add_extension("jinja2.ext.loopcontrols")

# Static asset cache buster: bump on every dashboard restart so users always
# see the latest CSS/JS without manual hard-refresh.
import time as _time
_ASSET_VERSION = str(int(_time.time()))


@app.context_processor
def _inject_asset_version():
    return {"asset_version": _ASSET_VERSION}


# ---------- formatting filters ----------

@app.template_filter("filesize")
def _filesize(n):
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


@app.template_filter("duration")
def _duration(s):
    if not s:
        return "-"
    # minidlna stores as 'H:MM:SS.fff' — trim ms
    return str(s).split(".", 1)[0]


@app.template_filter("ago")
def _ago(epoch):
    import time
    if not epoch:
        return "—"
    delta = time.time() - float(epoch)
    if delta < 0:
        return "just now"
    if delta < 60:
        return f"{int(delta)}秒前"
    if delta < 3600:
        return f"{int(delta // 60)}分钟前"
    if delta < 86400:
        return f"{int(delta // 3600)}小时前"
    return f"{int(delta // 86400)}天前"


@app.template_filter("kind")
def _kind(mime):
    if not mime:
        return "其它"
    if mime.startswith("audio"):
        return "音频"
    if mime.startswith("video"):
        return "视频"
    if mime.startswith("image"):
        return "图片"
    return "其它"


# ---------- helpers ----------

def _media_base_url() -> str:
    host = request.host.split(":")[0]
    return f"http://{host}:8200"


def _dlna_url(detail_id: int, path: str | None, mime: str | None) -> str:
    """The minidlna direct URL — works for projectors/TVs on the LAN, NOT for
    browsers on the same Mac (minidlna's network_interface=en0 rejects
    connections that route via loopback)."""
    ext = db.file_extension(path, mime)
    return f"{_media_base_url()}/MediaItems/{detail_id}.{ext}"


def _stream_url(detail_id: int, *_args, **_kwargs) -> str:
    """In-browser playback URL — served by THIS app directly from disk so it
    works regardless of minidlna's interface binding."""
    return url_for("stream", detail_id=detail_id)


def _is_hevc(info: dict) -> bool:
    """Best-effort guess: minidlna's DLNA_PN field encodes the codec profile."""
    pn = (info.get("DLNA_PN") or "").upper()
    if "H265" in pn or "HEVC" in pn:
        return True
    # minidlna often doesn't set DLNA_PN for HEVC; rely on container hints.
    # The Insta360 source we already verified is HEVC across the board, but
    # we can't know without ffprobe. Default false; the client can fall back.
    return False


def _jellyfin_base() -> str:
    host = request.host.split(":")[0]
    return f"http://{host}:8096"


# ---------- views ----------

@app.route("/")
def index():
    counts = db.counts()
    total = db.total_size()
    media_dirs = config.parse_media_dirs()
    dlna_status = status.fetch_minidlna_status([md.path for md in media_dirs])
    process = status.minidlna_process()
    disk = {}
    for md in media_dirs:
        usage = status.disk_usage_for(md.path)
        if usage:
            disk[md.path] = usage
    recent_video = db.recent(limit=12, kind="video")
    recent_audio = db.recent(limit=8, kind="audio")
    recent_image = db.recent(limit=12, kind="image")
    for item in recent_video + recent_audio + recent_image:
        item["stream_url"] = _stream_url(item["ID"])
        item["dlna_url"] = _dlna_url(item["ID"], item.get("PATH"), item.get("MIME"))

    # Hero slide pool: pick random videos that already have thumbnails (so the
    # backdrop never falls back to a black square). Over-fetch then filter.
    import time as _t
    pool = db.random_videos(limit=40)
    hero_slides: list[dict] = []
    now_ts = _t.time()
    for v in pool:
        if len(hero_slides) >= 10:
            break
        if not thumbs.has_thumb(v["ID"]):
            continue
        ts = float(v.get("TIMESTAMP") or 0)
        days = max(0, int((now_ts - ts) // 86400)) if ts else None
        if days is None:
            memory = ""
        elif days < 30:
            memory = f"{days} 天前的这一刻"
        elif days < 365:
            memory = f"{days // 30} 个月前的回忆"
        else:
            yrs = days // 365
            rem = (days % 365) // 30
            memory = f"{yrs} 年前的回忆" if rem == 0 else f"{yrs} 年 {rem} 个月前的回忆"
        hero_slides.append({
            "id": v["ID"],
            "title": v["TITLE"],
            "duration": str(v.get("DURATION") or "").split(".", 1)[0],
            "resolution": v.get("RESOLUTION") or "",
            "size": v.get("SIZE") or 0,
            "memory": memory,
            "thumb_url": url_for("thumb", detail_id=v["ID"]),
            "stream_url": _stream_url(v["ID"]),
            "dlna_url": _dlna_url(v["ID"], v.get("PATH"), v.get("MIME")),
        })
    hero = hero_slides[0] if hero_slides else None
    return render_template(
        "index.html",
        counts=counts,
        total_size=total,
        dlna_status=dlna_status,
        process=process,
        media_dirs=media_dirs,
        disk=disk,
        recent_video=recent_video,
        recent_audio=recent_audio,
        recent_image=recent_image,
        hero=hero,
        hero_slides=hero_slides,
        watcher=watcher.state_snapshot(),
        thumb_cache=thumbs.cache_stats(),
        db_size=db.db_size(),
        local_ip=status.local_ip(),
    )


PAGE_SIZE = 60


def _decorate(items: list) -> list:
    for it in items:
        it["stream_url"] = _stream_url(it["ID"])
        it["dlna_url"] = _dlna_url(it["ID"], it.get("PATH"), it.get("MIME"))
    return items


VALID_KINDS = {"all", "video", "image", "audio"}


@app.route("/browse")
def browse():
    kind = request.args.get("kind", "all")
    if kind not in VALID_KINDS:
        kind = "all"
    folder = request.args.get("folder")
    q = request.args.get("q", "").strip()
    items: list = []
    folders_list: list = []
    total = 0
    media_roots = [md.path for md in config.parse_media_dirs()]
    if q:
        items = db.search(q, limit=PAGE_SIZE)
        total = db.count_search(q)
    elif folder:
        items = db.items_in_folder(folder, kind, offset=0, limit=PAGE_SIZE)
        total = db.count_in_folder(folder, kind)
    else:
        folders_list = db.folders(kind, media_roots)
    _decorate(items)
    return render_template(
        "browse.html",
        kind=kind, folder=folder, q=q,
        items=items, folders=folders_list,
        total=total, page_size=PAGE_SIZE,
    )


@app.route("/api/items")
def api_items():
    kind = request.args.get("kind", "all")
    if kind not in VALID_KINDS:
        return jsonify({"items": [], "total": 0})
    folder = request.args.get("folder")
    q = request.args.get("q", "").strip()
    try:
        offset = max(0, int(request.args.get("offset", "0")))
    except ValueError:
        offset = 0
    limit = PAGE_SIZE
    if q:
        items = db.search(q, limit=limit + offset)[offset:]
        total = db.count_search(q)
    elif folder:
        items = db.items_in_folder(folder, kind, offset=offset, limit=limit)
        total = db.count_in_folder(folder, kind)
    else:
        items, total = [], 0
    _decorate(items)
    return jsonify({
        "items": [{
            "id": i["ID"],
            "title": i["TITLE"],
            "duration": i.get("DURATION"),
            "resolution": i.get("RESOLUTION"),
            "size": i.get("SIZE"),
            "mime": i.get("MIME"),
            "stream_url": i["stream_url"],
            "dlna_url": i["dlna_url"],
            "thumb_url": url_for("thumb", detail_id=i["ID"]) if (i.get("MIME") or "").startswith(("video", "image")) else None,
            "kind": (
                "video" if (i.get("MIME") or "").startswith("video") else
                "image" if (i.get("MIME") or "").startswith("image") else
                "audio"
            ),
        } for i in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    })


@app.route("/settings")
def settings_page():
    return render_template(
        "settings.html",
        media_dirs=config.parse_media_dirs(),
        friendly_name=config.parse_kv("friendly_name"),
        port=config.parse_kv("port"),
        log=config.log_tail(120),
        watcher=watcher.state_snapshot(),
        process=status.minidlna_process(),
    )


# ---------- streaming ----------

@app.route("/stream/<int:detail_id>")
def stream(detail_id: int):
    """Stream the file directly from disk so it plays in any browser on this
    Mac (minidlna's HTTP server rejects connections that route via loopback)."""
    info = db.item(detail_id)
    if not info or not info.get("PATH") or not os.path.exists(info["PATH"]):
        abort(404)
    return send_file(
        info["PATH"],
        mimetype=info.get("MIME") or "application/octet-stream",
        conditional=True,  # enables HTTP Range / seek
        max_age=0,
    )


# ---------- thumbs & covers ----------

@app.route("/thumb/<int:detail_id>")
def thumb(detail_id: int):
    info = db.item(detail_id)
    if not info:
        abort(404)
    mime = info.get("MIME") or ""
    if not (mime.startswith("video") or mime.startswith("image")):
        abort(404)
    p = thumbs.ensure_thumb(detail_id, info["PATH"], is_image=mime.startswith("image"))
    if not p:
        abort(404)
    return send_file(p, mimetype="image/jpeg", max_age=86400)


@app.route("/cover/<int:detail_id>")
def cover(detail_id: int):
    info = db.item(detail_id)
    if not info:
        abort(404)
    art_id = info.get("ALBUM_ART")
    if not art_id:
        abort(404)
    p = db.album_art_path(art_id)
    if not p or not Path(p).exists():
        abort(404)
    return send_file(p, max_age=86400)


# ---------- JSON APIs ----------

@app.route("/api/status")
def api_status():
    media_dirs = [md.path for md in config.parse_media_dirs()]
    return jsonify({
        "dlna": status.fetch_minidlna_status(media_dirs),
        "watcher": watcher.state_snapshot(),
        "process": status.minidlna_process(),
        "counts": db.counts(),
    })


@app.post("/api/rescan")
def api_rescan():
    ok = watcher.trigger_rescan_now()
    return jsonify({"ok": ok})


@app.post("/api/restart")
def api_restart():
    ok = status.restart_minidlna()
    return jsonify({"ok": ok})


@app.post("/api/add_dir")
def api_add_dir():
    path = (request.form.get("path") or request.json.get("path", "")).strip() if request.form or request.is_json else ""
    types = (request.form.get("types") or (request.json.get("types") if request.is_json else "") or "").strip()
    if not path:
        return jsonify({"ok": False, "error": "path required"}), 400
    if not os.path.isdir(path):
        return jsonify({"ok": False, "error": "directory does not exist or not mounted"}), 400
    config.append_media_dir(path, types)
    status.restart_minidlna()
    return jsonify({"ok": True})


@app.post("/api/remove_dir")
def api_remove_dir():
    path = (request.form.get("path") or (request.json.get("path") if request.is_json else "") or "").strip()
    if not path:
        return jsonify({"ok": False, "error": "path required"}), 400
    removed = config.remove_media_dir(path)
    if removed:
        status.restart_minidlna()
    return jsonify({"ok": removed})


@app.post("/api/watcher")
def api_watcher_toggle():
    enabled = bool((request.json or {}).get("enabled", True))
    watcher.set_enabled(enabled)
    return jsonify({"ok": True, "enabled": enabled})


@app.post("/api/batch_thumbs")
def api_batch_thumbs():
    import threading
    def worker():
        for item in db.all_items("video", limit=10000):
            if not thumbs.has_thumb(item["ID"]):
                thumbs.ensure_thumb(item["ID"], item["PATH"])
    threading.Thread(target=worker, daemon=True, name="batch-thumbs").start()
    return jsonify({"ok": True})


# ---------- launch ----------

def _start_watcher_after_delay() -> None:
    """Start the file watcher after Flask is accepting connections."""
    import time
    time.sleep(1.0)
    try:
        watcher.ensure_running()
        print("[startup] file watcher started", flush=True)
    except Exception as e:
        import traceback
        print(f"[startup] watcher failed: {e!r}\n{traceback.format_exc()}", flush=True)


if __name__ == "__main__":
    threading.Thread(target=_start_watcher_after_delay, daemon=True, name="watcher-deferred-init").start()
    print(f"[startup] minidlna-dashboard binding 0.0.0.0:8201", flush=True)
    app.run(host="0.0.0.0", port=8201, debug=False, use_reloader=False)
