"""Conexión SQLite, esquema y catálogos del sistema.

Este módulo es deliberadamente independiente de Qt para poder probarse
y ejecutarse desde la CLI (semilla, importaciones) sin interfaz gráfica.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------- catálogos
# Coinciden con la Tabla 6 de la tesis (TF-IN45) y con el catálogo de la maqueta.
PROCESOS = ["Costura", "Corte", "Etiquetado", "Acabado", "Calidad"]
TURNOS = ["Mañana", "Tarde", "Noche"]
CAUSAS = [
    "Operaciones no estandarizadas",
    "Errores humanos",
    "Incumplimiento del mantenimiento preventivo",
    "Descalibración de máquinas",
    "Variación en la calidad de los materiales",
    "Gestión inadecuada de materiales",
]
CAUSAS_MANO_OBRA = CAUSAS[0:2]
CAUSAS_MAQUINA = CAUSAS[2:4]
CRITICIDAD = ["Alta", "Media", "Baja"]
AREAS = ["Costura", "Corte", "Acabado", "Etiquetado", "Calidad"]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS maquinas (
    codigo            TEXT PRIMARY KEY,
    tipo              TEXT NOT NULL,
    marca_modelo      TEXT DEFAULT '',
    area              TEXT NOT NULL,
    criticidad        TEXT NOT NULL DEFAULT 'Media',
    fecha_compra      TEXT DEFAULT '',
    ultima_calibracion TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS operarios (
    codigo  TEXT PRIMARY KEY,
    nombre  TEXT NOT NULL,
    area    TEXT NOT NULL,
    proceso TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS produccion (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha          TEXT NOT NULL,
    proceso        TEXT NOT NULL,
    turno          TEXT NOT NULL,
    inspeccionadas INTEGER NOT NULL,
    nc_detectadas  INTEGER NOT NULL,
    UNIQUE (fecha, proceso, turno)
);

CREATE TABLE IF NOT EXISTS no_conformidades (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha      TEXT NOT NULL,
    turno      TEXT NOT NULL,
    proceso    TEXT NOT NULL,
    causa      TEXT NOT NULL,
    defecto    TEXT DEFAULT '',
    operario   TEXT DEFAULT '—',
    maquina    TEXT DEFAULT '—',
    cantidad   INTEGER NOT NULL DEFAULT 1,
    observacion TEXT DEFAULT '',
    creado_en  TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_nc_fecha   ON no_conformidades (fecha);
CREATE INDEX IF NOT EXISTS idx_nc_proceso ON no_conformidades (proceso);

CREATE TABLE IF NOT EXISTS frecuencias (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    maquina         TEXT NOT NULL,
    actividad       TEXT NOT NULL,
    frecuencia_dias INTEGER NOT NULL,
    responsable     TEXT DEFAULT 'Mantenimiento',
    UNIQUE (maquina, actividad)
);

CREATE TABLE IF NOT EXISTS metas (
    indicador TEXT PRIMARY KEY,
    as_is     REAL,
    to_be     REAL,
    unidad    TEXT DEFAULT '%'
);

CREATE TABLE IF NOT EXISTS importaciones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    archivo    TEXT,
    fecha      TEXT DEFAULT (datetime('now', 'localtime')),
    filas_ok   INTEGER DEFAULT 0,
    filas_error INTEGER DEFAULT 0,
    estado     TEXT DEFAULT 'importado'
);

-- ---- fase 2: checklists móviles y tarjetas TPM ----
CREATE TABLE IF NOT EXISTS plantilla_checklist (
    tipo TEXT NOT NULL,
    orden INTEGER NOT NULL,
    item TEXT NOT NULL,
    UNIQUE (tipo, item)
);

CREATE TABLE IF NOT EXISTS checklists (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    maquina    TEXT NOT NULL,
    operario   TEXT DEFAULT '—',
    turno      TEXT NOT NULL,
    fecha      TEXT NOT NULL,
    origen     TEXT DEFAULT 'celular',
    creada_en  TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_chk_fecha ON checklists (fecha);

CREATE TABLE IF NOT EXISTS checklist_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    checklist_id INTEGER NOT NULL REFERENCES checklists(id) ON DELETE CASCADE,
    item         TEXT NOT NULL,
    estado       TEXT NOT NULL CHECK (estado IN ('ok', 'falla')),
    severidad    TEXT DEFAULT '',
    comentario   TEXT DEFAULT '',
    foto         TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tarjetas_tpm (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT NOT NULL CHECK (tipo IN ('Mantenimiento', 'Seguridad', 'Operación')),
    severidad   TEXT NOT NULL CHECK (severidad IN ('Leve', 'Moderada', 'Crítica')),
    maquina     TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    origen      TEXT DEFAULT 'Manual',
    checklist_id INTEGER,
    estado      TEXT NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'atencion', 'cerrada')),
    responsable TEXT DEFAULT '—',
    creada_en   TEXT DEFAULT (datetime('now', 'localtime')),
    cerrada_en  TEXT
);
CREATE INDEX IF NOT EXISTS idx_tarj_estado ON tarjetas_tpm (estado);

-- ---- fase 3: motor del plan de mantenimiento preventivo (Fig. 42) ----
CREATE TABLE IF NOT EXISTS plan_ejecuciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    maquina     TEXT NOT NULL,
    actividad   TEXT NOT NULL,
    fecha       TEXT NOT NULL,
    responsable TEXT DEFAULT 'Mantenimiento',
    observacion TEXT DEFAULT '',
    creada_en   TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_exe_maquina ON plan_ejecuciones (maquina, actividad);
"""


def ruta_data() -> Path:
    """Carpeta de datos del sistema (~/.local/share/sicam o %APPDATA%/sicam)."""
    if base := os.environ.get("SICAM_DATA"):
        return Path(base)
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "sicam"
    return Path.home() / ".local" / "share" / "sicam"


def ruta_db() -> Path:
    return ruta_data() / "sicam.db"


def conectar(ruta: Path | str | None = None) -> sqlite3.Connection:
    """Abre la base de datos, crea el esquema si es nueva y activa WAL."""
    ruta = Path(ruta) if ruta else ruta_db()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ruta))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(ESQUEMA)
    return conn


def vaciar(conn: sqlite3.Connection) -> None:
    """Borra todo el contenido (para re-sembrar)."""
    tablas = [
        "no_conformidades", "produccion", "frecuencias", "metas",
        "operarios", "maquinas", "importaciones",
        "checklist_items", "checklists", "tarjetas_tpm", "plantilla_checklist",
        "plan_ejecuciones",
    ]
    with conn:
        for t in tablas:
            conn.execute(f"DELETE FROM {t}")


def contar(conn: sqlite3.Connection) -> dict[str, int]:
    out = {}
    for t in ("maquinas", "operarios", "produccion", "no_conformidades",
              "frecuencias", "metas", "importaciones",
              "checklists", "tarjetas_tpm", "plan_ejecuciones"):
        out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return out
