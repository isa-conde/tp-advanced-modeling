# Advanced Modeling for Operations - Group Assignment

Agent-Based Simulation de una **RTI closed-loop supply chain** para evaluar el
valor de usar información RFID en las decisiones operativas.

## Preparar el entorno

Usamos Python 3.12 (entorno local preparado con Python 3.12.7 en macOS Apple Silicon).
Cada integrante crea su propio virtual environment dentro del repositorio:

```bash
git clone https://github.com/isa-conde/tp-advanced-modeling.git
cd tp-advanced-modeling
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

Comprobar primero que `python3 --version` sea 3.12.x. En Windows, la activación
en PowerShell es `.venv\Scripts\Activate.ps1`.

Las dependencias principales son Mesa, pandas y openpyxl. `requirements.txt`
también fija sus dependencias transitivas. El entorno `.venv` es local y no se
sube a GitHub. Si se usa un editor, elegir `.venv/bin/python` como intérprete
(en Windows: `.venv\Scripts\python.exe`).

## Ejecutar el baseline

Desde la raíz del repositorio, con el entorno activado:

```bash
python Assignment_code_baseline_corrected.py
```

El script ejecuta **365 steps**, con **1 step = 1 día**, y genera un Excel en
`run_corrected_YYYY.MM.DD_HH.MM/`, con las hojas `Stock`, `Flows`, `Backorders` y `Orders`.
Los resultados se excluyen de Git. El nombre de carpeta tiene precisión de un
minuto: esperar al minuto siguiente o cambiar el destino antes de repetir una
ejecución para evitar sobrescribir resultados.

El archivo `Assignment_code_baseline.py` se incorporó sin modificar el original
de Drive. Conservar este punto de partida para poder comparar cambios de lógica.
La copia `Assignment_code_baseline_corrected.py` corrige los estados iniciales y
el reloj de permanencia. La explicación está en
[CORRECCIONES_BASELINE.md](CORRECCIONES_BASELINE.md). Para ejecutar la referencia
original: `python Assignment_code_baseline.py`; sus resultados siguen en `run_.../`.
Ninguna de las dos versiones configura todavía una seed en su ejecución directa;
sus resultados varían entre runs. Antes de realizar experimentos hay que preparar
la reproducibilidad y revisar los pendientes de [ROADMAP.md](ROADMAP.md).

Para comprobar las correcciones:

```bash
python -m unittest discover -s tests -v
```

### Verificación del entorno (4 de noviembre de 2026)

- `pip check` sin incompatibilidades.
- Ejecución completa del original: 365 días y exportación Excel correcta.
- Las cuatro hojas esperadas están presentes; Stock, Flows y Backorders incluyen
  366 observaciones temporales (estado inicial y días 1-365), sin cantidades negativas.
- El stock total conserva las 322.800 RTIs, por crate type, al cierre de cada día.

Esta ejecución corresponde al original. La validación de la copia corregida se
describe en [CORRECCIONES_BASELINE.md](CORRECCIONES_BASELINE.md).

## Material de referencia

- [Carpeta del assignment en Drive](https://drive.google.com/drive/folders/1vywSI3hNvZRdFgjm6whrnlX2EiiimrMh).
- [Código original](https://drive.google.com/file/d/1G8iSHPWW4aXr5LcqFx2bzk_6o6vuujpI/view).
- [Problem description y consigna](https://drive.google.com/file/d/1QjMdU0VwPYSbuBlQMbN28AbJmM126r5s/view), slides 38-41 para tasks y entregables.
- [Model description](https://drive.google.com/file/d/1uS0lwxobxxJl_q9B5uKdEPMg-I310QJJ/view).
- [Presentación original del assignment](https://drive.google.com/file/d/1ftHoEuQu_Ijx2IwSnQOoNb-GRMJMzTM_/view).

SHA-256 del código descargado:
`904fa580ddf227c467d4c6dd3a050a68a115ff42c7f9671f7ecdd0053a3695bb`.

## Trabajo en grupo

Antes de empezar: `git pull --ff-only`. Para cambios nuevos, crear una branch
con un nombre descriptivo y abrir un Pull Request para que otro integrante revise.
Subir código y documentación; mantener `.venv`, resultados y archivos temporales
fuera del repositorio.

El plan propuesto, las métricas y los puntos pendientes de validación están en
[ROADMAP.md](ROADMAP.md).
