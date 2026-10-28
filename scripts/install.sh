#!/usr/bin/env bash
# Build the console image, load images into the kind cluster and install the chart.
set -euo pipefail
cd "$(dirname "$0")/.."
BIN="${HOME}/bin"
CLUSTER=llm-demo
docker build -q -t llm-platform-console:0.1.0 console/
for img in llm-platform-console:0.1.0 ghcr.io/berriai/litellm:main-latest; do
  docker image inspect "$img" >/dev/null 2>&1 || docker pull "$img"
  "$BIN/kind" load docker-image "$img" --name "$CLUSTER"
done
"$BIN/helm" upgrade --install llm-platform chart/llm-platform \
  --kube-context "kind-$CLUSTER" -n llm-platform --create-namespace --wait --timeout 15m
