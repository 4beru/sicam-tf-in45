"""Smoke test offscreen: construye la app, recorre las páginas y captura PNGs.

Uso:  QT_QPA_PLATFORM=offscreen uv run python -m app.smoke
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# BD aislada para el smoke test (antes de importar db)
_tmp = Path(tempfile.mkdtemp(prefix="sicam-smoke-"))
os.environ["SICAM_DATA"] = str(_tmp)

from PySide6.QtWidgets import QApplication, QTableWidget  # noqa: E402

from .core import db, queries, seed  # noqa: E402
from .ui.shell import Shell  # noqa: E402
from .ui.theme import qss  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SICAM-smoke")
    app.setStyleSheet(qss())

    conn = db.conectar()
    resumen = seed.siembra(conn)

    shell = Shell(conn)
    shell.resize(1500, 950)
    shell.show()
    app.processEvents()

    capturas = Path(__file__).resolve().parent.parent / "capturas"
    capturas.mkdir(exist_ok=True)

    # servidor LAN: levantar y verificar que sirve el formulario
    from urllib.request import urlopen

    from .web.servidor import ServidorLAN

    servidor = ServidorLAN(8099)
    servidor.iniciar()
    respuesta = urlopen(f"{servidor.url_base()}/RECT-05", timeout=5)
    html_movil = respuesta.read().decode()
    servidor.detener()

    resultado: dict = {"bd": str(_tmp / "sicam.db"), "semilla": resumen, "paginas": {}}
    for pid in ("dashboard", "nc", "prod", "chk", "tpm", "maq", "plan", "iot", "rep", "datos"):
        shell.ir_a(pid)
        app.processEvents()
        png = capturas / f"{pid}.png"
        ok = shell.grab().save(str(png))
        w = shell.paginas[pid]
        resultado["paginas"][pid] = {
            "captura": str(png) if ok else None,
            "tablas": len(w.findChildren(QTableWidget)),
        }
    resultado["web"] = {
        "status_formulario": respuesta.status,
        "tiene_boton_falla": "FALLA" in html_movil,
        "tiene_foto_evidencia": "foto de evidencia" in html_movil,
        "url_ejemplo": servidor.url_estacion("RECT-05"),
    }

    # validaciones de datos
    tasa = queries.tasa_mensual(conn)
    meses_2024 = [m for m in tasa if m["mes"].startswith("2024")]
    prom_2024 = sum(m["nc"] for m in meses_2024) / sum(m["insp"] for m in meses_2024) * 100
    par = queries.pareto(conn)
    resultado["checks"] = {
        "meses": len(tasa),
        "tasa_2024_prom": round(prom_2024, 2),
        "causa_top": par[0][0],
        "causa_top_pct": par[0][2],
        "ultimo_mes": tasa[-1]["mes"],
        "tasa_ultimo_mes": tasa[-1]["tasa"],
    }
    from .core import iot

    alertas = iot.simular_paso(conn, "RECT-05")
    resultado["iot"] = {
        "umbrales": len(iot.umbrales(conn)),
        "historial_vibracion": len(iot.historial(conn, "RECT-05", "vibracion")),
        "alertas_pendientes": iot.alertas_pendientes(conn),
        "alertas_simuladas": len(alertas),
        "ultimas_por_maquina": len(iot.ultimas_por_maquina(conn)),
    }
    print(json.dumps(resultado, ensure_ascii=False, indent=1))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
