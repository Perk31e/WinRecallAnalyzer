# no_focus_frame_style.py
from PySide6.QtWidgets import QProxyStyle, QStyleFactory, QStyle

class NoFocusFrameStyle(QProxyStyle):
    def __init__(self):
        super().__init__(QStyleFactory.create('Fusion'))

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_FrameFocusRect:
            return
        super().drawPrimitive(element, option, painter, widget)
