#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Entry class
#

import signal
import os
import os.path
import sys
import fcntl
import traceback
import time
import string
import math
import copy
import random
import logging

sys.path.append(os.path.join(sys.path[0],"../../"))

from glideinwms.factory import glideFactoryPidLib
from glideinwms.factory import glideFactoryConfig
from glideinwms.factory import glideFactoryLib
from glideinwms.factory import glideFactoryMonitoring
from glideinwms.factory import glideFactoryInterface as gfi
from glideinwms.factory import glideFactoryLogParser
from glideinwms.factory import glideFactoryDowntimeLib
from glideinwms.factory import glideFactoryCredentials
from glideinwms.lib import logSupport
from glideinwms.lib import classadSupport
from glideinwms.lib import glideinWMSVersion
from glideinwms.lib import cleanupSupport


############################################################
class Entry:

    def __init__(self, name, startup_dir, glidein_descript, frontend_descript):
        """
        Class constructor

        @type name: string
        @param name: Name of the entry

        @type startup_dir: string
        @param startup_dir: Factory workspace

        @type glidein_descript: dict
        @param glidein_descript: Factory glidein config values

        @type frontend_descript: dict
        @param frontend_descript: Security mappings for frontend identities,
        security classes, and usernames for privsep
        """

        self.name = name
        self.startupDir = startup_dir
        self.glideinDescript = glidein_descript
        self.frontendDescript = frontend_descript

        self.jobDescript = glideFactoryConfig.JobDescript(name)
        self.jobAttributes = glideFactoryConfig.JobAttributes(name)
        self.jobParams = glideFactoryConfig.JobParams(name)

        # glideFactoryMonitoring.monitoringConfig.monitor_dir
        self.monitorDir = os.path.join(self.startupDir,
                                       "monitor/entry_%s" % self.name)

        # Dir where my logs are stored
        self.logDir = os.path.join(self.glideinDescript.data['LogDir'],
                                   "entry_%s" % self.name)

        # Schedd where my glideins will be submitted
        self.scheddName = self.jobDescript.data['Schedd']

        # glideFactoryLib.log_files
        process_logs = eval(self.glideinDescript.data['ProcessLogs'])
        for plog in process_logs:
            logSupport.add_processlog_handler(self.name, self.logDir,
                                              plog['msg_types'],
                                              plog['extension'],
                                              int(float(plog['max_days'])),
                                              int(float(plog['min_days'])),
                                              int(float(plog['max_mbytes'])),
                                              int(float(plog['backup_count'])))
        self.log = logging.getLogger(self.name)

        cleaner = cleanupSupport.PrivsepDirCleanupWSpace(
            None,
            self.logDir,
            "(condor_activity_.*\.log\..*\.ftstpk)",
            glideFactoryLib.days2sec(float(self.glideinDescript.data['CondorLogRetentionMaxDays'])),
            glideFactoryLib.days2sec(float(self.glideinDescript.data['CondorLogRetentionMinDays'])),
            float(self.glideinDescript.data['CondorLogRetentionMaxMBs']) * pow(2, 20))
        cleanupSupport.cleaners.add_cleaner(cleaner)

        self.monitoringConfig = glideFactoryMonitoring.MonitoringConfig(log=self.log)
        self.monitoringConfig.monitor_dir = self.monitorDir
        self.monitoringConfig.my_name = "%s@%s" % (name, self.glideinDescript.data['GlideinName'])

        self.monitoringConfig.config_log(
            self.logDir,
            float(self.glideinDescript.data['SummaryLogRetentionMaxDays']),
            float(self.glideinDescript.data['SummaryLogRetentionMinDays']),
            float(self.glideinDescript.data['SummaryLogRetentionMaxMBs']))

        # FactoryConfig object from glideFactoryInterface
        self.gfiFactoryConfig = gfi.FactoryConfig()
        #self.gfiFactoryConfig.warning_log = self.log.warning_log
        self.gfiFactoryConfig.advertise_use_tcp = (
            self.glideinDescript.data['AdvertiseWithTCP'] in ('True','1'))
        self.gfiFactoryConfig.advertise_use_multi = (
            self.glideinDescript.data['AdvertiseWithMultiple'] in ('True','1'))

        try:
            self.gfiFactoryConfig.glideinwms_version = glideinWMSVersion.GlideinWMSDistro(os.path.dirname(os.path.dirname(sys.argv[0])), 'checksum.factory').version()
        except:
            tb = traceback.format_exception(sys.exc_info()[0],
                                            sys.exc_info()[1],
                                            sys.exc_info()[2])
            self.log.warning("Exception occured while trying to retrieve the glideinwms version. See debug log for more details.")
            self.log.debug("Exception occurred while trying to retrieve the glideinwms version: %s" % tb)


        # FactoryConfig object from glideFactoryLib
        self.gflFactoryConfig = glideFactoryLib.FactoryConfig()

        self.gflFactoryConfig.config_whoamI(
            self.glideinDescript.data['FactoryName'],
            self.glideinDescript.data['GlideinName'])

        self.gflFactoryConfig.config_dirs(
            self.startupDir,
            self.glideinDescript.data['LogDir'],
            self.glideinDescript.data['ClientLogBaseDir'],
            self.glideinDescript.data['ClientProxiesBaseDir'])

        self.gflFactoryConfig.max_submits = int(self.jobDescript.data['MaxSubmitRate'])
        self.gflFactoryConfig.max_cluster_size = int(self.jobDescript.data['SubmitCluster'])
        self.gflFactoryConfig.slots_layout = self.jobDescript.data['SubmitSlotsLayout']
        self.gflFactoryConfig.submit_sleep = float(self.jobDescript.data['SubmitSleep'])
        self.gflFactoryConfig.max_removes = int(self.jobDescript.data['MaxRemoveRate'])
        self.gflFactoryConfig.remove_sleep = float(self.jobDescript.data['RemoveSleep'])
        self.gflFactoryConfig.max_releases = int(self.jobDescript.data['MaxReleaseRate'])
        self.gflFactoryConfig.release_sleep = float(self.jobDescript.data['ReleaseSleep'])
        self.gflFactoryConfig.log_stats = glideFactoryMonitoring.condorLogSummary(log=self.log)
        self.gflFactoryConfig.rrd_stats = glideFactoryMonitoring.FactoryStatusData(log=self.log, base_dir=self.monitoringConfig.monitor_dir)
        self.gflFactoryConfig.rrd_stats.base_dir = self.monitorDir

        # Add cleaners for the user log directories
        for username in self.frontendDescript.get_all_usernames():
            user_log_dir = self.gflFactoryConfig.get_client_log_dir(self.name,
                                                                    username)
            cleaner = cleanupSupport.PrivsepDirCleanupWSpace(
                username,
                user_log_dir,
                "(job\..*\.out)|(job\..*\.err)",
                glideFactoryLib.days2sec(float(self.glideinDescript.data['JobLogRetentionMaxDays'])),
                glideFactoryLib.days2sec(float(self.glideinDescript.data['JobLogRetentionMinDays'])),
                float(self.glideinDescript.data['JobLogRetentionMaxMBs']) * pow(2, 20))
            cleanupSupport.cleaners.add_cleaner(cleaner)

            cleaner = cleanupSupport.PrivsepDirCleanupWSpace(
                username,
                user_log_dir,
                "(condor_activity_.*\.log)|(condor_activity_.*\.log.ftstpk)|(submit_.*\.log)",
                glideFactoryLib.days2sec(float(self.glideinDescript.data['CondorLogRetentionMaxDays'])),
                glideFactoryLib.days2sec(float(self.glideinDescript.data['CondorLogRetentionMinDays'])),
                float(self.glideinDescript.data['CondorLogRetentionMaxMBs']) * pow(2,20))
            cleanupSupport.cleaners.add_cleaner(cleaner)

        self.glideinTotals = None

        # Load intial context for whitelist and downtimes
        self.loadWhitelist()
        self.loadDowntimes()

        # Create entry specific descript files
        write_descript(self.name, self.jobDescript, self.jobAttributes,
                       self.jobParams, self.monitorDir)


    def loadContext(self):
        """
        Load context for this entry object so monitoring and logs are
        writen correctly. This should be called in every method for now.
        """

        glideFactoryMonitoring.monitoringConfig = self.monitoringConfig
        gfi.factoryConfig = self.gfiFactoryConfig
        glideFactoryLib.factoryConfig = self.gflFactoryConfig


    def loadWhitelist(self):
        """
        Load the whitelist info for this entry
        """

        # Get information about which VOs to allow for this entry point.
        # This will be a comma-delimited list of pairs
        # vofrontendname:security_class,vofrontend:sec_class, ...
        self.frontendWhitelist = self.jobDescript.data['WhitelistMode']
        self.securityList = {};
        if (self.frontendWhitelist == "On"):
            allowed_vos = ''
            if self.jobDescript.has_key('AllowedVOs'):
                allowed_vos = self.jobDescript.data['AllowedVOs']
            frontend_allow_list = allowed_vos.split(',')
            for entry in frontend_allow_list:
                entry_part = entry.split(":");
                if (entry_part[0] in self.securityList):
                    self.securityList[entry_part[0]].append(entry_part[1]);
                else:
                    self.securityList[entry_part[0]] = [entry_part[1]];
        #self.allowedProxySource = self.glideinDescript.data['AllowedJobProxySource'].split(',')


    def loadDowntimes(self):
        """
        Load the downtime info for this entry
        """

        self.downtimes = glideFactoryDowntimeLib.DowntimeFile(self.glideinDescript.data['DowntimesFile'])
        self.downtimes.checkDowntime(entry=self.name)
        self.jobAttributes.data['GLIDEIN_Downtime_Comment'] = self.downtimes.downtime_comment


    def isClientBlacklisted(self, client_sec_name):
        """
        Check ifthe frontend whitelist is enabled and client is not in
        whitelist

        @rtype: boolean
        @return: True if the client's security name is blacklist
        """

        return ( (self.frontendWhitelist=="On") and
                 (not self.isClientInWhitelist(client_sec_name)) )


    def isClientWhitelisted(self, client_sec_name):
        """
        Check if the client's security name is in the whitelist of this entry
        and the frontend whitelist is enabled

        @rtype: boolean
        @return: True if the client's security name is whitelisted
        """

        return ( (self.frontendWhitelist=="On") and
                 (self.isClientInWhitelist(client_sec_name)) )


    def isClientInWhitelist(self, client_sec_name):
        """
        Check if the client's security name is in the whitelist of this entry

        @rtype: boolean
        @return: True if the client's security name is in the whitelist
        """

        return (client_sec_name in self.securityList)


    def isSecurityClassAllowed(self, client_sec_name, proxy_sec_class):
        """
        Check if the security class is allowed

        @rtype: boolean
        @return: True if the security class is allowed
        """

        return ((proxy_sec_class in self.securityList[client_sec_name]) or
                ("All" in self.securityList[client_sec_name]))


    def isInDowntime(self):
        """
        Check the downtime file to find out if entry is in downtime

        @rtype: boolean
        @return: True if the entry is in downtime
        """

        return self.downtimes.checkDowntime(entry=self.name)


    def isSecurityClassInDowntime(self, client_security_name, security_class):
        """
        Check if the security class is in downtime

        @rtype: boolean
        @return: True if the security class is in downtime
        """

        return ( (self.downtimes.checkDowntime(
                                     entry="factory",
                                     frontend=client_security_name,
                                     security_class=security_class)) or
                 (self.downtimes.checkDowntime(
                                     entry=self.name,
                                     frontend=client_security_name,
                                     security_class=security_class)) )

    def setDowntime(self, downtime_flag):
        """
        Check if we are in downtime and set info accordingly

        @type downtime_flag: boolean
        @param downtime_flag: Downtime flag
        """

        self.jobAttributes.data['GLIDEIN_In_Downtime'] = (downtime_flag or self.isInDowntime())


    def initIteration(self, factory_in_downtime):
        """
        Perform the reseting of stats as required before every iteration

        @type factory_in_downtime: boolean
        @param factory_in_downtime: Downtime flag for the factory
        """

        self.loadContext()

        self.setDowntime(factory_in_downtime)

        self.gflFactoryConfig.log_stats.reset()

        # This one is used for stats advertized in the ClassAd
        self.gflFactoryConfig.client_stats = glideFactoryMonitoring.condorQStats(log=self.log)
        # These two are used to write the history to disk
        self.gflFactoryConfig.qc_stats = glideFactoryMonitoring.condorQStats(log=self.log)
        self.gflFactoryConfig.client_internals = {}
        self.log.info("Iteration initialized")


    def unsetInDowntime(self):
        """
        Clear the downtime status of this entry
        """

        del self.jobAttributes.data['GLIDEIN_In_Downtime']


    def queryQueuedGlideins(self):
        """
        Query WMS schedd and get glideins info. Raise in case of failures.

        @rtype: condorMonitor.CondorQ
        @return: Information about the jobs in condor_schedd
        """

        try:
            return glideFactoryLib.getCondorQData(
                       self.name, None, self.scheddName,
                       factoryConfig=self.gflFactoryConfig)
        except Exception, e:
            self.log.info("Schedd %s not responding, skipping"%self.scheddName)
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            self.log.warning("getCondorQData failed, traceback: %s"%string.join(tb,''))
            raise e


    def glideinsWithinLimits(self, condorQ):
        """
        Check the condorQ info and see we are within limits & init entry limits

        @rtype: boolean
        @return: True if glideins are in limits and we can submit more
        """

        # Flag that says whether or not we can submit any more
        can_submit_glideins = True

        # Initialize entry and frontend limit dicts
        self.glideinTotals = glideFactoryLib.GlideinTotals(
                                 self.name, self.frontendDescript,
                                 self.jobDescript, condorQ,
                                 log=self.log)

        # Check if entry has exceeded max idle
        if self.glideinTotals.has_entry_exceeded_max_idle():
            self.log.warning("Entry %s has hit the limit for idle glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        # Check if entry has exceeded max glideins
        if (can_submit_glideins and
            self.glideinTotals.has_entry_exceeded_max_glideins()):
            self.log.warning("Entry %s has hit the limit for total glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        # Check if entry has exceeded max held
        if (can_submit_glideins and
            self.glideinTotals.has_entry_exceeded_max_held()):
            self.log.warning("Entry %s has hit the limit for held glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        return can_submit_glideins


    def writeClassadsToFile(self, factory_in_downtime, gf_filename,
                            gfc_filename, append=True):
        """
        Create the glidefactory and glidefactoryclient classads to advertise
        but do not advertise

        @type factory_in_downtime: boolean
        @param factory_in_downtime: factory in the downtimes file

        @type gf_filename: string
        @param gf_filename: Filename to write glidefactory classads

        @type gfc_filename: string
        @param gfc_filename: Filename to write glidefactoryclient classads

        @type append: boolean
        @param append: True to append new classads. i.e Multi classads file
        """

        self.loadContext()

        classads = {}
        trust_domain = self.jobDescript.data['TrustDomain']
        auth_method = self.jobDescript.data['AuthMethod']
        pub_key_obj = self.glideinDescript.data['PubKeyObj']

        self.gflFactoryConfig.client_stats.finalizeClientMonitor()
        current_qc_total = self.gflFactoryConfig.client_stats.get_total()

        ########################################################################
        # Logic to generate glidefactory classads file
        ########################################################################

        glidein_monitors = {}
        for w in current_qc_total:
            for a in current_qc_total[w]:
                glidein_monitors['Total%s%s'%(w,a)]=current_qc_total[w][a]
                self.jobAttributes.data['GlideinMonitorTotal%s%s' % (w, a)] = current_qc_total[w][a]

        # Make copy of job attributes so can override the validation
        # downtime setting with the true setting of the entry
        # (not from validation)
        myJobAttributes = self.jobAttributes.data.copy()
        myJobAttributes['GLIDEIN_In_Downtime'] = factory_in_downtime
        gf_classad = gfi.EntryClassad(
                         self.gflFactoryConfig.factory_name,
                         self.gflFactoryConfig.glidein_name,
                         self.name, trust_domain, auth_method,
                         self.gflFactoryConfig.supported_signtypes,
                         pub_key_obj=pub_key_obj, glidein_attrs=myJobAttributes,
                         glidein_params=self.jobParams.data.copy(),
                         glidein_monitors=glidein_monitors.copy())
        try:
            gf_classad.writeToFile(gf_filename, append=append)
        except:
            self.log.warning("Error writing classad to file %s" % gf_filename)
            self.log.exception("Error writing classad to file %s: " % (gf_filename))

        ########################################################################
        # Logic to generate glidefactoryclient classads file
        ########################################################################

        # Advertise the monitoring, use the downtime found in
        # validation of the credentials

        advertizer = gfi.MultiAdvertizeGlideinClientMonitoring(
                         self.gflFactoryConfig.factory_name,
                         self.gflFactoryConfig.glidein_name,
                         self.name, self.jobAttributes.data.copy())

        current_qc_data = self.gflFactoryConfig.client_stats.get_data()
        for client_name in current_qc_data:
            client_qc_data = current_qc_data[client_name]
            if client_name not in self.gflFactoryConfig.client_internals:
                self.log.warning("Client '%s' has stats, but no classad! Ignoring." % client_name)
                continue
            client_internals = self.gflFactoryConfig.client_internals[client_name]

            client_monitors={}
            for w in client_qc_data:
                for a in client_qc_data[w]:
                    # report only numbers
                    if type(client_qc_data[w][a])==type(1):
                        client_monitors['%s%s'%(w,a)] = client_qc_data[w][a]

            try:
                fparams = current_qc_data[client_name]['Requested']['Parameters']
            except:
                fparams = {}

            params = self.jobParams.data.copy()
            for p in fparams.keys():
                # Can only overwrite existing params, not create new ones
                if p in params.keys():
                    params[p] = fparams[p]

            advertizer.add(client_internals["CompleteName"],
                           client_name, client_internals["ReqName"],
                           params, client_monitors.copy())

        try:
            advertizer.writeToMultiClassadFile(gfc_filename)
        except:
            self.log.warning("Writing monitoring classad to file %s failed" % gfc_filename)

        return



    def advertise(self, factory_in_downtime):
        """
        Advertises the glidefactory and the glidefactoryclient classads.

        @type factory_in_downtime: boolean
        @param factory_in_downtime: factory in the downtimes file
        """

        self.loadContext()

        # Classad files to use
        gf_filename = classadSupport.generate_classad_filename(prefix='gfi_adm_gf')
        gfc_filename = classadSupport.generate_classad_filename(prefix='gfi_adm_gfc')
        self.writeClassadsToFile(factory_in_downtime, gf_filename, gfc_filename)

        # ADVERTISE: glidefactory classads
        gfi.advertizeGlideinFromFile(gf_filename, remove_file=True,
                                     is_multi=True)

        # ADVERTISE: glidefactoryclient classads
        gfi.advertizeGlideinClientMonitoringFromFile(gfc_filename,
                                                     remove_file=True,
                                                     is_multi=True)
        return


    def writeStats(self):
        """
        Calls the statistics functions to record and write stats for this
        iteration.

        There are several main types of statistics:

        log stats: That come from parsing the condor_activity
        and job logs.  This is computed every iteration
        (in perform_work()) and diff-ed to see any newly
        changed job statuses (ie. newly completed jobs)

        qc stats: From condor_q data.

        rrd stats: Used in monitoring statistics for javascript rrd graphs.
        """

        global log_rrd_thread, qc_rrd_thread

        self.loadContext()

        self.log.info("Computing log_stats diff for %s" % self.name)
        self.gflFactoryConfig.log_stats.computeDiff()
        self.log.info("log_stats diff computed")

        self.log.info("Writing log_stats for %s" % self.name)
        self.gflFactoryConfig.log_stats.write_file(monitoringConfig=self.monitoringConfig)
        self.log.info("log_stats written")

        self.gflFactoryConfig.qc_stats.finalizeClientMonitor()
        self.log.info("Writing qc_stats for %s" % self.name)
        self.gflFactoryConfig.qc_stats.write_file(monitoringConfig=self.monitoringConfig)
        self.log.info("qc_stats written")

        self.log.info("Writing rrd_stats for %s" % self.name)
        self.gflFactoryConfig.rrd_stats.writeFiles(monitoringConfig=self.monitoringConfig)
        self.log.info("rrd_stats written")

        return


    def getLogStatsOldStatsData(self):
        """
        Returns the gflFactoryConfig.log_stats.old_stats_data that can pickled

        @rtype: glideFactoryMonitoring.condorLogSummary
        @return: condorLogSummary from previous iteration
        """

        return self.getLogStatsData(self.gflFactoryConfig.log_stats.old_stats_data)


    def getLogStatsCurrentStatsData(self):
        """
        Returns the gflFactoryConfig.log_stats.current_stats_data that can
        pickled

        @rtype: glideFactoryMonitoring.condorLogSummary
        @return: condorLogSummary from current iteration
        """

        return self.getLogStatsData(self.gflFactoryConfig.log_stats.current_stats_data)


    def getLogStatsData(self, stats_data):
        """
        Returns the stats_data(stats_data[frontend][user].data) that can pickled

        @rtype: dict
        @return: Relevant stats data to pickle
        """

        return_dict = {}

        for frontend in stats_data:
            return_dict[frontend] = {}
            for user in stats_data[frontend]:
                return_dict[frontend][user] = stats_data[frontend][user].data
        return return_dict


    def setLogStatsOldStatsData(self, new_data):
        """
        Set old_stats_data or current_stats_data from pickled info

        @type new_data: glideFactoryMonitoring.condorLogSummary
        @param new_data: Data from pickled object to load
        """

        self.setLogStatsData(self.gflFactoryConfig.log_stats.old_stats_data,
                             new_data )


    def setLogStatsCurrentStatsData(self, new_data):
        """
        Set gflFactoryConfig.log_stats.current_stats_data from pickled info

        @type new_data: glideFactoryMonitoring.condorLogSummary
        @param new_data: Data from pickled object to load
        """

        self.setLogStatsData(self.gflFactoryConfig.log_stats.current_stats_data,
                             new_data )


    def setLogStatsData(self, stats_data, new_data):
        """
        Sets the stats_data(stats_data[frontend][user].data) from pickled info

        @type stats_data: dict
        @param stats_data: Stats data

        @type new_data: dict
        @param new_data: Stats data from pickled info
        """

        for frontend in new_data:
            stats_data[frontend] = {}
            for user in new_data[frontend]:
                x509_proxy_username = (user.split(':'))[0]
                client_int_name = (user.split(':'))[1]
                client_log_dir = self.gflFactoryConfig.get_client_log_dir(
                                     self.name, x509_proxy_username)
                stats = glideFactoryLogParser.dirSummaryTimingsOut(
                            client_log_dir, self.logDir,
                            client_int_name, x509_proxy_username)
                stats.load()
                stats_data[frontend][user] = stats.get_simple()
                stats_data[frontend][user].data = new_data


    def getState(self):
        """
        Compile a dictionary containt useful state information

        @rtype: dict
        @return: Useful state information that can pickled and restored
        """

        # Set logger to None else we can't pickle file objects
        self.gflFactoryConfig.client_stats.log = None
        self.gflFactoryConfig.qc_stats.log = None
        self.gflFactoryConfig.rrd_stats.log = None
        self.gflFactoryConfig.log_stats.log = None

        state = {
            'client_internals': self.gflFactoryConfig.client_internals,
            'glidein_totals': self.glideinTotals,
            'client_stats': self.gflFactoryConfig.client_stats,
            'qc_stats': self.gflFactoryConfig.qc_stats,
            'rrd_stats': self.gflFactoryConfig.rrd_stats,
            'log_stats': self.gflFactoryConfig.log_stats
        }
        return state


    def setState_old(self, state):
        """
        Load the post work state from the pickled info

        @type post_work_info: dict
        @param post_work_info: Picked state after doing work
        """

        self.gflFactoryConfig.client_stats = state.get('client_stats')
        self.gflFactoryConfig.qc_stats = state.get('qc_stats')
        self.gflFactoryConfig.rrd_stats = state.get('rrd_stats')
        self.gflFactoryConfig.client_internals = state.get('client_internals')
        self.glideinTotals = state.get('glidein_totals')
        self.gflFactoryConfig.log_stats = state['log_stats']


    def setState(self, state):
        """
        Load the post work state from the pickled info

        @type post_work_info: dict
        @param post_work_info: Picked state after doing work
        """

        self.gflFactoryConfig.client_stats = state.get('client_stats')
        if self.gflFactoryConfig.client_stats:
            self.gflFactoryConfig.client_stats.log = self.log

        self.gflFactoryConfig.qc_stats = state.get('qc_stats')
        if self.gflFactoryConfig.qc_stats:
            self.gflFactoryConfig.qc_stats.log = self.log

        self.gflFactoryConfig.rrd_stats = state.get('rrd_stats')
        if self.gflFactoryConfig.rrd_stats:
            self.gflFactoryConfig.rrd_stats.log = self.log

        self.gflFactoryConfig.client_internals = state.get('client_internals')

        self.glideinTotals = state.get('glidein_totals')

        self.gflFactoryConfig.log_stats = state['log_stats']
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
        self.log.debug(marker)
        self.log.debug("data = %s" % self.gflFactoryConfig.log_stats.data)
        self.log.debug("updated = %s" % self.gflFactoryConfig.log_stats.updated)
        self.log.debug("updated_year = %s" % self.gflFactoryConfig.log_stats.updated_year)
        self.log.debug("stats_diff = %s" % self.gflFactoryConfig.log_stats.stats_diff)
        self.log.debug("files_updated = %s" % self.gflFactoryConfig.log_stats.files_updated)
        self.log.debug("old_stats_data = %s" % self.gflFactoryConfig.log_stats.old_stats_data)
        self.log.debug("current_stats_data = %s" % self.gflFactoryConfig.log_stats.current_stats_data)
        self.log.debug(marker)


    def dump(self):
        return
        stdout = sys.stdout
        #sys.stdout = self.log.debug_log
        dump_obj(self)
        sys.stdout = stdout
# class Entry

def dump_obj(obj):
    import types
    print obj.__dict__
    print "======= START: %s ======" % obj
    for key in obj.__dict__:
        if type(obj.__dict__[key]) is not types.InstanceType:
            print "%s = %s" % (key, obj.__dict__[key])
        else:
            dump_obj(obj.__dict__[key])
    print "======= END: %s ======" % obj

###############################################################################

class X509Proxies:

    def __init__(self,frontendDescript,client_security_name):
        self.frontendDescript=frontendDescript
        self.client_security_name=client_security_name
        self.usernames={}
        self.fnames={}
        self.count_fnames=0 # len of sum(fnames)
        return

    # Return None, if cannot convert
    def get_username(self, x509_proxy_security_class):
        if not self.usernames.has_key(x509_proxy_security_class):
            # lookup only the first time
            x509_proxy_username=self.frontendDescript.get_username(self.client_security_name,x509_proxy_security_class)
            if x509_proxy_username is None:
                # but don't cache misses
                return None
            self.usernames[x509_proxy_security_class]=x509_proxy_username
        return self.usernames[x509_proxy_security_class][:]

    def add_fname(self,x509_proxy_security_class,x509_proxy_identifier,x509_proxy_fname):
        if not self.fnames.has_key(x509_proxy_security_class):
            self.fnames[x509_proxy_security_class]={}
        self.fnames[x509_proxy_security_class][x509_proxy_identifier]=x509_proxy_fname
        self.count_fnames+=1


###############################################################################

def check_and_perform_work(factory_in_downtime, entry, work):
    """
    Check if we need to do the work and then do the work. Called by child
    process per entry

    @param factory_in_downtime: Flag if factory is in downtime

    @type entry: glideFactoryEntry.Entry
    @param entry: Entry object
    """

    entry.loadContext()

    # Query glidein queue
    try:
        condorQ = entry.queryQueuedGlideins()
    except:
        # Protect and exit
        return 0

    # Consider downtimes and see if we can submit glideins
    all_security_names = set()
    done_something = 0
    entry.loadWhitelist()
    entry.loadDowntimes()
    # Variable to identify if frontend or sec_class is in downtime
    in_downtime = factory_in_downtime
    auth_method = entry.jobDescript.data['AuthMethod']

    #
    # STEP: Process every work one at a time
    #

    for work_key in work:
        if not glideFactoryLib.is_str_safe(work_key):
            # may be used to write files... make sure it is reasonable
            entry.log.warning("Request name '%s' not safe. Skipping request"%work_key)
            continue

        # merge work and default params
        params = work[work_key]['params']
        decrypted_params = work[work_key]['params_decrypted']

        # add default values if not defined
        for k in entry.jobParams.data.keys():
            if k not in params:
                params[k] = entry.jobParams.data[k]

        # Set client name (i.e. frontend.group) &
        # request name (i.e. entry@glidein@factory)
        try:
            client_int_name = work[work_key]['internals']["ClientName"]
            client_int_req = work[work_key]['internals']["ReqName"]
        except:
            entry.log.warning("Request %s not did not provide the client and/or request name. Skipping request" % work_key)
            continue

        if not glideFactoryLib.is_str_safe(client_int_name):
            # may be used to write files... make sure it is reasonable
            entry.log.warning("Client name '%s' not safe. Skipping request"%client_int_name)
            continue

        #
        # STEP: DOWNTIME AND FRONTEND/SECURITY_CLASS WHITELISTING CALCULATION
        #

        # Check request has the required credentials and nothing else
        try:
            entry.log.debug("Checking security credentials for client %s " % client_int_name)
            glideFactoryCredentials.check_security_credentials(
                auth_method, decrypted_params, client_int_name, entry.name)
        except glideFactoryCredentials.CredentialError:
            entry.log.exception("Error checking credentials, skipping request: ")
            continue

        # Check whether the frontend is in the whitelist of the entry
        client_security_name = decrypted_params.get('SecurityName')
        if client_security_name is None:
            entry.log.warning("Client %s did not provide the security name, skipping request" % client_int_name)
            continue

        if entry.isClientBlacklisted(client_security_name):
            entry.log.warning("Client name '%s' not in whitelist. Preventing glideins from %s "% (client_security_name,client_int_name))
            in_downtime=True

        client_expected_identity = entry.frontendDescript.get_identity(client_security_name)
        if client_expected_identity is None:
            entry.log.warning("Client %s (secid: %s) not in white list. Skipping request" % (client_int_name, client_security_name))
            continue

        client_authenticated_identity = work[work_key]['internals']["AuthenticatedIdentity"]
        if client_authenticated_identity != client_expected_identity:
            # silently drop... like if we never read it in the first place
            # this is compatible with what the frontend does
            entry.log.warning("Client %s (secid: %s) is not coming from a trusted source; AuthenticatedIdentity %s!=%s. Skipping for security reasons."%(client_int_name,client_security_name,client_authenticated_identity,client_expected_identity))
            continue

        #
        # STEP: Actually process the unit work using either v2 or v3 protocol
        #

        if ('x509_proxy_0' in decrypted_params):
            work_performed = unit_work_v2(entry, work[work_key], work_key,
                                          client_int_name, client_int_req,
                                          client_expected_identity,
                                          decrypted_params,
                                          params, in_downtime, condorQ)
        else:
            work_performed = unit_work_v3(entry, work[work_key], work_key,
                                          client_int_name, client_int_req,
                                          client_expected_identity,
                                          decrypted_params,
                                          params, in_downtime, condorQ)

        if not work_performed['success']:
            # There was error processing this unit work request.
            # Ignore this work request and continue to next one.
            continue

        done_something += work_performed['work_done']
        all_security_names = all_security_names.union(work_performed['security_names'])

    if done_something == 0:
        entry.log.info("Sanitizing glideins for entry %s" % entry.name)
        glideFactoryLib.sanitizeGlideins(condorQ, log=entry.log,
                                         factoryConfig=entry.gflFactoryConfig)

    #entry.log.info("all_security_names = %s" % all_security_names)

    for sec_el in all_security_names:
        try:
            #glideFactoryLib.factoryConfig.rrd_stats.getData("%s_%s" % sec_el)
            entry.gflFactoryConfig.rrd_stats.getData(
                "%s_%s" % sec_el, monitoringConfig=entry.monitoringConfig)
        except glideFactoryLib.condorExe.ExeError,e:
            # Never fail for monitoring. Just log
            entry.log.exception("get_RRD_data failed with condor error: ")
        except:
            # Never fail for monitoring. Just log
            entry.log.exception("get_RRD_data failed with unknown error: ")

    return done_something


###############################################################################
def unit_work_v3(entry, work, client_name, client_int_name, client_int_req,
                 client_expected_identity, decrypted_params, params,
                 in_downtime, condorQ):
    """
    Perform a single work unit using the v2 protocol. When we stop supporting
    v2 protocol, this function can be removed along with the places it is
    called from.
    """

    # Return dictionary. Only populate information to be passed at the end
    # just before returning.
    return_dict = {
        'success': False,
        'security_names': None,
        'work_done': None,
    }

    #
    # STEP: CHECK THAT GLIDEINS ARE WITING ALLOWED LIMITS
    #
    can_submit_glideins = entry.glideinsWithinLimits(condorQ)

    auth_method = entry.jobDescript.data['AuthMethod']
    all_security_names = set()

    # Get credential security class
    credential_security_class = decrypted_params.get('SecurityClass')
    client_security_name = decrypted_params.get('SecurityName')

    if not credential_security_class:
        entry.log.warning("Client %s did not provide a security class. Skipping bad request." % client_int_name)
        return return_dict

    # Check security class for downtime (in downtimes file)
    entry.log.info("Checking downtime for frontend %s security class: %s (entry %s)." % (client_security_name, credential_security_class, entry.name))

    if entry.isSecurityClassInDowntime(client_security_name,
                                       credential_security_class):

        # Cannot use proxy for submission but entry is not in downtime
        # since other proxies may map to valid security classes
        entry.log.warning("Security class %s is currently in a downtime window for entry: %s. Ignoring request." % (credential_security_class, entry.name))
        return return_dict

    # Deny Frontend from requesting glideins if the whitelist
    # does not have its security class (or "All" for everyone)
    if entry.isClientWhitelisted(client_security_name):
        if entry.isSecurityClassAllowed(client_security_name,
                                        credential_security_class):
            entry.log.info("Security test passed for : %s %s " % (entry.name, credential_security_class))
        else:
            entry.log.warning("Security class not in whitelist, skipping request (%s %s). " % (client_security_name, credential_security_class))
            return return_dict

    # Check that security class maps to a username for submission
    credential_username = entry.frontendDescript.get_username(
                              client_security_name, credential_security_class)
    if credential_username is None:
        entry.log.warning("No username mapping for security class %s of credential for %s (secid: %s), skipping request." % (credential_security_class, client_int_name, client_security_name))
        return return_dict

    # Initialize submit credential object & determine the credential location
    submit_credentials = glideFactoryCredentials.SubmitCredentials(
                             credential_username, credential_security_class)
    submit_credentials.cred_dir = entry.gflFactoryConfig.get_client_proxies_dir(credential_username)

    if 'grid_proxy' in auth_method:
        ########################
        # ENTRY TYPE: Grid Sites
        ########################

        # Check if project id is required
        if 'project_id' in auth_method:
            if decrypted_params.has_key('ProjectId'):
                submit_credentials.add_identity_credential('ProjectId', decrypted_params['ProjectId'])
            else:
                # ProjectId is required, cannot service request
                entry.log.warning("Client '%s' did not specify a Project Id in the request, this is required by entry %s, skipping request." % (client_int_name, entry.name))
                return return_dict

        # Check if voms_attr required
        if 'voms_attr' in auth_method:
            # TODO: PM: determine how to verify voms attribute on a proxy
            pass

        # Determine identifier for file name and add to
        # credentials to be passed to submit
        proxy_id = decrypted_params['SubmitProxy']

        if not submit_credentials.add_security_credential('SubmitProxy', "%s_%s" % (client_int_name, proxy_id)):
            entry.log.warning("Credential %s for the submit proxy cannot be found for client %s, skipping request." % (proxy_id, client_int_name))
            return return_dict

        # Set the id used for tracking what is in the factory queue
        submit_credentials.id = proxy_id

    else:
        #########################
        # ENTRY TYPE: Cloud Sites
        #########################

        # All non proxy auth methods are cloud sites.

        # Verify that the glidein proxy was provided. We still need it as it
        # is used to by the glidein's condor daemons to authenticate with the
        # user collector
        proxy_id = decrypted_params.get('GlideinProxy')

        if proxy_id:
            # the GlideinProxy must be compressed for usage within user data
            # so we specify the compressed version of the credential
            credential_name = "%s_%s_compressed" % (client_int_name, proxy_id)
            if not submit_credentials.add_security_credential('GlideinProxy', credential_name):
                entry.log.warning("Credential %s for the glidein proxy cannot be found for client %s, skipping request." % (proxy_id, client_int_name))
                return return_dict
        else:
            entry.log.warning("Glidein proxy cannot be found for client %s, skipping request" % client_int_name)
            return return_dict

        # VM id and type are required for cloud sites.
        # Either frontend or factory should provide it
        vm_id = None
        vm_type = None

        if 'vm_id' in auth_method:
            # First check if the Frontend supplied it
            vm_id = decrypted_params.get('VMId')
            if not vm_id:
                entry.log.warning("Client '%s' did not specify a VM Id in the request, this is required by entry %s, skipping request. " % (client_int_name, entry.name))
                return return_dict
        else:
            # Validate factory provided vm id exists
            if entry.jobDescript.data.has_key('EntryVMId'):
                vm_id = entry.jobDescript.data['EntryVMId']
            else:
                entry.log.warning("Entry does not specify a VM Id, this is required by entry %s, skipping request." % entry.name)
                return return_dict

        if 'vm_type' in auth_method:
            # First check if the Frontend supplied it
            vm_type = decrypted_params.get('VMType')
            if not vm_type:
                entry.log.warning("Client '%s' did not specify a VM Type in the request, this is required by entry %s, skipping request." % (client_int_name, entry.name))
                return return_dict
        else:
            # Validate factory provided vm type exists
            if entry.jobDescript.data.has_key('EntryVMType'):
                vm_type = entry.jobDescript.data['EntryVMType']
            else:
                entry.log.warning("Entry does not specify a VM Type, this is required by entry %s, skipping request." %  entry.name)
                return return_dict

        submit_credentials.add_identity_credential('VMId', vm_id)
        submit_credentials.add_identity_credential('VMType', vm_type)

        if 'cert_pair' in auth_method :
            public_cert_id = decrypted_params.get('PublicCert')
            submit_credentials.id = public_cert_id
            if ((public_cert_id) and
                (not submit_credentials.add_security_credential(
                         'PublicCert',
                         '%s_%s' % (client_int_name, public_cert_id))) ):
                entry.log.warning("Credential %s for the public certificate is not safe for client %s, skipping request." % (public_cert_id, client_int_name))
                return return_dict

            private_cert_id = decrypted_params.get('PrivateCert')
            if ( (private_cert_id) and
                 (submit_credentials.add_security_credential(
                      'PrivateCert',
                      '%s_%s' % (client_int_name, private_cert_id))) ):
                entry.log.warning("Credential %s for the private certificate is not safe for client %s, skipping request" % (private_cert_id, client_int_name))
                return return_dict

        elif 'key_pair' in auth_method:
            public_key_id = decrypted_params.get('PublicKey')
            submit_credentials.id = public_key_id
            if ( (public_key_id) and
                 (not submit_credentials.add_security_credential(
                          'PublicKey',
                          '%s_%s' % (client_int_name, public_key_id))) ):
                entry.log.warning("Credential %s for the public key is not safe for client %s, skipping request" % (public_key_id, client_int_name))
                return return_dict

            private_key_id = decrypted_params.get('PrivateKey')
            if ( (private_key_id) and
                 (not submit_credentials.add_security_credential(
                          'PrivateKey',
                          '%s_%s' % (client_int_name, private_key_id))) ):
                entry.log.warning("Credential %s for the private key is not safe for client %s, skipping request" % (private_key_id, client_int_name))
                return return_dict

        elif 'username_password' in auth_method:
            username_id = decrypted_params.get('Username')
            submit_credentials.id = username_id
            if ( (username_id) and
                 (not submit_credentials.add_security_credential(
                          'Username',
                          '%s_%s' % (client_int_name, username_id))) ):
                entry.log.warning("Credential %s for the username is not safe for client %s, skipping request" % (username_id, client_int_name))
                return return_dict

            password_id = decrypted_params.get('Password')
            if ( (password_id) and
                 (not submit_credentials.add_security_credential(
                          'Password',
                          '%s_%s' % (client_int_name, password_id))) ):
                entry.log.warning("Credential %s for the password is not safe for client %s, skipping request" % (password_id, client_int_name))
                return return_dict

        else:
            logSupport.log.warning("Factory entry %s has invalid authentication method. Skipping request for client %s." % (entry.name, client_int_name))
            return return_dict

    # Set the downtime status so the frontend-specific
    # downtime is advertised in glidefactoryclient ads
    entry.setDowntime(in_downtime)
    entry.gflFactoryConfig.qc_stats.set_downtime(in_downtime)

    #
    # STEP: CHECK IF CLEANUP OF IDLE GLIDEINS IS REQUIRED
    #

    remove_excess = work['requests'].get('RemoveExcess', 'NO')

    if 'IdleGlideins' not in work['requests']:
        # Malformed, if no IdleGlideins
        entry.log.warning("Skipping malformed classad for client %s" % client_name)
        return return_dict

    try:
        idle_glideins = int(work['requests']['IdleGlideins'])
    except ValueError, e:
        entry.log.warning("Client %s provided an invalid ReqIdleGlideins: '%s' not a number. Skipping request" % (client_int_name, work['requests']['IdleGlideins']))
        return return_dict

    if 'MaxGlideins' in work['requests']:
        try:
            max_glideins = int(work['requests']['MaxGlideins'])
        except ValueError, e:
            entry.log.warning("Client %s provided an invalid ReqMaxGlideins: '%s' not a number. Skipping request." % (client_int_name, work['requests']['MaxGlideins']))
            return return_dict
    else:
        try:
            max_glideins = int(work['requests']['MaxRunningGlideins'])
        except ValueError, e:
            entry.log.warning("Client %s provided an invalid ReqMaxRunningGlideins: '%s' not a number. Skipping request" % (client_int_name, work['requests']['MaxRunningGlideins']))
            return return_dict

    # If we got this far, it was because we were able to
    # successfully update all the credentials in the request
    # If we already have hit our limits checked at beginning of this
    # method and logged there, we can't submit.
    # We still need to check/update all the other request credentials
    # and do cleanup.

    # We'll set idle glideins to zero if hit max or in downtime.
    if in_downtime or not can_submit_glideins:
        idle_glideins=0

    try:
        client_web_url = work['web']['URL']
        client_signtype = work['web']['SignType']
        client_descript = work['web']['DescriptFile']
        client_sign = work['web']['DescriptSign']
        client_group = work['internals']['GroupName']
        client_group_web_url = work['web']['GroupURL']
        client_group_descript = work['web']['GroupDescriptFile']
        client_group_sign = work['web']['GroupDescriptSign']

        client_web = glideFactoryLib.ClientWeb(client_web_url, client_signtype,
                                               client_descript, client_sign,
                                               client_group,
                                               client_group_web_url,
                                               client_group_descript,
                                               client_group_sign)
    except:
        # malformed classad, skip
        entry.log.warning("Malformed classad for client %s, missing web parameters, skipping request." % client_name)
        return return_dict


    # Should log here or in perform_work
    glideFactoryLib.logWorkRequest(
        client_int_name, client_security_name,
        submit_credentials.security_class, idle_glideins,
        max_glideins, work, log=entry.log, factoryConfig=entry.gflFactoryConfig)

    all_security_names.add((client_security_name, credential_security_class))

    entry_condorQ = glideFactoryLib.getQProxSecClass(
                        condorQ, client_int_name,
                        submit_credentials.security_class,
                        client_schedd_attribute=entry.gflFactoryConfig.client_schedd_attribute,
                        credential_secclass_schedd_attribute=entry.gflFactoryConfig.credential_secclass_schedd_attribute,
                        factoryConfig=entry.gflFactoryConfig)


    # Map the identity to a frontend:sec_class for tracking totals
    frontend_name = "%s:%s" % \
        (entry.frontendDescript.get_frontend_name(client_expected_identity),
         credential_security_class)

    # do one iteration for the credential set (maps to a single security class)
    entry.gflFactoryConfig.client_internals[client_int_name] = \
        {"CompleteName":client_name, "ReqName":client_int_req}

    done_something = perform_work_v3(entry, entry_condorQ, client_name,
                                     client_int_name, client_security_name,
                                     submit_credentials, remove_excess,
                                     idle_glideins, max_glideins,
                                     credential_username, entry.glideinTotals,
                                     frontend_name, client_web, params)

    # Gather the information to be returned back
    return_dict['success'] = True
    return_dict['work_done'] = done_something
    return_dict['security_names'] = all_security_names

    return return_dict

###############################################################################

def unit_work_v2(entry, work, client_name, client_int_name, client_int_req,
                 client_expected_identity, decrypted_params, params,
                 in_downtime, condorQ):
    """
    Perform a single work unit using the v2 protocol. When we stop supporting
    v2 protocol, this function can be removed along with the places it is
    called from.
    """

    # Only populate information to be passed at the end just before returning
    # If any errors are identified in the work unit, just throw away the
    # processing done so far by returning with success = False
    return_dict = {
        'success': False,
        'work_done': 0,
        'security_names': None,
    }

    #
    # STEP: CHECK THAT GLIDEINS ARE WITING ALLOWED LIMITS
    #
    can_submit_glideins = entry.glideinsWithinLimits(condorQ)

    auth_method = entry.jobDescript.data['AuthMethod']
    client_security_name = decrypted_params.get('SecurityName')
    x509_proxies = X509Proxies(entry.frontendDescript, client_security_name)
    all_security_names = set()
    identity_credentials = {}

    # METHOD: grid_proxy
    if not ('grid_proxy' in auth_method):
        entry.log.warning("Client %s provided proxy, but a client supplied proxy is not allowed. Skipping bad request" % client_int_name)
        return return_dict

    # METHOD: Corral/Teragrid project_id
    if 'project_id' in auth_method:
        # Validate project id exists
        if 'ProjectId' in decrypted_params:
            identity_credentials['ProjectId'] = decrypted_params['ProjectId']
        else:
            # project id is required, cannot service request
            logSupport.log.warning("Client '%s' did not specify a Project Id in the request, this is required by entry %s, skipping "%(client_int_name, entry.name))
            return return_dict

    # METHOD: voms_attr
    if 'voms_attr' in auth_method:
        # TODO: PM: determine how to verify voms attribute on a proxy
        pass

    nr_x509_proxies = 0
    if ('nr_x509_proxies' not in decrypted_params):
        logSupport.log.warning("Could not determine number of proxies for %s, skipping request" % client_int_name)
        return return_dict
    try:
        nr_x509_proxies = int(decrypted_params['nr_x509_proxies'])
    except:
        logSupport.log.warning("Invalid number of proxies for %s, skipping request" % client_int_name)
        return return_dict

    # If the whitelist mode is on, then set downtime to true
    # We will set it to false in the loop if a security class passes the test
    if entry.frontendWhitelist == "On":
        prev_downtime = in_downtime
        in_downtime = True

    # Set security class downtime flag
    # TODO: PM: Why we need this? Its not used anywhere apart from being set
    security_class_downtime_found = False

    for i in range(nr_x509_proxies):
        # Validate each proxy
        x509_proxy = decrypted_params.get('x509_proxy_%i'%i)
        x509_proxy_identifier = decrypted_params.get(
                                    'x509_proxy_%i_identifier'%i)

        if x509_proxy is None:
            entry.log.warning("Could not decrypt x509_proxy_%i for %s, ignoring this proxy and trying the others" % (i, client_int_name))
            continue

        if x509_proxy_identifier is None:
            logSupport.log.warning("No identifier for x509_proxy_%i for %s, ignoring this proxy and trying the others" % (i, client_int_name))
            continue

        # Make sure proxy id is safe to write files.
        if not glideFactoryLib.is_str_safe(x509_proxy_identifier):
            entry.log.warning("Identifier for x509_proxy_%i for %s is not safe ('%s), skipping and trying the others" % (i, client_int_name, x509_proxy_identifier))
            continue

        # Check security class for downtime (in downtimes file)
        x509_proxy_security_class = decrypted_params.get(
                                        'x509_proxy_%i_security_class'%i,
                                        x509_proxy_identifier)


        entry.log.info("Checking downtime for frontend %s security class: %s (entry %s)." % (client_security_name, x509_proxy_security_class, entry.name))

        if entry.isSecurityClassInDowntime(client_security_name,
                                           x509_proxy_security_class):
            # Cannot use proxy for submission but entry is not in downtime
            # since other proxies may map to valid security classes
            entry.log.warning("Security Class %s is currently in a downtime window for Entry: %s. Ignoring request." % (x509_proxy_security_class, entry.name))
            security_class_downtime_found = True
            continue

        # Deny Frontend from requesting glideins if the whitelist
        # does not have its security class (or "All" for everyone)
        if entry.isClientWhitelisted(client_security_name):
            if entry.isSecurityClassAllowed(client_security_name,
                                            x509_proxy_security_class):
                in_downtime = prev_downtime
                entry.log.info("Security test passed for : %s %s " % (entry.name, x509_proxy_security_class))
            else:
                entry.log.warning("Security class not in whitelist, skipping request (%s %s) " % (client_security_name, x509_proxy_security_class))
                continue

        # Check that security class maps to a username for submission
        x509_proxy_username = x509_proxies.get_username(x509_proxy_security_class)
        if x509_proxy_username is None:
            entry.log.warning("No mapping for security class %s of x509_proxy_%i for %s (secid: %s), skipping and trying the others" % (x509_proxy_security_class, i, client_int_name, client_security_name))
            continue

        # Format proxy filename
        try:
            x509_proxy_fname = glideFactoryLib.update_x509_proxy_file(
                                   entry.name, x509_proxy_username,
                                   "%s_%s" % (client_name, x509_proxy_identifier),
                                   x509_proxy,
                                   factoryConfig=entry.gflFactoryConfig)
        except RuntimeError,e:
            entry.log.warning("Failed to update x509_proxy_%i using username %s for client %s, skipping request" % (i, x509_proxy_username, client_int_name))
            continue
        except:
            entry.log.exception("Failed to update x509_proxy_%i using usename %s for client %s, skipping request: " % (i, x509_proxy_username, client_int_name))
            continue

        x509_proxies.add_fname(x509_proxy_security_class,
                               x509_proxy_identifier,
                               x509_proxy_fname)

    if x509_proxies.count_fnames<1:
        entry.log.warning("No good proxies for %s, skipping request"%client_int_name)
        return return_dict

    # Set the downtime status so the frontend-specific
    # downtime is advertised in glidefactoryclient ads
    entry.setDowntime(in_downtime)
    entry.gflFactoryConfig.qc_stats.set_downtime(in_downtime)

    #
    # STEP: CHECK IF CLEANUP OF IDLE GLIDEINS IS REQUIRED
    #

    remove_excess = work['requests'].get('RemoveExcess', 'NO')

    if 'IdleGlideins' not in work['requests']:
        # Malformed, if no IdleGlideins
        entry.log.warning("Skipping malformed classad for client %s" % client_name)
        return return_dict

    try:
        idle_glideins = int(work['requests']['IdleGlideins'])
    except ValueError, e:
        entry.log.warning("Client %s provided an invalid ReqIdleGlideins: '%s' not a number. Skipping request" % (client_int_name, work['requests']['IdleGlideins']))
        return return_dict

    if 'MaxGlideins' in work['requests']:
        try:
            max_glideins = int(work['requests']['MaxGlideins'])
        except ValueError, e:
            entry.log.warning("Client %s provided an invalid ReqMaxGlideins: '%s' not a number. Skipping request." % (client_int_name, work['requests']['MaxGlideins']))
            return return_dict
    else:
        try:
            max_glideins = int(work['requests']['MaxRunningGlideins'])
        except ValueError, e:
            entry.log.warning("Client %s provided an invalid ReqMaxRunningGlideins: '%s' not a number. Skipping request" % (client_int_name, work['requests']['MaxRunningGlideins']))
            return return_dict

    # If we got this far, it was because we were able to
    # successfully update all the credentials in the request
    # If we already have hit our limits checked at beginning of this
    # method and logged there, we can't submit.
    # We still need to check/update all the other request credentials
    # and do cleanup.

    # We'll set idle glideins to zero if hit max or in downtime.
    if in_downtime or not can_submit_glideins:
        idle_glideins=0

    try:
        client_web_url = work['web']['URL']
        client_signtype = work['web']['SignType']
        client_descript = work['web']['DescriptFile']
        client_sign = work['web']['DescriptSign']
        client_group = work['internals']['GroupName']
        client_group_web_url = work['web']['GroupURL']
        client_group_descript = work['web']['GroupDescriptFile']
        client_group_sign = work['web']['GroupDescriptSign']

        client_web = glideFactoryLib.ClientWeb(
                         client_web_url, client_signtype, client_descript,
                         client_sign, client_group, client_group_web_url,
                         client_group_descript, client_group_sign,
                         factoryConfig=entry.gflFactoryConfig)
    except:
        # malformed classad, skip
        entry.log.warning("Malformed classad for client %s, missing web parameters, skipping request." % client_name)
        return return_dict

    x509_proxy_security_classes = x509_proxies.fnames.keys()
    # Sort to have consistent logging
    x509_proxy_security_classes.sort()
    for x509_proxy_security_class in x509_proxy_security_classes:
        # split the request proportionally between them

        x509_proxy_frac = 1.0 * len(x509_proxies.fnames[x509_proxy_security_class]) / x509_proxies.count_fnames

        # Round up if a client requests a non splittable number, worse for him.
        # Expect no issues in real world as the most reasonable
        # use case has a single proxy_class per client name
        idle_glideins_pc = int(math.ceil(idle_glideins * x509_proxy_frac))
        max_glideins_pc = int(math.ceil(max_glideins * x509_proxy_frac))

        # Should log here or in perform_work
        glideFactoryLib.logWorkRequest(
            client_int_name, client_security_name, x509_proxy_security_class,
            idle_glideins, max_glideins, work, fraction=x509_proxy_frac,
            log=entry.log, factoryConfig=entry.gflFactoryConfig)

        all_security_names.add((client_security_name,
                                x509_proxy_security_class))

        entry_condorQ = glideFactoryLib.getQProxSecClass(
                            condorQ, client_int_name,
                            x509_proxy_security_class,
                            client_schedd_attribute=entry.gflFactoryConfig.client_schedd_attribute,
                            credential_secclass_schedd_attribute=entry.gflFactoryConfig.credential_secclass_schedd_attribute,
                            factoryConfig=entry.gflFactoryConfig)


        # Map the identity to a frontend:sec_class for tracking totals
        frontend_name = "%s:%s" % \
            (entry.frontendDescript.get_frontend_name(client_expected_identity),
             x509_proxy_security_class)

        # Do a iteration for the credential set (maps to a 1 security class)
        entry.gflFactoryConfig.client_internals[client_int_name] = \
            {"CompleteName":client_name, "ReqName":client_int_req}

        done_something = perform_work_v2(
                             entry, entry_condorQ, client_name, client_int_name,
                             client_security_name, x509_proxy_security_class,
                             remove_excess, idle_glideins_pc, max_glideins_pc,
                             x509_proxies.fnames[x509_proxy_security_class],
                             x509_proxies.get_username(x509_proxy_security_class),
                             identity_credentials, entry.glideinTotals,
                             frontend_name, client_web, params)

    # Gather the information to be returned back
    return_dict['success'] = True
    return_dict['work_done'] = done_something
    return_dict['security_names'] = all_security_names

    return return_dict

###############################################################################

def perform_work_v3(entry, condorQ, client_name, client_int_name,
                    client_security_name, submit_credentials, remove_excess,
                    idle_glideins, max_glideins, credential_username,
                    glidein_totals, frontend_name, client_web, params):

    # find out the users it is using
    log_stats = {}
    log_stats[credential_username + ":" + client_int_name] = \
        glideFactoryLogParser.dirSummaryTimingsOut(
            entry.gflFactoryConfig.get_client_log_dir(entry.name,
                                                      credential_username),
            entry.logDir, client_int_name, credential_username)

    # should not need privsep for reading logs
    log_stats[credential_username + ":" + client_int_name].load()

    glideFactoryLib.logStats(condorQ, client_int_name,
                             client_security_name,
                             submit_credentials.security_class, log=entry.log,
                             factoryConfig=entry.gflFactoryConfig)

    client_log_name = glideFactoryLib.secClass2Name(
                          client_security_name,
                          submit_credentials.security_class)
    entry.gflFactoryConfig.log_stats.logSummary(client_log_name, log_stats)

    entry.log.info("Using v3+ protocol and credential %s" % submit_credentials.id)
    nr_submitted = glideFactoryLib.keepIdleGlideins(
                       condorQ, client_int_name, idle_glideins,
                       max_glideins, remove_excess, submit_credentials,
                       glidein_totals, frontend_name, client_web, params,
                       log=entry.log, factoryConfig=entry.gflFactoryConfig)

    if nr_submitted>0:
        entry.log.info("Submitted %s glideins" % nr_submitted)
        # We submitted something
        return 1

    return 0


###############################################################################


def perform_work_v2(entry, condorQ, client_name, client_int_name,
                    client_security_name, credential_security_class,
                    remove_excess, idle_glideins, max_running,
                    credential_fnames, credential_username,
                    identity_credentials, glidein_totals, frontend_name,
                    client_web, params):
    """
    Perform the work (Submit glideins)

    @type entry: glideFactoryEntry.Entry
    @param entry: Entry object

    @type condorQ: condorMonitor.CondorQ
    @param condorQ: Information about the jobs in condor_schedd

    @type client_int_name: string
    @param client_in_name: Internal name of the client

    @type client_securty_name: string
    @param client_security_name: Security name of the client

    @type credential_security_class: string
    @param credential_security_class: x509 proxy's security class

    @type client_int_req: string
    @param client_int_req: client_int_req

    @type remove_excess: boolean
    @param remove_excess: Flag if frontend wants us to remove excess glideins

    @type idle_glideins: int
    @param idle_glideins: Number of idle glideins

    @type max_running: int
    @param max_running: Maximum number of running glideins

    @type credential_fnames: string
    @param credential_fnames: Credential file

    @type credential_username: string
    @param credential_username: Credential username

    @type glidein_totals: object
    @param glidein_totals: glidein_totals object

    @type frontend_name: string
    @param frontend_name: Name of the frontend

    @type client_web: string
    @param client_web: Client's web location

    @type params: object
    @param params: Params object
    """

    entry.loadContext()

    condor_pool = params.get('GLIDEIN_Collector', None)

    credential_keys = credential_fnames.keys()
    # Randomize so I don't favour any proxy over another
    random.shuffle(credential_keys)

    # find out the users it is using
    log_stats = {}
    log_stats[credential_username+":"+client_int_name] = \
        glideFactoryLogParser.dirSummaryTimingsOut(
            entry.gflFactoryConfig.get_client_log_dir(entry.name,
                                                      credential_username),
            entry.logDir, client_int_name, credential_username)
    # should not need privsep for reading logs
    log_stats[credential_username+":"+client_int_name].load()

    glideFactoryLib.logStats(condorQ, client_int_name, client_security_name,                                 credential_security_class, log=entry.log,
                             factoryConfig=entry.gflFactoryConfig)
    client_log_name = glideFactoryLib.secClass2Name(client_security_name,
                                                    credential_security_class)
    entry.gflFactoryConfig.log_stats.logSummary(client_log_name, log_stats)

    # use the extended params for submission
    proxy_fraction = 1.0/len(credential_keys)

    # I will shuffle proxies around, so I may as well round up all of them
    idle_glideins_pproxy = int(math.ceil(idle_glideins*proxy_fraction))
    max_glideins_pproxy = int(math.ceil(max_running*proxy_fraction))

    # not reducing the held, as that is effectively per proxy, not per request
    nr_submitted=0
    for credential_id in credential_keys:
        security_credentials = {}
        security_credentials['SubmitProxy'] = credential_fnames[credential_id]
        submit_credentials = glideFactoryCredentials.SubmitCredentials(
                                 credential_username,
                                 credential_security_class)
        submit_credentials.id = credential_id
        submit_credentials.security_credentials = security_credentials
        submit_credentials.identity_credentials = identity_credentials

        entry.log.info("Using v2+ protocol and credential %s" % submit_credentials.id)
        nr_submitted += glideFactoryLib.keepIdleGlideins(
                            condorQ, client_int_name,
                            idle_glideins_pproxy, max_glideins_pproxy,
                            remove_excess, submit_credentials,
                            glidein_totals, frontend_name,
                            client_web, params, log=entry.log,
                            factoryConfig=entry.gflFactoryConfig)

    if nr_submitted>0:
        entry.log.info("Submitted %s glideins" % nr_submitted)
        # We submitted something
        return 1

    return 0


############################################################

# added by C.W. Murphy for glideFactoryEntryDescript
def write_descript(entry_name,entryDescript,entryAttributes,entryParams,monitor_dir):
    entry_data = {entry_name:{}}
    entry_data[entry_name]['descript'] = copy.deepcopy(entryDescript.data)
    entry_data[entry_name]['attributes'] = copy.deepcopy(entryAttributes.data)
    entry_data[entry_name]['params'] = copy.deepcopy(entryParams.data)

    descript2XML = glideFactoryMonitoring.Descript2XML()
    str = descript2XML.entryDescript(entry_data)
    xml_str = ""
    for line in str.split("\n")[1:-2]:
        line = line[3:] + "\n" # remove the extra tab
        xml_str += line

    try:
        descript2XML.writeFile(monitor_dir + "/",
                               xml_str, singleEntry = True)
    except IOError:
        logSupport.log.debug("IOError in writeFile in descript2XML")

    return


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
