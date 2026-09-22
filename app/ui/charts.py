"""Gráficos pintados con QPainter: Pareto de causas y tendencia de tasa NC.

Sin dependencias externas: mismo look que la maqueta HTML (barras teal,
línea acumulada oscura, cortes 80/20 y metas punteadas).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .theme import COLORS

TEAL = QColor(COLORS["teal"])
TEAL_CLARO = QColor("#A5D8D4")
SLATE = QColor("#334155")
GRIS = QColor("#64748b")
GRIS_CLARO = QColor("#F1F5F9")
EJE = QColor(COLORS["line"])
AMBAR = QColor(COLORS["amber"])
VERDE = QColor(COLORS["green"])


class ParetoWidget(QWidget):
    """Barras por causa + línea de % acumulado + corte 80/20."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(290)
        self._datos: list[tuple[str, int, float]] = []  # (causa, prendas, pct)

    def set_datos(self, datos: list[tuple[str, int, float]]):
        self._datos = datos
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(COLORS["surface"]))
        if not self._datos:
            p.setPen(GRIS)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos en el periodo")
            return

        fuente = QFont(self.font())
        fuente.setPointSizeF(8.5)
        p.setFont(fuente)
        fm = QFontMetrics(fuente)

        pl, pr, pt, pb = 44, 46, 26, 52
        cw, ch = w - pl - pr, h - pt - pb
        n = len(self._datos)
        bw = cw / n
        max_pct = max(d[2] for d in self._datos) * 1.18

        # gridlines + eje izquierdo (0–100 % acumulado)
        p.setPen(QPen(EJE, 1))
        p.drawLine(pl, pt, pl, pt + ch)
        p.drawLine(pl, pt + ch, pl + cw, pt + ch)
        for v in range(0, 101, 25):
            y = pt + ch - ch * v / 100
            p.setPen(QPen(GRIS_CLARO, 1))
            p.drawLine(pl, y, pl + cw, y)
            p.setPen(QPen(GRIS))
            p.drawText(QRectF(0, y - 7, pl - 8, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{v}%")

        # barras + etiquetas
        acum = 0.0
        puntos: list[QPointF] = []
        for i, (causa, _, pct) in enumerate(self._datos):
            acum += pct
            bh = ch * pct / max_pct
            x = pl + i * bw + bw * 0.2
            bwi = bw * 0.6
            y = pt + ch - bh
            p.setBrush(TEAL if i < 4 else TEAL_CLARO)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, y, bwi, bh), 4, 4)
            p.setPen(QPen(QColor(COLORS["ink"])))
            f = QFont(fuente); f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(x - bw * 0.2, y - 18, bwi + bw * 0.4, 14),
                       Qt.AlignmentFlag.AlignCenter, f"{pct:.1f}%")
            p.setFont(fuente)
            cy = pt + ch - ch * acum / 100
            puntos.append(QPointF(x + bwi / 2, cy))
            p.setBrush(QColor(COLORS["ink"]))
            p.drawEllipse(puntos[-1], 3.2, 3.2)
            p.setPen(QPen(GRIS))
            p.drawText(QRectF(x + bwi / 2 - bw, cy - 20, bw * 2, 12),
                       Qt.AlignmentFlag.AlignCenter, f"{acum:.0f}%")
            # etiqueta X en dos líneas
            palabras = causa.split()
            mitad = (len(palabras) + 1) // 2
            l1, l2 = " ".join(palabras[:mitad]), " ".join(palabras[mitad:])
            p.setPen(QPen(GRIS))
            p.drawText(QRectF(pl + i * bw, pt + ch + 6, bw, 14),
                       Qt.AlignmentFlag.AlignHCenter, self._elide(fm, l1, bw))
            p.drawText(QRectF(pl + i * bw, pt + ch + 19, bw, 14),
                       Qt.AlignmentFlag.AlignHCenter, self._elide(fm, l2, bw))

        # línea acumulada
        if len(puntos) > 1:
            pen = QPen(SLATE, 1.7)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            path_lines = [QPointF(a.x(), a.y()) for a in puntos]
            for a, b in zip(path_lines, path_lines[1:]):
                p.drawLine(a, b)

        # corte 80/20
        y80 = pt + ch - ch * 0.8
        p.setPen(QPen(AMBAR, 1.6, Qt.PenStyle.DashLine))
        p.drawLine(pl, y80, pl + cw, y80)
        p.setPen(QPen(QColor(COLORS["amber"]).darker(150)))
        f = QFont(fuente); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(pl + cw + 2, y80 - 7, pr - 4, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "80%")

    @staticmethod
    def _elide(fm: QFontMetrics, texto: str, ancho: int) -> str:
        return fm.elidedText(texto, Qt.TextElideMode.ElideRight, max(30, int(ancho)))


class SparkBarras(QWidget):
    """Barras pequeñas de historial mensual (última barra destacada en rojo)."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(130)
        self._datos: list[int] = []
        self._titulo = ""

    def set_datos(self, datos: list[int], titulo: str = ""):
        self._datos = datos
        self._titulo = titulo
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(COLORS["surface"]))
        if self._titulo:
            p.setPen(QPen(GRIS))
            f = QFont(self.font()); f.setPointSizeF(8.5)
            p.setFont(f)
            p.drawText(QRectF(6, 6, w - 12, 14), Qt.AlignmentFlag.AlignLeft, self._titulo)
        if not self._datos:
            return
        maximo = max(max(self._datos), 1)
        n = len(self._datos)
        area_h = h - 44
        bw = min(26.0, (w - 20) / n)
        for i, v in enumerate(self._datos):
            bh = area_h * v / maximo
            x = 10 + i * ((w - 20) / n) + bw * 0.18
            p.setBrush(QColor(COLORS["red"]) if i == n - 1 else QColor(13, 148, 136, 200))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, h - 26 - bh, bw * 0.64, max(2.0, bh)), 3, 3)
        p.setPen(QPen(GRIS))
        f = QFont(self.font()); f.setPointSizeF(8.5)
        p.setFont(f)
        p.drawText(QRectF(6, h - 20, w - 12, 14), Qt.AlignmentFlag.AlignLeft,
                   f"hace {n} meses")
        p.drawText(QRectF(6, h - 20, w - 12, 14), Qt.AlignmentFlag.AlignRight, "este mes")


class DonutWidget(QWidget):
    """Donut de cumplimiento (arco + porcentaje al centro)."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(150, 150)
        self._pct = 0.0
        self._meta = 85.0

    def set_datos(self, pct: float, meta: float):
        self._pct, self._meta = pct, meta
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 10
        grosor = 16

        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        p.setPen(QPen(QColor(COLORS["line"]), grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 90 * 16, 360 * 16)

        color = QColor(COLORS["teal"]) if self._pct >= self._meta else QColor(COLORS["amber"])
        p.setPen(QPen(color, grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span = int(-360 * 16 * min(1.0, self._pct / 100))
        p.drawArc(rect, 90 * 16, span)

        f = QFont(self.font()); f.setBold(True); f.setPointSizeF(19)
        p.setFont(f); p.setPen(QPen(QColor(COLORS["ink"])))
        p.drawText(self.rect().adjusted(0, -6, 0, 0), Qt.AlignmentFlag.AlignCenter,
                   f"{self._pct:.0f}%")
        f2 = QFont(self.font()); f2.setPointSizeF(8.5)
        p.setFont(f2); p.setPen(QPen(GRIS))
        p.drawText(self.rect().adjusted(0, 26, 0, 0), Qt.AlignmentFlag.AlignCenter,
                   f"meta ≥ {self._meta:.0f}%")


class TendenciaWidget(QWidget):
    """Tasa mensual: 2024 gris, piloto teal, As-Is y To-Be punteados."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(290)
        self._puntos: list[dict] = []
        self._as_is = 10.68
        self._to_be = 4.95

    def set_datos(self, puntos: list[dict], as_is: float, to_be: float):
        self._puntos = puntos
        self._as_is, self._to_be = as_is, to_be
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(COLORS["surface"]))
        if not self._puntos:
            p.setPen(GRIS)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos")
            return

        fuente = QFont(self.font())
        fuente.setPointSizeF(8.5)
        p.setFont(fuente)

        pl, pr, pt, pb = 42, 60, 24, 28
        cw, ch = w - pl - pr, h - pt - pb
        vmin, vmax = 4.0, 11.5
        pts = self._puntos
        n = len(pts)

        def X(i):
            return pl + cw * i / (n - 1)

        def Y(v):
            return pt + ch - ch * (v - vmin) / (vmax - vmin)

        # grid + eje Y
        v = 4.0
        while v <= vmax + 0.01:
            y = Y(v)
            p.setPen(QPen(GRIS_CLARO, 1))
            p.drawLine(pl, y, pl + cw, y)
            p.setPen(QPen(GRIS))
            p.drawText(QRectF(0, y - 7, pl - 8, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{v:.0f}%")
            v += 1.5

        i_2024 = [i for i, d in enumerate(pts) if not d["piloto"]]
        i_piloto = [i for i, d in enumerate(pts) if d["piloto"]]

        # línea base As-Is sobre el tramo 2024
        if i_2024:
            p.setPen(QPen(QColor("#94A3B8"), 1.4, Qt.PenStyle.DashLine))
            p.drawLine(X(i_2024[0]), Y(self._as_is), X(i_2024[-1]), Y(self._as_is))
            p.setPen(QPen(GRIS))
            p.drawText(QRectF(X(i_2024[0]), Y(self._as_is) - 16, 130, 14),
                       Qt.AlignmentFlag.AlignLeft, f"As-Is {self._as_is:.2f}%")

        # trazo 2024
        if len(i_2024) > 1:
            p.setPen(QPen(GRIS, 1.8))
            for a, b in zip(i_2024, i_2024[1:]):
                p.drawLine(X(a), Y(pts[a]["tasa"]), X(b), Y(pts[b]["tasa"]))
            p.setBrush(GRIS)
            for i in i_2024:
                p.drawEllipse(QPointF(X(i), Y(pts[i]["tasa"])), 2.4, 2.4)

        # unión 2024 → piloto
        if i_2024 and i_piloto:
            p.setPen(QPen(QColor("#94A3B8"), 1.2, Qt.PenStyle.DotLine))
            p.drawLine(X(i_2024[-1]), Y(pts[i_2024[-1]]["tasa"]),
                       X(i_piloto[0]), Y(pts[i_piloto[0]]["tasa"]))

        # trazo piloto
        if len(i_piloto) > 1:
            pen = QPen(TEAL, 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            for a, b in zip(i_piloto, i_piloto[1:]):
                p.drawLine(X(a), Y(pts[a]["tasa"]), X(b), Y(pts[b]["tasa"]))
        for i in i_piloto:
            p.setBrush(TEAL)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(X(i), Y(pts[i]["tasa"])), 4.6, 4.6)
            p.setBrush(QColor(COLORS["surface"]))
            p.drawEllipse(QPointF(X(i), Y(pts[i]["tasa"])), 2.0, 2.0)

        # valor actual
        if i_piloto:
            ult = i_piloto[-1]
            f = QFont(fuente); f.setBold(True); p.setFont(f)
            p.setPen(QPen(QColor(COLORS["teal_dark"])))
            p.drawText(QRectF(X(ult) - 90, Y(pts[ult]["tasa"]) - 22, 86, 14),
                       Qt.AlignmentFlag.AlignRight, f"{pts[ult]['tasa']:.1f}%")
            p.setFont(fuente)

        # meta To-Be
        p.setPen(QPen(VERDE, 1.6, Qt.PenStyle.DashLine))
        p.drawLine(pl, Y(self._to_be), pl + cw, Y(self._to_be))
        f = QFont(fuente); f.setBold(True); p.setFont(f)
        p.setPen(QPen(QColor("#15803D")))
        p.drawText(QRectF(pl + cw + 2, Y(self._to_be) - 7, pr + 40, 14),
                   Qt.AlignmentFlag.AlignLeft, f"{self._to_be:.2f}%")
        p.setFont(fuente)

        # eje X (cada 3 meses + piloto)
        p.setPen(QPen(QColor("#94A3B8")))
        for i, d in enumerate(pts):
            if (not d["piloto"] and i % 3 == 0) or d["piloto"]:
                p.save()
                if d["piloto"]:
                    f = QFont(fuente)
                    f.setBold(True)
                    p.setFont(f)
                    p.setPen(QPen(QColor(COLORS["teal_dark"])))
                p.drawText(QRectF(X(i) - 40, pt + ch + 8, 80, 14),
                           Qt.AlignmentFlag.AlignHCenter, d["etiqueta"])
                p.restore()


class GaugeWidget(QWidget):
    """Medidor circular de 270° (réplica de drawGauge de la maqueta HTML).

    Dibuja solo el arco de zonas, la aguja y el punto central; el valor
    numérico y la etiqueta van en el card que lo contiene.
    """

    ROJO = QColor("#EF4444")
    AMBAR = QColor("#F59E0B")
    VERDE = QColor("#22C55E")
    AGUJA = QColor("#0F172A")

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(150)
        self._u: dict | None = None
        self._valor: float | None = None
        self._nivel = "ok"

    def set_datos(self, u, valor, nivel: str = "ok"):
        self._u = u
        self._valor = valor
        self._nivel = nivel
        self.update()

    @staticmethod
    def _ang_qt(v: float, min_: float, max_: float) -> int:
        """Valor de datos -> ángulo Qt en 1/16 de grado (270°, hueco abajo)."""
        frac = (v - min_) / (max_ - min_)
        deg = 135.0 + frac * 270.0          # grados de la maqueta (a0=0.75π)
        return int(round(-deg * 16))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(COLORS["surface"]))

        u = self._u
        valor = self._valor
        if u is None or valor is None or u["max_escala"] <= u["min_escala"]:
            self._pintar_sin_datos(p, w, h)
            return

        min_, max_ = u["min_escala"], u["max_escala"]
        cx, cy = w / 2, h * 0.58
        R = min(w * 0.42, h * 0.62)
        rect = QRectF(cx - R, cy - R, 2 * R, 2 * R)

        zonas = [
            {"from": min_, "to": u["a_lo"], "color": self.ROJO},
            {"from": u["a_lo"], "to": u["ok_lo"], "color": self.AMBAR},
            {"from": u["ok_lo"], "to": u["ok_hi"], "color": self.VERDE},
            {"from": u["ok_hi"], "to": u["a_hi"], "color": self.AMBAR},
            {"from": u["a_hi"], "to": max_, "color": self.ROJO},
        ]
        for z in zonas:
            if z["to"] <= z["from"] + 0.001:
                continue
            color = QColor(z["color"])
            color.setAlpha(217)             # ~0.85 como la maqueta
            p.setPen(QPen(color, 11, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            inicio = self._ang_qt(z["from"], min_, max_)
            span = self._ang_qt(z["to"], min_, max_) - inicio
            p.drawArc(rect, inicio, span)

        # aguja hacia el valor (clamp al rango)
        frac = min(1.0, max(0.0, (valor - min_) / (max_ - min_)))
        av = (135.0 + frac * 270.0) * math.pi / 180.0
        p.setPen(QPen(self.AGUJA, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(cx, cy),
                   QPointF(cx + math.cos(av) * (R - 14), cy + math.sin(av) * (R - 14)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.AGUJA)
        p.drawEllipse(QPointF(cx, cy), 5, 5)

    def _pintar_sin_datos(self, p: QPainter, w: int, h: int):
        cx, cy = w / 2, h * 0.58
        R = min(w * 0.42, h * 0.62)
        rect = QRectF(cx - R, cy - R, 2 * R, 2 * R)
        p.setPen(QPen(QColor("#E2E8F0"), 11, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        p.drawArc(rect, int(-135 * 16), int(-270 * 16))
        p.setPen(GRIS)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos")


class LineaEnVivoWidget(QWidget):
    """Gráfico de línea en vivo (réplica de drawIotChart, generalizado a cualquier variable)."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(230)
        self._historial: list[dict] = []
        self._u: dict | None = None

    def set_datos(self, historial: list[dict], u):
        self._historial = historial or []
        self._u = u
        self.update()

    @staticmethod
    def _fmt(v: float) -> str:
        f = float(v)
        return str(int(f)) if f.is_integer() else f"{f:.1f}"

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(COLORS["surface"]))

        u = self._u
        if u is None or u["max_escala"] <= u["min_escala"]:
            p.setPen(GRIS)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin lecturas aún")
            return

        min_, max_ = u["min_escala"], u["max_escala"]
        a_lo, a_hi = u["a_lo"], u["a_hi"]
        ok_lo, ok_hi = u["ok_lo"], u["ok_hi"]
        tiene_lo = a_lo > min_

        padL, padR, padT, padB = 40, 14, 14, 24
        cw, ch = w - padL - padR, h - padT - padB
        fondo = padT + ch

        def y(v):
            return padT + ch - (v - min_) / (max_ - min_) * ch

        fuente = QFont(self.font())
        fuente.setPointSizeF(8.5)
        p.setFont(fuente)

        # bandas de zona
        rojo = QColor(239, 68, 68, 18)          # rgba(239,68,68,.07)
        verde = QColor(34, 197, 94, 18)         # rgba(34,197,94,.07)
        p.fillRect(QRectF(padL, padT, cw, max(0.0, y(a_hi) - padT)), rojo)
        if tiene_lo:
            p.fillRect(QRectF(padL, y(a_lo), cw, max(0.0, fondo - y(a_lo))), rojo)
        p.fillRect(QRectF(padL, y(ok_hi), cw, max(0.0, y(ok_lo) - y(ok_hi))), verde)

        # líneas punteadas de umbral
        p.setPen(QPen(QColor("#22C55E"), 1.3, Qt.PenStyle.DashLine))
        p.drawLine(padL, y(ok_hi), padL + cw, y(ok_hi))
        p.setPen(QPen(QColor("#15803D")))
        p.drawText(QRectF(0, y(ok_hi) - 7, padL - 6, 14),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"A {self._fmt(ok_hi)}")

        p.setPen(QPen(QColor("#EF4444"), 1.3, Qt.PenStyle.DashLine))
        p.drawLine(padL, y(a_hi), padL + cw, y(a_hi))
        p.setPen(QPen(QColor("#B91C1C")))
        p.drawText(QRectF(0, y(a_hi) - 7, padL - 6, 14),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"C {self._fmt(a_hi)}")

        if tiene_lo:
            p.setPen(QPen(QColor("#EF4444"), 1.3, Qt.PenStyle.DashLine))
            p.drawLine(padL, y(a_lo), padL + cw, y(a_lo))
            p.setPen(QPen(QColor("#B91C1C")))
            p.drawText(QRectF(0, y(a_lo) - 7, padL - 6, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"C {self._fmt(a_lo)}")

        # serie (últimos 60 puntos)
        hist = self._historial[:60]
        n = len(hist)

        def X(i):
            return padL + (i / 59.0) * cw

        teal = QColor("#0D9488")
        rojo_p = QColor("#EF4444")
        ambar_p = QColor("#F59E0B")
        if n > 1:
            pen = QPen(teal, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            for i in range(1, n):
                p.drawLine(QPointF(X(i - 1), y(hist[i - 1]["valor"])),
                           QPointF(X(i), y(hist[i]["valor"])))
        for i, d in enumerate(hist):
            v = d["valor"]
            if v > a_hi or (tiene_lo and v < a_lo):
                color, radio = rojo_p, 3.4
            elif v < ok_lo or v > ok_hi:
                color, radio = ambar_p, 2.8
            else:
                color, radio = teal, 2.8
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(QPointF(X(i), y(v)), radio, radio)

        # ejes
        p.setPen(QPen(QColor("#94A3B8")))
        p.drawText(QRectF(padL + 2, fondo + 4, 120, 14),
                   Qt.AlignmentFlag.AlignLeft, "hace 60 min")
        p.drawText(QRectF(padL + cw - 122, fondo + 4, 120, 14),
                   Qt.AlignmentFlag.AlignRight, "ahora")
