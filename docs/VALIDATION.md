# Validation

Validation is designed to test existing behavior without changing the MEIO algorithm.

## Automated test suite

Run:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Retained result for this package:

```text
12 passed
```

| Validation area | Test behavior |
|---|---|
| Service factor / safety stock / reorder point | Confirms equations against independently calculated values |
| Echelon inventory | Confirms downstream effective inventory is included |
| Repair/return credit | Confirms caller-supplied return quantity and yield are used only for repairable records |
| Topology validation | Confirms cyclic topology is rejected |
| Governance guardrail | Confirms out-of-threshold policy changes preserve prior values and require exception role |
| Baseline optimization | Confirms structured output and global supply/budget behavior |
| Node capacity | Confirms primary replenishment does not exceed remaining node capacity |
| Edge-flow capacity | Confirms explicit child-subtree flow limit binds |
| Service-level validation | Confirms invalid target returns 400 through Lambda wrapper |
| Required request fields | Confirms missing required configuration returns 400 |
| Risk simulation | Confirms seeded Monte Carlo output is deterministic for identical input |
| Offline replay | Confirms supplied observations/baseline are evaluated and bounded fill rates are returned |

## Retained scenario evidence

`evidence/validation_summary.json` summarizes actual execution outputs from the included source. Raw requests and responses are retained separately.

Key observed controlled behavior in this snapshot:

- baseline optimizer status: `OPTIMAL`;
- reducing available upstream supply to 15 limits total allocation to 15;
- setting regional budget to 1500 with ample supply limits allocation through the budget constraint;
- a strict zero-change guardrail with a changed demand input produces `APPROVAL_REQUIRED` and the exception approver role;
- an explicit `NATIONAL_HUB->DENVER_HUB` edge capacity of 2 limits the Denver allocation accordingly;
- the seeded risk scenario returns repeatable modeled stockout/fill-rate values;
- offline replay returns current-policy and caller-supplied baseline comparisons.

## Numerical presentation note

`RecommendedAllocation` values in policy responses are rounded to four decimal places, while LP feasibility is determined using internal floating-point values before response rounding. Recomputing a budget from displayed rounded allocations can therefore differ from the internal bound by a very small rounding amount. Validation should use a tolerance consistent with the output precision rather than treating display rounding as additional allocation.

## Evidence boundary

These tests and scenario runs validate behavior of the controlled reference implementation. They do not establish production performance, production deployment, carrier adoption, or real-world economic outcomes.
