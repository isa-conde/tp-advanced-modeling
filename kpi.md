# Project KPIs - Second Draft

Five operational measures for comparing the corrected Baseline and Traceability
scenarios. Together they support the assessment of efficiency, effectiveness and
RTI circularity; each KPI does not have to belong exclusively to one dimension.
These definitions may be revised before or during measurement implementation.

## Common rules

- Calculate results separately for each replication, normally over 365 days.
- Observe stocks and outstanding orders at day-end, excluding the initial day 0.
- Use the same definitions and horizon in both scenarios.
- Evaluate producer-type availability only for compatible crate types.
- Measurements observe the experiment; they do not give agents additional
  information for operational decisions.

| KPI | Main question | Unit | Interpretation |
| --- | --- | --- | --- |
| Stockout frequency | How often is a required crate type unavailable at a producer? | % of compatible producer-type-days | Lower is preferable. |
| Average backorders | How many due RTIs remain undelivered on an average day? | RTIs | Lower is preferable. |
| Average inventory by node | Where do crates accumulate? | RTIs per node | Interpret availability and accumulation together. |
| RTI turnover | How much reuse does the whole fleet achieve? | Completed observed cycles per fleet RTI | Higher is preferable. |
| Recovery treatments per reuse | How much recovery work is performed per reuse cycle? | Treatments per completed observed cycle | Lower is preferable, subject to fitness for use. |

## 1. Stockout frequency

A stockout observation occurs when a producer ends a day with **zero available
empty RTIs of a compatible crate type**. Count each producer-type-day once.
Do not include incompatible types or replenishment orders that have not arrived.

```text
Stockout frequency (%) =
100 × producer-type-days with zero stock / total compatible producer-type-days
```

Report the overall percentage and the breakdown by producer and crate type.
This is day-end availability, not the number of separate stockout events or
every intraday shortage. Zero stock can occur without an actual delivery failure
if no order requires that type; KPI 2 measures outstanding commitments.

## 2. Average backorders

At each day-end, count the remaining RTIs in orders **from the RDC to producers**
whose delivery deadline has been reached. Include only the outstanding balance
of partially fulfilled orders and include zero-backorder days in the average.

```text
Average backorders (RTIs) =
sum of daily due PRO-to-RDC backorder quantities / number of simulated days
```

For example, 1,000 RTIs outstanding for 10 days contribute 10,000 RTI-days to the
numerator; divide by the full simulation horizon to obtain the daily average.
Retain producer-type breakdowns. Pooler backorders concern another order tier
and may be reported separately, but are not added to this KPI.

## 3. Average inventory by node

For each node, average its physical RTI inventory across all day-end observations.

```text
Average inventory at node n (RTIs) =
sum of day-end RTI quantities at node n / number of simulated days
```

Include each RTI once in a node's total. Retain crate-type and stock-state
breakdowns: for example, washed/unwashed/processing at the Pooler and
displayed/empty at points of sale. State breakdowns are parts of the node total,
not additional inventory to add again. Record transit separately if present
at day-end.

This KPI is a profile across nodes, not the average of the total fleet: the
network's total number of RTIs is conserved. Lower inventory is not automatically
better; assess accumulation together with stockouts, backorders and throughput.

## 4. RTI turnover

An **observed reuse cycle** is completed between two consecutive filled-crate
dispatches of the same RTI from a producer to the RDC, after circulation through
the return loop. The first observed dispatch starts tracking; the next completes
one cycle. No history before the simulation is assumed.

```text
RTI turnover = completed observed reuse cycles / total initial RTI fleet
```

Include the whole initial fleet, including RTIs that complete no cycles. A value
of 2 means two completed observed cycles per fleet RTI on average over the
simulated horizon. Zero completed cycles gives zero turnover for a nonempty fleet.
Do not annualize short test runs or compare unequal horizons as annual results.

## 5. Recovery treatments per reuse

Count washing and repair operations per RTI during the simulation. Repairing and
then washing one crate counts as two treatments; repeatedly treating the same
crate counts each actual operation.

```text
Recovery treatments per reuse =
(washing operations + repair operations) / completed observed reuse cycles
```

Use the same cycle definition as KPI 4. Count all recovery work within the
horizon, even if some associated cycles remain unfinished at the end. If no
cycles finish, report the ratio as N/A and retain the operation counts.
Lower effort is preferable only while required recovery and service conditions
are respected; skipping necessary treatments is not an improvement.

## Data requirements and scope

Existing producer stocks, order books and model stock reporters provide the
basic data for KPIs 1-3. KPIs 4-5 require tracking repeated dispatches by RTI ID,
counting the initial fleet and counting actual washing/repair operations.

This branch starts from `main`, without the first draft's measurement module.
Implement only the records needed by the current definitions. Inventory-demand
mismatch, low-stock exposure and time to next reuse are not headline KPIs in
this second draft; they may be reconsidered later as diagnostic measures.
