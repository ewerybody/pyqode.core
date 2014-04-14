# -*- coding: utf-8 -*-
"""
This module contains the code completion mode and the related classes.
"""
import re

from PyQt4 import QtGui, QtCore

from pyqode.core import settings
from pyqode.core import frontend
from pyqode.core.frontend.utils import DelayJobRunner, memoized
from pyqode.core import logger
from pyqode.core import backend


class CodeCompletionMode(frontend.Mode, QtCore.QObject):
    """
    This mode provides code completion system wich is extensible. It takes care
    of running the completion request in a background process using one or more
    completion provider(s).

    To implement a code completion for a specific language, you only need to
    implement new :class:`pyqode.core.CompletionProvider`

    The completion popup is shown the user press **ctrl+space** or
    automatically while the user is typing some code (this can be configured
    using a series of properties described in the below table).

    .. note:: The code completion mode automatically starts a unique subprocess
              (:attr:`pyqode.core.CodeCompletionMode.SERVER`)
              to run code completion tasks. This process is automatically
              closed when the application is about to quit. You can use this
              process to run custom task on the completion process (e.g.
              setting up some :py:attr:`sys.modules`).
    """
    @property
    def trigger_key(self):
        return self._trigger_key

    @trigger_key.setter
    def trigger_key(self, value):
        self._trigger_key = value

    @property
    def trigger_length(self):
        return self._trigger_len

    @trigger_length.setter
    def trigger_length(self, value):
        self._trigger_len = value

    @property
    def trigger_symbols(self):
        return self._trigger_symbols

    @trigger_symbols.setter
    def trigger_symbols(self, value):
        self._trigger_symbols = value

    @property
    def show_tooltips(self):
        return self._show_tooltips

    @show_tooltips.setter
    def show_tooltips(self, value):
        self._show_tooltips = value

    @property
    def case_sensitive(self):
        return self._case_sensitive

    @case_sensitive.setter
    def case_sensitive(self, value):
        self._case_sensitive = value

    @property
    def completion_prefix(self):
        """
        Returns the current completion prefix
        """
        prefix = frontend.word_under_cursor(self.editor).selectedText()
        if prefix == "":
            try:
                prefix = frontend.word_under_cursor(
                    self.editor, select_whole_word=True).selectedText()[0]
            except IndexError:
                pass
        return prefix.strip()

    def __init__(self):
        frontend.Mode.__init__(self)
        QtCore.QObject.__init__(self)
        self._current_completion = ""
        # use to display a waiting cursor if completion provider takes too much
        # time
        self._job_runner = DelayJobRunner(self, nb_threads_max=1, delay=1000)
        self._tooltips = {}
        self._cursor_line = -1
        self._cancel_next = False
        self._request_cnt = 0
        self._last_completion_prefix = ""
        self._init_settings()

    def _init_settings(self):
        self._trigger_key = settings.cc_trigger_key
        self._trigger_len = settings.cc_trigger_len
        self._trigger_symbols = settings.cc_trigger_symbols
        self._show_tooltips = settings.cc_show_tooltips
        self._case_sensitive = settings.cc_case_sensitive

    def refresh_settings(self):
        self._init_settings()

    def request_completion(self):
        """
        Requests a code completion at the current cursor position.
        """
        if self._request_cnt:
            return
        # only check first byte
        column = frontend.current_column_nbr(self.editor)
        usd = self.editor.textCursor().block().userData()
        for start, end in usd.cc_disabled_zones:
            if start <= column < end:
                logger.debug(
                    "cc: cancel request, cursor is in a disabled zone")
                return
        self._request_cnt += 1
        self._collect_completions(
            self.editor.toPlainText(), frontend.current_line_nbr(self.editor),
            frontend.current_column_nbr(self.editor), self.editor.file_path,
            self.editor.file_encoding, self.completion_prefix)

    def _on_install(self, editor):
        self._completer = QtGui.QCompleter([""], editor)
        self._completer.setCompletionMode(self._completer.PopupCompletion)
        self._completer.activated.connect(self._insert_completion)
        self._completer.highlighted.connect(
            self._on_selected_completion_changed)
        self._completer.setModel(QtGui.QStandardItemModel())
        frontend.Mode._on_install(self, editor)

    def _on_uninstall(self):
        self._completer = None

    def _on_state_changed(self, state):
        if state:
            self.editor.focused_in.connect(self._on_focus_in)
            self.editor.key_pressed.connect(self._on_key_pressed)
            self.editor.post_key_pressed.connect(self._on_key_released)
            self._completer.highlighted.connect(
                self._display_completion_tooltip)
            self.editor.cursorPositionChanged.connect(
                self._on_cursor_position_changed)
        else:
            self.editor.focused_in.disconnect(self._on_focus_in)
            self.editor.key_pressed.disconnect(self._on_key_pressed)
            self.editor.post_key_pressed.disconnect(self._on_key_released)
            self._completer.highlighted.disconnect(
                self._display_completion_tooltip)
            self.editor.cursorPositionChanged.disconnect(
                self._on_cursor_position_changed)
            self.editor.new_text_set.disconnect(self.requestPreload)

    def _on_focus_in(self, event):
        """
        Resets completer widget

        :param event: QFocusEvents
        """
        self._completer.setWidget(self.editor)

    def _on_results_available(self, status, results):
        logger.debug("cc: got completion results")
        self.editor.set_mouse_cursor(QtCore.Qt.IBeamCursor)
        all_results = []
        if status:
            for res in results:
                all_results += res
        self._request_cnt -= 1
        self._show_completions(all_results)

    def _on_key_pressed(self, event):
        QtGui.QToolTip.hideText()
        is_shortcut = self._is_shortcut(event)
        # handle completer popup events ourselves
        if self._completer.popup().isVisible():
            self._handle_completer_events(event)
            if is_shortcut:
                event.accept()
        if is_shortcut:
            self.request_completion()
            event.accept()

    @staticmethod
    def _is_navigation_key(event):
        return (event.key() == QtCore.Qt.Key_Backspace or
                event.key() == QtCore.Qt.Key_Back or
                event.key() == QtCore.Qt.Key_Delete or
                event.key() == QtCore.Qt.Key_Left or
                event.key() == QtCore.Qt.Key_Right or
                event.key() == QtCore.Qt.Key_Up or
                event.key() == QtCore.Qt.Key_Down or
                event.key() == QtCore.Qt.Key_Space or
                event.key() == QtCore.Qt.Key_End or
                event.key() == QtCore.Qt.Key_Home)

    @staticmethod
    def _is_end_of_word_char(event, is_printable, symbols):
        ret_val = False
        if is_printable and symbols:
            k = event.text()
            seps = settings.word_separators
            ret_val = (k in seps and k not in symbols)
        return ret_val

    def _on_key_released(self, event):
        if self._is_shortcut(event):
            return
        is_printable = self._is_printable_key_event(event)
        is_navigation_key = self._is_navigation_key(event)
        symbols = self._trigger_symbols
        is_end_of_word = self._is_end_of_word_char(
            event, is_printable, symbols)
        if self._completer.popup().isVisible():
            # Update completion prefix
            self._completer.setCompletionPrefix(self.completion_prefix)
            cnt = self._completer.completionCount()
            if (not cnt or (self.completion_prefix == "" and is_navigation_key)
                or is_end_of_word or
                    (int(event.modifiers()) and event.key() ==
                        QtCore.Qt.Key_Backspace)):
                self._hide_popup()
            else:
                self._show_popup()
        # text triggers
        if is_printable:
            if event.text() == " ":
                self._cancel_next = self._request_cnt
            else:
                # trigger symbols
                if symbols:
                    tc = frontend.word_under_cursor(self.editor)
                    tc.setPosition(tc.position())
                    tc.movePosition(tc.StartOfLine, tc.KeepAnchor)
                    text_to_cursor = tc.selectedText()
                    for symbol in symbols:
                        if text_to_cursor.endswith(symbol):
                            logger.debug("cc: symbols trigger")
                            self._hide_popup()
                            self.request_completion()
                            return
                # trigger length
                if not self._completer.popup().isVisible():
                    prefix_len = len(self.completion_prefix)
                    if prefix_len == self._trigger_len:
                        logger.debug("cc: Len trigger")
                        self.request_completion()
                        return
            if self.completion_prefix == "":
                return self._hide_popup()

    def _on_selected_completion_changed(self, completion):
        self._current_completion = completion

    def _on_cursor_position_changed(self):
        cl = frontend.current_line_nbr(self.editor)
        if cl != self._cursor_line:
            self._cursor_line = cl
            self._hide_popup()
            self._job_runner.cancel_requests()
            self._job_runner.stop_job()

    @QtCore.pyqtSlot()
    def _set_wait_cursor(self):
        self.editor.set_mouse_cursor(QtCore.Qt.WaitCursor)

    def _is_last_char_end_of_word(self):
        try:
            tc = frontend.word_under_cursor(self.editor)
            tc.setPosition(tc.position())
            tc.movePosition(tc.StartOfLine, tc.KeepAnchor)
            l = tc.selectedText()
            last_char = l[len(l) - 1]
            if last_char != ' ':
                symbols = self._trigger_symbols
                seps = settings.word_separators
                return last_char in seps and last_char not in symbols
            return False
        except IndexError:
            return False
        except TypeError:
            return False  # no symbols

    def _show_completions(self, completions):
        self._job_runner.cancel_requests()
        # user typed too fast: end of word char has been inserted
        if self._is_last_char_end_of_word():
            return
        # user typed too fast: the user already typed the only suggestion we
        # have
        elif (len(completions) == 1 and
              completions[0]['name'] == self.completion_prefix):
            return
        # a request cancel has been set
        if self._cancel_next:
            self._cancel_next = False
            return
        # we can show the completer
        self._update_model(completions, self._completer.model())
        self._show_popup()
        # self.editor.viewport().setCursor(QtCore.Qt.IBeamCursor)

    def _handle_completer_events(self, event):
        # complete
        if (event.key() == QtCore.Qt.Key_Enter or
                event.key() == QtCore.Qt.Key_Return):
            self._insert_completion(self._current_completion)
            self._hide_popup()
            event.accept()
            return True
        # hide
        elif (event.key() == QtCore.Qt.Key_Escape or
                event.key() == QtCore.Qt.Key_Backtab):
            self._hide_popup()
            event.accept()
            return True
        return False

    def _hide_popup(self):
        # self.editor.viewport().setCursor(QtCore.Qt.IBeamCursor)
        self._completer.popup().hide()
        self._job_runner.cancel_requests()
        QtGui.QToolTip.hideText()

    def _show_popup(self):
        cnt = self._completer.completionCount()
        full_prefix = frontend.word_under_cursor(
            self.editor, select_whole_word=True).selectedText()
        if (full_prefix == self._current_completion) and cnt == 1:
            self._hide_popup()
        else:
            if self._case_sensitive:
                self._completer.setCaseSensitivity(QtCore.Qt.CaseSensitive)
            else:
                self._completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            # set prefix
            self._completer.setCompletionPrefix(self.completion_prefix)
            # compute size and pos
            cr = self.editor.cursorRect()
            char_width = self.editor.fontMetrics().width('A')
            prefix_len = (len(self.completion_prefix) * char_width)
            cr.translate(self.editor.margin_size() - prefix_len,
                         self.editor.margin_size(0))
            w = self._completer.popup().verticalScrollBar().sizeHint().width()
            cr.setWidth(self._completer.popup().sizeHintForColumn(0) + w)
            # show the completion list
            self._completer.complete(cr)
            self._completer.popup().setCurrentIndex(
                self._completer.completionModel().index(0, 0))

    def _insert_completion(self, completion):
        tc = frontend.word_under_cursor(self.editor, select_whole_word=True)
        tc.insertText(completion)
        self.editor.setTextCursor(tc)

    def _is_shortcut(self, event):
        """
        Checks if the event's key and modifiers make the completion shortcut
        (Ctrl+Space)

        :param event: QKeyEvent

        :return: bool
        """
        val = int(event.modifiers() & QtCore.Qt.ControlModifier)
        return val and event.key() == self._trigger_key

    @staticmethod
    def strip_control_characters(input):
        if input:
            # unicode invalid characters
            re_illegal = \
                '([\u0000-\u0008\u000b-\u000c\u000e-\u001f\ufffe-\uffff])' + \
                '|' + \
                '([%s-%s][^%s-%s])|([^%s-%s][%s-%s])|([%s-%s]$)|(^[%s-%s])' % \
                (chr(0xd800), chr(0xdbff), chr(0xdc00), chr(0xdfff),
                 chr(0xd800), chr(0xdbff), chr(0xdc00), chr(0xdfff),
                 chr(0xd800), chr(0xdbff), chr(0xdc00), chr(0xdfff))
            input = re.sub(re_illegal, "", input)
            # ascii control characters
            input = re.sub(r"[\x01-\x1F\x7F]", "", input)
        return input

    @staticmethod
    def _is_printable_key_event(event):
        return len(CodeCompletionMode.strip_control_characters(
            event.text())) == 1

    @staticmethod
    @memoized
    def _make_icon(icon):
        return QtGui.QIcon(icon)

    def _update_model(self, completions, cc_model):
        """
        Creates a QStandardModel that holds the suggestion from the completion
        models for the QCompleter

        :param completionPrefix:
        """
        # build the completion model
        cc_model.clear()
        displayed_texts = []
        self._tooltips.clear()
        for completion in completions:
            name = completion['name']
            if not name:
                continue
            # skip redundant completion
            if name != self.completion_prefix and name not in displayed_texts:
                displayed_texts.append(name)
                item = QtGui.QStandardItem()
                item.setData(name, QtCore.Qt.DisplayRole)
                if 'tooltip' in completion and completion['tooltip']:
                    self._tooltips[name] = completion['tooltip']
                if 'icon' in completion:
                    item.setData(self._make_icon(completion['icon']),
                                 QtCore.Qt.DecorationRole)
                cc_model.appendRow(item)
        return cc_model

    def _display_completion_tooltip(self, completion):
        if not self._show_tooltips:
            return
        if completion not in self._tooltips:
            QtGui.QToolTip.hideText()
            return
        if completion in self._tooltips:
            tooltip = self._tooltips[completion].strip()
        else:
            tooltip = None
        if tooltip:
            pos = self._completer.popup().pos()
            pos.setX(pos.x() + self._completer.popup().size().width())
            pos.setY(pos.y() - 15)
            QtGui.QToolTip.showText(pos, tooltip, self.editor)
        else:
            QtGui.QToolTip.hideText()

    def _collect_completions(self, code, line, column, path, encoding,
                             completion_prefix):
        logger.debug("cc: completion requested")
        data = {'code': code, 'line': line, 'column': column,
                'path': path, 'encoding': encoding,
                'prefix': completion_prefix}
        try:
            frontend.request_work(self.editor,
                                  backend.CodeCompletionWorker, args=data,
                                  on_receive=self._on_results_available)
        except frontend.NotConnectedError:
            pass
        else:
            self._set_wait_cursor()
