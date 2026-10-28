# Runbook 4: gateway errors and team limits

**Alert:** `GatewayErrorRateHigh` (more than 5 % of gateway requests fail for 5 minutes).

## Tell the causes apart

1. **429 for one team**: the team hit its parallel or per-minute limit, or its budget. This is the gateway
   working as designed. Dashboard panel "Gateway failures per second by team and status".
2. **5xx for all teams**: the gateway or the model fails. Check runbook 1 first.
3. **401**: a wrong or expired team key.

## Check

1. `kubectl -n llm-platform get pods` (all `Running`).
2. `kubectl -n llm-platform logs deploy/litellm --tail=100`.

## Fix

1. Legitimate demand above the limit: raise the team's limits in `values.yaml`
   (`tenants[].maxParallelRequests`, `rpmLimit`, `maxBudgetUsd`). The bootstrap job creates keys but does not
   change existing ones; update an existing key through the gateway admin API `/key/update` with the master key:

   ```bash
   kubectl -n llm-platform port-forward svc/litellm 4000:4000 &
   MASTER=$(kubectl -n llm-platform get secret llm-platform-secrets -o jsonpath="{.data.masterKey}" | base64 -d)
   curl -X POST http://127.0.0.1:4000/key/update -H "Authorization: Bearer $MASTER" \
     -H "Content-Type: application/json" \
     -d "{\"key\": \"<team key>\", \"rpm_limit\": 600, \"max_parallel_requests\": 16}"
   ```
2. Gateway pod crashing: `kubectl -n llm-platform describe pod -l app=litellm`; the pod waits for Postgres
   at start, so also check `kubectl -n llm-platform get pods -l app=postgres`.

## Verify

Failure rate below 5 %, a test from the console as the affected team succeeds.
