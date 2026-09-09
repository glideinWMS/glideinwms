#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

sfapi_setup_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SFAPI_HELPERS_DIR="${SFAPI_HELPERS_DIR:-$sfapi_setup_dir}"

sfapi_setup_load_job_metadata() {
    local blahp_job_id="$1"
    local job_payload=""
    local job_date=""
    local job_id=""
    local state_dir=""
    local state_file=""
    local line=""
    local payload=""
    local key=""
    local value=""

    if [ -z "$blahp_job_id" ]; then
        return
    fi

    blahp_job_id="${blahp_job_id#BLAHP_JOBID_PREFIX}"
    case "$blahp_job_id" in
        sfapi/*/*) ;;
        *) return ;;
    esac

    job_payload="${blahp_job_id#sfapi/}"
    job_date="${job_payload%%/*}"
    job_id="${job_payload#*/}"
    if [ -z "$job_date" ] || [ -z "$job_id" ] || [ "$job_date" = "$job_id" ]; then
        return
    fi

    state_dir="${SFAPI_STATE_DIR:-${HOME}/.blah/sfapi_jobs}"
    state_file="$state_dir/${job_date}_${job_id}"
    if [ ! -r "$state_file" ]; then
        return
    fi

    while IFS= read -r line; do
        case "$line" in
            meta::*) ;;
            *) continue ;;
        esac
        payload="${line#meta::}"
        key="${payload%%:*}"
        value="${payload#*:}"
        if [ "$payload" = "$key" ] || [ -z "$value" ]; then
            continue
        fi
        case "$key" in
            auth_mode) export SFAPI_AUTH_MODE="$value" ;;
            auth_file) export SFAPI_AUTH_FILE="$value" ;;
            resource) export SFAPI_RESOURCE="$value" ;;
            transfer_machine) export SFAPI_TRANSFER_MACHINE="$value" ;;
            python) export SFAPI_PYTHON="$value" ;;
            venv) export SFAPI_VENV="$value" ;;
            username) export SFAPI_USERNAME="$value" ;;
            nersc_username) export NERSC_USERNAME="$value" ;;
        esac
    done < "$state_file"
}

sfapi_setup_find_auth_file() {
    local auth_file

    if [ -n "${SFAPI_AUTH_FILE:-}" ]; then
        return
    fi

    for auth_file in /var/lib/gwms-factory/client-proxies/*/*/credential_request_*.txt; do
        if [ -r "$auth_file" ]; then
            SFAPI_AUTH_FILE="$auth_file"
            return
        fi
    done
}

if [ -r "$sfapi_setup_dir/blah_load_config.sh" ]; then
    # shellcheck disable=SC1091
    . "$sfapi_setup_dir/blah_load_config.sh"
fi

sfapi_setup_load_job_metadata "${SFAPI_BLAHP_JOB_ID:-}"

if [ -z "${SFAPI_VENV:-}" ] && [ -x /opt/gwms/sfapi-venv/bin/python ]; then
    SFAPI_VENV=/opt/gwms/sfapi-venv
fi

if [ -n "${SFAPI_VENV:-}" ]; then
    # shellcheck disable=SC1090
    . "$SFAPI_VENV/bin/activate"
fi

if [ -z "${SFAPI_PYTHON:-}" ] && [ -n "${SFAPI_VENV:-}" ] && [ -x "$SFAPI_VENV/bin/python" ]; then
    SFAPI_PYTHON="$SFAPI_VENV/bin/python"
fi

: "${SFAPI_PYTHON:=python3}"
: "${SFAPI_RESOURCE:=perlmutter}"
: "${SFAPI_TRANSFER_MACHINE:=dtns}"
: "${SFAPI_STATE_DIR:=${HOME}/.blah/sfapi_jobs}"

sfapi_setup_find_auth_file

export SFAPI_PYTHON SFAPI_RESOURCE SFAPI_TRANSFER_MACHINE SFAPI_STATE_DIR SFAPI_AUTH_MODE SFAPI_AUTH_FILE SFAPI_USERNAME NERSC_USERNAME SFAPI_ACCOUNT SFAPI_PROJECT SFAPI_QOS SFAPI_CONSTRAINT

if ! "$SFAPI_PYTHON" -c "import sfapi_client" >/dev/null 2>&1; then
    echo "SFAPI setup error: sfapi_client is not importable with $SFAPI_PYTHON" >&2
    return 1 2>/dev/null || exit 1
fi
