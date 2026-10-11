# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeCAD contributors.
"""A colleague's dimension redrawn in place reads what the author's CAD drew.

A grip edit, STRETCH or a property change re-renders a dimension's block
through ezdxf. Three ways that rewrote the author's number, found by
re-rendering every dimension of a corpus sample in place and comparing the
new block with the one the author's CAD wrote:

* an ALIGNED dimension from AutoCAD carries angle 0 (its direction is its
  two origins); ezdxf measured along that angle, so a vertical 2.54 read 0;
* LibreDWG leaves a DIMSTYLE's zeros implicit and ezdxf filled DIMZIN with
  8, so "0.10" read "0.1";
* a negative DIMLFAC applies in paper space only, and model-space
  dimensions read -10.00 for 10;
* a near-vertical dimension at UTM coordinates, rounded to whole units;
* halves rounded to even (".40" for .405), and a DIMPOST suffix without
  "<>" that aborted the edit.
"""
from __future__ import annotations

import ezdxf
import pytest

from core.actions import DimGripCommand
from core.commands import History
from core.document import Document
from formats.dwg_bridge import find_dxf2dwg, load_dwg


def _texts(doc, dim):
    return [e.plain_text() for e in doc.blocks.get(dim.dxf.geometry)
            if e.dxftype() == "MTEXT"]


def _grip_in_place(document, dim):
    p = dim.dxf.defpoint
    History(document).execute(DimGripCommand(dim, "defpoint", (p.x, p.y)))


def test_aligned_dimension_with_angle_zero_keeps_its_length():
    document = Document.new()
    d = document.doc
    d.dimstyles.new("Plain", dxfattribs={"dimdec": 2, "dimdsep": ord(".")})
    dim = document.modelspace().add_aligned_dim(
        p1=(0, 0), p2=(0, 2.54), distance=1, dimstyle="Plain").dimension
    dim.dxf.dimtype = 33             # aligned, as a DWG arrives
    dim.dxf.angle = 0.0              # what AutoCAD writes for an aligned one
    assert abs(dim.get_measurement() - 2.54) < 1e-9
    _grip_in_place(document, dim)
    assert _texts(d, dim) == ["2.54"]


def test_negative_dimlfac_is_ignored_in_model_space():
    document = Document.new()
    d = document.doc
    d.dimstyles.new("Planta", dxfattribs={
        "dimlfac": -1.0, "dimdec": 2, "dimzin": 0, "dimdsep": ord(".")})
    dim = document.modelspace().add_linear_dim(
        base=(0, 2), p1=(0, 0), p2=(10, 0), dimstyle="Planta") \
        .render().dimension
    _grip_in_place(document, dim)
    assert _texts(d, dim) == ["10.00"]


@pytest.mark.skipif(find_dxf2dwg() is None, reason="LibreDWG not available")
def test_dimstyle_zeros_survive_opening_a_dwg(tmp_path):
    doc = ezdxf.new("R2018")
    doc.dimstyles.new("Ceros", dxfattribs={
        "dimzin": 0, "dimdec": 2, "dimtofl": 0, "dimdsep": ord(".")})
    doc.dimstyles.new("Enteros", dxfattribs={
        "dimzin": 0, "dimdec": 0, "dimdsep": ord(".")})
    doc.modelspace().add_linear_dim(
        base=(0, 1), p1=(0, 0), p2=(0.1, 0), dimstyle="Ceros").render()
    doc.modelspace().add_linear_dim(
        base=(0, 5), p1=(0, 4), p2=(9657.3, 4), dimstyle="Enteros").render()
    dwg = tmp_path / "ceros.dwg"
    Document(doc).save_as(dwg)
    back = load_dwg(dwg)
    style = back.doc.dimstyles.get("Ceros")
    assert style.dxf.get("dimzin") == 0 and style.dxf.get("dimtofl") == 0
    tenth, whole = back.modelspace().query("DIMENSION")
    _grip_in_place(back, tenth)
    assert _texts(back.doc, tenth) == ["0.10"]
    _grip_in_place(back, whole)         # DIMDEC 0, not ezdxf's 2
    assert _texts(back.doc, whole) == ["9657"]


def test_near_vertical_dimension_at_utm_keeps_its_length():
    """AutoCAD's "vertical" origins differ by 1e-13 in x; at UTM
    coordinates ezdxf's slope/intercept rays rounded the dimension line to
    whole units and 1.60 read 2.00 (a reservoir plan, handle 829B)."""
    document = Document.new()
    d = document.doc
    d.dimstyles.new("Plain", dxfattribs={"dimdec": 2, "dimzin": 0,
                                         "dimdsep": ord(".")})
    dim = document.modelspace().add_aligned_dim(
        p1=(724674.2678785534, 8325513.635514607),
        p2=(724674.2678785532, 8325512.035514606),
        distance=0.19, dimstyle="Plain").dimension
    dim.dxf.dimtype = 33
    dim.dxf.angle = 0.0
    _grip_in_place(document, dim)
    assert _texts(d, dim) == ["1.60"]


def test_halves_round_up_and_a_bare_dimpost_is_a_suffix():
    from ezdxf.render import dim_base

    document = Document.new()              # applies the patches
    assert dim_base.format_text(0.405, None, 2, 0, ".") == "0.41"
    assert dim_base.format_text(2.625, None, 2, 0, ".") == "2.63"
    assert dim_base.format_text(2.99499999999, None, 2, 0, ".") == "3.00"
    # noise further below the half is the author's own .31
    assert dim_base.format_text(0.3149999999437, None, 2, 0, ".") == "0.31"
    d = document.doc
    d.dimstyles.new("Metros", dxfattribs={"dimdec": 2, "dimzin": 0,
                                          "dimpost": " m", "dimdsep": ord(".")})
    dim = document.modelspace().add_linear_dim(
        base=(0, 2), p1=(0, 0), p2=(2.5, 0), dimstyle="Metros") \
        .render().dimension
    _grip_in_place(document, dim)
    assert _texts(d, dim) == ["2.50 m"]
