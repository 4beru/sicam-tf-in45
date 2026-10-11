"""Página Producción diaria: registro de prendas inspeccionadas y tasa NC."""
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QGridLayout, QHeaderView, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from ..core import db, queries
from . import icons
from .charts import TendenciaWidget
from .theme import COLORS
from .widgets import Card, tabla, vaciar_layout

DER = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class ProduccionPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell):
        super().__init__()
        self.conn = conn
        self.shell = shell

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)

        # ---------------- formulario (columna izquierda)
        card_form = Card("Registrar producción del día")
        card_form.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.f_fecha = QDateEdit(date.today())
        self.f_fecha.setDisplayFormat("dd/MM/yyyy")
        self.f_fecha.setCalendarPopup(True)
        self.f_fecha.setProperty("cal", True)
        self.f_proceso = QComboBox()
        self.f_proceso.addItems(db.PROCESOS)
        self.f_turno = QComboBox()
        self.f_turno.addItems(db.TURNOS)
        self.f_insp = QSpinBox()
        self.f_insp.setRange(1, 1_000_000)
        self.f_nc = QSpinBox()
        self.f_nc.setRange(0, 1_000_000)

        def campo(etiqueta: str, control: QWidget) -> QVBoxLayout:
            bloque = QVBoxLayout()
            bloque.setContentsMargins(0, 0, 0, 0)
            bloque.setSpacing(5)
            lbl = QLabel(etiqueta)
            lbl.setProperty("cls", "muted")
            bloque.addWidget(lbl)
            control.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            bloque.addWidget(control)
            return bloque

        campos = QGridLayout()
        campos.setContentsMargins(0, 0, 0, 0)
        campos.setHorizontalSpacing(12)
        campos.setVerticalSpacing(12)
        campos.addLayout(campo("Fecha", self.f_fecha), 0, 0, 1, 2)
        campos.addLayout(campo("Proceso", self.f_proceso), 1, 0, 1, 2)
        campos.addLayout(campo("Turno", self.f_turno), 2, 0, 1, 2)
        campos.addLayout(campo("Prendas inspeccionadas", self.f_insp), 3, 0)
        campos.addLayout(campo("NC detectadas", self.f_nc), 3, 1)
        card_form.vbox.addLayout(campos)

        # Resumen calculado en tiempo real para aportar información útil al formulario.
        resumen = QWidget()
        resumen.setProperty("cls", "ficha")
        resumen_v = QVBoxLayout(resumen)
        resumen_v.setContentsMargins(12, 10, 12, 10)
        resumen_v.setSpacing(3)
        resumen_titulo = QLabel("TASA NC ESTIMADA")
        resumen_titulo.setProperty("cls", "summary_label")
        resumen_v.addWidget(resumen_titulo)
        self.lbl_tasa_valor = QLabel("0.0%")
        self.lbl_tasa_valor.setProperty("cls", "summary_value")
        resumen_v.addWidget(self.lbl_tasa_valor)
        self.lbl_tasa_detalle = QLabel()
        self.lbl_tasa_detalle.setProperty("cls", "summary_detail")
        self.lbl_tasa_detalle.setWordWrap(True)
        resumen_v.addWidget(self.lbl_tasa_detalle)
        card_form.vbox.addWidget(resumen)

        ayuda = QLabel(
            "El registro se identifica por fecha, proceso y turno. "
            "La tasa se calcula automáticamente como NC detectadas ÷ "
            "prendas inspeccionadas × 100."
        )
        ayuda.setProperty("cls", "hint")
        ayuda.setWordWrap(True)
        card_form.vbox.addWidget(ayuda)
        card_form.vbox.addStretch(1)

        btn = QPushButton("  Registrar producción")
        btn.setProperty("cls", "primary")
        btn.setIcon(icons.icono("plus", "#FFFFFF", 15))
        btn.setMinimumHeight(40)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.clicked.connect(self._agregar)
        card_form.vbox.addWidget(btn)

        self.f_insp.valueChanged.connect(self._actualizar_previsualizacion_tasa)
        self.f_nc.valueChanged.connect(self._actualizar_previsualizacion_tasa)
        self._actualizar_previsualizacion_tasa()

        # ---------------- tendencia a todo lo ancho
        self.card_chart = Card("Tasa diaria — últimos 14 días")
        self.chart = TendenciaWidget()
        self.chart.setMinimumHeight(290)
        self.card_chart.vbox.addWidget(self.chart)
        self.card_chart.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        v.addWidget(self.card_chart)

        # ---------------- formulario y tabla en columnas
        fila_registros = QHBoxLayout()
        fila_registros.setSpacing(14)
        fila_registros.addWidget(card_form, 2)

        self.card_tabla = Card("Producción y tasa de NC · últimos registros")
        self.card_tabla.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # Conserva los 30 registros y limita la altura visual de la tarjeta;
        # QTableWidget permite recorrer el resto con su scroll vertical.
        self.card_tabla.setMaximumHeight(640)
        self.tabla_layout = QVBoxLayout()
        self.tabla_layout.setContentsMargins(0, 0, 0, 0)
        self.tabla_layout.setSpacing(0)
        self.card_tabla.vbox.addLayout(self.tabla_layout)
        fila_registros.addWidget(self.card_tabla, 5)
        v.addLayout(fila_registros, 1)

    def _agregar(self):
        fecha = self.f_fecha.date().toString("yyyy-MM-dd")
        with self.conn:
            self.conn.execute(
                "INSERT INTO produccion (fecha, proceso, turno, inspeccionadas, nc_detectadas) "
                "VALUES (?,?,?,?,?) ON CONFLICT (fecha, proceso, turno) DO UPDATE SET "
                "inspeccionadas=excluded.inspeccionadas, nc_detectadas=excluded.nc_detectadas",
                (fecha, self.f_proceso.currentText(), self.f_turno.currentText(),
                 self.f_insp.value(), self.f_nc.value()))
        self.shell.toast("Producción registrada — tasa NC calculada automáticamente")
        self.shell.refresh_all(excepto="prod")
        self.refresh()

    def _actualizar_previsualizacion_tasa(self, *_):
        inspeccionadas = self.f_insp.value()
        nc = self.f_nc.value()
        tasa = nc / inspeccionadas * 100 if inspeccionadas else 0.0
        self.lbl_tasa_valor.setText(f"{tasa:.1f}%")
        self.lbl_tasa_detalle.setText(
            f"{nc:,}".replace(",", " ")
            + " NC detectadas de "
            + f"{inspeccionadas:,}".replace(",", " ")
            + " prendas inspeccionadas."
        )

    def refresh(self):
        filas = queries.produccion_reciente(self.conn, 30)
        datos = []
        for r in filas:
            tasa = r["nc_detectadas"] / r["inspeccionadas"] * 100 if r["inspeccionadas"] else 0
            color = (COLORS["red"] if tasa > 7 else
                     COLORS["amber"] if tasa > 5 else COLORS["green"])
            datos.append([
                r["fecha"], r["proceso"], r["turno"],
                (f"{r['inspeccionadas']:,}".replace(",", " "), DER),
                (f"{r['nc_detectadas']:,}".replace(",", " "), DER),
                (f"{tasa:.1f}%", color),
            ])
        nueva = tabla(["Fecha", "Proceso", "Turno", "Inspeccionadas", "NC", "Tasa NC"],
                      datos or [["—"] * 6])

        # Encabezados centrados; fechas y turnos centrados, texto descriptivo a
        # la izquierda y métricas numéricas alineadas a la derecha.
        header = nueva.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        # Distribuye el ancho disponible por igual entre las seis columnas.
        header.setStretchLastSection(False)
        for columna in range(nueva.columnCount()):
            header.setSectionResizeMode(
                columna, QHeaderView.ResizeMode.Stretch
            )
        for fila_idx in range(nueva.rowCount()):
            fecha_item = nueva.item(fila_idx, 0)
            turno_item = nueva.item(fila_idx, 2)
            tasa_item = nueva.item(fila_idx, 5)
            if fecha_item is not None:
                fecha_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                )
            if turno_item is not None:
                turno_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                )
            if tasa_item is not None:
                # Se conserva el color de severidad y se corrige solo la alineación.
                tasa_item.setTextAlignment(DER)

        vaciar_layout(self.tabla_layout)
        self.tabla_layout.addWidget(nueva)

        m = queries.metas(self.conn)
        as_is, to_be = m.get("Tasa de prendas no conformes", (10.68, 4.95))
        puntos = [{"etiqueta": e, "tasa": t, "piloto": True}
                  for e, t in queries.tasa_diaria(self.conn, 14)]
        self.chart.set_datos(puntos, as_is, to_be)
