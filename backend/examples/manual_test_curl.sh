#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
USER_ID="${USER_ID:-user-demo}"
PAYLOADS_FILE="${PAYLOADS_FILE:-backend/examples/manual_test_payloads.json}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for this script."
  exit 1
fi

echo "Using BASE_URL=$BASE_URL and USER_ID=$USER_ID"

INTAKE_BODY="$(jq -c '.intake_request' "$PAYLOADS_FILE")"
ITERATE_BODY="$(jq -c '.iterate_request' "$PAYLOADS_FILE")"
FINALIZE_BODY="$(jq -c '.finalize_request' "$PAYLOADS_FILE")"

echo
echo "1) POST /intake"
curl -sS -X POST "$BASE_URL/intake/?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d "$INTAKE_BODY" | tee /tmp/intake_response.json | jq

echo
echo "2) POST /plan/draft"
curl -sS -X POST "$BASE_URL/plan/draft?user_id=$USER_ID" \
  | tee /tmp/draft_response.json | jq

PLAN_ID="$(jq -r '.plan.plan_id' /tmp/draft_response.json)"
if [[ -z "$PLAN_ID" || "$PLAN_ID" == "null" ]]; then
  echo "Failed to obtain plan_id from /plan/draft response."
  exit 1
fi

echo
echo "3) POST /plan/$PLAN_ID/iterate"
curl -sS -X POST "$BASE_URL/plan/$PLAN_ID/iterate?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d "$ITERATE_BODY" | tee /tmp/iterate_response.json | jq

echo
echo "4) POST /plan/$PLAN_ID/finalize"
curl -sS -X POST "$BASE_URL/plan/$PLAN_ID/finalize?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d "$FINALIZE_BODY" | tee /tmp/finalize_response.json | jq

echo
echo "5) GET /plan/$PLAN_ID"
curl -sS "$BASE_URL/plan/$PLAN_ID" | tee /tmp/get_plan_response.json | jq

echo
echo "Done. plan_id=$PLAN_ID"
