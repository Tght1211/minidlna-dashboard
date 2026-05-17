"""minidlna runtime status — derived from fs and process state, since the HTTP
status page rejects local connections (network_interface=en0 binding only)."""
from __future__ import annotations

import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

MINIDLNA_PORT = 8200
MINIDLNAD = "/opt/homebrew/opt/minidlna/sbin/minidlnad"


def _running_pids() -> list[int]:
    try:
        r = subprocess.run(["pgrep", "-f", "minidlnad"], capture_output=True, text=True, timeout=2)
        return [int(p) for p in r.stdout.split() if p.isdigit()]
    except Exception:
        return []


def _lsof_for(pid: int, args: list[str]) -> str:
    try:
        r = subprocess.run(["lsof", "-p", str(pid), *args], capture_output=True, text=True, timeout=3)
        return r.stdout
    except Exception:
        return ""


def _scan_in_progress(pid: int, media_dirs: list[str]) -> bool:
    """True if minidlnad currently has open file descriptors inside any media_dir."""
    if not pid or not media_dirs:
        return False
    out = _lsof_for(pid, [])
    for line in out.splitlines():
        if any(md in line for md in media_dirs):
            return True
    return False


def _established_connections() -> list[dict[str, str]]:
    """Return list of established TCP connections TO our DLNA port from remote IPs."""
    try:
        r = subprocess.run(
            ["lsof", "-nP", "-iTCP", "-sTCP:ESTABLISHED"],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return []
    clients: dict[str, dict[str, str]] = {}
    for line in r.stdout.splitlines():
        if "minidlnad" not in line:
            continue
        parts = line.split()
        if len(parts) < 9:
            continue
        name = parts[8]  # e.g., 192.168.12.100:8200->192.168.12.115:54321
        if "->" not in name:
            continue
        local, remote = name.split("->", 1)
        remote_ip = remote.split(":", 1)[0]
        local_port = local.rsplit(":", 1)[-1]
        if local_port != str(MINIDLNA_PORT):
            continue
        c = clients.setdefault(remote_ip, {"ip": remote_ip, "connections": 0})
        c["connections"] = int(c["connections"]) + 1
    return list(clients.values())


def fetch_minidlna_status(media_dirs: list[str] | None = None) -> dict[str, Any]:
    pids = _running_pids()
    pid = pids[0] if pids else 0
    return {
        "reachable": bool(pid),
        "scan_in_progress": _scan_in_progress(pid, media_dirs or []),
        "clients": _established_connections() if pid else [],
        "version": _version_string(),
    }


_VERSION_CACHE: dict[str, str] = {}


def _version_string() -> str:
    if "v" in _VERSION_CACHE:
        return _VERSION_CACHE["v"]
    try:
        r = subprocess.run([MINIDLNAD, "-V"], capture_output=True, text=True, timeout=2)
        v = r.stdout.strip() or r.stderr.strip() or "MiniDLNA"
    except Exception:
        v = "MiniDLNA"
    _VERSION_CACHE["v"] = v
    return v


def disk_usage_for(path: str) -> dict[str, int] | None:
    try:
        usage = shutil.disk_usage(path)
        return {"total": usage.total, "used": usage.used, "free": usage.free}
    except OSError:
        return None


def minidlna_process() -> dict[str, Any] | None:
    """Return PID + start epoch + uptime seconds for the running minidlnad, or None."""
    try:
        pid_out = subprocess.run(
            ["pgrep", "-f", "minidlnad"], capture_output=True, text=True, timeout=2
        )
        pids = [p for p in pid_out.stdout.split() if p.isdigit()]
        if not pids:
            return None
        pid = pids[0]
        ps_out = subprocess.run(
            ["ps", "-p", pid, "-o", "lstart=,etime="],
            capture_output=True, text=True, timeout=2,
        )
        parts = ps_out.stdout.strip().rsplit(None, 1)
        if len(parts) != 2:
            return {"pid": int(pid), "started": None, "etime": None}
        lstart, etime = parts[0], parts[1]
        return {"pid": int(pid), "started": lstart, "etime": etime}
    except Exception:
        return None


def local_ip() -> str:
    """Best-effort LAN IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def hup_minidlna() -> bool:
    """Send SIGHUP to minidlnad to trigger config reload + rescan."""
    try:
        subprocess.run(["pkill", "-HUP", "-f", "minidlnad"], timeout=2, check=False)
        return True
    except Exception:
        return False


def restart_minidlna() -> bool:
    """Use brew services to restart minidlna."""
    try:
        r = subprocess.run(
            ["/opt/homebrew/bin/brew", "services", "restart", "minidlna"],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0
    except Exception:
        return False
