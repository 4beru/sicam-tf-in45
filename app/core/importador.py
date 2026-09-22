"""Importador de la plantilla Excel con validación en seco (dry-run).

Flujo: leer(ruta) -> validar(datos, conn) -> [corregir errores] -> importar(conn, datos).
`validar` jamás toca la base de datos; `importar` hace upsert por clave natural.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import db, plantilla

HOJAS = plantilla.HOJAS


@dataclass
class FilaError:
    hoja: str
    fila: int  # número de fila de Excel (2 = primera de datos)
    columna: str
    detalle: str

    def como_fila(self) -> tuple[str, int, str, str]:
        return self.hoja, self.fila, self.columna, self.detalle


@dataclass
class ResultadoValidacion:
    errores: list[FilaError] = field(default_factory=list)
    datos: dict[str, list[dict]] = field(default_factory=dict)
    aviso_hojas: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errores


@dataclass
class ResultadoImportacion:
    resumen: dict[str, tuple[int, int]] = field(default_factory=dict)  # hoja -> (nuevos, actualizados)


# ------------------------------------------------------------------ lectura
def leer(ruta: Path | str) -> dict[str, list[dict]]:
    """Lee la plantilla y devuelve {hoja: [fila_dict, ...]}."""
    from openpyxl import load_workbook

    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(ruta)
    wb = load_workbook(ruta, data_only=True, read_only=True)

    faltantes = [h for h in HOJAS if h not in wb.sheetnames]
    if len(faltantes) == len(HOJAS):
        raise ValueError("El archivo no contiene ninguna hoja de la plantilla "
                         f"(se esperaban: {', '.join(HOJAS)}). ¿Descargaste la plantilla desde el sistema?")

    datos: dict[str, list[dict]] = {}
    for hoja, (columnas, _) in HOJAS.items():
        if hoja not in wb.sheetnames:
            continue
        ws = wb[hoja]
        filas: list[dict] = []
        for valores in ws.iter_rows(min_row=2, values_only=True):
            if all(v is None or str(v).strip() == "" for v in valores):
                continue
            fila = {}
            for j, col in enumerate(columnas):
                fila[col] = valores[j] if j < len(valores) else None
            filas.append(fila)
        if filas:
            datos[hoja] = filas
    wb.close()
    return datos


# ------------------------------------------------------------------ utilidades
def _texto(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _fecha(v, err: list[str]) -> str:
    """Normaliza fechas a ISO; acepta datetime, date, AAAA-MM-DD y DD/MM/AAAA."""
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    s = _texto(v)
    if not s:
        err.append("fecha vacía")
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    err.append(f"fecha no válida: '{s}' (usa AAAA-MM-DD o DD/MM/AAAA)")
    return ""


def _entero(v, err: list[str], minimo: int, nombre: str) -> int | None:
    try:
        n = int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        err.append(f"{nombre} no es un número: '{v}'")
        return None
    if n < minimo:
        err.append(f"{nombre} debe ser ≥ {minimo} (recibido {n})")
        return None
    return n


def _real(v, err: list[str], nombre: str) -> float | None:
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        err.append(f"{nombre} no es un número: '{v}'")
        return None


# ------------------------------------------------------------------ validación
def validar(datos: dict[str, list[dict]], conn: sqlite3.Connection) -> ResultadoValidacion:
    res = ResultadoValidacion(datos=datos)
    err = res.errores

    maq_db = {r[0] for r in conn.execute("SELECT codigo FROM maquinas")}

    # ------- maquinas
    vistos: set[str] = set()
    for i, f in enumerate(datos.get("maquinas", []), start=2):
        e: list[str] = []
        codigo = _texto(f.get("codigo"))
        if not codigo:
            e.append("codigo vacío")
        elif codigo in vistos:
            e.append(f"codigo '{codigo}' repetido en el archivo")
        else:
            vistos.add(codigo)
        tipo = _texto(f.get("tipo"))
        if not tipo:
            e.append("tipo vacío")
        area = _texto(f.get("area"))
        if area and area not in db.AREAS:
            e.append(f"area '{area}' no está en el catálogo {db.AREAS}")
        crit = _texto(f.get("criticidad")) or "Media"
        if crit not in db.CRITICIDAD:
            e.append(f"criticidad '{crit}' no está en {db.CRITICIDAD}")
        for col in ("fecha_compra", "ultima_calibracion"):
            s = _texto(f.get(col))
            if s:
                _fecha(s, e)  # solo para validar formato; el texto se guarda tal cual
        for msg in e:
            err.append(FilaError("maquinas", i, "", msg))
        maq_db.add(codigo)

    # ------- operarios
    vistos_op: set[str] = set()
    for i, f in enumerate(datos.get("operarios", []), start=2):
        e = []
        codigo = _texto(f.get("codigo"))
        if not codigo:
            e.append("codigo vacío")
        elif codigo in vistos_op:
            e.append(f"codigo '{codigo}' repetido en el archivo")
        else:
            vistos_op.add(codigo)
        if not _texto(f.get("nombre")):
            e.append("nombre vacío")
        proceso = _texto(f.get("proceso"))
        if proceso and proceso not in db.PROCESOS:
            e.append(f"proceso '{proceso}' no está en el catálogo {db.PROCESOS}")
        for msg in e:
            err.append(FilaError("operarios", i, "", msg))

    # ------- produccion
    vistas_prod: set[tuple[str, str, str]] = set()
    for i, f in enumerate(datos.get("produccion", []), start=2):
        e = []
        fecha = _fecha(f.get("fecha"), e)
        proceso = _texto(f.get("proceso"))
        if proceso not in db.PROCESOS:
            e.append(f"proceso '{proceso}' no está en el catálogo {db.PROCESOS}")
        turno = _texto(f.get("turno"))
        if turno not in db.TURNOS:
            e.append(f"turno '{turno}' no está en el catálogo {db.TURNOS}")
        _entero(f.get("prendas_inspeccionadas"), e, 1, "prendas_inspeccionadas")
        _entero(f.get("nc_detectadas"), e, 0, "nc_detectadas")
        clave = (fecha, proceso, turno)
        if clave in vistas_prod:
            e.append(f"fila duplicada en el archivo para {fecha} {proceso} {turno}")
        else:
            vistas_prod.add(clave)
        for msg in e:
            err.append(FilaError("produccion", i, "", msg))

    # ------- no_conformidades
    for i, f in enumerate(datos.get("no_conformidades", []), start=2):
        e = []
        _fecha(f.get("fecha"), e)
        proceso = _texto(f.get("proceso"))
        if proceso not in db.PROCESOS:
            e.append(f"proceso '{proceso}' no está en el catálogo {db.PROCESOS}")
        turno = _texto(f.get("turno"))
        if turno not in db.TURNOS:
            e.append(f"turno '{turno}' no está en el catálogo {db.TURNOS}")
        causa = _texto(f.get("causa"))
        if causa not in db.CAUSAS:
            e.append(f"causa '{causa}' no está en el catálogo de la Tabla 6")
        _entero(f.get("cantidad"), e, 1, "cantidad")
        maquina = _texto(f.get("maquina"))
        if maquina and maquina != "—" and maquina not in maq_db:
            e.append(f"maquina '{maquina}' no existe (ni en el archivo ni en la base de datos)")
        # el operario es texto libre: si no está registrado, se crea el hábito de
        # completarlo en la hoja 'operarios', pero no bloquea la importación
        for msg in e:
            err.append(FilaError("no_conformidades", i, "", msg))

    # ------- frecuencias
    for i, f in enumerate(datos.get("frecuencias", []), start=2):
        e = []
        maquina = _texto(f.get("maquina"))
        if maquina not in maq_db:
            e.append(f"maquina '{maquina}' no existe (ni en el archivo ni en la base de datos)")
        if not _texto(f.get("actividad")):
            e.append("actividad vacía")
        _entero(f.get("frecuencia_dias"), e, 1, "frecuencia_dias")
        for msg in e:
            err.append(FilaError("frecuencias", i, "", msg))

    # ------- metas
    for i, f in enumerate(datos.get("metas", []), start=2):
        e = []
        if not _texto(f.get("indicador")):
            e.append("indicador vacío")
        _real(f.get("as_is"), e, "as_is")
        _real(f.get("to_be"), e, "to_be")
        for msg in e:
            err.append(FilaError("metas", i, "", msg))

    return res


# ------------------------------------------------------------------ importación
def importar(conn: sqlite3.Connection, datos: dict[str, list[dict]]) -> ResultadoImportacion:
    res = ResultadoImportacion()

    tabla_clave = {
        "maquinas":   ("maquinas", "codigo"),
        "operarios":  ("operarios", "codigo"),
        "produccion": ("produccion", "fecha||'|'||proceso||'|'||turno"),
        "frecuencias": ("frecuencias", "maquina||'|'||actividad"),
        "metas":      ("metas", "indicador"),
    }

    def upsert(hoja: str, sql: str, filas: list[tuple], key_fn) -> tuple[int, int]:
        """Cuenta nuevos vs actualizados usando la tabla antes del insert."""
        tabla, expr = tabla_clave[hoja]
        claves = {r[0] for r in conn.execute(f"SELECT {expr} FROM {tabla}")}
        nuevos = sum(1 for f in filas if key_fn(f) not in claves)
        conn.executemany(sql, filas)
        return nuevos, len(filas) - nuevos

    with conn:
        if "maquinas" in datos:
            sql = ("INSERT INTO maquinas VALUES (?,?,?,?,?,?,?) "
                   "ON CONFLICT (codigo) DO UPDATE SET tipo=excluded.tipo, "
                   "marca_modelo=excluded.marca_modelo, area=excluded.area, "
                   "criticidad=excluded.criticidad, fecha_compra=excluded.fecha_compra, "
                   "ultima_calibracion=excluded.ultima_calibracion")
            filas = [(_t(f["codigo"]), _t(f["tipo"]), _t(f.get("marca_modelo")),
                      _t(f["area"]), _t(f.get("criticidad")) or "Media",
                      _t(f.get("fecha_compra")), _t(f.get("ultima_calibracion")))
                     for f in datos["maquinas"]]
            res.resumen["maquinas"] = upsert("maquinas", sql, filas, lambda f: f[0])

        if "operarios" in datos:
            sql = ("INSERT INTO operarios VALUES (?,?,?,?) "
                   "ON CONFLICT (codigo) DO UPDATE SET nombre=excluded.nombre, "
                   "area=excluded.area, proceso=excluded.proceso")
            filas = [(_t(f["codigo"]), _t(f["nombre"]), _t(f["area"]), _t(f["proceso"]))
                     for f in datos["operarios"]]
            res.resumen["operarios"] = upsert("operarios", sql, filas, lambda f: f[0])

        if "produccion" in datos:
            sql = ("INSERT INTO produccion (fecha, proceso, turno, inspeccionadas, nc_detectadas) "
                   "VALUES (?,?,?,?,?) ON CONFLICT (fecha, proceso, turno) DO UPDATE SET "
                   "inspeccionadas=excluded.inspeccionadas, nc_detectadas=excluded.nc_detectadas")
            filas = [(_fecha_iso(f["fecha"]), _t(f["proceso"]), _t(f["turno"]),
                      int(float(str(f["prendas_inspeccionadas"]))),
                      int(float(str(f["nc_detectadas"]))))
                     for f in datos["produccion"]]
            res.resumen["produccion"] = upsert(
                "produccion", sql, filas, lambda f: "|".join(f[:3]))

        if "no_conformidades" in datos:
            sql = ("INSERT INTO no_conformidades (fecha, turno, proceso, causa, defecto, "
                   "operario, maquina, cantidad, observacion) VALUES (?,?,?,?,?,?,?,?,?)")
            filas = [(_fecha_iso(f["fecha"]), _t(f["turno"]), _t(f["proceso"]), _t(f["causa"]),
                      _t(f.get("defecto")), _t(f.get("operario")) or "—",
                      _t(f.get("maquina")) or "—",
                      int(float(str(f["cantidad"]))), _t(f.get("observacion")))
                     for f in datos["no_conformidades"]]
            conn.executemany(sql, filas)
            res.resumen["no_conformidades"] = (len(filas), 0)

        if "frecuencias" in datos:
            sql = ("INSERT INTO frecuencias (maquina, actividad, frecuencia_dias, responsable) "
                   "VALUES (?,?,?,?) ON CONFLICT (maquina, actividad) DO UPDATE SET "
                   "frecuencia_dias=excluded.frecuencia_dias, responsable=excluded.responsable")
            filas = [(_t(f["maquina"]), _t(f["actividad"]),
                      int(float(str(f["frecuencia_dias"]))), _t(f.get("responsable")) or "Mantenimiento")
                     for f in datos["frecuencias"]]
            res.resumen["frecuencias"] = upsert(
                "frecuencias", sql, filas, lambda f: f"{f[0]}|{f[1]}")

        if "metas" in datos:
            sql = ("INSERT INTO metas VALUES (?,?,?,'%') "
                   "ON CONFLICT (indicador) DO UPDATE SET as_is=excluded.as_is, to_be=excluded.to_be")
            filas = [(_t(f["indicador"]),
                      float(str(f["as_is"]).replace(",", ".")),
                      float(str(f["to_be"]).replace(",", ".")))
                     for f in datos["metas"]]
            res.resumen["metas"] = upsert("metas", sql, filas, lambda f: f[0])

    return res


def registrar_importacion(conn: sqlite3.Connection, archivo: str,
                          filas_ok: int, filas_error: int, estado: str) -> None:
    with conn:
        conn.execute("INSERT INTO importaciones (archivo, filas_ok, filas_error, estado) "
                     "VALUES (?,?,?,?)", (archivo, filas_ok, filas_error, estado))


def _t(v) -> str:
    return "" if v is None else str(v).strip()


def _fecha_iso(v) -> str:
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s
