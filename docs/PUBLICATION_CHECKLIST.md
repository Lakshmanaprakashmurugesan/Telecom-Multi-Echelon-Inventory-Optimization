# Publication Checklist

Use truthful, current dates. Do not backdate repository history or evidence.

## Before first push

- [ ] Confirm `lambda_function.py` is the deployment-canonical source copy you intend to publish.
- [ ] Run `python lambda_function.py`.
- [ ] Run `python -m pytest -q` and confirm all tests pass.
- [ ] Review `evidence/SHA256SUMS.txt` after any file change.
- [ ] Confirm no secrets, credentials, private customer data, or proprietary operational data are present.
- [ ] Confirm the API Gateway URL in `index.html` is intentionally public.
- [ ] Confirm the Amplify app is connected to the intended Git branch.
- [ ] Confirm API Gateway CORS allows `https://staging.d1jrsof4a5v813.amplifyapp.com/`.
- [ ] Decide whether to add an open-source license; no license is assumed here.

## Recommended initial commit sequence

```text
1. Publish existing MEIO optimization engine
2. Add browser interface and controlled workbook
3. Add reproducibility tests and controlled execution evidence
4. Document architecture, validation, and deployment boundaries
```

If publishing the prepared repository in one initial commit, use a factual message such as:

```text
Publish telecom MEIO reference implementation and reproducibility materials
```

## After push

- tag the independently reviewed snapshot if appropriate;
- record the Git commit SHA used by any reviewer;
- capture the Amplify deployment/commit identifier and remote Lambda/API metadata when a reviewer needs source-to-deployment binding.
- verify the hosted application at `https://staging.d1jrsof4a5v813.amplifyapp.com/` after each published UI revision.
