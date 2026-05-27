#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

script_dir="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
if ! . "$script_dir/sfapi_setup.sh"; then
    echo "1 SFAPI status error: setup failed"
    exit 0
fi

status_output="$("$SFAPI_PYTHON" "$SFAPI_HELPERS_DIR/sfapi_helpers.py" status --type resource --value "$SFAPI_RESOURCE" 2>&1)"
if [ $? -eq 0 ]; then
    echo "0 No error"
else
    echo "1 SFAPI status error: $status_output"
fi

exit 0
