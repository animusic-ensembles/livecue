from abc import ABC, abstractmethod

from PySide6.QtGui import (
    QCursor,
    QPainterPath,
    QPainter,
    QBrush,
    QPen,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QWidget,
    QApplication,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QRect, QRectF

import theme
from utils import chain
from .common import State
from .time import Time, TimeClock, TimeMusic
from .cue import LightingCue, SceneCue


class Row(ABC):
    ALLOWED_TYPES = []
    HEIGHT = 60
    ROW_PADDING = 0

    def __init__(self, timeline, elements=[]):
        self.timeline = timeline
        self.elements = set()

    def add(self, element):
        self.elements.add(element)

    def contains(self, element):
        return element in self.elements

    def remove(self, element):
        self.elements.remove(element)

    def canContain(self, element):
        return any(
            isinstance(element, allowed_type) for allowed_type in self.ALLOWED_TYPES
        )

    def elementsRects(self):
        for elem in self.elements:
            rect = QRectF(
                elem.start * self.timeline.scale,
                self.ROW_PADDING / 2,
                elem.length * self.timeline.scale,
                self.HEIGHT - self.ROW_PADDING,
            )
            yield elem, rect

    def paint(self, painter, y):
        # TODO: Display row properties
        for elem, rect in self.elementsRects():
            rect.adjust(0, y, 0, y)
            elem.paint(painter, rect)

    def snaps(self, exclude_element):
        for elem, rect in self.elementsRects():
            if elem == exclude_element:
                continue
            yield rect.x()
            yield rect.x() + rect.width()


class LabelRow(Row):
    HEIGHT = 15


class TimeRow(Row):
    HEIGHT = 40
    ALLOWED_TYPES = [Time]

    def snaps(self, exclude_element):
        super().snaps(exclude_element)
        for time in self.elements:
            if time == exclude_element:
                continue
            for marking, _ in time.markings():
                yield marking


class GuideRow(Row):
    HEIGHT = 20


class LightingRow(Row):
    HEIGHT = 40
    ALLOWED_TYPES = [LightingCue]


class SceneRow(Row):
    ALLOWED_TYPES = [SceneCue]
    ROW_PADDING = 6

    def __init__(self, timeline, name):
        super().__init__(timeline)
        self.name = name

    def paint(self, painter, y):
        for cue, rect in self.elementsRects():
            rect.adjust(0, y, 0, y)
            state = State.NONE
            if cue == self.timeline.hovering_object:
                state = State.HOVERING
            if cue == self.timeline.selected:
                state = State.SELECTED
            cue.paint(painter, rect, state)


class Timeline(QWidget):
    # Scale/Scroll-related
    SCROLL_MOVE_MULTIPLIER = 1 / 2
    SCROLL_SCALE_MULTIPLIER = 1 / 1000
    SCALE_MIN = 0.1
    SCALE_MAX = 10

    # Bounds
    RESIZE_INNER_BOUND = 10
    RESIZE_OUTER_BOUND = 2

    # Snapping
    SNAP_MARKING_PIXELS = 6

    def __init__(self):
        super().__init__()
        self.scale = 1
        self.rows = [
            LabelRow(self),
            TimeRow(self),
            GuideRow(self),
            LightingRow(self),
            SceneRow(self, "Projector"),
            SceneRow(self, "Stream"),
        ]

        # TODO: Remove
        self.rows[1].add(TimeClock(0, 30))
        self.rows[1].add(TimeMusic(30 * theme.PIXELS_PER_SECOND, 60))
        self.rows[4].add(SceneCue(0, 0, 100, "CAMERA 1", theme.NEUTRAL_RED))
        self.rows[4].add(SceneCue(0, 300, 50, "CAMERA 3", theme.NEUTRAL_BLUE))
        self.rows[4].add(SceneCue(0, 900, 50, "CAMERA 3", theme.NEUTRAL_BLUE))
        self.rows[5].add(SceneCue(1, 100, 100, "MEDIA", theme.NEUTRAL_GREEN))

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

    def wheelEvent(self, event):
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            self.scale += event.angleDelta().y() * self.SCROLL_SCALE_MULTIPLIER
            self.scale = max(min(self.scale, self.SCALE_MAX), self.SCALE_MIN)
        else:
            scroll_bar = self.parent().parent().horizontalScrollBar()
            scroll_bar.setValue(
                scroll_bar.value()
                - (event.angleDelta().y() + event.angleDelta().x())
                * self.SCROLL_MOVE_MULTIPLIER
            )
        self.update()

    def mousePressEvent(self, event):
        self.mouseButtonEvent(event)

    def mouseReleaseEvent(self, event):
        self.mouseButtonEvent(event)

    def mouseButtonEvent(self, event):
        if Qt.MouseButton.LeftButton & event.buttons():
            # Try each in order:
            # 1) Start resizing an object
            # 2) Mark an object for movement
            #
            # Note: Starting a movement happens when the mouse moves *after* a
            # click so it's handled in mouseMoveEvent()
            if self.potential_resizing_object:
                self.resizing_object = self.potential_resizing_object
                self.handleResize(event, start=True)
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
                self.handleResize(event, stop=True)
                self.resizing_object = None
            elif self.moving_object:
                self.handleMove(event, stop=True)
                self.moving_object = None
            elif self.potential_moving_object:
                self.selected = self.potential_moving_object
            else:
                self.selected = None
            self.potential_moving_object = None
        self.update()

    def handleResize(self, event, start=False, stop=False):
        if start:
            self.resizing_start_pos = event.position()
            self.resizing_old_start = self.resizing_object.start
            self.resizing_old_length = self.resizing_object.length

        if (
            self.resizing_start_pos.x()
            < (self.resizing_old_start + self.resizing_old_length / 2) * self.scale
        ):
            # resize left handle
            delta = (
                (event.position().x() - self.resizing_start_pos.x()) * 1 / self.scale
            )
            self.resizing_object.start = self.resizing_old_start + delta
            self.resizing_object.length = self.resizing_old_length - delta

            # Snap to markings
            for snap in self.snaps(self.resizing_object):
                if abs(self.resizing_object.start - snap) < self.SNAP_MARKING_PIXELS:
                    self.resizing_object.length += self.resizing_object.start - snap
                    self.resizing_object.start = snap
                    break
        else:
            # Resize right handle
            delta = (
                (event.position().x() - self.resizing_start_pos.x()) * 1 / self.scale
            )
            self.resizing_object.length = self.resizing_old_length + delta

            # Snap to markings
            for snap in self.snaps(self.resizing_object):
                right = self.resizing_object.start + self.resizing_object.length
                if abs(right - snap) < self.SNAP_MARKING_PIXELS:
                    self.resizing_object.length = snap - self.resizing_object.start
                    break

        if stop:
            if self.resizing_object.length < 0:
                self.resizing_object.length *= -1
                self.resizing_object.start -= self.resizing_object.length
            self.resizing_object.length = max(
                self.resizing_object.length, self.resizing_object.MIN_LENGTH
            )

    def snaps(self, exclude_element):
        yield 0
        for row in self.rows:
            for snap in row.snaps(exclude_element):
                yield snap

    def handleMove(self, event, start=False, stop=False):
        if start:
            self.moving_start_pos = event.position()
            self.moving_old_start = self.moving_object.start

        delta = (event.position().x() - self.moving_start_pos.x()) * 1 / self.scale
        self.moving_object.start = self.moving_old_start + delta

        for snap in self.snaps(self.moving_object):
            if abs(self.moving_object.start - snap) < self.SNAP_MARKING_PIXELS:
                self.moving_object.start = snap
                break

        goal_row = None
        current_row = None
        for row, y in self.rowsOffsets():
            if not goal_row and event.position().y() < y + row.HEIGHT:
                goal_row = row
            if row.contains(self.moving_object):
                current_row = row

        if (
            goal_row
            and current_row != goal_row
            and goal_row.canContain(self.moving_object)
        ):
            goal_row.add(self.moving_object)
            current_row.remove(self.moving_object)

    def rowsOffsets(self):
        y = 0
        for row in self.rows:
            yield row, y
            y += row.HEIGHT

    def elementsRects(self):
        for row, y in self.rowsOffsets():
            for elem, rect in row.elementsRects():
                yield elem, rect.adjusted(0, y, 0, y)

    def mouseMoveEvent(self, event):
        # Set hovering object
        self.hovering_object = None
        for obj, rect in self.elementsRects():
            if rect.contains(event.position()):
                self.hovering_object = obj
                break

        # Check object resize handles
        self.potential_resizing_object = None
        for obj, rect in self.elementsRects():
            left_rect = rect.adjusted(
                -self.RESIZE_OUTER_BOUND, 0, self.RESIZE_INNER_BOUND - rect.width(), 0
            )
            if left_rect.contains(event.position()):
                self.setCursor(QCursor(Qt.SplitHCursor))
                self.potential_resizing_object = obj
                break

            right_rect = rect.adjusted(
                rect.width() - self.RESIZE_INNER_BOUND, 0, self.RESIZE_OUTER_BOUND, 0
            )
            if right_rect.contains(event.position()):
                self.setCursor(QCursor(Qt.SplitHCursor))
                self.potential_resizing_object = obj
                break

        # Only reset cursor if not resizing and not hovering a handle
        if not self.resizing_object and not self.potential_resizing_object:
            self.setCursor(QCursor(Qt.ArrowCursor))

        # Send mouse event positions to objects
        if self.resizing_object:
            self.handleResize(event)

        if self.moving_object:
            self.handleMove(event)
        elif self.potential_moving_object:
            self.moving_object = self.potential_moving_object
            self.handleMove(event, start=True)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        # Background
        brush = QBrush()
        brush.setColor(theme.BG)
        brush.setStyle(Qt.SolidPattern)
        rect = QRect(0, 0, self.size().width(), self.size().height())
        painter.fillRect(rect, brush)

        pen = QPen()
        pen.setColor(theme.OUTLINE)
        pen.setWidth(0)

        for row, y in self.rowsOffsets():
            row.paint(painter, y)

            # Bottom row separator
            painter.setPen(pen)
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.drawLine(0, y + row.HEIGHT, self.size().width(), y + row.HEIGHT)
