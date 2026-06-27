from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from vcd.gui.utils.formatters import _fmt_dur
from vcd.gui.widgets.speed_graph import SpeedGraph


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
