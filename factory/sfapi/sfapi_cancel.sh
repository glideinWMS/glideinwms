#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

script_dir="$(cd "$(dirname "$0")" && pwd)"
export SFAPI_BLAHP_JOB_ID="${1:-}"
# shellcheck disable=SC1091
. "$script_dir/sfapi_setup.sh" || exit 1

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
        escaped_output="$(echo "$cancel_output" | sed "s/ /\\\\\\ /g")"
        if [ "$job_count" -eq 1 ]; then
            echo " $cancel_retcode $escaped_output"
        else
            echo ".$job_index $cancel_retcode $escaped_output"
        fi
    fi
    job_index=$((job_index + 1))
done
