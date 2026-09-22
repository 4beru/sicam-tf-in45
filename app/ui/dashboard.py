"""Página Dashboard: KPIs, Pareto, tendencia y rankings (todo desde SQLite)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..core import checklists, plan_tpm, queries
from .charts import ParetoWidget, TendenciaWidget
from .theme import COLORS
from .widgets import Card, Kpi, fila_kpis, tabla

DER = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def _limpiar(layout):
    while layout.count():
        item = layout.takeAt(0)
        if (w := item.widget()) is not None:
            w.deleteLater()
        elif item.layout() is not None:
            _limpiar(item.layout())


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
        _limpiar(self.layout_principal)
        m = queries.metas(self.conn)
        as_is, to_be = m.get("Tasa de prendas no conformes", (10.68, 4.95))
        r = queries.resumen_mes(self.conn)
        mes_et = queries.etiqueta_mes(r["mes"]) if r["mes"] else "—"

        # ---------------- KPIs
        chips_tasa = []
        if r.get("tasa_prev") is not None:
            delta = round(r["tasa"] - r["tasa_prev"], 2)
            if delta < 0:
                chips_tasa.append((f"▼ {abs(delta):.2f} pts vs mes anterior", "good"))
            elif delta > 0:
                chips_tasa.append((f"▲ +{delta:.2f} pts vs mes anterior", "bad"))
            else:
                chips_tasa.append(("= sin cambio vs mes anterior", "info"))
        en_meta = r["tasa"] <= to_be
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

        fila_kpis([
            Kpi(f"Tasa NC · {mes_et}", f"{r['tasa']:.2f}%", "trend", chips_tasa,
                f"As-Is {as_is:.2f} · Meta {to_be:.2f}"),
            Kpi(f"NC · {mes_et}", _num(r["nc"]), "nc",
                [(f"{proceso_top[0]} {_num(proceso_top[1])}", "info")] if por_proceso else [],
                "prendas no conformes"),
            Kpi("Cumpl. checklist · hoy", f"{cump['pct']:.0f}%", "checklist",
                [("✔ en meta" if en_cump else f"meta ≥ {m_cump[1]:.0f}%",
                  "good" if en_cump else "warn")],
                f"{cump['hechas']} de {cump['total']} estaciones · Tabla 21"),
            Kpi("Cumpl. plan TPM", f"{plan_r['cumplimiento']:.0f}%", "calendar",
                [("✔ en meta" if en_plan else f"meta ≥ {m_plan[1]:.0f}%",
                  "good" if en_plan else "warn")],
                f"{plan_r['vencidas']} vencidas · {plan_r['ejecutadas']} ejecutadas"),
            Kpi("Causa #1 (Pareto)", f"{causa_top[2]:.1f}%", "alert",
                [(causa_top[0].split()[0] + "…", "purple")], causa_top[0][:38]),
            Kpi("Proceso crítico", proceso_top[0], "wrench",
                [(_num(proceso_top[1]) + " NC", "bad")]),
        ], self.layout_principal)

        # ---------------- gráficos
        fila = QHBoxLayout()
        fila.setSpacing(14)

        c1 = Card("Pareto de causas de no conformidad", "Tabla 6 · Fig. 9")
        pareto = ParetoWidget()
        pareto.set_datos(queries.pareto(self.conn))
        h = QLabel("Barras: % de prendas defectuosas por causa · Línea: % acumulado · Punteada ámbar: corte 80/20.")
        h.setProperty("cls", "hint")
        c1.vbox.addWidget(pareto)
        c1.vbox.addWidget(h)
        fila.addWidget(c1, 1)

        c2 = Card("Tasa de NC — As-Is → Piloto → To-Be", "Tabla 22")
        tendencia = TendenciaWidget()
        tendencia.set_datos(queries.tasa_mensual(self.conn), as_is, to_be)
        h2 = QLabel("Gris: línea base 2024 · Teal: piloto 2026 · Punteada verde: meta To-Be del sector exportador.")
        h2.setProperty("cls", "hint")
        c2.vbox.addWidget(tendencia)
        c2.vbox.addWidget(h2)
        fila.addWidget(c2, 1)
        self.layout_principal.addLayout(fila)

        # ---------------- rankings
        fila2 = QHBoxLayout()
        fila2.setSpacing(14)

        c3 = Card("Operarios con más NC · Corte", "→ Capacitación")
        filas_ops = []
        for i, (nombre, n) in enumerate(queries.ranking_operarios(self.conn), 1):
            causa_dom = self.conn.execute(
                "SELECT causa, SUM(cantidad) n FROM no_conformidades "
                "WHERE operario = ? AND proceso = 'Corte' AND fecha >= ? "
                "GROUP BY causa ORDER BY n DESC LIMIT 1",
                (nombre, queries.INICIO_PILOTO)).fetchone()
            filas_ops.append([
                (str(i), COLORS["muted"]), f"<b>{nombre}</b>",
                (_num(n), DER),
                causa_dom["causa"] if causa_dom else "—",
            ])
        c3.vbox.addWidget(tabla(["#", "Operario", "NC", "Causa dominante"],
                                filas_ops or [["—", "—", "—", "—"]]))
        fila2.addWidget(c3, 1)

        c4 = Card("Máquinas con más NC asociadas", "Tabla 17")
        critic = {row["codigo"]: row["criticidad"]
                  for row in self.conn.execute("SELECT codigo, criticidad FROM maquinas")}
        filas_maqs = [[f"<b>{mid}</b>", critic.get(mid, "—"), (_num(n), DER)]
                      for mid, n in queries.ranking_maquinas(self.conn)]
        c4.vbox.addWidget(tabla(["Máquina", "Criticidad", "NC (piloto)"],
                                filas_maqs or [["—", "—", "—"]]))
        fila2.addWidget(c4, 1)
        self.layout_principal.addLayout(fila2)
        self.layout_principal.addStretch(1)
