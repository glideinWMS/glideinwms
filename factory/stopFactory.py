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

sys.path.append(os.path.join(sys.path[0],"../../"))
from glideinwms.factory import glideFactoryPidLib
from glideinwms.factory import glideFactoryConfig
from glideinwms.lib.pidSupport import kill_and_check_pgid

def main(startup_dir,force=True):
    # get the pids
    try:
        factory_pid=glideFactoryPidLib.get_factory_pid(startup_dir)
    except RuntimeError, e:
        print e
        return 1
    #print factory_pid

    factory_pgid = os.getpgid(factory_pid)

    if not glideFactoryPidLib.pidSupport.check_pid(factory_pid):
        # Factory already dead
        return 0

    # kill processes
    # first soft kill the factoryprocess group  (20s timeout)
    if (kill_and_check_pgid(factory_pgid) == 0):
        return 0

    if not force:
        print "Factory did not die within the timeout"
        return 1

    # retry soft kill the factory... should exit now (5s timeout)
    if (kill_and_check_pgid(factory_pgid, retries=25) == 0):
        return 0

    print "Factory or children still alive... sending hard kill"

    try:
        os.killpg(factory_pgid, signal.SIGKILL)
    except OSError:
        # in case they died between the last check and now
        pass

    return 0

if __name__ == '__main__':
    if len(sys.argv)<2:
        print "Usage: stopFactory.py submit_dir"
        sys.exit(1)

    if len(sys.argv)>2:
        if sys.argv[1]=='-force':
            sys.exit(main(sys.argv[2],True))
        else:
            print "Usage: stopFactory.py submit_dir"
            sys.exit(1)
    else:
        sys.exit(main(sys.argv[1]))
