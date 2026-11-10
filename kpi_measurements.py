"""Passive experiment observations for kpi.md (second draft). No random draws."""
from collections import Counter
import json
from pathlib import Path

import pandas as pd


class KPIObserver:
    def __init__(self, model):
        self.initial_fleet = sum(hasattr(a, 'rti_id') for a in model.agents)
        self.dispatched_ids = set()
        self.completed_cycles = 0
        self.treatments = Counter()
        self.producer_days = []
        self.inventory_days = []
        self.activity_days = []
        self.last_day = 0

    def dispatch(self, rti):
        # The only route back to a producer in this baseline is the return loop.
        if rti.rti_id in self.dispatched_ids:
            self.completed_cycles += 1
        self.dispatched_ids.add(rti.rti_id)

    def recovery(self, rti):
        # Called before process_rti clears broken and performs its unconditional wash.
        self.treatments['washing'] += 1
        if rti.broken:
            self.treatments['repair'] += 1

    def collect(self, model):
        day = model.steps
        if day != self.last_day + 1:
            raise ValueError('Collect exactly once at each consecutive day-end, starting at 1')
        self.last_day = day
        for pro in model.producers:
            for ct in pro.product.compatible_crates:
                stock = len(pro.forward_stock_pro[ct])
                due = sum(o.quantity for o in pro.order_book
                          if o.crate_type == ct and day >= o.creation_step + o.lead_time)
                self.producer_days.append(dict(day=day, producer=pro.producer_id,
                                               crate_type=ct.name, stock=stock,
                                               stockout=int(stock == 0), backorders=due))

        types = list(model.pool_agent.washed_stock_pool)
        def record(node, kind, state, counts):
            for ct in types:
                self.inventory_days.append(dict(day=day, node=node, node_kind=kind,
                                                state=state, crate_type=ct.name,
                                                quantity=counts.get(ct, 0)))

        pool = model.pool_agent
        for state, stock in [('washed', pool.washed_stock_pool),
                             ('unwashed', pool.unwashed_stock_pool)]:
            record(pool.pool_id, 'POOL', state,
                   {ct: sum(len(ul.rtis) for ul in uls) for ct, uls in stock.items()})
        record(pool.pool_id, 'POOL', 'processing',
               Counter({ct: sum(len(ul.rtis) for ul in pool.processing_buffer
                                if ul.crate_type == ct) for ct in types}))
        for pro in model.producers:
            record(pro.producer_id, 'PRO', 'empty',
                   {ct: len(rtis) for ct, rtis in pro.forward_stock_pro.items()})
        rdc = model.rdc_agent
        record(rdc.rdc_id, 'RDC', 'empty',
               {ct: sum(len(ul.rtis) for ul in uls) for ct, uls in rdc.reverse_stock_rdc.items()})
        record(rdc.rdc_id, 'RDC', 'filled',
               Counter(rti.crate_type for rti in rdc.forward_rtis_received_this_step))
        for i, pos in enumerate(model.r_pos_agents, 1):
            node = f'RPOS_{i:02d}'  # Stable list position, independent of random UUIDs.
            record(node, 'RPOS', 'displayed', Counter(r.crate_type for r in pos.displayed_rtis_rpos))
            record(node, 'RPOS', 'empty', {ct: len(rt) for ct, rt in pos.reverse_stock_rpos.items()})
        # All transfers are synchronous: TRANSPORT is an intraday state only.
        self.activity_days.append(dict(day=day, completed_cycles=self.completed_cycles,
                                       washing=self.treatments['washing'], repair=self.treatments['repair']))

    def summary(self):
        if not self.last_day:
            raise ValueError('At least one simulated day is required')
        producers = pd.DataFrame(self.producer_days)
        inventory = pd.DataFrame(self.inventory_days)
        by_pair = producers.groupby(['producer', 'crate_type'], sort=True)
        stockouts = by_pair.stockout.agg(['sum', 'count']).reset_index()
        stockouts['percentage'] = 100 * stockouts['sum'] / stockouts['count']
        backorders = by_pair.backorders.mean().reset_index(name='average_backorders')
        state_means = inventory.groupby(['node', 'node_kind', 'crate_type', 'state'], sort=True).quantity.mean()
        node_means = inventory.groupby(['day', 'node', 'node_kind']).quantity.sum().groupby(['node', 'node_kind']).mean()
        cycles = self.completed_cycles
        return {
            'observed_days': self.last_day,
            'Stockout frequency': 100 * float(producers.stockout.mean()),
            'stockout_observations': int(producers.stockout.sum()),
            'compatible_producer_type_days': len(producers),
            'stockout_by_producer_type': stockouts.to_dict('records'),
            'Average backorders': float(producers.groupby('day').backorders.sum().mean()),
            'backorders_by_producer_type': backorders.to_dict('records'),
            'Average inventory by node': node_means.reset_index(name='average_inventory').to_dict('records'),
            'inventory_by_node_type_state': state_means.reset_index(name='average_inventory').to_dict('records'),
            'initial_fleet': self.initial_fleet,
            'completed_observed_cycles': cycles,
            'RTI turnover': cycles / self.initial_fleet if self.initial_fleet else None,
            'washing_operations': self.treatments['washing'],
            'repair_operations': self.treatments['repair'],
            'Recovery treatments per reuse': sum(self.treatments.values()) / cycles if cycles else None,
            'ratio_status': 'defined' if cycles else 'N/A: no completed observed cycles',
            'turnover_status': 'defined' if self.initial_fleet else 'N/A: empty initial fleet',
            'day_end_transit': 'No overnight transit in the corrected baseline; transfers are synchronous',
        }

    def export(self, directory, metadata):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        result = dict(metadata=metadata, kpis=self.summary())
        (directory / 'kpis.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        for name, rows in [('producer_days', self.producer_days),
                           ('inventory_days', self.inventory_days), ('activity_days', self.activity_days)]:
            pd.DataFrame(rows).to_csv(directory / f'{name}.csv', index=False)
        return result
