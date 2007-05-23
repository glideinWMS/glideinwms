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
import fcntl
import popen2
import traceback
import signal
import time
import string
import copy
#import threading
sys.path.append("../lib")

import glideFactoryConfig
import glideFactoryLib
import glideFactoryMonitorAggregator
import logSupport


############################################################
def spawn(cleanupObj,sleep_time,advertize_rate,startup_dir,
          glideinDescript,entries):

    childs={}
    glideFactoryLib.factoryConfig.activity_log.write("Starting entries %s"%entries)
    try:
        for entry_name in entries:
            childs[entry_name]=popen2.Popen3("%s glideFactoryEntry.py %s %s %s %s"%(sys.executable,sleep_time,advertize_rate,startup_dir,entry_name),True)

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
            glideFactoryMonitorAggregator.aggregateStatus()

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
    main(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])
 

###########################################################
#
# CVS info
#
# $Id: glideFactory.py,v 1.59 2007/05/23 19:58:06 sfiligoi Exp $
#
# Log:
#  $Log: glideFactory.py,v $
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
