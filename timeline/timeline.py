import json
import sys
import shutil
import os
from abc import ABC, abstractmethod
from datetime import datetime

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
from .labels import Label


class Row(ABC):
    ALLOWED_TYPES = []
    HEIGHT = 30
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
        if isinstance(element, type):
            return element in self.ALLOWED_TYPES
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
            state = State.NONE
            if elem == self.timeline.hovering_element:
                state = State.HOVERING
            if elem == self.timeline.selected_element:
                state = State.SELECTED
            elem.paint(painter, rect, state)

    def snaps(self, exclude_element):
        for elem in self.elements:
            if elem == exclude_element:
                continue
            yield elem.start
            yield elem.start + elem.length


class LabelRow(Row):
    HEIGHT = 15
    ALLOWED_TYPES = [Label]


class TimeRow(Row):
    HEIGHT = 40
    ALLOWED_TYPES = [TimeClock, TimeMusic]

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
    HEIGHT = 60
    ROW_PADDING = 6

    def __init__(self, timeline, name):
        super().__init__(timeline)
        self.name = name


class Timeline(QWidget):
    # Scale/Scroll-related
    SCROLL_MOVE_MULTIPLIER = 1 / 2
    SCROLL_SCALE_MULTIPLIER = 1 / 5000
    SCALE_MIN = 0.001
    SCALE_MAX = 10
    MIN_WIDTH = 100
    EXTRA_WIDTH = 250

    # Bounds
    RESIZE_INNER_BOUND = 10
    RESIZE_OUTER_BOUND = 2

    # Snapping
    SNAP_MARKING_PIXELS = 240

    def __init__(self, hboxlayout):
        super().__init__()
        QApplication.instance().updateTimeline.connect(self.updateTimeline)
        self.hboxlayout = hboxlayout
        self.scale = 0.05
        self.rows = [
            LabelRow(self),
            GuideRow(self),
            TimeRow(self),
            LightingRow(self),
            SceneRow(self, "Projector"),
            SceneRow(self, "Stream"),
        ]

        self.selected_element = None
        self.hovering_element = None

        self.resizing_start_pos = None
        self.potential_resizing_element = None
        self.resizing_element = None
        self.resizing_old_start = 0
        self.resizing_old_length = 0

        self.moving_start_pos = None
        self.potential_moving_element = None
        self.moving_element = None
        self.moving_old_start = 0

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMinimumWidth(self.MIN_WIDTH + self.EXTRA_WIDTH)

    def wheelEvent(self, event):
        scroll_bar = self.parent().parent().horizontalScrollBar()
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            old_scale = self.scale
            self.scale += event.angleDelta().y() * self.scale * self.SCROLL_SCALE_MULTIPLIER
            self.scale = max(min(self.scale, self.SCALE_MAX), self.SCALE_MIN)

            # Scroll to maintain relative position of cursor on the timeline.
            mouse_pos = self.mapFromGlobal(QCursor.pos())
            new_value = (mouse_pos.x()) * self.scale / old_scale - (mouse_pos.x() - scroll_bar.value())
            self.update()
            scroll_bar.setValue(new_value)
        else:
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
            if self.potential_resizing_element:
                self.resizing_element = self.potential_resizing_element
                self.handleResize(event, start=True)
            elif self.hovering_element:
                self.potential_moving_element = self.hovering_element
        else:
            # Try each in order:
            # 1) Stop resizing an object
            # 2) Stop moving an object
            # 3) Select the object marked for movement that didn't move
            # 4) Deselect an object, because the press must not have been over
            #    an object (i.e. self.potential_moving_element = None)
            #
            if self.resizing_element:
                self.handleResize(event, stop=True)
                self.resizing_element = None
            elif self.moving_element:
                self.handleMove(event, stop=True)
                self.moving_element = None
            elif self.potential_moving_element:
                if self.selected_element:
                    self.hboxlayout.removeWidget(self.selected_element.getWidget())
                    self.selected_element.getWidget().hide()
                self.selected_element = self.potential_moving_element
                self.hboxlayout.addWidget(self.selected_element.getWidget())
                self.selected_element.getWidget().show()
            else:
                if self.selected_element:
                    self.hboxlayout.removeWidget(self.selected_element.getWidget())
                    self.selected_element.getWidget().hide()
                self.selected_element = None
            self.potential_moving_element = None
        self.update()
        self.save()

    def handleResize(self, event, start=False, stop=False):
        if start:
            self.resizing_start_pos = event.position()
            self.resizing_old_start = self.resizing_element.start
            self.resizing_old_length = self.resizing_element.length

        if (
            self.resizing_start_pos.x()
            < (self.resizing_old_start + self.resizing_old_length / 2) * self.scale
        ):
            # resize left handle
            delta = (
                (event.position().x() - self.resizing_start_pos.x()) * 1 / self.scale
            )
            self.resizing_element.start = self.resizing_old_start + delta
            self.resizing_element.length = self.resizing_old_length - delta

            # Snap to markings
            for snap in self.snaps(self.resizing_element):
                if abs(self.resizing_element.start - snap) < self.SNAP_MARKING_PIXELS:
                    self.resizing_element.length += self.resizing_element.start - snap
                    self.resizing_element.start = snap
                    break
        else:
            # Resize right handle
            delta = (
                (event.position().x() - self.resizing_start_pos.x()) * 1 / self.scale
            )
            self.resizing_element.length = self.resizing_old_length + delta

            # Snap to markings
            for snap in self.snaps(self.resizing_element):
                right = self.resizing_element.start + self.resizing_element.length
                if abs(right - snap) < self.SNAP_MARKING_PIXELS:
                    self.resizing_element.length = snap - self.resizing_element.start
                    break

    def snaps(self, exclude_element):
        yield 0
        for row in self.rows:
            for snap in row.snaps(exclude_element):
                yield snap

    def handleMove(self, event, start=False, stop=False):
        if start:
            self.moving_start_pos = event.position()
            self.moving_old_start = self.moving_element.start

        delta = (event.position().x() - self.moving_start_pos.x()) * 1 / self.scale
        self.moving_element.start = self.moving_old_start + delta

        for snap in self.snaps(self.moving_element):
            if abs(self.moving_element.start - snap) < self.SNAP_MARKING_PIXELS:
                self.moving_element.start = snap
                break

        goal_row = None
        current_row = None
        for row, y in self.rowsOffsets():
            if not goal_row and event.position().y() < y + row.HEIGHT:
                goal_row = row
            if row.contains(self.moving_element):
                current_row = row

        if (
            goal_row
            and current_row != goal_row
            and goal_row.canContain(self.moving_element)
        ):
            goal_row.add(self.moving_element)
            current_row.remove(self.moving_element)

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
        self.hovering_element = None
        for obj, rect in self.elementsRects():
            if rect.contains(event.position()):
                self.hovering_element = obj
                break

        # Check object resize handles
        self.potential_resizing_element = None
        for obj, rect in self.elementsRects():
            left_rect = rect.adjusted(
                -self.RESIZE_OUTER_BOUND, 0, self.RESIZE_INNER_BOUND - rect.width(), 0
            )
            if left_rect.contains(event.position()):
                self.setCursor(QCursor(Qt.SplitHCursor))
                self.potential_resizing_element = obj
                break

            right_rect = rect.adjusted(
                rect.width() - self.RESIZE_INNER_BOUND, 0, self.RESIZE_OUTER_BOUND, 0
            )
            if right_rect.contains(event.position()):
                self.setCursor(QCursor(Qt.SplitHCursor))
                self.potential_resizing_element = obj
                break

        # Only reset cursor if not resizing and not hovering a handle
        if not self.resizing_element and not self.potential_resizing_element:
            self.setCursor(QCursor(Qt.ArrowCursor))

        # Send mouse event positions to objects
        if self.resizing_element:
            self.handleResize(event)

        if self.moving_element:
            self.handleMove(event)
        elif self.potential_moving_element:
            self.moving_element = self.potential_moving_element
            self.handleMove(event, start=True)

        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            if self.selected_element:
                self.remove(self.selected_element)
                self.update()
        super().keyPressEvent(event)

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

    def add(self, element_type, **kwargs):
        for row in self.rows:
            if row.canContain(element_type):
                if "start" not in kwargs:
                    kwargs["start"] = 0
                    for element in row.elements:
                        kwargs["start"] = max(kwargs["start"], element.start + element.length)
                if "length" not in kwargs:
                    kwargs["length"] = 1000
                element = element_type(**kwargs)
                row.add(element)
                self.update()
                self.save()
                return

    def remove(self, element):
        for row in self.rows:
            if row.contains(element):
                row.remove(element)
        if self.selected_element == element:
            self.hboxlayout.removeWidget(self.selected_element.getWidget())
            self.selected_element.getWidget().hide()
            self.selected_element = None
        self.update()
        self.save()

    # TODO: Move somewhere higher level, like MainWindow or Application since saving
    # is likely to extend past the timeline in the future.
    def save(self):
        out = []
        # TODO: Preserve row (for when multiple rows of the same kind can exist)
        for row in self.rows:
            for element in row.elements:
                out.append((element.__class__.__name__, element.as_dict()))
        with open("animusic.json", "w") as f:
            f.write(json.dumps(out, indent=2))

    def load(self):
        os.makedirs("backups", exist_ok=True)
        try:
            shutil.copy("animusic.json", f"backups/animusic.{datetime.now().strftime('%Y%m%dT%H%M%S')}.json")
            with open("animusic.json", "r") as f:
                elements = json.loads(f.read())
                for element, kwargs in elements:
                    self.add(getattr(sys.modules[__name__], element), **kwargs)
        except FileNotFoundError:
            pass

    def updateWidth(self):
        w = self.MIN_WIDTH
        for _, rect in self.elementsRects():
            w = max(w, rect.x() + rect.width())
        self.setMinimumWidth(w + self.EXTRA_WIDTH)

    def updateTimeline(self):
        self.save()
        self.update()

    def update(self):
        self.updateWidth()
        super().update()
