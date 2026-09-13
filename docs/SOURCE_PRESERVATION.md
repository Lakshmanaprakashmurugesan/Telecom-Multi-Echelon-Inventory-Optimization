# Source Preservation Record

## Preservation rule

The existing MEIO backend implementation remains the technical source of truth. Repository preparation does not materially change the MEIO equations, optimizer, inventory logic, Lambda request/response contract, or the controlled Excel workbook.

## Backend source

The included backend is copied from the current supplied source file without intentional algorithmic or functional modification.

```text
lambda_function.py
SHA-256: 8297a2bf66f0b03702818ec836c3c503362e014dc989a0f6e2003128d3e37e12
```

The repository preparation did not intentionally change:

- Eq. (1) echelon inventory logic;
- Eq. (2) safety-stock logic;
- Eq. (3) reorder-point logic;
- Eq. (4) constrained allocation logic;
- simplex optimization behavior;
- topology validation;
- capacity, supply, budget, and optional edge-flow constraints;
- repair/return, substitution, surge, risk, or replay functions;
- guardrail/version/audit logic;
- Lambda handler behavior.

## Controlled workbook

The included workbook is copied byte-for-byte from the supplied test workbook.

```text
MEIO_Input_Test.xlsx
SHA-256: a7f5c86306801f615064eb757d588471099a7902f5fb10cd75897e4c9433b2fd
```

## Browser interface

The browser presentation layer is intentionally refined for professional AWS Amplify hosting. The current frontend is **Excel-first**: users upload `.xlsx`/`.xls` files and the generated API request remains internal instead of appearing in a visible editable JSON panel.

The current final frontend hash is:

```text
index.html
SHA-256: 0735b69c5ecc0a436c983bc0cd74b8713e7334db55190789780a79ffe15151dd
```

The supplied frontend before this final Excel-only UI adjustment had:

```text
Supplied index (4).html
SHA-256: 487537a9f52f540d8e2d32f64cf7c2c2100db116cf60a2394e73ffd6a98822bf
```

Frontend changes are limited to presentation and user-input workflow:

- professional UI layout/styling;
- hidden internal request buffer instead of visible Request JSON;
- Excel-only file selector in the hosted UI;
- removal of the user-facing JSON-file upload branch;
- deployment marker used to verify the correct Amplify build.

The following execution behavior is intentionally preserved:

- same configured `API_URL`;
- same Excel workbook schema;
- same workbook-to-request conversion functions;
- same required field lists;
- same numeric/boolean parsing rules;
- same request payload keys;
- same `fetch()` POST execution path;
- same response parsing;
- same policy-table field mapping;
- same success/error handling;
- same backend calculation source.

## Support artifacts

The following repository additions are support material around the existing implementation rather than new MEIO functionality:

- automated validation tests;
- controlled request/response evidence;
- reproducibility documentation;
- architecture-to-code mapping;
- methodology traceability;
- API verification utility;
- AWS Amplify deployment artifact;
- hashes and environment records.

## Change gate

Any future modification to `lambda_function.py` or `MEIO_Input_Test.xlsx` should be reviewed separately before it is described as the same implementation snapshot. For any source change, record the exact diff, technical reason, behavior impact, validation results, and new hashes.
