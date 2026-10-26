# -*- coding: utf-8 -*-
"""Reusable controls for the wake physics of the Energy dialog (#46 P1d; used by the new group of P5 and by #64).

- ``CollapsibleSection``: a header button with an arrow and a body, folded by default.
- ``ParamEditor``: one control per editable argument, by the kind of its default value (decision 4): a field for a
  number, one field per component for a list, a True/False drop-down for a boolean, a drop-down with the two
  functions for ``ct2a``. A number is read exactly as typed (a comma is taken as the decimal point): never rounded
  to a number of decimals, never clipped to a range. An unreadable field is reported, not replaced.
- ``fill_option_combo``: the options of a selector, each with its help and, when no other choice can make it
  calculable, disabled with its reason (P0, section 6). The data of an option is never ``None`` (an absence is a
  value of its own, such as ``""``), so a choice is always told from no choice.
- ``SubordinateEditor`` and ``ComponentWindow`` (#64): the arguments of a subordinate object of PyWake, by the kinds
  of ``ag_core.wake_setup.subordinates``, and the small window of a nested ground model (with, under «Heredar», the
  sum it inherits: ``INHERIT_WAKES``, ``INHERIT_BLOCKAGE``).

Apart from the table of ``subordinates`` (and the signatures it completes with), nothing here knows PyWake or the
catalogue beyond the values it is given; it builds widgets and reads them back.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from qgis.PyQt import QtCore, QtGui, QtWidgets

from .dialog_keys import enter_reaches_default

__all__ = ["CollapsibleSection", "ParamEditor", "SubordinateEditor", "ComponentWindow", "fill_option_combo", "format_number",
           "parse_number", "CT2A_FUNCTIONS", "READ_ONLY_STYLE"]

CT2A_FUNCTIONS = ("ct2a_madsen", "ct2a_mom1d")
# Values that are read, not edited (a predefined model): as text in the colour of the text, in a frame like that of a
# selector, without the arrow of a menu (the user's tests in QGIS: greyed out, they looked blocked and were hard to
# read; without a frame, they did not look like values).
READ_ONLY_STYLE = ("QComboBox:disabled, QLineEdit[readOnly=\"true\"], QAbstractSpinBox[readOnly=\"true\"] "
                   "{ color: palette(text); background: transparent; border: 1px solid palette(mid); "
                   "border-radius: 3px; padding: 1px 4px; } "
                   "QComboBox::drop-down:disabled { width: 0px; border: none; } "
                   "QComboBox::down-arrow:disabled { image: none; }")


def _identity(text: str) -> str:
    return text


def format_number(value: Any) -> str:
    """The text of a number, with all its digits (``repr``); an integer stays an integer."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    return repr(float(value))


def parse_number(text: str, integer: bool = False) -> Any:
    """The number typed, exactly; ``ValueError`` if it is not one (or not finite). A comma is the decimal point.

    With ``integer`` (the default value was an integer), a text without a decimal point gives an ``int``; one with
    decimals gives the ``float`` typed: an integer in a signature does not make PyWake refuse a fraction (e.g. ``B``
    of ``ZongGaussianDeficit`` is a factor of an expression, ``gaussian.py:342``), and nothing is rounded.
    """
    t = (text or "").strip().replace(",", ".")
    if not t:
        raise ValueError("vacío")
    value = float(t)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("no finito")
    if integer and "." not in t and "e" not in t.lower():
        return int(t)
    return value


class CollapsibleSection(QtWidgets.QWidget):
    """A section with a header («▸ title», «▾ title») that shows or hides its body; folded by default."""

    toggled = QtCore.pyqtSignal(bool)

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None, expanded: bool = False):
        super().__init__(parent)
        self.header = QtWidgets.QToolButton(self)
        self.header.setText(title)
        self.header.setCheckable(True)
        self.header.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.header.setAutoRaise(True)
        self.body = QtWidgets.QWidget(self)
        self.body_layout = QtWidgets.QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(16, 0, 0, 0)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.header)
        lay.addWidget(self.body)
        self.header.toggled.connect(self._apply)
        self.setExpanded(expanded)
        self._apply(expanded)

    def _apply(self, expanded: bool) -> None:
        self.header.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)
        self.body.setVisible(expanded)
        self.toggled.emit(bool(expanded))

    def setExpanded(self, expanded: bool) -> None:
        self.header.setChecked(bool(expanded))
        self._apply(bool(expanded))

    def isExpanded(self) -> bool:
        return self.header.isChecked()


class ParamEditor(QtWidgets.QWidget):
    """Controls for a set of editable arguments (see the module docstring).

    ``specs`` is an ordered list of ``(name, default)``; ``helps`` the help of each argument (already translated).
    ``values()`` gives the arguments as plain values and ``errors()`` the names of the fields that cannot be read.
    """

    changed = QtCore.pyqtSignal()

    _INVALID = "border: 1px solid #c0392b;"

    def __init__(self, specs: Sequence[Tuple[str, Any]], helps: Optional[Mapping[str, str]] = None,
                 parent: Optional[QtWidgets.QWidget] = None, tr: Callable[[str], str] = _identity):
        super().__init__(parent)
        self._specs = list(specs)
        self._controls: Dict[str, Any] = {}
        self._tr = tr
        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        for name, default in self._specs:
            control = self._make(name, default)
            help_text = (helps or {}).get(name, "")
            label = QtWidgets.QLabel(name)
            for w in (label,) + tuple(self._widgets(control)):
                w.setToolTip(help_text)
            form.addRow(label, control if isinstance(control, QtWidgets.QWidget) else control[0])
            self._controls[name] = control
        # Every control starts with the value of the signature it is given.
        self.set_values({name: getattr(d, "__name__", d) if callable(d) else d for name, d in self._specs})

    def retranslate(self, helps: Mapping[str, str]) -> None:
        for i, (name, _default) in enumerate(self._specs):
            label = self.layout().itemAt(i, QtWidgets.QFormLayout.LabelRole).widget()
            for widget in (label,) + tuple(self._widgets(self._controls[name])):
                widget.setToolTip(helps.get(name, ""))

    # --- construction -----------------------------------------------------------------------------------------
    def _make(self, name: str, default: Any):
        if isinstance(default, bool):
            combo = QtWidgets.QComboBox(self)
            combo.addItem("True", True)
            combo.addItem("False", False)
            combo.currentIndexChanged.connect(self.changed.emit)
            return combo
        if callable(default) or (isinstance(default, str) and default in CT2A_FUNCTIONS):
            combo = QtWidgets.QComboBox(self)
            for fn in CT2A_FUNCTIONS:
                combo.addItem(fn, fn)
            combo.currentIndexChanged.connect(self.changed.emit)
            return combo
        if isinstance(default, (list, tuple)):
            box = QtWidgets.QWidget(self)
            row = QtWidgets.QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            edits = []
            for i, _ in enumerate(default):
                edit = QtWidgets.QLineEdit(box)
                edit.setObjectName(f"{name}_{i + 1}")
                edit.textChanged.connect(self._on_text)
                row.addWidget(edit)
                edits.append(edit)
            return (box, edits)
        edit = QtWidgets.QLineEdit(self)
        edit.setObjectName(name)
        edit.textChanged.connect(self._on_text)
        return edit

    @staticmethod
    def _widgets(control) -> Iterable[QtWidgets.QWidget]:
        if isinstance(control, tuple):
            return (control[0],) + tuple(control[1])
        return (control,)

    def _on_text(self, *_: Any) -> None:
        self._mark()
        self.changed.emit()

    # --- reading and writing ----------------------------------------------------------------------------------
    def set_values(self, values: Mapping[str, Any]) -> None:
        """Show ``values`` (plain values: a ``ct2a`` by its name) without emitting ``changed`` per field."""
        self.blockSignals(True)
        try:
            for name, default in self._specs:
                if name not in values:
                    continue
                v, c = values[name], self._controls[name]
                if isinstance(c, QtWidgets.QComboBox):
                    i = c.findData(getattr(v, "__name__", v))
                    c.setCurrentIndex(i)
                elif isinstance(c, tuple):
                    if len(v) != len(c[1]):
                        raise ValueError(f"{name}: {len(c[1])} componentes, no {len(v)}: {v!r}")
                    for edit, x in zip(c[1], v):
                        edit.setText(format_number(x))
                else:
                    c.setText(format_number(v))
        finally:
            self.blockSignals(False)
        self._mark()
        self.changed.emit()

    def _read(self, name: str, default: Any) -> Any:
        c = self._controls[name]
        if isinstance(c, QtWidgets.QComboBox):
            if c.currentIndex() < 0:
                raise ValueError("sin elección")
            return c.currentData()
        if isinstance(c, tuple):
            return [parse_number(e.text(), integer=isinstance(d, int) and not isinstance(d, bool))
                    for e, d in zip(c[1], default)]
        return parse_number(c.text(), integer=isinstance(default, int) and not isinstance(default, bool))

    def values(self) -> Dict[str, Any]:
        """The arguments that can be read (see ``errors`` for the others)."""
        out: Dict[str, Any] = {}
        for name, default in self._specs:
            try:
                out[name] = self._read(name, default)
            except ValueError:
                continue
        return out

    def errors(self) -> List[str]:
        """The arguments whose field cannot be read as a value."""
        out = []
        for name, default in self._specs:
            try:
                self._read(name, default)
            except ValueError:
                out.append(name)
        return out

    def _mark(self) -> None:
        for name, default in self._specs:
            c = self._controls[name]
            edits = c[1] if isinstance(c, tuple) else ([c] if isinstance(c, QtWidgets.QLineEdit) else [])
            for i, e in enumerate(edits):
                d = default[i] if isinstance(c, tuple) else default
                try:
                    parse_number(e.text(), integer=isinstance(d, int) and not isinstance(d, bool))
                    e.setStyleSheet("")
                except ValueError:
                    e.setStyleSheet(self._INVALID)

    def set_read_only(self, read_only: bool) -> None:
        """Informative mode (the values are shown, not edited)."""
        for c in self._controls.values():
            for w in self._widgets(c):
                if isinstance(w, QtWidgets.QLineEdit):
                    w.setReadOnly(read_only)
                elif isinstance(w, QtWidgets.QComboBox):
                    w.setEnabled(not read_only)

    def control(self, name: str):
        """The widget (or ``(box, fields)`` for a list) of an argument, for the dialog and the tests."""
        return self._controls[name]


def fill_option_combo(combo: QtWidgets.QComboBox, options: Sequence[Tuple[Any, str, str, Optional[str]]]) -> None:
    """Fill ``combo`` with ``(data, label, help, disabled_reason)`` items, keeping the current choice if it is there.

    A disabled item shows its reason in its help; it stays selectable programmatically, so a choice made before
    (e.g. under another engine) is kept, never changed by this function.
    """
    if any(o[0] is None for o in options):
        raise ValueError("Una opción del desplegable no puede tener None como dato.")
    current = combo.currentData() if combo.currentIndex() >= 0 else None
    combo.blockSignals(True)
    try:
        combo.clear()
        model = combo.model()
        for i, (data, label, help_text, reason) in enumerate(options):
            combo.addItem(label, data)
            tip = help_text if not reason else f"{help_text}\n{reason}".strip()
            combo.setItemData(i, tip, QtCore.Qt.ToolTipRole)
            if reason and isinstance(model, QtGui.QStandardItemModel):
                model.item(i).setEnabled(False)
        if current is not None:
            i = combo.findData(current)
            if i >= 0:
                combo.setCurrentIndex(i)
    finally:
        combo.blockSignals(False)




class _IntSpin(QtWidgets.QSpinBox):
    """An integer with arrows that lets a value below its minimum be typed (a minus sign with a minimum of 0 or more, or
    −5 with a minimum of −2), so that it is corrected in view to the minimum when leaving the field
    (CorrectToNearestValue), not read without its sign nor left as it was."""

    def validate(self, text: str, pos: int):
        t = text.strip()
        if t.startswith("-") and self.minimum() >= 0:
            return QtGui.QValidator.Intermediate, text, pos
        try:
            if int(t) < self.minimum():
                return QtGui.QValidator.Intermediate, text, pos
        except ValueError:
            pass
        return super().validate(text, pos)

    def fixup(self, text: str) -> str:
        try:
            if int(text.strip()) < self.minimum():
                return str(self.minimum())
        except ValueError:
            pass
        return super().fixup(text)


class SubordinateEditor(QtWidgets.QWidget):
    """The arguments of a subordinate object of PyWake (#64; ``subordinates.ARGS``), one control each by its kind: a
    number, a list of fixed length, True/False, ``ct2a``, a value of a closed set, an integer (with arrows: a value
    below ``minimum`` is corrected to it, in view), a number or ``None`` (a selector and a field), or another PyWake
    class (a selector of the options of its family, with its own arguments in the same line or, for a ground model,
    in a small window opened with a button and summarised next to it; decision 1 of #64).

    ``component`` is the ``Component`` to show (completed); ``value()`` gives it back with what can be read and
    ``errors()`` the routes of the fields that cannot. ``helps(owner, arg)`` and ``option_help(arg, option)`` give
    the helps, translated; ``tr`` translates the texts of the controls; ``inherited`` is the class an inheriting sum
    takes (for its window). Each nested argument remembers the values of every option chosen in it.
    """

    changed = QtCore.pyqtSignal()

    def __init__(self, component: Any, parent: Optional[QtWidgets.QWidget] = None,
                 tr: Callable[[str], str] = _identity, helps: Optional[Callable[[str, str], str]] = None,
                 option_help: Optional[Callable[[Any, Any], str]] = None, skip: Sequence[str] = (),
                 minimum: Optional[Mapping[Tuple[str, str], int]] = None, path: str = "", inline: bool = False,
                 inherited: Optional[str] = None):
        super().__init__(parent)
        from ..ag_core.wake_setup import subordinates as sub
        self._sub = sub
        self._tr = tr
        self._helps = helps or (lambda owner, arg: "")
        self._option_help = option_help or (lambda arg, option: "")
        self._minimum = dict(minimum or {})
        self._path = path
        self.inherited = inherited
        self.name = component.name
        self._args = [a for a in sub.args_of(component.name) if a.name not in skip]
        self._controls: Dict[str, Any] = {}
        self._nested: Dict[str, Dict[str, Any]] = {}
        self._window_conflicts: Dict[str, List[str]] = {}
        self._window_notes: Dict[str, List[str]] = {}
        self._read_only = False
        # ``window_messages(arg, component)``: what the window of ``arg`` says for what is edited in it (the owner of
        # the editor knows the rest of the configuration); ``None``, what ``mark_window`` gave.
        self.window_messages: Optional[Callable[[str, Any], Any]] = None
        layout = QtWidgets.QHBoxLayout(self) if inline else QtWidgets.QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for a in self._args:
            widget = self._make(a, component.params.get(a.name))
            label = QtWidgets.QLabel(a.name, self)
            tip = self._helps(component.name, a.name)
            for w in (label, widget):
                w.setToolTip(tip)
            if inline:
                layout.addWidget(label)
                layout.addWidget(widget)
            else:
                layout.addRow(label, widget)
        self._mark()

    def retranslate(self) -> None:
        for a in self._args:
            control = self._controls[a.name]
            widget = (self._nested[a.name]["box"] if a.kind == self._sub.COMPONENT else
                      control[0] if isinstance(control, tuple) else control)
            tip = self._helps(self.name, a.name)
            widget.setToolTip(tip)
            for label in self.findChildren(QtWidgets.QLabel, options=QtCore.Qt.FindDirectChildrenOnly):
                if label.text() == a.name:
                    label.setToolTip(tip)
            if a.kind == self._sub.NUMBER_OR_NONE:
                mode = control[1]
                blocker = QtCore.QSignalBlocker(mode)
                mode.setItemText(0, self._tr("Comprobar convergencia"))
                mode.setItemText(1, self._tr("Una iteración (None)"))
                del blocker
            elif a.kind == self._sub.COMPONENT:
                state = self._nested[a.name]
                state["box"].setToolTip(tip)
                combo = state["combo"]
                blocker = QtCore.QSignalBlocker(combo)
                for i, option in enumerate(self._sub.options(a)):
                    combo.setItemText(i, self._tr(option.label) if option.name is None else option.name)
                    combo.setItemData(i, self._option_help(a, option), QtCore.Qt.ToolTipRole)
                del blocker
                self.mark_window(a.name, self._window_conflicts.get(a.name, []), self._window_notes.get(a.name, []))

    def _kw(self) -> Dict[str, Any]:
        return dict(tr=self._tr, helps=self._helps, option_help=self._option_help, minimum=self._minimum)

    # --- construction -----------------------------------------------------------------------------------------
    def _combo(self, a: Any, items: Sequence[Tuple[str, Any]], value: Any) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox(self)
        for text, data in items:
            combo.addItem(text, data)
        combo.setCurrentIndex(combo.findData(value))
        combo.currentIndexChanged.connect(self.changed.emit)
        self._controls[a.name] = combo
        return combo

    def _make(self, a: Any, value: Any) -> QtWidgets.QWidget:
        sub = self._sub
        if a.kind == sub.BOOL:
            return self._combo(a, (("True", True), ("False", False)), bool(value))
        if a.kind == sub.CT2A:
            return self._combo(a, [(fn, fn) for fn in CT2A_FUNCTIONS], value)
        if a.kind == sub.CHOICE:
            return self._combo(a, [(str(c), c) for c in a.choices], value)
        if a.kind == sub.INT:
            spin = _IntSpin(self)
            spin.setRange(self._minimum.get((self.name, a.name), -2 ** 31 + 1), 2 ** 31 - 1)
            spin.setCorrectionMode(QtWidgets.QAbstractSpinBox.CorrectToNearestValue)
            spin.setKeyboardTracking(False)
            spin.setValue(int(value))
            spin.valueChanged.connect(self.changed.emit)
            self._controls[a.name] = spin
            return spin
        if a.kind == sub.LIST:
            box = QtWidgets.QWidget(self)
            row = QtWidgets.QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            edits = []
            for i, x in enumerate(value):
                edit = QtWidgets.QLineEdit(format_number(x), box)
                edit.setObjectName(f"{a.name}_{i + 1}")
                edit.textChanged.connect(self._on_text)
                row.addWidget(edit)
                edits.append(edit)
            self._controls[a.name] = (box, edits)
            return box
        if a.kind == sub.NUMBER_OR_NONE:
            box = QtWidgets.QWidget(self)
            row = QtWidgets.QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            mode = QtWidgets.QComboBox(box)
            mode.addItem(self._tr("Comprobar convergencia"), "check")
            mode.addItem(self._tr("Una iteración (None)"), "none")
            mode.setCurrentIndex(1 if value is None else 0)
            # With None, the field keeps the value of the signature, for when the check is chosen again.
            edit = QtWidgets.QLineEdit(format_number(sub.signature_default(a) if value is None else value), box)
            edit.setObjectName(a.name)
            edit.setEnabled(value is not None)
            mode.currentIndexChanged.connect(lambda _i, e=edit, m=mode: (e.setEnabled(m.currentData() == "check"),
                                                                           self._on_text()))
            edit.textChanged.connect(self._on_text)
            row.addWidget(mode)
            row.addWidget(edit, 1)
            self._controls[a.name] = (box, mode, edit)
            return box
        if a.kind == sub.COMPONENT:
            return self._make_component(a, value)
        edit = QtWidgets.QLineEdit(format_number(value), self)
        edit.setObjectName(a.name)
        edit.textChanged.connect(self._on_text)
        self._controls[a.name] = edit
        return edit

    def _make_component(self, a: Any, value: Any) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget(self)
        col = QtWidgets.QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        top = QtWidgets.QHBoxLayout()
        combo = QtWidgets.QComboBox(box)
        for i, o in enumerate(self._sub.options(a)):
            combo.addItem(self._tr(o.label) if o.name is None else o.name, o.name or "")
            combo.setItemData(i, self._option_help(a, o), QtCore.Qt.ToolTipRole)
        combo.setCurrentIndex(combo.findData(value.name if value is not None else ""))
        top.addWidget(combo, 1)
        col.addLayout(top)
        # The editor in the line of each option chosen is kept (with what it holds, an unreadable text too); a
        # window keeps the values accepted for each option in "memory".
        self._nested[a.name] = {"value": value, "memory": {} if value is None else {value.name: value},
                                "combo": combo, "box": box, "top": top, "inner": None, "editors": {}, "button": None,
                                "window": a.family == "ground"}
        combo.currentIndexChanged.connect(lambda _i, arg=a.name: self._on_option(arg))
        self._show_nested(a.name)
        self._controls[a.name] = combo
        return box

    def _show_nested(self, arg: str) -> None:
        """The arguments of the option chosen for ``arg``: in the same line, or a button (ground)."""
        state = self._nested[arg]
        if state["button"] is not None:
            state["button"].setParent(None)
            state["button"].deleteLater()
            state["button"] = None
        if state["inner"] is not None:
            # Hidden after it stops being the current one: a value it commits when hidden (an integer being typed)
            # stays in it, never replaces the option chosen (final adversarial round 2).
            old, state["inner"] = state["inner"], None
            old.setVisible(False)
        value = state["value"]
        if value is None or not self._sub.args_of(value.name):
            return
        if state["window"]:
            button = QtWidgets.QPushButton(self._tr("Parámetros del modelo de suelo…"), state["box"])
            button.clicked.connect(lambda _c=False, a=arg: self.open_window(a))
            state["top"].addWidget(button)
            state["button"] = button
            self.mark_window(arg, self._window_conflicts.get(arg, []), self._window_notes.get(arg, []))
        else:
            inner = state["editors"].get(value.name)
            if inner is None:
                inner = SubordinateEditor(value, state["box"], path=f"{self._path}{arg} · ", inline=True, **self._kw())
                inner.changed.connect(lambda a=arg, e=inner: self._on_inner(a, e))
                state["top"].addWidget(inner, 2)
                state["editors"][value.name] = inner
            inner.set_read_only(self._read_only)
            inner.setVisible(True)
            state["inner"] = inner

    def take_drafts(self) -> Dict[str, Dict[str, Any]]:
        """The drafts of the options not chosen of each nested argument, taken out of this editor to keep them in a
        new one of the same class (decision 7 of #64): the values kept for a window, and the editors in the line, with
        what they hold (an unreadable text too), which leave this editor."""
        out: Dict[str, Dict[str, Any]] = {}
        for arg, state in self._nested.items():
            chosen = state["value"].name if state["value"] is not None else None
            editors = {}
            for name, editor in list(state["editors"].items()):
                if name == chosen:
                    continue
                editor.changed.disconnect()
                editor.setParent(None)  # kept, not deleted with this editor
                editors[name] = editor
            out[arg] = {"memory": {k: v for k, v in state["memory"].items() if k != chosen}, "editors": editors}
        return out

    def keep_drafts(self, drafts: Mapping[str, Mapping[str, Any]]) -> None:
        """The drafts ``take_drafts`` took out of another editor of the same class, but those of the option chosen
        here (shown with its signature)."""
        for arg, kept in drafts.items():
            state = self._nested.get(arg)
            shown_here = state["value"].name if state is not None and state["value"] is not None else None
            for name, comp in kept["memory"].items():
                if state is not None and name != shown_here:
                    state["memory"][name] = comp
            for name, editor in kept["editors"].items():
                if state is None or name == shown_here or name in state["editors"]:
                    editor.deleteLater()
                    continue
                editor.setParent(state["box"])
                state["top"].addWidget(editor, 2)
                editor.setVisible(False)
                editor.changed.connect(lambda a=arg, e=editor: self._on_inner(a, e))
                state["editors"][name] = editor

    def align_nested(self, width: int) -> None:
        """The button of a window and the only control of a nested option in its line (the n of a rotor), ``width``
        wide, its selector taking the rest (decision 7 of #64, D3: as in the line of the rotor of the deficit)."""
        for state in self._nested.values():
            if state["button"] is not None:
                state["button"].setFixedWidth(width)
            inner = state["inner"]
            if inner is not None and len(inner._controls) == 1:
                control = next(iter(inner._controls.values()))
                if isinstance(control, QtWidgets.QWidget):
                    control.setFixedWidth(width)
                    state["top"].setStretchFactor(inner, 0)

    def set_inherited(self, name: Optional[str]) -> None:
        """The class an inheriting sum takes now (the superposition of the object it wraps), for its windows."""
        self.inherited = name

    def mark_window(self, arg: str, conflicts: Sequence[str], notes: Sequence[str] = ()) -> None:
        """Mark the button of the window that holds the cause of ``conflicts`` or of ``notes`` (what PyWake refuses
        only from a number of turbines, decision 6.1 of #64): red, or orange with notes only. The window never opens
        by itself and shows them when opened."""
        self._window_conflicts[arg] = list(conflicts)
        self._window_notes[arg] = list(notes)
        state = self._nested.get(arg)
        if state and state["button"] is not None:
            text = self._tr("Parámetros del modelo de suelo…")
            state["button"].setText(("⚠ " + text) if conflicts or notes else text)
            state["button"].setStyleSheet(window_mark(conflicts, notes))

    def open_window(self, arg: str, exec_: bool = True) -> "ComponentWindow":
        """The window of the arguments of a nested component; «Aceptar» keeps them, «Cancelar» changes nothing.
        With ``exec_`` false (tests), the window is returned without running it; ``accept_window`` takes it."""
        messages = (lambda comp, a=arg: self.window_messages(a, comp)) if self.window_messages is not None else None
        window = ComponentWindow(self._nested[arg]["value"], self, path=f"{self._path}{arg} · ",
                                 inherited=self.inherited, conflicts=self._window_conflicts.get(arg, []),
                                 notes=self._window_notes.get(arg, []), inherit_note=INHERIT_BLOCKAGE,
                                 messages=messages, read_only=self._read_only, **self._kw())
        if exec_ and window.exec_() == QtWidgets.QDialog.Accepted:
            self.accept_window(arg, window)
        return window

    def accept_window(self, arg: str, window: "ComponentWindow") -> None:
        state = self._nested[arg]
        state["value"] = window.value()
        state["memory"][state["value"].name] = state["value"]
        self.changed.emit()

    # --- reactions --------------------------------------------------------------------------------------------
    def _on_option(self, arg: str) -> None:
        from ..ag_core.wake_setup.config import component_signature
        state = self._nested[arg]
        name = state["combo"].currentData() or None
        if name is not None and name in state["editors"]:  # its editor, with what it holds
            state["value"] = state["editors"][name].value()
        else:
            state["value"] = None if name is None else state["memory"].get(name) or component_signature(name)
        if name is not None:
            state["memory"][name] = state["value"]
        self._show_nested(arg)
        self.changed.emit()

    def _on_inner(self, arg: str, editor: "SubordinateEditor") -> None:
        state = self._nested[arg]
        if editor is not state["inner"]:  # the editor of another option, which keeps what it holds
            return
        if not editor.errors():
            state["value"] = state["inner"].value()
            state["memory"][state["value"].name] = state["value"]
        self.changed.emit()

    def _on_text(self, *_: Any) -> None:
        self._mark()
        self.changed.emit()

    # --- reading ----------------------------------------------------------------------------------------------
    def _read(self, a: Any) -> Any:
        sub, c = self._sub, self._controls[a.name]
        if a.kind == sub.COMPONENT:
            state = self._nested[a.name]
            return state["inner"].value() if state["inner"] is not None else state["value"]
        if a.kind == sub.INT:
            return int(c.value())
        if isinstance(c, QtWidgets.QComboBox):
            return c.currentData()
        if a.kind == sub.LIST:
            return [parse_number(e.text()) for e in c[1]]
        if a.kind == sub.NUMBER_OR_NONE:
            return None if c[1].currentData() == "none" else parse_number(c[2].text())
        default = sub.signature_default(a)
        return parse_number(c.text(), integer=isinstance(default, int) and not isinstance(default, bool))

    def value(self) -> Any:
        """The component with the values that can be read (see ``errors``) and, for the others, its signature's."""
        from ..ag_core.wake_setup.config import Component, complete
        params = {}
        for a in self._args:
            try:
                params[a.name] = self._read(a)
            except ValueError:
                continue
        return complete(Component(self.name, params))

    def errors(self) -> List[str]:
        """The routes of the arguments whose field cannot be read, nested ones included."""
        out = []
        for a in self._args:
            if a.kind == self._sub.COMPONENT:
                inner = self._nested[a.name]["inner"]
                out += inner.errors() if inner is not None else []
                continue
            try:
                self._read(a)
            except ValueError:
                out.append(self._path + a.name)
        return out

    def _mark(self) -> None:
        for a in self._args:
            c = self._controls.get(a.name)
            if a.kind == self._sub.LIST:
                edits = c[1]
            elif a.kind == self._sub.NUMBER_OR_NONE:
                edits = [c[2]]
            else:
                edits = [c] if isinstance(c, QtWidgets.QLineEdit) else []
            for e in edits:
                try:
                    if e.isEnabled():
                        parse_number(e.text())
                    e.setStyleSheet("")
                except ValueError:
                    e.setStyleSheet(ParamEditor._INVALID)

    def set_read_only(self, read_only: bool) -> None:
        """Informative mode (the values are shown, not edited; a predefined model): the fields are read-only and the
        selectors disabled, also those of the nested options; their windows still open, to be read and closed."""
        self._read_only = read_only
        for a in self._args:
            c = self._controls[a.name]
            widgets = list(c[1:]) if isinstance(c, tuple) else [c]
            for w in widgets:
                for x in (w if isinstance(w, list) else [w]):
                    if isinstance(x, (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox)):
                        x.setReadOnly(read_only)
                    elif isinstance(x, QtWidgets.QComboBox):
                        x.setEnabled(not read_only)
            if a.kind == self._sub.COMPONENT and self._nested[a.name]["inner"] is not None:
                self._nested[a.name]["inner"].set_read_only(read_only)

    # --- for the dialog and the tests -------------------------------------------------------------------------
    def control(self, name: str):
        """The widget of an argument (``(box, fields)`` for a list, ``(box, mode, field)`` for a number or
        ``None``); for a nested one, its selector."""
        return self._controls[name]

    def nested(self, name: str) -> Optional["SubordinateEditor"]:
        """The editor in the same line of the option chosen for ``name``, if it has one."""
        return self._nested[name]["inner"]

    def window_button(self, name: str) -> Optional[QtWidgets.QPushButton]:
        return self._nested[name]["button"]

# What a ground that inherits its sum takes (ground_models.py:22-31; engineering_models.py:110, 129).
INHERIT_WAKES = "Se hereda la superposición de estelas ({cls})"
INHERIT_BLOCKAGE = "Se hereda la superposición del bloqueo ({cls})"


def coloured_lines(conflicts: Sequence[str], notes: Sequence[str]) -> str:
    """The lines of a note as rich text, each in its colour (decision 7 of #64): the conflicts in red, the warnings
    and the notes in orange, also when they share the note."""
    from html import escape

    def line(text: str, colour: str) -> str:
        return f'<span style="color: {colour};">' + escape(str(text), quote=False).replace("\n", "<br>") + "</span>"
    return "<br>".join([line(t, "#c0392b") for t in conflicts] + [line(t, "#b9770e") for t in notes])


def window_mark(conflicts: Sequence[str], notes: Sequence[str]) -> str:
    """The colour of what marks a window: red with conflicts, orange with notes only."""
    return "color: #c0392b;" if conflicts else "color: #b9770e;" if notes else ""


class ComponentWindow(QtWidgets.QDialog):
    """The small window of the arguments of a nested component (a ground model, decision 1 of #64): «Aceptar» keeps
    them, «Cancelar» leaves everything as it was, «Restablecer» shows the values of its signature (kept only with
    «Aceptar»). A field that cannot be read is marked here and «Aceptar» waits for it; a conflict with an outer
    selector (``conflicts``, and the ``notes`` of what PyWake refuses only from a number of turbines, and warnings) is
    shown here and does not keep from accepting. ``messages(component)``, if given, says them again for what is being
    edited (``None``: unknown, they stay as they are). ``read_only``: the values of a predefined model, to be read and
    closed («Cerrar»), without «Aceptar» nor «Restablecer»."""

    def __init__(self, component: Any, parent: Optional[QtWidgets.QWidget] = None,
                 tr: Callable[[str], str] = _identity, helps: Optional[Callable[[str, str], str]] = None,
                 option_help: Optional[Callable[[Any, Any], str]] = None,
                 minimum: Optional[Mapping[Tuple[str, str], int]] = None, path: str = "",
                 inherited: Optional[str] = None, conflicts: Sequence[str] = (), notes: Sequence[str] = (),
                 inherit_note: Optional[str] = None, title: str = "Parámetros del modelo de suelo", info: str = "",
                 messages: Optional[Callable[[Any], Optional[Tuple[Sequence[str], Sequence[str]]]]] = None,
                 read_only: bool = False):
        super().__init__(parent)
        self._messages = messages
        self._read_only = read_only
        self._kw = dict(tr=tr, helps=helps, option_help=option_help, minimum=minimum, path=path, inherited=inherited)
        self._inherit_note = tr(inherit_note).format(cls=inherited) if inherit_note and inherited else ""
        self.setWindowTitle(tr(title) + f" · {component.name}")
        self._lay = QtWidgets.QVBoxLayout(self)
        self.lbl_conflicts = QtWidgets.QLabel(self)
        self.lbl_conflicts.setTextFormat(QtCore.Qt.RichText)
        self.lbl_conflicts.setWordWrap(True)
        self._show_messages(conflicts, notes)
        self._lay.addWidget(self.lbl_conflicts)
        # What the class has and the plugin does not offer, with its reason (the window of the engine, D5).
        self.lbl_info = QtWidgets.QLabel(info, self)
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("color: #666;")
        self.lbl_info.setVisible(bool(info))
        self._lay.addWidget(self.lbl_info)
        self.lbl_inherit: Optional[QtWidgets.QLabel] = None
        buttons = QtWidgets.QDialogButtonBox(self)
        self.btn_accept = buttons.addButton(tr("Aceptar"), QtWidgets.QDialogButtonBox.AcceptRole)
        self.btn_cancel = buttons.addButton(tr("Cancelar"), QtWidgets.QDialogButtonBox.RejectRole)
        self.btn_reset = buttons.addButton(tr("Restablecer"), QtWidgets.QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.btn_reset.clicked.connect(self.reset)
        if read_only:
            # Out of the box, not only hidden: the box shows its buttons again when it is laid out (a style change).
            for button in (self.btn_accept, self.btn_reset):
                buttons.removeButton(button)
                button.setParent(self)
                button.setVisible(False)
            self.btn_cancel.setText(tr("Cerrar"))
            self.setStyleSheet(READ_ONLY_STYLE)
        self._lay.addWidget(buttons)
        self.editor = self._new_editor(component)

    def _new_editor(self, component: Any) -> SubordinateEditor:
        editor = SubordinateEditor(component, self, **self._kw)
        editor.set_read_only(self._read_only)
        editor.changed.connect(self._check)
        self._lay.insertWidget(0, editor)
        self.editor = editor
        # Under «Heredar», the sum it inherits (decision 7 of #64): the superposition of the object the ground wraps,
        # in the row under superpositionModel.
        self.lbl_inherit = None
        form = editor.layout()
        if self._inherit_note and isinstance(form, QtWidgets.QFormLayout):
            for row in range(form.rowCount()):
                item = form.itemAt(row, QtWidgets.QFormLayout.LabelRole)
                if item is not None and item.widget() is not None and item.widget().text() == "superpositionModel":
                    self.lbl_inherit = QtWidgets.QLabel(self._inherit_note, editor)
                    self.lbl_inherit.setWordWrap(True)
                    self.lbl_inherit.setStyleSheet("color: #666;")
                    form.insertRow(row + 1, "", self.lbl_inherit)
                    break
        self._check()
        return editor

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt
        # Enter in a field confirms it and does not accept the window (piece E1 of #64).
        if enter_reaches_default(self, event):
            super().keyPressEvent(event)

    def _show_messages(self, conflicts: Sequence[str], notes: Sequence[str]) -> None:
        self.lbl_conflicts.setText(coloured_lines(conflicts, notes))  # each line in its colour
        self.lbl_conflicts.setVisible(bool(conflicts or notes))

    def _check(self) -> None:
        errors = self.editor.errors()
        self.btn_accept.setEnabled(not errors)
        if self.lbl_inherit is not None:
            self.lbl_inherit.setVisible(self.editor.value().params.get("superpositionModel") is None)
        # What is being edited, said again (discrete round 1 of #64, C2): a change or «Restablecer» does not leave
        # the messages of what was accepted; with a field that cannot be read they cannot be said, and those of
        # another selection are not left either (round 2, C).
        if self._messages is not None:
            found = ([], []) if errors else self._messages(self.editor.value())
            if found is not None:
                self._show_messages(*found)

    def reset(self) -> None:
        from ..ag_core.wake_setup.config import component_signature
        old = self.editor
        old.setParent(None)
        old.deleteLater()
        self._new_editor(component_signature(old.name))

    def value(self) -> Any:
        return self.editor.value()
