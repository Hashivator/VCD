#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCD v0.3 — Advanced GUI for the Vadana Class Downloader

New in v0.3:
  Batch Queue     — queue multiple class URLs, run them sequentially
  Job History     — persistent JSON log in ~/.vcd/history.json
  Output Files    — browse, play, and manage rendered videos
  Real-time Stats — ETA, bytes downloaded, elapsed time
  Speed Graph     — live area chart of download speed
  System Tray     — background mode + desktop notifications
  Cookie Profiles — save named BREEZESESSION presets
  URL History     — autocomplete from recent URLs
  Log Filter+Search — filter by level, full-text search
  Video Thumbnail — frame preview after render
  Disk Space Check — warn before starting if < 500 MB free
  Auto-retry      — auto-retry on failure up to 3 times
  Keyboard Shortcuts — Ctrl+Return, Esc, Ctrl+L, Ctrl+H, Ctrl+F...
  Resizable Splitter — drag the divider between left and right panels
"""

import sys
import io

# pythonw.exe on Windows nukes stdout — colorama dies without this guard
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

import os
import re
import math
import html
import json
import uuid
import random
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import Optional
from vcd.core.network import Downloader
from vcd.core.media import Renderer, init_tools, render_video_from_timeline
from vcd.core.config import DownloadConfig, RenderConfig
from vcd.core.auth import acquire_authenticated_session
from vcd.core.timeline import write_timeline_xml, collect_media_intervals
from vcd.core.exceptions import VCDError

try:
    from PySide6.QtCore import (
        Qt,
        QTimer,
        QThread,
        QObject,
        Signal,
        Slot,
        QSettings,
        QUrl,
        QPointF,
        QPropertyAnimation,
        QEasingCurve,
        QStringListModel,
    )
    from PySide6.QtGui import (
        QColor,
        QPainter,
        QLinearGradient,
        QRadialGradient,
        QDesktopServices,
        QPen,
        QPainterPath,
        QPixmap,
        QIcon,
        QKeySequence,
        QShortcut,
        QAction,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QWidget,
        QLabel,
        QLineEdit,
        QPushButton,
        QComboBox,
        QSpinBox,
        QSlider,
        QCheckBox,
        QPlainTextEdit,
        QFrame,
        QVBoxLayout,
        QHBoxLayout,
        QGridLayout,
        QButtonGroup,
        QGraphicsDropShadowEffect,
        QFileDialog,
        QMessageBox,
        QToolButton,
        QScrollArea,
        QProgressBar,
        QTabWidget,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QListWidget,
        QListWidgetItem,
        QSystemTrayIcon,
        QMenu,
        QCompleter,
        QAbstractItemView,
        QSizePolicy,
        QDialog,
        QDialogButtonBox,
    )
except ImportError:
    sys.stderr.write("PySide6 not installed. Run: pip install PySide6\n")
    raise

# import the core downloader — we call its functions, never touch its logic
core = None
_core_err = ""
try:
    import vcd_core as core
except Exception as exc:
    _core_err = (
        "Couldn't import vcd_core.py.\n\n"
        f"{type(exc).__name__}: {exc}\n\n"
        "Fix:\n"
        "  Rename your v0.2 script to vcd_core.py and put it next to this file.\n"
        "  Install its deps:  pip install requests urllib3 tqdm colorama"
    )

_APP_ICON_B64 = "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"


def _load_app_icon() -> "QIcon":
    """Decode the embedded icon and return a QIcon. Falls back to empty on error."""
    try:
        import base64 as _b64

        data = _b64.b64decode(_ICON_B64)
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            return QIcon(px)
    except Exception:
        pass
    return QIcon()


_APP_ICON = _load_app_icon()

# ---------------------------------------------------------------------------
# Palette (unchanged from v0.3 — deep space blues + indigo nebula)
# ---------------------------------------------------------------------------
SKY = "#38bdf8"
VIO = "#a78bfa"
TEXT = "#ddf4ff"
DGREY = "#3d5470"
GREEN = "#34d399"
AMBER = "#fbbf24"
RED = "#f87171"
TEAL = "#5eead4"

LEVEL_COLOR = {
    "INFO": SKY,
    "SUCCESS": GREEN,
    "STEP": VIO,
    "WARN": AMBER,
    "ERROR": RED,
    "DEBUG": DGREY,
    "LOG": TEAL,
}
LEVEL_ICON = {
    "INFO": "›",
    "SUCCESS": "✓",
    "STEP": "◆",
    "WARN": "!",
    "ERROR": "✗",
    "DEBUG": "·",
    "LOG": "·",
}


# ---------------------------------------------------------------------------
# Quality presets
# ---------------------------------------------------------------------------
PRESETS = {
    "Ultra (1080p)": dict(
        w=1920,
        h=1080,
        fps=30,
        crf=20,
        vp="slow",
        ab="192k",
        pad=2000,
        note="Best quality — slow encode, biggest file.",
    ),
    "High (720p - high)": dict(
        w=1280,
        h=720,
        fps=30,
        crf=23,
        vp="medium",
        ab="128k",
        pad=2000,
        note="Great quality, reasonable size.",
    ),
    "Balanced (720p - normal)": dict(
        w=1280,
        h=720,
        fps=30,
        crf=28,
        vp="veryfast",
        ab="96k",
        pad=2000,
        note="Fast encode, decent quality. Good for lectures.",
    ),
    "Compact (480p)": dict(
        w=854,
        h=480,
        fps=24,
        crf=32,
        vp="veryfast",
        ab="64k",
        pad=2000,
        note="Smallest file, fastest to make.",
    ),
    "Custom": None,
}
RESOLUTIONS = ["1920x1080", "1600x900", "1280x720", "960x540", "854x480", "640x360"]
VPRESETS = [
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
]
ABITRATES = ["64k", "96k", "128k", "160k", "192k", "256k"]
GPU_OPTIONS = ["CPU  (default)", "NVIDIA  (NVENC)", "AMD  (AMF)", "Intel  (QSV)"]
GPU_KEYS = ["cpu", "nvidia", "amd", "intel"]
DEFAULT_PRESET = "Balanced (720p)"
_MAX_RETRIES = 3
_MAX_URL_HIST = 30
_MAX_HISTORY = 500
_HISTORY_FILE = Path.home() / ".vcd" / "history.json"
_THUMB_DIR = Path.home() / ".vcd" / "thumbs"


def _tobool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on")


# progress bar chunk styles — swapped dynamically per mode
_BAR_DOWNLOAD = """QProgressBar::chunk {
    border-radius:8px; margin:1px;
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #0369a1, stop:0.55 #0ea5e9, stop:1 #38bdf8);
}"""
_BAR_RENDER = """QProgressBar::chunk {
    border-radius:8px; margin:1px;
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #4c1d95, stop:0.55 #7c3aed, stop:1 #a78bfa);
}"""

# active preset button — setStyleSheet beats :checked which is unreliable in QButtonGroup
_PRESET_ACTIVE = """QPushButton {
    background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1a3a5c,stop:1 #102540);
    border:1.5px solid #38bdf8; color:#ffffff;
}
QPushButton:hover {
    background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #24507e,stop:1 #163352);
    color:#ffffff;
}"""

_QUEUE_CLR = {
    "pending": "#7aacca",
    "running": "#38bdf8",
    "done": "#34d399",
    "failed": "#f87171",
}


# ---------------------------------------------------------------------------
# Global QSS
# ---------------------------------------------------------------------------
THEME = r"""
* { outline: none; }
QWidget { color:#ddf4ff; font-family:"Segoe UI","SF Pro Text","DejaVu Sans",Arial; font-size:13px; }
QToolTip { background:#040c18; color:#ddf4ff; border:1px solid rgba(56,189,248,.45); padding:5px 8px; border-radius:6px; }

QFrame#panel  { background:#070e1d; border:1px solid rgba(56,189,248,.16); border-radius:16px; }
QFrame#adv    { background:rgba(5,10,22,.92); border:1px solid rgba(167,139,250,.22); border-radius:12px; }
QFrame#stats_frame { background:rgba(4,9,20,.85); border:1px solid rgba(56,189,248,.12); border-radius:8px; }
QFrame#queue_frame { background:rgba(5,10,22,.7); border:1px solid rgba(56,189,248,.14); border-radius:10px; }
QFrame#card   { background:rgba(8,15,32,.8); border:1px solid rgba(56,189,248,.10); border-radius:10px; }
QFrame#card:hover { border-color:rgba(56,189,248,.28); }

QLabel#title    { color:#e4f4ff; font-size:44px; font-weight:800; letter-spacing:8px; }
QLabel#subtitle { color:#38bdf8; font-size:12px; font-weight:500; letter-spacing:1px; }
QLabel#tagline  { color:#2d4a62; font-size:11px; letter-spacing:0; }
QLabel#links { font-size: 11px; margin-top: 1px; }
QLabel#links a { text-decoration: none; }
QLabel#section  { color:#38bdf8; font-size:10px; font-weight:800; letter-spacing:3px; }
QLabel#stage    { color:#7aacca; font-size:12px; }
QLabel#detected { color:#334d66; font-size:11px; }
QLabel#note     { color:#3e5f7a; font-size:11px; }
QLabel#fld      { color:#456070; font-size:12px; }
QLabel#sys      { font-size:11px; font-weight:700; }
QLabel#speed    { color:#38bdf8; font-size:11px; font-weight:600; }
QLabel#stat_val { color:#7aacca; font-size:11px; font-weight:600; }
QLabel#file_name { color:#c0dff0; font-size:12px; font-weight:600; }
QLabel#file_meta { color:#3d5470; font-size:11px; }
QLabel#disk_ok   { color:#34d399; font-size:11px; }
QLabel#disk_warn { color:#fbbf24; font-size:11px; font-weight:700; }
QLabel#retry_lbl { color:#fbbf24; font-size:11px; font-weight:700; }

QLineEdit, QComboBox, QSpinBox {
    background:#091526; border:1px solid rgba(56,189,248,.18); border-radius:9px;
    padding:8px 11px; color:#ddf4ff;
    selection-background-color:#0369a1; selection-color:#e0f4ff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border:1px solid rgba(56,189,248,.6); }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { color:#243650; border-color:rgba(56,189,248,.06); background:#050c18; }
QComboBox::drop-down { border:none; width:22px; }
QComboBox QAbstractItemView { background:#091526; color:#ddf4ff; border:1px solid rgba(56,189,248,.45); selection-background-color:rgba(56,189,248,.18); outline:none; }

QCheckBox { spacing:9px; color:#6a9ab8; }
QCheckBox::indicator { width:17px; height:17px; border-radius:5px; border:1px solid rgba(56,189,248,.32); background:#091526; }
QCheckBox::indicator:checked { background:#0369a1; border-color:#38bdf8; }
QCheckBox:disabled { color:#243650; }

QPushButton#preset { background:rgba(9,16,34,.92); border:1px solid rgba(56,189,248,.18); border-radius:10px; padding:13px 8px; color:#5a88a8; font-weight:700; font-size:12px; }
QPushButton#preset:hover { border-color:rgba(56,189,248,.45); color:#c0dff0; background:rgba(14,26,50,.95); }
QPushButton#preset:disabled { color:#1e3048; border-color:rgba(56,189,248,.06); background:transparent; }

QPushButton#go {
    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #0f2540,stop:1 #081a2e);
    border:1.5px solid #38bdf8; border-radius:12px; padding:16px 20px;
    color:#e0f2fe; font-size:15px; font-weight:700; letter-spacing:1px;
}
QPushButton#go:hover { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1a3a60,stop:1 #102540); border-color:#7dd3fc; color:#ffffff; }
QPushButton#go:disabled { color:#1e3048; border-color:rgba(56,189,248,.1); background:#050c18; }

QPushButton#stop { border:1.5px solid #f87171; border-radius:12px; padding:15px 20px; color:#f87171; font-size:15px; font-weight:700; background:rgba(248,113,113,.07); }
QPushButton#stop:hover { background:rgba(248,113,113,.15); }
QPushButton#stop:disabled { color:#4a2530; border-color:#2e1820; }

QPushButton#ghost { background:rgba(56,189,248,.05); border:1px solid rgba(56,189,248,.25); border-radius:9px; padding:7px 14px; color:#5ca8cc; font-weight:600; }
QPushButton#ghost:hover { background:rgba(56,189,248,.12); color:#ddf4ff; border-color:rgba(56,189,248,.5); }
QPushButton#ghost:disabled { color:#1e3048; border-color:rgba(56,189,248,.06); }

QPushButton#icon_btn { background:transparent; border:1px solid rgba(56,189,248,.2); border-radius:7px; padding:4px 8px; color:#5ca8cc; font-size:12px; }
QPushButton#icon_btn:hover { background:rgba(56,189,248,.1); color:#ddf4ff; border-color:rgba(56,189,248,.45); }

QPushButton#danger_btn { background:transparent; border:1px solid rgba(248,113,113,.2); border-radius:7px; padding:4px 8px; color:#8a4444; font-size:12px; }
QPushButton#danger_btn:hover { background:rgba(248,113,113,.1); color:#f87171; border-color:rgba(248,113,113,.45); }

QToolButton#advbtn { background:transparent; border:none; color:rgba(56,189,248,.55); font-weight:600; padding:3px 2px; font-size:12px; }
QToolButton#advbtn:hover { color:#38bdf8; }
QToolButton#about {
    background: rgba(56,189,248,0.08);
    border: 1.5px solid rgba(56,189,248,0.50);
    border-radius: 14px;
    color: #bae6fd;
    font-weight: 800;
    font-size: 14px;
}
QToolButton#about:hover {
    background: rgba(56,189,248,0.18);
    border-color: #38bdf8;
    color: #ffffff;
}

QProgressBar { background:#060d1a; border:1px solid rgba(56,189,248,.18); border-radius:9px; min-height:20px; text-align:center; color:#90c8e8; font-weight:600; font-size:12px; }
QProgressBar::chunk { border-radius:8px; margin:1px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1e3a5f,stop:1 #265480); }

QSlider::groove:horizontal { height:5px; background:#091526; border-radius:3px; }
QSlider::sub-page:horizontal { height:5px; border-radius:3px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0369a1,stop:1 #38bdf8); }
QSlider::add-page:horizontal { background:#0d1e34; border-radius:3px; }
QSlider::handle:horizontal { width:15px; height:15px; margin:-6px 0; border-radius:8px; background:#ddf4ff; border:2px solid #38bdf8; }

QPlainTextEdit#log { background:#030810; border:1px solid rgba(56,189,248,.12); border-radius:14px; color:#38bdf8; padding:10px; font-family:"Cascadia Code","JetBrains Mono","Consolas","DejaVu Sans Mono",monospace; font-size:12px; }

QTabWidget#righttabs::pane { border:1px solid rgba(56,189,248,.16); border-radius:14px; background:#070e1d; top:-1px; }
QTabWidget#righttabs > QTabBar::tab { background:rgba(5,10,22,.9); color:#3d5470; border:1px solid rgba(56,189,248,.10); border-bottom:none; border-radius:8px 8px 0 0; padding:8px 20px; margin-right:3px; font-weight:700; font-size:11px; letter-spacing:1px; }
QTabWidget#righttabs > QTabBar::tab:selected { background:#070e1d; color:#38bdf8; border-color:rgba(56,189,248,.35); }
QTabWidget#righttabs > QTabBar::tab:hover:!selected { color:#7aacca; background:rgba(10,18,36,.95); }

QTableWidget { background:transparent; border:none; color:#ddf4ff; gridline-color:rgba(56,189,248,.06); selection-background-color:rgba(56,189,248,.12); selection-color:#ddf4ff; outline:none; }
QTableWidget::item { padding:6px 10px; border:none; }
QTableWidget::item:selected { background:rgba(56,189,248,.12); }
QHeaderView::section { background:rgba(5,10,22,.9); color:#38bdf8; border:none; border-bottom:1px solid rgba(56,189,248,.18); border-right:1px solid rgba(56,189,248,.06); padding:7px 10px; font-weight:800; font-size:10px; letter-spacing:2px; }

QListWidget { background:transparent; border:none; color:#ddf4ff; outline:none; selection-background-color:rgba(56,189,248,.10); }
QListWidget::item { border-bottom:1px solid rgba(56,189,248,.06); padding:5px 8px; }
QListWidget::item:selected { background:rgba(56,189,248,.10); }

QSplitter::handle:horizontal { width:4px; background:rgba(56,189,248,.08); }
QSplitter::handle:horizontal:hover { background:rgba(56,189,248,.25); }

QPushButton#filter_btn { background:transparent; border:1px solid rgba(56,189,248,.15); border-radius:6px; padding:3px 9px; color:#3d5470; font-weight:700; font-size:10px; letter-spacing:1px; }
QPushButton#filter_btn:hover { color:#7aacca; border-color:rgba(56,189,248,.35); }
QPushButton#filter_btn[active="1"] { color:#38bdf8; border-color:rgba(56,189,248,.55); background:rgba(56,189,248,.08); }

QLineEdit#log_search { background:rgba(5,10,22,.7); border:1px solid rgba(56,189,248,.14); border-radius:7px; padding:4px 10px; color:#7aacca; font-size:11px; }
QLineEdit#log_search:focus { border-color:rgba(56,189,248,.4); }

/* ---------- scrollbars ---------- */
QScrollBar:vertical {
    background: rgba(8,15,32,0.7);
    width: 10px;
    margin: 4px 2px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(56,189,248,0.30), stop:1 rgba(99,102,241,0.30));
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(56,189,248,0.60), stop:1 rgba(99,102,241,0.50));
}
QScrollBar::handle:vertical:pressed {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(56,189,248,0.90), stop:1 rgba(99,102,241,0.80));
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QScrollBar:horizontal {
    background: rgba(8,15,32,0.7);
    height: 10px;
    margin: 2px 4px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(56,189,248,0.30), stop:1 rgba(99,102,241,0.30));
    border-radius: 4px;
    min-width: 32px;
}
QScrollBar::handle:horizontal:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(56,189,248,0.60), stop:1 rgba(99,102,241,0.50));
}
QScrollBar::handle:horizontal:pressed {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(56,189,248,0.90), stop:1 rgba(99,102,241,0.80));
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ---------- message boxes and dialogs ---------- */
QMessageBox {
    background: #070e1d;
}
QMessageBox QLabel {
    color: #c8dff0;
    font-size: 13px;
    min-width: 280px;
}
QMessageBox QPushButton {
    background: rgba(9,16,34,0.95);
    border: 1px solid rgba(56,189,248,0.30);
    border-radius: 8px;
    padding: 7px 22px;
    color: #7aacca;
    font-weight: 600;
    min-width: 72px;
}
QMessageBox QPushButton:hover {
    background: rgba(56,189,248,0.10);
    border-color: rgba(56,189,248,0.65);
    color: #ddf4ff;
}
QMessageBox QPushButton:default {
    border-color: #38bdf8;
    color: #38bdf8;
}

QDialog {
    background: #070e1d;
    border: 1px solid rgba(56,189,248,0.18);
    border-radius: 12px;
}
QDialog QLabel {
    color: #c8dff0;
    font-size: 13px;
}
QDialog QPushButton {
    background: rgba(9,16,34,0.95);
    border: 1px solid rgba(56,189,248,0.30);
    border-radius: 8px;
    padding: 7px 22px;
    color: #7aacca;
    font-weight: 600;
    min-width: 72px;
}
QDialog QPushButton:hover {
    background: rgba(56,189,248,0.10);
    border-color: rgba(56,189,248,0.65);
    color: #ddf4ff;
}
QDialog QPushButton:default {
    border-color: #38bdf8;
    color: #38bdf8;
}

"""


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# StarField — animated space background (unchanged from v0.3)
# ---------------------------------------------------------------------------
class StarField(QWidget):
    def __init__(self, parent=None, n=160):
        super().__init__(parent)
        rnd = random.Random(42)
        self.stars = [
            dict(
                x=rnd.random(),
                y=rnd.random(),
                r=rnd.uniform(0.5, 1.9),
                base=rnd.uniform(25, 155),
                amp=rnd.uniform(18, 75),
                sp=rnd.uniform(0.4, 2.0),
                ph=rnd.uniform(0, 6.28),
                drift=rnd.uniform(0.003, 0.015),
            )
            for _ in range(n)
        ]
        self.big = [
            dict(
                x=rnd.random(),
                y=rnd.random(),
                r=rnd.uniform(1.4, 2.5),
                col=rnd.choice([(56, 189, 248), (167, 139, 250), (99, 102, 241)]),
                sp=rnd.uniform(0.3, 1.0),
                ph=rnd.uniform(0, 6.28),
                drift=rnd.uniform(0.002, 0.008),
            )
            for _ in range(9)
        ]
        self._t = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    def _tick(self):
        self._t += 0.05
        self.update()

    def paintEvent(self, _ev):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(3, 6, 14))
        bg.setColorAt(0.5, QColor(5, 8, 18))
        bg.setColorAt(1.0, QColor(6, 7, 20))
        p.fillRect(0, 0, w, h, bg)
        for cx, cy, col in (
            (0.15, 0.20, (56, 189, 248)),
            (0.88, 0.82, (167, 139, 250)),
            (0.68, 0.08, (99, 102, 241)),
        ):
            r, g, b = col
            rg = QRadialGradient(cx * w, cy * h, 0.48 * max(w, h))
            rg.setColorAt(0.0, QColor(r, g, b, 20))
            rg.setColorAt(1.0, QColor(r, g, b, 0))
            p.fillRect(0, 0, w, h, rg)
        t = self._t
        p.setPen(Qt.NoPen)
        for s in self.stars:
            a = int(
                max(0, min(255, s["base"] + s["amp"] * math.sin(t * s["sp"] + s["ph"])))
            )
            y = ((s["y"] + t * s["drift"]) % 1.0) * h
            p.setBrush(QColor(180, 215, 255, a))
            p.drawEllipse(QPointF(s["x"] * w, y), s["r"], s["r"])
        for s in self.big:
            a = int(max(0, min(255, 100 + 90 * math.sin(t * s["sp"] + s["ph"]))))
            x, y = s["x"] * w, ((s["y"] + t * s["drift"]) % 1.0) * h
            r, g, b = s["col"]
            glow = QRadialGradient(x, y, 11)
            glow.setColorAt(0.0, QColor(r, g, b, int(a * 0.45)))
            glow.setColorAt(1.0, QColor(r, g, b, 0))
            p.setBrush(glow)
            p.drawEllipse(QPointF(x, y), 11, 11)
            p.setBrush(QColor(r, g, b, a))
            p.drawEllipse(QPointF(x, y), s["r"], s["r"])
        p.end()


# ---------------------------------------------------------------------------
# SpeedGraph — 90-point live area chart of download speed
# ---------------------------------------------------------------------------
class SpeedGraph(QWidget):
    _MAX = 90

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pts: list = []
        self.setFixedHeight(48)
        self.setMinimumWidth(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def push(self, speed_str: str):
        bps = _parse_bps(speed_str)
        if bps > 0:
            self._pts.append(bps)
            if len(self._pts) > self._MAX:
                self._pts = self._pts[-self._MAX :]
            self.update()

    def clear(self):
        self._pts.clear()
        self.update()

    def paintEvent(self, _ev):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, w, h, QColor(3, 7, 16))
        if len(self._pts) < 2:
            p.setPen(QPen(QColor(56, 189, 248, 30), 1))
            p.drawLine(0, h - 2, w, h - 2)
            p.end()
            return
        mx = max(self._pts) or 1
        n = len(self._pts)
        pts = [
            QPointF(w * i / (n - 1), (h - 4) - (h - 8) * self._pts[i] / mx)
            for i in range(n)
        ]
        path = QPainterPath()
        path.moveTo(pts[0].x(), h)
        for pt in pts:
            path.lineTo(pt)
        path.lineTo(pts[-1].x(), h)
        path.closeSubpath()
        fill = QLinearGradient(0, 0, 0, h)
        fill.setColorAt(0.0, QColor(56, 189, 248, 70))
        fill.setColorAt(1.0, QColor(56, 189, 248, 5))
        p.fillPath(path, fill)
        pen = QPen(QColor(56, 189, 248), 1.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        for i in range(n - 1):
            p.drawLine(pts[i], pts[i + 1])
        # latest speed label
        if self._pts:
            lbl = _fmt_bytes(self._pts[-1]) + "/s"
            p.setPen(QColor(220, 242, 255, 210))
            p.drawText(0, 0, w - 3, h - 2, Qt.AlignRight | Qt.AlignTop, lbl)
        p.end()


# ---------------------------------------------------------------------------
# StatsWidget — elapsed, ETA, bytes + speed graph
# ---------------------------------------------------------------------------
class StatsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("stats_frame")
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 6, 10, 6)
        v.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(0)
        self.elapsed_lbl = QLabel("0:00")
        self.elapsed_lbl.setObjectName("stat_val")
        self.bytes_lbl = QLabel("")
        self.bytes_lbl.setObjectName("stat_val")
        self.bytes_lbl.setAlignment(Qt.AlignCenter)
        self.eta_lbl = QLabel("")
        self.eta_lbl.setObjectName("stat_val")
        self.eta_lbl.setAlignment(Qt.AlignRight)
        top.addWidget(self.elapsed_lbl)
        top.addStretch(1)
        top.addWidget(self.bytes_lbl)
        top.addStretch(1)
        top.addWidget(self.eta_lbl)
        v.addLayout(top)
        self.graph = SpeedGraph(self)
        v.addWidget(self.graph)

    def reset(self):
        self.elapsed_lbl.setText("0:00")
        self.bytes_lbl.setText("")
        self.eta_lbl.setText("")
        self.graph.clear()

    def set_elapsed(self, secs: int):
        self.elapsed_lbl.setText(f"⏱ {_fmt_dur(secs)}")

    def set_bytes(self, dl: str, total: str = ""):
        self.bytes_lbl.setText(f"↓ {dl} / {total}" if total else f"↓ {dl}")

    def set_eta(self, eta: str):
        self.eta_lbl.setText(f"ETA {eta}" if eta else "")

    def push_speed(self, spd: str):
        self.graph.push(spd)


# ---------------------------------------------------------------------------
# JobHistoryDB — saves every job to ~/.vcd/history.json
# ---------------------------------------------------------------------------
class JobHistoryDB:
    def __init__(self):
        self._entries: list = []
        self._load()

    def add(self, entry: dict):
        self._entries.insert(0, entry)
        self._entries = self._entries[:_MAX_HISTORY]
        self._save()

    def update_last(self, **kw):
        if self._entries:
            self._entries[0].update(kw)
            self._save()

    def remove(self, idx: int):
        if 0 <= idx < len(self._entries):
            self._entries.pop(idx)
            self._save()

    def clear(self):
        self._entries.clear()
        self._save()

    @property
    def entries(self) -> list:
        return list(self._entries)

    def _load(self):
        try:
            self._entries = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
            if not isinstance(self._entries, list):
                self._entries = []
        except Exception:
            self._entries = []

    def _save(self):
        try:
            _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            _HISTORY_FILE.write_text(
                json.dumps(self._entries, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# TrayManager — system tray icon + desktop notifications
# ---------------------------------------------------------------------------
class TrayManager:
    def __init__(self, window: QWidget):
        self._win = window
        self._tray = QSystemTrayIcon(window)
        # use the app icon for tray if available, otherwise fall back to the programmatic dot
        if not _APP_ICON.isNull():
            self._tray.setIcon(_APP_ICON)
        else:
            px = QPixmap(20, 20)
            px.fill(Qt.transparent)
            pp = QPainter(px)
            pp.setRenderHint(QPainter.Antialiasing)
            pp.setBrush(QColor(56, 189, 248))
            pp.setPen(Qt.NoPen)
            pp.drawEllipse(2, 2, 16, 16)
            pp.end()
            self._tray.setIcon(QIcon(px))
        menu = QMenu()
        a_show = QAction("Open VCD", window)
        a_show.triggered.connect(window.show)
        a_show.triggered.connect(window.raise_)
        a_quit = QAction("Quit", window)
        a_quit.triggered.connect(QApplication.quit)
        menu.addAction(a_show)
        menu.addSeparator()
        menu.addAction(a_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activate)
        self._tray.show()

    def _on_activate(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self._win.isVisible():
                self._win.hide()
            else:
                self._win.show()
                self._win.raise_()

    def notify(self, title: str, msg: str, error: bool = False):
        if QSystemTrayIcon.isSystemTrayAvailable():
            kind = QSystemTrayIcon.Critical if error else QSystemTrayIcon.Information
            self._tray.showMessage(title, msg, kind, 5000)

    def set_tip(self, text: str):
        self._tray.setToolTip(text)

    @staticmethod
    def available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()


# ---------------------------------------------------------------------------
# _StreamRouter — hijacks stdout/stderr, parses everything into callbacks
# ---------------------------------------------------------------------------
class _StreamRouter:
    _ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
    _LOG = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s+([A-Z]+)\s+(.*)$")
    _PCT = re.compile(r"(\d{1,3})\s*%")
    _SPD = re.compile(r"([\d.]+)\s*([kKmMgG]?[Bb])(?:yte)?s?/s")
    _ETA = re.compile(r"<(\d{1,2}:\d{2}(?::\d{2})?)")
    _BYTES = re.compile(r"([\d.]+\s*[kKmMgG]?B)\s*/\s*([\d.]+\s*[kKmMgG]?B)")

    def __init__(self, on_log, on_progress, on_speed=None, on_eta=None, on_bytes=None):
        self.on_log = on_log
        self.on_progress = on_progress
        self.on_speed = on_speed
        self.on_eta = on_eta
        self.on_bytes = on_bytes
        self._buf = ""
        self._last = {}

    def write(self, s):
        if not s:
            return
        if not isinstance(s, str):
            try:
                s = s.decode("utf-8", "replace")
            except Exception:
                s = str(s)
        self._buf += s
        while True:
            m = re.search(r"[\r\n]", self._buf)
            if not m:
                break
            seg = self._buf[: m.start()]
            self._buf = self._buf[m.start() + 1 :]
            self._emit(seg)

    def flush(self):
        if self._buf.strip():
            self._emit(self._buf)
            self._buf = ""

    def isatty(self):
        return False

    def _emit(self, seg):
        seg = self._ANSI.sub("", seg).rstrip()
        if not seg:
            return
        lm = self._LOG.match(seg)
        if lm:
            self.on_log(lm.group(2), lm.group(3))
            return
        if "%" in seg:
            pm = self._PCT.search(seg)
            if pm:
                pct = max(0, min(100, int(pm.group(1))))
                if "Merg" in seg or "FFmpeg" in seg or "µs" in seg:
                    mode = "render"
                elif "\u2193" in seg or "B/s" in seg or "B [" in seg:
                    mode = "download"
                    if self.on_speed:
                        sm = self._SPD.search(seg)
                        if sm:
                            self.on_speed(f"{sm.group(1)} {sm.group(2).upper()}/s")
                    if self.on_eta:
                        em = self._ETA.search(seg)
                        if em:
                            self.on_eta(em.group(1))
                    if self.on_bytes:
                        bm = self._BYTES.search(seg)
                        if bm:
                            self.on_bytes(bm.group(1).strip(), bm.group(2).strip())
                else:
                    mode = "busy"
                if self._last.get(mode) != pct:
                    self._last[mode] = pct
                    self.on_progress(mode, pct)
                return
        self.on_log("LOG", seg)


# ---------------------------------------------------------------------------
# Worker — runs core pipeline off the UI thread
# ---------------------------------------------------------------------------
class _Cancelled(Exception):
    """Internal exception to cleanly break the pipeline on user cancellation."""

    pass


class Worker(QObject):
    # Native Qt Signals for GUI Updates
    sig_log = Signal(str, str)
    sig_progress = Signal(str, int)
    sig_stage = Signal(str)
    sig_done = Signal(bool, str, str)

    def __init__(self, params: dict):
        super().__init__()
        self.p = params
        self._cancel = False

        # Instantiate objects to hold state, eliminating globals
        self.downloader = Downloader()
        self.renderer: Renderer | None = None

    def cancel(self):
        """Triggered by the GUI's Stop button. Cascades termination safely."""
        self._cancel = True
        self.downloader.cancel()
        if self.renderer:
            self.renderer.cancel()

    def _ck(self):
        """Check point. Raises an exception to abort if cancellation was requested."""
        if self._cancel:
            raise _Cancelled()

    @Slot()
    def run(self):
        p = self.p
        old_cwd = os.getcwd()
        try:
            out_dir = Path(p["output_dir"]).expanduser()
            out_dir.mkdir(parents=True, exist_ok=True)
            os.chdir(out_dir)

            self.sig_stage.emit("Checking FFmpeg...")
            tools = init_tools()
            # Initialize Renderer with the verified FFmpeg path
            self.renderer = Renderer(tools.ffmpeg)
            self._ck()

            rid = p["rid"]
            result_dir = Path(rid)

            # --- 1. DOWNLOAD STAGE ---
            if p["reuse"] and result_dir.is_dir():
                self.sig_log.emit(
                    "INFO", f"Found existing folder '{rid}' — skipping download."
                )
            else:
                self.sig_stage.emit("Downloading class files...")
                dl_cfg = DownloadConfig(verify_ssl=p["verify_ssl"])

                session = acquire_authenticated_session(
                    p["url"], dl_cfg, p.get("cookie")
                )
                self._ck()

                # Execute download, passing the GUI signal directly as a callback
                self.downloader.download_and_extract(
                    url=p["url"],
                    target_dir=result_dir,
                    session=session,
                    cfg=dl_cfg,
                    progress_cb=lambda pct: self.sig_progress.emit("download", pct),
                )
            self._ck()

            # --- 2. TIMELINE STAGE ---
            rcfg = RenderConfig(
                canvas_w=p["w"],
                canvas_h=p["h"],
                fps=p["fps"],
                crf=p["crf"],
                video_preset=p["vp"],
                audio_bitrate=p["ab"],
                padding_ms=p["pad"],
                gpu=p.get("gpu", "cpu"),
            )

            self.sig_stage.emit("Building timeline...")
            sc, ac, global_base = collect_media_intervals(result_dir, tools.ffprobe)

            if not sc and not ac:
                raise VCDError("No valid media files with pacingTick were found.")

            total_ms = (
                max((c["end_ms"] for c in sc + ac), default=0.0) + rcfg.padding_ms
            )
            xml_path = result_dir / "timeline.xml"

            # The TypeError Trap is fixed here: we removed the unused 'folder' arg
            write_timeline_xml(sc, ac, total_ms, xml_path)
            self._ck()

            out_path = xml_path.resolve()

            # --- 3. RENDER STAGE ---
            if not p["xml_only"]:
                self.sig_stage.emit("Rendering video...")
                output_video = Path(p["output_name"]).resolve()

                # Inject the renderer instance into the function to maintain state
                render_video_from_timeline(
                    renderer=self.renderer,
                    media_folder=result_dir,
                    timeline_path=xml_path,
                    output_video=output_video,
                    cfg=rcfg,
                    progress_cb=lambda pct: self.sig_progress.emit("render", pct),
                )
                out_path = output_video
            self._ck()

            self.sig_done.emit(True, "Done! 🎓", str(out_path))

        except _Cancelled:
            # Silent catch for deliberate interruptions
            self.sig_done.emit(False, "Stopped.", "")

        except Exception as exc:
            # Catch genuine crashes, unless they happened during a cancellation
            if self._cancel:
                self.sig_done.emit(False, "Stopped.", "")
            else:
                self.sig_done.emit(False, str(exc), "")

        finally:
            os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------
class MainWindow(StarField):
    def __init__(self):
        super().__init__(n=160)
        try:
            import base64

            _ico_bytes = base64.b64decode(_APP_ICON_B64)
            _icon_px = QPixmap()
            _icon_px.loadFromData(_ico_bytes)
            self.setWindowIcon(QIcon(_icon_px))
        except Exception:
            pass
        self.setWindowTitle("VCD v0.3 — Vadana Class Downloader")
        self.resize(1360, 860)
        self.setMinimumSize(1100, 700)

        self.thread = None
        self.worker = None
        self._running = False
        self._last_output = ""
        self._last_params = None
        self._retry_count = 0
        self._loading_preset = False
        self._fname_touched = False
        self._active_preset = DEFAULT_PRESET
        self._bar_mode = ""

        # log model for filter/search
        self._log_all: list = []  # (level, ts, msg, html_fragment)
        self._log_filter = "ALL"
        self._log_search = ""

        # elapsed time
        self._elapsed = 0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._elapsed_tick)

        # batch queue
        self._queue: list = []

        # persistent data
        self._history = JobHistoryDB()

        # url history + cookie profiles (loaded from settings)
        self._url_history: list = []
        self._cookie_profiles: dict = {}
        self._url_completer_model = QStringListModel([])

        self.settings = QSettings("VCD", "VCD-GUI-v04")
        self._tray = None

        self._build_ui()
        self._wire()
        self._setup_shortcuts()
        self._load_settings()
        self._refresh_detected()
        self._system_check()
        self._detect_gpu_encoders()
        self._setup_tray()

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _section(text):
        lbl = QLabel(text.upper())
        lbl.setObjectName("section")
        return lbl

    @staticmethod
    def _fld(text):
        lbl = QLabel(text)
        lbl.setObjectName("fld")
        return lbl

    @staticmethod
    def _glow(widget, color, blur=24, alpha=180):
        eff = QGraphicsDropShadowEffect(widget)
        eff.setBlurRadius(blur)
        c = QColor(color)
        c.setAlpha(alpha)
        eff.setColor(c)
        eff.setOffset(0, 0)
        widget.setGraphicsEffect(eff)
        return eff

    def _highlight_preset(self, name, active):
        btn = self.preset_btns.get(name)
        if btn:
            btn.setStyleSheet(_PRESET_ACTIVE if active else "")

    def _select_preset(self, name):
        self._active_preset = name
        for n in self.preset_btns:
            self._highlight_preset(n, n == name)

    # ── layout ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 14)
        root.setSpacing(12)
        root.addLayout(self._build_header())
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._build_left())
        self._splitter.addWidget(self._build_right())
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([500, 840])
        root.addWidget(self._splitter, 1)

    def _build_header(self):
        row = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        self.title = QLabel("VCD")
        self.title.setObjectName("title")
        self._glow(self.title, SKY, 30, 155)
        self.subtitle = QLabel("VADANA CLASS DOWNLOADER  ·  v0.3")
        self.subtitle.setObjectName("subtitle")
        self.tagline = QLabel("batch · history · tray · GPU encode · auto-retry")
        self.tagline.setObjectName("tagline")
        left.addWidget(self.title)
        left.addWidget(self.subtitle)
        left.addWidget(self.tagline)

        self.links_lbl = QLabel(
            '<a href="https://t.me/IAUCourseExp" '
            'style="color:#38bdf8;text-decoration:none;font-weight:600;">'
            "@IAUCourseExp</a>"
            '<span style="color:#1a3050;">  ·  </span>'
            '<a href="https://t.me/JozveIAU" '
            'style="color:#38bdf8;text-decoration:none;font-weight:600;">'
            "@JozveIAU</a>"
            '<span style="color:#1a3050;">  ·  </span>'
            '<a href="https://github.com/IAUCourseExp/VCD" '
            'style="color:#fbbf24;text-decoration:none;font-weight:600;">'
            "⭐ Star on GitHub</a>"
        )
        self.links_lbl.setObjectName("links")
        self.links_lbl.setOpenExternalLinks(True)  # opens in default browser on click
        left.addWidget(self.links_lbl)

        row.addLayout(left)
        row.addStretch(1)
        right = QVBoxLayout()
        right.setSpacing(4)
        sysrow = QHBoxLayout()
        sysrow.setSpacing(12)
        self.sc_ff = QLabel("FFmpeg …")
        self.sc_ff.setObjectName("sys")
        self.sc_fp = QLabel("FFprobe …")
        self.sc_fp.setObjectName("sys")
        self.about_btn = QToolButton()
        self.about_btn.setObjectName("about")
        self.about_btn.setText("?")
        self.about_btn.setFixedSize(28, 28)
        self.about_btn.setCursor(Qt.PointingHandCursor)
        sysrow.addStretch(1)
        for w in (self.sc_ff, self.sc_fp, self.about_btn):
            sysrow.addWidget(w)
        right.addStretch(1)
        right.addLayout(sysrow)
        row.addLayout(right)
        return row

    # ── left panel ───────────────────────────────────────────────────────────

    def _build_left(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(460)
        scroll.setMaximumWidth(545)
        scroll.setStyleSheet("background:transparent;")
        scroll.viewport().setStyleSheet("background:transparent;")

        panel = QFrame()
        panel.setObjectName("panel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(10)

        # ── URL ──
        v.addWidget(self._section("Class URL"))
        self.url_edit = QLineEdit()
        self.url_edit.setLayoutDirection(Qt.LeftToRight)
        self.url_edit.setPlaceholderText("Paste your class URL here")
        self.url_edit.setClearButtonEnabled(True)
        v.addWidget(self.url_edit)

        self.detected = QLabel("ID: —")
        self.detected.setObjectName("detected")
        v.addWidget(self.detected)

        # cookie + profile row
        cr = QHBoxLayout()
        self.cookie_edit = QLineEdit()
        self.cookie_edit.setLayoutDirection(Qt.LeftToRight)
        self.cookie_edit.setPlaceholderText(
            "Cookie  (optional — only if no ?session= in URL)"
        )
        cr.addWidget(self.cookie_edit, 1)
        self.cookie_profile_cb = QComboBox()
        self.cookie_profile_cb.setMinimumWidth(108)
        self.cookie_profile_cb.setToolTip("Saved cookie profiles")
        cr.addWidget(self.cookie_profile_cb)
        save_prof_btn = QPushButton("Save")
        save_prof_btn.setObjectName("ghost")
        save_prof_btn.setCursor(Qt.PointingHandCursor)
        save_prof_btn.setToolTip("Save current cookie under a name")
        save_prof_btn.clicked.connect(self._save_cookie_profile_dialog)
        cr.addWidget(save_prof_btn)
        v.addLayout(cr)

        # output folder + filename
        dr = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setLayoutDirection(Qt.LeftToRight)
        self.dir_edit.setPlaceholderText("Save to folder")
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setObjectName("ghost")
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        dr.addWidget(self.dir_edit, 1)
        dr.addWidget(self.browse_btn)
        v.addLayout(dr)

        self.fname_edit = QLineEdit()
        self.fname_edit.setLayoutDirection(Qt.LeftToRight)
        self.fname_edit.setPlaceholderText("Filename  (auto-filled from URL)")
        v.addWidget(self.fname_edit)

        # disk space indicator
        self.disk_lbl = QLabel("")
        self.disk_lbl.setObjectName("disk_ok")
        v.addWidget(self.disk_lbl)

        # ── Batch Queue section (visible when queue has items) ──
        self.queue_frame = QFrame()
        self.queue_frame.setObjectName("queue_frame")
        qv = QVBoxLayout(self.queue_frame)
        qv.setContentsMargins(10, 8, 10, 8)
        qv.setSpacing(6)
        qh = QHBoxLayout()
        qh.addWidget(self._section("Batch Queue"))
        qh.addStretch(1)
        self.queue_count_lbl = QLabel("0 pending")
        self.queue_count_lbl.setObjectName("note")
        qh.addWidget(self.queue_count_lbl)
        self.queue_clear_btn = QPushButton("Clear")
        self.queue_clear_btn.setObjectName("ghost")
        self.queue_clear_btn.setCursor(Qt.PointingHandCursor)
        self.queue_clear_btn.clicked.connect(self._queue_clear)
        qh.addWidget(self.queue_clear_btn)
        qv.addLayout(qh)
        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(120)
        self.queue_list.setSelectionMode(QAbstractItemView.SingleSelection)
        qv.addWidget(self.queue_list)
        qbr = QHBoxLayout()
        self.queue_remove_btn = QPushButton("Remove selected")
        self.queue_remove_btn.setObjectName("ghost")
        self.queue_remove_btn.setCursor(Qt.PointingHandCursor)
        self.queue_remove_btn.clicked.connect(self._queue_remove_selected)
        self.queue_run_btn = QPushButton("▶  Run Queue")
        self.queue_run_btn.setObjectName("ghost")
        self.queue_run_btn.setCursor(Qt.PointingHandCursor)
        self.queue_run_btn.clicked.connect(self._queue_run)
        qbr.addWidget(self.queue_remove_btn)
        qbr.addStretch(1)
        qbr.addWidget(self.queue_run_btn)
        qv.addLayout(qbr)
        self.queue_frame.setVisible(False)
        v.addWidget(self.queue_frame)

        # ── Quality presets ──
        v.addSpacing(2)
        v.addWidget(self._section("Quality"))
        self.preset_group = QButtonGroup(self)
        self.preset_group.setExclusive(True)
        self.preset_btns = {}
        self._btn_name = {}
        grid = QGridLayout()
        grid.setSpacing(7)
        for i, name in enumerate(PRESETS):
            b = QPushButton(name)
            b.setObjectName("preset")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.preset_group.addButton(b)
            self.preset_btns[name] = b
            self._btn_name[b] = name
            grid.addWidget(b, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        v.addLayout(grid)
        self.preset_note = QLabel("")
        self.preset_note.setObjectName("note")
        self.preset_note.setWordWrap(True)
        v.addWidget(self.preset_note)

        # ── Advanced settings (collapsible) ──
        self.adv_btn = QToolButton()
        self.adv_btn.setObjectName("advbtn")
        self.adv_btn.setText("▸  Advanced settings")
        self.adv_btn.setCheckable(True)
        self.adv_btn.setCursor(Qt.PointingHandCursor)
        v.addWidget(self.adv_btn)
        self.adv = QFrame()
        self.adv.setObjectName("adv")
        self.adv.setVisible(False)
        ag = QGridLayout(self.adv)
        ag.setContentsMargins(12, 12, 12, 12)
        ag.setHorizontalSpacing(8)
        ag.setVerticalSpacing(8)
        self.res_cb = QComboBox()
        self.res_cb.addItems(RESOLUTIONS)
        self.fps_sb = QSpinBox()
        self.fps_sb.setRange(5, 60)
        self.crf_sl = QSlider(Qt.Horizontal)
        self.crf_sl.setRange(0, 51)
        self.crf_val = QLabel("28")
        self.crf_val.setFixedWidth(26)
        self.crf_val.setAlignment(Qt.AlignCenter)
        self.ab_cb = QComboBox()
        self.ab_cb.addItems(ABITRATES)
        self.vp_cb = QComboBox()
        self.vp_cb.addItems(VPRESETS)
        self.pad_sb = QSpinBox()
        self.pad_sb.setRange(0, 15000)
        self.pad_sb.setSingleStep(250)
        self.pad_sb.setSuffix(" ms")
        crf_w = QWidget()
        cl = QHBoxLayout(crf_w)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        cl.addWidget(self.crf_sl, 1)
        cl.addWidget(self.crf_val)
        ag.addWidget(self._fld("Resolution"), 0, 0)
        ag.addWidget(self.res_cb, 0, 1)
        ag.addWidget(self._fld("FPS"), 0, 2)
        ag.addWidget(self.fps_sb, 0, 3)
        ag.addWidget(self._fld("Quality CRF"), 1, 0)
        ag.addWidget(crf_w, 1, 1)
        ag.addWidget(self._fld("Audio"), 1, 2)
        ag.addWidget(self.ab_cb, 1, 3)
        ag.addWidget(self._fld("Encoder"), 2, 0)
        ag.addWidget(self.vp_cb, 2, 1)
        ag.addWidget(self._fld("Tail pad"), 2, 2)
        ag.addWidget(self.pad_sb, 2, 3)
        # GPU encoder selector
        self.gpu_cb = QComboBox()
        self.gpu_cb.addItems(GPU_OPTIONS)
        self.gpu_cb.setToolTip(
            "CPU: always works, slower.\n"
            "NVIDIA/AMD/Intel: much faster — needs the right GPU + drivers.\n"
            "If unsure, leave on CPU."
        )
        ag.addWidget(self._fld("GPU Encode"), 3, 0)
        ag.addWidget(self.gpu_cb, 3, 1, 1, 3)
        self.xml_chk = QCheckBox("Build timeline only  (no video)")
        self.ssl_chk = QCheckBox("Verify SSL  (usually off for IAU servers)")
        self.reuse_chk = QCheckBox("Reuse already-downloaded files")
        self.reuse_chk.setChecked(True)
        self.auto_retry_chk = QCheckBox(
            f"Auto-retry on failure  (up to {_MAX_RETRIES}×)"
        )
        self.auto_retry_chk.setChecked(True)
        ag.addWidget(self.xml_chk, 4, 0, 1, 4)
        ag.addWidget(self.ssl_chk, 5, 0, 1, 4)
        ag.addWidget(self.reuse_chk, 6, 0, 1, 4)
        ag.addWidget(self.auto_retry_chk, 7, 0, 1, 4)
        v.addWidget(self.adv)

        v.addStretch(1)

        # ── Stats widget (hidden when idle) ──
        self.stats = StatsWidget(self)
        self.stats.setVisible(False)
        v.addWidget(self.stats)

        # ── Stage + retry + progress ──
        self.stage_lbl = QLabel("Ready")
        self.stage_lbl.setObjectName("stage")
        v.addWidget(self.stage_lbl)
        self.retry_lbl = QLabel("")
        self.retry_lbl.setObjectName("retry_lbl")
        self.retry_lbl.setVisible(False)
        v.addWidget(self.retry_lbl)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFormat(" %p% ")
        v.addWidget(self.bar)
        self.speed_lbl = QLabel("")
        self.speed_lbl.setObjectName("speed")
        self.speed_lbl.setAlignment(Qt.AlignRight)
        self.speed_lbl.setVisible(False)
        v.addWidget(self.speed_lbl)

        # ── Action buttons ──
        self.go_btn = QPushButton("⬇  Download & Render")
        self.go_btn.setObjectName("go")
        self.go_btn.setCursor(Qt.PointingHandCursor)
        self._go_glow = self._glow(self.go_btn, SKY, 18, 150)
        self._pulse = QPropertyAnimation(self._go_glow, b"blurRadius", self)
        self._pulse.setDuration(2200)
        self._pulse.setStartValue(10)
        self._pulse.setKeyValueAt(0.5, 34)
        self._pulse.setEndValue(10)
        self._pulse.setEasingCurve(QEasingCurve.InOutSine)
        self._pulse.setLoopCount(-1)
        self._pulse.start()
        v.addWidget(self.go_btn)

        # "Add to Queue" button — lets user queue URLs without starting
        qadd_row = QHBoxLayout()
        self.queue_add_btn = QPushButton("+ Add to Queue")
        self.queue_add_btn.setObjectName("ghost")
        self.queue_add_btn.setCursor(Qt.PointingHandCursor)
        self.queue_add_btn.setToolTip(
            "Add this URL to the batch queue.\n"
            "Queued jobs run one after another when you click 'Run Queue'.\n"
            "Shortcut: Ctrl+Shift+Q"
        )
        self.queue_add_btn.clicked.connect(self._queue_add_current)
        qadd_row.addWidget(self.queue_add_btn)
        qadd_row.addStretch(1)
        v.addLayout(qadd_row)

        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setVisible(False)
        v.addWidget(self.stop_btn)
        self.open_btn = QPushButton("📂  Open folder")
        self.open_btn.setObjectName("ghost")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.setVisible(False)
        v.addWidget(self.open_btn)

        scroll.setWidget(panel)
        return scroll

    # ── right panel: tab widget ───────────────────────────────────────────────

    def _build_right(self):
        self.right_tabs = QTabWidget()
        self.right_tabs.setObjectName("righttabs")
        self.right_tabs.addTab(self._build_log_tab(), "  Log  ")
        self.right_tabs.addTab(self._build_history_tab(), "  History  ")
        self.right_tabs.addTab(self._build_files_tab(), "  Output Files  ")
        self.right_tabs.currentChanged.connect(self._on_tab_changed)
        return self.right_tabs

    def _build_log_tab(self):
        panel = QFrame()
        panel.setObjectName("panel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 14, 16, 16)
        v.setSpacing(6)

        head = QHBoxLayout()
        head.addWidget(self._section("Live Log"))
        head.addStretch(1)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("ghost")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("ghost")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        head.addWidget(self.clear_btn)
        head.addWidget(self.save_btn)
        v.addLayout(head)

        # filter bar
        frow = QHBoxLayout()
        frow.setSpacing(5)
        self._filter_btns: dict = {}
        for level in ("ALL", "INFO", "STEP", "SUCCESS", "WARN", "ERROR"):
            btn = QPushButton(level)
            btn.setObjectName("filter_btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, lv=level: self._set_log_filter(lv))
            self._filter_btns[level] = btn
            frow.addWidget(btn)
        frow.addStretch(1)
        self.log_search = QLineEdit()
        self.log_search.setObjectName("log_search")
        self.log_search.setPlaceholderText("Search…")
        self.log_search.setMaximumWidth(140)
        self.log_search.setFixedHeight(24)
        frow.addWidget(self.log_search)
        v.addLayout(frow)
        self._set_filter_active("ALL")

        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(10000)
        v.addWidget(self.log, 1)

        self._append_log("INFO", "Ready — paste a URL and hit Download.")
        if core is None:
            self._append_log(
                "ERROR", "vcd_core.py not found. Check the startup error dialog."
            )
        return panel

    def _build_history_tab(self):
        panel = QFrame()
        panel.setObjectName("panel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 14, 16, 16)
        v.setSpacing(8)

        head = QHBoxLayout()
        head.addWidget(self._section("Job History"))
        head.addStretch(1)
        rb = QPushButton("Refresh")
        rb.setObjectName("ghost")
        rb.setCursor(Qt.PointingHandCursor)
        rb.clicked.connect(self._refresh_history)
        cb = QPushButton("Clear All")
        cb.setObjectName("ghost")
        cb.setCursor(Qt.PointingHandCursor)
        cb.clicked.connect(self._clear_history)
        head.addWidget(rb)
        head.addWidget(cb)
        v.addLayout(head)

        self.hist_table = QTableWidget()
        self.hist_table.setColumnCount(7)
        self.hist_table.setHorizontalHeaderLabels(
            ["Date", "ID", "Status", "Size", "Duration", "Preset", "File"]
        )
        self.hist_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.hist_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.hist_table.horizontalHeader().setStretchLastSection(True)
        self.hist_table.verticalHeader().setVisible(False)
        self.hist_table.setShowGrid(False)
        v.addWidget(self.hist_table, 1)
        self.hist_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.hist_table.customContextMenuRequested.connect(self._hist_context_menu)
        self.hist_table.doubleClicked.connect(self._hist_open_file)

        note = QLabel(
            "Right-click a row for options  ·  Double-click to open file  ·  Ctrl+H to focus"
        )
        note.setObjectName("note")
        v.addWidget(note)

        self._refresh_history()
        return panel

    def _build_files_tab(self):
        panel = QFrame()
        panel.setObjectName("panel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 14, 16, 16)
        v.setSpacing(8)

        head = QHBoxLayout()
        head.addWidget(self._section("Output Files"))
        head.addStretch(1)
        rf = QPushButton("Refresh")
        rf.setObjectName("ghost")
        rf.setCursor(Qt.PointingHandCursor)
        rf.clicked.connect(self._refresh_files)
        head.addWidget(rf)
        v.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent;")
        scroll.viewport().setStyleSheet("background:transparent;")
        self._files_container = QWidget()
        self._files_container.setStyleSheet("background:transparent;")
        self._files_layout = QVBoxLayout(self._files_container)
        self._files_layout.setContentsMargins(0, 0, 0, 0)
        self._files_layout.setSpacing(8)
        self._files_layout.addStretch(1)
        scroll.setWidget(self._files_container)
        v.addWidget(scroll, 1)

        self._refresh_files()
        return panel

    # ── wiring ───────────────────────────────────────────────────────────────

    def _wire(self):
        self.url_edit.textChanged.connect(self._refresh_detected)
        self.url_edit.textChanged.connect(self._update_disk_label)
        self.url_edit.returnPressed.connect(self._start)
        self.dir_edit.textChanged.connect(self._update_disk_label)
        self.fname_edit.textEdited.connect(
            lambda *_: setattr(self, "_fname_touched", True)
        )
        self.browse_btn.clicked.connect(self._browse_dir)
        self.cookie_profile_cb.currentIndexChanged.connect(
            self._on_cookie_profile_selected
        )
        self.preset_group.buttonClicked.connect(
            lambda b: self._on_preset_click(self._btn_name.get(b, "Custom"))
        )
        self.adv_btn.toggled.connect(self._toggle_adv)
        self.res_cb.currentIndexChanged.connect(self._on_adv_changed)
        self.fps_sb.valueChanged.connect(self._on_adv_changed)
        self.crf_sl.valueChanged.connect(self._on_crf)
        self.ab_cb.currentIndexChanged.connect(self._on_adv_changed)
        self.vp_cb.currentIndexChanged.connect(self._on_adv_changed)
        self.gpu_cb.currentIndexChanged.connect(self._on_adv_changed)
        self.pad_sb.valueChanged.connect(self._on_adv_changed)
        self.go_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        self.open_btn.clicked.connect(self._open_output)
        self.clear_btn.clicked.connect(self._clear_log)
        self.save_btn.clicked.connect(self._save_log)
        self.about_btn.clicked.connect(self._about)
        self.log_search.textChanged.connect(self._on_log_search)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._start)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._stop)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(
            lambda: self.right_tabs.setCurrentIndex(0)
        )
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(
            lambda: self.right_tabs.setCurrentIndex(1)
        )
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
            lambda: (self.right_tabs.setCurrentIndex(0), self.log_search.setFocus())
        )
        QShortcut(QKeySequence("Ctrl+Shift+C"), self).activated.connect(self._clear_log)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save_log)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)
        QShortcut(QKeySequence("Ctrl+Shift+Q"), self).activated.connect(
            self._queue_add_current
        )

    def _setup_tray(self):
        if TrayManager.available():
            self._tray = TrayManager(self)
            self._tray.set_tip("VCD v0.3 — Vadana Class Downloader")

    # ── preset ────────────────────────────────────────────────────────────────

    def _toggle_adv(self, on):
        self.adv.setVisible(on)
        self.adv_btn.setText(("▾" if on else "▸") + "  Advanced settings")

    def _apply_preset(self, name):
        btn = self.preset_btns.get(name)
        if btn:
            btn.setChecked(True)
        self._select_preset(name)
        cfg = PRESETS.get(name)
        if cfg is None:
            return
        self._loading_preset = True
        try:
            self.res_cb.setCurrentText(f"{cfg['w']}x{cfg['h']}")
            self.fps_sb.setValue(cfg["fps"])
            self.crf_sl.setValue(cfg["crf"])
            self.ab_cb.setCurrentText(cfg["ab"])
            self.vp_cb.setCurrentText(cfg["vp"])
            self.pad_sb.setValue(cfg["pad"])
            self.preset_note.setText(cfg["note"])
        finally:
            self._loading_preset = False

    def _on_preset_click(self, name):
        self._apply_preset(name)
        if name == "Custom":
            self.adv_btn.setChecked(True)
            self.preset_note.setText("Custom — adjust the Advanced settings below.")

    def _on_adv_changed(self, *_):
        if self._loading_preset:
            return
        self._select_preset("Custom")
        self.preset_btns["Custom"].setChecked(True)
        self.preset_note.setText("Custom settings.")

    def _on_crf(self, v):
        self.crf_val.setText(str(v))
        self._on_adv_changed()

    def _read_render_params(self) -> dict:
        try:
            w, h = self.res_cb.currentText().lower().split("x")
            w, h = int(w), int(h)
        except Exception:
            w, h = 1280, 720
        gpu_idx = max(0, min(self.gpu_cb.currentIndex(), len(GPU_KEYS) - 1))
        return dict(
            w=w,
            h=h,
            fps=self.fps_sb.value(),
            crf=self.crf_sl.value(),
            vp=self.vp_cb.currentText(),
            ab=self.ab_cb.currentText(),
            pad=self.pad_sb.value(),
            gpu=GPU_KEYS[gpu_idx],
        )

    def _current_preset_name(self) -> str:
        for name, btn in self.preset_btns.items():
            if btn.isChecked():
                return name
        return "Custom"

    # ── URL / detection ───────────────────────────────────────────────────────

    @staticmethod
    def _rid_of(url: str):
        try:
            return urlparse(url).path.rstrip("/").split("/")[-1] or None
        except Exception:
            return None

    @staticmethod
    def _token_of(url: str):
        try:
            return parse_qs(urlparse(url).query).get("session", [None])[0]
        except Exception:
            return None

    def _refresh_detected(self):
        url = self.url_edit.text().strip()
        rid = self._rid_of(url) if url else None
        tok = self._token_of(url) if url else None
        tok_txt = (
            f"session ✓  {tok[:8]}…"
            if tok
            else "no session token — paste cookie if needed"
        )
        self.detected.setText(f"ID: {rid or '—'}   ·   {tok_txt}")
        if rid and not self._fname_touched:
            self.fname_edit.blockSignals(True)
            self.fname_edit.setText(f"Class-{rid}.mp4")
            self.fname_edit.blockSignals(False)

    def _update_disk_label(self):
        out_dir = self.dir_edit.text().strip() or os.getcwd()
        ok, label = _disk_free(out_dir)
        if label:
            self.disk_lbl.setObjectName("disk_ok" if ok else "disk_warn")
            prefix = "💾 " if ok else "⚠ Low disk: "
            self.disk_lbl.setText(prefix + label)
            self.disk_lbl.style().unpolish(self.disk_lbl)
            self.disk_lbl.style().polish(self.disk_lbl)

    def _system_check(self):
        if core is None:
            for w in (self.sc_ff, self.sc_fp):
                w.setText("core missing")
                w.setStyleSheet(f"color:{RED};")
            return
        ff = core.find_tool("ffmpeg")
        fp = core.find_tool("ffprobe")
        for w, ok, name, path in (
            (self.sc_ff, ff, "FFmpeg", ff),
            (self.sc_fp, fp, "FFprobe", fp),
        ):
            w.setText(f"{name} {'✓' if ok else '✗'}")
            w.setStyleSheet(f"color:{GREEN if ok else RED}; font-weight:700;")
            if path:
                w.setToolTip(str(path))
        if not (ff and fp):
            self._append_log(
                "WARN", "FFmpeg or FFprobe not found — rendering will fail."
            )

    def _detect_gpu_encoders(self):
        """Run ffmpeg -encoders and grey out GPU options that aren't compiled in."""
        if core is None:
            return
        ff = core.find_tool("ffmpeg")
        if not ff:
            return
        try:
            import subprocess

            r = subprocess.run(
                [ff, "-encoders"], capture_output=True, text=True, timeout=6
            )
            out = r.stdout + r.stderr
            encoder_check = {
                "nvidia": "h264_nvenc",
                "amd": "h264_amf",
                "intel": "h264_qsv",
            }
            for i, key in enumerate(GPU_KEYS):
                if key == "cpu":
                    continue
                enc = encoder_check.get(key, "")
                available = enc in out
                item = self.gpu_cb.model().item(i)
                if item:
                    item.setEnabled(available)
                    if not available:
                        item.setText(GPU_OPTIONS[i] + "  ✗ not in your FFmpeg")
                    if available:
                        item.setText(GPU_OPTIONS[i] + "  ✓")
            # --- auto-select best available GPU (only if user has no saved preference) ---
            if not self.settings.value("gpu"):
                for auto_key in ("nvidia", "amd", "intel"):
                    if encoder_check.get(auto_key, "") in out:
                        self.gpu_cb.setCurrentIndex(GPU_KEYS.index(auto_key))
                        break
        except Exception:
            pass

    # ── cookie profiles ───────────────────────────────────────────────────────

    def _load_cookie_profiles(self):
        raw = self.settings.value("cookie_profiles", {}) or {}
        self._cookie_profiles = raw if isinstance(raw, dict) else {}
        self._refresh_profile_cb()

    def _refresh_profile_cb(self):
        self.cookie_profile_cb.blockSignals(True)
        self.cookie_profile_cb.clear()
        self.cookie_profile_cb.addItem("— profiles —")
        for name in self._cookie_profiles:
            self.cookie_profile_cb.addItem(name)
        self.cookie_profile_cb.blockSignals(False)

    def _on_cookie_profile_selected(self, idx):
        if idx <= 0:
            return
        name = self.cookie_profile_cb.currentText()
        val = self._cookie_profiles.get(name, "")
        if val:
            self.cookie_edit.setText(val)
            self._append_log("INFO", f"Cookie profile '{name}' loaded.")

    def _save_cookie_profile_dialog(self):
        cookie_val = self.cookie_edit.text().strip()
        if not cookie_val:
            QMessageBox.warning(self, "No Cookie", "Paste a cookie value first.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Save Cookie Profile")
        dialog.setMinimumWidth(310)
        dl = QVBoxLayout(dialog)
        dl.addWidget(QLabel("Profile name:"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("e.g. IAU Main Account")
        dl.addWidget(name_edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        dl.addWidget(btns)
        if dialog.exec() == QDialog.Accepted:
            name = name_edit.text().strip()
            if name:
                self._cookie_profiles[name] = cookie_val
                self.settings.setValue("cookie_profiles", self._cookie_profiles)
                self._refresh_profile_cb()
                self._append_log("INFO", f"Cookie profile '{name}' saved.")

    # ── URL history / autocomplete ────────────────────────────────────────────

    def _setup_url_completer(self):
        self._url_completer_model.setStringList(self._url_history)
        cmp = QCompleter(self._url_completer_model, self)
        cmp.setCaseSensitivity(Qt.CaseInsensitive)
        cmp.setFilterMode(Qt.MatchContains)
        self.url_edit.setCompleter(cmp)

    def _push_url_history(self, url: str):
        if url in self._url_history:
            self._url_history.remove(url)
        self._url_history.insert(0, url)
        self._url_history = self._url_history[:_MAX_URL_HIST]
        self._url_completer_model.setStringList(self._url_history)
        self.settings.setValue("url_history", self._url_history)

    # ── batch queue ───────────────────────────────────────────────────────────

    def _build_params_from_ui(self) -> Optional[dict]:
        url = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", self.url_edit.text().strip())
        if not url.startswith(("http://", "https://")):
            return None
        rid = self._rid_of(url)
        if not rid:
            return None
        out_dir = self.dir_edit.text().strip() or os.getcwd()
        fname = self.fname_edit.text().strip() or f"Class-{rid}.mp4"
        if not self.xml_chk.isChecked() and not fname.lower().endswith(".mp4"):
            fname += ".mp4"
        return dict(
            url=url,
            rid=rid,
            output_dir=out_dir,
            output_name=fname,
            cookie=self.cookie_edit.text().strip(),
            xml_only=self.xml_chk.isChecked(),
            verify_ssl=self.ssl_chk.isChecked(),
            reuse=self.reuse_chk.isChecked(),
            preset=self._current_preset_name(),
            **self._read_render_params(),
        )

    def _queue_add_current(self):
        params = self._build_params_from_ui()
        if params is None:
            QMessageBox.warning(self, "Bad URL", "Paste a valid class URL first.")
            return
        if params["url"] in [q["url"] for q in self._queue]:
            self._append_log("WARN", f"Already in queue: {params['rid']}")
            return
        self._queue.append(params)
        self._refresh_queue_ui()
        self._append_log(
            "INFO", f"Queued: {params['rid']}  ({len(self._queue)} total in queue)"
        )

    def _queue_run(self):
        if self._running:
            self._append_log(
                "WARN",
                "Job running — queue will continue automatically after it finishes.",
            )
            return
        if not self._queue:
            self._append_log("WARN", "Queue is empty.")
            return
        self._queue_next()

    def _queue_next(self):
        if not self._queue:
            self._append_log("SUCCESS", "Queue finished — all jobs done.")
            if self._tray:
                self._tray.notify("VCD — Queue Done", "All queued jobs completed.")
            return
        self._queue[0]["_status"] = "running"
        self._refresh_queue_ui()
        self._start_job(self._queue[0])

    def _queue_complete_current(self, ok: bool):
        if self._queue:
            self._queue[0]["_status"] = "done" if ok else "failed"
            self._refresh_queue_ui()
            self._queue.pop(0)
            self._refresh_queue_ui()
        if self._queue:
            QTimer.singleShot(1500, self._queue_next)

    def _queue_remove_selected(self):
        row = self.queue_list.currentRow()
        if 0 <= row < len(self._queue):
            removed = self._queue.pop(row)
            self._append_log("INFO", f"Removed from queue: {removed.get('rid', '?')}")
            self._refresh_queue_ui()

    def _queue_clear(self):
        self._queue.clear()
        self._refresh_queue_ui()
        self._append_log("INFO", "Queue cleared.")

    def _refresh_queue_ui(self):
        self.queue_list.clear()
        icons = {"pending": "⏳", "running": "▶", "done": "✓", "failed": "✗"}
        for item in self._queue:
            status = item.get("_status", "pending")
            label = f"{icons.get(status, '⏳')}  {item.get('rid', '?')}  —  {item.get('output_name', '')}"
            li = QListWidgetItem(label)
            li.setForeground(QColor(_QUEUE_CLR.get(status, "#7aacca")))
            self.queue_list.addItem(li)
        n = len(self._queue)
        self.queue_count_lbl.setText(f"{n} pending" if n else "empty")
        self.queue_frame.setVisible(n > 0)

    # ── job start / stop ──────────────────────────────────────────────────────

    def _start(self):
        if self._running:
            return
        if core is None:
            QMessageBox.critical(self, "Missing vcd_core.py", _core_err)
            return
        params = self._build_params_from_ui()
        if params is None:
            url = self.url_edit.text().strip()
            msg = (
                "URL must start with http:// or https://"
                if not url.startswith(("http://", "https://"))
                else "No recording ID found in that URL."
            )
            self._append_log("ERROR", msg)
            QMessageBox.warning(self, "Bad URL", msg)
            return
        ok, label = _disk_free(params["output_dir"])
        if not ok:
            r = QMessageBox.warning(
                self,
                "Low Disk Space",
                f"Only {label} in the output folder.\nContinue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                return
        self._save_settings()
        self._push_url_history(params["url"])
        self._retry_count = 0
        self._stop_requested = False  # True when user explicitly clicked Stop
        self._last_params = params
        self._start_job(params)

    def _start_job(self, params: dict):
        self._stop_requested = False
        self._set_running(True)
        self._elapsed = 0
        self.stats.reset()
        self.stats.setVisible(True)
        self._elapsed_timer.start()
        if self._tray:
            self._tray.set_tip(f"VCD — Downloading {params.get('rid', '')}…")
        self._append_log("STEP", f"Starting: {params['rid']}")
        self._append_log(
            "INFO",
            f"Output → {os.path.join(params['output_dir'], params['output_name'])}",
        )
        self.thread = QThread(self)
        self.worker = Worker(params)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.sig_log.connect(self._append_log)
        self.worker.sig_progress.connect(self._on_progress)
        self.worker.sig_stage.connect(self._on_stage)
        self.worker.sig_speed.connect(self._on_speed)
        self.worker.sig_eta.connect(self._on_eta)
        self.worker.sig_bytes.connect(self._on_bytes)
        self.worker.sig_done.connect(self._on_done)
        self.worker.sig_done.connect(self.thread.quit)
        self.worker.sig_done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _stop(self):
        if not self._running:
            return
        self._stop_requested = True
        if self.worker:
            self.worker.cancel()  # sets flag + kills ffmpeg process
        self.stop_btn.setEnabled(False)
        self._queue.clear()
        self._refresh_queue_ui()
        self._append_log("WARN", "Stopping...")

    def _set_running(self, running: bool):
        self._running = running
        self.go_btn.setVisible(not running)
        self.queue_add_btn.setVisible(not running)
        self.stop_btn.setVisible(running)
        self.stop_btn.setEnabled(running)
        for w in (
            self.url_edit,
            self.cookie_edit,
            self.dir_edit,
            self.fname_edit,
            self.browse_btn,
            self.adv,
        ):
            w.setEnabled(not running)
        for name, btn in self.preset_btns.items():
            btn.setEnabled(not running)
            if running:
                btn.setStyleSheet("")
            else:
                self._highlight_preset(name, name == self._active_preset)
        if running:
            self.open_btn.setVisible(False)
            self.bar.setRange(0, 0)
            self.bar.setFormat("")
            self.speed_lbl.setVisible(False)
            self._bar_mode = ""

    def _elapsed_tick(self):
        self._elapsed += 1
        self.stats.set_elapsed(self._elapsed)

    # ── signal handlers ───────────────────────────────────────────────────────

    def _on_stage(self, text: str):
        self.stage_lbl.setText(text)
        self.bar.setRange(0, 0)
        self.bar.setFormat("")
        if self._tray:
            self._tray.set_tip(f"VCD — {text}")
        divider = f'<span style="color:#1a3655">{"─" * 6} {html.escape(text)} {"─" * 6}</span>'
        sb = self.log.verticalScrollBar()
        at_bot = sb.value() >= sb.maximum() - 6
        self.log.appendHtml(divider)
        if at_bot:
            sb.setValue(sb.maximum())

    def _on_progress(self, mode: str, pct: int):
        if mode == "busy":
            self.bar.setRange(0, 0)
            self.bar.setFormat("")
            return
        if mode != self._bar_mode:
            self._bar_mode = mode
            self.bar.setStyleSheet(_BAR_DOWNLOAD if mode == "download" else _BAR_RENDER)
            if mode != "download":
                self.speed_lbl.setVisible(False)
        self.bar.setRange(0, 100)
        self.bar.setFormat(" %p% ")
        self.bar.setValue(pct)
        verb = "Downloading" if mode == "download" else "Rendering"
        self.stage_lbl.setText(f"{verb}... {pct}%")
        if self._tray:
            self._tray.set_tip(f"VCD — {verb} {pct}%")

    def _on_speed(self, spd: str):
        self.speed_lbl.setText(spd)
        self.speed_lbl.setVisible(True)
        self.stats.push_speed(spd)

    def _on_eta(self, eta: str):
        self.stats.set_eta(eta)

    def _on_bytes(self, dl: str, total: str):
        self.stats.set_bytes(dl, total)

    def _on_done(self, ok: bool, message: str, out_path: str):
        self._elapsed_timer.stop()
        self._set_running(False)
        self.bar.setRange(0, 100)
        self.bar.setFormat(" %p% ")
        self.bar.setValue(100 if ok else 0)
        self.bar.setStyleSheet("")
        self.speed_lbl.setVisible(False)
        self.stats.setVisible(False)
        self.retry_lbl.setVisible(False)

        # gather file info before logging
        size_str, dur_str = "", ""
        if ok and out_path and os.path.isfile(out_path):
            size_str = _fmt_size(out_path)
            dur_sec = self._probe_duration(out_path)
            dur_str = _fmt_dur(dur_sec) if dur_sec > 0 else ""

        # add to history
        entry = {
            "id": str(uuid.uuid4())[:8],
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "rid": self._last_params.get("rid", "?") if self._last_params else "?",
            "status": "done" if ok else "failed",
            "output_path": out_path,
            "size": size_str,
            "duration": dur_str,
            "preset": self._last_params.get("preset", "?")
            if self._last_params
            else "?",
            "elapsed_sec": self._elapsed,
        }
        self._history.add(entry)
        self._refresh_history()

        if ok:
            self._append_log("SUCCESS", message)
            detail = "  ·  ".join(p for p in [size_str, dur_str] if p)
            if detail:
                self._append_log("INFO", f"{os.path.basename(out_path)}  ({detail})")
            self.stage_lbl.setText("Done ✓")
            self._last_output = out_path
            self.open_btn.setVisible(True)
            self.open_btn.setEnabled(bool(out_path))
            if self._tray:
                self._tray.notify(
                    "VCD — Done!",
                    f"{os.path.basename(out_path)} — {detail or 'finished'}",
                )
            QTimer.singleShot(600, lambda: self._maybe_extract_thumb(out_path))
            QTimer.singleShot(1000, lambda: self.right_tabs.setCurrentIndex(2))
        else:
            self._append_log("ERROR", message)
            self.stage_lbl.setText("Failed — check the log")
            if self._tray:
                self._tray.notify("VCD — Failed", message, error=True)
            if not self._auto_retry():
                if not self._auto_retry():
                    pass  # no retry possible; user sees the error

        self.thread = None
        self.worker = None
        self._queue_complete_current(ok)

    def _auto_retry(self) -> bool:
        if not self.auto_retry_chk.isChecked():
            return False
        if self._retry_count >= _MAX_RETRIES:
            self._append_log(
                "WARN", f"Max retries ({_MAX_RETRIES}) reached. Giving up."
            )
            return False
        if self._last_params is None:
            return False
        self._retry_count += 1
        secs = 5 * self._retry_count
        self._append_log(
            "WARN",
            f"Auto-retrying in {secs}s…  (attempt {self._retry_count}/{_MAX_RETRIES})",
        )
        self.retry_lbl.setText(
            f"⟳  Retrying in {secs}s   (attempt {self._retry_count}/{_MAX_RETRIES})"
        )
        self.retry_lbl.setVisible(True)
        QTimer.singleShot(
            secs * 1000,
            lambda: (
                self.retry_lbl.setVisible(False),
                self._start_job(self._last_params),
            ),
        )
        return True

    # ── video info + thumbnail ────────────────────────────────────────────────

    def _probe_duration(self, path: str) -> float:
        if core is None:
            return 0.0
        try:
            fp = core.find_tool("ffprobe")
            if fp:
                return core.probe_duration(fp, Path(path))
        except Exception:
            pass
        return 0.0

    def _maybe_extract_thumb(self, video_path: str):
        if not video_path or not os.path.isfile(video_path):
            return
        if core is None:
            return
        try:
            ff = core.find_tool("ffmpeg")
            if not ff:
                return
            dur = self._probe_duration(video_path)
            t = max(2.0, dur * 0.35) if dur > 0 else 30.0
            _THUMB_DIR.mkdir(parents=True, exist_ok=True)
            out = str(_THUMB_DIR / (Path(video_path).stem + ".jpg"))
            r = subprocess.run(
                [
                    ff,
                    "-y",
                    "-ss",
                    f"{t:.1f}",
                    "-i",
                    video_path,
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=260:-1",
                    "-q:v",
                    "4",
                    out,
                ],
                capture_output=True,
                timeout=12,
            )
            if r.returncode == 0 and Path(out).exists():
                self._history.update_last(thumb=out)
                self._refresh_files()
        except Exception:
            pass

    # ── history tab ───────────────────────────────────────────────────────────

    def _refresh_history(self):
        entries = self._history.entries
        self.hist_table.setRowCount(len(entries))
        for col, w in enumerate([130, 110, 70, 70, 70, 100]):
            self.hist_table.setColumnWidth(col, w)
        for row, e in enumerate(entries):
            status = e.get("status", "?")
            ok_col = GREEN if status == "done" else RED
            cells = [
                (e.get("date", ""), "#7aacca"),
                (e.get("rid", ""), "#c0dff0"),
                (("✓ " if status == "done" else "✗ ") + status, ok_col),
                (e.get("size", ""), "#7aacca"),
                (e.get("duration", ""), "#7aacca"),
                (e.get("preset", ""), "#5a88a8"),
                (os.path.basename(e.get("output_path", "")), "#5a88a8"),
            ]
            for col, (text, color) in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                item.setData(Qt.UserRole, e)
                self.hist_table.setItem(row, col, item)
            self.hist_table.setRowHeight(row, 30)

    def _hist_context_menu(self, pos):
        row = self.hist_table.rowAt(pos.y())
        if row < 0:
            return
        entries = self._history.entries
        if row >= len(entries):
            return
        e = entries[row]
        path = e.get("output_path", "")
        menu = QMenu(self)
        if path and os.path.isfile(path):
            menu.addAction("▶  Play file", lambda: self._play_file(path))
            menu.addAction("📂  Open folder", lambda: self._open_in_folder(path))
            menu.addSeparator()
            menu.addAction("🗑  Delete file", lambda: self._delete_output_file(path))
        menu.addAction(
            "✕  Remove from history",
            lambda: (self._history.remove(row), self._refresh_history()),
        )
        menu.exec(self.hist_table.viewport().mapToGlobal(pos))

    def _hist_open_file(self, index):
        entries = self._history.entries
        if index.row() < len(entries):
            path = entries[index.row()].get("output_path", "")
            if path and os.path.isfile(path):
                self._play_file(path)

    def _clear_history(self):
        r = QMessageBox.question(
            self,
            "Clear History?",
            "Delete all job history records?\n(Output files are not deleted.)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if r == QMessageBox.Yes:
            self._history.clear()
            self._refresh_history()
            self._append_log("INFO", "History cleared.")

    # ── output files tab ──────────────────────────────────────────────────────

    def _refresh_files(self):
        # remove all existing cards (except the trailing stretch)
        while self._files_layout.count() > 1:
            item = self._files_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        entries = [
            e
            for e in self._history.entries
            if e.get("output_path") and os.path.isfile(e["output_path"])
        ]
        if not entries:
            empty = QLabel(
                "No output files yet.\nDownload and render a class to see files here."
            )
            empty.setObjectName("note")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            self._files_layout.insertWidget(0, empty)
            return
        for e in entries:
            card = self._build_file_card(e)
            self._files_layout.insertWidget(self._files_layout.count() - 1, card)

    def _build_file_card(self, entry: dict) -> QFrame:
        path = entry.get("output_path", "")
        fname = os.path.basename(path)
        size = entry.get("size") or _fmt_size(path)
        dur = entry.get("duration", "")
        date = entry.get("date", "")
        thumb = entry.get("thumb", "")

        card = QFrame()
        card.setObjectName("card")
        row = QHBoxLayout(card)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(12)

        # thumbnail preview
        thumb_lbl = QLabel()
        thumb_lbl.setFixedSize(80, 46)
        thumb_lbl.setAlignment(Qt.AlignCenter)
        if thumb and os.path.isfile(thumb):
            px = QPixmap(thumb).scaled(
                80, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            thumb_lbl.setPixmap(px)
        else:
            thumb_lbl.setText("▶")
            thumb_lbl.setStyleSheet(
                "background:rgba(10,20,40,0.8);"
                "border:1px solid rgba(56,189,248,0.12);"
                "border-radius:4px; color:#1e3a55; font-size:18px;"
            )
        row.addWidget(thumb_lbl)

        # name + meta
        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(fname)
        name_lbl.setObjectName("file_name")
        meta_parts = [p for p in [size, dur, date] if p]
        meta_lbl = QLabel("  ·  ".join(meta_parts))
        meta_lbl.setObjectName("file_meta")
        info.addWidget(name_lbl)
        info.addWidget(meta_lbl)
        row.addLayout(info, 1)

        # action buttons
        bcol = QVBoxLayout()
        bcol.setSpacing(4)
        for icon, tip, fn, obj in [
            ("▶", "Play", lambda _=False, p=path: self._play_file(p), "icon_btn"),
            (
                "📂",
                "Open folder",
                lambda _=False, p=path: self._open_in_folder(p),
                "icon_btn",
            ),
            (
                "🗑",
                "Delete file",
                lambda _=False, p=path: self._delete_output_file(p),
                "danger_btn",
            ),
        ]:
            b = QPushButton(icon)
            b.setObjectName(obj)
            b.setToolTip(tip)
            b.setFixedWidth(32)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            bcol.addWidget(b)
        row.addLayout(bcol)
        return card

    # ── file / folder actions ─────────────────────────────────────────────────

    def _play_file(self, path: str):
        if os.path.isfile(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))
        else:
            self._append_log("WARN", f"File not found: {path}")

    def _open_in_folder(self, path: str):
        folder = os.path.dirname(path) if os.path.isfile(path) else path
        if not os.path.isdir(folder):
            folder = os.path.dirname(folder) or "."
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(folder)))

    def _delete_output_file(self, path: str):
        r = QMessageBox.question(
            self,
            "Delete File?",
            f"Permanently delete:\n{path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if r == QMessageBox.Yes:
            try:
                os.remove(path)
                self._append_log("INFO", f"Deleted: {os.path.basename(path)}")
                self._refresh_history()
                self._refresh_files()
            except Exception as exc:
                self._append_log("ERROR", f"Couldn't delete: {exc}")

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Choose output folder", self.dir_edit.text() or os.getcwd()
        )
        if d:
            self.dir_edit.setText(d)
            self._update_disk_label()

    def _open_output(self):
        self._open_in_folder(self._last_output)

    # ── log ───────────────────────────────────────────────────────────────────

    def _append_log(self, level: str, msg: str):
        color = LEVEL_COLOR.get(level, TEAL)
        icon = LEVEL_ICON.get(level, "·")
        ts = datetime.now().strftime("%H:%M:%S")
        safe = html.escape(str(msg)).replace("\n", "<br>")
        frag = (
            f'<span style="color:#1e3a55">[{ts}]</span> '
            f'<span style="color:{color};font-weight:700">{icon} {html.escape(level)}</span> '
            f'<span style="color:{color}">{safe}</span>'
        )
        self._log_all.append((level, ts, str(msg), frag))
        if self._log_filter in ("ALL", level):
            srch = self._log_search
            if not srch or srch in str(msg).lower() or srch in level.lower():
                sb = self.log.verticalScrollBar()
                at_bot = sb.value() >= sb.maximum() - 6
                self.log.appendHtml(frag)
                if at_bot:
                    sb.setValue(sb.maximum())

    def _clear_log(self):
        self.log.clear()
        self._log_all.clear()

    def _set_log_filter(self, level: str):
        self._log_filter = level
        self._set_filter_active(level)
        self._rebuild_log()

    def _set_filter_active(self, active: str):
        for lv, btn in self._filter_btns.items():
            btn.setProperty("active", "1" if lv == active else "0")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_log_search(self, text: str):
        self._log_search = text.strip().lower()
        self._rebuild_log()

    def _rebuild_log(self):
        lf = self._log_filter
        ls = self._log_search
        self.log.setUpdatesEnabled(False)
        self.log.clear()
        for lv, ts, msg, frag in self._log_all:
            if lf != "ALL" and lf != lv:
                continue
            if ls and ls not in msg.lower() and ls not in lv.lower():
                continue
            self.log.appendHtml(frag)
        self.log.setUpdatesEnabled(True)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _save_log(self):
        fn, _ = QFileDialog.getSaveFileName(
            self, "Save log", "vcd_log.txt", "Text (*.txt)"
        )
        if fn:
            try:
                lines = [f"[{ts}] {lv}  {msg}" for (lv, ts, msg, _) in self._log_all]
                Path(fn).write_text("\n".join(lines), encoding="utf-8")
                self._append_log("INFO", f"Log saved → {fn}")
            except Exception as exc:
                self._append_log("ERROR", f"Couldn't save log: {exc}")

    def _on_tab_changed(self, idx: int):
        if idx == 1:
            self._refresh_history()
        elif idx == 2:
            self._refresh_files()

    # ── about ─────────────────────────────────────────────────────────────────

    def _about(self):
        QMessageBox.information(
            self,
            "About VCD v0.3",
            "VCD — Vadana Class Downloader  v0.3\n"
            "github.com/IAUCourseExp/VCD\n\n"
            "What's new in v0.3:\n"
            "  Batch Queue — queue multiple URLs, run sequentially\n"
            "  Job History — permanent record in ~/.vcd/history.json\n"
            "  Output Files — browse, play, delete rendered videos\n"
            "  Real-time stats — ETA, bytes, speed graph\n"
            "  System tray — background operation + notifications\n"
            "  Cookie profiles — save multiple sessions\n"
            "  URL autocomplete — remembers recent URLs\n"
            "  Log filter + search — find what you need fast\n"
            "  Auto-retry — retries failed jobs automatically\n"
            "  Disk space check, video thumbnail, resizable splitter\n\n"
            "Keyboard shortcuts:\n"
            "  Ctrl+Enter    Start job\n"
            "  Esc           Stop job\n"
            "  Ctrl+L        Log tab\n"
            "  Ctrl+H        History tab\n"
            "  Ctrl+F        Focus log search\n"
            "  Ctrl+S        Save log\n"
            "  Ctrl+Shift+Q  Add current URL to queue\n"
            "  Ctrl+Q        Quit",
        )

    # ── settings persistence ──────────────────────────────────────────────────

    def _save_settings(self):
        s = self.settings
        s.setValue("url", self.url_edit.text())
        s.setValue("dir", self.dir_edit.text())
        s.setValue("preset", self._current_preset_name())
        s.setValue("res", self.res_cb.currentText())
        s.setValue("fps", self.fps_sb.value())
        s.setValue("crf", self.crf_sl.value())
        s.setValue("ab", self.ab_cb.currentText())
        s.setValue("vp", self.vp_cb.currentText())
        s.setValue("gpu", GPU_KEYS[max(0, self.gpu_cb.currentIndex())])
        s.setValue("pad", self.pad_sb.value())
        s.setValue("xml", self.xml_chk.isChecked())
        s.setValue("ssl", self.ssl_chk.isChecked())
        s.setValue("reuse", self.reuse_chk.isChecked())
        s.setValue("auto_retry", self.auto_retry_chk.isChecked())
        s.setValue("adv_open", self.adv_btn.isChecked())
        s.setValue("splitter", self._splitter.sizes())
        s.setValue("url_history", self._url_history)

    def _load_settings(self):
        s = self.settings
        saved_url = s.value("url", "")
        if saved_url:
            self.url_edit.setText(saved_url)
        self.dir_edit.setText(s.value("dir", os.getcwd()))

        preset = s.value("preset", DEFAULT_PRESET)
        if preset not in PRESETS:
            preset = DEFAULT_PRESET
        self._apply_preset(preset)

        if preset == "Custom":
            self._loading_preset = True
            try:
                self.res_cb.setCurrentText(s.value("res", "1280x720"))
                self.fps_sb.setValue(int(s.value("fps", 30)))
                self.crf_sl.setValue(int(s.value("crf", 28)))
                self.ab_cb.setCurrentText(s.value("ab", "96k"))
                self.vp_cb.setCurrentText(s.value("vp", "veryfast"))
                # saved_gpu = s.value("gpu", "cpu")
                # if saved_gpu in GPU_KEYS:
                #     self.gpu_cb.setCurrentIndex(GPU_KEYS.index(saved_gpu))
                self.pad_sb.setValue(int(s.value("pad", 2000)))
                self._select_preset("Custom")
                self.preset_btns["Custom"].setChecked(True)
                self.preset_note.setText("Custom settings.")
            except Exception:
                pass
            finally:
                self._loading_preset = False

        self.xml_chk.setChecked(_tobool(s.value("xml", False)))
        self.ssl_chk.setChecked(_tobool(s.value("ssl", False)))
        self.reuse_chk.setChecked(_tobool(s.value("reuse", True)))
        self.auto_retry_chk.setChecked(_tobool(s.value("auto_retry", True)))
        saved_gpu = self.settings.value("gpu", "")
        if saved_gpu in GPU_KEYS:
            self.gpu_cb.setCurrentIndex(GPU_KEYS.index(saved_gpu))
        self.adv_btn.setChecked(_tobool(s.value("adv_open", False)))

        sizes = s.value("splitter", None)
        if sizes:
            try:
                self._splitter.setSizes([int(x) for x in sizes])
            except Exception:
                pass

        hist = s.value("url_history", []) or []
        self._url_history = list(hist)[:_MAX_URL_HIST]
        self._setup_url_completer()
        self._load_cookie_profiles()
        self._update_disk_label()

    def closeEvent(self, e):
        if self._running and self.thread:
            r = QMessageBox.question(
                self,
                "Quit?",
                "A download is still running. Quit anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                e.ignore()
                return
            try:
                if self.worker:
                    self.worker.cancel()
                self.thread.quit()
                self.thread.wait(1500)
            except Exception:
                pass
        try:
            self.timer.stop()
        except Exception:
            pass
        self._elapsed_timer.stop()
        self._save_settings()
        e.accept()


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------
def main():

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "IAUCourseExp.VCD.v03"
            )
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("VCD")
    app.setWindowIcon(_APP_ICON)
    app.setStyleSheet(THEME)
    win = MainWindow()
    win.show()
    if core is None:
        QMessageBox.critical(win, "Missing vcd_core.py", _core_err)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

