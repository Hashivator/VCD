import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLabel, QScrollArea
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap
from vcd.gui.utils.formatters import _fmt_size


class FilesTab(QWidget):
    sig_refresh = Signal()
    sig_play_file = Signal(str)
    sig_open_folder = Signal(str)
    sig_delete_file = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
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
        rf.clicked.connect(self.sig_refresh)
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(panel)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("section")
        return lbl

    def refresh_files(self, entries: list):
        while self._files_layout.count():
            item = self._files_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for entry in entries:
            card = self._build_file_card(entry)
            self._files_layout.addWidget(card)
        self._files_layout.addStretch(1)

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

        bcol = QVBoxLayout()
        bcol.setSpacing(4)
        for icon, tip, signal, obj in [
            ("▶", "Play", self.sig_play_file, "icon_btn"),
            ("📂", "Open folder", self.sig_open_folder, "icon_btn"),
            ("🗑", "Delete file", self.sig_delete_file, "danger_btn"),
        ]:
            b = QPushButton(icon)
            b.setObjectName(obj)
            b.setToolTip(tip)
            b.setFixedWidth(32)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, s=signal, p=path: s.emit(p))
            bcol.addWidget(b)
        row.addLayout(bcol)
        return card
