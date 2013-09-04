#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Stop a running glideinFrontend
# 
# Arguments:
#   $1 = work_dir
#
# Author:
#   Igor Sfiligoi
#

import signal
import sys
import os
import string
import time

sys.path.append(os.path.join(sys.path[0],"../.."))

from glideinwms.frontend import glideinFrontendPidLib
from glideinwms.frontend import glideinFrontendConfig
from glideinwms.lib.pidSupport import kill_and_check_pgid

def main(work_dir, force=False):
    # get the pids
    try:
        frontend_pid = glideinFrontendPidLib.get_frontend_pid(work_dir)
    except RuntimeError, e:
        print e
        return 1
    #print frontend_pid

    frontend_pgid = os.getpgid(frontend_pid)

    if not glideinFrontendPidLib.pidSupport.check_pid(frontend_pid):
        # Frontend already dead
        return 0

    # kill processes
    # first soft kill the frontend (20s timeout)
    if (kill_and_check_pgid(frontend_pgid) == 0):
        return 0

    if not force:
        print "Frontend did not die within the timeout"
        return 1

    # Retry soft kill the frontend ... should exit now
    print "Frontend still alive ... retrying soft kill"
    if (kill_and_check_pgid(frontend_pgid, retries=25) == 0):
        return 0

    print "Frontend still alive ... sending hard kill"

    try:
        os.killpg(frontend_pgid, signal.SIGKILL)
    except OSError:
        pass # ignore problems
    return 0

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "Usage: stopFrontend.py work_dir"
        sys.exit(1)

    sys.exit(main(sys.argv[1], force=True))
