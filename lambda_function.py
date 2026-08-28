"""Pure-Python AWS Lambda reference implementation for multi-echelon inventory optimization (MEIO).

Scope and evidence boundary
---------------------------
This file is a controlled reference implementation of the executable mechanisms
implemented in this repository as a Multi-Echelon Inventory Optimization (MEIO)
Framework for U.S. Telecommunications Supply Chain Resilience." It uses only
Python's standard library: no NumPy, SciPy, pandas, or other third-party package.

The implementation covers:
* Equation (1): echelon inventory.
* Equation (2): service-level safety stock.
* Equation (3): reorder point.
* Equation (4): constrained holding-cost / shortage-penalty allocation.
* Standardized, carrier-neutral input schema and governed policy output.
* Multi-echelon topology validation and optional edge-flow capacities.
* Node capacity, available-supply, and regional-budget constraints.
* ABC-XYZ / Criticality_Class validation and configurable criticality priority.
* Repair/return loop credits when caller supplies optional return parameters.
* Substitution compatibility when caller supplies optional substitution rules.
* Disaster/risk staging when caller supplies explicit risk/surge parameters.
* Monte Carlo resilience stress testing using the standard-library random module.
* Guardrails, versioning, rollback references, and audit records.
* Optional offline replay / validation helpers using caller-supplied observations.

Important boundary
------------------
This reference implementation is not a complete commercial specification.
Some concepts (e.g., exact ABC-XYZ numeric weights, repair yield assumptions,
substitution conversion rates, edge capacities, disaster-surge multipliers, and
risk-event probabilities) are not hard-coded by the implementation. This
implementation therefore NEVER invents those business values. They are optional
caller-supplied configuration. If they are omitted, the core equations
and constraints still run.

No ERP/WMS/OMS/procurement or carrier operational transaction is executed.
The function returns decision-support policy recommendations only.
"""

from __future__ import annotations

import base64
import json
import math
import random
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from statistics import NormalDist
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

EPS = 1e-9
ALLOWED_CRITICALITY = {"AX", "AY", "BZ", "CZ"}


# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------

@dataclass
class MEIORecord:
    # Minimum implementable interface fields
    SKU_ID: str
    Node_ID: str
    Calendar_Week: str
    Demand_Qty: float
    Demand_Mean: float
    Demand_Variance: float
    LeadTime_Days: float
    LeadTime_StdDev: float
    OnHand_Qty: float
    OnOrder_Qty: float
    InTransit_Qty: float
    UnitCost: float
    Criticality_Class: str
    Capacity_Units: float
    ServiceLevel_Target: float
    Repairable_Flag: bool
    Substitution_Group_ID: str
    RiskRegion: str

    # Eq. (4) needs cost coefficients. These are implementation inputs rather
    # than hard-coded numerical assumptions.
    HoldingCost_PerUnit: float = 0.0
    ShortagePenalty_PerUnit: float = 1.0

    # Optional governance history.
    Prior_SafetyStock: Optional[float] = None
    Prior_ReorderPoint: Optional[float] = None
    Prior_PolicyVersionID: Optional[str] = None

    # Optional reverse-logistics extension for repair/return loops.
    Return_Qty: float = 0.0
    RepairYield: float = 0.0


@dataclass
class NodePolicy:
    SKU_ID: str
    Node_ID: str
    PolicyVersionID: str
    EchelonInventory: float
    LocalInventoryPosition: float
    RepairReturnCredit: float
    EffectiveInventoryPosition: float
    ServiceLevel_Assigned: float
    ServiceLevelFactor_Z: float
    SafetyStock_Proposed: float
    ReorderPoint_Proposed: float
    SafetyStock_Target: float
    ReorderPoint: float
    OrderUpToLevel: Optional[float]
    RecommendedAllocation: float
    SubstitutionAllocation: float
    TotalRecommendedSupply: float
    RemainingShortage: float
    AllocationRule_UnderShortage: str
    Criticality_Class: str
    RiskRegion: str
    TriggerType: str
    ApproverRole: str
    GuardrailStatus: str
    EffectiveDate: str
    ExpirationDate: Optional[str]
    RollbackRef: Optional[str]


@dataclass
class AuditRecord:
    PolicyVersionID: str
    SKU_ID: str
    Node_ID: str
    Prior_SS: Optional[float]
    New_SS: float
    Prior_R: Optional[float]
    New_R: float
    TriggerType: str
    DataVersionRef: str
    ApproverRole: str
    ApprovalTimestamp: Optional[str]
    EffectiveDate: str
    RollbackRef: Optional[str]
    GuardrailStatus: str


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------

def _response(status_code: int, payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, default=str),
    }


def _payload_from_event(event: Any) -> Dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object.")

    if "body" not in event:
        return event

    body = event.get("body")
    if body in (None, ""):
        raise ValueError("API request body is required.")

    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

    if isinstance(body, str):
        body = json.loads(body)

    if not isinstance(body, dict):
        raise ValueError("API request body must decode to a JSON object.")

    return body


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def _num(value: Any, name: str, minimum: Optional[float] = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric.")
    n = float(value)
    if not math.isfinite(n):
        raise ValueError(f"{name} must be finite.")
    if minimum is not None and n < minimum:
        raise ValueError(f"{name} must be >= {minimum}.")
    return n


def _optional_num(value: Any, name: str, minimum: Optional[float] = None) -> Optional[float]:
    if value is None:
        return None
    return _num(value, name, minimum)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _round(value: float, digits: int = 6) -> float:
    if abs(value) < 10 ** (-(digits + 1)):
        return 0.0
    return round(float(value), digits)


# -----------------------------------------------------------------------------
# Input validation
# -----------------------------------------------------------------------------

def validate_record(r: MEIORecord) -> None:
    _text(r.SKU_ID, "SKU_ID")
    _text(r.Node_ID, "Node_ID")
    _text(r.Calendar_Week, "Calendar_Week")
    _text(r.Substitution_Group_ID, "Substitution_Group_ID")
    _text(r.RiskRegion, "RiskRegion")

    r.Criticality_Class = _text(r.Criticality_Class, "Criticality_Class").upper()
    if r.Criticality_Class not in ALLOWED_CRITICALITY:
        raise ValueError(
            f"Criticality_Class must be one of {sorted(ALLOWED_CRITICALITY)}; "
            f"received {r.Criticality_Class}."
        )

    for name in (
        "Demand_Qty",
        "Demand_Mean",
        "Demand_Variance",
        "LeadTime_Days",
        "LeadTime_StdDev",
        "OnHand_Qty",
        "OnOrder_Qty",
        "InTransit_Qty",
        "UnitCost",
        "Capacity_Units",
        "HoldingCost_PerUnit",
        "ShortagePenalty_PerUnit",
        "Return_Qty",
        "RepairYield",
    ):
        _num(getattr(r, name), name, 0.0)

    if r.RepairYield > 1.0:
        raise ValueError("RepairYield must be between 0.0 and 1.0.")

    _num(r.ServiceLevel_Target, "ServiceLevel_Target")
    service_level_factor(r.ServiceLevel_Target)

    _optional_num(r.Prior_SafetyStock, "Prior_SafetyStock", 0.0)
    _optional_num(r.Prior_ReorderPoint, "Prior_ReorderPoint", 0.0)

    if (r.Prior_SafetyStock is not None or r.Prior_ReorderPoint is not None) and not r.Prior_PolicyVersionID:
        raise ValueError(
            f"Prior_PolicyVersionID is required when prior policy values are supplied "
            f"for {r.SKU_ID}/{r.Node_ID}."
        )

    if local_inventory_position(r) > r.Capacity_Units + EPS:
        raise ValueError(
            f"Projected local inventory position exceeds Capacity_Units for {r.SKU_ID}/{r.Node_ID}."
        )


def parse_records(raw: Any) -> List[MEIORecord]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("records must be a non-empty JSON array.")

    result: List[MEIORecord] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"records[{idx}] must be a JSON object.")
        try:
            r = MEIORecord(**item)
        except TypeError as exc:
            raise ValueError(f"Invalid fields in records[{idx}]: {exc}") from exc
        validate_record(r)
        result.append(r)
    return result


# -----------------------------------------------------------------------------
# Equation (1), (2), (3)
# -----------------------------------------------------------------------------

def local_inventory_position(r: MEIORecord) -> float:
    """On hand + on order + in transit."""
    return r.OnHand_Qty + r.OnOrder_Qty + r.InTransit_Qty


def repair_return_credit(r: MEIORecord) -> float:
    """Optional reverse-logistics credit supplied by caller."""
    if not r.Repairable_Flag:
        return 0.0
    return r.Return_Qty * r.RepairYield


def effective_inventory_position(r: MEIORecord) -> float:
    return local_inventory_position(r) + repair_return_credit(r)


def service_level_factor(service_level_target: float) -> float:
    if not 0.50 < service_level_target < 1.0:
        raise ValueError("ServiceLevel_Target must be greater than 0.50 and less than 1.00.")
    return NormalDist().inv_cdf(service_level_target)


def safety_stock(r: MEIORecord, demand_variance_multiplier: float = 1.0, lead_time_multiplier: float = 1.0) -> float:
    """Equation (2): SS_i = z_i * sigma_i * sqrt(L_i).

    Risk/stress multipliers are caller-supplied and default to 1.0, preserving
    the exact equation for an ordinary run.
    """
    variance = max(0.0, r.Demand_Variance * demand_variance_multiplier)
    lead_time = max(0.0, r.LeadTime_Days * lead_time_multiplier)
    sigma = math.sqrt(variance)
    z = service_level_factor(r.ServiceLevel_Target)
    return z * sigma * math.sqrt(lead_time)


def reorder_point(r: MEIORecord, ss: float, demand_mean_multiplier: float = 1.0, lead_time_multiplier: float = 1.0) -> float:
    """Equation (3): R_i = mu_i * L_i + SS_i."""
    mu = r.Demand_Mean * demand_mean_multiplier
    lead = r.LeadTime_Days * lead_time_multiplier
    return mu * lead + ss


# -----------------------------------------------------------------------------
# Topology and Eq. (1) echelon inventory
# -----------------------------------------------------------------------------

def validate_topology(topology: Any) -> Dict[str, List[str]]:
    if not isinstance(topology, dict):
        raise ValueError("topology must be a JSON object mapping parent nodes to child-node arrays.")

    clean: Dict[str, List[str]] = {}
    for parent, children in topology.items():
        p = _text(parent, "topology parent node")
        if not isinstance(children, list):
            raise ValueError(f"topology[{p}] must be an array.")
        clean[p] = []
        for child in children:
            clean[p].append(_text(child, f"topology[{p}] child node"))

    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> None:
        if node in visiting:
            raise ValueError(f"topology contains a cycle involving {node}.")
        if node in visited:
            return
        visiting.add(node)
        for child in clean.get(node, []):
            dfs(child)
        visiting.remove(node)
        visited.add(node)

    nodes = set(clean)
    for children in clean.values():
        nodes.update(children)
    for node in nodes:
        dfs(node)
        clean.setdefault(node, [])

    return clean


def descendants(node_id: str, topology: Mapping[str, Sequence[str]]) -> List[str]:
    out: List[str] = []
    stack = list(topology.get(node_id, []))
    seen: set[str] = set()
    while stack:
        child = stack.pop()
        if child in seen:
            continue
        seen.add(child)
        out.append(child)
        stack.extend(topology.get(child, []))
    return out


def roots(topology: Mapping[str, Sequence[str]]) -> List[str]:
    children = {child for items in topology.values() for child in items}
    return [node for node in topology if node not in children]


def echelon_inventory(r: MEIORecord, by_node: Mapping[str, MEIORecord], topology: Mapping[str, Sequence[str]]) -> float:
    """Equation (1): E_i = I_i + sum downstream I_j."""
    total = effective_inventory_position(r)
    for node in descendants(r.Node_ID, topology):
        child_record = by_node.get(node)
        if child_record is not None:
            total += effective_inventory_position(child_record)
    return total


# -----------------------------------------------------------------------------
# Caller-supplied concepts: criticality, risk/surge, flow capacities
# -----------------------------------------------------------------------------

def _criticality_weights(payload: Mapping[str, Any]) -> Dict[str, float]:
    """Return caller-supplied priority multipliers; default 1.0 means neutral.

    The implementation supports differentiated policies by class but does not define a
    numeric multiplier. We therefore do not invent one.
    """
    raw = payload.get("criticality_priority_weights") or {}
    if not isinstance(raw, dict):
        raise ValueError("criticality_priority_weights must be a JSON object.")
    out = {klass: 1.0 for klass in ALLOWED_CRITICALITY}
    for klass, value in raw.items():
        k = _text(klass, "criticality class weight key").upper()
        if k not in ALLOWED_CRITICALITY:
            raise ValueError(f"Unknown criticality class in weights: {k}")
        out[k] = _num(value, f"criticality_priority_weights[{k}]", 0.0)
    return out


def _surge_parameters(payload: Mapping[str, Any], r: MEIORecord) -> Tuple[float, float, float]:
    """Return (mean_mult, variance_mult, lead_time_mult) from explicit caller config."""
    config = payload.get("surge_config") or {}
    if not isinstance(config, dict):
        raise ValueError("surge_config must be a JSON object.")

    region_cfg = config.get(r.RiskRegion) or config.get("*") or {}
    if not isinstance(region_cfg, dict):
        raise ValueError(f"surge_config[{r.RiskRegion}] must be a JSON object.")

    return (
        _num(region_cfg.get("demand_mean_multiplier", 1.0), "demand_mean_multiplier", 0.0),
        _num(region_cfg.get("demand_variance_multiplier", 1.0), "demand_variance_multiplier", 0.0),
        _num(region_cfg.get("lead_time_multiplier", 1.0), "lead_time_multiplier", 0.0),
    )


def parse_edge_capacities(payload: Mapping[str, Any]) -> Dict[Tuple[str, str], float]:
    raw = payload.get("edge_capacities") or {}
    if not isinstance(raw, dict):
        raise ValueError("edge_capacities must be a JSON object.")
    out: Dict[Tuple[str, str], float] = {}
    for key, value in raw.items():
        if "->" not in str(key):
            raise ValueError("edge_capacities keys must use 'PARENT->CHILD' format.")
        parent, child = [part.strip() for part in str(key).split("->", 1)]
        out[(parent, child)] = _num(value, f"edge_capacities[{key}]", 0.0)
    return out


# -----------------------------------------------------------------------------
# Governance guardrail
# -----------------------------------------------------------------------------

def _pct_change(new: float, prior: Optional[float]) -> Optional[float]:
    if prior is None:
        return None
    if abs(prior) < EPS:
        return math.inf if abs(new) > EPS else 0.0
    return (new - prior) / prior


def apply_guardrail(
    proposed_ss: float,
    proposed_rop: float,
    prior_ss: Optional[float],
    prior_rop: Optional[float],
    max_change_pct: float,
    normal_role: str,
    exception_role: str,
) -> Tuple[float, float, str, str]:
    changes = [
        c
        for c in (_pct_change(proposed_ss, prior_ss), _pct_change(proposed_rop, prior_rop))
        if c is not None
    ]
    if not changes:
        return proposed_ss, proposed_rop, "NO_PRIOR_POLICY", normal_role
    if any(abs(c) > max_change_pct for c in changes):
        ss = prior_ss if prior_ss is not None else proposed_ss
        rop = prior_rop if prior_rop is not None else proposed_rop
        return ss, rop, "APPROVAL_REQUIRED", exception_role
    return proposed_ss, proposed_rop, "WITHIN_GUARDRAIL", normal_role


# -----------------------------------------------------------------------------
# Pure-Python simplex for Eq. (4)
# -----------------------------------------------------------------------------

def simplex_maximize(objective: Sequence[float], a_ub: Sequence[Sequence[float]], b_ub: Sequence[float]) -> Tuple[List[float], float, int]:
    """Primal simplex for max c*x, Ax<=b, x>=0, where b>=0.

    This is intentionally small and dependency-free for the controlled prototype.
    """
    n = len(objective)
    m = len(a_ub)
    if m != len(b_ub):
        raise ValueError("Optimizer constraint count mismatch.")
    if any(len(row) != n for row in a_ub):
        raise ValueError("Optimizer constraint width mismatch.")
    if any(rhs < -EPS for rhs in b_ub):
        raise ValueError("Optimizer requires non-negative right-hand-side limits.")

    width = n + m + 1
    tableau: List[List[float]] = []
    basis: List[int] = []

    for i in range(m):
        row = [float(v) for v in a_ub[i]] + [0.0] * m + [float(b_ub[i])]
        row[n + i] = 1.0
        tableau.append(row)
        basis.append(n + i)

    tableau.append([-float(v) for v in objective] + [0.0] * m + [0.0])

    iterations = 0
    while True:
        iterations += 1
        if iterations > 20000:
            raise RuntimeError("MEIO optimizer iteration limit exceeded.")

        obj = tableau[-1]
        entering = next((j for j in range(n + m) if obj[j] < -EPS), None)
        if entering is None:
            break

        candidates: List[Tuple[float, int, int]] = []
        for i in range(m):
            coeff = tableau[i][entering]
            if coeff > EPS:
                candidates.append((tableau[i][-1] / coeff, basis[i], i))
        if not candidates:
            raise RuntimeError("MEIO optimization is unbounded.")

        _, _, leaving = min(candidates)
        pivot = tableau[leaving][entering]
        tableau[leaving] = [v / pivot for v in tableau[leaving]]

        for i in range(m + 1):
            if i == leaving:
                continue
            factor = tableau[i][entering]
            if abs(factor) <= EPS:
                continue
            tableau[i] = [tableau[i][j] - factor * tableau[leaving][j] for j in range(width)]

        basis[leaving] = entering

    solution = [0.0] * n
    for i, var in enumerate(basis):
        if var < n:
            solution[var] = max(0.0, tableau[i][-1])
    optimum = max(0.0, tableau[-1][-1])
    return solution, optimum, iterations


def _edge_subtree_constraints(
    records: Sequence[MEIORecord],
    topology: Mapping[str, Sequence[str]],
    edge_caps: Mapping[Tuple[str, str], float],
) -> List[Tuple[List[float], float, str]]:
    """Optional flow constraints: allocations into a child's subtree <= edge capacity."""
    if not edge_caps:
        return []
    node_index = {r.Node_ID: i for i, r in enumerate(records)}
    constraints: List[Tuple[List[float], float, str]] = []
    for (parent, child), cap in edge_caps.items():
        if child not in topology:
            # topology validation already creates leaf entries, so this indicates an unknown edge.
            raise ValueError(f"edge_capacities references unknown child node {child}.")
        subtree = {child, *descendants(child, topology)}
        row = [0.0] * len(records)
        for node in subtree:
            if node in node_index:
                row[node_index[node]] = 1.0
        constraints.append((row, cap, f"{parent}->{child}"))
    return constraints


def optimize_eq4(
    records: Sequence[MEIORecord],
    provisional: Sequence[Mapping[str, Any]],
    available_supply: float,
    regional_budget: Optional[float],
    topology: Mapping[str, Sequence[str]],
    edge_caps: Mapping[Tuple[str, str], float],
    criticality_weights: Mapping[str, float],
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, Any]]:
    """Equation (4), represented as a bounded allocation LP.

    With required_i fixed and B_i = required_i - x_i, minimizing
        h_i*x_i + p_i*B_i
    is equivalent (up to a constant) to maximizing
        (p_i - h_i) * x_i.
    Criticality only changes the penalty when the caller explicitly supplied
    a criticality weight; default weight is 1.0.
    """
    n = len(records)
    if n == 0:
        raise ValueError("At least one record is required for optimization.")

    required: List[float] = []
    max_alloc: List[float] = []
    benefits: List[float] = []

    for r, item in zip(records, provisional):
        req = max(0.0, float(item["ReorderPoint"]) - effective_inventory_position(r))
        cap_remaining = max(0.0, r.Capacity_Units - effective_inventory_position(r))
        required.append(req)
        max_alloc.append(min(req, cap_remaining))
        weighted_penalty = r.ShortagePenalty_PerUnit * criticality_weights[r.Criticality_Class]
        benefits.append(weighted_penalty - r.HoldingCost_PerUnit)

    a_ub: List[List[float]] = []
    b_ub: List[float] = []

    # Shared available supply.
    a_ub.append([1.0] * n)
    b_ub.append(available_supply)

    # Optional regional budget.
    if regional_budget is not None:
        a_ub.append([r.UnitCost for r in records])
        b_ub.append(regional_budget)

    # Node capacity / replenishment requirement upper bounds.
    for i in range(n):
        row = [0.0] * n
        row[i] = 1.0
        a_ub.append(row)
        b_ub.append(max_alloc[i])

    # Optional explicit edge-flow limits.
    edge_constraints = _edge_subtree_constraints(records, topology, edge_caps)
    for row, cap, _label in edge_constraints:
        a_ub.append(row)
        b_ub.append(cap)

    allocation, savings, iterations = simplex_maximize(benefits, a_ub, b_ub)
    shortage = [max(0.0, required[i] - allocation[i]) for i in range(n)]

    alloc_by_node = {records[i].Node_ID: allocation[i] for i in range(n)}
    short_by_node = {records[i].Node_ID: shortage[i] for i in range(n)}

    base_shortage_cost = sum(
        required[i]
        * records[i].ShortagePenalty_PerUnit
        * criticality_weights[records[i].Criticality_Class]
        for i in range(n)
    )

    evidence = {
        "optimizer_status": "OPTIMAL",
        "optimizer_method": "PURE_PYTHON_SIMPLEX_EQ4",
        "objective_value": _round(max(0.0, base_shortage_cost - savings)),
        "available_upstream_supply": available_supply,
        "regional_budget": regional_budget,
        "total_required_replenishment": _round(sum(required)),
        "total_allocation": _round(sum(allocation)),
        "total_remaining_shortage": _round(sum(shortage)),
        "simplex_iterations": iterations,
        "edge_flow_constraints_applied": [label for _, _, label in edge_constraints],
        "criticality_priority_weights": dict(criticality_weights),
    }
    return alloc_by_node, short_by_node, evidence


# -----------------------------------------------------------------------------
# Substitution compatibility
# -----------------------------------------------------------------------------

def apply_substitution(
    records: Sequence[MEIORecord],
    remaining_shortage: MutableMapping[Tuple[str, str], float],
    remaining_supply: MutableMapping[str, float],
    substitution_rules: Any,
) -> Tuple[Dict[Tuple[str, str], float], List[Dict[str, Any]]]:
    """Second-pass substitution allocation.

    Rule schema:
      {"from_sku":"NEW", "to_sku":"OLD", "conversion_rate":1.0,
       "same_node_only":true}

    The implementation supports the capability but does not define numeric conversion
    rates or direction, so rules must be supplied by the caller.
    """
    allocations: Dict[Tuple[str, str], float] = defaultdict(float)
    evidence: List[Dict[str, Any]] = []

    if substitution_rules in (None, []):
        return dict(allocations), evidence
    if not isinstance(substitution_rules, list):
        raise ValueError("substitution_rules must be an array.")

    records_by_sku_node = {(r.SKU_ID, r.Node_ID): r for r in records}
    nodes_by_sku: Dict[str, List[str]] = defaultdict(list)
    for r in records:
        nodes_by_sku[r.SKU_ID].append(r.Node_ID)

    for idx, rule in enumerate(substitution_rules):
        if not isinstance(rule, dict):
            raise ValueError(f"substitution_rules[{idx}] must be a JSON object.")
        from_sku = _text(rule.get("from_sku"), f"substitution_rules[{idx}].from_sku")
        to_sku = _text(rule.get("to_sku"), f"substitution_rules[{idx}].to_sku")
        rate = _num(rule.get("conversion_rate", 1.0), f"substitution_rules[{idx}].conversion_rate", EPS)
        same_node_only = bool(rule.get("same_node_only", True))

        source_units = remaining_supply.get(from_sku, 0.0)
        if source_units <= EPS:
            continue

        candidate_nodes = nodes_by_sku.get(to_sku, [])
        for node in candidate_nodes:
            key = (to_sku, node)
            need = remaining_shortage.get(key, 0.0)
            if need <= EPS or source_units <= EPS:
                continue

            if same_node_only and (from_sku, node) not in records_by_sku_node:
                continue

            # source units * rate = target-equivalent units.
            source_needed = need / rate
            source_used = min(source_units, source_needed)
            target_equiv = source_used * rate

            remaining_shortage[key] = max(0.0, need - target_equiv)
            remaining_supply[from_sku] = max(0.0, source_units - source_used)
            source_units = remaining_supply[from_sku]
            allocations[key] += target_equiv

            evidence.append(
                {
                    "from_sku": from_sku,
                    "to_sku": to_sku,
                    "node": node,
                    "source_units_used": _round(source_used),
                    "target_equivalent_units": _round(target_equiv),
                    "conversion_rate": rate,
                }
            )

    return dict(allocations), evidence


# -----------------------------------------------------------------------------
# Probabilistic risk modeling / Monte Carlo
# -----------------------------------------------------------------------------

def run_risk_simulation(
    records: Sequence[MEIORecord],
    policies: Sequence[NodePolicy],
    risk_model: Any,
) -> Dict[str, Any]:
    """Optional Monte Carlo resilience stress test.

    Expected risk_model keys (all caller-supplied):
      simulations, seed,
      supplier_disruption_probability, supplier_supply_multiplier,
      demand_shock_probability, demand_shock_multiplier,
      logistics_failure_probability, lead_time_multiplier.

    Probabilities and multipliers are not invented; they must be supplied explicitly.
    """
    if not risk_model:
        return {"enabled": False, "reason": "No risk_model supplied."}
    if not isinstance(risk_model, dict):
        raise ValueError("risk_model must be a JSON object.")

    simulations = int(_num(risk_model.get("simulations", 1000), "risk_model.simulations", 1.0))
    if simulations > 100000:
        raise ValueError("risk_model.simulations must be <= 100000 for this Lambda reference implementation.")

    seed = risk_model.get("seed", 0)
    rng = random.Random(seed)

    supplier_p = _num(risk_model.get("supplier_disruption_probability", 0.0), "supplier_disruption_probability", 0.0)
    supplier_mult = _num(risk_model.get("supplier_supply_multiplier", 1.0), "supplier_supply_multiplier", 0.0)
    demand_p = _num(risk_model.get("demand_shock_probability", 0.0), "demand_shock_probability", 0.0)
    demand_mult = _num(risk_model.get("demand_shock_multiplier", 1.0), "demand_shock_multiplier", 0.0)
    logistics_p = _num(risk_model.get("logistics_failure_probability", 0.0), "logistics_failure_probability", 0.0)
    lead_mult = _num(risk_model.get("lead_time_multiplier", 1.0), "lead_time_multiplier", 0.0)

    for p_name, p in (("supplier_disruption_probability", supplier_p), ("demand_shock_probability", demand_p), ("logistics_failure_probability", logistics_p)):
        if p > 1.0:
            raise ValueError(f"{p_name} must be <= 1.0.")

    policy_map = {(p.SKU_ID, p.Node_ID): p for p in policies}
    stockouts: Dict[Tuple[str, str], int] = defaultdict(int)
    total_demand: Dict[Tuple[str, str], float] = defaultdict(float)
    total_served: Dict[Tuple[str, str], float] = defaultdict(float)

    for _ in range(simulations):
        supplier_event = rng.random() < supplier_p
        demand_event = rng.random() < demand_p
        logistics_event = rng.random() < logistics_p

        for r in records:
            p = policy_map[(r.SKU_ID, r.Node_ID)]
            dm = r.Demand_Mean * (demand_mult if demand_event else 1.0)
            dv = max(0.0, r.Demand_Variance * ((demand_mult ** 2) if demand_event else 1.0))
            lt = r.LeadTime_Days * (lead_mult if logistics_event else 1.0)

            # Aggregate lead-time demand using Normal approximation.
            mean_lt = dm * lt
            sd_lt = math.sqrt(dv) * math.sqrt(max(lt, 0.0))
            simulated_demand = max(0.0, rng.gauss(mean_lt, sd_lt))

            replenishment = p.TotalRecommendedSupply
            if supplier_event:
                replenishment *= supplier_mult

            available = effective_inventory_position(r) + replenishment
            served = min(available, simulated_demand)
            key = (r.SKU_ID, r.Node_ID)
            total_demand[key] += simulated_demand
            total_served[key] += served
            if simulated_demand > available + EPS:
                stockouts[key] += 1

    by_node = []
    for r in records:
        key = (r.SKU_ID, r.Node_ID)
        demand = total_demand[key]
        served = total_served[key]
        by_node.append(
            {
                "SKU_ID": r.SKU_ID,
                "Node_ID": r.Node_ID,
                "RiskRegion": r.RiskRegion,
                "Criticality_Class": r.Criticality_Class,
                "stockout_probability": _round(stockouts[key] / simulations),
                "modeled_fill_rate": _round(served / demand if demand > EPS else 1.0),
            }
        )

    return {
        "enabled": True,
        "simulations": simulations,
        "seed": seed,
        "configuration": {
            "supplier_disruption_probability": supplier_p,
            "supplier_supply_multiplier": supplier_mult,
            "demand_shock_probability": demand_p,
            "demand_shock_multiplier": demand_mult,
            "logistics_failure_probability": logistics_p,
            "lead_time_multiplier": lead_mult,
        },
        "by_node": by_node,
        "evidence_boundary": "modeled stress-test output from caller-supplied risk assumptions; not observed carrier performance",
    }


# -----------------------------------------------------------------------------
# Offline replay helper
# -----------------------------------------------------------------------------

def run_offline_replay(policies: Sequence[NodePolicy], historical_replay: Any) -> Dict[str, Any]:
    """Optional replay of caller-supplied actual demand observations.

    Each observation may contain:
      SKU_ID, Node_ID, ActualDemand, BaselineAvailableQty(optional).
    Current-policy available quantity is modeled as ReorderPoint + recommended supply.
    This helper does not invent a prior baseline.
    """
    if not historical_replay:
        return {"enabled": False, "reason": "No historical_replay observations supplied."}
    if not isinstance(historical_replay, list):
        raise ValueError("historical_replay must be an array.")

    pmap = {(p.SKU_ID, p.Node_ID): p for p in policies}
    current_stockouts = 0
    baseline_stockouts = 0
    baseline_count = 0
    current_demand = 0.0
    current_served = 0.0
    baseline_demand = 0.0
    baseline_served = 0.0

    for idx, obs in enumerate(historical_replay):
        if not isinstance(obs, dict):
            raise ValueError(f"historical_replay[{idx}] must be a JSON object.")
        sku = _text(obs.get("SKU_ID"), f"historical_replay[{idx}].SKU_ID")
        node = _text(obs.get("Node_ID"), f"historical_replay[{idx}].Node_ID")
        demand = _num(obs.get("ActualDemand"), f"historical_replay[{idx}].ActualDemand", 0.0)
        policy = pmap.get((sku, node))
        if policy is None:
            raise ValueError(f"No generated policy for historical observation {sku}/{node}.")

        available = policy.ReorderPoint + policy.TotalRecommendedSupply
        current_demand += demand
        current_served += min(demand, available)
        if demand > available + EPS:
            current_stockouts += 1

        if obs.get("BaselineAvailableQty") is not None:
            base = _num(obs.get("BaselineAvailableQty"), f"historical_replay[{idx}].BaselineAvailableQty", 0.0)
            baseline_count += 1
            baseline_demand += demand
            baseline_served += min(demand, base)
            if demand > base + EPS:
                baseline_stockouts += 1

    result = {
        "enabled": True,
        "observation_count": len(historical_replay),
        "current_policy": {
            "stockout_observations": current_stockouts,
            "modeled_fill_rate": _round(current_served / current_demand if current_demand > EPS else 1.0),
        },
        "evidence_boundary": "offline replay using caller-supplied observations; not a claim of production deployment",
    }
    if baseline_count:
        result["baseline"] = {
            "observation_count": baseline_count,
            "stockout_observations": baseline_stockouts,
            "modeled_fill_rate": _round(baseline_served / baseline_demand if baseline_demand > EPS else 1.0),
        }
    return result


# -----------------------------------------------------------------------------
# Build policies for one SKU
# -----------------------------------------------------------------------------

def build_for_sku(
    records: Sequence[MEIORecord],
    topology: Mapping[str, Sequence[str]],
    available_supply: float,
    regional_budget: Optional[float],
    trigger_type: str,
    data_version_ref: str,
    max_change_pct: float,
    normal_role: str,
    exception_role: str,
    expiration_date: Optional[str],
    criticality_weights: Mapping[str, float],
    edge_caps: Mapping[Tuple[str, str], float],
    payload: Mapping[str, Any],
) -> Tuple[List[NodePolicy], List[AuditRecord], Dict[str, Any]]:
    if not records:
        raise ValueError("records cannot be empty.")
    sku_ids = {r.SKU_ID for r in records}
    if len(sku_ids) != 1:
        raise ValueError("One SKU is required per optimization slice.")

    node_ids = [r.Node_ID for r in records]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError(f"Duplicate Node_ID values found for SKU {records[0].SKU_ID}.")

    by_node = {r.Node_ID: r for r in records}
    now = _utc_now()
    policy_id = f"MEIO-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex}"
    effective_date = now.date().isoformat()
    now_iso = now.isoformat()

    provisional: List[Dict[str, Any]] = []
    for r in records:
        mean_mult, variance_mult, lead_mult = _surge_parameters(payload, r)
        ss_proposed = safety_stock(r, variance_mult, lead_mult)
        rop_proposed = reorder_point(r, ss_proposed, mean_mult, lead_mult)
        ss_target, rop_target, guardrail_status, approver = apply_guardrail(
            ss_proposed,
            rop_proposed,
            r.Prior_SafetyStock,
            r.Prior_ReorderPoint,
            max_change_pct,
            normal_role,
            exception_role,
        )
        provisional.append(
            {
                "record": r,
                "EchelonInventory": echelon_inventory(r, by_node, topology),
                "ServiceLevelFactor_Z": service_level_factor(r.ServiceLevel_Target),
                "SafetyStock_Proposed": ss_proposed,
                "ReorderPoint_Proposed": rop_proposed,
                "SafetyStock_Target": ss_target,
                "ReorderPoint": rop_target,
                "GuardrailStatus": guardrail_status,
                "ApproverRole": approver,
                "surge_multipliers": {
                    "demand_mean_multiplier": mean_mult,
                    "demand_variance_multiplier": variance_mult,
                    "lead_time_multiplier": lead_mult,
                },
            }
        )

    allocation, shortage, optimizer_evidence = optimize_eq4(
        records,
        provisional,
        available_supply,
        regional_budget,
        topology,
        edge_caps,
        criticality_weights,
    )

    policies: List[NodePolicy] = []
    audits: List[AuditRecord] = []
    for item in provisional:
        r: MEIORecord = item["record"]
        remaining = shortage[r.Node_ID]
        rule = "CONSTRAINED_NETWORK_ALLOCATION_EQ4" if remaining > EPS else "ALLOCATE_TO_REORDER_POINT"
        approval_ts = None if item["GuardrailStatus"] == "APPROVAL_REQUIRED" else now_iso
        base_alloc = allocation[r.Node_ID]

        policies.append(
            NodePolicy(
                SKU_ID=r.SKU_ID,
                Node_ID=r.Node_ID,
                PolicyVersionID=policy_id,
                EchelonInventory=_round(item["EchelonInventory"], 4),
                LocalInventoryPosition=_round(local_inventory_position(r), 4),
                RepairReturnCredit=_round(repair_return_credit(r), 4),
                EffectiveInventoryPosition=_round(effective_inventory_position(r), 4),
                ServiceLevel_Assigned=r.ServiceLevel_Target,
                ServiceLevelFactor_Z=_round(item["ServiceLevelFactor_Z"], 6),
                SafetyStock_Proposed=_round(item["SafetyStock_Proposed"], 4),
                ReorderPoint_Proposed=_round(item["ReorderPoint_Proposed"], 4),
                SafetyStock_Target=_round(item["SafetyStock_Target"], 4),
                ReorderPoint=_round(item["ReorderPoint"], 4),
                OrderUpToLevel=None,  # Optional field; no default formula is imposed.
                RecommendedAllocation=_round(base_alloc, 4),
                SubstitutionAllocation=0.0,
                TotalRecommendedSupply=_round(base_alloc, 4),
                RemainingShortage=_round(remaining, 4),
                AllocationRule_UnderShortage=rule,
                Criticality_Class=r.Criticality_Class,
                RiskRegion=r.RiskRegion,
                TriggerType=trigger_type,
                ApproverRole=item["ApproverRole"],
                GuardrailStatus=item["GuardrailStatus"],
                EffectiveDate=effective_date,
                ExpirationDate=expiration_date,
                RollbackRef=r.Prior_PolicyVersionID,
            )
        )

        audits.append(
            AuditRecord(
                PolicyVersionID=policy_id,
                SKU_ID=r.SKU_ID,
                Node_ID=r.Node_ID,
                Prior_SS=r.Prior_SafetyStock,
                New_SS=_round(item["SafetyStock_Proposed"], 4),
                Prior_R=r.Prior_ReorderPoint,
                New_R=_round(item["ReorderPoint_Proposed"], 4),
                TriggerType=trigger_type,
                DataVersionRef=data_version_ref,
                ApproverRole=item["ApproverRole"],
                ApprovalTimestamp=approval_ts,
                EffectiveDate=effective_date,
                RollbackRef=r.Prior_PolicyVersionID,
                GuardrailStatus=item["GuardrailStatus"],
            )
        )

    summary = {
        "PolicyVersionID": policy_id,
        "SKU_ID": records[0].SKU_ID,
        "node_count": len(records),
        "optimizer": optimizer_evidence,
        "surge_configuration_applied": {
            r.Node_ID: item["surge_multipliers"] for r, item in zip(records, provisional)
        },
        "evidence_boundary": "controlled reference implementation using caller-supplied inputs",
    }
    return policies, audits, summary


# -----------------------------------------------------------------------------
# Full request execution
# -----------------------------------------------------------------------------

def run_meio(payload: Mapping[str, Any]) -> Dict[str, Any]:
    required_keys = (
        "records",
        "topology",
        "available_upstream_supply_by_sku",
        "regional_budget_by_sku",
        "trigger_type",
        "data_version_ref",
        "max_change_pct",
        "normal_approver_role",
        "exception_approver_role",
        "expiration_date",
    )
    missing = [k for k in required_keys if k not in payload]
    if missing:
        raise ValueError("Missing required request fields: " + ", ".join(missing))

    records = parse_records(payload["records"])
    topology = validate_topology(payload["topology"])

    # Ensure record nodes are represented in the topology map, including leaves.
    for r in records:
        topology.setdefault(r.Node_ID, [])

    supply_by_sku = payload["available_upstream_supply_by_sku"]
    budgets_by_sku = payload["regional_budget_by_sku"]
    if not isinstance(supply_by_sku, dict):
        raise ValueError("available_upstream_supply_by_sku must be a JSON object.")
    if not isinstance(budgets_by_sku, dict):
        raise ValueError("regional_budget_by_sku must be a JSON object.")

    trigger_type = _text(payload["trigger_type"], "trigger_type")
    data_version_ref = _text(payload["data_version_ref"], "data_version_ref")
    max_change_pct = _num(payload["max_change_pct"], "max_change_pct", 0.0)
    normal_role = _text(payload["normal_approver_role"], "normal_approver_role")
    exception_role = _text(payload["exception_approver_role"], "exception_approver_role")
    expiration_date = payload["expiration_date"]
    if expiration_date is not None:
        expiration_date = _text(expiration_date, "expiration_date")

    criticality_weights = _criticality_weights(payload)
    edge_caps = parse_edge_capacities(payload)

    grouped: Dict[str, List[MEIORecord]] = defaultdict(list)
    for r in records:
        grouped[r.SKU_ID].append(r)

    policies: List[NodePolicy] = []
    audits: List[AuditRecord] = []
    summaries: List[Dict[str, Any]] = []

    original_supply: Dict[str, float] = {}
    allocated_primary_by_sku: Dict[str, float] = {}

    for sku, sku_records in grouped.items():
        if sku not in supply_by_sku:
            raise ValueError(f"available_upstream_supply_by_sku is missing SKU {sku}.")
        if sku not in budgets_by_sku:
            raise ValueError(f"regional_budget_by_sku is missing SKU {sku}.")

        supply = _num(supply_by_sku[sku], f"available_upstream_supply_by_sku[{sku}]", 0.0)
        original_supply[sku] = supply
        raw_budget = budgets_by_sku[sku]
        budget = None if raw_budget is None else _num(raw_budget, f"regional_budget_by_sku[{sku}]", 0.0)

        p, a, s = build_for_sku(
            sku_records,
            topology,
            supply,
            budget,
            trigger_type,
            data_version_ref,
            max_change_pct,
            normal_role,
            exception_role,
            expiration_date,
            criticality_weights,
            edge_caps,
            payload,
        )
        policies.extend(p)
        audits.extend(a)
        summaries.append(s)
        allocated_primary_by_sku[sku] = sum(x.RecommendedAllocation for x in p)

    # Optional substitution compatibility across SKUs.
    remaining_supply = {
        sku: max(0.0, original_supply[sku] - allocated_primary_by_sku.get(sku, 0.0))
        for sku in original_supply
    }
    remaining_shortage: Dict[Tuple[str, str], float] = {
        (p.SKU_ID, p.Node_ID): p.RemainingShortage for p in policies
    }
    substitution_alloc, substitution_evidence = apply_substitution(
        records,
        remaining_shortage,
        remaining_supply,
        payload.get("substitution_rules"),
    )

    if substitution_alloc:
        for p in policies:
            add = substitution_alloc.get((p.SKU_ID, p.Node_ID), 0.0)
            if add > EPS:
                p.SubstitutionAllocation = _round(add, 4)
                p.TotalRecommendedSupply = _round(p.RecommendedAllocation + add, 4)
                p.RemainingShortage = _round(remaining_shortage[(p.SKU_ID, p.Node_ID)], 4)
                if p.RemainingShortage <= EPS:
                    p.AllocationRule_UnderShortage = "SUBSTITUTION_TO_REORDER_POINT"
                else:
                    p.AllocationRule_UnderShortage = "CONSTRAINED_EQ4_PLUS_SUBSTITUTION"

    risk = run_risk_simulation(records, policies, payload.get("risk_model"))
    replay = run_offline_replay(policies, payload.get("historical_replay"))

    return {
        "message": "MEIO optimization completed",
        "implementation_scope": {
            "equation_1_echelon_inventory": True,
            "equation_2_safety_stock": True,
            "equation_3_reorder_point": True,
            "equation_4_constrained_allocation": True,
            "node_capacity": True,
            "regional_budget": True,
            "available_supply": True,
            "optional_edge_flow_capacity": bool(edge_caps),
            "criticality_class": True,
            "criticality_numeric_priority": "caller-supplied only",
            "repair_return_loop": any(r.Repairable_Flag and r.Return_Qty > 0 and r.RepairYield > 0 for r in records),
            "substitution_compatibility": bool(payload.get("substitution_rules")),
            "disaster_surge_staging": bool(payload.get("surge_config")),
            "probabilistic_risk_monte_carlo": bool(payload.get("risk_model")),
            "offline_replay": bool(payload.get("historical_replay")),
            "governance_guardrail": True,
            "versioned_audit": True,
        },
        "summaries": summaries,
        "policies": [asdict(p) for p in policies],
        "audit": [asdict(a) for a in audits],
        "substitution_evidence": substitution_evidence,
        "risk_simulation": risk,
        "offline_replay": replay,
        "evidence_boundary": (
            "Controlled reference implementation. Optional risk, repair, substitution, flow, and surge behavior "
            "uses caller-supplied assumptions rather than hard-coded numerical calibration."
        ),
    }


# -----------------------------------------------------------------------------
# AWS Lambda entry point
# -----------------------------------------------------------------------------

def lambda_handler(event: Any, context: Any) -> Dict[str, Any]:
    try:
        payload = _payload_from_event(event)
        result = run_meio(payload)
        return _response(200, result)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return _response(400, {"error": str(exc)})
    except Exception as exc:  # pragma: no cover - final Lambda safety boundary
        print("Unhandled MEIO error: " + str(exc))
        return _response(500, {"error": "MEIO optimization failed", "detail": str(exc)})


if __name__ == "__main__":
    # Minimal smoke-test payload. No hardcoded output is embedded; values below
    # are only caller-style demonstration inputs for local execution.
    demo = {
        "records": [
            {
                "SKU_ID": "TEL-SKU-001",
                "Node_ID": "NATIONAL_HUB",
                "Calendar_Week": "2026-W34",
                "Demand_Qty": 55,
                "Demand_Mean": 8,
                "Demand_Variance": 16,
                "LeadTime_Days": 7,
                "LeadTime_StdDev": 1.5,
                "OnHand_Qty": 20,
                "OnOrder_Qty": 10,
                "InTransit_Qty": 5,
                "UnitCost": 100,
                "Criticality_Class": "AX",
                "Capacity_Units": 200,
                "ServiceLevel_Target": 0.95,
                "Repairable_Flag": False,
                "Substitution_Group_ID": "TEL-GROUP-01",
                "RiskRegion": "NATIONAL",
                "HoldingCost_PerUnit": 2,
                "ShortagePenalty_PerUnit": 50,
            },
            {
                "SKU_ID": "TEL-SKU-001",
                "Node_ID": "DENVER_HUB",
                "Calendar_Week": "2026-W34",
                "Demand_Qty": 35,
                "Demand_Mean": 5,
                "Demand_Variance": 25,
                "LeadTime_Days": 5,
                "LeadTime_StdDev": 1.2,
                "OnHand_Qty": 10,
                "OnOrder_Qty": 3,
                "InTransit_Qty": 2,
                "UnitCost": 120,
                "Criticality_Class": "AY",
                "Capacity_Units": 100,
                "ServiceLevel_Target": 0.98,
                "Repairable_Flag": False,
                "Substitution_Group_ID": "TEL-GROUP-01",
                "RiskRegion": "WEST",
                "HoldingCost_PerUnit": 2.5,
                "ShortagePenalty_PerUnit": 80,
            },
            {
                "SKU_ID": "TEL-SKU-001",
                "Node_ID": "DALLAS_HUB",
                "Calendar_Week": "2026-W34",
                "Demand_Qty": 30,
                "Demand_Mean": 4,
                "Demand_Variance": 9,
                "LeadTime_Days": 5,
                "LeadTime_StdDev": 1,
                "OnHand_Qty": 7,
                "OnOrder_Qty": 2,
                "InTransit_Qty": 1,
                "UnitCost": 110,
                "Criticality_Class": "BZ",
                "Capacity_Units": 100,
                "ServiceLevel_Target": 0.97,
                "Repairable_Flag": True,
                "Substitution_Group_ID": "TEL-GROUP-01",
                "RiskRegion": "SOUTH",
                "HoldingCost_PerUnit": 2,
                "ShortagePenalty_PerUnit": 65,
                "Return_Qty": 4,
                "RepairYield": 0.75,
            },
        ],
        "topology": {
            "NATIONAL_HUB": ["DENVER_HUB", "DALLAS_HUB"],
            "DENVER_HUB": [],
            "DALLAS_HUB": [],
        },
        "available_upstream_supply_by_sku": {"TEL-SKU-001": 40},
        "regional_budget_by_sku": {"TEL-SKU-001": 4500},
        "trigger_type": "CONTROLLED_TEST_RUN",
        "data_version_ref": "SYNTHETIC-DEMO-2026-W34",
        "max_change_pct": 0.2,
        "normal_approver_role": "INVENTORY_PLANNER",
        "exception_approver_role": "SUPPLY_CHAIN_MANAGER",
        "expiration_date": None,
        "criticality_priority_weights": {},
        "edge_capacities": {},
        "surge_config": {},
        "substitution_rules": [],
    }
    print(json.dumps(run_meio(demo), indent=2))
