"""Ventana principal: sidebar oscura + topbar + páginas apiladas (QStackedWidget)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import QSize, Qt, QTimer
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



class Shell(QMainWindow):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.setWindowTitle("SICAM · Createl Trading S.A.C.")
        self.resize(1440, 920)
        self.setMinimumSize(720, 640)

        central = QWidget()
        central.setProperty("cls", "app_root")
        self.setCentralWidget(central)
        raiz = QHBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ---------------- sidebar expandible
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self._sidebar_expanded = True
        self._sidebar_width_expanded = 238
        self._sidebar_width_collapsed = 72
        self.sidebar.setFixedWidth(self._sidebar_width_expanded)
        sbox = QVBoxLayout(self.sidebar)
        sbox.setContentsMargins(14, 18, 14, 14)
        sbox.setSpacing(0)
        self.sidebar_layout = sbox

        marca = QHBoxLayout()
        self.brand_logo = QLabel("SICAM")
        self.brand_logo.setObjectName("brand")
        mtxt = QVBoxLayout()
        mtxt.setContentsMargins(0, 0, 0, 0)
        mtxt.setSpacing(1)
        self.brand_sub = QLabel("Createl Trading S.A.C.")
        self.brand_sub.setObjectName("brand_sub")
        mtxt.addWidget(self.brand_logo)
        mtxt.addWidget(self.brand_sub)
        marca.addLayout(mtxt)
        marca.addStretch(1)

        self.sidebar_toggle = QPushButton()
        self.sidebar_toggle.setObjectName("sidebar_toggle")
        self.sidebar_toggle.setFixedSize(28, 28)
        self.sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_toggle.clicked.connect(self._toggle_sidebar)
        marca.addWidget(self.sidebar_toggle)
        sbox.addLayout(marca)
        sbox.addSpacing(10)

        self.nav_botones: dict[str, QPushButton] = {}
        self.nav_titulos: dict[str, str] = {}
        self.nav_secciones: list[QLabel] = []
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        seccion_actual = ""
        for pid, seccion, titulo, icono in NAV:
            if seccion != seccion_actual:
                seccion_actual = seccion
                etiqueta_seccion = QLabel(seccion.upper())
                etiqueta_seccion.setObjectName("nav_section")
                self.nav_secciones.append(etiqueta_seccion)
                sbox.addWidget(etiqueta_seccion)
            b = QPushButton(f"  {titulo}")
            b.setObjectName("nav_btn")
            b.setProperty("collapsed", False)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIcon(icons.icono(icono, COLORS["sidebar_ink"], 18))
            b.setIconSize(QSize(18, 18))
            b.setToolTip("")
            b.setAccessibleName(titulo)
            b.clicked.connect(lambda _=False, p=pid: self.ir_a(p))
            self.grupo.addButton(b)
            self.nav_botones[pid] = b
            self.nav_titulos[pid] = titulo
            sbox.addWidget(b)
        sbox.addStretch(1)

        self.sidebar_foot = QLabel("SQLite local · 1 PC + celulares\nMVP v0.1 — datos sintéticos")
        self.sidebar_foot.setObjectName("sidebar_foot")
        sbox.addWidget(self.sidebar_foot)
        self._sync_sidebar_toggle()
        raiz.addWidget(self.sidebar)

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

        # Stack de viewports independientes: cada sección gestiona su propio scroll.
        # Así una página alta (p. ej. Tarjetas TPM) no determina la geometría de otra.
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.page_scrolls: dict[str, QScrollArea] = {}
        self.page_contents: dict[str, QWidget] = {}
        derecha.addWidget(self.stack, 1)
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
            # Cada sección obtiene su propio QScrollArea. El widget interior
            # conserva los márgenes actuales y siempre arranca alineado arriba.
            contenido = QWidget()
            contenido.setProperty("cls", "page_content")
            cbox = QVBoxLayout(contenido)
            cbox.setContentsMargins(26, 22, 26, 22)
            cbox.setSpacing(0)
            cbox.addWidget(self.paginas[pid])

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            scroll.setStyleSheet("QScrollArea { background:transparent; }")
            scroll.setWidget(contenido)

            self.page_scrolls[pid] = scroll
            self.page_contents[pid] = contenido
            self.stack.addWidget(scroll)
        self._pid_actual = "dashboard"

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
        self._firma = queries.firma_datos(self.conn)
        self._timer_reactividad = QTimer(self)
        self._timer_reactividad.setInterval(5_000)
        self._timer_reactividad.timeout.connect(self._revisar_cambios)
        self._timer_reactividad.start()

        self.nav_botones["dashboard"].setChecked(True)
        self.ir_a("dashboard")
        self.actualizar_campana()

    # ------------------------------------------------ sidebar
    def _sync_sidebar_toggle(self):
        """Actualiza el icono y el nombre accesible de expandir/contraer."""
        if self._sidebar_expanded:
            icono, accion = "panel_left_close", "Contraer menú"
        else:
            icono, accion = "panel_left_open", "Expandir menú"
        self.sidebar_toggle.setIcon(
            icons.icono(icono, COLORS["sidebar_ink"], 18)
        )
        self.sidebar_toggle.setToolTip(accion)
        self.sidebar_toggle.setAccessibleName(accion)

    def _toggle_sidebar(self):
        """Alterna entre navegación completa y navegación compacta por iconos."""
        self._sidebar_expanded = not self._sidebar_expanded
        compacto = not self._sidebar_expanded
        self.sidebar.setFixedWidth(
            self._sidebar_width_collapsed if compacto
            else self._sidebar_width_expanded
        )
        self.sidebar_layout.setContentsMargins(
            8 if compacto else 14, 18, 8 if compacto else 14, 14
        )

        self.brand_logo.setText("S" if compacto else "SICAM")
        self.brand_logo.setAlignment(
            Qt.AlignmentFlag.AlignCenter if compacto
            else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.brand_logo.setProperty("compact", compacto)
        self.brand_logo.style().unpolish(self.brand_logo)
        self.brand_logo.style().polish(self.brand_logo)
        self.brand_sub.setVisible(not compacto)

        for etiqueta in self.nav_secciones:
            etiqueta.setVisible(not compacto)
        for pid, boton in self.nav_botones.items():
            boton.setText("" if compacto else f"  {self.nav_titulos[pid]}")
            boton.setProperty("collapsed", compacto)
            boton.setToolTip(self.nav_titulos[pid] if compacto else "")
            boton.style().unpolish(boton)
            boton.style().polish(boton)
        self.sidebar_foot.setVisible(not compacto)
        self._sync_sidebar_toggle()

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
        actual = self.paginas.get(self._pid_actual)
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
        self._sync_sidebar_toggle()
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
        self._pid_actual = pid
        viewport = self.page_scrolls[pid]
        self.stack.setCurrentWidget(viewport)
        # La navegación empieza arriba en la sección elegida; sus scrolls
        # internos (tablas/kanban/listas) mantienen su propia independencia.
        viewport.verticalScrollBar().setValue(0)
        viewport.horizontalScrollBar().setValue(0)
        titulo = next(t for i, _, t, _ in NAV if i == pid)
        self.titulo.setText(titulo)
        self.paginas[pid].refresh()
        self._actualizar_geometria_pagina()

    def refresh_all(self, excepto: str | None = None):
        for pid, pagina in self.paginas.items():
            if pid != excepto:
                pagina.refresh()
        self._actualizar_geometria_pagina()

    def _actualizar_geometria_pagina(self):
        """Actualiza solo la geometría de la sección activa y de su viewport."""
        pid = getattr(self, "_pid_actual", None)
        actual = self.paginas.get(pid)
        viewport = self.page_scrolls.get(pid)
        contenido = self.page_contents.get(pid)
        if actual is not None:
            if actual.layout() is not None:
                actual.layout().activate()
            actual.updateGeometry()
        if contenido is not None:
            if contenido.layout() is not None:
                contenido.layout().activate()
            contenido.updateGeometry()
        if viewport is not None:
            viewport.updateGeometry()
            viewport.viewport().updateGeometry()
        self.stack.updateGeometry()

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
            self.usuario.setMaximumWidth(300 if self.width() >= 1120 else 220 if self.width() >= 820 else 175)
        if hasattr(self, "page_scrolls"):
            self._actualizar_geometria_pagina()
        if hasattr(self, "toast_host") and self.toast_host.isVisible():
            self._posicionar_toast()
