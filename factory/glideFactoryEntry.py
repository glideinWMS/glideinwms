#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This is the main of the glideinFactoryEntry
#
# Arguments:
#   $1 = poll period (in seconds)
#   $2 = advertize rate (every $2 loops)
#   $3 = glidein submit_dir
#   $4 = entry name
#
# Author:
#   Igor Sfiligoi (Sep 15th 2006 - as glideFactory.py)
#   Igor Sfiligoi (Apr 9th 2007 - as glideFactoryEntry.py)
#

import signal
import os,os.path,sys,fcntl
import traceback
import time,string,math
import copy,random
import sets
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

        self.monitoringConfig = glideFactoryMonitoring.MonitoringConfig()
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
        self.gflFactoryConfig.rrd_stats = glideFactoryMonitoring.FactoryStatusData()

        
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

        glideFactoryLib.log_files = self.logFiles
        glideFactoryMonitoring.monitoringConfig = self.monitoringConfig
        glideFactoryInterface.factoryConfig = self.gfiFactoryConfig
        glideFactoryLib.factoryConfig = self.gflFactoryConfig


    def loadWhitelist(self):
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
        self.downtimes = glideFactoryDowntimeLib.DowntimeFile(self.glideinDescript.data['DowntimesFile'])
        self.jobAttributes.data['GLIDEIN_Downtime_Comment'] = self.downtimes.downtime_comment


    def isClientInWhitelist(self, client_sec_name):
        return (client_sec_name in self.securityList)


    def isSecurityClassAllowed(self, client_sec_name, proxy_sec_class):
        return ((proxy_sec_class in self.securityList[client_sec_name]) or 
                ("All" in self.securityList[client_sec_name]))


    def isInDowntime(self):
        """
        Check the downtime file to find out if we are in downtime
        """
        return self.downtimes.checkDowntime(entry=self.name)


    def setDowntime(self, downtime_flag):
        """
        Check if we are in downtime and set info accordingly
        """

        self.jobAttributes.data['GLIDEIN_In_Downtime'] = (downtime_flag or self.isInDowntime())
           

    def initIteration(self, factory_in_downtime):
        """
        Perform the reseting of stats as required before every iteration
        """

        self.setDowntime(factory_in_downtime)

        # This one is used for stats advertized in the ClassAd
        self.gflFactoryConfig.client_stats = glideFactoryMonitoring.condorQStats()
        # These two are used to write the history to disk
        self.gflFactoryConfig.qc_stats = glideFactoryMonitoring.condorQStats()
        self.gflFactoryConfig.client_internals = {}


    def unsetInDowntime(self):
        del self.jobAttributes.data['GLIDEIN_In_Downtime']


    def queryQueuedGlideins(self):
        """
        Query WMS schedd and get glideins info. Raise in case of failures.
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

        # Check current state of the queue and initialize all entry limits

        # Flag that says whether or not we can submit any more
        can_submit_glideins = True

        # Initialize entry and frontend limit dicts
        self.glideinTotals = glideFactoryLib.GlideinTotals(
                                 self.name, 
                                 self.frontendDescript, 
                                 self.jobDescript,
                                 condorQ)

        # Check if entry has exceeded max idle
        if self.glideinTotals.has_entry_exceeded_max_idle():
            self.logFiles.logWarning("Entry %s has hit the limit for idle glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        # Check if entry has exceeded max glideins
        if can_submit_glideins and
           self.glideinTotals.has_entry_exceeded_max_glideins():
            self.logFiles.logWarning("Entry %s has hit the limit for total glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        # Check if entry has exceeded max held
        if can_submit_glideins and
           self.glideinTotals.has_entry_exceeded_max_held():
            self.logFiles.logWarning("Entry %s has hit the limit for held glideins, cannot submit any more" % self.name)
            can_submit_glideins = False

        return can_submit_glideins
    


def check_and_perform_work(factory_in_downtime, group_name, entry, work):
    """
    Check if we need to do the work and then do the work
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
    all_security_names = sets.Set()
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
        if ('x509_proxy' in decrypted_params) or 
           ('x509_proxy_0' in decrypted_params):
            if 'frontend' not in allowed_proxy_source:
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
            if 'factory' not in allowed_proxy_source:
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
                                       entry_name, x509_proxy_username,
                                       work_key, decrypted_params['x509_proxy'])
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
                in_sec_downtime = (entry.downtimes.checkDowntime(entry="factory", frontend=client_security_name, security_class=x509_proxy_security_class)) or 
                                  (entry.downtimes.checkDowntime(entry=entry.name, frontend=client_security_name, security_class=x509_proxy_security_class))

                if (in_sec_downtime):
                    entry.logFiles.logWarning("Security Class %s is currently in a downtime window for Entry: %s. Skipping proxy %s."%(x509_proxy_security_class,entry.name, x509_proxy_identifier))
                    security_class_downtime_found = True
                    # Cannot use proxy for submission but entry is not in
                    # downtime since other proxies may map to valid
                    # security classes
                    continue
                    
                # Deny Frontend from entering glideins if the whitelist
                # does not have its security class (or "All" for everyone)
                if (entry.frontendWhitelist == "On") and
                   (entry.isClientInWhitelist(client_security_name)):
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
                                           x509_proxy)
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
            if (frontend_whitelist == "On") and 
               (entry.isClientInWhiteList(client_security_name)) and 
               (not entry.isSecurityClassAllowed(client_security_name,
                                                 x509_proxy_security_class)):
                entry.logFiles.logWarning("Client %s not allowed to use entry point. Marking as in downtime (security class %s) "%(client_security_name,x509_proxy_security_class))
                in_downtime=True

        entry.setDowntime(in_downtime):
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
                if 'TG_PROJECT_ID' in jobDescript.data['GlobusRSL']:
                    if 'ProjectId' in decrypted_params:
                        project_id = decrypted_params['ProjectId']
                        # just add to params for now, not a security issue
                        # this may change when we implement the new protocol
                        # with the auth types and trust domains
                        params['ProjectId'] = project_id
                    else:
                        # project id is required, cannot service request
                        entry.logFiles.logActivity("Client '%s' did not specify a Project Id in the request, this is required by entry %s, skipping "%(client_int_name, jobDescript.data['EntryName']))
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
                                               work[work_key], x509_proxy_frac)
            
                all_security_names.add((client_security_name,
                                        x509_proxy_security_class))

                entry_condorQ = glideFactoryLib.getQProxSecClass(
                                    condorQ, client_int_name,
                                    x509_proxy_security_class)
                
                # Map the identity to a frontend:sec_class for tracking totals
                frontend_name = "%s:%s" % (frontendDescript.get_frontend_name(client_expected_identity),
                                           x509_proxy_security_class)

                done_something += perform_work(
                                      entry, entry_condorQ, work_key,
                                      client_int_name, client_security_name, 
                                      x509_proxy_security_class, client_int_req,
                                      in_downtime, remove_excess,
                                      idle_glideins_pc, max_running_pc,
                                      x509_proxies.fnames[x509_proxy_security_class],
                                      x509_proxies.get_username(x509_proxy_security_class),
                                      glidein_totals, frontend_name,
                                      client_web, params)
                
        else:
            # It is malformed and should be skipped
            entry.logFiles.logWarning("Malformed classad for client %s, skipping"%work_key)

    if done_something == 0:
        entry.logFiles.logActivity("Sanitizing glideins for entry %s" % entry.name)
        glideFactoryLib.sanitizeGlideinsSimple(condorQ)

    for sec_el in all_security_names:
        try:
            glideFactoryLib.factoryConfig.rrd_stats.getData("%s_%s" % sec_el)
        except glideFactoryLib.condorExe.ExeError,e:
            entry.logFiles.logWarning("get_RRD_data failed: %s" % e)
            # Never fail for monitoring. Just log
            pass
        except:
            entry.logFiles.logWarning("get_RRD_data failed: error unknown")
            # Never fail for monitoring. Just log
            pass

    return done_something



#############

def perform_work(entry, condorQ, client_name, client_int_name,
                 client_security_name, x509_proxy_security_class,
                 client_int_req, in_downtime,remove_excess, idle_glideins,
                 max_running, x509_proxy_fnames, x509_proxy_username,
                 glidein_totals, frontend_name, client_web, params):
    """
    Perform the work (Submit glideins)
    """
            
    glideFactoryLib.factoryConfig.client_internals[client_int_name]={"CompleteName":client_name,"ReqName":client_int_req}

    condor_pool = params.get('GLIDEIN_Collector', None)
    condorStatus = None

    x509_proxy_keys = x509_proxy_fnames.keys()
    # Randomize so I don't favour any proxy over another
    random.shuffle(x509_proxy_keys)

    # find out the users it is using
    log_stats = {}
    log_stats[x509_proxy_username+":"+client_int_name] = \
        glideFactoryLogParser.dirSummaryTimingsOut(
            glideFactoryLib.factoryConfig.get_client_log_dir(
                entry.name, x509_proxy_username),
            entry.logDir, client_int_name, x509_proxy_username)
    # should not need privsep for reading logs
    log_stats[x509_proxy_username+":"+client_int_name].load()

    glideFactoryLib.logStats(condorQ, condorStatus, client_int_name,
                             client_security_name, x509_proxy_security_class)
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
        nr_submitted + =glideFactoryLib.keepIdleGlideins(
                            condorQ, client_int_name, in_downtime,
                            remove_excess, idle_glideins_pproxy,
                            max_glideins_pproxy, glidein_totals, frontend_name,
                            x509_proxy_id, x509_proxy_fnames[x509_proxy_id],
                            x509_proxy_username, x509_proxy_security_class,
                            client_web, params)
    
    if nr_submitted>0:
        entry.logFiles.logActivity("Submitted %s glideins" % nr_submitted)
        # We submitted something
        return 1
   
    #glideFactoryLib.log_files.logActivity("Work done")
    return 0
    




















############################################################
def check_parent(parent_pid, glideinDescript, jobDescript):
    """Check to make sure that we aren't an orphaned process.  If Factory
    daemon has died, then clean up after ourselves and kill ourselves off.

    @type parent_pid: int
    @param parent_pid: the pid for the Factory daemon
    @type glideinDescript: glideFactoryConfig.GlideinDescript
    @param glideinDescript: Object that encapsulates glidein.descript in the Factory root directory
    @type jobDescript: glideFactoryConfig.JobDescript
    @param jobDescript: Object that encapsulates job.descript in the entry directory

    @raise KeyboardInterrupt: Raised when the Factory daemon cannot be found
    """
    if os.path.exists('/proc/%s'%parent_pid):
        return # parent still exists, we are fine
    
    glideFactoryLib.log_files.logActivity("Parent died, exit.")    

    # there is nobody to clean up after ourselves... do it here
    glideFactoryLib.log_files.logActivity("Deadvertize myself")
    
    try:
        glideFactoryInterface.deadvertizeGlidein(glideinDescript.data['FactoryName'],	 
                                                 glideinDescript.data['GlideinName'],	 
                                                 jobDescript.data['EntryName'])	 
    except:
        glideFactoryLib.log_files.logWarning("Failed to deadvertize myself")
    try:
        glideFactoryInterface.deadvertizeAllGlideinClientMonitoring(glideinDescript.data['FactoryName'],	 
                                                                    glideinDescript.data['GlideinName'],	 
                                                                    jobDescript.data['EntryName'])	 
    except:
        glideFactoryLib.log_files.logWarning("Failed to deadvertize my monitoring")

    raise KeyboardInterrupt,"Parent died"


############################################################
def perform_work_old(entry_name,
                 condorQ,
                 client_name,client_int_name,client_security_name,x509_proxy_security_class,client_int_req,
                 in_downtime,remove_excess,
                 idle_glideins,max_running,
                 jobDescript,
                 x509_proxy_fnames,x509_proxy_username,
                 glidein_totals, frontend_name,
                 client_web,
                 params):
            
    glideFactoryLib.factoryConfig.client_internals[client_int_name]={"CompleteName":client_name,"ReqName":client_int_req}

    if params.has_key("GLIDEIN_Collector"):
        condor_pool=params["GLIDEIN_Collector"]
    else:
        condor_pool=None
    

    #glideFactoryLib.log_files.logActivity("QueryS (%s,%s,%s,%s,%s)"%(glideFactoryLib.factoryConfig.factory_name,glideFactoryLib.factoryConfig.glidein_name,entry_name,client_name,schedd_name))

    # Temporary disable queries to the collector
    # Not really used by anybody, so let reduce the load
    #try:
    #    condorStatus=glideFactoryLib.getCondorStatusData(entry_name,client_name,condor_pool)
    #except:
    if 1:
        condorStatus=None # this is not fundamental information, can live without
    #glideFactoryLib.log_files.logActivity("Work")

    x509_proxy_keys=x509_proxy_fnames.keys()
    random.shuffle(x509_proxy_keys) # randomize so I don't favour any proxy over another

    # find out the users it is using
    log_stats={}
    log_stats[x509_proxy_username+":"+client_int_name]=glideFactoryLogParser.dirSummaryTimingsOut(glideFactoryLib.factoryConfig.get_client_log_dir(entry_name,x509_proxy_username),
                                                                              glideFactoryLib.log_files.log_dir,
                                                                              client_int_name,x509_proxy_username)
    # should not need privsep for reading logs
    log_stats[x509_proxy_username+":"+client_int_name].load()

    glideFactoryLib.logStats(condorQ,condorStatus,client_int_name,client_security_name,x509_proxy_security_class)
    client_log_name=glideFactoryLib.secClass2Name(client_security_name,x509_proxy_security_class)
    glideFactoryLib.factoryConfig.log_stats.logSummary(client_log_name,log_stats)

    # use the extended params for submission
    proxy_fraction=1.0/len(x509_proxy_keys)

    # I will shuffle proxies around, so I may as well round up all of them
    idle_glideins_pproxy=int(math.ceil(idle_glideins*proxy_fraction))
    max_glideins_pproxy=int(math.ceil(max_running*proxy_fraction))

    # not reducing the held, as that is effectively per proxy, not per request
    nr_submitted=0
    for x509_proxy_id in x509_proxy_keys:
        nr_submitted+=glideFactoryLib.keepIdleGlideins(condorQ,client_int_name,
                                                       in_downtime, remove_excess,
                                                       idle_glideins_pproxy, max_glideins_pproxy, glidein_totals, frontend_name,
                                                       x509_proxy_id,x509_proxy_fnames[x509_proxy_id],x509_proxy_username,x509_proxy_security_class,
                                                       client_web,params)
    
    if nr_submitted>0:
        #glideFactoryLib.log_files.logActivity("Submitted")
        return 1 # we submitted something
   
    #glideFactoryLib.log_files.logActivity("Work done")
    return 0
    

############################################################
# only allow simple strings
def is_str_safe(s):
    for c in s:
        if not c in ('._-@'+string.ascii_letters+string.digits):
            return False
    return True

############################################################
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

###
def find_and_perform_work(in_downtime, glideinDescript, frontendDescript, jobDescript, jobAttributes, jobParams):
    """
    Finds work requests from the WMS collector, validates credentials, and
    requests glideins. If an entry is in downtime, requested glideins is zero.
    
    @type in_downtime:  boolean
    @param in_downtime:  True if entry is in downtime
    @type glideinDescript:  dict
    @param glideinDescript:  factory glidein config values
    @type frontendDescript:  dict 
    @param frontendDescript:  security mappings for frontend identities, security classes, and usernames for privsep
    @type jobDescript:  dict
    @param jobDescript:  entry config values
    @type jobAttributes:  dict  
    @param jobAttributes:  entry attributes that are published in the classad
    @type jobParams:  dict
    @param jobParams:  entry parameters that are passed to the glideins
    
    @return: returns a value greater than zero if work was done.
    """
    
    entry_name=jobDescript.data['EntryName']
    pub_key_obj=glideinDescript.data['PubKeyObj']
    old_pub_key_obj = glideinDescript.data['OldPubKeyObj']

    # Get information about which VOs to allow for this entry point.
    # This will be a comma-delimited list of pairs
    # vofrontendname:security_class,vofrontend:sec_class, ...
    frontend_whitelist=jobDescript.data['WhitelistMode']
    security_list={};
    if (frontend_whitelist == "On"):
        frontend_allowed=jobDescript.data['AllowedVOs']
        frontend_allow_list=frontend_allowed.split(',');
        for entry in frontend_allow_list:
            entry_part=entry.split(":");
            if (security_list.has_key(entry_part[0])):
                security_list[entry_part[0]].append(entry_part[1]);
            else:
                security_list[entry_part[0]]=[entry_part[1]];
   
    allowed_proxy_source=glideinDescript.data['AllowedJobProxySource'].split(',')
    glideFactoryLib.factoryConfig.client_stats.set_downtime(in_downtime)
    glideFactoryLib.factoryConfig.qc_stats.set_downtime(in_downtime)
    
    #glideFactoryLib.log_files.logActivity("Find work")
    work = glideFactoryInterface.findWork(
               glideFactoryLib.factoryConfig.factory_name,
               glideFactoryLib.factoryConfig.glidein_name,
               entry_name,
               glideFactoryLib.factoryConfig.supported_signtypes,
               pub_key_obj,allowed_proxy_source)
    
    glideFactoryLib.log_files.logActivity("Found %s tasks to work on using existing factory key." % len(work))

    # If old key is valid, find the work using old key as well and append it
    # to existing work dictionary
    if (old_pub_key_obj is not None):
        work_oldkey = {}
        # still using the old key in this cycle
        glideFactoryLib.log_files.logActivity("Old factory key is still valid. Trying to find work using old factory key.")
        work_oldkey = glideFactoryInterface.findWork(
                   glideFactoryLib.factoryConfig.factory_name,
                   glideFactoryLib.factoryConfig.glidein_name, entry_name,
                   glideFactoryLib.factoryConfig.supported_signtypes,
                   old_pub_key_obj, allowed_proxy_source)
        glideFactoryLib.log_files.logActivity("Found %s tasks to work on using old factory key" % len(work_oldkey))

        # Merge the work_oldkey with work
        for w in work_oldkey.keys():
            if work.has_key(w):
                # This should not happen but still as a safegaurd warn
                glideFactoryLib.log_files.logActivity("Work task for %s exists using existing key and old key. Ignoring the work from old key." % w)
                glideFactoryLib.log_files.logError("Work task for %s exists using existing key and old key. Ignoring the work from old key." % w)
                continue
            work[w] = work_oldkey[w]

    if len(work.keys())==0:
        glideFactoryLib.log_files.logActivity("No work found")
        return 0 # nothing to be done

    glideFactoryLib.log_files.logActivity("Found %s total tasks to work on" % len(work))

    #glideFactoryLib.log_files.logActivity("Perform work")
    schedd_name=jobDescript.data['Schedd']

    try:
        condorQ=glideFactoryLib.getCondorQData(entry_name,None,schedd_name)
    except glideFactoryLib.condorExe.ExeError,e:
        glideFactoryLib.log_files.logActivity("Schedd %s not responding, skipping"%schedd_name)
        glideFactoryLib.log_files.logWarning("getCondorQData failed: %s"%e)
        # protect and exit
        return 0
    except:
        glideFactoryLib.log_files.logActivity("Schedd %s not responding, skipping"%schedd_name)
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logWarning("getCondorQData failed, traceback: %s"%string.join(tb,''))
        # protect and exit
        return 0
    
    # ===========  Check current state of the queue and initialize all entry limits  ==========
    
    # Set a flag that says whether or not we can submit any more (we still need to update credentials)
    can_submit_glideins = True
    
    # Initialize entry and frontend limit dicts
    glidein_totals = glideFactoryLib.GlideinTotals(entry_name, frontendDescript, jobDescript, condorQ)  
    
    if glidein_totals.has_entry_exceeded_max_idle():
        glideFactoryLib.log_files.logWarning("Entry %s has hit the limit for idle glideins, cannot submit any more" % entry_name)
        can_submit_glideins = False
        
    if can_submit_glideins and glidein_totals.has_entry_exceeded_max_glideins():
        glideFactoryLib.log_files.logWarning("Entry %s has hit the limit for total glideins, cannot submit any more" % entry_name)
        can_submit_glideins = False
        
    if can_submit_glideins and glidein_totals.has_entry_exceeded_max_held():
        glideFactoryLib.log_files.logWarning("Entry %s has hit the limit for held glideins, cannot submit any more" % entry_name)
        can_submit_glideins = False

    all_security_names=sets.Set()

    done_something=0
    for work_key in work.keys():
        if not is_str_safe(work_key):
            # may be used to write files... make sure it is reasonable
            glideFactoryLib.log_files.logWarning("Request name '%s' not safe. Skipping request"%work_key)
            continue #skip request

        # merge work and default params
        params=work[work_key]['params']
        decrypted_params=work[work_key]['params_decrypted']

        # add default values if not defined
        for k in jobParams.data.keys():
            if not (k in params.keys()):
                params[k]=jobParams.data[k]

        try:
            client_int_name=work[work_key]['internals']["ClientName"]
            client_int_req=work[work_key]['internals']["ReqName"]
        except:
            client_int_name="DummyName"
            client_int_req="DummyReq"

        if not is_str_safe(client_int_name):
            # may be used to write files... make sure it is reasonable
            glideFactoryLib.log_files.logWarning("Client name '%s' not safe. Skipping request"%client_int_name)
            continue #skip request

        # Check whether the frontend is on the whitelist for the 
        # Entry point.
        if decrypted_params.has_key('SecurityName'):
                client_security_name=decrypted_params['SecurityName']
        else:
                # backwards compatibility
                client_security_name=client_int_name

        if ((frontend_whitelist == "On") and (not security_list.has_key(client_security_name))):
            glideFactoryLib.log_files.logWarning("Client name '%s' not in whitelist. Preventing glideins from %s "% (client_security_name,client_int_name))
            in_downtime=True
            
        # Get factory, entry, and security class downtimes
        factory_downtimes=glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data['DowntimesFile'])
        
        # Check if proxy passing is compatible with allowed_proxy_source
        if decrypted_params.has_key('x509_proxy') or decrypted_params.has_key('x509_proxy_0'):
            if not ('frontend' in allowed_proxy_source):
                glideFactoryLib.log_files.logWarning("Client %s provided proxy, but cannot use it. Skipping request"%client_int_name)
                continue #skip request

            client_expected_identity=frontendDescript.get_identity(client_security_name)
            if client_expected_identity is None:
                glideFactoryLib.log_files.logWarning("Client %s (secid: %s) not in white list. Skipping request"%(client_int_name,client_security_name))
                continue #skip request
            
            client_authenticated_identity=work[work_key]['internals']["AuthenticatedIdentity"]

            if client_authenticated_identity!=client_expected_identity:
                # silently drop... like if we never read it in the first place
                # this is compatible with what the frontend does
                glideFactoryLib.log_files.logWarning("Client %s (secid: %s) is not coming from a trusted source; AuthenticatedIdentity %s!=%s. Skipping for security reasons."%(client_int_name,client_security_name,client_authenticated_identity,client_expected_identity))
                continue #skip request

        else:
            if not ('factory' in allowed_proxy_source):
                glideFactoryLib.log_files.logWarning("Client %s did not provide a proxy, but cannot use factory one. Skipping request"%client_int_name)
                continue #skip request

        x509_proxies=X509Proxies(frontendDescript,client_security_name)
        if decrypted_params.has_key('x509_proxy'):
            if decrypted_params['x509_proxy'] is None:
                glideFactoryLib.log_files.logWarning("Could not decrypt x509_proxy for %s, skipping request"%client_int_name)
                continue #skip request

            # This old style protocol does not support SecurityName, use default
            # Cannot check against a security class downtime since will never exist in the config
            x509_proxy_security_class="none"
            
            x509_proxy_username=x509_proxies.get_username(x509_proxy_security_class)
            if x509_proxy_username is None:
                glideFactoryLib.log_files.logWarning("No mapping for security class %s of x509_proxy for %s, skipping and trying the others"%(x509_proxy_security_class,client_int_name))
                continue # cannot map, skip proxy

            try:
                x509_proxy_fname=glideFactoryLib.update_x509_proxy_file(entry_name,x509_proxy_username,work_key,decrypted_params['x509_proxy'])
            except:
                glideFactoryLib.log_files.logWarning("Failed to update x509_proxy using usename %s for client %s, skipping request"%(x509_proxy_username,client_int_name))
                continue # skip request
            
            x509_proxies.add_fname(x509_proxy_security_class,'main',x509_proxy_fname)
            
        elif decrypted_params.has_key('x509_proxy_0'):
            if not decrypted_params.has_key('nr_x509_proxies'):
                glideFactoryLib.log_files.logWarning("Could not determine number of proxies for %s, skipping request"%client_int_name)
                continue #skip request
            try:
                nr_x509_proxies=int(decrypted_params['nr_x509_proxies'])
            except:
                glideFactoryLib.log_files.logWarning("Invalid number of proxies for %s, skipping request"%client_int_name)
                continue # skip request
            # If the whitelist mode is on, then set downtime to true
            # We will set it to false in the loop if a security class passes the test
            if (frontend_whitelist=="On"):
                prev_downtime=in_downtime
                in_downtime=True
            
            # Set security class downtime flag
            security_class_downtime_found = False
            
            for i in range(nr_x509_proxies):
                if decrypted_params['x509_proxy_%i'%i] is None:
                    glideFactoryLib.log_files.logWarning("Could not decrypt x509_proxy_%i for %s, skipping and trying the others"%(i,client_int_name))
                    continue #skip proxy
                if not decrypted_params.has_key('x509_proxy_%i_identifier'%i):
                    glideFactoryLib.log_files.logWarning("No identifier for x509_proxy_%i for %s, skipping and trying the others"%(i,client_int_name))
                    continue #skip proxy
                x509_proxy=decrypted_params['x509_proxy_%i'%i]
                x509_proxy_identifier=decrypted_params['x509_proxy_%i_identifier'%i]

                if not is_str_safe(x509_proxy_identifier):
                    # may be used to write files... make sure it is reasonable
                    glideFactoryLib.log_files.logWarning("Identifier for x509_proxy_%i for %s is not safe ('%s), skipping and trying the others"%(i,client_int_name,x509_proxy_identifier))
                    continue #skip proxy

                if decrypted_params.has_key('x509_proxy_%i_security_class'%i):
                    x509_proxy_security_class=decrypted_params['x509_proxy_%i_security_class'%i]
                else:
                    x509_proxy_security_class=x509_proxy_identifier
                
                # Check security class for downtime
                glideFactoryLib.log_files.logActivity("Checking downtime for frontend %s security class: %s (entry %s)."%(client_security_name, x509_proxy_security_class,jobDescript.data['EntryName']))
                in_sec_downtime=(factory_downtimes.checkDowntime(entry="factory",frontend=client_security_name,security_class=x509_proxy_security_class) or factory_downtimes.checkDowntime(entry=jobDescript.data['EntryName'],frontend=client_security_name,security_class=x509_proxy_security_class))
                if (in_sec_downtime):
                    glideFactoryLib.log_files.logWarning("Security Class %s is currently in a downtime window for Entry: %s. Skipping proxy %s."%(x509_proxy_security_class,jobDescript.data['EntryName'], x509_proxy_identifier))
                    security_class_downtime_found = True
                    continue # cannot use proxy for submission but entry is not in downtime since other proxies may map to valid security classes
                    
                # Deny Frontend from entering glideins if the whitelist
                # does not have its security class (or "All" for everyone)
                if (frontend_whitelist == "On") and (security_list.has_key(client_security_name)):
                    if ((x509_proxy_security_class in security_list[client_security_name])or ("All" in security_list[client_security_name])):
                        in_downtime=prev_downtime
                        glideFactoryLib.log_files.logDebug("Security test passed for : %s %s "%(jobDescript.data['EntryName'],x509_proxy_security_class))
                    else:
                        glideFactoryLib.log_files.logWarning("Security class not in whitelist, skipping (%s %s) "%(client_security_name,x509_proxy_security_class))

                x509_proxy_username=x509_proxies.get_username(x509_proxy_security_class)
                if x509_proxy_username is None:
                    glideFactoryLib.log_files.logWarning("No mapping for security class %s of x509_proxy_%i for %s (secid: %s), skipping and trying the others"%(x509_proxy_security_class,i,client_int_name,client_security_name))
                    continue # cannot map, skip proxy

                try:
                    x509_proxy_fname=glideFactoryLib.update_x509_proxy_file(entry_name,x509_proxy_username,"%s_%s"%(work_key,x509_proxy_identifier),x509_proxy)
                except RuntimeError,e:
                    glideFactoryLib.log_files.logWarning("Failed to update x509_proxy_%i using usename %s for client %s, skipping request"%(i,x509_proxy_username,client_int_name))
                    glideFactoryLib.log_files.logDebug("Failed to update x509_proxy_%i using usename %s for client %s: %s"%(i,x509_proxy_username,client_int_name,e))
                    continue # skip request
                except:
                    tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                    sys.exc_info()[2])
                    glideFactoryLib.log_files.logWarning("Failed to update x509_proxy_%i using usename %s for client %s, skipping request"%(i,x509_proxy_username,client_int_name))
                    glideFactoryLib.log_files.logDebug("Failed to update x509_proxy_%i using usename %s for client %s: Exception %s"%(i,x509_proxy_username,client_int_name,string.join(tb,'')))
                    continue # skip request
                
                x509_proxies.add_fname(x509_proxy_security_class,x509_proxy_identifier,x509_proxy_fname)

            if x509_proxies.count_fnames<1:
                glideFactoryLib.log_files.logWarning("No good proxies for %s, skipping request"%client_int_name)
                continue #skip request
        else:
            # no proxy passed, use factory one
            # Cannot check against a security class downtime since will never exist in the config
            x509_proxy_security_class="factory"
            
            x509_proxy_username=x509_proxies.get_username(x509_proxy_security_class)
            if x509_proxy_username is None:
                glideFactoryLib.log_files.logWarning("No mapping for security class %s for %s (secid: %s), skipping frontend"%(x509_proxy_security_class,client_int_name,client_security_name))
                continue # cannot map, frontend

            x509_proxies.add_fname(x509_proxy_security_class,'factory',
                                   os.environ['X509_USER_PROXY']) # use the factory one
        
            # Check if this entry point has a whitelist
            # If it does, then make sure that this frontend is in it.
            if (frontend_whitelist == "On")and (security_list.has_key(client_security_name))and(not x509_proxy_security_class in security_list[client_security_name])and (not "All" in security_list[client_security_name]):
                glideFactoryLib.log_files.logWarning("Client %s not allowed to use entry point. Marking as in downtime (security class %s) "%(client_security_name,x509_proxy_security_class))
                in_downtime=True

        jobAttributes.data['GLIDEIN_In_Downtime']=in_downtime
        glideFactoryLib.factoryConfig.qc_stats.set_downtime(in_downtime)
       
        if work[work_key]['requests'].has_key('RemoveExcess'):
            remove_excess=work[work_key]['requests']['RemoveExcess']
        else:
            remove_excess='NO'            

        if work[work_key]['requests'].has_key('IdleGlideins'):
            # malformed, if no IdleGlideins
            try:
                idle_glideins=int(work[work_key]['requests']['IdleGlideins'])
            except ValueError, e:
                glideFactoryLib.log_files.logWarning("Client %s provided an invalid ReqIdleGlideins: '%s' not a number. Skipping request"%(client_int_name,work[work_key]['requests']['IdleGlideins']))
                continue #skip request
            
            if work[work_key]['requests'].has_key('MaxRunningGlideins'):
                try:
                    max_running=int(work[work_key]['requests']['MaxRunningGlideins'])
                except ValueError, e:
                    glideFactoryLib.log_files.logWarning("Client %s provided an invalid ReqMaxRunningGlideins: '%s' not a number. Skipping request"%(client_int_name,work[work_key]['requests']['MaxRunningGlideins']))
                    continue #skip request
            else:
                max_running=int(jobDescript.data['MaxRunning'])
            
            # Validate that project id is supplied when required (as specified in the rsl string)
            if jobDescript.data.has_key('GlobusRSL'):
                if 'TG_PROJECT_ID' in jobDescript.data['GlobusRSL']:
                    if decrypted_params.has_key('ProjectId'):
                        project_id = decrypted_params['ProjectId']
                        # just add to params for now, not a security issue
                        # this may change when we implement the new protocol with the auth types and trust domains
                        params['ProjectId'] = project_id
                    else:
                        # project id is required, cannot service request
                        glideFactoryLib.log_files.logActivity("Client '%s' did not specify a Project Id in the request, this is required by entry %s, skipping "%(client_int_name, jobDescript.data['EntryName']))
                        continue      
                              
            # If we got this far, it was because we were able to successfully update all the proxies in the request
            # If we already have hit our maximums (checked at beginning of this method and logged there), we can't submit.  
            # We still need to check/update all the other request credentials and do cleanup.
            # We'll set idle glideins to zero if hit max or in downtime. 
            if in_downtime or not can_submit_glideins:
                idle_glideins=0          

            if work[work_key]['web'].has_key('URL'):
                try:
                    client_web_url=work[work_key]['web']['URL']
                    client_signtype=work[work_key]['web']['SignType']
                    client_descript=work[work_key]['web']['DescriptFile']
                    client_sign=work[work_key]['web']['DescriptSign']

                    if work[work_key]['internals'].has_key('GroupName'):
                        client_group=work[work_key]['internals']['GroupName']
                        client_group_web_url=work[work_key]['web']['GroupURL']
                        client_group_descript=work[work_key]['web']['GroupDescriptFile']
                        client_group_sign=work[work_key]['web']['GroupDescriptSign']
                        client_web=glideFactoryLib.ClientWeb(client_web_url,
                                                             client_signtype,
                                                             client_descript,client_sign,
                                                             client_group,client_group_web_url,
                                                             client_group_descript,client_group_sign)
                    else:
                        # new style, but without a group (basic frontend)
                        client_web=glideFactoryLib.ClientWebNoGroup(client_web_url,
                                                                    client_signtype,
                                                                    client_descript,client_sign)
                except:
                    # malformed classad, skip
                    glideFactoryLib.log_files.logWarning("Malformed classad for client %s, skipping"%work_key)
                    continue
            else:
                # old style
                client_web=None

            x509_proxy_security_classes=x509_proxies.fnames.keys()
            x509_proxy_security_classes.sort() # sort to have consistent logging
            for x509_proxy_security_class in x509_proxy_security_classes:
                # submit each security class independently
                # split the request proportionally between them

                x509_proxy_frac=1.0*len(x509_proxies.fnames[x509_proxy_security_class])/x509_proxies.count_fnames

                # round up... if a client requests a non splittable number, worse for him
                # expect to not be a problem in real world as
                # the most reasonable use case has a single proxy_class per client name
                idle_glideins_pc=int(math.ceil(idle_glideins*x509_proxy_frac))
                max_running_pc=int(math.ceil(max_running*x509_proxy_frac))

                #
                # Should log here or in perform_work
                #
                glideFactoryLib.logWorkRequest(client_int_name,client_security_name,x509_proxy_security_class,
                                               idle_glideins, max_running,
                                               work[work_key],x509_proxy_frac)
            
                all_security_names.add((client_security_name,x509_proxy_security_class))

                entry_condorQ=glideFactoryLib.getQProxSecClass(condorQ,client_int_name,x509_proxy_security_class)
                
                # Map the above identity to a frontend:sec_class for tracking totals
                frontend_name = "%s:%s" % (frontendDescript.get_frontend_name(client_expected_identity), x509_proxy_security_class)

                done_something += perform_work(entry_name,entry_condorQ,
                                             work_key,client_int_name,client_security_name,x509_proxy_security_class,client_int_req,
                                             in_downtime,remove_excess,
                                             idle_glideins_pc,max_running_pc,
                                             jobDescript,x509_proxies.fnames[x509_proxy_security_class],x509_proxies.get_username(x509_proxy_security_class),
                                             glidein_totals, frontend_name,
                                             client_web,params)
                
        else: # it is malformed and should be skipped
            glideFactoryLib.log_files.logWarning("Malformed classad for client %s, skipping"%work_key)
        
    # Only do cleanup when no work (submit new glideins or remove excess) was done, work is the priority
    if done_something == 0: 
        glideFactoryLib.log_files.logActivity("Sanitizing glideins for entry %s" % entry_name)
        glideFactoryLib.sanitizeGlideinsSimple(condorQ)

    for sec_el in all_security_names:
        try:
            glideFactoryLib.factoryConfig.rrd_stats.getData("%s_%s"%sec_el)
        except glideFactoryLib.condorExe.ExeError,e:
            glideFactoryLib.log_files.logWarning("get_RRD_data failed: %s"%e)
            pass # never fail for monitoring... just log
        except:
            glideFactoryLib.log_files.logWarning("get_RRD_data failed: error unknown")
            pass # never fail for monitoring... just log
        

    return done_something

############################################################
def write_stats():
    """
    Calls the statistics functions to record and write
    stats for this iteration.

    There are several main types of statistics:

    log stats: That come from parsing the condor_activity
    and job logs.  This is computed every iteration 
    (in perform_work()) and diff-ed to see any newly 
    changed job statuses (ie. newly completed jobs)

    qc stats: From condor_q data.
    
    rrd stats: Used in monitoring statistics for javascript rrd graphs.
    """
    global log_rrd_thread,qc_rrd_thread
    
    glideFactoryLib.factoryConfig.log_stats.computeDiff()
    glideFactoryLib.factoryConfig.log_stats.write_file()
    glideFactoryLib.log_files.logActivity("log_stats written")
    glideFactoryLib.factoryConfig.qc_stats.finalizeClientMonitor()
    glideFactoryLib.factoryConfig.qc_stats.write_file()
    glideFactoryLib.log_files.logActivity("qc_stats written")
    glideFactoryLib.factoryConfig.rrd_stats.writeFiles()
    glideFactoryLib.log_files.logActivity("rrd_stats written")
    
    return

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
def advertize_myself(in_downtime,glideinDescript,jobDescript,jobAttributes,jobParams):
    """
    Advertises the entry (glidefactory) and the monitoring (glidefactoryclient) Classads.
    
    @type in_downtime:  boolean
    @param in_downtime:  setting of the entry (or factory) in the downtimes file
    @type glideinDescript:  dict
    @param glideinDescript:  factory glidein config values
    @type jobDescript:  dict
    @param jobDescript:  entry config values
    @type jobAttributes:  dict  
    @param jobAttributes:  entry attributes to be published in the classad
    @type jobParams:  dict
    @param jobParams:  entry parameters to be passed to the glideins
    """
    
    entry_name=jobDescript.data['EntryName']
    allowed_proxy_source=glideinDescript.data['AllowedJobProxySource'].split(',')
    pub_key_obj=glideinDescript.data['PubKeyObj']

    glideFactoryLib.factoryConfig.client_stats.finalizeClientMonitor()

    current_qc_total=glideFactoryLib.factoryConfig.client_stats.get_total()

    glidein_monitors={}
    for w in current_qc_total.keys():
        for a in current_qc_total[w].keys():
            glidein_monitors['Total%s%s'%(w,a)]=current_qc_total[w][a]
    try:
        # Make copy of job attributes so can override the validation downtime setting with the true setting of the entry (not from validation)
        myJobAttributes=jobAttributes.data.copy()
        myJobAttributes['GLIDEIN_In_Downtime']=in_downtime
        glideFactoryInterface.advertizeGlidein(glideFactoryLib.factoryConfig.factory_name,glideFactoryLib.factoryConfig.glidein_name,entry_name,
                                               glideFactoryLib.factoryConfig.supported_signtypes,
                                               myJobAttributes,jobParams.data.copy(),glidein_monitors.copy(),
                                               pub_key_obj,allowed_proxy_source)
    except:
        glideFactoryLib.log_files.logWarning("Advertize failed")

    # Advertise the monitoring, use the downtime found in validation of the credentials
    monitor_job_attrs = jobAttributes.data.copy()
    advertizer=glideFactoryInterface.MultiAdvertizeGlideinClientMonitoring(glideFactoryLib.factoryConfig.factory_name,glideFactoryLib.factoryConfig.glidein_name,entry_name,
                                                                           monitor_job_attrs)

    current_qc_data=glideFactoryLib.factoryConfig.client_stats.get_data()
    for client_name in current_qc_data.keys():
        client_qc_data=current_qc_data[client_name]
        if not glideFactoryLib.factoryConfig.client_internals.has_key(client_name):
            glideFactoryLib.log_files.logWarning("Client '%s' has stats, but no classad! Ignoring."%client_name)
            continue
        client_internals=glideFactoryLib.factoryConfig.client_internals[client_name]

        client_monitors={}
        for w in client_qc_data.keys():
            for a in client_qc_data[w].keys():
                if type(client_qc_data[w][a])==type(1): # report only numbers
                    client_monitors['%s%s'%(w,a)]=client_qc_data[w][a]

        try:
            fparams=current_qc_data[client_name]['Requested']['Parameters']
        except:
            fparams={}
        params=jobParams.data.copy()
        for p in fparams.keys():
            if p in params.keys(): # can only overwrite existing params, not create new ones
                params[p]=fparams[p]
        advertizer.add(client_internals["CompleteName"],client_name,client_internals["ReqName"],
                       params,client_monitors.copy())
        
    try:
        advertizer.do_advertize()
    except:
        glideFactoryLib.log_files.logWarning("Advertize of monitoring failed")
        

    return

############################################################
def iterate_one(do_advertize,in_downtime,
                glideinDescript,frontendDescript,jobDescript,jobAttributes,jobParams):
    
    done_something=0
    jobAttributes.data['GLIDEIN_In_Downtime']=in_downtime
    
    try:
        done_something = find_and_perform_work(in_downtime,glideinDescript,frontendDescript,jobDescript,jobAttributes,jobParams)
    except:
        glideFactoryLib.log_files.logWarning("Error occurred while trying to find and do work.  ")
        
    if do_advertize or done_something:
        glideFactoryLib.log_files.logActivity("Advertize")
        advertize_myself(in_downtime,glideinDescript,jobDescript,jobAttributes,jobParams)
    del jobAttributes.data['GLIDEIN_In_Downtime']
    
    return done_something

############################################################
def iterate(parent_pid, sleep_time, advertize_rate,
            glideinDescript, frontendDescript, jobDescript, jobAttributes, jobParams):
    """iterate function

    The main "worker" function for the Factory Entry.
    @todo: More description to come

    @type parent_pid: int
    @param parent_pid: the pid for the Factory daemon
    @type sleep_time: int
    @param sleep_time: The number of seconds to sleep between iterations
    @type advertise_rate: int
    @param advertise_rate: The rate at which advertising should occur (CHANGE ME... THIS IS NOT HELPFUL)
    @type glideinDescript: glideFactoryConfig.GlideinDescript
    @param glideinDescript: Object that encapsulates glidein.descript in the Factory root directory
    @type frontendDescript: glideFactoryConfig.FrontendDescript
    @param frontendDescript: Object that encapsulates frontend.descript in the Factory root directory
    @type jobDescript: glideFactoryConfig.JobDescript
    @param jobDescript: Object that encapsulates job.descript in the entry directory
    @type jobAttributes: glideFactoryConfig.JobAttributes
    @param jobAttributes: Object that encapsulates attributes.cfg in the entry directory
    @type jobParams: glideFactoryConfig.JobParams
    @param jobParams: Object that encapsulates params.cfg in the entry directory


    """
    is_first=1
    count=0;

    # Record the starttime so we know when to disable the use of old pub key
    starttime = time.time()
    # The grace period should be in the factory config. Use it to determine
    # the end of lifetime for the old key object. Hardcoded for now to 30 mins.
    oldkey_gracetime = int(glideinDescript.data['OldPubKeyGraceTime'])
    oldkey_eoltime = starttime + oldkey_gracetime
    
    glideFactoryLib.factoryConfig.log_stats=glideFactoryMonitoring.condorLogSummary()
    glideFactoryLib.factoryConfig.rrd_stats = glideFactoryMonitoring.FactoryStatusData()
    factory_downtimes=glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data['DowntimesFile'])
    while 1:
        check_parent(parent_pid,glideinDescript,jobDescript)
        if ( (time.time() > oldkey_eoltime) and 
             (glideinDescript.data['OldPubKeyObj'] is not None) ):
            # Invalidate the use of factory's old key
            glideFactoryLib.log_files.logActivity("Retiring use of old key.")
            glideFactoryLib.log_files.logActivity("Old key was valid from %s to %s ie grace of ~%s sec" % (starttime,oldkey_eoltime,oldkey_gracetime))
            glideinDescript.data['OldPubKeyType'] = None
            glideinDescript.data['OldPubKeyObj'] = None

        in_downtime=(factory_downtimes.checkDowntime(entry="factory") or factory_downtimes.checkDowntime(entry=jobDescript.data['EntryName']))
        in_downtime_message=factory_downtimes.downtime_comment
        jobAttributes.data['GLIDEIN_Downtime_Comment']=in_downtime_message

        if in_downtime:
            glideFactoryLib.log_files.logActivity("Downtime iteration at %s" % time.ctime())
        else:
            glideFactoryLib.log_files.logActivity("Iteration at %s" % time.ctime())
        try:
            glideFactoryLib.factoryConfig.log_stats.reset()
            # This one is used for stats advertized in the ClassAd
            glideFactoryLib.factoryConfig.client_stats=glideFactoryMonitoring.condorQStats()
            # These two are used to write the history to disk
            glideFactoryLib.factoryConfig.qc_stats=glideFactoryMonitoring.condorQStats()
            glideFactoryLib.factoryConfig.client_internals = {}

            done_something=iterate_one(count==0,in_downtime,
                                       glideinDescript,frontendDescript,jobDescript,jobAttributes,jobParams)
            
            glideFactoryLib.log_files.logActivity("Writing stats")
            try:
                write_stats()
            except KeyboardInterrupt:
                raise # this is an exit signal, pass through
            except:
                # never fail for stats reasons!
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                glideFactoryLib.log_files.logWarning("Exception occurred: %s" % tb)                
        except KeyboardInterrupt:
            raise # this is an exit signal, pass through
        except:
            if is_first:
                raise
            else:
                # if not the first pass, just warn
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                glideFactoryLib.log_files.logWarning("Exception occurred: %s" % tb)                
                
        glideFactoryLib.log_files.cleanup()

        glideFactoryLib.log_files.logActivity("Sleep %is"%sleep_time)
        time.sleep(sleep_time)
        count=(count+1)%advertize_rate
        is_first=0
        
        
############################################################

def main(parent_pid, sleep_time, advertize_rate, startup_dir, entry_name):
    """GlideinFactoryEntry main function

    Setup logging, monitoring, and configuration information.  Starts the Entry
    main loop and handles cleanup at shutdown.

    @type parent_pid: int
    @param parent_pid: The pid for the Factory daemon
    @type sleep_time: int
    @param sleep_time: The number of seconds to sleep between iterations
    @type advertise_rate: int
    @param advertise_rate: The rate at which advertising should occur (CHANGE ME... THIS IS NOT HELPFUL)
    @type startup_dir: string
    @param startup_dir: The "home" directory for the entry.
    @type entry_name: string
    @param entry_name: The name of the entry as specified in the config file
    """
    startup_time=time.time()

    glideFactoryInterface.factoryConfig.lock_dir=os.path.join(startup_dir,"lock")

    glideFactoryMonitoring.monitoringConfig.monitor_dir=os.path.join(startup_dir,"monitor/entry_%s"%entry_name)

    os.chdir(startup_dir)
    glideinDescript=glideFactoryConfig.GlideinDescript()

    glideinDescript.load_pub_key()
    glideinDescript.load_old_rsa_key()
    if not (entry_name in string.split(glideinDescript.data['Entries'],',')):
        raise RuntimeError, "Entry '%s' not supported: %s"%(entry_name,glideinDescript.data['Entries'])

    log_dir=os.path.join(glideinDescript.data['LogDir'],"entry_%s"%entry_name)
    # Configure the process to use the proper LogDir as soon as you get the info
    glideFactoryLib.log_files=glideFactoryLib.LogFiles(log_dir,
                                                       float(glideinDescript.data['LogRetentionMaxDays']),
                                                       float(glideinDescript.data['LogRetentionMinDays']),
                                                       float(glideinDescript.data['LogRetentionMaxMBs']))
    glideFactoryMonitoring.monitoringConfig.config_log(log_dir,
                                                       float(glideinDescript.data['SummaryLogRetentionMaxDays']),
                                                       float(glideinDescript.data['SummaryLogRetentionMinDays']),
                                                       float(glideinDescript.data['SummaryLogRetentionMaxMBs']))

    glideFactoryInterface.factoryConfig.warning_log=glideFactoryLib.log_files.warning_log

    glideFactoryMonitoring.monitoringConfig.my_name="%s@%s"%(entry_name,glideinDescript.data['GlideinName'])

    frontendDescript=glideFactoryConfig.FrontendDescript()

    jobDescript=glideFactoryConfig.JobDescript(entry_name)
    jobAttributes=glideFactoryConfig.JobAttributes(entry_name)
    jobParams=glideFactoryConfig.JobParams(entry_name)

    write_descript(entry_name,jobDescript,jobAttributes,jobParams,glideFactoryMonitoring.monitoringConfig.monitor_dir)

    # use config values to configure the factory
    glideFactoryLib.factoryConfig.config_whoamI(glideinDescript.data['FactoryName'],
                                                glideinDescript.data['GlideinName'])
    glideFactoryLib.factoryConfig.config_dirs(startup_dir,
                                              glideinDescript.data['LogDir'],
                                              glideinDescript.data['ClientLogBaseDir'],
                                              glideinDescript.data['ClientProxiesBaseDir'])
    
    glideFactoryLib.factoryConfig.max_submits=int(jobDescript.data['MaxSubmitRate'])
    glideFactoryLib.factoryConfig.max_cluster_size=int(jobDescript.data['SubmitCluster'])
    glideFactoryLib.factoryConfig.submit_sleep=float(jobDescript.data['SubmitSleep'])
    glideFactoryLib.factoryConfig.max_removes=int(jobDescript.data['MaxRemoveRate'])
    glideFactoryLib.factoryConfig.remove_sleep=float(jobDescript.data['RemoveSleep'])
    glideFactoryLib.factoryConfig.max_releases=int(jobDescript.data['MaxReleaseRate'])
    glideFactoryLib.factoryConfig.release_sleep=float(jobDescript.data['ReleaseSleep'])

    glideFactoryLib.log_files.add_dir_to_cleanup(None,glideFactoryLib.log_files.log_dir,
                                                 "(condor_activity_.*\.log\..*\.ftstpk)",
                                                 float(glideinDescript.data['CondorLogRetentionMaxDays']),
                                                 float(glideinDescript.data['CondorLogRetentionMinDays']),
                                                 float(glideinDescript.data['CondorLogRetentionMaxMBs']))
    # add cleaners for the user log directories
    for username in frontendDescript.get_all_usernames():
        user_log_dir=glideFactoryLib.factoryConfig.get_client_log_dir(entry_name,username)
        glideFactoryLib.log_files.add_dir_to_cleanup(username,user_log_dir,
                                                     "(job\..*\.out)|(job\..*\.err)",
                                                     float(glideinDescript.data['JobLogRetentionMaxDays']),
                                                     float(glideinDescript.data['JobLogRetentionMinDays']),
                                                     float(glideinDescript.data['JobLogRetentionMaxMBs']))
        glideFactoryLib.log_files.add_dir_to_cleanup(username,user_log_dir,
                                                     "(condor_activity_.*\.log)|(condor_activity_.*\.log.ftstpk)|(submit_.*\.log)",
                                                     float(glideinDescript.data['CondorLogRetentionMaxDays']),
                                                     float(glideinDescript.data['CondorLogRetentionMinDays']),
                                                     float(glideinDescript.data['CondorLogRetentionMaxMBs']))

    glideFactoryInterface.factoryConfig.advertise_use_tcp=(glideinDescript.data['AdvertiseWithTCP'] in ('True','1'))
    glideFactoryInterface.factoryConfig.advertise_use_multi=(glideinDescript.data['AdvertiseWithMultiple'] in ('True','1'))
    
    try:
        dir = os.path.dirname(os.path.dirname(sys.argv[0]))
        glideFactoryInterface.factoryConfig.glideinwms_version = glideinWMSVersion.GlideinWMSDistro(dir, 'checksum.factory').version()
    except:
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logWarning("Exception occured while trying to retrieve the glideinwms version. See debug log for more details.")
        glideFactoryLib.log_files.logDebug("Exception occurred while trying to retrieve the glideinwms version: %s" % tb)    


    # create lock file
    pid_obj=glideFactoryPidLib.EntryPidSupport(startup_dir,entry_name)
    
    # Force integrity checks on all condor operations
    glideFactoryLib.set_condor_integrity_checks()

    # start
    pid_obj.register(parent_pid)
    try:
        try:
            try:
                glideFactoryLib.log_files.logActivity("Starting up")
                iterate(parent_pid,
                        sleep_time,advertize_rate,
                        glideinDescript,frontendDescript,jobDescript,jobAttributes,jobParams)
            except KeyboardInterrupt:
                glideFactoryLib.log_files.logActivity("Received signal...exit")
            except:
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                glideFactoryLib.log_files.logWarning("Exception occurred: %s" % tb)
                raise
        finally:
            # no need to cleanup.. the parent should be doing it
            glideFactoryLib.log_files.logActivity("Dying")
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
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]),
         sys.argv[4], sys.argv[5])
 

