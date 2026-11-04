# Correcciones del Baseline Scenario

## Para qué hicimos estos cambios

Antes de evaluar el valor de RFID, necesitamos que el modelo describa correctamente
el estado y la permanencia de cada caja. Si esos datos están mal, una política que
los utilice puede tomar decisiones equivocadas aunque su lógica sea razonable.

Corregimos dos errores: cómo nace una RTI en la simulación y cómo se mide el tiempo
que permanece en un nodo. Estas son correcciones del baseline, no el Traceability
Scenario ni mejoras operativas atribuibles a RFID.

Para leer esta explicación sin conocer el código: una **RTI** es una caja
reutilizable. Un **nodo** es uno de los lugares por los que pasa: el Pooler o POOL
la gestiona y recupera, el PRO es el productor, el RDC es el centro de distribución
y el RPOS es el punto de venta. El **baseline** es la versión de referencia del
sistema, contra la que después compararemos nuevas reglas de gestión.

## Archivos y organización

| Archivo | Para qué sirve |
| --- | --- |
| `Assignment_code_baseline.py` | Original del profesor, conservado sin modificaciones. |
| `Assignment_code_baseline_corrected.py` | Copia de trabajo con las dos correcciones. |
| `tests/test_baseline_corrections.py` | Pruebas automáticas de los estados y el reloj. |
| `CORRECCIONES_BASELINE.md` | Explicación de los cambios y cómo comprobarlos. |

## Corrección 1: cada caja debe comenzar con el estado que le corresponde

### Qué ocurría

Al crear una caja, el modelo indicaba dónde estaba, si estaba lavada, si estaba
llena y qué producto llevaba o había llevado. Pero la parte del código que
construía la caja ignoraba esos datos y siempre registraba:

- Ubicación: Pooler.
- Lavada: sí.
- Llena: no.
- Producto: ninguno.

Es como guardar una caja llena de fruta en un supermercado y escribir en su ficha
que es una caja vacía ubicada en el centro de lavado. La caja está en un sitio,
pero su ficha dice otra cosa.

### Qué corregimos

La ficha ahora conserva los datos que el modelo proporciona al crear la RTI:

| Dato | Nombre en el código | Antes | Ahora |
| --- | --- | --- | --- |
| Estado de lavado | `washed` | Siempre `True` | Usa el valor recibido. |
| Ubicación | `location` | Siempre `POOL` | Usa la ubicación recibida. |
| Si contiene productos | `is_filled` | Siempre `False` | Usa el valor recibido. |
| Producto asociado | `product` | Siempre `None` | Conserva el producto recibido, o `None` si no hay uno. |

Por ejemplo, las cajas iniciales en exhibición en un RPOS ahora figuran como llenas
y ubicadas en ese punto de venta. Las cajas del stock unwashed del Pooler figuran
como no lavadas. El producto asociado a las cajas iniciales del RDC también se
conserva; eso permite evaluar correctamente su condición al retornar al Pooler.

Esto no agrega información que antes no existiera: evita perder la que el propio
modelo ya estaba proporcionando. Tampoco asigna productos nuevos donde el original
no los especificaba. Si se crea una caja sin indicar esos datos, los valores por
defecto siguen siendo los del original.

## Corrección 2: un reloj de permanencia coherente para todos los nodos

### Qué ocurría

`detention_time` representa cuánto tiempo lleva una caja en su nodo actual.
Encontramos tres partes del mismo problema:

1. El RDC tenía un método que incrementaba ese contador, pero la secuencia diaria
   principal nunca lo ejecutaba. Una caja podía esperar allí varios días sin que
   el contador lo reflejara.
2. El momento de llegada no se registraba de forma uniforme en todos los nodos.
3. Sumar uno cada vez que actuaba un nodo hacía que el día de llegada se contara
   de manera distinta según el orden de ejecución. Una caja recibida antes de la
   actualización de un nodo podía terminar con edad 1 ese mismo día; una recibida
   después podía terminar con edad 0.

Por eso agregar solamente la llamada al RDC habría solucionado una parte del
error, pero habría dejado un reloj inconsistente.

### Qué significa ahora el contador

Usamos una convención explícita para las observaciones al cierre de cada día:

**En el día de llegada, la permanencia es 0. Al día siguiente es 1; dos días después
es 2, siempre que la caja continúe en ese mismo nodo.**

El modelo trabaja en días, no en horas. El contador registra días transcurridos
desde la llegada, no fracciones de día ni el tiempo total desde el inicio del run.

La regla es:

```text
detention_time = día actual - día de llegada al nodo actual
```

En el código, el día actual es `model.steps` y el día de llegada se guarda en
`arrival_time_at_node`. Las cajas presentes al inicio llegan en el día 0. Si se
crea una caja durante una simulación ya iniciada, su reloj también comienza en 0
en el día de creación.

### Qué cambiamos en el código

- Al recibir una caja, cada nodo registra su nueva ubicación, guarda el día de
  llegada y pone su permanencia en 0. Se revisaron las recepciones en POOL, PRO,
  RDC (forward y reverse flows) y RPOS.
- Las actualizaciones de permanencia calculan la diferencia entre días en lugar
  de sumar uno. Repetir una actualización dentro del mismo día no agrega tiempo.
- La secuencia principal ahora llama a `RDC_Agent.step()` después de despachar
  los ULs de retorno. Así actualiza la permanencia de las cajas que quedan en el
  RDC esperando un camión.
- Se conservan los reinicios a 0 durante los despachos. Al recibir la caja, el
  destino establece además su propia fecha de llegada.

Los movimientos internos no reinician el reloj: vender el producto y pasar una
caja de exhibición a stock vacío sigue ocurriendo dentro del mismo RPOS. De la
misma manera, terminar el lavado y pasar a stock sigue ocurriendo dentro del POOL.

### Ejemplo de una caja

Supongamos que una caja llega a un RPOS grande y, tras la venta, debe esperar
varios días hasta completar un UL:

| Día | Qué pasa | Nodo al cierre | `detention_time` |
| --- | --- | --- | ---: |
| 10 | Llega llena al punto de venta. | RPOS | 0 |
| 11 | Se vende el producto; queda vacía en el mismo punto de venta. | RPOS | 1 |
| 12 | Sigue esperando completar el UL. | RPOS | 2 |
| 13 | Completa un UL y se envía al RDC; permanece allí. | RDC | 0 |
| 14 | Sigue esperando un camión completo. | RDC | 1 |
| 15 | Se despacha y llega al Pooler para recuperación. | POOL | 0 |
| 16 | Termina la recuperación y queda en stock del Pooler. | POOL | 1 |

Cada cambio de nodo comienza una nueva permanencia. El tiempo en nodos anteriores
no se acumula en este contador. Para medir el tiempo total de un ciclo, más adelante
necesitaremos un historial o contador adicional.

## Qué se conserva del baseline

Estas correcciones mantienen los parámetros de demanda, stocks iniciales, tamaños
de UL y camión, capacidades, lead times y políticas de selección random. También
mantienen el orden de las operaciones físicas del día; se agrega la actualización
del reloj del RDC después de su despacho.

Como detalle de organización, al ejecutar la copia corregida sus resultados se
guardan en `run_corrected_YYYY.MM.DD_HH.MM/`. El original continúa usando
`run_YYYY.MM.DD_HH.MM/`. Así ambas versiones pueden ejecutarse sin compartir el
destino de resultados. Cada versión sigue usando precisión de un minuto: evitar
repetir la misma versión dentro de ese minuto si se desean conservar ambos runs.

## Cómo lo comprobamos

Las 11 pruebas automáticas verifican:

- Que los datos recibidos al crear una RTI se conserven y que los valores por
  defecto sigan siendo válidos.
- Que los estados iniciales individuales coincidan con los stocks físicos.
- Que cada recepción reinicie la permanencia y registre la llegada.
- Que el RDC actualice su reloj dentro de la secuencia diaria real.
- Que el día de llegada cuente como 0 y que no se cuenten días dos veces.
- Que las llegadas tardías POOL -> PRO respeten la misma regla.
- Que vender dentro del RPOS o terminar la recuperación dentro del POOL no
  reinicie la permanencia en ese nodo.
- Que durante 40 días, para cada una de tres seeds (3, 19 y 42), todas las cajas
  coincidan con un historial independiente de cambios de nodo. También se verifica
  conservación por tipo y ausencia de cajas duplicadas o perdidas.

Estos recorridos usan inventarios reducidos para que las pruebas sean rápidas;
ejecutan las mismas clases y operaciones del archivo corregido. Las 11 pruebas
pasan en la copia corregida. Al ejecutarlas contra el original, se reproducen
fallos: las pruebas distinguen la versión con errores de la versión corregida.

### Ejecución completa con el tamaño real del assignment

El 4 de noviembre de 2026 también se ejecutaron los 365 días de la copia corregida,
con seed 42 para esta comprobación y `PYTHONHASHSEED=0` en el proceso de validación.
No se agregaron esos ajustes a la ejecución directa del baseline.

Resultado: **PASS**.

- 366 observaciones: estado inicial y cierre de los días 1 a 365.
- 322.800 RTIs conservadas por tipo en todos los cierres diarios: 78.200 TYPE_1,
  78.200 TYPE_2, 88.200 TYPE_3 y 78.200 TYPE_4.
- Ninguna cantidad negativa ni dato faltante en las métricas recogidas.
- Sin referencias duplicadas ni cajas perdidas en los inventarios físicos inicial
  y final; ubicación y estado de contenido coherentes en ambos.
- Al finalizar, las 322.800 cajas cumplen la regla de permanencia respecto de su
  llegada al nodo actual. La comprobación contra un historial independiente en
  cada día se realizó en los recorridos reducidos descritos arriba.
- Excel exportado y reabierto correctamente con las hojas Stock, Flows,
  Backorders y Orders.

La evidencia local está en
[validation_report.json](results/baseline_corrections_validation/validation_report.json)
y el [Excel de validación](results/baseline_corrections_validation/sim_log_corrected_seed42.xlsx).
La carpeta `results/` está excluida de Git; estos archivos de evidencia quedan en
esta computadora.

## ¿Cambió algo en el Excel? ¿Entonces para qué corregirlo?

**Las correcciones hicieron más confiable la información de cada caja. En la
comparación que realizamos, las cantidades del Excel quedaron iguales.**

Para comprobarlo, ejecutamos el original y la copia corregida durante 365 días
con la misma seed (42) y el mismo ajuste de orden aleatorio (`PYTHONHASHSEED=0`).
La seed es una forma de repetir la secuencia de sorteos de la simulación. En
esta comparación permite evitar que una diferencia se deba simplemente a que
una ejecución tuvo otra demanda u otras selecciones al azar.

| Hoja | Qué muestra | Resultado de la comparación |
| --- | --- | --- |
| Stock | Cuántas cajas hay en cada stock y de cada tipo. | Ninguna diferencia. |
| Flows | Cuántas cajas se mueven entre los lugares de la red. | Ninguna diferencia. |
| Backorders | Cuántas cajas quedan pendientes de entregar en pedidos ya vencidos. | Ninguna diferencia. |
| Orders | Los pedidos generados, con sus cantidades, fechas y condiciones. | Mismo contenido, excluyendo `Order ID`. |

`Order ID` es la etiqueta que identifica a cada pedido. Se genera de nuevo al
ejecutar el programa y no es un indicador de rendimiento. Por eso se excluyó
de la comparación; sí se compararon las demás columnas de los pedidos.

Este resultado corresponde a esa ejecución controlada. **No encontramos una
reducción de backorders ni un cambio en los flujos que podamos atribuir a estas
correcciones.** La comparación está guardada en el
[informe local](results/baseline_comparison/comparison_report.json).

### Una caja puede estar bien contada y tener mal su ficha

Imaginemos un depósito con diez cajas en una estantería. Las contamos y anotamos:
"Hay diez cajas en esta estantería". Ese número está bien.

Ahora miramos la ficha individual de una de esas cajas. Dice que está en otro
edificio y que está vacía, aunque la tenemos delante llena de fruta. El recuento
sigue dando diez, pero la ficha está mal.

Eso explica lo que pasaba en el modelo. El Excel cuenta las cajas dentro de las
listas de cada stock. Por ejemplo, si una caja está en la lista del supermercado,
la cuenta allí. Para ese recuento no consulta si la ficha individual de la caja
también dice "estoy en el supermercado" o "estoy llena".

En el estado inicial del original encontramos estas diferencias entre las fichas
y lo que el propio modelo indicaba al crear las cajas:

- **162.800 cajas** tenían registrada una ubicación equivocada.
- **20.800 cajas** estaban en exhibición, pero su ficha decía que estaban vacías.
- **242.800 cajas** se creaban como no lavadas, pero su ficha decía que estaban lavadas.
- **12.000 cajas** del RDC perdían el dato del producto asociado que se les había asignado.

Estos grupos se superponen: una misma caja puede tener más de un dato mal. No
hay que sumar las cuatro cifras como si fueran cajas distintas.

La primera corrección hace que la ficha conserve los datos que le corresponden.
Que el total de cajas ya fuera correcto no hacía correctos esos otros datos.

### También podemos contar bien una caja y medir mal cuánto lleva esperando

Imaginemos ahora que una caja llega al RDC y permanece allí tres días. Un registro
correcto debería decir que lleva tres días en ese lugar. En el original, el
contador del RDC podía seguir indicando cero porque no se actualizaba.

Si el Excel pregunta solamente "¿cuántas cajas hay?", la respuesta sigue siendo
una. Por eso el error puede pasar desapercibido: **el Excel actual no muestra el
tiempo de permanencia de cada caja**.

La segunda corrección permite registrar esa espera con la misma regla en todos
los lugares: cero el día de llegada, uno al día siguiente, dos al otro, etcétera.

### Qué mejora concreta demostraron las pruebas

Las pruebas plantean situaciones con una respuesta conocida. Por ejemplo:

- Si creamos una caja llena en un punto de venta, su ficha debe decir "llena" y
  "en ese punto de venta". El original no respetaba esos datos; la copia corregida sí.
- Si una caja permanece tres días en el RDC sin salir, su contador debe marcar
  tres. En esa prueba, el original marca cero y la copia corregida marca tres.
- Si la caja llega a otro nodo, su nueva permanencia debe empezar en cero. Si
  solo pasa de exhibición a stock vacío dentro del mismo supermercado, debe
  conservar la fecha en que llegó a ese supermercado.

Las 11 pruebas pasan en la copia corregida y detectan fallos en el original.
Esto demuestra que se corrigieron esas inconsistencias. La conservación de las
cajas y la exportación del Excel también se comprobaron, pero esas dos cosas ya
funcionaban antes: no las presentamos como mejoras obtenidas con estos cambios.

### Por qué esto importa para las próximas decisiones

Supongamos que queremos dar prioridad a las cajas que llevan más tiempo esperando.
Para decidir, necesitamos distinguir una caja que llegó hoy de otra que está
esperando hace varios días. Si ambas figuran con tiempo cero, la regla recibe
información equivocada y puede elegir mal.

Lo mismo ocurre si queremos usar la ubicación, el estado de lavado o el producto
que llevó cada caja. RFID permite identificar cajas individuales y asociarles
información; el modelo tiene que conservar y actualizar bien esa información
para que podamos estudiar decisiones que la utilicen.

La justificación de estas correcciones es que **ahora podemos construir medidas
de desempeño (KPIs) y reglas de decisión sobre datos coherentes**. Para demostrar
que una nueva regla reduce esperas, pedidos pendientes o trabajo de lavado,
todavía tendremos que implementarla y comparar sus resultados con los del
baseline corregido.

### Repetir las comprobaciones

Desde la raíz del repositorio, con el entorno activado:

```bash
python -m unittest discover -s tests -v
python Assignment_code_baseline_corrected.py
```

El segundo comando ejecuta los 365 días con la configuración completa del
assignment y exporta el Excel. Los KPIs de permanencia todavía no se agregaron
a ese Excel; las pruebas comprueban directamente los atributos de cada caja.

## Cómo explicarlo en la presentación

> Antes de probar nuevas reglas de gestión, revisamos que la información de cada
> caja fuera correcta. Encontramos cajas cuya ficha indicaba una ubicación o un
> estado distintos de los que les correspondían, y un contador que no reflejaba
> los días de espera en el centro de distribución. Corregimos ambos problemas y
> comprobamos su funcionamiento con pruebas. En una comparación de 365 días, las
> cantidades del Excel quedaron iguales, porque ese archivo cuenta cajas pero no
> muestra toda su información individual. El aporte de estas correcciones es
> contar con datos coherentes para medir el sistema y evaluar después si las
> decisiones apoyadas en RFID mejoran su desempeño.

## Qué sigue después de la revisión del grupo

Con estas dos correcciones revisadas, el próximo paso es acordar los KPIs e
instrumentar su medición. Sigue pendiente preparar la configuración de seeds y
replications para los experimentos, y aclarar la interpretación del stock inicial
de los PROs mencionada en `ROADMAP.md`. El éxito de estas pruebas no equivale a
validar todos los supuestos del modelo ni a demostrar mejoras de performance.
