#!/usr/bin/env bash
# Run the IaC triage taskflow in the published seclab-taskflow-agent image.
#
# Adapted from the framework's own docker/run.sh, with two changes this
# pipeline needs:
#
#   * The repository root is mounted, and stays the working directory, because
#     the deterministic tasks read `live/` and `modules/` for the Terraform
#     corpus (ADR-0008), and the taskflow is addressed by its full dotted name
#     from that root.
#   * The agent's data directory is bound to `../runs/` here, so the run
#     manifest that `collect_verdicts.py` reads survives the container, in the
#     same place the collected verdicts are written.
#
# Usage:
#   export AI_API_TOKEN=...            # an Anthropic API key; no token, no run
#   ./run.sh                           # reproducible, propose-only
#   ./run.sh -g report=                # live Trivy scan instead of the baseline
#   ./run.sh --lint                    # validate offline, no model, no token

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/../../.." && pwd)"
image="${SECLAB_IMAGE:-ghcr.io/githubsecuritylab/seclab-taskflow-agent}"
runs="$here/../runs"

mkdir -p "$runs/logs"

# The framework touches .env in its working directory, which is the repository
# root: `load_dotenv(find_dotenv(usecwd=True))` starts at cwd, and the
# container's cwd is the mount root, not this directory.
touch -a "$repo_root/.env"

# Forward a token only when the host actually has one, using bare `-e VAR` so an
# unset variable stays unset in the container.
#
# `-e VAR=""` would be wrong, and silently so. The framework calls
# `load_dotenv(find_dotenv(usecwd=True))`, which does *not* override a variable
# already present in the environment -- and an empty string counts as present.
# Passing an empty value would therefore shadow a token supplied in .env, and
# the run would fail with "AI_API_TOKEN environment variable is not set" while
# the file holding it sat in the working directory.
token_args=()
if [[ -n "${AI_API_TOKEN:-}" ]]; then token_args+=(-e AI_API_TOKEN); fi
if [[ -n "${GH_TOKEN:-}" ]]; then token_args+=(-e GH_TOKEN); fi

# Run as the invoking user, not root. Without this the manifest, sessions and
# logs come back owned by root, and `collect_verdicts.py` -- which runs on the
# host -- can read them but the user cannot delete them.
#
# That in turn is why the data directory is bound under /data rather than at the
# image's default /root/.local/share: /root is mode 700, so a non-root user
# cannot traverse into it to reach a mount underneath. XDG_DATA_HOME moves
# platformdirs' idea of the data directory to match.
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
