# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeCAD contributors.
"""Undo gives back the whole object, not only its DXF attributes.

A randomized sweep of modify commands over 41 real plans, with a
fingerprint before and after each undo, found what the snapshot (an ezdxf
copy) left out: a dimension's block -- it drew nothing after the undo of
a STRETCH or a property edit --, a POLYLINE's vertices, an INSERT's
attributes, a hatch's pattern lines; and the *D blocks of copied
dimensions that an undo left for Save to write.
"""
from __future__ import annotations

from core import actions, modify
from core.commands import History
from core.document import Document


def _dim(document, y=0.0):
    return document.modelspace().add_linear_dim(
        base=(0, y + 2), p1=(0, y), p2=(10, y)).render().dimension


def _block_texts(document, dim):
    name = dim.dxf.get("geometry", None)
    assert name and name in document.doc.blocks, "the dimension lost its block"
    return [e.text for e in document.doc.blocks.get(name)
            if e.dxftype() == "MTEXT"]


def _dim_blocks(document):
    return {b.name for b in document.doc.blocks if b.name.startswith("*D")}


def test_a_dimension_keeps_its_block_through_stretch_and_property_undo():
    document = Document.new()
    history = History(document)
    dim = _dim(document)
    history.execute(modify.stretch_entities(
        [dim], [(-100, -100, 100, 100)], 5, 0))
    history.undo()
    assert _block_texts(document, dim)
    other = _dim(document, 10)

    def mutate():
        other.dxf.text = "X"
        actions.rerender_dimension(document, other)

    actions.apply_in_place(history, [other], mutate)
    history.undo()
    assert _block_texts(document, other)
    history.redo()
    assert _block_texts(document, other) == ["X"]


def test_a_grip_undo_gives_back_the_authors_own_block():
    """A no-op grip and its undo turned the author's "0.50" into ezdxf's
    "0.5" on every dimension of a colleague's plan."""
    document = Document.new()
    history = History(document)
    dim = _dim(document)
    for e in document.doc.blocks.get(dim.dxf.geometry):
        if e.dxftype() == "MTEXT":
            e.text = "AUTHOR"                  # what the author's CAD drew
    p = dim.dxf.defpoint
    history.execute(actions.DimGripCommand(dim, "defpoint", (p.x, p.y + 3)))
    assert _block_texts(document, dim) != ["AUTHOR"]
    history.undo()
    assert _block_texts(document, dim) == ["AUTHOR"]
    assert dim.dxf.defpoint.y == p.y


def test_polyline_vertices_and_insert_attributes_come_back():
    document = Document.new()
    history = History(document)
    msp = document.modelspace()
    poly = msp.add_polyline2d([(0, 0), (10, 0), (10, 5)])
    history.execute(actions.mirror_entities([poly], (0, 0), (1, 0)))
    history.undo()
    assert [tuple(v.dxf.location)[:2] for v in poly.vertices] \
        == [(0, 0), (10, 0), (10, 5)]
    block = document.doc.blocks.new("TAG")
    block.add_attdef("T", (0, 1))
    insert = msp.add_blockref("TAG", (0, 0))
    insert.add_auto_attribs({"T": "A"})
    history.execute(modify.stretch_entities(
        [insert], [(-1, -1, 1, 1)], 5, 0))
    history.undo()
    assert tuple(insert.attribs[0].dxf.insert)[:2] == (0, 1)


def test_undoing_a_copy_leaves_no_dimension_block_behind():
    document = Document.new()
    history = History(document)
    dim = _dim(document)
    before = _dim_blocks(document)
    history.execute(actions.copy_entities([dim], 50, 50))
    assert len(_dim_blocks(document)) > len(before)
    history.undo()
    assert _dim_blocks(document) == before
