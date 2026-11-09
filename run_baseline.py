"""Run one corrected-baseline replication with KPI output and recorded settings."""

import argparse
from datetime import datetime
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def build_run_metadata(model):
    module = sys.modules[type(model).__module__]
    source = Path(module.__file__).resolve()
    root = source.parent
    parameters = {
        name: value for name, value in vars(module).items()
        if name.isupper() and not name.startswith('_') and name != 'ALL_CRATE_TYPES'
    }
    def git_value(*args):
        try:
            result = subprocess.run(
                ['git', '-C', str(root), *args], capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    status = git_value('status', '--porcelain')
    return {
        'scenario': 'baseline_corrected', 'model': type(model).__name__,
        'seed': model.run_seed, 'python_hash_seed': os.environ.get('PYTHONHASHSEED'),
        'observed_days': model.steps, 'python': platform.python_version(),
        'packages': {name: version(name) for name in ('mesa', 'pandas', 'openpyxl')},
        'git_commit': git_value('rev-parse', 'HEAD'),
        'working_tree_dirty': status != '' if status is not None else None,
        'source_sha256': {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (source, root / 'kpi_measurements.py', root / 'run_baseline.py')
        },
        'parameters': parameters,
        'reproducibility_notes': (
            'Sequential replications: the baseline uses Python global random. '
            'Use a fixed PYTHONHASHSEED as well as the seed; UUID labels vary between runs. '
            'Shared exogenous random streams across different policies are not implemented.'
        ),
    }


def main():
    # The baseline iterates sets. Fix their process-level order before importing it.
    if os.environ.get('PYTHONHASHSEED') != '0':
        os.execve(sys.executable, [sys.executable, *sys.argv],
                  {**os.environ, 'PYTHONHASHSEED': '0'})

    import Assignment_code_baseline_corrected as baseline

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--steps', type=int, default=baseline.SIMULATION_STEPS)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.steps < 1 or args.seed < 0:
        parser.error('--steps must be positive and --seed must be nonnegative')
    stamp = datetime.now().strftime('%Y.%m.%d_%H.%M.%S_%f')
    folder = args.output_dir or Path('results') / f'baseline_{stamp}_seed{args.seed}'
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        parser.error('Output directory is not empty; choose a new directory')
    folder.mkdir(parents=True, exist_ok=True)
    model = baseline.CLSC_Model(results_dir=str(folder), run_timestamp=stamp, seed=args.seed)
    for day in range(1, args.steps + 1):
        model.step()
        if day % 25 == 0 or day == args.steps:
            print(f'Day {day}/{args.steps}', flush=True)
    model.export_to_excel()
    model.export_kpis()
    print(json.dumps(model.kpi_measurements.summary()['kpis'], indent=2), flush=True)
    print(f'Results: {folder.resolve()}', flush=True)


if __name__ == '__main__':
    main()
