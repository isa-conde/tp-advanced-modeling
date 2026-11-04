"""Regression tests for initial state and node residence time.

Run: python -m unittest discover -s tests -v
Set BASELINE_MODULE=Assignment_code_baseline to reproduce failures in the original.
"""

import importlib
import itertools
import os
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
b = importlib.import_module(
    os.environ.get("BASELINE_MODULE", "Assignment_code_baseline_corrected")
)

# Small inventories exercise the same production code and flows quickly.
SMALL_MODEL = dict(
    UL_SIZE=2,
    TRUCK_CAPACITY=3,
    PRO_REORDER_POINT=3,
    PRO_REORDER_QTY=3,
    RDC_DAILY_DEMAND_MEAN=8,
    RDC_DAILY_DEMAND_STD=0,
    POOL_SCREENING_CAPACITY=2,
    INIT_POOL_WASHED_UL=2,
    INIT_POOL_UNWASHED_UL=2,
    INIT_PRO_UL=2,
    INIT_RDC_UL=1,
    INIT_RPOS_RTI=1,
    N_RPOS_BIG=1,
    N_RPOS_MEDIUM=1,
    N_RPOS_SMALL=1,
    N_RPOS=3,
)


def inventory(model):
    """Physical ownership, independent of the RTI's own location/age fields."""
    pool = model.pool_agent
    for stock in (pool.washed_stock_pool, pool.unwashed_stock_pool):
        for uls in stock.values():
            for ul in uls:
                for rti in ul.rtis:
                    yield ("POOL", pool.pool_id), b.LocationType.POOL, False, rti
    for ul in pool.processing_buffer:
        for rti in ul.rtis:
            yield ("POOL", pool.pool_id), b.LocationType.POOL, False, rti
    for pro in model.producers:
        for rtis in pro.forward_stock_pro.values():
            for rti in rtis:
                yield ("PRO", pro.producer_id), b.LocationType.PRO, False, rti
    for uls in model.rdc_agent.reverse_stock_rdc.values():
        for ul in uls:
            for rti in ul.rtis:
                yield ("RDC", model.rdc_agent.rdc_id), b.LocationType.R_DC, False, rti
    for pos in model.r_pos_agents:
        for rti in pos.displayed_rtis_rpos:
            yield ("RPOS", pos.unique_id), b.LocationType.R_POS, True, rti
        for rtis in pos.reverse_stock_rpos.values():
            for rti in rtis:
                yield ("RPOS", pos.unique_id), b.LocationType.R_POS, False, rti


class BaselineCorrectionsTests(unittest.TestCase):
    def setUp(self):
        self.random_state = random.getstate()
        self.addCleanup(random.setstate, self.random_state)
        random.seed(42)
        settings = patch.multiple(b, **SMALL_MODEL)
        settings.start()
        self.addCleanup(settings.stop)
        self.model = b.CLSC_Model()

    def new_rti(self, **kwargs):
        return b.RTI_Agent(self.model, **kwargs)

    def test_constructor_preserves_all_supplied_states(self):
        product = self.model.products[0]
        for location, washed, filled, value in itertools.product(
            b.LocationType, (False, True), (False, True), (None, product)
        ):
            with self.subTest(location=location, washed=washed, filled=filled, product=value):
                rti = self.new_rti(
                    crate_type=b.CrateType.TYPE_2,
                    washed=washed,
                    location=location,
                    is_filled=filled,
                    product=value,
                )
                self.assertIs(rti.crate_type, b.CrateType.TYPE_2)
                self.assertEqual(rti.washed, washed)
                self.assertIs(rti.location, location)
                self.assertEqual(rti.is_filled, filled)
                self.assertIs(rti.product, value)

    def test_constructor_defaults_remain_valid(self):
        rti = self.new_rti()
        self.assertIs(rti.crate_type, b.CrateType.TYPE_1)
        self.assertTrue(rti.washed)
        self.assertFalse(rti.is_filled)
        self.assertIsNone(rti.product)
        self.assertIs(rti.location, b.LocationType.POOL)

    def test_creation_later_in_the_run_starts_with_zero_age(self):
        self.model.steps = 7
        rti = self.new_rti()
        self.assertEqual(rti.arrival_time_at_node, 7)
        self.assertEqual(rti.detention_time, 0)

    def test_initial_individual_states_match_physical_stocks(self):
        for owner, location, filled, rti in inventory(self.model):
            with self.subTest(owner=owner, rti=rti.unique_id):
                self.assertIs(rti.location, location)
                self.assertEqual(rti.is_filled, filled)
                self.assertEqual(rti.detention_time, 0)
        for uls in self.model.pool_agent.washed_stock_pool.values():
            self.assertTrue(all(rti.washed for ul in uls for rti in ul.rtis))
        for uls in self.model.pool_agent.unwashed_stock_pool.values():
            self.assertTrue(all(not rti.washed for ul in uls for rti in ul.rtis))
        for uls in self.model.rdc_agent.reverse_stock_rdc.values():
            self.assertTrue(all(rti.product is not None for ul in uls for rti in ul.rtis))

    def test_every_receiving_method_resets_node_arrival_and_age(self):
        receivers = (
            (self.model.pool_agent.receive_uls, b.LocationType.POOL, True),
            (self.model.producers[0].receive_uls, b.LocationType.PRO, True),
            (self.model.rdc_agent.receive_rtis, b.LocationType.R_DC, False),
            (self.model.rdc_agent.receive_uls, b.LocationType.R_DC, True),
            (self.model.r_pos_agents[0].receive_rtis, b.LocationType.R_POS, False),
        )
        self.model.steps = 9
        for receive, location, unit_load in receivers:
            with self.subTest(receiver=receive.__qualname__):
                rti = self.new_rti()
                rti.arrival_time_at_node = 2
                rti.detention_time = 7
                payload = b.UnitLoad(crate_type=rti.crate_type, rtis=[rti]) if unit_load else rti
                receive([payload])
                self.assertIs(rti.location, location)
                self.assertEqual(rti.arrival_time_at_node, 9)
                self.assertEqual(rti.detention_time, 0)

    def test_main_step_updates_crates_held_at_rdc(self):
        rti = next(iter(self.model.rdc_agent.reverse_stock_rdc.values()))[0].rtis[0]
        with patch.object(self.model.rdc_agent, "generate_orders"), patch.object(
            self.model.rdc_agent, "extract_uls"
        ):
            for day in range(1, 4):
                self.model.step()
                self.assertEqual(rti.detention_time, day)

    def test_rdc_arrival_day_is_zero_and_repeated_update_does_not_add_time(self):
        rti = self.new_rti()
        self.model.steps = 5
        self.model.rdc_agent.receive_uls([b.UnitLoad(crate_type=rti.crate_type, rtis=[rti])])
        self.model.rdc_agent.step()
        self.model.rdc_agent.step()
        self.assertEqual(rti.detention_time, 0)
        self.model.steps = 7
        self.model.rdc_agent.step()
        self.assertEqual(rti.detention_time, 2)

    def test_late_pool_to_pro_arrival_matches_other_node_arrivals(self):
        # The Pooler runs after producers; a late arrival still starts at age 0.
        producer = self.model.producers[0]
        ct = producer.product.compatible_crates[0]
        rti = self.new_rti(crate_type=ct)
        self.model.steps = 5
        producer.receive_uls([b.UnitLoad(crate_type=ct, rtis=[rti])])
        self.assertEqual(rti.detention_time, 0)
        self.model.steps = 6
        with patch.object(producer, "fulfill_orders"), patch.object(producer, "generate_orders"):
            producer.step()
        self.assertEqual(rti.detention_time, 1)

    def test_sale_within_pos_keeps_same_node_arrival(self):
        pos = self.model.r_pos_agents[0]
        rti = pos.displayed_rtis_rpos[0]
        self.model.steps = 3
        pos.process_sales()
        self.assertIn(rti, pos.reverse_stock_rpos[rti.crate_type])
        self.assertFalse(rti.is_filled)
        self.assertEqual(rti.arrival_time_at_node, 0)
        with patch.object(pos, "extract_rtis"):
            pos.step()
        self.assertEqual(rti.detention_time, 3)

    def test_recovery_within_pool_keeps_same_node_arrival(self):
        pool = self.model.pool_agent
        self.model.steps = 5
        rti = self.new_rti()
        pool.receive_uls([b.UnitLoad(crate_type=rti.crate_type, rtis=[rti])])
        self.model.steps = 6
        with patch.object(pool, "fulfill_orders"):
            pool.step()
        self.assertFalse(rti.under_processing)
        self.assertEqual(rti.arrival_time_at_node, 5)
        self.assertEqual(rti.detention_time, 1)

    def test_40_days_three_seeds_against_independent_ownership_history(self):
        for seed in (3, 19, 42):
            with self.subTest(seed=seed):
                random.seed(seed)
                model = b.CLSC_Model()
                initial = list(inventory(model))
                ids = {rti.unique_id for _, _, _, rti in initial}
                self.assertEqual(len(ids), len(initial))
                history = {rti.unique_id: (owner, 0) for owner, _, _, rti in initial}
                types = {ct: sum(rti.crate_type == ct for _, _, _, rti in initial) for ct in b.CrateType}
                for day in range(1, 41):
                    model.step()
                    current = list(inventory(model))
                    self.assertEqual(len(current), len(ids))
                    self.assertEqual({rti.unique_id for _, _, _, rti in current}, ids)
                    for ct, count in types.items():
                        self.assertEqual(sum(rti.crate_type == ct for _, _, _, rti in current), count)
                    for owner, location, filled, rti in current:
                        previous_owner, arrived = history[rti.unique_id]
                        if owner != previous_owner:
                            arrived = day
                        history[rti.unique_id] = (owner, arrived)
                        self.assertIs(rti.location, location)
                        self.assertEqual(rti.is_filled, filled)
                        self.assertEqual(rti.arrival_time_at_node, arrived)
                        self.assertEqual(rti.detention_time, day - arrived)


if __name__ == "__main__":
    unittest.main()
