# Plan de trabajo del assignment

## Qué pide la consigna

Fuente principal: [Problem description](https://drive.google.com/file/d/1QjMdU0VwPYSbuBlQMbN28AbJmM126r5s/view), slides 38-41.

1. **Task 1:** analizar problemas de efficiency, effectiveness y RTI circularity
   del Baseline Scenario, tanto dentro de los nodos como en los flujos entre ellos.
   Definir performance measures y diseñar e implementar decision-making logics
   que usen información individual de las RTIs para resolver esos problemas.
2. **Task 2:** comparar Baseline y Traceability con las mismas métricas, cuantificar
   mejoras y explicar su mecanismo y trade-offs.
3. **Task 3:** realizar un ANOVA-based experimental analysis sobre al menos tres
   performance measures, con al menos un factor y niveles justificados para cada
   medida. Explicar cuándo la trazabilidad aporta más valor desde una perspectiva
   managerial.

Entregar una presentación de 15-20 slides (sin contar title y agenda), Python
script y Excel si es necesario, en un ZIP `Group_XX` en WeBeep. La slide 3 indica
10 de enero como deadline; confirmar año y fecha vigente en WeBeep. La frase
"one week before" junto al examen del 14 de enero no coincide con esas fechas.

El resto de este documento son propuestas del grupo para discutir, no políticas
ni resultados impuestos por la profesora.

## 1. Validar el modelo antes de diagnosticar

El código original queda conservado. Se creó una copia de trabajo en
`Assignment_code_baseline_corrected.py`. El detalle y las pruebas están en
[CORRECCIONES_BASELINE.md](CORRECCIONES_BASELINE.md).

Corregido en esa copia, pendiente de revisión por el grupo:

- El constructor de las RTIs ahora conserva `washed`, `location`, `is_filled`
  y `product` tal como se reciben.
- Se activa la actualización diaria del RDC y se unifica el reloj en todos los
  nodos: edad cero al llegar y, después, días transcurridos desde esa llegada.

Pendientes antes de experimentar:

- Los PROs comienzan con stock solo de sus crate types compatibles. La slide de
  descripción dice "for each crate type": confirmar si se refiere a compatibles.
- Las decisiones aleatorias usan el módulo global `random`. `run_baseline.py`
  ahora fija la seed y el orden de los conjuntos para repetir una corrida. Falta
  separar streams exógenos al comparar políticas que consuman azar de otra manera.

Si se corrige el modelo, aplicar la misma corrección al baseline de comparación y
al Traceability Scenario. Separar correcciones del modelo de las nuevas políticas,
para no atribuir a RFID una mejora causada por un bug corregido.

Verificaciones propuestas: conservación del número de RTIs por tipo, ausencia de
referencias duplicadas en los stocks, ULs completas, estados coherentes, cantidades
no negativas y lead times/orden de activación diarios acordes al modelo.

## 2. Preparar experimentos reproducibles

- Incorporar configuración de scenario, seed, horizonte y carpeta de resultados
  sin editar constantes manualmente entre runs; mantener el original como referencia.
- Guardar configuración, versiones y commit junto a cada resultado.
- Hacer un piloto con varias replications y elegir su número según la precisión
  deseada. Los 365 días de un run no son 365 replications independientes.
- Para comparaciones pareadas, controlar la demanda y las demás fuentes exógenas
  con streams separados. Repetir una seed global no garantiza los mismos inputs
  si una política cambia el número de llamadas aleatorias.
- Decidir y justificar si interesa el año completo desde el estado inicial o un
  régimen estable; no descartar un warm-up automáticamente.

## 3. Medir y diagnosticar el baseline

Los seis KPIs acordados están definidos en [KPIS.md](KPIS.md). Ya se implementaron
los registros y cálculos; las fuentes de datos, cambios de código y archivos de
salida están en [MEDICION_KPIS.md](MEDICION_KPIS.md).

La suma diaria de backlog tiene unidades **RTI-days**: no es el número de pedidos
distintos incumplidos. Tampoco dividir despachos de hoy por demanda de hoy mide
directamente on-time service, porque existen lead times y backorders anteriores.
Los contadores de ciclos deben distinguir ciclos completos de los incompletos al
final del horizonte. No todas estas métricas se obtienen del Excel actual.

Primer resultado esperado: identificar dónde, cuándo y para qué tipo de caja se
acumulan backorders o inmovilización, y relacionarlo con washing y screening.

## 4. Probar políticas RFID con una hipótesis explícita

Dos candidatos iniciales, sujetos al diagnóstico:

- **Screening informado:** priorizar ULs con mayor necesidad de recuperación
  usando estado/historial RTI-level observable. Definir cómo se agrega la
  información individual al UL y respetar la capacidad de 20 UL/día. Distinguir
  datos que RFID registra de condiciones físicas que requieren inspección;
  no asumir que un tag detecta daños por sí solo.
- **Retrieval por antigüedad:** priorizar crates o ULs con mayor detention time
  en lugar de selección random. Medir si mejora la cola de edades o la circulación;
  no asumir que FIFO reduce necesariamente el stock medio o los backorders.

Para cada política: problema observado -> información disponible -> regla -> efecto
esperado -> KPI -> resultado. Probar reglas por separado antes de combinarlas,
manteniendo recursos y restricciones comparables.

## 5. Comparar y preparar ANOVA

Comparar los escenarios con intervalos de confianza y magnitud de mejora, además
de discutir efectos adversos (por ejemplo, más washing para mejorar service).

Diseño candidato: `scenario` (Baseline/Traceability) combinado con presión de
demanda y/o screening capacity. Elegir niveles después del piloto; cada una de
las tres métricas seleccionadas debe tener al menos un factor justificado.
Estudiar interacciones con `scenario` para responder en qué condiciones cambia
la ventaja de RFID. Si las replications se parean por seed, reflejar ese bloqueo
en el análisis en lugar de tratarlas como observaciones independientes.

Usar resultados agregados por replication como unidades de análisis, comprobar
los supuestos del modelo estadístico y distinguir significancia estadística de
relevancia operativa. Preparar la presentación alrededor de evidencia, explicación
causal del modelo y recomendaciones, con las limitaciones explícitas.

## Próxima sesión propuesta

Revisar la medición implementada, analizar un piloto y después varias replications
del baseline con los seis KPIs antes de decidir qué política implementar.
