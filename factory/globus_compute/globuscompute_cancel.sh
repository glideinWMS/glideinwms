#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2026 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GLOBUS_COMPUTE_BLAHP_JOB_ID="${1:-}"

globus_compute_cancel_escape() {
    printf '%s\n' "$1" | sed "s/ /\\\\\\ /g"
}

globus_compute_emit_cancel_failure() {
    local job_count="$1"
    local job_index="$2"
    local retcode="$3"
    local reason="$4"
    local escaped_output
    escaped_output="$(globus_compute_cancel_escape "$reason")"
    if [ "$job_count" -eq 1 ]; then
        echo " $retcode $escaped_output"
    else
        echo ".$job_index $retcode $escaped_output"
    fi
}

setup_output="$(mktemp)"
if ! "$script_dir/globus_compute_setup.sh" >"$setup_output" 2>&1; then
    setup_reason="$(cat "$setup_output")"
    rm -f "$setup_output"
    job_count=$#
    job_index=0
    for _job_id in "$@"; do
        globus_compute_emit_cancel_failure "$job_count" "$job_index" 1 "$setup_reason"
        job_index=$((job_index + 1))
    done
    exit 0
fi
rm -f "$setup_output"

. "$script_dir/globus_compute_setup.sh"

job_count=$#
job_index=0
for job_id in "$@"; do
    cancel_output="$("$GLOBUS_COMPUTE_PYTHON" "$script_dir/globus_compute_helpers.py" cancel "$job_id" 2>&1)"
    cancel_retcode=$?
    if [ "$cancel_retcode" -eq 0 ]; then
        if [ "$job_count" -eq 1 ]; then
            echo " 0 No\\ error"
        else
            echo ".$job_index 0 No\\ error"
        fi
    else
        globus_compute_emit_cancel_failure "$job_count" "$job_index" "$cancel_retcode" "$cancel_output"
    fi
    job_index=$((job_index + 1))
done
