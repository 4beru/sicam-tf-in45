"""Exportación PDF de los reportes del sistema (reportlab).

La empresa no recibe Excel: recibe PDFs generados por el sistema.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from . import plan_tpm, queries

TEAL = colors.HexColor("#0D9488")
TEAL_SUAVE = colors.HexColor("#CCFBF1")
INK = colors.HexColor("#0F172A")
GRIS = colors.HexColor("#64748B")
LINEA = colors.HexColor("#E2E8F0")

_h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, textColor=INK,
                     spaceBefore=14, spaceAfter=6)
_normal = ParagraphStyle("n", fontName="Helvetica", fontSize=9.5, textColor=GRIS)


def _doc(ruta: Path | str, titulo: str) -> SimpleDocTemplate:
    doc = SimpleDocTemplate(str(ruta), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=titulo, author="SICAM · Createl Trading S.A.C.")
    return doc


def _cabecera(titulo: str, subtitulo: str) -> list:
    marca = Table(
        [[Paragraph("<b>SICAM</b> · Createl Trading S.A.C.",
                    ParagraphStyle("m", fontName="Helvetica-Bold", fontSize=9,
                                   textColor=colors.white)),
          Paragraph(f"Generado: {date.today().strftime('%d/%m/%Y')}",
                    ParagraphStyle("f", fontName="Helvetica", fontSize=8,
                                   textColor=colors.white))]],
        colWidths=[120 * mm, 54 * mm])
    marca.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [
        marca,
        Spacer(1, 8 * mm),
        Paragraph(f"<font size=17><b>{titulo}</b></font>", ParagraphStyle(
            "h1", fontName="Helvetica-Bold", fontSize=17, textColor=INK)),
        Paragraph(subtitulo, _normal),
        Spacer(1, 4 * mm),
    ]


def pdf_plan(conn: sqlite3.Connection, ruta: Path | str, hoy: date | None = None) -> Path:
    """Plan mensual de mantenimiento preventivo (Fig. 42) en PDF."""
    hoy = hoy or date.today()
    r = plan_tpm.resumen(conn, hoy)
    tareas = plan_tpm.tareas_del_mes(conn, hoy)

    filas = [["Máquina", "Actividad", "Frecuencia", "Sem 1", "Sem 2", "Sem 3", "Sem 4", "Responsable"]]
    frecs = conn.execute("SELECT * FROM frecuencias ORDER BY maquina").fetchall()
    ESTADO_TXT = {"over": "VENCIDA", "soon": "Próxima", "sched": "Programada"}
    for f in frecs:
        fila = [f["maquina"], f["actividad"], plan_tpm._texto_freq(f["frecuencia_dias"])]
        for s in range(1, 5):
            en_semana = [t for t in tareas
                         if t["maquina"] == f["maquina"]
                         and t["actividad"] == f["actividad"]
                         and t["semana"] == s]
            if en_semana:
                peor = min(en_semana, key=lambda t: {"over": 0, "soon": 1, "sched": 2}[t["estado"]])
                fila.append(f"{ESTADO_TXT[peor['estado']]} ({peor['fecha'][8:]}/{peor['fecha'][5:7]})")
            else:
                fila.append("—")
        fila.append(f["responsable"])
        filas.append(fila)

    t = Table(filas, colWidths=[20 * mm, 52 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 26 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, LINEA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    resumen = Table([[
        Paragraph("<b>Vencidas</b><br/>" + str(r["vencidas"]), ParagraphStyle(
            "c", fontName="Helvetica", fontSize=9, alignment=1, textColor=INK)),
        Paragraph("<b>Vencen ≤7 días</b><br/>" + str(r["proximas"]), ParagraphStyle(
            "c2", fontName="Helvetica", fontSize=9, alignment=1, textColor=INK)),
        Paragraph("<b>Ejecutadas</b><br/>" + str(r["ejecutadas"]), ParagraphStyle(
            "c3", fontName="Helvetica", fontSize=9, alignment=1, textColor=INK)),
        Paragraph(f"<b>Cumplimiento</b><br/>{r['cumplimiento']:.0f}% (meta ≥ 85%)",
                  ParagraphStyle("c4", fontName="Helvetica", fontSize=9, alignment=1, textColor=INK)),
    ]], colWidths=[40 * mm, 40 * mm, 40 * mm, 54 * mm])
    resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL_SUAVE),
        ("BOX", (0, 0), (-1, -1), 0.6, TEAL),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    doc = _doc(ruta, f"Plan de mantenimiento preventivo · {r['mes']}")
    doc.build(_cabecera(f"Plan de mantenimiento preventivo TPM — {r['mes']}",
                        "Frecuencias según la Figura 42 de la tesis (TF-IN45). "
                        "Estados calculados por el motor del sistema.")
              + [resumen, Spacer(1, 6 * mm), t])
    return Path(ruta)


def pdf_indicadores(conn: sqlite3.Connection, ruta: Path | str) -> Path:
    """As-Is vs To-Be vs actual para los indicadores de las Tablas 21 y 22."""
    metas = queries.metas(conn)
    r = queries.resumen_mes(conn)
    from . import checklists
    cump_chk = checklists.cumplimiento_hoy(conn)["pct"]
    cump_plan = plan_tpm.resumen(conn)["cumplimiento"]

    actuales = {
        "Tasa de prendas no conformes": f"{r['tasa']:.2f}%",
        "Cumplimiento de checklists": f"{cump_chk:.0f}% (hoy)",
        "Cumplimiento del plan TPM": f"{cump_plan:.0f}%",
    }
    filas = [["Indicador", "As-Is", "To-Be", "Actual"]]
    for indicador, (as_is, to_be) in metas.items():
        filas.append([indicador, f"{as_is:g}", f"{to_be:g}",
                      actuales.get(indicador, "—")])

    t = Table(filas, colWidths=[86 * mm, 26 * mm, 26 * mm, 36 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, LINEA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    doc = _doc(ruta, "Resumen de indicadores")
    doc.build(_cabecera("Resumen de indicadores — As-Is · To-Be · Piloto",
                        "Valores de referencia según las Tablas 21 y 22 de la tesis; "
                        "los valores actuales se calculan desde la base del sistema.")
              + [t])
    return Path(ruta)


def pdf_pareto(conn: sqlite3.Connection, ruta: Path | str) -> Path:
    """Pareto de causas con % acumulado (barras teal + línea a mano)."""
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing as RLDrawing
    from reportlab.graphics.shapes import Line, String

    par = queries.pareto(conn)
    total_pct = sum(p for _, _, p in par) or 1.0
    acum, puntos = 0.0, []
    for _, _, p in par:
        acum += p / total_pct * 100
        puntos.append(acum)

    d = RLDrawing(560, 300)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 50, 40, 460, 200
    chart.data = [[p for _, _, p in par]]
    chart.bars[0].fillColor = TEAL
    chart.bars[0].strokeColor = None
    chart.strokeColor = LINEA
    chart.categoryAxis.categoryNames = [c.split()[0] + "." for c, _, _ in par]
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = int(max(p for _, _, p in par) * 1.2)
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 8
    d.add(chart)

    # línea acumulada + etiquetas + corte 80/20
    x0 = 50 + 460 / len(par) / 2
    x1 = 50 + 460 - 460 / len(puntos) / 2
    for i, punto in enumerate(puntos):
        x = x0 + (x1 - x0) * i / max(1, len(puntos) - 1)
        y = 40 + 200 * punto / 100
        d.add(String(x, y + 6, f"{punto:.0f}%", fontName="Helvetica-Bold",
                     fontSize=7, fillColor=INK, textAnchor="middle"))
        if i:
            px = x0 + (x1 - x0) * (i - 1) / max(1, len(puntos) - 1)
            py = 40 + 200 * puntos[i - 1] / 100
            d.add(Line(px, py, x, y, strokeColor=INK, strokeWidth=1.2))
    d.add(Line(50, 40 + 200 * 0.8, 510, 40 + 200 * 0.8,
               strokeColor=colors.HexColor("#F59E0B"), strokeWidth=1.2,
               strokeDashArray=[4, 3]))

    doc = _doc(ruta, "Pareto de causas")
    doc.build(_cabecera("Pareto de causas de no conformidad",
                        "Barras: % por causa (Tabla 6) · Línea: % acumulado · "
                        "Punteada: corte 80/20.")
              + [d])
    return Path(ruta)
