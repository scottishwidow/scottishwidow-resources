#!/usr/bin/env bash
# Run the IaC triage taskflow in the published seclab-taskflow-agent image.
#
# Usage:
#   export AI_API_TOKEN=...                                               # an Anthropic API key; no token, no run
#   ./run.sh                                                              # live Trivy scan, propose-only
#   ./run.sh -g report=security/iac_security/fixtures/baseline-scan.json  # replay the committed baseline
#   ./run.sh --lint                                                       # validate offline, no model, no token

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/../../.." && pwd)"
image="${SECLAB_IMAGE:-ghcr.io/githubsecuritylab/seclab-taskflow-agent}"
runs="$here/../runs"

mkdir -p "$runs/logs"

# `load_dotenv(find_dotenv(usecwd=True))` reads .env from the repository root, the container's mount point.
touch -a "$repo_root/.env"

# Bare `-e VAR` so an unset variable stays unset; `-e VAR=""` would shadow a token already in .env.
token_args=()
if [[ -n "${AI_API_TOKEN:-}" ]]; then token_args+=(-e AI_API_TOKEN); fi
if [[ -n "${GH_TOKEN:-}" ]]; then token_args+=(-e GH_TOKEN); fi

# Run as the invoking user so the manifest, sessions and logs are not left owned by root.
exec docker run -i --rm \
    --user "$(id -u):$(id -g)" \
    -e HOME=/data \
    -e XDG_DATA_HOME=/data \
    --mount type=bind,src="$repo_root",dst=/app \
    --mount type=bind,src="$runs",dst=/data/seclab-taskflow-agent \
    -w /app \
    -e LOG_DIR=/data/seclab-taskflow-agent/logs \
    "${token_args[@]}" \
    "$image" \
    -t security.iac_security.taskflow.taskflows.iac_triage "$@"
