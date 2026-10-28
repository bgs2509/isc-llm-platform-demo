# Runbook 1: model endpoint down

**Alert:** `ModelEndpointDown` (Prometheus cannot scrape the model server for 1 minute).
**Impact:** every team gets errors; gateway failures rise.

## Check

1. Is the model server alive on the GPU host?
   `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18300/v1/models` (expect 200; the port is the
   one the server listens on).
2. Is the relay listening for the cluster? `ss -ltn | grep 18310` (expect a listener on the cluster network gateway address).
3. From inside the cluster:
   `kubectl -n llm-platform run probe --rm -i --restart=Never --image=curlimages/curl --command -- curl -s -m 5 -o /dev/null -w "%{http_code}\n" http://172.23.0.1:18310/v1/models`

## Fix

1. Server down: start the model container the way its owner started it; wait until `/v1/models` answers.
2. Relay down: `nohup python3 tools/model_forward.py 172.23.0.1 18310 127.0.0.1 18300 > tools/model_forward.log 2>&1 &`.
   The relay does not start after a reboot of the host.
3. GPU exporter down (the `gpu` target is down): `nohup python3 tools/gpu_exporter.py 172.23.0.1 18311 > tools/gpu_exporter.log 2>&1 &`.

## Verify

The `vllm` target is `up` in Prometheus (`/targets`), the alert resolves, and a one-request test from the
console succeeds.

## Escalate

If the server container will not start, the problem is on the GPU host (driver, memory): check `nvidia-smi`
and the container log, then call the host owner.
