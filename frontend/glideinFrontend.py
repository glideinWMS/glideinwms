#!/bin/env python
#
# Description:
#   This is the main of the glideinFrontend
#
# Arguments:
#   $1 = work_dir
#
# Author:
#   Igor Sfiligoi
#

import os
import os.path
import sys

STARTUP_DIR=sys.path[0]

import fcntl
import popen2
import traceback
import signal
import time
import string
import copy
import threading
sys.path.append(os.path.join(STARTUP_DIR,"../lib"))

import glideinFrontendPidLib
import glideinFrontendConfig
import glideinFrontendLib
import glideinFrontendMonitorAggregator
import logSupport


############################################################
def aggregate_stats():
    status=glideinFrontendMonitorAggregator.aggregateStatus()

    return

############################################################
def spawn(sleep_time,advertize_rate,work_dir,
          glideinDescript,groups):

    global STARTUP_DIR
    childs={}
    glideinFrontendLib.log_files.logActivity("Starting groups %s"%groups)
    try:
        for group_name in groups:
            childs[group_name]=popen2.Popen3("%s %s %s %s %s"%(sys.executable,os.path.join(STARTUP_DIR,"glideinFrontendElement.py"),os.getpid(),work_dir,group_name),True)

        for group_name in childs.keys():
            childs[group_name].tochild.close()
            # set it in non blocking mode
            # since we will run for a long time, we do not want to block
            for fd  in (childs[group_name].fromchild.fileno(),childs[group_name].childerr.fileno()):
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)



        while 1:
            glideinFrontendLib.log_files.logActivity("Checking groups %s"%groups)
            for group_name in childs.keys():
                child=childs[group_name]

                # empty stdout and stderr
                try:
                    tempOut = child.fromchild.read()
                    if len(tempOut)!=0:
                        print child, tempOut
                except IOError:
                    pass # ignore
                try:
                    tempErr = child.childerr.read()
                    if len(tempErr)!=0:
                        print child, tempErr
                except IOError:
                    pass # ignore
                
                # look for exit childs
                if child.poll()!=-1:
                    # the child exited
                    tempOut = child.fromchild.readlines()
                    tempErr = child.childerr.readlines()
                    del childs[group_name]
                    raise RuntimeError,"Group '%s' exited, quit the whole frontend:\n%s\n%s"%(group_name,tempOut,tempErr)

            glideinFrontendLib.log_files.logActivity("Aggregate monitoring data")
            aggregate_stats()
            
            # do it just before the sleep
            glideinFrontendLib.log_files.cleanup()

            glideinFrontendLib.log_files.logActivity("Sleep")
            time.sleep(sleep_time)
    finally:        
        # cleanup at exit
        for group_name in childs.keys():
            try:
                os.kill(childs[group_name].pid,signal.SIGTERM)
            except OSError:
                pass # ignore failed kills of non-existent processes
        
        
############################################################
def main(work_dir):
    startup_time=time.time()

    glideinFrontendConfig.frontendConfig.frontend_descript_file=os.path.join(work_dir,glideinFrontendConfig.frontendConfig.frontend_descript_file)
    frontendDescript=glideinFrontendConfig.FrontendDescript(work_dir)

    # the log dir is shared between the frontend main and the groups, so use a subdir
    log_dir=os.path.join(frontendDescript.data['LogDir'],"frontend")

    # Configure the process to use the proper LogDir as soon as you get the info
    glideinFrontendLib.log_files=glideinFrontendLib.LogFiles(log_dir,
                                                             float(frontendDescript.data['LogRetentionMaxDays']),
                                                             float(frontendDescript.data['LogRetentionMinDays']),
                                                             float(frontendDescript.data['LogRetentionMaxMBs']))
    
    try:
        sleep_time=int(frontendDescript.data['LoopDelay'])
        advertize_rate=int(frontendDescript.data['AdvertiseDelay'])
        
        groups=string.split(frontendDescript.data['Groups'],',')
        groups.sort()

        glideinFrontendMonitorAggregator.monitorAggregatorConfig.config_frontend(os.path.join(work_dir,"monitor"),groups)
    except:
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideinFrontendLib.log_files.logWarning("Exception at %s: %s" % (time.ctime(),string.join(tb,'')))
        print tb
        raise

    # create lock file
    pid_obj=glideinFrontendPidLib.FrontendPidSupport(work_dir)
    
    # start
    pid_obj.register()
    try:
        try:
            spawn(sleep_time,advertize_rate,work_dir,
                  frontendDescript,groups)
        except KeyboardInterrupt, e:
            glideinFrontendLib.log_files.logActivity("Received signal...exit")
        except:
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            glideinFrontendLib.log_files.logWarning("Exception at %s: %s" % (time.ctime(),string.join(tb,'')))
            print tb
    finally:
        pid_obj.relinquish()
    
############################################################
#
# S T A R T U P
#
############################################################

def termsignal(signr,frame):
    raise KeyboardInterrupt, "Received signal %s"%signr

if __name__ == '__main__':
    signal.signal(signal.SIGTERM,termsignal)
    signal.signal(signal.SIGQUIT,termsignal)

    main(sys.argv[1])
 

