#!/usr/bin/env bash
# Produce the normalised, partitioned findings the taskflow fans out over.
#
#   TRIVY_REPORT unset  scan the working tree with Trivy (a live run)
#   TRIVY_REPORT=<path> replay a committed report (a reproducible run)

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
triage_dir="$(dirname "$here")"
repo_root="$(dirname "$(dirname "$triage_dir")")"

report="${TRIVY_REPORT:-}"

if [[ -n "$report" ]]; then
    [[ -f "$report" ]] || { echo "no such Trivy report: $report" >&2; exit 1; }
    exec python3 "$triage_dir/normalise.py" "$report"
fi

command -v trivy >/dev/null 2>&1 || {
    echo "trivy not on PATH and TRIVY_REPORT unset: nothing to scan" >&2
    exit 1
}

cd "$repo_root"
trivy config --format json . | python3 "$triage_dir/normalise.py"
