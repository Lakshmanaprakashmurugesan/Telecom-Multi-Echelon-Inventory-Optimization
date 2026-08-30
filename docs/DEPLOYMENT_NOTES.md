# Deployment Notes

## Existing hosted application

The browser UI is configured for the existing AWS Amplify site:

**https://staging.d1jrsof4a5v813.amplifyapp.com/**

The configured API Gateway endpoint in `index.html` is:

```text
https://7qdd3wap3a.execute-api.us-east-1.amazonaws.com/M/meio/optimize
```

## Frontend deployment

For a manual AWS Amplify UI deployment, use:

```text
deploy/MEIO-Amplify-Deploy.zip
```

This archive intentionally contains `index.html` directly at its root. It avoids the common mistake of deploying a ZIP that contains an extra parent directory.

After Amplify reports a successful deployment, open the hosted URL and hard-refresh the page. The final HTML contains an invisible marker:

```text
MEIO UI BUILD: 2026-08-23-final-excel-ui
```

Verify the live deployment from PowerShell:

```powershell
curl.exe -s "https://staging.d1jrsof4a5v813.amplifyapp.com/?v=final" | Select-String "MEIO UI BUILD"
```

If the marker is not returned, the intended `index.html` is not what the `staging` URL is serving.

## Backend deployment

`lambda_function.py` contains the Lambda-compatible handler:

```python
lambda_handler(event, context)
```

The repository does not automatically deploy this source. If the AWS Lambda function behind API Gateway is updated, use the exact intended source snapshot and capture the AWS `CodeSha256`/version after deployment.

## CORS and endpoint verification

Browser execution requires API Gateway to allow the Amplify origin:

```text
https://staging.d1jrsof4a5v813.amplifyapp.com/
```

The repository includes:

```bash
python tools/verify_api.py
```

which checks the preflight request and a controlled baseline POST request.

## External browser dependency

The hosted `index.html` loads SheetJS/XLSX 0.18.5 from the CDN referenced in the source. This dependency is used only to parse Excel workbooks in the browser. The Python MEIO backend itself uses only the standard library.

## Deployment evidence boundary

Repository contents demonstrate source and reproducible local behavior. They do not by themselves prove that a particular remote AWS deployment is running the identical source revision. For strict source-to-deployment traceability, record:

- Amplify app and deployment identifier;
- Lambda function/version/alias;
- Lambda `CodeSha256`;
- API Gateway stage/deployment identifier;
- repository commit SHA;
- deployment date/time.
