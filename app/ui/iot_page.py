"""Página Monitor IoT: gauges en vivo, gráfico de línea y alertas (Fig. 47).

Replica la sección MONITOR IoT de la maqueta HTML: 4 gauges de 270°, un
gráfico de línea de la última hora, el registro de alertas y los umbrales
configurables. Un QTimer genera lecturas simuladas cada 2 s cuando el
simulador está activo y repinta siempre para ver las lecturas ESP32 en vivo.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..core import iot
from .charts import GaugeWidget, LineaEnVivoWidget
from .theme import COLORS
from .widgets import Card, chip, vaciar_layout

ETIQUETAS = {
    "tension": "Tensión de hilo",
    "velocidad": "Velocidad",
    "temperatura": "Temperatura",
    "vibracion": "Vibración",
}


def _hhmm(ts) -> str:
    s = str(ts or "")
    if "T" in s:
        return s.split("T")[1][:5]
    if " " in s:
        return s.split(" ")[1][:5]
    return s[:5] if len(s) >= 5 else (s or "—")


def _estado_chip(nivel: str) -> tuple[str, str]:
    if nivel == "ok":
        return "Normal", "good"
    if nivel == "A":
        return "Alerta A", "warn"
    if nivel == "C":
        return "Alerta C", "bad"
    return "Alerta D", "bad"


class IotPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell):
        super().__init__()
        self.conn = conn
        self.shell = shell
        self._maquina_actual = "RECT-05"

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)

        # ---------------- cabecera (máquina + simulador + botones de simulación)
        self.cabecera = Card()
        v.addWidget(self.cabecera)
        self._construir_cabecera()

        # ---------------- fila de 4 gauges
        self.fila_gauges = QHBoxLayout()
        self.fila_gauges.setSpacing(12)
        v.addLayout(self.fila_gauges)
        self._gauges: dict[str, dict] = {}
        self._construir_gauges()

        # ---------------- gráfico en vivo + registro de alertas
        fila = QHBoxLayout()
        fila.setSpacing(14)
        self.card_chart = Card("Última hora · en vivo", "Fig. 47")
        self._construir_chart()
        fila.addWidget(self.card_chart, 1)

        self.card_alertas = Card("Registro de alertas", "Fig. 47")
        self.alert_cuerpo = QVBoxLayout()
        self.alert_cuerpo.setSpacing(8)
        self.card_alertas.vbox.addLayout(self.alert_cuerpo)
        self.card_alertas.vbox.addStretch(1)
        fila.addWidget(self.card_alertas, 1)
        v.addLayout(fila, 1)

        # ---------------- umbrales configurables
        self.card_umbrales = Card("Umbrales IoT", "Fig. 47 · configurables")
        self._spin_umbrales: dict[tuple[str, str], QDoubleSpinBox] = {}
        self._construir_umbrales()
        v.addWidget(self.card_umbrales)

        # ---------------- timer de simulación / repintado en vivo
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ------------------------------------------------ construcción única
    def _construir_cabecera(self):
        fila = QHBoxLayout()
        fila.setSpacing(10)
        etiqueta = QLabel("Máquina")
        etiqueta.setProperty("cls", "muted")
        fila.addWidget(etiqueta)

        self.combo_maquinas = QComboBox()
        for r in self.conn.execute("SELECT codigo FROM maquinas ORDER BY codigo"):
            self.combo_maquinas.addItem(r["codigo"])
        idx = self.combo_maquinas.findText("RECT-05")
        if idx >= 0:
            self.combo_maquinas.setCurrentIndex(idx)
        self._maquina_actual = self.combo_maquinas.currentText()
        self.combo_maquinas.currentTextChanged.connect(self._cambiar_maquina)
        fila.addWidget(self.combo_maquinas)

        self.btn_sim = QPushButton("Simulador activo")
        self.btn_sim.setProperty("cls", "chipbtn")
        self.btn_sim.setCheckable(True)
        self.btn_sim.setChecked(True)
        self.btn_sim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sim.setToolTip("Genera lecturas simuladas cada 2 s")
        fila.addWidget(self.btn_sim)

        self.btn_c = QPushButton("Simular alerta C")
        self.btn_c.setProperty("cls", "ghost")
        self.btn_c.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_c.setToolTip("Inyecta vibración sobre el umbral C en la máquina seleccionada")
        self.btn_c.clicked.connect(self._simular_c)
        fila.addWidget(self.btn_c)

        self.btn_d = QPushButton("Simular alerta D")
        self.btn_d.setProperty("cls", "ghost")
        self.btn_d.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_d.setToolTip("Inyecta evento de prenda no conforme (sensor)")
        self.btn_d.clicked.connect(self._simular_d)
        fila.addWidget(self.btn_d)

        fila.addStretch(1)
        self.cabecera.vbox.addLayout(fila)

    def _construir_gauges(self):
        for var in iot.VARIABLES:
            card = Card(ETIQUETAS[var])
            gauge = GaugeWidget()
            card.vbox.addWidget(gauge)

            valor = QLabel("—")
            valor.setStyleSheet("font-size:20px;font-weight:800;")
            valor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card.vbox.addWidget(valor)

            estado = chip("Normal", "good")
            estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card.vbox.addWidget(estado)

            self._gauges[var] = {"gauge": gauge, "valor": valor, "estado": estado}
            self.fila_gauges.addWidget(card)

    def _construir_chart(self):
        fila = QHBoxLayout()
        fila.setSpacing(8)
        etiqueta = QLabel("Variable:")
        etiqueta.setProperty("cls", "muted")
        fila.addWidget(etiqueta)
        self.combo_variable = QComboBox()
        for var in iot.VARIABLES:
            self.combo_variable.addItem(ETIQUETAS[var], var)
        self.combo_variable.setCurrentIndex(iot.VARIABLES.index("vibracion"))
        self.combo_variable.currentIndexChanged.connect(lambda _=0: self._repintar_chart())
        fila.addWidget(self.combo_variable)
        fila.addStretch(1)
        self.card_chart.vbox.addLayout(fila)

        self.chart = LineaEnVivoWidget()
        self.card_chart.vbox.addWidget(self.chart)

        hint = QLabel("Zonas: verde = rango normal · ámbar = Alerta A (ajuste preventivo) · "
                      "rojo = Alerta C (detener y calibrar). Los umbrales son configurables abajo.")
        hint.setProperty("cls", "hint")
        hint.setWordWrap(True)
        self.card_chart.vbox.addWidget(hint)

    def _construir_umbrales(self):
        u = iot.umbrales(self.conn)
        columnas = ["Variable", "Rango normal lo", "Rango normal hi",
                    "Alerta A lo", "Alerta A hi"]
        tabla = QTableWidget(len(iot.VARIABLES), len(columnas))
        tabla.setHorizontalHeaderLabels(columnas)
        tabla.verticalHeader().setVisible(False)
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabla.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        tabla.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tabla.setShowGrid(False)
        tabla.setAlternatingRowColors(True)
        tabla.verticalHeader().setDefaultSectionSize(40)

        for i, var in enumerate(iot.VARIABLES):
            ud = u[var]
            item = QTableWidgetItem(ETIQUETAS[var])
            tabla.setItem(i, 0, item)
            dec = 0 if ud["unidad"] == "spm" else 1
            for j, campo in enumerate(("ok_lo", "ok_hi", "a_lo", "a_hi")):
                sp = QDoubleSpinBox()
                sp.setDecimals(dec)
                sp.setRange(ud["min_escala"], ud["max_escala"])
                if var == "vibracion" and campo == "a_lo":
                    sp.setMinimum(-1.0)
                sp.setSingleStep(1 if dec == 0 else 0.1)
                sp.setValue(float(ud[campo]))
                self._spin_umbrales[(var, campo)] = sp
                tabla.setCellWidget(i, j + 1, sp)

        header = tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.card_umbrales.vbox.addWidget(tabla)

        fila = QHBoxLayout()
        b_guardar = QPushButton("Guardar umbrales")
        b_guardar.setProperty("cls", "primary")
        b_guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        b_guardar.clicked.connect(self._guardar_umbrales)
        fila.addWidget(b_guardar)
        fila.addStretch(1)
        self.card_umbrales.vbox.addLayout(fila)

    # ------------------------------------------------ refresco dinámico
    def refresh(self):
        self._repintar()

    def _repintar(self):
        self._repintar_gauges()
        self._repintar_chart()
        self._repintar_alertas()

    def _repintar_gauges(self):
        u = iot.umbrales(self.conn)
        for var in iot.VARIABLES:
            hist = iot.historial(self.conn, self._maquina_actual, var, limite=1)
            valor = hist[-1]["valor"] if hist else None
            nivel = hist[-1]["nivel"] if hist else "ok"
            g = self._gauges[var]
            g["gauge"].set_datos(u.get(var), valor, nivel)

            ud = u.get(var)
            if valor is None or ud is None:
                g["valor"].setText("—")
            else:
                dec = 0 if ud["unidad"] == "spm" else 1
                g["valor"].setText(f"{valor:.{dec}f} {ud['unidad']}")

            texto, tipo = _estado_chip(nivel)
            if g["estado"].text() != texto:
                g["estado"].setText(texto)
                g["estado"].setProperty("cls", f"chip_{tipo}")
                g["estado"].style().unpolish(g["estado"])
                g["estado"].style().polish(g["estado"])

    def _repintar_chart(self):
        var = self.combo_variable.currentData()
        u = iot.umbrales(self.conn)
        self.chart.set_datos(iot.historial(self.conn, self._maquina_actual, var), u.get(var))

    def _repintar_alertas(self):
        alertas = iot.alertas(self.conn, limite=50)
        firma = tuple((a["id"], a["atendida"], a["tarjeta_id"]) for a in alertas)
        if firma == getattr(self, "_firma_alertas", None):
            return  # nada cambió: no reconstruir widgets
        self._firma_alertas = firma
        vaciar_layout(self.alert_cuerpo)
        if not alertas:
            vacio = QLabel("Sin alertas IoT registradas.")
            vacio.setProperty("cls", "muted")
            self.alert_cuerpo.addWidget(vacio)
            return
        for a in alertas:
            self.alert_cuerpo.addWidget(self._fila_alerta(a))

    def _fila_alerta(self, a: dict) -> QWidget:
        fila = QWidget()
        h = QHBoxLayout(fila)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        nivel = a["nivel"]
        h.addWidget(chip(nivel, "warn" if nivel == "A" else "bad"))

        texto = (f"<b>{a['maquina']} — nivel {nivel}</b> {a['mensaje']} "
                 f"<span style='color:{COLORS['muted']}'>{_hhmm(a['ts'])}</span>")
        lbl = QLabel(texto)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        h.addWidget(lbl, 1)

        if not a["atendida"]:
            if nivel in ("A", "C"):
                b = QPushButton("Crear tarjeta TPM")
                b.setProperty("cls", "ghost")
                b.clicked.connect(lambda _=False, aid=a["id"]: self._crear_tarjeta(aid))
                h.addWidget(b)
            elif nivel == "D":
                b = QPushButton("Registrar NC")
                b.setProperty("cls", "ghost")
                b.clicked.connect(lambda _=False, aid=a["id"]: self._registrar_nc(aid))
                h.addWidget(b)
            b_at = QPushButton("Atender")
            b_at.setProperty("cls", "ghost")
            b_at.clicked.connect(lambda _=False, aid=a["id"]: self._atender(aid))
            h.addWidget(b_at)
        else:
            h.addWidget(chip("Atendida", "info"))
            if a.get("tarjeta_id"):
                h.addWidget(chip(f"TPM-{a['tarjeta_id']:04d}", "info"))

        return fila

    # ------------------------------------------------ acciones
    def _cambiar_maquina(self, codigo: str):
        self._maquina_actual = codigo
        self._repintar()

    def _crear_tarjeta(self, alerta_id: int):
        try:
            tarjeta_id = iot.crear_tarjeta_desde_alerta(self.conn, alerta_id)
        except ValueError as e:
            self.shell.toast(str(e), "warn")
            return
        self.shell.toast(f"Tarjeta {tarjeta_id} creada desde alerta IoT", "ok")
        self.shell.refresh_all(excepto="iot")
        self._repintar()

    def _registrar_nc(self, alerta_id: int):
        try:
            iot.registrar_nc_desde_alerta(self.conn, alerta_id)
        except ValueError as e:
            self.shell.toast(str(e), "warn")
            return
        self.shell.toast("NC registrada desde alerta D", "ok")
        self.shell.refresh_all(excepto="iot")
        self._repintar()

    def _atender(self, alerta_id: int):
        iot.atender_alerta(self.conn, alerta_id)
        self._repintar()

    def _simular_c(self):
        u = iot.umbrales(self.conn).get("vibracion", {})
        valor = round(u.get("a_hi", 5.2) + 0.7, 1)
        r = iot.registrar_lectura(self.conn, self._maquina_actual, "vibracion", valor)
        if r.get("alerta"):
            self.shell.toast(
                f"Alerta C: vibración {valor:.1f} mm/s en {self._maquina_actual}", "warn")
        else:
            self.shell.toast(
                f"Vibración inyectada {valor:.1f} mm/s en {self._maquina_actual}", "warn")
        self._repintar()

    def _simular_d(self):
        iot.registrar_alerta(
            self.conn, self._maquina_actual, "etiqueta", "D",
            "Sensor de etiqueta: prenda no conforme detectada (alerta D). Inspeccionar proceso.",
            1.0)
        self.shell.toast(
            f"Alerta D inyectada: prenda no conforme en {self._maquina_actual}", "warn")
        self._repintar()

    def _guardar_umbrales(self):
        try:
            actual = iot.umbrales(self.conn)
            for (var, campo), sp in self._spin_umbrales.items():
                if abs(sp.value() - float(actual[var][campo])) > 1e-9:
                    iot.actualizar_umbral(self.conn, var, **{campo: sp.value()})
        except ValueError as e:
            self.shell.toast(str(e), "warn")
            return
        self.shell.toast("Umbrales IoT actualizados — las alertas A/C/D se recalculan", "ok")
        self._repintar()

    # ------------------------------------------------ timer
    def _tick(self):
        if QApplication.activeModalWidget() is not None:
            return
        if self.btn_sim.isChecked():
            alertas = iot.simular_paso(self.conn, self._maquina_actual)
            for a in alertas:
                self.shell.toast(f"Alerta IoT: {a['nivel']} · {a['maquina']}", "warn")
        self._repintar()
