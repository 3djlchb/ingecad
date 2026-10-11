# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeCAD contributors.
"""A release's hands-on test, run by the machine the way a user works.

    DISPLAY=:0 QT_QPA_PLATFORM=xcb venv/bin/python tools/qa_tour.py OUT_DIR [scenario ...]

The real IngeCAD window opens and every scenario drives it through the
user's own doors: commands typed on the command line, the mouse moved and
clicked over the canvas (real Qt events, snaps answering the cursor),
dialogs pressed. Each step leaves a capture of the window -- canvas
composited from its framebuffer, since ``win.grab()`` draws the GL widget
without its overlay -- and the checks it made. ``OUT_DIR/report.json``
lists them for a report page.

A scenario is a function ``scenario_<name>(tour)`` below; run them all, or
name the ones wanted.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


class Tour:
    def __init__(self, app, out: Path) -> None:
        self.app = app
        self.out = out
        self.steps: list[dict] = []
        self.scenario = ""
        self.windows: list = []
        self.win = None

    # -- windows -----------------------------------------------------------------
    def new_window(self, size=(1500, 950)):
        from views.main_window import MainWindow

        win = MainWindow()
        win.maybe_save_changes = lambda: True
        win.resize(*size)
        win.show()
        win.new_document()
        self.windows.append(win)
        self.win = win
        self.focus(win)
        self.wait(200)
        return win

    def focus(self, win) -> None:
        from PySide6.QtTest import QTest

        win.activateWindow()
        win.raise_()
        QTest.qWaitForWindowActive(win, 3000)
        self.win = win

    def close_all(self) -> None:
        for win in self.windows:
            try:
                for s in win.document_sessions():
                    s.document.dirty = False
                win.close()
            except RuntimeError:
                pass
        self.windows = []
        self.wait(100)

    # -- time ---------------------------------------------------------------------
    def wait(self, ms: int = 50) -> None:
        end = time.monotonic() + ms / 1000
        while time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.005)

    def settle(self, timeout: float = 60) -> None:
        win = self.win
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            busy = (win._open_thread is not None or win._regen_worker is not None
                    or bool(win.tools._warmers))
            self.app.processEvents()
            if not busy:
                break
            time.sleep(0.01)
        self.wait(120)

    # -- the user's hands --------------------------------------------------------
    def type(self, text: str) -> None:
        """Type on the command line and press Enter."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        edit = self.win.command_line.input
        edit.setFocus()
        if text:
            QTest.keyClicks(edit, text)
        QTest.keyClick(edit, Qt.Key_Return)
        self.wait(60)

    def keys(self, sequence: str) -> None:
        from PySide6.QtGui import QKeySequence
        from PySide6.QtTest import QTest

        self.win.viewport.setFocus()
        QTest.keySequence(self.win.viewport, QKeySequence(sequence))
        self.wait(60)

    def esc(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        QTest.keyClick(self.win.viewport, Qt.Key_Escape)
        self.wait(40)

    def _pos(self, wx, wy):
        from PySide6.QtCore import QPoint

        sx, sy = self.win.viewport.view.world_to_screen(wx, wy)
        return QPoint(int(round(sx)), int(round(sy)))

    def move(self, wx: float, wy: float) -> None:
        """A mouse move delivered to the canvas itself. QTest.mouseMove
        warps the real X pointer, and the move went to whatever window lay
        over that spot of the user's screen (a terminal, another program)."""
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QApplication

        vp = self.win.viewport
        local = QPointF(self._pos(wx, wy))
        event = QMouseEvent(QEvent.MouseMove, local, QPointF(vp.mapToGlobal(local)),
                            Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        QApplication.sendEvent(vp, event)
        self.wait(40)

    def click(self, wx: float, wy: float, *, shift=False) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        self.move(wx, wy)
        mods = Qt.ShiftModifier if shift else Qt.NoModifier
        QTest.mouseClick(self.win.viewport, Qt.LeftButton, mods, self._pos(wx, wy))
        self.wait(60)

    def drag(self, a, b) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        vp = self.win.viewport
        QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, self._pos(*a))
        for k in range(1, 9):
            x = a[0] + (b[0] - a[0]) * k / 8
            y = a[1] + (b[1] - a[1]) * k / 8
            from PySide6.QtCore import QEvent, QPointF
            from PySide6.QtGui import QMouseEvent
            from PySide6.QtWidgets import QApplication

            local = QPointF(self._pos(x, y))
            QApplication.sendEvent(vp, QMouseEvent(
                QEvent.MouseMove, local, QPointF(vp.mapToGlobal(local)),
                Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
            self.wait(15)
        QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, self._pos(*b))
        self.wait(80)

    def snaps(self, *kinds) -> None:
        t = self.win.tools
        t.osnap_on = bool(kinds)
        t.osnap_modes = set(kinds)

    def frame(self, x0, y0, x1, y1) -> None:
        vp = self.win.viewport
        vp.view.zoom_extents(x0, y0, x1, y1, margin=0.08)
        vp.update()
        self.wait(80)

    def open(self, path) -> None:
        self.win.open_path(Path(path))
        self.settle()

    def last_lines(self, n=4) -> list[str]:
        return self.win.command_line.history.toPlainText().splitlines()[-n:]

    # -- record ---------------------------------------------------------------------
    def shot(self, name: str, caption: str, widget=None) -> str:
        """Capture the window (canvas from its framebuffer, overlay included)
        or ``widget`` (a dialog)."""
        from PySide6.QtGui import QPainter

        self.wait(120)
        fname = f"{len(self.steps) + 1:03d}-{self.scenario}-{name}.png"
        path = self.out / fname
        if widget is not None:
            image = widget.grab().toImage()
        else:
            win = self.win
            vp = win.viewport
            vp.grabFramebuffer()
            canvas = vp.grabFramebuffer()        # the first may miss the grid
            image = win.grab().toImage()
            image.setDevicePixelRatio(1.0)       # paint in the image's pixels
            scale = image.width() / max(1, win.width())
            top_left = vp.mapTo(win, vp.rect().topLeft())
            from PySide6.QtCore import QRect

            target = QRect(round(top_left.x() * scale), round(top_left.y() * scale),
                           round(vp.width() * scale), round(vp.height() * scale))
            canvas.setDevicePixelRatio(1.0)
            painter = QPainter(image)
            painter.drawImage(target, canvas)
            painter.end()
        image.save(str(path))
        self.steps.append({"scenario": self.scenario, "kind": "shot",
                           "file": fname, "caption": caption})
        return fname

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        self.steps.append({"scenario": self.scenario, "kind": "check",
                           "ok": bool(ok), "label": label, "detail": str(detail)})
        print(("  ok   " if ok else "  FAIL ") + label + (f" -- {detail}" if detail else ""),
              flush=True)
        return ok

    def note(self, text: str) -> None:
        self.steps.append({"scenario": self.scenario, "kind": "note", "text": text})

    def save(self) -> None:
        (self.out / "report.json").write_text(
            json.dumps(self.steps, ensure_ascii=False, indent=1), encoding="utf-8")
        (self.out / "index.html").write_text(self.html(), encoding="utf-8")

    def html(self) -> str:
        """A page to read the tour: per scenario its checks and captures."""
        import html as h

        checks = [s for s in self.steps if s["kind"] == "check"]
        failed = sum(1 for s in checks if not s["ok"])
        out = ["<!doctype html><meta charset=utf-8><title>Recorrido IngeCAD</title>",
               "<style>body{font:15px system-ui;background:#1e1e22;color:#ddd;"
               "max-width:1100px;margin:auto;padding:16px}img{width:100%;"
               "border:1px solid #444;margin:6px 0 18px}h2{color:#8fd16a;"
               "border-top:1px solid #444;padding-top:18px}.ok{color:#8fd16a}"
               ".fail{color:#ff6b6b;font-weight:bold}.cap{color:#aaa}"
               "pre{white-space:pre-wrap;color:#aaa;font-size:12px}</style>",
               f"<h1>Recorrido de prueba</h1><p>{len(checks)} comprobaciones, "
               f"<span class={'fail' if failed else 'ok'}>{failed} fallidas</span></p>"]
        for s in self.steps:
            if s["kind"] == "title":
                out.append(f"<h2>{h.escape(s['scenario'])}</h2><p>{h.escape(s['text'])}</p>")
            elif s["kind"] == "check":
                cls, mark = ("ok", "✔") if s["ok"] else ("fail", "✘")
                out.append(f"<div class={cls}>{mark} {h.escape(s['label'])}</div>")
                if s["detail"] and not s["ok"]:
                    out.append(f"<pre>{h.escape(s['detail'])}</pre>")
            elif s["kind"] == "shot":
                out.append(f"<p class=cap>{h.escape(s['caption'])}</p>"
                           f"<img src='{h.escape(s['file'])}' loading=lazy>")
            elif s["kind"] == "note":
                out.append(f"<p>{h.escape(s['text'])}</p>")
        return "\n".join(out)


def run(names: list[str], out: Path) -> int:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication

    # a profile of its own: the user's settings stay untouched
    QCoreApplication.setOrganizationName("IngeCAD-QA")
    QCoreApplication.setApplicationName("IngeCAD-QA")
    app = QApplication.instance() or QApplication(sys.argv[:1])
    from core import i18n

    try:
        i18n.set_language("es")
    except Exception:  # noqa: BLE001
        pass
    import qa_scenarios as scenarios

    out.mkdir(parents=True, exist_ok=True)
    tour = Tour(app, out)
    available = [n[len("scenario_"):] for n in dir(scenarios) if n.startswith("scenario_")]
    chosen = names or sorted(available, key=lambda n: getattr(scenarios, "scenario_" + n).__code__.co_firstlineno)
    failures = 0
    for name in chosen:
        tour.scenario = name
        print(f"== {name}", flush=True)
        func = getattr(scenarios, "scenario_" + name)
        tour.steps.append({"scenario": name, "kind": "title",
                           "text": (func.__doc__ or name).strip()})
        try:
            func(tour)
        except Exception:  # noqa: BLE001 -- a broken scenario is a failed check
            tour.check(False, "the scenario raised", traceback.format_exc()[-1500:])
        finally:
            try:
                if tour.windows:
                    tour.shot("end", "Estado al terminar")
            except Exception:  # noqa: BLE001
                pass
            tour.close_all()
            tour.save()
    failures = sum(1 for s in tour.steps if s["kind"] == "check" and not s["ok"])
    print(f"DONE: {sum(1 for s in tour.steps if s['kind'] == 'check')} checks, "
          f"{failures} failed", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(run(sys.argv[2:], Path(sys.argv[1])))
