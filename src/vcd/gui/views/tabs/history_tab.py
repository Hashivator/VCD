from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from vcd.gui.constants import GREEN, RED


class HistoryTab(QWidget):
    sig_refresh = Signal()
    sig_clear_all = Signal()
    sig_row_context_menu = Signal(int, object)
    sig_row_double_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
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
        rb.clicked.connect(self.sig_refresh)
        cb = QPushButton("Clear All")
        cb.setObjectName("ghost")
        cb.setCursor(Qt.PointingHandCursor)
        cb.clicked.connect(self.sig_clear_all)
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
        self.hist_table.customContextMenuRequested.connect(lambda pos: self.sig_row_context_menu.emit(self.hist_table.rowAt(pos.y()), pos))
        self.hist_table.doubleClicked.connect(lambda idx: self.sig_row_double_clicked.emit(idx.row()))

        note = QLabel(
            "Right-click a row for options  ·  Double-click to open file  ·  Ctrl+H to focus"
        )
        note.setObjectName("note")
        v.addWidget(note)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(panel)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("section")
        return lbl

    def refresh_table(self, entries: list):
        self.hist_table.setRowCount(0)
        self.hist_table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            status = e.get("status", "")
            color = GREEN if status == "done" else RED if status == "failed" else "#7aacca"
            vals = [
                e.get("date", ""),
                e.get("rid", "")[:8],
                status,
                e.get("size", ""),
                e.get("duration", ""),
                e.get("preset", ""),
                e.get("file", ""),
            ]
            for j, v in enumerate(vals):
                item = self.hist_table.item(i, j)
                if not item:
                    from PySide6.QtWidgets import QTableWidgetItem
                    item = QTableWidgetItem()
                    self.hist_table.setItem(i, j, item)
                item.setText(str(v))
                if j == 2:
                    from PySide6.QtGui import QColor
                    item.setForeground(QColor(color))
