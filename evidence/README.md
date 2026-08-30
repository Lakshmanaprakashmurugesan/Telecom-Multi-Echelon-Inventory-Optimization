# Reproducibility Evidence

This directory contains machine-readable artifacts generated from actual executions of the included MEIO source using controlled synthetic inputs.

## Contents

```text
backend_smoke_test_console.txt     Local `python lambda_function.py` output
pytest_console_output.txt          Automated validation console output
pytest_results.xml                 JUnit-formatted automated test result
validation_summary.json            Compact summary of retained controlled runs
ENVIRONMENT.txt                    Runtime/platform record
SHA256SUMS.txt                     Hash manifest for repository artifacts
baseline/request.json              Workbook-equivalent controlled request
baseline/response.json             Actual generated baseline response
scenarios/*/request.json           Controlled scenario request
scenarios/*/response.json          Actual generated scenario response
```

## Controlled scenarios

- `supply_constraint`: available upstream supply reduced to 15 units;
- `budget_constraint`: ample supply with regional budget reduced to 1500;
- `guardrail`: prior policy values supplied, one demand input changed, and `max_change_pct` set to 0;
- `edge_flow`: explicit `NATIONAL_HUB->DENVER_HUB` flow capacity of 2;
- `risk_model`: seeded Monte Carlo stress configuration;
- `offline_replay`: supplied demand observations with optional baseline available quantities.

## Evidence boundary

These artifacts establish reproducible behavior of the controlled implementation. They are not production carrier data, production benchmarks, customer adoption evidence, or claims of nationwide operational impact.

Runtime-generated policy IDs and timestamps will differ when the same requests are executed again.
