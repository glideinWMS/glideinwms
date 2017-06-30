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
import logging

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../.."))

from glideinwms.lib import condorExe
from glideinwms.lib import logSupport
from glideinwms.lib import cleanupSupport
from glideinwms.lib import servicePerformance
from glideinwms.frontend import glideinFrontendPidLib
from glideinwms.frontend import glideinFrontendConfig
from glideinwms.frontend import glideinFrontendLib
from glideinwms.frontend import glideinFrontendInterface
from glideinwms.frontend import glideinFrontendMonitorAggregator
from glideinwms.frontend import glideinFrontendMonitoring
from glideinFrontendElement import glideinFrontendElement
FRONTEND_DIR = os.path.dirname(glideinFrontendLib.__file__)
############################################################
# KEL remove this method and just call the monitor aggregator method directly below?  we don't use the results
def aggregate_stats():
    return glideinFrontendMonitorAggregator.aggregateStatus()


############################################################
class FailureCounter:
    def __init__(self, my_name, max_lifetime):
        self.my_name = my_name
        self.max_lifetime = max_lifetime
        
        self.failure_times = []

    def add_failure(self, when=None):
        if when is None:
            when = time.time()

        self.clean_old()
        self.failure_times.append(when)

    def get_failures(self):
        self.clean_old()
        return self.failure_times

    def count_failures(self):
        return len(self.get_failures())

    # INTERNAL

    # clean out any old records
    def clean_old(self):
        min_time = time.time() - self.max_lifetime
        while (self.failure_times and (self.failure_times[0] < min_time)):
            # Assuming they are ordered
            self.failure_times.pop(0)
        
############################################################
def spawn_group(work_dir, group_name, action):
    global STARTUP_DIR

    command_list = [sys.executable,
                    os.path.join(STARTUP_DIR,
                                 "glideinFrontendElement.py"),
                    str(os.getpid()),
                    work_dir,
                    group_name,
                    action]
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
def poll_group_process(group_name, child):
    # empty stdout and stderr
    try:
        tempOut = child.stdout.read()
        if len(tempOut) != 0:
            logSupport.log.info("[%s]: %s" % (group_name, tempOut))
    except IOError:
        pass # ignore
    try:
        tempErr = child.stderr.read()
        if len(tempErr) != 0:
            logSupport.log.warning("[%s]: %s" % (group_name, tempErr))
    except IOError:
        pass # ignore

    return child.poll()

############################################################

# return the list of (group,walltime) pairs
def spawn_iteration(work_dir, frontendDescript, groups, max_active,
                    failure_dict, max_failures, action):
    childs = {}
  
    for group_name in groups:
        childs[group_name] = {'state': 'queued'}

    active_groups = 0
    groups_tofinish = len(groups)


    max_num_failures = 0
    logSupport.log.info("Starting iteration")
    try:
        while groups_tofinish > 0:
            done_something = False
            # check if any group finished by now
            for group_name in groups:
                if childs[group_name]['state'] == 'spawned':
                    group_rc = poll_group_process(group_name,
                                                  childs[group_name]['data'])
                    if not (group_rc is None): # None means "still alive"
                        if group_rc == 0:
                            childs[group_name]['state'] = 'finished'
                        else:
                            childs[group_name]['state'] = 'failed'
                            failure_dict[group_name].add_failure()
                            num_failures = failure_dict[group_name].count_failures()
                            max_num_failures = max(max_num_failures,
                                                   num_failures)
                            logSupport.log.warning("Group %s terminated with exit code %i (%i recent failure)" % (group_name, group_rc, num_failures))
                        childs[group_name]['end_time'] = time.time()
                        servicePerformance.endPerfMetricEvent(
                            'frontend', 'group_%s_iteration'%group_name)
                        active_groups -= 1
                        groups_tofinish -= 1
                        done_something = True

            # see if I can spawn more
            for group_name in groups:
                if active_groups < max_active: # can spawn more
                    if childs[group_name]['state'] == 'queued':
                        childs[group_name]['data'] = spawn_group(work_dir, group_name, action)
                        childs[group_name]['state'] = 'spawned'
                        childs[group_name]['start_time'] = time.time()
                        servicePerformance.startPerfMetricEvent(
                            'frontend', 'group_%s_iteration'%group_name)
                        active_groups += 1
                        done_something = True
                else:
                    break

            if done_something:
                logSupport.log.info("Active groups = %i, Groups to finish = %i" % (active_groups, groups_tofinish))
            if groups_tofinish > 0:
                time.sleep(0.01)
    
        logSupport.log.info("All groups finished")

        logSupport.log.info("Aggregate monitoring data")
        # KEL - can we just call the monitor aggregator method directly?  see above
        servicePerformance.startPerfMetricEvent('frontend', 'aggregate_stats')
        stats = aggregate_stats()
        servicePerformance.endPerfMetricEvent('frontend', 'aggregate_stats')
        #logSupport.log.debug(stats)

        # Create the glidefrontendmonitor classad
        fm_advertiser = glideinFrontendInterface.FrontendMonitorClassadAdvertiser(multi_support=glideinFrontendInterface.frontendConfig.advertise_use_multi)
        fm_classad = glideinFrontendInterface.FrontendMonitorClassad(
                         frontendDescript.data['FrontendName'])
        fm_classad.setFrontendDetails(
            frontendDescript.data['FrontendName'], ','.join(groups),
            glideinFrontendLib.getHAMode(frontendDescript.data))
        try:
            idle_jobs = {
                'Total': stats['total']['Jobs']['Idle'],
                '600': stats['total']['Jobs']['OldIdle'],
                '3600': stats['total']['Jobs']['Idle_3600'],
            }
        except KeyError as err:
            idle_jobs = {'Total': 0, '600': 0, '3600': 0}
            logSupport.log.error("Error in RRD Database. Setting idle_jobs[%s] Failed. Reconfig the frontend with -fix_rrd to fix this error" % (err.message,))

        fm_classad.setIdleJobCount(idle_jobs)
        fm_classad.setPerfMetrics(servicePerformance.getPerfMetric('frontend'))
        # Gather performance stats from history file of each group
        for group_name in groups:
            gname = 'group_%s' % group_name
            try:
                history_obj = glideinFrontendConfig.HistoryFile(
                    work_dir, group_name, True, dict)
                pfm = servicePerformance.getPerfMetric(gname)
                pfm.metric = history_obj['perf_metrics'].metric

                fm_classad.setPerfMetrics(
                    servicePerformance.getPerfMetric(gname))
            except:
                pass # Do not fail for non-critical actions

        fm_advertiser.addClassad(fm_classad.adParams['Name'], fm_classad)

        # Advertise glidefrontendmonitor classad to user pool
        logSupport.log.info("Advertising %i %s classad(s) to the user pool" % (len(fm_advertiser.classads), fm_advertiser.adType))
        try:
            set_frontend_htcondor_env(work_dir, frontendDescript)
            fm_advertiser.advertiseAllClassads()
            logSupport.log.info("Done advertising %s classad(s) to the user pool" % fm_advertiser.adType)
        except condorExe.ExeError:
            logSupport.log.error("Exception occurred trying to advertise %s classad(s) to the user pool" % fm_advertiser.adType)
        except:
            # Rethrow any other exception including stop signal
            raise
        finally:
            # Cleanup the env
            clean_htcondor_env()

        logSupport.log.info("Cleaning logs")
        cleanupSupport.cleaners.cleanup()

        if max_num_failures > max_failures:
            logSupport.log.info("Too many group failures, aborting")
            logSupport.log.debug("Failed %i times (limit %i), aborting"%(max_num_failures, max_failures))
            raise RuntimeError, "Too many group failures, aborting" 
    finally:
        # cleanup at exit
        # if anything goes wrong, hardkill the rest
        for group_name in childs:
            if childs[group_name]['state']=='spawned':
                logSupport.log.info("Hard killing group %s" % group_name)
                servicePerformance.endPerfMetricEvent(
                    'frontend', 'group_%s_iteration'%group_name)
                try:
                    os.kill(childs[group_name]['data'].pid, signal.SIGKILL)
                except OSError:
                    pass # ignore failed kills of non-existent processes

    # at this point, all groups should have been run
    timings = []
    for group_name in groups:
        timings.append((group_name, childs[group_name]['end_time']-childs[group_name]['start_time']))
    return timings
        
############################################################
def spawn_cleanup(work_dir, frontendDescript, groups, frontend_name, ha_mode):
    global STARTUP_DIR

    # Invalidate glidefrontendmonitor classad
    try:
        set_frontend_htcondor_env(work_dir, frontendDescript)
        fm_advertiser = glideinFrontendInterface.FrontendMonitorClassadAdvertiser()
        constraint = '(GlideFrontendName=="%s")&&(GlideFrontendHAMode=?="%s")' % (frontend_name, ha_mode)
        fm_advertiser.invalidateConstrainedClassads(constraint)
    except:
        # Do not fail in case of errors.
        logSupport.log.warning("Failed to deadvertise glidefrontendmonitor classad")

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

            while poll_group_process(group_name, child) is None:
                # None means "still alive"
                time.sleep(0.01)
        except:
            # never fail on cleanup
            pass


############################################################
def spawn(sleep_time, advertize_rate, work_dir, frontendDescript,
          groups, max_parallel_workers, restart_interval, restart_attempts):

    num_groups = len(groups)

    # TODO: Get the ha_check_interval from the config
    ha = glideinFrontendLib.getHASettings(frontendDescript.data)
    ha_check_interval = glideinFrontendLib.getHACheckInterval(frontendDescript.data)
    mode = glideinFrontendLib.getHAMode(frontendDescript.data)
    master_frontend_name = ''
    if mode == 'slave':
        master_frontend_name = ha.get('ha_frontends')[0].get('frontend_name')

    active = (mode == 'master')
    hibernate = shouldHibernate(frontendDescript, work_dir, ha, mode, groups)

    logSupport.log.info('Frontend started with mode = %s' % mode)
    try:

        # Service will exit on signal only.
        # This infinite loop is for the slave to go back into hibernation
        # once the master becomes alive.
        # Master never loops infinitely here, but instead it does in
        # the inner loop while(mode=='master') ...
        while True:

            while hibernate:
                # If I am slave enter hibernation cycle while Master is alive
                logSupport.log.info('Master Frontend %s is online. Hibernating.' % master_frontend_name)
                time.sleep(ha_check_interval)
                hibernate = shouldHibernate(frontendDescript, work_dir,
                                            ha, mode, groups)

            # We broke out of hibernation cycle
            # Either Master has disappeared or I am the Master
            if mode == 'slave':
                logSupport.log.info("Master frontend %s is offline. Activating slave frontend." % master_frontend_name)
                active = True

            failure_dict = {} 
            for group in groups:
                failure_dict[group] = FailureCounter(group, restart_interval)

            while ((mode == 'master') or ((mode == 'slave') and active)):
                servicePerformance.startPerfMetricEvent('frontend', 'iteration')
                start_time = time.time()
                timings = spawn_iteration(work_dir, frontendDescript, groups,
                                          max_parallel_workers, failure_dict,
                                          restart_attempts, "run")
                servicePerformance.endPerfMetricEvent('frontend', 'iteration')
                end_time = time.time()
                elapsed_time = servicePerformance.getPerfMetricEventLifetime('frontend', 'iteration')
                if elapsed_time < sleep_time:
                    real_sleep_time = sleep_time - elapsed_time
                    logSupport.log.info("Sleep %.1f sec" % real_sleep_time)
                    time.sleep(real_sleep_time)
                else:
                    logSupport.log.info("No sleeping this loop, took %.1f sec > %.1f sec" % (elapsed_time, sleep_time))

                # order the groups by walltime
                # longest walltime first
                timings.sort(lambda x, y:-cmp(x[1], y[1]))
                # recreate the groups list, with new ordering
                groups = [el[0] for el in timings]
                assert num_groups == len(groups), "Something went wrong, number of groups changed"

                if mode == 'slave':
                    # If we are slave, check if master is back and if so
                    # deadvertise my classads and hibernate
                    hibernate = shouldHibernate(frontendDescript, work_dir,
                                                ha, mode, groups)

                    if hibernate:
                        active = False
                        logSupport.log.info("Master frontend %s is back online" % master_frontend_name)
                        logSupport.log.info("Deadvertize my ads and enter hibernation cycle")
                        spawn_cleanup(work_dir, frontendDescript, groups,
                                      frontendDescript.data['FrontendName'],
                                      mode)
                    else:
                        logSupport.log.info("Master frontend %s is still offline" % master_frontend_name)


    finally:
        # We have been asked to terminate
        logSupport.log.info("Deadvertize my ads")
        spawn_cleanup(work_dir, frontendDescript, groups,
                      frontendDescript.data['FrontendName'], mode)


############################################################
def shouldHibernate(frontendDescript, work_dir, ha, mode, groups):
    """
    Check if the frontend is running in HA mode. If run in master mode never
    hibernate. If run in slave mode, hiberate if master is active.

    @rtype: bool
    @return: True if we should hibernate else False
    """

    servicePerformance.startPerfMetricEvent('frontend', 'ha_check')
    if mode == 'slave':
        master_frontend_name = str(ha.get('ha_frontends')[0].get('frontend_name'))

        for group in groups:
            element = glideinFrontendElement(os.getpid(), work_dir,
                                             group, "run")
            # Set environment required to query factory collector
            set_frontend_htcondor_env(work_dir, frontendDescript, element)

            for factory_pool in element.factory_pools:
                try:
                    factory_pool_node = factory_pool[0]
                    master_classads = glideinFrontendInterface.findMasterFrontendClassads(factory_pool_node, master_frontend_name)

                    if master_classads:
                        # Found some classads in one of the collectors
                        # Cleanup the env and return True
                        clean_htcondor_env()
                        servicePerformance.endPerfMetricEvent(
                            'frontend', 'ha_check')
                        return True
                except RuntimeError:
                    # Failed to talk
                    if not factory_pool_node:
                        factory_pool_node = ''
                    msg = "Failed to talk to the factory_pool %s to get the status of Master frontend %s" % (factory_pool_node, master_frontend_name)
                    logSupport.log.warn(msg)
                    msg = "Exception talking to the factory_pool %s to get the status of Master frontend %s: " % (factory_pool_node, master_frontend_name)
                    logSupport.log.exception(msg )

        # Cleanup the env
        clean_htcondor_env()

        # NOTE:
        # If we got this far with no errors then we could not find
        # active master frontend. We should not hibernate as slave
        # However, if there were errors checking with factory pool
        # then the master frontend could be down so its safe to wake
        # up and start advertising.

    servicePerformance.endPerfMetricEvent('frontend', 'ha_check')
    return False


def set_frontend_htcondor_env(work_dir, frontendDescript, element=None):
    # Collector DN is only in the group's mapfile. Just get first one.
    groups = frontendDescript.data['Groups'].split(',')
    if groups:
        if element is None:
            element = glideinFrontendElement(os.getpid(), work_dir,
                                             groups[0], "run")
        htc_env = {
            'CONDOR_CONFIG': frontendDescript.data['CondorConfig'],
            'X509_USER_PROXY': frontendDescript.data['ClassAdProxy'],
            '_CONDOR_CERTIFICATE_MAPFILE':  element.elementDescript.element_data['MapFile']
        }
        set_env(htc_env)

def set_env(env):
    for var in env:
        os.environ[var] = env[var]


def clean_htcondor_env():
    for v in ('CONDOR_CONFIG', '_CONDOR_CERTIFICATE_MAPFILE', 'X509_USER_PROXY'):
        if os.environ.get(v):
            del os.environ[v]

############################################################

def spawn_removal(work_dir, frontendDescript, groups,
                  max_parallel_workers, removal_action):

    failure_dict={}
    for group in groups:
        failure_dict[group]=FailureCounter(group, 3600)

    spawn_iteration(work_dir, frontendDescript, groups,
                    max_parallel_workers, failure_dict, 1, removal_action)

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
def main(work_dir, action):
    startup_time = time.time()

    glideinFrontendConfig.frontendConfig.frontend_descript_file = os.path.join(work_dir, glideinFrontendConfig.frontendConfig.frontend_descript_file)
    frontendDescript = glideinFrontendConfig.FrontendDescript(work_dir)

    # the log dir is shared between the frontend main and the groups, so use a subdir
    logSupport.log_dir = os.path.join(frontendDescript.data['LogDir'],
                                      "frontend")

    # Configure frontend process logging
    process_logs = eval(frontendDescript.data['ProcessLogs']) 
    for plog in process_logs:
        logSupport.add_processlog_handler("frontend", logSupport.log_dir,
                                          plog['msg_types'], plog['extension'],
                                          int(float(plog['max_days'])),
                                          int(float(plog['min_days'])),
                                          int(float(plog['max_mbytes'])),
                                          int(float(plog['backup_count'])),
                                          plog['compression'])
    logSupport.log = logging.getLogger("frontend")
    logSupport.log.info("Logging initialized")
    logSupport.log.debug("Frontend startup time: %s" % str(startup_time))

    try:
        cleanup_environ()
        # we use a dedicated config... ignore the system-wide
        os.environ['CONDOR_CONFIG'] = frontendDescript.data['CondorConfig']

        sleep_time = int(frontendDescript.data['LoopDelay'])
        advertize_rate = int(frontendDescript.data['AdvertiseDelay'])
        max_parallel_workers = int(frontendDescript.data['GroupParallelWorkers'])
        restart_attempts = int(frontendDescript.data['RestartAttempts'])
        restart_interval = int(frontendDescript.data['RestartInterval'])


        groups = sorted(frontendDescript.data['Groups'].split(','))

        glideinFrontendMonitorAggregator.monitorAggregatorConfig.config_frontend(os.path.join(work_dir, "monitor"), groups)
    except:
        logSupport.log.exception("Exception occurred configuring monitoring: ")
        raise

    glideinFrontendMonitoring.write_frontend_descript_xml(
        frontendDescript, os.path.join(work_dir, 'monitor/'))
    
    logSupport.log.info("Enabled groups: %s" % groups)

    # create lock file
    pid_obj = glideinFrontendPidLib.FrontendPidSupport(work_dir)

    # start
    try:
        pid_obj.register(action)
    except  glideinFrontendPidLib.pidSupport.AlreadyRunning as err:
        pid_obj.load_registered()
        logSupport.log.exception("Failed starting Frontend with action %s. Instance with pid %s is aready running for action %s. Exception during pid registration: %s" % (action, pid_obj.mypid, str(pid_obj.action_type), err))
        raise

    try:
        try:
            if action == "run":
                spawn(sleep_time, advertize_rate, work_dir,
                      frontendDescript, groups, max_parallel_workers,
                      restart_interval, restart_attempts)
            elif action in ('removeWait', 'removeIdle', 'removeAll', 'removeWaitExcess', 'removeIdleExcess', 'removeAllExcess'):
                spawn_removal(work_dir, frontendDescript, groups,
                              max_parallel_workers, action)
            else:
                raise ValueError, "Unknown action: %s" % action
        except KeyboardInterrupt:
            logSupport.log.info("Received signal...exit")
        except HUPException:
            logSupport.log.info("Received SIGHUP, reload config")
            pid_obj.relinquish()
            os.execv( os.path.join(FRONTEND_DIR, "../creation/reconfig_frontend"), ['reconfig_frontend', '-sighupreload', '-xml', '/etc/gwms-frontend/frontend.xml'] )
        except:
            logSupport.log.exception("Exception occurred trying to spawn: ")
    finally:
        pid_obj.relinquish()

############################################################
#
# S T A R T U P
#
############################################################

class HUPException(Exception):
    pass

def termsignal(signr, frame):
    raise KeyboardInterrupt, "Received signal %s" % signr

def hupsignal(signr, frame):
    signal.signal( signal.SIGHUP,  signal.SIG_IGN )
    raise HUPException, "Received signal %s" % signr

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, termsignal)
    signal.signal(signal.SIGQUIT, termsignal)
    signal.signal(signal.SIGHUP,  hupsignal)

    if len(sys.argv) == 2:
        action = "run"
    else:
        action = sys.argv[2]

    main(sys.argv[1], action)
