from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel
from PySide6.QtGui import QFontMetrics

def chain(*iterators):
    for iterator in iterators:
        for element in iterator:
            yield element

def widgetWithLabel(widget, label_text):
    hbox = QHBoxLayout()
    label = QLabel(label_text)
    hbox.addWidget(label)
    hbox.addWidget(widget)
    return hbox

def updateTimelineReceiver(*args):
    QApplication.instance().updateTimeline.emit()

def saveProject(*args):
    QApplication.instance().saveProject.emit()

TEXT_WIDTH_CACHE = {}
def textWidth(font, text):
    if (font, text) not in TEXT_WIDTH_CACHE:
        TEXT_WIDTH_CACHE[(font, text)] = QFontMetrics(font).horizontalAdvance(text)
    return TEXT_WIDTH_CACHE[(font, text)]
