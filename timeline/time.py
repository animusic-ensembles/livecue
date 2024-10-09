from abc import ABC, abstractmethod

from PySide6.QtGui import (
    QPainterPath,
    QPainter,
    QBrush,
    QPen,
    QFontMetrics,
)
from PySide6.QtCore import Qt, QRect

import theme


class Time(ABC):
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
    def get_length(self):
        pass

    @abstractmethod
    def set_length(self, length):
        pass

    @abstractmethod
    def get_marking_label_width(self):
        pass

    def paint(self, painter, rect):
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
        self.start = start
        self.duration = duration

    def markings(self):
        x = self.start
        for i in range(self.duration):
            yield x, f"{i // 60}:{i%60:02d}"
            x += theme.PIXELS_PER_SECOND
        yield x, " "

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
        yield x, " "

    def get_length(self):
        return self.duration * 1 / self.bpm * 60 * theme.PIXELS_PER_SECOND

    def set_length(self, length):
        self.duration = int(length * self.bpm / 60 / theme.PIXELS_PER_SECOND)

    length = property(get_length, set_length)

    def get_marking_label_width(self):
        return self.pixels_per_beat * self.beats_per_bar

    def get_name(self):
        return f"♩={self.bpm}"
