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

import signal,sys,os,os.path,string,time
import glideinFrontendPidLib

def main(config_file):
    if not os.path.isfile(config_file):
        print "Invalid file '%s'"%config_file
        return 1
    
    config_dict={}
    execfile(config_file,config_dict)
    log_dir=config_dict['log_dir']
    
    # get the pid
    try:
        frontend_pid=glideinFrontendPidLib.get_frontend_pid(log_dir)
    except RuntimeError, e:
        print e
        return 1
    #print frontend_pid

    # kill proces
    # first soft kill (5s timeout)
    os.kill(frontend_pid,signal.SIGTERM)
    for retries in range(25):
        if glideinFrontendPidLib.check_pid(frontend_pid):
            time.sleep(0.2)
        else:
            break # frontend dead

    # final check for processes
    if glideinFrontendPidLib.check_pid(frontend_pid):
        print "Hard killed frontend"
        os.kill(frontend_pid,signal.SIGKILL)

    return
        

if __name__ == '__main__':
    if len(sys.argv)<2:
        print "Usage: stopFrontend.py config_file"
        sys.exit(1)

    main(sys.argv[1])
