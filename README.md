<h1 align="center">
  <br>
  <a href="https://github.com/IAUCourseExp/VCD">
    <img src="https://raw.githubusercontent.com/IAUCourseExp/VCD/main/vcd0.4.png" alt="VCD – Vadana Class Downloader" width="900">
  </a>
  <br>
  VCD – Vadana Class Downloader
  <br>
</h1>

<p align="center">
  Download, sync, and render Adobe Connect (Vadana) class recordings into a single MP4.<br>
  Screenshare + audio &nbsp;·&nbsp; GPU-accelerated &nbsp;·&nbsp; Batch queue
</p>

<p align="center">
  <a href="https://github.com/IAUCourseExp/VCD/releases/latest">
    <img src="https://img.shields.io/github/v/release/IAUCourseExp/VCD?style=flat-square&label=release" alt="Release">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square" alt="Python">
  </a>
  <a href="https://github.com/IAUCourseExp/VCD/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/IAUCourseExp/VCD?style=flat-square" alt="License">
  </a>
  <a href="https://github.com/IAUCourseExp/VCD/stargazers">
    <img src="https://img.shields.io/github/stars/IAUCourseExp/VCD?style=flat-square" alt="Stars">
  </a>
  <a href="https://github.com/IAUCourseExp/VCD/issues">
    <img src="https://img.shields.io/github/issues/IAUCourseExp/VCD?style=flat-square" alt="Issues">
  </a>
  <a href="https://github.com/IAUCourseExp/VCD/network/members">
    <img src="https://img.shields.io/github/forks/IAUCourseExp/VCD?style=flat-square" alt="Forks">
  </a>
</p>

<p align="center">
  <a href="#overview">Overview</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#features">Features</a> ·
  <a href="#requirements">Requirements</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#how-it-works">How It Works</a> ·
  <a href="#output">Output</a> ·
  <a href="#troubleshooting">Troubleshooting</a> ·
  <a href="#changelog">Changelog</a>
</p>

<p align="center">
  <a href="https://t.me/IAUCourseExp">@IAUCourseExp</a>
  &nbsp;·&nbsp;
  <a href="https://t.me/JozveIAU">@JozveIAU</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/IAUCourseExp/VCD">⭐ Star this project ⭐</a>
</p>

---

## Overview

IAU Azad University's Vadana platform is built on Adobe Connect. Class recordings are stored as a ZIP archive of FLV video segments and XML timing files — not a single watchable video. Reconstructing those pieces into one correctly-synchronised MP4, with screenshare overlaid on audio and all timing offsets precisely applied, is what VCD does.

The tool covers the full pipeline: authentication, download with resume support, millisecond-accurate timeline extraction from Adobe Connect's internal `pacingTick` format, and FFmpeg rendering with hardware GPU acceleration.

**Two subpackages, one job:**

| Package | Role |
|---------|------|
| `src/vcd/core/` | Download and render engine — runs standalone as a CLI |
| `src/vcd/gui/` | PySide6 desktop GUI — wraps core via MVC without modifying its logic |

---

## Architecture

The codebase has one hard rule: **the GUI never modifies core's logic.** `vcd.gui` uses an MVC architecture where the `Worker` intercepts `sys.stdout`/`sys.stderr` to capture core's `log()` output and `tqdm` progress bars, converting them into Qt signals that drive UI updates. Core runs in a background `QThread` and knows nothing about the GUI.

### Package layout

```
src/vcd/
├── logger.py                  shared timestamped, colour-coded logging
├── core/
│   ├── auth.py                acquire_authenticated_session() — auth chain
│   ├── cli.py                 CLI entry point (argparse)
│   ├── config.py              RenderConfig, DownloadConfig dataclasses
│   ├── exceptions.py          VCDError hierarchy
│   ├── media.py               Renderer, FilterGraphBuilder, render_video_from_timeline()
│   ├── network.py             Downloader — HTTPS stream, Range resume, ZIP extraction
│   └── timeline.py            pacingTick XML → timeline.xml
└── gui/
    ├── main.py                GUI entry point
    ├── constants.py           palette, QSS theme, presets, icons
    ├── controllers/
    │   └── main_controller.py MainController — MVC orchestrator
    ├── managers/
    │   ├── settings_manager.py  QSettings persistence
    │   └── tray_manager.py      system tray + notifications
    ├── models/
    │   ├── history_db.py      JobHistoryDB (~/.vcd/history.json)
    │   └── queue_manager.py   in-memory batch queue
    ├── views/
    │   ├── main_window.py     top-level QMainWindow
    │   └── tabs/              left_panel, log_tab, history_tab, files_tab
    ├── widgets/
    │   ├── speed_graph.py     real-time speed sparkline
    │   ├── starfield.py       animated background
    │   └── stats_panel.py     elapsed · bytes · ETA · speed graph
    ├── workers/
    │   └── async_worker.py    Worker + _StreamRouter (QThread bridge)
    └── utils/
        └── formatters.py      string formatting helpers
```

### System diagram

```
┌───────────────────────────────────────────────────────────────────┐
│  src/vcd/gui/  —  PySide6 Desktop GUI (MVC)                      │
│                                                                   │
│  MainController                                                   │
│   ├─ QueueManager        sequential URL processing                │
│   ├─ JobHistoryDB        ~/.vcd/history.json                      │
│   ├─ SettingsManager     QSettings persistence                    │
│   ├─ TrayManager         system tray + notifications              │
│   └─ Worker ──────────────────────────────────────────→ QThread   │
│          │                                                        │
│          └──→ _StreamRouter                                       │
│                 hijacks sys.stdout / sys.stderr                   │
│                 parses log() lines + tqdm bars into signals:      │
│                 sig_log · sig_progress · sig_speed                │
│                 sig_eta · sig_bytes · sig_done                    │
└──────────────────────────┬────────────────────────────────────────┘
                           │ calls (never modifies)
┌──────────────────────────▼────────────────────────────────────────┐
│  src/vcd/core/  —  Download & Render Engine                       │
│                                                                   │
│  auth.py                                                           │
│   └─→ acquire_authenticated_session()                             │
│          ?session= token → manual cookie → interactive prompt     │
│  network.py                                                        │
│   └─→ Downloader.download_and_extract()                           │
│          HTTPS stream · HTTP Range resume · ZIP extraction        │
│  timeline.py                                                       │
│   └─→ collect_media_intervals()                                   │
│          parse pacingTick XML → millisecond-accurate clip offsets │
│   └─→ write_timeline_xml()                                        │
│          serialise for inspection / reuse                         │
│  media.py                                                          │
│          ┌──────────────────────────────┐                         │
│          │  render_video_from_timeline  │──→ Class-<id>.mp4       │
│          │  FilterGraphBuilder          │   GPU: NVENC/AMF/QSV    │
│          │  _video_encoder_args()       │   CPU: libx264          │
│          └──────────────────────────────┘                         │
└───────────────────────────────────────────────────────────────────┘
```

### Core modules

| Module | Responsibility |
|--------|---------------|
| `auth.py` | `acquire_authenticated_session()` — auth chain: URL `?session=` → CLI cookie → interactive prompt |
| `network.py` | `Downloader` — HTTPS streaming with `Range` header resume; ZIP validation and extraction; retry with exponential backoff |
| `timeline.py` | `collect_media_intervals()` — reads `pacingTick` from each XML, computes `start_ms` / `end_ms` per clip; `write_timeline_xml()` — serialises timeline |
| `media.py` | `Renderer` — FFmpeg execution with progress tracking; `render_video_from_timeline()` — filter graph: black canvas + video overlays + `amix`; `FilterGraphBuilder`; `_video_encoder_args()` for CPU / NVIDIA / AMD / Intel |
| `cli.py` | CLI entry point (`main()`) — argparse, banner, orchestration |
| `config.py` | `RenderConfig`, `DownloadConfig` dataclasses |
| `exceptions.py` | `VCDError` hierarchy: `ToolNotFoundError`, `AuthenticationError`, `DownloadError`, `MediaProcessingError` |
| `logger.py` | Shared `log(msg, level)` — timestamped, colour-coded stdout output |

### GUI threading model

```
UI Thread                         Worker Thread
─────────────────────             ─────────────────────────────────
MainWindow._start()
  → Worker.run() ───────────────→ sys.stdout = _StreamRouter
                                  init_tools()
                                  acquire_authenticated_session()
                                  Downloader.download_and_extract()
                                  collect_media_intervals()
                                  write_timeline_xml()
                                  render_video_from_timeline()
                                  sys.stdout = old_stdout

← sig_log(level, msg)           ← _StreamRouter.write() ← log()
← sig_progress(mode, pct)       ← tqdm bar pattern matched
← sig_speed("2.4 MB/s")         ← speed parsed from tqdm line
← sig_eta("01:23")              ← remaining time parsed
← sig_bytes("142 MB", "380 MB") ← bytes parsed from tqdm line
← sig_done(ok, msg, out_path)   ← emitted at end of Worker.run()
```

### Stop mechanism

Stopping immediately requires interrupting work across two layers:

| Stage | Method | Effect |
|-------|--------|--------|
| Download | `Downloader.cancel()` → closes the response socket | `stream_to_file()` raises immediately |
| FFmpeg render | `Renderer.cancel()` → terminates the ffmpeg process | SIGTERM to the running ffmpeg process |

Both calls happen in `Worker.cancel()`, triggered by `_stop()` on the UI thread via `MainController`.

---

## Features

### Current — v0.4

#### Download

- HTTP `Range` header resume — continues a partial download from the byte offset on disk
- Instant stop — closes socket and kills FFmpeg without waiting for the current stage to finish
- Auto-retry on failure, up to 3× with increasing delay
- Disk space check before starting

#### Render

- GPU encoding: **NVIDIA NVENC**, **AMD AMF**, **Intel QSV** — detected at launch, auto-selected, validated against your FFmpeg build
- Header chip shows detected GPU hardware; selecting an unavailable encoder shows an error and reverts the choice
- CPU fallback (`libx264`) always available
- Volume fix: `amix normalize=0` (prior versions halved audio volume when mixed with the silence padding track)

#### GUI

- Batch queue — add multiple URLs, process sequentially with automatic continuation
- Job history — every job logged to `~/.vcd/history.json`, viewable in the History tab
- Output files tab — thumbnail preview, play, open folder, delete
- Real-time speed graph with ETA and bytes downloaded
- System tray — minimize to background, desktop notification on finish
- Log panel — per-level filter (ALL / INFO / STEP / WARN / ERROR) + free-text search
- Cookie profiles — save and reload multiple BREEZESESSION sessions
- URL autocomplete — last 30 entries
- Clipboard URL detection — auto-fills on launch if a class link is copied
- Custom FFmpeg path — bypass PATH lookup with a specific binary
- Auto-open output when done
- Resizable splitter between controls panel and log

#### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+Enter` | Start job |
| `Esc` | Stop job |
| `Ctrl+Shift+Q` | Add current URL to batch queue |
| `Ctrl+L` | Log tab |
| `Ctrl+H` | History tab |
| `Ctrl+F` | Focus log search |
| `Ctrl+S` | Save log to file |
| `Ctrl+Q` | Quit |

---

## Requirements

- **Python** 3.10 or newer
- **FFmpeg + FFprobe** in PATH → [ffmpeg.org](https://ffmpeg.org/download.html)
- **PySide6** — GUI only

**GPU encoding** (optional — 3–8× faster rendering):

| GPU | Encoder | Platform |
|-----|---------|---------|
| NVIDIA | `h264_nvenc` | Windows, Linux |
| AMD | `h264_amf` | Windows |
| Intel | `h264_qsv` | Windows, Linux |
| CPU | `libx264` | All (default) |

> For GPU support, use the `win64-gpl` build from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases) — it ships with all three hardware encoders.

---

## Installation

```bash
git clone https://github.com/IAUCourseExp/VCD
cd VCD
pip install -r requirements.txt
```

`requirements.txt`:

```
PySide6>=6.0.0
requests>=2.28.0
urllib3>=1.26.0
tqdm>=4.64.0
colorama>=0.4.4
beautifulsoup4>=4.9.0
browser-cookie3>=0.12.0
pyfiglet>=0.8.post1
```

> **Note:** The core modules import `niquests` (aliased as `requests`) for HTTP/2 multiplexed sessions. The `requests` entry in `requirements.txt` is the current dependency name — update it to `niquests` if your build uses the niquests fork.

Optional packages degrade gracefully when missing.

---

## Usage

### GUI

```bash
python -m vcd.gui.main
```

On launch: FFmpeg and FFprobe are located, the best available GPU encoder is auto-detected and selected, and the URL field is auto-filled if a class link is in the clipboard.

Paste a class URL and click **Download & Render**.  
For batch processing: **+ Add to Queue** → build a list → **Run Queue**.

### CLI

```bash
# Video — default
python -m vcd.core.cli "https://vadavc32.ec.iau.ir/<id>/?session=TOKEN&proto=true"

# Custom output filename
python -m vcd.core.cli --output lecture_week3.mp4 "https://..."

# Timeline XML only, skip render
python -m vcd.core.cli --xml-only "https://..."
```

**All CLI flags:**

```
python -m vcd.core.cli [OPTIONS] URL

  --output FILE       Output filename  (default: Class-<id>.mp4)
  --cookie VALUE      BREEZESESSION value or full cookie string
  --xml-only          Write timeline.xml only, skip render
  --crf INT           Quality — lower = better  (default: 30)
  --fps INT           Frame rate  (default: 30)
```

### Authentication

Tried in order — the first working method is used:

1. **`?session=` in URL** — paste the full recording link; the tool extracts the token automatically
2. **`--cookie` flag / Cookie field** — your `BREEZESESSION` value (browser DevTools → Application → Cookies → your server domain)
3. **Interactive prompt** — CLI only; guides you through copying the cookie manually when no other method works

---

## How It Works

1. **Authentication** — establishes a session via the chain above
2. **Download** — fetches `/<id>/output/<id>.zip` over HTTPS; sends `Range: bytes=<offset>-` if a partial file exists on disk from a prior attempt
3. **Extraction** — validates and unzips FLV and XML files into `<id>/`
4. **Timing extraction** — reads `pacingTick` events from each XML file to compute a shared millisecond timebase; each clip gets an exact `start_ms` and `end_ms` relative to the recording start
5. **Segment building** — determines which screenshare and audio clip is active at each point in time, handling gaps and overlaps
6. **Timeline serialisation** — writes `<id>/timeline.xml` with `start`, `end`, and `offset` for every media segment; reusable for debugging or re-render without re-downloading
7. **Render** — builds FFmpeg filter graph:
   - Black canvas for the full recording duration
   - Each screenshare scaled and overlaid with a PTS offset (`setpts` + `overlay`)
   - Each audio clip delayed to its start time (`adelay`) then mixed with `amix normalize=0`
   - Encoded with the selected GPU encoder or CPU `libx264`
8. **Output** — `Class-<id>.mp4`

---

## Output

| File | Description |
|------|-------------|
| `Class-<id>.mp4` | Final synced video |
| `<id>/timeline.xml` | Serialised timeline — inspect or reuse for re-render |
| `<id>/` | Extracted raw files — safe to delete after a successful render |

---

## Troubleshooting

| Problem | Cause & fix |
|---------|-------------|
| `AuthenticationError` — "Could not authenticate" | Session expired. Get a fresh class link or copy a fresh `BREEZESESSION` from browser DevTools → Application → Cookies. |
| `DownloadError` — HTTP 403 / 404 | Recording may no longer exist or requires a different account. Open the ZIP URL in your browser while logged in to verify access. |
| `ToolNotFoundError` — ffmpeg/ffprobe not found | Add FFmpeg's `bin` folder to PATH, or set a custom path in GUI → Advanced → FFmpeg path. |
| `MediaProcessingError` — "No media files with a valid pacingTick" | Extracted folder may be empty or corrupt from an earlier interrupted download. Delete `<id>/` and retry. |
| GPU option grayed out | That encoder is not in your FFmpeg build. Use the `win64-gpl` build from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases). |
| Download restarts from 0 after interruption | Affects v0.3 and earlier — no resume support. Update to v0.4. |
| No screenshare in output | The class had no screenshare stream, only audio. |

---

## Changelog

> **For maintainers:** to add a new release, paste a new `### vX.Y — YYYY-MM-DD` block
> at the **top** of this section. Keep the structure: one-line summary, then bullet
> groups by category (New / Fixed / Changed). Dates go in the header, not in bullets.

---

### v0.4 

*Download resume · GPU validation · bug fixes.*

**New**
- HTTP `Range` resume: an interrupted download continues from the existing partial file on disk
- GPU auto-detection: header chip shows detected hardware; selecting an unavailable encoder shows an error dialog and reverts
- Auto-open output file when done, custom FFmpeg path in Advanced, clipboard URL auto-fill on launch

**Fixed**
- `amix normalize=0` — audio was 6 dB too quiet in all prior versions (`amix` default divides output by input count)
- `@retry` on `_stream_to_file` — manual Stop during download was delayed 5–8 s by retry backoff; decorator removed
- Double `_auto_retry()` call in `_on_done` — "Max retries reached" message appeared twice in the log
- Auto-retry fired after manual Stop — `_stop_requested` flag was not checked before scheduling retry
- `_stop_requested` not initialised in `__init__` — could raise `AttributeError` before first job
- Dead imports (`getpass`, `random`, `Callable`, `urlencode`) and duplicate CLI code removed

---

### v0.3

*First GUI release.*

**New**
- PySide6 desktop GUI wrapping the unchanged v0.2 core
- Quality presets: Ultra (1080p) / High (720p) / Balanced (720p) / Compact (480p) / Custom
- GPU encoder selection: NVIDIA NVENC · AMD AMF · Intel QSV · CPU
- Batch queue, job history (`~/.vcd/history.json`), output files tab with thumbnail extraction
- Real-time speed graph with ETA and bytes downloaded
- System tray with notifications, cookie profiles, URL autocomplete
- Log panel with per-level filter and free-text search
- Auto-retry on failure, disk space check, resizable splitter

---

### v0.2

*Authentication and network resilience.*

**New**
- Auth chain: `?session=` URL token → `--cookie` flag → browser cookies (`browser_cookie3`)
- Automatic retry with exponential backoff for unreliable connections
- `argparse` CLI: `--cookie`, `--output`, `--crf`, `--fps`, `--xml-only`
- `ToolManager`, `RenderConfig`, `DownloadConfig` dataclasses
- Custom exceptions: `AuthenticationError`, `DownloadError`, `MediaProcessingError`, `ToolNotFoundError`

---

### v0.1 — Initial release

- ZIP download and extraction (unauthenticated)
- `pacingTick` alignment for screenshare + audio synchronisation
- `timeline.xml` generation and single-pass FFmpeg render

---

## Contributing

Pull requests and issues are welcome.  
Please open an issue before implementing large changes to align on approach first.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <a href="https://t.me/IAUCourseExp">@IAUCourseExp</a>
  &nbsp;·&nbsp;
  <a href="https://t.me/JozveIAU">@JozveIAU</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/IAUCourseExp/VCD">⭐ Star on GitHub</a>
</p>
