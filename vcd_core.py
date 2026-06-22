import subprocess
import shutil
import json
import sys
import os
import platform
import textwrap
import re
import time
import getpass
import argparse
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse, urljoin, urlencode, parse_qs
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile
from typing import Optional, Callable

# ── third-party ───────────────────────────────────────────────────────────────
import requests
import urllib3
from tqdm import tqdm
from colorama import init as colorama_init, Fore, Style
import random

colorama_init(autoreset=True)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from pyfiglet import Figlet
except ImportError:
    Figlet = None

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import browser_cookie3
    BROWSER_COOKIE3_AVAILABLE = True
except ImportError:
    BROWSER_COOKIE3_AVAILABLE = False

# holds the currently-running ffmpeg subprocess so GUI can kill it on stop
_current_proc: "Optional[subprocess.Popen]" = None

_current_response = None    # streaming response — closed on stop to interrupt download

# ═══════════════════════════════════════════════════════════════════════════════
# Custom exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class VCDError(Exception):
    """Base for all tool‑specific errors."""

class ToolNotFoundError(VCDError):
    """ffmpeg or ffprobe is missing."""

class AuthenticationError(VCDError):
    """Could not log in or session is invalid."""

class DownloadError(VCDError):
    """Download failed or archive is corrupt."""

class MediaProcessingError(VCDError):
    """Something went wrong while reading media / XML."""


# ═══════════════════════════════════════════════════════════════════════════════
# Config dataclasses
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RenderConfig:
    canvas_w: int = 1280
    canvas_h: int = 720
    fps: int = 30
    crf: int = 30
    video_preset: str = "veryfast"
    audio_bitrate: str = "92k"
    padding_ms: int = 2000
    gpu: str = "cpu"   # "cpu" | "nvidia" | "amd" | "intel"


@dataclass
class DownloadConfig:
    verify_ssl: bool = False
    chunk_size: int = 8192
    timeout: int = 60
    headers: dict = field(default_factory=lambda: {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fa,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════════════════════════

LEVEL_COLORS = {
    "INFO":    Fore.GREEN,
    "WARN":    Fore.YELLOW,
    "ERROR":   Fore.RED,
    "SUCCESS": Fore.CYAN,
    "STEP":    Fore.MAGENTA,
    "DEBUG":   Fore.WHITE,
}


def log(msg: str, level: str = "INFO") -> None:
    now = datetime.now().strftime("%H:%M:%S")
    color = LEVEL_COLORS.get(level, Fore.WHITE)
    print(
        f"{Style.DIM}[{now}]{Style.RESET_ALL} "
        f"{color}{level:7s}{Style.RESET_ALL} {msg}",
        flush=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tool discovery
# ═══════════════════════════════════════════════════════════════════════════════

IS_WINDOWS = platform.system() == "Windows"


class ToolManager:
    """Holds validated paths to ffmpeg and ffprobe."""
    def __init__(self, ffmpeg_path: str, ffprobe_path: str):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path


def find_tool(base_name: str) -> Optional[str]:
    """Search for a binary; first in the bundled dir, then PATH."""
    candidates = [base_name]
    if IS_WINDOWS and not base_name.endswith(".exe"):
        candidates.append(base_name + ".exe")

    try:
        bundle_dir = sys._MEIPASS   # type: ignore[attr-defined]
    except AttributeError:
        bundle_dir = os.path.abspath(".")

    for name in candidates:
        p = os.path.join(bundle_dir, name)
        if os.path.isfile(p):
            return p

    for name in candidates:
        found = shutil.which(name)
        if found:
            return found

    return None


def init_tools() -> ToolManager:
    """Locate ffmpeg and ffprobe, exit if not found."""
    ffmpeg = find_tool("ffmpeg")
    ffprobe = find_tool("ffprobe")
    missing = []
    if not ffmpeg:
        missing.append("ffmpeg")
    if not ffprobe:
        missing.append("ffprobe")
    if missing:
        raise ToolNotFoundError(
            f"{', '.join(missing)} not found. Install FFmpeg and add it to PATH."
        )
    log(f"ffmpeg  → {ffmpeg}")
    log(f"ffprobe → {ffprobe}")
    return ToolManager(ffmpeg, ffprobe)


# ═══════════════════════════════════════════════════════════════════════════════
# FFprobe helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _run_ffprobe(ffprobe_path: str, extra_args: list[str], file_path: Path) -> Optional[dict]:
    cmd = [ffprobe_path, "-v", "quiet", "-print_format", "json", *extra_args, str(file_path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return None
        return json.loads(res.stdout)
    except (json.JSONDecodeError, OSError) as exc:
        log(f"ffprobe failed for {file_path.name}: {exc}", "WARN")
        return None


def contains_stream(ffprobe_path: str, file_path: Path, stream_kind: str) -> bool:
    info = _run_ffprobe(ffprobe_path, ["-show_streams"], file_path)
    if not info:
        return False
    return any(s.get("codec_type") == stream_kind for s in info.get("streams", []))


def probe_duration(ffprobe_path: str, file_path: Path) -> float:
    """Return duration in seconds; 0.0 on any error."""
    info = _run_ffprobe(ffprobe_path, ["-show_format"], file_path)
    if not info:
        return 0.0
    try:
        return float(info["format"]["duration"])
    except (KeyError, ValueError, TypeError):
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# FFmpeg runner
# ═══════════════════════════════════════════════════════════════════════════════

def execute_ffmpeg(ffmpeg_path: str, cmd_parts: list[str], description: str = "FFmpeg",
                   duration_sec: Optional[float] = None) -> None:
    log(f"Launching: {description}")
    full_cmd = (
        [ffmpeg_path]
        + ["-progress", "pipe:1", "-nostats", "-loglevel", "quiet"]
        + cmd_parts[1:] if cmd_parts[0] == ffmpeg_path else cmd_parts
    )
    global _current_proc
    proc = subprocess.Popen(full_cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    _current_proc = proc

    pbar = None
    if duration_sec and duration_sec > 0:
        pbar = tqdm(total=int(duration_sec * 1_000_000), unit="µs",
                    desc=description, colour="cyan", smoothing=0.02)

    last_us = 0
    try:
        for line in proc.stdout:
            if "out_time_ms=" in line:
                try:
                    cur = int(line.strip().split("=")[1])
                    if pbar:
                        pbar.update(max(0, cur - last_us))
                        last_us = cur
                except (ValueError, IndexError):
                    pass
            elif "progress=end" in line:
                break
        proc.wait()

    finally:
        _current_proc = None
    
    if pbar:
        pbar.close()

    if proc.returncode != 0:
        raise MediaProcessingError(f"ffmpeg exited with code {proc.returncode}")
    log("FFmpeg finished successfully.", "SUCCESS")


# ═══════════════════════════════════════════════════════════════════════════════
# Retry helper for iranian networks:(
# ═══════════════════════════════════════════════════════════════════════════════

def retry(max_retries: int = 3, backoff_factor: float = 2.0,
          exceptions: tuple = (requests.RequestException,)) -> Callable:
    """Decorator: retry a network call with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries - 1:
                        delay = backoff_factor ** attempt + random.uniform(0, 1)
                        log(f"Retry {attempt+1}/{max_retries} after {delay:.1f}s – {exc}", "WARN")
                        time.sleep(delay)
            raise DownloadError(f"Network request failed after {max_retries} attempts: {last_exc}")
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# Download helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _build_zip_url(meeting_url: str) -> tuple[str, str]:
    parsed = urlparse(meeting_url)
    rid = parsed.path.rstrip("/").split("/")[-1]
    if not rid:
        raise ValueError("Cannot extract recording ID from the URL.")
    base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{base}/{rid}/output/{rid}.zip?download=zip", rid


def _extract_session_from_url(meeting_url: str) -> Optional[str]:
    """If the URL contains a ?session= parameter, return it."""
    parsed = urlparse(meeting_url)
    params = parse_qs(parsed.query)
    token = params.get("session", [None])[0]
    if token:
        log(f"Session token found in URL: {token[:8]}…", "INFO")
    return token


def _looks_like_zip(resp: requests.Response) -> bool:
    """Quick sanity check before saving the file."""
    if resp.status_code != 200:
        log(f"HTTP {resp.status_code} — server refused the request.", "WARN")
        return False

    ct = resp.headers.get("Content-Type", "").lower()
    if "text/html" in ct:
        log("Server returned HTML – probably a login page or error.", "WARN")
        return False

    cl = int(resp.headers.get("Content-Length", 0))
    if cl > 0 and cl < 60_000:
        log(f"Content-Length ({cl} bytes) is too small for a real class ZIP.", "WARN")
        return False

    return True


@retry(max_retries=3, backoff_factor=2.0)
def _stream_to_file(resp: requests.Response, dest: Path,
                    cfg: DownloadConfig) -> None:
    """Download the response body to a file with a progress bar."""
    global _current_response
    _current_response = resp
    total = int(resp.headers.get("content-length", 0))
    try:
        with open(dest, "wb") as fh:
            with tqdm(total=total or None, unit="B", unit_scale=True,
                      desc=f"↓ {dest.name}", colour="#00ff00") as pbar:
                for chunk in resp.iter_content(cfg.chunk_size):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    pbar.update(len(chunk))
    finally:
        _current_response = None    # always clear on exit, success or not


def _try_extract(zip_path: Path, target_dir: Path) -> bool:
    """Extract the ZIP and delete it. Return False if archive is invalid."""
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as arc:
            arc.extractall(target_dir)
        zip_path.unlink(missing_ok=True)
        log(f"Extracted to '{target_dir}'.", "SUCCESS")
        return True
    except (zipfile.BadZipFile, OSError) as exc:
        log(f"ZIP extraction failed: {exc}", "WARN")
        zip_path.unlink(missing_ok=True)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  Authentication
# ═══════════════════════════════════════════════════════════════════════════════

def _make_session(cfg: DownloadConfig) -> requests.Session:
    s = requests.Session()
    s.headers.update(cfg.headers)
    s.verify = cfg.verify_ssl
    return s


# ── Method A – Adobe Connect XML API login ────────────────────────────────────

def _login_via_ac_api(base_url: str, username: str, password: str,
                      cfg: DownloadConfig) -> Optional[requests.Session]:
    """
    Use the official Adobe Connect XML API.
    Returns an authenticated session or None.
    """
    api_url = f"{base_url}/api/xml"
    session = _make_session(cfg)

    # Some servers want a "common-info" call first to set an initial cookie
    try:
        session.get(f"{api_url}?action=common-info", timeout=cfg.timeout)
    except requests.RequestException:
        pass

    params = {"action": "login", "login": username, "password": password}
    try:
        resp = session.get(api_url, params=params, timeout=cfg.timeout)
    except requests.RequestException as exc:
        log(f"[Auth-API] Network error: {exc}", "WARN")
        return None

    try:
        root = ET.fromstring(resp.text)
        status = root.find(".//status")
        if status is None:
            log("[Auth-API] Unexpected XML response.", "WARN")
            return None
        code = status.get("code", "")
        if code == "ok":
            log("[Auth-API] Login successful via XML API.", "SUCCESS")
            return session
        sub = status.get("subcode", "")
        detail = status.get("detail", "")
        log(f"[Auth-API] Login rejected: code={code} sub={sub} detail={detail}", "WARN")
        return None
    except ET.ParseError:
        log("[Auth-API] Response is not XML – server may not support this endpoint.", "WARN")
        return None


# ── Method B – HTML form login ────────────────────────────────────────────────

def _scrape_form_fields(html: str) -> dict[str, str]:
    """Extract all hidden/visible input names and default values."""
    fields: dict[str, str] = {}
    if BS4_AVAILABLE:
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if form:
            for inp in form.find_all("input"):
                name = inp.get("name")
                value = inp.get("value", "")
                itype = inp.get("type", "text").lower()
                if name and itype in ("hidden", "text", "email"):
                    fields[name] = value
    else:
        # Simple regex fallback
        for m in re.finditer(
            r'<input[^>]+name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']',
            html, re.I
        ):
            fields[m.group(1)] = m.group(2)
        for m in re.finditer(
            r'<input[^>]+value=["\']([^"\']*)["\'][^>]*name=["\']([^"\']+)["\']',
            html, re.I
        ):
            fields[m.group(2)] = m.group(1)
    return fields


def _find_form_action(html: str, page_url: str) -> str:
    m = re.search(r'<form[^>]+action=["\']([^"\']+)["\']', html, re.I)
    return urljoin(page_url, m.group(1)) if m else page_url


def _login_via_html_form(login_page_url: str, username: str, password: str,
                         cfg: DownloadConfig) -> Optional[requests.Session]:
    """
    1. GET the login page.
    2. Parse the form.
    3. POST credentials.
    Returns session on success, None otherwise.
    """
    session = _make_session(cfg)
    log(f"[Auth-Form] Fetching login page: {login_page_url}")
    try:
        get_resp = session.get(login_page_url, timeout=cfg.timeout)
    except requests.RequestException as exc:
        log(f"[Auth-Form] Cannot reach login page: {exc}", "WARN")
        return None

    html = get_resp.text
    form_action = _find_form_action(html, login_page_url)
    fields = _scrape_form_fields(html)

    # Possible field names for username / password
    username_keys = ["username", "login", "email", "user", "loginname", "j_username"]
    password_keys = ["password", "pass", "passwd", "j_password", "loginpassword"]

    found_user = next((k for k in username_keys if k in fields), None)
    found_pass = next((k for k in password_keys if k in fields), None)

    fields[found_user or "username"] = username
    fields[found_pass or "password"] = password

    log(f"[Auth-Form] POSTing to: {form_action}")
    # Hide password value in log
    safe_fields = {k: ('***' if 'pass' in k.lower() else v) for k, v in fields.items()}
    log(f"[Auth-Form] Fields: {safe_fields}")

    try:
        post_resp = session.post(
            form_action,
            data=fields,
            timeout=cfg.timeout,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        log(f"[Auth-Form] POST failed: {exc}", "WARN")
        return None

    final_url = post_resp.url
    body_lower = post_resp.text.lower()

    failed_signals = [
        "invalid password", "wrong password", "login failed",
        "نام کاربری", "رمز", "incorrect", "خطا در ورود",
        "authentication failed",
    ]
    if any(sig in body_lower for sig in failed_signals):
        log("[Auth-Form] Login appears to have failed (error text in response).", "WARN")
        return None

    if "login" in final_url.lower() and "logout" not in body_lower:
        log("[Auth-Form] Still on login page after POST – credentials may be wrong.", "WARN")
        return None

    log("[Auth-Form] Form login appears successful.", "SUCCESS")
    return session


# ── Method C – Manual cookie paste  ─────────────────────────────────

def _login_via_manual_cookie(cfg: DownloadConfig,
                              server_domain: str) -> Optional[requests.Session]:
    """
    Ask the user to paste a cookie string (whole header or bare value).
    Returns a session with that cookie set.
    """
    print()
    print(Fore.YELLOW + "━" * 72)
    print(Fore.YELLOW + "  Manual Cookie – quick guide:")
    print(Fore.YELLOW + "━" * 72)
    print(f"""
  1. Log in to Vadana in your browser and open the class page.
  2. Press F12 → Network tab → reload the page (Ctrl+R).
  3. Click any request to {server_domain}.
  4. In "Request Headers", find the "Cookie:" line.
  5. Copy the entire value after "Cookie: " (or just the BREEZESESSION token).
  6. Paste it below.

  ⭐ Easier: If your class link has ?session=…, just pass that URL directly.
""")
    raw = input(Fore.LIGHTMAGENTA_EX + "  Paste Cookie value: " + Style.RESET_ALL).strip()
    if not raw:
        return None

    session = _make_session(cfg)

    if "=" in raw:
        session.headers["Cookie"] = raw
        log("[Auth-Cookie] Using provided cookie string as-is.")
        return session

    # Bare token – try common Adobe Connect cookie names
    ac_names = ["BREEZESESSION", "breeze_session", "session", "JSESSIONID", "PHPSESSID"]
    log(f"[Auth-Cookie] Bare token – trying names: {ac_names}", "WARN")
    for name in ac_names:
        session.cookies.set(name, raw)
    return session


# ── Method D – browser_cookie3 (optional) ─────────────────────────────────────

def _login_via_browser_cookies(domain: str,
                                cfg: DownloadConfig) -> Optional[requests.Session]:
    if not BROWSER_COOKIE3_AVAILABLE:
        return None

    log("[Auth-Browser] Trying to extract cookies from installed browsers…")
    browsers = []
    try:
        browsers.append(("Firefox", browser_cookie3.firefox))
    except Exception:
        pass
    try:
        browsers.append(("Edge", browser_cookie3.edge))
    except Exception:
        pass
    try:
        browsers.append(("Chrome", browser_cookie3.chrome))
    except Exception:
        pass

    for name, loader in browsers:
        try:
            jar = loader(domain_name=domain)
            session = _make_session(cfg)
            session.cookies.update(jar)
            log(f"[Auth-Browser] Loaded cookies from {name}.")
            return session
        except Exception as exc:
            log(f"[Auth-Browser] {name}: {exc}", "WARN")

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Login orchestrator – tries everything in a sensible order
# ═══════════════════════════════════════════════════════════════════════════════

def acquire_authenticated_session(
    meeting_url: str,
    cfg: DownloadConfig,
    manual_cookie: Optional[str] = None,
) -> requests.Session:
    """
    Return an authenticated session, or raise AuthenticationError.
    Order: 0. session token from URL → 1. manual cookie (if given) → 2. browser cookies.
    """
    zip_url, _ = _build_zip_url(meeting_url)

    # 0 – ?session= in URL
    token = _extract_session_from_url(meeting_url)
    if token:
        log("[Auth-0] Trying session token from URL…", "STEP")
        s = _make_session(cfg)
        s.cookies.set("BREEZESESSION", token)
        try:
            r = s.get(zip_url, stream=True, timeout=cfg.timeout)
            if _looks_like_zip(r):
                log("[Auth-0] ✅ Session token valid!", "SUCCESS")
                r.close()
                return s
            log("[Auth-0] Token rejected – it may have expired.", "WARN")
        except requests.RequestException as exc:
            log(f"[Auth-0] Network error: {exc}", "WARN")

    # 1 – manual cookie
    if manual_cookie:
        log("[Auth-1] Trying manual cookie from command line…", "STEP")
        s = _make_session(cfg)
        if "=" in manual_cookie:
            s.headers["Cookie"] = manual_cookie
        else:
            for name in ["BREEZESESSION", "breeze_session"]:
                s.cookies.set(name, manual_cookie)
        try:
            r = s.get(zip_url, stream=True, timeout=cfg.timeout)
            if _looks_like_zip(r):
                log("[Auth-1] ✅ Manual cookie accepted.", "SUCCESS")
                r.close()
                return s
            log("[Auth-1] Manual cookie rejected.", "WARN")
        except requests.RequestException as exc:
            log(f"[Auth-1] Network error: {exc}", "WARN")

    # 2 – interactive cookie paste (fallback)
    log("[Auth-2] Falling back to interactive cookie paste…", "STEP")
    s = _login_via_manual_cookie(cfg, urlparse(meeting_url).netloc)
    if s is not None:
        try:
            r = s.get(zip_url, stream=True, timeout=cfg.timeout)
            if _looks_like_zip(r):
                log("[Auth-2] ✅ Interactive cookie works!", "SUCCESS")
                r.close()
                return s
            log("[Auth-2] Cookie accepted but doesn't grant ZIP access.", "WARN")
        except requests.RequestException as exc:
            log(f"[Auth-2] Network error: {exc}", "WARN")

    raise AuthenticationError(
        "Could not authenticate.\n"
        "  • Make sure you are logged in to the correct Vadana server.\n"
        "  • Copy your BREEZESESSION cookie manually (see instructions above).\n"
        "  • Use the --cookie flag to pass it directly, e.g. --cookie abc123..."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Download orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

def download_and_extract(
    meeting_url: str,
    target_dir: str,
    cfg: DownloadConfig = DownloadConfig(),
    manual_cookie: Optional[str] = None,
) -> Path:
    """
    Authenticate, download the ZIP, extract it.
    Returns the extraction directory Path.
    """
    zip_url, recording_id = _build_zip_url(meeting_url)
    zip_path = Path(f"{recording_id}_dl.zip")
    extract_dir = Path(target_dir)

    log(f"ZIP URL: {zip_url}")

    session = acquire_authenticated_session(meeting_url, cfg, manual_cookie)

    log("Verifying download access…")
    try:
        resp = session.get(zip_url, stream=True, timeout=cfg.timeout)
    except requests.RequestException as exc:
        raise DownloadError(f"Cannot reach download server: {exc}")

    if not _looks_like_zip(resp):
        raise DownloadError(
            "The server did not return a valid ZIP.\n"
            "  • Your session may have expired.\n"
            "  • The class may belong to a different account.\n"
            "  • Re‑run with a fresh BREEZESESSION cookie."
        )

    _stream_to_file(resp, zip_path, cfg)

    if not _try_extract(zip_path, extract_dir):
        # remove the empty folder _try_extract created so next run re-downloads cleanly
        try:
            if extract_dir.exists() and not any(extract_dir.iterdir()):
                extract_dir.rmdir()
        except Exception:
            pass
        raise DownloadError(
            "Downloaded file is not a valid ZIP archive.\n"
            "  • The server might have sent a login page instead.\n"
            "  • Try again with a correct session cookie."
        )

    return extract_dir


# ═══════════════════════════════════════════════════════════════════════════════
# XML timing extraction
# ═══════════════════════════════════════════════════════════════════════════════

def find_base_tick_from_xml(xml_path: Path) -> Optional[int]:
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
    except ET.ParseError as exc:
        log(f"Cannot parse {xml_path.name}: {exc}", "WARN")
        return None

    best_base: Optional[int] = None
    earliest_time = float("inf")

    for elem in root.findall(".//Message"):
        method_el = elem.find("Method")
        if method_el is None or not method_el.text or "pacingTick" not in method_el.text:
            continue
        time_str = elem.get("time")
        number = elem.find("Number")
        if time_str is None or number is None or not number.text:
            continue
        try:
            offset = int(time_str.strip())
            tick = int(number.text.strip())
        except ValueError:
            continue
        if offset < 0:
            continue
        if offset < earliest_time:
            earliest_time = offset
            best_base = tick - offset

    return best_base


def collect_media_intervals(
    media_folder: Path,
    ffprobe_path: str,
) -> tuple[list[dict], list[dict], Optional[int]]:
    xml_files = list(media_folder.glob("*.xml"))
    xml_bases: dict[str, int] = {}

    log("Extracting base ticks from XML …")
    for xp in xml_files:
        b = find_base_tick_from_xml(xp)
        if b is not None:
            xml_bases[xp.stem] = b

    if not xml_bases:
        return [], [], None

    global_base = min(xml_bases.values())
    log(f"Global base tick: {global_base}")

    screen_clips: list[dict] = []
    audio_clips: list[dict] = []

    for flv in sorted(media_folder.glob("*.flv")):
        stem = flv.stem
        if stem not in xml_bases:
            log(f"  ⚠  {flv.name} – no valid pacingTick", "WARN")
            continue

        has_video = contains_stream(ffprobe_path, flv, "video")
        has_audio = contains_stream(ffprobe_path, flv, "audio")
        if not has_video and not has_audio:
            log(f"  ⚠  {flv.name} – no usable stream", "WARN")
            continue

        dur_sec = probe_duration(ffprobe_path, flv)
        if dur_sec <= 0:
            log(f"  ⚠  {flv.name} – zero duration", "WARN")
            continue

        start_ms = max(0.0, xml_bases[stem] - global_base)
        duration_ms = dur_sec * 1000.0
        entry = {
            "file": flv,
            "start_ms": start_ms,
            "end_ms": start_ms + duration_ms,
            "duration_ms": duration_ms,
        }

        if has_video and flv.name.startswith("screenshare"):
            screen_clips.append(entry)
        if has_audio:
            audio_clips.append(entry)

        log(f"   {flv.name}: {start_ms/1000:.1f}s → {entry['end_ms']/1000:.1f}s")

    return screen_clips, audio_clips, global_base


# ═══════════════════════════════════════════════════════════════════════════════
# Timeline builder
# ═══════════════════════════════════════════════════════════════════════════════

def _build_continuous_segments(clips: list[dict], total_ms: float) -> list[dict]:
    bps = sorted({0.0, total_ms} | {c["start_ms"] for c in clips} | {c["end_ms"] for c in clips})
    segs: list[dict] = []
    for i in range(len(bps) - 1):
        s, e = bps[i], bps[i + 1]
        if e <= s:
            continue
        covering = [c for c in clips if c["start_ms"] <= s and c["end_ms"] >= e]
        chosen = max(covering, key=lambda x: x["start_ms"])["file"] if covering else None
        if segs and segs[-1]["file"] == chosen:
            segs[-1]["end"] = e
        else:
            segs.append({"start": s, "end": e, "file": chosen})
    return segs


def _build_audio_mix_segments(audio_clips: list[dict], total_ms: float) -> list[dict]:
    bps = sorted({0.0, total_ms} | {c["start_ms"] for c in audio_clips} | {c["end_ms"] for c in audio_clips})
    segs: list[dict] = []
    for i in range(len(bps) - 1):
        s, e = bps[i], bps[i + 1]
        if e <= s:
            continue
        active = [c for c in audio_clips if c["start_ms"] <= s and c["end_ms"] >= e]
        if segs and segs[-1]["files"] == active:
            segs[-1]["end"] = e
        else:
            segs.append({"start": s, "end": e, "files": active})
    return segs


def write_timeline_xml(
    folder: Path, screen_clips: list[dict], audio_clips: list[dict],
    total_ms: float, out_path: Path,
) -> None:
    v_segs = _build_continuous_segments(screen_clips, total_ms)
    a_segs = _build_audio_mix_segments(audio_clips, total_ms)

    all_t = sorted({s["start"] for s in v_segs + a_segs} | {s["end"] for s in v_segs + a_segs})

    def vid_at(t: float):
        for s in v_segs:
            if s["start"] <= t < s["end"]:
                return s["file"]
        return None

    def aud_at(t: float):
        for s in a_segs:
            if s["start"] <= t < s["end"]:
                return s["files"]
        return []

    fmap: dict = {c["file"]: c["start_ms"] for c in screen_clips + audio_clips}

    root = ET.Element("timeline")
    ET.SubElement(root, "total_duration_ms").text = str(int(total_ms))
    segs_el = ET.SubElement(root, "segments")

    for i in range(len(all_t) - 1):
        t0, t1 = all_t[i], all_t[i + 1]
        if t1 <= t0:
            continue
        mid = (t0 + t1) / 2
        vf = vid_at(mid)
        af = aud_at(mid)
        dur = t1 - t0

        seg = ET.SubElement(segs_el, "segment", start=str(int(t0)), end=str(int(t1)))
        if vf is None:
            ET.SubElement(seg, "video", file="black")
        else:
            ET.SubElement(seg, "video", file=vf.name,
                          offset=str(round((t0 - fmap[vf]) / 1000, 3)),
                          dur=str(round(dur / 1000, 3)))
        if not af:
            ET.SubElement(seg, "audio", file="silence")
        else:
            for ac in af:
                ET.SubElement(seg, "audio", file=ac["file"].name,
                              offset=str(round((t0 - fmap[ac["file"]]) / 1000, 3)),
                              dur=str(round(dur / 1000, 3)))

    pretty = minidom.parseString(ET.tostring(root, encoding="utf-8")).toprettyxml(
        indent="  ", encoding="utf-8"
    )
    out_path.write_bytes(pretty)
    log(f"✅ timeline.xml → {out_path}", "SUCCESS")


# ═══════════════════════════════════════════════════════════════════════════════
# FilterGraphBuilder – helper for ffmpeg filter chains
# ═══════════════════════════════════════════════════════════════════════════════

class FilterGraphBuilder:
    def __init__(self):
        self._p: list[str] = []

    def add(self, s: str) -> "FilterGraphBuilder":
        self._p.append(s.rstrip(";"))
        return self

    def build(self) -> str:
        return ";".join(self._p)


# ═══════════════════════════════════════════════════════════════════════════════
# Timeline reader & renderer
# ═══════════════════════════════════════════════════════════════════════════════

def _read_timeline_xml(path: Path) -> tuple[list[dict], dict, int]:
    tree = ET.parse(str(path))
    root = tree.getroot()
    total_ms = int(root.find("total_duration_ms").text)  # type: ignore
    video_plan: list[dict] = []
    audio_meta: dict[str, dict] = {}

    for seg in root.findall(".//segment"):
        ss = int(seg.get("start"))  # type: ignore
        se = int(seg.get("end"))    # type: ignore
        ve = seg.find("video")
        vf = ve.get("file") if ve is not None else "black"
        if vf and vf != "black":
            vo = float(ve.get("offset", 0))    # type: ignore
            vd = float(ve.get("dur", (se - ss) / 1000))  # type: ignore
        else:
            vo, vf, vd = None, "black", (se - ss) / 1000
        video_plan.append({"start_ms": ss, "end_ms": se, "file": vf, "offset": vo, "dur": vd})

        for ae in seg.findall("audio"):
            af = ae.get("file")
            if af == "silence":
                continue
            sd = float(ae.get("dur", (se - ss) / 1000)) * 1000
            om = float(ae.get("offset", 0)) * 1000
            if af not in audio_meta:
                audio_meta[af] = {"first_start_ms": ss, "first_offset_ms": om,
                                  "latest_end_ms": ss + sd}
            else:
                info = audio_meta[af]
                if ss < info["first_start_ms"]:
                    info["first_start_ms"] = ss
                    info["first_offset_ms"] = om
                info["latest_end_ms"] = max(info["latest_end_ms"], ss + sd)
    return video_plan, audio_meta, total_ms


def _video_encoder_args(cfg: "RenderConfig") -> list:
    """Return the FFmpeg video encoder CLI args based on cfg.gpu.

    CPU uses libx264 + CRF (same as before).
    GPU encoders use hardware-specific quality params roughly equivalent to CRF.
    """
    _nvenc_preset = {
        "ultrafast": "p1", "superfast": "p2", "veryfast": "p3",
        "faster": "p3", "fast": "p4", "medium": "p4",
        "slow": "p5", "slower": "p6",
    }
    if cfg.gpu == "nvidia":
        return [
            "-c:v", "h264_nvenc",
            "-preset", _nvenc_preset.get(cfg.video_preset, "p4"),
            "-rc", "vbr",
            "-cq", str(cfg.crf),
            "-b:v", "0",
        ]
    if cfg.gpu == "amd":
        return [
            "-c:v", "h264_amf",
            "-quality", "balanced",
            "-rc", "cqp",
            "-qp_i", str(cfg.crf),
            "-qp_p", str(cfg.crf),
            "-qp_b", str(cfg.crf),
        ]
    if cfg.gpu == "intel":
        return [
            "-c:v", "h264_qsv",
            "-preset", cfg.video_preset,
            "-global_quality", str(cfg.crf),
        ]
    # default: CPU libx264
    return [
        "-c:v", "libx264",
        "-preset", cfg.video_preset,
        "-crf", str(cfg.crf),
    ]


def render_video_from_timeline(
    tools: ToolManager,
    media_folder: Path,
    timeline_path: Path,
    output_video: Path,
    cfg: RenderConfig = RenderConfig(),
) -> None:
    video_plan, audio_meta, total_ms = _read_timeline_xml(timeline_path)
    total_sec = total_ms / 1000.0

    done: set[str] = set()
    video_srcs: list[dict] = []
    for seg in video_plan:
        fn = seg["file"]
        if fn == "black" or fn in done:
            continue
        rows = [s for s in video_plan if s["file"] == fn]
        video_srcs.append({"file": media_folder / fn,
                            "start_ms": min(r["start_ms"] for r in rows),
                            "end_ms":   max(r["end_ms"]   for r in rows)})
        done.add(fn)

    audio_srcs = [{"file": media_folder / fn,
                   "start_ms": i["first_start_ms"],
                   "end_ms":   i["latest_end_ms"]}
                  for fn, i in audio_meta.items()]

    video_srcs.sort(key=lambda x: x["start_ms"])
    audio_srcs.sort(key=lambda x: x["start_ms"])
    nv, na = len(video_srcs), len(audio_srcs)

    cmd = [tools.ffmpeg, "-y"]
    cmd += ["-f", "lavfi", "-i",
            f"color=c=black:s={cfg.canvas_w}x{cfg.canvas_h}:r={cfg.fps}:d={total_sec},format=yuv420p"]
    for vs in video_srcs:
        cmd += ["-i", str(vs["file"])]
    for as_ in audio_srcs:
        cmd += ["-i", str(as_["file"])]
    silence_idx = 1 + nv + na
    cmd += ["-f", "lavfi", "-i",
            f"anullsrc=channel_layout=stereo:sample_rate=44100:duration={total_sec}"]

    fb = FilterGraphBuilder()

    if nv > 0:
        for idx, vs in enumerate(video_srcs):
            fb.add(f"[{1+idx}:v]"
                   f"scale={cfg.canvas_w}:{cfg.canvas_h}:force_original_aspect_ratio=decrease,"
                   f"pad={cfg.canvas_w}:{cfg.canvas_h}:(ow-iw)/2:(oh-ih)/2,"
                   f"setsar=1,format=rgba,"
                   f"setpts=PTS-STARTPTS+{vs['start_ms']/1000}/TB[v{idx}]")
        prev = "[0:v]"
        for idx in range(nv):
            lbl = f"vo{idx}" if idx < nv - 1 else "vout"
            fb.add(f"{prev}[v{idx}]overlay=0:0[{lbl}]")
            prev = f"[{lbl}]"
    else:
        fb.add("[0:v]null[vout]")

    alabs: list[str] = []
    for idx, as_ in enumerate(audio_srcs):
        lbl = f"a{idx}"
        fb.add(f"[{1+nv+idx}:a]"
               f"asetpts=PTS-STARTPTS,"
               f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
               f"adelay={int(as_['start_ms'])}|{int(as_['start_ms'])}:all=1[{lbl}]")
        alabs.append(f"[{lbl}]")

    fb.add(f"[{silence_idx}:a]"
           f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[silence]")
    alabs.append("[silence]")
    fb.add(f"{''.join(alabs)}amix=inputs={len(alabs)}:duration=longest:dropout_transition=0[outa]")

    cmd += [
        "-filter_complex", fb.build(),
        "-map", "[vout]", "-map", "[outa]",
        # "-c:v", "libx264", "-preset", cfg.video_preset, "-crf", str(cfg.crf),
        *_video_encoder_args(cfg),
        "-c:a", "aac", "-b:a", cfg.audio_bitrate,
        "-movflags", "+faststart", "-avoid_negative_ts", "make_zero",
        str(output_video),
    ]

    execute_ffmpeg(tools.ffmpeg, cmd, "Merging final video", duration_sec=total_sec)
    log(f"🎉 Final video: {output_video}", "SUCCESS")


# ═══════════════════════════════════════════════════════════════════════════════
# Main processing pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def process_recording(
    tools: ToolManager,
    folder_path: str,
    output_video: str = "synced_class.mp4",
    xml_only: bool = False,
    cfg: RenderConfig = RenderConfig(),
) -> None:
    folder = Path(folder_path)
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    sc, ac, _ = collect_media_intervals(folder, tools.ffprobe)
    if not sc and not ac:
        raise MediaProcessingError("No media files with a valid pacingTick were found.")

    total_ms = max((c["end_ms"] for c in sc + ac), default=0.0) + cfg.padding_ms
    xml_path = folder / "timeline.xml"

    log("Generating timeline.xml …", "STEP")
    write_timeline_xml(folder, sc, ac, total_ms, xml_path)
    if xml_only:
        return

    log("Assembling video …", "STEP")
    render_video_from_timeline(tools, folder, xml_path, Path(output_video), cfg)


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def _print_rgb_banner(text: str) -> None:
    """Print the banner text cycling through rainbow colors."""
    colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA]
    for i, line in enumerate(text.splitlines()):
        color = colors[i % len(colors)]
        print(color + line.center(shutil.get_terminal_size((80, 24)).columns) + Style.RESET_ALL)
        time.sleep(0.08)  # gentle animation


if __name__ == "__main__":
    # ── Parse arguments (ignore Jupyter's -f flag) ─────────────────────────
    parser = argparse.ArgumentParser(
        description="VCD – Vadana Class Downloader & Sync Tool (v0.2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        examples:
          %(prog)s "https://vadavc32.ec.iau.ir/lasqwynd9xye/?session=ABC123&proto=true"
          %(prog)s --cookie "BREEZESESSION=abc123..." "https://..."
          %(prog)s --output my_class.mp4 "https://..."
        """),
    )
    parser.add_argument("url", nargs="?", default=None,
                        help="Full class URL (with ?session= is best). "
                             "If omitted, you will be prompted.")
    parser.add_argument("--output", "-o", default=None,
                        help="Output MP4 filename (default: Class-<id>.mp4)")
    parser.add_argument("--cookie",
                        help="BREEZESESSION value or full cookie string")
    parser.add_argument("--xml-only", action="store_true",
                        help="Only generate timeline.xml, don't render video")
    parser.add_argument("--crf", type=int, default=30,
                        help="Video quality (CRF, lower=better, default 30)")
    parser.add_argument("--fps", type=int, default=30,
                        help="Output frame rate")

    args, unknown = parser.parse_known_args()
    # Filter out Jupyter/IPython connection file flag
    cleaned_unknown = []
    skip = False
    for u in unknown:
        if skip:
            skip = False
            continue
        if u == "-f":
            skip = True
            continue
        cleaned_unknown.append(u)
    if cleaned_unknown:
        log(f"Ignoring unknown arguments: {' '.join(cleaned_unknown)}", "WARN")

    # ── Tools (must exist before anything else) ────────────────────────────
    try:
        tools = init_tools()
    except ToolNotFoundError as exc:
        log(str(exc), "ERROR")
        sys.exit(1)

    # ── Banner & Description (ALWAYS first thing the user sees) ────────────
    tw = shutil.get_terminal_size((80, 24)).columns
    if Figlet:
        banner_text = Figlet(font="slant").renderText("VCD - v0.2")
    else:
        banner_text = "VCD - v0.2"
    _print_rgb_banner(banner_text)

    desc = ("v0.2 — HTTP‑native login. "
            "Screenshare + audio classes. Whiteboard/file support: coming soo..")
    print(Style.DIM + Fore.CYAN + desc.center(tw) + Style.RESET_ALL)
    print()

    # ── URL prompt (if needed) ─────────────────────────────────────────────
    if not args.url or not args.url.startswith(("http://", "https://")):
        if args.url:
            log(f"Ignoring non-URL argument: {args.url}", "WARN")
        print()
        print(Fore.LIGHTMAGENTA_EX
              + "Enter class URL (full URL with ?session= is best):",
              flush=True)
        print("  e.g. https://vadavc32.ec.iau.ir/lasqwynd9xye/"
              "?session=adminbreezcdu7pad2xwpfe39a&proto=true", flush=True)
        print("  or just: https://vadavc32.ec.iau.ir/lasqwynd9xye", flush=True)
        args.url = input("> " + Style.RESET_ALL).strip()
        args.url = args.url.strip()
        if not args.url.startswith(("http://", "https://")):
            log("ERROR: The URL must start with http:// or https://", "ERROR")
            sys.exit(1)
        # remove any accidentally pasted control characters
        import re
        args.url = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', args.url)
        if not args.url.startswith(("http://", "https://")):
            log("ERROR: The provided URL does not look like a web address.", "ERROR")
            sys.exit(1)

    # ── Recording ID ───────────────────────────────────────────────────────
    try:
        parsed = urlparse(args.url)
        rid = parsed.path.rstrip("/").split("/")[-1]
        if not rid:
            raise ValueError("Could not extract recording ID")
    except Exception as e:
        log(f"Failed to parse the URL: {e}", "ERROR")
        sys.exit(1)
    rid = parsed.path.rstrip("/").split("/")[-1]
    if not rid:
        log("Could not parse recording ID from the URL.", "ERROR")
        sys.exit(1)

    working_dir = rid
    result_dir: Optional[Path] = None

    # ── Download or reuse ──────────────────────────────────────────────────
    if Path(working_dir).is_dir():
        log(f"Folder '{working_dir}' already exists – skipping download.")
        result_dir = Path(working_dir)
    else:
        try:
            result_dir = download_and_extract(
                args.url, working_dir, DownloadConfig(), args.cookie
            )
        except (DownloadError, AuthenticationError) as exc:
            log(str(exc), "ERROR")
            sys.exit(1)
        except Exception as exc:
            log(f"Unexpected error during download: {exc}", "ERROR")
            sys.exit(1)

    # ── Process ────────────────────────────────────────────────────────────
    output_file = args.output or f"Class-{rid}.mp4"
    render_cfg = RenderConfig(crf=args.crf, fps=args.fps)

    try:
        process_recording(tools, str(result_dir), output_file,
                          args.xml_only, render_cfg)
    except (MediaProcessingError, FileNotFoundError) as exc:
        log(str(exc), "ERROR")
        sys.exit(1)

    log("All done. 🎓", "SUCCESS")

# VCD-v0.2
