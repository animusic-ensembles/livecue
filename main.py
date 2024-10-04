import sys
from abc import ABC, abstractmethod
from enum import Enum, auto

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGui import QPainterPath, QTransform, QColor, QPainter, QBrush, QPen, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget, QMainWindow, QApplication, QVBoxLayout, QScrollArea, QSizePolicy
from PySide6.QtCore import Qt, QRect, QRectF

import colors


class State(Enum):
    NONE = auto()
    SELECTED = auto()
    HOVERING = auto()


class Scene:
    def __init__(self, name, color):
        self.name = name
        self.color = color


class TimelineTime:
    def __init__(
        self,
    ):
        pass


class TimelineScene:
    ROUNDING_RADIUS = 3
    MIN_LENGTH = 1

    def __init__(self, row, start, length, scene):
        self.row = row
        self.start = start
        self.length = length
        self.scene = scene

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
            brush.setColor(self.scene.color)
        elif state == State.HOVERING:
            brush.setColor(self.scene.color.darker(120))
        elif state == State.SELECTED:
            brush.setColor(self.scene.color.lighter(120))
        brush.setStyle(Qt.SolidPattern)

        pen = QPen()
        if state == State.SELECTED:
            pen.setColor(colors.SELECTED_OUTLINE)
        else:
            pen.setColor(colors.OUTLINE)
        pen.setWidth(1)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillPath(qpp, brush)
        painter.setPen(pen)
        painter.drawPath(qpp)

        pen = QPen()
        pen.setColor(colors.TEXT)

        font = QFont()
        font.setStyleHint(QFont.SansSerif)
        font.setFamily(font.defaultFamily())
        
        fm = QFontMetrics(font)
        if fm.horizontalAdvance(self.scene.name) < rect.width():
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignCenter, self.scene.name)

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
        brush.setColor(colors.TIME_BG)
        brush.setStyle(Qt.SolidPattern)

        pen = QPen()
        pen.setColor(colors.OUTLINE)
        pen.setWidth(1)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillPath(qpp, brush)
        painter.setPen(pen)
        painter.drawPath(qpp)

        pen = QPen()
        pen.setColor(colors.TEXT)

        font = QFont()
        font.setStyleHint(QFont.SansSerif)
        font.setFamily(font.defaultFamily())
        
        fm = QFontMetrics(font)
        if fm.horizontalAdvance(self.get_name()) < rect.width():
            painter.setPen(pen)
            painter.drawText(rect.adjusted(self.LEFT_TEXT_OFFSET, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, self.get_name())


class TimeClock(Time):
    PIXELS_PER_SECOND = 80

    def __init__(self, start, length):
        self.start = start
        self.length= length


class TimeMusic(Time):
    PIXELS_PER_BEAT = 20

    def __init__(self, start, length, bpm, bpb, bar_offset=0):
        self.start = start
        self.bpm = bpm
        self.bpb = bpb
        self.bar_offset = bar_offset
        self.length = length

    def get_name(self):
        return f"♩={self.bpm}"


class Timeline(QWidget):
    ROWS = 2

    # Scale/Scroll-related
    SCROLL_MOVE_MULTIPLIER = 1 / 8
    SCROLL_SCALE_MULTIPLIER = 1 / 1000
    SCALE_MIN = 0.1
    SCALE_MAX = 10

    # Drawing offsets
    TIME_Y = 0
    TIME_HEIGHT = 20
    RULER_Y = TIME_HEIGHT
    RULER_HEIGHT = 20
    SCENE_Y = RULER_Y + RULER_HEIGHT
    SCENE_HEIGHT = 50
    ROW_PADDING = 6

    # Bounds
    RESIZE_INNER_BOUND = 10
    RESIZE_OUTER_BOUND = 2

    def __init__(self):
        super().__init__()
        self.scale = 1
        self.times = [
            TimeClock(0, 30),
            TimeMusic(30, 120, 120, 4),
            TimeMusic(120, 120, 60, 4, 120),
            TimeClock(240, 5*60),
        ]
        self.scenes = [
            TimelineScene(0, 0, 100, Scene("CAMERA 1", colors.NEUTRAL_RED)),
            TimelineScene(1, 100, 100, Scene("MEDIA", colors.NEUTRAL_GREEN)),
            TimelineScene(0, 300, 50, Scene("CAMERA 3", colors.NEUTRAL_BLUE)),
            TimelineScene(0, 900, 50, Scene("CAMERA 3", colors.NEUTRAL_BLUE)),
        ]

        self.selected = None
        self.hovering = None

        self.resizing_start_pos = None
        self.future_resizing_object = None
        self.resizing_object = None
        self.resizing_old_start = 0
        self.resizing_old_length = 0

        self.setMouseTracking(True)
        self.setMinimumWidth(1000)

    def wheelEvent(self, e):
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            self.scale += e.angleDelta().y() * self.SCROLL_SCALE_MULTIPLIER
            self.scale = max(min(self.scale, self.SCALE_MAX), self.SCALE_MIN)

        self.update()

    def mousePressEvent(self, e):
        self.mouseButtonEvent(e)

    def mouseReleaseEvent(self, e):
        self.mouseButtonEvent(e)

    def mouseButtonEvent(self, e):
        if Qt.MouseButton.LeftButton & e.buttons():
            # Start resize
            if self.future_resizing_object:
                self.resizing_object = self.future_resizing_object
                self.handleResize(e, start=True)

            # Select object
            self.selected = self.hovering
        else:
            # Stop resize
            if self.resizing_object:
                self.handleResize(e, stop=True)
                self.resizing_object = None

            # Deselect object
            if self.selected and not self.sceneRect(self.selected).contains(e.position()):
                self.selected = None
        self.update()

    def handleResize(self, e, start=False, stop=False):
        if start:
            print("Starting resize")
            self.resizing_start_pos = e.position()
            self.resizing_old_start = self.resizing_object.start
            self.resizing_old_length = self.resizing_object.length

        if self.resizing_start_pos.x() < (self.resizing_old_start + self.resizing_old_length / 2) * self.scale:
            # resize left handle
            delta = (e.position().x() - self.resizing_start_pos.x()) * 1/self.scale
            self.resizing_object.start = self.resizing_old_start + delta
            self.resizing_object.length = self.resizing_old_length - delta
        else:
            # resize right handle
            delta = (e.position().x() - self.resizing_start_pos.x()) * 1/self.scale
            self.resizing_object.length = self.resizing_old_length + delta

        if stop:
            print("Stopping resize")
            if self.resizing_object.length < 0:
                self.resizing_object.length *= -1
                self.resizing_object.start -= self.resizing_object.length
            self.resizing_object.length = max(self.resizing_object.length, self.resizing_object.MIN_LENGTH)


    def mouseMoveEvent(self, e):
        print(e.position())
        # Set hovering object
        self.hovering = None
        for scene, rect in self.sceneRects():
            if rect.contains(e.position()):
                self.hovering = scene
                break

        # Check object resize handles
        self.future_resizing_object = None
        for scene, rect in self.sceneRects():
            left_rect = rect.adjusted(-self.RESIZE_OUTER_BOUND, 0, self.RESIZE_INNER_BOUND - rect.width(), 0)
            if left_rect.contains(e.position()):
                self.setCursor(QtGui.QCursor(Qt.SplitHCursor))
                self.future_resizing_object = scene
                break

            right_rect = rect.adjusted(rect.width() - self.RESIZE_INNER_BOUND, 0, self.RESIZE_OUTER_BOUND, 0)
            if right_rect.contains(e.position()):
                self.setCursor(QtGui.QCursor(Qt.SplitHCursor))
                self.future_resizing_object = scene
                break

        # Only reset cursor if not resizing and not hovering a handle
        if not self.resizing_object and not self.future_resizing_object:
            self.setCursor(QtGui.QCursor(Qt.ArrowCursor))

        # Send mouse event positions to resizing object
        if self.resizing_object:
            self.handleResize(e)

        self.update()

    def sceneRect(self, scene):
        return QRectF(
            scene.start * self.scale,
            scene.row * self.SCENE_HEIGHT + self.ROW_PADDING / 2 + self.SCENE_Y,
            scene.length * self.scale,
            self.SCENE_HEIGHT - self.ROW_PADDING,
        )

    def sceneRects(self):
        for scene in self.scenes:
            yield scene, self.sceneRect(scene)

    def paintEvent(self, e):
        painter = QPainter(self)

        # Background
        brush = QBrush()
        brush.setColor(colors.BG)
        brush.setStyle(Qt.SolidPattern)
        rect = QRect(0, 0, self.size().width(), self.size().height())
        painter.fillRect(rect, brush)

        # Times
        for time in self.times:
            rect = QRect(
                    time.start * self.scale,
                    0,
                    time.length * self.scale,
                    self.TIME_HEIGHT)
            time.paint(painter, rect)

        # Ruler

        # Rows
        for i in range(self.ROWS + 1):
            pen = QPen()
            pen.setColor(colors.OUTLINE)
            pen.setWidth(0)

            painter.setPen(pen)
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.drawLine(0, i * self.SCENE_HEIGHT + self.SCENE_Y, self.size().width(), i * self.SCENE_HEIGHT + self.SCENE_Y)

        # Scenes
        for scene, rect in self.sceneRects():
            state = State.NONE
            if scene == self.hovering:
                state = State.HOVERING
            if scene == self.selected:
                state = State.SELECTED
            scene.paint(painter, rect, state)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timeline")


        timeline = Timeline()
        #timeline.setLayout(QVBoxLayout())

        scroll_area = QScrollArea()
        timeline.scroll_area = scroll_area
        #scroll_area.setWidget(timeline)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(timeline)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        main_layout.addWidget(scroll_area)


app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()
