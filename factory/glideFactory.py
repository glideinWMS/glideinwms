#!/bin/env python
#
# Description:
#   This is the main of the glideinFactory
#
# Arguments:
#   $1 = poll period (in seconds)
#   $2 = advertize rate (every $2 loops)
#   $3 = glidein submit_dir
#
# Author:
#   Igor Sfiligoi (Apr 9th 2007 - moved old glideFactory to glideFactoryEntry)
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

import glideFactoryConfig
import glideFactoryLib
import glideFactoryMonitorAggregator
import logSupport

# this thread will be used for lazy updates of rrd history conversions
rrd_thread=None

############################################################
def aggregate_stats():
    global rrd_thread
    
    status=glideFactoryMonitorAggregator.aggregateStatus()
    status=glideFactoryMonitorAggregator.aggregateLogSummary()

    # keep just one thread per monitoring type running at any given time
    # if the old one is still running, do nothing (lazy)
    # create_support_history can take a-while
    if rrd_thread==None:
        thread_alive=0
    else:
        thread_alive=rrd_thread.isAlive()
        if not thread_alive:
            rrd_thread.join()

    if not thread_alive:
        glideFactoryLib.factoryConfig.activity_log.write("Writing lazy stats")
        rrd_thread=threading.Thread(target=glideFactoryMonitorAggregator.create_status_history)
        rrd_thread.start()

    return

############################################################
def spawn(cleanupObj,sleep_time,advertize_rate,startup_dir,
          glideinDescript,entries):

    global STARTUP_DIR
    childs={}
    glideFactoryLib.factoryConfig.activity_log.write("Starting entries %s"%entries)
    try:
        for entry_name in entries:
            childs[entry_name]=popen2.Popen3("%s %s %s %s %s %s %s"%(sys.executable,os.path.join(STARTUP_DIR,"glideFactoryEntry.py"),os.getpid(),sleep_time,advertize_rate,startup_dir,entry_name),True)

        for entry_name in childs.keys():
            childs[entry_name].tochild.close()
            # set it in non blocking mode
            # since we will run for a long time, we do not want to block
            for fd  in (childs[entry_name].fromchild.fileno(),childs[entry_name].childerr.fileno()):
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)



        while 1:
            glideFactoryLib.factoryConfig.activity_log.write("Checking entries %s"%entries)
            for entry_name in childs.keys():
                child=childs[entry_name]

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
                    del childs[entry_name]
                    raise RuntimeError,"Entry '%s' exited, quit the whole factory:\n%s\n%s"%(entry_name,tempOut,tempErr)

            glideFactoryLib.factoryConfig.activity_log.write("Aggregate monitoring data")
            aggregate_stats()

            glideFactoryLib.factoryConfig.activity_log.write("Sleep")
            time.sleep(sleep_time)
    finally:        
        # cleanup at exit
        for entry_name in childs.keys():
            try:
                os.kill(childs[entry_name].pid,signal.SIGTERM)
            except OSError:
                pass # ignore failed kills of non-existent processes
        
        
############################################################
def main(sleep_time,advertize_rate,startup_dir):
    startup_time=time.time()

    # create log files in the glidein log directory
    activity_log=logSupport.DayLogFile(os.path.join(startup_dir,"log/factory_info"))
    warning_log=logSupport.DayLogFile(os.path.join(startup_dir,"log/factory_err"))
    glideFactoryLib.factoryConfig.activity_log=activity_log
    glideFactoryLib.factoryConfig.warning_log=warning_log
    
    cleanupObj=logSupport.DirCleanup(os.path.join(startup_dir,"log"),"(factory_info\..*)|(factory_err\..*)",
                                     7*24*3600,
                                     activity_log,warning_log)

    glideFactoryConfig.factoryConfig.glidein_descript_file=os.path.join(startup_dir,glideFactoryConfig.factoryConfig.glidein_descript_file)
    glideinDescript=glideFactoryConfig.GlideinDescript()
    entries=string.split(glideinDescript.data['Entries'],',')
    entries.sort()

    glideFactoryMonitorAggregator.monitorAggregatorConfig.config_factory(os.path.join(startup_dir,"monitor"),entries)

    # check lock file
    lock_file=os.path.join(startup_dir,"glideinWMS.lock")
    if not os.path.exists(lock_file): #create a lock file if needed
        fd=open(lock_file,"w")
        fd.close()

    fd=open(lock_file,"r+")
    try:
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        fd.close()
        raise RuntimeError, "Another glidein factory already running"
    fd.seek(0)
    fd.truncate()
    fd.write("PID: %s\nStarted: %s\n"%(os.getpid(),time.ctime(startup_time)))
    fd.flush()
    
    # start
    try:
        try:
            spawn(cleanupObj,sleep_time,advertize_rate,startup_dir,
                  glideinDescript,entries)
        except:
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            glideFactoryLib.factoryConfig.warning_log.write("Exception at %s: %s" % (time.ctime(),tb))
            print tb
    finally:
        fd.close()
    
############################################################
#
# S T A R T U P
#
############################################################

if __name__ == '__main__':
    # check that the GSI environment is properly set
    if not os.environ.has_key('X509_USER_PROXY'):
        raise RuntimeError, "Need X509_USER_PROXY to work!"
    if not os.environ.has_key('X509_CERT_DIR'):
        raise RuntimeError, "Need X509_CERT_DIR to work!"

    main(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])
 

###########################################################
#
# CVS info
#
# $Id: glideFactory.py,v 1.66 2008/05/23 17:42:18 sfiligoi Exp $
#
# Log:
#  $Log: glideFactory.py,v $
#  Revision 1.66  2008/05/23 17:42:18  sfiligoi
#  Add creation of the log_summary
#
#  Revision 1.65  2008/05/09 20:50:11  sfiligoi
#  Make them executable
#
#  Revision 1.64  2008/05/07 20:05:16  sfiligoi
#  Change rel paths into abspaths
#
#  Revision 1.63  2008/05/07 19:59:07  sfiligoi
#  Change rel paths into abspaths
#
#  Revision 1.62  2007/07/03 16:41:46  sfiligoi
#  Add few GSI checks
#
#  Revision 1.61  2007/06/15 18:53:44  sfiligoi
#  Add parent pid to the list of entries, so that an entry can exit if parent dies
#
#  Revision 1.60  2007/05/23 22:04:51  sfiligoi
#  Finalize aggregate monitoring
#
#  Revision 1.59  2007/05/23 19:58:06  sfiligoi
#  Start using the MonitorAggregator
#
#  Revision 1.58  2007/05/21 17:06:42  sfiligoi
#  Pass through stdout and stederr
#
#  Revision 1.57  2007/05/18 19:10:57  sfiligoi
#  Add CVS tags
#
#
###########################################################
