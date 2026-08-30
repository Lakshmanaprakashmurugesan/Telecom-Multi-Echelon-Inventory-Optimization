#!/usr/bin/env python3
"""Verify the configured API Gateway endpoint from outside the browser.

This utility does not modify the MEIO implementation. It sends an OPTIONS
preflight and the retained baseline POST request, then reports status/CORS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://7qdd3wap3a.execute-api.us-east-1.amazonaws.com/M/meio/optimize"
AMPLIFY_ORIGIN = "https://staging.d1jrsof4a5v813.amplifyapp.com/"
ROOT = Path(__file__).resolve().parents[1]
REQUEST_FILE = ROOT / "evidence" / "baseline" / "request.json"


def request(req: Request):
    try:
        with urlopen(req, timeout=30) as response:
            return response.status, dict(response.headers.items()), response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), body
    except URLError as exc:
        raise SystemExit(f"Network error: {exc}") from exc


def main() -> int:
    preflight = Request(
        API_URL,
        method="OPTIONS",
        headers={
            "Origin": AMPLIFY_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    status, headers, _ = request(preflight)
    print(f"OPTIONS status: {status}")
    print("OPTIONS allow-origin:", headers.get("access-control-allow-origin", "<missing>"))
    print("OPTIONS allow-methods:", headers.get("access-control-allow-methods", "<missing>"))

    payload = REQUEST_FILE.read_bytes()
    post = Request(
        API_URL,
        data=payload,
        method="POST",
        headers={
            "Origin": AMPLIFY_ORIGIN,
            "Content-Type": "application/json",
        },
    )
    status, headers, body = request(post)
    print(f"POST status: {status}")
    print("POST allow-origin:", headers.get("access-control-allow-origin", "<missing>"))

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("POST body is not valid JSON")
        print(body[:1000])
        return 1

    print("POST message:", data.get("message", data.get("error", "<no message>")))
    if status == 200 and data.get("message") == "MEIO optimization completed":
        print("API verification: PASS")
        return 0
    print("API verification: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
