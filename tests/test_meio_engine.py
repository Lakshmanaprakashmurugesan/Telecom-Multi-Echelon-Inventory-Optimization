import copy
import json
import math

import pytest

import lambda_function as meio


def baseline_payload():
    return {
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


def test_service_level_factor_and_core_equations():
    r = meio.MEIORecord(**baseline_payload()["records"][0])
    z = meio.service_level_factor(r.ServiceLevel_Target)
    ss = meio.safety_stock(r)
    rop = meio.reorder_point(r, ss)
    assert z > 0
    assert ss == pytest.approx(z * math.sqrt(r.Demand_Variance) * math.sqrt(r.LeadTime_Days))
    assert rop == pytest.approx(r.Demand_Mean * r.LeadTime_Days + ss)


def test_echelon_inventory_includes_downstream_effective_inventory():
    records = [meio.MEIORecord(**x) for x in baseline_payload()["records"]]
    by_node = {r.Node_ID: r for r in records}
    topology = meio.validate_topology(baseline_payload()["topology"])
    national = by_node["NATIONAL_HUB"]
    expected = sum(meio.effective_inventory_position(r) for r in records)
    assert meio.echelon_inventory(national, by_node, topology) == pytest.approx(expected)


def test_repair_return_credit_uses_only_caller_supplied_values():
    dallas = meio.MEIORecord(**baseline_payload()["records"][2])
    assert meio.repair_return_credit(dallas) == pytest.approx(3.0)
    dallas.Repairable_Flag = False
    assert meio.repair_return_credit(dallas) == 0.0


def test_topology_cycle_is_rejected():
    with pytest.raises(ValueError, match="cycle"):
        meio.validate_topology({"A": ["B"], "B": ["A"]})


def test_guardrail_requires_approval_and_preserves_prior_values():
    ss, rop, status, role = meio.apply_guardrail(
        proposed_ss=150,
        proposed_rop=300,
        prior_ss=100,
        prior_rop=200,
        max_change_pct=0.20,
        normal_role="PLANNER",
        exception_role="MANAGER",
    )
    assert (ss, rop) == (100, 200)
    assert status == "APPROVAL_REQUIRED"
    assert role == "MANAGER"


def test_baseline_run_is_structured_and_respects_global_constraints():
    payload = baseline_payload()
    result = meio.run_meio(payload)
    assert result["message"] == "MEIO optimization completed"
    assert len(result["policies"]) == 3
    assert len(result["audit"]) == 3
    optimizer = result["summaries"][0]["optimizer"]
    assert optimizer["optimizer_status"] == "OPTIMAL"
    assert optimizer["total_allocation"] <= payload["available_upstream_supply_by_sku"]["TEL-SKU-001"] + 1e-8
    total_spend = sum(p["RecommendedAllocation"] * next(r["UnitCost"] for r in payload["records"] if r["Node_ID"] == p["Node_ID"]) for p in result["policies"])
    assert total_spend <= payload["regional_budget_by_sku"]["TEL-SKU-001"] + 0.02


def test_node_capacity_is_never_exceeded_after_primary_allocation():
    payload = baseline_payload()
    result = meio.run_meio(payload)
    source = {r["Node_ID"]: r for r in payload["records"]}
    for p in result["policies"]:
        r = source[p["Node_ID"]]
        effective = r["OnHand_Qty"] + r["OnOrder_Qty"] + r["InTransit_Qty"]
        if r.get("Repairable_Flag"):
            effective += r.get("Return_Qty", 0) * r.get("RepairYield", 0)
        assert effective + p["RecommendedAllocation"] <= r["Capacity_Units"] + 1e-4


def test_edge_flow_capacity_binds_when_supplied():
    payload = baseline_payload()
    payload["available_upstream_supply_by_sku"]["TEL-SKU-001"] = 100
    payload["regional_budget_by_sku"]["TEL-SKU-001"] = None
    payload["edge_capacities"] = {"NATIONAL_HUB->DENVER_HUB": 2.0}
    result = meio.run_meio(payload)
    denver = next(p for p in result["policies"] if p["Node_ID"] == "DENVER_HUB")
    assert denver["RecommendedAllocation"] <= 2.0 + 1e-8
    assert "NATIONAL_HUB->DENVER_HUB" in result["summaries"][0]["optimizer"]["edge_flow_constraints_applied"]


def test_invalid_service_level_is_rejected_through_lambda_contract():
    payload = baseline_payload()
    payload["records"][0]["ServiceLevel_Target"] = 1.0
    response = meio.lambda_handler({"body": json.dumps(payload)}, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "ServiceLevel_Target" in body["error"]


def test_missing_required_field_returns_400():
    payload = baseline_payload()
    payload.pop("regional_budget_by_sku")
    response = meio.lambda_handler(payload, None)
    assert response["statusCode"] == 400
    assert "regional_budget_by_sku" in json.loads(response["body"])["error"]


def test_risk_simulation_is_reproducible_with_explicit_seed():
    payload = baseline_payload()
    payload["risk_model"] = {
        "simulations": 200,
        "seed": 17,
        "supplier_disruption_probability": 0.10,
        "supplier_supply_multiplier": 0.5,
        "demand_shock_probability": 0.15,
        "demand_shock_multiplier": 1.25,
        "logistics_failure_probability": 0.10,
        "lead_time_multiplier": 1.2,
    }
    a = meio.run_meio(copy.deepcopy(payload))["risk_simulation"]
    b = meio.run_meio(copy.deepcopy(payload))["risk_simulation"]
    assert a == b
    assert a["enabled"] is True
    assert len(a["by_node"]) == 3


def test_offline_replay_uses_only_supplied_observations_and_baseline():
    payload = baseline_payload()
    payload["historical_replay"] = [
        {"SKU_ID": "TEL-SKU-001", "Node_ID": "DENVER_HUB", "ActualDemand": 35, "BaselineAvailableQty": 20},
        {"SKU_ID": "TEL-SKU-001", "Node_ID": "DALLAS_HUB", "ActualDemand": 30, "BaselineAvailableQty": 18},
    ]
    replay = meio.run_meio(payload)["offline_replay"]
    assert replay["enabled"] is True
    assert replay["observation_count"] == 2
    assert replay["baseline"]["observation_count"] == 2
    assert 0.0 <= replay["current_policy"]["modeled_fill_rate"] <= 1.0
    assert 0.0 <= replay["baseline"]["modeled_fill_rate"] <= 1.0
