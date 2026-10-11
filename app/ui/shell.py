"""Ventana principal: sidebar oscura + topbar + páginas apiladas (QStackedWidget)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
    QVBoxLayout, QWidget,
)

from ..core import db, iot, queries
from ..web.servidor import ServidorLAN
from . import icons
from .checklists_page import ChecklistsPage
from .dashboard import DashboardPage
from .datos_page import DatosPage
from .iot_page import IotPage
from .maquinas_page import MaquinasPage
from .no_conformidades import NoConformidadesPage
from .plan_page import PlanPage
from .produccion import ProduccionPage
from .reportes_page import ReportesPage
from .tarjetas_page import TarjetasPage
from .theme import COLORS, current_theme, qss
from .widgets import Toast

NAV = [
    # (id, sección, título, icono)
    ("dashboard", "Monitoreo",  "Dashboard",           "dashboard"),
    ("iot",       "Monitoreo",  "Monitor IoT",         "activity"),
    ("nc",        "Operación",  "No conformidades",    "nc"),
    ("prod",      "Operación",  "Producción diaria",   "package"),
    ("chk",       "Operación",  "Checklists",          "checklist"),
    ("tpm",       "Mantenimiento", "Tarjetas TPM",     "alert"),
    ("maq",       "Mantenimiento", "Máquinas",         "wrench"),
    ("plan",      "Mantenimiento", "Plan TPM",         "calendar"),
    ("rep",       "Sistema",    "Reportes",            "sheet"),
    ("datos",     "Sistema",    "Datos e importación", "database"),
]


class ActivePageStack(QStackedWidget):
    """Expone el tamaño de la página visible, no el de la página más grande."""

    def sizeHint(self) -> QSize:
        page = self.currentWidget()
        if page is None:
            return QSize(0, 0)
        hint = page.sizeHint()
        return hint if hint.isValid() else QSize(0, 0)

    def minimumSizeHint(self) -> QSize:
        # La altura preferida de la página activa determina si hace falta
        # scroll; el ancho queda libre para que las cuadrículas puedan refluir.
        hint = self.sizeHint()
        return QSize(0, max(0, hint.height()))


class Shell(QMainWindow):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.setWindowTitle("SICAM · Createl Trading S.A.C.")
        self.resize(1440, 920)
        self.setMinimumSize(960, 640)

        central = QWidget()
        central.setProperty("cls", "app_root")
        self.setCentralWidget(central)
        raiz = QHBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ---------------- sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(238)
        sbox = QVBoxLayout(sidebar)
        sbox.setContentsMargins(14, 18, 14, 14)
        sbox.setSpacing(0)

        marca = QHBoxLayout()
        logo = QLabel("◈")
        logo.setStyleSheet("color:#5EEAD4; font-size:22px; font-weight:800; background:transparent;")
        marca.addWidget(logo)
        mtxt = QVBoxLayout()
        m1 = QLabel("SICAM"); m1.setObjectName("brand")
        m2 = QLabel("Createl Trading S.A.C."); m2.setObjectName("brand_sub")
        mtxt.addWidget(m1); mtxt.addWidget(m2)
        marca.addLayout(mtxt)
        sbox.addLayout(marca)
        sbox.addSpacing(10)

        self.nav_botones: dict[str, QPushButton] = {}
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        seccion_actual = ""
        for pid, seccion, titulo, icono in NAV:
            if seccion != seccion_actual:
                seccion_actual = seccion
                s = QLabel(seccion.upper())
                s.setObjectName("nav_section")
                sbox.addWidget(s)
            b = QPushButton(f"  {titulo}")
            b.setObjectName("nav_btn")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIcon(icons.icono(icono, "#94A3B8", 17))
            b.clicked.connect(lambda _=False, p=pid: self.ir_a(p))
            self.grupo.addButton(b)
            self.nav_botones[pid] = b
            sbox.addWidget(b)
        sbox.addStretch(1)

        pie = QLabel("SQLite local · 1 PC + celulares\nMVP v0.1 — datos sintéticos")
        pie.setObjectName("sidebar_foot")
        sbox.addWidget(pie)
        raiz.addWidget(sidebar)

        # ---------------- zona derecha
        derecha = QVBoxLayout()
        derecha.setContentsMargins(0, 0, 0, 0)
        derecha.setSpacing(0)

        topbar = QFrame()
        topbar.setProperty("cls", "topbar")
        topbar.setFixedHeight(62)
        tbox = QHBoxLayout(topbar)
        tbox.setContentsMargins(26, 0, 26, 0)
        self.titulo = QLabel("Dashboard")
        self.titulo.setObjectName("page_title")
        tbox.addWidget(self.titulo)
        tbox.addStretch(1)

        pill = QLabel("Piloto · setiembre 2026")
        pill.setObjectName("pill")
        self.pill = pill
        tbox.addWidget(pill)

        self.usuario = QComboBox()
        self.usuario.addItems(["Supervisor — J. de Producción",
                               "Personal de Mantenimiento", "Operario"])
        self.usuario.currentTextChanged.connect(
            lambda _: self.toast("El filtrado por rol llega con los roles completos (próxima fase)", "warn"))
        tbox.addWidget(self.usuario)

        self.bell = QPushButton()
        self.bell.setObjectName("bell")
        self.bell.setIcon(icons.icono("bell", COLORS["slate"], 17))
        self.bell.clicked.connect(self._campana_clic)
        tbox.addWidget(self.bell)

        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("theme_toggle")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        tbox.addWidget(self.theme_btn)
        self._sync_theme_button()
        derecha.addWidget(topbar)

        # páginas dentro de un scroll con márgenes
        contenido = QWidget()
        contenido.setProperty("cls", "page_content")
        cbox = QHBoxLayout(contenido)
        cbox.setContentsMargins(26, 22, 26, 22)
        self.stack = ActivePageStack()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        cbox.addWidget(self.stack)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background:transparent; }")
        scroll.setWidget(contenido)
        self.page_scroll = scroll
        self.page_content = contenido
        derecha.addWidget(scroll, 1)
        raiz.addLayout(derecha, 1)

        # ---------------- páginas
        self.servidor = ServidorLAN()
        self.paginas: dict[str, QWidget] = {
            "dashboard": DashboardPage(conn, self),
            "iot": IotPage(conn, self),
            "nc": NoConformidadesPage(conn, self),
            "prod": ProduccionPage(conn, self),
            "chk": ChecklistsPage(conn, self, self.servidor),
            "tpm": TarjetasPage(conn, self),
            "maq": MaquinasPage(conn, self),
            "plan": PlanPage(conn, self),
            "rep": ReportesPage(conn, self),
            "datos": DatosPage(conn, self),
        }
        for pid, _, _, _ in NAV:
            self.stack.addWidget(self.paginas[pid])

        # ---------------- toast + statusbar + servidor
        self.toast_host = Toast(self)
        self.statusBar().showMessage(
            f"BD: {db.ruta_db()}  ·  Piloto desde: {queries.INICIO_PILOTO}")

        try:
            url = self.servidor.iniciar()
            self.statusBar().showMessage(
                f"BD: {db.ruta_db()}  ·  Celulares: {url}  ·  Piloto desde: {queries.INICIO_PILOTO}")
        except OSError as e:
            self.statusBar().showMessage(
                f"BD: {db.ruta_db()}  ·  Servidor móvil no iniciado ({e})")

        # refresco periódico: detecta cualquier cambio (celular, diálogo,
        # importación) vía firma de datos y actualiza la vista activa
        from PySide6.QtCore import QTimer
        self._firma = queries.firma_datos(self.conn)
        self._timer_reactividad = QTimer(self)
        self._timer_reactividad.setInterval(5_000)
        self._timer_reactividad.timeout.connect(self._revisar_cambios)
        self._timer_reactividad.start()

        self.nav_botones["dashboard"].setChecked(True)
        self.ir_a("dashboard")
        self.actualizar_campana()

    # ------------------------------------------------ reactividad
    def _revisar_cambios(self):
        firma = queries.firma_datos(self.conn)
        if firma == self._firma:
            return
        self._firma = firma
        self.actualizar_campana()
        # no reconstruir la vista si hay un diálogo modal abierto encima
        from PySide6.QtWidgets import QApplication
        if QApplication.activeModalWidget() is not None:
            return
        actual = self.stack.currentWidget()
        if actual is not None:
            actual.refresh()
            self._actualizar_geometria_pagina()

    # ------------------------------------------------ tema visual
    def _sync_theme_button(self):
        """Muestra el icono del tema al que se cambiaría al pulsar."""
        tema = current_theme()
        destino = "claro" if tema == "dark" else "oscuro"
        icono = "sun" if tema == "dark" else "moon"
        self.theme_btn.setIcon(icons.icono(icono, COLORS["muted"], 18))
        self.theme_btn.setToolTip(f"Cambiar al tema {destino}")
        self.theme_btn.setAccessibleName(f"Cambiar al tema {destino}")

    def _toggle_theme(self):
        nuevo = "dark" if current_theme() == "light" else "light"
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss(nuevo))

        # QPainter usa colores cacheados; actualizarlos antes de reconstruir
        # los widgets para que los gráficos también respondan al tema.
        from .charts import actualizar_colores_tema
        actualizar_colores_tema()
        self.bell.setIcon(icons.icono("bell", COLORS["slate"], 17))
        self._sync_theme_button()
        self.refresh_all()
        self.toast(f"Tema {'oscuro' if nuevo == 'dark' else 'claro'} activado")

    # ------------------------------------------------ campana
    def actualizar_campana(self):
        n_tarjetas = self.conn.execute(
            "SELECT COUNT(*) FROM tarjetas_tpm WHERE estado != 'cerrada'").fetchone()[0]
        n_alertas = iot.alertas_pendientes(self.conn)
        n = n_tarjetas + n_alertas
        self.bell.setText(f" {n}" if n else "")
        self.bell.setToolTip(
            f"{n} pendientes: {n_tarjetas} tarjetas TPM · {n_alertas} alertas IoT")

    def _campana_clic(self):
        n_tarjetas = self.conn.execute(
            "SELECT COUNT(*) FROM tarjetas_tpm WHERE estado != 'cerrada'").fetchone()[0]
        n_alertas = iot.alertas_pendientes(self.conn)
        if n_tarjetas:
            self.ir_a("tpm")
        elif n_alertas:
            self.ir_a("iot")
        else:
            self.toast("Sin pendientes — todo cerrado")

    # ------------------------------------------------ navegación
    def ir_a(self, pid: str):
        self.stack.setCurrentWidget(self.paginas[pid])
        titulo = next(t for i, _, t, _ in NAV if i == pid)
        self.titulo.setText(titulo)
        self.paginas[pid].refresh()
        # Recalcular el viewport a partir de la página activa para que una
        # pantalla que cabe no conserve la altura mínima de otra sección.
        self._actualizar_geometria_pagina()

    def refresh_all(self, excepto: str | None = None):
        for pid, pagina in self.paginas.items():
            if pid != excepto:
                pagina.refresh()
        self._actualizar_geometria_pagina()

    def _actualizar_geometria_pagina(self):
        """Notifica al scroll que cambió la geometría de la página activa."""
        self.stack.updateGeometry()
        self.page_content.updateGeometry()
        self.page_scroll.updateGeometry()

    # ------------------------------------------------ toast
    def toast(self, mensaje: str, tipo: str = "ok"):
        self.toast_host.mostrar(mensaje, tipo)
        self._posicionar_toast()

    def _posicionar_toast(self):
        t = self.toast_host
        t.adjustSize()
        t.move(self.width() - t.width() - 28, self.height() - t.height() - 46)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # En ventanas estrechas se oculta el chip secundario de la barra para
        # reservar espacio para el selector de usuario y los botones de acción.
        if hasattr(self, "pill"):
            self.pill.setVisible(self.width() >= 1120)
        if hasattr(self, "usuario"):
            self.usuario.setMaximumWidth(300 if self.width() >= 1120 else 220)
        if hasattr(self, "toast_host") and self.toast_host.isVisible():
            self._posicionar_toast()
