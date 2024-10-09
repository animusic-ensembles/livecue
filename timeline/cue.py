from abc import ABC, abstractmethod

from PySide6.QtGui import (
    QPainterPath,
    QPainter,
    QBrush,
    QPen,
    QFontMetrics,
)
from PySide6.QtCore import Qt

import theme
from .common import State


class Cue(ABC):
    ROUNDING_RADIUS = 3
    MIN_LENGTH = 1

    @abstractmethod
    def getColor(self):
        pass

    @abstractmethod
    def getText(self):
        pass

    def __init__(self, row, start, length):
        self.row = row
        self.start = start
        self.length = length

        self.old_start = start
        self.old_length = length

    def paint(self, painter, rect, state):
        qpp = QPainterPath()
        qpp.addRoundedRect(
            rect,
            self.ROUNDING_RADIUS,
            self.ROUNDING_RADIUS,
        )

        # Fix bad anti-aliasing rendering
        qpp.translate(0.5, 0.5)

        brush = QBrush()
        if state == State.NONE:
            brush.setColor(self.getColor())
        elif state == State.HOVERING:
            brush.setColor(self.getColor().darker(120))
        elif state == State.SELECTED:
            brush.setColor(self.getColor().lighter(120))
        brush.setStyle(Qt.SolidPattern)

        pen = QPen()
        if state == State.SELECTED:
            pen.setColor(theme.SELECTED_OUTLINE)
        else:
            pen.setColor(theme.OUTLINE)
        pen.setWidth(1)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillPath(qpp, brush)
        painter.setPen(pen)
        painter.drawPath(qpp)

        pen = QPen()
        pen.setColor(theme.TEXT)

        fm = QFontMetrics(theme.CUE_FONT)
        if fm.horizontalAdvance(self.getText()) < rect.width():
            painter.setFont(theme.CUE_FONT)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignCenter, self.getText())

class SceneCue(Cue):
    def __init__(self, row, start, length, name, color):
        super().__init__(row, start, length)
        self.name = name
        self.color = color

    def getColor(self):
        return self.color

    def getText(self):
        return self.name

class LightingCue(Cue):
    pass