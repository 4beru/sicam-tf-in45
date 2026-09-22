# SICAM — Sistema Integral de Calidad y Mantenimiento

Aplicación de escritorio (PySide6) para **Createl Trading S.A.C.** — trabajo TF-IN45.
Digitaliza las herramientas del Capítulo III de la tesis (TPM, Poka Yoke, IoT) para
producir el Capítulo IV de validación con resultados.

> v0.3 — Fase 3 de 4: máquinas, motor de plan TPM (Fig. 42) y reportes PDF.

## Ejecutar

```bash
cd sicam
uv run python -m app.main          # abre la app (siembra datos la primera vez)
```

Al arrancar, la app levanta el **servidor para celulares** en `http://IP-de-tu-PC:8080`.
Para probarlo con tu celular: ambos en el mismo wifi → página *Checklists* → escanea
el QR mostrado (o abre la URL en el navegador del celular).

Otros comandos:

```bash
uv run python -m app.core.seed --reset   # re-sembrar la línea base 2024 + piloto
uv run pytest -q                          # tests (importador, semilla, checklists, web)
QT_QPA_PLATFORM=offscreen uv run python -m app.smoke   # smoke test + capturas PNG
```

La base de datos vive en `~/.local/share/sicam/sicam.db` (Linux) o
`%APPDATA%\sicam\sicam.db` (Windows), junto a la carpeta `fotos/`.
Variables de entorno: `SICAM_DATA` (carpeta de datos) y `SICAM_DB` (archivo .db).

## Qué incluye este MVP

| Módulo | Detalle |
|---|---|
| **Dashboard** | KPIs del mes (incluye cumplimiento de checklists), Pareto de causas (Tabla 6), tendencia As-Is → Piloto → To-Be (Tabla 22), rankings de operarios y máquinas |
| **No conformidades** | Vistas rápidas ("este turno · Costura"), filtros por proceso/turno/causa/fechas, registro en ~30 s |
| **Producción diaria** | Registro de prendas inspeccionadas por proceso/turno con tasa NC calculada |
| **Checklists** | QR por estación + servidor LAN embebido: el operario llena el checklist en su celular, con foto de evidencia obligatoria por falla; cumplimiento del día vs meta ≥85% |
| **Tarjetas TPM** | Kanban Abiertas / En atención / Cerradas (Fig. 43-45); nacen solas desde las fallas de checklist y muestran la acción requerida según severidad + foto de evidencia |
| **Máquinas** | Ficha por equipo: criticidad, estado de calibración (>90 días = vencida), tarjetas abiertas, historial 12 meses y próxima tarea del plan |
| **Plan TPM** | Grid S1–S4 del mes generado por el motor (última ejecución + frecuencia, Fig. 42); celdas clicables para registrar ejecuciones; cumplimiento vs meta ≥85% |
| **Reportes** | PDFs generados con reportlab: plan mensual, Pareto de causas y resumen de indicadores (As-Is/To-Be/actual); NC exportable a Excel bidireccional |
| **Datos e importación** | Plantilla XLSX con listas desplegables, importador con **dry-run**, upsert sin duplicados, exportación a Excel y semilla sintética |

## Estructura

```
app/
├── main.py            # punto de entrada
├── smoke.py           # smoke test offscreen + capturas
├── core/              # lógica sin Qt (testeable, sirve también a la CLI y al servidor web)
│   ├── db.py          # esquema SQLite + catálogos (Tabla 6)
│   ├── seed.py        # semilla sintética: 2024 (10.68%) + piloto 2026 + checklists/tarjetas
│   ├── plantilla.py   # genera plantilla_sicam.xlsx / exporta NC a Excel
│   ├── importador.py  # leer → validar (dry-run) → importar (upsert)
│   ├── queries.py     # analítica: Pareto, tasas, rankings, metas, firma de reactividad
│   ├── checklists.py  # checklists → tarjetas TPM (regla de oro), cumplimiento, kanban
│   ├── plan_tpm.py    # motor del plan preventivo (Fig. 42): frecuencias → calendario
│   └── reportes.py    # PDFs con reportlab (plan, indicadores, Pareto)
├── web/
│   └── servidor.py    # servidor LAN (Flask) + formulario móvil mobile-first
└── ui/                # interfaz PySide6
    ├── shell.py       # ventana principal (sidebar + QStackedWidget + campana)
    ├── theme.py       # paleta + QSS con chevrons/calendario SVG (subcontroles)
    ├── icons.py       # iconos SVG de línea (estilo Lucide, sin emojis)
    ├── charts.py      # Pareto, tendencia y donut pintados con QPainter
    ├── widgets.py     # tarjetas, KPIs, chips, tablas, toast
    └── ... páginas: dashboard, no_conformidades, produccion, checklists, tarjetas, datos
```

## Hoja de ruta

- [x] **Fase 1** — Núcleo + NC + Dashboard + importador Excel
- [x] **Fase 2** — Checklists móviles (QR + servidor LAN embebido) y tarjetas TPM
- [x] **Fase 3** — Máquinas + motor de plan TPM (Fig. 42) + reportes PDF
- [ ] **Fase 4** — Monitor IoT (simulador → ESP32 vía HTTP) + empaquetado `.exe` (PyInstaller + GitHub Actions)

## Notas de reactividad

Cada 5 s el shell compara una *firma* del contenido (conteos y máximos de las tablas
mutables). Si algo cambió — un checklist desde un celular, una tarjeta, una ejecución
del plan, una importación — la página que estás viendo se refresca sola y la campana
se actualiza; no hay que volver a hacer clic en el módulo.

## Notas de packaging

Nuitka **no** compila cruzado Linux → Windows. El `.exe` se generará con PyInstaller
en un runner `windows-latest` de GitHub Actions (flujo pensado para la fase 4).
