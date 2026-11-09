# Project KPIs

Specification for comparing the corrected Baseline and Traceability scenarios.
These are group-defined measures, implemented in `kpi_measurements.py` and
collected by the corrected baseline. Run one replication with
`python run_baseline.py --seed 42 --steps 365`. See
[MEDICION_KPIS.md](MEDICION_KPIS.md) for data sources, code changes and outputs.

## Common definitions

- **Horizon:** days 1-365; day 0 is the initial state. Daily stocks and backlogs
  are measured at day-end. Calculate results separately for each replication.
- **Observed reuse cycle:** the interval between two consecutive filled-crate
  dispatches of the same RTI from a producer to the RDC, including the return loop.
  The first observed dispatch starts tracking; the next completes one cycle.
  No use history before the simulation is assumed.
- Use identical definitions and measurement rules in both scenarios.
- Short smoke runs report their actual observed horizon; results are not annualized.

| # | KPI | Dimension | Unit | Preferred direction |
| --- | --- | --- | --- | --- |
| 1 | Inventory-demand mismatch | Efficiency | % | Lower |
| 2 | Recovery treatments per reuse | Efficiency | Treatments/completed cycle | Lower, subject to fitness for use |
| 3 | Low-stock exposure | Effectiveness | % of producer-type-days | Lower |
| 4 | Cumulative backorder exposure | Effectiveness | RTI-days | Lower |
| 5 | RTI turnover | RTI circularity | Completed cycles/RTI over 365 days | Higher |
| 6 | Time to next reuse | RTI circularity | Days/completed cycle | Lower, interpreted with unfinished intervals |

## 1. Inventory-demand mismatch

**Purpose:** assess whether crates are allocated to the producers that need them.

For each day and crate type, compare the distribution of available empty-crate
stock across compatible producers with their share of RDC demand. Demand means
the original quantities ordered during the last seven days, including today,
whether fulfilled or not. Use available history during days 1-6.

For crate type `c`, let `s_pc` be producer `p`'s share of that type's stock and
`d_pc` its share of that type's demand:

```text
Mismatch_c (%) = 100 × 0.5 × sum over compatible producers |s_pc - d_pc|
```

The daily KPI is the demand-weighted average across crate types; the annual KPI
is the average of valid daily values. A type with demand but no available stock
receives 100%. Types with no demand are excluded; days with no demand at all are
excluded from the annual average.

**Interpretation:** 0% means stock and demand shares match. This measures relative
allocation, not whether total inventory is sufficient. For example, stock shares
of 80%/20% versus demand shares of 50%/50% give a mismatch of 30%.

## 2. Recovery treatments per reuse

**Purpose:** relate recovery effort to actual reuse achieved.

```text
KPI = (washing operations + repair operations) / completed observed reuse cycles
```

Count operations per RTI: repairing and then washing one crate counts as two
treatments. Include all treatments performed during the horizon, even if the
associated cycle is unfinished at the end.

**Interpretation:** lower effort per completed cycle is preferable, provided
required washing and repairs are performed. If no cycles are completed, report
the ratio as N/A and retain the treatment counts.

## 3. Low-stock exposure

**Purpose:** identify shortage risk before delivery failures necessarily occur.

A compatible producer-type combination is exposed when its available physical
empty-crate stock is **at or below 5,000 RTIs** at day-end. Outstanding orders to
the Pooler are not available stock. Keep this reference threshold fixed across
the compared scenarios.

```text
Exposure (%) = 100 × exposed producer-type-days / evaluated producer-type-days
```

The denominator includes every compatible producer-type combination for all
365 days. Retain the breakdown by producer and crate type.

**Interpretation:** lower exposure is preferable. Exposure is a risk indicator;
it does not imply that an actual backorder occurred.

## 4. Cumulative backorder exposure

**Purpose:** capture both the size and duration of delivery failures.

```text
KPI (RTI-days) = sum over days of outstanding RTIs in due PRO-to-RDC orders
```

At each day-end, count only the remaining quantities in RDC orders to producers
whose delivery deadline has been reached. A shortage of 1,000 RTIs lasting ten
days contributes 10,000 RTI-days. Retain producer and crate-type breakdowns.

**Interpretation:** lower is preferable. Pooler backorders may be examined
separately but are not added to this KPI, since they concern another order tier.

## 5. RTI turnover

**Purpose:** measure reuse achieved by the entire available fleet.

```text
Turnover = completed observed reuse cycles / total initial RTI fleet
```

Include every RTI in the denominator, including crates that complete no cycles.

**Interpretation:** higher is preferable. A value of 2 means two completed
observed cycles per fleet RTI on average over the simulated year, not two cycles
for every individual crate.

## 6. Time to next reuse

**Purpose:** measure how quickly a crate returns to productive use.

```text
Cycle time = next PRO-to-RDC dispatch day - previous dispatch day of the same RTI
KPI = arithmetic mean of completed observed cycle times
```

Each completed cycle has equal weight. The interval includes circulation,
display, waiting, recovery and storage.

Always accompany this average with:

- The percentage of initiated intervals still unfinished at day 365:
  `100 × unfinished intervals / (completed + unfinished intervals)`.
- Their mean elapsed waiting time: `365 - last dispatch day` for each RTI with
  an unfinished interval. Report N/A if there are no such intervals.

**Interpretation:** shorter completed cycles are preferable, but must be read
alongside unfinished intervals to avoid hiding long waits. Unfinished intervals
are not zero-duration or completed cycles. RTIs with no observed dispatch have
no initiated interval; they remain included in KPI 5's fleet denominator.
If no cycles finish, report the completed-cycle average as N/A.

## Joint interpretation

Read the six measures together: improved allocation or faster reuse may involve
more recovery work, while low stocks may increase service risk. The accompanying
unfinished-interval statistics support KPI 6; they are not additional headline KPIs.
