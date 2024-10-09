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

class Time(ABC):
    LEFT_TEXT_OFFSET = 3

    @abstractmethod
    def get_name(self):
        pass

    def paint(self, painter, rect):
        qpp = QPainterPath()
        qpp.addRect(rect)

        # Fix bad anti-aliasing rendering
        qpp.translate(0.5, 0.5)

        brush = QBrush()
        brush.setColor(theme.TIME_BG)
        brush.setStyle(Qt.SolidPattern)

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
        if fm.horizontalAdvance(self.get_name()) + self.LEFT_TEXT_OFFSET < rect.width():
            painter.setFont(theme.TIME_FONT)
            painter.setPen(pen)
            painter.drawText(
                rect.adjusted(self.LEFT_TEXT_OFFSET, 0, 0, 0),
                Qt.AlignLeft | Qt.AlignVCenter,
                self.get_name(),
            )


class TimeClock(Time):
    MIN_LENGTH = theme.PIXELS_PER_SECOND

    def __init__(self, start, duration):
        self.start = start
        self.duration = duration

    def markings(self):
        x = self.start
        for i in range(self.duration):
            yield x, f"{i // 60}:{i%60:02d}"
            x += theme.PIXELS_PER_SECOND

    def get_length(self):
        return self.duration * theme.PIXELS_PER_SECOND

    def set_length(self, length):
        self.duration = int(length / theme.PIXELS_PER_SECOND)

    length = property(get_length, set_length)

    def get_marking_label_width(self):
        return theme.PIXELS_PER_SECOND

    def get_name(self):
        return f"◷ {self.duration // 60}:{self.duration%60:02d}"


class TimeMusic(Time):
    MIN_LENGTH = theme.PIXELS_PER_SECOND

    def __init__(self, start, duration, bpm=100, time_signature="4/4", starting_bar=1):
        self.start = start
        self.duration = duration
        self.bpm = bpm
        self.beats_per_bar = int(time_signature.split("/")[0])
        self.starting_bar = starting_bar
        self.pixels_per_beat = 1 / self.bpm * 60 * theme.PIXELS_PER_SECOND

    def markings(self):
        x = self.start
        for beat in range(self.duration):
            if beat % self.beats_per_bar == 0:
                yield x, f"{self.starting_bar + beat // self.beats_per_bar}"
            else:
                yield x, ""
            x += self.pixels_per_beat

    def get_length(self):
        return self.duration * 1 / self.bpm * 60 * theme.PIXELS_PER_SECOND

    def set_length(self, length):
        self.duration = int(length * self.bpm / 60 / theme.PIXELS_PER_SECOND)

    length = property(get_length, set_length)

    def get_marking_label_width(self):
        return self.pixels_per_beat * self.beats_per_bar

    def get_name(self):
        return f"♩={self.bpm}"