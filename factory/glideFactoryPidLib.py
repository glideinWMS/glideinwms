#
# Description:
#  Handle factory pids
# 
# Author:
#   Igor Sfiligoi Jul 9th 2008
#

import sys,os,os.path,fcntl

#
# Verify if the system knows about a pid
#
def check_pid(pid):
    return os.path.isfile("/proc/%s/cmdline"%pid)

#
# Find and return the factory pid
#
# return pid
# raises an exception if it cannot find it
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

#
# Find and return the factory entry pid 
#
# returns (pid, parent pid)
# raises an exception if it cannot find it
def get_entry_pid(startup_dir,entry_name):
    lock_fname=os.path.join(startup_dir,"entry_%s/factory.lock"%entry_name)

    if not os.path.isfile(lock_fname):
        raise RuntimeError, "Entry '%s' never started"%entry_name

    fd=open(lock_fname,"r")
    try:
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.close()
        # if I can get a lock, it means that there is no factory 
        raise RuntimeError, "Entry '%s' not running"%entry_name
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

