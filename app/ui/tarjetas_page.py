"""Página Tarjetas TPM: kanban Abiertas / En atención / Cerradas (Etapa 6)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..core import checklists
from . import icons
from .theme import COLORS
from .widgets import Card, vaciar_layout


def _abrir_foto(ruta: str):
    """Abre la evidencia con el visor de imágenes del sistema."""
    if not ruta:
        return
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))

COLUMNAS = [
    ("abierta", "Abiertas"),
    ("atencion", "En atención"),
    ("cerrada", "Cerradas"),
]


def _badges(t: dict) -> str:
    return (f"<span style='background:{COLORS['purple_soft']};color:#6D28D9;"
            f"font-size:9.5px;font-weight:800;padding:2px 8px;border-radius:6px'>{t['tipo']}</span> "
            f"<span style='background:{COLORS['amber_soft'] if t['severidad'] == 'Moderada' else '#E0F2FE' if t['severidad'] == 'Leve' else COLORS['red_soft']};"
            f"color:{'#B45309' if t['severidad'] == 'Moderada' else '#0369A1' if t['severidad'] == 'Leve' else '#B91C1C'};"
            f"font-size:9.5px;font-weight:800;padding:2px 8px;border-radius:6px'>{t['severidad']}</span>")


class DetalleTarjetaDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, tarjeta_id: int, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.t = checklists.detalle_tarjeta(conn, tarjeta_id)
        self.setWindowTitle(f"{checklists.codigo_tarjeta(tarjeta_id)} · {self.t['tipo']}")
        self.setMinimumWidth(470)

        v = QVBoxLayout(self)
        cab = QLabel(_badges(self.t))
        v.addWidget(cab)
        v.addSpacing(8)

        ficha = QLabel(
            f"<table cellpadding='4'>"
            f"<tr><td color='#64748B'>Máquina</td><td><b>{self.t['maquina']}</b></td>"
            f"<td width='18'></td><td color='#64748B'>Origen</td><td><b>{self.t['origen']}</b></td></tr>"
            f"<tr><td color='#64748B'>Responsable</td><td><b>{self.t['responsable']}</b></td>"
            f"<td></td><td color='#64748B'>Estado</td><td><b>{self.t['estado']}</b></td></tr>"
            f"<tr><td color='#64748B'>Creada</td><td colspan='4'>{self.t['creada_en']}</td></tr>"
            f"</table>")
        v.addWidget(ficha)

        desc = QPlainTextEdit(self.t["descripcion"])
        desc.setReadOnly(True)
        desc.setMaximumHeight(84)
        v.addWidget(desc)

        accion = checklists.ACCION_SEGUN_SEVERIDAD[self.t["severidad"]]
        nota = QLabel(f"Acción requerida según tesis (Etapa 6 TPM): <b>{accion}</b>"
                      + (" · con foto de evidencia adjunta" if self.t["origen"] == "Checklist" else ""))
        nota.setProperty("cls", "hint")
        nota.setWordWrap(True)
        v.addWidget(nota)

        # evidencia fotográfica (tarjetas nacidas de un checklist)
        if self.t["origen"] == "Checklist" and self.t["checklist_id"]:
            fotos = self.conn.execute(
                "SELECT item, foto FROM checklist_items "
                "WHERE checklist_id = ? AND estado = 'falla' AND foto != ''",
                (self.t["checklist_id"],)).fetchall()
            for f in fotos:
                b = QPushButton(f"  Ver foto de evidencia — {f['item'][:44]}")
                b.setProperty("cls", "ghost")
                b.setIcon(icons.icono("camera", COLORS["teal"], 15))
                b.clicked.connect(lambda _=False, r=f["foto"]: _abrir_foto(r))
                v.addWidget(b)

        botones = QDialogButtonBox()
        if self.t["estado"] == "abierta":
            b_tomar = botones.addButton("Tomar (en atención)", QDialogButtonBox.ButtonRole.AcceptRole)
            b_tomar.clicked.connect(self._tomar)
        if self.t["estado"] != "cerrada":
            b_cerrar = botones.addButton("Cerrar tarjeta", QDialogButtonBox.ButtonRole.DestructiveRole)
            b_cerrar.setStyleSheet(f"color:{COLORS['red']};font-weight:700")
            b_cerrar.clicked.connect(self._cerrar)
        b_volver = botones.addButton("Volver", QDialogButtonBox.ButtonRole.RejectRole)
        b_volver.clicked.connect(self.reject)
        v.addWidget(botones)

    def _tomar(self):
        checklists.cambiar_estado_tarjeta(self.conn, self.t["id"], "atencion", "Téc. Mendoza")
        self.accept()

    def _cerrar(self):
        checklists.cambiar_estado_tarjeta(self.conn, self.t["id"], "cerrada", "Téc. Mendoza")
        self.accept()


class NuevaTarjetaDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Registrar anomalía (tarjeta TPM)")
        self.setMinimumWidth(440)

        form = QFormLayout(self)
        self.tipo = QComboBox(); self.tipo.addItems(checklists.TIPOS_TARJETA)
        self.severidad = QComboBox(); self.severidad.addItems(checklists.SEVERIDADES)
        self.severidad.setCurrentText("Moderada")
        self.maquina = QComboBox()
        for r in conn.execute("SELECT codigo FROM maquinas ORDER BY codigo"):
            self.maquina.addItem(r["codigo"])
        self.descripcion = QPlainTextEdit()
        self.descripcion.setPlaceholderText("Ej: ruido anormal al arrancar, protector retirado…")

        form.addRow("Tipo", self.tipo)
        form.addRow("Severidad", self.severidad)
        form.addRow("Máquina / estación", self.maquina)
        form.addRow("Descripción *", self.descripcion)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Crear tarjeta")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._crear)
        botones.rejected.connect(self.reject)
        form.addRow(botones)

    def _crear(self):
        if not self.descripcion.toPlainText().strip():
            self.descripcion.setFocus()
            return
        checklists.crear_tarjeta_manual(
            self.conn, self.tipo.currentText(), self.severidad.currentText(),
            self.maquina.currentText(), self.descripcion.toPlainText().strip())
        self.accept()


class TarjetasPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell):
        super().__init__()
        self.conn = conn
        self.shell = shell
        self.filtro_origen = ""

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        # ---------------- barra
        barra = Card()
        fila = QHBoxLayout()
        fila.setSpacing(7)
        etiqueta = QLabel("Origen:")
        etiqueta.setProperty("cls", "muted")
        fila.addWidget(etiqueta)
        for texto, clave in [("Todos", ""), ("Checklist", "Checklist"),
                             ("IoT", "IoT"), ("Manual", "Manual"), ("Semilla", "semilla")]:
            b = QPushButton(texto)
            b.setProperty("cls", "chipbtn")
            b.setCheckable(True)
            b.setChecked(clave == "")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=clave: self._filtrar(c))
            fila.addWidget(b)
        fila.addStretch(1)
        btn_nueva = QPushButton("  Registrar anomalía")
        btn_nueva.setProperty("cls", "primary")
        btn_nueva.setIcon(icons.icono("plus", "#FFFFFF", 15))
        btn_nueva.clicked.connect(self._nueva)
        fila.addWidget(btn_nueva)
        barra.vbox.addLayout(fila)
        v.addWidget(barra)

        # ---------------- kanban (envuelto en tarjeta blanca)
        contenedor = Card()
        self.kan_layout = QHBoxLayout()
        self.kan_layout.setContentsMargins(0, 0, 0, 0)
        self.kan_layout.setSpacing(14)
        contenedor.vbox.addLayout(self.kan_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;}")
        scroll.setWidget(contenedor)
        v.addWidget(scroll, 1)

    def _filtrar(self, clave: str):
        self.filtro_origen = clave
        self.refresh()

    def _nueva(self):
        if NuevaTarjetaDialog(self.conn, self).exec() == QDialog.DialogCode.Accepted:
            self.shell.toast("Tarjeta TPM creada")
            self.shell.refresh_all(excepto="tpm")

    def _detalle(self, tarjeta_id: int):
        if DetalleTarjetaDialog(self.conn, tarjeta_id, self).exec():
            self.shell.toast("Tarjeta actualizada — MTTR recalculado")
            self.shell.refresh_all(excepto="tpm")

    def refresh(self):
        vaciar_layout(self.kan_layout)

        por_estado = checklists.tarjetas_por_estado(self.conn)
        for estado, titulo in COLUMNAS:
            col = QWidget()
            col.setProperty("cls", "kcol")
            col_v = QVBoxLayout(col)
            col_v.setContentsMargins(10, 10, 10, 10)
            col_v.setSpacing(8)

            encabezado = QHBoxLayout()
            t = QLabel(titulo)
            t.setStyleSheet("font-size:13px;font-weight:800;background:transparent;")
            n = QLabel(str(len(por_estado[estado])))
            n.setStyleSheet("font-size:11px;font-weight:800;background:#fff;"
                            "border-radius:10px;padding:1px 9px;color:#64748B;")
            encabezado.addWidget(t)
            encabezado.addStretch(1)
            encabezado.addWidget(n)
            col_v.addLayout(encabezado)

            tarjetas = por_estado[estado]
            if self.filtro_origen == "semilla":
                tarjetas = [t2 for t2 in tarjetas if t2["origen"] == "Checklist" or t2["origen"] == "Manual"]
            elif self.filtro_origen:
                tarjetas = [t2 for t2 in tarjetas if t2["origen"] == self.filtro_origen]

            if not tarjetas:
                vacio = QLabel("Sin tarjetas.")
                vacio.setProperty("cls", "muted")
                col_v.addWidget(vacio)
            for t in tarjetas[:30]:
                tarjeta = self._card(t)
                col_v.addWidget(tarjeta)
            col_v.addStretch(1)

            scroll_col = QScrollArea()
            scroll_col.setWidgetResizable(True)
            scroll_col.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll_col.setStyleSheet("QScrollArea{background:transparent;}")
            scroll_col.setWidget(col)
            self.kan_layout.addWidget(scroll_col, 1)

    def _card(self, t: dict) -> QWidget:
        card = QWidget()
        card.setProperty("cls", "kcard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setMinimumWidth(230)
        v = QVBoxLayout(card)
        v.setContentsMargins(11, 10, 11, 10)
        v.setSpacing(6)

        r1 = QLabel(f"<b style='color:#64748B;font-size:10.5px'>{checklists.codigo_tarjeta(t['id'])}</b>")
        r1.setTextFormat(Qt.TextFormat.RichText)
        fila1 = QHBoxLayout()
        fila1.addWidget(r1)
        fila1.addStretch(1)
        fila1.addWidget(QLabel(_badges(t)))
        v.addLayout(fila1)

        desc = QLabel(t["descripcion"])
        desc.setProperty("cls", "kcard_title")
        desc.setWordWrap(True)
        v.addWidget(desc)

        meta = QLabel(f"{t['maquina']} · {t['origen']} · "
                      f"{t['creada_en'][5:16] if t['creada_en'] else ''}")
        meta.setProperty("cls", "hint")
        v.addWidget(meta)

        def abrir(_=False, tid=t["id"]):
            self._detalle(tid)
        card.mousePressEvent = abrir
        return card
