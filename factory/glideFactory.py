#!/bin/env python
#
# Description:
#   This is the main of the glideinFactory
#
# Arguments:
#   $1 = glidein submit_dir
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

import glideFactoryPidLib
import glideFactoryConfig
import glideFactoryLib
import glideFactoryMonitorAggregator
import logSupport

# this thread will be used for lazy updates of rrd history conversions
rrd_thread=None

def create_history_thread():
    glideFactoryMonitorAggregator.create_status_history()
    glideFactoryMonitorAggregator.create_log_history()
    return

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
        rrd_thread=threading.Thread(target=create_history_thread)
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
def main(startup_dir):
    startup_time=time.time()

    # force integrity checks on all the operations
    # I need integrity checks also on reads, as I depend on them
    os.environ['_CONDOR_SEC_DEFAULT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_CLIENT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_READ_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_WRITE_INTEGRITY'] = 'REQUIRED'

    # disable locking... else I can get in deadlock with entries
    glideFactoryMonitorAggregator.glideFactoryMonitoring.monitoringConfig.lock_dir=None

    # create log files in the glidein log directory
    activity_log=logSupport.DayLogFile(os.path.join(startup_dir,"log/factory_info"))
    warning_log=logSupport.DayLogFile(os.path.join(startup_dir,"log/factory_err"))
    glideFactoryLib.factoryConfig.activity_log=activity_log
    glideFactoryLib.factoryConfig.warning_log=warning_log
    
    try:
        glideFactoryConfig.factoryConfig.glidein_descript_file=os.path.join(startup_dir,glideFactoryConfig.factoryConfig.glidein_descript_file)
        glideinDescript=glideFactoryConfig.GlideinDescript()
        glideinDescript.load_pub_key(recreate=True)

        glideFactoryMonitorAggregator.glideFactoryMonitoring.monitoringConfig.my_name="%s@%s"%(glideinDescript.data['GlideinName'],glideinDescript.data['FactoryName'])

        cleanupObj=logSupport.DirCleanupWSpace(os.path.join(startup_dir,"log"),"(factory_info\..*)|(factory_err\..*)",
                                               float(glideinDescript.data['LogRetentionMaxDays'])*24*3600,
                                               float(glideinDescript.data['LogRetentionMinDays'])*24*3600,
                                               float(glideinDescript.data['LogRetentionMaxMBs'])*1024*1024,
                                               activity_log,warning_log)
        
        sleep_time=int(glideinDescript.data['LoopDelay'])
        advertize_rate=int(glideinDescript.data['AdvertiseDelay'])
        glideFactoryMonitorAggregator.glideFactoryMonitoring.monitoringConfig.wanted_graphs=string.split(glideinDescript.data['FactoryWantedMonitorGraphs'],',')
        
        entries=string.split(glideinDescript.data['Entries'],',')
        entries.sort()

        glideFactoryMonitorAggregator.monitorAggregatorConfig.config_factory(os.path.join(startup_dir,"monitor"),entries)
    except:
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.factoryConfig.warning_log.write("Exception at %s: %s" % (time.ctime(),string.join(tb,'')))
        print tb
        raise

    # create lock file
    pid_obj=glideFactoryPidLib.FactoryPidSupport(startup_dir)
    
    # start
    pid_obj.register()
    try:
        try:
            spawn(cleanupObj,sleep_time,advertize_rate,startup_dir,
                  glideinDescript,entries)
        except:
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            glideFactoryLib.factoryConfig.warning_log.write("Exception at %s: %s" % (time.ctime(),string.join(tb,'')))
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

    # check that the GSI environment is properly set
    if not os.environ.has_key('X509_USER_PROXY'):
        raise RuntimeError, "Need X509_USER_PROXY to work!"
    if not os.environ.has_key('X509_CERT_DIR'):
        raise RuntimeError, "Need X509_CERT_DIR to work!"

    main(sys.argv[1])
 

