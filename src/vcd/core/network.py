import random
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import niquests as requests
from niquests.packages.urllib3.exceptions import InsecureRequestWarning
from tqdm import tqdm

from vcd.core.auth import acquire_authenticated_session
from vcd.core.config import DownloadConfig
from vcd.core.exceptions import DownloadError
from vcd.logger import log

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class Downloader:
    def __init__(self):
        # Instance variable replaces the global _current_response
        self._response: Optional[requests.Response] = None

    def cancel(self):
        """Immediately interrupt the network socket if open."""
        if self._response:
            self._response.close()

    def stream_to_file(
        self,
        resp: requests.Response,
        dest: Path,
        chunk_size: int,
        progress_cb: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Download the response body to a file, emitting native progress."""
        self._response = resp
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        try:
            with open(dest, "wb") as fh:
                # iter_content will immediately raise an error if self.cancel() is called
                for chunk in resp.iter_content(chunk_size):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    downloaded += len(chunk)

                    # Fire the callback to update the GUI natively (No Regex)
                    if progress_cb and total > 0:
                        pct = int((downloaded / total) * 100)
                        progress_cb(max(0, min(100, pct)))
        finally:
            self._response = None

    def download_and_extract(
        self,
        url: str,
        target_dir: Path,
        session: requests.Session,
        cfg: DownloadConfig,
        progress_cb: Optional[Callable[[int], None]] = None,
    ) -> Path:
        """
        Authenticates, streams the ZIP to disk, and extracts it.
        """
        zip_url, recording_id = _build_zip_url(url)
        zip_path = Path(f"{recording_id}_dl.zip")

        log(f"ZIP URL: {zip_url}")
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
                "  • Re-run with a fresh BREEZESESSION cookie."
            )

        # Execute the stream. The progress callback routes straight to PySide6.
        self.stream_to_file(resp, zip_path, cfg.chunk_size, progress_cb)

        if not _try_extract(zip_path, target_dir):
            try:
                if target_dir.exists() and not any(target_dir.iterdir()):
                    target_dir.rmdir()
            except Exception:
                pass
            raise DownloadError(
                "Downloaded file is not a valid ZIP archive.\n"
                "  • The server might have sent a login page instead.\n"
                "  • Try again with a correct session cookie."
            )

        return target_dir


# Retry helper for iranian networks
def retry(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    exceptions: tuple = (requests.RequestException,),
) -> Callable:
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
                        delay = backoff_factor**attempt + random.uniform(0, 1)
                        log(
                            f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s – {exc}",
                            "WARN",
                        )
                        time.sleep(delay)
            raise DownloadError(
                f"Network request failed after {max_retries} attempts: {last_exc}"
            )

        return wrapper

    return decorator


# Download helpers
def _build_zip_url(meeting_url: str) -> tuple[str, str]:
    parsed = urlparse(meeting_url)
    rid = parsed.path.rstrip("/").split("/")[-1]
    if not rid:
        raise ValueError("Cannot extract recording ID from the URL.")
    base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{base}/{rid}/output/{rid}.zip?download=zip", rid


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
def _stream_to_file(resp: requests.Response, dest: Path, cfg: DownloadConfig) -> None:
    """Download the response body to a file with a progress bar."""
    global _current_response
    _current_response = resp
    total = int(resp.headers.get("content-length", 0))
    try:
        with open(dest, "wb") as fh:
            with tqdm(
                total=total or None,
                unit="B",
                unit_scale=True,
                desc=f"↓ {dest.name}",
                colour="#00ff00",
            ) as pbar:
                for chunk in resp.iter_content(cfg.chunk_size):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    pbar.update(len(chunk))
    finally:
        _current_response = None  # always clear on exit, success or not


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
