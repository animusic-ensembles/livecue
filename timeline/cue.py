from abc import ABC, abstractmethod

from PySide6.QtGui import (
    QPainterPath,
    QPainter,
    QBrush,
    QPen,
    QFontMetrics,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QSpinBox, QLineEdit

import theme
from .common import Element, State
from utils import widgetWithLabel, updateTimelineReceiver


class Cue(Element):
    ROUNDING_RADIUS = 3
    MIN_LENGTH = 1

    @abstractmethod
    def getColor(self):
        pass

    @abstractmethod
    def getText(self):
        pass

    def __init__(self, start, length):
        self._length = QSpinBox()
        self._length.setMaximum(10e6)
        self._length.valueChanged.connect(updateTimelineReceiver)
        self.length = length
        super().__init__(start)

    def set_length(self, value):
        self._length.setValue(max(value, self.MIN_LENGTH))

    def get_length(self):
        return self._length.value()

    length = property(get_length, set_length)

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
    def __init__(self, start, length, name, color):
        self._name = QLineEdit()
        self._name.textChanged.connect(updateTimelineReceiver)
        self.name = name
        self.color = color
        super().__init__(start, length)

    def getColor(self):
        return self.color

    def getText(self):
        return self.name

    def get_name(self):
        return self._name.text()

    def set_name(self, value):
        self._name.setText(value)

    name = property(get_name, set_name)

    def createWidget(self):
        groupbox = QGroupBox("Scene Cue")
        vboxlayout = QVBoxLayout()
        vboxlayout.addLayout(widgetWithLabel(self._start, "Start (px):"))
        vboxlayout.addLayout(widgetWithLabel(self._length, "Duration (px):"))
        vboxlayout.addLayout(widgetWithLabel(self._name, "Cue:"))
        vboxlayout.addStretch()
        groupbox.setLayout(vboxlayout)
        return groupbox


class LightingCue(Cue):
    pass
