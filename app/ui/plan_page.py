"""Página Plan TPM: grid S1–S4 del mes con estados y registro de ejecuciones."""
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from ..core import plan_tpm
from . import icons
from .theme import COLORS
from .widgets import Card, chip_punto, tabla, vaciar_layout

ESTADO_UI = {
    "over": ("st_over", "Vencida"),
    "soon": ("st_soon", "Esta semana"),
    "sched": ("st_sched", "Programada"),
}
PRIORIDAD = {"over": 0, "soon": 1, "sched": 2}


class EjecucionDialog(QDialog):
    def __init__(self, maquina: str, actividad: str, frecuencia_txt: str, parent=None):
        super().__init__(parent)
        self.maquina, self.actividad = maquina, actividad
        self.setWindowTitle(f"Registrar ejecución — {maquina}")
        self.setMinimumWidth(440)

        form = QFormLayout(self)
        info = QLabel(f"<b>{actividad}</b> · frecuencia {frecuencia_txt}")
        info.setTextFormat(Qt.TextFormat.RichText)
        form.addRow(info)
        self.fecha = QDateEdit(date.today())
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        self.fecha.setCalendarPopup(True)
        self.fecha.setProperty("cal", True)
        self.responsable = QComboBox()
        self.responsable.addItems(plan_tpm.RESPONSABLES)
        self.observacion = QLineEdit()
        self.observacion.setPlaceholderText("Repuestos usados, hallazgos… (opcional)")
        form.addRow("Fecha de ejecución", self.fecha)
        form.addRow("Responsable", self.responsable)
        form.addRow("Observaciones", self.observacion)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Registrar como ejecutada")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._guardar)
        botones.rejected.connect(self.reject)
        form.addRow(botones)

    def _guardar(self):
        plan_tpm.registrar_ejecucion(
            self.maquina, self.actividad,
            fecha=self.fecha.date().toString("yyyy-MM-dd"),
            responsable=self.responsable.currentText(),
            observacion=self.observacion.text().strip())
        self.accept()


class PlanPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell):
        super().__init__()
        self.conn = conn
        self.shell = shell
        self._tareas: list[dict] = []

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)

        self.cabecera = Card()
        v.addWidget(self.cabecera)

        self.card_grid = Card("Plan mensual de mantenimiento preventivo", "Fig. 42")
        v.addWidget(self.card_grid, 1)

    # ------------------------------------------------ refresco
    def refresh(self):
        r = plan_tpm.resumen(self.conn)
        self._tareas = plan_tpm.tareas_del_mes(self.conn)

        # ---- cabecera: chips + cumplimiento + exportar
        vaciar_layout(self.cabecera.vbox)
        fila = QHBoxLayout()
        fila.setSpacing(10)
        titulo = QLabel(f"<b style='font-size:15px'>{r['mes']}</b>")
        titulo.setTextFormat(Qt.TextFormat.RichText)
        fila.addWidget(titulo)
        fila.addWidget(chip_punto(f"{r['vencidas']} vencidas", COLORS["red"],
                                  "bad" if r["vencidas"] else "good"))
        fila.addWidget(chip_punto(f"{r['proximas']} vencen ≤ 7 días", COLORS["amber"],
                                  "warn" if r["proximas"] else "info"))
        fila.addWidget(chip_punto(f"{r['ejecutadas']} ejecutadas este mes",
                                  COLORS["green"], "good"))
        fila.addStretch(1)

        cumple = QWidget()
        cv = QVBoxLayout(cumple)
        cv.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(f"Cumplimiento: <b>{r['cumplimiento']:.0f}%</b> "
                     f"<span style='color:#64748B'>(meta ≥ 85%)</span>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        # barra de cumplimiento: gradiente truncado al % (QSS no admite anchos en %)
        color = (COLORS["teal"] if r["cumplimiento"] >= 85 else COLORS["amber"])
        fraccion = min(1.0, r["cumplimiento"] / 100)
        barra = QWidget()
        barra.setFixedHeight(9)
        barra.setStyleSheet(
            f"border-radius:4px;background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {color}, stop:{fraccion:.3f} {color},"
            f"stop:{min(1.0, fraccion + 0.001):.3f} {COLORS['bg']},"
            f"stop:1 {COLORS['bg']});")
        cv.addWidget(lbl)
        cv.addWidget(barra)
        fila.addWidget(cumple, 1)

        b_pdf = QPushButton("  Exportar plan (PDF)")
        b_pdf.setProperty("cls", "primary")
        b_pdf.setIcon(icons.icono("download", "#FFFFFF", 15))
        b_pdf.clicked.connect(self._exportar_pdf)
        fila.addWidget(b_pdf)
        self.cabecera.vbox.addLayout(fila)

        # ---- grid S1–S4
        vaciar_layout(self.card_grid.vbox)

        frecs = self.conn.execute("SELECT * FROM frecuencias ORDER BY maquina").fetchall()
        ejecutadas = plan_tpm.ejecuciones_del_mes(self.conn)
        grid = QTableWidget(len(frecs), 8)
        grid.setHorizontalHeaderLabels(
            ["Máquina", "Actividad", "Frecuencia", "Sem 1", "Sem 2", "Sem 3", "Sem 4", "Responsable"])
        grid.verticalHeader().setVisible(False)
        grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        grid.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        grid.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        grid.setShowGrid(False)
        grid.verticalHeader().setDefaultSectionSize(44)
        grid.setAlternatingRowColors(True)

        for i, f in enumerate(frecs):
            grid.setItem(i, 0, QTableWidgetItem(f["maquina"]))
            grid.setItem(i, 1, QTableWidgetItem(f["actividad"]))
            grid.setItem(i, 2, QTableWidgetItem(plan_tpm._texto_freq(f["frecuencia_dias"])))
            grid.setItem(i, 7, QTableWidgetItem(f["responsable"]))
            for col in (0, 1, 2, 7):
                it = grid.item(i, col)
                it.setToolTip(it.text())
            for s in range(1, 5):
                en_semana = [t for t in self._tareas
                             if t["maquina"] == f["maquina"]
                             and t["actividad"] == f["actividad"] and t["semana"] == s]
                hecha = any(e["maquina"] == f["maquina"] and e["actividad"] == f["actividad"]
                            and plan_tpm.semana_de(date.fromisoformat(e["fecha"])) == s
                            for e in ejecutadas)
                celda = QWidget()
                cv = QHBoxLayout(celda)
                cv.setContentsMargins(4, 4, 4, 4)
                cv.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if hecha:
                    b = QPushButton("✔ Hecha")
                    b.setProperty("cls", "st_done")
                    b.setEnabled(False)
                    cv.addWidget(b)
                elif en_semana:
                    peor = min(en_semana, key=lambda t: PRIORIDAD[t["estado"]])
                    cls, txt = ESTADO_UI[peor["estado"]]
                    b = QPushButton(f"{txt} · {peor['fecha'][8:]}/{peor['fecha'][5:7]}")
                    b.setProperty("cls", cls)
                    b.setCursor(Qt.CursorShape.PointingHandCursor)
                    maq, act, ft = f["maquina"], f["actividad"], peor["frecuencia_txt"]
                    b.clicked.connect(lambda _=False, m=maq, a=act, t=ft: self._registrar(m, a, t))
                    cv.addWidget(b)
                else:
                    lbl = QLabel("—")
                    lbl.setProperty("cls", "st_none")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    cv.addWidget(lbl)
                grid.setCellWidget(i, s + 2, celda)
        grid.horizontalHeader().setStretchLastSection(True)
        grid.horizontalHeader().resizeSection(0, 80)
        grid.horizontalHeader().resizeSection(1, 220)
        grid.horizontalHeader().resizeSection(2, 90)
        for s in range(4):
            grid.horizontalHeader().resizeSection(s + 3, 120)
        self.card_grid.vbox.addWidget(grid)

        h = QLabel("Clic en una celda vencida/próxima/programada para registrar su ejecución: "
                   "el motor recalcula la próxima fecha (última ejecución + frecuencia) y el cumplimiento.")
        h.setProperty("cls", "hint")
        self.card_grid.vbox.addWidget(h)

        # ---- ejecuciones recientes
        self.card_grid.vbox.addSpacing(4)
        ejec = plan_tpm.ejecuciones_del_mes(self.conn)[:10]
        if ejec:
            titulo2 = QLabel("<b>Ejecuciones recientes</b>")
            titulo2.setTextFormat(Qt.TextFormat.RichText)
            self.card_grid.vbox.addWidget(titulo2)
            self.card_grid.vbox.addWidget(tabla(
                ["Fecha", "Máquina", "Actividad", "Responsable", "Observación"],
                [[e["fecha"], e["maquina"], e["actividad"], e["responsable"],
                  e["observacion"]] for e in ejec]))

    def _registrar(self, maquina: str, actividad: str, frecuencia_txt: str):
        if EjecucionDialog(maquina, actividad, frecuencia_txt, self).exec():
            self.shell.toast(f"Ejecución registrada — próxima de {maquina} recalculada")
            self.shell.refresh_all(excepto="plan")

    def _exportar_pdf(self):
        from PySide6.QtWidgets import QFileDialog
        from ..core import reportes
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar plan mensual", "plan_tpm.pdf", "PDF (*.pdf)")
        if not ruta:
            return
        reportes.pdf_plan(self.conn, ruta)
        self.shell.toast(f"Plan exportado: {ruta}")
