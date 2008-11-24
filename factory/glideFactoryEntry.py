#!/bin/env python
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
import os.path
import sys
import fcntl
import traceback
import time
import string
import copy
import threading
sys.path.append(os.path.join(sys.path[0],"../lib"))

import glideFactoryPidLib
import glideFactoryConfig
import glideFactoryLib
import glideFactoryMonitoring
import glideFactoryInterface
import glideFactoryLogParser
import glideFactoryDowntimeLib
import logSupport

# this thread will be used for lazy updates of rrd history conversions
log_rrd_thread=None
qc_rrd_thread=None

############################################################
def check_parent(parent_pid):
    if os.path.exists('/proc/%s'%parent_pid):
        return # parent still exists, we are fine
    
    glideFactoryLib.factoryConfig.activity_log.write("Parent died, exit.")    
    raise KeyboardInterrupt,"Parent died"


############################################################
def perform_work(factory_name,glidein_name,entry_name,
                 schedd_name,
                 client_name,client_int_name,client_int_req,
                 idle_glideins,max_running,max_held,
                 jobDescript,
                 x509_proxy_fname,params):
    glideFactoryLib.factoryConfig.client_internals[client_int_name]={"CompleteName":client_name,"ReqName":client_int_req}

    if params.has_key("GLIDEIN_Collector"):
        condor_pool=params["GLIDEIN_Collector"]
    else:
        condor_pool=None
    
    #glideFactoryLib.factoryConfig.activity_log.write("QueryQ (%s,%s,%s,%s,%s)"%(factory_name,glidein_name,entry_name,client_name,schedd_name))
    condorQ=glideFactoryLib.getCondorQData(factory_name,glidein_name,entry_name,client_name,schedd_name)
    #glideFactoryLib.factoryConfig.activity_log.write("QueryS (%s,%s,%s,%s,%s)"%(factory_name,glidein_name,entry_name,client_name,schedd_name))

    # Temporary disable queries to the collector
    # Not really used by anybody, so let reduce the load
    #try:
    #    condorStatus=glideFactoryLib.getCondorStatusData(factory_name,glidein_name,entry_name,client_name,condor_pool)
    #except:
    if 1:
        condorStatus=None # this is not fundamental information, can live without
    #glideFactoryLib.factoryConfig.activity_log.write("Work")
    lck=glideFactoryMonitoring.monitoringConfig.get_disk_lock()
    try:
      log_stats=glideFactoryLogParser.dirSummaryTimingsOut("entry_%s/log"%entry_name,client_name)
      log_stats.load()
    finally:
      lck.close()

    glideFactoryLib.logStats(condorQ,condorStatus,client_int_name)
    glideFactoryLib.factoryConfig.log_stats.logSummary(client_int_name,log_stats)


    submit_attrs=[]

    # use the extended params for submission
    nr_submitted=glideFactoryLib.keepIdleGlideins(condorQ,idle_glideins,max_running,max_held,submit_attrs,x509_proxy_fname,params)
    if nr_submitted>0:
        #glideFactoryLib.factoryConfig.activity_log.write("Submitted")
        return 1 # we submitted somthing, return immediately

    if condorStatus!=None: # temporary glitch, no sanitization this round
        #glideFactoryLib.factoryConfig.activity_log.write("Sanitize")
        glideFactoryLib.sanitizeGlideins(condorQ,condorStatus)
    else:
        glideFactoryLib.sanitizeGlideinsSimple(condorQ)
    
    #glideFactoryLib.factoryConfig.activity_log.write("Work done")
    return 0
    

############################################################
def find_and_perform_work(in_downtime,glideinDescript,jobDescript,jobParams):
    factory_name=glideinDescript.data['FactoryName']
    glidein_name=glideinDescript.data['GlideinName']
    entry_name=jobDescript.data['EntryName']
    pub_key_obj=glideinDescript.data['PubKeyObj']
    allowed_proxy_source=glideinDescript.data['AllowedJobProxySource'].split(',')

    #glideFactoryLib.factoryConfig.activity_log.write("Find work")
    work = glideFactoryInterface.findWork(factory_name,glidein_name,entry_name,pub_key_obj,allowed_proxy_source)
    glideFactoryLib.logWorkRequests(work)
    
    if len(work.keys())==0:
        return 0 # nothing to be done

    #glideFactoryLib.factoryConfig.activity_log.write("Perform work")
    schedd_name=jobDescript.data['Schedd']

    factory_max_running=int(jobDescript.data['MaxRunning'])
    factory_max_idle=int(jobDescript.data['MaxIdle'])
    factory_max_held=int(jobDescript.data['MaxHeld'])

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

        x509_proxy_fname=os.environ['X509_USER_PROXY'] # by default use factory proxy
        if decrypted_params.has_key('x509_proxy'):
            if decrypted_params['x509_proxy']==None:
                glideFactoryLib.factoryConfig.warning_log.write("Could not decrypt x509_proxy for %s, skipping request"%client_int_name)
                continue #skip request
            x509_proxy_fname=glideFactoryLib.update_x509_proxy_file(work_key,decrypted_params['x509_proxy'])
            if not ('frontend' in allowed_proxy_source):
                glideFactoryLib.factoryConfig.warning_log.write("Client %s provided proxy, but cannot use it. Skipping request"%client_int_name)
                continue #skip request
        else:
            if not ('factory' in allowed_proxy_source):
                glideFactoryLib.factoryConfig.warning_log.write("Client %s did not provide a proxy, but cannot use factory one. Skipping request"%client_int_name)
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

            if in_downtime:
                # we are in downtime... no new submissions
                idle_glideins=0
                max_running=0
            
            done_something+=perform_work(factory_name,glidein_name,entry_name,schedd_name,
                                         work_key,client_int_name,client_int_req,
                                         idle_glideins,max_running,factory_max_held,
                                         jobDescript,x509_proxy_fname,params)
        #else, it is malformed and should be skipped

    return done_something

############################################################
def write_stats():
    global log_rrd_thread,qc_rrd_thread
    
    glideFactoryLib.factoryConfig.log_stats.write_file()
    glideFactoryLib.factoryConfig.activity_log.write("log_stats written")
    glideFactoryLib.factoryConfig.qc_stats.write_file()
    glideFactoryLib.factoryConfig.activity_log.write("qc_stats written")

    # keep just one thread per monitoring type running at any given time
    # if the old one is still running, do nothing (lazy)
    # create_support_history can take a-while
    if log_rrd_thread==None:
        thread_alive=0
    else:
        thread_alive=log_rrd_thread.isAlive()
        if not thread_alive:
            glideFactoryLib.factoryConfig.activity_log.write("Waiting for thread")
            log_rrd_thread.join()

    if not thread_alive:
        glideFactoryLib.factoryConfig.activity_log.write("Writing lazy stats for logSummary")
        log_copy=copy.deepcopy(glideFactoryLib.factoryConfig.log_stats)
        log_rrd_thread=threading.Thread(target=log_copy.create_support_history)
        log_rrd_thread.start()

    # -----
    if qc_rrd_thread==None:
        thread_alive=0
    else:
        thread_alive=qc_rrd_thread.isAlive()
        if not thread_alive:
            qc_rrd_thread.join()

    if not thread_alive:
        glideFactoryLib.factoryConfig.activity_log.write("Writing lazy stats for qc")
        qc_copy=copy.deepcopy(glideFactoryLib.factoryConfig.qc_stats)
        qc_rrd_thread=threading.Thread(target=qc_copy.create_support_history)
        qc_rrd_thread.start()

    return

############################################################
def advertize_myself(in_downtime,glideinDescript,jobDescript,jobAttributes,jobParams):
    factory_name=glideinDescript.data['FactoryName']
    glidein_name=glideinDescript.data['GlideinName']
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
        glideFactoryInterface.advertizeGlidein(factory_name,glidein_name,entry_name,
                                               myJobAttributes,jobParams.data.copy(),glidein_monitors.copy(),
                                               pub_key_obj,allowed_proxy_source)
    except:
        glideFactoryLib.factoryConfig.warning_log.write("Advertize failed")

    current_qc_data=glideFactoryLib.factoryConfig.qc_stats.get_data()
    for client_name in current_qc_data.keys():
        client_qc_data=current_qc_data[client_name]
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
        try:
            glideFactoryInterface.advertizeGlideinClientMonitoring(factory_name,glidein_name,entry_name,client_internals["CompleteName"],client_name,client_internals["ReqName"],jobAttributes.data.copy(),params,client_monitors.copy())
        except:
            glideFactoryLib.factoryConfig.warning_log.write("Advertize of '%s' failed"%client_name)
        

    return

############################################################
def iterate_one(do_advertize,in_downtime,
                glideinDescript,jobDescript,jobAttributes,jobParams):
    done_something = find_and_perform_work(in_downtime,glideinDescript,jobDescript,jobParams)

    if do_advertize or done_something:
        glideFactoryLib.factoryConfig.activity_log.write("Advertize")
        advertize_myself(in_downtime,glideinDescript,jobDescript,jobAttributes,jobParams)
    
    return done_something

############################################################
def iterate(parent_pid,cleanupObjs,sleep_time,advertize_rate,
            glideinDescript,jobDescript,jobAttributes,jobParams):
    is_first=1
    count=0;

    glideFactoryLib.factoryConfig.log_stats=glideFactoryMonitoring.condorLogSummary()
    factory_downtimes=glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data['DowntimesFile'])
    entry_downtimes=glideFactoryDowntimeLib.DowntimeFile(jobDescript.data['DowntimesFile'])
    while 1:
        check_parent(parent_pid)
        in_downtime=(factory_downtimes.checkDowntime() or entry_downtimes.checkDowntime())
        if in_downtime:
            glideFactoryLib.factoryConfig.activity_log.write("Downtime iteration at %s" % time.ctime())
        else:
            glideFactoryLib.factoryConfig.activity_log.write("Iteration at %s" % time.ctime())
        try:
            glideFactoryLib.factoryConfig.log_stats.reset()
            glideFactoryLib.factoryConfig.qc_stats=glideFactoryMonitoring.condorQStats()
            glideFactoryLib.factoryConfig.client_internals = {}

            done_something=iterate_one(count==0,in_downtime,
                                       glideinDescript,jobDescript,jobAttributes,jobParams)
            
            glideFactoryLib.factoryConfig.activity_log.write("Writing stats")
            try:
                write_stats()
            except KeyboardInterrupt:
                raise # this is an exit signal, pass through
            except:
                # never fail for stats reasons!
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                glideFactoryLib.factoryConfig.warning_log.write("Exception at %s: %s" % (time.ctime(),tb))                
        except KeyboardInterrupt:
            raise # this is an exit signal, pass through
        except:
            if is_first:
                raise
            else:
                # if not the first pass, just warn
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                glideFactoryLib.factoryConfig.warning_log.write("Exception at %s: %s" % (time.ctime(),tb))
                
        for cleanupObj in cleanupObjs:
            cleanupObj.cleanup()

        glideFactoryLib.factoryConfig.activity_log.write("Sleep %is"%sleep_time)
        time.sleep(sleep_time)
        count=(count+1)%advertize_rate
        is_first=0
        
        
############################################################
def main(parent_pid,sleep_time,advertize_rate,startup_dir,entry_name):
    startup_time=time.time()

    # create log files in the glidein log directory
    activity_log=logSupport.DayLogFile(os.path.join(startup_dir,"entry_%s/log/factory_info"%entry_name))
    warning_log=logSupport.DayLogFile(os.path.join(startup_dir,"entry_%s/log/factory_err"%entry_name))
    glideFactoryLib.factoryConfig.activity_log=activity_log
    glideFactoryLib.factoryConfig.warning_log=warning_log
    
    glideFactoryMonitoring.monitoringConfig.monitor_dir=os.path.join(startup_dir,"monitor/entry_%s"%entry_name)
    glideFactoryMonitoring.monitoringConfig.log_dir=os.path.join(startup_dir,"entry_%s/log"%entry_name)

    os.chdir(startup_dir)
    glideinDescript=glideFactoryConfig.GlideinDescript()
    glideinDescript.load_pub_key()
    if not (entry_name in string.split(glideinDescript.data['Entries'],',')):
        raise RuntimeError, "Entry '%s' not supported: %s"%(entry_name,glideinDescript.data['Entries'])
    jobDescript=glideFactoryConfig.JobDescript(entry_name)
    jobAttributes=glideFactoryConfig.JobAttributes(entry_name)
    jobParams=glideFactoryConfig.JobParams(entry_name)

    logCleanupObj=logSupport.DirCleanupWSpace(os.path.join(startup_dir,"entry_%s/log"%entry_name),"(factory_info\..*)|(factory_err\..*)",
                                              float(glideinDescript.data['LogRetentionMaxDays'])*24*3600,
                                              float(glideinDescript.data['LogRetentionMinDays'])*24*3600,
                                              float(glideinDescript.data['LogRetentionMaxMBs'])*1024*1024,
                                              activity_log,warning_log)

    jobCleanupObj=logSupport.DirCleanupWSpace(os.path.join(startup_dir,"entry_%s/log"%entry_name),"(job\..*\.out)|(job\..*\.err)",
                                              float(glideinDescript.data['JobLogRetentionMaxDays'])*24*3600,
                                              float(glideinDescript.data['JobLogRetentionMinDays'])*24*3600,
                                              float(glideinDescript.data['JobLogRetentionMaxMBs'])*1024*1024,
                                              activity_log,warning_log)
    summaryCleanupObj=logSupport.DirCleanupWSpace(os.path.join(startup_dir,"entry_%s/log"%entry_name),"(completed_jobs_\..*\.log)",
                                                  float(glideinDescript.data['SummaryLogRetentionMaxDays'])*24*3600,
                                                  float(glideinDescript.data['SummaryLogRetentionMinDays'])*24*3600,
                                                  float(glideinDescript.data['SummaryLogRetentionMaxMBs'])*1024*1024,
                                                  activity_log,warning_log)

    condorCleanupObj=logSupport.DirCleanupWSpace(os.path.join(startup_dir,"entry_%s/log"%entry_name),"(condor_activity_\..*\.log)|(condor_activity_\..*\.log.ftstpk)",
                                                 float(glideinDescript.data['CondorLogRetentionMaxDays'])*24*3600,
                                                 float(glideinDescript.data['CondorLogRetentionMinDays'])*24*3600,
                                                 float(glideinDescript.data['CondorLogRetentionMaxMBs'])*1024*1024,
                                                 activity_log,warning_log)

    # use config values to configure the factory
    glideFactoryMonitoring.monitoringConfig.wanted_graphs=string.split(glideinDescript.data['EntryWantedMonitorGraphs'],',')
    glideFactoryLib.factoryConfig.max_submits=int(jobDescript.data['MaxSubmitRate'])
    glideFactoryLib.factoryConfig.max_cluster_size=int(jobDescript.data['SubmitCluster'])
    glideFactoryLib.factoryConfig.submit_sleep=float(jobDescript.data['SubmitSleep'])
    glideFactoryLib.factoryConfig.max_removes=int(jobDescript.data['MaxRemoveRate'])
    glideFactoryLib.factoryConfig.remove_sleep=float(jobDescript.data['RemoveSleep'])
    glideFactoryLib.factoryConfig.max_releases=int(jobDescript.data['MaxReleaseRate'])
    glideFactoryLib.factoryConfig.release_sleep=float(jobDescript.data['ReleaseSleep'])

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
                glideFactoryLib.factoryConfig.activity_log.write("Starting up")
                iterate(parent_pid,
                        (jobCleanupObj,logCleanupObj,summaryCleanupObj,condorCleanupObj),
                        sleep_time,advertize_rate,
                        glideinDescript,jobDescript,jobAttributes,jobParams)
            except KeyboardInterrupt:
                glideFactoryLib.factoryConfig.activity_log.write("Received signal...exit")
            except:
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                glideFactoryLib.factoryConfig.warning_log.write("Exception at %s: %s" % (time.ctime(),tb))
                raise
        finally:
            try:
                glideFactoryLib.factoryConfig.activity_log.write("Deadvertize of (%s,%s,%s)"%(glideinDescript.data['FactoryName'],
                                                                                              glideinDescript.data['GlideinName'],
                                                                                              jobDescript.data['EntryName']))
                glideFactoryInterface.deadvertizeGlidein(glideinDescript.data['FactoryName'],
                                                         glideinDescript.data['GlideinName'],
                                                         jobDescript.data['EntryName'])
                glideFactoryInterface.deadvertizeAllGlideinClientMonitoring(glideinDescript.data['FactoryName'],
                                                                            glideinDescript.data['GlideinName'],
                                                                            jobDescript.data['EntryName'])
            except:
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                glideFactoryLib.factoryConfig.warning_log.write("Failed to deadvertize of (%s,%s,%s)"%(glideinDescript.data['FactoryName'],
                                                                                                       glideinDescript.data['GlideinName'],
                                                                                                       jobDescript.data['EntryName']))
                glideFactoryLib.factoryConfig.warning_log.write("Exception at %s: %s" % (time.ctime(),tb))
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
 

