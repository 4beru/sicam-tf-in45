# SICAM — documentación integral

**Manual de usuario · Especificación funcional · Procesos · Datos · Arquitectura · Soporte**

> **Base de revisión:** rama `main` del repositorio [`4beru/sicam-tf-in45`](https://github.com/4beru/sicam-tf-in45), commit `c6ba4a275a90bc7791a3cd10daef4c2fd4392c3f` (11 de octubre de 2026). La suite de CI asociada a ese commit terminó correctamente: **65 pruebas aprobadas**. El trabajo fue una inspección remota de código, pruebas y logs de CI; no se alteró el repositorio ni se ejecutó una base de datos del usuario.

## Documentos

1. [Manual de usuario y catálogo de las diez vistas](01-manual-usuario.md)
2. [Procesos de negocio y recorridos end-to-end](02-procesos-negocio.md)
3. [Diccionario de indicadores, terminología y modelo de datos](03-diccionario-funcional-datos.md)
4. [Arquitectura, configuración, soporte, discrepancias y trazabilidad](04-referencia-tecnica-soporte.md)

## Lectura recomendada

- **Supervisor / calidad:** documentos 1 y 2; consultar el documento 3 para interpretar indicadores.
- **Operario de estación:** apartados Checklists del documento 1 y los flujos de checklist y anomalías del documento 2.
- **Mantenimiento:** apartados Tarjetas TPM, Máquinas y Plan TPM del documento 1; flujos 5–9 del documento 2.
- **Responsable de datos / desarrollador:** documentos 3 y 4, además de la tabla de trazabilidad de pruebas.

## Cómo leer las afirmaciones

- **Implementado en código:** hay una ruta de ejecución, consulta o escritura identificable.
- **Cubierto por tests:** además existe una prueba automatizada que verifica el comportamiento indicado.
- **CI verificada:** el último run consultado ejecutó el comando de tests y reportó 65 aprobadas.
- **Limitación / discrepancia:** la interfaz, comentarios o README sugieren algo que el código no garantiza, o existe una ruta que parece defectuosa.
- **No verificado visualmente:** la vista o interacción no se ejecutó manualmente en una sesión gráfica durante esta revisión.

## Propósito en pocas palabras

SICAM significa **Sistema Integral de Calidad y Mantenimiento**. Es una aplicación de escritorio PySide6 que utiliza SQLite local y un servidor Flask embebido para formularios móviles en la red local. Reúne el registro de producción y no conformidades, listas de verificación por estación, tarjetas de anomalía TPM, un plan de mantenimiento basado en frecuencias, monitorización IoT simulada o recibida por HTTP y generación de reportes PDF/XLSX.

El producto es un MVP operativo/demostrativo. Los datos sintéticos constituyen una parte importante de la demostración. El selector de usuario no aplica autorización, las rutas LAN no exigen autenticación y hay discrepancias de implementación que deben tenerse presentes antes de utilizar el software como sistema de registro de producción real.

## Hallazgos prioritarios detectados durante la inspección

1. El selector de usuario anuncia que el filtrado por rol pertenece a una fase futura; no constituye autenticación ni control de permisos.
2. El diálogo de ejecución de Plan TPM llama a `plan_tpm.registrar_ejecucion` sin pasar la conexión SQLite. La función de negocio exige la conexión como primer argumento: la acción de guardar desde esa pantalla parece fallar por incompatibilidad de argumentos. El motor, invocado directamente con una conexión, sí está cubierto por tests.
3. Reimportar la hoja `no_conformidades` agrega filas; no existe clave natural ni `ON CONFLICT` para esas filas. Reimportar el mismo XLSX puede duplicarlas.
4. Los códigos canónicos sembrados son `Costura 001`–`Costura 030`. Algunos ejemplos del README (`RECT-05`, `ETQ-03`) no existen en la semilla y el endpoint IoT rechaza máquinas no registradas.
5. La gráfica IoT se titula “Última hora”, pero consulta 60 lecturas recientes y no filtra por una ventana de 60 minutos. Con el simulador cada 2 segundos, esas 60 muestras representan aproximadamente dos minutos.
6. “Tarjetas 12 m” en la ficha de máquina cuenta todas las tarjetas de esa máquina; la restricción de fecha se usa en la gráfica histórica, pero no en ese KPI.
7. El README y un comentario de semilla hablan de “5 de 7 estaciones”; el código y las pruebas actuales usan 30 máquinas, por lo que cinco checklists equivalen a 5/30, no a 5/7.
8. La plantilla/documentación de Excel promete una ida y vuelta sencilla, pero no conserva todos los campos de NC: `observacion` existe en el formulario y la tabla de SQLite, pero no está entre las columnas exportadas/de plantilla.
9. El último CI consultado sí está verde (65 tests), pero ese run de push en `main` ejecutó pruebas y dejó omitida la compilación Windows; no demuestra por sí mismo un `.exe` recién compilado en ese run.

Consulte el documento 4 para evidencias por archivo, riesgos y recomendaciones.

## Cobertura del paquete

La entrega contiene **4 documentos Markdown**, con aproximadamente 1.600 líneas de referencia, un manual separado para las **10 vistas** del sistema, **15 flujos funcionales** identificados con base en la implementación, diccionario de KPIs y glosario, esquema de datos con Mermaid ER, diagrama de arquitectura, procedimientos diarios, guías de operación, endpoints HTTP, instalación y prueba, matriz de trazabilidad, estado de CI, discrepancias y recomendaciones.

### Importante antes de usar SICAM como registro operativo

El hallazgo más importante de usabilidad técnica es el guardado de ejecución en Plan TPM, cuya llamada desde la interfaz no pasa la conexión exigida por la función de negocio. Además, no deben reimportarse repetidamente las mismas filas de NC porque esa entidad no tiene upsert; la app móvil no autentica usuarios y el reset del piloto sustituye datos y puede borrar evidencias fotográficas administradas por el sistema. Estos límites están ampliados en los documentos 2 y 4.