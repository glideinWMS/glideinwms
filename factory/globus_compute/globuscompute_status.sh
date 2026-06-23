#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2026 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

globus_compute_bare_jobid() {
    local job_id="$1"
    if [[ "$job_id" == BLAHP_JOBID_PREFIX* ]]; then
        job_id="${job_id#BLAHP_JOBID_PREFIX}"
    fi
    if [[ "$job_id" == globuscompute/*/* ]]; then
        echo "${job_id##*/}"
    else
        echo "$job_id"
    fi
}

globus_compute_escape_reason() {
    echo "$1" | tr '\n' ' ' | sed 's/\\/\\\\/g; s/"/\\"/g'
}

globus_compute_emit_failure() {
    local blahp_job_id="$1"
    local reason="$2"
    local bare_job_id
    bare_job_id="$(globus_compute_bare_jobid "$blahp_job_id")"
    echo "1[BatchJobId=\"$bare_job_id\";Reason=\"$(globus_compute_escape_reason "$reason")\";]"
}

blahp_job_id="${1:-unknown}"
export GLOBUS_COMPUTE_BLAHP_JOB_ID="$blahp_job_id"
setup_output="$(mktemp)"
if ! "$script_dir/globus_compute_setup.sh" >"$setup_output" 2>&1; then
    setup_reason="$(cat "$setup_output")"
    rm -f "$setup_output"
    globus_compute_emit_failure "$blahp_job_id" "$setup_reason"
    exit 0
fi
rm -f "$setup_output"

. "$script_dir/globus_compute_setup.sh"

exec "$GLOBUS_COMPUTE_PYTHON" "$script_dir/globus_compute_helpers.py" status "$blahp_job_id"
