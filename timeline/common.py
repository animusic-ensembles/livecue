import sys
from abc import ABC, abstractmethod
from enum import Enum, auto

from PySide6.QtWidgets import QApplication, QSpinBox

from utils import updateTimelineReceiver


class TimelineElement(ABC):
    MIN_LENGTH = 1
    SAVED_ATTRIBUTES = ["start", "length"]

    def __init__(self, start, length):
        self._start = QSpinBox()
        self._start.setMaximum(10e6)
        self._start.valueChanged.connect(updateTimelineReceiver)
        self.start = start

        self._length = QSpinBox()
        self._length.setMaximum(10e6)
        self._length.valueChanged.connect(updateTimelineReceiver)
        self.length = length

        self.widget = self.createWidget()

    def set_length(self, value):
        self._length.setValue(max(value, self.MIN_LENGTH))

    def get_length(self):
        return self._length.value()

    length = property(get_length, set_length)

    def set_start(self, value):
        self._start.setValue(value)

    def get_start(self):
        return self._start.value()
    
    start = property(get_start, set_start)

    @abstractmethod
    def createWidget(self):
        pass

    def getWidget(self):
        return self.widget

    def save(self):
        out = {"type": self.__class__.__name__}
        for attr in self.SAVED_ATTRIBUTES:
            out[attr] = getattr(self, attr)
        return out

    @classmethod
    def load(cls, type, **kwargs):
        element_type = getattr(sys.modules["timeline"], type)
        return element_type(**kwargs)

class State(Enum):
    NONE = auto()
    SELECTED = auto()
    HOVERING = auto()
