#!/bin/env python
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
import glideFactoryConfig

def check_pid(pid):
    return os.path.isfile("/proc/%s/cmdline"%pid)

def get_gfactory_pid(startup_dir):
    lock_fname=os.path.join(startup_dir,"glideinWMS.lock")

    if not os.path.isfile(lock_fname):
        raise RuntimeError, "glideinFactory never started"

    fd=open(lock_fname,"r")
    try:
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.close()
        # if I can get a lock, it means that there is no factory 
        raise RuntimeError, "glideinFactory not running"
    except IOError:
        lines=fd.readlines()
        fd.close()

    if len(lines)<2:
        raise RuntimeError, "Corrupted lock file '%s': too short"%lock_fname

    pidarr=lines[0].split()
    if (len(pidarr)!=2) or (pidarr[0]!='PID:'):
        raise RuntimeError, "Corrupted lock file '%s': no PID"%lock_fname

    try:
        pid=long(pidarr[1])
    except:
        raise RuntimeError, "Corrupted lock file '%s': invalid PID"%lock_fname

    if not check_pid(pid):
        raise RuntimeError, "glideinFactory (PID %s) not running"%pid
    
    return pid

# returns (pid, parent pid)
def get_entry_pid(startup_dir,entry_name):
    lock_fname=os.path.join(startup_dir,"entry_%s/factory.lock"%entry_name)

    if not os.path.isfile(lock_fname):
        raise RuntimeError, "Entry '%s' never started"%entry_name

    fd=open(lock_fname,"r")
    try:
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.close()
        # if I can get a lock, it means that there is no factory 
        raise RuntimeError, "Entry '%s' not running"%s
    except IOError:
        lines=fd.readlines()
        fd.close()

    if len(lines)<3:
        raise RuntimeError, "Corrupted lock file '%s': too short"%lock_fname

    pidarr=lines[0].split(':')
    if (len(pidarr)!=2) or (pidarr[0]!='PID'):
        raise RuntimeError, "Corrupted lock file '%s': no PID"%lock_fname

    try:
        pid=long(pidarr[1])
    except:
        raise RuntimeError, "Corrupted lock file '%s': invalid PID"%lock_fname

    if not check_pid(pid):
        raise RuntimeError, "glideinFactory (PID %s) not running"%pid
    
    ppidarr=lines[1].split(':')
    if (len(ppidarr)!=2) or (ppidarr[0]!='Parent PID'):
        raise RuntimeError, "Corrupted lock file '%s': no Parent PID"%lock_fname

    try:
        ppid=long(ppidarr[1])
    except:
        raise RuntimeError, "Corrupted lock file '%s': invalid Parent PID"%lock_fname

    return (pid,ppid)

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
            entry_pid,entry_ppid=get_entry_pid(startup_dir,entry)
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
        factory_pid=get_gfactory_pid(startup_dir)
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
        if check_pid(factory_pid):
            time.sleep(0.2)
        else:
            break # factory dead

    # now check the entries (5s timeout)
    entries_alive=False
    for entry in entry_keys:
        if check_pid(entry_pids[entry]):
            #print "Entry '%s' still alive, sending SIGTERM"%entry
            os.kill(entry_pids[entry],signal.SIGTERM)
            entries_alive=True
    if entries_alive:
        for retries in range(25):
            entries_alive=False
            for entry in entry_keys:
                if check_pid(entry_pids[entry]):
                    entries_alive=True
            if entries_alive:
                time.sleep(0.2)
            else:
                break # all entries dead
        
    # final check for processes
    if check_pid(factory_pid):
        print "Hard killed factory"
        os.kill(factory_pid,signal.SIGKILL)
    for entry in entry_keys:
        if check_pid(entry_pids[entry]):
            print "Hard killed entry '%s'"%entry
            os.kill(entry_pids[entry],signal.SIGKILL)
    return
        

if __name__ == '__main__':
    if len(sys.argv)<2:
        print "Usage: stopFactory.py submit_dir"
        sys.exit(1)

    main(sys.argv[1])
