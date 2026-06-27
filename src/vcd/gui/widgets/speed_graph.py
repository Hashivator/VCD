import time

from PySide6.QtCore import QPointF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    Qt,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from vcd.gui.utils.formatters import _fmt_bytes, _parse_bps


class SpeedGraph(QWidget):
    _MAX = 90

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pts: list[float] = []
        self.setFixedHeight(48)
        self.setMinimumWidth(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._last_update_time = 0.0

    def push(self, speed_str: str):
        bps = _parse_bps(speed_str)
        if bps <= 0:
            return

        self._pts.append(bps)
        if len(self._pts) > self._MAX:
            self._pts = self._pts[-self._MAX :]

        now = time.time()
        if now - self._last_update_time > 0.06:
            self.update()
            self._last_update_time = now

    def clear(self):
        self._pts.clear()
        self.update()

    def paintEvent(self, _ev):
        w, h = self.width(), self.height()

        if w <= 0 or h <= 0:
            return

        with QPainter(self) as p:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.fillRect(0, 0, w, h, QColor(3, 7, 16))

            if len(self._pts) < 2:
                p.setPen(QPen(QColor(56, 189, 248, 30), 1))
                p.drawLine(0, h - 2, w, h - 2)
                return

            mx = max(self._pts)
            if mx == 0.0:
                mx = 1.0

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

            p.fillPath(path, QBrush(fill))

            pen = QPen(QColor(56, 189, 248), 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)

            for i in range(n - 1):
                p.drawLine(pts[i], pts[i + 1])

            lbl = _fmt_bytes(self._pts[-1]) + "/s"
            p.setPen(QColor(220, 242, 255, 210))

            flags = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            p.drawText(0, 0, w - 3, h - 2, flags, lbl)
