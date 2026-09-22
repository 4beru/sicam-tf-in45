"""Paleta y hoja de estilos QSS — espejo de la maqueta HTML (SICAM teal)."""
from __future__ import annotations

COLORS = {
    "bg":        "#EEF2F7",
    "surface":   "#FFFFFF",
    "line":      "#E2E8F0",
    "ink":       "#0F172A",
    "muted":     "#64748B",
    "teal":      "#0D9488",
    "teal_dark": "#0F766E",
    "teal_soft": "#CCFBF1",
    "amber":     "#F59E0B",
    "amber_soft": "#FEF3C7",
    "red":       "#EF4444",
    "red_soft":  "#FEE2E2",
    "green":     "#22C55E",
    "green_soft": "#DCFCE7",
    "purple":    "#8B5CF6",
    "purple_soft": "#EDE9FE",
    "sidebar":   "#0B1220",
    "sidebar_ink": "#94A3B8",
    "slate":     "#475569",
}

QSS = f"""
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
    color: #475569; font-size: 10px; font-weight: 800;
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
QLabel#sidebar_foot {{ color: #475569; font-size: 10.5px; }}

/* ---------- topbar ---------- */
QLabel#page_title {{ font-size: 19px; font-weight: 800; }}
QLabel#pill {{
    background: {COLORS['teal_soft']}; color: {COLORS['teal_dark']};
    font-size: 11.5px; font-weight: 700; padding: 5px 12px; border-radius: 11px;
}}
QPushButton#bell {{
    border: 1px solid {COLORS['line']}; border-radius: 9px;
    background: {COLORS['surface']}; padding: 6px;
}}
QPushButton#bell:hover {{ background: {COLORS['bg']}; }}

/* ---------- cards ---------- */
QFrame[cls="card"] {{
    background: {COLORS['surface']}; border: 1px solid {COLORS['line']};
    border-radius: 13px;
}}
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
QLabel[cls="chip_good"] {{ background: {COLORS['green_soft']};  color: #15803D; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}
QLabel[cls="chip_warn"] {{ background: {COLORS['amber_soft']};  color: #B45309; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}
QLabel[cls="chip_bad"]  {{ background: {COLORS['red_soft']};    color: #B91C1C; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}
QLabel[cls="chip_info"] {{ background: #E0F2FE;                 color: #0369A1; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}
QLabel[cls="chip_teal"] {{ background: {COLORS['teal_soft']};   color: {COLORS['teal_dark']}; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}
QLabel[cls="chip_purple"] {{ background: {COLORS['purple_soft']}; color: #6D28D9; font-size: 10.5px; font-weight: 800; padding: 3px 9px; border-radius: 10px; }}

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
QComboBox::drop-down:hover {{ background: #F1F5F9; }}
QComboBox QAbstractItemView {{
    background: {COLORS['surface']}; border: 1px solid {COLORS['line']};
    selection-background-color: {COLORS['teal_soft']}; selection-color: {COLORS['teal_dark']};
    outline: none;
}}

/* ---------- tablas ---------- */
QTableView, QTableWidget {{
    background: {COLORS['surface']}; border: none; alternate-background-color: #F8FAFC;
    gridline-color: #F1F5F9; selection-background-color: {COLORS['teal_soft']};
    selection-color: {COLORS['ink']}; font-size: 12px;
}}
QTableView::item, QTableWidget::item {{ padding: 5px 8px; border-bottom: 1px solid #F1F5F9; }}
QHeaderView::section {{
    background: {COLORS['surface']}; color: {COLORS['muted']};
    font-size: 10.5px; font-weight: 800; text-transform: uppercase;
    border: none; border-bottom: 1px solid {COLORS['line']}; padding: 7px 8px;
}}
QTableWidget::item:selected {{ background: {COLORS['teal_soft']}; color: {COLORS['ink']}; }}

/* ---------- banner / toast ---------- */
QFrame[cls="banner"] {{
    background: {COLORS['teal_soft']}; border: 1px solid #99F6E4; border-radius: 12px;
}}
QLabel[cls="banner_txt"] {{ color: #134E4A; font-size: 12.5px; }}

/* ---------- plan TPM: celdas de semana ---------- */
QPushButton[cls="st_done"]  {{ background: {COLORS['green_soft']}; color: #15803D; font-size: 10.5px; font-weight: 800; border: none; border-radius: 8px; padding: 5px 10px; }}
QPushButton[cls="st_over"]  {{ background: {COLORS['red_soft']}; color: #B91C1C; font-size: 10.5px; font-weight: 800; border: 1px solid #FCA5A5; border-radius: 8px; padding: 5px 10px; }}
QPushButton[cls="st_over"]:hover  {{ background: #FECACA; }}
QPushButton[cls="st_soon"]  {{ background: {COLORS['amber_soft']}; color: #B45309; font-size: 10.5px; font-weight: 800; border: none; border-radius: 8px; padding: 5px 10px; }}
QPushButton[cls="st_soon"]:hover  {{ background: #FDE68A; }}
QPushButton[cls="st_sched"] {{ background: #F1F5F9; color: {COLORS['slate']}; font-size: 10.5px; font-weight: 800; border: none; border-radius: 8px; padding: 5px 10px; }}
QPushButton[cls="st_sched"]:hover {{ background: #E2E8F0; }}
QLabel[cls="st_none"] {{ color: #CBD5E1; font-weight: 800; }}

/* ---------- fichas de máquinas ---------- */
QFrame[cls="maq-card"] {{
    background: {COLORS['surface']}; border: 1.5px solid {COLORS['line']}; border-radius: 12px;
}}
QFrame[cls="maq-card"]:selected, QFrame[cls="maq-sel"] {{
    border-color: {COLORS['teal']}; background: #F0FDFA;
}}
QLabel[cls="ficha_lbl"] {{ color: {COLORS['muted']}; font-size: 10px; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.4px; }}
QFrame[cls="ficha"] {{ background: {COLORS['bg']}; border-radius: 10px; }}

/* ---------- kanban tarjetas TPM ---------- */
QFrame[cls="kcol"] {{ background: #E9EDF3; border-radius: 13px; }}
QFrame[cls="kcard"] {{
    background: {COLORS['surface']}; border: 1px solid {COLORS['line']}; border-radius: 11px;
}}
QLabel[cls="kcard_title"] {{ font-size: 12.5px; font-weight: 700; }}
QLabel[cls="sev_Leve"] {{ background: #E0F2FE; color: #0369A1; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="sev_Moderada"] {{ background: {COLORS['amber_soft']}; color: #B45309; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="sev_Crítica"] {{ background: {COLORS['red_soft']}; color: #B91C1C; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="tipo_Mantenimiento"] {{ background: {COLORS['purple_soft']}; color: #6D28D9; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="tipo_Seguridad"] {{ background: {COLORS['red_soft']}; color: #B91C1C; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="tipo_Operación"] {{ background: {COLORS['teal_soft']}; color: {COLORS['teal_dark']}; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; }}
QLabel[cls="dot_ok"] {{ background: {COLORS['green']}; border-radius: 5px; }}
QLabel[cls="dot_off"] {{ background: #94A3B8; border-radius: 5px; }}
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
_SUBCONTROLES = f"""
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


def qss() -> str:
    """QSS completo, con chevrons/calendario como archivos SVG en disco."""
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
        if not ruta.exists():
            ruta.write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                f'fill="none" stroke="#64748B" stroke-width="2.2" '
                f'stroke-linecap="round" stroke-linejoin="round">{interno}</svg>',
                encoding="utf-8")
        rutas[nombre] = ruta.as_posix()

    extra = _SUBCONTROLES.replace("__CHEV_DOWN__", rutas["chev_down"])
    extra = extra.replace("__CHEV_UP__", rutas["chev_up"])
    extra = extra.replace("__CAL__", rutas["cal"])
    return QSS + extra
