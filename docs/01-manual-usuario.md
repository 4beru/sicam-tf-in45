# 1. Manual de usuario de SICAM

## 1.1 Alcance y propósito

SICAM es el **Sistema Integral de Calidad y Mantenimiento** de Createl Trading S.A.C. El software enlaza datos de producción, calidad, inspección autónoma de estaciones y mantenimiento. El objetivo es que el equipo pueda registrar hechos operativos, priorizar problemas repetitivos y generar evidencia e informes desde una base SQLite común.

Los módulos no tienen el mismo grado de automatización:

- **Registrar:** Producción diaria y No conformidades escriben datos manuales; los checklists móviles registran verificaciones y, si detectan fallas, generan tarjetas TPM.
- **Analizar:** el Dashboard calcula agregados desde producción y no conformidades; no demuestra por sí solo causalidad.
- **Actuar:** Tarjetas TPM permite mover una anomalía por estados; Plan TPM calcula tareas por frecuencia, aunque su acción de guardado desde la UI presenta la incompatibilidad descrita en el documento 4.
- **Monitorizar:** Monitor IoT procesa lecturas simuladas o HTTP. No controla físicamente las máquinas ni ejecuta una parada real.
- **Comunicar / conservar:** Reportes genera PDFs y Excel; Datos e importación permite plantilla, importación, exportación, auditoría y restauración destructiva del conjunto piloto.

No se debe asumir que toda pantalla está protegida por rol o que todo registro se enlaza a otro por una clave. Varias asociaciones son analíticas o por el código de máquina, no por una clave foránea.

## 1.2 Inicio de la aplicación

### Abrir SICAM

Desde el directorio del proyecto:

```bash
uv run python -m app.main
```

También hay un lanzador de raíz:

```bash
uv run python main.py
```

`app/main.py` crea la aplicación Qt, aplica el tema, abre SQLite y se asegura de que existan datos de arranque. Si tanto producción como no conformidades están vacías ejecuta la semilla inicial; si la base tiene datos, aplica comprobaciones/migraciones ligeras para máquinas de costura, checklists, ejecuciones del plan y datos IoT que falten. Al iniciar intenta levantar el servidor para celulares en el puerto 8080.

### Datos iniciales

La semilla incluye histórico sintético de 2024 y un piloto sintético de julio a noviembre de 2026, además de máquinas, operarios, frecuencias, metas, checklists de ejemplo, tarjetas y lecturas IoT. Estos registros son útiles para demostración, no evidencia de producción real. No utilice el comando de reseteo en una base que contenga datos operativos que desee conservar.

## 1.3 Ventana principal y controles globales

El archivo principal de la interfaz es [`app/ui/shell.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/shell.py).

| Control | Comportamiento actual | Alcance / limitación |
|---|---|---|
| Barra lateral | Navega entre diez pantallas; puede contraerse para mostrar solo iconos. Al entrar en una vista, el desplazamiento de esa vista vuelve al principio. | No es un mecanismo de permisos; cada botón simplemente cambia la página activa del `QStackedWidget`. |
| Selector “Mes del piloto” | Opciones: Agosto, Setiembre, Octubre y Noviembre de 2026. Cambia filtros/periodos de las páginas que implementan `set_mes_activo` y luego refresca las vistas. | No ofrece julio de 2026 aunque la semilla lo genera; tampoco es un selector de fecha para todos los módulos. Checklists del día, alertas IoT y parte del estado TPM permanecen vinculados a la fecha actual. |
| Valor inicial del mes | Si el mes del sistema está entre las cuatro opciones, lo selecciona; si no, selecciona Setiembre 2026. | No escoge automáticamente “el último mes con datos”; es una regla visual predeterminada. |
| Selector de usuario | Muestra “Supervisor — J. de Producción”, “Personal de Mantenimiento” u “Operario”. | Al cambiarlo muestra un aviso de que el filtrado por rol llegará en una fase futura. **No autentica ni bloquea operaciones.** |
| Campana | Cuenta tarjetas TPM cuyo estado no está cerrado más alertas IoT con `atendida = 0`. El tooltip separa ambos conteos. | Al hacer clic, prioriza ir a Tarjetas TPM si existe alguna tarjeta pendiente; solo si no hay tarjetas pendientes abre Monitor IoT cuando hay alertas. No abre un listado de ambas categorías. |
| Tema | Alterna tema claro/oscuro, actualiza la hoja de estilo Qt y los colores cacheados de los gráficos QPainter y refresca las páginas. | Es visual; no modifica datos operativos. |
| Toast | Mensaje temporal de éxito/aviso/error en la esquina inferior derecha, con duración aproximada de 3,4 segundos. | Es una confirmación visual generada por la UI; no sustituye la verificación del registro cuando la operación es importante. |
| Barra de estado | Muestra ruta de SQLite, fecha de inicio del piloto y la URL LAN cuando el servidor se inicia correctamente; si falla, informa el error de inicio. | La URL LAN debe ser alcanzable desde la red del celular y el firewall debe permitir el puerto. |
| Refresco automático | Cada cinco segundos calcula una firma de cambios; si detecta cambios actualiza la campana y refresca la vista activa. | La firma no incluye cada lectura IoT para evitar reconstruir todas las páginas cada dos segundos; Monitor IoT tiene su propio temporizador. Las vistas no se refrescan simultáneamente en cada tick, solo la activa. |

### Navegación real

| Grupo | Vista | Cuándo utilizarla |
|---|---|---|
| Monitoreo | Dashboard | Revisar calidad del periodo seleccionado, prioridades, cumplimiento de hoy/plan actual y pendientes IoT. |
| Monitoreo | Monitor IoT | Examinar la última lectura por variable de una máquina, historial reciente, alertas y umbrales. |
| Operación | No conformidades | Registrar un defecto detectado, filtrar incidencias y revisar el detalle disponible. |
| Operación | Producción diaria | Registrar o reemplazar el total inspeccionado y NC detectadas por fecha/proceso/turno. |
| Operación | Checklists | Mostrar el QR de una estación, administrar el servidor para celulares y consultar verificaciones recibidas. |
| Mantenimiento | Tarjetas TPM | Atender anomalías abiertas, asignar el responsable implícito de la UI, cambiar su estado y cerrar. |
| Mantenimiento | Máquinas | Consultar datos maestros, criticidad, calibración, tarjetas e historial de la máquina seleccionada. |
| Mantenimiento | Plan TPM | Consultar el calendario mensual generado por frecuencias y registrar ejecuciones (la UI de guardado presenta un defecto confirmado por inspección estática). |
| Sistema | Reportes | Generar PDF del plan, Pareto, indicadores y exportar NC del mes a XLSX. |
| Sistema | Datos e importación | Generar plantilla, exportar el registro completo de NC, importar XLSX, auditar o restaurar el piloto. |

---

## 1.4 Dashboard

**Código principal:** [`app/ui/dashboard.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/dashboard.py). Utiliza `core.queries`, `core.checklists`, `core.plan_tpm`, `core.iot` y widgets de `app/ui/charts.py`.

La disposición vigente es de **siete tarjetas principales** en grupos adaptables, no siete KPI equivalentes: tres tarjetas de resumen superiores y cuatro tarjetas inferiores (dos gráficos y dos rankings).

### Tarjeta 1 — “Calidad de producción”

- **Tasa de no conformidad:** porcentaje calculado como suma de `produccion.nc_detectadas` del mes / suma de `produccion.inspeccionadas` del mismo mes × 100. Aparece con dos decimales. Si no hay inspecciones, el resumen informa 0,00%.
- **As-Is:** valor de referencia leído desde `metas`, sembrado inicialmente en 10,68%. Es referencia de línea base, no necesariamente el promedio calculado en un conjunto de datos importado.
- **Meta / To-Be:** sembrada en 4,95%. La etiqueta “En meta” se activa si la tasa actual es menor o igual que To-Be.
- **Variación vs. periodo anterior:** diferencia de la tasa actual menos la del mes calendario anterior, en puntos porcentuales. Una variación negativa se muestra como mejora; positiva, como empeoramiento. Si el mes anterior no tiene inspecciones, el delta puede no mostrarse.
- **NC registradas:** total de `nc_detectadas` agregadas desde Producción diaria, no `COUNT(*)` de la tabla `no_conformidades`.
- **Prendas inspeccionadas:** suma de las inspeccionadas del mes; es el denominador de la tasa.
- **Proceso con más NC:** se calcula con `SUM(no_conformidades.cantidad)` agrupado por proceso en el mes. Por tanto, los indicadores principales de producción y el ranking pueden discrepar si los registros de NC no se corresponden con los contadores diarios.

**Uso recomendado:** si la tasa aumenta, comprobar la calidad de los datos de producción, comparar el delta, revisar el Pareto y abrir los detalles de NC del mismo mes. No concluir automáticamente que una máquina u operario causó el cambio sin validar la evidencia.

### Tarjeta 2 — “Cumplimiento operativo”

- **Checklists · hoy:** estaciones distintas con un checklist cuya fecha es hoy / total de máquinas registradas × 100, redondeado a entero. No mide el porcentaje de ítems contestados ni el número de checklists; mide máquinas que han completado al menos uno ese día. Meta sembrada: 85%.
- **Plan TPM:** muestra el cumplimiento del motor TPM para el mes actual del sistema (no necesariamente el mes elegido en el encabezado), tareas vencidas y ejecuciones en ese mes. Meta sembrada: 85%.
- **Estados “En meta”:** los calcula comparando cada valor con su meta configurada.

La selección mensual no convierte estos indicadores “hoy” en una serie histórica de checklists. El KPI de plan tampoco se desplaza automáticamente al mes piloto elegido en el navbar dentro del Dashboard.

### Tarjeta 3 — “Focos de atención”

- **Causa principal de NC:** primera causa del Pareto del mes activo. Su porcentaje corresponde a prendas afectadas por causa (`SUM(cantidad)`), no al porcentaje de registros de la tabla.
- **Proceso con más NC:** mayor suma de cantidad de prendas NC por proceso en el mes elegido.
- **Alertas IoT activas:** cantidad global de filas en `iot_alertas` con `atendida = 0`, sin filtro por mes ni por máquina.

### Gráfico — “Pareto de causas de no conformidad”

Fuente: `queries.pareto(conn, desde, hasta)`; tabla `no_conformidades`. Agrupa por `causa`, suma `cantidad`, ordena de mayor a menor y calcula el porcentaje de cada causa sobre la suma total del periodo. Las barras comparan la participación de cada causa; la línea muestra el porcentaje acumulado y la línea punteada señala el corte del 80%.

Interpretación: las primeras barras que llevan la curva acumulada hacia 80% son candidatas de priorización. El principio 80/20 es una regla práctica, no una garantía estadística. Como las cantidades son de prendas afectadas, una causa puede aparecer con menos registros pero con mayor impacto en unidades.

### Gráfico — “Tasa de NC — As-Is → Piloto → To-Be”

Fuente: `queries.tasa_mensual`. La serie incluye los meses existentes en la tabla Producción agregados por mes. La tasa mensual es `SUM(nc_detectadas) / SUM(inspeccionadas) × 100`. El código clasifica como piloto los periodos cuyo valor `AAAA-MM` es igual o posterior a `2026-07`; la semilla genera meses de 2024 y julio–noviembre de 2026.

La referencia As-Is proviene de la meta configurada (inicialmente 10,68%) y To-Be de 4,95%. El gráfico no crea datos faltantes: representa meses presentes en los registros. La interpretación debe separarse del hecho de que el piloto viene de una semilla sintética.

### Tabla — “Operarios con más NC · Corte”

Muestra como máximo cinco nombres en el proceso `Corte`, con posición, operario, cantidad agregada y causa dominante. El orden se calcula sumando `no_conformidades.cantidad` para cada nombre y ordenando descendentemente dentro del mes seleccionado; los registros con operario `—` se excluyen. La causa dominante es la de mayor suma para ese operario y proceso en el periodo.

**No es un ranking de desempeño individual ajustado por volumen trabajado**, y la columna “NC” representa suma de prendas afectadas, no número de filas NC. Usarlo para sancionar o evaluar personas sin contexto sería una interpretación incorrecta.

### Tabla — “Máquinas con más NC asociadas”

Ordena por suma de `no_conformidades.cantidad` agrupada por máquina no vacía ni igual a `—`, limitada a cinco. Añade la criticidad tomada del maestro `maquinas`. El mes viene del rango del dashboard. El dato se registra en la NC y no demuestra una relación automática con una fila de producción específica.

### Límites y uso

El Dashboard es de lectura. No se editan filas desde gráficos o rankings; las operaciones de modificación se realizan en Producción diaria, No conformidades, Checklists, Tarjetas TPM, Monitor IoT o Plan TPM. Si calidad, Pareto y rankings no concuerdan, primero revisar el origen y el periodo de cada medida antes de asumir un defecto analítico.

---

## 1.5 Monitor IoT

**Código:** [`app/ui/iot_page.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/iot_page.py) y [`app/core/iot.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/core/iot.py).

### Cabecera y máquina seleccionada

- **Máquina:** lista los códigos de `maquinas`; los gauges y el historial se actualizan para esa máquina. Valor inicial `Costura 001`.
- **Simulador activo:** interruptor que hace que el temporizador de dos segundos agregue una lectura simulada por cada una de las cuatro variables para la máquina actualmente seleccionada. Al desactivarlo se siguen repintando valores, pero no se agregan lecturas del simulador.
- **Simular alerta C:** calcula un valor de vibración 0,7 unidades por encima de `a_hi` (por defecto 5,2, por tanto 5,9 mm/s) e intenta registrarlo como lectura. La alerta nueva depende de la transición respecto de la última lectura de esa variable.
- **Simular alerta D:** crea directamente un evento de alerta D por defecto, describiendo una prenda no conforme detectada por un sensor de etiqueta. No representa una medición de una de las cuatro variables continuas.

### Cuatro gauges

| Etiqueta | Nombre interno | Unidad por defecto | Rango de escala inicial | Normal inicial | Banda A inicial |
|---|---|---|---:|---:|---:|
| Tensión de hilo | `tension` | cN | 35–65 | 45–55 | 40–60 |
| Velocidad | `velocidad` | spm | 3000–6000 | 4300–5200 | 4000–5500 |
| Temperatura | `temperatura` | °C | 30–95 | 45–70 | 40–75 |
| Vibración | `vibracion` | mm/s | 0–8 | 0–4,5 | -1–5,2 |

La clasificación `ok` se asigna si el valor está dentro del rango normal, inclusive. Si no es normal pero está dentro de la banda A, se clasifica `A`; fuera de ambos rangos se clasifica `C`. A significa ajuste preventivo; C se presenta como detener y calibrar. No se envía comando de parada a una máquina.

Las lecturas que aparecen en los gauges son las últimas registradas para la máquina/variable. Un gauge sin lectura presenta “—”. Los valores/unidades vienen de SQLite, y los colores del chip reflejan el nivel calculado.

### Gráfico “Última hora · en vivo”

El selector “Variable” permite escoger una de las cuatro series. El gráfico muestra hasta 60 lecturas recientes (eje de tiempo rotulado “hace 60 min” a “ahora”). **El código no filtra por una hora de reloj:** recupera las últimas 60 filas ordenadas por id. Con el simulador activo a 2 s por paso, 60 puntos corresponden aproximadamente a dos minutos, por lo que no debe interpretarse como un historial garantizado de 60 minutos.

Las bandas, líneas y puntos visualizan normal/A/C conforme a los umbrales. El gráfico es informativo; no puede abrir un mantenimiento por seleccionar un punto.

### Registro de alertas

Se presenta un máximo de 50 alertas recientes, con nivel, máquina, mensaje y hora. Las alertas A/C generadas por lectura continua aparecen en el historial solo cuando existe una transición hacia un nivel de alerta diferente del nivel de la lectura anterior para esa máquina/variable; varias lecturas seguidas con el mismo nivel no crean una alerta duplicada cada vez.

- **Crear tarjeta TPM** (solo A/C pendiente): crea una tarjeta de tipo Mantenimiento con origen IoT. Nivel A produce severidad Moderada; nivel C, Crítica. Guarda `tarjeta_id` en la alerta y la marca atendida.
- **Registrar NC** (solo D pendiente): crea NC con fecha actual, turno fijo “Tarde”, proceso derivado del área de la máquina, causa “Descalibración de máquinas”, operario `—`, cantidad por defecto 1 y defecto por defecto “Detectada por sensor IoT (alerta D)”. Después marca la alerta atendida.
- **Atender:** marca la alerta como atendida sin crear una tarjeta ni una NC. Es una acción de reconocimiento/cierre del pendiente, no evidencia de que la anomalía física fue corregida.
- Las alertas atendidas quedan visibles con chip “Atendida”; si se creó una tarjeta, se muestra su código.

### Umbrales IoT

Los controles permiten cambiar `ok_lo`, `ok_hi`, `a_lo` y `a_hi` para cada variable. `Guardar umbrales` actualiza los campos modificados en `iot_umbrales`. La clasificación de **nuevas lecturas** utiliza esos umbrales.

Limitaciones: la función no valida que los límites inferior/superior estén ordenados o sean coherentes; el guardado no recalcula las lecturas históricas, no reescribe alertas ya generadas y no recalcula nivel D (D es un evento de defecto, no una banda de umbral). El toast de la UI sugiere que A/C/D “se recalculan”, algo más amplio que el comportamiento real.

### ESP32 y HTTP

El servidor LAN define `POST /iot/lectura` y `GET /iot/estado` en [`app/web/servidor.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/web/servidor.py). El JSON de una lectura continua admite `maquina`, `variable`, `valor`; las variables permitidas son las cuatro nombradas arriba, el código de máquina debe existir y `valor` debe ser numérico. En el caso de defecto se envía también `nivel: "D"`; la variable puede describir, por ejemplo, `etiqueta`, y `valor` numérico es obligatorio. JSON ausente/mal formado, máquina desconocida, variable inválida o valor no numérico producen HTTP 400.

Ejemplo para catálogo actual:

```bash
curl -X POST http://IP-DEL-PC:8080/iot/lectura \
  -H 'Content-Type: application/json' \
  -d '{"maquina":"Costura 001","variable":"vibracion","valor":5.9}'

curl http://IP-DEL-PC:8080/iot/estado
```

La respuesta de lectura indica id, nivel y alerta creada cuando aplica. `GET /iot/estado` devuelve las últimas lecturas agrupadas por máquina/variable. Los datos de origen `sim` y `esp32` se distinguen en `iot_lecturas`; para la ruta de alerta D no existe un campo de origen en `iot_alertas` que distinga inequívocamente la inyección de demostración de un evento real.

**Seguridad:** el servidor se enlaza a `0.0.0.0:8080`, usa HTTP y no aplica autenticación ni tokens a esos endpoints. Debe tratarse como servicio de confianza limitado a una LAN controlada, no exponerse a Internet.

---

## 1.6 No conformidades

**Código:** [`app/ui/no_conformidades.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/no_conformidades.py), lógica analítica en `app/core/queries.py`.

### Vistas rápidas y filtros

- **Todas:** consulta general dentro del rango de fechas seleccionado.
- **Este turno · Costura:** aplica proceso Costura y turno Tarde.
- **Hoy:** fuerza desde/hasta a la fecha real del sistema, aunque el mes seleccionado sea otro.
- **Causa: máquinas:** filtra las dos causas clasificadas en `db.CAUSAS_MAQUINA`: “Incumplimiento del mantenimiento preventivo” y “Descalibración de máquinas”.
- **Proceso / Turno / Causa:** opciones desde los catálogos de `app/core/db.py`.
- **Desde / Hasta:** fechas inclusivas en formato visible `dd/MM/yyyy`, aplicadas a la columna ISO `fecha`.

El periodo inicial coincide con el mes activo del encabezado. Si cambia el mes, el módulo repone el filtro “Todas” y actualiza los límites al mes completo.

### Tabla de resultados

Las filas se ordenan por `fecha DESC, id DESC` y se limitan a 200. Columnas: Fecha, Turno, Proceso, Causa, Defecto específico, Operario, Máquina y Cant. La tabla es de lectura; no hay edición ni eliminación de NC desde una fila. El resumen “registros” y “prendas NC” se calcula sobre las filas obtenidas (máximo 200), por lo que no debe interpretarse como total absoluto si el filtro devuelve más de 200 registros.

### Registrar una no conformidad

Botón **Registrar no conformidad** abre un diálogo con:

| Campo | Regla / efecto |
|---|---|
| Proceso * | Combo de `Costura`, `Corte`, `Etiquetado`, `Acabado`, `Calidad`. |
| Turno * | Combo `Mañana`, `Tarde`, `Noche`. |
| Causa raíz * | Combo agrupado visualmente en Mano de obra, Máquinas y Materiales; escribe una causa del catálogo. Si se intenta guardar en un separador, el código sustituye por la primera causa. |
| Defecto específico * | Texto libre; obligatorio no vacío. Describe el defecto observable, no la categoría de causa. |
| Operario | Combo del catálogo con opción `—`. |
| Máquina | Combo de códigos del maestro con opción `—`. |
| Cantidad de prendas * | Entero entre 1 y 100 000. |
| Observación | Texto libre opcional. |

**La fecha no aparece como campo editable del diálogo.** Se determina desde la UI: hoy si el mes seleccionado es el actual; en caso contrario, primer día del mes seleccionado. Por tanto el usuario no puede fechar una NC en un día arbitrario desde este formulario.

Al guardar se inserta una fila en `no_conformidades`; no se crea un vínculo individual con un registro de producción. Las comparaciones con Producción diaria ocurren por agregación de fechas/proceso/turno, y la integridad semántica de cada captura real no se garantiza automáticamente.

### Interpretación

La causa responde “qué factor contribuyente se clasifica”; el defecto específico describe qué se observó; cantidad indica cuántas prendas están afectadas por ese registro. No equivale necesariamente a cantidad de eventos o filas. Si una NC proviene de IoT D, parte de los campos se fija automáticamente en el código de integración (ver IoT).

---

## 1.7 Producción diaria

**Código:** [`app/ui/produccion.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/produccion.py).

### Formulario “Registrar producción del día”

- **Fecha:** calendario; debe pertenecer al mes seleccionado en el encabezado.
- **Proceso:** catálogo de procesos.
- **Turno:** Mañana, Tarde o Noche.
- **Prendas inspeccionadas:** entero de 1 a 1 000 000.
- **NC detectadas:** entero de 0 a 1 000 000; no puede exceder las inspeccionadas.
- **TASA NC ESTIMADA:** previsualización de `nc / inspeccionadas × 100` con un decimal; no escribe hasta registrar.
- **Registrar producción:** inserta o reemplaza el valor para la misma clave `fecha + proceso + turno`.

La base impone `UNIQUE(fecha, proceso, turno)`. Si la combinación ya existe, el botón no agrega una segunda fila ni suma automáticamente los valores: **reemplaza** inspeccionadas y NC detectadas por los nuevos números, y pone `origen_dato = 'manual'`. Confirmar las cifras totales antes de guardar.

### Gráfico “Tasa diaria · últimos 14 días del mes seleccionado”

Agrega NC detectadas e inspeccionadas por cada fecha con producción dentro del mes y calcula la tasa agregada por día. Recupera las últimas 14 fechas **que tienen registros**, no necesariamente los catorce días calendario inmediatamente anteriores si hubo días sin producción. La serie y las referencias As-Is / To-Be ayudan a observar tendencia.

### Tabla “Producción y tasa de NC · mes seleccionado”

Máximo 30 filas recientes, ordenadas por fecha descendente y proceso. Columnas Fecha, Proceso, Turno, Inspeccionadas, NC y Tasa NC. La tasa se calcula por fila. El color de tasa usa cortes de UI (>7% rojo, >5% ámbar, resto verde); esos cortes son fijos y no se derivan dinámicamente de la meta To-Be.

### Buenas prácticas

Registrar cantidades del mismo corte operacional; no escribir NC de más de las inspeccionadas; validar que una re-edición es un reemplazo total y no un incremento; después revisar el Dashboard del mismo mes. Las NC detalladas se registran separadamente en No conformidades y no quedan unidas por ID a esta fila.

---

## 1.8 Checklists móviles

**Código de escritorio:** [`app/ui/checklists_page.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/checklists_page.py). **Web móvil:** [`app/web/servidor.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/web/servidor.py). **Lógica:** `app/core/checklists.py`.

### Preparar una estación en la computadora

1. Abrir **Checklists**.
2. Seleccionar la estación en “QR de estación”. La lista del módulo ofrece `Costura 001`–`Costura 030`.
3. Verificar la URL que aparece. Si el servidor está activo, debe incluir la IP local de la computadora y el puerto 8080.
4. Para conservar el QR, pulsar **Imprimir QR de la estación** y guardar una imagen PNG. El botón abre un selector para guardar; la aplicación no envía directamente una impresión a la impresora.
5. Si aparece “Servidor detenido”, pulsar **Iniciar**. Si no puede enlazar el puerto, comprobar si ya está ocupado y si el firewall permite 8080.
6. Conectar celular y PC a la misma red Wi‑Fi de planta y abrir el QR desde el teléfono.

El servidor normalmente también se intenta iniciar cuando arranca la aplicación. La pantalla ofrece control manual para detenerlo o volver a iniciarlo.

### Formulario desde el celular

La URL `/` presenta una lista de estaciones; `/<maquina>` genera el formulario de mantenimiento autónomo adaptado al tipo de máquina. Campos principales:

- Máquina, tipo y área: identificados por la URL y el maestro de máquinas.
- Turno: selector con Mañana, Tarde y Noche; por defecto Tarde.
- Operario: selector de nombres del área de la máquina. En el caso de que no haya operarios en ese área, el código intenta usar todos los operarios; existe una ruta de fallback defectuosa porque consulta una conexión que ya fue cerrada, documentada en el documento 4.
- Cada ítem de la plantilla se marca `OK` o `FALLA`. Deben quedar verificados todos para que el botón del navegador se habilite en el flujo normal de la UI.
- En cada ítem marcado FALLA aparece severidad Leve, Moderada o Crítica, foto obligatoria y comentario opcional. La acción recomendada se presenta automáticamente como texto; no ejecuta una reparación física.

Plantillas: Recta (8 ítems), Overlock (8), Recubridora (7), Cortadora (6), Plancha/prensa (5) y Etiquetado (5). Si una máquina tiene un tipo no reconocido, la función de lógica usa la plantilla de Etiquetado como fallback.

### Fotos y envío

El cliente web intenta comprimir imágenes a un máximo de 1280 píxeles de lado y JPEG calidad 0,82. El servidor acepta solicitudes de hasta 16 MB. Si un ítem FALLA no incluye archivo de foto, el cliente muestra una alerta; el endpoint también rechaza el envío con HTTP 400 antes de registrar el checklist. La foto se guarda en disco y la ruta se registra en `checklist_items.foto`.

Al guardar, `registrar_checklist` escribe el registro padre, los ítems y una tarjeta TPM de origen Checklist por cada ítem fallido, dentro de la transacción SQLite. Cada tarjeta lleva máquina, severidad y una descripción formada por el nombre del ítem y comentario si existe. La evidencia queda asociada al ítem/foto del checklist; la tarjeta no contiene un campo propio de archivo.

La pantalla de escritorio muestra cumplimiento del día, ítems con falla, tarjetas creadas hoy y los 15 checklists más recientes. Doble clic en una fila abre un detalle y botones de acceso a fotos. El donut compara cumplimiento con meta (por defecto 85%).

**Interpretación de cumplimiento:** estaciones distintas con checklist hoy / máquinas del maestro. Una estación que envía varios checklists cuenta una sola vez para el numerador.

---

## 1.9 Tarjetas TPM

**Código:** [`app/ui/tarjetas_page.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/tarjetas_page.py), lógica `app/core/checklists.py`.

### Tablero Kanban

Tres columnas: **Abiertas**, **En atención** y **Cerradas**. Cada encabezado muestra el número de tarjetas en ese estado. La pantalla muestra hasta 30 tarjetas por columna tras aplicar el filtro de origen; el contenido de cada columna tiene desplazamiento propio.

Filtros de origen: Todos, Checklist, IoT, Manual y Semilla. El filtro etiquetado “Semilla” no consulta literalmente un origen `semilla` en las tarjetas: incluye orígenes Checklist y Manual, porque las tarjetas de muestra se crean mediante los mismos caminos que las operativas. Esta etiqueta no permite separar con certeza todas las tarjetas sintéticas.

Las tarjetas visibles muestran código legible `TPM-0001`, tipo, severidad, descripción, máquina, origen y hora/fecha de creación. Pulsar una tarjeta abre el diálogo de detalle.

### Crear una anomalía manual

1. Pulsar **Registrar anomalía**.
2. Elegir Tipo: Mantenimiento, Seguridad u Operación.
3. Elegir Severidad: Leve, Moderada o Crítica (por defecto Moderada).
4. Elegir Máquina / estación de catálogo.
5. Completar Descripción; es el único campo de texto validado como obligatorio.
6. Pulsar **Crear tarjeta**.

La tarjeta nace con estado `abierta`, origen `Manual`, fecha/hora de creación y responsable por defecto `—`.

### Ficha de tarjeta y transiciones

La ficha muestra máquina, origen, responsable, estado, fecha de creación, descripción y recomendación por severidad:

| Severidad | Recomendación visible |
|---|---|
| Leve | Corrección por operario |
| Moderada | Revisión por mantenimiento |
| Crítica | Intervención inmediata |

Estas frases son recomendaciones estáticas, no una orden enviada al equipo. Si la tarjeta proviene de un checklist se ofrecen enlaces a las fotos de los ítems fallidos relacionados con ese checklist.

- Si está abierta, aparece **Tomar (en atención)**. El diálogo cambia estado a `atencion` y asigna de forma fija a `Téc. Mendoza`.
- Si no está cerrada, aparece **Cerrar tarjeta**. Cambia estado a `cerrada`, asigna también `Téc. Mendoza` y registra `cerrada_en` con la hora local de SQLite.
- Si ya está cerrada, no ofrece transición desde el diálogo.

La función de lógica acepta más transiciones que la UI y al cambiar una tarjeta desde estado cerrado a otro estado no limpia `cerrada_en`. No se solicita fecha de cierre ni evidencia de reparación. La UI muestra un toast que dice “MTTR recalculado”, pero en el esquema y lógica inspeccionados no existe un cálculo de MTTR; ese mensaje no debe interpretarse como métrica implementada.

### Orígenes

- **Checklist:** generado por cada ítem FALLA; lleva `checklist_id` para enlazarlo lógicamente al origen.
- **IoT:** creado desde alerta A/C, severidad Moderada para A y Crítica para C.
- **Manual:** registrado en el diálogo o por datos demo.
- **Semilla:** no se representa como un valor uniforme del campo `origen` de la tarjeta; el filtro “Semilla” es una agregación de Checklist y Manual.

El cambio de estado actualiza el tablero y los KPI globales de pendientes. Cerrar tarjeta no cambia automáticamente la NC ni marca como corregida la lectura física que originó el caso.

---

## 1.10 Máquinas

**Código:** [`app/ui/maquinas_page.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/maquinas_page.py).

La vista combina una lista de selección a la izquierda y la ficha de la máquina activa a la derecha. La lista muestra código, tipo, marca/modelo, área y criticidad. El primer código alfabético se selecciona al abrir la vista si no había selección.

### Datos de ficha

- **Código:** identificador de máquina (clave primaria de `maquinas`).
- **Tipo / marca-modelo / área:** datos maestros; se pueden actualizar mediante importación, no editando desde esta ficha.
- **Criticidad:** Alta, Media o Baja; es un dato de clasificación, no un bloqueo automático.
- **Fecha de compra:** texto/fecha guardado en maestro.
- **Última calibración:** si no hay fecha muestra “Sin registro”; si la fecha no puede parsearse conserva el texto de fecha y color neutral; si el parseo ISO funciona, calcula días desde la fecha actual. Más de 90 días es “Vencida”; 90 o menos, “Al día”. El cálculo usa hoy, no el mes piloto seleccionado.
- **Tarjetas abiertas:** cuenta tarjetas de esa máquina con estado distinto de cerrada.
- **Tarjetas 12 m:** el KPI actual cuenta todas las tarjetas para la máquina sin filtro temporal, pese a la etiqueta “12 m”.
- **Próx. mantenimiento:** primera tarea de `plan_tpm.proxima_tarea` dentro del mes actual de sistema; puede mostrar “—” si no quedan tareas ese mes.
- **Tarjetas TPM por mes · histórico:** gráfica de tarjetas creadas en cada uno de los últimos 12 meses.

### Acciones

- **Nueva tarjeta para esta máquina:** abre el formulario manual TPM y preselecciona la máquina actual.
- **Ver en plan TPM:** navega a la pantalla Plan TPM.

No hay edición/alta/baja directa del maestro en esa vista. Las relaciones con checklists, alertas IoT, tarjetas y frecuencias se basan principalmente en el código de máquina. No hay una pantalla para registrar una calibración directamente; el dato del maestro se altera por importación o por cambios externos en los datos.

---

## 1.11 Plan TPM

**Código UI:** [`app/ui/plan_page.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/plan_page.py). **Motor:** [`app/core/plan_tpm.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/core/plan_tpm.py).

### Cómo se calcula el plan

Cada par máquina/actividad tiene una frecuencia de días guardada en `frecuencias`. La próxima tarea se calcula como última ejecución válida hasta la fecha de referencia + frecuencia. Si no existe ejecución, el motor produce una primera fecha determinista dentro del mes usando un desplazamiento calculado a partir del código de máquina y la actividad. Repite cada frecuencia hasta el fin del mes.

Estados del motor:

- `over` → **Vencida**, si faltan menos de cero días (la fecha está antes de hoy).
- `soon` → **Esta semana**, si faltan 0 a 7 días, incluyendo la tarea que vence hoy.
- `sched` → **Programada**, si faltan más de siete días.

Semanas: S1 días 1–7, S2 días 8–14, S3 días 15–21 y S4 desde el día 22 hasta fin de mes.

El plan usa `queries.fecha_referencia_mes` para traducir el mes seleccionado: para mes pasado toma el último día de ese mes; para el mes actual toma hoy; para un mes futuro toma su primer día. El encabezado global permite elegir agosto–noviembre de 2026.

### Resumen

Chips con número de vencidas, próximas (≤7 días) y ejecuciones del mes; porcentaje de cumplimiento y meta visual de 85%; botón **Exportar plan (PDF)**.

La fórmula real del resumen es `ejecutadas / (ejecutadas + vencidas) × 100`; cuando ambos valores son cero el resultado es 100%. Las tareas “próximas” y “programadas” no se incluyen en el denominador. Por esto el KPI no representa “porcentaje de todas las tareas de calendario concluidas” en el sentido habitual, sino esa regla específica del motor.

### Tabla semanal

Cada fila representa una actividad configurada para una máquina: Máquina, Actividad, Frecuencia, Sem 1–4 y Responsable. La tabla es de solo lectura; una celda pendiente puede mostrar la peor prioridad de las tareas en esa semana. Si hay al menos una ejecución de esa actividad en esa semana, la UI muestra “Hecha”. Las celdas sin tareas muestran guion. La tarjeta lista hasta diez ejecuciones recientes del mes, con fecha, máquina, actividad, responsable y observación.

### Registrar ejecución: limitación crítica

El diálogo propone Fecha de ejecución, Responsable (Téc. Mendoza, Téc. Soto o Mantenimiento) y Observaciones opcionales, y presenta el botón “Registrar como ejecutada”. Sin embargo, en el código actual `EjecucionDialog._guardar` llama a `plan_tpm.registrar_ejecucion(self.maquina, self.actividad, ...)`, mientras que la función requiere `registrar_ejecucion(conn, maquina, actividad, ...)`. La conexión no se suministra al diálogo ni a esa llamada. Por ello, la operación desde el botón no es funcional según las firmas examinadas y previsiblemente lanza un `TypeError`; no se debe documentar como operación confirmada en el uso diario hasta corregir y probar este defecto.

El motor central sí está implementado y probado directamente en `tests/test_plan_tpm.py`; documentarlo no equivale a que la integración de la UI sea válida.

### Exportar plan

**Exportar plan (PDF)** abre un cuadro para elegir ruta y llama a `reportes.pdf_plan` con la referencia temporal que deriva del mes activo. No modifica la base; genera un PDF con cronograma S1–S4 y resumen de estados/cumplimiento.

---

## 1.12 Reportes

**UI:** [`app/ui/reportes_page.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/reportes_page.py). **Generación:** `app/core/reportes.py` y `app/core/plantilla.py`.

### Tarjetas disponibles

1. **Plan mensual de mantenimiento** — PDF con cronograma S1–S4, máquina, actividad, frecuencia, responsable, vencidas, próximas, ejecutadas y cumplimiento. Usa el mes de referencia seleccionado.
2. **Pareto de causas** — PDF de Pareto del mes activo. Incluye las barras con porcentajes, acumulado y la línea de corte 80/20. Si no hay NC en el periodo, produce un PDF explicando que no hay datos.
3. **Resumen de indicadores** — PDF con las metas As-Is/To-Be y la tasa NC del mes seleccionado, más estado operativo de checklists de hoy y plan TPM actual. Aunque el título se basa en el mes seleccionado, checklists se calcula con la fecha de hoy y TPM con el mes actual del sistema. Para otros indicadores de `metas` que no tengan valor actual implementado, el documento pone `—`.
4. **Registro de no conformidades** — XLSX con filas del mes activo y ocho columnas de plantilla (fecha, turno, proceso, causa, defecto, operario, máquina, cantidad). No incluye observaciones.

### Procedimiento

1. Elegir la tarjeta de reporte.
2. Pulsar **Generar**.
3. En el cuadro de diálogo, elegir ruta/nombre del archivo y confirmar guardar.
4. Esperar el toast de finalización y verificar que el archivo existe en el destino.

La generación lee SQLite y escribe un archivo; no modifica registros operativos. Los errores de escritura, ruta inválida o acceso denegado pueden impedir la salida. Un PDF generado contiene un snapshot del momento de la exportación: no se actualiza automáticamente después de guardar.

---

## 1.13 Datos e importación

**Código UI:** [`app/ui/datos_page.py`](https://github.com/4beru/sicam-tf-in45/blob/main/app/ui/datos_page.py). **Lógica:** `app/core/importador.py`, `app/core/plantilla.py`, `app/core/integridad.py` y `app/core/seed.py`.

### Tarjeta “Plantilla de carga”

**Descargar plantilla** abre un diálogo para guardar `plantilla_sicam.xlsx`. Incluye hoja `Leeme` y hojas de tabla: `maquinas`, `operarios`, `produccion`, `no_conformidades`, `frecuencias` y `metas`. Tiene encabezados y listas desplegables para las categorías catalogadas. La plantilla se aplica a filas 2–2001 para esas validaciones.

La hoja NC expone ocho columnas; aunque la base y el formulario tienen `observacion`, esa columna no forma parte de la plantilla. Exportar y reimportar NC, por tanto, no es una vuelta de ida y vuelta completa.

### Tarjeta “Exportar a Excel”

**Exportar no conformidades** genera un XLSX con todas las NC, ordenadas de más reciente a más antigua, sin filtro de mes. Difiere de la tarjeta equivalente de Reportes, que exporta solo el mes seleccionado.

### Tarjeta “Importar plantilla” — validación en seco

1. Pulsar **Seleccionar archivo…** y elegir `.xlsx`.
2. SICAM lee las hojas reconocidas. Un archivo sin ninguna hoja de la plantilla se rechaza; puede contener solo algunas hojas.
3. `importador.validar` analiza filas sin aplicar sus datos de negocio a SQLite.
4. Si hay errores, muestra hoja, fila, columna y detalle (hasta 200 filas en el diálogo), no importa ninguna de las hojas de ese archivo y registra una entrada de historial con estado “con errores”.
5. Si no hay errores, muestra un resumen por hoja y pide confirmación.
6. Tras confirmar, aplica la importación en una transacción y registra la operación como “importado”. La pantalla refresca el historial y el resto de vistas.

**Claves de actualización:** máquinas por `codigo`; operarios por `codigo`; producción por `fecha + proceso + turno`; frecuencias por `maquina + actividad`; metas por `indicador`. Para estas hojas el importador hace upsert (inserta nuevas o reemplaza campos de la clave existente). Las no conformidades son distintas: cada importación las inserta como filas nuevas, sin clave natural ni deduplicación. La misma hoja importada dos veces puede duplicar todas sus NC.

Validaciones destacadas: fecha aceptada ISO (`AAAA-MM-DD`) o `DD/MM/AAAA`/`DD/MM/AA`; catálogo válido de proceso, turno, causa, área y criticidad; cantidad NC ≥1; inspeccionadas ≥1; NC detectadas ≥0 y no mayores que inspeccionadas; códigos repetidos de máquina/operario dentro del archivo; máquina existente en la base o en la hoja de máquinas; frecuencia ≥1. `operario` en NC es texto libre.

Las fechas de producción y NC se normalizan antes de guardar. Para `fecha_compra` y `ultima_calibracion` de máquinas el importador valida el formato pero guarda el texto original; las fechas escritas como `DD/MM/AAAA` podrían no parsearse luego con `date.fromisoformat` en el cálculo de calibración.

### Historial de importaciones

Muestra las últimas 20 operaciones con fecha, nombre de archivo (derivado de la ruta), filas OK, filas con error y estado. Para una importación rechazada, “Filas OK” queda en cero y “Con error” es el número de errores detectados, no un recuento de registros importados parcialmente. La validación se realiza antes de tocar los registros de negocio, pero el historial sí se modifica para dejar constancia del rechazo.

### Tarjeta “Datos piloto e integridad”

Muestra cantidades de NC, filas de producción, máquinas, operarios, checklists y tarjetas actuales.

- **Auditar y sanear datos:** inspecciona integridad física SQLite, claves foráneas y reglas semánticas seleccionadas; borra ciertos huérfanos inequívocos de checklist y tarjetas de checklist, e informa el resto para investigación.
- **Restablecer datos piloto:** operación destructiva, no rutinaria. Requiere confirmación explícita y advierte pérdida de datos manuales/importados y de operación.

#### Efectos exactos del restablecimiento

1. La confirmación avisa que se sustituirán los datos manuales/importados y los registros de operación por el conjunto de demostración, que no se puede deshacer.
2. Se toma una copia SQLite en memoria con `Connection.backup`.
3. `seed.siembra(conn, reset=True)` vacía el contenido de las tablas administradas y reinicia secuencias; vuelve a crear datos sintéticos 2024, piloto julio–noviembre 2026, catálogos, checklists, tarjetas, ejecuciones TPM, umbrales e historial IoT sintético.
4. `integridad.auditar_y_reparar` verifica el resultado. Si la integridad física no es `ok` o quedan problemas semánticos, el sistema intenta restaurar la copia previa desde memoria y muestra error.
5. Solo después de pasar la validación, reúne rutas de foto de checklist que estaban registradas y elimina archivos que estén dentro de `SICAM_DATA/fotos` (o su carpeta equivalente). Las rutas fuera de esa carpeta no se borran. Errores al eliminar fotografías se omiten.
6. Actualiza la firma de reactividad, muestra un toast y refresca las páginas.

La copia cubre SQLite, no una copia recuperable de los archivos de fotografía. La limpieza de fotos ocurre después de validar la nueva base, por lo que si se completó el reset y se eliminaron fotos, la copia en memoria ya se habrá cerrado. Los datos reales pueden perderse: NC, producción, maestros, importaciones, checklists, ítems y rutas de evidencia, tarjetas TPM, ejecuciones del plan, lecturas, alertas y umbrales IoT quedan reemplazados por la semilla/configuración de demostración. Use previamente una copia de la carpeta de datos si existe cualquier posibilidad de necesitar esos datos.

---

## 1.14 Resumen de operaciones por pantalla

| Pantalla | Puede hacer | No debe suponerse que puede hacer |
|---|---|---|
| Dashboard | Consultar tasas, Pareto, rankings, cumplimiento y pendientes. | Editar registros, rastrear automáticamente una prenda hasta una fila específica o conceder acciones por rol. |
| Monitor IoT | Leer señales, guardar umbrales, simular lecturas/alertas, convertir A/C a tarjeta y D a NC, atender alertas. | Parar una máquina físicamente, autenticar sensores o recalcular el historial al cambiar umbrales. |
| No conformidades | Crear NC y filtrar/consultar las últimas filas. | Cambiar/eliminar NC, seleccionar libremente fecha, vincularla por ID a producción. |
| Producción diaria | Registrar/reemplazar una combinación fecha-proceso-turno, ver tasa y tendencia. | Acumular automáticamente valores sobre una fila ya existente. |
| Checklists | Generar/guardar QR, iniciar/detener servidor, consultar checklist, detalle y fotos. | Proteger endpoints con cuentas o impedir toda solicitud incompleta fuera del cliente normal de navegador. |
| Tarjetas TPM | Crear manuales y pasar abiertas a atención/cerradas desde la UI. | Ejecutar automáticamente la acción recomendada, mantener asignación editable o medir MTTR de forma demostrada. |
| Máquinas | Consultar ficha e historial, crear una tarjeta y navegar al plan. | Editar el catálogo/calibración directamente desde la ficha. |
| Plan TPM | Ver tareas generadas y exportar calendario PDF. | Confiar en el botón de ejecución hasta corregir la llamada de UI y verificarla. |
| Reportes | Generar PDFs y exportación mensual de NC. | Modificar registros por exportar o asumir que todo indicador histórico tiene actual. |
| Datos e importación | Plantilla, exportación global de NC, dry-run, importación, auditoría y restauración. | Suponer que reimportar NC no duplica; tratar el reset como reparación segura o reversible de fotos. |