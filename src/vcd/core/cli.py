import argparse
import re
import shutil
import sys
import textwrap
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from colorama import Fore, Style

from vcd.core.config import DownloadConfig, RenderConfig
from vcd.core.exceptions import (
    AuthenticationError,
    DownloadError,
    MediaProcessingError,
    ToolNotFoundError,
)
from vcd.core.media import init_tools, process_recording
from vcd.core.network import Downloader
from vcd.logger import log

try:
    from pyfiglet import Figlet
except ImportError:
    Figlet = None

downloader = Downloader()


def _print_rgb_banner(text: str) -> None:
    """Print the banner text cycling through rainbow colors."""
    colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA]
    for i, line in enumerate(text.splitlines()):
        color = colors[i % len(colors)]
        print(
            color
            + line.center(shutil.get_terminal_size((80, 24)).columns)
            + Style.RESET_ALL
        )
        time.sleep(0.08)  # gentle animation


def main():
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
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Full class URL (with ?session= is best). "
        "If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output MP4 filename (default: Class-<id>.mp4)",
    )
    parser.add_argument("--cookie", help="BREEZESESSION value or full cookie string")
    parser.add_argument(
        "--xml-only",
        action="store_true",
        help="Only generate timeline.xml, don't render video",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=30,
        help="Video quality (CRF, lower=better, default 30)",
    )
    parser.add_argument("--fps", type=int, default=30, help="Output frame rate")

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

    desc = (
        "v0.2 — HTTP‑native login. "
        "Screenshare + audio classes. Whiteboard/file support: coming soo.."
    )
    print(Style.DIM + Fore.CYAN + desc.center(tw) + Style.RESET_ALL)
    print()

    # ── URL prompt (if needed) ─────────────────────────────────────────────
    if not args.url or not args.url.startswith(("http://", "https://")):
        if args.url:
            log(f"Ignoring non-URL argument: {args.url}", "WARN")
        print()
        print(
            Fore.LIGHTMAGENTA_EX + "Enter class URL (full URL with ?session= is best):",
            flush=True,
        )
        print(
            "  e.g. https://vadavc32.ec.iau.ir/lasqwynd9xye/"
            "?session=adminbreezcdu7pad2xwpfe39a&proto=true",
            flush=True,
        )
        print("  or just: https://vadavc32.ec.iau.ir/lasqwynd9xye", flush=True)
        args.url = input("> " + Style.RESET_ALL).strip()
        args.url = args.url.strip()
        if not args.url.startswith(("http://", "https://")):
            log("ERROR: The URL must start with http:// or https://", "ERROR")
            sys.exit(1)

        args.url = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", args.url)
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
            result_dir = downloader.download_and_extract(
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
        process_recording(
            tools, str(result_dir), output_file, args.xml_only, render_cfg
        )
    except (MediaProcessingError, FileNotFoundError) as exc:
        log(str(exc), "ERROR")
        sys.exit(1)

    log("All done. 🎓", "SUCCESS")
