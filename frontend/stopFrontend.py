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

# this one should  never throw an exeption
def get_element_pids(work_dir, frontend_pid):
    # get element pids
    frontendDescript = glideinFrontendConfig.FrontendDescript(work_dir)
    groups = string.split(frontendDescript.data['Groups'], ',')
    groups.sort()

    element_pids = {}
    for group in groups:
        try:
            element_pid, element_ppid = glideinFrontendPidLib.get_element_pid(work_dir, group)
        except RuntimeError, e:
            print e
            continue # report error and go to next group
        if element_ppid != frontend_pid:
            print "Group '%s' has an unexpected Parent PID: %s!=%s" % (group, element_ppid, frontend_pid)
            continue # report error and go to next group
        element_pids[group] = element_pid

    return element_pids

def main(work_dir, force=False):
    retries_count = 50
    sleep_in_retries = 0.6
    # get the pids
    try:
        frontend_pid = glideinFrontendPidLib.get_frontend_pid(work_dir)
    except RuntimeError, e:
        print e
        if str(e) == "Frontend not running":
            # Workaround to distinguish when the frontend is not running
            # string must be the same as in glideinFrontendPidLib
            return 2
        return 1
    #print frontend_pid

    if not glideinFrontendPidLib.pidSupport.check_pid(frontend_pid):
        # Frontend already dead
        return 0

    # kill processes
    # first soft kill the frontend (30s timeout, retries_count*sleep_in_retries )
    try:
        os.kill(frontend_pid, signal.SIGTERM)
    except OSError:
        pass # frontend likely already dead

    for retries in range(retries_count):
        if glideinFrontendPidLib.pidSupport.check_pid(frontend_pid):
            time.sleep(sleep_in_retries)
        else:
            return 0 # frontend dead

    if not force:
        print "Frontend did not die after the timeout of %s sec" % (retries_count * sleep_in_retries)
        return 1

    # Retry soft kill the frontend ... should exit now
    print "Frontend still alive ... retrying soft kill"
    try:
        os.kill(frontend_pid, signal.SIGTERM)
    except OSError:
        pass # frontend likely already dead

    for retries in range(retries_count):
        if glideinFrontendPidLib.pidSupport.check_pid(frontend_pid):
            time.sleep(sleep_in_retries)
        else:
            return 0 # frontend dead

    print "Frontend still alive ... sending hard kill"

    element_pids = get_element_pids(work_dir, frontend_pid)
    #print element_pids

    element_keys = element_pids.keys()
    element_keys.sort()

    for element in element_keys:
        if glideinFrontendPidLib.pidSupport.check_pid(element_pids[element]):
            print "Hard killing element %s" % element
            try:
                os.kill(element_pids[element], signal.SIGKILL)
            except OSError:
                pass # ignore already dead processes

    if not glideinFrontendPidLib.pidSupport.check_pid(frontend_pid):
        return 0 # Frontend died

    try:
        os.kill(frontend_pid, signal.SIGKILL)
    except OSError:
        pass # ignore problems
    return 0

USAGE_STRING = """Usage: stopFrontend [-f|force] work_dir
     return values: 0 Frontend stopped, 
         1 unable to stop Frontend or wrong invocation, 2 Frontend was not running
"""
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print USAGE_STRING
        sys.exit(1)

    if len(sys.argv)>2:
        if sys.argv[1]=='-force' or sys.argv[1]=='-f':
            sys.exit(main(sys.argv[2], force=True))
        else:
            print USAGE_STRING
            sys.exit(1)
    else:
        #sys.exit(main(sys.argv[1]))
        # force should be false but keeping old behavior, always forced stop
        sys.exit(main(sys.argv[1], force=True))

