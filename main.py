import sys
from abc import ABC, abstractmethod
from enum import Enum, auto

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGui import (
    QPainterPath,
    QTransform,
    QColor,
    QPainter,
    QBrush,
    QPen,
    QFont,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QWidget,
    QMainWindow,
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
)
from PySide6.QtCore import Qt, QRect, QRectF

import theme

PIXELS_PER_SECOND = 20


def chain(*iterators):
    for iterator in iterators:
        for element in iterator:
            yield element


class State(Enum):
    NONE = auto()
    SELECTED = auto()
    HOVERING = auto()


class Cue:
    def __init__(self, name, color):
        self.name = name
        self.color = color


class TimelineTime:
    def __init__(
        self,
    ):
        pass


class TimelineCue:
    ROUNDING_RADIUS = 3
    MIN_LENGTH = 1

    def __init__(self, row, start, length, cue):
        self.row = row
        self.start = start
        self.length = length
        self.cue = cue

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
            brush.setColor(self.cue.color)
        elif state == State.HOVERING:
            brush.setColor(self.cue.color.darker(120))
        elif state == State.SELECTED:
            brush.setColor(self.cue.color.lighter(120))
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
        if fm.horizontalAdvance(self.cue.name) < rect.width():
            painter.setFont(theme.CUE_FONT)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignCenter, self.cue.name)


class Time(ABC):
    LEFT_TEXT_OFFSET = 3

    def get_name(self):
        return ""

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
    MIN_LENGTH = PIXELS_PER_SECOND

    def __init__(self, start, duration):
        self.start = start
        self.duration = duration

    def markings(self):
        x = self.start
        for i in range(self.duration):
            yield x, f"{i // 60}:{i%60:02d}"
            x += PIXELS_PER_SECOND

    def get_length(self):
        return self.duration * PIXELS_PER_SECOND

    def set_length(self, length):
        self.duration = int(length / PIXELS_PER_SECOND)

    length = property(get_length, set_length)

    def get_marking_label_width(self):
        return PIXELS_PER_SECOND

    def get_name(self):
        return f"◷ {self.duration // 60}:{self.duration%60:02d}"


class TimeMusic(Time):
    MIN_LENGTH = PIXELS_PER_SECOND

    def __init__(self, start, duration, bpm=100, time_signature="4/4", starting_bar=1):
        self.start = start
        self.duration = duration
        self.bpm = bpm
        self.beats_per_bar = int(time_signature.split("/")[0])
        self.starting_bar = starting_bar
        self.pixels_per_beat = 1 / self.bpm * 60 * PIXELS_PER_SECOND

    def markings(self):
        x = self.start
        for beat in range(self.duration):
            if beat % self.beats_per_bar == 0:
                yield x, f"{self.starting_bar + beat // self.beats_per_bar}"
            else:
                yield x, ""
            x += self.pixels_per_beat

    def get_length(self):
        return self.duration * 1 / self.bpm * 60 * PIXELS_PER_SECOND

    def set_length(self, length):
        self.duration = int(length * self.bpm / 60 / PIXELS_PER_SECOND)

    length = property(get_length, set_length)

    def get_marking_label_width(self):
        return self.pixels_per_beat * self.beats_per_bar

    def get_name(self):
        return f"♩={self.bpm}"


class Timeline(QWidget):
    # Scale/Scroll-related
    SCROLL_MOVE_MULTIPLIER = 1 / 2
    SCROLL_SCALE_MULTIPLIER = 1 / 1000
    SCALE_MIN = 0.1
    SCALE_MAX = 10

    # Drawing offsets
    TIME_Y = 0
    TIME_HEIGHT = 20
    RULER_Y = TIME_HEIGHT
    RULER_HEIGHT = 30
    RULER_LABEL_LEFT_OFFSET = 3
    RULER_LABEL_TOP_OFFSET = 2
    CUE_Y = RULER_Y + RULER_HEIGHT
    CUE_HEIGHT = 60
    ROW_PADDING = 6

    # Bounds
    RESIZE_INNER_BOUND = 10
    RESIZE_OUTER_BOUND = 2

    # Snapping
    SNAP_MARKING_PIXELS = 6

    def __init__(self):
        super().__init__()
        self.rows = 2
        self.scale = 1
        self.times = [
            TimeClock(0, 30),
            TimeMusic(30 * PIXELS_PER_SECOND, 60),
        ]
        self.cues = [
            TimelineCue(0, 0, 100, Cue("CAMERA 1", theme.NEUTRAL_RED)),
            TimelineCue(1, 100, 100, Cue("MEDIA", theme.NEUTRAL_GREEN)),
            TimelineCue(0, 300, 50, Cue("CAMERA 3", theme.NEUTRAL_BLUE)),
            TimelineCue(0, 900, 50, Cue("CAMERA 3", theme.NEUTRAL_BLUE)),
        ]

        self.selected = None
        self.hovering_object = None

        self.resizing_start_pos = None
        self.potential_resizing_object = None
        self.resizing_object = None
        self.resizing_old_start = 0
        self.resizing_old_length = 0

        self.moving_start_pos = None
        self.potential_moving_object = None
        self.moving_object = None
        self.moving_old_start = 0

        self.setMouseTracking(True)
        self.setMinimumWidth(3000)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

    def wheelEvent(self, e):
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            self.scale += e.angleDelta().y() * self.SCROLL_SCALE_MULTIPLIER
            self.scale = max(min(self.scale, self.SCALE_MAX), self.SCALE_MIN)
        else:
            self.parent().parent().horizontalScrollBar().setValue(self.parent().parent().horizontalScrollBar().value() - e.angleDelta().y() * self.SCROLL_MOVE_MULTIPLIER)
        self.update()

    def mousePressEvent(self, e):
        self.mouseButtonEvent(e)

    def mouseReleaseEvent(self, e):
        self.mouseButtonEvent(e)

    def mouseButtonEvent(self, e):
        if Qt.MouseButton.LeftButton & e.buttons():
            # Try each in order:
            # 1) Start resizing an object
            # 2) Mark an object for movement
            #
            # Note: Starting a movement happens when the mouse moves *after* a
            # click so it's handled in mouseMoveEvent()
            if self.potential_resizing_object:
                self.resizing_object = self.potential_resizing_object
                self.handleResize(e, start=True)
            elif self.hovering_object:
                self.potential_moving_object = self.hovering_object
        else:
            # Try each in order:
            # 1) Stop resizing an object
            # 2) Stop moving an object
            # 3) Select the object marked for movement that didn't move
            # 4) Deselect an object, because the press must not have been over
            #    an object (i.e. self.potential_moving_object = None)
            #
            if self.resizing_object:
                self.handleResize(e, stop=True)
                self.resizing_object = None
            elif self.moving_object:
                self.handleMove(e, stop=True)
                self.moving_object = None
            elif self.potential_moving_object:
                self.selected = self.potential_moving_object
            else:
                self.selected = None
            self.potential_moving_object = None
        self.update()

    def handleResize(self, e, start=False, stop=False):
        if start:
            self.resizing_start_pos = e.position()
            self.resizing_old_start = self.resizing_object.start
            self.resizing_old_length = self.resizing_object.length

        if (
            self.resizing_start_pos.x()
            < (self.resizing_old_start + self.resizing_old_length / 2) * self.scale
        ):
            # resize left handle
            delta = (e.position().x() - self.resizing_start_pos.x()) * 1 / self.scale
            self.resizing_object.start = self.resizing_old_start + delta
            self.resizing_object.length = self.resizing_old_length - delta

            # Snap to markings
            for time in self.times:
                for marking, _ in time.markings():
                    if (
                        abs(self.resizing_object.start - marking)
                        < self.SNAP_MARKING_PIXELS
                    ):
                        self.resizing_object.length += (
                            self.resizing_object.start - marking
                        )
                        self.resizing_object.start = marking
                        break
        else:
            # Resize right handle
            delta = (e.position().x() - self.resizing_start_pos.x()) * 1 / self.scale
            self.resizing_object.length = self.resizing_old_length + delta

            # Snap to markings
            for time in self.times:
                for marking, _ in time.markings():
                    right = self.resizing_object.start + self.resizing_object.length
                    if abs(right - marking) < self.SNAP_MARKING_PIXELS:
                        self.resizing_object.length = (
                            marking - self.resizing_object.start
                        )
                        break

        if stop:
            if self.resizing_object.length < 0:
                self.resizing_object.length *= -1
                self.resizing_object.start -= self.resizing_object.length
            self.resizing_object.length = max(
                self.resizing_object.length, self.resizing_object.MIN_LENGTH
            )

    def handleMove(self, e, start=False, stop=False):
        if start:
            self.moving_start_pos = e.position()
            self.moving_old_start = self.moving_object.start

        delta = (e.position().x() - self.moving_start_pos.x()) * 1 / self.scale
        self.moving_object.start = self.moving_old_start + delta

        if isinstance(self.moving_object, TimelineCue):
            # Snap to markings
            for time in self.times:
                for marking, _ in time.markings():
                    if (
                        abs(self.moving_object.start - marking)
                        < self.SNAP_MARKING_PIXELS
                    ):
                        self.moving_object.start = marking
                        break

            # Snap to rows
            y = self.CUE_Y
            for row in range(self.rows):
                y += self.CUE_HEIGHT
                if e.position().y() < y:
                    self.moving_object.row = row
                    break

    def mouseMoveEvent(self, e):
        # Set hovering object
        self.hovering_object = None
        for obj, rect in chain(self.cueRects(), self.timeRects()):
            if rect.contains(e.position()):
                self.hovering_object = obj
                break

        # Check object resize handles
        self.potential_resizing_object = None
        for obj, rect in chain(self.cueRects(), self.timeRects()):
            left_rect = rect.adjusted(
                -self.RESIZE_OUTER_BOUND, 0, self.RESIZE_INNER_BOUND - rect.width(), 0
            )
            if left_rect.contains(e.position()):
                self.setCursor(QtGui.QCursor(Qt.SplitHCursor))
                self.potential_resizing_object = obj
                break

            right_rect = rect.adjusted(
                rect.width() - self.RESIZE_INNER_BOUND, 0, self.RESIZE_OUTER_BOUND, 0
            )
            if right_rect.contains(e.position()):
                self.setCursor(QtGui.QCursor(Qt.SplitHCursor))
                self.potential_resizing_object = obj
                break

        # Only reset cursor if not resizing and not hovering a handle
        if not self.resizing_object and not self.potential_resizing_object:
            self.setCursor(QtGui.QCursor(Qt.ArrowCursor))

        # Send mouse event positions to objects
        if self.resizing_object:
            self.handleResize(e)

        if self.moving_object:
            self.handleMove(e)
        elif self.potential_moving_object:
            self.moving_object = self.potential_moving_object
            self.handleMove(e, start=True)

        self.update()

    def cueRects(self):
        for cue in self.cues:
            rect = QRectF(
                cue.start * self.scale,
                cue.row * self.CUE_HEIGHT + self.ROW_PADDING / 2 + self.CUE_Y,
                cue.length * self.scale,
                self.CUE_HEIGHT - self.ROW_PADDING,
            )
            yield cue, rect

    def timeRects(self):
        for time in self.times:
            rect = QRectF(
                time.start * self.scale,
                0,
                time.length * self.scale,
                self.TIME_HEIGHT,
            )
            yield time, rect

    def paintEvent(self, e):
        painter = QPainter(self)

        # Background
        brush = QBrush()
        brush.setColor(theme.BG)
        brush.setStyle(Qt.SolidPattern)
        rect = QRect(0, 0, self.size().width(), self.size().height())
        painter.fillRect(rect, brush)

        # Times
        for time, rect in self.timeRects():
            time.paint(painter, rect)

            # Ruler
            text_pen = QPen()
            text_pen.setColor(theme.TEXT)

            ruler_pen = QPen()
            ruler_pen.setColor(theme.RULER)
            ruler_pen.setWidth(0)

            painter.setFont(theme.RULER_MARKING_FONT)
            for x, label in time.markings():
                if label:
                    # Marking text
                    painter.setRenderHint(QPainter.Antialiasing, True)
                    painter.setPen(text_pen)
                    rect = QRect(
                        x * self.scale + self.RULER_LABEL_LEFT_OFFSET,
                        self.RULER_Y + self.RULER_LABEL_TOP_OFFSET,
                        time.get_marking_label_width() * self.scale,
                        self.RULER_HEIGHT / 2,
                    )
                    fm = QFontMetrics(theme.RULER_MARKING_FONT)
                    if fm.horizontalAdvance(label) + self.RULER_LABEL_LEFT_OFFSET < rect.width():
                        painter.drawText(
                            rect,
                            Qt.AlignLeft | Qt.AlignVCenter,
                            label,
                        )

                    # Full-height marking
                    painter.setRenderHint(QPainter.Antialiasing, False)
                    painter.setPen(ruler_pen)
                    painter.drawLine(
                        x * self.scale,
                        self.RULER_Y,
                        x * self.scale,
                        self.RULER_Y + self.RULER_HEIGHT,
                    )
                else:
                    # Half-height marking
                    painter.setRenderHint(QPainter.Antialiasing, False)
                    painter.setPen(ruler_pen)
                    painter.drawLine(
                        x * self.scale,
                        self.RULER_Y + self.RULER_HEIGHT / 2,
                        x * self.scale,
                        self.RULER_Y + self.RULER_HEIGHT,
                    )

        # Rows
        for i in range(self.rows + 1):
            pen = QPen()
            pen.setColor(theme.OUTLINE)
            pen.setWidth(0)

            painter.setPen(pen)
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.drawLine(
                0,
                i * self.CUE_HEIGHT + self.CUE_Y,
                self.size().width(),
                i * self.CUE_HEIGHT + self.CUE_Y,
            )

        # Cues
        for cue, rect in self.cueRects():
            state = State.NONE
            if cue == self.hovering_object:
                state = State.HOVERING
            if cue == self.selected:
                state = State.SELECTED
            cue.paint(painter, rect, state)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timeline")
        self.resize(1080, 720)

        timeline = Timeline()

        scroll_area = QScrollArea()
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(timeline)

        left_tabs = QTabWidget()
        left_tabs.setMinimumHeight(720 / 2)

        right_tabs = QTabWidget()
        right_tabs.setMinimumHeight(720 / 2)

        left_layout = QVBoxLayout()
        left_layout.addWidget(left_tabs)
        right_layout = QVBoxLayout()
        right_layout.addWidget(right_tabs)

        top_layout = QHBoxLayout()
        top_layout.addLayout(left_layout)
        top_layout.addLayout(right_layout)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(scroll_area)


app = QApplication(sys.argv)
theme.load()
window = MainWindow()
window.show()
app.exec()
