"""Experiment measurements only: no operational decisions or random draws.

Definitions: KPIS.md. RTI dispatch histories are reduced to one record per crate,
so memory grows with the fleet rather than the number of events.
"""

from collections import Counter
import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from statistics import fmean


@dataclass(slots=True)
class ReuseRecord:
    crate_type: str
    first_dispatch_day: int
    last_dispatch_day: int
    last_producer: str
    dispatches: int = 1


class KPIMeasurements:
    def __init__(self, producers, initial_fleet_size, *, low_stock_threshold=5000,
                 demand_window_days=7):
        if demand_window_days < 1 or low_stock_threshold < 0:
            raise ValueError("Invalid KPI window or stock threshold")
        self.initial_fleet_size = initial_fleet_size
        self.low_stock_threshold = low_stock_threshold
        self.demand_window_days = demand_window_days
        self.pairs = tuple(
            (p.producer_id, ct.name)
            for p in producers for ct in p.product.compatible_crates
        )
        self.reuse_records = {}
        self.completed_cycles = 0
        self.completed_cycle_days = 0
        self.washes = 0
        self.repairs = 0
        self._events_today = Counter()
        self.daily_rows = []
        self.producer_type_rows = []
        self.mismatch_type_rows = []

    def record_dispatch(self, rti, producer_id, day):
        record = self.reuse_records.get(rti.rti_id)
        if record is None:
            self.reuse_records[rti.rti_id] = ReuseRecord(
                rti.crate_type.name, day, day, producer_id
            )
        else:
            if day <= record.last_dispatch_day:
                raise ValueError("Consecutive dispatches must occur on different increasing days")
            duration = day - record.last_dispatch_day
            self.completed_cycles += 1
            self.completed_cycle_days += duration
            self._events_today['completed_cycles'] += 1
            self._events_today['completed_cycle_days'] += duration
            record.last_dispatch_day = day
            record.last_producer = producer_id
            record.dispatches += 1
        self._events_today['dispatches'] += 1

    def record_recovery(self, *, repaired):
        # In this baseline every processed RTI is washed; only broken ones are repaired.
        self.washes += 1
        self.repairs += int(repaired)
        self._events_today['washes'] += 1
        self._events_today['repairs'] += int(repaired)

    def collect_day(self, model):
        day = model.steps
        if day != len(self.daily_rows) + 1:
            raise ValueError("Collect KPI observations once per day, starting at day 1")

        demand = Counter()
        first_day = max(1, day - self.demand_window_days + 1)
        for order in model.all_orders:
            if (order.issuer == model.rdc_agent.rdc_id and order.uom == 'RTI'
                    and first_day <= order.creation_step <= day):
                demand[order.supplier, order.crate_type.name] += order.quantity

        stocks = {}
        backlog = Counter()
        for producer in model.producers:
            for ct in producer.product.compatible_crates:
                stocks[producer.producer_id, ct.name] = len(producer.forward_stock_pro[ct])
            for order in producer.order_book:
                if (order.issuer == model.rdc_agent.rdc_id and order.uom == 'RTI'
                        and day >= order.creation_step + order.lead_time):
                    backlog[producer.producer_id, order.crate_type.name] += order.quantity

        exposed = 0
        for producer_id, crate_type in self.pairs:
            key = producer_id, crate_type
            low = stocks[key] <= self.low_stock_threshold
            exposed += int(low)
            self.producer_type_rows.append({
                'day': day, 'producer': producer_id, 'crate_type': crate_type,
                'available_stock_rtis': stocks[key], 'window_demand_rtis': demand[key],
                'low_stock': int(low), 'due_backorder_rtis': backlog[key],
            })

        weighted_mismatch = 0.0
        total_demand = 0
        for crate_type in dict.fromkeys(ct for _, ct in self.pairs):
            pairs = [pair for pair in self.pairs if pair[1] == crate_type]
            type_demand = sum(demand[pair] for pair in pairs)
            type_stock = sum(stocks[pair] for pair in pairs)
            mismatch = None
            if type_demand:
                mismatch = (100.0 if not type_stock else 50.0 * sum(
                    abs(stocks[pair] / type_stock - demand[pair] / type_demand)
                    for pair in pairs
                ))
                weighted_mismatch += type_demand * mismatch
                total_demand += type_demand
            self.mismatch_type_rows.append({
                'day': day, 'crate_type': crate_type,
                'available_stock_rtis': type_stock, 'window_demand_rtis': type_demand,
                'mismatch_pct': mismatch,
            })

        self.daily_rows.append({
            'day': day,
            'inventory_demand_mismatch_pct': (
                weighted_mismatch / total_demand if total_demand else None
            ),
            'exposed_producer_type_days': exposed,
            'evaluated_producer_type_days': len(self.pairs),
            'due_pro_to_rdc_backorder_rtis': sum(backlog.values()),
            **{name: self._events_today[name] for name in (
                'washes', 'repairs', 'dispatches', 'completed_cycles', 'completed_cycle_days'
            )},
        })
        self._events_today.clear()

    def summary(self):
        days = len(self.daily_rows)
        mismatches = [row['inventory_demand_mismatch_pct'] for row in self.daily_rows
                      if row['inventory_demand_mismatch_pct'] is not None]
        exposed = sum(row['exposed_producer_type_days'] for row in self.daily_rows)
        evaluated = days * len(self.pairs)
        open_intervals = len(self.reuse_records)
        initiated = self.completed_cycles + open_intervals
        open_wait = sum(days - record.last_dispatch_day for record in self.reuse_records.values())
        return {
            'observed_days': days,
            'initial_fleet_rtis': self.initial_fleet_size,
            'kpis': {
                'inventory_demand_mismatch_pct': fmean(mismatches) if mismatches else None,
                'recovery_treatments_per_reuse': (
                    (self.washes + self.repairs) / self.completed_cycles
                    if self.completed_cycles else None
                ),
                'low_stock_exposure_pct': 100 * exposed / evaluated if evaluated else None,
                'cumulative_backorder_exposure_rti_days': sum(
                    row['due_pro_to_rdc_backorder_rtis'] for row in self.daily_rows
                ),
                'rti_turnover': (self.completed_cycles / self.initial_fleet_size
                                 if self.initial_fleet_size else None),
                'time_to_next_reuse_days': (
                    self.completed_cycle_days / self.completed_cycles
                    if self.completed_cycles else None
                ),
            },
            'supporting_counts': {
                'washing_operations': self.washes, 'repair_operations': self.repairs,
                'completed_cycles': self.completed_cycles,
                'completed_cycle_days': self.completed_cycle_days,
                'initiated_intervals': initiated, 'unfinished_intervals': open_intervals,
                'unfinished_intervals_pct': 100 * open_intervals / initiated if initiated else None,
                'unfinished_wait_mean_days': open_wait / open_intervals if open_intervals else None,
                'rtis_without_observed_dispatch': self.initial_fleet_size - open_intervals,
                'exposed_producer_type_days': exposed, 'evaluated_producer_type_days': evaluated,
                'valid_mismatch_days': len(mismatches),
            },
            'measurement_parameters': {
                'low_stock_threshold_rtis': self.low_stock_threshold,
                'demand_window_days': self.demand_window_days,
            },
        }

    def export(self, folder, metadata):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        summary = self.summary()
        (folder / 'kpi_summary.json').write_text(
            json.dumps(summary, indent=2, allow_nan=False) + '\n', encoding='utf-8'
        )
        (folder / 'run_metadata.json').write_text(
            json.dumps(metadata, indent=2, allow_nan=False) + '\n', encoding='utf-8'
        )
        self._write_csv(folder / 'kpi_summary.csv', ('kpi', 'value'), (
            {'kpi': name, 'value': value} for name, value in summary['kpis'].items()
        ))
        self._write_csv(folder / 'kpi_daily.csv', (
            'day', 'inventory_demand_mismatch_pct', 'exposed_producer_type_days',
            'evaluated_producer_type_days', 'due_pro_to_rdc_backorder_rtis',
            'washes', 'repairs', 'dispatches', 'completed_cycles', 'completed_cycle_days'
        ), self.daily_rows)
        self._write_csv(folder / 'kpi_producer_type_daily.csv', (
            'day', 'producer', 'crate_type', 'available_stock_rtis', 'window_demand_rtis',
            'low_stock', 'due_backorder_rtis'
        ), self.producer_type_rows)
        self._write_csv(folder / 'kpi_mismatch_type_daily.csv', (
            'day', 'crate_type', 'available_stock_rtis', 'window_demand_rtis', 'mismatch_pct'
        ), self.mismatch_type_rows)
        self._write_csv(folder / 'rti_reuse.csv', (
            'rti_id', 'crate_type', 'first_dispatch_day', 'last_dispatch_day',
            'last_producer', 'dispatches', 'completed_cycles', 'completed_cycle_days',
            'unfinished_wait_days'
        ), (
            {'rti_id': rti_id, **asdict(record),
             'completed_cycles': record.dispatches - 1,
             'completed_cycle_days': record.last_dispatch_day - record.first_dispatch_day,
             'unfinished_wait_days': len(self.daily_rows) - record.last_dispatch_day}
            for rti_id, record in self.reuse_records.items()
        ))

    @staticmethod
    def _write_csv(path, fields, rows):
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
