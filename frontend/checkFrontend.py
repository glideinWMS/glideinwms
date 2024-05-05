#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Check if a glideinFrontend is running

Arguments:
   $1 = work_dir
   $2 = (optional) run mode (defaults to "run")

Exit code:
   0 - Running
   1 - Not running anything
   2 - Not running my types, but another type is indeed running
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
        # if not defined, assume it is the standard running type
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
