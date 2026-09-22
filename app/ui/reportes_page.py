"""Página Reportes: PDFs generados por el sistema + exportación a Excel."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ..core import plantilla, reportes
from . import icons
from .theme import COLORS
from .widgets import Card


class ReportesPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell):
        super().__init__()
        self.conn = conn
        self.shell = shell

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)

        banner = Card()
        banner.setProperty("cls", "banner")
        txt = QLabel(
            "La empresa no recibe Excel: recibe <b>PDFs generados por el sistema</b> "
            "(reportlab), listos para imprimir o enviar. Lo que sale del sistema en Excel "
            "usa las mismas columnas de la plantilla, así puede volver a entrar sin fricción.")
        txt.setProperty("cls", "banner_txt")
        txt.setWordWrap(True)
        banner.vbox.addWidget(txt)
        v.addWidget(banner)

        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(14)

        self._tarjeta_reporte(grid, 0, 0, "calendar", "Plan mensual de mantenimiento",
                              "Cronograma S1–S4 por máquina con frecuencias de la Fig. 42, "
                              "estados y cumplimiento del mes.", self._pdf_plan)
        self._tarjeta_reporte(grid, 0, 1, "chart", "Pareto de causas",
                              "Pareto del periodo completo con % acumulado y corte 80/20, "
                              "listo para exponer (Fig. 9).", self._pdf_pareto)
        self._tarjeta_reporte(grid, 1, 0, "trend", "Resumen de indicadores",
                              "As-Is · To-Be · actual para los indicadores de las Tablas 21 "
                              "y 22 de la tesis.", self._pdf_indicadores)
        self._tarjeta_reporte(grid, 1, 1, "sheet", "Registro de no conformidades",
                              "Detalle de NC en Excel con las mismas columnas de la "
                              "plantilla de carga (formato bidireccional).", self._xlsx_nc)

        v.addWidget(grid_wrap)
        v.addStretch(1)

    def _tarjeta_reporte(self, grid, fila, col, icono, titulo, desc, accion):
        t = Card()
        t.setMinimumHeight(150)
        cabeza = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icono, COLORS["teal"], 22))
        cabeza.addWidget(ic)
        titulo_lbl = QLabel(f"<b>{titulo}</b>")
        titulo_lbl.setTextFormat(Qt.TextFormat.RichText)
        cabeza.addWidget(titulo_lbl)
        cabeza.addStretch(1)
        t.vbox.addLayout(cabeza)
        d = QLabel(desc)
        d.setProperty("cls", "hint")
        d.setWordWrap(True)
        t.vbox.addWidget(d)
        t.vbox.addStretch(1)
        b = QPushButton("  Generar")
        b.setProperty("cls", "primary")
        b.setIcon(icons.icono("download", "#FFFFFF", 15))
        b.clicked.connect(accion)
        t.vbox.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(t, fila, col)

    # ------------------------------------------------ acciones
    def _guardar(self, filtro: str, defecto: str) -> str | None:
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar reporte", defecto, filtro)
        return ruta or None

    def _pdf_plan(self):
        if ruta := self._guardar("PDF (*.pdf)", "plan_tpm.pdf"):
            reportes.pdf_plan(self.conn, ruta)
            self.shell.toast(f"Plan mensual exportado: {ruta}")

    def _pdf_pareto(self):
        if ruta := self._guardar("PDF (*.pdf)", "pareto_causas.pdf"):
            reportes.pdf_pareto(self.conn, ruta)
            self.shell.toast(f"Pareto exportado: {ruta}")

    def _pdf_indicadores(self):
        if ruta := self._guardar("PDF (*.pdf)", "indicadores.pdf"):
            reportes.pdf_indicadores(self.conn, ruta)
            self.shell.toast(f"Indicadores exportados: {ruta}")

    def _xlsx_nc(self):
        if ruta := self._guardar("Excel (*.xlsx)", "no_conformidades.xlsx"):
            n = plantilla.exportar_no_conformidades(self.conn, ruta)
            self.shell.toast(f"Exportadas {n} filas a {ruta}")

    def refresh(self):
        pass
