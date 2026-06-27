import random
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import niquests as requests

from vcd.core.config import DownloadConfig
from vcd.core.exceptions import DownloadError
from vcd.logger import log


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


class Downloader:
    def __init__(self):
        self._response: Optional[requests.Response] = None

    def cancel(self):
        """Immediately interrupt the network socket if open."""
        if self._response:
            self._response.close()

    @retry(max_retries=3, backoff_factor=2.0)
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

        last_pct = -1

        try:
            with open(dest, "wb", buffering=chunk_size) as fh:
                for chunk in resp.iter_content(chunk_size):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    downloaded += len(chunk)

                    if progress_cb and total > 0:
                        pct = int((downloaded / total) * 100)
                        if pct != last_pct:
                            progress_cb(max(0, min(100, pct)))
                            last_pct = pct
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
        """Authenticates, streams the ZIP to disk, and extracts it."""
        zip_url, recording_id = _build_zip_url(url)

        zip_path = target_dir.parent / f"{recording_id}_dl.zip"

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
