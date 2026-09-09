#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2026 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

set -eo pipefail

globus_compute_setup_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
globus_compute_env_file="$globus_compute_setup_dir/globus_compute_env.sh"

globus_compute_restore_env_var() {
    local name="$1"
    local was_set="$2"
    local value="$3"

    if [ "$was_set" = "yes" ] && [ -n "$value" ]; then
        export "$name=$value"
    fi
}

globus_compute_endpoint_was_set="${GLOBUS_COMPUTE_ENDPOINT+yes}"
globus_compute_auth_file_was_set="${GLOBUS_COMPUTE_AUTH_FILE+yes}"
globus_compute_function_was_set="${GLOBUS_COMPUTE_FUNCTION+yes}"
globus_compute_helpers_dir_was_set="${GLOBUS_COMPUTE_HELPERS_DIR+yes}"
globus_compute_python_was_set="${GLOBUS_COMPUTE_PYTHON+yes}"
globus_compute_state_dir_was_set="${GLOBUS_COMPUTE_STATE_DIR+yes}"
globus_compute_user_dir_was_set="${GLOBUS_COMPUTE_USER_DIR+yes}"
globus_compute_saved_endpoint="${GLOBUS_COMPUTE_ENDPOINT:-}"
globus_compute_saved_auth_file="${GLOBUS_COMPUTE_AUTH_FILE:-}"
globus_compute_saved_function="${GLOBUS_COMPUTE_FUNCTION:-}"
globus_compute_saved_helpers_dir="${GLOBUS_COMPUTE_HELPERS_DIR:-}"
globus_compute_saved_python="${GLOBUS_COMPUTE_PYTHON:-}"
globus_compute_saved_state_dir="${GLOBUS_COMPUTE_STATE_DIR:-}"
globus_compute_saved_user_dir="${GLOBUS_COMPUTE_USER_DIR:-}"

if [ -f "$globus_compute_env_file" ]; then
    . "$globus_compute_env_file"
fi
globus_compute_restore_env_var GLOBUS_COMPUTE_ENDPOINT "$globus_compute_endpoint_was_set" "$globus_compute_saved_endpoint"
globus_compute_restore_env_var GLOBUS_COMPUTE_AUTH_FILE "$globus_compute_auth_file_was_set" "$globus_compute_saved_auth_file"
globus_compute_restore_env_var GLOBUS_COMPUTE_FUNCTION "$globus_compute_function_was_set" "$globus_compute_saved_function"
globus_compute_restore_env_var GLOBUS_COMPUTE_HELPERS_DIR "$globus_compute_helpers_dir_was_set" "$globus_compute_saved_helpers_dir"
globus_compute_restore_env_var GLOBUS_COMPUTE_PYTHON "$globus_compute_python_was_set" "$globus_compute_saved_python"
globus_compute_restore_env_var GLOBUS_COMPUTE_STATE_DIR "$globus_compute_state_dir_was_set" "$globus_compute_saved_state_dir"
globus_compute_restore_env_var GLOBUS_COMPUTE_USER_DIR "$globus_compute_user_dir_was_set" "$globus_compute_saved_user_dir"

export GLOBUS_COMPUTE_HELPERS_DIR="${GLOBUS_COMPUTE_HELPERS_DIR:-$globus_compute_setup_dir}"
export GLOBUS_COMPUTE_PYTHON="${GLOBUS_COMPUTE_PYTHON:-python3}"
export GLOBUS_COMPUTE_STATE_DIR="${GLOBUS_COMPUTE_STATE_DIR:-${HOME:-.}/.blah/globus_compute_jobs}"
if [ -n "${GLOBUS_COMPUTE_USER_DIR:-}" ]; then
    export GLOBUS_COMPUTE_USER_DIR
fi

if ! "$GLOBUS_COMPUTE_PYTHON" -c "import globus_compute_sdk" >/dev/null 2>&1; then
    echo "Globus Compute setup error: globus_compute_sdk is not importable with $GLOBUS_COMPUTE_PYTHON" >&2
    exit 1
fi

if [ -z "${GLOBUS_COMPUTE_BLAHP_JOB_ID:-}" ]; then
    if [ -z "${GLOBUS_COMPUTE_ENDPOINT:-}" ]; then
        echo "Globus Compute setup error: GLOBUS_COMPUTE_ENDPOINT is not set" >&2
        exit 1
    fi

    if [ -z "${GLOBUS_COMPUTE_AUTH_FILE:-}" ]; then
        echo "Globus Compute setup error: GLOBUS_COMPUTE_AUTH_FILE is not set" >&2
        exit 1
    fi
fi
