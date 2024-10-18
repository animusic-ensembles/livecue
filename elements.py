from PySide6.QtGui import QColor
 

SCENES = {}

class Scene:
    def __init__(self, id, name, color):
        self.id = id
        self.name = name
        self.color = QColor(color)
        SCENES[id] = self

    @classmethod
    def from_id(self, id):
        return SCENES[id]