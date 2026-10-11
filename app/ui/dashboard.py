"""Página Dashboard: KPIs, Pareto, tendencia y rankings (todo desde SQLite)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..core import checklists, iot, plan_tpm, queries
from .charts import ParetoWidget, TendenciaWidget
from .theme import COLORS
from .widgets import Card, ResponsiveGrid, chip, tabla, vaciar_layout

DER = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def _num(n: int) -> str:
    return f"{n:,}".replace(",", " ")


# Escala de espaciado alineada con las páginas basadas en Card (p. ej. Checklists).
DASHBOARD_GAP = 10
DASHBOARD_CARD_MARGINS = (16, 14, 16, 14)
DASHBOARD_CARD_SPACING = 10


def _dashboard_card(titulo: str) -> Card:
    """Crea una tarjeta del Dashboard con el mismo padding base que el resto de la UI."""
    card = Card(titulo)
    card.vbox.setContentsMargins(*DASHBOARD_CARD_MARGINS)
    card.vbox.setSpacing(DASHBOARD_CARD_SPACING)
    return card


def _metric_block(titulo: str, valor: str, detalle: str = "", value_cls: str = "summary_value") -> QWidget:
    """Bloque compacto para componer resúmenes que aprovechan el ancho de una tarjeta."""
    bloque = QWidget()
    layout = QVBoxLayout(bloque)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    label = QLabel(titulo)
    label.setProperty("cls", "summary_label")
    label.setWordWrap(True)
    layout.addWidget(label)

    value = QLabel(valor)
    value.setProperty("cls", value_cls)
    value.setWordWrap(True)
    layout.addWidget(value)

    if detalle:
        caption = QLabel(detalle)
        caption.setProperty("cls", "summary_detail")
        caption.setWordWrap(True)
        layout.addWidget(caption)

    return bloque


class DashboardPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell):
        super().__init__()
        self.conn = conn
        self.shell = shell
        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setContentsMargins(0, 0, 0, 0)
        self.layout_principal.setSpacing(DASHBOARD_GAP)

    def refresh(self):
        vaciar_layout(self.layout_principal)
        mes = self.shell.mes_activo
        desde, hasta = queries.limites_mes(mes)
        m = queries.metas(self.conn)
        as_is, to_be = m.get("Tasa de prendas no conformes", (10.68, 4.95))
        r = queries.resumen_mes(self.conn, mes)
        mes_et = queries.etiqueta_mes(r["mes"]) if r["mes"] else "—"

        # ---------------- resumen principal
        en_meta = r["tasa"] <= to_be
        delta = None
        if r.get("tasa_prev") is not None:
            delta = round(r["tasa"] - r["tasa_prev"], 2)

        por_proceso = r.get("por_proceso") or []
        proceso_top = por_proceso[0] if por_proceso else ("—", 0)
        causa_top = r.get("causa_top") or ("—", 0, 0.0)

        cump = checklists.cumplimiento_hoy(self.conn)
        m_cump = queries.metas(self.conn).get("Cumplimiento de checklists", (0, 85))
        en_cump = cump["pct"] >= m_cump[1]
        plan_r = plan_tpm.resumen(self.conn)
        m_plan = queries.metas(self.conn).get("Cumplimiento del plan TPM", (60, 85))
        en_plan = plan_r["cumplimiento"] >= m_plan[1]
        alertas_iot = iot.alertas_pendientes(self.conn)

        # 1. Calidad: tasa principal y los volúmenes que la explican.
        calidad = _dashboard_card("Calidad de producción")
        fila_tasa = QHBoxLayout()
        fila_tasa.setSpacing(DASHBOARD_GAP)
        fila_tasa.addWidget(
            _metric_block("Tasa de no conformidad", f"{r['tasa']:.2f}%", 
                          f"As-Is {as_is:.2f}% · Meta {to_be:.2f}%", "summary_primary"),
            2,
        )
        estado_tasa = QVBoxLayout()
        estado_tasa.setSpacing(5)
        if delta is not None:
            if delta < 0:
                detalle_delta, tipo_delta = f"▼ {abs(delta):.2f} pts vs ant.", "good"
            elif delta > 0:
                detalle_delta, tipo_delta = f"▲ {delta:.2f} pts vs ant.", "bad"
            else:
                detalle_delta, tipo_delta = "Sin cambio", "info"
            estado_tasa.addWidget(chip(detalle_delta, tipo_delta))
        estado_tasa.addWidget(chip("En meta" if en_meta else f"Meta {to_be:.2f}%",
                                   "good" if en_meta else "warn"))
        estado_tasa.addStretch(1)
        fila_tasa.addLayout(estado_tasa, 1)
        calidad.vbox.addLayout(fila_tasa)

        volúmenes = QHBoxLayout()
        volúmenes.setSpacing(DASHBOARD_GAP)
        volúmenes.addWidget(_metric_block("NC registradas · " + mes_et, _num(r["nc"]),
                                          f"Proceso con más NC: {proceso_top[0]}"), 1)
        volúmenes.addWidget(_metric_block("Prendas inspeccionadas", _num(r["insp"]),
                                          "Base de cálculo de la tasa"), 1)
        calidad.vbox.addLayout(volúmenes)

        # 2. Cumplimiento: reúne los dos indicadores de ejecución operativa.
        cumplimiento = _dashboard_card("Cumplimiento operativo")
        metricas_cumplimiento = QHBoxLayout()
        metricas_cumplimiento.setSpacing(DASHBOARD_GAP)
        chk = QVBoxLayout()
        chk.setSpacing(4)
        chk.addWidget(_metric_block("Checklists · hoy", f"{cump['pct']:.0f}%",
                                    f"{cump['hechas']} de {cump['total']} estaciones",
                                    "summary_primary"))
        chk.addWidget(chip("En meta" if en_cump else f"Meta ≥ {m_cump[1]:.0f}%",
                           "good" if en_cump else "warn"))
        tpm = QVBoxLayout()
        tpm.setSpacing(4)
        tpm.addWidget(_metric_block("Plan TPM", f"{plan_r['cumplimiento']:.0f}%",
                                    f"{plan_r['vencidas']} vencidas · {plan_r['ejecutadas']} ejecutadas",
                                    "summary_primary"))
        tpm.addWidget(chip("En meta" if en_plan else f"Meta ≥ {m_plan[1]:.0f}%",
                           "good" if en_plan else "warn"))
        metricas_cumplimiento.addLayout(chk, 1)
        metricas_cumplimiento.addLayout(tpm, 1)
        cumplimiento.vbox.addLayout(metricas_cumplimiento)

        # 3. Prioridades: causa dominante, proceso más afectado y alertas activas.
        prioridades = _dashboard_card("Focos de atención")
        prioridades.vbox.addWidget(
            _metric_block("Causa principal de NC",
                          f"{causa_top[2]:.1f}%", causa_top[0])
        )
        fila_prioridades = QHBoxLayout()
        fila_prioridades.setSpacing(DASHBOARD_GAP)
        fila_prioridades.addWidget(
            _metric_block("Proceso con más NC", proceso_top[0],
                          f"{_num(proceso_top[1])} NC del mes"), 1
        )
        fila_prioridades.addWidget(
            _metric_block("Alertas IoT activas", _num(alertas_iot),
                          "Pendientes de atención"), 1
        )
        prioridades.vbox.addLayout(fila_prioridades)

        grid_resumen = ResponsiveGrid(
            min_item_width=340,
            max_columns=3,
            spacing=DASHBOARD_GAP,
            center_items=True,
        )
        grid_resumen.set_items([calidad, cumplimiento, prioridades])
        self.layout_principal.addWidget(grid_resumen)

        # ---------------- gráficos adaptables
        c1 = _dashboard_card("Pareto de causas de no conformidad")
        pareto = ParetoWidget(min_height=200)
        pareto.set_datos(queries.pareto(self.conn, desde=desde, hasta=hasta))
        h = QLabel("Barras: % de prendas defectuosas por causa · Línea: % acumulado · Punteada ámbar: corte 80/20.")
        h.setProperty("cls", "hint")
        h.setWordWrap(True)
        c1.vbox.addWidget(pareto)
        c1.vbox.addWidget(h)

        c2 = _dashboard_card("Tasa de NC — As-Is → Piloto → To-Be")
        tendencia = TendenciaWidget(min_height=200)
        tendencia.set_datos(queries.tasa_mensual(self.conn), as_is, to_be)
        h2 = QLabel("Gris: línea base 2024 · Teal: piloto 2026 · Punteada verde: meta To-Be del sector exportador.")
        h2.setProperty("cls", "hint")
        h2.setWordWrap(True)
        c2.vbox.addWidget(tendencia)
        c2.vbox.addWidget(h2)

        grid_graficos = ResponsiveGrid(
            min_item_width=460, max_columns=2, spacing=DASHBOARD_GAP
        )
        grid_graficos.set_items([c1, c2])
        self.layout_principal.addWidget(grid_graficos)

        # ---------------- rankings adaptables

        c3 = _dashboard_card("Operarios con más NC · Corte")
        filas_ops = []
        for i, (nombre, n) in enumerate(
                queries.ranking_operarios(self.conn, desde=desde, hasta=hasta), 1):
            causa_dom = self.conn.execute(
                "SELECT causa, SUM(cantidad) n FROM no_conformidades "
                "WHERE operario = ? AND proceso = 'Corte' AND fecha BETWEEN ? AND ? "
                "GROUP BY causa ORDER BY n DESC LIMIT 1",
                (nombre, desde, hasta)).fetchone()
            filas_ops.append([
                (str(i), COLORS["muted"]), (nombre, None, True),
                (_num(n), DER),
                causa_dom["causa"] if causa_dom else "—",
            ])
        tabla_ops = tabla(["#", "Operario", "NC", "Causa dominante"],
                          filas_ops or [["—", "—", "—", "—"]])
        tabla_ops.verticalHeader().setDefaultSectionSize(29)
        c3.vbox.addWidget(tabla_ops)


        c4 = _dashboard_card("Máquinas con más NC asociadas")
        critic = {row["codigo"]: row["criticidad"]
                  for row in self.conn.execute("SELECT codigo, criticidad FROM maquinas")}
        filas_maqs = [[(mid, None, True), critic.get(mid, "—"), (_num(n), DER)]
                      for mid, n in queries.ranking_maquinas(self.conn, desde=desde, hasta=hasta)]
        tabla_maqs = tabla(["Máquina", "Criticidad", "NC (piloto)"],
                           filas_maqs or [["—", "—", "—"]])
        tabla_maqs.verticalHeader().setDefaultSectionSize(29)
        c4.vbox.addWidget(tabla_maqs)
        grid_rankings = ResponsiveGrid(
            min_item_width=460, max_columns=2, spacing=DASHBOARD_GAP
        )
        grid_rankings.set_items([c3, c4])
        self.layout_principal.addWidget(grid_rankings)
