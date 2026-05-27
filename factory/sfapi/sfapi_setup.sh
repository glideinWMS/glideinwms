#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

sfapi_setup_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SFAPI_HELPERS_DIR="${SFAPI_HELPERS_DIR:-$sfapi_setup_dir}"

if [ -r "$sfapi_setup_dir/blah_load_config.sh" ]; then
    # shellcheck disable=SC1091
    . "$sfapi_setup_dir/blah_load_config.sh"
fi

if [ -n "${SFAPI_VENV:-}" ]; then
    # shellcheck disable=SC1090
    . "$SFAPI_VENV/bin/activate"
fi

: "${SFAPI_PYTHON:=python3}"
: "${SFAPI_RESOURCE:=perlmutter}"
: "${SFAPI_TRANSFER_MACHINE:=dtns}"
: "${SFAPI_STATE_DIR:=${HOME}/.blah/sfapi_jobs}"

export SFAPI_PYTHON SFAPI_RESOURCE SFAPI_TRANSFER_MACHINE SFAPI_STATE_DIR SFAPI_AUTH_MODE SFAPI_AUTH_FILE SFAPI_USERNAME NERSC_USERNAME

if ! "$SFAPI_PYTHON" -c "import sfapi_client" >/dev/null 2>&1; then
    echo "SFAPI setup error: sfapi_client is not importable with $SFAPI_PYTHON" >&2
    return 1 2>/dev/null || exit 1
fi
