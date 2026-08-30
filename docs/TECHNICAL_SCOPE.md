# Technical Scope

This repository documents the implemented multi-echelon inventory optimization (MEIO) system.

## Implemented capabilities

| Technical capability | Implementation | Status |
|---|---|---|
| Multi-echelon topology | `validate_topology` | Implemented |
| Echelon inventory | `echelon_inventory` | Implemented |
| Safety stock | `service_level_factor`, `safety_stock` | Implemented |
| Reorder point | `reorder_point` | Implemented |
| Constrained allocation | `simplex_maximize`, `optimize_eq4` | Implemented |
| Available supply constraint | `optimize_eq4` | Implemented |
| Regional budget constraint | `optimize_eq4` | Implemented |
| Node capacity | `optimize_eq4` | Implemented |
| Optional edge-flow capacity | `parse_edge_capacities`, `_edge_subtree_constraints` | Implemented when supplied |
| Criticality differentiation | `_criticality_weights` | Implemented when supplied |
| Repair/return credit | `repair_return_credit` | Implemented when supplied |
| Substitution | `apply_substitution` | Implemented when supplied |
| Surge configuration | `_surge_parameters` | Implemented when supplied |
| Monte Carlo risk simulation | `run_risk_simulation` | Implemented when supplied |
| Offline replay | `run_offline_replay` | Implemented when supplied |
| Governance guardrail and audit | `apply_guardrail`, `NodePolicy`, `AuditRecord` | Implemented |

## Boundary

The repository is a controlled decision-support implementation. Optional scenario behavior depends on explicit caller-supplied inputs. It does not claim production deployment, external adoption, or outcomes beyond the executable behavior and retained validation evidence in this repository.
