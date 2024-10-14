from abc import ABC, abstractmethod

from PySide6.QtGui import (
    QPainterPath,
    QPainter,
    QBrush,
    QPen,
    QFontMetrics,
)
from PySide6.QtWidgets import QApplication, QGroupBox, QVBoxLayout, QSpinBox
from PySide6.QtCore import Qt, QRect

import theme
from .common import State, Element
from utils import widgetWithLabel, updateTimelineReceiver


class Time(Element):
    LEFT_TEXT_OFFSET = 3
    TEXT_HEIGHT = 20
    SHORT_MARK_HEIGHT = 6
    RULER_LABEL_LEFT_OFFSET = 2
    RULER_LABEL_TOP_OFFSET = 3

    @abstractmethod
    def get_name(self):
        pass

    @abstractmethod
    def markings(self):
        pass

    @abstractmethod
    def get_marking_label_width(self):
        pass

    def paint(self, painter, rect, state):
        scale = rect.width() / self.get_length()
        # rect but with a height of TEXT_HEIGHT.
        text_rect = rect.adjusted(0, 0, 0, -(rect.height() - self.TEXT_HEIGHT))
        # rect but starting TEXT_HEIGHT lower.
        ruler_rect = rect.adjusted(0, self.TEXT_HEIGHT, 0, 0)

        # Time header
        qpp = QPainterPath()
        qpp.addRect(text_rect)

        # Fix bad anti-aliasing rendering
        qpp.translate(0.5, 0.5)

        brush = QBrush()
        brush.setStyle(Qt.SolidPattern)
        if state == State.NONE:
            brush.setColor(theme.TIME_BG)
        elif state == State.HOVERING:
            brush.setColor(theme.TIME_BG.darker(120))
        elif state == State.SELECTED:
            brush.setColor(theme.TIME_BG.lighter(150))

        pen = QPen()
        pen.setColor(theme.OUTLINE)
        pen.setWidth(1)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillPath(qpp, brush)
        painter.setPen(pen)
        painter.drawPath(qpp)

        pen = QPen()
        pen.setColor(theme.TEXT)

        fm = QFontMetrics(theme.TIME_FONT)
        if (
            fm.horizontalAdvance(self.get_name()) + self.LEFT_TEXT_OFFSET
            < text_rect.width()
        ):
            painter.setFont(theme.TIME_FONT)
            painter.setPen(pen)
            painter.drawText(
                text_rect.adjusted(self.LEFT_TEXT_OFFSET, 0, 0, 0),
                Qt.AlignLeft | Qt.AlignVCenter,
                self.get_name(),
            )

        # Ruler
        text_pen = QPen()
        text_pen.setColor(theme.TEXT)

        ruler_pen = QPen()
        ruler_pen.setColor(theme.RULER)
        ruler_pen.setWidth(0)

        painter.setFont(theme.RULER_MARKING_FONT)
        for x, label in self.markings():
            if label:
                # Marking text
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setPen(text_pen)
                label_rect = QRect(
                    x * scale + self.RULER_LABEL_LEFT_OFFSET,
                    ruler_rect.y() + self.RULER_LABEL_TOP_OFFSET,
                    self.get_marking_label_width() * scale,
                    ruler_rect.height(),
                )
                fm = QFontMetrics(theme.RULER_MARKING_FONT)
                if (
                    fm.horizontalAdvance(label) + self.RULER_LABEL_LEFT_OFFSET
                    < label_rect.width()
                ):
                    painter.drawText(
                        label_rect,
                        Qt.AlignLeft | Qt.AlignTop,
                        label,
                    )

                # Full-height marking
                painter.setRenderHint(QPainter.Antialiasing, False)
                painter.setPen(ruler_pen)
                painter.drawLine(
                    x * scale,
                    ruler_rect.y(),
                    x * scale,
                    ruler_rect.y() + ruler_rect.height(),
                )
            else:
                # Half-height marking
                painter.setRenderHint(QPainter.Antialiasing, False)
                painter.setPen(ruler_pen)
                painter.drawLine(
                    x * scale,
                    ruler_rect.y() + ruler_rect.height() - self.SHORT_MARK_HEIGHT,
                    x * scale,
                    ruler_rect.y() + ruler_rect.height(),
                )


class TimeClock(Time):
    MIN_LENGTH = theme.PIXELS_PER_SECOND

    def __init__(self, start, duration):
        self._duration = QSpinBox()
        self._duration.setMaximum(10e6)
        self._duration.valueChanged.connect(updateTimelineReceiver)
        self.duration = duration
        super().__init__(start)

    #
    # Definitions required by Element ABC.
    #
    def get_length(self):
        return self.duration * theme.PIXELS_PER_SECOND

    def set_length(self, length):
        length = max(length, self.MIN_LENGTH)
        self.duration = int(length / theme.PIXELS_PER_SECOND)

    length = property(get_length, set_length)

    #
    # Definitions required by Time class.
    #
    def get_name(self):
        return f"◷ {self.duration // 60}:{self.duration%60:02d}"

    def markings(self):
        x = self.start
        for i in range(self.duration):
            yield x, f"{i // 60}:{i%60:02d}"
            x += theme.PIXELS_PER_SECOND
        yield x, " "

    def get_marking_label_width(self):
        return theme.PIXELS_PER_SECOND

    #
    # Properties for widget-based internal values.
    #
    def get_duration(self):
        return self._duration.value()

    def set_duration(self, value):
        self._duration.setValue(value)

    duration = property(get_duration, set_duration)

    def createWidget(self):
        groupbox = QGroupBox("Clock Time Element")
        vboxlayout = QVBoxLayout()
        vboxlayout.addLayout(widgetWithLabel(self._start, "Start (px):"))
        vboxlayout.addLayout(widgetWithLabel(self._duration, "Duration (sec):"))
        vboxlayout.addStretch()
        groupbox.setLayout(vboxlayout)
        return groupbox


class TimeMusic(Time):
    MIN_LENGTH = theme.PIXELS_PER_SECOND

    def __init__(self, start, duration, bpm=100, beats_per_bar=4, starting_bar=1):
        self._duration = QSpinBox()
        self._duration.setMaximum(10e6)
        self._duration.valueChanged.connect(updateTimelineReceiver)
        self.duration = duration
        
        self._bpm = QSpinBox()
        self._bpm.setMinimum(1)
        self._bpm.setMaximum(1000)
        self._bpm.valueChanged.connect(updateTimelineReceiver)
        self.bpm = bpm

        self._beats_per_bar = QSpinBox()
        self._beats_per_bar.setMinimum(1)
        self._beats_per_bar.setMaximum(16)
        self._beats_per_bar.valueChanged.connect(updateTimelineReceiver)
        self.beats_per_bar = beats_per_bar

        self._starting_bar = QSpinBox()
        self._starting_bar.setMinimum(1)
        self._starting_bar.setMaximum(1000)
        self._starting_bar.valueChanged.connect(updateTimelineReceiver)
        self.starting_bar = starting_bar
        super().__init__(start)


    # Definitions required by Element ABC.
    def get_length(self):
        return self.duration * 1 / self.bpm * 60 * theme.PIXELS_PER_SECOND

    def set_length(self, length):
        length = max(length, self.MIN_LENGTH)
        self.duration = int(length * self.bpm / 60 / theme.PIXELS_PER_SECOND)

    length = property(get_length, set_length)

    #
    # Definitions required by Time class.
    #
    def get_name(self):
        return f"♩={self.bpm}"

    def markings(self):
        x = self.start
        for beat in range(self.duration):
            if beat % self.beats_per_bar == 0:
                yield x, f"{self.starting_bar + beat // self.beats_per_bar}"
            else:
                yield x, ""
            x += self.get_pixels_per_beat()
        yield x, " "
    
    def get_marking_label_width(self):
        return self.get_pixels_per_beat() * self.beats_per_bar

    #
    # Properties for widget-based internal values.
    #
    def get_duration(self):
        return self._duration.value()

    def set_duration(self, value):
        self._duration.setValue(value)

    duration = property(get_duration, set_duration)

    def get_bpm(self):
        return self._bpm.value()

    def set_bpm(self, value):
        self._bpm.setValue(value)

    bpm = property(get_bpm, set_bpm)

    def get_beats_per_bar(self):
        return self._beats_per_bar.value()

    def set_beats_per_bar(self, value):
        self._beats_per_bar.setValue(value)

    beats_per_bar = property(get_beats_per_bar, set_beats_per_bar)

    def get_starting_bar(self):
        return self._starting_bar.value()

    def set_starting_bar(self, value):
        self._starting_bar.setValue(value)

    starting_bar = property(get_starting_bar, set_starting_bar)

    def createWidget(self):
        groupbox = QGroupBox("Music Time Element")
        vboxlayout = QVBoxLayout()
        vboxlayout.addLayout(widgetWithLabel(self._start, "Start (px):"))
        vboxlayout.addLayout(widgetWithLabel(self._duration, "Duration (beats):"))
        vboxlayout.addLayout(widgetWithLabel(self._bpm, "BPM:"))
        vboxlayout.addLayout(widgetWithLabel(self._beats_per_bar, "Beats per bar:"))
        vboxlayout.addLayout(widgetWithLabel(self._starting_bar, "Starting bar:"))
        vboxlayout.addStretch()
        groupbox.setLayout(vboxlayout)
        return groupbox

    #
    # Everything else.
    #
    def get_pixels_per_beat(self):
        return 1 / self.bpm * 60 * theme.PIXELS_PER_SECOND
