#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Check if a glideinFrontend is running.

This script checks whether a glideinFrontend is running in the specified 
working directory. It optionally allows specifying a run mode.

Usage:
    python script_name.py <work_dir> [run_mode]

Args:
    work_dir (str): The working directory to check for a running glideinFrontend.
    run_mode (str, optional): The desired run mode to check for. Defaults to "run".

Exit Codes:
    0: A glideinFrontend of the specified type is running.
    1: No glideinFrontend is running.
    2: A glideinFrontend of a different type is running.

Examples:
    Check for a glideinFrontend running in "my_work_dir" with the default mode:
        $ python check_glidein_frontend.py my_work_dir

    Check for a glideinFrontend running in "my_work_dir" with a specific mode:
        $ python check_glidein_frontend.py my_work_dir run
"""

import sys
from glideinwms.frontend import glideinFrontendPidLib

if __name__ == "__main__":
    try:
        work_dir = sys.argv[1]
        action_type = glideinFrontendPidLib.get_frontend_action_type(work_dir)
    except Exception:
        print("Not running")
        sys.exit(1)

    if action_type is None:
        # If not defined, assume it is the standard running type
        action_type = "run"

    if len(sys.argv) >= 3:
        req_action_type = sys.argv[2]
    else:
        req_action_type = "run"

    if action_type != req_action_type:
        print('Not running my type (note that conflicting "%s" type is running).' % action_type)
        sys.exit(2)

    print("Running")
    sys.exit(0)
