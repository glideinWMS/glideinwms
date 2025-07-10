#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module contains the main class and related utilities for the glideinFrontend.

This script processes Frontend group activities, handling the interaction with
factories and job schedulers, and sending requests for submitting or removing glideins.

Args:
    $1 (int): parent PID
    $2 (str): work dir
    $3 (str): group_name
    $4 (str, optional): operation type (defaults to "run")
"""

import copy
import getpass
import os
import re
import socket
import sys
import tempfile
import time
import traceback

from importlib import import_module
from pathlib import Path

from glideinwms.frontend import (
    glideinFrontendConfig,
    glideinFrontendDowntimeLib,
    glideinFrontendInterface,
    glideinFrontendLib,
    glideinFrontendMonitoring,
    glideinFrontendPidLib,
    glideinFrontendPlugins,
)

# from glideinwms.lib.util import file_tmp2final
from glideinwms.lib import cleanupSupport, condorMonitor, logSupport, pubCrypto, servicePerformance, token_util
from glideinwms.lib.disk_cache import DiskCache
from glideinwms.lib.fork import fork_in_bg, ForkManager, wait_for_pids
from glideinwms.lib.pidSupport import register_sighandler
from glideinwms.lib.util import safe_boolcomp

# this should not be needed in RPM install: sys.path.append(os.path.join(sys.path[0], "../.."))

# credential generator plugins support
# TODO: This path should come from the frontend configuration, but it's not available yet.
sys.path.append("/etc/gwms-frontend/plugin.d")
plugins = {}

###########################################################
# Support class that mimics the 2.7 collections.Counter class
#
# Not a 1-to-1 implementation though... just straight minimum
# to support auto initialization to 0
# This can be deleted once we switch to python3


class CounterWrapper:
    """Support class that mimics the 2.7 collections.Counter class.

    Provides auto-initialization to 0 for missing keys. Not a 1-to-1 implementation.
    Used for maintaining counts without explicit initialization.
    """

    def __init__(self, dict_el):
        """Initialize the CounterWrapper.

        Args:
            dict_el (dict): Dictionary to wrap and use for counting.
        """
        self.dict_el = dict_el

    def has_key(self, keyid):
        """Check if key is in dictionary.

        Args:
            keyid: Key to check for.

        Returns:
            bool: True if key exists, False otherwise.
        """
        return keyid in self.dict_el

    def __contains__(self, keyid):
        """Check for membership using 'in'.

        Args:
            keyid: Key to check.

        Returns:
            bool: True if key exists, False otherwise.
        """
        return keyid in self.dict_el

    def __getitem__(self, keyid):
        """Get item or initialize to 0 if missing.

        Args:
            keyid: Key to retrieve.

        Returns:
            int: Value associated with the key or 0 if missing.
        """
        try:
            return self.dict_el[keyid]
        except KeyError:
            self.dict_el[keyid] = 0
            return self.dict_el[keyid]

    def __setitem__(self, keyid, val):
        """Set value for a key.

        Args:
            keyid: Key to set.
            val: Value to assign.
        """
        self.dict_el[keyid] = val

    def __delitem__(self, keyid):
        """Delete a key from the dictionary.

        Args:
            keyid: Key to delete.
        """
        del self.dict_el[keyid]


#####################################################
#
# Main class for the module


class glideinFrontendElement:
    """Main class for processing the Frontend group activity.

    Spawned by glideinFrontend. Aware of the available Entries in the Factory and the job requests from schedds.
    Sends requests to the Factory: either to submit new glideins, or to remove them.
    """

    def __init__(self, parent_pid, work_dir, group_name, action):
        """Initialize the glideinFrontendElement instance.

        Args:
            parent_pid (int): Parent process ID.
            work_dir (str): Working directory.
            group_name (str): Name of the group.
            action (str): Action type (e.g. 'run', 'deadvertise', etc.).
        """
        self.parent_pid = parent_pid
        self.work_dir = work_dir
        self.group_name = group_name
        self.action = action

        self.elementDescript = glideinFrontendConfig.ElementMergedDescript(self.work_dir, self.group_name)
        self.paramsDescript = glideinFrontendConfig.ParamsDescript(self.work_dir, self.group_name)
        self.signatureDescript = glideinFrontendConfig.GroupSignatureDescript(self.work_dir, self.group_name)
        self.attr_dict = glideinFrontendConfig.AttrsDescript(self.work_dir, self.group_name).data

        # Automatically initialize history object data to dictionaries
        # PS: The default initialization is not to CounterWrapper, to avoid
        # saving custom classes to disk
        self.history_obj = glideinFrontendConfig.HistoryFile(self.work_dir, self.group_name, True, dict)
        # Reset the perf_metrics info
        self.history_obj["perf_metrics"] = {}

        self.startup_time = time.time()

        # All the names here must be consistent with the ones in creation/lib
        # self.sleep_time = int(self.elementDescript.frontend_data['LoopDelay'])
        self.frontend_name = self.elementDescript.frontend_data["FrontendName"]
        self.web_url = self.elementDescript.frontend_data["WebURL"]
        self.monitoring_web_url = self.elementDescript.frontend_data["MonitoringWebURL"]

        self.security_name = self.elementDescript.merged_data["SecurityName"]
        self.factory_pools = self.elementDescript.merged_data["FactoryCollectors"]

        # If the IgnoreDownEntries knob is set in the group use that, otherwise use the global one
        if self.elementDescript.element_data.get("IgnoreDownEntries", "") != "":
            self.ignore_down_entries = self.elementDescript.element_data["IgnoreDownEntries"] == "True"
        else:
            self.ignore_down_entries = self.elementDescript.frontend_data.get("IgnoreDownEntries") == "True"
        # TODO: do I need like ignore_down_entries with "" group default? How are other parameters handling defaults?
        self.ramp_up_attenuation = float(self.elementDescript.element_data["RampUpAttenuation"])
        self.min_running = int(self.elementDescript.element_data["MinRunningPerEntry"])
        self.max_running = int(self.elementDescript.element_data["MaxRunningPerEntry"])
        self.fraction_running = float(self.elementDescript.element_data["FracRunningPerEntry"])
        self.max_idle = int(self.elementDescript.element_data["MaxIdlePerEntry"])
        self.reserve_idle = int(self.elementDescript.element_data["ReserveIdlePerEntry"])
        self.idle_lifetime = int(self.elementDescript.element_data["IdleLifetime"])
        self.max_vms_idle = int(self.elementDescript.element_data["MaxIdleVMsPerEntry"])
        self.curb_vms_idle = int(self.elementDescript.element_data["CurbIdleVMsPerEntry"])
        self.total_max_glideins = int(self.elementDescript.element_data["MaxRunningTotal"])
        self.total_curb_glideins = int(self.elementDescript.element_data["CurbRunningTotal"])
        self.total_max_vms_idle = int(self.elementDescript.element_data["MaxIdleVMsTotal"])
        self.total_curb_vms_idle = int(self.elementDescript.element_data["CurbIdleVMsTotal"])
        self.fe_total_max_glideins = int(self.elementDescript.frontend_data["MaxRunningTotal"])
        self.fe_total_curb_glideins = int(self.elementDescript.frontend_data["CurbRunningTotal"])
        self.fe_total_max_vms_idle = int(self.elementDescript.frontend_data["MaxIdleVMsTotal"])
        self.fe_total_curb_vms_idle = int(self.elementDescript.frontend_data["CurbIdleVMsTotal"])
        self.global_total_max_glideins = int(self.elementDescript.frontend_data["MaxRunningTotalGlobal"])
        self.global_total_curb_glideins = int(self.elementDescript.frontend_data["CurbRunningTotalGlobal"])
        self.global_total_max_vms_idle = int(self.elementDescript.frontend_data["MaxIdleVMsTotalGlobal"])
        self.global_total_curb_vms_idle = int(self.elementDescript.frontend_data["CurbIdleVMsTotalGlobal"])

        self.p_glidein_min_memory = int(self.elementDescript.element_data["PartGlideinMinMemory"])
        self.max_matchmakers = int(self.elementDescript.element_data["MaxMatchmakers"])

        self.removal_type = self.elementDescript.element_data["RemovalType"]
        self.removal_wait = int(self.elementDescript.element_data["RemovalWait"])
        self.removal_requests_tracking = self.elementDescript.element_data["RemovalRequestsTracking"]
        self.removal_margin = int(self.elementDescript.element_data["RemovalMargin"])

        self.schedd_cache = {"timestamp": None, "data": None}

        # Default behavior: Use factory proxies unless configure overrides it
        self.x509_proxy_plugin = None

        # If not None, this is a request for removal of glideins only (i.e. do not ask for more)
        self.request_removal_wtype = None
        self.request_removal_excess_only = False
        self.ha_mode = glideinFrontendLib.getHAMode(self.elementDescript.frontend_data)

        # Initializing some monitoring variables
        self.count_real_jobs = {}
        self.count_real_glideins = {}

        self.glidein_config_limits = {}
        self.set_glidein_config_limits()

        # Initialize the cache for the schedd queries
        cache_dir = os.path.join(work_dir, glideinFrontendConfig.frontendConfig.cache_dir)
        condorMonitor.disk_cache = DiskCache(cache_dir)

    def configure(self):
        """Perform initial configuration of the element.

        Sets up group directories, logging, monitoring, proxy plugins, token lifetime,
        and environment variables for Condor and X509.
        """
        group_dir = glideinFrontendConfig.get_group_dir(self.work_dir, self.group_name)

        # the log dir is shared between the frontend main and the groups, so use a subdir
        logSupport.log_dir = glideinFrontendConfig.get_group_dir(
            self.elementDescript.frontend_data["LogDir"], self.group_name
        )

        # Configure frontend group process logging
        logSupport.log = logSupport.get_logger_with_handlers(
            self.group_name, logSupport.log_dir, self.elementDescript.frontend_data
        )

        # We will be starting often, so reduce the clutter
        # logSupport.log.info("Logging initialized")

        glideinFrontendMonitoring.monitoringConfig.monitor_dir = glideinFrontendConfig.get_group_dir(
            os.path.join(self.work_dir, "monitor"), self.group_name
        )
        glideinFrontendInterface.frontendConfig.advertise_use_tcp = self.elementDescript.frontend_data[
            "AdvertiseWithTCP"
        ] in ("True", "1")
        glideinFrontendInterface.frontendConfig.advertise_use_multi = self.elementDescript.frontend_data[
            "AdvertiseWithMultiple"
        ] in ("True", "1")

        if self.elementDescript.merged_data["Proxies"]:
            proxy_plugins = glideinFrontendPlugins.proxy_plugins
            if not proxy_plugins.get(self.elementDescript.merged_data["ProxySelectionPlugin"]):
                logSupport.log.warning(
                    "Invalid ProxySelectionPlugin '%s', supported plugins are %s"
                    % (self.elementDescript.merged_data["ProxySelectionPlugin"], list(proxy_plugins.keys()))
                )
                return 1
            self.x509_proxy_plugin = proxy_plugins[self.elementDescript.merged_data["ProxySelectionPlugin"]](
                group_dir, glideinFrontendPlugins.createCredentialList(self.elementDescript)
            )
        self.idtoken_lifetime = int(self.elementDescript.merged_data.get("IDTokenLifetime", 24))
        # The default token KEY name is the username uppercase, e.g. FRONTEND or DECISIONENGINE
        default_key_name = getpass.getuser().upper()
        self.idtoken_keyname = self.elementDescript.merged_data.get("IDTokenKeyname", default_key_name)

        # set the condor configuration and GSI setup globally, so I don't need to worry about it later on
        os.environ["CONDOR_CONFIG"] = self.elementDescript.frontend_data["CondorConfig"]
        os.environ["_CONDOR_CERTIFICATE_MAPFILE"] = self.elementDescript.element_data["MapFile"]
        os.environ["X509_USER_PROXY"] = self.elementDescript.frontend_data["ClassAdProxy"]

    def set_glidein_config_limits(self):
        """Set various limits and curbs configured in the frontend config.

        Populates self.glidein_config_limits with values from frontend and element data.
        """
        fe_data_keys = (
            "MaxRunningTotal",
            "CurbRunningTotal",
            "MaxIdleVMsTotal",
            "CurbIdleVMsTotal",
            "MaxRunningTotalGlobal",
            "CurbRunningTotalGlobal",
            "MaxIdleVMsTotalGlobal",
            "CurbIdleVMsTotalGlobal",
        )

        el_data_keys = (
            "MaxRunningPerEntry",
            "MinRunningPerEntry",
            "MaxIdlePerEntry",
            "ReserveIdlePerEntry",
            "MaxIdleVMsPerEntry",
            "CurbIdleVMsPerEntry",
            "MaxRunningTotal",
            "CurbRunningTotal",
            "MaxIdleVMsTotal",
            "CurbIdleVMsTotal",
        )
        # Add frontend global config info
        for key in fe_data_keys:
            ad_key = "Frontend%s" % (key)
            self.glidein_config_limits[ad_key] = int(self.elementDescript.frontend_data[key])

        # Add frontend group config info
        for key in el_data_keys:
            ad_key = "Group%s" % (key)
            self.glidein_config_limits[ad_key] = int(self.elementDescript.element_data[key])

    def main(self):
        """Run the main event loop for the frontend element.

        Handles configuration, lock file creation, signal catching, and main iteration.
        Returns an exit code based on completion or error status.

        Returns:
            int: Return code (0 for success, 1 for interrupt, 2 for exception).
        """
        self.configure()
        # create lock file
        pid_obj = glideinFrontendPidLib.ElementPidSupport(self.work_dir, self.group_name)
        rc = 0
        pid_obj.register(self.parent_pid)
        try:
            # logSupport.log.info("Starting up")
            rc = self.iterate()
        except KeyboardInterrupt:
            logSupport.log.info("Received signal...exit")
            rc = 1
        except Exception:
            # TODO is tb needed? Don't we print the exception twice?
            tb = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            logSupport.log.exception("Unhandled exception, dying: %s" % tb)
            rc = 2
        finally:
            pid_obj.relinquish()

        return rc

    def iterate(self):
        """Perform the main iteration logic for frontend group operations.

        This method handles actions based on the type set (run, deadvertise, removal operations, etc.)
        and manages state and statistics writing.

        Returns:
            int: 0 if operation is successful, 1 for unknown action.
        """
        self.stats = {"group": glideinFrontendMonitoring.groupStats()}

        if "X509Proxy" not in self.elementDescript.frontend_data:
            self.published_frontend_name = f"{self.frontend_name}.{self.group_name}"
        else:
            # if using a VO proxy, label it as such
            # this way we don't risk of using the wrong proxy on the other side
            # if/when we decide to stop using the proxy
            self.published_frontend_name = f"{self.frontend_name}.XPVO_{self.group_name}"

        if self.action == "run":
            logSupport.log.info("Iteration at %s" % time.ctime())
            done_something = self.iterate_one()  # pylint: disable=assignment-from-none
            logSupport.log.info("iterate_one status: %s" % str(done_something))

            logSupport.log.info("Writing stats")
            try:
                servicePerformance.startPerfMetricEvent(self.group_name, "write_monitoring_stats")
                write_stats(self.stats)
                servicePerformance.endPerfMetricEvent(self.group_name, "write_monitoring_stats")
            except KeyboardInterrupt:
                raise  # this is an exit signal, pass through
            except Exception:
                # never fail for stats reasons!
                logSupport.log.exception("Exception occurred writing stats: ")
            finally:
                # Save the history_obj last even in case of exceptions
                self.history_obj["perf_metrics"] = servicePerformance.getPerfMetric(self.group_name)
                self.history_obj.save()

            # do it just before the sleep
            cleanupSupport.cleaners.cleanup()
        elif self.action == "deadvertise":
            logSupport.log.info("Deadvertize my ads")
            self.deadvertiseAllClassads()
        elif self.action in (
            "removeWait",
            "removeIdle",
            "removeAll",
            "removeWaitExcess",
            "removeIdleExcess",
            "removeAllExcess",
        ):
            # use the standard logic for most things, but change what is being requested
            if self.action.endswith("Excess"):
                self.request_removal_wtype = self.action[6:-6].upper()
                self.request_removal_excess_only = True
                logSupport.log.info("Requesting removal of %s excess glideins" % self.request_removal_wtype)
            else:
                self.request_removal_wtype = self.action[6:].upper()
                self.request_removal_excess_only = False
                logSupport.log.info("Requesting removal of %s glideins" % self.request_removal_wtype)
            done_something = self.iterate_one()  # pylint: disable=assignment-from-none
            logSupport.log.info("iterate_one status: %s" % str(done_something))
            # no saving or disk cleanup... be quick
        else:
            logSupport.log.warning("Unknown action: %s" % self.action)
            return 1

        return 0

    def deadvertiseAllClassads(self):
        """Invalidate all glideclient, glideclientglobal, and glideresource classads."""
        # Invalidate all glideclient glideclientglobal classads
        for factory_pool in self.factory_pools:
            factory_pool_node = factory_pool[0]
            try:
                glideinFrontendInterface.deadvertizeAllWork(
                    factory_pool_node, self.published_frontend_name, ha_mode=self.ha_mode
                )
            except Exception:
                logSupport.log.warning("Failed to deadvertise work on %s" % factory_pool_node)

            try:
                glideinFrontendInterface.deadvertizeAllGlobals(
                    factory_pool_node, self.published_frontend_name, ha_mode=self.ha_mode
                )
            except Exception:
                logSupport.log.warning("Failed to deadvertise globals on %s" % factory_pool_node)

        # Invalidate all glideresource classads
        try:
            resource_advertiser = glideinFrontendInterface.ResourceClassadAdvertiser()
            resource_advertiser.invalidateConstrainedClassads(
                f'(GlideClientName=="{self.published_frontend_name}")&&(GlideFrontendHAMode=?="{self.ha_mode}")'
            )
        except Exception:
            logSupport.log.warning("Failed to deadvertise resources classads")

    def iterate_one(self):
        """Query schedd, entry, and glidein status using child processes.

        Performs multi-fork querying, collects data, updates internal state, and logs job/glidein statistics.
        """
        logSupport.log.info("Querying schedd, entry, and glidein status using child processes.")

        forkm_obj = ForkManager()

        # query globals and entries
        idx = 0
        for factory_pool in self.factory_pools:
            idx += 1
            forkm_obj.add_fork(("factory", idx), self.query_factory, factory_pool)

        ## schedd
        idx = 0
        for schedd_name in self.getScheddList():
            idx += 1
            forkm_obj.add_fork(("schedd", idx), self.get_condor_q, schedd_name)

        ## resource
        forkm_obj.add_fork(("collector", 0), self.get_condor_status)

        logSupport.log.debug("%i child query processes started" % len(forkm_obj))
        try:
            servicePerformance.startPerfMetricEvent(self.group_name, "condor_queries")
            pipe_out = forkm_obj.fork_and_collect()
            servicePerformance.endPerfMetricEvent(self.group_name, "condor_queries")
        except RuntimeError:
            # expect all errors logged already
            logSupport.log.info(
                "Missing schedd, factory entry, and/or current glidein state information. "
                "Unable to calculate required glideins, terminating loop."
            )
            return
        logSupport.log.info("All children terminated")
        del forkm_obj

        self.globals_dict = {}
        self.glidein_dict = {}
        self.factoryclients_dict = {}
        self.condorq_dict = {}

        for pkel in pipe_out:
            ptype, idx = pkel
            if ptype == "factory":
                # one of the factories
                pglobals_dict, pglidein_dict, pfactoryclients_dict = pipe_out[pkel]
                self.globals_dict.update(pglobals_dict)
                self.glidein_dict.update(pglidein_dict)
                self.factoryclients_dict.update(pfactoryclients_dict)
                del pglobals_dict
                del pglidein_dict
                del pfactoryclients_dict
            elif ptype == "schedd":
                # one of the schedds
                pcondorq_dict = pipe_out[pkel]
                self.condorq_dict.update(pcondorq_dict)
                del pcondorq_dict
            # collector dealt with outside the loop because there is only one
            # nothing else left

        (self.status_dict, self.fe_counts, self.global_counts, self.status_schedd_dict) = pipe_out[("collector", 0)]

        # M2Crypto objects are not pickleable, so do the transformation here
        self.populate_pubkey()
        self.identify_bad_schedds()
        self.populate_condorq_dict_types()

        condorq_dict_types = self.condorq_dict_types
        condorq_dict_abs = glideinFrontendLib.countCondorQ(self.condorq_dict)

        self.stats["group"].logJobs(
            {
                "Total": condorq_dict_abs,
                "Idle": condorq_dict_types["Idle"]["abs"],
                "OldIdle": condorq_dict_types["OldIdle"]["abs"],
                "Idle_3600": condorq_dict_types["Idle_3600"]["abs"],
                "Running": condorq_dict_types["Running"]["abs"],
            }
        )

        logSupport.log.info(
            "Jobs found total %i idle %i (good %i, old(10min %i, 60min %i), voms %i) running %i"
            % (
                condorq_dict_abs,
                condorq_dict_types["IdleAll"]["abs"],
                condorq_dict_types["Idle"]["abs"],
                condorq_dict_types["OldIdle"]["abs"],
                condorq_dict_types["Idle_3600"]["abs"],
                condorq_dict_types["VomsIdle"]["abs"],
                condorq_dict_types["Running"]["abs"],
            )
        )
        self.populate_status_dict_types()
        glideinFrontendLib.appendRealRunning(self.condorq_dict_running, self.status_dict_types["Running"]["dict"])

        self.stats["group"].logGlideins(
            {
                "Total": self.status_dict_types["Total"]["abs"],
                "Idle": self.status_dict_types["Idle"]["abs"],
                "Running": self.status_dict_types["Running"]["abs"],
                "Failed": self.status_dict_types["Failed"]["abs"],
                "TotalCores": self.status_dict_types["TotalCores"]["abs"],
                "IdleCores": self.status_dict_types["IdleCores"]["abs"],
                "RunningCores": self.status_dict_types["RunningCores"]["abs"],
            }
        )

        total_glideins = self.status_dict_types["Total"]["abs"]
        total_running_glideins = self.status_dict_types["Running"]["abs"]
        total_idle_glideins = self.status_dict_types["Idle"]["abs"]
        # not used - they should be removed MM
        # total_failed_glideins = self.status_dict_types['Failed']['abs']
        # total_cores = self.status_dict_types['TotalCores']['abs']
        # total_running_cores = self.status_dict_types['RunningCores']['abs']
        # total_idle_cores = self.status_dict_types['IdleCores']['abs']

        logSupport.log.info(
            "Group glideins found total %i limit %i curb %i; of these idle %i limit %i curb %i running %i"
            % (
                total_glideins,
                self.total_max_glideins,
                self.total_curb_glideins,
                total_idle_glideins,
                self.total_max_vms_idle,
                self.total_curb_vms_idle,
                total_running_glideins,
            )
        )

        fe_total_glideins = self.fe_counts["Total"]
        fe_total_idle_glideins = self.fe_counts["Idle"]
        logSupport.log.info(
            "Frontend glideins found total %i limit %i curb %i; of these idle %i limit %i curb %i"
            % (
                fe_total_glideins,
                self.fe_total_max_glideins,
                self.fe_total_curb_glideins,
                fe_total_idle_glideins,
                self.fe_total_max_vms_idle,
                self.fe_total_curb_vms_idle,
            )
        )

        global_total_glideins = self.global_counts["Total"]
        global_total_idle_glideins = self.global_counts["Idle"]
        logSupport.log.info(
            "Overall slots found total %i limit %i curb %i; of these idle %i limit %i curb %i"
            % (
                global_total_glideins,
                self.global_total_max_glideins,
                self.global_total_curb_glideins,
                global_total_idle_glideins,
                self.global_total_max_vms_idle,
                self.global_total_curb_vms_idle,
            )
        )

        # Update x509 user map and give proxy plugin a chance
        # to update based on condor stats
        if self.x509_proxy_plugin:
            logSupport.log.info("Updating usermap")
            self.x509_proxy_plugin.update_usermap(
                self.condorq_dict, condorq_dict_types, self.status_dict, self.status_dict_types
            )

        # here we have all the data needed to build a GroupAdvertizeType object
        descript_obj = glideinFrontendInterface.FrontendDescript(
            self.published_frontend_name,
            self.frontend_name,
            self.group_name,
            self.web_url,
            self.signatureDescript.frontend_descript_fname,
            self.signatureDescript.group_descript_fname,
            self.signatureDescript.signature_type,
            self.signatureDescript.frontend_descript_signature,
            self.signatureDescript.group_descript_signature,
            x509_proxies_plugin=self.x509_proxy_plugin,
            ha_mode=self.ha_mode,
        )
        descript_obj.add_monitoring_url(self.monitoring_web_url)

        # reuse between loops might be a good idea, but this will work for now
        key_builder = glideinFrontendInterface.Key4AdvertizeBuilder()

        logSupport.log.info("Match")

        # extract only the attribute names from format list
        self.condorq_match_list = [f[0] for f in self.elementDescript.merged_data["JobMatchAttrs"]]

        servicePerformance.startPerfMetricEvent(self.group_name, "matchmaking")
        self.do_match()
        servicePerformance.endPerfMetricEvent(self.group_name, "matchmaking")

        logSupport.log.info(
            "Total matching idle %i (old 10min %i 60min %i) running %i limit %i"
            % (
                condorq_dict_types["Idle"]["total"],
                condorq_dict_types["OldIdle"]["total"],
                condorq_dict_types["Idle_3600"]["total"],
                self.condorq_dict_types["Running"]["total"],
                self.max_running,
            )
        )

        advertizer = glideinFrontendInterface.MultiAdvertizeWork(descript_obj)
        resource_advertiser = glideinFrontendInterface.ResourceClassadAdvertiser(
            multi_support=glideinFrontendInterface.frontendConfig.advertise_use_multi
        )

        # Add globals
        for globalid, globals_el in self.globals_dict.items():
            if "PubKeyObj" in globals_el["attrs"]:
                key_obj = key_builder.get_key_obj(
                    globals_el["attrs"]["FactoryPoolId"],
                    globals_el["attrs"]["PubKeyID"],
                    globals_el["attrs"]["PubKeyObj"],
                )
                advertizer.add_global(globals_el["attrs"]["FactoryPoolNode"], globalid, self.security_name, key_obj)

        # Add glidein config limits to the glideclient classads
        advertizer.set_glidein_config_limits(self.glidein_config_limits)

        # TODO: python2 allows None elements to be sorted putting them on top
        #   recreating the behavior but should check if (None, None, None) is giving problems somewhere else
        glideid_list = sorted(
            condorq_dict_types["Idle"]["count"].keys(), key=lambda x: ("", "", "") if x == (None, None, None) else x
        )
        # TODO: PM Following shows up in branch_v2plus. Which is correct?
        # glideid_list=glidein_dict.keys()
        # sort for the sake of monitoring

        # we will need this for faster lookup later
        self.processed_glideid_strs = []

        log_factory_header()
        total_up_stats_arr = init_factory_stats_arr()
        total_down_stats_arr = init_factory_stats_arr()

        # Going through all jobs, grouped by entry they can run on
        for glideid in glideid_list:
            if glideid == (None, None, None):
                continue  # This is the special "Unmatched" entry
            factory_pool_node = glideid[0]
            request_name = glideid[1]
            my_identity = str(glideid[2])  # get rid of unicode
            glideid_str = f"{request_name}@{factory_pool_node}"
            self.processed_glideid_strs.append(glideid_str)

            glidein_el = self.glidein_dict[glideid]
            glidein_in_downtime = safe_boolcomp(glidein_el["attrs"].get("GLIDEIN_In_Downtime", False), True)

            count_jobs = {}  # straight match
            prop_jobs = {}  # proportional subset for this entry
            # proportional subset of jobs for this entry scaled also for multicore (requested cores/available cores)
            prop_mc_jobs = {}
            hereonly_jobs = {}  # can only run on this site
            for dt in list(condorq_dict_types.keys()):
                count_jobs[dt] = condorq_dict_types[dt]["count"][glideid]
                prop_jobs[dt] = condorq_dict_types[dt]["prop"][glideid]
                prop_mc_jobs[dt] = condorq_dict_types[dt]["prop_mc"][glideid]
                hereonly_jobs[dt] = condorq_dict_types[dt]["hereonly"][glideid]

            count_status = self.count_status_multi[request_name]
            count_status_per_cred = self.count_status_multi_per_cred[request_name]

            # If the glidein requires a voms proxy, only match voms idle jobs
            # Note: if GLEXEC is set to NEVER, the site will never see
            # the proxy, so it can be avoided.
            # TODO: GlExec is gone (assuming same as NEVER), what is the meaning of GLIDEIN_REQUIRE_VOMS,
            #  VomsIdle, are they still needed?
            #  The following lines should go and maybe all GLIDEIN_REQUIRE_VOMS
            # if (self.glexec != 'NEVER'):
            #    if safe_boolcomp(glidein_el['attrs'].get('GLIDEIN_REQUIRE_VOMS'), True):
            #            prop_jobs['Idle']=prop_jobs['VomsIdle']
            #            logSupport.log.info("Voms proxy required, limiting idle glideins to: %i" % prop_jobs['Idle'])

            # effective idle is how much more we need
            # if there are idle slots, subtract them, they should match soon
            effective_idle = max(prop_jobs["Idle"] - count_status["Idle"], 0)
            # not used -  effective_oldidle = max(prop_jobs['OldIdle'] - count_status['Idle'], 0)

            # Adjust the number of idle jobs in case the minimum running parameter is set
            if prop_mc_jobs["Idle"] < self.min_running:
                logSupport.log.info(
                    "Entry %s: Adjusting idle cores to %s since the 'min' attribute of 'running_glideins_per_entry' is set"
                    % (glideid[1], self.min_running)
                )
                prop_mc_jobs["Idle"] = self.min_running

            # Compute min glideins required based on multicore jobs
            effective_idle_mc = max(prop_mc_jobs["Idle"] - count_status["Idle"], 0)
            effective_oldidle_mc = max(prop_mc_jobs["OldIdle"] - count_status["Idle"], 0)

            limits_triggered = {}

            down_fd = glideinFrontendDowntimeLib.DowntimeFile(
                os.path.join(self.work_dir, self.elementDescript.frontend_data["DowntimesFile"])
            )
            downflag = down_fd.checkDowntime()
            # If frontend or entry are in downtime
            # both min glideins required max running are 0
            if downflag or glidein_in_downtime:
                glidein_min_idle = 0
                glidein_max_run = 0
            else:
                glidein_min_idle = self.compute_glidein_min_idle(
                    count_status,
                    total_glideins,
                    total_idle_glideins,
                    fe_total_glideins,
                    fe_total_idle_glideins,
                    global_total_glideins,
                    global_total_idle_glideins,
                    effective_idle_mc,
                    effective_oldidle_mc,
                    limits_triggered,
                )

                # Compute max running glideins for this site based on
                # idle jobs, running jobs and idle slots
                glidein_max_run = self.compute_glidein_max_run(
                    prop_mc_jobs, self.count_real_glideins[glideid], count_status["Idle"]
                )

            remove_excess_str, remove_excess_margin = self.decide_removal_type(count_jobs, count_status, glideid)

            this_stats_arr = (
                prop_jobs["Idle"],
                count_jobs["Idle"],
                effective_idle,
                prop_jobs["OldIdle"],
                hereonly_jobs["Idle"],
                count_jobs["Running"],
                self.count_real_jobs[glideid],
                self.max_running,
                count_status["Total"],
                count_status["Idle"],
                count_status["Running"],
                count_status["Failed"],
                count_status["TotalCores"],
                count_status["IdleCores"],
                count_status["RunningCores"],
                glidein_min_idle,
                glidein_max_run,
            )

            self.stats["group"].logMatchedJobs(
                glideid_str,
                prop_jobs["Idle"],
                effective_idle,
                prop_jobs["OldIdle"],
                count_jobs["Running"],
                self.count_real_jobs[glideid],
            )

            self.stats["group"].logMatchedGlideins(
                glideid_str,
                count_status["Total"],
                count_status["Idle"],
                count_status["Running"],
                count_status["Failed"],
                count_status["TotalCores"],
                count_status["IdleCores"],
                count_status["RunningCores"],
            )

            self.stats["group"].logFactAttrs(glideid_str, glidein_el["attrs"], ("PubKeyValue", "PubKeyObj"))

            self.stats["group"].logFactDown(glideid_str, glidein_in_downtime)

            if glidein_in_downtime:
                total_down_stats_arr = log_and_sum_factory_line(
                    glideid_str, glidein_in_downtime, this_stats_arr, total_down_stats_arr
                )
            else:
                total_up_stats_arr = log_and_sum_factory_line(
                    glideid_str, glidein_in_downtime, this_stats_arr, total_up_stats_arr
                )

            # get the parameters
            glidein_params = copy.deepcopy(self.paramsDescript.const_data)
            for k in list(self.paramsDescript.expr_data.keys()):
                kexpr = self.paramsDescript.expr_objs[k]
                # convert kexpr -> kval
                glidein_params[k] = glideinFrontendLib.evalParamExpr(kexpr, self.paramsDescript.const_data, glidein_el)
            # we will need this param to monitor orphaned glideins
            glidein_params["GLIDECLIENT_ReqNode"] = factory_pool_node

            self.stats["group"].logFactReq(glideid_str, glidein_min_idle, glidein_max_run, glidein_params)

            glidein_monitors = {}
            glidein_monitors_per_cred = {}
            for t in count_jobs:
                glidein_monitors[t] = count_jobs[t]
            glidein_monitors["RunningHere"] = self.count_real_jobs[glideid]

            for t in count_status:
                glidein_monitors["Glideins%s" % t] = count_status[t]

            """
            for cred in self.x509_proxy_plugin.cred_list:
                glidein_monitors_per_cred[cred.getId()] = {}
                for t in count_status:
                    glidein_monitors_per_cred[cred.getId()]['Glideins%s' % t] = count_status_per_cred[cred.getId()][t]
            """

            # Number of credentials that have running and glideins.
            # This will be used to scale down the glidein_monitors[Running]
            # when there are multiple credentials per group.
            # This is efficient way of achieving the end result. Note that
            # Credential specific stats are not presented anywhere except the
            # classad. Monitoring info in frontend and factory shows
            # aggregated info considering all the credentials
            creds_with_running = 0

            for cred in self.x509_proxy_plugin.cred_list:
                glidein_monitors_per_cred[cred.getId()] = {}
                for t in count_status:
                    glidein_monitors_per_cred[cred.getId()]["Glideins%s" % t] = count_status_per_cred[cred.getId()][t]
                glidein_monitors_per_cred[cred.getId()]["ScaledRunning"] = 0
                # This credential has running glideins.
                if glidein_monitors_per_cred[cred.getId()]["GlideinsRunning"]:
                    creds_with_running += 1

            if creds_with_running:
                # Counter to handle rounding errors
                scaled = 0
                tr = glidein_monitors["Running"]
                for cred in self.x509_proxy_plugin.cred_list:
                    if glidein_monitors_per_cred[cred.getId()]["GlideinsRunning"]:
                        # This cred has running. Scale them down

                        if (creds_with_running - scaled) == 1:
                            # This is the last one. Assign remaining running

                            glidein_monitors_per_cred[cred.getId()]["ScaledRunning"] = (
                                tr - (tr // creds_with_running) * scaled
                            )
                            scaled += 1
                            break
                        else:
                            glidein_monitors_per_cred[cred.getId()]["ScaledRunning"] = tr // creds_with_running
                            scaled += 1

            key_obj = None
            for globalid in self.globals_dict:
                if glideid[1].endswith(globalid):
                    globals_el = self.globals_dict[globalid]
                    if "PubKeyObj" in globals_el["attrs"] and "PubKeyID" in globals_el["attrs"]:
                        key_obj = key_builder.get_key_obj(
                            my_identity, globals_el["attrs"]["PubKeyID"], globals_el["attrs"]["PubKeyObj"]
                        )
                    break

            trust_domain = glidein_el["attrs"].get("GLIDEIN_TrustDomain", "Grid")
            auth_method = glidein_el["attrs"].get("GLIDEIN_SupportedAuthenticationMethod", "grid_proxy")

            # Only advertise if there is a valid key for encryption
            if key_obj is not None:
                # determine whether to encrypt a condor token or scitoken into the classad
                ctkn = ""
                gp_encrypt = {}
                # see if site supports condor token
                ctkn = self.refresh_entry_token(glidein_el)
                expired = token_util.token_str_expired(ctkn)
                entry_token_name = "%s.idtoken" % glidein_el["attrs"].get("EntryName", "condor")
                if ctkn and not expired:
                    # mark token for encrypted advertisement
                    logSupport.log.debug("found condor token: %s" % entry_token_name)
                    gp_encrypt[entry_token_name] = ctkn
                else:
                    if expired:
                        logSupport.log.debug("found EXPIRED condor token: %s" % entry_token_name)
                    else:
                        logSupport.log.debug("could NOT find condor token: %s" % entry_token_name)

                # now try to generate a credential using a generator plugin
                generator_name, stkn = self.generate_credential(
                    self.elementDescript, glidein_el, self.group_name, trust_domain
                )

                # look for a local scitoken if no credential was generated
                if not stkn:
                    stkn = self.get_scitoken(self.elementDescript, trust_domain)

                if stkn:
                    if generator_name:
                        for cred_el in advertizer.descript_obj.x509_proxies_plugin.cred_list:
                            if cred_el.filename == generator_name:
                                cred_el.generated_data = stkn
                                break
                    if token_util.token_str_expired(stkn):
                        logSupport.log.warning("SciToken is expired, not forwarding.")
                    else:
                        gp_encrypt["frontend_scitoken"] = stkn

                # now advertise
                logSupport.log.debug("advertising tokens %s" % gp_encrypt.keys())
                advertizer.add(
                    factory_pool_node,
                    request_name,
                    request_name,
                    glidein_min_idle,
                    glidein_max_run,
                    self.idle_lifetime,
                    glidein_params=glidein_params,
                    glidein_monitors=glidein_monitors,
                    glidein_monitors_per_cred=glidein_monitors_per_cred,
                    remove_excess_str=remove_excess_str,
                    remove_excess_margin=remove_excess_margin,
                    key_obj=key_obj,
                    glidein_params_to_encrypt=gp_encrypt,
                    security_name=self.security_name,
                    trust_domain=trust_domain,
                    auth_method=auth_method,
                    ha_mode=self.ha_mode,
                )
            else:
                logSupport.log.warning(
                    "Cannot advertise requests for %s because no factory %s key was found"
                    % (request_name, factory_pool_node)
                )

            resource_classad = self.build_resource_classad(
                this_stats_arr,
                request_name,
                glidein_el,
                glidein_in_downtime,
                factory_pool_node,
                my_identity,
                limits_triggered,
            )
            resource_advertiser.addClassad(resource_classad.adParams["Name"], resource_classad)

        # end for glideid in condorq_dict_types['Idle']['count'].keys()

        total_down_stats_arr = self.count_factory_entries_without_classads(total_down_stats_arr)

        self.log_and_print_total_stats(total_up_stats_arr, total_down_stats_arr)
        self.log_and_print_unmatched(total_down_stats_arr)

        pids = []
        # Advertise glideclient and glideclient global classads
        ad_file_id_cache = glideinFrontendInterface.CredentialCache()
        advertizer.renew_and_load_credentials()

        ad_factnames = advertizer.get_advertize_factory_list()
        servicePerformance.startPerfMetricEvent(self.group_name, "advertize_classads")

        for ad_factname in ad_factnames:
            logSupport.log.info("Advertising global and singular requests for factory %s" % ad_factname)
            # they will run in parallel, make sure they don't collide
            adname = advertizer.initialize_advertize_batch() + "_" + ad_factname
            g_ads = advertizer.do_global_advertize_one(
                ad_factname, adname=adname, create_files_only=True, reset_unique_id=False
            )
            s_ads = advertizer.do_advertize_one(
                ad_factname, ad_file_id_cache, adname=adname, create_files_only=True, reset_unique_id=False
            )
            pids.append(fork_in_bg(advertizer.do_advertize_batch_one, ad_factname, tuple(set(g_ads) | set(s_ads))))

        del ad_file_id_cache

        # Advertise glideresource classads
        logSupport.log.info(
            "Advertising %i glideresource classads to the user pool" % len(resource_advertiser.classads)
        )
        pids.append(fork_in_bg(resource_advertiser.advertiseAllClassads))

        wait_for_pids(pids)
        logSupport.log.info("Done advertising")
        servicePerformance.endPerfMetricEvent(self.group_name, "advertize_classads")

        return

    def getScheddList(self):
        """Get all the schedds from the collector"""
        # Get the original list from config
        schedd_list = self.elementDescript.merged_data.get("JobSchedds", [])

        if schedd_list != ["ALL"]:
            # If the frontend admin specified a scheduler list use it.
            return schedd_list

        # logSupport.log.info("Getting list of schedulers from collector since 'ALL' has been used") # Too verbose. Keeping it around until production deployment
        # If the admin specified ALL then query the condor collector to get the list of schedulers
        res = glideinFrontendLib.getCondorStatusSchedds([None], constraint=None, format_list=[])

        if res and None in res:
            schedds = list(res[None].fetchStored().keys())

            # Cache the result with timestamp
            self.schedd_cache["data"] = schedds
            self.schedd_cache["timestamp"] = time.time()

            return schedds
        else:
            msg = "Cannot get the list of scheduler with 'condor_status -sched'. "
            # Cache valid for 1 hour
            now = time.time()
            if self.schedd_cache["timestamp"] and (now - self.schedd_cache["timestamp"] < 3600):
                msg += "Using cached schedd list."
                logSupport.log.warning(msg)
                return self.schedd_cache["data"]
            else:
                msg += "Schedd cache empty or expired."
                logSupport.log.warning(msg)

        return {}

    def get_scitoken(self, elementDescript, trust_domain):
        """Look for a local SciToken specified for the trust domain.

        Args:
            elementDescript (ElementMergedDescript): element descript
            trust_domain (string): trust domain for the element

        Returns:
            string, None: SciToken or None if not found
        """

        scitoken_fullpath = ""
        cred_type_data = elementDescript.element_data.get("ProxyTypes")
        trust_domain_data = elementDescript.element_data.get("ProxyTrustDomains")
        if not cred_type_data:
            cred_type_data = elementDescript.frontend_data.get("ProxyTypes")
        if not trust_domain_data:
            trust_domain_data = elementDescript.frontend_data.get("ProxyTrustDomains")
        if trust_domain_data and cred_type_data:
            cred_type_map = eval(cred_type_data)
            trust_domain_map = eval(trust_domain_data)
            for cfname in cred_type_map:
                if cred_type_map[cfname] == "scitoken":
                    if trust_domain_map[cfname] == trust_domain:
                        scitoken_fullpath = cfname

        if os.path.exists(scitoken_fullpath):
            try:
                logSupport.log.debug(f"found scitoken {scitoken_fullpath}")
                stkn = ""
                with open(scitoken_fullpath) as fbuf:
                    for line in fbuf:
                        stkn += line
                stkn = stkn.strip()
                return stkn
            except Exception as err:
                logSupport.log.exception(f"failed to read scitoken: {err}")

        return None

    def generate_credential(self, elementDescript, glidein_el, group_name, trust_domain):
        """Generates a credential with a credential generator plugin provided for the trust domain.

        Args:
            elementDescript (ElementMergedDescript): element descript
            glidein_el (dict): glidein element
            group_name (string): group name
            trust_domain (string): trust domain for the element

        Returns:
            string, None: Credential or None if not generated
        """

        ### The credential generator plugin should define the following function:
        # def get_credential(log:logger, group:str, entry:dict{name:str, gatekeeper:str}, trust_domain:str):
        # Generates a credential given the parameter

        # Args:
        # log:logger
        # group:str,
        # entry:dict{
        #     name:str,
        #     gatekeeper:str},
        # trust_domain:str,
        # Return
        # tuple
        #     token:str
        #     lifetime:int seconds of remaining lifetime
        # Exception
        # KeyError - miss some information to generate
        # ValueError - could not generate the token

        generator = None
        generators = elementDescript.element_data.get("CredentialGenerators")
        trust_domain_data = elementDescript.element_data.get("ProxyTrustDomains")
        if not generators:
            generators = elementDescript.frontend_data.get("CredentialGenerators")
        if not trust_domain_data:
            trust_domain_data = elementDescript.frontend_data.get("ProxyTrustDomains")
        if trust_domain_data and generators:
            generators_map = eval(generators)
            trust_domain_map = eval(trust_domain_data)
            for cfname in generators_map:
                if trust_domain_map[cfname] == trust_domain:
                    generator = generators_map[cfname]
                    logSupport.log.debug(f"found credential generator plugin {generator}")
                    try:
                        if generator not in plugins:
                            plugins[generator] = import_module(generator)
                        entry = {
                            "name": glidein_el["attrs"].get("EntryName"),
                            "gatekeeper": glidein_el["attrs"].get("GLIDEIN_Gatekeeper"),
                            "factory": glidein_el["attrs"].get("AuthenticatedIdentity"),
                        }
                        stkn, _ = plugins[generator].get_credential(logSupport, group_name, entry, trust_domain)
                        return cfname, stkn
                    except ModuleNotFoundError:
                        logSupport.log.warning(f"Failed to load credential generator plugin {generator}")
                    except Exception as e:  # catch any exception from the plugin to prevent the frontend from crashing
                        logSupport.log.warning(f"Failed to generate credential: {e}.")

        return None, None

    def refresh_entry_token(self, glidein_el):
        """Create or update a condor token for an entry point

        Args:
            glidein_el: a glidein element data structure

        Returns:
            jwt encoded condor token on success
            None on failure
        """
        tkn_file = ""
        tkn_str = ""

        # does condor version of entry point support condor token auth
        condor_version = glidein_el["params"].get("CONDOR_VERSION")
        if condor_version:
            try:
                # create a condor token named for entry point site name

                glidein_site = glidein_el["attrs"]["GLIDEIN_Site"]
                # Using the home directory should solve ownership conflicts for different clients (e.g. DE)
                user_home = Path.home()  # "/var/lib/gwms-frontend"
                tkn_dir = user_home / "tokens.d"
                pwd_dir = user_home / "passwords.d"
                tkn_file = os.path.join(tkn_dir, f"{self.group_name}.{glidein_site}.idtoken")
                pwd_file = os.path.join(pwd_dir, glidein_site)
                pwd_default = os.path.join(pwd_dir, self.idtoken_keyname)
                one_hr = 3600
                tkn_age = sys.maxsize

                if not os.path.exists(tkn_dir):
                    os.mkdir(tkn_dir, 0o700)
                if not os.path.exists(pwd_dir):
                    os.mkdir(pwd_dir, 0o700)

                if not os.path.exists(pwd_file):
                    if os.path.exists(pwd_default):
                        pwd_file = pwd_default
                    else:
                        logSupport.log.warning(f"cannot find pwd HTCSS key file '{pwd_default}'.")

                if os.path.exists(tkn_file):
                    tkn_age = time.time() - os.stat(tkn_file).st_mtime
                if tkn_age > one_hr and os.path.exists(pwd_file):
                    # TODO: scope, duration, identity  should be configurable from frontend.xml
                    scope = "condor:/READ condor:/ADVERTISE_STARTD condor:/ADVERTISE_MASTER"
                    duration = self.idtoken_lifetime * one_hr
                    identity = f"{glidein_site}@{socket.gethostname()}"
                    logSupport.log.debug("creating token %s" % tkn_file)
                    logSupport.log.debug("pwd_flie= %s" % pwd_file)
                    logSupport.log.debug("scope= %s" % scope)
                    logSupport.log.debug("duration= %s" % duration)
                    logSupport.log.debug("identity= %s" % identity)
                    # issuer (TRUST_DOMAIN) not passed, token generation will use the collector host name
                    tkn_str = token_util.create_and_sign_token(
                        pwd_file, scope=scope, duration=duration, identity=identity
                    )
                    # NOTE: Sensitive information. Uncomment only in development machines.
                    #   # cmd = "/usr/sbin/frontend_condortoken %s" % glidein_site
                    #   tkn_str = subprocessSupport.iexe_cmd(cmd, useShell=True)
                    #   logSupport.log.debug("tkn_str= %s" % tkn_str)
                    # The token file is read as text file below. Writing fixed to be consistent
                    with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=tkn_dir) as fd:
                        os.chmod(fd.name, 0o600)
                        fd.write(tkn_str)
                        os.replace(fd.name, tkn_file)
                    logSupport.log.debug("created token %s" % tkn_file)
                elif os.path.exists(tkn_file):
                    with open(tkn_file) as fbuf:
                        for line in fbuf:
                            tkn_str += line
            except Exception:
                logSupport.log.warning("failed to create %s" % tkn_file)
                logSupport.log.warning("Error details: %s" % traceback.format_exc())

        return tkn_str

    def populate_pubkey(self):
        """Populate public key information for glidein communication.

        Updates internal structures with public key objects for encryption.
        """
        bad_id_list = []
        for globalid, globals_el in self.globals_dict.items():
            try:
                globals_el["attrs"]["PubKeyObj"] = pubCrypto.PubRSAKey(globals_el["attrs"]["PubKeyValue"])
            except pubCrypto.PubCryptoError as e:
                # if no valid key
                # if key needed, will handle the error later on
                logSupport.log.warning(f"Factory Globals '{globalid}', invalid RSA key: {e}")
                logSupport.log.exception(f"Factory Globals '{globalid}', invalid RSA key: {e}")
                # but mark it for removal from the dictionary
                bad_id_list.append(globalid)
            except Exception:
                # Catch all to be more robust, was there, probably should be removed
                logSupport.log.warning("Factory Globals '%s', unknown error, probably invalid RSA key" % globalid)
                logSupport.log.exception("Factory Globals '%s', unknown error, probably invalid RSA key" % globalid)
                # but mark it for removal from the dictionary
                bad_id_list.append(globalid)
        for badid in bad_id_list:
            logSupport.log.warning("Factory Globals removing'%s': invalid RSA key" % badid)
            del self.globals_dict[badid]

    def identify_bad_schedds(self):
        """Identify the list of schedds that should not be considered when
        requesting glideins for idle jobs. Schedds with one of the criteria

        1. Running jobs (TotalRunningJobs + TotalSchedulerJobsRunning)
           is greater than 95% of max number of jobs (MaxJobsRunning)
        2. Transfer queue (TransferQueueNumUploading) is greater than 95%
           of max allowed transfers (TransferQueueMaxUploading)
        3. CurbMatchmaking in schedd classad is true
        """
        self.blacklist_schedds = set()

        for c in self.status_schedd_dict:
            coll_status_schedd_dict = self.status_schedd_dict[c].fetchStored()
            for schedd in coll_status_schedd_dict:
                # Only consider global or group specific schedds
                # To be on the safe side add them to blacklist_schedds
                if schedd not in self.getScheddList():
                    logSupport.log.debug("Ignoring schedd %s for this group based on the configuration" % (schedd))
                    self.blacklist_schedds.add(schedd)
                    continue
                el = coll_status_schedd_dict[schedd]
                try:
                    # Here 0 really means no jobs
                    # Stop a bit earlier at 95% of the limit
                    max_run = int(el["MaxJobsRunning"] * 0.95 + 0.5)
                    current_run = el["TotalRunningJobs"]
                    # older schedds may not have TotalSchedulerJobsRunning
                    # commented out based on redmine ticket #8849
                    # current_run += el.get('TotalSchedulerJobsRunning',0)
                    logSupport.log.debug("Schedd %s has %i running with max %i" % (schedd, current_run, max_run))

                    if current_run >= max_run:
                        self.blacklist_schedds.add(schedd)
                        logSupport.log.warning(
                            "Schedd %s hit maxrun limit, blacklisting: has %i running with max %i"
                            % (schedd, current_run, max_run)
                        )

                    if el.get("TransferQueueMaxUploading", 0) > 0:
                        # el['TransferQueueMaxUploading'] = 0 means unlimited
                        # Stop a bit earlier at 95% of the limit
                        max_up = int(el["TransferQueueMaxUploading"] * 0.95 + 0.5)
                        current_up = el["TransferQueueNumUploading"]
                        logSupport.log.debug("Schedd %s has %i uploading with max %i" % (schedd, current_up, max_up))
                        if current_up >= max_up:
                            self.blacklist_schedds.add(schedd)
                            logSupport.log.warning(
                                "Schedd %s hit maxupload limit, blacklisting: has %i uploading with max %i"
                                % (schedd, current_up, max_up)
                            )

                    # Pre 8.3.5 schedds do not have CurbMatchmaking.
                    # Assume False if not present
                    curb_matchmaking = str(el.get("CurbMatchmaking", "FALSE"))
                    if curb_matchmaking.upper() == "TRUE":
                        self.blacklist_schedds.add(schedd)
                        logSupport.log.warning(
                            "Ignoring schedd %s since CurbMatchmaking in its classad evaluated to 'True'" % (schedd)
                        )
                except Exception:
                    logSupport.log.exception("Unexpected exception checking schedd %s for limit" % schedd)

    def populate_condorq_dict_types(self):
        """Builds the dictionary of condorq types, filtering out blacklisted schedds.

        Populates self.condorq_dict_types with idle, old idle, voms idle, and running states.
        """
        # create a dictionary that does not contain the blacklisted schedds
        good_condorq_dict = self.condorq_dict.copy()  # simple copy enough, will only modify keys
        for k in self.blacklist_schedds:
            if k in good_condorq_dict:  # some schedds may not have returned anything
                del good_condorq_dict[k]
        # use only the good schedds when considering idle
        condorq_dict_idle = glideinFrontendLib.getIdleCondorQ(good_condorq_dict)
        condorq_dict_idle_600 = glideinFrontendLib.getOldCondorQ(condorq_dict_idle, 600)
        condorq_dict_idle_3600 = glideinFrontendLib.getOldCondorQ(condorq_dict_idle, 3600)
        condorq_dict_voms = glideinFrontendLib.getIdleVomsCondorQ(condorq_dict_idle)

        # then report how many we really had
        condorq_dict_idle_all = glideinFrontendLib.getIdleCondorQ(self.condorq_dict)

        self.condorq_dict_running = glideinFrontendLib.getRunningCondorQ(self.condorq_dict)

        self.condorq_dict_types = {
            "IdleAll": {"dict": condorq_dict_idle_all, "abs": glideinFrontendLib.countCondorQ(condorq_dict_idle_all)},
            "Idle": {"dict": condorq_dict_idle, "abs": glideinFrontendLib.countCondorQ(condorq_dict_idle)},
            # idle 600s or more
            "OldIdle": {"dict": condorq_dict_idle_600, "abs": glideinFrontendLib.countCondorQ(condorq_dict_idle_600)},
            # idle 3600s or more
            "Idle_3600": {
                "dict": condorq_dict_idle_3600,
                "abs": glideinFrontendLib.countCondorQ(condorq_dict_idle_3600),
            },
            "VomsIdle": {"dict": condorq_dict_voms, "abs": glideinFrontendLib.countCondorQ(condorq_dict_voms)},
            "Running": {
                "dict": self.condorq_dict_running,
                "abs": glideinFrontendLib.countCondorQ(self.condorq_dict_running),
            },
        }

    def populate_status_dict_types(self):
        """Creates various dictionaries for glidein slot statuses.

        Populates self.status_dict_types for total, idle, running, failed, and core counts.

        """
        # dict with static + pslot
        status_dict_non_dynamic = glideinFrontendLib.getCondorStatusNonDynamic(self.status_dict)

        # dict with idle static + idle pslot
        status_dict_idle = glideinFrontendLib.getIdleCondorStatus(self.status_dict, self.p_glidein_min_memory)

        # dict with static + dynamic + pslot_with_dyanmic_slot
        status_dict_running = glideinFrontendLib.getRunningCondorStatus(self.status_dict)

        # dict with pslot_with_dyanmic_slot
        status_dict_running_pslot = glideinFrontendLib.getRunningPSlotCondorStatus(self.status_dict)

        # dict with failed slots
        status_dict_failed = glideinFrontendLib.getFailedCondorStatus(self.status_dict)

        # Dict of dict containing sub-dicts and counts for slots in
        # different states
        self.status_dict_types = {
            "Total": {"dict": self.status_dict, "abs": glideinFrontendLib.countCondorStatus(self.status_dict)},
            "Idle": {"dict": status_dict_idle, "abs": glideinFrontendLib.countCondorStatus(status_dict_idle)},
            # For Running, consider static + dynamic + pslot_with_dyanmic_slot
            # We do this so comparison with the job classad's RemoteHost
            # can be easily done with the p-slot at the later stage in
            # appendRealRunning(condor_q_dict, status_dict)
            # However, while counting we exclude the p-slots that have
            # one or more dynamic slots
            "Running": {
                "dict": status_dict_running,
                "abs": glideinFrontendLib.countCondorStatus(status_dict_running)
                - glideinFrontendLib.countCondorStatus(status_dict_running_pslot),
            },
            "Failed": {"dict": status_dict_failed, "abs": glideinFrontendLib.countCondorStatus(status_dict_failed)},
            "TotalCores": {
                "dict": status_dict_non_dynamic,
                "abs": glideinFrontendLib.countTotalCoresCondorStatus(status_dict_non_dynamic),
            },
            "IdleCores": {
                "dict": status_dict_idle,
                "abs": glideinFrontendLib.countIdleCoresCondorStatus(status_dict_idle),
            },
            "RunningCores": {
                "dict": status_dict_running,
                "abs": glideinFrontendLib.countRunningCoresCondorStatus(status_dict_running),
            },
        }

    def build_resource_classad(
        self,
        this_stats_arr,
        request_name,
        glidein_el,
        glidein_in_downtime,
        factory_pool_node,
        my_identity,
        limits_triggered,
    ):
        """Builds and populates a resource classad with relevant information for a specific glidein entry.

        This method creates a ResourceClassad object and populates it with details about the frontend,
        entry attributes, monitoring information, downtime status, configuration limits, match expressions,
        and triggered limits/curbs. Optionally, it adds monitoring info from factory clients if available.

        Args:
            this_stats_arr (tuple): Array of statistics for the current glidein entry.
            request_name (str): The name of the resource request or entry.
            glidein_el (dict): Dictionary containing attributes and monitoring info for the glidein entry.
            glidein_in_downtime (bool): True if the glidein is currently in downtime.
            factory_pool_node (str): Identifier for the factory pool node.
            my_identity (str): The identity of the frontend at the factory pool.
            limits_triggered (dict): Dictionary of limits and curbs triggered for this entry.

        Returns:
            ResourceClassad: A populated resource classad object for the given glidein entry.
        """
        # Create the resource classad and populate the required information
        resource_classad = glideinFrontendInterface.ResourceClassad(request_name, self.published_frontend_name)
        resource_classad.setFrontendDetails(self.frontend_name, self.group_name, self.ha_mode)
        resource_classad.setInDownTime(glidein_in_downtime)
        # From glidefactory classad
        resource_classad.setEntryInfo(glidein_el["attrs"])
        resource_classad.setEntryMonitorInfo(glidein_el["monitor"])
        resource_classad.setGlideClientConfigLimits(self.glidein_config_limits)
        try:
            # From glidefactorylient classad
            key = (factory_pool_node, resource_classad.adParams["Name"], my_identity)
            if key in self.factoryclients_dict:
                resource_classad.setGlideFactoryMonitorInfo(self.factoryclients_dict[key]["monitor"])
        except Exception:
            # Ignore errors. Just log them.
            logSupport.log.exception("Populating GlideFactoryMonitor info in resource classad failed: ")

        resource_classad.setMatchExprs(
            self.elementDescript.merged_data["MatchExpr"],
            self.elementDescript.merged_data["JobQueryExpr"],
            self.elementDescript.merged_data["FactoryQueryExpr"],
            self.attr_dict["GLIDECLIENT_Start"],
        )
        try:
            resource_classad.setGlideClientMonitorInfo(this_stats_arr)
        except RuntimeError:
            logSupport.log.exception("Populating GlideClientMonitor info in resource classad failed: ")

        # simply invoke a new method in glideinFrontendInterface.py
        resource_classad.setCurbsAndLimits(limits_triggered)

        return resource_classad

    def compute_glidein_min_idle(
        self,
        count_status,
        total_glideins,
        total_idle_glideins,
        fe_total_glideins,
        fe_total_idle_glideins,
        global_total_glideins,
        global_total_idle_glideins,
        effective_idle,
        effective_oldidle,
        limits_triggered,
    ):
        """Computes the minimum number of idle glideins to request for this entry.

        Computes the minimum number of idle glideins to request for this entry after considering
        all relevant limits and curbs. Identifies the limits and curbs triggered for advertising
        the information in the glideresource classad.

        Args:
            count_status (dict): Counters for glideins in different states (from condor_q).
            total_glideins (int): Total number of glideins for the Entry.
            total_idle_glideins (int): Number of idle glideins for the Entry.
            fe_total_glideins (int): Total number of glideins for this Frontend at the Entry.
            fe_total_idle_glideins (int): Number of idle glideins for this Frontend at the Entry.
            global_total_glideins (int): Total number of glideins for all Entries.
            global_total_idle_glideins (int): Number of idle glideins for all Entries.
            effective_idle (int): Effective number of idle glideins.
            effective_oldidle (int): Effective number of old idle glideins.
            limits_triggered (dict): Used to return the limits triggered.

        Returns:
            int: Minimum number of idle glideins to request for this entry.
        """
        if self.request_removal_wtype is not None:
            # we are requesting the removal of glideins, do not request more
            return 0
        if (
            (count_status["Total"] >= self.max_running)
            or (count_status["Idle"] >= self.max_vms_idle)
            or (total_glideins >= self.total_max_glideins)
            or (total_idle_glideins >= self.total_max_vms_idle)
            or (fe_total_glideins >= self.fe_total_max_glideins)
            or (fe_total_idle_glideins >= self.fe_total_max_vms_idle)
            or (global_total_glideins >= self.global_total_max_glideins)
            or (global_total_idle_glideins >= self.global_total_max_vms_idle)
        ):
            # Do not request more glideins under following conditions:
            # 1. Have all the running jobs I wanted
            # 2. Have enough idle vms/slots
            # 3. Reached the system-wide limit
            glidein_min_idle = 0

            # Modifies limits_triggered dict
            self.identify_limits_triggered(
                count_status,
                total_glideins,
                total_idle_glideins,
                fe_total_glideins,
                fe_total_idle_glideins,
                global_total_glideins,
                global_total_idle_glideins,
                limits_triggered,
            )

        elif effective_idle > 0:
            # don't go over the system-wide max
            # not perfect, given the number of entries, but better than nothing
            glidein_min_idle = min(
                effective_idle,
                self.max_running - count_status["Total"],
                self.total_max_glideins - total_glideins,
                self.total_max_vms_idle - total_idle_glideins,
                self.fe_total_max_glideins - fe_total_glideins,
                self.fe_total_max_vms_idle - fe_total_idle_glideins,
                self.global_total_max_glideins - global_total_glideins,
                self.global_total_max_vms_idle - global_total_idle_glideins,
            )

            # since it takes a few cycles to stabilize, ask for only one third
            # 3 was based on observation and tests: The factory can be still processing the previous request,
            # previously requested glideins could be still idle in the site queue
            glidein_min_idle = int(glidein_min_idle / self.ramp_up_attenuation)
            # do not reserve any more than the number of old idles
            # for reserve (/3)
            glidein_idle_reserve = min(effective_oldidle // 3, self.reserve_idle)

            glidein_min_idle += glidein_idle_reserve
            glidein_min_idle = min(glidein_min_idle, self.max_idle)

            # /2 each time you hit a limit, to do an exponential backoff
            if count_status["Idle"] >= self.curb_vms_idle:
                glidein_min_idle /= 2  # above first threshold, reduce
                limits_triggered["CurbIdleGlideinsPerEntry"] = "count=%i, curb=%i" % (
                    count_status["Idle"],
                    self.curb_vms_idle,
                )
            if total_glideins >= self.total_curb_glideins:
                glidein_min_idle /= 2  # above global threshold, reduce further
                limits_triggered["CurbTotalGlideinsPerGroup"] = "count=%i, curb=%i" % (
                    total_glideins,
                    self.total_curb_glideins,
                )
            if total_idle_glideins >= self.total_curb_vms_idle:
                glidein_min_idle /= 2  # above global threshold, reduce further
                limits_triggered["CurbIdleGlideinsPerGroup"] = "count=%i, curb=%i" % (
                    total_idle_glideins,
                    self.total_curb_vms_idle,
                )
            if fe_total_glideins >= self.fe_total_curb_glideins:
                glidein_min_idle /= 2  # above global threshold, reduce further
                limits_triggered["CurbTotalGlideinsPerFrontend"] = "count=%i, curb=%i" % (
                    fe_total_glideins,
                    self.fe_total_curb_glideins,
                )
            if fe_total_idle_glideins >= self.fe_total_curb_vms_idle:
                glidein_min_idle /= 2  # above global threshold, reduce further
                limits_triggered["CurbIdleGlideinsPerFrontend"] = "count=%i, curb=%i" % (
                    fe_total_idle_glideins,
                    self.fe_total_curb_vms_idle,
                )
            if global_total_glideins >= self.global_total_curb_glideins:
                glidein_min_idle /= 2  # above global threshold, reduce further
                limits_triggered["CurbTotalGlideinsGlobal"] = "count=%i, curb=%i" % (
                    global_total_glideins,
                    self.global_total_curb_glideins,
                )
            if global_total_idle_glideins >= self.global_total_curb_vms_idle:
                glidein_min_idle /= 2  # above global threshold, reduce further
                limits_triggered["CurbIdleGlideinsGlobal"] = "count=%i, curb=%i" % (
                    global_total_idle_glideins,
                    self.global_total_curb_vms_idle,
                )

            if glidein_min_idle < 1:
                glidein_min_idle = 1
        else:
            # no idle, make sure the Entries know it
            glidein_min_idle = 0

        return int(glidein_min_idle)

    def identify_limits_triggered(
        self,
        count_status,
        total_glideins,
        total_idle_glideins,
        fe_total_glideins,
        fe_total_idle_glideins,
        global_total_glideins,
        global_total_idle_glideins,
        limits_triggered,
    ):
        """Identifies which glidein limits have been triggered for advertising in the glideresource.

        This method checks various thresholds related to glideins (such as total, idle, per entry, per group,
        per frontend, and global limits) and updates the `limits_triggered` dictionary with details of each limit
        that has been reached or exceeded.

        Args:
            count_status (dict): Dictionary with counters for glideins in different states (e.g., "Total", "Idle").
            total_glideins (int): Total number of glideins for the current entry group.
            total_idle_glideins (int): Number of idle glideins for the current entry group.
            fe_total_glideins (int): Total number of glideins for this frontend at the entry group.
            fe_total_idle_glideins (int): Number of idle glideins for this frontend at the entry group.
            global_total_glideins (int): Total number of glideins across all entries.
            global_total_idle_glideins (int): Total number of idle glideins across all entries.
            limits_triggered (dict): Dictionary to be updated with the triggered limits and their respective details.

        Returns:
            None: This method updates the `limits_triggered` dictionary in place and does not return a value.
        """
        # Identify the limits triggered for advertizing in glideresource
        if count_status["Total"] >= self.max_running:
            limits_triggered["TotalGlideinsPerEntry"] = "count=%i, limit=%i" % (count_status["Total"], self.max_running)
        if count_status["Idle"] >= self.max_vms_idle:
            limits_triggered["IdleGlideinsPerEntry"] = "count=%i, limit=%i" % (count_status["Idle"], self.max_vms_idle)
        if total_glideins >= self.total_max_glideins:
            limits_triggered["TotalGlideinsPerGroup"] = "count=%i, limit=%i" % (total_glideins, self.total_max_glideins)
        if total_idle_glideins >= self.total_max_vms_idle:
            limits_triggered["IdleGlideinsPerGroup"] = "count=%i, limit=%i" % (
                total_idle_glideins,
                self.total_max_vms_idle,
            )
        if fe_total_glideins >= self.fe_total_max_glideins:
            limits_triggered["TotalGlideinsPerFrontend"] = "count=%i, limit=%i" % (
                fe_total_glideins,
                self.fe_total_max_glideins,
            )
        if fe_total_idle_glideins >= self.fe_total_max_vms_idle:
            limits_triggered["IdleGlideinsPerFrontend"] = "count=%i, limit=%i" % (
                fe_total_idle_glideins,
                self.fe_total_max_vms_idle,
            )
        if global_total_glideins >= self.global_total_max_glideins:
            limits_triggered["TotalGlideinsGlobal"] = "count=%i, limit=%i" % (
                global_total_glideins,
                self.global_total_max_glideins,
            )
        if global_total_idle_glideins >= self.global_total_max_vms_idle:
            limits_triggered["IdleGlideinsGlobal"] = "count=%i, limit=%i" % (
                global_total_idle_glideins,
                self.global_total_max_vms_idle,
            )

    def compute_glidein_max_run(self, prop_jobs, real, idle_glideins):
        """Computes the maximum number of running glideins for this entry.

        Args:
            prop_jobs (dict): Proportional idle multicore jobs for this entry.
            real (int): Number of jobs running at the given glideid.
            idle_glideins (int): Number of idle startds at this entry.

        Returns:
            int: Maximum number of running glideins for the entry.
        """
        glidein_max_run = 0

        if (self.request_removal_wtype is not None) and (not self.request_removal_excess_only):
            # We are requesting the removal of all the glideins
            # Factory should remove all of them
            return 0

        # We don't need more slots than number of jobs in the queue
        # unless the fraction is positive
        if (prop_jobs["Idle"] + real) > 0:
            if prop_jobs["Idle"] > 0:
                # We have idle jobs in the queue. Consider idle startds
                # at this entry when computing max_run. This makes the
                # requests conservative when short running jobs come in
                # frequent but smaller bursts.
                # NOTE: We do not consider idle cores as fragmentation can
                #       impact use negatively
                glidein_max_run = int((max(prop_jobs["Idle"] - idle_glideins, 0) + real) * self.fraction_running + 1)
            else:
                # No reason for a delta when we don't need more than we have
                glidein_max_run = int(real)

        return glidein_max_run

    def log_and_print_total_stats(self, total_up_stats_arr, total_down_stats_arr):
        """Logs and prints the total statistics for matched up and matched down glideins.

        This method logs various statistics related to "MatchedUp" and "MatchedDown" glideins
        using the `stats["group"]` logger, and then prints summaries for both using helper functions.
        It processes statistical arrays representing the state of factories that are up or down.

        Args:
            total_up_stats_arr (list): Statistical data array for factories in the "up" state.
            total_down_stats_arr (list): Statistical data array for factories in the "down" state.

        Returns:
            None: This method logs and prints information but does not return a value.
        """
        # Log the totals
        for el in (("MatchedUp", total_up_stats_arr, True), ("MatchedDown", total_down_stats_arr, False)):
            el_str, el_stats_arr, el_updown = el
            self.stats["group"].logMatchedJobs(
                el_str, el_stats_arr[0], el_stats_arr[2], el_stats_arr[3], el_stats_arr[5], el_stats_arr[6]
            )

            self.stats["group"].logMatchedGlideins(
                el_str,
                el_stats_arr[8],
                el_stats_arr[9],
                el_stats_arr[10],
                el_stats_arr[11],
                el_stats_arr[12],
                el_stats_arr[13],
                el_stats_arr[14],
            )
            self.stats["group"].logFactAttrs(el_str, [], ())  # for completeness
            self.stats["group"].logFactDown(el_str, el_updown)
            self.stats["group"].logFactReq(el_str, el_stats_arr[15], el_stats_arr[16], {})

        # Print the totals
        # Ignore the resulting sum
        log_factory_header()
        log_and_sum_factory_line("Sum of useful factories", False, tuple(total_up_stats_arr))
        log_and_sum_factory_line("Sum of down factories", True, tuple(total_down_stats_arr))

    def log_and_print_unmatched(self, total_down_stats_arr):
        """Logs and prints statistics for unmatched jobs and glideins.

        This method logs statistics related to unmatched idle, old idle, and running jobs,
        as well as unmatched glideins, using the `stats["group"]` logger. It also prints a summary line
        for unmatched jobs using the statistical data array provided. The function is typically called to
        record and report jobs and resources that could not be matched to available factories.

        Args:
            total_down_stats_arr (list): Statistical data array for factories in the "down" state
                (provided for completeness but not used directly in unmatched calculation).

        Returns:
            None: This method logs and prints information but does not return a value.
        """
        # Print unmatched... Ignore the resulting sum
        unmatched_idle = self.condorq_dict_types["Idle"]["count"][(None, None, None)]
        unmatched_oldidle = self.condorq_dict_types["OldIdle"]["count"][(None, None, None)]
        unmatched_running = self.condorq_dict_types["Running"]["count"][(None, None, None)]

        self.stats["group"].logMatchedJobs(
            "Unmatched", unmatched_idle, unmatched_idle, unmatched_oldidle, unmatched_running, 0
        )

        # Nothing running
        self.stats["group"].logMatchedGlideins("Unmatched", 0, 0, 0, 0, 0, 0, 0)
        # just for completeness
        self.stats["group"].logFactAttrs("Unmatched", [], ())
        self.stats["group"].logFactDown("Unmatched", True)
        self.stats["group"].logFactReq("Unmatched", 0, 0, {})

        this_stats_arr = (
            unmatched_idle,
            unmatched_idle,
            unmatched_idle,
            unmatched_oldidle,
            unmatched_idle,
            unmatched_running,
            0,
            0,
            0,
            0,
            0,
            0,  # glideins... none, since no matching
            0,
            0,
            0,  # Cores
            0,
            0,  # requested... none, since not matching
        )
        log_and_sum_factory_line("Unmatched", True, this_stats_arr)

    def decide_removal_type(self, count_jobs, count_status, glideid):
        """Pick the max removal type (unless disable is requested)
        - if it was requested explicitly, send that one
        - otherwise check automatic triggers and configured removal and send the max of the 2

        If configured removal is selected, take into account also the margin and the tracking
        This handles all the Glidein removals triggered by the Frontend. It does not affect automatic mechanisms
        in the Factory, like Glidein timeouts

        Args:
            count_jobs (dict): dict with job stats
            count_status (dict): dict with glidein stats
            glideid (str): ID of the glidein request

        Returns:
            str: remove excess string to send to the Factory, one of: "DISABLE", "ALL", "IDLE", "WAIT", or "NO"
        """
        if self.request_removal_wtype is not None:
            # we are requesting the removal of glideins via command line tool, and we have the explicit code to use
            return self.request_removal_wtype, 0

        # removal within the Frontend
        remove_levels = {
            "NO": 0,
            "WAIT": 1,
            "IDLE": 2,
            "ALL": 3,
            "UNREG": 4,  # Mentioned in glideinFrontendIntrface.py - not documented
            "DISABLE": -1,
        }
        remove_excess_str_auto = self.choose_remove_excess_type(count_jobs, count_status, glideid)
        remove_excess_str_config = self.check_removal_type_config(glideid)
        remove_excess_str_auto_nr = remove_levels[remove_excess_str_auto]
        remove_excess_str_config_nr = remove_levels[remove_excess_str_config]
        if remove_excess_str_config_nr < 0:
            # disable all removals
            return "NO", 0
        if remove_excess_str_auto_nr > remove_excess_str_config_nr:
            return remove_excess_str_auto, 0
        # Config request >= automatic removal
        if remove_excess_str_config_nr >= 0:
            if self.removal_requests_tracking and self.removal_margin > 0:
                return remove_excess_str_config, self.removal_margin
            return remove_excess_str_config, 0
        return "NO", 0

    def check_removal_type_config(self, glideid):
        """Decides what kind of excess glideins to remove depending on the configuration requests (glideins_remove)
        "ALL", "IDLE", "WAIT", "NO" (default) or "DISABLE" (disable also automatic removal)

        If removal_requests_tracking or active removal are enabled, this may result in Glidein removals
        depending on the parameters in the configuration and the current number of Glideins and requests

        Args:
            glideid (str): ID of the glidein request

        Returns:
            str: remove excess string from configuration, one of: "DISABLE", "ALL", "IDLE", "WAIT", or "NO"
        """
        # self.removal_type is RemovalType from the FE group configuration
        if self.removal_type is None or self.removal_type == "NO":
            # No special semoval requested, leave things unchanged
            return "NO"
        if self.removal_type == "DISABLE":
            return "DISABLE"
        # Cannot compare the current requests w/ the available glideins (factory status not provided to the FE)
        # If tracking is enabled, always request removal and send the margin. The factory will decide
        if self.removal_requests_tracking:
            return self.removal_type
        # No tracking, remove glideins if there are no requests
        # History counters have been just updated in self.choose_remove_excess_type
        history_idle0 = CounterWrapper(self.history_obj["idle0"])
        if history_idle0[glideid] > self.removal_wait:
            return self.removal_type
        return "NO"

    def choose_remove_excess_type(self, count_jobs, count_status, glideid):
        """Decides what kind of excess glideins to remove: control for request and automatic trigger:
            "ALL", "IDLE", "WAIT", or "NO"

        If it is a request from the client (command line) then execute that
        Otherwise calculate the result of the automatic removal mechanism: increasingly remove WAIT, IDLE and ALL
        depending on how long (measured in Frontend cycles) there have been no requests.

        Args:
            count_jobs (dict): dict with job stats
            count_status (dict): dict with glidein stats
            glideid (str): ID of the glidein request

        Returns:
            str: remove excess string from automatic mechanism, one of: "ALL", "IDLE", "WAIT", or "NO"

        """
        if self.request_removal_wtype is not None:
            # we are requesting the removal of glideins, and we have the explicit code to use
            return self.request_removal_wtype

        # do not remove excessive glideins by default
        remove_excess_wait = False

        # keep track of how often idle was 0
        history_idle0 = CounterWrapper(self.history_obj["idle0"])
        if count_jobs["Idle"] == 0:
            # no idle jobs in the queue left
            # consider asking for unsubmitted idle glideins to be removed
            history_idle0[glideid] += 1
            if history_idle0[glideid] > 5:
                # nobody asked for anything more for some time, so
                remove_excess_wait = True
        else:
            history_idle0[glideid] = 0

        # do not remove excessive glideins by default
        remove_excess_idle = False

        # keep track of how often glideidle was 0
        history_glideempty = CounterWrapper(self.history_obj["glideempty"])
        if count_status["Idle"] >= count_status["Total"]:
            # no glideins being used
            # consider asking for all idle glideins to be removed
            history_glideempty[glideid] += 1
            if remove_excess_wait and (history_glideempty[glideid] > 10):
                # no requests and no glideins being used
                # no harm getting rid of everything
                remove_excess_idle = True
        else:
            history_glideempty[glideid] = 0

        # do not remove excessive glideins by default
        remove_excess_running = False

        # keep track of how often glidetotal was 0
        history_glidetotal0 = CounterWrapper(self.history_obj["glidetotal0"])
        if count_status["Total"] == 0:
            # no glideins registered
            # consider asking for all idle glideins to be removed
            history_glidetotal0[glideid] += 1
            if remove_excess_wait and (history_glidetotal0[glideid] > 10):
                # no requests and no glidein registered
                # no harm getting rid of everything
                remove_excess_running = True
        else:
            history_glidetotal0[glideid] = 0

        if remove_excess_running:
            remove_excess_str = "ALL"
        elif remove_excess_idle:
            remove_excess_str = "IDLE"
        elif remove_excess_wait:
            remove_excess_str = "WAIT"
        else:
            remove_excess_str = "NO"
        return remove_excess_str

    def count_factory_entries_without_classads(self, total_down_stats_arr):
        """Counts and logs statistics for factory entries that do not have Factory ClassAds.

        This method iterates through factory entries that are present in the status dictionary but lack
        corresponding Factory ClassAds, computes various status metrics (such as total, idle, running,
        failed slots and cores), logs these statistics, and marks each such entry as "down" in the group logger.
        It also updates and returns the cumulative statistics array for down factory entries.

        Args:
            total_down_stats_arr (list): The cumulative statistics array for down factory entries,
                which is updated as each unmatched entry is processed.

        Returns:
            list: The updated statistics array for down factory entries after including entries without ClassAds.
        """
        # Find out the slots/cores for factory entries that are in various
        # states, but for which Factory ClassAds don't exist
        #
        factory_entry_list = glideinFrontendLib.getFactoryEntryList(self.status_dict)
        processed_glideid_str_set = frozenset(self.processed_glideid_strs)

        factory_entry_list.sort()  # sort for the sake of monitoring
        for request_name, factory_pool_node in factory_entry_list:
            glideid_str = f"{request_name}@{factory_pool_node}"
            if glideid_str in processed_glideid_str_set:
                continue  # already processed... ignore

            self.count_status_multi[request_name] = {}
            for st in self.status_dict_types:
                c = glideinFrontendLib.getClientCondorStatus(
                    self.status_dict_types[st]["dict"], self.frontend_name, self.group_name, request_name
                )
                if st in ("TotalCores", "IdleCores", "RunningCores"):
                    self.count_status_multi[request_name][st] = glideinFrontendLib.countCoresCondorStatus(c, st)
                elif st == "Running":
                    # Running counts are computed differently because of
                    # the dict composition. Dict also has p-slots
                    # corresponding to the dynamic slots
                    self.count_status_multi[request_name][st] = glideinFrontendLib.countRunningCondorStatus(c)
                else:
                    self.count_status_multi[request_name][st] = glideinFrontendLib.countCondorStatus(c)

            count_status = self.count_status_multi[request_name]

            # ignore matching jobs
            # since we don't have the entry classad, we have no clue how to match
            this_stats_arr = (
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                count_status["Total"],
                count_status["Idle"],
                count_status["Running"],
                count_status["Failed"],
                count_status["TotalCores"],
                count_status["IdleCores"],
                count_status["RunningCores"],
                0,
                0,
            )

            self.stats["group"].logMatchedGlideins(
                glideid_str,
                count_status["Total"],
                count_status["Idle"],
                count_status["Running"],
                count_status["Failed"],
                count_status["TotalCores"],
                count_status["IdleCores"],
                count_status["RunningCores"],
            )

            # since I don't see it in the factory anymore, mark it as down
            self.stats["group"].logFactDown(glideid_str, True)
            total_down_stats_arr = log_and_sum_factory_line(glideid_str, True, this_stats_arr, total_down_stats_arr)
        return total_down_stats_arr

    def query_globals(self, factory_pool):
        """Queries the glidefactoryglobal ClassAd and retrieves global attributes from the factory pool.

        This method connects to the specified factory pool and fetches global configuration information,
        including RSA public keys and other relevant attributes. Only RSA keys are trusted and included in the results.
        The function handles connection errors and malformed keys by logging appropriate messages and continues
        processing other entries.

        Args:
            factory_pool (tuple): A tuple containing information about the factory pool node and identity.

        Returns:
            dict: A dictionary mapping global IDs to their corresponding attribute dictionaries, including
                RSA public keys and other relevant information. Only entries with valid RSA public keys are included.
        """
        # Query glidefactoryglobal ClassAd
        globals_dict = {}

        try:
            # Note: M2Crypto key objects are not pickle-able,
            # so we will have to do that in the parent later on
            factory_pool_node = factory_pool[0]
            my_identity_at_factory_pool = factory_pool[2]
            try:
                factory_globals_dict = glideinFrontendInterface.findGlobals(
                    factory_pool_node, None, glideinFrontendInterface.frontendConfig.factory_global
                )
            except RuntimeError:
                # Failed to talk or likely result is empty
                # Maybe the next factory will have something
                if not factory_pool_node:
                    logSupport.log.exception("Failed to talk to factory_pool %s for global info: " % factory_pool_node)
                else:
                    logSupport.log.exception("Failed to talk to factory_pool for global info: ")
                factory_globals_dict = {}

            for globalid in factory_globals_dict:
                globals_el = factory_globals_dict[globalid]
                if "PubKeyType" not in globals_el["attrs"]:
                    # no pub key at all, nothing to do
                    pass
                elif globals_el["attrs"]["PubKeyType"] == "RSA":
                    # only trust RSA for now
                    try:
                        # The parent really needs just the M2Ctype object,
                        # but that is not picklable, so it will have to
                        # do it ourself
                        globals_el["attrs"]["PubKeyValue"] = str(
                            re.sub(r"\\+n", r"\n", globals_el["attrs"]["PubKeyValue"])
                        )
                        globals_el["attrs"]["FactoryPoolNode"] = factory_pool_node
                        globals_el["attrs"]["FactoryPoolId"] = my_identity_at_factory_pool

                        # KEL: OK to put here?
                        # Do we want all globals even if there is no key?
                        # May resolve other issues with checking later on
                        globals_dict[globalid] = globals_el
                    except KeyError:
                        # if no valid key, just notify...
                        # if key needed, will handle the error later on
                        logSupport.log.warning("Factory Globals '%s': invalid RSA key" % globalid)
                        tb = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
                        logSupport.log.debug(f"Factory Globals '{globalid}': invalid RSA key traceback: {str(tb)}\n")
                else:
                    # don't know what to do with this key, notify the admin
                    # if key needed, will handle the error later on
                    logSupport.log.info(
                        "Factory Globals '%s': unsupported pub key type '%s'"
                        % (globalid, globals_el["attrs"]["PubKeyType"])
                    )

        except Exception:
            logSupport.log.exception("Error in talking to the factory pool:")

        return globals_dict

    def query_factoryclients(self, factory_pool):
        """Queries the factory pool for glidefactoryclient ClassAds and retrieves client monitoring information.

        This method connects to a specified factory pool and fetches information about glidefactoryclients,
        including their attributes and authenticated identities. It applies constraints from the frontend configuration
        and only includes clients that have a trusted and matching authenticated identity. Connection or identity
        errors are logged appropriately.

        Args:
            factory_pool (tuple): A tuple containing the factory pool node, factory identity, and the
                frontend's identity at the factory pool.

        Returns:
            dict: A dictionary mapping (factory_pool_node, glidein name, frontend identity at factory pool)
                to their corresponding client attribute dictionaries. Only trusted clients with matching identities
                are included.
        """
        # Query glidefactoryclient ClassAd

        try:
            factoryclients = {}
            factory_constraint = expand_DD(self.elementDescript.merged_data["FactoryQueryExpr"], self.attr_dict)

            factory_pool_node = factory_pool[0]
            factory_identity = factory_pool[1]
            my_identity_at_factory_pool = factory_pool[2]
            try:
                factory_factoryclients = glideinFrontendInterface.findGlideinClientMonitoring(
                    factory_pool_node, None, self.published_frontend_name, factory_constraint
                )
            except RuntimeError:
                # Failed to talk or likely result is empty
                # Maybe the next factory will have something
                if factory_pool_node:
                    logSupport.log.exception(
                        "Failed to talk to factory_pool %s for glidefactoryclient info: " % factory_pool_node
                    )
                else:
                    logSupport.log.exception("Failed to talk to factory_pool for glidefactoryclient info: ")
                factory_factoryclients = {}

            for glidename in factory_factoryclients:
                auth_id = factory_factoryclients[glidename]["attrs"].get("AuthenticatedIdentity")
                if not auth_id:
                    logSupport.log.warning(f"Found an untrusted factory {glidename} at {factory_pool_node}; ignoring.")
                    break
                if auth_id != factory_identity:
                    logSupport.log.warning(
                        "Found an untrusted factory %s at %s; identity mismatch '%s'!='%s'"
                        % (glidename, factory_pool_node, auth_id, factory_identity)
                    )
                    break
                factoryclients[(factory_pool_node, glidename, my_identity_at_factory_pool)] = factory_factoryclients[
                    glidename
                ]

        except Exception:
            logSupport.log.exception("Error in talking to the factory pool:")

        return factoryclients

    def query_entries(self, factory_pool):
        """Queries the factory pool for glidefactory (glidein) ClassAds and retrieves entry information.

        This method connects to the specified factory pool node and fetches information about available glidein
        entries using provided constraints and signature types. Only glideins with a trusted and matching
        authenticated identity are included in the result. Connection errors and identity mismatches are
        logged for auditing and debugging purposes.

        Args:
            factory_pool (tuple): A tuple containing the factory pool node, factory identity, and
                the frontend's identity at the factory pool.

        Returns:
            dict: A dictionary mapping (factory_pool_node, glidein name, frontend identity at factory pool)
                to their corresponding glidein attribute dictionaries. Only trusted entries with matching
                identities are included.
        """
        # Query glidefactory ClassAd
        try:
            glidein_dict = {}
            factory_constraint = self.elementDescript.merged_data["FactoryQueryExpr"]
            # factory_constraint=expand_DD(self.elementDescript.merged_data['FactoryQueryExpr'], self.attr_dict)

            factory_pool_node = factory_pool[0]
            factory_identity = factory_pool[1]
            my_identity_at_factory_pool = factory_pool[2]
            try:
                factory_glidein_dict = glideinFrontendInterface.findGlideins(
                    factory_pool_node, None, self.signatureDescript.signature_type, factory_constraint
                )
            except RuntimeError:
                # Failed to talk or likely result is empty
                # Maybe the next factory will have something
                if factory_pool_node:
                    logSupport.log.exception("Failed to talk to factory_pool %s for entry info: " % factory_pool_node)
                else:
                    logSupport.log.exception("Failed to talk to factory_pool for entry info: ")
                factory_glidein_dict = {}

            for glidename in factory_glidein_dict:
                auth_id = factory_glidein_dict[glidename]["attrs"].get("AuthenticatedIdentity")
                if not auth_id:
                    logSupport.log.warning(f"Found an untrusted factory {glidename} at {factory_pool_node}; ignoring.")
                    break
                if auth_id != factory_identity:
                    logSupport.log.warning(
                        "Found an untrusted factory %s at %s; identity mismatch '%s'!='%s'"
                        % (glidename, factory_pool_node, auth_id, factory_identity)
                    )
                    break
                glidein_dict[(factory_pool_node, glidename, my_identity_at_factory_pool)] = factory_glidein_dict[
                    glidename
                ]

        except Exception:
            logSupport.log.exception("Error in talking to the factory pool:")

        return glidein_dict

    def query_factory(self, factory_pool):
        """Serializes and performs multiple queries to the same factory pool.

        This method sequentially queries the specified factory pool for global attributes, glidein entries,
        and client monitoring information. It returns the results of these three queries as a tuple.

        Args:
            factory_pool (tuple): A tuple containing factory pool node information and identity details.

        Returns:
            tuple: A tuple containing:
                - dict: Global attributes dictionary returned by `query_globals`.
                - dict: Glidein entries dictionary returned by `query_entries`.
                - dict: Factory client monitoring dictionary returned by `query_factoryclients`.
        """
        return (
            self.query_globals(factory_pool),
            self.query_entries(factory_pool),
            self.query_factoryclients(factory_pool),
        )

    def get_condor_q(self, schedd_name):
        """Retrieve the jobs a schedd is requesting

        Args:
            schedd_name (str): the schedd name

        Returns (dict): a dictionary with all the jobs


        """
        condorq_dict = {}
        try:
            condorq_format_list = self.elementDescript.merged_data["JobMatchAttrs"]
            if self.x509_proxy_plugin:
                condorq_format_list = list(condorq_format_list) + list(
                    self.x509_proxy_plugin.get_required_job_attributes()
                )

            ### Add in elements to help in determining if jobs have voms creds
            condorq_format_list = list(condorq_format_list) + list((("x509UserProxyFirstFQAN", "s"),))
            condorq_format_list = list(condorq_format_list) + list((("x509UserProxyFQAN", "s"),))
            condorq_format_list = list(condorq_format_list) + list((("x509userproxy", "s"),))
            condorq_dict = glideinFrontendLib.getCondorQ(
                [schedd_name],
                self.elementDescript.merged_data["JobQueryExpr"],
                # expand_DD(self.elementDescript.merged_data['JobQueryExpr'], self.attr_dict),
                condorq_format_list,
            )
        except Exception:
            logSupport.log.exception("In query schedd child, exception:")

        return condorq_dict

    def get_condor_status(self):
        """Retrieves and summarizes Condor slot and job status information for the current group and globally.

        This method queries the HTCondor collector for slot and job status information at different levels:
        - All slots for the current frontend group,
        - All slots managed by the entire frontend,
        - All slots known globally to the collector,
        - All schedd classads (scheduler daemons), including those with matchmaking curbs.

        The method applies memory constraints to filter useful slots, accounts for multicore and partitionable slots,
        and gracefully handles errors by logging warnings and returning default values if any query fails.

        Returns:
            tuple: A tuple containing:
                - dict: Status dictionary for all slots in this group, keyed by slot attributes.
                - dict: Counts of idle and total slots for the frontend group (e.g., {'Idle': int, 'Total': int}).
                - dict: Counts of idle and total slots known globally (e.g., {'Idle': int, 'Total': int}).
                - dict: Status dictionary of schedd classads, including information about CurbMatchmaking if available.
        """
        # All slots for this group
        status_dict = {}
        fe_counts = {"Idle": 0, "Total": 0}
        global_counts = {"Idle": 0, "Total": 0}
        status_schedd_dict = {}

        # Minimum free memory required by CMS jobs is 2500 MB. If we look for
        # less memory in idle MC slot, there is a possibility that we consider
        # it as an idle resource but non of the jobs would match it.
        # In case of other VOs that require less memory, HTCondor will auto
        # carve out a slot and there is a chance for over provisioning by a
        # small amount. Over provisioning is by far the worst case than
        # under provisioning.

        # mc_idle_constraint = '(PartitionableSlot=!=True) || (PartitionableSlot=?=True && cpus > 0 && memory > 2500)'

        try:
            # Always get the credential id used to submit the glideins
            # This is essential for proper accounting info related to running
            # glideins that have reported back to user pool
            status_format_list = [
                ("GLIDEIN_CredentialIdentifier", "s"),
                ("TotalSlots", "i"),
                ("Cpus", "i"),
                ("Memory", "i"),
                ("PartitionableSlot", "s"),
                ("SlotType", "s"),
                ("TotalSlotCpus", "i"),
            ]

            if self.x509_proxy_plugin:
                status_format_list = list(status_format_list) + list(
                    self.x509_proxy_plugin.get_required_classad_attributes()
                )

            # Consider multicore slots with free cpus/memory only
            # constraint = '(GLIDECLIENT_Name=?="%s.%s") && (%s)' % (
            #    self.frontend_name, self.group_name, mc_idle_constraint)

            # Consider all slots for this group irrespective of slot type
            constraint = f'(GLIDECLIENT_Name=?="{self.frontend_name}.{self.group_name}")'

            # use the main collector... all adds must go there
            status_dict = glideinFrontendLib.getCondorStatus(
                [None], constraint=constraint, format_list=status_format_list
            )

            # Also get all the classads for the whole FE for counting
            # do it in the same thread, as we are hitting the same collector
            # minimize the number of attributes, since we are
            # really just interest in the counts
            status_format_list = [
                ("State", "s"),
                ("Activity", "s"),
                ("PartitionableSlot", "s"),
                ("TotalSlots", "i"),
                ("Cpus", "i"),
                ("Memory", "i"),
            ]

            try:
                # PM/MM: Feb 09, 2016
                # Do not filter unusable partitionable slots here.
                # Filtering is done at a later stage as needed for idle
                constraint = '(substr(GLIDECLIENT_Name,0,%i)=?="%s.")' % (
                    len(self.frontend_name) + 1,
                    self.frontend_name,
                )

                fe_status_dict = glideinFrontendLib.getCondorStatus(
                    [None], constraint=constraint, format_list=status_format_list, want_format_completion=False
                )

                # fe_counts: PM/MM: Feb 09, 2016
                # Idle: Number of useful idle slots from this frontend
                #       as known to the collector
                # Total: Number of useful total slots from this frontend
                #       as known to the collector
                fe_counts = {
                    "Idle": glideinFrontendLib.countCondorStatus(
                        glideinFrontendLib.getIdleCondorStatus(fe_status_dict, self.p_glidein_min_memory)
                    ),
                    "Total": glideinFrontendLib.countCondorStatus(fe_status_dict),
                }
                del fe_status_dict
            except Exception:
                # This is not critical information, do not fail
                logSupport.log.warning("Error computing slot stats at frontend level. Defaulting to %s" % fe_counts)

            # same for all slots in the collectors
            try:
                constraint = "True"

                global_status_dict = glideinFrontendLib.getCondorStatus(
                    [None],
                    constraint=constraint,
                    want_glideins_only=False,
                    format_list=status_format_list,
                    want_format_completion=False,
                )

                # global_counts: Is similar to fe_counts except that it
                #                accounts for all the slots known to the
                #                collector. i.e. includes monitoring slots,
                #                local cluster slots, etc
                global_counts = {
                    "Idle": glideinFrontendLib.countCondorStatus(
                        glideinFrontendLib.getIdleCondorStatus(global_status_dict, self.p_glidein_min_memory)
                    ),
                    "Total": glideinFrontendLib.countCondorStatus(global_status_dict),
                }
                del global_status_dict
            except Exception:
                # This is not critical information, do not fail
                logSupport.log.warning("Error computing slot stats at global level. Defaulting to %s" % global_counts)

            # Finally, get also the schedd classads
            try:
                status_schedd_dict = glideinFrontendLib.getCondorStatusSchedds([None], constraint=None, format_list=[])
                # Also get the list of schedds that has CurbMatchMaking = True
                # We need to query this explicitly since CurbMatchMaking
                # that we get from condor is a condor expression and is not
                # an evaluated value. So we have to manually filter it out and
                # adjust the info accordingly
                status_curb_schedd_dict = glideinFrontendLib.getCondorStatusSchedds(
                    [None], constraint="CurbMatchmaking=?=True", format_list=[]
                )

                for c in status_curb_schedd_dict:
                    c_curb_schedd_dict = status_curb_schedd_dict[c].fetchStored()
                    for schedd in c_curb_schedd_dict:
                        if schedd in status_schedd_dict[c].fetchStored():
                            status_schedd_dict[c].stored_data[schedd]["CurbMatchmaking"] = "True"

            except Exception:
                # This is not critical information, do not fail
                logSupport.log.warning("Error gathering job stats from schedd. Defaulting to %s" % status_schedd_dict)

        except Exception:
            logSupport.log.exception("Error talking to the user pool (condor_status):")

        return (status_dict, fe_counts, global_counts, status_schedd_dict)

    def do_match(self):
        """Performs the actual job-to-glidein matching process in parallel.

        This method forks subprocesses to parallelize the work of counting glideins, real jobs, and data transfers.
        It runs the following subprocess methods in parallel:
        - self.subprocess_count_glidein
        - self.subprocess_count_real
        - self.subprocess_count_dt

        The results are stored in the following dictionaries:
        - self.count_status_multi
        - self.count_status_multi_per_cred
        - self.count_real_jobs
        - self.count_real_glideins
        - self.condorq_dict_types

        Returns:
            None: This method updates internal attributes with matching results and does not return a value.
        """

        # IS: Heuristics of 100 glideins per fork
        #     Based on times seen by CMS
        glideins_per_fork = 100

        glidein_list = list(self.glidein_dict.keys())
        # split the list in equal pieces
        # the result is a list of lists
        split_glidein_list = [
            glidein_list[i : i + glideins_per_fork] for i in range(0, len(glidein_list), glideins_per_fork)
        ]

        forkm_obj = ForkManager()

        for i in range(len(split_glidein_list)):
            forkm_obj.add_fork(("Glidein", i), self.subprocess_count_glidein, split_glidein_list[i])

        forkm_obj.add_fork("Real", self.subprocess_count_real)

        for dt in self.condorq_dict_types:
            forkm_obj.add_fork(dt, self.subprocess_count_dt, dt)

        try:
            t_begin = time.time()
            pipe_out = forkm_obj.bounded_fork_and_collect(self.max_matchmakers)
            t_end = time.time() - t_begin
        except RuntimeError:
            # expect all errors logged already
            logSupport.log.exception("Terminating iteration due to errors:")
            return
        logSupport.log.info("All children terminated - took %s seconds" % t_end)

        for dt, el in self.condorq_dict_types.items():
            # c, p, h, pmc, t returned by  subprocess_count_dt(self, dt)
            (el["count"], el["prop"], el["hereonly"], el["prop_mc"], el["total"]) = pipe_out[dt]

        (self.count_real_jobs, self.count_real_glideins) = pipe_out["Real"]
        self.count_status_multi = {}
        self.count_status_multi_per_cred = {}
        for i in range(len(split_glidein_list)):
            tmp_count_status_multi = pipe_out[("Glidein", i)][0]
            self.count_status_multi.update(tmp_count_status_multi)
            tmp_count_status_multi_per_cred = pipe_out[("Glidein", i)][1]
            self.count_status_multi_per_cred.update(tmp_count_status_multi_per_cred)

    def subprocess_count_dt(self, dt):
        """Counts the matches (glideins matching entries) using glideinFrontendLib.countMatch.

        This method performs calculations in parallel using multiple processes to determine
        the number of matches for a given index within the data dictionary.

        Args:
            dt (int): Index within the data dictionary to process.

        Returns:
            tuple: A tuple of five elements:
                - count: Number of matches.
                - prop: Proportional matches.
                - hereonly: Matches exclusive to this context.
                - prop_mc: Proportional multicore matches.
                - total: Total matches.
        """

        out = ()

        c, p, h, pmc = glideinFrontendLib.countMatch(
            self.elementDescript.merged_data["MatchExprCompiledObj"],
            self.condorq_dict_types[dt]["dict"],
            self.glidein_dict,
            self.attr_dict,
            self.ignore_down_entries,
            self.condorq_match_list,
            match_policies=self.elementDescript.merged_data["MatchPolicyModules"],
            # This is the line to enable if you want the frontend to dump data structures during countMatch
            # You can then use the profile_frontend.py script to execute the countMatch function with real data
            # Data will be saved into /tmp/frontend_dump/ . Make sure to create the dir beforehand.
            #                        group_name=self.group_name
        )
        t = glideinFrontendLib.countCondorQ(self.condorq_dict_types[dt]["dict"])

        out = (c, p, h, pmc, t)

        return out

    def subprocess_count_real(self):
        """Counts the jobs running on glideins for the current requests using glideinFrontendLib.countRealRunning.

        This method performs the calculations in parallel using multiple processes to determine
        the number of real jobs and real glideins running for the requests.

        Returns:
            tuple: A tuple containing:
                - count_real_jobs (int): Number of real jobs running on glideins.
                - count_real_glideins (int): Number of real glideins running jobs.
        """
        out = glideinFrontendLib.countRealRunning(
            self.elementDescript.merged_data["MatchExprCompiledObj"],
            self.condorq_dict_running,
            self.glidein_dict,
            self.attr_dict,
            self.condorq_match_list,
            match_policies=self.elementDescript.merged_data["MatchPolicyModules"],
        )
        return out

    def subprocess_count_glidein(self, glidein_list):
        """Counts statistics for glideins in parallel using multiple processes.

        This method calculates various statistics for the provided list of glideins,
        distributing the work across multiple processes for efficiency.

        Args:
            glidein_list (list): List of glideins to analyze.

        Returns:
            tuple: A tuple containing statistics results for the given glideins.
                (You can specify the exact elements of the tuple if known.)
        """
        out = ()

        count_status_multi = {}
        # Count distribution per credentials
        count_status_multi_per_cred = {}
        for glideid in glidein_list:
            request_name = glideid[1]

            count_status_multi[request_name] = {}
            count_status_multi_per_cred[request_name] = {}
            for cred in self.x509_proxy_plugin.cred_list:
                count_status_multi_per_cred[request_name][cred.getId()] = {}

            # It is cheaper to get Idle and Running from request-only
            # classads then filter out requests from Idle and Running
            # glideins
            total_req_dict = glideinFrontendLib.getClientCondorStatus(
                self.status_dict_types["Total"]["dict"], self.frontend_name, self.group_name, request_name
            )

            req_dict_types = {
                "Total": total_req_dict,
                "Idle": glideinFrontendLib.getIdleCondorStatus(total_req_dict, self.p_glidein_min_memory),
                "Running": glideinFrontendLib.getRunningCondorStatus(total_req_dict),
                "Failed": glideinFrontendLib.getFailedCondorStatus(total_req_dict),
                "TotalCores": glideinFrontendLib.getCondorStatusNonDynamic(total_req_dict),
                "IdleCores": glideinFrontendLib.getIdleCoresCondorStatus(total_req_dict),
                "RunningCores": glideinFrontendLib.getRunningCoresCondorStatus(total_req_dict),
            }

            for st in req_dict_types:
                req_dict = req_dict_types[st]
                if st in ("TotalCores", "IdleCores", "RunningCores"):
                    count_status_multi[request_name][st] = glideinFrontendLib.countCoresCondorStatus(req_dict, st)
                elif st == "Running":
                    # Running counts are computed differently because of
                    # the dict composition. Dict also has p-slots
                    # corresponding to the dynamic slots
                    count_status_multi[request_name][st] = glideinFrontendLib.countRunningCondorStatus(req_dict)
                else:
                    count_status_multi[request_name][st] = glideinFrontendLib.countCondorStatus(req_dict)

                for cred in self.x509_proxy_plugin.cred_list:
                    cred_id = cred.getId()
                    cred_dict = glideinFrontendLib.getClientCondorStatusCredIdOnly(req_dict, cred_id)

                    if st in ("TotalCores", "IdleCores", "RunningCores"):
                        count_status_multi_per_cred[request_name][cred_id][st] = (
                            glideinFrontendLib.countCoresCondorStatus(cred_dict, st)
                        )
                    elif st == "Running":
                        # Running counts are computed differently because of
                        # the dict composition. Dict also has p-slots
                        # corresponding to the dynamic slots
                        count_status_multi_per_cred[request_name][cred_id][st] = (
                            glideinFrontendLib.countRunningCondorStatus(cred_dict)
                        )
                    else:
                        count_status_multi_per_cred[request_name][cred_id][st] = glideinFrontendLib.countCondorStatus(
                            cred_dict
                        )

        out = (count_status_multi, count_status_multi_per_cred)

        return out


############################################################
def check_parent(parent_pid):
    if os.path.exists("/proc/%s" % parent_pid):
        return  # parent still exists, we are fine

    logSupport.log.warning("Parent died, exit.")
    raise KeyboardInterrupt("Parent died")


############################################################
def write_stats(stats):
    for k in list(stats.keys()):
        stats[k].write_file()


############################################################
def log_and_sum_factory_line(factory, is_down, factory_stat_arr, old_factory_stat_arr=None):
    """Logs the factory statistics array and returns the sum with the old statistics array if provided.

    This function logs the provided factory statistics (a tuple of 17 numbers) and, if an
    old statistics array is given, returns a new list with element-wise sums of factory_stat_arr
    and old_factory_stat_arr.

    Args:
        factory (str): Entry name or a label to use when writing totals.
        is_down (bool): True if the entry is down, otherwise False.
        factory_stat_arr (tuple): Frontend statistics for this line (tuple of 17 numbers).
        old_factory_stat_arr (list or None): Accumulator for the line stats. If None, only logs are performed.

    Returns:
        list or None: A new list containing the element-wise sum of old_factory_stat_arr and factory_stat_arr,
        or None if old_factory_stat_arr is None.
    """
    # if numbers are too big, reduce them to either k or M for presentation
    form_arr = []
    for i in factory_stat_arr:
        if i < 100000:
            form_arr.append("%5i" % i)
        elif i < 10000000:
            form_arr.append("%4ik" % (i // 1000))
        else:
            form_arr.append("%4iM" % (i // 1000000))

    if is_down:
        down_str = "Down"
    else:
        down_str = "Up  "

    logSupport.log.info(
        ("%s(%s %s %s %s) %s(%s %s) | %s %s %s %s | %s %s %s | %s %s | " % tuple(form_arr)) + (f"{down_str} {factory}")
    )

    if old_factory_stat_arr is None:
        return None
    # else branch, a valid old_factory_stat_arr hes been provided
    new_arr = []
    for i in range(len(factory_stat_arr)):
        new_arr.append(factory_stat_arr[i] + old_factory_stat_arr[i])
    return new_arr


def init_factory_stats_arr():
    return [0] * 17


def log_factory_header():
    """Logs the formatted header lines for factory and entry statistics output.

    This function logs two informational lines that serve as column headers
    for subsequent statistics about jobs, slots, cores, glidein requests,
    and factory/entry information.

    Args:
        None

    Returns:
        None: This function only performs logging.
    """
    logSupport.log.info(
        "            Jobs in schedd queues                 |           Slots         |       Cores       | Glidein Req | Factory/Entry Information"
    )
    logSupport.log.info(
        "Idle (match  eff   old  uniq )  Run ( here  max ) | Total  Idle   Run  Fail | Total  Idle   Run | Idle MaxRun | State Factory"
    )


# TODO: 5345 to remove once verified, because global expansion is supported during configuration
def expand_DD(qstr, attr_dict):
    """expand $$(attribute)

    Args:
        qstr (str): string to be expanded
        attr_dict (dict): attributes to use in the expansion

    Returns:
        str: expanded string

    """
    robj = re.compile(r"\$\$\((?P<attrname>[^\)]*)\)")
    while True:
        m = robj.search(qstr)
        if m is None:
            break  # no more substitutions to do
        attr_name = m.group("attrname")
        if attr_name not in attr_dict:
            raise KeyError("Missing attribute %s" % attr_name)
        attr_val = attr_dict[attr_name]
        if isinstance(attr_val, int):
            attr_str = str(attr_val)
        else:  # assume it is a string for all other purposes... quote and escape existing quotes
            attr_str = '"%s"' % attr_val.replace('"', '\\"')
        qstr = f"{qstr[: m.start()]}{attr_str}{qstr[m.end() :]}"
    return qstr


############################################################
#
# S T A R T U P
#
############################################################

if __name__ == "__main__":
    register_sighandler()
    if len(sys.argv) == 4:
        action = "run"
    else:
        action = sys.argv[4]
    gfe = glideinFrontendElement(int(sys.argv[1]), sys.argv[2], sys.argv[3], action)
    rcm = gfe.main()

    # explicitly exit with 0
    # this allows for reliable checking
    sys.exit(rcm)
