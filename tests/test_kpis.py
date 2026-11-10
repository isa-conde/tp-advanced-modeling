"""Known-answer examples and passive-observer regression tests."""
from collections import Counter
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from test_baseline_corrections import b, SMALL_MODEL, inventory


class KPITests(unittest.TestCase):
    def setUp(self):
        state = random.getstate()
        self.addCleanup(random.setstate, state)
        settings = patch.multiple(b, **SMALL_MODEL)
        settings.start()
        self.addCleanup(settings.stop)
        random.seed(42)
        self.model = b.CLSC_Model(measure_kpis=True)
        self.observer = self.model.kpi_observer

    def test_known_day_end_stockouts_backorders_and_node_averages(self):
        m, obs = self.model, self.observer
        pro = m.producers[0]
        ct = pro.product.compatible_crates[0]
        rtis = pro.forward_stock_pro[ct][:]
        initial_fleet = obs.initial_fleet
        # Move stock to one POS: day 1 zero at PRO, day 2 replenished.
        pro.forward_stock_pro[ct].clear()
        pos = m.r_pos_agents[0]
        pos.reverse_stock_rpos[ct].extend(rtis)
        pos_initial = len(pos.displayed_rtis_rpos) + sum(map(len, pos.reverse_stock_rpos.values()))
        def order(qty, created, lt):
            return b.OrderLine('RDC_1', pro.producer_id, 'test', ct, qty, 'RTI', lt, created)
        pro.order_book = [order(3, 0, 1), order(100, 1, 5)]
        m.pool_agent.order_book = [b.OrderLine(pro.producer_id, 'POOL_1', 'pool', ct, 999, 'UL', 0, 0)]
        m.steps = 1
        obs.collect(m)
        # Outstanding balance drops to 1; day 3 contributes zero.
        pro.order_book[0].quantity = 1
        pro.forward_stock_pro[ct].extend(rtis)
        del pos.reverse_stock_rpos[ct][-len(rtis):]
        m.steps = 2
        obs.collect(m)
        pro.order_book.pop(0)
        m.steps = 3
        obs.collect(m)
        result = obs.summary()
        pairs = sum(len(p.product.compatible_crates) for p in m.producers)
        self.assertAlmostEqual(result['Stockout frequency'], 100 / (3 * pairs))
        self.assertEqual(result['stockout_observations'], 1)
        self.assertAlmostEqual(result['Average backorders'], 4 / 3)
        nodes = {r['node']: r['average_inventory'] for r in result['Average inventory by node']}
        self.assertAlmostEqual(nodes['RPOS_01'], pos_initial - 2 * len(rtis) / 3)
        self.assertEqual(sum(nodes.values()), initial_fleet)
        self.assertEqual(len([n for n in nodes if n.startswith('RPOS_')]), 3)
        states = result['inventory_by_node_type_state']
        for node, total in nodes.items():
            self.assertAlmostEqual(sum(r['average_inventory'] for r in states if r['node'] == node), total)
        with tempfile.TemporaryDirectory() as directory:
            obs.export(directory, {'seed': 42, 'horizon_days': 3})
            saved = json.loads((Path(directory) / 'kpis.json').read_text())
            self.assertIsNone(saved['kpis']['Recovery treatments per reuse'])
            self.assertEqual(saved['kpis']['RTI turnover'], 0)
            self.assertEqual(len(list(Path(directory).glob('*.csv'))), 3)

    def test_real_dispatch_and_processing_hooks_known_cycles(self):
        m, obs = self.model, self.observer
        pro = m.producers[0]
        ct = pro.product.compatible_crates[0]
        rti = pro.forward_stock_pro[ct][0]
        pro.forward_stock_pro[ct] = [rti]
        def dispatch():
            pro.order_book = [b.OrderLine('RDC_1', pro.producer_id, 'x', ct, 1, 'RTI', 0, 0)]
            pro.fulfill_orders()
            m.rdc_agent.forward_rtis_received_this_step.remove(rti)
        dispatch()
        self.assertEqual(obs.completed_cycles, 0)  # First dispatch never completes a cycle.
        # Route this RTI through the real return and recovery methods.
        pos = m.r_pos_agents[0]
        pos.receive_rtis([rti])
        m.steps = 3
        pos.process_sales()
        pos.reverse_stock_rpos[ct].remove(rti)
        ul = b.UnitLoad(crate_type=ct, rtis=[rti])
        m.rdc_agent.receive_uls([ul])
        m.rdc_agent.reverse_stock_rdc[ct].remove(ul)
        m.pool_agent.receive_uls([ul])
        rti.broken = True
        m.steps = 4
        m.pool_agent.process_uls()
        m.pool_agent.washed_stock_pool[ct].remove(ul)
        pro.receive_uls([ul])
        dispatch()
        self.assertEqual(obs.completed_cycles, 1)
        # More work within horizon counts even without another completed cycle.
        m.pool_agent.process_rti(rti)
        obs.last_day = 0
        m.steps = 1
        obs.collect(m)
        result = obs.summary()
        self.assertEqual(result['washing_operations'], 2)
        self.assertEqual(result['repair_operations'], 1)
        self.assertEqual(result['Recovery treatments per reuse'], 3)
        self.assertEqual(result['RTI turnover'], 1 / obs.initial_fleet)

    def test_no_cycles_retains_work_counts_and_empty_fleet_is_explicit(self):
        m, obs = self.model, self.observer
        m.pool_agent.process_rti(m.producers[0].forward_stock_pro[b.CrateType.TYPE_1][0])
        m.steps = 1
        obs.collect(m)
        self.assertEqual(obs.summary()['washing_operations'], 1)
        self.assertIsNone(obs.summary()['Recovery treatments per reuse'])
        obs.initial_fleet = 0
        self.assertIsNone(obs.summary()['RTI turnover'])
        with self.assertRaises(ValueError):
            obs.collect(m)

    def test_observer_does_not_change_operation_for_three_seeds(self):
        def snapshot(m):
            ownership = [(owner, r.unique_id, r.crate_type.name, r.washed, r.broken,
                          r.dirty, r.is_filled, r.detention_time, r.arrival_time_at_node,
                          r.product.name if r.product else None)
                         for owner, _, _, r in inventory(m)]
            def orders(book):
                return [(o.issuer, o.supplier, o.crate_type.name, o.quantity, o.creation_step,
                         o.lead_time, o.needs_washed) for o in book]
            return (ownership, orders(m.all_orders), orders(m.pool_agent.order_book),
                    [orders(p.order_book) for p in m.producers],
                    [dict(p.on_order_from_pool) for p in m.producers],
                    [m.pool_agent.processing_times[u.id] for u in m.pool_agent.processing_buffer])
        for seed in (3, 19, 42):
            random.seed(seed)
            reference = b.CLSC_Model()
            expected = []
            for _ in range(60):
                reference.step()
                expected.append((snapshot(reference), random.getstate()))
            random.seed(seed)
            measured = b.CLSC_Model(measure_kpis=True)
            for state, rng in expected:
                measured.step()
                self.assertEqual(snapshot(measured), state)
                self.assertEqual(random.getstate(), rng)
            self.assertTrue(reference.datacollector.get_model_vars_dataframe().equals(
                measured.datacollector.get_model_vars_dataframe()))
            # All day-end physical stocks, including each POS, must conserve fleet.
            totals = Counter()
            for row in measured.kpi_observer.inventory_days:
                totals[row['day']] += row['quantity']
            self.assertEqual(set(totals.values()), {measured.kpi_observer.initial_fleet})
            self.assertGreater(measured.kpi_observer.completed_cycles, 0)


if __name__ == '__main__':
    unittest.main()
