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
)
from PySide6.QtWidgets import (
    QWidget,
    QApplication,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QPoint, QRect, QRectF, QTimer

import theme
from utils import chain, textWidth, saveProject
from .common import State, TimelineElement
from .time import Time, TimeClock, TimeMusic
from .cue import LightingCue, SceneCue
from .labels import Label


class Row(ABC):
    SAVED_ATTRIBUTES = []
    ALLOWED_TYPES = []
    HEIGHT = 30
    ROW_PADDING = 0

    def __init__(self, timeline, elements=[]):
        self.timeline = timeline
        self.elements = elements
        self.elements_set = set(self.elements)

    def add(self, element):
        self.elements_set.add(element)
        self.elements = sorted(self.elements_set, key=lambda e : e.start)

    def contains(self, element):
        return element in self.elements_set

    def remove(self, element):
        self.elements_set.remove(element)
        self.elements = sorted(self.elements_set, key=lambda e : e.start)

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

    def paint(self, painter, y, bounds):
        # TODO: Display row properties
        for elem, rect in self.elementsRects():
            if rect.x() + rect.width() < bounds[0]:
                continue
            if rect.x() > bounds[1]:
                break
            rect.adjust(0, y, 0, y)
            state = State.NONE
            if elem == self.timeline.hovering_element:
                state = State.HOVERING
            if elem == self.timeline.selected_element:
                state = State.SELECTED
            elem.paint(painter, rect, state)

    def snaps(self, exclude_element=None):
        for elem in self.elements:
            if elem == exclude_element:
                continue
            yield elem.start
            yield elem.start + elem.length

    def save(self):
        out = {
            "type": self.__class__.__name__,
            "elements": [element.save() for element in self.elements]
        }
        for attr in self.SAVED_ATTRIBUTES:
            out[attr] = getattr(self, attr)
        return out

    @classmethod
    def load(cls, timeline, type, elements, **kwargs):
        row_type = getattr(sys.modules[__name__], type)
        elements = [TimelineElement.load(**element) for element in elements]
        kwargs["elements"] = elements
        return row_type(timeline, **kwargs)


class LabelRow(Row):
    HEIGHT = 15
    ALLOWED_TYPES = [Label]


class TimeRow(Row):
    HEIGHT = 40
    ALLOWED_TYPES = [TimeClock, TimeMusic]

    def snaps(self, exclude_element=None, coarse=False):
        super().snaps(exclude_element)
        for time in self.elements:
            if time == exclude_element:
                continue
            for marking, label in time.markings():
                if coarse:
                    if label:
                        yield marking
                else:
                    yield marking


class GuideRow(Row):
    HEIGHT = 20


class LightingRow(Row):
    HEIGHT = 40
    ALLOWED_TYPES = [LightingCue]


class SceneRow(Row):
    SAVED_ATTRIBUTES = ["name"]
    ALLOWED_TYPES = [SceneCue]
    HEIGHT = 60
    ROW_PADDING = 6

    def __init__(self, timeline, name, elements=[]):
        super().__init__(timeline, elements)
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

    # Drawing
    PLAYHEAD_TOP_OFFSET = 2
    PLAYHEAD_BOTTOM_OFFSET = 2

    # Playback
    TIMER_INTERVAL = 40

    def __init__(self, hboxlayout, scale=0.05):
        super().__init__()
        QApplication.instance().updateTimeline.connect(self.updateTimeline)
        self.hboxlayout = hboxlayout
        self.scale = scale
        self.rows = []
        self.total_row_height = 0
        self.playhead_height = 0

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

        self.seeking = False
        self.playing = False
        self.playhead = 0
        self.accurate_playhead = 0
        self.play_timer = None
        self.playing_elements = set()
        self.next_elements = set()

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMinimumWidth(self.MIN_WIDTH + self.EXTRA_WIDTH)

    def wheelEvent(self, event):
        scroll_bar = self.parent().parent().horizontalScrollBar()
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.ControlModifier:
            old_scale = self.scale
            self.scale += event.angleDelta().y() * self.scale * self.SCROLL_SCALE_MULTIPLIER
            self.scale = max(min(self.scale, self.SCALE_MAX), self.SCALE_MIN)

            # Scroll to maintain relative position of cursor on the timeline.
            mouse_pos = self.mapFromGlobal(QCursor.pos())
            new_value = (mouse_pos.x()) * self.scale / old_scale - (mouse_pos.x() - scroll_bar.value())
            self.updateTimeline()
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

    def select(self, element):
        if self.selected_element:
            self.hboxlayout.removeWidget(self.selected_element.getWidget())
            self.selected_element.getWidget().hide()
        self.selected_element = element
        if self.selected_element:
            self.hboxlayout.addWidget(self.selected_element.getWidget())
            self.selected_element.getWidget().show()

    def mouseButtonEvent(self, event):
        if Qt.MouseButton.LeftButton & event.buttons():
            # Try each in order:
            # 1) Start seeking
            # 2) Start resizing an object
            # 3) Mark an object for movement
            #
            # Note: Starting a movement happens when the mouse moves *after* a
            # click so it's handled in mouseMoveEvent()
            if self.mouseInSeekArea(event):
                self.seeking = True
            elif self.potential_resizing_element:
                self.resizing_element = self.potential_resizing_element
                self.handleResize(event, start=True)
            elif self.hovering_element:
                self.potential_moving_element = self.hovering_element
        else:
            # Try each in order:
            # 1) Stop seeking
            # 2) Stop resizing an object
            # 3) Stop moving an object
            # 4) Select the object marked for movement that didn't move
            # 5) Deselect an object, because the press must not have been over
            #    an object (i.e. self.potential_moving_element = None)
            #
            if self.seeking:
                self.seeking = False
            elif self.resizing_element:
                self.handleResize(event, stop=True)
                self.resizing_element = None
            elif self.moving_element:
                self.handleMove(event, stop=True)
                self.moving_element = None
            elif self.potential_moving_element:
                self.select(self.potential_moving_element)
            else:
                self.select(None)
            self.potential_moving_element = None
        self.update()

        # Save on any mouse button press which generally corresponds to an
        # action worth saving (e.g. let go of a move).
        saveProject()

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

    def snaps(self, exclude_element=None):
        yield 0
        yield self.playhead
        for row in self.rows:
            for snap in row.snaps(exclude_element):
                yield snap

    def fineTimeSnaps(self):
        yield 0
        for row in self.rows:
            if isinstance(row, TimeRow):
                for snap in row.snaps():
                    yield snap

    def coarseTimeSnaps(self):
        yield 0
        for row in self.rows:
            if isinstance(row, TimeRow):
                for snap in row.snaps(coarse=True):
                    yield snap

    def cueSnaps(self):
        for row in self.rows:
            if isinstance(row, (SceneRow, LightingRow)):
                for element in row.elements:
                    yield element.start
                    yield element.start + element.length

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

    def mouseInSeekArea(self, event):
        return self.playhead_height < event.position().y() < self.playhead_height + TimeRow.HEIGHT - Time.TEXT_HEIGHT

    def mouseMoveEvent(self, event):
        # Seek playhead
        if self.seeking and self.mouseInSeekArea(event):
            self.playhead = self.accurate_playhead = event.position().x() / self.scale
            self.updatePlayhead()

        # Set hovering object
        self.hovering_element = None
        if not self.mouseInSeekArea(event):
            for obj, rect in self.elementsRects():
                if rect.contains(event.position()):
                    self.hovering_element = obj
                    break

        # Check object resize handles
        self.potential_resizing_element = None
        if not self.mouseInSeekArea(event):
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
        modifiers = QApplication.keyboardModifiers()
        if event.key() == Qt.Key_Delete:
            if not self.selected_element:
                super().keyPressEvent(event)
                return

            for row in self.rows:
                if row.contains(self.selected_element):
                    for i, e in enumerate(row.elements):
                        if e == self.selected_element:
                            break
                    self.remove(self.selected_element, row=row)

                    # Select previous element
                    if i > 0:
                        self.select(row.elements[i - 1])
        elif event.key() == Qt.Key_P:
            if self.playing:
                self.stopPlaying()
            else:
                self.startPlaying()
            return
        elif event.key() == Qt.Key_Left:
            if modifiers & Qt.ShiftModifier and modifiers & Qt.ControlModifier:
                pass
            elif modifiers & Qt.ShiftModifier:
                self.seekRelative(-1)
            elif modifiers & Qt.ControlModifier:
                prevSnap = 0
                for snap in self.coarseTimeSnaps():
                    if snap > prevSnap and snap < self.accurate_playhead:
                        prevSnap = snap
                self.seekAbsolute(prevSnap)
            else:
                prevSnap = 0
                for snap in self.fineTimeSnaps():
                    if snap > prevSnap and snap < self.accurate_playhead:
                        prevSnap = snap
                self.seekAbsolute(prevSnap)
            return
        elif event.key() == Qt.Key_Right:
            if modifiers & Qt.ShiftModifier and modifiers & Qt.ControlModifier:
                pass
            elif modifiers & Qt.ShiftModifier:
                self.seekRelative(1)
            elif modifiers & Qt.ControlModifier:
                # TODO: don't hardcode
                nextSnap = 10e8
                for snap in self.coarseTimeSnaps():
                    if snap < nextSnap and snap > self.accurate_playhead:
                        nextSnap = snap
                self.seekAbsolute(nextSnap)
            else:
                # TODO: don't hardcode
                nextSnap = 10e8
                for snap in self.fineTimeSnaps():
                    if snap < nextSnap and snap > self.accurate_playhead:
                        nextSnap = snap
                self.seekAbsolute(nextSnap)
            return
        elif event.key() == Qt.Key_Space:
            if modifiers & Qt.ShiftModifier:
                prevSnap = 0
                for snap in self.cueSnaps():
                    if snap > prevSnap and snap < self.accurate_playhead:
                        prevSnap = snap
                self.seekAbsolute(prevSnap)
            else:
                # TODO: don't hardcode
                nextSnap = 10e8
                for snap in self.cueSnaps():
                    if snap < nextSnap and snap > self.accurate_playhead:
                        nextSnap = snap
                self.seekAbsolute(nextSnap)
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

        # Rendering bounds
        scroll_bar = self.parent().parent().horizontalScrollBar()
        bounds = scroll_bar.value(), scroll_bar.value() + scroll_bar.width()

        for row, y in self.rowsOffsets():
            row.paint(painter, y, bounds)

            # Bottom row separator
            painter.setPen(pen)
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.drawLine(0, y + row.HEIGHT, self.size().width(), y + row.HEIGHT)

        # Playhead
        pen = QPen()
        pen.setColor(theme.PLAYHEAD)
        pen.setWidth(1)
        brush = QBrush()
        brush.setColor(theme.PLAYHEAD)
        brush.setStyle(Qt.SolidPattern)
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawLine(self.playhead * self.scale, 0, self.playhead * self.scale, self.total_row_height)
        points = [
            QPoint(self.playhead * self.scale, self.playhead_height + self.PLAYHEAD_TOP_OFFSET),
            QPoint(self.playhead * self.scale + 10, self.playhead_height + (TimeRow.HEIGHT - Time.TEXT_HEIGHT) / 2),
            QPoint(self.playhead * self.scale, self.playhead_height + (TimeRow.HEIGHT - Time.TEXT_HEIGHT) - self.PLAYHEAD_BOTTOM_OFFSET),
        ]
        painter.drawPolygon(points)

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
                QApplication.instance().updateTimeline.emit()
                self.select(element)
                break

    def addRow(self, row):
        self.rows.append(row)
        self.total_row_height = sum([row.HEIGHT for row in self.rows])
        self.playhead_height = 0
        for row in self.rows:
            if isinstance(row, TimeRow):
                self.playhead_height += Time.TEXT_HEIGHT
                break
            self.playhead_height += row.HEIGHT

    def remove(self, element, row=None):
        if not row:
            for r in self.rows:
                if r.contains(element):
                    row = r
        row.remove(element)
        if self.selected_element == element:
            self.hboxlayout.removeWidget(self.selected_element.getWidget())
            self.selected_element.getWidget().hide()
            self.selected_element = None
        QApplication.instance().updateTimeline.emit()

    def startPlaying(self):
        self.play_timer = QTimer()
        self.play_timer.setInterval(self.TIMER_INTERVAL)
        self.play_timer.timeout.connect(self.playTimerTick)
        self.play_timer.start()
        self.playing = True

    def playTimerTick(self):
        self.accurate_playhead += self.TIMER_INTERVAL * theme.PIXELS_PER_SECOND / 1000
        self.playhead = int(self.accurate_playhead)
        self.updatePlayhead()

    def stopPlaying(self):
        self.play_timer.stop()
        self.play_timer = None
        self.playing = False

    def seekRelative(self, delta):
        self.seekAbsolute(self.accurate_playhead + delta)

    def seekAbsolute(self, value):
        self.playhead = self.accurate_playhead = value
        self.updatePlayhead()

    def updatePlayhead(self):
        new_playing = set()
        new_next = set()
        for row in self.rows:
            next_element = False
            for element in row.elements:
                if self.playhead < element.start:
                    new_next.add(element)
                    break
                if element.start <= self.playhead < element.start + element.length:
                    new_playing.add(element)
                    next_element = True
        for element in self.playing_elements - new_playing:
            element.exit()
        for element in new_playing - self.playing_elements:
            element.enter()
        for element in new_next - self.next_elements:
            element.enterNextInRow()
        self.playing_elements = new_playing
        self.next_elements = new_next
        self.update()

    def save(self):
        return {
            "scale": self.scale,
            "rows": [row.save() for row in self.rows],
        }

    @classmethod
    def load(cls, hboxlayout, scale, rows):
        timeline = cls(hboxlayout, scale)
        for row in rows:
            timeline.addRow(Row.load(timeline, **row))
        timeline.update()
        return timeline

    def updateWidth(self):
        w = self.MIN_WIDTH
        for _, rect in self.elementsRects():
            w = max(w, rect.x() + rect.width())
        self.setMinimumWidth(w + self.EXTRA_WIDTH)

    def updateTimeline(self):
        saveProject()
        self.updateWidth()
        self.update()