#!/usr/bin/env bash
# Smoke test: start the real stack and check that readiness follows Qdrant's state.
#
# Uses its own Compose project, so it never touches the development stack or its
# data. Stop the development stack first (make down): both publish the same ports.
set -euo pipefail

PROJECT="docagent-smoke"
API="http://127.0.0.1:8000"
WAIT_TIMEOUT=120 # seconds to wait for health checks
CURL_TIMEOUT=10  # seconds to wait for one HTTP response

compose() { docker compose -p "$PROJECT" "$@"; }

cleanup() {
    local status=$?
    if [[ $status -ne 0 ]]; then
        echo "Smoke test failed; container logs:" >&2
        compose logs --no-color >&2 || true
    fi
    compose down -v || true
    exit "$status"
}
trap cleanup EXIT

expect_status() {
    local path="$1" expected="$2" actual
    actual=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$CURL_TIMEOUT" "$API$path" || true)
    if [[ "$actual" != "$expected" ]]; then
        echo "FAIL: GET $path returned $actual, expected $expected" >&2
        exit 1
    fi
    echo "ok: GET $path -> $actual"
}

compose up -d --build --wait --wait-timeout "$WAIT_TIMEOUT"

# 1. Full stack up: ready.
expect_status "/ready" 200

# 2. Dependency down: not ready, but still alive.
compose stop qdrant
expect_status "/ready" 503
expect_status "/health" 200

# 3. Dependency back: ready again, without restarting the API.
compose up -d --wait --wait-timeout "$WAIT_TIMEOUT" qdrant
expect_status "/ready" 200

echo "Smoke test passed."
