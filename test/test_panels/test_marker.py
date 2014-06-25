from pyqode.core.api import TextHelper
from pyqode.core.qt import QtCore
from pyqode.core.qt.QtTest import QTest
from pyqode.core import panels
from test.helpers import editor_open


def get_panel(editor):
    return editor.panels.get(panels.MarkerPanel)


def test_enabled(editor):
    panel = get_panel(editor)
    assert panel.enabled
    panel.enabled = False
    panel.enabled = True


def test_marker_properties(editor):
    m = panels.Marker(1, icon=':/pyqode-icons/rc/edit-undo.png',
                      description='Marker description')
    assert m.icon == ':/pyqode-icons/rc/edit-undo.png'
    assert m.description == 'Marker description'
    assert m.position == 1


@editor_open(__file__)
def test_add_marker(editor):
    panel = get_panel(editor)
    marker = panels.Marker(1, icon=':/pyqode-icons/rc/edit-undo.png',
                           description='Marker description')
    panel.add_marker(marker)
    QTest.qWait(500)
    assert panel.marker_for_line(1) == marker


@editor_open(__file__)
def test_clear_markers(editor):
    panel = get_panel(editor)
    marker = panels.Marker(
        2, icon=('edit-undo', ':/pyqode-icons/rc/edit-undo.png'),
        description='Marker description')
    panel.add_marker(marker)
    panel.clear_markers()


@editor_open(__file__)
def test_make_marker_icon(editor):
    panel = get_panel(editor)
    # other tests already test icon from tuple or from string
    # we still need to test empty icons -> None
    assert panel.make_marker_icon(None) == (None, None)


@editor_open(__file__)
def test_leave_event(editor):
    panel = get_panel(editor)
    panel.leaveEvent()


@editor_open(__file__)
def test_mouse_press(editor):
    panel = get_panel(editor)
    panel.clear_markers()
    marker = panels.Marker(1, icon=':/pyqode-icons/rc/edit-undo.png',
                           description='Marker description')
    panel.add_marker(marker)
    y_pos = TextHelper(editor).line_pos_from_number(1)
    QTest.mousePress(panel, QtCore.Qt.RightButton, QtCore.Qt.NoModifier,
                     QtCore.QPoint(1000, 1000))
    QTest.mousePress(panel, QtCore.Qt.RightButton, QtCore.Qt.NoModifier,
                     QtCore.QPoint(3, y_pos))


@editor_open(__file__)
def test_mouse_move(editor):
    panel = get_panel(editor)
    panel.clear_markers()
    marker = panels.Marker(1, icon=':/pyqode-icons/rc/edit-undo.png',
                           description='Marker description')
    panel.add_marker(marker)
    y_pos = TextHelper(editor).line_pos_from_number(1)
    QTest.mouseMove(panel, QtCore.QPoint(3, y_pos ))
    QTest.qWait(1000)
    QTest.mouseMove(panel, QtCore.QPoint(1000, 1000))