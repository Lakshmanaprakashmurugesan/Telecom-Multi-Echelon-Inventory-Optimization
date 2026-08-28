# Telecom Multi-Echelon Inventory Optimization (MEIO)

### Reproducible · Network-Aware · Constraint-Driven · Auditable

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
![Validation](https://img.shields.io/badge/validation-12%2F12%20tests%20passing-brightgreen)
![Optimization](https://img.shields.io/badge/optimization-primal%20simplex-blueviolet)
![Input](https://img.shields.io/badge/interface-Excel-217346)
![Deployment](https://img.shields.io/badge/deployment-AWS-orange)

A reproducible, network-aware **Multi-Echelon Inventory Optimization (MEIO)** implementation for telecommunications supply-chain planning.

The repository demonstrates an executable workflow that transforms caller-supplied demand, inventory, service-level, network, supply, capacity, cost, budget, and governance conditions into structured inventory-policy recommendations through deterministic calculations and constrained optimization.

### 🌐 Live Application

**[Launch the Hosted MEIO Application →](https://staging.d1jrsof4a5v813.amplifyapp.com/)**

> Use the included `MEIO_Input_Test.xlsx` workbook to execute the controlled demonstration.

> **Scope boundary:** This is a controlled decision-support implementation. It generates non-binding inventory recommendations and does not autonomously execute ERP, WMS, OMS, procurement, carrier, or other operational transactions.

---

## Overview

Inventory planning across a telecommunications supply network requires more than evaluating individual stocking locations independently.

An upstream supply limitation can affect multiple downstream locations. Capacity at one node can restrict replenishment. Budget constraints can change feasible allocations. Service-level requirements influence safety stock and reorder points. Network topology determines how inventory at related locations contributes to the broader inventory position.

This repository implements these relationships in an inspectable and reproducible MEIO workflow.

```text
Caller-Supplied Operating Conditions
                │
                ▼
        Input Validation
                │
                ▼
       Network Topology
                │
                ▼
      Inventory Position
                │
                ▼
       Echelon Inventory
                │
                ▼
     Service-Level Factor
                │
                ▼
         Safety Stock
                │
                ▼
        Reorder Point
                │
                ▼
  Replenishment Requirement
                │
                ▼
Supply · Budget · Capacity Constraints
                │
                ▼
 Constrained Network Allocation
                │
                ▼
    Governance Guardrails
                │
                ▼
 Versioned Policy + Audit Record
```

The core implementation is contained in:

```text
lambda_function.py
```

---

## Why Multi-Echelon?

A single-location inventory calculation does not capture the relationships between upstream and downstream inventory nodes.

This implementation models those relationships explicitly through a validated network topology. Effective inventory at downstream nodes contributes to echelon inventory, while replenishment decisions are evaluated against shared operating constraints.

The resulting workflow connects:

**inventory state → network structure → service requirement → replenishment need → constrained allocation → governed policy**

rather than treating each calculation as an isolated output.

---

## Implemented Technical Workflow

### 1. Input and Record Validation

The engine accepts structured caller-supplied inventory and operating conditions and validates required fields, numerical bounds, service-level targets, criticality classes, and prior-policy consistency before optimization begins.

Primary implementation:

```text
MEIORecord
parse_records
validate_record
```

### 2. Inventory Position

The engine calculates local inventory position from on-hand, on-order, and in-transit inventory.

Where explicitly supplied for repairable inventory, caller-provided return quantity and repair yield can contribute a repair/return credit to the effective inventory position.

Primary implementation:

```text
local_inventory_position
repair_return_credit
effective_inventory_position
```

### 3. Multi-Echelon Network Evaluation

Caller-supplied topology defines relationships between inventory nodes.

The implementation normalizes the network, validates its structure, rejects cycles, traverses downstream nodes, and calculates echelon inventory using the effective inventory positions of related locations.

Primary implementation:

```text
validate_topology
descendants
roots
echelon_inventory
```

### 4. Service-Level Inventory Policy

The engine converts caller-supplied service-level targets into statistical service factors and uses demand variability and lead-time information to calculate safety stock.

Reorder points combine expected lead-time demand with the calculated safety stock.

Primary implementation:

```text
service_level_factor
safety_stock
reorder_point
```

### 5. Constrained Network Allocation

When calculated replenishment requirements exceed available operating resources, the implementation performs constrained allocation rather than assuming every requirement can be fulfilled.

A dependency-free primal simplex implementation evaluates allocation subject to the supplied network constraints.

Primary implementation:

```text
simplex_maximize
optimize_eq4
```

The allocation workflow supports:

| Constraint | Status |
|---|---|
| Available upstream supply | **Implemented** |
| Regional budget | **Implemented** |
| Node capacity | **Implemented** |
| Network topology | **Implemented** |
| Edge-flow capacity | **Implemented when supplied** |
| Caller-supplied criticality weights | **Implemented when supplied** |

This produces an allocation that remains bounded by the operating conditions supplied for that execution.

### 6. Governance and Policy Traceability

Generated recommendations can be evaluated against prior policy values and caller-supplied change thresholds.

Where a proposed policy change exceeds the configured threshold, the governance logic can preserve prior values unless the required approval condition is satisfied.

The implementation also generates policy-version identifiers, approval metadata, rollback references, and structured audit records.

Primary implementation:

```text
apply_guardrail
NodePolicy
AuditRecord
build_for_sku
```

---

## Optional Scenario Capabilities

The backend contains additional mechanisms that are activated only when their required configuration is explicitly supplied.

These include repair/return credit, edge-flow capacity, caller-defined criticality priority weights, substitution, surge configuration, seeded Monte Carlo risk simulation, and offline replay against supplied observations.

These capabilities are not represented as universally active features. Their behavior depends on the corresponding caller-supplied inputs.

| Capability | Implementation |
|---|---|
| Repair / return credit | `repair_return_credit` |
| Edge-flow constraints | `parse_edge_capacities`, `_edge_subtree_constraints` |
| Criticality weighting | `_criticality_weights` |
| Substitution | `apply_substitution` |
| Surge configuration | `_surge_parameters` |
| Seeded risk simulation | `run_risk_simulation` |
| Offline replay | `run_offline_replay` |

---

## System Architecture

```text
┌──────────────────────────────┐
│     MEIO_Input_Test.xlsx     │
│                              │
│ Controlled demonstration     │
│ inventory-network inputs     │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│      AWS Amplify UI          │
│         index.html           │
│                              │
│ Workbook validation          │
│ Input extraction             │
│ Request construction         │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│     Amazon API Gateway       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│         AWS Lambda           │
│     lambda_function.py       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│         MEIO Engine          │
│                              │
│ Inventory Position           │
│        ↓                     │
│ Echelon Inventory            │
│        ↓                     │
│ Safety Stock                 │
│        ↓                     │
│ Reorder Point                │
│        ↓                     │
│ Constrained Allocation       │
│        ↓                     │
│ Governance + Audit           │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│    Structured MEIO Output    │
│                              │
│ Inventory Policies           │
│ Optimization Summary         │
│ Remaining Shortage           │
│ Governance Status            │
│ Versioned Audit Records      │
└──────────────────────────────┘
```

---

## Hosted Application

The MEIO browser interface is deployed through AWS Amplify and connected to the API-based optimization workflow.

### **[Open the Live MEIO Application →](https://staging.d1jrsof4a5v813.amplifyapp.com/)**

The browser interface provides an **Excel-first** execution workflow:

```text
Upload Workbook
      ↓
Validate Workbook
      ↓
Construct MEIO Request
      ↓
Invoke API Gateway
      ↓
Execute Lambda
      ↓
Run MEIO Engine
      ↓
Display Policy Results
```

The generated API request is maintained internally by the browser interface. Users do not need to manually construct or edit JSON.

### Controlled Demonstration

Use the included workbook:

```text
MEIO_Input_Test.xlsx
```

Then:

1. Open the hosted application.
2. Select **Choose File**.
3. Upload `MEIO_Input_Test.xlsx`.
4. Confirm successful workbook loading.
5. Select **Run MEIO Optimization**.
6. Review the resulting policy and optimization output.

The included workbook contains controlled synthetic/non-proprietary demonstration inputs.

---

## Excel Input Model

The workbook contains five worksheets:

| Worksheet | Purpose |
|---|---|
| `Records` | Node-level demand, inventory, service-level, capacity and cost inputs |
| `Topology` | Inventory-network relationships |
| `SKU_Config` | Available supply and regional budget configuration |
| `Run_Config` | Execution and governance parameters |
| `Instructions` | Workbook guidance |

The browser implementation converts the execution worksheets into the request structure expected by the backend.

Primary frontend implementation:

```text
workbookToMeioPayload
buildRecords
buildTopology
buildSkuConfig
buildRunConfig
```

Not every optional backend capability is exposed through the controlled Excel workbook. Additional functionality can be exercised through the backend request contract when its required configuration is supplied.

---

## Structured Policy Output

A successful execution returns a structured policy response rather than a fixed or predetermined recommendation.

The response connects the supplied operating conditions to calculated inventory requirements, applied constraints, network allocation, remaining shortages, governance decisions, policy versions, and audit information.

```text
Supplied Conditions
        │
        ▼
Calculated Requirements
        │
        ▼
Applied Constraints
        │
        ▼
Allocation Decision
        │
        ▼
Remaining Shortage
        │
        ▼
Governance Evaluation
        │
        ▼
Versioned Policy
        │
        ▼
Structured Audit Record
```

This structure makes the result traceable from input conditions through calculation and optimization to the final decision-support output.

---

## Repository Structure

```text
.
├── lambda_function.py
│   └── Core MEIO engine and Lambda-compatible handler
│
├── index.html
│   └── AWS Amplify browser interface
│
├── MEIO_Input_Test.xlsx
│   └── Controlled demonstration workbook
│
├── tests/
│   └── test_meio_engine.py
│
├── tools/
│   └── verify_api.py
│
├── evidence/
│   ├── README.md
│   ├── ENVIRONMENT.txt
│   ├── SHA256SUMS.txt
│   ├── backend_smoke_test_console.txt
│   ├── pytest_console_output.txt
│   ├── pytest_results.xml
│   ├── validation_summary.json
│   ├── baseline/
│   └── scenarios/
│
├── docs/
│   ├── ARCHITECTURE_TO_CODE.md
│   ├── TECHNICAL_SCOPE.md
│   ├── REPRODUCIBILITY.md
│   ├── VALIDATION.md
│   ├── HOSTED_DEPLOYMENT.md
│   ├── DEPLOYMENT_NOTES.md
│   ├── SOURCE_PRESERVATION.md
│   └── PUBLICATION_CHECKLIST.md
│
├── deploy/
│   └── MEIO-Amplify-Deploy.zip
│
├── requirements-dev.txt
├── .gitignore
├── .gitattributes
└── README.md
```

---

## Quick Start

### Requirements

- Python 3.9+
- Python standard library for the core MEIO engine
- `pytest` for automated validation

Install the development dependency:

```bash
python -m pip install -r requirements-dev.txt
```

### Run the Engine

```bash
python lambda_function.py
```

A successful controlled execution returns:

```json
{
  "message": "MEIO optimization completed"
}
```

### Run Automated Validation

```bash
python -m pytest -v
```

Current validated repository result:

```text
12 passed
```

---

## Automated Validation

The included automated test suite verifies core calculations, network behavior, constrained optimization, governance behavior, request validation, and optional controlled scenarios.

| Validation Area | Result |
|---|:---:|
| Service-level factor and core equations | ✓ |
| Echelon inventory | ✓ |
| Caller-supplied repair/return credit | ✓ |
| Topology-cycle rejection | ✓ |
| Governance guardrail | ✓ |
| Baseline constrained allocation | ✓ |
| Node-capacity enforcement | ✓ |
| Edge-flow capacity | ✓ |
| Invalid service-level rejection | ✓ |
| Missing required-field handling | ✓ |
| Seeded risk-simulation reproducibility | ✓ |
| Offline replay | ✓ |

**Repository validation result: 12/12 tests passing.**

Detailed validation documentation:

```text
docs/VALIDATION.md
```

---

## Controlled Scenario Validation

The repository retains reproducible request/response evidence for multiple controlled operating conditions.

| Scenario | Demonstrated Behavior |
|---|---|
| Baseline | Complete MEIO workflow and structured policy generation |
| Supply constraint | Allocation bounded by limited upstream supply |
| Budget constraint | Allocation bounded by caller-supplied regional budget |
| Edge-flow constraint | Network allocation subject to supplied flow capacity |
| Governance guardrail | Material policy change produces approval-required behavior |
| Risk model | Seeded Monte Carlo simulation with reproducible configuration |
| Offline replay | Generated policies evaluated against supplied observations |

The retained validation summary records the results of the controlled scenarios and preserves the relevant scenario-specific outputs.

---

## Evidence of Implementation

The repository contains executable source code together with controlled inputs, automated validation, and retained execution artifacts so that implementation behavior can be independently inspected.

| Evidence | What It Demonstrates |
|---|---|
| `lambda_function.py` | Executable MEIO calculation and optimization implementation |
| `MEIO_Input_Test.xlsx` | Controlled reproducible input |
| `tests/test_meio_engine.py` | Automated behavioral validation |
| `backend_smoke_test_console.txt` | Recorded direct backend execution |
| `pytest_console_output.txt` | Recorded automated test execution |
| `pytest_results.xml` | Machine-readable validation results |
| `validation_summary.json` | Structured controlled-scenario results |
| `baseline/` | Baseline request/response evidence |
| `scenarios/` | Constraint and optional-capability evidence |
| `ENVIRONMENT.txt` | Execution-environment record |
| `SHA256SUMS.txt` | File-integrity information |

These artifacts document behavior of the included controlled implementation.

They do not establish production carrier deployment, external adoption, proprietary-data use, nationwide operational results, or measured real-world economic outcomes.

---

## Architecture-to-Code Traceability

The repository is structured so that significant technical capabilities can be traced directly to executable implementation and validation evidence.

Detailed mapping is available in:

```text
docs/ARCHITECTURE_TO_CODE.md
```

Examples:

| Technical Component | Source Implementation | Verification |
|---|---|---|
| Inventory position | `local_inventory_position` | Core-equation test |
| Repair/return credit | `repair_return_credit` | Repair-credit test |
| Safety stock | `safety_stock` | Core-equation test + baseline |
| Reorder point | `reorder_point` | Core-equation test + baseline |
| Topology validation | `validate_topology` | Cycle-rejection test |
| Echelon inventory | `echelon_inventory` | Echelon-inventory test |
| Allocation optimizer | `simplex_maximize`, `optimize_eq4` | Baseline + constraint scenarios |
| Edge-flow constraint | `_edge_subtree_constraints` | Edge-flow scenario |
| Governance | `apply_guardrail` | Guardrail test + scenario |
| Risk simulation | `run_risk_simulation` | Seeded reproducibility test |
| Offline replay | `run_offline_replay` | Replay test + scenario |
| Policy and audit generation | `NodePolicy`, `AuditRecord`, `build_for_sku` | Structured responses |

The intended technical review path is:

```text
Technical Capability
        ↓
Actual Source
        ↓
Controlled Input
        ↓
Execution
        ↓
Observed Output
        ↓
Automated Validation
        ↓
Retained Evidence
```

---

## Reproducibility

The primary local verification workflow requires only:

```bash
python -m pip install -r requirements-dev.txt
python lambda_function.py
python -m pytest -v
```

A reviewer can then compare the resulting behavior with the retained evidence in:

```text
evidence/
```

Additional instructions are provided in:

```text
docs/REPRODUCIBILITY.md
```

Integrity hashes are maintained in:

```text
evidence/SHA256SUMS.txt
```

---

## Reusable Technical Design

The MEIO calculation logic is separated from the operating conditions supplied for an individual execution.

Demand, variability, inventory, topology, service targets, available supply, capacity, budget, cost, and governance parameters are provided as caller-supplied inputs rather than embedded as fixed policy outcomes.

Accordingly, the same technical workflow can be exercised against different controlled:

```text
Network Structures
Demand Conditions
Inventory Positions
Service-Level Targets
Supply Availability
Capacity Constraints
Budget Constraints
Cost Conditions
Governance Parameters
```

without redesigning the underlying MEIO calculation and optimization workflow.

This separation between **operating inputs** and **reusable calculation logic** supports reproducible evaluation of different inventory-network scenarios.

---

## Remote API Verification

The hosted API integration can be independently checked using:

```bash
python tools/verify_api.py
```

The utility verifies:

```text
CORS Preflight
      ↓
API Connectivity
      ↓
POST Request
      ↓
Lambda Execution
      ↓
Structured MEIO Response
```

The verification utility does not alter the MEIO calculation implementation.

---

## Technical Scope

This repository implements a controlled **multi-echelon inventory optimization and inventory-policy decision-support workflow for telecommunications supply-chain planning**.

Its implemented scope includes network topology, echelon inventory, service-level-based inventory calculations, constrained allocation, supply/budget/capacity controls, optional caller-configured scenario mechanisms, governance guardrails, policy versioning, and structured audit generation.

The implementation is designed around a reusable input-driven workflow: operating conditions are supplied by the caller while the underlying calculation and optimization logic remains unchanged. This permits the same technical workflow to be exercised across different inventory networks, demand conditions, service-level requirements, supply constraints, capacity limits, budget conditions, cost structures, and governance configurations.

The repository can therefore be evaluated through a direct technical chain:

> **Executable Source → Controlled Inputs → Reproducible Execution → Structured Outputs → Automated Validation → Retained Evidence**

### Boundaries

The repository does not claim:

- autonomous operational transaction execution;
- direct production ERP/WMS/OMS integration;
- production carrier or OEM deployment;
- external adoption established by this repository;
- proprietary carrier data in the included demonstration;
- nationwide operational results;
- measured production economic outcomes.

Optional behavior depends on explicit caller-supplied configuration and should not be interpreted as universally active functionality.

---

## Independent Technical Review Path

A reviewer does not need to rely solely on the README to evaluate the implementation.

### 1. Inspect the core implementation

```text
lambda_function.py
```

### 2. Review architecture-to-code traceability

```text
docs/ARCHITECTURE_TO_CODE.md
```

### 3. Execute the backend

```bash
python lambda_function.py
```

### 4. Execute automated validation

```bash
python -m pytest -v
```

### 5. Review retained execution evidence

```text
evidence/
```

### 6. Review reproducibility documentation

```text
docs/REPRODUCIBILITY.md
```

### 7. Exercise the hosted workflow

**[Launch the Hosted MEIO Application →](https://staging.d1jrsof4a5v813.amplifyapp.com/)**

This provides a direct path from documented technical capability to source implementation, controlled execution, automated validation, and retained evidence.

---

## Documentation

| Document | Purpose |
|---|---|
| [`ARCHITECTURE_TO_CODE.md`](docs/ARCHITECTURE_TO_CODE.md) | Maps technical components to source and evidence |
| [`TECHNICAL_SCOPE.md`](docs/TECHNICAL_SCOPE.md) | Defines implemented scope and boundaries |
| [`REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) | Provides reproduction instructions |
| [`VALIDATION.md`](docs/VALIDATION.md) | Documents validation coverage |
| [`HOSTED_DEPLOYMENT.md`](docs/HOSTED_DEPLOYMENT.md) | Documents frontend deployment |
| [`DEPLOYMENT_NOTES.md`](docs/DEPLOYMENT_NOTES.md) | Records deployment considerations |
| [`SOURCE_PRESERVATION.md`](docs/SOURCE_PRESERVATION.md) | Documents source preservation |
| [`PUBLICATION_CHECKLIST.md`](docs/PUBLICATION_CHECKLIST.md) | Provides publication checks |

---

## Source Integrity

Repository integrity information is retained in:

```text
evidence/SHA256SUMS.txt
```

Together with the source, controlled inputs, tests, execution records, and architecture mapping, these materials allow the repository's technical behavior to be independently inspected and reproduced.

---

# Run the Demonstration

## Hosted Application

### **[Launch Telecom MEIO →](https://staging.d1jrsof4a5v813.amplifyapp.com/)**

Upload:

```text
MEIO_Input_Test.xlsx
```

and select:

```text
Run MEIO Optimization
```

## Local Verification

```bash
python lambda_function.py
python -m pytest -v
```

Expected validation result:

```text
12 passed
```

---

## Engineering Review Path

### **Problem → Method → Source Code → Controlled Input → Execution → Output → Validation → Evidence**

---

**Telecom Multi-Echelon Inventory Optimization (MEIO)**  
*Network-Aware · Constraint-Driven · Reproducible · Auditable*