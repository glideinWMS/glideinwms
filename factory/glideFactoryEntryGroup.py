#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This is the glideinFactoryEntryGroup. Common Tasks like queering collector
#   are done here
#
# Arguments:
#   $1 = poll period (in seconds)
#   $2 = advertize rate (every $2 loops)
#   $3 = glidein submit_dir
#   $4 = entry name
#
# Author:
#   Parag Mhashilkar (October 2012)
#

import signal
import os,os.path,sys,fcntl
import traceback
import time,string,math
import copy,random
import sets
sys.path.append(os.path.join(sys.path[0],"../lib"))

import glideFactoryPidLib
import glideFactoryMonitoring
import glideFactoryLogParser
import glideFactoryDowntimeLib
import logSupport
import glideinWMSVersion
import glideFactoryInterface as gfi
import glideFactoryLib as gfl
import glideFactoryConfig as gfc

############################################################
class EntryGroup:

    def __init__(self):
        pass

############################################################
def check_parent(parent_pid, glideinDescript, jobDescript):
    """
    TODO: PM: Need to modify this for both Entry and EntryGroup

    Check to make sure that we aren't an orphaned process.  If Factory
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
        glideFactoryInterface.deadvertizeGlidein(
            glideinDescript.data['FactoryName'],	 
            glideinDescript.data['GlideinName'],	 
            jobDescript.data['EntryName'])	 
    except:
        glideFactoryLib.log_files.logWarning("Failed to deadvertize myself")


    try:
        glideFactoryInterface.deadvertizeAllGlideinClientMonitoring(
            glideinDescript.data['FactoryName'],	 
            glideinDescript.data['GlideinName'],	 
            jobDescript.data['EntryName'])	 
    except:
        glideFactoryLib.log_files.logWarning("Failed to deadvertize my monitoring")

    raise KeyboardInterrupt,"Parent died. Quiting."


############################################################
def perform_work(entry_name,
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
    
###############################
def find_work(factory_in_downtime, glideinDescript,
              frontendDescript, group_name, my_entries):
    """
    Find work
    """

    pub_key_obj = glideinDescript.data['PubKeyObj']
    old_pub_key_obj = glideinDescript.data['OldPubKeyObj']

    allowed_proxy_source = glideinDescript.data['AllowedJobProxySource'].split(',')

    gfl.log_files.logActivity("Finding work")
    work = gfi.findGroupWork(gfl.factoryConfig.factory_name,
                             gfl.factoryConfig.glidein_name,
                             my_entries.keys(),
                             gfl.factoryConfig.supported_signtypes,
                             pub_key_obj, allowed_proxy_source)
    



     ############ I AM HERE IMPLEMENTING ABOVE







    gfl.log_files.logActivity("Found %s total tasks to work on using existing factory key." % len(work))

    # If old key is valid, find the work using old key as well and append it
    # to existing work dictionary
    if (old_pub_key_obj != None):
        work_oldkey = {}
        # still using the old key in this cycle
        gfl.log_files.logActivity("Old factory key is still valid. Trying to find work using old factory key.")
        work_oldkey = gfi.findWork(gfl.factoryConfig.factory_name,
                                   gfl.factoryConfig.glidein_name,
                                   entry_name,
                                   gfl.factoryConfig.supported_signtypes,
                                   old_pub_key_obj,
                                   allowed_proxy_source)
        gfl.log_files.logActivity("Found %s tasks to work on using old factory key" % len(work_oldkey))

        # Merge the work_oldkey with work
        for w in work_oldkey.keys():
            if work.has_key(w):
                # This should not happen but still as a safegaurd warn
                gfl.log_files.logActivity("Work task for %s exists using existing key and old key. Ignoring the work from old key." % w)
                gfl.log_files.logError("Work task for %s exists using existing key and old key. Ignoring the work from old key." % w)
                continue
            work[w] = work_oldkey[w]

    return work

###############################
def find_and_perform_work(factory_in_downtime, glideinDescript,
                          frontendDescript, group_name, my_entries)
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
    
    work = find_work(factory_in_downtime, glideinDescript,
                     frontendDescript, group_name, my_entries)   
































    entry_name=jobDescript.data['EntryName']

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
            if client_expected_identity==None:
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
            if decrypted_params['x509_proxy']==None:
                glideFactoryLib.log_files.logWarning("Could not decrypt x509_proxy for %s, skipping request"%client_int_name)
                continue #skip request

            # This old style protocol does not support SecurityName, use default
            # Cannot check against a security class downtime since will never exist in the config
            x509_proxy_security_class="none"
            
            x509_proxy_username=x509_proxies.get_username(x509_proxy_security_class)
            if x509_proxy_username==None:
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
                if decrypted_params['x509_proxy_%i'%i]==None:
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
                if x509_proxy_username==None:
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
            if x509_proxy_username==None:
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
"""
             done_something = iterate_one(count==0, factory_in_downtime,
                                         glideinDescript, frontendDescript,
                                         group_name, my_entries)
"""

def iterate_one(do_advertize, factory_in_downtime, glideinDescript,
                frontendDescript, group_name, my_entries):
    
    done_something = 0

    for entry in my_entries.values():
        entry.initIteration(factory_in_downtime)

    try:
        done_something = find_and_perform_work(factory_in_downtime, 
                                               glideinDescript,
                                               frontendDescript,
                                               group_name, my_entries)
    except:
        gfl.log_files.logWarning("Error occurred while trying to find and do work.")
        







    if do_advertize or done_something:
        gfl.log_files.logActivity("Advertize")
        advertize_myself(in_downtime,glideinDescript,jobDescript,jobAttributes,jobParams)






    for entry in my_entries.values():
        entry.unsetInDowntime()
    
    return done_something

############################################################
def iterate(parent_pid, sleep_time, advertize_rate, glideinDescript,
            frontendDescript, group_name, my_entries):
    """
    Iterate over set of tasks until its time to quit or die. The main "worker" 
    function for the Factory Entry Group.
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
    
    factory_downtimes = glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data['DowntimesFile'])

    while 1:
        
        # Check if parent is still active. If not cleanup and die.
        check_parent(parent_pid, glideinDescript, jobDescript)

        # Check if its time to invalidate factory's old key
        if ( (time.time() > oldkey_eoltime) and 
             (glideinDescript.data['OldPubKeyObj'] != None) ):
            # Invalidate the use of factory's old key
            gfl.log_files.logActivity("Retiring use of old key.")
            gfl.log_files.logActivity("Old key was valid from %s to %s ie grace of ~%s sec" % (starttime,oldkey_eoltime,oldkey_gracetime))
            glideinDescript.data['OldPubKeyType'] = None
            glideinDescript.data['OldPubKeyObj'] = None

        # Check if the factory is in downtime. Group is in downtime only if the
        # factory is in downtime. Entry specific downtime is handled in entry
        factory_in_downtime = factory_downtimes.checkDowntime(entry="factory")

        if factory_in_downtime:
            gfl.log_files.logActivity("Downtime iteration at %s" % time.ctime())
        else:
            gfl.log_files.logActivity("Iteration at %s" % time.ctime())




        try:
            done_something = iterate_one(count==0, factory_in_downtime,
                                         glideinDescript, frontendDescript,
                                         group_name, my_entries)


       

            
            gfl.log_files.logActivity("Writing stats")
            try:
                write_stats()
            except KeyboardInterrupt:
                raise # this is an exit signal, pass through
            except:
                # never fail for stats reasons!
                tb = traceback.format_exception(sys.exc_info()[0],
                                                sys.exc_info()[1],
                                                sys.exc_info()[2])
                gfl.log_files.logWarning("Exception occurred: %s" % tb)                
        except KeyboardInterrupt:
            raise # this is an exit signal, pass through
        except:
            if is_first:
                raise
            else:
                # if not the first pass, just warn
                tb = traceback.format_exception(sys.exc_info()[0],
                                                sys.exc_info()[1],
                                                sys.exc_info()[2])
                gfl.log_files.logWarning("Exception occurred: %s" % tb)                
                
        gfl.log_files.cleanup()

        gfl.log_files.logActivity("Sleep %is" % sleep_time)
        time.sleep(sleep_time)
        count = (count+1) % advertize_rate
        is_first = 0
        
        
############################################################
# Initialize log_files for entries and groups

def init_logs(name, entity, log_dir):
    gfl.log_files_dict[entity][name] = gfl.LogFiles(
        log_dir,
        float(glideinDescript.data['LogRetentionMaxDays']),
        float(glideinDescript.data['LogRetentionMinDays']),
        float(glideinDescript.data['LogRetentionMaxMBs']))

    # TODO: PM: What to do with warning_log.
    #       Is this correct? Or do we need warning logs for every entry?
    #       If so how to we instantiate it?
    gfi.factoryConfig.warning_log=gfl.log_files_dict[entity][name].warning_log

def init_group_logs(name):
    log_dir=os.path.join(glideinDescript.data['LogDir'],"factory")
    init_logs(name, 'group', log_dir)

def init_entry_logs(name):
    log_dir=os.path.join(glideinDescript.data['LogDir'],"entry_%s"%entry_name)
    init_logs(name, 'entry', log_dir)
    glideFactoryMonitoring.monitoringConfig.config_log(
        log_dir,
        float(glideinDescript.data['SummaryLogRetentionMaxDays']),
        float(glideinDescript.data['SummaryLogRetentionMinDays']),
        float(glideinDescript.data['SummaryLogRetentionMaxMBs']))



############################################################

def main(parent_pid, sleep_time, advertize_rate,
         startup_dir, entry_names, group_id):
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
    @type entry_names: string
    @param entry_name: The CVS name of the entries this process should work on 
    """

    # Assume name to be group_[0,1,2] etc. Only required to create log_dir
    # where tasks common to the group will be stored. There is no other 
    # significance to the group_name and number of entries supported by a group
    # can change between factory reconfigs

    group_name = "group_%s" % group_id

    os.chdir(startup_dir)

    # Setup the lock_dir
    gfi.factoryConfig.lock_dir = os.path.join(startup_dir, "lock")

    # Read information about the glidein and frontends
    glideinDescript = gfc.GlideinDescript()
    frontendDescript = gfc.FrontendDescript()

    # Load factory keys
    glideinDescript.load_pub_key()
    glideinDescript.load_old_rsa_key()

    # Dictionary of Entry objects this group will process
    my_entries = {}

    glidein_entries = glideinDescript.data['Entries']


    # Initiate the log_files
    log_dir = os.path.join(glideinDescript.data['LogDir'], group_name)
    gfl.log_files = gfl.LogFiles(
        log_dir,
        float(glideinDescript.data['LogRetentionMaxDays']),
        float(glideinDescript.data['LogRetentionMinDays']),
        float(glideinDescript.data['LogRetentionMaxMBs']))
    glideFactoryMonitoring.monitoringConfig.config_log(
        log_dir,
        float(glideinDescript.data['SummaryLogRetentionMaxDays']),
        float(glideinDescript.data['SummaryLogRetentionMinDays']),
        float(glideinDescript.data['SummaryLogRetentionMaxMBs']))
    gfi.factoryConfig.warning_log = gfl.log_files.warning_log

    gfl.log_files.logActivity("Starting up")
    gfl.log_files.logActivity("Entries processed by %s: %s " % (group_name, entry_names))


    # Check if all the entries in this group are valid
    for entry in string.split(entry_names, ','):
        if not (entry in string.split(glidein_entries, ',')):
            msg = "Entry '%s' not configured: %s" % (entry, glidein_entries)
            gfl.log_files.logError(msg)
            raise RuntimeError, msg

        # Create entry objects
        my_entries[entry] = glideFactoryEntry.Entry(entry, startup_dir,
                                                    glideinDescript,
                                                    frontendDescript)

    # Create lock file for this group and register its parent
    pid_obj = glideFactoryPidLib.EntryGroupPidSupport(startup_dir, group_name)
    pid_obj.register(parent_pid)

    try:
        try:
            try:
                iterate(parent_pid, sleep_time, advertize_rate,
                        glideinDescript, frontendDescript,
                        group_name, my_entries)
            except KeyboardInterrupt:
                gfl.log_files.logActivity("Received signal...exit")
            except:
                tb = traceback.format_exception(sys.exc_info()[0],
                                                sys.exc_info()[1],
                                                sys.exc_info()[2])
                gfl.log_files.logWarning("Exception occurred: %s" % tb)
                raise
        finally:
            # No need to cleanup. The parent should be doing it
            gfl.log_files.logActivity("Dying")
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
    signal.signal(signal.SIGTERM, termsignal)
    signal.signal(signal.SIGQUIT, termsignal)

    # Force integrity checks on all condor operations
    glideFactoryLib.set_condor_integrity_checks()

    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), 
         sys.argv[4], sys.argv[5], sys.argv[6])
 

