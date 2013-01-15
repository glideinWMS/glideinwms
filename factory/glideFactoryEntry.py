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
try:
    set
except:
    from sets import Set as set

sys.path.append(os.path.join(sys.path[0],"../lib"))

import glideFactoryPidLib
import glideFactoryConfig
import glideFactoryLib
import glideFactoryMonitoring
import glideFactoryInterface
import glideFactoryLogParser
import glideFactoryDowntimeLib
import logSupport
import glideinWMSVersion


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
        self.logFiles = glideFactoryLib.LogFiles(
            self.logDir,
            float(self.glideinDescript.data['LogRetentionMaxDays']),
            float(self.glideinDescript.data['LogRetentionMinDays']),
            float(self.glideinDescript.data['LogRetentionMaxMBs']))

        self.logFiles.add_dir_to_cleanup(
            None,
            self.logDir,
            "(condor_activity_.*\.log\..*\.ftstpk)",
            float(self.glideinDescript.data['CondorLogRetentionMaxDays']),
            float(self.glideinDescript.data['CondorLogRetentionMinDays']),
            float(self.glideinDescript.data['CondorLogRetentionMaxMBs']))

        self.monitoringConfig = glideFactoryMonitoring.MonitoringConfig(logfiles=self.logFiles)
        self.monitoringConfig.monitor_dir = self.monitorDir
        self.monitoringConfig.my_name = "%s@%s" % (name, self.glideinDescript.data['GlideinName'])

        self.monitoringConfig.config_log(
            self.logDir,
            float(self.glideinDescript.data['SummaryLogRetentionMaxDays']),
            float(self.glideinDescript.data['SummaryLogRetentionMinDays']),
            float(self.glideinDescript.data['SummaryLogRetentionMaxMBs']))

        # FactoryConfig object from glideFactoryInterface
        self.gfiFactoryConfig = glideFactoryInterface.FactoryConfig()
        self.gfiFactoryConfig.warning_log = self.logFiles.warning_log
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
            self.logFiles.logWarning("Exception occured while trying to retrieve the glideinwms version. See debug log for more details.")
            self.logFiles.logDebug("Exception occurred while trying to retrieve the glideinwms version: %s" % tb)


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
        self.gflFactoryConfig.submit_sleep = float(self.jobDescript.data['SubmitSleep'])
        self.gflFactoryConfig.max_removes = int(self.jobDescript.data['MaxRemoveRate'])
        self.gflFactoryConfig.remove_sleep = float(self.jobDescript.data['RemoveSleep'])
        self.gflFactoryConfig.max_releases = int(self.jobDescript.data['MaxReleaseRate'])
        self.gflFactoryConfig.release_sleep = float(self.jobDescript.data['ReleaseSleep'])
        self.gflFactoryConfig.log_stats = glideFactoryMonitoring.condorLogSummary()
        self.gflFactoryConfig.rrd_stats = glideFactoryMonitoring.FactoryStatusData(logfiles=self.logFiles)
        self.gflFactoryConfig.rrd_stats.base_dir = self.monitorDir


        # Add cleaners for the user log directories
        for username in self.frontendDescript.get_all_usernames():
            user_log_dir = self.gflFactoryConfig.get_client_log_dir(self.name,
                                                                    username)
            self.logFiles.add_dir_to_cleanup(
                username,
                user_log_dir,
                "(job\..*\.out)|(job\..*\.err)",
                float(self.glideinDescript.data['JobLogRetentionMaxDays']),
                float(self.glideinDescript.data['JobLogRetentionMinDays']),
                float(self.glideinDescript.data['JobLogRetentionMaxMBs']))

            self.logFiles.add_dir_to_cleanup(
                username,
                user_log_dir,
                "(condor_activity_.*\.log)|(condor_activity_.*\.log.ftstpk)|(submit_.*\.log)",
                float(self.glideinDescript.data['CondorLogRetentionMaxDays']),
                float(self.glideinDescript.data['CondorLogRetentionMinDays']),
                float(self.glideinDescript.data['CondorLogRetentionMaxMBs']))

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

        #glideFactoryLib.log_files = self.logFiles
        glideFactoryMonitoring.monitoringConfig = self.monitoringConfig
        glideFactoryInterface.factoryConfig = self.gfiFactoryConfig
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
            frontend_allow_list = self.jobDescript.data['AllowedVOs'].split(',')
            for entry in frontend_allow_list:
                entry_part = entry.split(":");
                if (entry_part[0] in self.securityList):
                    self.securityList[entry_part[0]].append(entry_part[1]);
                else:
                    self.securityList[entry_part[0]] = [entry_part[1]];
        self.allowedProxySource = self.glideinDescript.data['AllowedJobProxySource'].split(',')


    def loadDowntimes(self):
        """
        Load the downtime info for this entry
        """

        self.downtimes = glideFactoryDowntimeLib.DowntimeFile(self.glideinDescript.data['DowntimesFile'])
        self.downtimes.checkDowntime(entry=self.name)
        self.jobAttributes.data['GLIDEIN_Downtime_Comment'] = self.downtimes.downtime_comment


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

        self.setDowntime(factory_in_downtime)

        # This one is used for stats advertized in the ClassAd
        self.gflFactoryConfig.client_stats = glideFactoryMonitoring.condorQStats()
        # These two are used to write the history to disk
        self.gflFactoryConfig.qc_stats = glideFactoryMonitoring.condorQStats()
        self.gflFactoryConfig.client_internals = {}
        self.gflFactoryConfig.log_stats.reset()


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
            return glideFactoryLib.getCondorQData(self.name, None,
                                                  self.scheddName)
        except Exception, e:
            self.logFiles.logActivity("Schedd %s not responding, skipping"%self.scheddName)
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            self.logFiles.logWarning("getCondorQData failed, traceback: %s"%string.join(tb,''))
            raise e


    def glideinsWithinLimits(self, condorQ):
        """
        Check the condorQ info and see we are within limits

        @rtype: boolean
        @return: True if glideins are in limits and we can submit more
        """


        # Check current state of the queue and initialize all entry limits

        # Flag that says whether or not we can submit any more
        can_submit_glideins = True

        # Initialize entry and frontend limit dicts
        self.glideinTotals = glideFactoryLib.GlideinTotals(
                                 self.name, self.frontendDescript,
                                 self.jobDescript, condorQ,
                                 logfiles=self.logFiles)

        # Check if entry has exceeded max idle
        if self.glideinTotals.has_entry_exceeded_max_idle():
            self.logFiles.logWarning("Entry %s has hit the limit for idle glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        # Check if entry has exceeded max glideins
        if can_submit_glideins and self.glideinTotals.has_entry_exceeded_max_glideins():
            self.logFiles.logWarning("Entry %s has hit the limit for total glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        # Check if entry has exceeded max held
        if can_submit_glideins and self.glideinTotals.has_entry_exceeded_max_held():
            self.logFiles.logWarning("Entry %s has hit the limit for held glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        return can_submit_glideins


    def advertise(self, factory_in_downtime):
        """
        Advertises the glidefactory and the glidefactoryclient classads.

        @type factory_in_downtime: boolean
        @param factory_in_downtime: factory in the downtimes file
        """

        self.loadContext()
        pub_key_obj = self.glideinDescript.data['PubKeyObj']

        self.gflFactoryConfig.client_stats.finalizeClientMonitor()

        current_qc_total = self.gflFactoryConfig.client_stats.get_total()

        glidein_monitors = {}
        for w in current_qc_total:
            for a in current_qc_total[w]:
                glidein_monitors['Total%s%s'%(w,a)]=current_qc_total[w][a]
        try:
            # Make copy of job attributes so can override the validation
            # downtime setting with the true setting of the entry 
            # (not from validation)
            myJobAttributes = self.jobAttributes.data.copy()
            myJobAttributes['GLIDEIN_In_Downtime'] = factory_in_downtime
            glideFactoryInterface.advertizeGlidein(
                self.gflFactoryConfig.factory_name,
                self.gflFactoryConfig.glidein_name,
                self.name, self.gflFactoryConfig.supported_signtypes,
                myJobAttributes, self.jobParams.data.copy(),
                glidein_monitors.copy(), pub_key_obj, self.allowedProxySource)
        except:
            self.logFiles.logWarning("Advertising entry '%s' failed"%self.name)
            tb = traceback.format_exception(sys.exc_info()[0],
                                            sys.exc_info()[1],
                                            sys.exc_info()[2])
            self.logFiles.logWarning("Exception: %s" % tb)


        # Advertise the monitoring, use the downtime found in
        # validation of the credentials
        monitor_job_attrs = self.jobAttributes.data.copy()
        advertizer = \
            glideFactoryInterface.MultiAdvertizeGlideinClientMonitoring(
                self.gflFactoryConfig.factory_name,
                self.gflFactoryConfig.glidein_name,
                self.name, monitor_job_attrs)

        current_qc_data = self.gflFactoryConfig.client_stats.get_data()
        #self.logFiles.logActivity("=======================================")
        #self.logFiles.logActivity(self.gflFactoryConfig.client_internals)
        #self.logFiles.logActivity("---------------------------------------")
        #self.logFiles.logActivity(current_qc_data)
        #self.logFiles.logActivity("=======================================")
        for client_name in current_qc_data:
            client_qc_data = current_qc_data[client_name]
            if client_name not in self.gflFactoryConfig.client_internals:
                self.logFiles.logWarning("Client '%s' has stats, but no classad! Ignoring." % client_name)
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
            advertizer.do_advertize()
        except:
            self.logFiles.logWarning("Advertize of monitoring failed")

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

        self.logFiles.logActivity("Computing log_stats diff for %s" % self.name)
        self.logFiles.logDebug("Computing log_stats diff for %s" % self.name)
        self.gflFactoryConfig.log_stats.computeDiff()
        self.logFiles.logActivity("log_stats diff computed")
        self.logFiles.logDebug("log_stats diff computed")

        self.logFiles.logActivity("Writing log_stats for %s" % self.name)
        self.logFiles.logDebug("Writing log_stats for %s" % self.name)
        self.gflFactoryConfig.log_stats.write_file()
        self.logFiles.logActivity("log_stats written")
        self.logFiles.logDebug("log_stats written")

        self.gflFactoryConfig.qc_stats.finalizeClientMonitor()
        self.logFiles.logActivity("Writing qc_stats for %s" % self.name)
        self.logFiles.logDebug("Writing qc_stats for %s" % self.name)
        self.gflFactoryConfig.qc_stats.write_file()
        self.logFiles.logActivity("qc_stats written")
        self.logFiles.logDebug("qc_stats written")

        self.logFiles.logActivity("Writing rrd_stats for %s" % self.name)
        self.logFiles.logDebug("Writing rrd_stats for %s" % self.name)
        self.gflFactoryConfig.rrd_stats.writeFiles()
        self.logFiles.logActivity("rrd_stats written")
        self.logFiles.logDebug("rrd_stats written")

        #self.logFiles.logDebug("ARTIFICIALLY SLEEPING ...")
        #import time
        #time.sleep(120)
        #self.logFiles.logDebug("ARTIFICIALLY SLEEPING ... DONE")
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


    def loadPostWorkState(self, post_work_info):
        """
        Load the post work state from the pickled info
        
        @type post_work_info: dict
        @param post_work_info: Picked state after doing work
        """

        self.gflFactoryConfig.client_stats = post_work_info['client_stats']
        self.gflFactoryConfig.qc_stats = post_work_info['qc_stats']
        self.gflFactoryConfig.rrd_stats = post_work_info['rrd_stats']
        self.gflFactoryConfig.client_internals = post_work_info['client_internals']
        # Load info for latest log_stats correctly
        self.gflFactoryConfig.log_stats.data = post_work_info['log_stats']['data']
        self.gflFactoryConfig.log_stats.updated = post_work_info['log_stats']['updated']
        self.gflFactoryConfig.log_stats.updated_year = post_work_info['log_stats']['updated_year']
        self.gflFactoryConfig.log_stats.stats_diff = post_work_info['log_stats']['stats_diff']
        self.gflFactoryConfig.log_stats.files_updated = post_work_info['log_stats']['files_updated']
        self.setLogStatsOldStatsData(post_work_info['log_stats']['old_stats_data'])
        self.setLogStatsCurrentStatsData(post_work_info['log_stats']['current_stats_data'])
    
# class Entry

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

def check_and_perform_work(factory_in_downtime, group_name, entry, work):
    """
    Check if we need to do the work and then do the work. Called by child
    process per entry

    @type factory_in_downtime: boolean
    @param factory_in_downtime: Flag if factory is in downtime

    @type group_name: boolean
    @param group_name: Name of the factory

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

    #
    # STEP: CHECK THAT GLIDEINS ARE WITING ALLOWED LIMITS
    #
    can_submit_glideins = entry.glideinsWithinLimits(condorQ)

    # Consider downtimes and see if we can submit glideins
    all_security_names = set()
    done_something = 0
    entry.loadWhitelist()
    entry.loadDowntimes()
    # Variable to identify if frontend or sec_class is in downtime
    in_downtime = factory_in_downtime

    #
    # STEP: Process every work one at a time
    #

    for work_key in work:
        if not is_str_safe(work_key):
            # may be used to write files... make sure it is reasonable
            entry.logFiles.logWarning("Request name '%s' not safe. Skipping request"%work_key)
            continue #skip request

        # merge work and default params
        params = work[work_key]['params']
        decrypted_params = work[work_key]['params_decrypted']

        # add default values if not defined
        for k in entry.jobParams.data.keys():
            if k not in params:
                params[k] = entry.jobParams.data[k]

        try:
            client_int_name = work[work_key]['internals']["ClientName"]
            client_int_req = work[work_key]['internals']["ReqName"]
        except:
            client_int_name = "DummyName"
            client_int_req = "DummyReq"

        if not is_str_safe(client_int_name):
            # may be used to write files... make sure it is reasonable
            entry.log_files.logWarning("Client name '%s' not safe. Skipping request"%client_int_name)
            continue #skip request

        #
        # STEP: DOWNTIME AND FRONTEND/SECURITY_CLASS WHITELISTING CALCULATION
        #

        # Check whether the frontend is in the whitelist of the entry
        client_security_name = decrypted_params.get('SecurityName',
                                                    client_int_name)

        if ( (entry.frontendWhitelist == "On") and
             (client_security_name not in entry.securityList) ):
            entry.logFiles.logWarning("Client name '%s' not in whitelist. Preventing glideins from %s "% (client_security_name,client_int_name))
            in_downtime=True

        # Check if proxy passing is compatible with allowed_proxy_source
        if ( ('x509_proxy' in decrypted_params) or
             ('x509_proxy_0' in decrypted_params) ):
            if 'frontend' not in entry.allowedProxySource:
                entry.logFiles.logWarning("Client %s provided proxy, but cannot use it. Skipping request"%client_int_name)
                continue #skip request

            client_expected_identity = entry.frontendDescript.get_identity(client_security_name)
            if client_expected_identity is None:
                entry.logFiles.logWarning("Client %s (secid: %s) not in white list. Skipping request"%(client_int_name,client_security_name))
                continue #skip request

            client_authenticated_identity = work[work_key]['internals']["AuthenticatedIdentity"]
            if client_authenticated_identity!=client_expected_identity:
                # silently drop... like if we never read it in the first place
                # this is compatible with what the frontend does
                entry.logFiles.logWarning("Client %s (secid: %s) is not coming from a trusted source; AuthenticatedIdentity %s!=%s. Skipping for security reasons."%(client_int_name,client_security_name,client_authenticated_identity,client_expected_identity))
                continue #skip request

        else:
            if 'factory' not in entry.allowedProxySource:
                entry.logFiles.logWarning("Client %s did not provide a proxy, but cannot use factory one. Skipping request"%client_int_name)
                continue #skip request

        x509_proxies = X509Proxies(entry.frontendDescript, client_security_name)

        if 'x509_proxy' in decrypted_params:
            if decrypted_params['x509_proxy'] is None:
                entry.logFiles.logWarning("Could not decrypt x509_proxy for %s, skipping request"%client_int_name)
                continue #skip request

            # This old style protocol does not support SecurityName, use default
            # Cannot check against a security class downtime since will never
            # exist in the config
            x509_proxy_security_class = "none"

            x509_proxy_username = x509_proxies.get_username(x509_proxy_security_class)
            if x509_proxy_username is None:
                entry.logFiles.logWarning("No mapping for security class %s of x509_proxy for %s, skipping and trying the others"%(x509_proxy_security_class,client_int_name))
                continue # cannot map, skip proxy

            try:
                x509_proxy_fname = glideFactoryLib.update_x509_proxy_file(
                                       entry.name, x509_proxy_username,
                                       work_key, decrypted_params['x509_proxy'],
                                       logfiles=entry.logFiles)
            except:
                entry.logFiles.logWarning("Failed to update x509_proxy using usename %s for client %s, skipping request"%(x509_proxy_username,client_int_name))
                continue # skip request

            x509_proxies.add_fname(x509_proxy_security_class,
                                   'main', x509_proxy_fname)

        elif 'x509_proxy_0' in decrypted_params:
            if 'nr_x509_proxies' not in decrypted_params:
                entry.logFiles.logWarning("Could not determine number of proxies for %s, skipping request"%client_int_name)
                continue #skip request
            try:
                nr_x509_proxies = int(decrypted_params['nr_x509_proxies'])
            except:
                entry.logFiles.logWarning("Invalid number of proxies for %s, skipping request"%client_int_name)
                continue # skip request
            # If the whitelist mode is on, then set downtime to true
            # We will set it to false in the loop if a security class passes the test
            if (entry.frontendWhitelist == "On"):
                prev_downtime = in_downtime
                in_downtime = True

            # Set security class downtime flag
            security_class_downtime_found = False

            for i in range(nr_x509_proxies):
                if decrypted_params['x509_proxy_%i'%i] is None:
                    entry.logFiles.logWarning("Could not decrypt x509_proxy_%i for %s, skipping and trying the others"%(i,client_int_name))
                    continue #skip proxy
                if 'x509_proxy_%i_identifier'%i not in decrypted_params:
                    entry.logFiles.logWarning("No identifier for x509_proxy_%i for %s, skipping and trying the others"%(i,client_int_name))
                    continue #skip proxy
                x509_proxy = decrypted_params['x509_proxy_%i'%i]
                x509_proxy_identifier = decrypted_params['x509_proxy_%i_identifier'%i]

                if not is_str_safe(x509_proxy_identifier):
                    # may be used to write files... make sure it is reasonable
                    entry.logFiles.logWarning("Identifier for x509_proxy_%i for %s is not safe ('%s), skipping and trying the others"%(i,client_int_name,x509_proxy_identifier))
                    continue #skip proxy

                x509_proxy_security_class = decrypted_params.get(
                                             'x509_proxy_%i_security_class'%i,
                                              x509_proxy_identifier)

                # Check security class for downtime
                entry.logFiles.logActivity("Checking downtime for frontend %s security class: %s (entry %s)."%(client_security_name, x509_proxy_security_class,entry.name))
                in_sec_downtime = ( (entry.downtimes.checkDowntime(
                                        entry="factory",
                                        frontend=client_security_name,
                                        security_class=x509_proxy_security_class)) or
                                    (entry.downtimes.checkDowntime(
                                         entry=entry.name,
                                         frontend=client_security_name,
                                         security_class=x509_proxy_security_class)) )

                if (in_sec_downtime):
                    entry.logFiles.logWarning("Security Class %s is currently in a downtime window for Entry: %s. Skipping proxy %s."%(x509_proxy_security_class,entry.name, x509_proxy_identifier))
                    security_class_downtime_found = True
                    # Cannot use proxy for submission but entry is not in
                    # downtime since other proxies may map to valid
                    # security classes
                    continue

                # Deny Frontend from entering glideins if the whitelist
                # does not have its security class (or "All" for everyone)
                if ( (entry.frontendWhitelist == "On") and
                     (entry.isClientInWhitelist(client_security_name)) ):
                    if entry.isSecurityClassAllowed(client_security_name,
                                                    x509_proxy_security_class):
                        in_downtime = prev_downtime
                        entry.logFiles.logDebug("Security test passed for : %s %s "%(entry.name, x509_proxy_security_class))
                    else:
                        entry.logFiles.logWarning("Security class not in whitelist, skipping (%s %s) "%(client_security_name,x509_proxy_security_class))

                x509_proxy_username = x509_proxies.get_username(x509_proxy_security_class)
                if x509_proxy_username is None:
                    entry.logFiles.logWarning("No mapping for security class %s of x509_proxy_%i for %s (secid: %s), skipping and trying the others"%(x509_proxy_security_class,i,client_int_name,client_security_name))
                    # Cannot map, skip proxy
                    continue

                try:
                    x509_proxy_fname = glideFactoryLib.update_x509_proxy_file(
                                           entry.name, x509_proxy_username,
                                           "%s_%s"%(work_key,
                                                    x509_proxy_identifier),
                                           x509_proxy, logfiles=entry.logFiles)
                except RuntimeError,e:
                    entry.logFiles.logWarning("Failed to update x509_proxy_%i using usename %s for client %s, skipping request"%(i,x509_proxy_username,client_int_name))
                    entry.logFiles.logDebug("Failed to update x509_proxy_%i using usename %s for client %s: %s"%(i,x509_proxy_username,client_int_name,e))
                    continue # skip request
                except:
                    tb = traceback.format_exception(sys.exc_info()[0],
                                                    sys.exc_info()[1],
                                                    sys.exc_info()[2])
                    entry.logFiles.logWarning("Failed to update x509_proxy_%i using usename %s for client %s, skipping request"%(i,x509_proxy_username,client_int_name))
                    entry.logFiles.logDebug("Failed to update x509_proxy_%i using usename %s for client %s: Exception %s"%(i,x509_proxy_username,client_int_name,string.join(tb,'')))
                    continue # skip request

                x509_proxies.add_fname(x509_proxy_security_class,
                                       x509_proxy_identifier,
                                       x509_proxy_fname)

            if x509_proxies.count_fnames<1:
                entry.logFiles.logWarning("No good proxies for %s, skipping request"%client_int_name)
                continue #skip request
        else:
            # no proxy passed, use factory one
            # Cannot check against a security class downtime since will never exist in the config
            x509_proxy_security_class = "factory"

            x509_proxy_username = x509_proxies.get_username(x509_proxy_security_class)
            if x509_proxy_username is None:
                entry.logFiles.logWarning("No mapping for security class %s for %s (secid: %s), skipping frontend"%(x509_proxy_security_class,client_int_name,client_security_name))
                continue # cannot map, frontend

            x509_proxies.add_fname(x509_proxy_security_class,'factory',
                                   os.environ['X509_USER_PROXY']) # use the factory one

            # Check if this entry point has a whitelist
            # If it does, then make sure that this frontend is in it.
            if ((entry.frontendWhitelist == "On") and 
                (entry.isClientInWhiteList(client_security_name)) and 
                (not entry.isSecurityClassAllowed(client_security_name,
                                                  x509_proxy_security_class))):
                entry.logFiles.logWarning("Client %s not allowed to use entry point. Marking as in downtime (security class %s) "%(client_security_name,x509_proxy_security_class))
                in_downtime=True

        entry.setDowntime(in_downtime)
        entry.gflFactoryConfig.qc_stats.set_downtime(in_downtime)

        #
        # STEP: CHECK IF CLEANUP OF IDLE GLIDEINS IS REQUIRED
        #

        remove_excess = work[work_key]['requests'].get('RemoveExcess', 'NO')

        if 'IdleGlideins' in work[work_key]['requests']:
            # malformed, if no IdleGlideins
            try:
                idle_glideins = int(work[work_key]['requests']['IdleGlideins'])
            except ValueError, e:
                entry.logFiles.logWarning("Client %s provided an invalid ReqIdleGlideins: '%s' not a number. Skipping request"%(client_int_name,work[work_key]['requests']['IdleGlideins']))
                continue #skip request

            if 'MaxRunningGlideins' in work[work_key]['requests']:
                try:
                    max_running = int(work[work_key]['requests']['MaxRunningGlideins'])
                except ValueError, e:
                    entry.logFiles.logWarning("Client %s provided an invalid ReqMaxRunningGlideins: '%s' not a number. Skipping request"%(client_int_name,work[work_key]['requests']['MaxRunningGlideins']))
                    continue #skip request
            else:
                max_running = int(entry.jobDescript.data['MaxRunning'])

            # Validate that project id is supplied when required
            # (as specified in the rsl string)

            if entry.jobDescript.data.has_key('GlobusRSL'):
                if 'TG_PROJECT_ID' in entry.jobDescript.data['GlobusRSL']:
                    if 'ProjectId' in decrypted_params:
                        project_id = decrypted_params['ProjectId']
                        # just add to params for now, not a security issue
                        # this may change when we implement the new protocol
                        # with the auth types and trust domains
                        params['ProjectId'] = project_id
                    else:
                        # project id is required, cannot service request
                        entry.logFiles.logActivity("Client '%s' did not specify a Project Id in the request, this is required by entry %s, skipping "%(client_int_name, entry.name))
                        continue

            # If we got this far, it was because we were able to
            # successfully update all the proxies in the request
            # If we already have hit our limits checked at beginning of this 
            # method and logged there, we can't submit.  
            # We still need to check/update all the other request credentials
            # and do cleanup.
            # We'll set idle glideins to zero if hit max or in downtime. 
            if in_downtime or not can_submit_glideins:
                idle_glideins=0

            if 'URL' in work[work_key]['web']:
                try:
                    client_web_url = work[work_key]['web']['URL']
                    client_signtype = work[work_key]['web']['SignType']
                    client_descript = work[work_key]['web']['DescriptFile']
                    client_sign = work[work_key]['web']['DescriptSign']

                    if 'GroupName' in work[work_key]['internals']:
                        client_group = work[work_key]['internals']['GroupName']
                        client_group_web_url = work[work_key]['web']['GroupURL']
                        client_group_descript = work[work_key]['web']['GroupDescriptFile']
                        client_group_sign = work[work_key]['web']['GroupDescriptSign']
                        client_web = glideFactoryLib.ClientWeb(
                                         client_web_url, client_signtype,
                                         client_descript, client_sign,
                                         client_group, client_group_web_url,
                                         client_group_descript,
                                         client_group_sign)
                    else:
                        # new style, but without a group (basic frontend)
                        client_web = glideFactoryLib.ClientWebNoGroup(
                                         client_web_url, client_signtype,
                                         client_descript, client_sign)
                except:
                    # malformed classad, skip
                    glideFactoryLib.log_files.logWarning("Malformed classad for client %s, skipping"%work_key)
                    continue
            else:
                # old style
                client_web = None

            x509_proxy_security_classes = x509_proxies.fnames.keys()
            # Sort to have consistent logging
            x509_proxy_security_classes.sort() 
            for x509_proxy_security_class in x509_proxy_security_classes:
                # submit each security class independently
                # split the request proportionally between them

                x509_proxy_frac = 1.0*len(x509_proxies.fnames[x509_proxy_security_class])/x509_proxies.count_fnames

                # Round up if a client requests a non splittable number,
                # worse for him.
                # Expect no issues in real world as the most reasonable
                # use case has a single proxy_class per client name
                idle_glideins_pc = int(math.ceil(idle_glideins*x509_proxy_frac))
                max_running_pc = int(math.ceil(max_running*x509_proxy_frac))

                # Should log here or in perform_work
                glideFactoryLib.logWorkRequest(client_int_name, 
                                               client_security_name,
                                               x509_proxy_security_class,
                                               idle_glideins, max_running,
                                               work[work_key], x509_proxy_frac,
                                               logfiles=entry.logFiles)

                all_security_names.add((client_security_name,
                                        x509_proxy_security_class))

                entry_condorQ = glideFactoryLib.getQProxSecClass(
                                    condorQ, client_int_name,
                                    x509_proxy_security_class)

                # Map the identity to a frontend:sec_class for tracking totals
                frontend_name = "%s:%s" % \
                    (entry.frontendDescript.get_frontend_name(client_expected_identity), x509_proxy_security_class)

                done_something += perform_work(
                                      entry, entry_condorQ, work_key,
                                      client_int_name, client_security_name, 
                                      x509_proxy_security_class, client_int_req,
                                      in_downtime, remove_excess,
                                      idle_glideins_pc, max_running_pc,
                                      x509_proxies.fnames[x509_proxy_security_class],
                                      x509_proxies.get_username(x509_proxy_security_class),
                                      entry.glideinTotals, frontend_name,
                                      client_web, params)

        else:
            # It is malformed and should be skipped
            entry.logFiles.logWarning("Malformed classad for client %s, skipping"%work_key)

    if done_something == 0:
        entry.logFiles.logActivity("Sanitizing glideins for entry %s" % entry.name)
        glideFactoryLib.sanitizeGlideinsSimple(condorQ, logfiles=entry.logFiles)

    entry.logFiles.logActivity("all_security_names = %s" % all_security_names)

    for sec_el in all_security_names:
        try:
            #glideFactoryLib.factoryConfig.rrd_stats.getData("%s_%s" % sec_el)
            entry.gflFactoryConfig.rrd_stats.getData("%s_%s" % sec_el)
        except glideFactoryLib.condorExe.ExeError,e:
            # Never fail for monitoring. Just log
            entry.logFiles.logWarning("get_RRD_data failed: %s" % e)
            tb = traceback.format_exception(sys.exc_info()[0],
                                            sys.exc_info()[1],
                                            sys.exc_info()[2])
            entry.logFiles.logWarning("Traceback: %s"%string.join(tb,''))
        except:
            # Never fail for monitoring. Just log
            entry.logFiles.logWarning("get_RRD_data failed: error unknown")
            tb = traceback.format_exception(sys.exc_info()[0],
                                            sys.exc_info()[1],
                                            sys.exc_info()[2])
            entry.logFiles.logWarning("Traceback: %s"%string.join(tb,''))

    return done_something


###############################################################################

def perform_work(entry, condorQ, client_name, client_int_name,
                 client_security_name, x509_proxy_security_class,
                 client_int_req, in_downtime, remove_excess, idle_glideins,
                 max_running, x509_proxy_fnames, x509_proxy_username,
                 glidein_totals, frontend_name, client_web, params):
    """
    Perform the work (Submit glideins)

    @type entry: glideFactoryEntry.Entry
    @param entry: Entry object

    @type condorQ: condorMonitor.CondorQ
    @param condorQ: Information about the jobs in condor_schedd

    @type client_name: string
    @param client_name: Name of the client

    @type client_int_name: string
    @param client_in_name: Internal name of the client

    @type client_securty_name: string
    @param client_security_name: Security name of the client

    @type x509_proxy_security_class: string
    @param x509_proxy_security_class: x509 proxy's security class

    @type client_int_req: string
    @param client_int_req: client_int_req

    @type in_downtime: boolean
    @param in_downtime: Downtime flag

    @type remove_excess: boolean
    @param remove_excess: Flag if frontend wants us to remove excess glideins

    @type idle_glideins: int
    @param idle_glideins: Number of idle glideins

    @type max_running: int
    @param max_running: Maximum number of running glideins

    @type x509_proxy_fnames: string
    @param x509_proxy_fnames: x509 proxy file

    @type x509_proxy_username: string
    @param x509_proxy_username: x509 proxy username

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

    entry.gflFactoryConfig.client_internals[client_int_name] = \
        {"CompleteName":client_name, "ReqName":client_int_req}

    condor_pool = params.get('GLIDEIN_Collector', None)
    condorStatus = None

    x509_proxy_keys = x509_proxy_fnames.keys()
    # Randomize so I don't favour any proxy over another
    random.shuffle(x509_proxy_keys)

    # find out the users it is using
    log_stats = {}
    log_stats[x509_proxy_username+":"+client_int_name] = \
        glideFactoryLogParser.dirSummaryTimingsOut(
            entry.gflFactoryConfig.get_client_log_dir(entry.name,
                                                      x509_proxy_username),
            entry.logDir, client_int_name, x509_proxy_username)
    # should not need privsep for reading logs
    log_stats[x509_proxy_username+":"+client_int_name].load()

    glideFactoryLib.logStats(condorQ, condorStatus, client_int_name,
                             client_security_name, x509_proxy_security_class,
                             logfiles=entry.logFiles)
    client_log_name = glideFactoryLib.secClass2Name(client_security_name,
                                                    x509_proxy_security_class)
    entry.gflFactoryConfig.log_stats.logSummary(client_log_name, log_stats)

    # use the extended params for submission
    proxy_fraction = 1.0/len(x509_proxy_keys)

    # I will shuffle proxies around, so I may as well round up all of them
    idle_glideins_pproxy = int(math.ceil(idle_glideins*proxy_fraction))
    max_glideins_pproxy = int(math.ceil(max_running*proxy_fraction))

    # not reducing the held, as that is effectively per proxy, not per request
    nr_submitted=0
    for x509_proxy_id in x509_proxy_keys:
        nr_submitted += glideFactoryLib.keepIdleGlideins(
                            condorQ, client_int_name, in_downtime,
                            remove_excess, idle_glideins_pproxy,
                            max_glideins_pproxy, glidein_totals, frontend_name,
                            x509_proxy_id, x509_proxy_fnames[x509_proxy_id],
                            x509_proxy_username, x509_proxy_security_class,
                            client_web, params, entry.logFiles)

    if nr_submitted>0:
        entry.logFiles.logActivity("Submitted %s glideins" % nr_submitted)
        # We submitted something
        return 1

    #glideFactoryLib.log_files.logActivity("Work done")
    return 0


############################################################

# only allow simple strings
def is_str_safe(s):
    for c in s:
        if not c in ('._-@'+string.ascii_letters+string.digits):
            return False
    return True

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
        glideFactoryLib.log_files.logDebug("IOError in writeFile in descript2XML")

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
