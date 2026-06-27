from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from vcd.gui.constants import (
    _BAR_DOWNLOAD,
    _BAR_RENDER,
    _MAX_RETRIES,
    _PRESET_ACTIVE,
    _QUEUE_CLR,
    ABITRATES,
    GPU_OPTIONS,
    PRESETS,
    RESOLUTIONS,
    SKY,
    VPRESETS,
)
from vcd.gui.widgets.stats_panel import StatsWidget


class LeftPanel(QWidget):
    sig_url_changed = Signal(str)
    sig_url_return_pressed = Signal()
    sig_dir_changed = Signal(str)
    sig_fname_edited = Signal(str)
    sig_browse_clicked = Signal()
    sig_cookie_profile_selected = Signal(str)
    sig_save_cookie_profile = Signal()
    sig_preset_clicked = Signal(str)
    sig_adv_toggled = Signal(bool)
    sig_adv_changed = Signal()
    sig_crf_changed = Signal(int)
    sig_go_clicked = Signal()
    sig_stop_clicked = Signal()
    sig_open_output_clicked = Signal()
    sig_queue_add_clicked = Signal()
    sig_queue_run_clicked = Signal()
    sig_queue_remove_clicked = Signal()
    sig_queue_clear_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fname_touched = False
        self._loading_preset = False

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

        v.addWidget(self._section("Class URL"))
        self.url_edit = QLineEdit()
        self.url_edit.setLayoutDirection(Qt.LeftToRight)
        self.url_edit.setPlaceholderText("Paste your class URL here")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.textChanged.connect(self.sig_url_changed)
        self.url_edit.returnPressed.connect(self.sig_url_return_pressed)
        v.addWidget(self.url_edit)

        self.detected = QLabel("ID: —")
        self.detected.setObjectName("detected")
        v.addWidget(self.detected)

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
        self.cookie_profile_cb.currentIndexChanged.connect(
            lambda idx: (
                self.sig_cookie_profile_selected.emit(
                    self.cookie_profile_cb.currentText()
                )
                if idx > 0
                else None
            )
        )
        cr.addWidget(self.cookie_profile_cb)
        save_prof_btn = QPushButton("Save")
        save_prof_btn.setObjectName("ghost")
        save_prof_btn.setCursor(Qt.PointingHandCursor)
        save_prof_btn.setToolTip("Save current cookie under a name")
        save_prof_btn.clicked.connect(self.sig_save_cookie_profile)
        cr.addWidget(save_prof_btn)
        v.addLayout(cr)

        dr = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setLayoutDirection(Qt.LeftToRight)
        self.dir_edit.setPlaceholderText("Save to folder")
        self.dir_edit.textChanged.connect(self.sig_dir_changed)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setObjectName("ghost")
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self.sig_browse_clicked)
        dr.addWidget(self.dir_edit, 1)
        dr.addWidget(self.browse_btn)
        v.addLayout(dr)

        self.fname_edit = QLineEdit()
        self.fname_edit.setLayoutDirection(Qt.LeftToRight)
        self.fname_edit.setPlaceholderText("Filename  (auto-filled from URL)")
        self.fname_edit.textEdited.connect(self._on_fname_edited)
        v.addWidget(self.fname_edit)

        self.disk_lbl = QLabel("")
        self.disk_lbl.setObjectName("disk_ok")
        v.addWidget(self.disk_lbl)

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
        self.queue_clear_btn.clicked.connect(self.sig_queue_clear_clicked)
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
        self.queue_remove_btn.clicked.connect(self.sig_queue_remove_clicked)
        self.queue_run_btn = QPushButton("▶  Run Queue")
        self.queue_run_btn.setObjectName("ghost")
        self.queue_run_btn.setCursor(Qt.PointingHandCursor)
        self.queue_run_btn.clicked.connect(self.sig_queue_run_clicked)
        qbr.addWidget(self.queue_remove_btn)
        qbr.addStretch(1)
        qbr.addWidget(self.queue_run_btn)
        qv.addLayout(qbr)
        self.queue_frame.setVisible(False)
        v.addWidget(self.queue_frame)

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
            b.clicked.connect(lambda checked, n=name: self.sig_preset_clicked.emit(n))
            grid.addWidget(b, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        v.addLayout(grid)
        self.preset_note = QLabel("")
        self.preset_note.setObjectName("note")
        self.preset_note.setWordWrap(True)
        v.addWidget(self.preset_note)

        self.adv_btn = QToolButton()
        self.adv_btn.setObjectName("advbtn")
        self.adv_btn.setText("▸  Advanced settings")
        self.adv_btn.setCheckable(True)
        self.adv_btn.setCursor(Qt.PointingHandCursor)
        self.adv_btn.toggled.connect(self.sig_adv_toggled)
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
        self.res_cb.currentIndexChanged.connect(lambda: self.sig_adv_changed.emit())
        self.fps_sb = QSpinBox()
        self.fps_sb.setRange(5, 60)
        self.fps_sb.valueChanged.connect(lambda: self.sig_adv_changed.emit())
        self.crf_sl = QSlider(Qt.Horizontal)
        self.crf_sl.setRange(0, 51)
        self.crf_sl.valueChanged.connect(self.sig_crf_changed)
        self.crf_val = QLabel("28")
        self.crf_val.setFixedWidth(26)
        self.crf_val.setAlignment(Qt.AlignCenter)
        self.ab_cb = QComboBox()
        self.ab_cb.addItems(ABITRATES)
        self.ab_cb.currentIndexChanged.connect(lambda: self.sig_adv_changed.emit())
        self.vp_cb = QComboBox()
        self.vp_cb.addItems(VPRESETS)
        self.vp_cb.currentIndexChanged.connect(lambda: self.sig_adv_changed.emit())
        self.pad_sb = QSpinBox()
        self.pad_sb.setRange(0, 15000)
        self.pad_sb.setSingleStep(250)
        self.pad_sb.setSuffix(" ms")
        self.pad_sb.valueChanged.connect(lambda: self.sig_adv_changed.emit())
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
        self.gpu_cb = QComboBox()
        self.gpu_cb.addItems(GPU_OPTIONS)
        self.gpu_cb.setToolTip(
            "CPU: always works, slower.\n"
            "NVIDIA/AMD/Intel: much faster — needs the right GPU + drivers.\n"
            "If unsure, leave on CPU."
        )
        self.gpu_cb.currentIndexChanged.connect(lambda: self.sig_adv_changed.emit())
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

        self.stats = StatsWidget(self)
        self.stats.setVisible(False)
        v.addWidget(self.stats)

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
        self.go_btn.clicked.connect(self.sig_go_clicked)
        v.addWidget(self.go_btn)

        qadd_row = QHBoxLayout()
        self.queue_add_btn = QPushButton("+ Add to Queue")
        self.queue_add_btn.setObjectName("ghost")
        self.queue_add_btn.setCursor(Qt.PointingHandCursor)
        self.queue_add_btn.setToolTip(
            "Add this URL to the batch queue.\n"
            "Queued jobs run one after another when you click 'Run Queue'.\n"
            "Shortcut: Ctrl+Shift+Q"
        )
        self.queue_add_btn.clicked.connect(self.sig_queue_add_clicked)
        qadd_row.addWidget(self.queue_add_btn)
        qadd_row.addStretch(1)
        v.addLayout(qadd_row)

        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.sig_stop_clicked)
        v.addWidget(self.stop_btn)
        self.open_btn = QPushButton("📂  Open folder")
        self.open_btn.setObjectName("ghost")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.setVisible(False)
        self.open_btn.clicked.connect(self.sig_open_output_clicked)
        v.addWidget(self.open_btn)

        scroll.setWidget(panel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("section")
        return lbl

    def _fld(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("fld")
        return lbl

    @staticmethod
    def _glow(widget, color, blur, alpha):
        from PySide6.QtWidgets import QGraphicsDropShadowEffect

        e = QGraphicsDropShadowEffect()
        e.setColor(QColor(color))
        e.setBlurRadius(blur)
        e.setOffset(0, 0)
        widget.setGraphicsEffect(e)
        return e

    def _on_fname_edited(self, text):
        self._fname_touched = True
        self.sig_fname_edited.emit(text)

    def set_fname_text(self, text: str):
        if not self._fname_touched:
            self.fname_edit.setText(text)

    def set_detected_text(self, text: str):
        self.detected.setText(text)

    def set_disk_label(self, ok: bool, label: str):
        self.disk_lbl.setText(label)
        self.disk_lbl.setObjectName("disk_ok" if ok else "disk_warn")
        self.disk_lbl.style().unpolish(self.disk_lbl)
        self.disk_lbl.style().polish(self.disk_lbl)

    def set_stage_text(self, text: str):
        self.stage_lbl.setText(text)

    def set_retry_text(self, text: str, visible: bool):
        self.retry_lbl.setText(text)
        self.retry_lbl.setVisible(visible)

    def set_progress(self, mode: str, pct: int):
        self.bar.setValue(pct)
        if mode == "download":
            self.bar.setStyleSheet(_BAR_DOWNLOAD)
        elif mode == "render":
            self.bar.setStyleSheet(_BAR_RENDER)

    def set_running(self, running: bool):
        self.go_btn.setVisible(not running)
        self.stop_btn.setVisible(running)
        self.open_btn.setVisible(False)
        self.queue_add_btn.setVisible(not running)
        self.url_edit.setEnabled(not running)
        self.dir_edit.setEnabled(not running)
        self.fname_edit.setEnabled(not running)
        self.browse_btn.setEnabled(not running)
        self.cookie_edit.setEnabled(not running)
        for b in self.preset_btns.values():
            b.setEnabled(not running)
        self.adv_btn.setEnabled(not running)

    def set_stats_visible(self, visible: bool):
        self.stats.setVisible(visible)

    def set_speed_text(self, text: str, visible: bool):
        self.speed_lbl.setText(text)
        self.speed_lbl.setVisible(visible)

    def apply_preset(self, name: str):
        self._loading_preset = True
        try:
            p = PRESETS.get(name)
            if p is None:
                return
            idx = self.res_cb.findText(f"{p['w']}x{p['h']}")
            if idx >= 0:
                self.res_cb.setCurrentIndex(idx)
            self.fps_sb.setValue(p["fps"])
            self.crf_sl.setValue(p["crf"])
            self.crf_val.setText(str(p["crf"]))
            idx = self.ab_cb.findText(p["ab"])
            if idx >= 0:
                self.ab_cb.setCurrentIndex(idx)
            idx = self.vp_cb.findText(p["vp"])
            if idx >= 0:
                self.vp_cb.setCurrentIndex(idx)
            self.pad_sb.setValue(p["pad"])
            self.preset_note.setText(p.get("note", ""))
        finally:
            self._loading_preset = False

    def select_preset(self, name: str):
        for n, b in self.preset_btns.items():
            if n == name:
                b.setStyleSheet(_PRESET_ACTIVE)
            else:
                b.setStyleSheet("")

    def toggle_adv(self, on: bool):
        self.adv.setVisible(on)
        self.adv_btn.setText(("▾" if on else "▸") + "  Advanced settings")

    def read_render_params(self) -> dict:
        res = self.res_cb.currentText()
        w, h = (int(x) for x in res.split("x"))
        return {
            "w": w,
            "h": h,
            "fps": self.fps_sb.value(),
            "crf": self.crf_sl.value(),
            "ab": self.ab_cb.currentText(),
            "vp": self.vp_cb.currentText(),
            "pad": self.pad_sb.value(),
            "gpu_index": max(0, self.gpu_cb.currentIndex()),
            "xml_only": self.xml_chk.isChecked(),
            "verify_ssl": self.ssl_chk.isChecked(),
            "reuse": self.reuse_chk.isChecked(),
            "auto_retry": self.auto_retry_chk.isChecked(),
        }

    def current_preset_name(self) -> str:
        for n, b in self.preset_btns.items():
            if b.isChecked():
                return n
        return "Balanced (720p)"

    def read_url(self) -> str:
        return self.url_edit.text().strip()

    def read_dir(self) -> str:
        return self.dir_edit.text().strip()

    def read_fname(self) -> str:
        return self.fname_edit.text().strip()

    def read_cookie(self) -> str:
        return self.cookie_edit.text().strip()

    def read_xml_only(self) -> bool:
        return self.xml_chk.isChecked()

    def read_ssl(self) -> bool:
        return self.ssl_chk.isChecked()

    def read_reuse(self) -> bool:
        return self.reuse_chk.isChecked()

    def read_auto_retry(self) -> bool:
        return self.auto_retry_chk.isChecked()

    def refresh_cookie_profiles(self, profiles: dict):
        self.cookie_profile_cb.blockSignals(True)
        self.cookie_profile_cb.clear()
        self.cookie_profile_cb.addItem("— profiles —")
        for name in profiles:
            self.cookie_profile_cb.addItem(name)
        self.cookie_profile_cb.blockSignals(False)

    def refresh_queue_ui(self, queue_items: list):
        self.queue_list.clear()
        icons = {"pending": "⏳", "running": "▶", "done": "✓", "failed": "✗"}
        for item in queue_items:
            status = item.get("_status", "pending")
            label = f"{icons.get(status, '⏳')}  {item.get('rid', '?')}  —  {item.get('output_name', '')}"
            from PySide6.QtWidgets import QListWidgetItem

            li = QListWidgetItem(label)
            li.setForeground(QColor(_QUEUE_CLR.get(status, "#7aacca")))
            self.queue_list.addItem(li)
        n = len(queue_items)
        self.queue_count_lbl.setText(f"{n} pending" if n else "empty")
        self.queue_frame.setVisible(n > 0)

    def set_gpu_index(self, idx: int):
        self.gpu_cb.setCurrentIndex(idx)

    def get_gpu_index(self) -> int:
        return self.gpu_cb.currentIndex()
