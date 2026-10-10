# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeCAD contributors.
"""Linetypes: the standard library, and loading one into a drawing.

How AutoCAD works with linetypes, and what this module mirrors (LINETYPE,
reference p. 1043):

* A drawing can only use the linetypes **loaded into it**. The standard
  definitions live in a library file (``acad.lin``), and the *Load or Reload
  Linetypes* dialog copies the ones you pick into the drawing.
* The Linetype Manager lists what is loaded in three columns -- **Linetype,
  Appearance, Description** -- where Appearance is a drawn sample of the
  pattern, which is how you tell CENTER from PHANTOM at a glance.
* CONTINUOUS, BYLAYER and BYBLOCK are always there and cannot be deleted.
* The dashes are drawing units, scaled on screen by LTSCALE (and by the
  object's own linetype scale).

Where the numbers come from, because inventing them would be worse than
useless: they were **read out of real drawings** -- 120 plans of the corpus,
keeping the definition several of them agree on (the counts are in the
comments below). Two things that harvest settled that memory could not:
a plan's ``HIDDEN2`` of ``[3.175, -1.5875]`` is the imperial pattern in
millimetres, so the file's own numbers are not automatically the standard;
and ezdxf's ``standards.linetypes()``, the obvious source, disagrees with
what every plan carries for several families.
"""
from __future__ import annotations

from typing import Iterable

from core.commands import Command

#: Names every drawing has and no one may load, rename or delete.
RESERVED = ("BYLAYER", "BYBLOCK", "CONTINUOUS")


#: The standard library, as REAL DRAWINGS carry it.
#:
#: Each entry is (description, [dashes]) in drawing units: positive is a
#: dash, negative a gap, 0.0 a dot -- a LIN file's own notation. The counts
#: in the comments are how many of the 120 harvested plans agree on that
#: definition; where a plan carried the same shape in millimetres (0.5 in ->
#: 12.7 mm) the imperial one is kept, which is what ``acad.lin`` defines and
#: what LTSCALE is there to adapt.
#:
#: ⚠️ These are NOT ezdxf's ``standards.linetypes()`` values, which was the
#: obvious source. Its DASHED is [0.5, -0.1] where 47 of 55 plans say
#: [0.5, -0.25], and its CENTERX2 doubles the dashes but not the gaps where
#: 16 of 16 plans double both. When a library and the drawings disagree
#: about what a drawing contains, the drawings win.
STANDARD: dict[str, tuple[str, list[float]]] = {
    "CONTINUOUS": ("Solid line", []),
    # -- the classic families, imperial, as acad.lin defines them ------------
    "BORDER": ("Border __ __ . __ __ . __ __ . __ __ . __ __ .",      # 7/8
               [0.5, -0.25, 0.5, -0.25, 0.0, -0.25]),
    "BORDER2": ("Border (.5x) __.__.__.__.__.__.__.__.__.__.__.",     # 1/1
                [0.25, -0.125, 0.25, -0.125, 0.0, -0.125]),
    "BORDERX2": ("Border (2x) ____  ____  .  ____  ____  .  ___",     # derived
                 [1.0, -0.5, 1.0, -0.5, 0.0, -0.5]),
    "CENTER": ("Center ____ _ ____ _ ____ _ ____ _ ____ _ ____",      # 35/51
               [1.25, -0.25, 0.25, -0.25]),
    "CENTER2": ("Center (.5x) ___ _ ___ _ ___ _ ___ _ ___ _ ___",     # 34/43
                [0.75, -0.125, 0.125, -0.125]),
    "CENTERX2": ("Center (2x) ________  __  ________  __  _____",     # 16/16
                 [2.5, -0.5, 0.5, -0.5]),
    "DASHDOT": ("Dash dot __ . __ . __ . __ . __ . __ . __ . __",     # 21/29
                [0.5, -0.25, 0.0, -0.25]),
    "DASHDOT2": ("Dash dot (.5x) _._._._._._._._._._._._._._._.",     # 14/18
                 [0.25, -0.125, 0.0, -0.125]),
    "DASHDOTX2": ("Dash dot (2x) ____  .  ____  .  ____  .  ___",     # 7/11
                  [1.0, -0.5, 0.0, -0.5]),
    "DASHED": ("Dashed __ __ __ __ __ __ __ __ __ __ __ __ __ _",     # 47/55
               [0.5, -0.25]),
    "DASHED2": ("Dashed (.5x) _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _",     # 80/90
                [0.25, -0.125]),
    "DASHEDX2": ("Dashed (2x) ____  ____  ____  ____  ____  ___",     # 2/2
                 [1.0, -0.5]),
    "DIVIDE": ("Divide ____ . . ____ . . ____ . . ____ . . ____",     # 2/2
               [0.5, -0.25, 0.0, -0.25, 0.0, -0.25]),
    "DIVIDE2": ("Divide (.5x) __..__..__..__..__..__..__..__.._",     # 3/5
                [0.25, -0.125, 0.0, -0.125, 0.0, -0.125]),
    "DIVIDEX2": ("Divide (2x) ________  .  .  ________  .  .  _",     # 3/3
                 [1.0, -0.5, 0.0, -0.5, 0.0, -0.5]),
    "DOT": ("Dot . . . . . . . . . . . . . . . . . . . . . . . .",    # 6/9
            [0.0, -0.25]),
    "DOT2": ("Dot (.5x) ........................................",    # 3/3
             [0.0, -0.125]),
    "DOTX2": ("Dot (2x) .    .    .    .    .    .    .    .   ",     # derived
              [0.0, -0.5]),
    "HIDDEN": ("Hidden __ __ __ __ __ __ __ __ __ __ __ __ __ _",     # 59/73
               [0.25, -0.125]),
    "HIDDEN2": ("Hidden (.5x) _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _",     # derived
                [0.125, -0.0625]),
    "HIDDENX2": ("Hidden (2x) ____ ____ ____ ____ ____ ____ ___",     # 5/5
                 [0.5, -0.25]),
    "PHANTOM": ("Phantom ______  __  __  ______  __  __  ______",     # 28/32
                [1.25, -0.25, 0.25, -0.25, 0.25, -0.25]),
    "PHANTOM2": ("Phantom (.5x) ___ _ _ ___ _ _ ___ _ _ ___ _ _",     # 24/24
                 [0.625, -0.125, 0.125, -0.125, 0.125, -0.125]),
    "PHANTOMX2": ("Phantom (2x) ____________    ____    ____   ",     # derived
                  [2.5, -0.5, 0.5, -0.5, 0.5, -0.5]),
    # -- the ISO family (acadiso.lin), millimetres ---------------------------
    "ACAD_ISO02W100": ("ISO dash __ __ __ __ __ __ __ __ __ __ _",    # 44/44
                       [12.0, -3.0]),
    "ACAD_ISO03W100": ("ISO dash space __    __    __    __    _",    # 23/23
                       [12.0, -18.0]),
    "ACAD_ISO04W100": ("ISO long-dash dot ____ . ____ . ____ . _",    # 17/19
                       [24.0, -3.0, 0.0, -3.0]),
    "ACAD_ISO05W100": ("ISO long-dash double-dot ____ .. ____ ..",    # derived
                       [24.0, -3.0, 0.0, -3.0, 0.0, -3.0]),
    "ACAD_ISO06W100": ("ISO long-dash triple-dot ____ ... ____ .",    # 1 plan
                       [24.0, -3.0, 0.0, -3.0, 0.0, -3.0, 0.0, -3.0]),
    "ACAD_ISO07W100": ("ISO dot . . . . . . . . . . . . . . . . .",   # 7/7
                       [0.0, -3.0]),
    "ACAD_ISO08W100": ("ISO long-dash short-dash ____ __ ____ __",    # derived
                       [24.0, -3.0, 6.0, -3.0]),
    "ACAD_ISO09W100": ("ISO long-dash double-short-dash ____ __ _",   # derived
                       [24.0, -3.0, 6.0, -3.0, 6.0, -3.0]),
    "ACAD_ISO10W100": ("ISO dash dot __ . __ . __ . __ . __ . __",    # 8/10
                       [12.0, -3.0, 0.0, -3.0]),
    "ACAD_ISO11W100": ("ISO double-dash dot __ __ . __ __ . __ _",    # derived
                       [12.0, -3.0, 12.0, -3.0, 0.0, -3.0]),
    "ACAD_ISO12W100": ("ISO dash double-dot __ . . __ . . __ . .",    # 7/9
                       [12.0, -3.0, 0.0, -3.0, 0.0, -3.0]),
    "ACAD_ISO13W100": ("ISO double-dash double-dot __ __ . . __ _",   # derived
                       [12.0, -3.0, 12.0, -3.0, 0.0, -3.0, 0.0, -3.0]),
    "ACAD_ISO14W100": ("ISO dash triple-dot __ . . . __ . . . __",    # 5/6
                       [12.0, -3.0, 0.0, -3.0, 0.0, -3.0, 0.0, -3.0]),
    "ACAD_ISO15W100": ("ISO double-dash triple-dot __ __ . . . _",    # 3/3
                       [12.0, -3.0, 12.0, -3.0,
                        0.0, -3.0, 0.0, -3.0, 0.0, -3.0]),
}

#: The nine marked "derived" are members of a family whose siblings WERE
#: measured, built by the rule the family itself shows: an X2 doubles every
#: number, a 2 halves it, and each ISO name says how many dashes and dots it
#: carries (ISO15, measured, is ISO13 plus a dot). None was written from
#: memory, and none contradicts a plan.


def library() -> dict[str, tuple[str, list[float]]]:
    """{NAME: (description, dashes)} of everything that can be loaded."""
    return STANDARD


def library_names() -> list[str]:
    """The loadable linetypes, CONTINUOUS first then alphabetical -- the
    order the Load dialog shows them in."""
    names = [n for n in library() if n != "CONTINUOUS"]
    names.sort()
    return ["CONTINUOUS"] + names


def parse_lin(text: str) -> dict[str, tuple[str, list[float] | str]]:
    """Read a LIN file: ``{NAME: (description, definition)}``.

    A simple definition is its dash list, as :data:`STANDARD` holds them. A
    complex one -- a line carrying text or shapes in brackets, GAS_LINE's
    ``["GAS",STANDARD,S=2.54,...]`` -- is kept as the LIN pattern line itself
    (``"A,12.7,-5.08,[...],-2.54"``), which is what ezdxf builds it from.
    Comments start with ``;;``; a pattern may continue on the next line after
    a trailing comma, as AutoCAD's own files do for the long ones.
    """
    entries: dict[str, tuple[str, list[float] | str]] = {}
    name = description = None
    pattern = ""
    for raw in text.splitlines():
        line = raw.split(";;", 1)[0].strip()
        if not line:
            continue
        if line.startswith("*"):
            head, _, desc = line[1:].partition(",")
            name, description, pattern = head.strip(), desc.strip(), ""
            continue
        if name is None:
            continue
        pattern += line
        if pattern.endswith(","):
            continue                     # the definition goes on below
        body = pattern
        if body[:2].upper() == "A,":
            body = body[2:]
        if "[" in body:
            entries[name.upper()] = (description, "A," + body)
        else:
            try:
                dashes = [float(v) for v in body.split(",") if v.strip()]
            except ValueError:
                dashes = None            # a line we cannot read: skip it
            if dashes is not None:
                entries[name.upper()] = (description, dashes)
        name, pattern = None, ""
    return entries


def read_lin_file(path) -> dict[str, tuple[str, list[float] | str]]:
    """``parse_lin`` of a file on disk. LIN files from AutoCAD are ANSI
    (cp1252); one that is valid UTF-8 is read as such."""
    from pathlib import Path

    data = Path(path).read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    return parse_lin(text)


def description_of(document, name: str) -> str:
    """What the drawing says this linetype is, or the library's wording."""
    try:
        entry = document.doc.linetypes.get(name)
    except Exception:
        entry = None
    if entry is not None:
        text = entry.dxf.get("description", "") or ""
        if text:
            return text
    found = library().get(name.upper())
    return found[0] if found else ""


def pattern_of(document, name: str) -> list[float]:
    """The dash pattern of a linetype AS THE DRAWING HAS IT.

    ``[]`` means a solid line -- CONTINUOUS, or a definition with no dashes.
    Negative numbers are gaps, positive ones dashes and 0.0 a dot, which is
    exactly how a LIN file writes them.
    """
    try:
        entry = document.doc.linetypes.get(name)
    except Exception:
        found = library().get(name.upper())
        return list(found[1]) if found else []
    try:
        return [tag.value for tag in entry.pattern_tags.tags if tag.code == 49]
    except Exception:
        return []


def ezdxf_pattern(dashes: Iterable[float]) -> list[float]:
    """The library's dash list in the shape ``ezdxf.linetypes.add`` expects.

    A LIN file lists only the dashes; ezdxf wants ``[total_length, dash,
    dash, ...]`` with the pattern length (group 40) in front. Handing it the
    bare dashes swallows the first one as that length -- ACAD_ISO02W100
    ``[12, -3]`` became a lone gap (an invisible line) and ISO04
    ``[24, -3, 0, -3]`` a dotted one -- which is the bug a tester saw as
    "picks an ISO linetype and it loads as something else".
    """
    dashes = [float(d) for d in dashes]
    return [sum(abs(d) for d in dashes)] + dashes


def loaded_names(document) -> list[str]:
    """Linetypes the drawing carries, CONTINUOUS first then alphabetical."""
    names = [lt.dxf.name for lt in document.doc.linetypes
             if lt.dxf.name.upper() not in ("BYLAYER", "BYBLOCK")]
    names.sort(key=lambda n: (n.upper() != "CONTINUOUS", n.lower()))
    return names


def loadable_names(document) -> list[str]:
    """Library linetypes this drawing does NOT have yet."""
    have = {n.upper() for n in loaded_names(document)}
    return [n for n in library_names() if n.upper() not in have]


class LoadLinetypesCommand(Command):
    """Load linetype definitions into the drawing (AutoCAD's Load button).

    ``catalog`` is where the definitions come from: the standard library by
    default, or a LIN file the user picked (``read_lin_file``). Names the
    drawing already has are skipped unless they are listed in ``reload`` --
    AutoCAD's "Linetype X is already loaded. Reload it?" answered Yes --
    which redefines them in place, keeping the entry (and its handle) and
    so every object that uses it.

    Undoable: loading writes LTYPE table entries, which is a change to the
    document like any other; undo removes what was added and puts the old
    definition back on what was reloaded.
    """

    needs_regen = True

    def __init__(self, names: Iterable[str], catalog=None,
                 reload: Iterable[str] = ()) -> None:
        self.names = [n for n in names]
        self.catalog = catalog
        self.reload = {n.upper() for n in reload}
        self.name = "LINETYPE Load"
        self._added: list[str] = []
        self._reloaded: list[tuple] = []

    def _source(self):
        return self.catalog if self.catalog is not None else library()

    def do(self, document) -> None:
        self._added = []
        self._reloaded = []
        table = document.doc.linetypes
        source = self._source()
        for name in self.names:
            found = source.get(name.upper())
            if found is None or name.upper() in RESERVED:
                continue
            description, pattern = found
            if table.has_entry(name):
                if name.upper() not in self.reload:
                    continue
                entry = table.get(name)
                old = (entry, entry.pattern_tags,
                       entry.dxf.get("description", ""))
                try:
                    _setup(entry, pattern, description)
                except Exception:
                    continue
                self._reloaded.append(old)
                continue
            try:
                if isinstance(pattern, str):
                    table.add(name=name, pattern=pattern,
                              description=description)
                else:
                    table.add(name=name, pattern=ezdxf_pattern(pattern),
                              description=description)
            except Exception:
                continue
            self._added.append(name)
        if self._added or self._reloaded:
            document.dirty = True

    def undo(self, document) -> None:
        for entry, tags, description in reversed(self._reloaded):
            entry.pattern_tags = tags      # carries the length (group 40)
            entry.dxf.description = description
        for name in self._added:
            try:
                document.doc.linetypes.remove(name)
            except Exception:
                pass
        if self._added or self._reloaded:
            document.dirty = True


def _setup(entry, pattern, description: str) -> None:
    """Redefine a loaded linetype in place (Reload)."""
    if isinstance(pattern, str):
        # a complex pattern names its text style, resolved through the doc
        entry.setup_pattern(pattern, 0.0)
    else:
        entry.setup_pattern(ezdxf_pattern(pattern))
    entry.dxf.description = description


def is_xref_dependent(name: str) -> bool:
    """``XREF|NAME``: a linetype that came in with an external reference.
    AutoCAD lists them but will not rename or delete them."""
    return "|" in name


def unused_names(document) -> list[str]:
    """Loaded linetypes no object, layer, style or setting uses -- the ones
    the Linetype Manager may Delete. Same answer PURGE gives."""
    from core.cleanup import used_linetypes

    used = used_linetypes(document.doc)
    return [n for n in loaded_names(document)
            if n.upper() not in used and not is_xref_dependent(n)]


class RenameLinetypeCommand(Command):
    """Rename a linetype and every reference to it by name: objects in all
    layouts and blocks, layers, dimension styles and $CELTYPE. AutoCAD
    renames in place in the manager's list; BYLAYER, BYBLOCK, CONTINUOUS and
    xref-dependent linetypes cannot be renamed."""

    name = "LINETYPE Rename"
    needs_regen = True

    def __init__(self, old_name: str, new_name: str) -> None:
        self.old_name = old_name
        self.new_name = new_name
        self._changed: list[tuple] = []

    @staticmethod
    def check(document, old_name: str, new_name: str) -> str | None:
        """Why this rename is refused, or None. Messages are translatable
        keys with ``{name}``."""
        new = new_name.strip()
        if old_name.upper() in RESERVED or is_xref_dependent(old_name):
            return "Linetype {name} cannot be renamed."
        if not new or any(c in new for c in '<>/\\":;?*|,=`'):
            return "Invalid linetype name."
        if new.upper() != old_name.upper() and \
                document.doc.linetypes.has_entry(new):
            return "Linetype {name} already exists."
        return None

    def _rename(self, document, old: str, new: str) -> list[tuple]:
        doc = document.doc
        changed = []
        up = old.upper()
        entry = doc.linetypes.get(old)
        changed.append(("entry", entry, entry.dxf.name))
        # the table is keyed by name: take the entry out under its old key
        doc.linetypes.discard(old)
        entry.dxf.name = new
        doc.linetypes.add_entry(entry)
        for layout in list(doc.layouts) + list(doc.blocks):
            for e in layout:
                if str(e.dxf.get("linetype", "")).upper() == up:
                    changed.append(("attr", e, "linetype", e.dxf.linetype))
                    e.dxf.linetype = new
        for layer in doc.layers:
            if str(layer.dxf.get("linetype", "")).upper() == up:
                changed.append(("attr", layer, "linetype", layer.dxf.linetype))
                layer.dxf.linetype = new
        for style in doc.dimstyles:
            for attr in ("dimltype", "dimltex1", "dimltex2"):
                if str(style.dxf.get(attr, "")).upper() == up:
                    changed.append(("attr", style, attr, style.dxf.get(attr)))
                    style.dxf.set(attr, new)
        if str(doc.header.get("$CELTYPE", "")).upper() == up:
            changed.append(("header", "$CELTYPE", doc.header["$CELTYPE"]))
            doc.header["$CELTYPE"] = new
        return changed

    def do(self, document) -> None:
        self._changed = self._rename(document, self.old_name, self.new_name)
        document.dirty = True

    def undo(self, document) -> None:
        doc = document.doc
        for record in reversed(self._changed):
            if record[0] == "attr":
                _k, obj, attr, value = record
                obj.dxf.set(attr, value)
            elif record[0] == "header":
                doc.header[record[1]] = record[2]
            else:
                _k, entry, name = record
                doc.linetypes.discard(entry.dxf.name)
                entry.dxf.name = name
                doc.linetypes.add_entry(entry)
        document.dirty = True


class LinetypeDescriptionCommand(Command):
    """Edit a linetype's description (the manager's Details > Description)."""

    name = "LINETYPE Description"

    def __init__(self, linetype: str, description: str) -> None:
        self.linetype = linetype
        self.description = description
        self._old = ""

    def do(self, document) -> None:
        entry = document.doc.linetypes.get(self.linetype)
        self._old = entry.dxf.get("description", "")
        entry.dxf.description = self.description
        document.dirty = True

    def undo(self, document) -> None:
        document.doc.linetypes.get(self.linetype).dxf.description = self._old
        document.dirty = True


#: ISO pen widths offered by the manager's Details, in millimetres. An
#: ACAD_ISOnnW100 linetype is defined for a 1.00 mm pen, so the scale it
#: takes is the width itself (reference p. 1046: "Sets the linetype scale
#: to one of a list of standard ISO values").
ISO_PEN_WIDTHS = (0.13, 0.18, 0.25, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0)
