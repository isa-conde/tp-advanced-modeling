# Mediciones del segundo borrador

La referencia de definiciones es `kpi.md`. Las etiquetas de los cinco indicadores
se conservan en inglés. Esta implementación observa el **corrected baseline**;
no incorpora políticas RFID ni la instrumentación de `kpis_draft`.

## Del sistema al registro

Las cajas circulan por POOL → PRO → RDC → RPOS → RDC → POOL. Un flujo diario
indica cuántas cajas salieron, pero no permite saber si una misma caja volvió a
utilizarse. Por eso los tres primeros indicadores se obtienen de stocks y pedidos,
mientras los dos últimos necesitan observar eventos individuales.

| KPI | Información existente aprovechada | Registro agregado y cálculo |
| --- | --- | --- |
| Stockout frequency | `forward_stock_pro`, tipos compatibles del producto | Por cada cierre y combinación compatible, guardar stock y `stockout = int(stock == 0)`. Porcentaje global y por productor–tipo. |
| Average backorders | `Producer_Agent.order_book`, `quantity`, `creation_step`, `lead_time` | Sumar el saldo con `day >= creation_step + lead_time`, por productor–tipo. Sumar productores y tipos por día y promediar todos los días, incluidos ceros. |
| Average inventory by node | Stocks físicos de todos los agentes | Registrar cantidades por nodo, tipo y estado. Promediar cierres; sumar estados y tipos para el total de cada nodo. |
| RTI turnover | `rti_id` y el evento real de dispatch lleno PRO → RDC | Guardar IDs que ya tuvieron un dispatch. Cada dispatch posterior del mismo ID completa un observed reuse cycle. Dividir por toda la flota inicial. |
| Recovery treatments per reuse | `process_rti` y el estado `broken` antes de tratar | Contar una washing operation por llamada y una repair operation adicional si estaba rota. Dividir la suma por el mismo conteo de ciclos de turnover. |

El baseline ya ofrece reporters de stock y backorders; estos se conservan. La
medición lee directamente los stocks y order books al cierre para incorporar el
detalle individual de los RPOS y aplicar una única regla temporal. No usa el
historial de pedidos originales para backorders: `all_orders` conserva cantidades
solicitadas, mientras el order book operativo conserva los saldos pendientes.

Por ejemplo, un pedido de 10 RTIs con 7 entregadas deja `quantity = 3`. Si vence
hoy, aporta 3 a este cierre; otro pedido que vence mañana todavía aporta 0.
Los pedidos de PRO al Pooler, expresados en UL, pertenecen a otro tier y no se
suman al KPI 2.

## Momento y unidad de observación

Se observa después de **toda** la secuencia diaria, incluida la entrega POOL → PRO
que ocurre después de la actividad de los productores. Un productor vacío a
media jornada puede cerrar con stock: en ese caso no se cuenta un stockout.
El día inicial 0 no entra en los cinco indicadores. El Excel tradicional sigue
incluyendo ese día, por lo que promediar sus 366 filas directamente sería incorrecto.

Cada combinación compatible tiene una observación por día. El resultado global
de stockouts es el porcentaje de esas observaciones, no un promedio sin ponderar
de porcentajes por productor. Se conserva el numerador y el denominador.

Para inventario se identifican `POOL_1`, los `PRO_*`, `RDC_1` y cada `RPOS_01`,
`RPOS_02`, etc. Los IDs de RPOS corresponden a su posición estable en
`model.r_pos_agents`, no a los IDs de Mesa, que dependen de cuántas cajas fueron
creadas antes. Su tamaño se puede reconstruir desde la configuración: primero
big, luego medium y después small.

Los estados son washed/unwashed/processing en POOL, empty en PRO,
empty/filled en RDC y displayed/empty en cada RPOS. Las cantidades cero también
se registran. Los estados forman partes del total: **no** se suman el total y
sus componentes. El inventario global conservado es una comprobación, no el
indicador para comparar escenarios.

En este modelo, los traslados son síncronos: cada extracción tiene recepción en
el mismo día, sin inventario físico en tránsito al cierre. `on_order_from_pool`
es una cantidad pedida, no cajas físicamente en tránsito, y no se suma al stock.
El resultado declara esta característica. Si otro escenario agrega tránsito que
persiste al cierre, deberá registrar ese stock por separado y adaptar el
observador antes de compararlo; el observador actual es específico del baseline.

## Ciclos y recovery work

El primer dispatch lleno de una caja inicia su observación, sin completar un
ciclo. El segundo completa uno; el tercero, otro. En la topología actual, para
volver a salir del productor una caja necesariamente recorrió el return loop.
No se inventa un dispatch anterior para cajas que comienzan en RPOS o RDC.
El set de IDs es memoria del experimento, no información para los actores.

El denominador de turnover cuenta todos los RTI agents iniciales, incluidos los
que nunca salen del productor o nunca completan un ciclo. No cambia cada día.
No se anualizan corridas cortas.

`process_rti` repara condicionalmente y lava incondicionalmente: incluso una caja
no dirty pasa por la operación de lavado si entra a ese método. La medición
cuenta esas operaciones reales del baseline, no estima operaciones a partir de
flujos o cambios en la bandera `washed`. No cuenta screening, tiempo en buffer,
stocks iniciales ya lavados ni las cajas que evitan el procesamiento. Una caja
rota suma repair + washing = 2; tratarla de nuevo vuelve a sumar. Los conteos
son agregados: no se guarda un historial completo por RTI porque estos KPIs no
lo necesitan. El ID individual sí se utiliza para reconocer ciclos.

Todo el trabajo dentro del horizonte se cuenta, aunque no termine un ciclo
asociado. Si los ciclos son 0, turnover es 0 para una flota no vacía, y
Recovery treatments per reuse es `null` en JSON, acompañado por un estado N/A;
los conteos de operaciones quedan disponibles. Para una flota inicial vacía,
turnover también es `null` y tiene su propio estado N/A. Sin días observados no
se genera un promedio: se informa un error.

## Qué cambió en el código

- `kpi_measurements.py`: observador pasivo, cálculo de indicadores y exportación.
- `Assignment_code_baseline_corrected.py`: opción `measure_kpis=False` y llamadas
  al observador en dispatch, recovery y cierre diario. Por defecto sigue sin
  instrumentación; las operaciones originales mantienen su secuencia.
- `run_kpis.py`: ejecuta una replication con seed y horizonte explícitos y crea
  una carpeta exclusiva por corrida. No cambia parámetros operativos.
- `tests/test_kpis.py`: ejemplos con resultados conocidos y comparación con la
  instrumentación desactivada.

`Assignment_code_baseline.py` permanece intacto. El umbral operativo existente
`PRO_REORDER_POINT = 5000` sigue siendo parte de la política del profesor; no es
un umbral del KPI. No hay ventanas de demanda ni mediciones de low stock.

## Ejecutar y revisar una replication

Desde la raíz del repositorio:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python run_kpis.py --seed 42 --days 365 --excel
```

Se puede omitir `--excel` para exportar únicamente los registros de medición.
Para una prueba breve usar, por ejemplo, `--days 10`; los resultados representan
esos diez días. Para replications usar distintas seeds, manteniendo el horizonte
y la configuración. Todavía no se calculan confidence intervals entre corridas.

El destino predeterminado es `results/kpis_second_draft/<run_id>/`; puede cambiarse
con `--output`. El run ID usa fecha UTC con microsegundos y un sufijo único. No
sobrescribe corridas previas. Cada carpeta contiene:

| Archivo | Uso |
| --- | --- |
| `metadata.json` | ID, escenario, seed, horizonte, configuración efectiva, versiones y hashes de código y definiciones. Se escribe al inicio. |
| `kpis.json` | Los cinco KPIs, conteos y desgloses; repite metadata para que sea autosuficiente. Su presencia indica que terminó el cálculo. |
| `producer_days.csv` | Stock, stockout y saldo vencido por día, productor y tipo compatible. |
| `inventory_days.csv` | Cantidad por día, nodo, tipo y estado. |
| `activity_days.csv` | Conteos **acumulados** al cierre: ciclos completados, washing y repair. La diferencia entre dos filas da la actividad del día. |
| `sim_log_<run_id>.xlsx` | Solo con `--excel`: exportación original de stocks, flujos, backorders y pedidos. |

Los CSV pertenecen a la corrida identificada por su carpeta. `null` debe leerse
como N/A, nunca como cero. Para revisar un resultado, empezar por los cinco
campos con nombres ingleses de `kpis.json` y sus breakdowns. Para auditar,
recalcular desde los CSV: media de stockout × 100, media de la suma diaria de
backorders y media de cada inventario por nodo. La última fila de actividad
contiene los numeradores de los KPIs 4–5.

El runner fija `random.seed` antes de construir el modelo. Además se reinicia,
si hace falta, con `PYTHONHASHSEED=0`: el baseline itera sobre sets de tipos, por
lo que fijar solamente la seed no garantiza el mismo orden entre procesos.
La reproducibilidad se refiere a resultados operativos con iguales versiones,
código y configuración; UUIDs de pedidos y carpetas seguirán siendo diferentes.
Mesa también crea sus propios generadores, pero la lógica operativa actual usa
el módulo global `random`; si cambia eso, habrá que ampliar el seeding.

## Comprobaciones y alcance

Las 15 pruebas pasan: las 11 anteriores y 4 nuevas. Los casos conocidos verifican
un único stockout sobre tres días, backorders diarios 3, 1 y 0 (media 4/3),
exclusión de pedidos futuros y del tier Pooler, inventarios separados por POS,
suma de estados, primer dispatch sin ciclo, segundo dispatch con ciclo,
repair + washing y trabajo sin ciclo completado. También se comprueba exportación
JSON/CSV, N/A y prevención de observar dos veces el mismo cierre.

La comparación pasiva usa seeds 3, 19 y 42 durante 60 días con inventarios
reducidos. Día a día compara propiedad física e identidad de las cajas, estados,
productos, permanencia, pedidos y saldos, on-order, tiempos de procesamiento y
estado del generador aleatorio. Los reporters históricos también son idénticos.
Se comprueba conservación de la flota en los nuevos registros. Estas pruebas
permiten detectar cambios de operación y consumo accidental de números aleatorios;
no equivalen a demostrar igualdad para toda configuración posible.

### Corrida real de comprobación (10 de noviembre de 2026)

Se completó una replication de 365 días con seed 42, configuración original y
flota de 322.800 RTIs. Run ID: `20261110T083242_990909Z_111416c2`.

| Indicador | Resultado de esta replication |
| --- | ---: |
| Stockout frequency | 0,0421496 % (2 / 4.745 producer-type-days) |
| Average backorders | 10,3232877 RTIs |
| Average inventory by node | Perfil de 29 nodos, incluidos 20 RPOS individuales, en `kpis.json` |
| RTI turnover | 6,9144021 completed observed cycles / fleet RTI |
| Recovery treatments per reuse | 0,6419166 treatments / completed observed cycle |

Se observaron 2.231.969 ciclos completados, 1.324.000 washing operations y
108.738 repair operations. El ratio puede ser menor que 1: no todas las cajas
pasan por recovery, y el numerador y los ciclos tienen los límites temporales
que especifica `kpi.md`. Estos resultados describen una replication del baseline;
no son una comparación entre escenarios ni una estimación con confidence intervals.

La auditoría verificó conservación diaria de toda la flota, ausencia de registros
duplicados y coincidencia, para cada cierre, de stocks PRO y backorders con el
Excel del baseline. También contrastó el inventario total diario con el Excel
y recalculó los KPIs desde los CSV. Dos corridas cortas independientes con seed
19 y horizonte de 2 días produjeron KPIs y CSV idénticos.

Evidencia local (excluida de Git):

- [Indicadores y breakdowns](results/kpis_second_draft/20261110T083242_990909Z_111416c2/kpis.json).
- [Informe de validación](results/kpis_second_draft/20261110T083242_990909Z_111416c2/validation_report.json).
- [Excel](results/kpis_second_draft/20261110T083242_990909Z_111416c2/sim_log_20261110T083242_990909Z_111416c2.xlsx).

El archivo original del profesor conserva su SHA-256:
`904fa580ddf227c467d4c6dd3a050a68a115ff42c7f9671f7ecdd0053a3695bb`.
