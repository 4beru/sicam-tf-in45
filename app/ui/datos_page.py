"""Página Datos: plantilla Excel, importador con dry-run, exportación y semilla."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from ..core import db, importador, plantilla, seed
from . import icons
from .theme import COLORS
from .widgets import Card, tabla, vaciar_layout


class DatosPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell):
        super().__init__()
        self.conn = conn
        self.shell = shell

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)

        # ---------------- banner
        banner = Card()
        banner.setProperty("cls", "banner")
        txt = QLabel(
            "La empresa no abandona Excel de un día para otro: el sistema lo absorbe. "
            "Descarga la plantilla, llénala como cualquier tabla y el importador la valida "
            "completa ANTES de tocar la base de datos. Reimportar no duplica: las filas se "
            "actualizan por su clave.")
        txt.setProperty("cls", "banner_txt")
        txt.setWordWrap(True)
        banner.vbox.addWidget(txt)
        v.addWidget(banner)

        fila = QHBoxLayout()
        fila.setSpacing(14)

        # ---------------- plantilla + exportar
        col1 = QVBoxLayout()
        col1.setSpacing(14)

        c_plantilla = Card("Plantilla de carga", "XLSX con listas desplegables")
        b1 = QPushButton("  Descargar plantilla")
        b1.setProperty("cls", "primary")
        b1.setIcon(icons.icono("download", "#FFFFFF", 15))
        b1.clicked.connect(self._descargar_plantilla)
        c_plantilla.vbox.addWidget(b1)
        h1 = QLabel("Una hoja por tabla: maquinas, operarios, produccion, no_conformidades, "
                    "frecuencias y metas. Columnas con desplegable para que sea imposible "
                    "escribir una causa con otra ortografía.")
        h1.setProperty("cls", "hint"); h1.setWordWrap(True)
        c_plantilla.vbox.addWidget(h1)
        col1.addWidget(c_plantilla)

        c_export = Card("Exportar a Excel", "bidireccional")
        b2 = QPushButton("  Exportar no conformidades")
        b2.setProperty("cls", "ghost")
        b2.setIcon(icons.icono("sheet", COLORS["teal"], 15))
        b2.clicked.connect(self._exportar)
        c_export.vbox.addWidget(b2)
        h2 = QLabel("El registro de NC se exporta con las mismas columnas de la plantilla: "
                    "lo que sale del sistema puede volver a entrar sin fricción.")
        h2.setProperty("cls", "hint"); h2.setWordWrap(True)
        c_export.vbox.addWidget(h2)
        col1.addWidget(c_export)

        c_semilla = Card("Datos sintéticos", "línea base de la tesis")
        self.lbl_semilla = QLabel()
        self.lbl_semilla.setProperty("cls", "muted"); self.lbl_semilla.setWordWrap(True)
        c_semilla.vbox.addWidget(self.lbl_semilla)
        b3 = QPushButton("  Restablecer semilla 2024 + piloto")
        b3.setProperty("cls", "ghost")
        b3.setIcon(icons.icono("refresh", COLORS["teal"], 15))
        b3.clicked.connect(self._resembrar)
        c_semilla.vbox.addWidget(b3)
        col1.addWidget(c_semilla)
        col1.addStretch(1)
        fila.addLayout(col1, 1)

        # ---------------- importar + historial
        col2 = QVBoxLayout()
        col2.setSpacing(14)

        c_import = Card("Importar plantilla", "validación en seco (dry-run)")
        b4 = QPushButton("  Seleccionar archivo…")
        b4.setProperty("cls", "primary")
        b4.setIcon(icons.icono("upload", "#FFFFFF", 15))
        b4.clicked.connect(self._importar)
        c_import.vbox.addWidget(b4)
        h3 = QLabel("1) valida todas las hojas · 2) te muestra filas con error (fila y motivo exactos) "
                    "sin tocar nada · 3) solo cuando todo está limpio, importa con upsert.")
        h3.setProperty("cls", "hint"); h3.setWordWrap(True)
        c_import.vbox.addWidget(h3)
        col2.addWidget(c_import)

        self.card_hist = Card("Historial de importaciones")
        col2.addWidget(self.card_hist, 1)
        fila.addLayout(col2, 2)

        v.addLayout(fila, 1)

    # ------------------------------------------------ acciones
    def _descargar_plantilla(self):
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar plantilla", "plantilla_sicam.xlsx", "Excel (*.xlsx)")
        if not ruta:
            return
        try:
            plantilla.generar_plantilla(ruta)
            self.shell.toast(f"Plantilla generada: {ruta}")
        except Exception as e:  # noqa: BLE001 — se reporta al usuario tal cual
            QMessageBox.critical(self, "Error", f"No se pudo generar la plantilla:\n{e}")

    def _exportar(self):
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar no conformidades", "no_conformidades.xlsx", "Excel (*.xlsx)")
        if not ruta:
            return
        n = plantilla.exportar_no_conformidades(self.conn, ruta)
        self.shell.toast(f"Exportadas {n} filas a {ruta}")

    def _importar(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar plantilla", "", "Excel (*.xlsx)")
        if not ruta:
            return
        try:
            datos = importador.leer(ruta)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Archivo no legible", str(e))
            return
        if not datos:
            QMessageBox.information(self, "Sin datos",
                                    "El archivo no contiene filas en ninguna hoja de la plantilla.")
            return

        val = importador.validar(datos, self.conn)
        if not val.ok:
            importador.registrar_importacion(self.conn, ruta, 0, len(val.errores), "con errores")
            self._dialogo_errores(ruta, val.errores)
            self.refresh()
            return

        if not self._dialogo_confirmar(ruta, datos):
            return
        res = importador.importar(self.conn, datos)
        total = sum(n + a for n, a in res.resumen.values())
        importador.registrar_importacion(self.conn, ruta, total, 0, "importado")
        self.shell.toast(f"Importación completa: {total} filas (nuevas + actualizadas)")
        self.shell.refresh_all(excepto="datos")
        self.refresh()

    def _dialogo_errores(self, ruta: str, errores: list[importador.FilaError]):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Validación con errores — no se importó nada")
        dlg.resize(760, 420)
        v = QVBoxLayout(dlg)
        intro = QLabel(
            f"Se encontraron <b>{len(errores)}</b> problemas en “{ruta.split('/')[-1]}”. "
            "La base de datos no fue modificada. Corrige las filas indicadas y vuelve a intentar.")
        intro.setWordWrap(True)
        v.addWidget(intro)
        v.addWidget(tabla(
            ["Hoja", "Fila", "Columna", "Detalle"],
            [list(e.como_fila()) for e in errores[:200]]))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        v.addWidget(bb)
        dlg.exec()

    def _dialogo_confirmar(self, ruta: str, datos: dict) -> bool:
        dlg = QDialog(self)
        dlg.setWindowTitle("Importación validada")
        dlg.setMinimumWidth(420)
        v = QVBoxLayout(dlg)
        resumen = "<br>".join(
            f"• <b>{hoja}</b>: {len(filas)} filas" for hoja, filas in datos.items())
        lbl = QLabel(f"El archivo pasó la validación completa:<br><br>{resumen}<br><br>"
                     "¿Importar ahora? Las filas repetidas se actualizarán, no se duplicarán.")
        lbl.setWordWrap(True)
        v.addWidget(lbl)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        bb.button(QDialogButtonBox.StandardButton.Yes).setText("Importar")
        bb.button(QDialogButtonBox.StandardButton.No).setText("Cancelar")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        return dlg.exec() == QDialog.DialogCode.Accepted

    def _resembrar(self):
        if QMessageBox.question(
                self, "Restablecer datos sintéticos",
                "Esto BORRA todos los datos actuales y vuelve a generar la línea base 2024 "
                "+ piloto sintético. ¿Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        seed.siembra(self.conn, reset=True)
        self.shell.toast("Semilla restablecida: 2024 + piloto regenerados")
        self.shell.refresh_all(excepto="datos")
        self.refresh()

    # ------------------------------------------------ refresco
    def refresh(self):
        c = db.contar(self.conn)
        self.lbl_semilla.setText(
            f"Contenido actual: {c['no_conformidades']:,} registros NC · "
            f"{c['produccion']:,} de producción · {c['maquinas']} máquinas · "
            f"{c['operarios']} operarios".replace(",", " "))

        filas = self.conn.execute(
            "SELECT fecha, archivo, filas_ok, filas_error, estado FROM importaciones "
            "ORDER BY id DESC LIMIT 20").fetchall()
        datos = [[r["fecha"], (r["archivo"] or "").split("/")[-1],
                  f"{r['filas_ok']}", f"{r['filas_error']}",
                  r["estado"]] for r in filas]
        nueva = tabla(["Fecha", "Archivo", "Filas OK", "Con error", "Estado"],
                      datos or [["—", "—", "—", "—", "—"]])
        vaciar_layout(self.card_hist.vbox)
        self.card_hist.vbox.addWidget(nueva)
