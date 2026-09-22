"""Módulo CORE del monitor IoT (Figura 47 de la tesis).

Núcleo de datos del monitor de máquinas textiles: umbrales por variable,
clasificación de lecturas (ok / A / C / D), registro de lecturas con
detección de transiciones a alerta, y conversión de alertas en tarjetas
TPM o no conformidades.

Deliberadamente independiente de Qt y de Flask: solo sqlite3 y el resto
del paquete core, para poder probarse y ejecutarse desde la CLI.
"""
from __future__ import annotations

import random
import sqlite3
from datetime import date

from . import db

VARIABLES = ["tension", "velocidad", "temperatura", "vibracion"]
NIVELES = ("ok", "A", "C", "D")

ETIQUETAS = {
    "tension": "Tensión de hilo",
    "velocidad": "Velocidad",
    "temperatura": "Temperatura",
    "vibracion": "Vibración",
}

# variable, unidad, min_escala, max_escala, ok_lo, ok_hi, a_lo, a_hi, paso_sim
UMBRALES_POR_DEFECTO = [
    ("tension", "cN", 35.0, 65.0, 45.0, 55.0, 40.0, 60.0, 1.1),
    ("velocidad", "spm", 3000.0, 6000.0, 4300.0, 5200.0, 4000.0, 5500.0, 55.0),
    ("temperatura", "°C", 30.0, 95.0, 45.0, 70.0, 40.0, 75.0, 1.3),
    ("vibracion", "mm/s", 0.0, 8.0, 0.0, 4.5, -1.0, 5.2, 0.22),
]

CAMPOS_UMBRAL = {"unidad", "min_escala", "max_escala",
                 "ok_lo", "ok_hi", "a_lo", "a_hi", "paso_sim"}


# ------------------------------------------------------------------ umbrales
def sembrar_umbrales(conn: sqlite3.Connection) -> None:
    """Reemplaza los umbrales por los valores por defecto (idempotente)."""
    with conn:
        conn.execute("DELETE FROM iot_umbrales")
        conn.executemany(
            "INSERT INTO iot_umbrales (variable, unidad, min_escala, max_escala, "
            "ok_lo, ok_hi, a_lo, a_hi, paso_sim) VALUES (?,?,?,?,?,?,?,?,?)",
            UMBRALES_POR_DEFECTO)


def umbrales(conn: sqlite3.Connection) -> dict[str, dict]:
    """Devuelve {variable: {unidad, min_escala, max_escala, ok_lo, ok_hi,
    a_lo, a_hi, paso_sim}} con los umbrales vigentes."""
    out: dict[str, dict] = {}
    for r in conn.execute("SELECT * FROM iot_umbrales"):
        out[r["variable"]] = {
            "unidad": r["unidad"],
            "min_escala": r["min_escala"],
            "max_escala": r["max_escala"],
            "ok_lo": r["ok_lo"],
            "ok_hi": r["ok_hi"],
            "a_lo": r["a_lo"],
            "a_hi": r["a_hi"],
            "paso_sim": r["paso_sim"],
        }
    return out


def actualizar_umbral(conn: sqlite3.Connection, variable: str, **campos) -> None:
    """Actualiza uno o más campos de un umbral existente.

    Acepta solo campos de {unidad, min_escala, max_escala, ok_lo, ok_hi,
    a_lo, a_hi, paso_sim}; lanza ValueError si la variable no existe o si
    se pasa un campo no válido.
    """
    if variable not in VARIABLES:
        raise ValueError(f"variable no existe: {variable}")
    invalidos = set(campos) - CAMPOS_UMBRAL
    if invalidos:
        raise ValueError(f"campos no válidos: {sorted(invalidos)}")
    if not campos:
        return
    fila = conn.execute("SELECT 1 FROM iot_umbrales WHERE variable = ?",
                        (variable,)).fetchone()
    if not fila:
        raise ValueError(f"variable no existe: {variable}")
    sets = ", ".join(f"{k} = ?" for k in campos)
    with conn:
        conn.execute(f"UPDATE iot_umbrales SET {sets} WHERE variable = ?",
                     (*campos.values(), variable))


# ------------------------------------------------------------------ reglas
def clasificar(valor: float, u: dict) -> str:
    """Clasifica un valor según los umbrales: ok / A / C (regla de la maqueta)."""
    if u["ok_lo"] <= valor <= u["ok_hi"]:
        return "ok"
    if u["a_lo"] <= valor <= u["a_hi"]:
        return "A"
    return "C"


def _fmt_valor(variable: str, valor: float) -> str:
    """Formatea el valor con 1 decimal salvo la velocidad (0 decimales)."""
    if variable == "velocidad":
        return f"{valor:.0f}"
    return f"{valor:.1f}"


def mensaje_alerta(variable: str, nivel: str, valor: float, u: dict) -> str:
    """Mensaje legible de una alerta A o C para mostrar en la UI."""
    etiqueta = ETIQUETAS[variable]
    v = _fmt_valor(variable, valor)
    if nivel == "A":
        ok_lo = _fmt_valor(variable, u["ok_lo"])
        ok_hi = _fmt_valor(variable, u["ok_hi"])
        return f"{etiqueta} {v} fuera del rango normal ({ok_lo}–{ok_hi}). Ajuste preventivo."
    direccion = "sobre umbral"
    if u["a_lo"] > u["min_escala"] and valor < u["a_lo"]:
        direccion = "bajo umbral"
    return f"{etiqueta} {v} {direccion}. Detener y calibrar."


# ------------------------------------------------------------------ lecturas
def registrar_lectura(conn: sqlite3.Connection, maquina: str, variable: str,
                      valor: float, origen: str = "sim") -> dict:
    """Registra una lectura y, si hay transición a alerta A/C, crea la alerta.

    Retorna {"id", "nivel", "alerta"}; alerta es el dict completo de la alerta
    creada o None. Valida máquina existente, variable válida y valor numérico.
    """
    if variable not in VARIABLES:
        raise ValueError(f"variable no válida: {variable}")
    if conn.execute("SELECT 1 FROM maquinas WHERE codigo = ?",
                    (maquina,)).fetchone() is None:
        raise ValueError(f"máquina no existe: {maquina}")
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"valor no numérico: {valor!r}")

    u = dict(conn.execute("SELECT * FROM iot_umbrales WHERE variable = ?",
                          (variable,)).fetchone())
    nivel = clasificar(valor, u)

    with conn:
        prev = conn.execute(
            "SELECT nivel FROM iot_lecturas WHERE maquina = ? AND variable = ? "
            "ORDER BY id DESC LIMIT 1", (maquina, variable)).fetchone()
        lectura_id = conn.execute(
            "INSERT INTO iot_lecturas (maquina, variable, valor, nivel, origen) "
            "VALUES (?,?,?,?,?)", (maquina, variable, valor, nivel, origen)).lastrowid
        alerta = None
        if nivel in ("A", "C") and (prev is None or prev["nivel"] != nivel):
            mensaje = mensaje_alerta(variable, nivel, valor, u)
            aid = conn.execute(
                "INSERT INTO iot_alertas (maquina, variable, nivel, mensaje, valor) "
                "VALUES (?,?,?,?,?)", (maquina, variable, nivel, mensaje, valor)).lastrowid
            alerta = dict(conn.execute(
                "SELECT * FROM iot_alertas WHERE id = ?", (aid,)).fetchone())

    return {"id": lectura_id, "nivel": nivel, "alerta": alerta}


def ultima_lectura(conn: sqlite3.Connection, maquina: str, variable: str) -> dict | None:
    """Última lectura de (máquina, variable) o None si no hay."""
    r = conn.execute(
        "SELECT * FROM iot_lecturas WHERE maquina = ? AND variable = ? "
        "ORDER BY id DESC LIMIT 1", (maquina, variable)).fetchone()
    return dict(r) if r else None


def historial(conn: sqlite3.Connection, maquina: str, variable: str,
              limite: int = 60) -> list[dict]:
    """Últimas N lecturas de (máquina, variable) en orden ascendente."""
    filas = conn.execute(
        "SELECT id, valor, nivel, origen, ts FROM iot_lecturas "
        "WHERE maquina = ? AND variable = ? ORDER BY id DESC LIMIT ?",
        (maquina, variable, limite)).fetchall()
    filas.reverse()
    return [dict(r) for r in filas]


def ultimas_por_maquina(conn: sqlite3.Connection) -> dict[str, dict]:
    """Última lectura de cada variable por máquina:
    {maquina: {variable: {valor, nivel, ts}}}."""
    out: dict[str, dict] = {}
    for r in conn.execute(
            "SELECT maquina, variable, valor, nivel, ts FROM iot_lecturas "
            "ORDER BY id ASC"):
        out.setdefault(r["maquina"], {})[r["variable"]] = {
            "valor": r["valor"], "nivel": r["nivel"], "ts": r["ts"]}
    return out


# ------------------------------------------------------------------ alertas
def registrar_alerta(conn: sqlite3.Connection, maquina: str, variable: str,
                     nivel: str, mensaje: str, valor: float) -> int:
    """Inserta una alerta manual (p. ej. nivel D: etiqueta invertida)."""
    with conn:
        return conn.execute(
            "INSERT INTO iot_alertas (maquina, variable, nivel, mensaje, valor) "
            "VALUES (?,?,?,?,?)",
            (maquina, variable, nivel, mensaje, valor)).lastrowid


def alertas(conn: sqlite3.Connection, limite: int = 200,
            solo_pendientes: bool = False) -> list[dict]:
    """Alertas ordenadas por id descendente; opcionalmente solo pendientes."""
    if solo_pendientes:
        filas = conn.execute(
            "SELECT * FROM iot_alertas WHERE atendida = 0 "
            "ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    else:
        filas = conn.execute(
            "SELECT * FROM iot_alertas ORDER BY id DESC LIMIT ?",
            (limite,)).fetchall()
    return [dict(r) for r in filas]


def alertas_pendientes(conn: sqlite3.Connection) -> int:
    """Número de alertas sin atender."""
    return conn.execute(
        "SELECT COUNT(*) FROM iot_alertas WHERE atendida = 0").fetchone()[0]


def atender_alerta(conn: sqlite3.Connection, alerta_id: int) -> None:
    """Marca una alerta como atendida."""
    with conn:
        conn.execute("UPDATE iot_alertas SET atendida = 1 WHERE id = ?",
                     (alerta_id,))


def crear_tarjeta_desde_alerta(conn: sqlite3.Connection, alerta_id: int) -> int:
    """Convierte una alerta A/C no atendida en tarjeta TPM de mantenimiento.

    Severidad Crítica si nivel C, Moderada si A; origen "IoT". Marca la alerta
    atendida y le asigna el id de la tarjeta. Lanza ValueError si no procede.
    """
    a = conn.execute("SELECT * FROM iot_alertas WHERE id = ?",
                     (alerta_id,)).fetchone()
    if a is None:
        raise ValueError(f"alerta no existe: {alerta_id}")
    if a["nivel"] not in ("A", "C"):
        raise ValueError("solo alertas A o C generan tarjeta TPM")
    if a["atendida"]:
        raise ValueError("la alerta ya fue atendida")
    severidad = "Crítica" if a["nivel"] == "C" else "Moderada"
    with conn:
        tid = conn.execute(
            "INSERT INTO tarjetas_tpm (tipo, severidad, maquina, descripcion, origen) "
            "VALUES ('Mantenimiento', ?, ?, ?, 'IoT')",
            (severidad, a["maquina"], a["mensaje"])).lastrowid
        conn.execute("UPDATE iot_alertas SET atendida = 1, tarjeta_id = ? WHERE id = ?",
                     (tid, alerta_id))
    return tid


def registrar_nc_desde_alerta(conn: sqlite3.Connection, alerta_id: int,
                              defecto: str = "", cantidad: int = 1) -> int:
    """Convierte una alerta D en no conformidad y la marca atendida.

    Usa el área de la máquina como proceso y la causa "Descalibración de
    máquinas". Lanza ValueError si el nivel no es D.
    """
    a = conn.execute("SELECT * FROM iot_alertas WHERE id = ?",
                     (alerta_id,)).fetchone()
    if a is None:
        raise ValueError(f"alerta no existe: {alerta_id}")
    if a["nivel"] != "D":
        raise ValueError("solo alertas D generan no conformidad")
    m = conn.execute("SELECT area FROM maquinas WHERE codigo = ?",
                     (a["maquina"],)).fetchone()
    proceso = m["area"] if m else ""
    defecto = defecto or "Detectada por sensor IoT (alerta D)"
    with conn:
        nc_id = conn.execute(
            "INSERT INTO no_conformidades (fecha, turno, proceso, causa, defecto, "
            "operario, maquina, cantidad) VALUES (?,?,?,?,?,?,?,?)",
            (date.today().isoformat(), "Tarde", proceso, "Descalibración de máquinas",
             defecto, "—", a["maquina"], cantidad)).lastrowid
        conn.execute("UPDATE iot_alertas SET atendida = 1 WHERE id = ?",
                     (alerta_id,))
    return nc_id


# ------------------------------------------------------------------ simulación
def simular_paso(conn: sqlite3.Connection, maquina: str,
                 rng: random.Random | None = None) -> list[dict]:
    """Avanza las 4 variables un paso (random walk) y devuelve las alertas.

    Usa random.Random(42) si no se pasa rng. Cada variable parte de su última
    lectura o del centro del rango ok y se mueve ±paso_sim, acotada a la escala.
    """
    rng = rng or random.Random(42)
    u = umbrales(conn)
    alertas: list[dict] = []
    for variable in VARIABLES:
        ub = u[variable]
        ult = conn.execute(
            "SELECT valor FROM iot_lecturas WHERE maquina = ? AND variable = ? "
            "ORDER BY id DESC LIMIT 1", (maquina, variable)).fetchone()
        base = ult["valor"] if ult else (ub["ok_lo"] + ub["ok_hi"]) / 2.0
        nuevo = base + (rng.random() - 0.5) * 2 * ub["paso_sim"]
        nuevo = max(ub["min_escala"], min(ub["max_escala"], nuevo))
        res = registrar_lectura(conn, maquina, variable, nuevo, origen="sim")
        if res["alerta"] is not None:
            alertas.append(res["alerta"])
    return alertas


def generar_historial(conn: sqlite3.Connection, maquina: str, n: int = 60,
                      rng: random.Random | None = None) -> None:
    """Siembra n lecturas por variable con el mismo random walk del simulador.

    Inserta todo en una sola transacción y sin generar alertas: es la línea
    base para que los gráficos no nazcan vacíos; las alertas nacen de las
    lecturas en vivo, no del historial.
    """
    rng = rng or random.Random(42)
    u = umbrales(conn)
    filas: list[tuple] = []
    for variable in VARIABLES:
        ub = u[variable]
        valor = (ub["ok_lo"] + ub["ok_hi"]) / 2.0
        for _ in range(n):
            valor += (rng.random() - 0.5) * 2 * ub["paso_sim"]
            valor = max(ub["min_escala"], min(ub["max_escala"], valor))
            filas.append((maquina, variable, valor, clasificar(valor, ub), "sim"))
    with conn:
        conn.executemany(
            "INSERT INTO iot_lecturas (maquina, variable, valor, nivel, origen) "
            "VALUES (?,?,?,?,?)", filas)
