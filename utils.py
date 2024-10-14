from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel

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

def updateTimelineReceiver(self, *args):
    QApplication.instance().updateTimeline.emit()
