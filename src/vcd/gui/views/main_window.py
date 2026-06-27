from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
)

from vcd.gui.constants import _APP_ICON_B64, SKY
from vcd.gui.views.tabs.files_tab import FilesTab
from vcd.gui.views.tabs.history_tab import HistoryTab
from vcd.gui.views.tabs.left_panel import LeftPanel
from vcd.gui.views.tabs.log_tab import LogTab
from vcd.gui.widgets.starfield import StarField


class MainWindow(StarField):
    sig_close = Signal(object)

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

        self._build_ui()
        self._setup_shortcuts()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 14)
        root.setSpacing(12)
        root.addLayout(self._build_header())
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self.left_panel = LeftPanel()
        self._splitter.addWidget(self.left_panel)
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
        self.links_lbl.setOpenExternalLinks(True)
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

    def _build_right(self):
        self.right_tabs = QTabWidget()
        self.right_tabs.setObjectName("righttabs")
        self.log_tab = LogTab()
        self.history_tab = HistoryTab()
        self.files_tab = FilesTab()
        self.right_tabs.addTab(self.log_tab, "Log")
        self.right_tabs.addTab(self.history_tab, "History")
        self.right_tabs.addTab(self.files_tab, "Output Files")
        return self.right_tabs

    def _glow(self, widget, color, blur=24, alpha=180):
        from PySide6.QtWidgets import QGraphicsDropShadowEffect

        eff = QGraphicsDropShadowEffect(widget)
        eff.setBlurRadius(blur)
        c = QColor(color)
        c.setAlpha(alpha)
        eff.setColor(c)
        eff.setOffset(0, 0)
        widget.setGraphicsEffect(eff)
        return eff

    def _setup_shortcuts(self):
        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(
            self.left_panel.sig_go_clicked
        )
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            self.left_panel.sig_stop_clicked
        )
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(
            lambda: self.right_tabs.setCurrentIndex(0)
        )
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(
            lambda: self.right_tabs.setCurrentIndex(1)
        )
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
            lambda: (
                self.right_tabs.setCurrentIndex(0),
                self.left_panel.url_edit.setFocus(),
            )
        )
        QShortcut(QKeySequence("Ctrl+Shift+C"), self).activated.connect(
            self.log_tab.sig_clear
        )
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.log_tab.sig_save)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)
        QShortcut(QKeySequence("Ctrl+Shift+Q"), self).activated.connect(
            self.left_panel.sig_queue_add_clicked
        )

    def _about(self):
        QMessageBox.about(
            self,
            "About VCD",
            "<h3>VCD v0.3</h3>"
            "<p>Vadana Class Downloader</p>"
            "<p>Download and render Vadana class recordings.</p>"
            "<p>Created by IAUCourseExp</p>",
        )

    def closeEvent(self, e):
        self.sig_close.emit(e)
