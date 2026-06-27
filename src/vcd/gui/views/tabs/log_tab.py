from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLineEdit, QPlainTextEdit, QLabel
from PySide6.QtCore import Signal, Qt
from vcd.gui.constants import LEVEL_COLOR, LEVEL_ICON


class LogTab(QWidget):
    sig_clear = Signal()
    sig_save = Signal()
    sig_filter_changed = Signal(str)
    sig_search_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
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

        frow = QHBoxLayout()
        frow.setSpacing(5)
        self._filter_btns: dict = {}
        for level in ("ALL", "INFO", "STEP", "SUCCESS", "WARN", "ERROR"):
            btn = QPushButton(level)
            btn.setObjectName("filter_btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, lv=level: self.sig_filter_changed.emit(lv))
            self._filter_btns[level] = btn
            frow.addWidget(btn)
        frow.addStretch(1)
        self.log_search = QLineEdit()
        self.log_search.setObjectName("log_search")
        self.log_search.setPlaceholderText("Search…")
        self.log_search.setMaximumWidth(140)
        self.log_search.setFixedHeight(24)
        self.log_search.textChanged.connect(self.sig_search_changed)
        frow.addWidget(self.log_search)
        v.addLayout(frow)

        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(10000)
        v.addWidget(self.log, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(panel)

        self.clear_btn.clicked.connect(self.sig_clear)
        self.save_btn.clicked.connect(self.sig_save)

        self._log_all = []

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("section")
        return lbl

    def append_log(self, level: str, msg: str, filter_level: str = "ALL", filter_search: str = ""):
        color = LEVEL_COLOR.get(level, "#7aacca")
        icon = LEVEL_ICON.get(level, "›")
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_all.append((level, msg, color, icon, ts))
        if filter_level != "ALL" and level != filter_level:
            return
        if filter_search and filter_search.lower() not in msg.lower() and filter_search.lower() not in level.lower():
            return
        html = f'<span style="color:#3d5470">[{ts}]</span> <span style="color:{color};font-weight:700">{icon} {level}</span> <span style="color:#c0dff0">{msg}</span>'
        self.log.appendHtml(html)

    def clear_log(self):
        self.log.clear()
        self._log_all.clear()

    def set_filter_active(self, active: str):
        for lv, btn in self._filter_btns.items():
            btn.setProperty("active", "1" if lv == active else "0")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def rebuild_log(self, log_filter: str, log_search: str):
        self.log.clear()
        for level, msg, color, icon, ts in self._log_all:
            if log_filter != "ALL" and level != log_filter:
                continue
            if log_search and log_search.lower() not in msg.lower():
                continue
            html = f'<span style="color:#3d5470">[{ts}]</span> <span style="color:{color};font-weight:700">{icon} {level}</span> <span style="color:#c0dff0">{msg}</span>'
            self.log.appendHtml(html)
