# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeCAD contributors.
"""MOVE, COPY, STRETCH, ROTATE and SCALE answer the prompts AutoCAD offers.

Typed as the user types them. Found by driving the real window through the
daily commands and comparing with the Command Reference:

* "Specify base point or [Displacement]": D, or Enter, asks for a vector;
  Enter at the second point takes the first point as the displacement --
  "MOVE, 2,3, Enter" moved nothing and ended the command (MOVE, p.1211);
* COPY's later prompt has Exit and Undo; U was "Invalid input.";
* ROTATE and SCALE have [Copy/Reference]; C was "Invalid input.".
"""
from __future__ import annotations

import pytest


@pytest.fixture
def win(qapp):
    from views.main_window import MainWindow

    window = MainWindow()
    window.show()
    window.new_document()
    yield window
    window.document.dirty = False
    window.close()


def _type(win, *texts):
    for text in texts:
        win._on_command_submitted(text)


def _circles(win):
    return sorted((round(c.dxf.center.x, 9), round(c.dxf.center.y, 9),
                   round(c.dxf.radius, 9))
                  for c in win.document.modelspace().query("CIRCLE"))


def test_move_takes_the_first_point_or_a_typed_displacement(win):
    _type(win, "CIRCLE", "0,0", "1")
    _type(win, "MOVE", "L", "", "2,3", "")
    assert _circles(win) == [(2, 3, 1)]
    _type(win, "MOVE", "L", "", "D", "1,1")
    assert _circles(win) == [(3, 4, 1)]
    _type(win, "MOVE", "L", "", "", "-3,-4")      # Enter = <Displacement>
    assert _circles(win) == [(0, 0, 1)]


def test_copy_repeats_with_exit_and_undo(win):
    _type(win, "CIRCLE", "0,0", "1")
    _type(win, "COPY", "L", "", "0,0", "5,0", "10,0", "U", "E")
    assert _circles(win) == [(0, 0, 1), (5, 0, 1)]
    # Last is the copy at 5,0; 0,7 then Enter copies it by (0, 7)
    _type(win, "COPY", "L", "", "0,7", "")
    assert (5, 7, 1) in _circles(win)


def test_rotate_and_scale_can_work_on_a_copy(win):
    _type(win, "CIRCLE", "10,0", "1")
    _type(win, "ROTATE", "L", "", "0,0", "C", "90")
    assert _circles(win) == [(0, 10, 1), (10, 0, 1)]
    _type(win, "SCALE", "L", "", "0,0", "C", "2")
    assert (0, 20, 2) in _circles(win) and len(_circles(win)) == 3


def test_stretch_takes_a_displacement_too(win):
    _type(win, "LINE", "0,0", "10,0", "")
    t = win.tools
    _type(win, "STRETCH")
    t.on_click(12.0, 1.0)                 # crossing over the right end
    t.on_click(8.0, -1.0)
    _type(win, "", "D", "2,0")
    line = win.document.modelspace().query("LINE")[0]
    assert (line.dxf.start.x, line.dxf.end.x) == (0.0, 12.0)


def test_undo_takes_a_count(win):
    """UNDO undid one step at once and the 2 typed next was an unknown
    command (UNDO: "Enter the number of operations to undo <1>")."""
    for x in (0, 5, 10):
        _type(win, "CIRCLE", f"{x},0", "1")
    _type(win, "UNDO", "2")
    assert _circles(win) == [(0, 0, 1)]
    _type(win, "UNDO", "")                 # Enter = 1
    assert _circles(win) == []


def test_text_ends_on_enter_at_an_empty_line(win):
    t = win.tools
    _type(win, "TEXT", "0,5", "1", "0")
    for ch in "ABC":
        t.tool.on_char(ch)
    _type(win, "")                         # next line
    _type(win, "")                         # empty line: the command ends
    assert t.tool is None
    assert [e.dxf.text for e in win.document.modelspace().query("TEXT")] \
        == ["ABC"]


def test_erase_all_takes_layers_that_are_off_and_oops_gives_back(win):
    """ALL: "except those objects on frozen or on locked layers"."""
    _type(win, "-LAYER", "M", "OCULTA", "")
    _type(win, "CIRCLE", "0,0", "1")
    _type(win, "-LAYER", "S", "0", "OFF", "OCULTA", "")
    assert win.document.doc.layers.get("OCULTA").is_off()
    _type(win, "CIRCLE", "5,0", "1")
    _type(win, "ERASE", "ALL", "")
    assert _circles(win) == []
    _type(win, "LINE", "0,0", "1,1", "")   # OOPS works after other commands
    _type(win, "OOPS")
    assert _circles(win) == [(0, 0, 1), (5, 0, 1)]
    assert len(win.document.modelspace().query("LINE")) == 1
