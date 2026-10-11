"""Paleta y hoja de estilos QSS — espejo de la maqueta HTML (SICAM teal)."""
from __future__ import annotations

LIGHT_COLORS = {
    "bg": "#EEF2F7", "surface": "#FFFFFF", "surface_alt": "#F8FAFC",
    "line": "#E2E8F0", "ink": "#0F172A", "muted": "#64748B",
    "teal": "#0D9488", "teal_dark": "#0F766E", "teal_soft": "#CCFBF1",
    "amber": "#F59E0B", "amber_soft": "#FEF3C7", "red": "#EF4444",
    "red_soft": "#FEE2E2", "green": "#22C55E", "green_soft": "#DCFCE7",
    "purple": "#8B5CF6", "purple_soft": "#EDE9FE",
    "sidebar": "#0B1220", "sidebar_ink": "#94A3B8", "slate": "#475569",
    "good_text": "#15803D", "warn_text": "#B45309", "bad_text": "#B91C1C",
    "info_soft": "#E0F2FE", "info_text": "#0369A1", "purple_text": "#6D28D9",
    "teal_text": "#134E4A", "teal_border": "#99F6E4",
    "severity_low_bg": "#E0F2FE", "severity_low_text": "#0369A1",
    "severity_medium_bg": "#FEF3C7", "severity_medium_text": "#B45309",
    "severity_high_bg": "#FEE2E2", "severity_high_text": "#B91C1C",
}

DARK_COLORS = {
    "bg": "#0B1220", "surface": "#111C2E", "surface_alt": "#172337",
    "line": "#2A3A50", "ink": "#E6EDF7", "muted": "#9AAEC4",
    "teal": "#2DD4BF", "teal_dark": "#5EEAD4", "teal_soft": "#123E3D",
    "amber": "#FBBF24", "amber_soft": "#423316", "red": "#F87171",
    "red_soft": "#451D29", "green": "#4ADE80", "green_soft": "#143A2B",
    "purple": "#C4B5FD", "purple_soft": "#30264F",
    "sidebar": "#070D17", "sidebar_ink": "#A7B6C9", "slate": "#A7B6C9",
    "good_text": "#86EFAC", "warn_text": "#FCD34D", "bad_text": "#FDA4AF",
    "info_soft": "#162E47", "info_text": "#7DD3FC", "purple_text": "#C4B5FD",
    "teal_text": "#99F6E4", "teal_border": "#1F6A65",
    "severity_low_bg": "#162E47", "severity_low_text": "#7DD3FC",
    "severity_medium_bg": "#423316", "severity_medium_text": "#FCD34D",
    "severity_high_bg": "#451D29", "severity_high_text": "#FDA4AF",
}

COLORS = dict(LIGHT_COLORS)
_CURRENT_THEME = "light"


def set_theme(name: str) -> str:
    """Cambia la paleta activa sin romper las referencias compartidas por los módulos."""
    global _CURRENT_THEME
    _CURRENT_THEME = name if name in ("light", "dark") else "light"
    COLORS.clear()
    COLORS.update(DARK_COLORS if _CURRENT_THEME == "dark" else LIGHT_COLORS)
    return _CURRENT_THEME


def current_theme() -> str:
    return _CURRENT_THEME


def _build_qss() -> str:
    return f"""
* {{
    font-family: "Inter", "Segoe UI", "SF Pro Text", "Noto Sans", sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{ background: {COLORS['bg']}; }}
QWidget {{ color: {COLORS['ink']}; }}

/* ---------- sidebar ---------- */
QFrame#sidebar {{ background: {COLORS['sidebar']}; border: none; }}
QLabel#brand {{ color: #F8FAFC; font-size: 17px; font-weight: 800; }}
QLabel#brand_sub {{ color: {COLORS['sidebar_ink']}; font-size: 10.5px; }}
QLabel#nav_section {{
    color: {COLORS['sidebar_ink']}; font-size: 10px; font-weight: 800;
    letter-spacing: 1px; padding: 12px 10px 4px 10px;
}}
QPushButton#nav_btn {{
    text-align: left; color: {COLORS['sidebar_ink']};
    background: transparent; border: none; border-radius: 9px;
    padding: 9px 10px; font-size: 13px;
}}
QPushButton#nav_btn:hover {{ background: rgba(148,163,184,0.12); color: #E2E8F0; }}
QPushButton#nav_btn:checked {{
    background: rgba(13,148,136,0.25); color: #5EEAD4; font-weight: 700;
}}
QLabel#sidebar_foot {{ color: {COLORS['sidebar_ink']}; font-size: 10.5px; }}

/* ---------- topbar ---------- */
QLabel#page_title {{ font-size: 19px; font-weight: 800; }}
QLabel#pill {{
    background: {COLORS['teal_soft']}; color: {COLORS['teal_dark']};
    font-size: 11.5px; font-weight: 700; padding: 5px 12px; border-radius: 11px;
}}
QPushButton#bell, QPushButton#theme_toggle {{
    border: 1px solid {COLORS['line']}; border-radius: 9px;
    background: {COLORS['surface']}; padding: 6px;
}}
QPushButton#bell:hover, QPushButton#theme_toggle:hover {{ background: {COLORS['bg']}; }}

/* ---------- cards ---------- */
QFrame[cls="card"] {{
    background: {COLORS['surface']}; border: 1px solid {COLORS['line']};
    border-radius: 13px;
}}
QFrame[cls="topbar"] {{ background: {COLORS['surface']}; border: none; border-bottom: 1px solid {COLORS['line']}; }}
QLabel[cls="card_title"] {{ font-size: 14px; font-weight: 800; }}
QLabel[cls="ref"] {{
    color: {COLORS['muted']}; font-size: 10.5px; font-weight: 700;
    background: {COLORS['bg']}; border: 1px solid {COLORS['line']};
    padding: 2px 9px; border-radius: 10px;
}}
QLabel[cls="hint"] {{ color: {COLORS['muted']}; font-size: 11px; }}
QLabel[cls="muted"] {{ color: {COLORS['muted']}; font-size: 12px; }}

/* ---------- KPI ---------- */
QFrame[cls="kpi"] {{
    background: {COLORS['surface']}; border: 1px solid {COLORS['line']};
    border-radius: 13px;
}}
QLabel[cls="kpi_name"] {{ color: {COLORS['muted']}; font-size: 11px; font-weight: 700; }}
QLabel[cls="kpi_value"] {{ font-size: 26px; font-weight: 800; }}
QLabel[cls="kpi_target"] {{ color: {COLORS['muted']}; font-size: 10px; }}

/* ---------- chips ---------- */
QLabel[cls="chip_good"] {{ background: {COLORS['green_soft']};  color: {COLORS['good_text']}; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}
QLabel[cls="chip_warn"] {{ background: {COLORS['amber_soft']};  color: {COLORS['warn_text']}; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}
QLabel[cls="chip_bad"]  {{ background: {COLORS['red_soft']};    color: {COLORS['bad_text']}; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}
QLabel[cls="chip_info"] {{ background: {COLORS['info_soft']};                 color: {COLORS['info_text']}; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}
QLabel[cls="chip_teal"] {{ background: {COLORS['teal_soft']};   color: {COLORS['teal_dark']}; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}
QLabel[cls="chip_purple"] {{ background: {COLORS['purple_soft']}; color: {COLORS['purple_text']}; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}

/* ---------- botones ---------- */
QPushButton[cls="primary"] {{
    background: {COLORS['teal']}; color: white; font-weight: 700;
    border: none; border-radius: 9px; padding: 8px 16px;
}}
QPushButton[cls="primary"]:hover {{ background: {COLORS['teal_dark']}; }}
QPushButton[cls="primary"]:disabled {{ background: #94A3B8; }}
QPushButton[cls="ghost"] {{
    background: {COLORS['surface']}; color: {COLORS['slate']}; font-weight: 600;
    border: 1px solid {COLORS['line']}; border-radius: 9px; padding: 8px 14px;
}}
QPushButton[cls="ghost"]:hover {{ background: {COLORS['bg']}; }}
QPushButton[cls="chipbtn"] {{
    background: {COLORS['surface']}; color: {COLORS['slate']}; font-weight: 700;
    border: 1px solid {COLORS['line']}; border-radius: 14px; padding: 5px 13px;
    font-size: 11.5px;
}}
QPushButton[cls="chipbtn"]:hover {{ border-color: {COLORS['teal']}; color: {COLORS['teal_dark']}; }}
QPushButton[cls="chipbtn"]:checked {{ background: {COLORS['teal']}; color: white; border-color: {COLORS['teal']}; }}

/* ---------- inputs ---------- */
QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QLineEdit, QPlainTextEdit {{
    background: {COLORS['surface']}; border: 1px solid {COLORS['line']};
    border-radius: 8px; padding: 6px 10px; font-size: 12.5px; color: {COLORS['ink']};
    min-height: 18px;
}}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDateEdit:focus {{ border-color: {COLORS['teal']}; }}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 26px; border: none; border-left: 1px solid {COLORS['line']};
    border-top-right-radius: 8px; border-bottom-right-radius: 8px; background: transparent;
}}
QComboBox::drop-down:hover {{ background: {COLORS['surface_alt']}; }}
QComboBox QAbstractItemView {{
    background: {COLORS['surface']}; border: 1px solid {COLORS['line']};
    selection-background-color: {COLORS['teal_soft']}; selection-color: {COLORS['teal_dark']};
    outline: none;
}}

/* ---------- tablas ---------- */
QTableView, QTableWidget {{
    background: {COLORS['surface']}; border: none; alternate-background-color: {COLORS['surface_alt']};
    gridline-color: {COLORS['line']}; selection-background-color: {COLORS['teal_soft']};
    selection-color: {COLORS['ink']}; font-size: 12px;
}}
QTableView::item, QTableWidget::item {{ padding: 5px 8px; border-bottom: 1px solid {COLORS['line']}; }}
QHeaderView::section {{
    background: {COLORS['surface']}; color: {COLORS['muted']};
    font-size: 10.5px; font-weight: 800; text-transform: uppercase;
    border: none; border-bottom: 1px solid {COLORS['line']}; padding: 7px 8px;
}}
QTableWidget::item:selected {{ background: {COLORS['teal_soft']}; color: {COLORS['ink']}; }}

/* ---------- banner / toast ---------- */
QFrame[cls="banner"] {{
    background: {COLORS['teal_soft']}; border: 1px solid {COLORS['teal_border']}; border-radius: 12px;
}}
QLabel[cls="banner_txt"] {{ color: {COLORS['teal_text']}; font-size: 12.5px; }}

/* ---------- plan TPM: celdas de semana ---------- */
QPushButton[cls="st_done"]  {{ background: {COLORS['green_soft']}; color: {COLORS['good_text']}; font-size: 10.5px; font-weight: 800; border: none; border-radius: 8px; padding: 5px 10px; }}
QPushButton[cls="st_over"]  {{ background: {COLORS['red_soft']}; color: {COLORS['bad_text']}; font-size: 10.5px; font-weight: 800; border: 1px solid {COLORS['bad_text']}; border-radius: 8px; padding: 5px 10px; }}
QPushButton[cls="st_over"]:hover  {{ background: #FECACA; }}
QPushButton[cls="st_soon"]  {{ background: {COLORS['amber_soft']}; color: {COLORS['warn_text']}; font-size: 10.5px; font-weight: 800; border: none; border-radius: 8px; padding: 5px 10px; }}
QPushButton[cls="st_soon"]:hover  {{ background: #FDE68A; }}
QPushButton[cls="st_sched"] {{ background: {COLORS['surface_alt']}; color: {COLORS['slate']}; font-size: 10.5px; font-weight: 800; border: none; border-radius: 8px; padding: 5px 10px; }}
QPushButton[cls="st_sched"]:hover {{ background: #E2E8F0; }}
QLabel[cls="st_none"] {{ color: {COLORS['muted']}; font-weight: 800; }}

/* ---------- fichas de máquinas ---------- */
QFrame[cls="maq-card"] {{
    background: {COLORS['surface']}; border: 1.5px solid {COLORS['line']}; border-radius: 12px;
}}
QFrame[cls="maq-card"]:selected, QFrame[cls="maq-sel"] {{
    border-color: {COLORS['teal']}; background: {COLORS['teal_soft']};
}}
QLabel[cls="ficha_lbl"] {{ color: {COLORS['muted']}; font-size: 10px; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.4px; }}
QWidget[cls="ficha"] {{ background: {COLORS['surface_alt']}; border-radius: 10px; }}

/* ---------- kanban tarjetas TPM ---------- */
QWidget[cls="kcol"] {{ background: {COLORS['surface_alt']}; border: 1px solid {COLORS['line']}; border-radius: 13px; }}
QWidget[cls="kcard"] {{
    background: {COLORS['surface']}; border: 1px solid {COLORS['line']}; border-radius: 11px;
}}
QLabel[cls="kcard_title"] {{ color: {COLORS['ink']}; font-size: 12.5px; font-weight: 700; }}
QLabel[cls="kcol_title"] {{ color: {COLORS['ink']}; font-size: 13px; font-weight: 800; }}
QLabel[cls="kanban_count"] {{ background: {COLORS['surface']}; color: {COLORS['muted']}; border: 1px solid {COLORS['line']}; border-radius: 10px; padding: 1px 9px; font-size: 11px; font-weight: 800; }}
QLabel[cls="sev_Leve"] {{ background: {COLORS['severity_low_bg']}; color: {COLORS['severity_low_text']}; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="sev_Moderada"] {{ background: {COLORS['severity_medium_bg']}; color: {COLORS['severity_medium_text']}; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="sev_Crítica"] {{ background: {COLORS['severity_high_bg']}; color: {COLORS['severity_high_text']}; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="tipo_Mantenimiento"] {{ background: {COLORS['purple_soft']}; color: {COLORS['purple_text']}; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="tipo_Seguridad"] {{ background: {COLORS['severity_high_bg']}; color: {COLORS['severity_high_text']}; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="tipo_Operación"] {{ background: {COLORS['teal_soft']}; color: {COLORS['teal_dark']}; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="dot_ok"] {{ background: {COLORS['green']}; border-radius: 5px; }}
QLabel[cls="dot_off"] {{ background: {COLORS['muted']}; border-radius: 5px; }}
QLabel[cls="url"] {{ background: {COLORS['teal_soft']}; color: {COLORS['teal_dark']};
    font-family: Consolas, monospace; font-size: 11.5px; font-weight: 700;
    padding: 6px 10px; border-radius: 8px; }}

QLabel#toast {{
    background: #0F172A; color: #F8FAFC; font-size: 12.5px; font-weight: 700;
    border-radius: 11px; padding: 11px 17px;
}}
QLabel#toast[cls="ok"]   {{ background: #065F46; }}
QLabel#toast[cls="warn"] {{ background: #92400E; }}

QStatusBar {{ background: transparent; color: {COLORS['muted']}; font-size: 11px; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #CBD5E1; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #94A3B8; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; }}
QScrollBar::handle:horizontal {{ background: #CBD5E1; border-radius: 4px; min-width: 30px; }}
"""

# ---- subcontroles con iconos SVG reales (chevrons / calendario) -------------
# Se generan archivos al arrancar porque QSS solo acepta image: url(archivo).
def _subcontroles() -> str:
    return f"""
QComboBox::down-arrow {{ width: 15px; height: 15px; image: url("__CHEV_DOWN__"); }}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 22px; border: none; border-left: 1px solid {COLORS['line']};
    border-top-right-radius: 8px; background: transparent;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 22px; border: none; border-left: 1px solid {COLORS['line']};
    border-bottom-right-radius: 8px; background: transparent;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{ background: #F1F5F9; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ width: 12px; height: 12px; image: url("__CHEV_UP__"); }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ width: 12px; height: 12px; image: url("__CHEV_DOWN__"); }}

/* QDateEdit sin popup de calendario: flechas arriba/abajo */
QDateEdit::up-button, QDateEdit::down-button {{
    subcontrol-origin: border; width: 24px; border: none;
    border-left: 1px solid {COLORS['line']}; background: transparent;
}}
QDateEdit::up-button {{ subcontrol-position: top right; border-top-right-radius: 8px; }}
QDateEdit::down-button {{ subcontrol-position: bottom right; border-bottom-right-radius: 8px; }}
QDateEdit::up-button:hover, QDateEdit::down-button:hover {{ background: #F1F5F9; }}
QDateEdit::up-arrow {{ width: 12px; height: 12px; image: url("__CHEV_UP__"); }}
QDateEdit::down-arrow {{ width: 12px; height: 12px; image: url("__CHEV_DOWN__"); }}

/* botón de calendario (cuando calendarPopup está activo) */
QDateEdit::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 30px; border: none; border-left: 1px solid {COLORS['line']};
    border-top-right-radius: 8px; border-bottom-right-radius: 8px; background: transparent;
}}
QDateEdit::drop-down:hover {{ background: #F1F5F9; }}

/* fecha con popup de calendario: icono de calendario en vez de chevron */
QDateEdit[cal="true"]::down-arrow {{ width: 15px; height: 15px; image: url("__CAL__"); }}
"""


def qss(theme: str | None = None) -> str:
    """Construye el tema solicitado y recuerda el preferido en QSettings."""
    from PySide6.QtCore import QSettings

    settings = QSettings()
    selected = theme if theme is not None else settings.value("theme", "light", type=str)
    set_theme(selected)
    if theme is not None:
        settings.setValue("theme", _CURRENT_THEME)
    from ..core import db

    _svg = {
        "chev_down": '<path d="m6 9 6 6 6-6"/>',
        "chev_up": '<path d="m18 15-6-6-6 6"/>',
        "cal": ('<path d="M8 2v4"/><path d="M16 2v4"/>'
                '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>'),
    }
    dir_iconos = db.ruta_data() / "iconos"
    dir_iconos.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for nombre, interno in _svg.items():
        ruta = dir_iconos / f"{nombre}.svg"
        ruta.write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                f'fill="none" stroke="{COLORS["muted"]}" stroke-width="2.2" '
                f'stroke-linecap="round" stroke-linejoin="round">{interno}</svg>',
                encoding="utf-8")
        rutas[nombre] = ruta.as_posix()

    extra = _subcontroles().replace("__CHEV_DOWN__", rutas["chev_down"])
    extra = extra.replace("__CHEV_UP__", rutas["chev_up"])
    extra = extra.replace("__CAL__", rutas["cal"])
    return _build_qss() + extra
