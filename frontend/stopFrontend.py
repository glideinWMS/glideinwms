#!/bin/env python
#
# Description:
#   Stop a running glideinFrontend
# 
# Arguments:
#   $1 = config file
#
# Author:
#   Igor Sfiligoi May 6th 2008
#

import signal,sys,os,os.path,fcntl,string,time

def check_pid(pid):
    return os.path.isfile("/proc/%s/cmdline"%pid)

def get_frontend_pid(lock_dir):
    lock_fname=os.path.join(lock_dir,"frontend.lock")

    if not os.path.isfile(lock_fname):
        raise RuntimeError, "glideinFrontend never started"

    fd=open(lock_fname,"r")
    try:
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.close()
        # if I can get a lock, it means that there is no factory 
        raise RuntimeError, "glideinFrontend not running"
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
        raise RuntimeError, "glideinFrontend (PID %s) not running"%pid
    
    return pid

def main(config_file):
    if not os.path.isfile(config_file):
        print "Invalid file '%s'"%config_file
        return 1
    
    config_dict={}
    execfile(config_file,config_dict)
    log_dir=config_dict['log_dir']
    
    # get the pid
    try:
        frontend_pid=get_frontend_pid(log_dir)
    except RuntimeError, e:
        print e
        return 1
    #print frontend_pid

    # kill proces
    # first soft kill (5s timeout)
    os.kill(frontend_pid,signal.SIGTERM)
    for retries in range(25):
        if check_pid(frontend_pid):
            time.sleep(0.2)
        else:
            break # frontend dead

    # final check for processes
    if check_pid(frontend_pid):
        print "Hard killed frontend"
        os.kill(frontend_pid,signal.SIGKILL)

    return
        

if __name__ == '__main__':
    if len(sys.argv)<2:
        print "Usage: stopFrontend.py config_file"
        sys.exit(1)

    main(sys.argv[1])
