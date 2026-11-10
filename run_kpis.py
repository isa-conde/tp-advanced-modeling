"""Run one reproducible replication of the corrected baseline with passive KPIs."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--days', type=int, default=365)
    parser.add_argument('--output', type=Path, default=Path('results/kpis_second_draft'))
    parser.add_argument('--excel', action='store_true', help='Also export the baseline Excel (includes day 0)')
    args = parser.parse_args()
    if args.days < 1:
        parser.error('--days must be positive')
    # Sets affect producer iteration order. Set this before Python starts, not at runtime.
    if os.environ.get('PYTHONHASHSEED') != '0':
        os.execve(sys.executable, [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
                  dict(os.environ, PYTHONHASHSEED='0'))

    import Assignment_code_baseline_corrected as baseline
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ') + '_' + uuid.uuid4().hex[:8]
    directory = args.output / run_id
    directory.mkdir(parents=True, exist_ok=False)
    source_dir = Path(__file__).resolve().parent
    # Constants declared before the imports are the model's configuration.
    configuration = {name: value for name, value in vars(baseline).items()
                     if name.isupper() and name != 'ALL_CRATE_TYPES'}
    configuration['SIMULATION_STEPS'] = args.days
    metadata = dict(run_id=run_id, scenario='corrected_baseline', seed=args.seed,
                    horizon_days=args.days, pythonhashseed=0, configuration=configuration,
                    python=sys.version, versions={p: importlib.metadata.version(p)
                                                  for p in ('mesa', 'pandas', 'openpyxl')},
                    source_sha256={name: hashlib.sha256((source_dir / name).read_bytes()).hexdigest()
                                   for name in ('Assignment_code_baseline_corrected.py',
                                                'kpi_measurements.py', 'run_kpis.py', 'kpi.md')})
    (directory / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    random.seed(args.seed)
    model = baseline.CLSC_Model(results_dir=str(directory), run_timestamp=run_id, measure_kpis=True)
    for day in range(1, args.days + 1):
        model.step()
        if day % 30 == 0 or day == args.days:
            print(f'Day {day}/{args.days}', flush=True)
    result = model.kpi_observer.export(directory, metadata)
    if args.excel:
        model.export_to_excel()
    print(json.dumps({key: result['kpis'][key] for key in
                      ('Stockout frequency', 'Average backorders', 'RTI turnover',
                       'Recovery treatments per reuse')}, indent=2))
    print(f'Results: {directory.resolve()}')


if __name__ == '__main__':
    main()
