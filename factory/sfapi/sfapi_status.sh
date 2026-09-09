#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

script_dir="$(cd "$(dirname "$0")" && pwd)"
export SFAPI_BLAHP_JOB_ID="${1:-}"

sfapi_bare_jobid() {
    local job_id="$1"
    job_id="${job_id#BLAHP_JOBID_PREFIX}"
    if [[ "$job_id" == sfapi/*/* ]]; then
        echo "${job_id##*/}"
    else
        echo "$job_id"
    fi
}

sfapi_escape_reason() {
    local reason="$1"
    reason="${reason//$'\n'/ }"
    reason="${reason//\\/\\\\}"
    reason="${reason//\"/\\\"}"
    echo "$reason"
}

sfapi_emit_failure() {
    local blahp_job_id="$1"
    local reason="$2"
    local bare_job_id
    bare_job_id="$(sfapi_bare_jobid "$blahp_job_id")"
    echo "1[BatchJobId=\"$bare_job_id\";Reason=\"$(sfapi_escape_reason "$reason")\";]"
}

sfapi_extract_state() {
    local status_output="$1"
    case "$status_output" in
        SFAPI_STATUS:*)
            echo "${status_output##*:}"
            return 0
            ;;
        *" state: "*)
            echo "${status_output##* state: }"
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

sfapi_state_to_blahp() {
    case "$1" in
        PENDING*|CONFIGURING*|REQUEUED*|RESIZING*) echo 1 ;;
        RUNNING*|COMPLETING*|STOPPED*|SUSPENDED*) echo 2 ;;
        CANCELLED*) echo 3 ;;
        COMPLETED*|FAILED*|BOOT_FAIL*|DEADLINE*|NODE_FAIL*|OUT_OF_MEMORY*|PREEMPTED*|SPECIAL_EXIT*|TIMEOUT*) echo 4 ;;
        *) echo 1 ;;
    esac
}

sfapi_state_to_exit_code() {
    case "$1" in
        COMPLETED*) echo 0 ;;
        *) echo 1 ;;
    esac
}

sfapi_setup_output="$(mktemp)"
# shellcheck disable=SC1091
if ! . "$script_dir/sfapi_setup.sh" >"$sfapi_setup_output" 2>&1; then
    setup_reason="$(cat "$sfapi_setup_output")"
    rm -f "$sfapi_setup_output"
    for blahp_job_id in "$@"; do
        sfapi_emit_failure "$blahp_job_id" "$setup_reason"
    done
    exit 0
fi
rm -f "$sfapi_setup_output"

for blahp_job_id in "$@"; do
    bare_job_id="$(sfapi_bare_jobid "$blahp_job_id")"
    status_output="$("$SFAPI_PYTHON" "$SFAPI_HELPERS_DIR/sfapi_helpers.py" status --type job --value "$blahp_job_id" 2>&1)"
    if [ $? -ne 0 ]; then
        sfapi_emit_failure "$blahp_job_id" "$status_output"
        continue
    fi

    if ! state="$(sfapi_extract_state "$status_output")"; then
        sfapi_emit_failure "$blahp_job_id" "Unexpected SFAPI status result: $status_output"
        continue
    fi
    blahp_status="$(sfapi_state_to_blahp "$state")"
    exit_code=0

    if [ "$blahp_status" = "4" ]; then
        exit_code="$(sfapi_state_to_exit_code "$state")"
        download_output="$("$SFAPI_PYTHON" "$SFAPI_HELPERS_DIR/sfapi_helpers.py" download "$blahp_job_id" 2>&1)"
        if [ $? -ne 0 ]; then
            sfapi_emit_failure "$blahp_job_id" "$download_output"
            continue
        fi
    fi

    echo "0[BatchJobId=\"$bare_job_id\";JobStatus=$blahp_status;ExitCode=$exit_code;]"
done
