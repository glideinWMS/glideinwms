#!/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: stopFactory.py,v 1.7.24.1 2010/08/31 18:49:16 parag Exp $
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

def main(startup_dir):
    # get the pids
    try:
        factory_pid=glideFactoryPidLib.get_factory_pid(startup_dir)
    except RuntimeError, e:
        print e
        return 1
    #print factory_pid

    entry_pids=get_entry_pids(startup_dir,factory_pid)
    #print entry_pids

    entry_keys=entry_pids.keys()
    entry_keys.sort()

    # kill processes
    # first soft kill the factory (5s timeout)
    os.kill(factory_pid,signal.SIGTERM)
    for retries in range(25):
        if glideFactoryPidLib.pidSupport.check_pid(factory_pid):
            time.sleep(0.2)
        else:
            break # factory dead

    # now check the entries (5s timeout)
    entries_alive=False
    for entry in entry_keys:
        if glideFactoryPidLib.pidSupport.check_pid(entry_pids[entry]):
            #print "Entry '%s' still alive, sending SIGTERM"%entry
            os.kill(entry_pids[entry],signal.SIGTERM)
            entries_alive=True
    if entries_alive:
        for retries in range(25):
            entries_alive=False
            for entry in entry_keys:
                if glideFactoryPidLib.pidSupport.check_pid(entry_pids[entry]):
                    entries_alive=True
            if entries_alive:
                time.sleep(0.2)
            else:
                break # all entries dead
        
    # final check for processes
    if glideFactoryPidLib.pidSupport.check_pid(factory_pid):
        print "Hard killed factory"
        os.kill(factory_pid,signal.SIGKILL)
    for entry in entry_keys:
        if glideFactoryPidLib.pidSupport.check_pid(entry_pids[entry]):
            print "Hard killed entry '%s'"%entry
            os.kill(entry_pids[entry],signal.SIGKILL)
    return 0
        

if __name__ == '__main__':
    if len(sys.argv)<2:
        print "Usage: stopFactory.py submit_dir"
        sys.exit(1)

    sys.exit(main(sys.argv[1]))
