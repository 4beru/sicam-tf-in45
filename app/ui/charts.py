"""Gráficos pintados con QPainter: Pareto de causas y tendencia de tasa NC.

Sin dependencias externas: mismo look que la maqueta HTML (barras teal,
línea acumulada oscura, cortes 80/20 y metas punteadas).
"""
from __future__ import annotations

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
