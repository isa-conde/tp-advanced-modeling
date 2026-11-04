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

El código original queda conservado. Estos puntos se detectaron al leerlo y deben
resolverse/documentarse antes de usar estados individuales para una política RFID:

- `RTI_Agent.__init__` recibe `washed`, `location`, `is_filled` y `product`, pero
  asigna valores fijos (`True`, `POOL`, `False` y `None`). Las listas de stock y
  los atributos individuales pueden describir estados iniciales diferentes.
- `RDC_Agent.step()` incrementa `detention_time` en el RDC, pero
  `CLSC_Model.step()` no lo llama. Revisar también cuándo se reinicia la edad al
  cambiar de nodo. Una política basada en edad requiere un reloj consistente.
- Los PROs comienzan con stock solo de sus crate types compatibles. La slide de
  descripción dice "for each crate type": confirmar si se refiere a compatibles.
- Las decisiones aleatorias usan el módulo global `random`; el modelo no recibe
  una seed. Además, se itera un `set` de tipos compatibles, cuyo orden puede variar
  entre procesos. Una seed de Mesa por sí sola no controla esas decisiones.

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

Empezar con pocas métricas que cubran las tres dimensiones:

| Dimensión | KPI propuesto | Datos necesarios |
| --- | --- | --- |
| Effectiveness | Backlog medio y máximo, por nodo y crate type | Hoja Backorders; cantidades en RTIs |
| Effectiveness | Fracción de demanda atendida a tiempo | Instrumentar cantidad y fecha de fulfillment por order |
| Efficiency | Utilización del screening y RTIs lavadas/reparadas | Nuevos contadores diarios; no confundir lavado con inspección |
| Circularity | Ciclos completados por RTI durante el horizonte | Historial/contador por RTI, con frontera de ciclo explícita |
| Circularity | Detention time medio y percentil 95 por nodo | Corregir/validar el reloj y registrar entradas/salidas |

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

Revisar juntos `CLSC_Model.step()` siguiendo una caja a través del loop, acordar
los puntos de validación anteriores e instrumentar los primeros KPIs. Después,
ejecutar un piloto del baseline antes de decidir qué política implementar.
