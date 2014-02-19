#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Stop a running glideinFactory
# 
# Arguments:
#   $1 = glidein submit_dir (i.e. factory dir)
#
# Author:
#   Igor Sfiligoi May 6th 2008
#

import signal
import sys
import os
import os.path
import fcntl
import string
import time
import subprocess

sys.path.append(os.path.join(sys.path[0],"../../"))
from glideinwms.factory import glideFactoryPidLib
from glideinwms.factory import glideFactoryConfig

def all_pids_in_pgid_dead(pgid):
    # return 1 if there are no pids in the pgid still alive
    # 0 otherwise 
    devnull = os.open(os.devnull, os.O_RDWR)
    return subprocess.call(["pgrep", "-g", "%s" % pgid],
                            stdout=devnull,
                            stderr=devnull)


def kill_and_check_pgid(pgid, signr=signal.SIGTERM, 
                        retries=100, retry_interval=0.5):
    # return 0 if all pids in pgid are dead
    # 50 sec timeout by default

    try:
        os.killpg(pgid, signr)
    except OSError:
        # can check err.errno
        # errno.EPERM if it is not allowed
        # errno.ESRCH if the process does not exist
        pass

    for retries in range(retries):
        if all_pids_in_pgid_dead(pgid)==1:
            return 0
        else:
            time.sleep(retry_interval)

    return 1


def main(startup_dir,force=True):
    # get the pids
    try:
        factory_pid=glideFactoryPidLib.get_factory_pid(startup_dir)
    except RuntimeError, e:
        print e
        if str(e) == "Factory not running":
            # Workaround to distinguish when the factory is not running
            # string must be the same as in glideFactoryPidLib
            return 2
        return 1
    #print factory_pid

    factory_pgid = os.getpgid(factory_pid)

    if not glideFactoryPidLib.pidSupport.check_pid(factory_pid):
        # Factory already dead
        return 0

    # kill processes
    # first soft kill the factoryprocess group  (50s timeout)
    if (kill_and_check_pgid(factory_pgid) == 0):
        return 0

    if not force:
        print "Factory did not die within the timeout"
        return 1

    # retry soft kill the factory... should exit now (5s timeout)
    if (kill_and_check_pgid(factory_pgid, retries=30, signr=signal.SIGTERM) == 0):
        return 0

    print "Factory or children still alive... sending hard kill"

    try:
        os.killpg(factory_pgid, signal.SIGKILL)
    except OSError:
        # in case they died between the last check and now
        pass

    return 0

USAGE_STRING = """Usage: stopFactory [-f|-force] submit_dir
     return values: 0 Factory stopped, 
         1 unable to stop Factory or wrong invocation, 2 Factory was not running
"""
if __name__ == '__main__':
    if len(sys.argv)<2:
        print USAGE_STRING
        sys.exit(1)

    if len(sys.argv)>2:
        if sys.argv[1]=='-force' or sys.argv[1]=='-f':
            sys.exit(main(sys.argv[2],True))
        else:
            print USAGE_STRING
            sys.exit(1)
    else:
        sys.exit(main(sys.argv[1]))
