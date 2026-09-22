"""Página No conformidades: filtros, vistas rápidas, tabla y registro."""
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ..core import db, queries
from . import icons
from .theme import COLORS

DER = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class RegistroNCDialog(QDialog):
    """Formulario de registro rápido (~30 s): combos precargados, sin tipeo."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Registrar no conformidad")
        self.setMinimumWidth(430)

        form = QFormLayout(self)
        form.setSpacing(10)

        self.proceso = QComboBox(); self.proceso.addItems(db.PROCESOS)
        self.turno = QComboBox(); self.turno.addItems(db.TURNOS)
        self.causa = QComboBox()
        self.causa.addItem("— Mano de obra —")
        self.causa.addItems(db.CAUSAS_MANO_OBRA)
        self.causa.insertSeparator(self.causa.count())
        self.causa.addItem("— Máquinas —")
        self.causa.addItems(db.CAUSAS_MAQUINA)
        self.causa.insertSeparator(self.causa.count())
        self.causa.addItem("— Materiales —")
        self.causa.addItems(db.CAUSAS[4:])
        # por defecto una causa real (la primera)
        self.causa.setCurrentText(db.CAUSAS[0])

        self.defecto = QLineEdit()
        self.defecto.setPlaceholderText("Ej: manga menor al estándar (S), desfase de costura…")

        self.operario = QComboBox()
        self.operario.addItem("—")
        for row in conn.execute("SELECT nombre FROM operarios ORDER BY nombre"):
            self.operario.addItem(row["nombre"])

        self.maquina = QComboBox()
        self.maquina.addItem("—")
        for row in conn.execute("SELECT codigo FROM maquinas ORDER BY codigo"):
            self.maquina.addItem(row["codigo"])

        self.cantidad = QSpinBox()
        self.cantidad.setRange(1, 100_000)
        self.observacion = QLineEdit()
        self.observacion.setPlaceholderText("Opcional")

        form.addRow("Proceso *", self.proceso)
        form.addRow("Turno *", self.turno)
        form.addRow("Causa raíz (Tabla 6) *", self.causa)
        form.addRow("Defecto específico *", self.defecto)
        form.addRow("Operario", self.operario)
        form.addRow("Máquina", self.maquina)
        form.addRow("Cantidad de prendas *", self.cantidad)
        form.addRow("Observación", self.observacion)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._guardar)
        botones.rejected.connect(self.reject)
        form.addRow(botones)

    def _guardar(self):
        if not self.defecto.text().strip():
            QMessageBox.warning(self, "Falta dato", "Escribe el defecto específico.")
            return
        # descartar separadores del combo de causa
        causa = self.causa.currentText()
        if causa.startswith("—"):
            causa = db.CAUSAS[0]
        with self.conn:
            self.conn.execute(
                "INSERT INTO no_conformidades (fecha, turno, proceso, causa, defecto, "
                "operario, maquina, cantidad, observacion) VALUES (?,?,?,?,?,?,?,?,?)",
                (date.today().isoformat(), self.turno.currentText(),
                 self.proceso.currentText(), causa, self.defecto.text().strip(),
                 self.operario.currentText(), self.maquina.currentText(),
                 self.cantidad.value(), self.observacion.text().strip()))
        self.accept()


class NoConformidadesPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell):
        super().__init__()
        self.conn = conn
        self.shell = shell
        self.filtros = {"proceso": "", "turno": "", "causa": "", "desde": "", "hasta": ""}
        self.qf = "all"

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        # ------- barra de herramientas
        from .widgets import Card
        barra = Card()
        fila1 = QHBoxLayout()
        fila1.setSpacing(7)
        etiqueta = QLabel("Vistas rápidas:")
        etiqueta.setProperty("cls", "muted")
        fila1.addWidget(etiqueta)

        from PySide6.QtWidgets import QButtonGroup
        self.grupo_qf = QButtonGroup(self)
        self.grupo_qf.setExclusive(True)
        for clave, texto in [
            ("all", "Todas"),
            ("turno_costura", "Este turno · Costura"),
            ("hoy", "Hoy"),
            ("maquina", "Causa: máquinas"),
        ]:
            b = QPushButton(texto)
            b.setProperty("cls", "chipbtn")
            b.setCheckable(True)
            b.setChecked(clave == "all")
            b.clicked.connect(lambda _=False, c=clave: self._set_qf(c))
            self.grupo_qf.addButton(b)
            fila1.addWidget(b)
        fila1.addStretch(1)
        barra.vbox.addLayout(fila1)

        fila2 = QHBoxLayout()
        fila2.setSpacing(8)
        self.c_proceso = QComboBox()
        self.c_proceso.addItem("Proceso: todos")
        self.c_proceso.addItems(db.PROCESOS)
        self.c_proceso.currentTextChanged.connect(lambda t: self._set_filtro("proceso", t))
        self.c_turno = QComboBox()
        self.c_turno.addItem("Turno: todos")
        self.c_turno.addItems(db.TURNOS)
        self.c_turno.currentTextChanged.connect(lambda t: self._set_filtro("turno", t))
        self.c_causa = QComboBox()
        self.c_causa.addItem("Causa: todas")
        self.c_causa.addItems(db.CAUSAS)
        self.c_causa.currentTextChanged.connect(lambda t: self._set_filtro("causa", t))
        self.d_desde = QDateEdit()
        self.d_desde.setDisplayFormat("dd/MM/yyyy")
        self.d_desde.setCalendarPopup(True)
        self.d_desde.setProperty("cal", True)
        self.d_desde.setDate(date(2024, 1, 1))
        self.d_desde.dateChanged.connect(
            lambda d: self._set_filtro("desde", d.toString("yyyy-MM-dd")))
        self.d_hasta = QDateEdit()
        self.d_hasta.setDisplayFormat("dd/MM/yyyy")
        self.d_hasta.setCalendarPopup(True)
        self.d_hasta.setProperty("cal", True)
        self.d_hasta.setDate(date.today())
        self.d_hasta.dateChanged.connect(
            lambda d: self._set_filtro("hasta", d.toString("yyyy-MM-dd")))
        btn_nuevo = QPushButton("  Registrar no conformidad")
        btn_nuevo.setProperty("cls", "primary")
        btn_nuevo.setIcon(icons.icono("plus", "#FFFFFF", 15))
        btn_nuevo.clicked.connect(self._registrar)
        for w in (self.c_proceso, self.c_turno, self.c_causa, self.d_desde, self.d_hasta):
            fila2.addWidget(w)
        fila2.addStretch(1)
        fila2.addWidget(btn_nuevo)
        barra.vbox.addLayout(fila2)
        v.addWidget(barra)

        # ------- resumen
        self.resumen = QLabel()
        self.resumen.setProperty("cls", "muted")
        v.addWidget(self.resumen)

        # ------- tabla
        self.card_tabla = Card()
        v.addWidget(self.card_tabla, 1)

    def _set_qf(self, clave: str):
        self.qf = clave
        # las vistas rápidas ajustan los combos visibles
        if clave == "turno_costura":
            self.c_proceso.setCurrentText("Costura")
            self.c_turno.setCurrentText("Tarde")
        elif clave == "maquina":
            self.c_causa.setCurrentText(db.CAUSAS_MAQUINA[0])
        self.refresh()

    def _set_filtro(self, clave: str, valor: str):
        if valor and valor.startswith(("Proceso:", "Turno:", "Causa:")):
            valor = ""
        self.filtros[clave] = valor
        self.refresh()

    def _registrar(self):
        dlg = RegistroNCDialog(self.conn, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.shell.toast("No conformidad registrada — Pareto y tasa se recalculan al instante")
            self.shell.refresh_all(excepto="nc")

    def refresh(self):
        f = dict(self.filtros)
        if self.qf == "hoy":
            f["desde"] = f["hasta"] = date.today().isoformat()
        if self.qf == "turno_costura":
            f["proceso"], f["turno"] = "Costura", "Tarde"
        if self.qf == "maquina":
            f["causa"] = tuple(db.CAUSAS_MAQUINA)  # ambas causas de máquina

        condiciones, params = [], []
        if isinstance(f["causa"], tuple):
            condiciones.append("causa IN (?,?)")
            params.extend(f["causa"])
        elif f["causa"]:
            condiciones.append("causa = ?")
            params.append(f["causa"])
        for col in ("proceso", "turno"):
            if f[col]:
                condiciones.append(f"{col} = ?")
                params.append(f[col])
        for col in ("desde", "hasta"):
            if f[col]:
                condiciones.append(f"fecha {'>=' if col == 'desde' else '<='} ?")
                params.append(f[col])
        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
        filas = self.conn.execute(
            f"SELECT * FROM no_conformidades {where} ORDER BY fecha DESC, id DESC LIMIT 200",
            params).fetchall()

        total = sum(r["cantidad"] for r in filas)
        self.resumen.setText(
            f"<b>{len(filas)}</b> registros · <b>{total:,}</b> prendas NC "
            f"— el registro usa el catálogo de causas de la Tabla 6".replace(",", " "))

        from .widgets import tabla
        datos = [[
            r["fecha"], r["turno"], r["proceso"], r["causa"], r["defecto"],
            r["operario"], r["maquina"], (f"{r['cantidad']}", DER),
        ] for r in filas]
        nueva = tabla(["Fecha", "Turno", "Proceso", "Causa (Tabla 6)", "Defecto específico",
                       "Operario", "Máquina", "Cant."],
                      datos or [["—"] * 8])
        # reemplazar la tabla anterior
        while self.card_tabla.vbox.count():
            item = self.card_tabla.vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.card_tabla.vbox.addWidget(nueva)
