"""Página Checklists: QR por estación, servidor LAN y cumplimiento del día."""
from __future__ import annotations

import io
import sqlite3

import qrcode
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..core import checklists, db
from ..web.servidor import ServidorLAN
from . import icons
from .charts import DonutWidget
from .theme import COLORS
from .widgets import Card, tabla


def _qr_pixmap(url: str, tam: int = 190) -> QPixmap:
    img = qrcode.make(url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    pm = QPixmap()
    pm.loadFromData(buf.getvalue())
    return pm.scaled(tam, tam, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)


class DetalleChecklistDialog(QDialog):
    """Detalle de un checklist recibido, con acceso a las fotos de evidencia."""

    def __init__(self, conn: sqlite3.Connection, checklist_id: int, parent=None):
        super().__init__(parent)
        from .tarjetas_page import _abrir_foto

        c = conn.execute("SELECT * FROM checklists WHERE id = ?", (checklist_id,)).fetchone()
        self.setWindowTitle(f"Checklist #{checklist_id:04d} · {c['maquina']}")
        self.setMinimumWidth(560)

        v = QVBoxLayout(self)
        info = QLabel(
            f"<b>{c['maquina']}</b> · {c['turno']} · {c['operario']} · "
            f"{c['fecha']} {c['creada_en'][11:16] if c['creada_en'] else ''}")
        v.addWidget(info)
        v.addSpacing(6)

        items = conn.execute(
            "SELECT ci.*, t.id AS tarjeta FROM checklist_items ci "
            "LEFT JOIN tarjetas_tpm t ON t.checklist_id = ci.checklist_id "
            "AND ci.estado = 'falla' "
            "WHERE ci.checklist_id = ? ORDER BY ci.id", (checklist_id,)).fetchall()
        for it in items:
            fila = QHBoxLayout()
            marca = ("✔" if it["estado"] == "ok" else "⚠")
            color = ("#15803D" if it["estado"] == "ok" else "#B91C1C")
            etiqueta = QLabel(f"<span style='color:{color};font-weight:800'>{marca}</span>"
                              f"&nbsp; {it['item']}"
                              + (f" &nbsp;<span style='background:#FEF3C7;color:#B45309;"
                                 f"font-size:10px;font-weight:800;padding:2px 8px;"
                                 f"border-radius:6px'>{it['severidad']}</span>"
                                 if it["severidad"] else ""))
            etiqueta.setTextFormat(Qt.TextFormat.RichText)
            etiqueta.setWordWrap(True)
            fila.addWidget(etiqueta, 1)
            if it["foto"]:
                b = QPushButton("  Evidencia")
                b.setProperty("cls", "ghost")
                b.setIcon(icons.icono("camera", COLORS["teal"], 14))
                b.clicked.connect(lambda _=False, r=it["foto"]: _abrir_foto(r))
                fila.addWidget(b)
            wrap = QWidget()
            wrap.setLayout(fila)
            v.addWidget(wrap)

        cerrar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cerrar.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        cerrar.rejected.connect(self.reject)
        cerrar.accepted.connect(self.accept)
        v.addWidget(cerrar)


class ChecklistsPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell, servidor: ServidorLAN):
        super().__init__()
        self.conn = conn
        self.shell = shell
        self.servidor = servidor

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)

        # ---------------- banner
        banner = Card()
        banner.setProperty("cls", "banner")
        txt = QLabel(
            "El operario escanea el QR de su estación y el checklist se abre en su celular "
            "(misma red wifi de planta, servida por este PC). Nada de papel: si un ítem falla, "
            "pide foto de evidencia y genera la Tarjeta TPM automáticamente. "
            "Equivale a las Figuras 38, 39 y 51 de la tesis.")
        txt.setProperty("cls", "banner_txt")
        txt.setWordWrap(True)
        banner.vbox.addWidget(txt)
        v.addWidget(banner)

        fila = QHBoxLayout()
        fila.setSpacing(14)

        # ---------------- columna izquierda: QR + servidor
        col_izq = QVBoxLayout()
        col_izq.setSpacing(14)

        c_qr = Card("QR de estación", "imprimible")
        self.combo_estacion = QComboBox()
        for r in conn.execute("SELECT codigo, tipo, area FROM maquinas ORDER BY codigo"):
            self.combo_estacion.addItem(f"{r['codigo']} · {r['tipo']} ({r['area']})", r["codigo"])
        self.combo_estacion.currentIndexChanged.connect(self._actualizar_qr)
        c_qr.vbox.addWidget(self.combo_estacion)

        self.lbl_qr = QLabel()
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_qr.vbox.addWidget(self.lbl_qr, 1)

        self.lbl_url = QLabel()
        self.lbl_url.setProperty("cls", "url")
        self.lbl_url.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_qr.vbox.addWidget(self.lbl_url)

        b_imprimir = QPushButton("  Imprimir QR de la estación")
        b_imprimir.setProperty("cls", "ghost")
        b_imprimir.setIcon(icons.icono("printer", COLORS["teal"], 15))
        b_imprimir.clicked.connect(self._imprimir_qr)
        c_qr.vbox.addWidget(b_imprimir)
        col_izq.addWidget(c_qr)

        c_servidor = Card("Servidor para celulares", "wifi de planta")
        fila_estado = QHBoxLayout()
        self.dot = QLabel()
        self.dot.setFixedSize(10, 10)
        self.lbl_estado = QLabel("Servidor detenido")
        self.lbl_estado.setProperty("cls", "muted")
        fila_estado.addWidget(self.dot)
        fila_estado.addWidget(self.lbl_estado)
        fila_estado.addStretch(1)
        self.btn_power = QPushButton("  Iniciar")
        self.btn_power.setProperty("cls", "primary")
        self.btn_power.setIcon(icons.icono("power", "#FFFFFF", 15))
        self.btn_power.clicked.connect(self._alternar_servidor)
        fila_estado.addWidget(self.btn_power)
        c_servidor.vbox.addLayout(fila_estado)
        h = QLabel("Mientras esté activo, los celulares conectados al mismo wifi pueden "
                   "abrir los checklists escaneando los QR. En planta: abrir el puerto 8080 "
                   "en el firewall de Windows la primera vez.")
        h.setProperty("cls", "hint"); h.setWordWrap(True)
        c_servidor.vbox.addWidget(h)
        col_izq.addWidget(c_servidor)
        col_izq.addStretch(1)
        fila.addLayout(col_izq, 2)

        # ---------------- columna derecha: cumplimiento + recientes
        col_der = QVBoxLayout()
        col_der.setSpacing(14)

        c_cumple = Card("Cumplimiento de checklists · hoy", "Meta ≥ 85% · Tabla 21")
        fila_donut = QHBoxLayout()
        fila_donut.setSpacing(22)
        self.donut = DonutWidget()
        fila_donut.addWidget(self.donut)
        stats = QVBoxLayout()
        stats.setSpacing(9)
        self.lbl_stats = QLabel()
        self.lbl_stats.setTextFormat(Qt.TextFormat.RichText)
        stats.addWidget(self.lbl_stats)
        stats.addStretch(1)
        fila_donut.addLayout(stats, 1)
        c_cumple.vbox.addLayout(fila_donut)
        col_der.addWidget(c_cumple)

        self.card_recientes = Card("Últimos checklists recibidos")
        col_der.addWidget(self.card_recientes, 1)
        fila.addLayout(col_der, 3)

        v.addLayout(fila, 1)

    # ------------------------------------------------ acciones
    def _estacion(self) -> str:
        return self.combo_estacion.currentData() or "RECT-05"

    def _actualizar_qr(self):
        url = (self.servidor.url_estacion(self._estacion())
               if self.servidor.activo else f"http://<IP-de-este-PC>:8080/{self._estacion()}")
        self.lbl_qr.setPixmap(_qr_pixmap(url))
        self.lbl_url.setText(url)

    def _imprimir_qr(self):
        url = (self.servidor.url_estacion(self._estacion())
               if self.servidor.activo else f"http://IP-DEL-PC:8080/{self._estacion()}")
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar QR", f"qr_{self._estacion()}.png", "Imagen PNG (*.png)")
        if not ruta:
            return
        img = qrcode.make(url, box_size=12, border=3)
        img.save(ruta)
        self.shell.toast(f"QR guardado: {ruta} — listo para imprimir y pegar en la máquina")

    def _alternar_servidor(self):
        if self.servidor.activo:
            self.servidor.detener()
            self.shell.toast("Servidor detenido — los celulares ya no podrán abrir checklists", "warn")
        else:
            try:
                url = self.servidor.iniciar()
                self.shell.toast(f"Servidor activo en {url} — escanea el QR desde el celular")
            except OSError as e:
                self.shell.toast(f"No se pudo iniciar el servidor: {e}", "warn")
        self._pintar_estado()
        self._actualizar_qr()

    def _detalle(self, recientes: list[dict], fila: int):
        r = recientes[fila]
        DetalleChecklistDialog(self.conn, r["id"], self).exec()

    def _pintar_estado(self):
        if self.servidor.activo:
            self.dot.setProperty("cls", "dot_ok")
            self.lbl_estado.setText(f"Activo · {self.servidor.url_base()}")
            self.btn_power.setText("  Detener")
            self.btn_power.setProperty("cls", "ghost")
        else:
            self.dot.setProperty("cls", "dot_off")
            self.lbl_estado.setText("Servidor detenido")
            self.btn_power.setText("  Iniciar")
            self.btn_power.setProperty("cls", "primary")
        for w in (self.dot, self.btn_power):
            w.style().unpolish(w)
            w.style().polish(w)
        icono = icons.icono("power", "#FFFFFF" if not self.servidor.activo else COLORS["slate"], 15)
        self.btn_power.setIcon(icono)

    # ------------------------------------------------ refresco
    def refresh(self):
        self._pintar_estado()
        self._actualizar_qr()

        c = checklists.cumplimiento_hoy(self.conn)
        m = {r["indicador"]: r["to_be"] for r in self.conn.execute("SELECT indicador, to_be FROM metas")}
        meta = m.get("Cumplimiento de checklists", 85.0)
        self.donut.set_datos(c["pct"], meta)

        fallas_hoy = self.conn.execute(
            "SELECT COUNT(*) FROM checklist_items ci JOIN checklists c ON c.id = ci.checklist_id "
            "WHERE ci.estado = 'falla' AND c.fecha = ?", (c["hoy"],)).fetchone()[0]
        tarj_hoy = self.conn.execute(
            "SELECT COUNT(*) FROM tarjetas_tpm WHERE date(creada_en) = ?", (c["hoy"],)).fetchone()[0]
        en_meta = c["pct"] >= meta
        estado_txt = ("✔ en meta" if en_meta
                      else f"faltan {meta - c['pct']:.0f} pts para la meta")
        self.lbl_stats.setText(
            f"<span style='font-size:19px;font-weight:800'>{c['hechas']} / {c['total']}</span>"
            f"&nbsp;&nbsp;<span style='color:#64748B'>estaciones completadas hoy</span><br>"
            f"<span style='font-size:19px;font-weight:800'>{fallas_hoy}</span>"
            f"&nbsp;&nbsp;<span style='color:#64748B'>ítems con falla declarada</span><br>"
            f"<span style='font-size:19px;font-weight:800'>{tarj_hoy}</span>"
            f"&nbsp;&nbsp;<span style='color:#64748B'>tarjetas TPM generadas hoy</span><br>"
            f"<span style='color:{'#15803D' if en_meta else '#B45309'};font-weight:800'>{estado_txt}</span>")

        recientes = checklists.checklists_recientes(self.conn, 15)
        filas = []
        for r in recientes:
            resultado = ("<span style='color:#15803D;font-weight:700'>Sin fallas</span>"
                         if not r["fallas"] else
                         f"<span style='color:#B91C1C;font-weight:700'>{r['fallas']} falla(s) → {r['tarjeta']}</span>")
            filas.append([
                f"<b>#{r['id']:04d}</b>", r["maquina"], r["operario"], r["turno"],
                r["creada_en"][11:16] if r["creada_en"] else "", f"{r['items'] - r['fallas']}/{r['items']}",
                resultado,
            ])
        nueva = tabla(["#", "Estación", "Operario", "Turno", "Hora", "Ítems", "Resultado"],
                      filas or [["—"] * 7])
        nueva.cellDoubleClicked.connect(lambda f, _c: self._detalle(recientes, f))
        h = QLabel("Doble clic sobre un checklist para ver su detalle y las fotos de evidencia.")
        h.setProperty("cls", "hint")
        self.card_recientes.vbox.addWidget(h)
        while self.card_recientes.vbox.count():
            item = self.card_recientes.vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;}")
        contenido = QWidget()
        lay = QVBoxLayout(contenido)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(nueva)
        scroll.setWidget(contenido)
        self.card_recientes.vbox.addWidget(scroll)
