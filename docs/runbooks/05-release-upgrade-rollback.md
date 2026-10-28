# Runbook 5: upgrade and roll back a release

## Upgrade

1. Change `values.yaml` or the templates.
2. `helm lint chart/llm-platform`
3. `helm upgrade llm-platform chart/llm-platform -n llm-platform --wait`

Random secrets (master key, team keys, passwords) are kept across upgrades.

## Roll back

1. `helm history llm-platform -n llm-platform` — find the last good revision.
2. `helm rollback llm-platform <revision> -n llm-platform --wait`

## Verify

All pods `Running`, Prometheus targets `up`, a one-request test from the console succeeds.

## Notes

1. The database lives on a 1 GiB volume; deleting the Postgres pod keeps it, deleting the release's
   volume claim loses keys, spend and budgets.
2. To rotate a team key: remove the entry `key-<team>` from the Secret and run `helm upgrade`; the bootstrap
   job creates the new key. The old key stays valid in the gateway until it is deleted through the gateway admin
   API (see the LiteLLM documentation for key deletion).
