import re
import os
import shutil


def _tobool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on")


_BPS_RE = re.compile(r"([\d.]+)\s*([kKmMgG]?[Bb])/s")


def _parse_bps(s: str) -> float:
    m = _BPS_RE.search(s)
    if not m:
        return 0.0
    val, unit = float(m.group(1)), m.group(2).upper()
    return val * {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}.get(unit, 1)


def _fmt_bytes(n: float) -> str:
    for unit, thr in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= thr:
            return f"{n / thr:.1f} {unit}"
    return f"{n:.0f} B"


def _fmt_dur(secs) -> str:
    s = int(float(secs))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _fmt_size(path: str) -> str:
    try:
        return _fmt_bytes(os.path.getsize(path))
    except Exception:
        return "?"


def _disk_free(directory: str) -> tuple:
    try:
        free = shutil.disk_usage(directory).free
        return free / (1024 * 1024) >= 500, _fmt_bytes(free) + " free"
    except Exception:
        return True, ""
