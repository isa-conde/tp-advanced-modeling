# Qué agregamos para medir los KPIs

La idea es sencilla: **el modelo ya mueve y recupera las cajas; ahora dejamos
registro de lo que sucede y calculamos los seis indicadores**. Las definiciones
en inglés están en [KPIS.md](KPIS.md).

Estos registros son para evaluar el experimento. Las reglas actuales de pedidos,
selección random, transporte y recuperación siguen siendo las mismas. Ninguna
decisión operativa consulta los resultados de los KPIs.

## Resumen: qué información ya existía y qué agregamos

| Medición | Información que ya existía en el código | Qué agregamos | KPI |
| --- | --- | --- | --- |
| Despachos individuales PRO -> RDC | Cada RTI ya tenía identidad y tipo; el productor ya despachaba cajas y el modelo conocía el día. | Guardamos por caja su primer y último despacho, cantidad de despachos y último productor. Cada nuevo despacho cierra el intervalo anterior. | 2, 5 y 6 |
| Lavados y reparaciones | El Pooler ya ejecutaba `process_rti()` y conocía si la caja estaba rota antes de repararla. | Contamos un lavado por caja procesada y una reparación adicional si estaba rota. | 2 |
| Flota inicial | Las cajas ya estaban creadas y registradas como agentes del modelo. | Contamos las RTIs una sola vez al finalizar la inicialización. Incluimos las que después no circulen. | 5 |
| Stock frente a demanda | Existían los stocks de los productores y las copias de los pedidos originales en `all_orders`. | Comparamos proporciones por tipo, usando los pedidos de los últimos siete días. | 1 |
| Exposición a bajo stock | Existían las cantidades disponibles por productor y tipo. | Al cierre de cada día marcamos las combinaciones compatibles con stock <= 5.000 RTIs y acumulamos la exposición. | 3 |
| Exposición a backorders | Cada productor ya tenía su `order_book`, con cantidad pendiente, fecha y lead time. | Sumamos cada día las cantidades pendientes de pedidos PRO -> RDC cuyo plazo ya se cumplió. | 4 |
| Ciclos sin terminar | El modelo conocía el día final; el nuevo registro de despachos conserva la última salida de cada caja. | Contamos intervalos abiertos y calculamos cuánto llevan esperando al finalizar. | 6 |
| Resumen por corrida | Ya existían los parámetros operativos y la exportación de Stock, Flows, Backorders y Orders. | Exportamos los seis KPIs, detalles de apoyo, seed, parámetros y versiones del código. | Todos |

**No inventamos nuevas lecturas RFID:** aprovechamos identidad, movimientos y
estados que el modelo ya representa. Contar un lavado significa observar una
operación realizada, no suponer que RFID detecta suciedad. Del mismo modo, la
reparación se cuenta cuando realmente ocurre en el proceso modelado.

## Qué cambió concretamente en el código

### 1. Un módulo dedicado a medir: `kpi_measurements.py`

Este archivo reúne los contadores y las fórmulas. Al separarlo, es más fácil
revisar las mediciones y reutilizarlas cuando implementemos el Traceability
Scenario.

Conserva un resumen por caja en lugar de millones de movimientos individuales.
Por ejemplo, si una caja sale los días 10, 35 y 60, registra tres despachos,
dos ciclos completados y 50 días de ciclos completados. El tiempo medio de esos
ciclos es 25 días. Después del día 60 queda iniciado otro intervalo.

### 2. Una anotación al despachar desde un productor

En `Producer_Agent.fulfill_orders()` se avisa al módulo de medición qué caja se
despachó, desde qué productor y en qué día.

El primer despacho observado inicia el seguimiento. El siguiente completa un
ciclo observado. No se atribuye un ciclo a una caja solo por haberla usado una vez,
ni se supone un historial anterior al comienzo del run.

La identidad utilizada es `rti_id`, que ya existía. El día sale de `model.steps`,
y el tipo de caja de `crate_type`. Agregamos el historial resumido, no esas
propiedades.

### 3. Contadores dentro del proceso de recuperación

En `Pooler_Agent.process_rti()` contamos las operaciones antes de que se borre
el estado de rotura de la caja:

- Si la caja no está rota: un lavado.
- Si está rota: una reparación y un lavado.

Esto respeta el proceso del baseline, que lava todas las cajas seleccionadas
para procesamiento. No decidimos aquí si hubiera sido conveniente lavarlas.

### 4. Una observación al cierre de cada día

Al terminar `CLSC_Model.step()`, después de las operaciones físicas, tomamos la
medición del día. El día 0 se conserva como estado inicial en el Excel, pero no
se suma como un día de exposición a los KPIs.

Para cada indicador aprovechamos lo siguiente:

- **KPI 1:** el stock físico en `forward_stock_pro` y las cantidades originales
  de pedidos del RDC guardadas en `all_orders`. Usamos esas copias porque la
  cantidad del pedido pendiente puede disminuir al atenderse parcialmente.
- **KPI 3:** el mismo stock físico por productor y tipo. Las cajas pedidas al
  Pooler que todavía no llegaron no cuentan como disponibles. Solo se evalúan
  tipos compatibles; no marcamos como faltante un tipo que ese productor no usa.
- **KPI 4:** las cantidades que siguen pendientes en `order_book`, comprobando
  `creation_step + lead_time`. Se consideran los pedidos del RDC a productores;
  los pedidos al Pooler no se suman a ese mismo indicador.

Un dato representa lo que se solicitó originalmente y otro lo que todavía falta
entregar. Ambos ya existían, pero sirven para preguntas distintas.

### 5. Resumen final y esperas abiertas

Al finalizar se calculan los seis resultados y los datos que ayudan a interpretarlos.
Por ejemplo, si una caja salió el día 350 y el run termina el 365, tiene una espera
abierta de 15 días. No se trata como un ciclo completado ni como una duración cero.

El KPI 6 se acompaña del porcentaje de intervalos abiertos y su espera media.
Las cajas que nunca se despacharon siguen incluidas en la flota del KPI 5.

Si no hay ciclos completados, los cocientes que los necesitan se exportan como
`null` en JSON y celdas vacías en CSV: significan **N/A**, no cero.

## Cómo ejecutar y qué archivos se generan

Con el entorno activado, desde la raíz del repositorio:

```bash
python run_baseline.py --seed 42 --steps 365
```

`run_baseline.py` prepara una corrida repetible, fija el orden de los conjuntos
de Python antes de cargar el modelo y crea una carpeta distinta en `results/`.
La seed controla el azar del baseline; el registro de mediciones no consume
números aleatorios.

Se puede usar `--steps 10` para una comprobación corta. En ese caso se mide ese
horizonte de diez días: los resultados no se extrapolan ni equivalen a un año.

| Archivo de salida | Qué contiene |
| --- | --- |
| `sim_log_....xlsx` | El Excel habitual con stocks, flujos, backorders y pedidos. |
| `kpi_summary.csv` / `kpi_summary.json` | Los seis KPIs. El JSON también incluye contadores de apoyo y parámetros de medición. |
| `kpi_daily.csv` | Observaciones diarias y cantidades de operaciones, despachos y ciclos. |
| `kpi_producer_type_daily.csv` | Stock, demanda de la ventana, exposición a bajo stock y backorders por productor y tipo. |
| `kpi_mismatch_type_daily.csv` | Desajuste y cantidades de apoyo por tipo de caja y día. |
| `rti_reuse.csv` | Resumen por caja despachada, ciclos y espera abierta al final. |
| `run_metadata.json` | Seed, horizonte ejecutado, parámetros operativos, versiones, commit y huellas de los archivos usados. |

La carpeta `results/` está excluida de Git. Los CSV pueden abrirse en Excel; el
detalle por caja se guarda separado para no agrandar el libro habitual.

También se puede ejecutar `Assignment_code_baseline_corrected.py` directamente:
genera el Excel y los nuevos archivos en `run_corrected_.../`, pero no fija una
seed. Para experimentos comparables recomendamos el comando anterior.

La repetibilidad se refiere a los valores operativos y KPIs: los identificadores
UUID siguen generándose de nuevo en cada corrida. Para comparar políticas
distintas con los mismos inputs exógenos todavía habrá que preparar streams
aleatorios separados; esta implementación no resuelve esa etapa.

## Qué comprobamos

Las pruebas están en `tests/test_kpi_measurements.py`, además de las pruebas
existentes del baseline corregido:

- Ejemplos con respuesta conocida: desajuste 30%, umbral exacto de 5.000,
  backlog acumulado, tratamientos y tiempos entre reutilizaciones.
- Ventana de siete días, días sin demanda y casos sin ciclos completados.
- Tratamiento de intervalos abiertos y exclusión del día 0.
- Coincidencia de despachos y backorders con los reportes que ya tenía el modelo.
- Igualdad de stocks, flujos, backorders y estado del generador aleatorio al
  ejecutar el mismo escenario con la medición activada o desactivada.
- Exportación de los seis KPIs y de la configuración de la corrida.

```bash
python -m unittest discover -s tests -v
```

La implementación permite empezar a medir el baseline. El diagnóstico operativo
requiere después analizar los KPIs y sus desgloses en varias replications.

### Validación realizada el 9 de noviembre de 2026

- **24 pruebas pasaron**, incluyendo las 11 pruebas anteriores del baseline corregido.
- Se completaron **365 días con seed 42**, usando la flota real de **322.800 RTIs**.
- Los seis KPIs se recalcularon desde los archivos exportados y coincidieron con
  el resumen. El stock se conservó por tipo en todos los cierres diarios.
- El Excel habitual coincidió con la corrida previa a esta instrumentación con
  la misma seed: Stock, Flows, Backorders y contenido operativo de Orders.
  Se excluyeron los identificadores aleatorios de pedidos.

El [resumen de esa corrida](results/kpi_implementation_validation_20261109_seed42/kpi_summary.json)
y su [informe de validación](results/kpi_implementation_validation_20261109_seed42/validation_report.json)
quedan como evidencia local, dentro de `results/`. Es una corrida de validación;
no sustituye el análisis de varias replications ni demuestra mejoras por RFID.
