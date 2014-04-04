#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This example is an alternative version of style_and_settings where we modify
the settings and styles after QCodeEdit has been shown.

"""
import sys
from PyQt4 import QtGui
from pyqode.core import api
from pyqode.core import settings
from pyqode.core import style
from pyqode.core.code_edit import QCodeEdit

from pyqode.core.modes import PygmentsSyntaxHighlighter
from pyqode.core.modes import CaretLineHighlighterMode
from pyqode.core.panels import SearchAndReplacePanel


def main():
    app = QtGui.QApplication(sys.argv)
    window = QtGui.QMainWindow()

    # code from the simple example
    editor = QCodeEdit()
    editor.open_file(__file__)
    api.install_mode(editor, CaretLineHighlighterMode())
    api.install_mode(editor, PygmentsSyntaxHighlighter(editor.document()))
    api.install_panel(editor, SearchAndReplacePanel(),
                      position=SearchAndReplacePanel.Position.TOP)
    window.setCentralWidget(editor)
    window.show()

    # make qcodeedit show whitespaces in dark gray
    settings.show_white_spaces = True
    style.whitespaces_foreground = QtGui.QColor('#606020')

    # make a dark editor using the monokai theme
    style.pygments_style = 'monokai'

    # we need to tell QCodeEdit instance to refresh its settings and style
    editor.refresh_settings()
    editor.refresh_style()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()