from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap

_APP_ICON_B64 = "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"


def _load_app_icon() -> "QIcon":
    """Decode the embedded icon and return a QIcon. Falls back to empty on error."""
    try:
        import base64 as _b64

        data = _b64.b64decode(_APP_ICON_B64)
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            return QIcon(px)
    except Exception:
        pass
    return QIcon()


_APP_ICON = None

def get_app_icon():
    global _APP_ICON
    if _APP_ICON is None:
        _APP_ICON = _load_app_icon()
    return _APP_ICON

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
