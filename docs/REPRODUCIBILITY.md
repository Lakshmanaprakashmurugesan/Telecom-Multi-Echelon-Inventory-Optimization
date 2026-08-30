# Reproducibility Guide

## 1. Capture the exact snapshot

After cloning or extracting the repository:

```bash
git rev-parse HEAD  # when running from Git
sha256sum lambda_function.py index.html MEIO_Input_Test.xlsx
```

PowerShell:

```powershell
Get-FileHash .\lambda_function.py -Algorithm SHA256
Get-FileHash .\index.html -Algorithm SHA256
Get-FileHash .\MEIO_Input_Test.xlsx -Algorithm SHA256
```

The retained artifact manifest is `evidence/SHA256SUMS.txt`.

## 2. Record environment

```bash
python --version
```

Record the operating system and execution date/time. The included backend uses only the Python standard library.

## 3. Backend smoke test

```bash
python lambda_function.py
```

Compare the structure—not runtime-generated policy IDs/timestamps—with `evidence/backend_smoke_test_console.txt`.

## 4. Automated tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The retained run is in:

```text
evidence/pytest_console_output.txt
evidence/pytest_results.xml
```

## 5. Baseline controlled request

The workbook-equivalent request is retained at:

```text
evidence/baseline/request.json
```

Execute it directly:

```bash
python - <<'PY'
import json
from pathlib import Path
from lambda_function import run_meio

request = json.loads(Path("evidence/baseline/request.json").read_text())
print(json.dumps(run_meio(request), indent=2))
PY
```

The generated policy IDs and timestamps change each run. Numeric policy/optimizer fields should reproduce subject to normal floating-point and output-rounding behavior.

## 6. Controlled scenarios

Retained scenario request/response pairs are under `evidence/scenarios/`:

- `supply_constraint/`
- `budget_constraint/`
- `guardrail/`
- `edge_flow/`
- `risk_model/`
- `offline_replay/`

Each scenario changes a defined input or supplies an optional configuration rather than changing the algorithm.

## 7. Hosted browser / workbook path

Open the existing AWS Amplify application:

**https://staging.d387jy9rxdyq28.amplifyapp.com/**

Upload `MEIO_Input_Test.xlsx`, confirm the workbook is accepted, then select **Run MEIO Optimization**. The generated request is kept internal by the browser UI. No local web server is required for the normal browser workflow.

Browser reproduction additionally depends on:

- the deployed Amplify build corresponding to the intended repository revision;
- the SheetJS/XLSX CDN referenced in `index.html`;
- network reachability of the API Gateway endpoint configured in `index.html`;
- CORS/deployment configuration at that endpoint.

For strict source-to-deployment reproducibility, record the Amplify deployment/commit identifier and the Lambda/API deployment metadata described in `docs/DEPLOYMENT_NOTES.md`.

## 8. Evidence integrity

Do not edit retained output files after execution. If evidence is regenerated, regenerate `evidence/SHA256SUMS.txt` and record the new repository commit/hash.

Screenshots are secondary visual aids. Raw JSON, console output, tests, and hashes are stronger reproducibility artifacts.
