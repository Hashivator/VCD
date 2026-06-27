# Authentication
from typing import Optional
from urllib.parse import parse_qs, urlparse

import niquests as requests
from colorama import Fore, Style

from vcd.core.config import DownloadConfig
from vcd.core.exceptions import AuthenticationError
from vcd.logger import log


def _make_session(cfg: DownloadConfig) -> requests.Session:
    s = requests.Session(multiplexed=True)
    s.headers.update(cfg.headers)
    s.verify = cfg.verify_ssl
    return s


def _login_via_manual_cookie(
    cfg: DownloadConfig, server_domain: str
) -> Optional[requests.Session]:
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
    raw = input(
        Fore.LIGHTMAGENTA_EX + "  Paste Cookie value: " + Style.RESET_ALL
    ).strip()
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


# Login orchestrator
def acquire_authenticated_session(
    meeting_url: str,
    cfg: DownloadConfig,
    manual_cookie: Optional[str] = None,
) -> requests.Session:
    """
    Return an authenticated session, or raise AuthenticationError.
    Order: 0. session token from URL → 1. manual cookie (if given) → 2. browser cookies.
    """
    from vcd.core.network import _build_zip_url, _looks_like_zip

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


def _extract_session_from_url(meeting_url: str) -> Optional[str]:
    """If the URL contains a ?session= parameter, return it."""
    parsed = urlparse(meeting_url)
    params = parse_qs(parsed.query)
    token = params.get("session", [None])[0]
    if token:
        log(f"Session token found in URL: {token[:8]}…", "INFO")
    return token
