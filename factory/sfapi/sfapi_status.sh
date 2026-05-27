#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

script_dir="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$script_dir/sfapi_setup.sh" || exit 1

sfapi_bare_jobid() {
    local job_id="$1"
    job_id="${job_id#BLAHP_JOBID_PREFIX}"
    if [[ "$job_id" == sfapi/*/* ]]; then
        echo "${job_id##*/}"
    else
        echo "$job_id"
    fi
}

sfapi_state_to_blahp() {
    case "$1" in
        PENDING|CONFIGURING) echo 1 ;;
        RUNNING|COMPLETING|STOPPED|SUSPENDED) echo 2 ;;
        CANCELLED) echo 3 ;;
        COMPLETED|FAILED|BOOT_FAIL|NODE_FAIL|PREEMPTED|SPECIAL_EXIT|TIMEOUT) echo 4 ;;
        *) echo 1 ;;
    esac
}

for blahp_job_id in "$@"; do
    bare_job_id="$(sfapi_bare_jobid "$blahp_job_id")"
    status_output="$("$SFAPI_PYTHON" "$SFAPI_HELPERS_DIR/sfapi_helpers.py" status --type job --value "$blahp_job_id" 2>&1)"
    if [ $? -ne 0 ]; then
        echo "1[BatchJobId=\"$bare_job_id\";Reason=\"$status_output\";]"
        continue
    fi

    state="${status_output##* state: }"
    blahp_status="$(sfapi_state_to_blahp "$state")"

    if [ "$blahp_status" = "4" ]; then
        download_output="$("$SFAPI_PYTHON" "$SFAPI_HELPERS_DIR/sfapi_helpers.py" download "$blahp_job_id" 2>&1)"
        if [ $? -ne 0 ]; then
            echo "1[BatchJobId=\"$bare_job_id\";Reason=\"$download_output\";]"
            continue
        fi
    fi

    echo "0[BatchJobId=\"$bare_job_id\";JobStatus=$blahp_status;ExitCode=0;]"
done
