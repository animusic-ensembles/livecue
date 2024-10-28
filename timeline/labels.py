from PySide6.QtGui import (
    QPainterPath,
    QPainter,
    QBrush,
    QPen,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QLineEdit

import theme
from .common import Element, State
from utils import widgetWithLabel, updateTimelineReceiver, textWidth


class Label(Element):
    SAVED_ATTRIBUTES = ["start", "length", "text"]
    TEXT_LEFT_OFFSET = 2
    TEXT_TOP_OFFSET = 2

    def __init__(self, start, length, text="Label"):
        self._text = QLineEdit()
        self._text.textChanged.connect(updateTimelineReceiver)
        self.text = text
        super().__init__(start, length)

    def get_text(self):
        return self._text.text()

    def set_text(self, value):
        self._text.setText(value)

    text = property(get_text, set_text)

    def paint(self, painter, rect, state):
        qpp = QPainterPath()
        qpp.addRect(rect)

        # Fix bad anti-aliasing rendering
        qpp.translate(0.5, 0.5)

        brush = QBrush()
        if state == State.NONE:
            brush.setColor(theme.LABEL_BG)
        elif state == State.HOVERING:
            brush.setColor(theme.LABEL_BG.darker(120))
        elif state == State.SELECTED:
            brush.setColor(theme.LABEL_BG.lighter(120))
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

        rect.adjust(self.TEXT_LEFT_OFFSET, self.TEXT_TOP_OFFSET, 0, 0)
        if textWidth(theme.CUE_FONT, self.text) < rect.width():
            painter.setFont(theme.CUE_FONT)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignLeft, self.text)

    def createWidget(self):
        groupbox = QGroupBox("Label")
        groupbox.setMaximumWidth(300)
        groupbox.setMaximumHeight(240)
        vboxlayout = QVBoxLayout()
        vboxlayout.addLayout(widgetWithLabel(self._start, "Start (px):"))
        vboxlayout.addLayout(widgetWithLabel(self._length, "Duration (px):"))
        vboxlayout.addLayout(widgetWithLabel(self._text, "Label:"))
        vboxlayout.addStretch()
        groupbox.setLayout(vboxlayout)
        return groupbox