# Architecture-to-Code Map

This map links implemented behavior to inspectable source and reproducible evidence. Source presence is not treated as proof of production deployment.

| Technical component | Implementation | Source | Reproducible evidence |
|---|---|---|---|
| Lambda/API request decoding | Direct JSON or proxy-body decoding, including base64 wrapper | `lambda_function.py` → `_payload_from_event` | Tests for Lambda request/error handling; direct execution |
| Record validation | Dataclass construction, numeric bounds, service-level validation, prior-policy consistency | `MEIORecord`, `parse_records`, `validate_record` | `tests/test_meio_engine.py` |
| Local inventory position | `OnHand + OnOrder + InTransit` | `local_inventory_position` | Core-equation test; policy output |
| Repair/return credit | `Return_Qty × RepairYield` only when caller marks item repairable | `repair_return_credit`, `effective_inventory_position` | Repair-credit test; backend smoke output |
| Service-level factor | Inverse normal CDF | `service_level_factor` | Core-equation test |
| Safety stock | `z × sigma × sqrt(lead time)` | `safety_stock` | Core-equation test; baseline response |
| Reorder point | expected lead-time demand + safety stock | `reorder_point` | Core-equation test; baseline response |
| Topology validation | Normalizes graph and rejects cycles | `validate_topology` | Cycle-rejection test |
| Downstream traversal | Traverses downstream nodes while avoiding repeat visits | `descendants` | Used by echelon-inventory test |
| Echelon inventory | Effective node inventory plus downstream effective inventory | `echelon_inventory` | Echelon-inventory test; baseline response |
| Criticality handling | Validates `AX`, `AY`, `BZ`, `CZ`; optional explicit priority weights | `_criticality_weights` | Optimizer evidence in responses |
| Surge configuration | Caller-supplied region/default multipliers | `_surge_parameters` | Backend capability; direct JSON only |
| Edge-flow constraints | Adds child-subtree capacity constraints | `parse_edge_capacities`, `_edge_subtree_constraints` | `evidence/scenarios/edge_flow/` |
| Governance guardrail | Compares proposed policy with prior values and threshold | `_pct_change`, `apply_guardrail` | Guardrail unit test; `evidence/scenarios/guardrail/` |
| Allocation optimizer | Dependency-free primal simplex | `simplex_maximize`, `optimize_eq4` | Baseline + supply/budget/edge scenarios |
| Shared supply constraint | Limits total allocation by available upstream supply | `optimize_eq4` | `evidence/scenarios/supply_constraint/` |
| Regional budget constraint | Limits unit-cost-weighted allocation when budget is supplied | `optimize_eq4` | `evidence/scenarios/budget_constraint/` |
| Node capacity | Caps replenishment by remaining node capacity | `optimize_eq4` | Automated capacity test |
| Substitution | Caller-defined second-pass cross-SKU substitution | `apply_substitution` | Backend capability; direct JSON only unless separately exercised |
| Monte Carlo stress test | Seeded repeated stochastic demand/supply/logistics simulation | `run_risk_simulation` | Risk test; `evidence/scenarios/risk_model/` |
| Offline replay | Evaluates generated policies against caller-supplied observations | `run_offline_replay` | Replay test; `evidence/scenarios/offline_replay/` |
| Policy versioning and audit | Policy IDs, data version, approval metadata, rollback reference | `NodePolicy`, `AuditRecord`, `build_for_sku` | Baseline response `policies` and `audit` arrays |
| Full orchestration | Groups records by SKU, executes policy build, optional substitution/risk/replay | `run_meio` | All retained execution scenarios |
| Lambda response wrapper | 200/400/500 response contract | `lambda_handler` | Automated Lambda validation tests |
| Excel input conversion | Converts `Records`, `Topology`, `SKU_Config`, `Run_Config` sheets to JSON | `index.html` → `workbookToMeioPayload`, `buildRecords`, `buildTopology`, `buildSkuConfig`, `buildRunConfig` | Controlled workbook + browser execution |
| Browser API execution | Internal request POST to configured endpoint | `index.html` → run handler / `fetch` | Requires configured remote endpoint |
| Browser result rendering | Policy table and complete response display | `index.html` | Browser execution |
