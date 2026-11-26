#!/usr/bin/env bash
# Smoke test: start the real stack, check that readiness follows Qdrant's state,
# and check that uploaded PDFs are rendered and survive an API restart.
#
# Uses its own Compose project, so it never touches the development stack or its
# data. Stop the development stack first (make down): both publish the same ports.
set -euo pipefail

PROJECT="docagent-smoke"
API="http://127.0.0.1:8000"
WAIT_TIMEOUT=120 # seconds to wait for health checks
CURL_TIMEOUT=10  # seconds to wait for one HTTP response
FIXTURE="tests/fixtures/sample.pdf"
NOT_A_PDF="README.md"

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

expect_upload() {
    local file="$1" expected="$2" actual
    actual=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$CURL_TIMEOUT" \
        -F "file=@$file;type=application/pdf" "$API/documents" || true)
    if [[ "$actual" != "$expected" ]]; then
        echo "FAIL: POST /documents with $file returned $actual, expected $expected" >&2
        exit 1
    fi
    echo "ok: POST /documents ($file) -> $actual"
}

# Fail early with a clear message, rather than curl's "000" later.
[[ -f "$FIXTURE" ]] || { echo "FAIL: missing $FIXTURE (run from the repo root)" >&2; exit 1; }
doc_id=$(sha256sum "$FIXTURE" | cut -d' ' -f1)

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

# 4. Upload: a new PDF is rendered (201), the same PDF is found again (200),
#    and a file that is not a PDF is rejected (422).
expect_upload "$FIXTURE" 201
expect_upload "$FIXTURE" 200
expect_upload "$NOT_A_PDF" 422

# 5. Rendered pages are on the volume, not in the container: remove the API
#    container (its own filesystem goes with it), start a new one, and the
#    document is still there.
compose rm -f -s api
compose up -d --wait --wait-timeout "$WAIT_TIMEOUT" api
expect_status "/documents/$doc_id" 200

echo "Smoke test passed."
