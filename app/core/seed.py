"""Semilla de datos sintéticos coherente con la tesis TF-IN45.

Genera:
  · Línea base 2024: tasa mensual ~10.4–11.2% (promedio 10.68%),
    causas distribuidas según la Tabla 7 (25.52 / 23.83 / 16.92 / 14.50 / 11.90 / 7.32).
  · Piloto jul–set 2026: tasa descendente 8.9 → 8.1 → 7.2%.
  · Máquinas, operarios, frecuencias (Fig. 42) y metas (Tablas 21/22).

Determinista (semilla fija) para que las demostraciones sean reproducibles.
"""
from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta

from . import db

RNG = random.Random(42)

MAQUINAS = [
    # codigo, tipo, marca_modelo, area, criticidad, fecha_compra, ultima_calibracion
    ("RECT-05", "Recta",           "Brother LN-2828",       "Costura",    "Alta",  "2021-04-12", "2026-07-02"),
    ("RECT-01", "Recta",           "Juki DDL-8700",         "Costura",    "Media", "2019-03-08", "2026-08-28"),
    ("OVE-01",  "Overlock",        "Juki MO-6714S",         "Costura",    "Alta",  "2018-08-19", "2026-09-02"),
    ("REC-02",  "Recubridora",     "Siruba F007J",          "Costura",    "Media", "2020-11-30", "2026-09-02"),
    ("COR-01",  "Cortadora",       "Eastman Blue Streak",   "Corte",      "Alta",  "2017-05-23", "2026-08-15"),
    ("ACB-01",  "Plancha / prensa", "Veit Brisay",          "Acabado",    "Media", "2022-02-14", "2026-08-30"),
    ("ETQ-03",  "Etiquetado",      "Estación manual",       "Etiquetado", "Media", "2023-01-10", "2026-09-10"),
]

OPERARIOS = [
    # codigo, nombre, area, proceso
    ("OP-01", "Rojas M.",    "Costura",    "Costura"),
    ("OP-02", "Torres L.",   "Costura",    "Costura"),
    ("OP-03", "Ccahuana P.", "Costura",    "Costura"),
    ("OP-04", "Flores A.",   "Costura",    "Costura"),
    ("OP-05", "Vilca S.",    "Costura",    "Costura"),
    ("OP-06", "Ortiz E.",    "Costura",    "Costura"),
    ("OP-07", "Quispe J.",   "Corte",      "Corte"),
    ("OP-08", "Huamán R.",   "Corte",      "Corte"),
    ("OP-09", "Paredes D.",  "Corte",      "Corte"),
    ("OP-10", "Medina K.",   "Etiquetado", "Etiquetado"),
    ("OP-11", "Salas C.",    "Etiquetado", "Etiquetado"),
    ("OP-12", "Ramos J.",    "Acabado",    "Acabado"),
    ("OP-13", "León P.",     "Calidad",    "Calidad"),
]

OPERARIOS_POR_PROCESO: dict[str, list[str]] = {}
for _, nombre, _, proceso in OPERARIOS:
    OPERARIOS_POR_PROCESO.setdefault(proceso, []).append(nombre)

MAQUINAS_POR_PROCESO: dict[str, list[str]] = {}
for codigo, _, _, area, *_ in MAQUINAS:
    MAQUINAS_POR_PROCESO.setdefault(area, []).append(codigo)

DEFECTOS: dict[str, list[str]] = {
    "Costura": [
        "Desfase de costura 3 mm", "Tensión de costura irregular", "Hilo sobrante en costura",
        "Puntadas saltadas", "Rotura de hilo repetida", "Costura doblada en puño",
        "Manga desalineada respecto a cuerpo", "Costura fruncida al iniciar",
    ],
    "Corte": [
        "Manga menor al estándar (S)", "Talla mezclada en lote", "Piezas cortadas contra trama",
        "Corte irregular por cuchilla", "Variación en medidas de corte",
    ],
    "Etiquetado": [
        "Etiqueta invertida", "Etiqueta incorrecta de talla", "Etiqueta despegada",
        "Código de barra ilegible",
    ],
    "Acabado": ["Planchado desigual", "Manchas por planchado", "Empaque incompleto"],
    "Calidad": ["Defecto detectado en inspección final", "Reproceso de prenda aprobada"],
}

# Tabla 7 — participación de cada causa (2024)
PESOS_CAUSA = [
    ("Operaciones no estandarizadas",                25.52),
    ("Errores humanos",                              23.83),
    ("Incumplimiento del mantenimiento preventivo",  16.92),
    ("Descalibración de máquinas",                   14.50),
    ("Variación en la calidad de los materiales",    11.90),
    ("Gestión inadecuada de materiales",              7.32),
]

# Tasa mensual 2024 (As-Is 10.68% promedio) — Fig. tendencia de la tesis
TASA_2024 = [11.2, 10.9, 10.8, 10.7, 10.6, 10.9, 10.5, 10.6, 10.7, 10.4, 10.7, 10.7]

# Piloto 2026 (mes, tasa)
PILOTO = {7: 8.9, 8: 8.1, 9: 7.2}

VOLUMEN_DIARIO = {"Costura": 720, "Corte": 310, "Etiquetado": 260, "Acabado": 148}

METAS = [
    # indicador, as_is, to_be — Tablas 21 y 22
    ("Tasa de prendas no conformes",      10.68, 4.95, "%"),
    ("Cumplimiento de checklists",         0.0,  85.0, "%"),
    ("Cumplimiento del plan TPM",         60.0,  85.0, "%"),
    ("Disponibilidad de máquinas",        80.0,  90.0, "%"),
    ("Reprocesos por errores operativos", 100.0, 70.0, "%"),
    ("Errores de etiquetado",             100.0, 60.0, "%"),
    ("Descalibraciones de máquinas",      100.0, 65.0, "%"),
]

# Fig. 42 — actividad y frecuencia por tipo de máquina
FRECUENCIAS_TIPO = {
    "Recta":           ("Lubricación y revisión de puntada", 7),
    "Overlock":        ("Revisión de cuchilla", 15),
    "Recubridora":     ("Calibración de tensión", 15),
    "Cortadora":       ("Revisión de sensor/encoder", 30),
    "Plancha / prensa": ("Limpieza y revisión de presión", 30),
    "Etiquetado":      ("Verificación de guías y estación", 30),
}


def _causa_aleatoria() -> str:
    r = RNG.random() * 100.0
    acum = 0.0
    for causa, peso in PESOS_CAUSA:
        acum += peso
        if r <= acum:
            return causa
    return PESOS_CAUSA[-1][0]


def _generar_nc_dia(fecha_iso: str, proceso: str, nc_total: int) -> list[tuple]:
    """Reparte el NC del día en filas (lotes de 3–12 prendas)."""
    filas = []
    restante = nc_total
    turnos = ["Mañana", "Tarde"]
    while restante > 0:
        cant = min(restante, RNG.randint(3, 12))
        restante -= cant
        causa = _causa_aleatoria()
        es_maquina = causa in db.CAUSAS_MAQUINA
        es_humana = causa in db.CAUSAS_MANO_OBRA
        maquinas = MAQUINAS_POR_PROCESO.get(proceso, [])
        fila = (
            fecha_iso,
            RNG.choice(turnos),
            proceso,
            causa,
            RNG.choice(DEFECTOS[proceso]),
            (RNG.choice(OPERARIOS_POR_PROCESO.get(proceso, ["—"]))
             if (es_humana or (not es_maquina and RNG.random() < 0.3)) else "—"),
            (RNG.choice(maquinas) if (es_maquina and maquinas) else "—"),
            cant,
            "",
        )
        filas.append(fila)
    return filas


def siembra(conn: sqlite3.Connection, reset: bool = False) -> dict[str, int]:
    """Puebla la base con datos sintéticos. Retorna conteos insertados."""
    if reset:
        db.vaciar(conn)

    with conn:
        conn.executemany("INSERT OR IGNORE INTO maquinas VALUES (?,?,?,?,?,?,?)", MAQUINAS)
        conn.executemany("INSERT OR IGNORE INTO operarios VALUES (?,?,?,?)", OPERARIOS)
        conn.executemany(
            "INSERT OR IGNORE INTO frecuencias (maquina, actividad, frecuencia_dias, responsable) "
            "SELECT ?, ?, ?, 'Mantenimiento'",
            [(m[0], FRECUENCIAS_TIPO[m[1]][0], FRECUENCIAS_TIPO[m[1]][1]) for m in MAQUINAS],
        )
        conn.executemany("INSERT OR IGNORE INTO metas VALUES (?,?,?,?)", METAS)

        filas_prod: list[tuple] = []
        filas_nc: list[tuple] = []

        def periodo(inicio: date, fin: date, tasa_de: "callable") -> None:
            d = inicio
            while d <= fin:
                if d.weekday() != 6:  # domingo sin producción
                    iso = d.isoformat()
                    for proceso, base in VOLUMEN_DIARIO.items():
                        insp = int(base * (1 + RNG.uniform(-0.08, 0.08)))
                        nc = int(round(insp * tasa_de(d) / 100.0))
                        # producción en dos turnos (55 / 45)
                        m = int(insp * 0.55)
                        filas_prod.append((iso, proceso, "Mañana", m, int(nc * 0.55)))
                        filas_prod.append((iso, proceso, "Tarde", insp - m, nc - int(nc * 0.55)))
                        filas_nc.extend(_generar_nc_dia(iso, proceso, nc))
                d += timedelta(days=1)

        # Línea base 2024
        periodo(date(2024, 1, 1), date(2024, 12, 31),
                lambda d: TASA_2024[d.month - 1])
        # Piloto 2026 (hasta la fecha de la maqueta)
        periodo(date(2026, 7, 1), date(2026, 9, 13),
                lambda d: PILOTO[d.month])

        conn.executemany(
            "INSERT INTO produccion (fecha, proceso, turno, inspeccionadas, nc_detectadas) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT (fecha, proceso, turno) DO UPDATE SET "
            "inspeccionadas=excluded.inspeccionadas, nc_detectadas=excluded.nc_detectadas",
            filas_prod,
        )
        conn.executemany(
            "INSERT INTO no_conformidades (fecha, turno, proceso, causa, defecto, operario, "
            "maquina, cantidad, observacion) VALUES (?,?,?,?,?,?,?,?,?)",
            filas_nc,
        )

    return {
        "produccion": len(filas_prod),
        "no_conformidades": len(filas_nc),
        "prendas_nc": sum(f[7] for f in filas_nc),
    } | sembrar_fase2(conn) | sembrar_fase3(conn)


def sembrar_fase3(conn: sqlite3.Connection) -> dict[str, int]:
    """Ejecuciones de mantenimiento pasadas para que el motor del plan (Fig. 42)
    tenga vencidas, próximas y hechas desde el primer arranque."""
    from . import plan_tpm

    hoy = date.today()
    historial = [
        # (maquina, días atrás, responsable, observación)
        ("RECT-05", 12, "Téc. Mendoza", "Lubricación completa; puntada uniforme."),
        ("RECT-01", 3, "Téc. Soto", "Rutina semanal sin hallazgos."),
        ("OVE-01", 17, "Téc. Mendoza", "Cuchilla con desgaste inicial."),
        ("REC-02", 8, "Téc. Soto", "Calibración de tensión según estándar."),
        ("COR-01", 24, "Téc. Mendoza", "Sensor limpio y verificado."),
        ("ACB-01", 34, "Téc. Soto", "Revisión de presión; manguera ajustada."),
        ("ETQ-03", 2, "Calidad", "Verificación de guías correcta."),
    ]
    n = 0
    with conn:
        for maquina, atras, resp, obs in historial:
            actividad = FRECUENCIAS_TIPO[next(m[1] for m in MAQUINAS if m[0] == maquina)][0]
            plan_tpm.registrar_ejecucion(
                conn, maquina, actividad,
                fecha=(hoy - timedelta(days=atras)).isoformat(),
                responsable=resp, observacion=obs)
            n += 1
    return {"plan_ejecuciones": n}


def sembrar_fase2(conn: sqlite3.Connection) -> dict[str, int]:
    """Plantillas de checklist + checklists y tarjetas TPM de muestra (hoy).

    Se usa también como migración ligera para bases creadas en la fase 1:
    no toca producción ni no conformidades, solo agrega lo de la fase 2.
    """
    from datetime import datetime

    from . import checklists

    checklists.sembrar_plantillas(conn)

    hoy = date.today().isoformat()
    n_chk = n_tarj = 0

    # 5 de 7 estaciones completaron hoy su checklist (cumplimiento ~71%)
    plan_hoy = [
        ("RECT-05", "Tarde", "Rojas M.", {"Tensión del hilo (prueba en retazo)": ("Moderada", "Costura fruncida al iniciar.")}),
        ("RECT-01", "Mañana", "Torres L.", {}),
        ("OVE-01", "Mañana", "Quispe J.", {"Estado de cuchilla (corte limpio)": ("Crítica", "Cortes irregulares en tela.")}),
        ("COR-01", "Mañana", "Huamán R.", {}),
        ("ETQ-03", "Tarde", "Medina K.", {}),
    ]
    hora_base = datetime.now()
    for maquina, turno, operario, fallas in plan_hoy:
        items = []
        for item in checklists.items_de_maquina(conn, maquina):
            if item in fallas:
                sev, com = fallas[item]
                items.append({"item": item, "estado": "falla", "severidad": sev, "comentario": com})
            else:
                items.append({"item": item, "estado": "ok"})
        res = checklists.registrar_checklist(conn, maquina, turno, operario, items, origen="semilla")
        n_chk += 1
        n_tarj += len(res["tarjetas"])
        # hora de muestra descendente (los más recientes arriba)
        con_hora = hora_base.replace(hour=12, minute=41 - n_chk * 7 if n_chk < 5 else 5)
        conn.execute("UPDATE checklists SET creada_en = ? WHERE id = ?",
                     (f"{hoy} {con_hora.strftime('%H:%M')}:00", res["checklist_id"]))

    # tarjetas de muestra en distintos estados (Figuras 43–45)
    extra = [
        ("Seguridad", "Crítica", "COR-01", "Protector de cuchilla retirado; riesgo de corte en operación.", "abierta"),
        ("Operación", "Leve", "ETQ-03", "Secuencia incorrecta de etiquetado detectada en lote.", "abierta"),
        ("Mantenimiento", "Moderada", "OVE-01", "Cuchilla desafilada generando cortes irregulares.", "atencion"),
        ("Mantenimiento", "Leve", "RECT-01", "Falta de lubricación leve en bandeja inferior.", "cerrada"),
    ]
    for tipo, sev, maq, desc, estado in extra:
        tid = checklists.crear_tarjeta_manual(conn, tipo, sev, maq, desc)
        checklists.cambiar_estado_tarjeta(
            conn, tid, estado,
            "Téc. Mendoza" if estado == "atencion" else "—")
        n_tarj += 1

    return {"checklists": n_chk, "tarjetas_tpm": n_tarj}


def main() -> None:
    import argparse

    from . import db

    parser = argparse.ArgumentParser(description="Siembra datos sintéticos del SICAM")
    parser.add_argument("--db", default=None, help="ruta alternativa de la base de datos")
    parser.add_argument("--reset", action="store_true", help="borra todo antes de sembrar")
    args = parser.parse_args()

    conn = db.conectar(args.db)
    res = siembra(conn, reset=args.reset)
    tot = db.contar(conn)
    print("Semilla lista:")
    for k, v in res.items():
        print(f"  {k:18} {v:>9,}".replace(",", "."))
    print("Conteo por tabla:", {k: v for k, v in tot.items() if v})


if __name__ == "__main__":
    main()
