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

import signal,sys,os,os.path,fcntl,string,time
sys.path.append(os.path.join(sys.path[0],"../lib"))
import glideFactoryPidLib
import glideFactoryConfig
import subprocess
try:
    set
except:
    from sets import Set as set

def get_pids_in_pgid(pgid):
    pids = []
    try:
        p = subprocess.Popen(['pgrep', '-g', pgid], shell=False,
                             stdout=subprocess.PIPE)
        out,err = p.communicate()
        pids = out.strip('\n').split('\n')
    except:
        pass
    return pids


def all_pids_dead(pids):
    for pid in pids:
        if glideFactoryPidLib.pidSupport.check_pid(pid):
            return False
    return True

def kill_and_check_pgid(pgid, signr=signal.SIGTERM, 
                        retries=100, retry_interval=0.2):
    pids = get_pids_in_pgid(pgid)
    alive_pids = set(pids)

    try:
        os.killpg(pgid, signr)
    except OSError:
        pass

    for p in pids:
        p_dead = False
        for retries in range(retries):
            if glideFactoryPidLib.pidSupport.check_pid(p):
                time.sleep(retry_interval)
            else:
                p_dead = True
                alive_pids.remove(p)
                break

        if not p_dead:
            try:
                os.kill(p, signr)
            except OSError:
                # process already dead
                alive_pids.remove(p)
    if len(alive_pids) == 0:
        return 0
    return 1

def main(startup_dir,force=False):
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
        print "Factory did not die withing the timeout"
        return 1

    # retry soft kill the factory... should exit now (5s timeout)
    if (kill_and_check_pgid(factory_pgid, retries=25) == 0):
        return 0

    print "Factory or children still alive... sending hard kill"

    alive_pids = get_pids_in_pgid(factory_pgid)

    for p in alive_pids:
        if glideFactoryPidLib.pidSupport.check_pid(p):
            print "Hard killing %s" % p
            try:
                os.kill(p, signal.SIGKILL)
            except OSError:
                pass # ignore already dead processes

    return 0

if __name__ == '__main__':
    if len(sys.argv)<2:
        print "Usage: stopFactory.py [-force] submit_dir"
        sys.exit(1)

    if len(sys.argv)>2:
        if sys.argv[1]=='-force':
            sys.exit(main(sys.argv[2],True))
        else:
            print "Usage: stopFactory.py [-force] submit_dir"
            sys.exit(1)
    else:
        sys.exit(main(sys.argv[1]))
