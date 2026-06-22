<h1 align="center">
  <br>
  <a href="https://github.com/IAUCourseExp/VCD"><img src="https://raw.githubusercontent.com/IAUCourseExp/VCD/main/vcd0.3.png" alt="VCD" width="3000"></a>
  <br>
  VCD – Vadana Class Downloader
  <br>
</h1>

<h4 align="center">Download & merge <b>Adobe Connect (Vadana (Azad University Online Classes))</b> recordings into a single synced MP4 – w/ some authentication methods.</h4>

<p align="center">
  <a href="https://github.com/IAUCourseExp/VCD/releases/latest"><img src="https://img.shields.io/github/v/release/IAUCourseExp/VCD?style=flat-square" alt="Release"></a>
  <a href="https://github.com/IAUCourseExp/VCD/blob/main/LICENSE"><img src="https://img.shields.io/github/license/IAUCourseExp/VCD?style=flat-square" alt="License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square" alt="Python"></a>
  <a href="https://github.com/IAUCourseExp/VCD/stargazers"><img src="https://img.shields.io/github/stars/IAUCourseExp/VCD?style=flat-square" alt="Stars"></a>
  <br>
  <a href="https://github.com/IAUCourseExp/VCD/issues"><img src="https://img.shields.io/github/issues/IAUCourseExp/VCD?style=flat-square" alt="Issues"></a>
  <a href="https://github.com/IAUCourseExp/VCD/network/members"><img src="https://img.shields.io/github/forks/IAUCourseExp/VCD?style=flat-square" alt="Forks"></a>
</p>

<p align="center">
  <a href="#-key-features">Features</a> •
  <a href="#-requirements">Requirements</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-usage">Usage</a> •
  <a href="#-how-it-works-briefly">How It Works</a> •
  <a href="#-output">Output</a> •
  <a href="#-troubleshooting">Troubleshooting</a> •
  <a href="#-changelog">Changelog</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## ✨ Key Features

## GUI — v0.3 features (June 22nd 2026)

**Download & encode**
- Quality presets: Ultra (1080p) / High (720p) / Balanced (720p) / Compact (480p) / Custom
- GPU encode selector — NVIDIA, AMD, Intel, or CPU; auto-detected and defaulted at startup
- Advanced settings: resolution, FPS, CRF, audio bitrate, x264 preset, tail padding

**Workflow**
- Batch queue — queue multiple class URLs, run them one after another automatically
- Instant stop — kills FFmpeg and closes the download socket immediately; no waiting
- Auto-retry — retries failed jobs up to 3× with increasing delay
- Disk space check — warns before starting if output folder has < 500 MB free

**History & files**
- Job history — every job is logged persistently to `~/.vcd/history.json`
- Output files tab — browse rendered videos, preview thumbnail, play, open folder, delete

**Live feedback**
- Real-time speed graph with ETA and bytes downloaded
- Log panel with per-level filter (INFO / STEP / WARN / ERROR) and free-text search
- System tray — minimize to background, get a desktop notification on finish

**Convenience**
- Cookie profiles — save and reload multiple named BREEZESESSION presets
- URL autocomplete — remembers the last 30 URLs
- Resizable splitter between the controls panel and the log

**Keyboard shortcuts**

| Keys | Action |
|------|--------|
| `Ctrl+Enter` | Start job |
| `Esc` | Stop job |
| `Ctrl+Shift+Q` | Add current URL to batch queue |
| `Ctrl+L` | Switch to Log tab |
| `Ctrl+H` | Switch to History tab |
| `Ctrl+F` | Focus log search |
| `Ctrl+S` | Save log to file |
| `Ctrl+Q` | Quit |

---

### 🚀 What’s new in v0.2

- **🔐 Smart authentication**  
  *Automatically uses `?session=` tokens from class URLs, manual `BREEZESESSION` cookies, or browser cookies (via `browser_cookie3`).*  
  *No more manual ZIP downloads!*

- **📡 Network resilience**  
  *Automatic retry with exponential backoff for flaky connections – built‑in tolerance for Iranian networks.*

- **🖥️ Cross‑platform & Jupyter‑friendly**  
  *Works identically in CMD, VSCode, Jupyter Notebook, IPython – even when the kernel injects extra arguments.*

- **⚙️ Command‑line power**  
  *Pass the URL, cookie, output filename, CRF, FPS directly via flags. Perfect for scripting and automation.*

- **🎨 Beautiful terminal UX**  
  *Animated RGB banner, colour‑coded log levels, and clean progress bars.*

- **🧰 Robust error handling**  
  *Custom exceptions (`AuthenticationError`, `DownloadError`, …) tell you exactly what went wrong and how to fix it.*

- **🧹 Cleaner codebase**  
  *No global variables; tool paths are managed by a `ToolManager` class. FFmpeg filters use a `FilterGraphBuilder` for readability.*

### 🔧 Existing goodness (from v0.1)

- **Automatic ZIP download & extraction** (with authentication now)
- **Pacing‑tick alignment** from internal XML files – *true zero‑point synchronisation*
- **Screenshare + audio** merging into a single MP4
- **Black‑canvas background** – no stale frames, clean composition
- **Detailed `timeline.xml`** for inspection or manual editing
- **Idempotent** – re‑running re‑uses the downloaded folder

---

## 📋 Requirements

- **Python** `3.8` or newer  
- **FFmpeg** (with `ffmpeg` and `ffprobe` accessible in your `PATH`)  
  Download from [ffmpeg.org](https://ffmpeg.org/download.html).

---

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/IAUCourseExp/VCD
cd VCD

# Install Python dependencies
pip install -r requirements.txt
```

`requirements.txt` contains:

```
requests
tqdm
colorama
pyfiglet        # optional – for the fancy ASCII banner
urllib3
beautifulsoup4  # optional – for HTML form authentication
browser-cookie3 # optional – for automatic browser cookie extraction
```

> ℹ️ The optional packages are not strictly required; the script gracefully degrades if they are missing.

---

## 🚀 Usage

### Basic interactive mode

Run the script and paste your class URL when prompted:

```bash
python VCD.py
```

You will see the animated banner, then:

```
Enter class URL (full URL with ?session= is best):
  e.g. https://vadavc32.ec.iau.ir/lasqwynd9xye/?session=adminbreezcdu7pad2xwpfe39a&proto=true
  or just: https://vadavc32.ec.iau.ir/lasqwynd9xye
>
```

### Authentication options

**A) URL with `?session=` – best & easiest**  
Paste the full link you received from the educational system. The tool extracts the session token automatically.

**B) Command‑line cookie**  
If you have the `BREEZESESSION` value:

```bash
python VCD.py --cookie "BREEZESESSION=abc123..." "https://vadavc32.ec.iau.ir/lasqwynd9xye"
```

**C) Interactive cookie paste**  
The tool will guide you to copy the cookie from your browser’s DevTools if no other method works.

### Command‑line arguments

```
usage: VCD.py [-h] [--output OUTPUT] [--cookie COOKIE] [--xml-only] [--crf CRF] [--fps FPS] [url]

positional arguments:
  url                   Full class URL (with ?session= is best). If omitted, you will be prompted.

options:
  -h, --help            show this help message and exit
  --output, -o OUTPUT   Output MP4 filename (default: Class-<id>.mp4)
  --cookie COOKIE       BREEZESESSION value or full cookie string
  --xml-only            Only generate timeline.xml, don't render video
  --crf CRF             Video quality (CRF, lower=better, default 30)
  --fps FPS             Output frame rate (default 30)
```

**Examples:**

```bash
# Use session token from URL
python VCD.py "https://vadavc32.ec.iau.ir/lasqwynd9xye/?session=...&proto=true"

# Provide cookie and custom output name
python VCD.py --cookie "BREEZESESSION=abc123" -o my_class.mp4 "https://..."

# Only generate the timeline (no video)
python VCD.py --xml-only "https://..."
```

### Running inside Jupyter / IPython

You can run the script directly in a notebook cell – it automatically filters out the kernel’s connection file argument and asks for the URL interactively.

```python
%run VCD.py
```

or, with arguments:

```python
%run VCD.py --cookie "BREEZESESSION=abc" "https://..."
```

---

## 🔍 How It Works (briefly)

1. **Authentication** – obtains a valid session using the provided cookie/token (fallback chain: `?session=` → CLI `--cookie` → interactive paste).
2. **Download** – fetches the recording ZIP from `https://<server>/<id>/output/<id>.zip?download=zip`.
3. **Extraction** – unzips all FLV and XML files into a folder named after the recording ID.
4. **Timing extraction** – reads `pacingTick` timestamps from XML files to compute a common timebase.
5. **Segment building** – determines when each screenshare video and audio file is active.
6. **`timeline.xml`** – generates a unified timeline with exact start/end offsets for every media segment.
7. **Rendering** – invokes FFmpeg with a complex filter graph:
   - Black canvas for the whole duration.
   - Video overlays with PTS offsets (no stale frames).
   - Audio mixer with precise delays and trimming.
8. **Output** – a single `Class-<id>.mp4` file placed in the working directory.

---

## 📂 Output

- **Final video:** `Class-<recording_id>.mp4` (e.g., `Class-lasqwynd9xye.mp4`)
- **Extracted files:** a folder named after the recording ID (e.g., `lasqwynd9xye/`).  
  You can safely delete this folder after a successful run.

---

## ❗ Troubleshooting

| Problem | Likely cause & solution |
|---------|--------------------------|
| `AuthenticationError` – “Could not authenticate” | The session token is expired or invalid. Get a fresh class link or copy the `BREEZESESSION` cookie manually. |
| `DownloadError` – “HTTP 404 / 403” | The recording may no longer exist or the server requires additional login. Try opening the ZIP URL in your browser while logged in. |
| `ToolNotFoundError` – ffmpeg/ffprobe not found | Install FFmpeg and ensure `ffmpeg`/`ffprobe` are in your `PATH`, or place them next to `VCD.py`. |
| Render seems stuck at 95 % | Audio mixing for very long classes can take extra time. Let it finish – a future update will optimise this step. |
| No video, only audio | Ensure the class actually contained a screenshare. The tool only processes `screenshare*.flv` files with a video track. |
| `WARN Ignoring non-URL argument` in Jupyter | Normal – the kernel connection file is automatically ignored. The prompt will still ask for the real URL. |
| URL accepted but script exits silently | A hidden control character may have been pasted. Re‑type the URL manually or use the `--cookie` method. |

---

## 📝 Changelog

### v0.2 – The “Authentication & Robustness” release
- 🔐 Multiple authentication methods (session token, manual cookie, browser cookies)
- 🔄 Automatic retry on network failures with exponential backoff
- 🧪 `argparse` for full command‑line control
- 🧠 `ToolManager` class replaces global variables
- 🛡️ Custom exceptions for crystal‑clear error messages
- 🎨 Animated RGB banner & improved log formatting
- 🐍 Jupyter/IPython support out‑of‑the‑box
- 🔧 `RenderConfig` & `DownloadConfig` dataclasses for clean parameter management
- … and many more small fixes & improvements

### v0.1 – Initial release
- Basic ZIP download & extraction (unauthenticated)
- Pacing‑tick alignment for screenshare + audio
- `timeline.xml` generation and video rendering

---

## 🤝 Contributing

Pull requests, issues, and ideas are warmly welcomed🤗

Please open an issue before implementing large changes to discuss your approach.

---

## 📄 License

MIT – see [LICENSE](LICENSE) for details.

---
