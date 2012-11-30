#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This is the glideinFactoryEntryGroup. Common Tasks like queering collector
#   and advertizing the work done by group are done here
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
import sets
import cPickle

sys.path.append(os.path.join(sys.path[0],"../lib"))

import glideFactoryPidLib
import glideFactoryMonitoring
import glideFactoryLogParser
import glideFactoryDowntimeLib
import glideFactoryEntry
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
    
    gfl.log_files.logActivity("Parent died, exit.")    

    # there is nobody to clean up after ourselves... do it here
    gfl.log_files.logActivity("Deadvertize myself")
    
    try:
        gfi.deadvertizeGlidein(
            glideinDescript.data['FactoryName'],	 
            glideinDescript.data['GlideinName'],	 
            jobDescript.data['EntryName'])	 
    except:
        gfl.log_files.logWarning("Failed to deadvertize myself")


    try:
        gfi.deadvertizeAllGlideinClientMonitoring(
            glideinDescript.data['FactoryName'],	 
            glideinDescript.data['GlideinName'],	 
            jobDescript.data['EntryName'])	 
    except:
        gfl.log_files.logWarning("Failed to deadvertize my monitoring")

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
            
    gfl.factoryConfig.client_internals[client_int_name]={"CompleteName":client_name,"ReqName":client_int_req}

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
    log_stats[x509_proxy_username+":"+client_int_name]=glideFactoryLogParser.dirSummaryTimingsOut(gfl.factoryConfig.get_client_log_dir(entry_name,x509_proxy_username),
                                                                              gfl.log_files.log_dir,
                                                                              client_int_name,x509_proxy_username)
    # should not need privsep for reading logs
    log_stats[x509_proxy_username+":"+client_int_name].load()

    gfl.logStats(condorQ,condorStatus,client_int_name,client_security_name,x509_proxy_security_class)
    client_log_name=gfl.secClass2Name(client_security_name,x509_proxy_security_class)
    gfl.factoryConfig.log_stats.logSummary(client_log_name,log_stats)

    # use the extended params for submission
    proxy_fraction=1.0/len(x509_proxy_keys)

    # I will shuffle proxies around, so I may as well round up all of them
    idle_glideins_pproxy=int(math.ceil(idle_glideins*proxy_fraction))
    max_glideins_pproxy=int(math.ceil(max_running*proxy_fraction))

    # not reducing the held, as that is effectively per proxy, not per request
    nr_submitted=0
    for x509_proxy_id in x509_proxy_keys:
        nr_submitted+=gfl.keepIdleGlideins(condorQ,client_int_name,
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
    log_work_info(work, key='existing')



    # If old key is valid, find the work using old key as well and append it
    # to existing work dictionary
    if (old_pub_key_obj != None):
        work_oldkey = {}
        # still using the old key in this cycle
        gfl.log_files.logActivity("Old factory key is still valid. Trying to find work using old factory key.")
        work_oldkey = gfi.findGroupWork(gfl.factoryConfig.factory_name,
                                        gfl.factoryConfig.glidein_name,
                                        my_entries.keys(),
                                        gfl.factoryConfig.supported_signtypes,
                                        old_pub_key_obj, allowed_proxy_source)
        log_work_info(work, key='old')

        # Merge the work_oldkey with work
        for w in work_oldkey.keys():
            if work.has_key(w):
                # This should not happen but still as a safegaurd warn
                gfl.log_files.logActivity("Work task for %s exists using existing key and old key. Ignoring the work from old key." % w)
                gfl.log_files.logError("Work task for %s exists using existing key and old key. Ignoring the work from old key." % w)
                continue
            work[w] = work_oldkey[w]

    return work


def log_work_info(work, key=''):
    keylogstr = ''
    if key.strip() != '':
        gfl.log_files.logActivity('Work tasks grouped by entries using %s factory key' % (key))
    else:
        gfl.log_files.logActivity('Work tasks grouped by entries')

    for entry in work:
        # Only log if there is work to do
        if len(work[entry]) > 0:
            gfl.log_files.logActivity("Entry: %s (Tasks: %s)" % (entry, len(work[entry])))


def get_work_count(work):
    count = 0
    for entry in work:
        count += len(work[entry])
    return count

###############################
def fetch_fork_result(r, pid):
    """
    Used with fork clients
    Args:
     r    - input pipe
     pid - pid of the child
    """

    try:
        rin = ""
        s = os.read(r, 1024*1024)
        while (s != ""): # "" means EOF
            rin += s
            s = os.read(r,1024*1024)
    finally:
        os.close(r)
        os.waitpid(pid, 0)

    out = cPickle.loads(rin)
    return out

def fetch_fork_result_list(pipe_ids):
    """
       in: pipe_ids - dict, of {'r':r,'pid':pid} keyed on entry name
       out: dictionary of fork_results
    """

    out = {}
    failures = 0
    for entry in pipe_ids:
        try:
            # Collect the results
            out[entry] = fetch_fork_result(pipe_ids[entry]['r'],
                                           pipe_ids[entry]['pid'])
        except Exception, e:
            gfl.log_files.logWarning("Failed to retrieve work done for entry subprocess '%s'" % entry)
            gfl.log_files.logDebug("Failed to retrieve work done for entry subprocess '%s': %s" % (entry, e))
            failures += 1

    if failures>0:
        raise RuntimeError, "Found %i errors" % failures

    return out

###############################


def find_and_perform_work(factory_in_downtime, glideinDescript,
                          frontendDescript, group_name, my_entries):
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
    
    # Step 1:
    # Find work to perform. Work is a dict work[entry_name][frontend]
    # We may or may not be able to perform all the work but that will be
    # checked later per entry

    work = {}
    work = find_work(factory_in_downtime, glideinDescript,
                     frontendDescript, group_name, my_entries)   

    work_count = get_work_count(work)
    if (work_count == 0):
        gfl.log_files.logActivity("No work found")
        return 0

    gfl.log_files.logActivity("Found %s total tasks to work on" % work_count)

    # Got the work items grouped by entries
    # Now fork a process per entry and wait for certain duration to get back
    # the results. Kill processes if they take too long to get back with result

    # TODO: PM: Following should be multithreaded non-blocking

    # ids keyed by entry name
    pipe_ids = {}

    for entry in my_entries.values():
        r,w = os.pipe()
        pid = os.fork()
        if pid != 0:
            # This is the original process
            gfl.log_files.logActivity("In check_and_perform_work process with pid %s for entry %s" % (pid, entry.name))
            os.close(w)
            pipe_ids[entry.name] = {'r': r, 'pid': pid}
        else:
            # This is the child process
            gfl.log_files.logActivity("Forked check_and_perform_work process with pid %s for entry %s" % (pid, entry.name))
            os.close(r)

            try:
                work_done = glideFactoryEntry.check_and_perform_work(
                                factory_in_downtime, group_name,
                                entry, work[entry.name])
                # entry object now has updated info in the child process
                # This info is required for monitoring and advertising
                # return the updated entry object back to the parent
                #return_dict = {entry.name: {'entry': entry,
                #                            'work_done': work_done}}
                return_dict = {'entry_obj': entry, 'work_done': work_done}
                os.write(w,cPickle.dumps(return_dict))
            except Exception, ex:
                tb = traceback.format_exception(sys.exc_info()[0],
                                                sys.exc_info()[1],
                                                sys.exc_info()[2])
                entry.logFiles.logDebug("Error in talking to the factory pool: %s" % tb)

            os.close(w)
            # Hard kill myself. Don't want any cleanup, since I was created
            # just for doing check and perform work for each entry
            os.kill(os.getpid(),signal.SIGKILL)

    # Gather results from the forked children
    gfl.log_files.logActivity("All children terminated")
    work_info_read_err = False
    try:
        post_work_info = fetch_fork_result_list(pipe_ids)
    except RuntimeError:
        # Expect all errors logged already
        work_info_read_err = True
        gfl.log_files.logWarning("Unable to process response from check_and_perform_work")
        # PM: TODO: Whats the best action? Ignore or return?
        #           We may have to ignore bad info and continue with the 
        #           good info. How to update the monitoring and etc in this
        #           case? We dont want errors in one entry to affect other
        #           entries. Needs further discussion


    # Work done by group keyed by entry name
    groupwork_done = {}

    if not work_info_read_err:
        # Entry object changes after doing work. Just capture the entry object
        # from the child process and use it for further processing
        for entry in my_entries = {}
            my_entries[entry] = post_work_info[entry]['entry_obj']
            groupwork_done[entry] = post_work_info[entry]['work_done']
    
    return groupwork_done

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
    
    gfl.factoryConfig.log_stats.computeDiff()
    gfl.factoryConfig.log_stats.write_file()
    gfl.log_files.logActivity("log_stats written")
    gfl.factoryConfig.qc_stats.finalizeClientMonitor()
    gfl.factoryConfig.qc_stats.write_file()
    gfl.log_files.logActivity("qc_stats written")
    gfl.factoryConfig.rrd_stats.writeFiles()
    gfl.log_files.logActivity("rrd_stats written")
    
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
        gfl.log_files.logDebug("IOError in writeFile in descript2XML")

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

    gfl.factoryConfig.client_stats.finalizeClientMonitor()

    current_qc_total=gfl.factoryConfig.client_stats.get_total()

    glidein_monitors={}
    for w in current_qc_total.keys():
        for a in current_qc_total[w].keys():
            glidein_monitors['Total%s%s'%(w,a)]=current_qc_total[w][a]
    try:
        # Make copy of job attributes so can override the validation downtime setting with the true setting of the entry (not from validation)
        myJobAttributes=jobAttributes.data.copy()
        myJobAttributes['GLIDEIN_In_Downtime']=in_downtime
        gfi.advertizeGlidein(gfl.factoryConfig.factory_name,gfl.factoryConfig.glidein_name,entry_name,
                                               gfl.factoryConfig.supported_signtypes,
                                               myJobAttributes,jobParams.data.copy(),glidein_monitors.copy(),
                                               pub_key_obj,allowed_proxy_source)
    except:
        gfl.log_files.logWarning("Advertize failed")

    # Advertise the monitoring, use the downtime found in validation of the credentials
    monitor_job_attrs = jobAttributes.data.copy()
    advertizer=gfi.MultiAdvertizeGlideinClientMonitoring(gfl.factoryConfig.factory_name,gfl.factoryConfig.glidein_name,entry_name,
                                                                           monitor_job_attrs)

    current_qc_data=gfl.factoryConfig.client_stats.get_data()
    for client_name in current_qc_data.keys():
        client_qc_data=current_qc_data[client_name]
        if not gfl.factoryConfig.client_internals.has_key(client_name):
            gfl.log_files.logWarning("Client '%s' has stats, but no classad! Ignoring."%client_name)
            continue
        client_internals=gfl.factoryConfig.client_internals[client_name]

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
            if p in params.keys():
                # Can only overwrite existing params, not create new ones
                params[p]=fparams[p]
        advertizer.add(client_internals["CompleteName"],client_name,client_internals["ReqName"],
                       params,client_monitors.copy())
        
    try:
        advertizer.do_advertize()
    except:
        gfl.log_files.logWarning("Advertize of monitoring failed")
        

    return

############################################################
"""
             done_something = iterate_one(count==0, factory_in_downtime,
                                         glideinDescript, frontendDescript,
                                         group_name, my_entries)
"""

def iterate_one(do_advertize, factory_in_downtime, glideinDescript,
                frontendDescript, group_name, my_entries):
    
    groupwork_done = {}

    for entry in my_entries.values():
        entry.initIteration(factory_in_downtime)

    try:
        groupwork_done = find_and_perform_work(factory_in_downtime, 
                                               glideinDescript,
                                               frontendDescript,
                                               group_name, my_entries)
    except:
        gfl.log_files.logWarning("Error occurred while trying to find and do work.")
        




    for entry in my_entries.values():
        # Advertise if work was done or if advertise flag is set
        # TODO: PM: Advertising can be optimized by grouping multiple entry
        #           ads together. For now do it one at a time.
        if ( (do_advertize) or 
             ((groupwork_done.get(entry.name)).get('work_done')) ) :
            gfl.log_files.logActivity("Advertising %s" % entry.name)

            # PM: I AM HERE WRITING entry.advertise 30 Nov 2012
            entry.advertise(factory_in_downtime)
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
                for entry in my_entries.values():
                    entry.writeStats()
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

def init_logs(name, entity, log_dir, glideinDescript):
    gfl.log_files_dict[entity][name] = gfl.LogFiles(
        log_dir,
        float(glideinDescript.data['LogRetentionMaxDays']),
        float(glideinDescript.data['LogRetentionMinDays']),
        float(glideinDescript.data['LogRetentionMaxMBs']))

    # TODO: PM: What to do with warning_log.
    #       Is this correct? Or do we need warning logs for every entry?
    #       If so how to we instantiate it?
    gfi.factoryConfig.warning_log = gfl.log_files_dict[entity][name].warning_log

def init_group_logs(name, glideinDescript):
    log_dir = os.path.join(glideinDescript.data['LogDir'], 'factory')
    init_logs(name, 'group', log_dir, glideinDescript)

def init_entry_logs(name, glideinDescript):
    log_dir = os.path.join(glideinDescript.data['LogDir'], "entry_%s"%name)
    init_logs(name, 'entry', log_dir, glideinDescript)
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
    gfl.set_condor_integrity_checks()

    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), 
         sys.argv[4], sys.argv[5], sys.argv[6])
 

