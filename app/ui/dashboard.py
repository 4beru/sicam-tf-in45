"""Página Dashboard: KPIs, Pareto, tendencia y rankings (todo desde SQLite)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..core import checklists, iot, plan_tpm, queries
from .charts import ParetoWidget, TendenciaWidget
from .theme import COLORS
from .widgets import Card, Kpi, ResponsiveGrid, tabla, vaciar_layout

DER = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def _num(n: int) -> str:
    return f"{n:,}".replace(",", " ")


class DashboardPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell):
        super().__init__()
        self.conn = conn
        self.shell = shell
        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setContentsMargins(0, 0, 0, 0)
        self.layout_principal.setSpacing(14)

    def refresh(self):
        vaciar_layout(self.layout_principal)
        m = queries.metas(self.conn)
        as_is, to_be = m.get("Tasa de prendas no conformes", (10.68, 4.95))
        r = queries.resumen_mes(self.conn)
        mes_et = queries.etiqueta_mes(r["mes"]) if r["mes"] else "—"

        # ---------------- KPIs
        en_meta = r["tasa"] <= to_be
        chips_tasa = []
        if r.get("tasa_prev") is not None:
            delta = round(r["tasa"] - r["tasa_prev"], 2)
            if delta < 0:
                chips_tasa.append((f"▼ {abs(delta):.2f} pts", "good"))
            elif delta > 0:
                chips_tasa.append((f"▲ +{delta:.2f} pts", "bad"))
            else:
                chips_tasa.append(("= sin cambio", "info"))
        chips_tasa.append(("✔ en meta" if en_meta else f"meta {to_be}%",
                           "good" if en_meta else "warn"))

        por_proceso = r.get("por_proceso") or []
        proceso_top = por_proceso[0] if por_proceso else ("—", 0)
        causa_top = r.get("causa_top") or ("—", 0, 0.0)

        cump = checklists.cumplimiento_hoy(self.conn)
        m_cump = queries.metas(self.conn).get("Cumplimiento de checklists", (0, 85))
        en_cump = cump["pct"] >= m_cump[1]
        plan_r = plan_tpm.resumen(self.conn)
        m_plan = queries.metas(self.conn).get("Cumplimiento del plan TPM", (60, 85))
        en_plan = plan_r["cumplimiento"] >= m_plan[1]

        kpis = [
            Kpi(f"Tasa NC · {mes_et}", f"{r['tasa']:.2f}%", "trend", chips_tasa,
                (f"vs mes anterior · As-Is {as_is:.2f} · Meta {to_be:.2f}"
                 if r.get("tasa_prev") is not None
                 else f"As-Is {as_is:.2f} · Meta {to_be:.2f}")),
            Kpi(f"NC · {mes_et}", _num(r["nc"]), "nc",
                [(f"{proceso_top[0]} · {_num(proceso_top[1])}", "info")] if por_proceso else [],
                "prendas no conformes"),
            Kpi("Cumpl. checklist · hoy", f"{cump['pct']:.0f}%", "checklist",
                [("✔ en meta" if en_cump else f"meta ≥ {m_cump[1]:.0f}%",
                  "good" if en_cump else "warn")],
                f"{cump['hechas']} de {cump['total']} estaciones"),
            Kpi("Cumpl. plan TPM", f"{plan_r['cumplimiento']:.0f}%", "calendar",
                [("✔ en meta" if en_plan else f"meta ≥ {m_plan[1]:.0f}%",
                  "good" if en_plan else "warn")],
                f"{plan_r['vencidas']} vencidas · {plan_r['ejecutadas']} ejecutadas"),
            Kpi("Causa #1 (Pareto)", f"{causa_top[2]:.1f}%", "alert",
                [(causa_top[0].split()[0] + "…", "purple")], causa_top[0][:38]),
            Kpi("Prendas inspeccionadas", _num(r["insp"]), "package",
                [], "base de cálculo de la tasa NC"),
            Kpi("Alertas IoT activas", _num(iot.alertas_pendientes(self.conn)), "activity",
                [("En vivo · simulador", "teal")], "sin atender"),
        ]
        grid_kpis = ResponsiveGrid(
            min_item_width=220, max_columns=4, spacing=12, center_items=True
        )
        grid_kpis.set_items(kpis)
        self.layout_principal.addWidget(grid_kpis)

        # ---------------- gráficos adaptables
        c1 = Card("Pareto de causas de no conformidad")
        c1.vbox.setContentsMargins(14, 10, 14, 10)
        c1.vbox.setSpacing(7)
        pareto = ParetoWidget(min_height=200)
        pareto.set_datos(queries.pareto(self.conn))
        h = QLabel("Barras: % de prendas defectuosas por causa · Línea: % acumulado · Punteada ámbar: corte 80/20.")
        h.setProperty("cls", "hint")
        h.setWordWrap(True)
        c1.vbox.addWidget(pareto)
        c1.vbox.addWidget(h)

        c2 = Card("Tasa de NC — As-Is → Piloto → To-Be")
        c2.vbox.setContentsMargins(14, 10, 14, 10)
        c2.vbox.setSpacing(7)
        tendencia = TendenciaWidget(min_height=200)
        tendencia.set_datos(queries.tasa_mensual(self.conn), as_is, to_be)
        h2 = QLabel("Gris: línea base 2024 · Teal: piloto 2026 · Punteada verde: meta To-Be del sector exportador.")
        h2.setProperty("cls", "hint")
        h2.setWordWrap(True)
        c2.vbox.addWidget(tendencia)
        c2.vbox.addWidget(h2)

        grid_graficos = ResponsiveGrid(
            min_item_width=460, max_columns=2, spacing=14
        )
        grid_graficos.set_items([c1, c2])
        self.layout_principal.addWidget(grid_graficos)

        # ---------------- rankings adaptables

        c3 = Card("Operarios con más NC · Corte")
        c3.vbox.setContentsMargins(14, 10, 14, 10)
        c3.vbox.setSpacing(7)
        filas_ops = []
        for i, (nombre, n) in enumerate(queries.ranking_operarios(self.conn), 1):
            causa_dom = self.conn.execute(
                "SELECT causa, SUM(cantidad) n FROM no_conformidades "
                "WHERE operario = ? AND proceso = 'Corte' AND fecha >= ? "
                "GROUP BY causa ORDER BY n DESC LIMIT 1",
                (nombre, queries.INICIO_PILOTO)).fetchone()
            filas_ops.append([
                (str(i), COLORS["muted"]), (nombre, None, True),
                (_num(n), DER),
                causa_dom["causa"] if causa_dom else "—",
            ])
        tabla_ops = tabla(["#", "Operario", "NC", "Causa dominante"],
                          filas_ops or [["—", "—", "—", "—"]])
        tabla_ops.verticalHeader().setDefaultSectionSize(29)
        c3.vbox.addWidget(tabla_ops)


        c4 = Card("Máquinas con más NC asociadas")
        c4.vbox.setContentsMargins(14, 10, 14, 10)
        c4.vbox.setSpacing(7)
        critic = {row["codigo"]: row["criticidad"]
                  for row in self.conn.execute("SELECT codigo, criticidad FROM maquinas")}
        filas_maqs = [[(mid, None, True), critic.get(mid, "—"), (_num(n), DER)]
                      for mid, n in queries.ranking_maquinas(self.conn)]
        tabla_maqs = tabla(["Máquina", "Criticidad", "NC (piloto)"],
                           filas_maqs or [["—", "—", "—"]])
        tabla_maqs.verticalHeader().setDefaultSectionSize(29)
        c4.vbox.addWidget(tabla_maqs)
        grid_rankings = ResponsiveGrid(
            min_item_width=460, max_columns=2, spacing=14
        )
        grid_rankings.set_items([c3, c4])
        self.layout_principal.addWidget(grid_rankings)
        self.layout_principal.addStretch(1)
