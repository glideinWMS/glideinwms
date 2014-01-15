#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
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
import sys
import fcntl
import subprocess
import traceback
import signal
import time
import string
import logging

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR,"../.."))

from glideinwms.lib import logSupport
from glideinwms.lib import cleanupSupport
from glideinwms.frontend import glideinFrontendPidLib
from glideinwms.frontend import glideinFrontendConfig
from glideinwms.frontend import glideinFrontendInterface
from glideinwms.frontend import glideinFrontendMonitorAggregator
from glideinwms.frontend import glideinFrontendMonitoring

############################################################
# KEL remove this method and just call the monitor aggregator method directly below?  we don't use the results
def aggregate_stats():
    _ = glideinFrontendMonitorAggregator.aggregateStatus()

    return

############################################################
def spawn_group(work_dir,group_name):
    global STARTUP_DIR

    command_list = [sys.executable,
                    os.path.join(STARTUP_DIR,
                                 "glideinFrontendElement.py"),
                    str(os.getpid()),
                    work_dir,
                    group_name]
    #logSupport.log.debug("Command list: %s" % command_list)
    child = subprocess.Popen(command_list, shell=False,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)

    # set it in non blocking mode
    for fd in (child.stdout.fileno(),
               child.stderr.fileno()):
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    return child

############################################################
def check_alive(group_name,child):
    # empty stdout and stderr
    try:
        tempOut = child.stdout.read()
        if len(tempOut)!=0:
            logSupport.log.info("[%s]: %s" % (group_name, tempOut))
    except IOError:
        pass # ignore
    try:
        tempErr = child.stderr.read()
        if len(tempErr)!=0:
            logSupport.log.warning("[%s]: %s" % (group_name, tempErr))
    except IOError:
        pass # ignore

    return (child.poll() is None)

############################################################
def spawn_iteration(work_dir,groups,max_active):
    childs = {}
  
    for group_name in groups:
        childs[group_name] = {'state':'queued'}

    active_groups = 0
    groups_tofinish = len(groups)


    logSupport.log.info("Starting iteration")
    try:
        while groups_tofinish>0:
            done_something = False
            # check if any group finished by now
            for group_name in groups:
                if childs[group_name]['state']=='spawned':
                    if not check_alive(group_name,childs[group_name]['data']):
                        childs[group_name]['state'] = 'finished'
                        active_groups-=1
                        groups_tofinish-=1
                        done_something = True

            # see if I can spawn more
            for group_name in groups:
                if active_groups<max_active: # can spawn more
                    if childs[group_name]['state']=='queued':
                        childs[group_name]['data'] = spawn_group(work_dir,group_name)
                        childs[group_name]['state'] = 'spawned'
                        active_groups+=1
                        done_something = True
                else:
                    break

            if done_something:
                logSupport.log.info("Active groups = %i, Groups to finish = %i"%(active_groups,groups_tofinish))
            if groups_tofinish>0:
                time.sleep(0.01)
    
        logSupport.log.info("All groups finished")

        logSupport.log.info("Aggregate monitoring data")
        # KEL - can we just call the monitor aggregator method directly?  see above
        aggregate_stats()
        """
        try:
          aggregate_stats()
        except Exception:
          logSupport.log.exception("Aggregate monitoring data .. ERROR")
        """

        logSupport.log.info("Cleaning logs")
        cleanupSupport.cleaners.cleanup()
    finally:
        # cleanup at exit
        # if anything goes wrong, hardkill the rest
        for group_name in childs.keys():
            if childs[group_name]['state']=='spawned':
                logSupport.log.info("Hard killing group %s" % group_name)
                try:
                    os.kill(childs[group_name]['data'].pid,signal.SIGKILL)
                except OSError:
                    pass # ignore failed kills of non-existent processes
        
        
############################################################
def spawn_cleanup(work_dir,groups):
    global STARTUP_DIR

    for group_name in groups:
        try:
            command_list = [sys.executable,
                            os.path.join(STARTUP_DIR,
                                         "glideinFrontendElement.py"),
                            str(os.getpid()),
                            work_dir,
                            group_name,
                            "deadvertise"]
            #logSupport.log.debug("Command list: %s" % command_list)
            child = subprocess.Popen(command_list, shell=False,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)

            # set it in non blocking mode
            for fd in (child.stdout.fileno(),
                       child.stderr.fileno()):
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            while check_alive(group_name,child):
                time.sleep(0.01)
        except:
            # never fail on cleanup
            pass
        
############################################################
def spawn(sleep_time,advertize_rate,work_dir,
          frontendDescript,groups,restart_attempts,restart_interval):

    try:
        while 1: #will exit on signal
            start_time=time.time()
            spawn_iteration(work_dir,groups,2)
            end_time=time.time()
            elapsed_time=end_time-start_time
            if elapsed_time<sleep_time:
                real_sleep_time=sleep_time-elapsed_time
                logSupport.log.info("Sleep %.1f sec" % real_sleep_time)
                time.sleep(real_sleep_time)
            else:
                logSupport.log.info("No sleeping this loop, took %.1f sec > %.1f sec" % (elapsed_time, sleep_time))
    finally:
        logSupport.log.info("Deadvertize my ads")
        spawn_cleanup(work_dir,groups)


############################################################
def cleanup_environ():
    for val in os.environ.keys():
        val_low = val.lower()
        if val_low[:8] == "_condor_":
            # remove any CONDOR environment variables
            # don't want any surprises
            del os.environ[val]
        elif val_low[:5] == "x509_":
            # remove any X509 environment variables
            # don't want any surprises
            del os.environ[val]


############################################################
def main(work_dir):
    startup_time=time.time()

    glideinFrontendConfig.frontendConfig.frontend_descript_file = os.path.join(work_dir, glideinFrontendConfig.frontendConfig.frontend_descript_file)
    frontendDescript = glideinFrontendConfig.FrontendDescript(work_dir)

    # the log dir is shared between the frontend main and the groups, so use a subdir
    logSupport.log_dir = os.path.join(frontendDescript.data['LogDir'], "frontend")

    # Configure frontend process logging
    process_logs = eval(frontendDescript.data['ProcessLogs']) 
    for plog in process_logs:
        logSupport.add_processlog_handler("frontend", logSupport.log_dir,
                                          plog['msg_types'], plog['extension'],
                                          int(float(plog['max_days'])),
                                          int(float(plog['min_days'])),
                                          int(float(plog['max_mbytes'])))
    logSupport.log = logging.getLogger("frontend")
    logSupport.log.info("Logging initialized")
    logSupport.log.debug("Frontend startup time: %s" % str(startup_time))

    try:
        cleanup_environ()
        # we use a dedicated config... ignore the system-wide
        os.environ['CONDOR_CONFIG'] = frontendDescript.data['CondorConfig']

        sleep_time = int(frontendDescript.data['LoopDelay'])
        advertize_rate = int(frontendDescript.data['AdvertiseDelay'])
        restart_attempts = int(frontendDescript.data['RestartAttempts'])
        restart_interval = int(frontendDescript.data['RestartInterval'])

        groups = string.split(frontendDescript.data['Groups'], ',')
        groups.sort()

        glideinFrontendMonitorAggregator.monitorAggregatorConfig.config_frontend(os.path.join(work_dir, "monitor"), groups)
    except:
        logSupport.log.exception("Exception occurred configuring monitoring: ")
        raise

    glideinFrontendMonitoring.write_frontend_descript_xml(frontendDescript, os.path.join(work_dir, 'monitor/'))
    
    logSupport.log.info("Enabled groups: %s" % groups)

    # create lock file
    pid_obj = glideinFrontendPidLib.FrontendPidSupport(work_dir)

    # start
    pid_obj.register()
    try:
        try:
            spawn(sleep_time, advertize_rate, work_dir,
                  frontendDescript, groups, restart_attempts, restart_interval)
        except KeyboardInterrupt:
            logSupport.log.info("Received signal...exit")
        except:
            logSupport.log.exception("Exception occurred trying to spawn: ")
    finally:
        pid_obj.relinquish()

############################################################
#
# S T A R T U P
#
############################################################

def termsignal(signr, frame):
    raise KeyboardInterrupt, "Received signal %s" % signr

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, termsignal)
    signal.signal(signal.SIGQUIT, termsignal)

    main(sys.argv[1])
