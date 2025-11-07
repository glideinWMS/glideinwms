#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Entry class.

Model and behavior of a Factory Entry (an element describing a resource).
"""

import copy
import os
import os.path
import signal
import sys
import tempfile
import traceback

from glideinwms.factory import glideFactoryConfig, glideFactoryCredentials, glideFactoryDowntimeLib
from glideinwms.factory import glideFactoryInterface as gfi
from glideinwms.factory import glideFactoryLib, glideFactoryLogParser, glideFactoryMonitoring
from glideinwms.lib import classadSupport, cleanupSupport, defaults, glideinWMSVersion, logSupport, token_util, util
from glideinwms.lib.util import chmod


############################################################
class Entry:
    def __init__(self, name, startup_dir, glidein_descript, frontend_descript):
        """Construct an Entry instance.

        Args:
            name (str): Name of the entry.
            startup_dir (str): Path to the Factory workspace.
            glidein_descript (glideFactoryConfig.GlideinDescript): Factory glidein configuration values.
            frontend_descript (glideFactoryConfig.FrontendDescript): Security mappings for Frontend identities and security classes.
        """
        self.limits_triggered = {}
        self.name = name
        self.startupDir = startup_dir
        self.glideinDescript = glidein_descript
        self.frontendDescript = frontend_descript

        self.signatures = glideFactoryConfig.SignatureFile()

        self.jobDescript = glideFactoryConfig.JobDescript(name)
        self.jobAttributes = glideFactoryConfig.JobAttributes(name)
        self.jobParams = glideFactoryConfig.JobParams(name)
        self.jobSubmitAttrs = glideFactoryConfig.JobSubmitAttrs(name)

        # glideFactoryMonitoring.monitoringConfig.monitor_dir
        self.monitorDir = os.path.join(self.startupDir, "monitor/entry_%s" % self.name)

        # Dir where my logs are stored
        self.logDir = os.path.join(self.glideinDescript.data["LogDir"], "entry_%s" % self.name)

        # Schedd where my glideins will be submitted
        self.scheddName = self.jobDescript.data["Schedd"]

        # glideFactoryLib.log_files
        self.log = logSupport.get_logger_with_handlers(self.name, self.logDir, self.glideinDescript.data)

        cleaner = cleanupSupport.DirCleanupWSpace(
            self.logDir,
            r"(condor_activity_.*\.log\..*\.ftstpk)",
            glideFactoryLib.days2sec(float(self.glideinDescript.data["CondorLogRetentionMaxDays"])),
            glideFactoryLib.days2sec(float(self.glideinDescript.data["CondorLogRetentionMinDays"])),
            float(self.glideinDescript.data["CondorLogRetentionMaxMBs"]) * pow(2, 20),
        )
        cleanupSupport.cleaners.add_cleaner(cleaner)

        self.monitoringConfig = glideFactoryMonitoring.MonitoringConfig(log=self.log)
        self.monitoringConfig.monitor_dir = self.monitorDir
        self.monitoringConfig.my_name = "{}@{}".format(name, self.glideinDescript.data["GlideinName"])

        self.monitoringConfig.config_log(
            self.logDir,
            float(self.glideinDescript.data["SummaryLogRetentionMaxDays"]),
            float(self.glideinDescript.data["SummaryLogRetentionMinDays"]),
            float(self.glideinDescript.data["SummaryLogRetentionMaxMBs"]),
        )

        # FactoryConfig object from glideFactoryInterface
        self.gfiFactoryConfig = gfi.FactoryConfig()
        # self.gfiFactoryConfig.warning_log = self.log.warning_log
        self.gfiFactoryConfig.advertise_use_tcp = self.glideinDescript.data["AdvertiseWithTCP"] in ("True", "1")
        self.gfiFactoryConfig.advertise_use_multi = self.glideinDescript.data["AdvertiseWithMultiple"] in ("True", "1")
        # set factory_collector at a global level, since we do not expect it to change
        self.gfiFactoryConfig.factory_collector = self.glideinDescript.data["FactoryCollector"]

        try:
            self.gfiFactoryConfig.glideinwms_version = glideinWMSVersion.GlideinWMSDistro("checksum.factory").version()
        except Exception:
            tb = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            self.log.warning(
                "Exception occurred while trying to retrieve the glideinwms version. See debug log for more details."
            )
            self.log.debug("Exception occurred while trying to retrieve the glideinwms version: %s" % tb)

        # FactoryConfig object from glideFactoryLib
        self.gflFactoryConfig = glideFactoryLib.FactoryConfig()

        self.gflFactoryConfig.config_whoamI(
            self.glideinDescript.data["FactoryName"], self.glideinDescript.data["GlideinName"]
        )

        self.gflFactoryConfig.config_dirs(
            self.startupDir,
            self.glideinDescript.data["LogDir"],
            self.glideinDescript.data["ClientLogBaseDir"],
            self.glideinDescript.data["ClientProxiesBaseDir"],
        )

        self.gflFactoryConfig.max_submits = int(self.jobDescript.data["MaxSubmitRate"])
        self.gflFactoryConfig.max_cluster_size = int(self.jobDescript.data["SubmitCluster"])
        self.gflFactoryConfig.slots_layout = self.jobDescript.data["SubmitSlotsLayout"]
        self.gflFactoryConfig.submit_sleep = float(self.jobDescript.data["SubmitSleep"])
        self.gflFactoryConfig.max_removes = int(self.jobDescript.data["MaxRemoveRate"])
        self.gflFactoryConfig.remove_sleep = float(self.jobDescript.data["RemoveSleep"])
        self.gflFactoryConfig.max_releases = int(self.jobDescript.data["MaxReleaseRate"])
        self.gflFactoryConfig.release_sleep = float(self.jobDescript.data["ReleaseSleep"])
        self.gflFactoryConfig.log_stats = glideFactoryMonitoring.condorLogSummary(log=self.log)
        self.gflFactoryConfig.rrd_stats = glideFactoryMonitoring.FactoryStatusData(
            log=self.log, base_dir=self.monitoringConfig.monitor_dir
        )
        self.gflFactoryConfig.rrd_stats.base_dir = self.monitorDir

        # Configure stale times
        self.gflFactoryConfig.stale_maxage[1] = int(self.jobDescript.data["StaleAgeIdle"])
        self.gflFactoryConfig.stale_maxage[2] = int(self.jobDescript.data["StaleAgeRunning"])
        self.gflFactoryConfig.stale_maxage[-1] = int(self.jobDescript.data["StaleAgeUnclaimed"])

        # Add cleaners for the user log directories
        for username in self.frontendDescript.get_all_usernames():
            user_log_dir = self.gflFactoryConfig.get_client_log_dir(self.name, username)
            cleaner = cleanupSupport.DirCleanupWSpace(
                user_log_dir,
                r"(job\..*\.out)|(job\..*\.err)",
                glideFactoryLib.days2sec(float(self.glideinDescript.data["JobLogRetentionMaxDays"])),
                glideFactoryLib.days2sec(float(self.glideinDescript.data["JobLogRetentionMinDays"])),
                float(self.glideinDescript.data["JobLogRetentionMaxMBs"]) * pow(2, 20),
            )
            cleanupSupport.cleaners.add_cleaner(cleaner)

            cleaner = cleanupSupport.DirCleanupWSpace(
                user_log_dir,
                r"(condor_activity_.*\.log)|(condor_activity_.*\.log.ftstpk)|(submit_.*\.log)",
                glideFactoryLib.days2sec(float(self.glideinDescript.data["CondorLogRetentionMaxDays"])),
                glideFactoryLib.days2sec(float(self.glideinDescript.data["CondorLogRetentionMinDays"])),
                float(self.glideinDescript.data["CondorLogRetentionMaxMBs"]) * pow(2, 20),
            )
            cleanupSupport.cleaners.add_cleaner(cleaner)

        self.glideinTotals = None

        # Load initial context for whitelist and downtimes
        self.loadWhitelist()
        self.loadDowntimes()

        # Create entry specific descript files
        write_descript(self.name, self.jobDescript, self.jobAttributes, self.jobParams, self.monitorDir)

    def loadContext(self):
        """Load the context for this entry.

        Sets up the monitoring configuration, factory configuration,
        and logging configuration for this entry. Should be called at the start
        of each method that needs to operate within the correct context.
        """
        glideFactoryMonitoring.monitoringConfig = self.monitoringConfig
        gfi.factoryConfig = self.gfiFactoryConfig
        glideFactoryLib.factoryConfig = self.gflFactoryConfig

    # TODO: This function should return the same number as getGlideinCpusNum(glidein) in glideinFrontendLib
    # TODO: consider moving getGlideinCpusNum to shared lib (and wrap it to avoid ValueError)
    def getGlideinExpectedCores(self):
        """Return the expected number of cores for each glidein.

        This returns the value of the GLIDEIN_CPUS attribute if > 0;
        otherwise, it returns the GLIDEIN_ESTIMATED_CPUS value when GLIDEIN_CPUS <= 0
        or a string (auto/node/slot) or 1 if not set.
        Note that this number is used in provisioning and set in HTCondor. The actual
        number of cores used will depend on the RSL or HTCondor attributes, on the Entry,
        and could also vary over time.

        Returns:
            int: The expected number of cores.
        """
        try:
            cpus = str(self.jobAttributes.data["GLIDEIN_CPUS"])
            try:
                glidein_cpus = int(cpus)
            except ValueError:
                cpus = int(self.jobAttributes.data["GLIDEIN_ESTIMATED_CPUS"])
                return cpus
            if glidein_cpus <= 0:
                cpus = int(self.jobAttributes.data["GLIDEIN_ESTIMATED_CPUS"])
                return cpus
            else:
                return glidein_cpus
        except (KeyError, ValueError):
            return 1

    def loadWhitelist(self):
        """Load the whitelist information for this entry.

        Retrieves the allowed VOs and corresponding security classes from the job description.
        If whitelist mode is enabled, populates the securityList attribute.
        """
        # Get information about which VOs to allow for this entry point.
        # This will be a comma-delimited list of pairs
        # vofrontendname:security_class,vofrontend:sec_class, ...
        self.frontendWhitelist = self.jobDescript.data["WhitelistMode"]
        self.securityList = {}
        if self.frontendWhitelist == "On":
            allowed_vos = ""
            if "AllowedVOs" in self.jobDescript:
                allowed_vos = self.jobDescript.data["AllowedVOs"]
            frontend_allow_list = allowed_vos.split(",")
            for entry in frontend_allow_list:
                entry_part = entry.split(":")
                if entry_part[0] in self.securityList:
                    self.securityList[entry_part[0]].append(entry_part[1])
                else:
                    self.securityList[entry_part[0]] = [entry_part[1]]
        # self.allowedProxySource = self.glideinDescript.data['AllowedJobProxySource'].split(',')

    def loadDowntimes(self):
        """Load downtime information for this entry.

        Loads downtime data from the downtime file specified in the glidein description
        and updates the job attributes with the downtime comment.
        """
        self.downtimes = glideFactoryDowntimeLib.DowntimeFile(self.glideinDescript.data["DowntimesFile"])
        self.downtimes.check_downtime(entry=self.name)
        self.jobAttributes.data["GLIDEIN_Downtime_Comment"] = self.downtimes.downtime_comment

    def isClientBlacklisted(self, client_sec_name):
        """Check if a client (Frontend) is blacklisted. I.e. the whitelist is enabled and the client is not in the list.

        Args:
            client_sec_name (str): The security name of the client.

        Returns:
            bool: True if the frontend whitelist is enabled and the client is not in the whitelist, False otherwise.
        """
        return (self.frontendWhitelist == "On") and (not self.isClientInWhitelist(client_sec_name))

    def isClientWhitelisted(self, client_sec_name):
        """Check if a client (Frontend) is whitelisted.

        Args:
            client_sec_name (str): The security name of the client.

        Returns:
            bool: True if the clients whitelist is enabled and the client is in the whitelist, False otherwise.
        """
        return (self.frontendWhitelist == "On") and (self.isClientInWhitelist(client_sec_name))

    def isClientInWhitelist(self, client_sec_name):
        """Check if a client's security name is in the whitelist of this entry.

        Args:
            client_sec_name (str): The security name of the client.

        Returns:
            bool: True if the client is in the whitelist, False otherwise.
        """
        return client_sec_name in self.securityList

    def isSecurityClassAllowed(self, client_sec_name, proxy_sec_class):
        """Check if a proxy security class is allowed for a client.

        Args:
            client_sec_name (str): The client's security name.
            proxy_sec_class (str): The security class of the proxy.

        Returns:
            bool: True if the security class is allowed for the client, False otherwise.
        """
        return (proxy_sec_class in self.securityList[client_sec_name]) or ("All" in self.securityList[client_sec_name])

    def isInDowntime(self):
        """Determine if the entry is currently in downtime.

        Returns:
            bool: True if the entry is in downtime, False otherwise.
        """
        return self.downtimes.check_downtime(entry=self.name)

    def isSecurityClassInDowntime(self, client_security_name, security_class):
        """Check if a security class is in downtime in the Factory or in this Entry.

        Args:
            client_security_name (str): The client's security name.
            security_class (str): The security class to check.

        Returns:
            bool: True if the security class is in downtime in the Factory or this entry, False otherwise.
        """
        return (
            self.downtimes.check_downtime(entry="factory", frontend=client_security_name, security_class=security_class)
        ) or (
            self.downtimes.check_downtime(entry=self.name, frontend=client_security_name, security_class=security_class)
        )

    def setDowntime(self, downtime_flag):
        """Check if the entry or Factory is in downtime and set the job status accordingly.

        Updates the job attributes with the downtime status. If either the provided flag is True or the entry
        is in downtime, the attribute "GLIDEIN_In_Downtime" is updated accordingly.

        Args:
            downtime_flag (bool): The downtime flag.
        """
        self.jobAttributes.data["GLIDEIN_In_Downtime"] = downtime_flag or self.isInDowntime()

    def initIteration(self, factory_in_downtime):
        """Initialize the entry for a new iteration.

        Resets statistics, updates downtime status, and initializes client statistics.

        Args:
            factory_in_downtime (bool): Flag indicating if the factory is in downtime.
        """
        self.loadContext()

        self.setDowntime(factory_in_downtime)

        self.gflFactoryConfig.log_stats.reset()

        # This one is used for stats advertised in the ClassAd
        self.gflFactoryConfig.client_stats = glideFactoryMonitoring.condorQStats(
            log=self.log, cores=self.getGlideinExpectedCores()
        )
        # These two are used to write the history to disk
        self.gflFactoryConfig.qc_stats = glideFactoryMonitoring.condorQStats(
            log=self.log, cores=self.getGlideinExpectedCores()
        )
        self.gflFactoryConfig.client_internals = {}
        self.log.info("Iteration initialized")

    def unsetInDowntime(self):
        """Clear the downtime status for the entry."""
        del self.jobAttributes.data["GLIDEIN_In_Downtime"]

    def queryQueuedGlideins(self):
        """Query the HTCondor schedd for glidein job information.

        Query the WMS schedd (on Factory) and get glideins info. Re-raise exceptions in case of failures.
        Return a loaded condorMonitor.CondorQ object using the entry attributes (name, schedd, ...).
        Consists of a fetched dictionary with jobs (keyed by job cluster, ID) in .stored_data,
        some query attributes and the ability to reload (load/fetch)

        Returns:
            condorMonitor.CondorQ: A loaded CondorQ object with job information.
        """
        try:
            return glideFactoryLib.getCondorQData(self.name, None, self.scheddName, factoryConfig=self.gflFactoryConfig)
        except Exception:
            self.log.info("Schedd %s not responding, skipping" % self.scheddName)
            tb = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            self.log.warning("getCondorQData failed, traceback: %s" % "".join(tb))
            raise

    def glideinsWithinLimits(self, condorQ):
        """Check if glidein submission is within allowed limits.

        This function checks both per-entry and per-client limits set in the Factory based on the Condor queue.
        It also updates the limits_triggered attribute with details of any exceeded limits.

        Args:
            condorQ (condorMonitor.CondorQ): The CondorQ object with job information.

        Returns:
            bool: True if additional glideins can be submitted, False otherwise.
        """
        # Flag that says whether we can submit or not more glideins
        can_submit_glideins = True

        # Initialize entry and frontend limit dicts
        self.glideinTotals = glideFactoryLib.GlideinTotals(
            self.name, self.frontendDescript, self.jobDescript, condorQ, log=self.log
        )

        # Check if entry has exceeded max idle
        if self.glideinTotals.has_entry_exceeded_max_idle():
            self.log.warning("Entry %s has hit the limit for idle glideins, cannot submit any more" % self.name)
            can_submit_glideins = False
        # Check if entry has exceeded max glideins
        if can_submit_glideins and self.glideinTotals.has_entry_exceeded_max_glideins():
            self.log.warning("Entry %s has hit the limit for total glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        # Check if entry has exceeded max held
        if can_submit_glideins and self.glideinTotals.has_entry_exceeded_max_held():
            self.log.warning("Entry %s has hit the limit for held glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        # set limits_triggered here so that it can be getStated and setStated later
        glideinTotals = self.glideinTotals
        if glideinTotals.has_entry_exceeded_max_idle():
            self.limits_triggered["IdleGlideinsPerEntry"] = "count=%i, limit=%i" % (
                glideinTotals.entry_idle,
                glideinTotals.entry_max_idle,
            )

        if glideinTotals.has_entry_exceeded_max_held():
            self.limits_triggered["HeldGlideinsPerEntry"] = "count=%i, limit=%i" % (
                glideinTotals.entry_held,
                glideinTotals.entry_max_held,
            )

        if glideinTotals.has_entry_exceeded_max_glideins():
            total_max_glideins = glideinTotals.entry_idle + glideinTotals.entry_running + glideinTotals.entry_held
            self.limits_triggered["TotalGlideinsPerEntry"] = "count=%i, limit=%i" % (
                total_max_glideins,
                glideinTotals.entry_max_glideins,
            )

        all_frontends = self.frontendDescript.get_all_frontend_sec_classes()
        self.limits_triggered["all_frontends"] = all_frontends

        for fe_sec_class in all_frontends:
            if (
                glideinTotals.frontend_limits[fe_sec_class]["idle"]
                > glideinTotals.frontend_limits[fe_sec_class]["max_idle"]
            ):
                fe_key = "IdlePerClass_%s" % fe_sec_class
                self.limits_triggered[fe_key] = "count=%i, limit=%i" % (
                    glideinTotals.frontend_limits[fe_sec_class]["idle"],
                    glideinTotals.frontend_limits[fe_sec_class]["max_idle"],
                )

            total_sec_class_glideins = (
                glideinTotals.frontend_limits[fe_sec_class]["idle"]
                + glideinTotals.frontend_limits[fe_sec_class]["held"]
                + glideinTotals.frontend_limits[fe_sec_class]["running"]
            )
            if total_sec_class_glideins > glideinTotals.frontend_limits[fe_sec_class]["max_glideins"]:
                fe_key = "TotalPerClass_%s" % fe_sec_class
                self.limits_triggered[fe_key] = "count=%i, limit=%i" % (
                    total_sec_class_glideins,
                    glideinTotals.frontend_limits[fe_sec_class]["max_glideins"],
                )

        return can_submit_glideins

    def getGlideinConfiguredLimits(self):
        """Extract the configured glidein limits for advertisement in ClassAds.

        Returns:
            dict: A dictionary containing the configured limits.
        """
        configured_limits = {}

        # Create list of attributes upfrontend and iterate over them.
        limits = (
            # DefaultPerFrontend limits
            "DefaultPerFrontendMaxIdle",
            "DefaultPerFrontendMaxHeld",
            "DefaultPerFrontendMaxGlideins",
            # PerFrontend limits
            "PerFrontendMaxIdle",
            "PerFrontendMaxHeld",
            "PerFrontendMaxGlideins",
            # PerEntry limits
            "PerEntryMaxIdle",
            "PerEntryMaxHeld",
            "PerEntryMaxGlideins",
        )

        for limit in limits:
            if limit.startswith("PerFrontend"):
                # PerFrontend limit has value that cannot be converted to int
                # without further processing.
                # 'Frontend-master:frontend;100,Frontend-master:foo;100'
                # Add the string values for PerFrontend limits along with
                # processed values
                configured_limits[limit] = self.jobDescript.data[limit].replace(";", "=")

                # NOTE: (Parag: March 04, 2016)
                # Rest of the code is disabled for now. Assumption is that
                # the external monitoring components can do the processing
                # so we dont have to. If required we can just easily enable
                # the code if required.
                # for fe_sec in self.jobDescript.data[limit].split(','):
                #    try:
                #        tokens = fe_sec.split(';')
                #        k = '%s_%s' % (limit, tokens[0].replace(':', '__'))
                #        configured_limits[k] = int(tokens[1])
                #    except Exception:
                #        logSupport.log.warning('Error extracting %s for %s from %s' % (limit, fe_sec, self.jobDescript.data[limit]))
            else:
                try:
                    # Default and per entry limits are numeric
                    configured_limits[limit] = int(self.jobDescript.data[limit])
                except (KeyError, ValueError):
                    logSupport.log.warning(f"{limit} (value={self.jobDescript.data[limit]}) is not an int")

        return configured_limits

    def writeClassadsToFile(self, downtime_flag, gf_filename, gfc_filename, append=True):
        """Write the glidefactory and glidefactoryclient ClassAds to files.

        This function creates ClassAds for the Factory and client monitoring,
        and writes them to the specified files.
        Advertising is done in a separate function.

        Args:
            downtime_flag (bool): Flag indicating whether the Factory is in downtime or not.
            gf_filename (str): Filename to write the glidefactory classads.
            gfc_filename (str): Filename to write the glidefactoryclient classads.
            append (bool, optional): If True, append to existing files (i.e Multi ClassAds file);
                otherwise, overwrite. Defaults to True.
        """
        self.loadContext()

        trust_domain = self.jobDescript.data["TrustDomain"]
        auth_method = self.jobDescript.data["AuthMethod"]
        pub_key_obj = self.glideinDescript.data["PubKeyObj"]

        self.gflFactoryConfig.client_stats.finalizeClientMonitor()
        current_qc_total = self.gflFactoryConfig.client_stats.get_total()

        ########################################################################
        # Logic to generate glidefactory classads file
        ########################################################################

        glidein_monitors = {}
        for w in current_qc_total:
            for a in current_qc_total[w]:
                # Summary stats to publish in GF and all GFC ClassAds
                glidein_monitors[f"Total{w}{a}"] = current_qc_total[w][a]

        # Load serialized aggregated Factory statistics
        stats = util.file_pickle_load(
            os.path.join(self.startupDir, glideFactoryConfig.factoryConfig.aggregated_stats_file),
            mask_exceptions=(logSupport.log.exception, "Reading of aggregated statistics failed: "),
            default={},
            expiration=3600,
        )

        stats_dict = {}
        try:
            stats_dict["entry"] = util.dict_normalize(
                stats["LogSummary"]["entries"][self.name]["total"]["CompletedCounts"]["JobsNr"],
                glideFactoryMonitoring.getAllJobRanges(),
                "CompletedJobsPerEntry",
                default=0,
            )
            stats_dict["total"] = util.dict_normalize(
                stats["LogSummary"]["total"]["CompletedCounts"]["JobsNr"],
                glideFactoryMonitoring.getAllJobRanges(),
                "CompletedJobsPerFactory",
                default=0,
            )
        except (KeyError, TypeError):
            # dict_normalize() already handles partial availability
            # If there is an error all stats may be corrupted, do not publish
            stats_dict = {}

        glidein_web_attrs = {
            #'GLIDEIN_StartupDir': self.jobDescript.data["StartupDir"],
            #'GLIDEIN_Verbosity': self.jobDescript.data["Verbosity"],
            "URL": self.glideinDescript.data["WebURL"],
            "SignType": "sha1",
            "DescriptFile": self.signatures.data["main_descript"],
            "DescriptSign": self.signatures.data["main_sign"],
            "EntryDescriptFile": self.signatures.data["entry_%s_descript" % self.name],
            "EntryDescriptSign": self.signatures.data["entry_%s_sign" % self.name],
        }

        # Make copy of job attributes so can override the validation
        # downtime setting with the true setting of the entry
        # (not from validation)
        myJobAttributes = self.jobAttributes.data.copy()
        myJobAttributes["GLIDEIN_In_Downtime"] = downtime_flag or self.isInDowntime()
        gf_classad = gfi.EntryClassad(
            self.gflFactoryConfig.factory_name,
            self.gflFactoryConfig.glidein_name,
            self.name,
            trust_domain,
            auth_method,
            self.gflFactoryConfig.supported_signtypes,
            pub_key_obj=pub_key_obj,
            glidein_submit=self.jobSubmitAttrs.data.copy(),
            glidein_attrs=myJobAttributes,
            glidein_params=self.jobParams.data.copy(),
            glidein_monitors=glidein_monitors.copy(),
            glidein_stats=stats_dict,
            glidein_web_attrs=glidein_web_attrs,
            glidein_config_limits=self.getGlideinConfiguredLimits(),
        )
        try:
            gf_classad.writeToFile(gf_filename, append=append)
        except Exception:
            self.log.warning("Error writing classad to file %s" % gf_filename)
            self.log.exception("Error writing classad to file %s: " % gf_filename)

        ########################################################################
        # Logic to generate glidefactoryclient classads file
        ########################################################################

        # Advertise the monitoring, use the downtime found in
        # validation of the credentials

        advertizer = gfi.MultiAdvertizeGlideinClientMonitoring(
            self.gflFactoryConfig.factory_name,
            self.gflFactoryConfig.glidein_name,
            self.name,
            self.jobAttributes.data.copy(),
        )

        current_qc_data = self.gflFactoryConfig.client_stats.get_data()
        for client_name in current_qc_data:
            client_qc_data = current_qc_data[client_name]
            if client_name not in self.gflFactoryConfig.client_internals:
                self.log.warning("Client '%s' has stats, but no classad! Ignoring." % client_name)
                continue
            client_internals = self.gflFactoryConfig.client_internals[client_name]
            client_monitors = {}
            for w in client_qc_data:
                for a in client_qc_data[w]:
                    # report only numbers
                    if isinstance(client_qc_data[w][a], int):
                        client_monitors[f"{w}{a}"] = client_qc_data[w][a]
            merged_monitors = glidein_monitors.copy()
            merged_monitors.update(client_monitors)

            try:
                fparams = current_qc_data[client_name]["Requested"]["Parameters"]
            except KeyError:
                fparams = {}
            params = self.jobParams.data.copy()
            for p in list(fparams.keys()):
                # Can only overwrite existing params, not create new ones
                if p in list(params.keys()):
                    params[p] = fparams[p]

            advertizer.add(
                client_internals["CompleteName"],
                client_name,
                client_internals["ReqName"],
                params,
                merged_monitors,
                self.limits_triggered,
            )

        try:
            advertizer.writeToMultiClassadFile(gfc_filename)
        except Exception:
            self.log.warning("Writing monitoring classad to file %s failed" % gfc_filename)

        return

    def advertise(self, downtime_flag):
        """Advertise the glidefactory and glidefactoryclient classads.

        Args:
            downtime_flag (bool): Flag indicating whether the Factory is in downtime or not.
        """
        self.loadContext()

        # Classad files to use
        gf_filename = classadSupport.generate_classad_filename(prefix="gfi_adm_gf")
        gfc_filename = classadSupport.generate_classad_filename(prefix="gfi_adm_gfc")
        self.writeClassadsToFile(downtime_flag, gf_filename, gfc_filename)

        # ADVERTISE: glidefactory classads
        gfi.advertizeGlideinFromFile(gf_filename, remove_file=True, is_multi=True)

        # ADVERTISE: glidefactoryclient classads
        gfi.advertizeGlideinClientMonitoringFromFile(gfc_filename, remove_file=True, is_multi=True)
        return

    def writeStats(self):
        """Write statistics for the current iteration.

        Computes and writes log statistics, qc statistics, and rrd statistics:
        - log stats: That come from parsing the condor_activity
          and job logs.  This is computed every iteration
          (in perform_work()) and diff-ed to see any newly
          changed job statuses (i.e. newly completed jobs)
        - qc stats: From condor_q data.
        - rrd stats: Used in monitoring statistics for javascript rrd graphs.
        """
        # Not found anywhere:  global log_rrd_thread, qc_rrd_thread

        self.loadContext()

        self.log.info("Computing log_stats diff for %s" % self.name)
        self.gflFactoryConfig.log_stats.computeDiff()
        self.log.info("log_stats diff computed")

        self.log.info("Writing log_stats for %s" % self.name)
        self.gflFactoryConfig.log_stats.write_file(monitoringConfig=self.monitoringConfig)
        self.log.info("log_stats written")

        self.log.info("Writing glidein job info for %s" % self.name)
        self.gflFactoryConfig.log_stats.write_job_info(
            scheddName=self.scheddName, collectorName=self.gfiFactoryConfig.factory_collector
        )
        self.log.info("glidein job info written")

        self.gflFactoryConfig.qc_stats.finalizeClientMonitor()
        self.log.info("Writing qc_stats for %s" % self.name)
        self.gflFactoryConfig.qc_stats.write_file(
            monitoringConfig=self.monitoringConfig, alt_stats=self.gflFactoryConfig.client_stats
        )
        self.log.info("qc_stats written")

        self.log.info("Writing rrd_stats for %s" % self.name)
        self.gflFactoryConfig.rrd_stats.writeFiles(monitoringConfig=self.monitoringConfig)
        self.log.info("rrd_stats written")

        return

    def getLogStatsOldStatsData(self):
        """Get the old log statistics data.

        Returns the gflFactoryConfig.log_stats.old_stats_data that can be pickled

        Returns:
            glideFactoryMonitoring.condorLogSummary: The log statistics data from the previous iteration.
        """
        return self.getLogStatsData(self.gflFactoryConfig.log_stats.old_stats_data)

    def getLogStatsCurrentStatsData(self):
        """Get the current log statistics data.

        Returns the gflFactoryConfig.log_stats.current_stats_data that can be pickled

        Returns:
            glideFactoryMonitoring.condorLogSummary: The current log statistics data.
        """
        return self.getLogStatsData(self.gflFactoryConfig.log_stats.current_stats_data)

    def getLogStatsData(self, stats_data):
        """Retrieve normalized log statistics data, ``stats_data[frontend][user].data``, for pickling.

        Args:
            stats_data (dict): Dictionary of statistics data keyed by Frontend and user.

        Returns:
            dict: Normalized log statistics data.
        """
        return_dict = {}

        for frontend in stats_data:
            return_dict[frontend] = {}
            for user in stats_data[frontend]:
                return_dict[frontend][user] = stats_data[frontend][user].data
        return return_dict

    def setLogStatsOldStatsData(self, new_data):
        """Set the old log statistics data from pickled information.

        Args:
            new_data (glideFactoryMonitoring.condorLogSummary): The pickled statistics data.
        """
        self.setLogStatsData(self.gflFactoryConfig.log_stats.old_stats_data, new_data)

    def setLogStatsCurrentStatsData(self, new_data):
        """Set the current log statistics data (gflFactoryConfig.log_stats.current_stats_data) from pickled information.

        Args:
            new_data (glideFactoryMonitoring.condorLogSummary): The pickled statistics data to use.
        """
        self.setLogStatsData(self.gflFactoryConfig.log_stats.current_stats_data, new_data)

    def setLogStatsData(self, stats_data, new_data):
        """Set log statistics data, ``stats_data[frontend][user].data``, from pickled information.

        Args:
            stats_data (dict): The existing statistics data.
            new_data (dict): The new statistics data from the pickled object.
        """
        for frontend in new_data:
            stats_data[frontend] = {}
            for user in new_data[frontend]:
                x509_proxy_username = (user.split(":"))[0]
                client_int_name = (user.split(":"))[1]
                client_log_dir = self.gflFactoryConfig.get_client_log_dir(self.name, x509_proxy_username)
                stats = glideFactoryLogParser.dirSummaryTimingsOut(
                    client_log_dir, self.logDir, client_int_name, x509_proxy_username
                )
                stats.load()
                stats_data[frontend][user] = stats.get_simple()
                stats_data[frontend][user].data = new_data

    def getState(self):
        """Compile state information for this entry.

        Returns:
            dict: A dictionary containing state information (e.g., client internals, totals, limits, statistics)
                  that can be pickled and later restored.
        """
        # Set logger to None else we can't pickle file objects
        self.gflFactoryConfig.client_stats.log = None
        self.gflFactoryConfig.qc_stats.log = None
        self.gflFactoryConfig.rrd_stats.log = None
        self.gflFactoryConfig.log_stats.log = None

        state = {
            "client_internals": self.gflFactoryConfig.client_internals,
            "glidein_totals": self.glideinTotals,
            "limits_triggered": self.limits_triggered,
            "client_stats": self.gflFactoryConfig.client_stats,
            "qc_stats": self.gflFactoryConfig.qc_stats,
            "rrd_stats": self.gflFactoryConfig.rrd_stats,
            "log_stats": self.gflFactoryConfig.log_stats,
        }
        return state

    def setState(self, state):
        """Load the post work state from pickled information.

        Args:
            state (dict): The pickled state after work has been performed.
        """
        self.gflFactoryConfig.client_stats = state.get("client_stats")
        if self.gflFactoryConfig.client_stats:
            self.gflFactoryConfig.client_stats.log = self.log

        self.gflFactoryConfig.qc_stats = state.get("qc_stats")
        if self.gflFactoryConfig.qc_stats:
            self.gflFactoryConfig.qc_stats.log = self.log

        self.gflFactoryConfig.rrd_stats = state.get("rrd_stats")
        if self.gflFactoryConfig.rrd_stats:
            self.gflFactoryConfig.rrd_stats.log = self.log

        self.gflFactoryConfig.client_internals = state.get("client_internals")

        self.glideinTotals = state.get("glidein_totals")
        self.limits_triggered = state.get("limits_triggered")

        self.gflFactoryConfig.log_stats = state["log_stats"]
        if self.gflFactoryConfig.log_stats:
            self.gflFactoryConfig.log_stats.log = self.log

        # Load info for latest log_stats correctly
        """
        self.gflFactoryConfig.log_stats.data = state['log_stats']['data']
        self.gflFactoryConfig.log_stats.updated = state['log_stats']['updated']
        self.gflFactoryConfig.log_stats.updated_year = state['log_stats']['updated_year']
        self.gflFactoryConfig.log_stats.stats_diff = state['log_stats']['stats_diff']
        self.gflFactoryConfig.log_stats.files_updated = state['log_stats']['files_updated']
        self.setLogStatsCurrentStatsData(state['log_stats']['current_stats_data'])
        self.setLogStatsOldStatsData(state['log_stats']['old_stats_data'])
        """

    #####################
    # Debugging functions
    #####################
    def logLogStats(self, marker=""):
        """Log detailed statistics for debugging.

        Args:
            marker (str, optional): A marker string to prefix the debug logs. Defaults to an empty string.
        """
        self.log.debug(marker)
        self.log.debug("data = %s" % self.gflFactoryConfig.log_stats.data)
        self.log.debug("updated = %s" % self.gflFactoryConfig.log_stats.updated)
        self.log.debug("updated_year = %s" % self.gflFactoryConfig.log_stats.updated_year)
        self.log.debug("stats_diff = %s" % self.gflFactoryConfig.log_stats.stats_diff)
        self.log.debug("files_updated = %s" % self.gflFactoryConfig.log_stats.files_updated)
        self.log.debug("old_stats_data = %s" % self.gflFactoryConfig.log_stats.old_stats_data)
        self.log.debug("current_stats_data = %s" % self.gflFactoryConfig.log_stats.current_stats_data)
        self.log.debug(marker)


###############################################################################
# Functions to serve work requests (invoked from glideFactoryEntryGroup)
###############################################################################


def check_and_perform_work(factory_in_downtime, entry, work):
    """Check and perform work requests for the entry.

    This function checks if work needs to be done for the entry and processes each work request
    using the v3 protocol. It updates credentials, checks downtimes and whitelisting, and submits work.
    It is called by a child process per entry.

    Args:
        factory_in_downtime (bool): True if the factory is in downtime.
        entry (Entry): The Entry object.
        work (dict): A dictionary of work requests for the entry.

    Returns:
        int: The total work done (e.g., the number of glideins submitted).
    """
    entry.loadContext()

    # Query glidein queue
    try:
        condorQ = entry.queryQueuedGlideins()
    except Exception:
        # Protect and exit
        entry.log.debug("Failed condor_q for entry %s, skipping stats update and work" % entry.name)
        return 0

    # Consider downtimes and see if we can submit glideins
    all_security_names = set()
    done_something = 0
    entry.loadWhitelist()
    entry.loadDowntimes()
    # Variable to identify if frontend or sec_class is in downtime
    in_downtime = factory_in_downtime
    auth_method = entry.jobDescript.data["AuthMethod"]

    #
    # STEP: Process every work one at a time. This is done only for entries with work to do
    #
    for work_key in work:
        if not glideFactoryLib.is_str_safe(work_key):
            # may be used to write files... make sure it is reasonable
            entry.log.warning("Request name '%s' not safe. Skipping request" % work_key)
            continue

        # merge work and default params
        params = work[work_key]["params"]
        decrypted_params = {key: value.decode() for key, value in work[work_key]["params_decrypted"].items()}

        # add default values if not defined
        for k in entry.jobParams.data:
            if k not in params:
                params[k] = entry.jobParams.data[k]

        # Set client name (i.e. frontend.group) &
        # request name (i.e. entry@glidein@factory)
        try:
            client_int_name = work[work_key]["internals"]["ClientName"]
            client_int_req = work[work_key]["internals"]["ReqName"]
        except KeyError:
            entry.log.warning("Request %s did not provide the client and/or request name. Skipping request" % work_key)
            continue

        if not glideFactoryLib.is_str_safe(client_int_name):
            # may be used to write files... make sure it is reasonable
            entry.log.warning("Client name '%s' not safe. Skipping request" % client_int_name)
            continue

        # Retrieve client_security_name, used in logging and to check entry's whitelist
        client_security_name = decrypted_params.get("SecurityName")
        if client_security_name is None:
            entry.log.warning("Client %s did not provide the security name, skipping request" % client_int_name)
            continue

        # Skipping requests using v2 protocol - No more supported
        if "x509_proxy_0" in decrypted_params:
            entry.log.warning(
                "Request from client %s (secid: %s) using unsupported protocol v2 (x509_proxy_0 in message). "
                "Skipping." % (client_int_name, client_security_name)
            )
            continue

        #
        # STEP: DOWNTIME AND FRONTEND/SECURITY_CLASS WHITELISTING CALCULATION
        #

        # Check request has the required credentials and nothing else
        scitoken_passthru = params.get("CONTINUE_IF_NO_PROXY") == "True"
        try:
            entry.log.debug("Checking security credentials for client %s " % client_int_name)
            glideFactoryCredentials.check_security_credentials(
                auth_method, decrypted_params, client_int_name, entry.name, scitoken_passthru
            )
        except glideFactoryCredentials.CredentialError:
            entry.log.exception("Error checking credentials, skipping request: ")
            continue

        # Check whether the frontend is in the whitelist of the entry
        if entry.isClientBlacklisted(client_security_name):
            entry.log.warning(
                "Client name '%s' not in whitelist. Preventing glideins from %s "
                % (client_security_name, client_int_name)
            )
            in_downtime = True

        client_expected_identity = entry.frontendDescript.get_identity(client_security_name)
        if client_expected_identity is None:
            entry.log.warning(
                f"Client {client_int_name} (secid: {client_security_name}) not in white list. Skipping request"
            )
            continue

        client_authenticated_identity = work[work_key]["internals"]["AuthenticatedIdentity"]
        if client_authenticated_identity != client_expected_identity:
            entry.log.warning(
                "Client %s (secid: %s) is not coming from a trusted source; AuthenticatedIdentity %s!=%s. "
                "Skipping for security reasons."
                % (client_int_name, client_security_name, client_authenticated_identity, client_expected_identity)
            )
            continue

        entry.gflFactoryConfig.client_internals[client_int_name] = {
            "CompleteName": f"{client_int_req}@{client_int_name}",
            "CompleteNameWithCredentialsId": work_key,
            "ReqName": client_int_req,
        }

        #
        # STEP: Actually process the unit work using v3 protocol
        #
        work_performed = unit_work_v3(
            entry,
            work[work_key],
            work_key,
            client_int_name,
            client_int_req,
            client_expected_identity,
            decrypted_params,
            params,
            in_downtime,
            condorQ,
        )

        if not work_performed["success"]:
            # There was error processing this unit work request.
            # Ignore this work request and continue to next one.
            continue

        done_something += work_performed["work_done"]
        all_security_names = all_security_names.union(work_performed["security_names"])

    # sanitize glideins (if there was no work done, otherwise it is done in glidein submission)
    if done_something == 0:
        entry.log.info("Sanitizing glideins for entry %s" % entry.name)
        glideFactoryLib.sanitizeGlideins(condorQ, log=entry.log, factoryConfig=entry.gflFactoryConfig)
        glideFactoryLib.sanitizeGlideins(condorQ, log=entry.log)

    # This is the only place where rrd_stats.getData(), updating RRD as side effect, is called for clients;
    # totals are updated also elsewhere
    # i.e. RRD stats and the content of XML files are not updated for clients w/o work requests
    # TODO: #22163, should this change and rrd_stats.getData() be called for all clients anyway?
    #  if yes, How to get security names tuples (client_security_name, credential_security_class)? - mmb
    # entry.log.debug("Processed work requests: all_security_names = %s" % all_security_names)
    for sec_el in all_security_names:
        try:
            # returned data is not used, function called only to trigger RRD update via side effect
            entry.gflFactoryConfig.rrd_stats.getData("%s_%s" % sec_el, monitoringConfig=entry.monitoringConfig)
        except glideFactoryLib.condorExe.ExeError:
            # Never fail for monitoring. Just log
            entry.log.exception("get_RRD_data failed with HTCondor error: ")
        except Exception:
            # Never fail for monitoring. Just log
            entry.log.exception("get_RRD_data failed with unknown error: ")

    return done_something


###############################################################################
def unit_work_v3(
    entry,
    work,
    client_name,
    client_int_name,
    client_int_req,
    client_expected_identity,
    decrypted_params,
    params,
    in_downtime,
    condorQ,
):
    """Perform a single work unit using the v3 protocol.

    Args:
        entry (Entry): The entry object.
        work (dict): The work request data.
        client_name (str): The client name (work key).
        client_int_name (str): The internal client name. Client name declared in the request.
        client_int_req (str): The request name, as declared in the request.
        client_expected_identity (str): The expected identity of the client.
        decrypted_params (dict): Decrypted parameters from the frontend request.
        params (dict): Original parameters from the frontend request.
        in_downtime (bool): True if the system is in downtime.
        condorQ (condorMonitor.CondorQ): The CondorQ object with job information.
            List of HTCondor jobs for this entry as returned by entry.queryQueuedGlideins().

    Returns:
        dict: A dictionary with keys:
            - "success" (bool): True if work was performed successfully.
            - "security_names" (set): A set of security name tuples processed.
            - "work_done" (int): The number of units of work performed.
    """
    # Return dictionary. Only populate information to be passed at the end
    # just before returning.
    return_dict = {
        "success": False,
        "security_names": None,
        "work_done": None,
    }

    #
    # STEP: CHECK THAT GLIDEINS ARE WITHIN ALLOWED LIMITS
    #
    can_submit_glideins = entry.glideinsWithinLimits(condorQ)

    # TODO REV: check if auth_method is a string or list.
    #  If string split at + and make list and use list below (in), otherwise there could be partial string matches
    auth_method = entry.jobDescript.data["AuthMethod"]
    grid_type = entry.jobDescript.data["GridType"]
    all_security_names = set()

    # Get credential security class
    credential_security_class = decrypted_params.get("SecurityClass")
    client_security_name = decrypted_params.get("SecurityName")

    if not credential_security_class:
        entry.log.warning("Client %s did not provide a security class. Skipping bad request." % client_int_name)
        return return_dict

    # Check security class for downtime (in downtimes file)
    entry.log.info(
        "Checking downtime for frontend %s security class: %s (entry %s)."
        % (client_security_name, credential_security_class, entry.name)
    )

    if entry.isSecurityClassInDowntime(client_security_name, credential_security_class):
        # Cannot use proxy for submission but entry is not in downtime
        # since other proxies may map to valid security classes
        entry.log.warning(
            "Security class %s is currently in a downtime window for entry: %s. Ignoring request."
            % (credential_security_class, entry.name)
        )
        # this below change is based on redmine ticket 3110.
        # even though we do not return here, setting in_downtime=True (for entry downtime)
        # will make sure no new glideins will be submitted in the same way that
        # the code does for the factory downtime
        in_downtime = True
    #        return return_dict

    # Deny Frontend from requesting glideins if the whitelist
    # does not have its security class (or "All" for everyone)
    if entry.isClientWhitelisted(client_security_name):
        if entry.isSecurityClassAllowed(client_security_name, credential_security_class):
            entry.log.info(f"Security test passed for : {entry.name} {credential_security_class} ")
        else:
            entry.log.warning(
                "Security class not in whitelist, skipping request (%s %s)."
                % (client_security_name, credential_security_class)
            )
            return return_dict

    # Check that security class maps to a username for submission
    # The username is still used also in single user factory (for log dirs, ...)
    credential_username = entry.frontendDescript.get_username(client_security_name, credential_security_class)
    if credential_username is None:
        entry.log.warning(
            "No username mapping for security class %s of credential for %s (secid: %s), skipping request."
            % (credential_security_class, client_int_name, client_security_name)
        )
        return return_dict

    # Initialize submit credential object & determine the credential location
    submit_credentials = glideFactoryCredentials.SubmitCredentials(credential_username, credential_security_class)
    submit_credentials.cred_dir = entry.gflFactoryConfig.get_client_proxies_dir(credential_username)

    condortoken = f"{entry.name}.idtoken"
    condortokenbase = f"credential_{client_int_name}_{entry.name}.idtoken"
    condortoken_file = os.path.join(submit_credentials.cred_dir, condortokenbase)
    condortoken_data = decrypted_params.get(condortoken)
    if condortoken_data:
        (fd, tmpnm) = tempfile.mkstemp(dir=submit_credentials.cred_dir)
        try:
            entry.log.info(f"frontend_token supplied, writing to {condortoken_file}")
            chmod(tmpnm, 0o600)
            os.write(fd, condortoken_data.encode("utf-8"))
            os.close(fd)
            util.file_tmp2final(condortoken_file, tmpnm)

        except Exception as err:
            entry.log.exception(f"failed to create token: {err}")
            for i in sys.exc_info():
                entry.log.exception("%s" % i)
        finally:
            if os.path.exists(tmpnm):
                os.remove(tmpnm)
    if os.path.exists(condortoken_file):
        if not submit_credentials.add_identity_credential("frontend_condortoken", condortoken_file):
            entry.log.warning(
                "failed to add frontend_condortoken %s to the identity credentials %s"
                % (condortoken_file, str(submit_credentials.identity_credentials))
            )

    scitoken_passthru = params.get("CONTINUE_IF_NO_PROXY") == "True"
    scitoken = f"credential_{client_int_name}_{entry.name}.scitoken"
    scitoken_file = os.path.join(submit_credentials.cred_dir, scitoken)
    scitoken_data = decrypted_params.get("frontend_scitoken")
    if scitoken_data:
        if token_util.token_str_expired(scitoken_data):
            entry.log.warning(f"Continuing, but the frontend_scitoken supplied is expired: {scitoken_file}")
        tmpnm = ""
        try:
            entry.log.info(f"frontend_scitoken supplied, writing to {scitoken_file}")
            (fd, tmpnm) = tempfile.mkstemp(dir=submit_credentials.cred_dir)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"{scitoken_data.strip()}\n")
            chmod(tmpnm, 0o600)
            util.file_tmp2final(scitoken_file, tmpnm)
        except Exception as err:
            entry.log.exception(f"failed to create scitoken: {err}")
        finally:
            if os.path.exists(tmpnm):
                os.remove(tmpnm)

    if os.path.exists(scitoken_file):
        # TODO: why identity_credential and not submit_credential? Consider moving when refactoring
        if not submit_credentials.add_identity_credential("frontend_scitoken", scitoken_file):
            entry.log.warning(
                "failed to add frontend_scitoken %s to identity credentials %s"
                % (scitoken_file, str(submit_credentials.identity_credentials))
            )

    # Check if project id is required
    if "project_id" in auth_method:
        if "ProjectId" in decrypted_params:
            submit_credentials.add_identity_credential("ProjectId", decrypted_params["ProjectId"])
        else:
            # ProjectId is required, cannot service request
            entry.log.warning(
                "Client '%s' did not specify a Project Id in the request, this is required by entry %s, skipping request."
                % (client_int_name, entry.name)
            )
            return return_dict

    if "scitoken" in auth_method:
        if os.path.exists(scitoken_file):
            if token_util.token_file_expired(scitoken_file):
                entry.log.warning(f"Found frontend_scitoken '{scitoken_file}', but is expired. Continuing")
            if "ScitokenId" in decrypted_params:
                scitoken_id = decrypted_params.get("ScitokenId")
                submit_credentials.id = scitoken_id
            else:
                entry.log.warning(
                    "SciToken present but ScitokenId not found, "
                    f"continuing but monitoring will be incorrect for client {client_int_name}."
                )
        else:
            entry.log.warning(f"auth method is scitoken, but file '{scitoken_file}' not found. skipping request")
            return return_dict

    elif "grid_proxy" in auth_method:
        ########################
        # ENTRY TYPE: Grid Sites
        ########################

        # Check if voms_attr required
        if "voms_attr" in auth_method:
            # TODO: PM: determine how to verify voms attribute on a proxy
            pass

        # Determine identifier for file name and add to
        # credentials to be passed to submit
        proxy_id = decrypted_params.get("SubmitProxy")

        if not submit_credentials.add_security_credential("SubmitProxy", f"{client_int_name}_{proxy_id}"):
            if not scitoken_passthru:
                entry.log.warning(
                    "Credential %s for the submit proxy cannot be found for client %s, skipping request."
                    % (proxy_id, client_int_name)
                )
                return return_dict
            else:
                # Using token, set appropriate credential ID
                if "ScitokenId" in decrypted_params:
                    proxy_id = decrypted_params.get("ScitokenId")
                else:
                    entry.log.warning(
                        "SciToken present but ScitokenId not found, continuing but monitoring will be incorrect for client %s."
                        % client_int_name
                    )

        # Set the id used for tracking what is in the factory queue
        submit_credentials.id = proxy_id

    else:
        ###################################
        # ENTRY TYPE: Other than grid sites
        # - Cloud Sites
        # - BOSCO
        ###################################

        # Verify that the glidein proxy was provided. We still need it as it
        # is used to by the glidein's condor daemons to authenticate with the
        # user collector
        proxy_id = decrypted_params.get("GlideinProxy")

        if proxy_id:
            if grid_type in ("ec2", "gce"):
                credential_name = f"{client_int_name}_{proxy_id}_compressed"
                if condortoken_data:
                    # create an idtoken file that process_global can find and add to compressed credential
                    _fname_idtoken = f"credential_{client_int_name}_{proxy_id}_idtoken"
                    credential_idtoken_fname = os.path.join(submit_credentials.cred_dir, _fname_idtoken)
                    glideFactoryCredentials.safe_update(
                        credential_idtoken_fname, defaults.force_bytes(condortoken_data)
                    )
            else:
                # BOSCO is using regular proxy, not compressed
                credential_name = f"{client_int_name}_{proxy_id}"
            if not submit_credentials.add_security_credential("GlideinProxy", credential_name):
                if grid_type in ("ec2", "gce"):
                    # dont necessarily need these for ec2,gce, can use idtoken
                    pass
                else:
                    entry.log.warning(
                        "Credential %s for the glidein proxy cannot be found for client %s, skipping request."
                        % (proxy_id, client_int_name)
                    )
                    return return_dict
        else:
            entry.log.warning("Glidein proxy cannot be found for client %s, skipping request" % client_int_name)
            return return_dict

        # VM id and type are required for cloud sites.
        # Either frontend or factory should provide it
        vm_id = None
        vm_type = None
        remote_username = None

        if grid_type in ("ec2", "gce"):
            # vm_id and vm_type are only applicable to Clouds

            if "vm_id" in auth_method:
                # First check if the Frontend supplied it
                vm_id = decrypted_params.get("VMId")
                if not vm_id:
                    entry.log.warning(
                        "Client '%s' did not specify a VM Id in the request, this is required by entry %s, skipping request. "
                        % (client_int_name, entry.name)
                    )
                    return return_dict
            else:
                # Validate factory provided vm id exists
                if "EntryVMId" in entry.jobDescript.data:
                    vm_id = entry.jobDescript.data["EntryVMId"]
                else:
                    entry.log.warning(
                        "Entry does not specify a VM Id, this is required by entry %s, skipping request." % entry.name
                    )
                    return return_dict

            if "vm_type" in auth_method:
                # First check if the Frontend supplied it
                vm_type = decrypted_params.get("VMType")
                if not vm_type:
                    entry.log.warning(
                        "Client '%s' did not specify a VM Type in the request, this is required by entry %s, skipping request."
                        % (client_int_name, entry.name)
                    )
                    return return_dict
            else:
                # Validate factory provided vm type exists
                if "EntryVMType" in entry.jobDescript.data:
                    vm_type = entry.jobDescript.data["EntryVMType"]
                else:
                    entry.log.warning(
                        f"Entry does not specify a VM Type, this is required by entry {entry.name}, skipping request."
                    )
                    return return_dict

        submit_credentials.add_identity_credential("VMId", vm_id)
        submit_credentials.add_identity_credential("VMType", vm_type)

        if "cert_pair" in auth_method:
            public_cert_id = decrypted_params.get("PublicCert")
            submit_credentials.id = public_cert_id
            if public_cert_id and not submit_credentials.add_security_credential(
                "PublicCert", f"{client_int_name}_{public_cert_id}"
            ):
                entry.log.warning(
                    "Credential %s for the public certificate is not safe for client %s, skipping request."
                    % (public_cert_id, client_int_name)
                )
                return return_dict

            private_cert_id = decrypted_params.get("PrivateCert")
            if private_cert_id and submit_credentials.add_security_credential(
                "PrivateCert", f"{client_int_name}_{private_cert_id}"
            ):
                entry.log.warning(
                    "Credential %s for the private certificate is not safe for client %s, skipping request"
                    % (private_cert_id, client_int_name)
                )
                return return_dict

        elif "key_pair" in auth_method:
            # Used by AWS & BOSCO so handle accordingly
            public_key_id = decrypted_params.get("PublicKey")
            submit_credentials.id = public_key_id
            if public_key_id and not submit_credentials.add_security_credential(
                "PublicKey", f"{client_int_name}_{public_key_id}"
            ):
                entry.log.warning(
                    "Credential %s for the public key is not safe for client %s, skipping request"
                    % (public_key_id, client_int_name)
                )
                return return_dict

            if grid_type == "ec2":
                # AWS usecase. Added empty if block for clarity
                pass
            else:
                # BOSCO Use case
                # Entry Gatekeeper is [<user_name>@]hostname[:port]
                # PublicKey can have RemoteUsername
                # Can we just put this else block with if grid_type.startswith('batch '):
                # and remove if clause? Check with Marco Mambelli
                remote_username = decrypted_params.get("RemoteUsername")
                if not remote_username:
                    if "username" in auth_method:
                        entry.log.warning(
                            f"Client '{client_int_name}' did not specify a remote username in the request, "
                            f"this is required by entry {entry.name}, skipping request."
                        )
                        return return_dict
                    # default remote_username from entry (if present)
                    gatekeeper_list = entry.jobDescript.data["Gatekeeper"].split("@")
                    if len(gatekeeper_list) == 2:
                        remote_username = gatekeeper_list[0].strip()
                    else:
                        entry.log.warning(
                            "Client '%s' did not specify a Username in Key %s and the entry %s does not provide a default username in the gatekeeper string, skipping request"
                            % (client_int_name, public_key_id, entry.name)
                        )
                        return return_dict

            private_key_id = decrypted_params.get("PrivateKey")
            if private_key_id and not submit_credentials.add_security_credential(
                "PrivateKey", f"{client_int_name}_{private_key_id}"
            ):
                entry.log.warning(
                    "Credential %s for the private key is not safe for client %s, skipping request"
                    % (private_key_id, client_int_name)
                )
                return return_dict

        elif "auth_file" in auth_method:
            auth_file_id = decrypted_params.get("AuthFile")
            submit_credentials.id = auth_file_id
            if auth_file_id and not submit_credentials.add_security_credential(
                "AuthFile", f"{client_int_name}_{auth_file_id}"
            ):
                entry.log.warning(
                    "Credential %s for the auth file is not safe for client %s, skipping request"
                    % (auth_file_id, client_int_name)
                )
                return return_dict

        elif "username_password" in auth_method:
            username_id = decrypted_params.get("Username")
            submit_credentials.id = username_id
            if username_id and not submit_credentials.add_security_credential(
                "Username", f"{client_int_name}_{username_id}"
            ):
                entry.log.warning(
                    "Credential %s for the username is not safe for client %s, skipping request"
                    % (username_id, client_int_name)
                )
                return return_dict

            password_id = decrypted_params.get("Password")
            if password_id and not submit_credentials.add_security_credential(
                "Password", f"{client_int_name}_{password_id}"
            ):
                entry.log.warning(
                    "Credential %s for the password is not safe for client %s, skipping request"
                    % (password_id, client_int_name)
                )
                return return_dict

        else:
            logSupport.log.warning(
                "Factory entry %s has invalid authentication method. Skipping request for client %s."
                % (entry.name, client_int_name)
            )
            return return_dict

        submit_credentials.add_identity_credential("RemoteUsername", remote_username)
        if submit_credentials.id is None:
            entry.log.warning(
                "Credentials for entry %s and client %s have no ID, continuing but monitoring will be incorrect."
                % (entry.name, client_int_name)
            )

    # Set the downtime status so the frontend-specific
    # downtime is advertised in glidefactoryclient ads
    entry.setDowntime(in_downtime)
    entry.gflFactoryConfig.qc_stats.set_downtime(in_downtime)

    #
    # STEP: CHECK IF CLEANUP OF IDLE GLIDEINS IS REQUIRED
    #

    remove_excess = (
        work["requests"].get("RemoveExcess", "NO"),
        work["requests"].get("RemoveExcessMargin", 0),
        work["requests"].get("IdleGlideins", 0),
    )
    idle_lifetime = work["requests"].get("IdleLifetime", 0)

    if "IdleGlideins" not in work["requests"]:
        # Malformed, if no IdleGlideins
        entry.log.warning("Skipping malformed classad for client %s" % client_name)
        return return_dict

    try:
        idle_glideins = int(work["requests"]["IdleGlideins"])
    except ValueError:
        entry.log.warning(
            "Client %s provided an invalid ReqIdleGlideins: '%s' not a number. Skipping request"
            % (client_int_name, work["requests"]["IdleGlideins"])
        )
        return return_dict
    req_idle_glideins = (
        idle_glideins  # to distinguish between frontend request and factory's calculated value for idle glideins
    )
    # from here on, idle_glideins represents the factory-adjusted (enforcing entry limits if any) number of idle glideins and req_idle_glideins represents the original request coming from the frontend

    if "MaxGlideins" in work["requests"]:
        try:
            max_glideins = int(work["requests"]["MaxGlideins"])
        except ValueError:
            entry.log.warning(
                "Client %s provided an invalid ReqMaxGlideins: '%s' not a number. Skipping request."
                % (client_int_name, work["requests"]["MaxGlideins"])
            )
            return return_dict
    else:
        try:
            max_glideins = int(work["requests"]["MaxRunningGlideins"])
        except ValueError:
            entry.log.warning(
                "Client %s provided an invalid ReqMaxRunningGlideins: '%s' not a number. Skipping request"
                % (client_int_name, work["requests"]["MaxRunningGlideins"])
            )
            return return_dict

    # If we got this far, it was because we were able to
    # successfully update all the credentials in the request
    # If we already have hit our limits checked at beginning of this
    # method and logged there, we can't submit.
    # We still need to check/update all the other request credentials
    # and do cleanup.

    # We'll set idle glideins to zero if hit max or in downtime.
    if in_downtime or not can_submit_glideins:
        idle_glideins = 0

    try:
        client_web_url = work["web"]["URL"]
        client_signtype = work["web"]["SignType"]
        client_descript = work["web"]["DescriptFile"]
        client_sign = work["web"]["DescriptSign"]
        client_group = work["internals"]["GroupName"]
        client_group_web_url = work["web"]["GroupURL"]
        client_group_descript = work["web"]["GroupDescriptFile"]
        client_group_sign = work["web"]["GroupDescriptSign"]

        client_web = glideFactoryLib.ClientWeb(
            client_web_url,
            client_signtype,
            client_descript,
            client_sign,
            client_group,
            client_group_web_url,
            client_group_descript,
            client_group_sign,
        )
    except Exception:
        # malformed classad, skip
        entry.log.warning("Malformed classad for client %s, missing web parameters, skipping request." % client_name)
        return return_dict

    # Should log here or in perform_work
    glideFactoryLib.logWorkRequest(
        client_int_name,
        client_security_name,
        submit_credentials.security_class,
        req_idle_glideins,
        idle_glideins,
        max_glideins,
        remove_excess,
        work,
        log=entry.log,
        factoryConfig=entry.gflFactoryConfig,
    )

    all_security_names.add((client_security_name, credential_security_class))

    # Iv v2 this was:
    # entry_condorQ = glideFactoryLib.getQProxSecClass(
    #                    condorQ, client_int_name,
    #                    submit_credentials.security_class,
    #                    client_schedd_attribute=entry.gflFactoryConfig.client_schedd_attribute,
    #                    credential_secclass_schedd_attribute=entry.gflFactoryConfig.credential_secclass_schedd_attribute,
    #                    factoryConfig=entry.gflFactoryConfig)

    # Sub-query selecting jobs in Factory schedd (still dictionary keyed by cluster, proc)
    # for (client_schedd_attribute, credential_secclass_schedd_attribute, credential_id_schedd_attribute)
    # ie (GlideinClient, GlideinSecurityClass, GlideinCredentialIdentifier)
    entry_condorQ = glideFactoryLib.getQCredentials(
        condorQ,
        client_int_name,
        submit_credentials,
        entry.gflFactoryConfig.client_schedd_attribute,
        entry.gflFactoryConfig.credential_secclass_schedd_attribute,
        entry.gflFactoryConfig.credential_id_schedd_attribute,
    )

    # Map the identity to a frontend:sec_class for tracking totals
    frontend_name = "{}:{}".format(
        entry.frontendDescript.get_frontend_name(client_expected_identity),
        credential_security_class,
    )

    # do one iteration for the credential set (maps to a single security class)
    # entry.gflFactoryConfig.client_internals[client_int_name] = \
    #    {"CompleteName":client_name, "ReqName":client_int_req}

    done_something = perform_work_v3(
        entry,
        entry_condorQ,
        client_name,
        client_int_name,
        client_security_name,
        submit_credentials,
        remove_excess,
        idle_glideins,
        max_glideins,
        idle_lifetime,
        credential_username,
        entry.glideinTotals,
        frontend_name,
        client_web,
        params,
    )

    # Gather the information to be returned back
    return_dict["success"] = True
    return_dict["work_done"] = done_something
    return_dict["security_names"] = all_security_names

    return return_dict


###############################################################################

# removed
# def unit_work_v2(entry, work, client_name, client_int_name, client_int_req,
#             client_expected_identity, decrypted_params, params,
#             in_downtime, condorQ):


###############################################################################


def perform_work_v3(
    entry,
    condorQ,
    client_name,
    client_int_name,
    client_security_name,
    submit_credentials,
    remove_excess,
    idle_glideins,
    max_glideins,
    idle_lifetime,
    credential_username,
    glidein_totals,
    frontend_name,
    client_web,
    params,
):
    """Perform work (Submit or remove Glideins).

    This function computes log statistics, logs work request information,
    and invokes glideFactoryLib.keepIdleGlideins to submit or remove Glideins.

    Args:
        entry (Entry): The entry object.
        condorQ (condorMonitor.CondorQ): The CondorQ object with job information.
            Information about the jobs in condor_schedd (entry values sub-query from glideFactoryLib.getQCredentials())
        client_name (str): The client name (work key).
        client_int_name (str): The internal client name.
        client_security_name (str): The client's security name.
        submit_credentials (SubmitCredentials): The submit credentials object.
        remove_excess (tuple): Tuple to control Glidein removal: remove_excess_str, remove_excess_margin
        idle_glideins (int): Number of idle glideins.
        max_glideins (int): Maximum number of glideins allowed.
        idle_lifetime: The idle lifetime of glideins.
        credential_username (str): Username associated with credentials.
        glidein_totals: The glideinTotals object.
        frontend_name (str): Frontend name for monitoring.
        client_web (ClientWeb): The client web information object.
        params (dict): Parameters from the request.

    Returns:
        int: The number of glideins submitted (returns 1 if any were submitted, 0 otherwise).
    """
    # find out the users it is using
    log_stats = {}
    log_stats[credential_username + ":" + client_int_name] = glideFactoryLogParser.dirSummaryTimingsOut(
        entry.gflFactoryConfig.get_client_log_dir(entry.name, credential_username),
        entry.logDir,
        client_int_name,
        credential_username,
    )

    try:  # the logParser class will throw an exception if the input file is bad
        log_stats[credential_username + ":" + client_int_name].load()
    except Exception as e:
        entry.log.exception(e)

    glideFactoryLib.logStats(
        condorQ,
        client_int_name,
        client_security_name,
        submit_credentials.security_class,
        log=entry.log,
        factoryConfig=entry.gflFactoryConfig,
    )

    client_log_name = glideFactoryLib.secClass2Name(client_security_name, submit_credentials.security_class)
    entry.gflFactoryConfig.log_stats.logSummary(client_log_name, log_stats)

    entry.log.info("Using v3+ protocol and credential %s" % submit_credentials.id)
    nr_submitted = glideFactoryLib.keepIdleGlideins(
        condorQ,
        client_int_name,
        idle_glideins,
        max_glideins,
        idle_lifetime,
        remove_excess,
        submit_credentials,
        glidein_totals,
        frontend_name,
        client_web,
        params,
        log=entry.log,
        factoryConfig=entry.gflFactoryConfig,
    )

    if nr_submitted > 0:
        entry.log.info("Submitted %s glideins" % nr_submitted)
        # We submitted something
        return 1

    return 0


####################


def update_entries_stats(factory_in_downtime, entry_list):
    """Update client statistics for entries with no work requests.

    For each entry in the list, queries the glidein queue, sanitizes glideins,
    and updates log statistics.

    TODO: #22163, skip update when in downtime?

    Note:
        `qc_stats` (the client queue information) cannot be updated because the
        Frontend certificate information are missing.

    Args:
        factory_in_downtime (bool): True if the factory is in downtime.
            Here for future needs (not used now)
        entry_list (list): List of Entry objects to update.

    Returns:
        list: A list of Entry objects that were updated (subset of entry_list).
    """
    updated_entries = []
    for entry in entry_list:
        # Add a heuristic to improve efficiency. Skip if no changes in the entry
        # if nothing_to_do:
        #    continue

        entry.loadContext()

        # Query glidein queue
        try:
            condorQ = entry.queryQueuedGlideins()
        except Exception:
            # Protect and exit
            logSupport.log.warning("Failed condor_q for entry %s, skipping stats update" % entry.name)
            continue

        if condorQ is None or len(condorQ.stored_data) == 0:
            # no glideins
            logSupport.log.debug("No glideins for entry %s, skipping stats update" % entry.name)
            continue

        # Sanitizing glideins, e.g. removing unrecoverable held glideins
        entry.log.info("Sanitizing glideins for entry w/o work %s" % entry.name)
        glideFactoryLib.sanitizeGlideins(condorQ, log=entry.log, factoryConfig=entry.gflFactoryConfig)

        # TODO: #22163, RRD stats for individual clients are not updated here. Are updated only when work is done,
        #  see check_and_perform_work. RRD for Entry Totals are still recalculated (from the partial RRD that
        #  were not updated) in the loop and XML files written.
        #  should this behavior change and rrd_stats.getData() be called for all clients anyway?
        #  should this behavior change and rrd_stats.getData() be called for all clients anyway?
        #  if yes, How to get security names?
        #  see check_and_perform_work above for more.
        #  These are questions to solve in #22163
        #  - mmb

        glideFactoryLib.logStatsAll(condorQ, log=entry.log, factoryConfig=entry.gflFactoryConfig)

        updated_entries.append(entry)

    return updated_entries


###############################################################################
# removed
# def perform_work_v2(entry, condorQ, client_name, client_int_name,
#                    client_security_name, credential_security_class,
#                    remove_excess, idle_glideins, max_running, idle_lifetime,
#                    credential_fnames, credential_username,
#                    identity_credentials, glidein_totals, frontend_name,
#                    client_web, params):


############################################################


# added by C.W. Murphy for glideFactoryEntryDescript
def write_descript(entry_name, entryDescript, entryAttributes, entryParams, monitor_dir):
    """Write the entry description XML file.

    Generates an XML description for the entry using the provided job description,
    attributes, and parameters, and writes the result to the specified monitor directory.

    Args:
        entry_name (str): Name of the entry.
        entryDescript: Entry job description object.
        entryAttributes: Entry job attributes object.
        entryParams: Entry job parameters object.
        monitor_dir (str): Directory to write the XML file.
    """
    entry_data = {entry_name: {}}
    entry_data[entry_name]["descript"] = copy.deepcopy(entryDescript.data)
    entry_data[entry_name]["attributes"] = copy.deepcopy(entryAttributes.data)
    entry_data[entry_name]["params"] = copy.deepcopy(entryParams.data)

    descript2XML = glideFactoryMonitoring.Descript2XML()
    str = descript2XML.entryDescript(entry_data)
    xml_str = ""
    for line in str.split("\n")[1:-2]:
        line = line[3:] + "\n"  # remove the extra tab
        xml_str += line

    try:
        descript2XML.writeFile(monitor_dir + "/", xml_str, singleEntry=True)
    except OSError:
        logSupport.log.debug("IOError in writeFile in descript2XML")

    return


############################################################
#
# S T A R T U P
#
############################################################


def termsignal(signr, frame):
    """Signal handler that raises KeyboardInterrupt.

    Args:
        signr (int): The signal number.
        frame: The current stack frame.
    """
    raise KeyboardInterrupt("Received signal %s" % signr)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, termsignal)
    signal.signal(signal.SIGQUIT, termsignal)
