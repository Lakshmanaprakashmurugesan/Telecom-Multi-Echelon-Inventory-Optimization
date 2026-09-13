# Hosted AWS Amplify Deployment

## Hosted URL

The browser application is intended to be served from:

**https://staging.d1jrsof4a5v813.amplifyapp.com/**

The frontend in `index.html` is configured to call:

```text
https://7qdd3wap3a.execute-api.us-east-1.amazonaws.com/M/meio/optimize
```

## Manual Amplify deployment

For a frontend-only update, use the prepared file:

```text
deploy/MEIO-Amplify-Deploy.zip
```

That ZIP contains `index.html` directly at the archive root. Upload it to the existing Amplify `staging` deployment and wait for the deployment to complete.

After deployment, open the hosted URL and hard-refresh the page. The HTML contains this invisible build marker for verification:

```text
MEIO UI BUILD: 2026-08-23-final-excel-ui
```

From PowerShell, verify the deployed HTML with:

```powershell
curl.exe -s "https://staging.d1jrsof4a5v813.amplifyapp.com/?v=final" | Select-String "MEIO UI BUILD"
```

## Hosted workflow

```text
Excel workbook
      ↓
AWS Amplify / index.html
      ↓
Browser workbook validation/conversion
      ↓
API Gateway
      ↓
AWS Lambda
      ↓
MEIO engine
      ↓
Policy table + structured response
```

The current UI is intentionally Excel-first. The generated request payload remains internal and is not displayed as an editable JSON panel.

## API verification

The repository includes a standard-library utility:

```bash
python tools/verify_api.py
```

It checks both the browser-style CORS preflight and the baseline POST request. The command requires internet access and the remote API to be deployed.

## Important deployment boundary

The repository contains the Lambda-compatible source, but a repository snapshot alone does not prove which source revision is currently deployed behind API Gateway. For a formal deployment record, capture the Lambda `CodeSha256`, function version/alias, API Gateway stage/deployment identifier, Amplify deployment identifier, and repository commit SHA.
