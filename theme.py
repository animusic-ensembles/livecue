from PySide6.QtGui import QColor, QFont

# Just the colors
DARK0_HARD = QColor("#1d2021")
DARK0 = QColor("#282828")
DARK0_SOFT = QColor("#32302f")
DARK1 = QColor("#3c3836")
DARK2 = QColor("#504945")
DARK3 = QColor("#665c54")
DARK4 = QColor("#7c6f64")

GRAY_245 = QColor("#928374")
GRAY_244 = QColor("#928374")

LIGHT0_HARD = QColor("#f9f5d7")
LIGHT0 = QColor("#fbf1c7")
LIGHT0_SOFT = QColor("#f2e5bc")
LIGHT1 = QColor("#ebdbb2")
LIGHT2 = QColor("#d5c4a1")
LIGHT3 = QColor("#bdae93")
LIGHT4 = QColor("#a89984")

BRIGHT_RED = QColor("#fb4934")
BRIGHT_GREEN = QColor("#b8bb26")
BRIGHT_YELLOW = QColor("#fabd2f")
BRIGHT_BLUE = QColor("#83a598")
BRIGHT_PURPLE = QColor("#d3869b")
BRIGHT_AQUA = QColor("#8ec07c")
BRIGHT_ORANGE = QColor("#fe8019")

NEUTRAL_RED = QColor("#cc241d")
NEUTRAL_GREEN = QColor("#98971a")
NEUTRAL_YELLOW = QColor("#d79921")
NEUTRAL_BLUE = QColor("#458588")
NEUTRAL_PURPLE = QColor("#b16286")
NEUTRAL_AQUA = QColor("#689d6a")
NEUTRAL_ORANGE = QColor("#d65d0e")

FADED_RED = QColor("#9d0006")
FADED_GREEN = QColor("#79740e")
FADED_YELLOW = QColor("#b57614")
FADED_BLUE = QColor("#076678")
FADED_PURPLE = QColor("#8f3f71")
FADED_AQUA = QColor("#427b58")
FADED_ORANGE = QColor("#af3a03")

# UI colors
BG = DARK0_HARD
OUTLINE = DARK2
SELECTED_OUTLINE = LIGHT4
TEXT = LIGHT0_HARD
TIME_BG = DARK0_SOFT
RULER = DARK0_SOFT
PLAYHEAD = BRIGHT_RED

SCENE_FONT = None
TIME_FONT = None
RULER_MARKING_FONT = None
def load():
    # Fonts
    scene_font = QFont()
    scene_font.setStyleHint(QFont.SansSerif)
    scene_font.setFamily(scene_font.defaultFamily())
    global SCENE_FONT
    SCENE_FONT = scene_font

    time_font = QFont()
    time_font.setStyleHint(QFont.SansSerif)
    time_font.setFamily(time_font.defaultFamily())
    global TIME_FONT
    TIME_FONT = time_font

    ruler_marking_font = QFont()
    ruler_marking_font.setPixelSize(10)
    ruler_marking_font.setStyleHint(QFont.SansSerif)
    global RULER_MARKING_FONT
    ruler_marking_font.setFamily(ruler_marking_font.defaultFamily())
    RULER_MARKING_FONT = ruler_marking_font
