import csv
from enum import Enum
import json
from pathlib import Path
import random
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import Assignment_code_baseline_corrected as baseline
from kpi_measurements import KPIMeasurements
from test_baseline_corrections import SMALL_MODEL


Crate = Enum('Crate', 'A B')


def order(producer, crate, quantity, day=1, lead_time=0, issuer='RDC', uom='RTI'):
    return SimpleNamespace(issuer=issuer, supplier=producer, crate_type=crate,
                           quantity=quantity, creation_step=day, lead_time=lead_time, uom=uom)


def example_model(stocks, orders=(), pending=(), day=1):
    producers = []
    for producer_id, by_type in stocks.items():
        producers.append(SimpleNamespace(
            producer_id=producer_id,
            product=SimpleNamespace(compatible_crates=list(by_type)),
            forward_stock_pro={ct: [None] * count for ct, count in by_type.items()},
            order_book=[o for o in pending if o.supplier == producer_id],
        ))
    return SimpleNamespace(steps=day, producers=producers,
                           rdc_agent=SimpleNamespace(rdc_id='RDC'), all_orders=list(orders))


class KPIFormulaTests(unittest.TestCase):
    def test_mismatch_80_20_vs_50_50_is_30_percent(self):
        model = example_model({'P1': {Crate.A: 80}, 'P2': {Crate.A: 20}},
                              [order('P1', Crate.A, 50), order('P2', Crate.A, 50)])
        kpi = KPIMeasurements(model.producers, 100)
        kpi.collect_day(model)
        self.assertAlmostEqual(kpi.summary()['kpis']['inventory_demand_mismatch_pct'], 30)

    def test_mismatch_is_demand_weighted_across_types_and_excludes_no_demand(self):
        model = example_model({'P1': {Crate.A: 10, Crate.B: 10},
                               'P2': {Crate.A: 0, Crate.B: 10}}, [
            order('P1', Crate.A, 50), order('P2', Crate.A, 50),
            order('P1', Crate.B, 150), order('P2', Crate.B, 150),
        ])
        kpi = KPIMeasurements(model.producers, 30)
        kpi.collect_day(model)
        # Type A: 50%, weight 100; type B: 0%, weight 300.
        self.assertAlmostEqual(kpi.summary()['kpis']['inventory_demand_mismatch_pct'], 12.5)

    def test_demand_without_stock_is_100_percent_and_no_demand_is_na(self):
        model = example_model({'P1': {Crate.A: 0, Crate.B: 20}}, [order('P1', Crate.A, 5)])
        kpi = KPIMeasurements(model.producers, 20)
        kpi.collect_day(model)
        self.assertEqual(kpi.daily_rows[0]['inventory_demand_mismatch_pct'], 100)
        self.assertIsNone(kpi.mismatch_type_rows[1]['mismatch_pct'])
        empty = example_model({'P1': {Crate.A: 20}})
        no_demand = KPIMeasurements(empty.producers, 20)
        no_demand.collect_day(empty)
        self.assertIsNone(no_demand.summary()['kpis']['inventory_demand_mismatch_pct'])

    def test_seven_day_window_expires_day_one_and_uses_original_requests(self):
        model = example_model({'P1': {Crate.A: 10}, 'P2': {Crate.A: 0}}, [
            order('P1', Crate.A, 100), order('P2', Crate.A, 100, day=8),
            order('P1', Crate.A, 999, issuer='PRO', uom='UL'),
        ])
        kpi = KPIMeasurements(model.producers, 10)
        for day in range(1, 9):
            model.steps = day
            kpi.collect_day(model)
        self.assertEqual(kpi.daily_rows[6]['inventory_demand_mismatch_pct'], 0)
        self.assertEqual(kpi.daily_rows[7]['inventory_demand_mismatch_pct'], 100)

    def test_low_stock_counts_threshold_equality_and_only_compatible_pairs(self):
        model = example_model({'P1': {Crate.A: 5000}, 'P2': {Crate.B: 5001}})
        kpi = KPIMeasurements(model.producers, 10001)
        kpi.collect_day(model)
        self.assertEqual(kpi.summary()['kpis']['low_stock_exposure_pct'], 50)
        self.assertEqual(kpi.summary()['supporting_counts']['evaluated_producer_type_days'], 2)

    def test_backorder_exposure_counts_only_due_rdc_remaining_quantities(self):
        late = order('P1', Crate.A, 1000)
        not_due = order('P1', Crate.A, 9000, lead_time=10)
        upstream = order('P1', Crate.A, 9999, issuer='POOL', uom='UL')
        model = example_model({'P1': {Crate.A: 0}}, pending=[late, not_due, upstream])
        kpi = KPIMeasurements(model.producers, 1)
        kpi.collect_day(model)
        model.steps = 2
        late.quantity = 400  # A partial fulfillment leaves only 400 pending.
        kpi.collect_day(model)
        self.assertEqual(kpi.summary()['kpis']['cumulative_backorder_exposure_rti_days'], 1400)

    def test_reuse_cycles_recovery_ratio_and_open_intervals(self):
        model = example_model({'P1': {Crate.A: 0}})
        kpi = KPIMeasurements(model.producers, 4)
        a = SimpleNamespace(rti_id='a', crate_type=Crate.A)
        b = SimpleNamespace(rti_id='b', crate_type=Crate.A)
        for day in range(1, 11):
            model.steps = day
            if day in (1, 4, 9):
                kpi.record_dispatch(a, 'P1', day)
            if day == 8:
                kpi.record_dispatch(b, 'P1', day)
            if day == 2:
                kpi.record_recovery(repaired=True)   # Two treatments.
                kpi.record_recovery(repaired=False)  # One treatment.
            kpi.collect_day(model)
        result = kpi.summary()
        self.assertEqual(result['kpis']['recovery_treatments_per_reuse'], 1.5)
        self.assertEqual(result['kpis']['rti_turnover'], 0.5)
        self.assertEqual(result['kpis']['time_to_next_reuse_days'], 4)
        self.assertEqual(result['supporting_counts']['unfinished_intervals_pct'], 50)
        self.assertEqual(result['supporting_counts']['unfinished_wait_mean_days'], 1.5)
        self.assertEqual(result['supporting_counts']['rtis_without_observed_dispatch'], 2)

    def test_no_completed_cycles_is_na_not_zero_and_day_zero_is_excluded(self):
        model = example_model({'P1': {Crate.A: 1}})
        kpi = KPIMeasurements(model.producers, 1)
        result = kpi.summary()['kpis']
        self.assertIsNone(result['recovery_treatments_per_reuse'])
        self.assertIsNone(result['time_to_next_reuse_days'])
        self.assertIsNone(result['low_stock_exposure_pct'])
        model.steps = 0
        with self.assertRaises(ValueError):
            kpi.collect_day(model)

    def test_duplicate_observations_and_dispatches_are_rejected(self):
        model = example_model({'P1': {Crate.A: 1}})
        kpi = KPIMeasurements(model.producers, 1)
        rti = SimpleNamespace(rti_id='a', crate_type=Crate.A)
        kpi.record_dispatch(rti, 'P1', 1)
        with self.assertRaises(ValueError):
            kpi.record_dispatch(rti, 'P1', 1)
        kpi.collect_day(model)
        with self.assertRaises(ValueError):
            kpi.collect_day(model)


class KPIIntegrationTests(unittest.TestCase):
    def setUp(self):
        state = random.getstate()
        self.addCleanup(random.setstate, state)
        settings = patch.multiple(baseline, **SMALL_MODEL)
        settings.start()
        self.addCleanup(settings.stop)

    def test_measurement_does_not_change_flows_or_random_state(self):
        frames = []
        states = []
        for enabled in (False, True):
            model = baseline.CLSC_Model(seed=42, measure_kpis=enabled)
            for _ in range(40):
                model.step()
            frames.append(model.datacollector.get_model_vars_dataframe())
            states.append(random.getstate())
        self.assertTrue(frames[0].equals(frames[1]))
        self.assertEqual(states[0], states[1])

    def test_logged_dispatches_and_backlogs_reconcile_with_existing_reporters(self):
        model = baseline.CLSC_Model(seed=19)
        for _ in range(40):
            model.step()
        frame = model.datacollector.get_model_vars_dataframe().iloc[1:]
        flow_columns = [c for c in frame if c.startswith('Flow|PRO_') and '|RDC|' in c]
        backlog_columns = [c for c in frame if c.startswith('Backorders|PRO_')]
        kpi = model.kpi_measurements
        self.assertEqual(sum(row['dispatches'] for row in kpi.daily_rows),
                         int(frame[flow_columns].sum().sum()))
        self.assertEqual(kpi.summary()['kpis']['cumulative_backorder_exposure_rti_days'],
                         int(frame[backlog_columns].sum().sum()))
        self.assertEqual(kpi.completed_cycles, sum(r.dispatches - 1 for r in kpi.reuse_records.values()))
        self.assertEqual(kpi.completed_cycle_days,
                         sum(r.last_dispatch_day - r.first_dispatch_day for r in kpi.reuse_records.values()))

    def test_repair_counter_observes_broken_state_before_it_is_cleared(self):
        model = baseline.CLSC_Model(seed=42)
        healthy = baseline.RTI_Agent(model)
        broken = baseline.RTI_Agent(model)
        broken.broken = True
        model.pool_agent.process_rti(healthy)
        model.pool_agent.process_rti(broken)
        self.assertEqual(model.kpi_measurements.washes, 2)
        self.assertEqual(model.kpi_measurements.repairs, 1)
        self.assertFalse(broken.broken)

    def test_export_contains_six_kpis_metadata_and_reconciled_reuse_rows(self):
        with TemporaryDirectory() as folder:
            model = baseline.CLSC_Model(results_dir=folder, seed=42)
            for _ in range(10):
                model.step()
            model.export_kpis()
            root = Path(folder)
            result = json.loads((root / 'kpi_summary.json').read_text())
            metadata = json.loads((root / 'run_metadata.json').read_text())
            self.assertEqual(len(result['kpis']), 6)
            self.assertEqual(result['observed_days'], 10)
            self.assertEqual(metadata['seed'], 42)
            self.assertEqual(metadata['parameters']['KPI_LOW_STOCK_THRESHOLD'], 5000)
            with (root / 'kpi_summary.csv').open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 6)
            with (root / 'rti_reuse.csv').open() as handle:
                reuse = list(csv.DictReader(handle))
            self.assertEqual(sum(int(row['completed_cycles']) for row in reuse),
                             result['supporting_counts']['completed_cycles'])


if __name__ == '__main__':
    unittest.main()
