# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeCAD contributors.
"""Opening a dimension style and pressing OK changes nothing.

The editor wrote every field back, rounded to three decimals, plus
defaults the style never had: ISO-25 in a drawing in metres (text 0.0025)
came back with text 0.01 -- four times taller -- and a 3.75 m baseline
spacing (a YouTuber's staircase drawing, reproduced in IngeCAD).
"""
from __future__ import annotations


def test_ok_without_touching_writes_nothing(qapp):
    from views.dimstyle_dialog import DimStyleEditorDialog

    attribs = {"dimtxt": 0.0025, "dimasz": 0.0025, "dimgap": 0.000625,
               "dimexe": 0.00125, "dimexo": 0.000625}
    dlg = DimStyleEditorDialog(None, "t", attribs, ["Standard"])
    assert dlg.changed_props() == {}
    dlg.dimtxt.setValue(0.004)
    assert dlg.changed_props() == {"dimtxt": 0.004}
    assert dlg.dimtxt.text() in ("0.004", "0,004")
    dlg.reject()
