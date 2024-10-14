from abc import ABC, abstractmethod
from enum import Enum, auto

from PySide6.QtWidgets import QApplication, QSpinBox


class Element(ABC):
    def __init__(self, start):
        self._start = QSpinBox()
        self._start.setMaximum(10e6)
        self._start.valueChanged.connect(self.set_start)
        self.start = start

        self.widget = self.createWidget()

    def set_start(self, value):
        self._start.setValue(value)
        QApplication.instance().updateTimeline.emit()

    def get_start(self):
        return self._start.value()
    
    start = property(get_start, set_start)

    @abstractmethod
    def set_length(self, value):
        pass

    @abstractmethod
    def get_length(self):
        pass

    @abstractmethod
    def createWidget(self):
        pass

    def getWidget(self):
        return self.widget


class State(Enum):
    NONE = auto()
    SELECTED = auto()
    HOVERING = auto()
