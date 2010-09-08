#!/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glideFactory.py,v 1.89.2.1.8.2.4.4 2010/09/08 18:10:08 sfiligoi Exp $
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
import glideFactoryInterface
import glideFactoryMonitorAggregator

############################################################
def aggregate_stats():
    global rrd_thread
    
    status=glideFactoryMonitorAggregator.aggregateStatus()
    status=glideFactoryMonitorAggregator.aggregateLogSummary()

    return

############################################################
def is_crashing_often(startup_time, restart_interval, restart_attempts):
    crashing_often = True

    if (len(startup_time) < restart_attempts):
        # We haven't exhausted restart attempts
        crashing_often = False
    else:
        # Check if the service has been restarted often
        if restart_attempts == 1:
            crashing_often = True
        elif (time.time() - startup_time[0]) >= restart_interval:
            crashing_often = False
        else:
            crashing_often = True

    return crashing_often

############################################################
def clean_exit(childs):
    # first send a nice kill signal
    entries=childs.keys()
    entries.sort()
    glideFactoryLib.log_files.logActivity("Killing entries %s"%entries)
    for entry_name in childs.keys():
        try:
            os.kill(childs[entry_name].pid,signal.SIGTERM)
        except OSError:
            glideFactoryLib.log_files.logActivity("Entry %s already dead"%entry_name)
            del childs[entry_name] # already dead

    sleep_time=0.1 # start with very little sleep
    while len(childs.keys())>0:
        glideFactoryLib.log_files.logActivity("Sleep")
        time.sleep(sleep_time)
        # exponentially increase, up to 5 secs
        sleep_time=sleep_time*2
        if sleep_time>5:
            sleep_time=5
        
        entries=childs.keys()
        entries.sort()
        
        glideFactoryLib.log_files.logActivity("Checking dying entries %s"%entries)
        for entry_name in childs.keys():
            child=childs[entry_name]

            # empty stdout and stderr
            try:
                tempOut = child.fromchild.read()
                if len(tempOut)!=0:
                    glideFactoryLib.log_files.logWarning("Child %s STDOUT: %s"%(child, tempOut))
            except IOError:
                pass # ignore
            try:
                tempErr = child.childerr.read()
                if len(tempErr)!=0:
                    glideFactoryLib.log_files.logWarning("Child %s STDERR: %s"%(child, tempErr))
            except IOError:
                pass # ignore

            # look for exited child
            if child.poll()!=-1:
                # the child exited
                glideFactoryLib.log_files.logActivity("Entry %s is now dead"%entry_name)
                del childs[entry_name]
                tempOut = child.fromchild.readlines()
                tempErr = child.childerr.readlines()

    glideFactoryLib.log_files.logActivity("All entries dead")


############################################################
def spawn(sleep_time,advertize_rate,startup_dir,
          glideinDescript,entries,restart_attempts,restart_interval):

    global STARTUP_DIR
    childs={}

    childs_uptime={}
    # Allow max 3 restarts every 30 min before giving up
    #restart_attempts = 3
    #restart_interval = 1800

    glideFactoryLib.log_files.logActivity("Starting entries %s"%entries)
    try:
        for entry_name in entries:
            childs[entry_name]=popen2.Popen3("%s %s %s %s %s %s %s"%(sys.executable,os.path.join(STARTUP_DIR,"glideFactoryEntry.py"),os.getpid(),sleep_time,advertize_rate,startup_dir,entry_name),True)
            # Get the startup time. Used to check if the entry is crashing
            # periodically and needs to be restarted.
            childs_uptime[entry_name]=list()
            childs_uptime[entry_name].insert(0,time.time())
        glideFactoryLib.log_files.logActivity("Entry startup times: %s"%childs_uptime)

        for entry_name in childs.keys():
            childs[entry_name].tochild.close()
            # set it in non blocking mode
            # since we will run for a long time, we do not want to block
            for fd  in (childs[entry_name].fromchild.fileno(),childs[entry_name].childerr.fileno()):
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        while 1:
            glideFactoryLib.log_files.logActivity("Checking entries %s"%entries)
            for entry_name in childs.keys():
                child=childs[entry_name]

                # empty stdout and stderr
                try:
                    tempOut = child.fromchild.read()
                    if len(tempOut)!=0:
                        glideFactoryLib.log_files.logWarning("Child %s STDOUT: %s"%(child, tempOut))
                except IOError:
                    pass # ignore
                try:
                    tempErr = child.childerr.read()
                    if len(tempErr)!=0:
                        glideFactoryLib.log_files.logWarning("Child %s STDERR: %s"%(child, tempErr))
                except IOError:
                    pass # ignore
                
                # look for exited child
                if child.poll()!=-1:
                    # the child exited
                    glideFactoryLib.log_files.logWarning("Child %s exited. Checking if it should be restarted."%(entry_name))
                    tempOut = child.fromchild.readlines()
                    tempErr = child.childerr.readlines()

                    if is_crashing_often(childs_uptime[entry_name], restart_interval, restart_attempts):
                        del childs[entry_name]
                        raise RuntimeError,"Entry '%s' has been crashing too often, quit the whole factory:\n%s\n%s"%(entry_name,tempOut,tempErr)
                    else:
                        # Restart the entry setting its restart time
                        glideFactoryLib.log_files.logWarning("Restarting child %s."%(entry_name))
                        del childs[entry_name]
                        childs[entry_name]=popen2.Popen3("%s %s %s %s %s %s %s"%(sys.executable,os.path.join(STARTUP_DIR,"glideFactoryEntry.py"),os.getpid(),sleep_time,advertize_rate,startup_dir,entry_name),True)
                        if len(childs_uptime[entry_name]) == restart_attempts:
                            childs_uptime[entry_name].pop(0)
                        childs_uptime[entry_name].append(time.time())
                        childs[entry_name].tochild.close()
                        for fd  in (childs[entry_name].fromchild.fileno(),childs[entry_name].childerr.fileno()):
                            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                        glideFactoryLib.log_files.logWarning("Entry startup/restart times: %s"%childs_uptime)

            glideFactoryLib.log_files.logActivity("Aggregate monitoring data")
            aggregate_stats()
            
            # do it just before the sleep
            glideFactoryLib.log_files.cleanup()

            glideFactoryLib.log_files.logActivity("Sleep")
            time.sleep(sleep_time)
    finally:        
        # cleanup at exit
        try:
            try:
                clean_exit(childs)
            except:
                # if anything goes wrong, hardkill the rest
                for entry_name in childs.keys():
                    glideFactoryLib.log_files.logActivity("Hard killing entry %s"%entry_name)
                    try:
                        os.kill(childs[entry_name].pid,signal.SIGKILL)
                    except OSError:
                        pass # ignore dead clients
        finally:
            glideFactoryLib.log_files.logActivity("Deadvertize myself")
            try:
                glideFactoryInterface.deadvertizeFactory(glideinDescript.data['FactoryName'],
                                                         glideinDescript.data['GlideinName'])
            except:
                glideFactoryLib.log_files.logWarning("Factory deadvertize failed!")
                pass # just warn
            try:
                glideFactoryInterface.deadvertizeFactoryClientMonitoring(glideinDescript.data['FactoryName'],
                                                                         glideinDescript.data['GlideinName'])
            except:
                glideFactoryLib.log_files.logWarning("Factory Monitoring deadvertize failed!")
                pass # just warn
        
        
############################################################
def main(startup_dir):
    
    startup_time=time.time()

    # force integrity checks on all the operations
    # I need integrity checks also on reads, as I depend on them
    os.environ['_CONDOR_SEC_DEFAULT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_CLIENT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_READ_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_WRITE_INTEGRITY'] = 'REQUIRED'

    glideFactoryConfig.factoryConfig.glidein_descript_file=os.path.join(startup_dir,glideFactoryConfig.factoryConfig.glidein_descript_file)
    glideinDescript=glideFactoryConfig.GlideinDescript()

    # the log dir is shared between the factory main and the entries, so use a subdir
    log_dir=os.path.join(glideinDescript.data['LogDir'],"factory")

    # Configure the process to use the proper LogDir as soon as you get the info
    glideFactoryLib.log_files=glideFactoryLib.LogFiles(log_dir,
                                                       float(glideinDescript.data['LogRetentionMaxDays']),
                                                       float(glideinDescript.data['LogRetentionMinDays']),
                                                       float(glideinDescript.data['LogRetentionMaxMBs']))
    

    try:
        os.chdir(startup_dir)
    except:
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logWarning("Unable to change to startup_dir %s: %s" % (startup_dir,tb))
        raise

    try:
        glideinDescript.load_pub_key(recreate=True)

        glideFactoryMonitorAggregator.glideFactoryMonitoring.monitoringConfig.my_name="%s@%s"%(glideinDescript.data['GlideinName'],glideinDescript.data['FactoryName'])

        # check that the GSI environment is properly set
        if not os.environ.has_key('X509_CERT_DIR'):
            glideFactoryLib.log_files.logWarning("Environment variable X509_CERT_DIR not set. Need X509_CERT_DIR to work!")
            raise RuntimeError, "Need X509_CERT_DIR to work!"

        allowed_proxy_source=glideinDescript.data['AllowedJobProxySource'].split(',')
        if 'factory' in allowed_proxy_source:
            if not os.environ.has_key('X509_USER_PROXY'):
                glideFactoryLib.log_files.logWarning("Factory is supposed to allow provide a proxy, but environment variable X509_USER_PROXY not set. Need X509_USER_PROXY to work!")
                raise RuntimeError, "Factory is supposed to allow provide a proxy. Need X509_USER_PROXY to work!"
            

        sleep_time=int(glideinDescript.data['LoopDelay'])
        advertize_rate=int(glideinDescript.data['AdvertiseDelay'])
        restart_attempts=int(glideinDescript.data['RestartAttempts'])
        restart_interval=int(glideinDescript.data['RestartInterval'])
        
        entries=string.split(glideinDescript.data['Entries'],',')
        entries.sort()

        glideFactoryMonitorAggregator.monitorAggregatorConfig.config_factory(os.path.join(startup_dir,"monitor"),entries)

        glideFactoryInterface.factoryConfig.advertise_use_tcp=(glideinDescript.data['AdvertiseWithTCP'] in ('True','1'))
        glideFactoryInterface.factoryConfig.advertise_use_multi=(glideinDescript.data['AdvertiseWithMultiple'] in ('True','1'))
    except:
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logWarning("Exception occurred: %s" % tb)
        raise

    # create lock file
    pid_obj=glideFactoryPidLib.FactoryPidSupport(startup_dir)
    
    # start
    pid_obj.register()
    try:
        try:
            spawn(sleep_time,advertize_rate,startup_dir,
                  glideinDescript,entries,restart_attempts,restart_interval)
        except KeyboardInterrupt,e:
            raise e
        except:
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            glideFactoryLib.log_files.logWarning("Exception occurred: %s" % tb)
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

    try:
        main(sys.argv[1])
    except KeyboardInterrupt,e:
        print glideFactoryLib.log_files.logActivity("Terminating: %s"%e)
