"""Widgets compartidos: tarjetas, KPIs, chips, tablas y toast."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import icons
from .theme import COLORS


def _cls(widget, nombre: str):
    widget.setProperty("cls", nombre)
    return widget


class Card(QFrame):
    """Tarjeta blanca con título opcional y etiqueta de referencia (p. ej. 'Tabla 6')."""

    def __init__(self, titulo: str = "", ref: str = "", parent=None):
        super().__init__(parent)
        _cls(self, "card")
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(16, 14, 16, 14)
        self.vbox.setSpacing(10)
        if titulo or ref:
            fila = QHBoxLayout()
            if titulo:
                t = QLabel(titulo)
                _cls(t, "card_title")
                fila.addWidget(t)
            fila.addStretch(1)
            if ref:
                r = QLabel(ref)
                _cls(r, "ref")
                fila.addWidget(r)
            self.vbox.addLayout(fila)

    def cuerpo(self) -> QVBoxLayout:
        return self.vbox


class Kpi(QFrame):
    """Tarjeta de indicador: nombre, valor grande y metadatos (chips + texto)."""

    def __init__(self, nombre: str, valor: str, icono: str = "chart",
                 chips: list[tuple[str, str]] | None = None, target: str = ""):
        super().__init__()
        _cls(self, "kpi")
        self.setMinimumWidth(170)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(4)

        arriba = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icono, COLORS["teal"], 17))
        arriba.addWidget(ic)
        n = QLabel(nombre)
        _cls(n, "kpi_name")
        n.setWordWrap(True)
        arriba.addWidget(n, 1)
        v.addLayout(arriba)

        val = QLabel(valor)
        _cls(val, "kpi_value")
        v.addWidget(val)
        self.valor_label = val

        meta = QHBoxLayout()
        meta.setSpacing(5)
        for texto, tipo in (chips or []):
            meta.addWidget(chip(texto, tipo))
        if target:
            t = QLabel(target)
            _cls(t, "kpi_target")
            meta.addWidget(t)
        meta.addStretch(1)
        v.addLayout(meta)


def chip(texto: str, tipo: str = "info") -> QLabel:
    c = QLabel(texto)
    _cls(c, f"chip_{tipo}")
    return c


def chip_punto(texto: str, color_punto: str, tipo: str = "info") -> QLabel:
    """Chip con un punto de color (en vez de emoji) al inicio."""
    c = QLabel(f"<span style='color:{color_punto}'>●</span>&nbsp; {texto}")
    _cls(c, f"chip_{tipo}")
    return c


def tabla(columnas: list[str], filas: list[list], stretch_ultima: bool = True) -> QTableWidget:
    """Tabla estilizada de solo lectura con filas ya formateadas."""
    t = QTableWidget(len(filas), len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(34)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    for i, fila in enumerate(filas):
        for j, valor in enumerate(fila):
            item = QTableWidgetItem()
            if isinstance(valor, tuple):  # (texto, color) o (texto, alignment)
                texto, extra = valor
                item.setText(str(texto))
                if isinstance(extra, Qt.AlignmentFlag):
                    item.setTextAlignment(extra | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setForeground(_qcolor(extra))
            else:
                item.setText(str(valor))
            item.setToolTip(item.text())
            t.setItem(i, j, item)

    header = t.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(stretch_ultima)
    return t


def _qcolor(hexa: str):
    from PySide6.QtGui import QColor
    return QColor(hexa)


class Toast(QLabel):
    """Notificación flotante abajo a la derecha (equivalente al toast de la maqueta)."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setVisible(False)
        self.setWordWrap(True)
        self.setMaximumWidth(420)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def mostrar(self, mensaje: str, tipo: str = "ok"):
        self.setProperty("cls", tipo)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setText(mensaje)
        self.adjustSize()
        self.setVisible(True)
        self.raise_()
        self._timer.start(3400)


def fila_kpis(kpis: list[Kpi], parent_layout: QVBoxLayout):
    """Agrega una fila de KPIs con separación uniforme."""
    h = QHBoxLayout()
    h.setSpacing(12)
    for k in kpis:
        h.addWidget(k, 1)
    parent_layout.addLayout(h)
