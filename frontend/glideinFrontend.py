#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""glideinFrontend Main Script.

This script serves as the entry point for managing the glideinFrontend processes, handling group operations,
failure monitoring, and performance aggregation.

Usage:
    python glideinFrontend.py <work_dir>

Args:
    work_dir (str): The working directory for the Frontend.
"""


import fcntl
import os
import shutil
import signal
import subprocess
import sys
import time

from glideinwms.frontend import (
    glideinFrontendConfig,
    glideinFrontendElement,
    glideinFrontendInterface,
    glideinFrontendLib,
    glideinFrontendMonitorAggregator,
    glideinFrontendMonitoring,
    glideinFrontendPidLib,
)
from glideinwms.lib import cleanupSupport, condorExe, logSupport, servicePerformance


############################################################
# KEL remove this method and just call the monitor aggregator method directly below?  we don't use the results
def aggregate_stats():
    """Aggregate monitoring data using the monitor aggregator.

    Returns:
        dict: Aggregated statistics for the frontend.
    """
    return glideinFrontendMonitorAggregator.aggregateStatus()


############################################################
class FailureCounter:
    """Tracks and counts failures within a specific time window.

    Attributes:
        my_name (str): Name or identifier for the failure counter.
        max_lifetime (int): Time window in seconds for retaining failure records.
        failure_times (list): List of timestamps for failures.
    """

    def __init__(self, my_name, max_lifetime):
        """Initializes the FailureCounter.

        Args:
            my_name (str): Name or identifier for the failure counter.
            max_lifetime (int): Time window in seconds for retaining failure records.
        """
        self.my_name = my_name
        self.max_lifetime = max_lifetime
        self.failure_times = []

    def add_failure(self, when=None):
        """Record a failure event.

        Args:
            when (float, optional): Timestamp of the failure. Defaults to the current time.
        """
        if when is None:
            when = time.time()
        self.clean_old()
        self.failure_times.append(when)

    def get_failures(self):
        """Retrieve a list of failures within the retention window.

        Returns:
            list: A list of timestamps for failures.
        """
        self.clean_old()
        return self.failure_times

    def count_failures(self):
        """Count the number of failures within the retention window.

        Returns:
            int: The number of recorded failures.
        """
        return len(self.get_failures())

    # INTERNAL

    def clean_old(self):
        """Remove outdated failure records that exceed the retention window."""
        min_time = time.time() - self.max_lifetime
        while self.failure_times and (self.failure_times[0] < min_time):
            # Assuming they are ordered
            self.failure_times.pop(0)


############################################################
def spawn_group(work_dir, group_name, action):
    """Spawn a subprocess for a specific group.

    Args:
        work_dir (str): The working directory for the frontend.
        group_name (str): The name of the group to process.
        action (str): The action to perform for the group.

    Returns:
        subprocess.Popen: The spawned child process.
    """
    command_list = [sys.executable, glideinFrontendElement.__file__, str(os.getpid()), work_dir, group_name, action]
    child = subprocess.Popen(command_list, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Set stdout and stderr to non-blocking mode
    for fd in (child.stdout.fileno(), child.stderr.fileno()):
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    return child


############################################################
def poll_group_process(group_name, child):
    """Poll the status of a group's subprocess.

    Args:
        group_name (str): The name of the group being processed.
        child (subprocess.Popen): The child process to poll.

    Returns:
        int or None: The exit code of the process if it has exited, or None if it is still running.
    """
    # Empty stdout and stderr
    try:
        tempOut = child.stdout.read()
        if tempOut:
            logSupport.log.info(f"[{group_name}]: {tempOut}")
    except OSError:
        pass  # Ignore errors

    try:
        tempErr = child.stderr.read()
        if tempErr:
            logSupport.log.warning(f"[{group_name}]: {tempErr}")
    except OSError:
        pass  # Ignore errors

    return child.poll()


############################################################
def spawn_iteration(work_dir, frontendDescript, groups, max_active, failure_dict, max_failures, action):
    """Execute a full iteration for managing groups and monitoring failures.

    Args:
        work_dir (str): The working directory for the frontend.
        frontendDescript (FrontendDescript): The frontend configuration descriptor.
        groups (list): A list of group names to process.
        max_active (int): The maximum number of active groups allowed simultaneously.
        failure_dict (dict): A dictionary mapping group names to their respective FailureCounter objects.
        max_failures (int): The maximum number of failures allowed before aborting.
        action (str): The action to perform for the iteration.

    Returns:
        list: A list of tuples containing group names and their respective wall times.
    """
    children = {}

    for group_name in groups:
        children[group_name] = {"state": "queued"}

    active_groups = 0
    groups_tofinish = len(groups)

    max_num_failures = 0
    logSupport.log.info("Starting iteration")
    try:
        while groups_tofinish > 0:
            done_something = False
            # check if any group finished by now
            for group_name in groups:
                if children[group_name]["state"] == "spawned":
                    group_rc = poll_group_process(group_name, children[group_name]["data"])
                    if group_rc is not None:  # None means "still alive"
                        if group_rc == 0:
                            children[group_name]["state"] = "finished"
                        else:
                            children[group_name]["state"] = "failed"
                            failure_dict[group_name].add_failure()
                            num_failures = failure_dict[group_name].count_failures()
                            max_num_failures = max(max_num_failures, num_failures)
                            logSupport.log.warning(
                                "Group %s terminated with exit code %i (%i recent failure)"
                                % (group_name, group_rc, num_failures)
                            )
                        children[group_name]["end_time"] = time.time()
                        servicePerformance.endPerfMetricEvent("frontend", "group_%s_iteration" % group_name)
                        active_groups -= 1
                        groups_tofinish -= 1
                        done_something = True

            # see if I can spawn more
            for group_name in groups:
                if active_groups < max_active:  # can spawn more
                    if children[group_name]["state"] == "queued":
                        children[group_name]["data"] = spawn_group(work_dir, group_name, action)
                        children[group_name]["state"] = "spawned"
                        children[group_name]["start_time"] = time.time()
                        servicePerformance.startPerfMetricEvent("frontend", "group_%s_iteration" % group_name)
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
        servicePerformance.startPerfMetricEvent("frontend", "aggregate_stats")
        stats = aggregate_stats()
        servicePerformance.endPerfMetricEvent("frontend", "aggregate_stats")
        # logSupport.log.debug(stats)

        # Create the glidefrontendmonitor classad
        fm_advertiser = glideinFrontendInterface.FrontendMonitorClassadAdvertiser(
            multi_support=glideinFrontendInterface.frontendConfig.advertise_use_multi
        )
        fm_classad = glideinFrontendInterface.FrontendMonitorClassad(frontendDescript.data["FrontendName"])
        fm_classad.setFrontendDetails(
            frontendDescript.data["FrontendName"], ",".join(groups), glideinFrontendLib.getHAMode(frontendDescript.data)
        )
        try:
            # pylint: disable=E1136
            #  (unsubscriptable-object, false positive)
            idle_jobs = {
                "Total": stats["total"]["Jobs"]["Idle"],
                "600": stats["total"]["Jobs"]["OldIdle"],
                "3600": stats["total"]["Jobs"]["Idle_3600"],
            }
            # pylint: enable=E1136
        except KeyError as err:
            idle_jobs = {"Total": 0, "600": 0, "3600": 0}
            logSupport.log.error(
                "Error in RRD Database. Setting idle_jobs[%s] Failed. Reconfig the frontend with -fix_rrd to fix this error"
                % (err,)
            )

        fm_classad.setIdleJobCount(idle_jobs)
        fm_classad.setPerfMetrics(servicePerformance.getPerfMetric("frontend"))
        # Gather performance stats from history file of each group
        for group_name in groups:
            gname = "group_%s" % group_name
            try:
                history_obj = glideinFrontendConfig.HistoryFile(work_dir, group_name, True, dict)
                pfm = servicePerformance.getPerfMetric(gname)
                pfm.metric = history_obj["perf_metrics"].metric

                fm_classad.setPerfMetrics(servicePerformance.getPerfMetric(gname))
            except Exception:
                pass  # Do not fail for non-critical actions

        fm_advertiser.addClassad(fm_classad.adParams["Name"], fm_classad)

        # Advertise glidefrontendmonitor classad to user pool
        logSupport.log.info(
            "Advertising %i %s classad(s) to the user pool" % (len(fm_advertiser.classads), fm_advertiser.adType)
        )
        try:
            set_frontend_htcondor_env(work_dir, frontendDescript)
            fm_advertiser.advertiseAllClassads()
            logSupport.log.info("Done advertising %s classad(s) to the user pool" % fm_advertiser.adType)
        except condorExe.ExeError:
            logSupport.log.error(
                "Exception occurred trying to advertise %s classad(s) to the user pool" % fm_advertiser.adType
            )
        except Exception:
            # Rethrow any other exception including stop signal
            raise
        finally:
            # Cleanup the env
            clean_htcondor_env()

        logSupport.log.info("Cleaning logs")
        cleanupSupport.cleaners.cleanup()

        if max_num_failures > max_failures:
            logSupport.log.info("Too many group failures, aborting")
            logSupport.log.debug("Failed %i times (limit %i), aborting" % (max_num_failures, max_failures))
            raise RuntimeError("Too many group failures, aborting")
    finally:
        # cleanup at exit
        # if anything goes wrong, hardkill the rest
        for group_name in children:
            if children[group_name]["state"] == "spawned":
                logSupport.log.info("Hard killing group %s" % group_name)
                servicePerformance.endPerfMetricEvent("frontend", "group_%s_iteration" % group_name)
                try:
                    os.kill(children[group_name]["data"].pid, signal.SIGKILL)
                except OSError:
                    pass  # ignore failed kills of non-existent processes

    # at this point, all groups should have been run
    timings = []
    for group_name in groups:
        timings.append((group_name, children[group_name]["end_time"] - children[group_name]["start_time"]))
    return timings


############################################################
def spawn_cleanup(work_dir, frontendDescript, groups, frontend_name, ha_mode):
    """Perform cleanup tasks for frontend processes.

    This function invalidates glidefrontendmonitor classads and performs deadvertising
    for all groups.

    Args:
        work_dir (str): The working directory.
        frontendDescript (FrontendDescript): The frontend descriptor object.
        groups (list): List of groups to clean up.
        frontend_name (str): The name of the frontend.
        ha_mode (str): High-availability mode.
    """
    try:
        set_frontend_htcondor_env(work_dir, frontendDescript)
        fm_advertiser = glideinFrontendInterface.FrontendMonitorClassadAdvertiser()
        constraint = f'(GlideFrontendName=="{frontend_name}")&&(GlideFrontendHAMode=?="{ha_mode}")'
        fm_advertiser.invalidateConstrainedClassads(constraint)
    except Exception:
        # Do not fail in case of errors.
        logSupport.log.warning("Failed to deadvertise glidefrontendmonitor classad")

    for group_name in groups:
        try:
            command_list = [
                sys.executable,
                glideinFrontendElement.__file__,
                str(os.getpid()),
                work_dir,
                group_name,
                "deadvertise",
            ]
            # logSupport.log.debug("Command list: %s" % command_list)
            child = subprocess.Popen(command_list, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # set it in non blocking mode
            for fd in (child.stdout.fileno(), child.stderr.fileno()):
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

            while poll_group_process(group_name, child) is None:
                # None means "still alive"
                time.sleep(0.01)
        except Exception:
            # never fail on cleanup
            pass


############################################################
def spawn(
    sleep_time,
    advertise_rate,
    work_dir,
    frontendDescript,
    groups,
    max_parallel_workers,
    restart_interval,
    restart_attempts,
):
    """Spawn and manage frontend groups in master/slave modes.

    This function manages the spawning and monitoring of frontend groups
    in a high-availability (HA) environment, supporting master and slave roles.

    Args:
        sleep_time (float): Time (in seconds) to sleep between iterations.
        advertise_rate (int): Rate at which to advertise classads.
        work_dir (str): The working directory for the frontend.
        frontendDescript (FrontendDescript): The frontend descriptor object.
        groups (list): List of groups to manage.
        max_parallel_workers (int): Maximum number of parallel workers.
        restart_interval (int): Interval (in seconds) before attempting a restart.
        restart_attempts (int): Maximum number of restart attempts.
    """
    num_groups = len(groups)

    # TODO: Get the ha_check_interval from the config
    ha = glideinFrontendLib.getHASettings(frontendDescript.data)
    ha_check_interval = glideinFrontendLib.getHACheckInterval(frontendDescript.data)
    mode = glideinFrontendLib.getHAMode(frontendDescript.data)
    master_frontend_name = ""
    if mode == "slave":
        master_frontend_name = ha.get("ha_frontends")[0].get("frontend_name")

    active = mode == "master"
    hibernate = shouldHibernate(frontendDescript, work_dir, ha, mode, groups)

    logSupport.log.info("Frontend started with mode = %s" % mode)
    try:
        # Service will exit on signal only.
        # This infinite loop is for the slave to go back into hibernation
        # once the master becomes alive.
        # Master never loops infinitely here, but instead it does in
        # the inner loop while(mode=='master') ...
        while True:
            while hibernate:
                # If I am slave enter hibernation cycle while Master is alive
                logSupport.log.info("Master Frontend %s is online. Hibernating." % master_frontend_name)
                time.sleep(ha_check_interval)
                hibernate = shouldHibernate(frontendDescript, work_dir, ha, mode, groups)

            # We broke out of hibernation cycle
            # Either Master has disappeared or I am the Master
            if mode == "slave":
                logSupport.log.info("Master frontend %s is offline. Activating slave frontend." % master_frontend_name)
                active = True

            failure_dict = {}
            for group in groups:
                failure_dict[group] = FailureCounter(group, restart_interval)

            while (mode == "master") or ((mode == "slave") and active):
                servicePerformance.startPerfMetricEvent("frontend", "iteration")
                # start_time = time.time()
                timings = spawn_iteration(
                    work_dir, frontendDescript, groups, max_parallel_workers, failure_dict, restart_attempts, "run"
                )
                servicePerformance.endPerfMetricEvent("frontend", "iteration")
                # end_time = time.time()
                elapsed_time = servicePerformance.getPerfMetricEventLifetime("frontend", "iteration")
                if elapsed_time < sleep_time:
                    real_sleep_time = sleep_time - elapsed_time
                    logSupport.log.info("Sleep %.1f sec" % real_sleep_time)
                    time.sleep(real_sleep_time)
                else:
                    logSupport.log.info(f"No sleeping this loop, took {elapsed_time:.1f} sec > {sleep_time:.1f} sec")

                # order the groups by walltime
                # longest walltime first
                timings.sort(key=lambda x: x[1])
                # recreate the groups list, with new ordering
                groups = [el[0] for el in timings]
                assert num_groups == len(groups), "Something went wrong, number of groups changed"

                if mode == "slave":
                    # If we are slave, check if master is back and if so
                    # deadvertise my classads and hibernate
                    hibernate = shouldHibernate(frontendDescript, work_dir, ha, mode, groups)

                    if hibernate:
                        active = False
                        logSupport.log.info("Master frontend %s is back online" % master_frontend_name)
                        logSupport.log.info("Deadvertise my ads and enter hibernation cycle")
                        spawn_cleanup(work_dir, frontendDescript, groups, frontendDescript.data["FrontendName"], mode)
                    else:
                        logSupport.log.info("Master frontend %s is still offline" % master_frontend_name)

    finally:
        # We have been asked to terminate
        logSupport.log.info("Deadvertise my ads")
        spawn_cleanup(work_dir, frontendDescript, groups, frontendDescript.data["FrontendName"], mode)


############################################################
def shouldHibernate(frontendDescript, work_dir, ha, mode, groups):
    """Determine if the frontend should enter hibernation.

    Check if the frontend is running in HA mode. If run in master mode never
    hibernate. If run in slave mode, hibernate if master is active.

    Args:
        frontendDescript (FrontendDescript): The frontend descriptor object.
        work_dir (str): The working directory for the frontend.
        ha (dict): High-availability settings.
        mode (str): Current operating mode ("master" or "slave").
        groups (list): List of groups being managed.

    Returns:
        bool: True if this Frontend should hibernate, False otherwise.
    """

    servicePerformance.startPerfMetricEvent("frontend", "ha_check")
    if mode == "slave":
        master_frontend_name = str(ha.get("ha_frontends")[0].get("frontend_name"))

        for group in groups:
            element = glideinFrontendElement.glideinFrontendElement(os.getpid(), work_dir, group, "run")
            # Set environment required to query factory collector
            set_frontend_htcondor_env(work_dir, frontendDescript, element)

            for factory_pool in element.factory_pools:
                try:
                    factory_pool_node = factory_pool[0]
                    master_classads = glideinFrontendInterface.findMasterFrontendClassads(
                        factory_pool_node, master_frontend_name
                    )

                    if master_classads:
                        # Found some classads in one of the collectors
                        # Cleanup the env and return True
                        clean_htcondor_env()
                        servicePerformance.endPerfMetricEvent("frontend", "ha_check")
                        return True
                except RuntimeError:
                    # Failed to talk
                    if not factory_pool_node:
                        factory_pool_node = ""
                    msg = "Failed to talk to the factory_pool {} to get the status of Master frontend {}".format(
                        factory_pool_node,
                        master_frontend_name,
                    )
                    logSupport.log.warning(msg)
                    msg = "Exception talking to the factory_pool {} to get the status of Master frontend {}: ".format(
                        factory_pool_node,
                        master_frontend_name,
                    )
                    logSupport.log.exception(msg)

        # Cleanup the env
        clean_htcondor_env()

        # NOTE:
        # If we got this far with no errors then we could not find
        # active master frontend. We should not hibernate as slave
        # However, if there were errors checking with factory pool
        # then the master frontend could be down so its safe to wake
        # up and start advertising.

    servicePerformance.endPerfMetricEvent("frontend", "ha_check")
    return False


def clear_diskcache_dir(work_dir):
    """Clear the disk cache directory and recreate it.

    This function removes the existing cache directory used by the frontend,
    handles any errors if the directory does not exist, and recreates it.

    Args:
        work_dir (str): The working directory for the frontend.

    Raises:
        OSError: If an error occurs while attempting to remove the cache directory.
    """
    cache_dir = os.path.join(work_dir, glideinFrontendConfig.frontendConfig.cache_dir)
    try:
        shutil.rmtree(cache_dir)
    except OSError as ose:
        if ose.errno != 2:  # errno 2 is okay (directory missing - Maybe it's the first execution?)
            logSupport.log.exception(f"Error removing cache directory {cache_dir}")
            raise
    os.mkdir(cache_dir)


def set_frontend_htcondor_env(work_dir, frontendDescript, element=None):
    """Set the HTCondor environment for the frontend.

    Configures the environment variables required for HTCondor operations
    based on the frontend description and element.

    The Collector DN is only in the group's mapfile. Just get first one.

    Args:
        work_dir (str): The working directory for the frontend.
        frontendDescript (FrontendDescript): The frontend descriptor object.
        element (Element, optional): The specific group element. Defaults to None.
    """
    groups = frontendDescript.data["Groups"].split(",")
    if groups:
        if element is None:
            element = glideinFrontendElement.glideinFrontendElement(os.getpid(), work_dir, groups[0], "run")
        htc_env = {
            "CONDOR_CONFIG": frontendDescript.data["CondorConfig"],
            "X509_USER_PROXY": frontendDescript.data["ClassAdProxy"],
            "_CONDOR_CERTIFICATE_MAPFILE": element.elementDescript.element_data["MapFile"],
        }
        set_env(htc_env)


def set_env(env):
    """Set the environment variables from a dictionary.

    Args:
        env (dict): Dictionary of environment variables and their values.
    """
    for var, value in env.items():
        os.environ[var] = value


def clean_htcondor_env():
    """Remove HTCondor-related environment variables.

    This function clears specific environment variables used by HTCondor
    to prevent conflicts with other processes.
    """
    for v in ("CONDOR_CONFIG", "_CONDOR_CERTIFICATE_MAPFILE", "X509_USER_PROXY"):
        if os.environ.get(v):
            del os.environ[v]


############################################################


def spawn_removal(work_dir, frontendDescript, groups, max_parallel_workers, removal_action):
    """Perform group removal operations.

    This function handles removing groups based on the specified removal action.

    Args:
        work_dir (str): The working directory for the frontend.
        frontendDescript (FrontendDescript): The frontend descriptor object.
        groups (list): List of group names to process.
        max_parallel_workers (int): Maximum number of parallel workers.
        removal_action (str): The specific removal action to perform.
    """
    failure_dict = {group: FailureCounter(group, 3600) for group in groups}
    spawn_iteration(work_dir, frontendDescript, groups, max_parallel_workers, failure_dict, 1, removal_action)


############################################################
def cleanup_environ():
    """Clean up environment variables.

    Removes environment variables related to CONDOR and X509 to ensure
    a clean execution environment.
    """
    for val in list(os.environ.keys()):
        val_low = val.lower()
        if val_low.startswith("_condor_"):
            del os.environ[val]
        elif val_low.startswith("x509_"):
            del os.environ[val]


############################################################
def main(work_dir, action):
    """Main entry point for the glideinFrontend.

    This function initializes logging, processes configuration, and starts
    the frontend based on the specified action.

    Args:
        work_dir (str): The working directory for the frontend.
        action (str): The action to perform (e.g., "run", "removeIdle").

    Raises:
        ValueError: If an unknown action is specified.
        Exception: For any errors during initialization or processing.
    """
    startup_time = time.time()

    glideinFrontendConfig.frontendConfig.frontend_descript_file = os.path.join(
        work_dir, glideinFrontendConfig.frontendConfig.frontend_descript_file
    )
    frontendDescript = glideinFrontendConfig.FrontendDescript(work_dir)

    # Configure logging
    # the log dir is shared between the frontend main and the groups, so use a subdirectory
    logSupport.log_dir = os.path.join(frontendDescript.data["LogDir"], "frontend")
    logSupport.log = logSupport.get_logger_with_handlers("frontend", logSupport.log_dir, frontendDescript.data)

    logSupport.log.info("Logging initialized")
    logSupport.log.debug(f"Frontend startup time: {startup_time}")

    clear_diskcache_dir(work_dir)

    try:
        cleanup_environ()
        # We use a dedicated config... ignore the system-wide
        os.environ["CONDOR_CONFIG"] = frontendDescript.data["CondorConfig"]

        sleep_time = int(frontendDescript.data["LoopDelay"])
        advertise_rate = int(frontendDescript.data["AdvertiseDelay"])
        max_parallel_workers = int(frontendDescript.data["GroupParallelWorkers"])
        restart_attempts = int(frontendDescript.data["RestartAttempts"])
        restart_interval = int(frontendDescript.data["RestartInterval"])

        groups = sorted(frontendDescript.data["Groups"].split(","))

        glideinFrontendMonitorAggregator.monitorAggregatorConfig.config_frontend(
            os.path.join(work_dir, "monitor"), groups
        )
    except Exception:
        logSupport.log.exception("Exception occurred configuring monitoring: ")
        raise

    glideinFrontendMonitoring.write_frontend_descript_xml(frontendDescript, os.path.join(work_dir, "monitor/"))
    logSupport.log.info(f"Enabled groups: {groups}")

    # Create lock file
    pid_obj = glideinFrontendPidLib.FrontendPidSupport(work_dir)

    # Start the main operation
    try:
        pid_obj.register(action)
    except glideinFrontendPidLib.pidSupport.AlreadyRunning as err:
        pid_obj.load_registered()
        logSupport.log.exception(
            f"Failed starting Frontend with action {action}. "
            f"Instance with pid {pid_obj.mypid} is already running for action {pid_obj.action_type}. "
            f"Exception during pid registration: {err}"
        )
        raise

    try:
        if action == "run":
            spawn(
                sleep_time,
                advertise_rate,
                work_dir,
                frontendDescript,
                groups,
                max_parallel_workers,
                restart_interval,
                restart_attempts,
            )
        elif action in (
            "removeWait",
            "removeIdle",
            "removeAll",
            "removeWaitExcess",
            "removeIdleExcess",
            "removeAllExcess",
        ):
            spawn_removal(work_dir, frontendDescript, groups, max_parallel_workers, action)
        else:
            raise ValueError(f"Unknown action: {action}")
    except KeyboardInterrupt:
        logSupport.log.info("Received signal...exit")
    except HUPException:
        logSupport.log.info("Received SIGHUP, reload config")
        pid_obj.relinquish()
        os.execv(
            os.path.join(glideinFrontendLib.__file__, "../creation/reconfig_frontend"),
            ["reconfig_frontend", "-sighupreload", "-xml", "/etc/gwms-frontend/frontend.xml"],
        )
    except Exception:
        logSupport.log.exception("Exception occurred trying to spawn: ")
    finally:
        pid_obj.relinquish()


############################################################
#
# S T A R T U P
#
############################################################


class HUPException(Exception):
    """Exception for handling a SIGHUP signal, used to trigger reconfiguration."""

    pass


def termsignal(signr, frame):
    """Generic signal handler, used for SIGTERM and SIGQUIT.

    Args:
        signr (int): Signal number.
        frame (Frame object or None): Current stack frame where the signal was received.

    Raises:
        KeyboardInterrupt: Whenever a signal is received.
    """
    raise KeyboardInterrupt("Received signal %s" % signr)


def hupsignal(signr, frame):
    """Generic signal handler, used for SIGHUP. Raises `HUPException` to trigger a reconfiguration.

    Args:
        signr (int): Signal number.
        frame (Frame object or None): Current stack frame where the signal was received.

    Raises:
        HUPException: Whenever SIGHUP is received, to trigger a reconfiguration.
    """
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    raise HUPException("Received signal %s" % signr)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, termsignal)
    signal.signal(signal.SIGQUIT, termsignal)
    signal.signal(signal.SIGHUP, hupsignal)

    if len(sys.argv) == 2:
        action = "run"
    else:
        action = sys.argv[2]

    main(sys.argv[1], action)
