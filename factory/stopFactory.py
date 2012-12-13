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

sys.path.append(os.path.join(sys.path[0],"../../"))
from glideinwms.factory import glideFactoryPidLib
from glideinwms.factory import glideFactoryConfig

# this one should  never throw an exeption
def get_entry_pids(startup_dir,factory_pid):
    # get entry pids
    glideFactoryConfig.factoryConfig.glidein_descript_file=os.path.join(startup_dir,glideFactoryConfig.factoryConfig.glidein_descript_file)
    glideinDescript=glideFactoryConfig.GlideinDescript()
    entries=string.split(glideinDescript.data['Entries'],',')
    entries.sort()

    entry_pids={}
    for entry in entries:
        try:
            entry_pid,entry_ppid=glideFactoryPidLib.get_entry_pid(startup_dir,entry)
        except RuntimeError,e:
            print e
            continue # report error and fgo to next entry
        if entry_ppid!=factory_pid:
            print "Entry '%s' has an unexpected Parent PID: %s!=%s"%(entry,entry_ppid,factory_pid)
            continue # report error and go to next entry
        entry_pids[entry]=entry_pid

    return entry_pids

def main(startup_dir,force=False):
    # get the pids
    try:
        factory_pid=glideFactoryPidLib.get_factory_pid(startup_dir)
    except RuntimeError, e:
        print e
        return 1
    #print factory_pid

    if not glideFactoryPidLib.pidSupport.check_pid(factory_pid):
        # Factory already dead
        return 0

    # kill processes
    # first soft kill the factory (20s timeout)
    try:
        os.kill(factory_pid,signal.SIGTERM)
    except OSError:
        pass # factory likely already dead

    for retries in range(100):
        if glideFactoryPidLib.pidSupport.check_pid(factory_pid):
            time.sleep(0.2)
        else:
            return 0 # factory dead

    if not force:
        print "Factory did not dye withing the timeout"
        return 1

    # retry soft kill the factory... should exit now (5s timeout)
    print "Retrying a soft kill"
    try:
        os.kill(factory_pid,signal.SIGTERM)
    except OSError:
        pass # factory likely already dead

    for retries in range(25):
        if glideFactoryPidLib.pidSupport.check_pid(factory_pid):
            time.sleep(0.2)
        else:
            return 0 # factory dead
    
    print "Factory still alive... sending hard kill"

    entry_pids=get_entry_pids(startup_dir,factory_pid)
    #print entry_pids

    entry_keys=entry_pids.keys()
    entry_keys.sort()

    for entry in entry_keys:
        if glideFactoryPidLib.pidSupport.check_pid(entry_pids[entry]):
            print "Hard killing entry %s"%entry
            try:
                os.kill(entry_pids[entry],signal.SIGKILL)
            except OSError:
                pass # ignore already dead processes

    if not glideFactoryPidLib.pidSupport.check_pid(factory_pid):
        return 0 # factory died

    try:
        os.kill(factory_pid,signal.SIGKILL)
    except OSError:
        pass # ignore problems
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
