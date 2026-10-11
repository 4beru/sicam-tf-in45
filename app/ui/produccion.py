"""Página Producción diaria: registro de prendas inspeccionadas y tasa NC."""
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
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

        # ---------------- formulario
        card_form = Card("Registrar producción del día")
        fila = QHBoxLayout()
        fila.setSpacing(9)
        self.f_fecha = QDateEdit(date.today())
        self.f_fecha.setDisplayFormat("dd/MM/yyyy")
        self.f_fecha.setCalendarPopup(True)
        self.f_fecha.setProperty("cal", True)
        self.f_fecha.setCalendarPopup(True)
        self.f_proceso = QComboBox(); self.f_proceso.addItems(db.PROCESOS)
        self.f_turno = QComboBox(); self.f_turno.addItems(db.TURNOS)
        self.f_insp = QSpinBox(); self.f_insp.setRange(1, 1_000_000)
        self.f_nc = QSpinBox(); self.f_nc.setRange(0, 1_000_000)
        btn = QPushButton("  Agregar")
        btn.setProperty("cls", "primary")
        btn.setIcon(icons.icono("plus", "#FFFFFF", 15))
        btn.clicked.connect(self._agregar)
        for w in (self.f_fecha, self.f_proceso, self.f_turno, self.f_insp, self.f_nc, btn):
            fila.addWidget(w)
        fila.addStretch(1)
        card_form.vbox.addLayout(fila)
        h = QLabel("Las NC detectadas provienen del módulo de No conformidades; esta tasa es el insumo del dashboard.")
        h.setProperty("cls", "hint")
        card_form.vbox.addWidget(h)
        v.addWidget(card_form)

        # ---------------- tendencia arriba; tabla al final
        columna_resultados = QVBoxLayout()
        columna_resultados.setSpacing(14)

        self.card_chart = Card("Tasa diaria — últimos 14 días")
        self.chart = TendenciaWidget()
        self.chart.setMinimumHeight(290)
        self.card_chart.vbox.addWidget(self.chart)
        # Evita que la cantidad de filas de la tabla estire este gráfico.
        self.card_chart.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        columna_resultados.addWidget(self.card_chart)

        self.card_tabla = Card("Producción y tasa de NC · últimos registros")
        columna_resultados.addWidget(self.card_tabla)
        v.addLayout(columna_resultados, 1)

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
        nueva.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
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

        vaciar_layout(self.card_tabla.vbox)
        self.card_tabla.vbox.addWidget(nueva)

        m = queries.metas(self.conn)
        as_is, to_be = m.get("Tasa de prendas no conformes", (10.68, 4.95))
        puntos = [{"etiqueta": e, "tasa": t, "piloto": True}
                  for e, t in queries.tasa_diaria(self.conn, 14)]
        self.chart.set_datos(puntos, as_is, to_be)
