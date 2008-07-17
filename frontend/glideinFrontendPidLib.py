#
# Description:
#  Handle frontend pids
# 
# Author:
#   Igor Sfiligoi Jul 17th 2008
#

import sys,os,os.path,fcntl,time

############################################################

#
# Verify if the system knows about a pid
#
def check_pid(pid):
    return os.path.isfile("/proc/%s/cmdline"%pid)

############################################################

#
# Create the lock file and registers the frontend pid
#
# return fd (to be closed by frontend before ending)
# raises an exception if it cannot create the lock file
def register_frontend_pid(log_dir):
    lock_file=os.path.join(log_dir,"frontend.lock")

    # check lock file
    if not os.path.exists(lock_file): #create a lock file if needed
        fd=open(lock_file,"w")
        fd.close()

    fd=open(lock_file,"r+")
    try:
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        fd.close()
        raise RuntimeError, "Another glideinFrontend already running"
    fd.seek(0)
    fd.truncate()
    fd.write("PID: %s\nStarted: %s\n"%(os.getpid(),time.ctime(time.time())))
    fd.flush()

    return fd

#
# Find and return the frontend pid
#
# return pid
# raises an exception if it cannot find it
def get_frontend_pid(log_dir):
    lock_fname=os.path.join(log_dir,"frontend.lock")

    if not os.path.isfile(lock_fname):
        raise RuntimeError, "glideinFrontend never started"

    fd=open(lock_fname,"r")
    try:
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.close()
        # if I can get a lock, it means that there is no frontend 
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

