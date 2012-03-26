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
import os
import sys
import traceback
import time
import string
import math
import copy
import random
import sets
import logging
sys.path.append(os.path.join(sys.path[0], "../lib"))

import glideFactoryPidLib
import glideFactoryConfig
import glideFactoryLib
import glideFactoryMonitoring
import glideFactoryInterface
import glideFactoryLogParser
import glideFactoryDowntimeLib
import glideinWMSVersion
import glideFactoryCredentials

import logSupport
import cleanupSupport

# This declaration is not strictly needed - it is declared as global in main
# however, to make code clearer (hopefully), it is declared here to make it
# easy to see that log is a module level variable
log = None

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

    if os.path.exists('/proc/%s' % parent_pid):
        return # parent still exists, we are fine

    logSupport.log.info("Parent died, exit.")

    # there is nobody to clean up after ourselves... do it here
    logSupport.log.info("Deadvertize myself")

    # Attempt to deadvertise the entry classads
    try:
        glideFactoryInterface.deadvertizeGlidein(glideinDescript.data['FactoryName'],
                                                 glideinDescript.data['GlideinName'],
                                                 jobDescript.data['EntryName'])
    except:
        logSupport.log.exception("Failed to deadvertize myself")

    # Attempt to deadvertise the entry monitoring classads
    try:
        glideFactoryInterface.deadvertizeAllGlideinClientMonitoring(glideinDescript.data['FactoryName'],
                                                                    glideinDescript.data['GlideinName'],
                                                                    jobDescript.data['EntryName'])
    except:
        logSupport.log.exception("Failed to deadvertize my monitoring")
    
        
    try:
        glideFactoryInterface.deadvertizeGlobal(glideinDescript.data['FactoryName'],     
                                                 glideinDescript.data['GlideinName'])     
    except:
        logSupport.log.exception("Failed to deadvertize my global")

    raise KeyboardInterrupt, "Parent died"


############################################################
def perform_work(entry_name, condorQ,
                 client_name, client_int_name, client_security_name,
                 credential_security_class, client_int_req,
                 idle_glideins, max_glideins, remove_excess,
                 jobDescript, x509_proxy_fnames, credential_username,
                 identity_credentials, glidein_totals, frontend_name,
                 client_web, params):
    """
    Logs stats.  Determines how many idle glideins are needed per proxy.  Only used in the v2+ protocol.

    @type entry_name:  string
    @param entry_name:  name of the entry
    @type condorQ:  CondorQ object
    @param condorQ:  Condor queue filtered by security class
    @type client_name:  string
    @param client_name:  name of the frontend client
    @type client_int_name:  string
    @param client_int_name:  client name in the request
    @type client_security_name:  string
    @param client_security_name:  decrypted client security name in the request
    @type credential_security_class:  string
    @param credential_security_class:  security class this client and credential are mapped to
    @type client_int_req:  string
    @param client_int_req:  name of the request from the client
    @type idle_glideins:  int
    @param idle_glideins:  number of idle glideins requested
    @type max_glideins:  int
    @param max_glideins:  max number of glideins requested
    @type remove_excess:  string
    @param remove_excess:  passed from Frontend in the request, tells the factory what to do about excess glideins
    @type jobDescript:  dict
    @param jobDescript:  entry configuration values
    @type x509_proxy_fnames:  dict
    @param x509_proxy_fnames:  proxies for the associated security class
    @type credential_username:  string
    @param credential_username:  username to be used for submitting glideins (if not factory username, privsep is used)
    @type identity_credentials: dict
    @param identity_credentials: identity information passed by the frontend
    @type glidein_totals: GlideinTotals object
    @param glidein_totals: entry and frontend glidein counts
    @type frontend_name: string
    @param frontend_name: frontend name, used to map frontend totals in glidein_totals ("frontend:sec_class")
    @type client_web:   glideFactoryLib.ClientWeb 
    @param client_web:  client web values
    @type params:  dict
    @param params:  entry parameters to be passed to the glidein
    """

    glideFactoryLib.factoryConfig.client_internals[client_int_name] = {"CompleteName":client_name, "ReqName":client_int_req}

    x509_proxy_keys = x509_proxy_fnames.keys() 
    random.shuffle(x509_proxy_keys) # randomize so I don't favour any proxy over another, only matters if prob occurs mid-iteration

    # find out the users it is using
    log_stats = {}
    log_stats[credential_username+":"+client_int_name] = glideFactoryLogParser.dirSummaryTimingsOut(glideFactoryLib.factoryConfig.get_client_log_dir(entry_name, credential_username),
                                                                              logSupport.log_dir, client_int_name, credential_username)
    # should not need privsep for reading logs
    log_stats[credential_username+":"+client_int_name].load()
    glideFactoryLib.logStats(condorQ, client_int_name, client_security_name, credential_security_class)
    client_log_name = glideFactoryLib.secClass2Name(client_security_name, credential_security_class)
    glideFactoryLib.factoryConfig.log_stats.logSummary(client_log_name, log_stats) #@UndefinedVariable

    # use the extended params for submission
    proxy_fraction = 1.0 / len(x509_proxy_keys)

    # I will shuffle proxies around, so I may as well round up all of them
    idle_glideins_pproxy = int(math.ceil(idle_glideins * proxy_fraction))
    max_glideins_pproxy = int(math.ceil(max_glideins * proxy_fraction))

    # not reducing the held, as that is effectively per proxy, not per request
    nr_submitted = 0
    for x509_proxy_id in x509_proxy_keys:
        security_credentials = {}
        security_credentials['SubmitProxy'] = x509_proxy_fnames[x509_proxy_id]
        submit_credentials = glideFactoryCredentials.SubmitCredentials(credential_username, credential_security_class)
        submit_credentials.id = x509_proxy_id
        submit_credentials.security_credentials = security_credentials
        submit_credentials.identity_credentials = identity_credentials
        logSupport.log.info("Using v2+ protocol and credential %s" % submit_credentials.id)
        nr_submitted += glideFactoryLib.keepIdleGlideins(condorQ, client_int_name, 
                                                         idle_glideins_pproxy, max_glideins_pproxy, remove_excess,
                                                         submit_credentials, glidein_totals, frontend_name,
                                                         client_web, params)

    if nr_submitted > 0:
        return 1 # we submitted something, return immediately

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
    """
    I think this class is only used for the v2+ protocol
    """
    def __init__(self, frontendDescript, client_security_name):
        self.frontendDescript = frontendDescript
        self.client_security_name = client_security_name
        self.usernames = {}
        self.fnames = {}
        self.count_fnames = 0 # len of sum(fnames)

    # Return None, if cannot convert
    def get_username(self, x509_proxy_security_class):
        if not self.usernames.has_key(x509_proxy_security_class):
            # lookup only the first time
            x509_proxy_username = self.frontendDescript.get_username(self.client_security_name, x509_proxy_security_class)
            if x509_proxy_username == None:
                # but don't cache misses
                return None
            self.usernames[x509_proxy_security_class] = x509_proxy_username
        return self.usernames[x509_proxy_security_class][:]

    def add_fname(self, x509_proxy_security_class, x509_proxy_identifier, x509_proxy_fname):
        if not self.fnames.has_key(x509_proxy_security_class):
            self.fnames[x509_proxy_security_class] = {}
        self.fnames[x509_proxy_security_class][x509_proxy_identifier] = x509_proxy_fname
        self.count_fnames += 1

###
def find_and_perform_work(in_downtime, glideinDescript, frontendDescript, jobDescript, jobAttributes, jobParams):
    """
    Finds work requests from the WMS collector, validates security credentials, and requests glideins.  If an entry is
    in downtime, requested glideins is zero.

    @type in_downtime: boolean
    @param in_downtime: True if entry is in downtime
    @type glideinDescript:  dictionary
    @param glideinDescript: factory configuration values
    @type frontendDescript:  dictionary
    @param frontendDescript: frontend identity and security mappings
    @type jobDescript:  dictionary
    @param jobDescript: entry configuration values
    @type jobAttributes:  dictionary
    @param jobAttributes: entry attributes to be published
    @type jobParams:  dictionary
    @param jobParams: entry parameters that will be passed to the glideins

    @return: returns a value greater than zero if work was done.
    """

    # Get glidein and entry details
    schedd_name = jobDescript.data['Schedd']
    entry_name = jobDescript.data['EntryName']
    pub_key_obj = glideinDescript.data['PubKeyObj']
    auth_method = jobDescript.data['AuthMethod']
    old_pub_key_obj = glideinDescript.data['OldPubKeyObj']
    
    # Get the factory and entry downtimes
    factory_downtimes = glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data['DowntimesFile'])
    
    # Set downtime in the stats
    glideFactoryLib.factoryConfig.client_stats.set_downtime(in_downtime) #@UndefinedVariable
    # KEL - this line below is executed again later in this method - why do this twice if downtime can change?
    glideFactoryLib.factoryConfig.qc_stats.set_downtime(in_downtime) #@UndefinedVariable

    # ===========  Get queue data for all clients  ==========
    try:
        condorQ = glideFactoryLib.getCondorQData(entry_name, None, schedd_name)
    except glideFactoryLib.condorExe.ExeError, e:
        logSupport.log.info("Schedd %s not responding, skipping" % schedd_name)
        logSupport.log.exception("getCondorQData failed:" )
        # protect and exit
        return 0
    except:
        logSupport.log.info("Skipping schedd %s because unable to get queue data" % schedd_name)
        logSupport.log.exception("getCondorQData failed: " )
        # protect and exit
        return 0

    # Get information about which VOs to allow for this entry point.
    # This will be a comma-delimited list of pairs
    # vofrontendname:security_class,vofrontend:sec_class, ...
    frontend_whitelist = jobDescript.data['WhitelistMode']
    security_list = {}
    if (frontend_whitelist == "On"):
        frontend_allowed = jobDescript.data['AllowedVOs']
        frontend_allow_list = frontend_allowed.split(',')
        for entry in frontend_allow_list:
            entry_part = entry.split(":")
            if (security_list.has_key(entry_part[0])):
                security_list[entry_part[0]].append(entry_part[1])
            else:
                security_list[entry_part[0]] = [entry_part[1]]
                                
    # ===========  Check current state of the queue and initialize all entry limits  ==========
    
    # Set a flag that says whether or not we can submit any more (we still need to update credentials)
    can_submit_glideins = True
    
    # Initialize entry and frontend limit dicts
    glidein_totals = glideFactoryLib.GlideinTotals(entry_name, frontendDescript, jobDescript, condorQ)
    
    if glidein_totals.has_entry_exceeded_max_idle():
        logSupport.log.warning("Entry %s has hit the limit for idle glideins, cannot submit any more" % entry_name)
        can_submit_glideins = False
        
    if can_submit_glideins and glidein_totals.has_entry_exceeded_max_glideins():
        logSupport.log.warning("Entry %s has hit the limit for total glideins, cannot submit any more" % entry_name)
        can_submit_glideins = False
        
    if can_submit_glideins and glidein_totals.has_entry_exceeded_max_held():
        logSupport.log.warning("Entry %s has hit the limit for held glideins, cannot submit any more" % entry_name)
        can_submit_glideins = False
        
    # ===========  Finding work requests  ==========
    logSupport.log.info("Finding work")
    # Find requests that we have the key to decrypt
    additional_constraints = '((ReqPubKeyID=?="%s") && (ReqEncKeyCode=!=Undefined) && (ReqEncIdentity=!=Undefined))' % pub_key_obj.get_pub_key_id() 
    #logSupport.log.info("Find work")
    work = glideFactoryInterface.findWork(
               glideFactoryLib.factoryConfig.factory_name,
               glideFactoryLib.factoryConfig.glidein_name,
               entry_name,
               glideFactoryLib.factoryConfig.supported_signtypes,
               pub_key_obj,additional_constraints)
    
    logSupport.log.info("Found %s tasks to work on using existing factory key." % len(work))

    # If old key is valid, find the work using old key as well and append it
    # to existing work dictionary
    if (old_pub_key_obj != None):
        work_oldkey = {}
        # still using the old key in this cycle
        logSupport.log.info("Old factory key is still valid. Trying to find work using old factory key.")
        additional_constraints = '((ReqPubKeyID=?="%s") && (ReqEncKeyCode=!=Undefined) && (ReqEncIdentity=!=Undefined))' % old_pub_key_obj.get_pub_key_id() 
        work_oldkey = glideFactoryInterface.findWork(
                   glideFactoryLib.factoryConfig.factory_name,
                   glideFactoryLib.factoryConfig.glidein_name, 
                   entry_name,
                   glideFactoryLib.factoryConfig.supported_signtypes,
                   old_pub_key_obj,additional_constraints)
        logSupport.log.info("Found %s tasks to work on using old factory key" % len(work_oldkey))

        # Merge the work_oldkey with work
        for w in work_oldkey.keys():
            if work.has_key(w):
                # This should not happen but still as a safeguard warn
                logSupport.log.warning("Work task for %s exists using existing key and old key. Ignoring the work from old key." % w)
                continue
            work[w] = work_oldkey[w]

    if len(work.keys())==0:
        logSupport.log.info("No work found")
        return 0 # nothing to be done

    logSupport.log.info("Found %s total tasks to work on" % len(work))

    all_security_names=sets.Set()

    # ======= Process work requests ============
    logSupport.log.info("Validating requests and doing work")
    done_something = 0
    for work_key in work.keys():
            
        # Key name may be used to write files... make sure it is reasonable
        if not glideFactoryLib.is_str_safe(work_key):
            logSupport.log.warning("Request name '%s' not safe. Skipping request" % work_key)
            continue #skip request

        # merge work and default params
        params = work[work_key]['params']
        decrypted_params = work[work_key]['params_decrypted']

        # add default values if not defined
        for k in jobParams.data.keys():
            if not (k in params.keys()):
                params[k] = jobParams.data[k]

        # Set client name (i.e. frontend.group) and request (i.e. entry@glidein@factory) names
        try:
            client_int_name = work[work_key]['internals']["ClientName"]
            client_int_req = work[work_key]['internals']["ReqName"]
        except:
            logSupport.log.warning("Request %s not did not provide the client and/or request name. Skipping request" % work_key)
            continue #skip request
        
        if not glideFactoryLib.is_str_safe(client_int_name):
            # may be used to write files... make sure it is reasonable
            logSupport.log.warning("Client name '%s' not safe. Skipping request" % client_int_name)
            continue #skip request
        
        # Check request has the required credentials and nothing else
        try:
            logSupport.log.debug("Checking security credentials for client %s " % client_int_name)
            glideFactoryCredentials.check_security_credentials(auth_method, decrypted_params, client_int_name, jobDescript.data['EntryName'])
        except glideFactoryCredentials.CredentialError:
            # skip request
            logSupport.log.exception("Error checking credentials, skipping request: ")
            continue
            
        # ======== validate security and whitelist information ================
        # Check whether the frontend is on the whitelist for the entry point
        if decrypted_params.has_key('SecurityName'):
            client_security_name = decrypted_params['SecurityName']
        else:
            logSupport.log.warning("Client %s did not provide the security name, skipping request" % client_int_name)
            continue

        if frontend_whitelist == "On" and not security_list.has_key(client_security_name):
            logSupport.log.warning("Client name '%s' not in whitelist. Preventing glideins from %s " % (client_security_name, client_int_name))
            in_downtime = True        

        # Validate the client is who they say they are (using Condor AuthenticatedIdentity)
        client_expected_identity = frontendDescript.get_identity(client_security_name)
        if client_expected_identity == None:
            logSupport.log.warning("Client %s (secid: %s) not in white list. Skipping request" % (client_int_name, client_security_name))
            continue #skip request
    
        client_authenticated_identity = work[work_key]['internals']["AuthenticatedIdentity"]
    
        if client_authenticated_identity != client_expected_identity:
            # silently drop... like if we never read it in the first place
            # this is compatible with what the frontend does
            logSupport.log.warning("Client %s (secid: %s) is not coming from a trusted source; AuthenticatedIdentity %s!=%s. " \
                                "Skipping for security reasons." % (client_int_name, client_security_name,
                                                                    client_authenticated_identity, client_expected_identity))
            continue #skip request
                                 
        # ========= v2+ protocol ==============
        # Initialize credentials for each request
        security_credentials = {}       
        identity_credentials = {}   
        if decrypted_params.has_key('x509_proxy_0'):            
            
            if not ('grid_proxy' in auth_method):
                logSupport.log.warning("Client %s provided proxy, but a client supplied proxy is not allowed. Skipping bad request" % client_int_name)
                continue #skip request
        
            # Check if project id is required    
            if 'project_id' in auth_method:
                # Validate project id exists
                if decrypted_params.has_key('ProjectId'):
                    # just add to params for now, not a security issue
                    identity_credentials['ProjectId'] = decrypted_params['ProjectId']
                else:
                    # project id is required, cannot service request
                    logSupport.log.warning("Client '%s' did not specify a Project Id in the request, this is required by entry %s, skipping "%(client_int_name, jobDescript.data['EntryName']))
                    continue  
                           
            # Check if voms_attr required
            if 'voms_attr' in auth_method:
                # TODO determine how to verify voms attribute on a proxy
                pass   
                            
            x509_proxies = X509Proxies(frontendDescript, client_security_name)
            if not decrypted_params.has_key('nr_x509_proxies'):
                logSupport.log.warning("Could not determine number of proxies for %s, skipping request" % client_int_name)
                continue #skip request
            try:
                nr_x509_proxies = int(decrypted_params['nr_x509_proxies'])
            except:
                logSupport.log.warning("Invalid number of proxies for %s, skipping request" % client_int_name)
                continue # skip request
                
            # If the whitelist mode is on, then set downtime to true
            # We will set it to false in the loop if a security class passes the test
            if frontend_whitelist == "On":
                prev_downtime = in_downtime
                in_downtime = True                    
            
            # Set security class downtime flag
            security_class_downtime_found = False
            
            # Validate each proxy
            for i in range(nr_x509_proxies):
                # Get proxy params 
                if decrypted_params['x509_proxy_%i' % i] == None:
                    logSupport.log.warning("Could not decrypt x509_proxy_%i for %s, skipping and trying the others" % (i, client_int_name))
                    continue #skip proxy
                if not decrypted_params.has_key('x509_proxy_%i_identifier' % i):
                    logSupport.log.warning("No identifier for x509_proxy_%i for %s, skipping and trying the others" % (i, client_int_name))
                    continue #skip proxy
                x509_proxy = decrypted_params['x509_proxy_%i' % i]
                x509_proxy_identifier = decrypted_params['x509_proxy_%i_identifier' % i]
    
                # Make sure proxy id is safe to write files... make sure it is reasonable
                if not glideFactoryLib.is_str_safe(x509_proxy_identifier):
                    logSupport.log.warning("Identifier for x509_proxy_%i for %s is not safe ('%s), skipping and trying the others" % (i, client_int_name, x509_proxy_identifier))
                    continue #skip proxy
    
                # Check security class for downtime (in downtimes file)
                if decrypted_params.has_key('x509_proxy_%i_security_class' % i):
                    x509_proxy_security_class = decrypted_params['x509_proxy_%i_security_class' % i]
                else:
                    x509_proxy_security_class = x509_proxy_identifier
                logSupport.log.info("Checking downtime for frontend %s security class: %s (entry %s)." % (client_security_name, x509_proxy_security_class, jobDescript.data['EntryName']))
                in_sec_downtime = (factory_downtimes.checkDowntime(entry="factory", frontend=client_security_name, security_class=x509_proxy_security_class) or
                                       factory_downtimes.checkDowntime(entry=jobDescript.data['EntryName'], frontend=client_security_name, security_class=x509_proxy_security_class))
                if in_sec_downtime:
                    logSupport.log.warning("Security Class %s is currently in a downtime window for Entry: %s. Ignoring request." % (x509_proxy_security_class, jobDescript.data['EntryName']))
                    security_class_downtime_found = True
                    continue # cannot use proxy for submission but entry is not in downtime since other proxies may map to valid security classes
                    
                # Make sure security class in the request is allowed (in AllowedVOs)
                #   (ie: deny Frontend from requesting glideins if the whitelist
                #     does not have its security class (or "All" for everyone) )
                if frontend_whitelist == "On" and security_list.has_key(client_security_name):
                    if x509_proxy_security_class in security_list[client_security_name] or "All" in security_list[client_security_name]:
                        in_downtime = prev_downtime
                        logSupport.log.info("Security test passed for : %s %s " % (jobDescript.data['EntryName'], x509_proxy_security_class))
                    else:
                        logSupport.log.warning("Security class not in whitelist, skipping request (%s %s) " % (client_security_name, x509_proxy_security_class))
                        continue
                else:
                    pass
                    # already checked security name 
                             
                # Check that security class maps to a username for submission                   
                x509_proxy_username = x509_proxies.get_username(x509_proxy_security_class)
                if x509_proxy_username == None:
                    logSupport.log.warning("No mapping for security class %s of x509_proxy_%i for %s (secid: %s), skipping and trying the others" % (x509_proxy_security_class, i, client_int_name, client_security_name))
                    continue 
    
                # Format proxy filename
                try:
                    x509_proxy_fname = glideFactoryLib.update_x509_proxy_file(entry_name, x509_proxy_username, "%s_%s" % (work_key, x509_proxy_identifier), x509_proxy)
                except RuntimeError,e:
                    logSupport.log.warning("Failed to update x509_proxy_%i using username %s for client %s, skipping request" % (i, x509_proxy_username, client_int_name))
                    continue 
                except:
                    logSupport.log.exception("Failed to update x509_proxy_%i using usename %s for client %s, skipping request: " % (i, x509_proxy_username, client_int_name))
                    continue 
                        
                x509_proxies.add_fname(x509_proxy_security_class, x509_proxy_identifier, x509_proxy_fname)

            if x509_proxies.count_fnames < 1:
                if security_class_downtime_found:
                    logSupport.log.warning("Found proxies for client %s but the security class was in downtime, setting entry into downtime for advertising" % client_int_name)
                    in_downtime = True
                else:
                    logSupport.log.warning("No good proxies for %s, skipping request" % client_int_name)
                    continue
            else:
                security_credentials['x509_proxy_list'] = x509_proxies
 
            # ========== end v2+ protocol =============
                 
        else:
            # ========== v3+ proxy protocol ===============
            
            # Get credential security class
            credential_security_class = None  
            if decrypted_params.has_key('SecurityClass'):
                credential_security_class = decrypted_params['SecurityClass']
            else:
                logSupport.log.warning("Client %s did not provide a security class. Skipping bad request." % client_int_name)
                continue #skip request
                    
            # Check security class for downtime (in downtimes file)
            logSupport.log.info("Checking downtime for frontend %s security class: %s (entry %s)." % (client_security_name, credential_security_class, jobDescript.data['EntryName']))
            in_sec_downtime = (factory_downtimes.checkDowntime(entry="factory", frontend=client_security_name, security_class=credential_security_class) or
                                factory_downtimes.checkDowntime(entry=jobDescript.data['EntryName'], frontend=client_security_name, security_class=credential_security_class))
            if in_sec_downtime:
                logSupport.log.warning("Security class %s is currently in a downtime window for entry: %s. Ignoring request." % (credential_security_class, jobDescript.data['EntryName']))
                continue # cannot use proxy for submission but entry is not in downtime since other proxies may map to valid security classes
            
            # Make sure security class in the request is allowed (in AllowedVOs)
            if frontend_whitelist == "On" and security_list.has_key(client_security_name):
                if credential_security_class in security_list[client_security_name] or "All" in security_list[client_security_name]:
                    in_downtime = prev_downtime
                    logSupport.log.info("Security test passed for : %s %s " % (jobDescript.data['EntryName'], credential_security_class))
                else:
                    logSupport.log.warning("Security class not in whitelist, skipping request (%s %s). " % (client_security_name, credential_security_class))
                    continue
            else:
                pass # already checked security name      
              
            # Check that security class maps to a username for submission          
            credential_username = frontendDescript.get_username(client_security_name, credential_security_class)
            if credential_username == None:
                logSupport.log.warning("No username mapping for security class %s of credential for %s (secid: %s), skipping request." % (credential_security_class, client_int_name, client_security_name))
                continue
            
            # Initialize submit credential object
            submit_credentials = glideFactoryCredentials.SubmitCredentials(credential_username, credential_security_class)
                                                
            # Determine the credential location  
            submit_credentials.cred_dir = glideFactoryLib.factoryConfig.get_client_proxies_dir(credential_username) 
            #submit_credentials.cred_dir = os.path.join(client_proxies_base_dir, "user_%s/glidein_%s" % (credential_username, glidein_name))
                        
            # Grid sites do not require VM id or type.  All have proxy in their auth method
            if 'grid_proxy' in auth_method:   
                                
                # Check if project id is required    
                if 'project_id' in auth_method:
                    if decrypted_params.has_key('ProjectId'):
                        submit_credentials.add_identity_credential('ProjectId', decrypted_params['ProjectId'])
                    else:
                        # project id is required, cannot service request
                        logSupport.log.warning("Client '%s' did not specify a Project Id in the request, this is required by entry %s, skipping request." % (client_int_name, jobDescript.data['EntryName']))
                        continue 
                                   
                # Check if voms_attr required
                if 'voms_attr' in auth_method:
                    # TODO determine how to verify voms attribute on a proxy
                    pass 
                          
                # Determine identifier for file name and add to credentials to be passed to submit
                proxy_id = decrypted_params['SubmitProxy']
                # KEL need to change call to frontendname_frontendgroup_proxy_id (and all other ref to call add_security_cred)
                if not submit_credentials.add_security_credential('SubmitProxy', "%s_%s" % (client_int_name, proxy_id)):
                    logSupport.log.warning("Credential %s for the submit proxy cannot be found for client %s, skipping request." % (proxy_id, client_int_name))
                    continue #skip proxy
                    
                # Set the id used for tracking what is in the factory queue       
                submit_credentials.id = proxy_id
                                     
            else:
                # All non proxy auth methods are cloud sites. 
                
                # Verify that the glidein proxy was provided for the non-proxy auth methods
                if decrypted_params.has_key('GlideinProxy'):
                    proxy_id = decrypted_params['GlideinProxy']
                    if not submit_credentials.add_security_credential('GlideinProxy', "%s_%s" % (client_int_name, proxy_id)):
                        logSupport.log.warning("Credential %s for the glidein proxy cannot be found for client %s, skipping request." % (proxy_id, client_int_name))
                        continue  
                else:  
                    logSupport.log.warning("Glidein proxy cannot be found for client %s, skipping request" % client_int_name)
                
                # VM id and type are required for cloud sites
                if 'vm_id' in auth_method:                 
                    # Otherwise the Frontend should supply it
                    if decrypted_params.has_key('VMId'):     
                        submit_credentials.add_identity_credential('VMId', decrypted_params['VMId'])
                    else:
                        logSupport.log.warning("Client '%s' did not specify a VM Id in the request, this is required by entry %s, skipping request. " % (client_int_name, jobDescript.data['EntryName']))
                        continue  
                else:
                    # Validate factory provided vm id exists
                    if jobDescript.data.has_key('EntryVMId'): 
                        submit_credentials.add_identity_credential('VMId', jobDescript.data['EntryVMId'])
                    else:
                        logSupport.log.warning("Entry does not specify a VM Id, this is required by entry %s, skipping request." % jobDescript.data['EntryName'])
                        continue  
                    
                if 'vm_type' in auth_method:                  
                    # Otherwise the Frontend should supply it
                    if decrypted_params.has_key('VMType'):
                        submit_credentials.add_identity_credential('VMType', decrypted_params['VMType'])
                    else:
                        logSupport.log.warning("Client '%s' did not specify a VM Type in the request, this is required by entry %s, skipping request." % (client_int_name, jobDescript.data['EntryName']))
                        continue
                else:
                    # Validate factory provided vm type exists
                    if jobDescript.data.has_key('EntryVMType'): 
                        submit_credentials.add_identity_credential('VMType', jobDescript.data['EntryVMType'])
                    else:
                        logSupport.log.warning("Entry does not specify a VM Type, this is required by entry %s, skipping request." %  jobDescript.data['EntryName'])
                        continue
                
                if 'cert_pair' in auth_method :
                    public_cert_id = decrypted_params['PublicCert']
                    submit_credentials.id = public_cert_id
                    if not submit_credentials.add_security_credential('PublicCert', "%s_%s" % (client_int_name, public_cert_id)):
                        logSupport.log.warning("Credential %s for the public certificate is not safe for client %s, skipping request." % (public_cert_id, client_int_name))
                        continue #skip   
                        
                    private_cert_id = decrypted_params['PrivateCert']
                    if not submit_credentials.add_security_credential('PrivateCert', "%s_%s" % (client_int_name, private_cert_id)):
                        logSupport.log.warning("Credential %s for the private certificate is not safe for client %s, skipping request" % (private_cert_id, client_int_name))
                        continue #skip   
                        
                elif 'key_pair' in auth_method:
                    public_key_id = decrypted_params['PublicKey']
                    submit_credentials.id = public_key_id
                    if not submit_credentials.add_security_credential('PublicKey', "%s_%s" % (client_int_name, public_key_id)):
                        logSupport.log.warning("Credential %s for the public key is not safe for client %s, skipping request" % (public_key_id, client_int_name))
                        continue #skip   
                        
                    private_key_id = decrypted_params['PrivateKey']
                    if not submit_credentials.add_security_credential('PrivateKey', "%s_%s" % (client_int_name, private_key_id)):
                        logSupport.log.warning("Credential %s for the private key is not safe for client %s, skipping request" % (private_key_id, client_int_name))
                        continue #skip 
                    
                elif 'username_password' in auth_method:
                    username_id = decrypted_params['Username']
                    submit_credentials.id = username_id
                    if not submit_credentials.add_security_credential('Username', "%s_%s" % (client_int_name, username_id)):
                        logSupport.log.warning("Credential %s for the username is not safe for client %s, skipping request" % (username_id, client_int_name))
                        continue    
                        
                    password_id = decrypted_params['Password']
                    if not submit_credentials.add_security_credential('Password', "%s_%s" % (client_int_name, password_id)):
                        logSupport.log.warning("Credential %s for the password is not safe for client %s, skipping request" % (password_id, client_int_name))
                        continue    
                                            
                else:
                    logSupport.log.warning("Factory entry %s has invalid authentication method. Skipping request for client %s." % (entry_name, client_int_name))
                    continue
                ''' 
                elif auth_method == 'factory_grid_proxy':
                    # Check no crendentials were passed in the request 
                    if decrypted_params.has_key('SubmitProxy') or decrypted_params.has_key('GlideinProxy') or \
                            decrypted_params.has_key('PublicCert') or decrypted_params.has_key('PrivateCert') or \
                            decrypted_params.has_key('PublicKey') and decrypted_params.has_key('PrivateKey') or \
                            decrypted_params.has_key('Username') or decrypted_params.has_key('Password'):
                        logSupport.log.warning("Client %s provided credentials but only factory proxy is allowed. Skipping bad request" % client_int_name)
                        continue #skip request
                    
                    # only support factory supplying one credential set (list of proxies not supported)
                    credential_security_class = "factory"
                    credential_username = frontendDescript[client_security_name]['usermap'][credential_security_class]
                    
                    if credential_username == None:
                        logSupport.log.warning("No mapping for security class %s for %s (secid: %s), skipping request." % (credential_security_class, client_int_name, client_security_name))
                        continue # cannot map, frontend
                                
                    if glideinDescript.has_key('FactoryProxy'):
                        proxy_absfname = glideinDescript['FactoryProxy']    
                        submit_credentials.id = os.path.split(proxy_absfname)[1]                    
                        if not submit_credentials.add_factory_credential('SubmitProxy', proxy_absfname):
                            logSupport.log.warning("Could not find factory proxy for client %s, skipping request" % client_int_name)
                            continue                               
                    else: 
                        # project id is required, cannot service request
                        logSupport.log.warning("The Factory did not specify the submit proxy in the config, this is required by entry %s, skipping request." %jobDescript.data['EntryName'])
                        continue        
                          
                    # Check if voms_attr is required
                    if 'voms_attr' in auth_method:
                        # TODO determine how to verify voms attribute on a proxy
                        pass                    
                ''' 
            
            # ========== end of v3+ proxy protocol ===============
            ##### END - CREDENTIAL HANDLING - END #####
        
        # Set the downtime status in jobAttributes so the frontend-specific downtime is advertised in glidefactoryclient ads
        jobAttributes.data['GLIDEIN_In_Downtime'] = in_downtime
        glideFactoryLib.factoryConfig.qc_stats.set_downtime(in_downtime)#@UndefinedVariable

        if work[work_key]['requests'].has_key('RemoveExcess'):
            remove_excess = work[work_key]['requests']['RemoveExcess']
        else:
            remove_excess = 'NO'

        if work[work_key]['requests'].has_key('IdleGlideins'):
            # malformed, if no IdleGlideins
            try:
                idle_glideins = int(work[work_key]['requests']['IdleGlideins'])
            except ValueError, e:
                logSupport.log.warning("Client %s provided an invalid ReqIdleGlideins: '%s' not a number. Skipping request." % (client_int_name, work[work_key]['requests']['IdleGlideins']))
                continue #skip request

            if work[work_key]['requests'].has_key('MaxGlideins'):
                try:
                    max_glideins = int(work[work_key]['requests']['MaxGlideins'])
                except ValueError, e:
                    logSupport.log.warning("Client %s provided an invalid ReqMaxGlideins: '%s' not a number. Skipping request." % (client_int_name, work[work_key]['requests']['MaxGlideins']))
                    continue #skip request
            else:
                try:
                    max_glideins = int(work[work_key]['requests']['MaxRunningGlideins'])
                except ValueError, e:
                    logSupport.log.warning("Client %s provided an invalid ReqMaxRunningGlideins: '%s' not a number. Skipping request." % (client_int_name, work[work_key]['requests']['MaxRunningGlideins']))
                    continue #skip request
                
            # If we got this far, it was because we were able to successfully update all the credentials 
            # in the request even if we can't submit glideins.
            # If we already have hit our maximums (checked at beginning of this method and logged there), we can't submit.  
            # We still need to check/update all the other requests and do cleanup.
            # We'll set idle glideins to zero if hit max or in downtime. 
            if in_downtime or not can_submit_glideins:
                idle_glideins=0          
                      
            try:
                client_web_url = work[work_key]['web']['URL']
                client_signtype = work[work_key]['web']['SignType']
                client_descript = work[work_key]['web']['DescriptFile']
                client_sign = work[work_key]['web']['DescriptSign']

                client_group = work[work_key]['internals']['GroupName']
                client_group_web_url = work[work_key]['web']['GroupURL']
                client_group_descript = work[work_key]['web']['GroupDescriptFile']
                client_group_sign = work[work_key]['web']['GroupDescriptSign']
                client_web = glideFactoryLib.ClientWeb(client_web_url, client_signtype, client_descript, client_sign,
                                                    client_group, client_group_web_url, client_group_descript, client_group_sign)                
            except:
                # malformed classad, skip
                logSupport.log.warning("Malformed classad for client %s, missing web parameters, skipping request." % work_key)
                continue
                                              
            if security_credentials.has_key('x509_proxy_list'):
                # ======= v2+ support for multiple proxies ==========
                x509_proxies = security_credentials['x509_proxy_list']
                x509_proxy_security_classes = x509_proxies.fnames.keys()
                x509_proxy_security_classes.sort() # sort to have consistent logging
                for x509_proxy_security_class in x509_proxy_security_classes:
                    # submit each security class independently
                    # split the request proportionally between them
                    x509_proxy_frac = 1.0 * len(x509_proxies.fnames[x509_proxy_security_class]) / x509_proxies.count_fnames
    
                    # round up... if a client requests a non splittable number, worse for him
                    # expect to not be a problem in real world as
                    # the most reasonable use case has a single proxy_class per client name
                    idle_glideins_pc = int(math.ceil(idle_glideins * x509_proxy_frac))
                    max_glideins_pc = int(math.ceil(max_glideins * x509_proxy_frac))
    
                    # Should log here or in perform_work
                    glideFactoryLib.logWorkRequest(client_int_name, client_security_name, x509_proxy_security_class,
                                                   idle_glideins, max_glideins, work[work_key], x509_proxy_frac)
    
                    all_security_names.add((client_security_name, x509_proxy_security_class))
                    entry_condorQ = glideFactoryLib.getQProxSecClass(condorQ, client_int_name, x509_proxy_security_class)

                    # Map the above identity to a frontend:sec_class for tracking totals
                    frontend_name = "%s:%s" % (frontendDescript.get_frontend_name(client_expected_identity), x509_proxy_security_class)   
                
                    done_something += perform_work(entry_name, entry_condorQ,
                                                   work_key, client_int_name, client_security_name,
                                                   x509_proxy_security_class, client_int_req,
                                                   idle_glideins_pc, max_glideins_pc, remove_excess,
                                                   jobDescript, x509_proxies.fnames[x509_proxy_security_class], x509_proxies.get_username(x509_proxy_security_class),
                                                   identity_credentials, glidein_totals, frontend_name,
                                                   client_web, params)            
                # ======= end of v2+ support for multiple proxies ==========
                
            else:
                # ======= v3+ protocol =============
                
                # do one iteration for the credential set (maps to a single security class)
                glideFactoryLib.factoryConfig.client_internals[client_int_name] = {"CompleteName":client_int_name, "ReqName":client_int_req}
                
                # find out the users it is using
                log_stats = {}
                log_stats[credential_username + ":" + client_int_name] = glideFactoryLogParser.dirSummaryTimingsOut(glideFactoryLib.factoryConfig.get_client_log_dir(entry_name, credential_username),
                                                                                          logSupport.log_dir, client_int_name, credential_username)
                # should not need privsep for reading logs
                log_stats[credential_username + ":" + client_int_name].load()
                                         
                # Should log here or in perform_work
                glideFactoryLib.logWorkRequest(client_int_name, client_security_name, submit_credentials.security_class,
                                                   idle_glideins, max_glideins, work[work_key])
    
                all_security_names.add((client_security_name, credential_security_class))
                entry_condorQ = glideFactoryLib.getQProxSecClass(condorQ, client_int_name, submit_credentials.security_class)
                
                glideFactoryLib.logStats(entry_condorQ, client_int_name, client_security_name, submit_credentials.security_class) 
                client_log_name = glideFactoryLib.secClass2Name(client_security_name, submit_credentials.security_class)
                glideFactoryLib.factoryConfig.log_stats.logSummary(client_log_name, log_stats) #@UndefinedVariable

                # Map the above identity to a frontend:sec_class for tracking totals
                frontend_name = "%s:%s" % (frontendDescript.get_frontend_name(client_expected_identity), submit_credentials.security_class)  
                
                logSupport.log.info("Using v3+ protocol and credential %s" % submit_credentials.id)
                done_something += glideFactoryLib.keepIdleGlideins(entry_condorQ, client_int_name, 
                                                             idle_glideins, max_glideins, remove_excess,
                                                             submit_credentials, glidein_totals, frontend_name,
                                                             client_web, params)
                # ======= end of v3+ protocol =============
    
    logSupport.log.info("Updating statistics")
    for sec_el in all_security_names:
        try:
            glideFactoryLib.factoryConfig.rrd_stats.getData("%s_%s" % sec_el) 
        except glideFactoryLib.condorExe.ExeError:
            # never fail for monitoring... just log
            logSupport.log.exception("get_RRD_data failed with Condor error: ")
        except:
            # never fail for monitoring... just log
            logSupport.log.exception("get_RRD_data failed with unknown error: ")

    # Only do cleanup when no work (submit new glideins or remove excess) was done, work is the priority
    if done_something == 0: 
        logSupport.log.info("Sanitizing glideins for entry %s" % entry_name)
        glideFactoryLib.sanitizeGlideins(condorQ)
        
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
    logSupport.log.info("log_stats written")
    glideFactoryLib.factoryConfig.qc_stats.finalizeClientMonitor()
    glideFactoryLib.factoryConfig.qc_stats.write_file()
    logSupport.log.info("qc_stats written")
    glideFactoryLib.factoryConfig.rrd_stats.writeFiles()
    logSupport.log.info("rrd_stats written")
    
    return

# added by C.W. Murphy for glideFactoryEntryDescript
def write_descript(entry_name, entryDescript, entryAttributes, entryParams, monitor_dir):
    entry_data = {entry_name:{}}
    entry_data[entry_name]['descript'] = copy.deepcopy(entryDescript.data)
    entry_data[entry_name]['attributes'] = copy.deepcopy(entryAttributes.data)
    entry_data[entry_name]['params'] = copy.deepcopy(entryParams.data)

    descript2XML = glideFactoryMonitoring.Descript2XML()
    entry_str = descript2XML.entryDescript(entry_data)
    xml_str = ""
    for line in entry_str.split("\n")[1:-2]:
        line = line[3:] + "\n" # remove the extra tab
        xml_str += line

    try:
        descript2XML.writeFile(monitor_dir + "/", xml_str, singleEntry=True)
    except IOError:
        logSupport.log.exception("Unable to write descript.xml file: ")

    return


############################################################
    
def advertize_myself(in_downtime, glideinDescript, jobDescript, jobAttributes, jobParams):
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
    
    entry_name = jobDescript.data['EntryName']
    trust_domain = jobDescript.data['TrustDomain']
    auth_method = jobDescript.data['AuthMethod']
    pub_key_obj = glideinDescript.data['PubKeyObj']

    glideFactoryLib.factoryConfig.client_stats.finalizeClientMonitor() #@UndefinedVariable

    current_qc_total = glideFactoryLib.factoryConfig.client_stats.get_total() #@UndefinedVariable

    glidein_monitors = {}
    for w in current_qc_total.keys():
        for a in current_qc_total[w].keys():
            glidein_monitors['Total%s%s' % (w, a)] = current_qc_total[w][a]
    try:
        myJobAttributes = jobAttributes.data.copy()
        myJobAttributes['GLIDEIN_In_Downtime'] = in_downtime
        glideFactoryInterface.advertizeGlidein(glideFactoryLib.factoryConfig.factory_name,
                                               glideFactoryLib.factoryConfig.glidein_name,
                                               entry_name,
                                               trust_domain,
                                               auth_method,
                                               glideFactoryLib.factoryConfig.supported_signtypes,
                                               pub_key_obj,
                                               myJobAttributes,
                                               jobParams.data.copy(),
                                               glidein_monitors.copy())
    except:
        logSupport.log.error("Advertize failed")

    advertizer = glideFactoryInterface.MultiAdvertizeGlideinClientMonitoring(glideFactoryLib.factoryConfig.factory_name,
                                                                             glideFactoryLib.factoryConfig.glidein_name,
                                                                             entry_name,
                                                                             jobAttributes.data.copy())

    current_qc_data = glideFactoryLib.factoryConfig.client_stats.get_data() #@UndefinedVariable
    for client_name in current_qc_data.keys():
        client_qc_data = current_qc_data[client_name]
        if not glideFactoryLib.factoryConfig.client_internals.has_key(client_name): #@UndefinedVariable
            logSupport.log.warning("Client '%s' has stats, but no classad! Ignoring." % client_name)
            continue

        client_internals = glideFactoryLib.factoryConfig.client_internals[client_name]

        client_monitors = {}
        for w in client_qc_data.keys():
            for a in client_qc_data[w].keys():
                if type(client_qc_data[w][a]) == type(1): # report only numbers
                    client_monitors['%s%s' % (w, a)] = client_qc_data[w][a]

        try:
            fparams = current_qc_data[client_name]['Requested']['Parameters']
        except:
            fparams = {}

        params = jobParams.data.copy()
        for p in fparams.keys():
            if p in params.keys(): # can only overwrite existing params, not create new ones
                params[p] = fparams[p]

        advertizer.add(client_internals["CompleteName"], client_name, client_internals["ReqName"], params, client_monitors.copy())

    try:
        advertizer.do_advertize()
    except:
        logSupport.log.error("Advertize of monitoring failed")

    return

############################################################
def iterate_one(do_advertize,in_downtime,
                glideinDescript,frontendDescript,jobDescript,jobAttributes,jobParams):
    """
    Do one iteration of advertising and processing of requests.
    """
    
    done_something=0
    jobAttributes.data['GLIDEIN_In_Downtime']=in_downtime
    
    
    # Process requests from the frontends
    try:
        done_something = find_and_perform_work(in_downtime, glideinDescript, frontendDescript, jobDescript, jobAttributes, jobParams)
    except Exception:
        logSupport.log.exception("Error occurred while trying to find and do work: ")

    # Only advertise if work was done or if the nth iteration
    if do_advertize or done_something:
        logSupport.log.info("Advertize")
        advertize_myself(in_downtime, glideinDescript, jobDescript, jobAttributes, jobParams)

    # Why do we delete this attribute?  Seems rather unecessary
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

    is_first = 1
    count = 0

    # Record the starttime so we know when to disable the use of old pub key
    starttime = time.time()
    # The grace period should be in the factory config. Use it to determine
    # the end of lifetime for the old key object. Hardcoded for now to 30 mins.
    oldkey_gracetime = int(glideinDescript.data['OldPubKeyGraceTime'])
    oldkey_eoltime = starttime + oldkey_gracetime
    # Set Monitoring logging
    glideFactoryLib.factoryConfig.log_stats = glideFactoryMonitoring.condorLogSummary()


    glideFactoryLib.factoryConfig.rrd_stats = glideFactoryMonitoring.FactoryStatusData()

    # Get downtimes
    factory_downtimes = glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data['DowntimesFile'])

    # Start work loop
    while 1:
        # check to see if we are orphaned - raises KeyboardInterrupt exception if we are
        check_parent(parent_pid,glideinDescript,jobDescript)
        if ( (time.time() > oldkey_eoltime) and 
             (glideinDescript.data['OldPubKeyObj'] != None) ):
            # Invalidate the use of factory's old key
            logSupport.log.info("Retiring use of old key.")
            logSupport.log.info("Old key was valid from %s to %s ie grace of ~%s sec" % (starttime,oldkey_eoltime,oldkey_gracetime))
            glideinDescript.data['OldPubKeyType'] = None
            glideinDescript.data['OldPubKeyObj'] = None

        # are we in downtime?  True/False
        in_downtime = (factory_downtimes.checkDowntime(entry="factory") or
                       factory_downtimes.checkDowntime(entry=jobDescript.data['EntryName']))
        in_downtime_message=factory_downtimes.downtime_comment
        jobAttributes.data['GLIDEIN_Downtime_Comment']=in_downtime_message

        if in_downtime:
            logSupport.log.info("Downtime iteration at %s" % time.ctime())
        else:
            logSupport.log.info("Iteration at %s" % time.ctime())

        try:
            glideFactoryLib.factoryConfig.log_stats.reset() #@UndefinedVariable
            # This one is used for stats advertized in the ClassAd
            glideFactoryLib.factoryConfig.client_stats = glideFactoryMonitoring.condorQStats()
            # These two are used to write the history to disk
            glideFactoryLib.factoryConfig.qc_stats = glideFactoryMonitoring.condorQStats()
            glideFactoryLib.factoryConfig.client_internals = {}

            # actually do some work now that we have everything setup (hopefully)
            # KEL do we need to acknowledge that work was done?  this variable is currently unused
            done_something = iterate_one(count == 0, in_downtime, glideinDescript, frontendDescript,
                                         jobDescript, jobAttributes, jobParams)

            logSupport.log.info("Writing stats")
            try:
                write_stats()
            except KeyboardInterrupt:
                raise # this is an exit signal, pass through
            except:
                # never fail for stats reasons!
                logSupport.log.exception("Unable to write stats, but does not cause entry to fail: ")
        except KeyboardInterrupt:
            raise # this is an exit signal, pass through
        except:
            if is_first:
                raise
            else:
                # if not the first pass, just warn
                logSupport.log.exception("Exception occurred during an entry iteration, continue iterating: " )

        cleanupSupport.cleaners.cleanup()

        # Sleep now before next iteration
        logSupport.log.info("Sleep %is" % sleep_time)
        time.sleep(sleep_time)

        count = (count + 1) % advertize_rate
        is_first = 0


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
    # KEL should we use this startup time somewhere?  this is currently unused
    startup_time = time.time()

    glideFactoryInterface.factoryConfig.lock_dir=os.path.join(startup_dir,"lock")

    os.chdir(startup_dir)

    glideinDescript = glideFactoryConfig.GlideinDescript()
    glideinDescript.load_pub_key()
    glideinDescript.load_old_rsa_key()

    # Check whether the entry name passed in matches a supported entry
    if not (entry_name in string.split(glideinDescript.data['Entries'], ',')):
        raise RuntimeError, "Entry '%s' not supported: %s" % \
            (entry_name, glideinDescript.data['Entries'])

    # Set the Log directory
    logSupport.log_dir = os.path.join(glideinDescript.data['LogDir'], "entry_%s" % entry_name)

    # Configure entry process logging
    process_logs = eval(glideinDescript.data['ProcessLogs']) 
    for plog in process_logs:
        logSupport.add_processlog_handler(entry_name, logSupport.log_dir, plog['msg_types'], plog['extension'],
                                      int(float(plog['max_days'])),
                                      int(float(plog['min_days'])),
                                      int(float(plog['max_mbytes'])))
    logSupport.log = logging.getLogger(entry_name)
    logSupport.log.info("Logging initialized")
 
    ## Not touching the monitoring logging.  Don't know how that works yet
    logSupport.log.debug("Setting up the monitoring")
    glideFactoryMonitoring.monitoringConfig.monitor_dir = os.path.join(startup_dir, "monitor/entry_%s" % entry_name)
    logSupport.log.debug("Monitoring directory: %s" % glideFactoryMonitoring.monitoringConfig.monitor_dir)
    glideFactoryMonitoring.monitoringConfig.config_log(logSupport.log_dir,
                                                       float(glideinDescript.data['SummaryLogRetentionMaxDays']),
                                                       float(glideinDescript.data['SummaryLogRetentionMinDays']),
                                                       float(glideinDescript.data['SummaryLogRetentionMaxMBs']))

    glideFactoryMonitoring.monitoringConfig.my_name = "%s@%s" % (entry_name, glideinDescript.data['GlideinName'])
    logSupport.log.debug("Monitoring Name: %s" % glideFactoryMonitoring.monitoringConfig.my_name)


    logSupport.log.debug("Getting configurations")
    frontendDescript = glideFactoryConfig.FrontendDescript()
    jobDescript = glideFactoryConfig.JobDescript(entry_name)
    jobAttributes = glideFactoryConfig.JobAttributes(entry_name)
    jobParams = glideFactoryConfig.JobParams(entry_name)

    logSupport.log.debug("Write descripts")
    write_descript(entry_name, jobDescript, jobAttributes, jobParams, glideFactoryMonitoring.monitoringConfig.monitor_dir)

    # use config values to configure the factory
    logSupport.log.debug("Setting Factory (Entry) Config")
    glideFactoryLib.factoryConfig.config_whoamI(glideinDescript.data['FactoryName'], glideinDescript.data['GlideinName'])
    glideFactoryLib.factoryConfig.config_dirs(startup_dir,
                                              glideinDescript.data['LogDir'],
                                              glideinDescript.data['ClientLogBaseDir'],
                                              glideinDescript.data['ClientProxiesBaseDir'])

    glideFactoryLib.factoryConfig.max_submits = int(jobDescript.data['MaxSubmitRate'])
    glideFactoryLib.factoryConfig.max_cluster_size = int(jobDescript.data['SubmitCluster'])
    glideFactoryLib.factoryConfig.slots_layout = jobDescript.data['SubmitSlotsLayout'] 
    glideFactoryLib.factoryConfig.submit_sleep = float(jobDescript.data['SubmitSleep'])
    glideFactoryLib.factoryConfig.max_removes = int(jobDescript.data['MaxRemoveRate'])
    glideFactoryLib.factoryConfig.remove_sleep = float(jobDescript.data['RemoveSleep'])
    glideFactoryLib.factoryConfig.max_releases = int(jobDescript.data['MaxReleaseRate'])
    glideFactoryLib.factoryConfig.release_sleep = float(jobDescript.data['ReleaseSleep'])

    logSupport.log.debug("Adding directory cleaners")
    cleaner = cleanupSupport.PrivsepDirCleanupWSpace(None, logSupport.log_dir,
                                      "(condor_activity_.*\.log\..*\.ftstpk)",
                                      int(float(glideinDescript.data['CondorLogRetentionMaxDays'])) * 24 * 3600,
                                      int(float(glideinDescript.data['CondorLogRetentionMinDays'])) * 24 * 3600,
                                      long(float(glideinDescript.data['CondorLogRetentionMaxMBs'])) * (1024.0 * 1024.0))
    cleanupSupport.cleaners.add_cleaner(cleaner)

    # add cleaners for the user log directories
    for username in frontendDescript.get_all_usernames():
        user_log_dir = glideFactoryLib.factoryConfig.get_client_log_dir(entry_name, username)
        cleaner = cleanupSupport.PrivsepDirCleanupWSpace(username, user_log_dir,
                                          "(job\..*\.out)|(job\..*\.err)",
                                          int(float(glideinDescript.data['JobLogRetentionMaxDays'])) * 24 * 3600,
                                          int(float(glideinDescript.data['JobLogRetentionMinDays'])) * 24 * 3600,
                                          long(float(glideinDescript.data['JobLogRetentionMaxMBs'])) * (1024.0 * 1024.0))
        cleanupSupport.cleaners.add_cleaner(cleaner)
        cleaner = cleanupSupport.PrivsepDirCleanupWSpace(username, user_log_dir,
                                          "(condor_activity_.*\.log)|(condor_activity_.*\.log.ftstpk)|(submit_.*\.log)",
                                          int(float(glideinDescript.data['CondorLogRetentionMaxDays'])) * 24 * 3600,
                                          int(float(glideinDescript.data['CondorLogRetentionMinDays'])) * 24 * 3600,
                                          long(float(glideinDescript.data['CondorLogRetentionMaxMBs'])) * (1024.0 * 1024.0))
        cleanupSupport.cleaners.add_cleaner(cleaner)

    logSupport.log.debug("Set advertiser parameters")
    glideFactoryInterface.factoryConfig.advertise_use_tcp = (glideinDescript.data['AdvertiseWithTCP'] in ('True', '1'))
    glideFactoryInterface.factoryConfig.advertise_use_multi = (glideinDescript.data['AdvertiseWithMultiple'] in ('True', '1'))

    logSupport.log.debug("Get glideinWMS version")
    try:
        gwms_dirname = os.path.dirname(os.path.dirname(sys.argv[0]))
        glideFactoryInterface.factoryConfig.glideinwms_version = glideinWMSVersion.GlideinWMSDistro(gwms_dirname, os.path.join(gwms_dirname, 'etc/checksum.factory')).version()
    except:
        logSupport.log.exception("Exception occured while trying to retrieve the glideinwms version: ")


    # create lock file
    pid_obj = glideFactoryPidLib.EntryPidSupport(startup_dir, entry_name)
    logSupport.log.debug("Created lock file")

    # force integrity checks on all the operations
    # I need integrity checks also on reads, as I depend on them
    os.environ['_CONDOR_SEC_DEFAULT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_CLIENT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_READ_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_WRITE_INTEGRITY'] = 'REQUIRED'
    logSupport.log.debug("Set Condor security environment")

    # start
    pid_obj.register(parent_pid)
    try:
        try:
            try:
                logSupport.log.info("Starting up")
                iterate(parent_pid, sleep_time, advertize_rate,
                        glideinDescript, frontendDescript, jobDescript, jobAttributes, jobParams)
            except KeyboardInterrupt:
                logSupport.log.info("Received signal...exit")
            except:
                logSupport.log.exception("Exception occurred in the entry: ")
                raise
        finally:
            # no need to cleanup.. the parent should be doing it
            logSupport.log.info("Dying")
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
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5])


