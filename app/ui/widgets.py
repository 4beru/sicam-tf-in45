"""Widgets compartidos: tarjetas, KPIs, chips, tablas y toast."""
from __future__ import annotations

import re
from html import unescape

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import icons
from .theme import COLORS


def vaciar_layout(layout) -> None:
    """Elimina inmediatamente (shiboken6.delete) todo el contenido de un layout.

    Sustituye al patrón takeAt + deleteLater: con churn constante de
    refrescos, la eliminación diferida deja ventanas de use-after-free
    en PySide6 (SIGSEGV / munmap_chunk). La eliminación inmediata cierra
    esa ventana.
    """
    from shiboken6 import delete
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            delete(w)
        elif item.layout() is not None:
            vaciar_layout(item.layout())
        elif item.spacerItem() is not None:
            delete(item)


def _cls(widget, nombre: str):
    widget.setProperty("cls", nombre)
    return widget


class Card(QFrame):
    """Tarjeta blanca con título opcional."""

    def __init__(self, titulo: str = "", ref: str = "", parent=None):
        super().__init__(parent)
        _cls(self, "card")
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(16, 14, 16, 14)
        self.vbox.setSpacing(10)
        if titulo:
            t = QLabel(titulo)
            _cls(t, "card_title")
            self.vbox.addWidget(t)

    def cuerpo(self) -> QVBoxLayout:
        return self.vbox


class ResponsiveGrid(QWidget):
    """Reorganiza tarjetas según el ancho real disponible, sin reconstruirlas."""

    def __init__(
        self,
        min_item_width: int = 220,
        max_columns: int = 4,
        spacing: int = 12,
        center_items: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._items: list[QWidget] = []
        self._min_item_width = max(1, min_item_width)
        self._max_columns = max(1, max_columns)
        self._spacing = max(0, spacing)
        self._center_items = center_items
        self._center_max_width: int | None = None
        self._columns = 0

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(self._spacing)
        self._grid.setVerticalSpacing(self._spacing)
        # The grid must grow horizontally, but its vertical extent should stay
        # content-driven. Preferred allows the dashboard rows to absorb surplus
        # height from the page stack, which can create large empty cards.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

    def set_items(self, items: list[QWidget]) -> None:
        self._items = list(items)
        self._center_max_width = (
            min(widget.maximumWidth() for widget in self._items)
            if self._center_items and self._items else None
        )
        self._columns = 0
        self._reflow(force=True)

    def _column_count(self) -> int:
        width = max(1, self.contentsRect().width())
        # Durante la construcción todavía no hay un ancho real. Usar la
        # cantidad máxima evita calcular un sizeHint inicial exageradamente alto.
        if width < self._min_item_width and not self.isVisible():
            return self._max_columns
        return max(
            1,
            min(
                self._max_columns,
                (width + self._spacing) // (self._min_item_width + self._spacing),
            ),
        )

    def _size_centered_items(self, columns: int) -> None:
        if not self._center_items or not self._items:
            return
        width = max(1, self.contentsRect().width())
        cell_width = max(
            self._min_item_width,
            (width - self._spacing * (columns - 1)) // columns,
        )
        max_width = self._center_max_width or cell_width
        item_width = max(self._min_item_width, min(max_width, cell_width))
        for widget in self._items:
            if widget.minimumWidth() != item_width or widget.maximumWidth() != item_width:
                widget.setFixedWidth(item_width)

    def _reflow(self, force: bool = False) -> None:
        if not self._items:
            return
        columns = self._column_count()
        if not force and columns == self._columns:
            # Aunque no cambie el número de columnas, las tarjetas KPI dejan
            # de crecer al alcanzar su ancho máximo y permanecen uniformes.
            self._size_centered_items(columns)
            return

        while self._grid.count():
            self._grid.takeAt(0)

        # Cada columna lógica usa dos pistas para centrar también las filas
        # incompletas (por ejemplo, tres tarjetas debajo de cuatro).
        tracks = self._max_columns * 2
        for col in range(tracks):
            self._grid.setColumnStretch(col, 1 if col < columns * 2 else 0)

        self._size_centered_items(columns)
        for index, widget in enumerate(self._items):
            row = index // columns
            col_in_row = index % columns
            items_in_row = min(columns, len(self._items) - row * columns)
            offset = columns - items_in_row if self._center_items and items_in_row < columns else 0
            col = offset + col_in_row * 2
            if self._center_items:
                self._grid.addWidget(
                    widget, row, col, 1, 2, Qt.AlignmentFlag.AlignHCenter
                )
            else:
                self._grid.addWidget(widget, row, col, 1, 2)

        self._columns = columns
        self.updateGeometry()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()


class Kpi(QFrame):
    """Tarjeta de indicador: nombre, valor grande y metadatos (chips + texto)."""

    def __init__(self, nombre: str, valor: str, icono: str = "chart",
                 chips: list[tuple[str, str]] | None = None, target: str = ""):
        super().__init__()
        _cls(self, "kpi")
        self.setMinimumWidth(220)
        self.setMaximumWidth(290)
        self.setMinimumHeight(126)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 9, 12, 9)
        v.setSpacing(3)

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

        # Separar chips y descripción evita que se desborden al mostrar
        # cuatro indicadores por fila en resoluciones de escritorio habituales.
        meta = QVBoxLayout()
        meta.setSpacing(3)
        for texto, tipo in (chips or []):
            linea_chips = QHBoxLayout()
            linea_chips.setSpacing(5)
            linea_chips.addWidget(chip(texto, tipo))
            linea_chips.addStretch(1)
            meta.addLayout(linea_chips)

        t = QLabel(target)
        _cls(t, "kpi_target")
        t.setWordWrap(True)
        t.setMinimumHeight(12)
        meta.addWidget(t)
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
            if isinstance(valor, tuple):
                # Formatos compatibles: (texto, color/alineación) o
                # (texto, color/alineación, negrita). QTableWidgetItem no
                # interpreta HTML; se aplica el estilo con propiedades Qt.
                texto, extra, *opciones = valor
                item.setText(_texto_tabla(texto))
                if isinstance(extra, Qt.AlignmentFlag):
                    item.setTextAlignment(extra | Qt.AlignmentFlag.AlignVCenter)
                elif extra is not None:
                    item.setForeground(_qcolor(str(extra)))
                if opciones and opciones[0]:
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
            else:
                item.setText(_texto_tabla(valor))
            item.setToolTip(item.text())
            t.setItem(i, j, item)

    header = t.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(stretch_ultima)
    return t


_ETIQUETA_HTML = re.compile(r"</?[A-Za-z][^>]*>")


def _texto_tabla(valor) -> str:
    """Convierte texto accidentalmente marcado con HTML a texto plano legible."""
    texto = str(valor)
    if _ETIQUETA_HTML.search(texto):
        texto = _ETIQUETA_HTML.sub("", texto)
    return unescape(texto)


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


def fila_kpis(kpis: list[Kpi], parent_layout: QVBoxLayout, por_fila: int = 3):
    """Agrega filas de KPIs uniformes y centra la última fila si le falta una tarjeta."""
    for i in range(0, len(kpis), por_fila):
        h = QHBoxLayout()
        h.setSpacing(12)
        chunk = kpis[i:i + por_fila]

        # En una cuadrícula de cuatro columnas, centrar la última fila de tres
        # conserva el ancho de cada tarjeta y evita dejarla pegada al margen.
        if por_fila >= 4 and len(chunk) == por_fila - 1:
            h.addStretch(1)
            for k in chunk:
                h.addWidget(k, 2)
            h.addStretch(1)
        else:
            for k in chunk:
                h.addWidget(k, 1)
            for _ in range(por_fila - len(chunk)):
                h.addStretch(1)
        parent_layout.addLayout(h)
