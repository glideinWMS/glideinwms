#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

script_dir="$(cd "$(dirname "$0")" && pwd)"

if [ ! -r "$script_dir/sfapi_helpers.py" ] || [ ! -x "$script_dir/sfapi_submit.sh" ]; then
    echo "1 SFAPI setup error: required SFAPI BLAHP scripts are not installed"
    exit 0
fi

echo "0 No error"
exit 0
