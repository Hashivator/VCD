import math
import random

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient, Qt
from PySide6.QtWidgets import QWidget


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
