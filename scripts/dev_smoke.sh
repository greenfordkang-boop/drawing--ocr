#!/usr/bin/env bash
set -euo pipefail

curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/ | head -n 5 >/dev/null

echo "smoke test passed"
