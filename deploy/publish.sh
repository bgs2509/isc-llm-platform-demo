#!/usr/bin/env bash
# Build the static site on the GPU host and copy the generated, git-ignored files to the web server.
# Run from a machine that can reach both hosts over SSH.
set -euo pipefail
GPU_HOST=${GPU_HOST:-spark-1}
WEB_HOST=${WEB_HOST:?set WEB_HOST to the SSH name of the web server}
WEB_DIR=${WEB_DIR:-/var/www/isc-1}
ssh "$GPU_HOST" 'cd ~/isc-llm-platform-demo && .venv/bin/python site/build.py'
ssh "$GPU_HOST" 'tar -C ~/isc-llm-platform-demo/site/dist -c .' | ssh "$WEB_HOST" "mkdir -p '$WEB_DIR' && tar -x -C '$WEB_DIR'"
echo "published to $WEB_HOST:$WEB_DIR"
