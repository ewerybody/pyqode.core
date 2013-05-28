#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# PCEF - Python/Qt Code Editing Framework
# Copyright 2013, Colin Duquesnoy <colin.duquesnoy@gmail.com>
#
# This software is released under the LGPLv3 license.
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
""" An easy to use and easy to customise full featured code editor for PySide
applications.

This module contains helper functions for the end user.
"""
import sys
import logging

__version__ = "0.3.0-dev"


def openFileInEditor(editor, filename, encoding=sys.getfilesystemencoding(),
                     replaceTabsBySpaces=True):
    """
    Open a file in an editor

    :param editor: Editor instance where the file content will be displayed

    :param filename: Filename of the file to open

    :param encoding: Encoding to use to load the file

    :param replaceTabsBySpaces: True to replace tabs by spaces
    """
    with open(filename, 'r') as f:
        content = unicode(f.read().decode(encoding))
    if replaceTabsBySpaces:
        content = content.replace("\t", " " * editor.TAB_SIZE)
    editor.codeEdit.tagFilename = filename
    editor.codeEdit.tagEncoding = encoding

    editor.syntaxHighlightingMode.setLexerFromFilename(filename)
    editor.codeEdit.setPlainText(content)
    editor.ui.codeEdit.dirty = False


def saveFileFromEditor(editor, filename=None,
                       encoding=sys.getfilesystemencoding()):
    """
    Save the editor content to a file

    :param editor: Editor instance

    :param filename: The filename to save. If none the editor filename attribute is used.

    :param encoding: The save encoding
    """
    if filename is None:
        filename = editor.codeEdit.tagFilename
    if encoding is None:
        encoding = editor.codeEdit.tagEncoding
    content = unicode(editor.codeEdit.toPlainText()).encode(encoding)
    with open(filename, "w") as f:
        f.write(content)
    editor.codeEdit.updateOriginalText()
    editor.codeEdit.dirty = False
    editor.codeEdit.tagFilename = filename
    editor.codeEdit.tagEncoding = encoding
    editor.codeEdit.textSaved.emit(filename)