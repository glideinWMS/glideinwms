#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

script_dir="$(cd "$(dirname "$0")" && pwd)"
export SFAPI_BLAHP_JOB_ID="${1:-}"

sfapi_cancel_escape() {
    echo "$1" | sed "s/ /\\\\\\ /g"
}

sfapi_emit_cancel_failure() {
    local job_count="$1"
    local job_index="$2"
    local retcode="$3"
    local reason="$4"
    local escaped_output
    escaped_output="$(sfapi_cancel_escape "$reason")"
    if [ "$job_count" -eq 1 ]; then
        echo " $retcode $escaped_output"
    else
        echo ".$job_index $retcode $escaped_output"
    fi
}

sfapi_setup_output="$(mktemp)"
# shellcheck disable=SC1091
if ! . "$script_dir/sfapi_setup.sh" >"$sfapi_setup_output" 2>&1; then
    setup_reason="$(cat "$sfapi_setup_output")"
    rm -f "$sfapi_setup_output"
    job_count=$#
    job_index=0
    for _job_id in "$@"; do
        sfapi_emit_cancel_failure "$job_count" "$job_index" 1 "$setup_reason"
        job_index=$((job_index + 1))
    done
    exit 0
fi
rm -f "$sfapi_setup_output"

job_count=$#
job_index=0
for job_id in "$@"; do
    cancel_output="$("$SFAPI_PYTHON" "$SFAPI_HELPERS_DIR/sfapi_helpers.py" cancel "$job_id" 2>&1)"
    cancel_retcode=$?
    if [ "$cancel_retcode" -eq 0 ]; then
        if [ "$job_count" -eq 1 ]; then
            echo " 0 No\\ error"
        else
            echo ".$job_index 0 No\\ error"
        fi
    else
        sfapi_emit_cancel_failure "$job_count" "$job_index" "$cancel_retcode" "$cancel_output"
    fi
    job_index=$((job_index + 1))
done
