#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version:
#   $Id: glideFactoryEntry.py,v 1.96.2.27.6.2 2010/11/27 17:48:33 sfiligoi Exp $
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
def check_parent(parent_pid,glideinDescript,jobDescript):
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
def perform_work(entry_name,
                 schedd_name,
                 client_name,client_int_name,client_security_name,client_int_req,
                 idle_glideins,max_running,max_held,
                 jobDescript,
                 x509_proxy_fnames,x509_proxy_usernames,
                 client_web,
                 params):
    glideFactoryLib.factoryConfig.client_internals[client_int_name]={"CompleteName":client_name,"ReqName":client_int_req}

    if params.has_key("GLIDEIN_Collector"):
        condor_pool=params["GLIDEIN_Collector"]
    else:
        condor_pool=None
    
    #glideFactoryLib.log_files.logActivity("QueryQ (%s,%s,%s,%s,%s)"%(glideFactoryLib.factoryConfig.factory_name,glideFactoryLib.factoryConfig.glidein_name,entry_name,client_name,schedd_name))
    try:
        condorQ=glideFactoryLib.getCondorQData(entry_name,client_int_name,schedd_name)
    except glideFactoryLib.condorExe.ExeError,e:
        glideFactoryLib.log_files.logActivity("Client '%s', schedd not responding, skipping"%client_int_name)
        glideFactoryLib.log_files.logWarning("getCondorQData failed: %s"%e)
        # protect and skip
        return 0
    except:
        glideFactoryLib.log_files.logActivity("Client '%s', schedd not responding, skipping"%client_int_name)
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logWarning("getCondorQData failed, traceback: %s"%string.join(tb,''))
        # protect and skip
        return 0

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
    usernames={}
    for x509_proxy_id in x509_proxy_keys:
        username=x509_proxy_usernames[x509_proxy_id]
        usernames[username]=True

    log_stats={}
    for username in usernames.keys():
        log_stats[username]=glideFactoryLogParser.dirSummaryTimingsOut(glideFactoryLib.factoryConfig.get_client_log_dir(entry_name,username),
                                                                       glideFactoryLib.log_files.log_dir,
                                                                       client_int_name,username)
        # should not need privsep for reading logs
        log_stats[username].load()

    glideFactoryLib.logStats(condorQ,condorStatus,client_int_name,client_security_name)
    glideFactoryLib.factoryConfig.log_stats.logSummary(client_security_name,log_stats)
        

    submit_attrs=[]

    # use the extended params for submission
    proxy_fraction=1.0/len(x509_proxy_keys)

    # I will shuffle proxies around, so I may as well round up all of them
    idle_glideins_pproxy=math.ceil(idle_glideins*proxy_fraction)
    max_running_pproxy=math.ceil(max_running*proxy_fraction)

    # not reducing the held, as that is effectively per proxy, not per request
    nr_submitted=0
    for x509_proxy_id in x509_proxy_keys:
        nr_submitted+=glideFactoryLib.keepIdleGlideins(condorQ,client_int_name,
                                                       idle_glideins_pproxy,max_running_pproxy,max_held,submit_attrs,
                                                       x509_proxy_id,x509_proxy_fnames[x509_proxy_id],x509_proxy_usernames[x509_proxy_id],
                                                       client_web,params)
    if nr_submitted>0:
        #glideFactoryLib.log_files.logActivity("Submitted")
        return 1 # we submitted something, return immediately

    if condorStatus!=None: # temporary glitch, no sanitization this round
        #glideFactoryLib.log_files.logActivity("Sanitize")
        glideFactoryLib.sanitizeGlideins(condorQ,condorStatus)
    else:
        glideFactoryLib.sanitizeGlideinsSimple(condorQ)
    
    #glideFactoryLib.log_files.logActivity("Work done")
    return 0
    

############################################################
def find_and_perform_work(in_downtime,glideinDescript,frontendDescript,jobDescript,jobParams):
    entry_name=jobDescript.data['EntryName']
    pub_key_obj=glideinDescript.data['PubKeyObj']

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
    glideFactoryLib.factoryConfig.qc_stats.set_downtime(in_downtime)
    
    #glideFactoryLib.log_files.logActivity("Find work")
    work = glideFactoryInterface.findWork(glideFactoryLib.factoryConfig.factory_name,glideFactoryLib.factoryConfig.glidein_name,entry_name,
                                          glideFactoryLib.factoryConfig.supported_signtypes,
                                          pub_key_obj,allowed_proxy_source)
    
    if len(work.keys())==0:
        return 0 # nothing to be done

    #glideFactoryLib.log_files.logActivity("Perform work")
    schedd_name=jobDescript.data['Schedd']

    factory_max_running=int(jobDescript.data['MaxRunning'])
    factory_max_idle=int(jobDescript.data['MaxIdle'])
    factory_max_held=int(jobDescript.data['MaxHeld'])

    all_security_names=sets.Set()

    done_something=0
    for work_key in work.keys():
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

        # Check whether the frontend is on the whitelist for the 
        # Entry point.
        if decrypted_params.has_key('SecurityName'):
                client_security_name=decrypted_params['SecurityName']
        else:
                # backwards compatibility
                client_security_name=client_int_name

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

        x509_proxy_fnames={}
        x509_proxy_usernames={}
        if decrypted_params.has_key('x509_proxy'):
            if decrypted_params['x509_proxy']==None:
                glideFactoryLib.log_files.logWarning("Could not decrypt x509_proxy for %s, skipping request"%client_int_name)
                continue #skip request

            # This old style protocol does not support SecurityName, use default
            x509_proxy_security_class="none"
            
            x509_proxy_username=frontendDescript.get_username(client_security_name,x509_proxy_security_class)
            if x509_proxy_username==None:
                glideFactoryLib.log_files.logWarning("No mapping for security class %s of x509_proxy for %s, skipping and trying the others"%(x509_proxy_security_class,client_int_name))
                continue # cannot map, skip proxy

            try:
                x509_proxy_fname=glideFactoryLib.update_x509_proxy_file(entry_name,x509_proxy_username,work_key,decrypted_params['x509_proxy'])
            except:
                glideFactoryLib.log_files.logWarning("Failed to update x509_proxy using usename %s for client %s, skipping request"%(x509_proxy_username,client_int_name))
                continue # skip request
            
            x509_proxy_fnames['main']=x509_proxy_fname
            x509_proxy_usernames['main']=x509_proxy_username
        elif decrypted_params.has_key('x509_proxy_0'):
            if not decrypted_params.has_key('nr_x509_proxies'):
                glideFactoryLib.log_files.logWarning("Could not determine number of proxies for %s, skipping request"%client_int_name)
                continue #skip request
            try:
                nr_x509_proxies=int(decrypted_params['nr_x509_proxies'])
            except:
                glideFactoryLib.log_files.logWarning("Invalid number of proxies for %s, skipping request"%client_int_name)
                continue # skip request

            for i in range(nr_x509_proxies):
                if decrypted_params['x509_proxy_%i'%i]==None:
                    glideFactoryLib.log_files.logWarning("Could not decrypt x509_proxy_%i for %s, skipping and trying the others"%(i,client_int_name))
                    continue #skip proxy
                if not decrypted_params.has_key('x509_proxy_%i_identifier'%i):
                    glideFactoryLib.log_files.logWarning("No identifier for x509_proxy_%i for %s, skipping and trying the others"%(i,client_int_name))
                    continue #skip proxy
                x509_proxy=decrypted_params['x509_proxy_%i'%i]
                x509_proxy_identifier=decrypted_params['x509_proxy_%i_identifier'%i]

                if decrypted_params.has_key('x509_proxy_%i_security_class'%i):
                    x509_proxy_security_class=decrypted_params['x509_proxy_%i_security_class'%i]
                else:
                    x509_proxy_security_class=x509_proxy_identifier

                # Deny Frontend from entering glideins if the whitelist
                # does not have its security class (or "All" for everyone)
                if (frontend_whitelist == "On")and(not x509_proxy_security_class in security_list[client_security_name])and (not "All" in security_list[client_security_name]):
                    glideFactoryLib.log_files.logWarning("Security class not in whitelist, skipping (%s %s) "%(client_authenticated_identity,x509_proxy_security_class))
                    continue # skip request
#                else:
#                    glideFactoryLib.log_files.logWarning("Security test passed for : %s %s "%(client_authenticated_identity,x509_proxy_security_class))

                x509_proxy_username=frontendDescript.get_username(client_security_name,x509_proxy_security_class)
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
                
                x509_proxy_fnames[x509_proxy_identifier]=x509_proxy_fname
                x509_proxy_usernames[x509_proxy_identifier]=x509_proxy_username

            if len(x509_proxy_fnames.keys())<1:
                glideFactoryLib.log_files.logWarning("No good proxies for %s, skipping request"%client_int_name)
                continue #skip request
        else:
            # no proxy passed, use factory one
            x509_proxy_security_class="factory"
            
            x509_proxy_username=frontendDescript.get_username(client_security_name,x509_proxy_security_class)
            if x509_proxy_username==None:
                glideFactoryLib.log_files.logWarning("No mapping for security class %s for %s (secid: %s), skipping frontend"%(x509_proxy_security_class,client_int_name,client_security_name))
                continue # cannot map, frontend

            x509_proxy_fnames['factory']=os.environ['X509_USER_PROXY'] # use the factory one
            x509_proxy_usernames['factory']=x509_proxy_username
        
        # Check if this entry point has a whitelist
        # If it does, then make sure that this frontend is in it.
        if (frontend_whitelist == "On")and(not security_list.has_key(x509_proxy_security_class)):
            glideFactoryLib.log_files.logWarning("Client %s not allowed to use entry point. Skipping security class %s "%(client_int_name,x509_proxy_security_class))
            continue #skip request

        #Check security class for downtime
        factory_downtimes=glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data['DowntimesFile'])
        glideFactoryLib.log_files.logActivity("Checking downtime for security class: %s (entry %s)."%(x509_proxy_security_class,jobDescript.data['EntryName']))

        in_sec_downtime=(factory_downtimes.checkDowntime(entry="factory",security_class=x509_proxy_security_class) or factory_downtimes.checkDowntime(entry=jobDescript.data['EntryName'],security_class=x509_proxy_security_class))
        if (in_sec_downtime):
            glideFactoryLib.log_files.logWarning("Security Class %s is currently in a downtime window for Entry: %s. Skipping request."%(x509_proxy_security_class,jobDescript.data['EntryName']))
            continue #skip request

        if work[work_key]['requests'].has_key('IdleGlideins'):
            idle_glideins=work[work_key]['requests']['IdleGlideins']
            if idle_glideins>factory_max_idle:
                idle_glideins=factory_max_idle
            
            if work[work_key]['requests'].has_key('MaxRunningGlideins'):
                max_running=work[work_key]['requests']['MaxRunningGlideins']
                if max_running>factory_max_running:
                    max_running=factory_max_running
            else:
                max_running=factory_max_running

            glideFactoryLib.logWorkRequest(client_int_name,client_security_name,
                                           idle_glideins, max_running,
                                           work[work_key])
            all_security_names.add(client_security_name)
            
            if in_downtime:
                # we are in downtime... no new submissions
                idle_glideins=0
                max_running=0
            

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
                    glideFactoryLib.log_files.logWarning("Malformed classad '%s', skipping"%work_key)
                    continue
            else:
                # old style
                client_web=None

            done_something+=perform_work(entry_name,schedd_name,
                                         work_key,client_int_name,client_security_name,client_int_req,
                                         idle_glideins,max_running,factory_max_held,
                                         jobDescript,x509_proxy_fnames,x509_proxy_usernames,
                                         client_web,params)
        #else, it is malformed and should be skipped

    for client_security_name in all_security_names:
        try:
            glideFactoryLib.factoryConfig.rrd_stats.getData(client_security_name)
        except glideFactoryLib.condorExe.ExeError,e:
            glideFactoryLib.log_files.logWarning("get_RRD_data failed: %s"%e)
        except:
            glideFactoryLib.log_files.logWarning("get_RRD_data failed: error unknown")
        

    return done_something

############################################################
def write_stats():
    global log_rrd_thread,qc_rrd_thread
    
    glideFactoryLib.factoryConfig.log_stats.write_file()
    glideFactoryLib.log_files.logActivity("log_stats written")
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
    entry_name=jobDescript.data['EntryName']
    allowed_proxy_source=glideinDescript.data['AllowedJobProxySource'].split(',')
    pub_key_obj=glideinDescript.data['PubKeyObj']

    current_qc_total=glideFactoryLib.factoryConfig.qc_stats.get_total()

    glidein_monitors={}
    for w in current_qc_total.keys():
        for a in current_qc_total[w].keys():
            glidein_monitors['Total%s%s'%(w,a)]=current_qc_total[w][a]
    try:
        myJobAttributes=jobAttributes.data.copy()
        myJobAttributes['GLIDEIN_In_Downtime']=in_downtime
        glideFactoryInterface.advertizeGlidein(glideFactoryLib.factoryConfig.factory_name,glideFactoryLib.factoryConfig.glidein_name,entry_name,
                                               glideFactoryLib.factoryConfig.supported_signtypes,
                                               myJobAttributes,jobParams.data.copy(),glidein_monitors.copy(),
                                               pub_key_obj,allowed_proxy_source)
    except:
        glideFactoryLib.log_files.logWarning("Advertize failed")

    # Advertise the monitoring
    advertizer=glideFactoryInterface.MultiAdvertizeGlideinClientMonitoring(glideFactoryLib.factoryConfig.factory_name,glideFactoryLib.factoryConfig.glidein_name,entry_name,
                                                                           jobAttributes.data.copy())

    current_qc_data=glideFactoryLib.factoryConfig.qc_stats.get_data()
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
    
    try:
        done_something = find_and_perform_work(in_downtime,glideinDescript,frontendDescript,jobDescript,jobParams)
    except:
        glideFactoryLib.log_files.logWarning("Error occurred while trying to find and do work.  ")
        
    if do_advertize or done_something:
        glideFactoryLib.log_files.logActivity("Advertize")
        advertize_myself(in_downtime,glideinDescript,jobDescript,jobAttributes,jobParams)
    
    return done_something

############################################################
def iterate(parent_pid,sleep_time,advertize_rate,
            glideinDescript,frontendDescript,jobDescript,jobAttributes,jobParams):
    is_first=1
    count=0;

    glideFactoryLib.factoryConfig.log_stats=glideFactoryMonitoring.condorLogSummary()
    glideFactoryLib.factoryConfig.rrd_stats = glideFactoryMonitoring.FactoryStatusData()
    factory_downtimes=glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data['DowntimesFile'])
    while 1:
        check_parent(parent_pid,glideinDescript,jobDescript)
        in_downtime=(factory_downtimes.checkDowntime(entry="factory") or factory_downtimes.checkDowntime(entry=jobDescript.data['EntryName']))
        if in_downtime:
            glideFactoryLib.log_files.logActivity("Downtime iteration at %s" % time.ctime())
        else:
            glideFactoryLib.log_files.logActivity("Iteration at %s" % time.ctime())
        try:
            glideFactoryLib.factoryConfig.log_stats.reset()
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
def main(parent_pid,sleep_time,advertize_rate,startup_dir,entry_name):
    startup_time=time.time()

    glideFactoryMonitoring.monitoringConfig.monitor_dir=os.path.join(startup_dir,"monitor/entry_%s"%entry_name)

    os.chdir(startup_dir)
    glideinDescript=glideFactoryConfig.GlideinDescript()

    glideinDescript.load_pub_key()
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
        glideFactoryInterface.factoryConfig.glideinwms_version = glideinWMSVersion.GlideinWMSDistro(os.path.dirname(os.path.dirname(sys.argv[0]))).version()
    except:
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logWarning("Exception occured while trying to retrieve the glideinwms version. See debug log for more details.")
        glideFactoryLib.log_files.logDebug("Exception occurred: %s" % tb)    


    # create lock file
    pid_obj=glideFactoryPidLib.EntryPidSupport(startup_dir,entry_name)
    
    # force integrity checks on all the operations
    # I need integrity checks also on reads, as I depend on them
    os.environ['_CONDOR_SEC_DEFAULT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_CLIENT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_READ_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_WRITE_INTEGRITY'] = 'REQUIRED'

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
    main(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4],sys.argv[5])
 

