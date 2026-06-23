# Authentication
from typing import Optional

from colorama import Fore, Style
import requests

from vcd.core.network import DownloadConfig
from vcd.core.logging import log


def _make_session(cfg: DownloadConfig) -> requests.Session:
    s = requests.Session()
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
