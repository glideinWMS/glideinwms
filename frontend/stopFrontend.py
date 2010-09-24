#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: stopFrontend.py,v 1.7.8.1.8.2 2010/09/24 15:38:10 parag Exp $
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

import signal,sys,os,os.path,fcntl,string,time
sys.path.append(os.path.join(sys.path[0],"../lib"))
import glideinFrontendPidLib
import glideinFrontendConfig

# this one should  never throw an exeption
def get_element_pids(work_dir,frontend_pid):
    # get element pids
    frontendDescript=glideinFrontendConfig.FrontendDescript(work_dir)
    groups=string.split(frontendDescript.data['Groups'],',')
    groups.sort()

    element_pids={}
    for group in groups:
        try:
            element_pid,element_ppid=glideinFrontendPidLib.get_element_pid(work_dir,group)
        except RuntimeError,e:
            print e
            continue # report error and go to next group
        if element_ppid!=frontend_pid:
            print "Group '%s' has an unexpected Parent PID: %s!=%s"%(group,element_ppid,frontend_pid)
            continue # report error and go to next group
        element_pids[group]=element_pid

    return element_pids

def main(work_dir):
    # get the pids
    try:
        frontend_pid=glideinFrontendPidLib.get_frontend_pid(work_dir)
    except RuntimeError, e:
        print e
        return 1
    #print frontend_pid

    element_pids=get_element_pids(work_dir,frontend_pid)
    #print element_pids

    element_keys=element_pids.keys()
    element_keys.sort()

    # kill processes
    # first soft kill the frontend (5s timeout)
    os.kill(frontend_pid,signal.SIGTERM)
    for retries in range(25):
        if glideinFrontendPidLib.pidSupport.check_pid(frontend_pid):
            time.sleep(0.2)
        else:
            break # frontend dead

    # now check the elements (5s timeout)
    elements_alive=False
    for element in element_keys:
        if glideinFrontendPidLib.pidSupport.check_pid(element_pids[element]):
            #print "Element '%s' still alive, sending SIGTERM"%element
            os.kill(element_pids[element],signal.SIGTERM)
            elements_alive=True
    if elements_alive:
        for retries in range(25):
            elements_alive=False
            for element in element_keys:
                if glideinFrontendPidLib.pidSupport.check_pid(element_pids[element]):
                    elements_alive=True
            if elements_alive:
                time.sleep(0.2)
            else:
                break # all elements dead
        
    # final check for processes
    if glideinFrontendPidLib.pidSupport.check_pid(frontend_pid):
        print "Hard killed frontend"
        os.kill(frontend_pid,signal.SIGKILL)
    for element in element_keys:
        if glideinFrontendPidLib.pidSupport.check_pid(element_pids[element]):
            print "Hard killed element '%s'"%element
            os.kill(element_pids[element],signal.SIGKILL)
    return 0
        

if __name__ == '__main__':
    if len(sys.argv)<2:
        print "Usage: stopFrontend.py work_dir"
        sys.exit(1)

    sys.exit(main(sys.argv[1]))
