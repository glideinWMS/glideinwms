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
sys.path.append("../lib")

import glideFactoryConfig
import glideFactoryLib
import glideFactoryMonitoring
import glideFactoryInterface
import glideFactoryLogParser
import logSupport

# this thread will be used for lazy updates of rrd history conversions
log_rrd_thread=None
qc_rrd_thread=None


############################################################
def perform_work(factory_name,glidein_name,entry_name,
                 schedd_name,
                 client_name,idle_glideins,
                 jobDescript,
                 params):
    if params.has_key("GLIDEIN_Collector"):
        condor_pool=params["GLIDEIN_Collector"]
    else:
        condor_pool=None
    
    #glideFactoryLib.factoryConfig.activity_log.write("QueryQ (%s,%s,%s,%s,%s)"%(factory_name,glidein_name,entry_name,client_name,schedd_name))
    condorQ=glideFactoryLib.getCondorQData(factory_name,glidein_name,entry_name,client_name,schedd_name)
    #glideFactoryLib.factoryConfig.activity_log.write("QueryS (%s,%s,%s,%s,%s)"%(factory_name,glidein_name,entry_name,client_name,schedd_name))
    condorStatus=glideFactoryLib.getCondorStatusData(factory_name,glidein_name,entry_name,client_name,condor_pool)
    #glideFactoryLib.factoryConfig.activity_log.write("Work")
    log_stats=glideFactoryLogParser.dirSummary("log",client_name)
    log_stats.load()

    glideFactoryLib.logStats(condorQ,condorStatus)
    glideFactoryLib.factoryConfig.log_stats.logSummary(client_name,log_stats)


    submit_attrs=[]

    submit_attrs.append(jobDescript.data["GridType"])
    submit_attrs.append(jobDescript.data["Gatekeeper"])

    if jobDescript.data.has_key("GlobusRSL"):
        submit_attrs.append("globus_rsl = %s"%jobDescript.data["GlobusRSL"])
    else:
        submit_attrs.append("") #something is needed, empty string is fine
        
    submit_attrs.append("-dir")
    submit_attrs.append(jobDescript.data["StartupDir"])

    if jobDescript.data.has_key("ProxyURL"):
        submit_attrs.apeend("-proxy")
        submit_attrs.append(jobDescript.data["ProxyURL"])

    # use the extended params for submission
    nr_submitted=glideFactoryLib.keepIdleGlideins(condorQ,idle_glideins,submit_attrs,params)
    if nr_submitted>0:
        #glideFactoryLib.factoryConfig.activity_log.write("Submitted")
        return 1 # we submitted somthing, return immediately

    #glideFactoryLib.factoryConfig.activity_log.write("Sanitize")

    glideFactoryLib.sanitizeGlideins(condorQ,condorStatus)
    
    #glideFactoryLib.factoryConfig.activity_log.write("Work done")
    return 0
    

############################################################
def find_and_perform_work(glideinDescript,jobDescript,jobParams):
    factory_name=glideinDescript.data['FactoryName']
    glidein_name=glideinDescript.data['GlideinName']
    entry_name=jobDescript.data['EntryName']

    #glideFactoryLib.factoryConfig.activity_log.write("Find work")
    work = glideFactoryInterface.findWork(factory_name,glidein_name,entry_name)
    glideFactoryLib.logWorkRequests(work)
    
    if len(work.keys())==0:
        return 0 # nothing to be done

    #glideFactoryLib.factoryConfig.activity_log.write("Perform work")
    schedd_name=glideinDescript.data['Schedd']

    done_something=0
    for work_key in work.keys():
        # merge work and default params
        params=work[work_key]['params']

        # add default values if not defined
        for k in jobParams.data.keys():
            if not (k in params.keys()):
                params[k]=jobParams.data[k]

        if work[work_key]['requests'].has_key('IdleGlideins'):
            done_something+=perform_work(factory_name,glidein_name,entry_name,schedd_name,
                                         work_key,work[work_key]['requests']['IdleGlideins'],
                                         jobDescript,params)
        #else, it is malformed and should be skipped

    return done_something

############################################################
def write_stats():
    global log_rrd_thread,qc_rrd_thread
    
    glideFactoryLib.factoryConfig.log_stats.write_file()
    glideFactoryLib.factoryConfig.qc_stats.write_file()

    # keep just one thread per monitoring type running at any given time
    # if the old one is still running, do nothing (lazy)
    # create_support_history can take a-while
    if log_rrd_thread==None:
        thread_alive=0
    else:
        thread_alive=log_rrd_thread.isAlive()
        if not thread_alive:
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
def advertize_myself(glideinDescript,jobDescript,jobAttributes,jobParams):
    factory_name=glideinDescript.data['FactoryName']
    glidein_name=glideinDescript.data['GlideinName']
    entry_name=jobDescript.data['EntryName']

    current_qc_total=glideFactoryLib.factoryConfig.qc_stats.get_total()

    glidein_monitors={}
    for w in current_qc_total.keys():
        for a in current_qc_total[w].keys():
            glidein_monitors['Total%s%s'%(w,a)]=current_qc_total[w][a]
    try:
        glideFactoryInterface.advertizeGlidein(factory_name,glidein_name,entry_name,jobAttributes.data.copy(),jobParams.data.copy(),glidein_monitors.copy())
    except:
        glideFactoryLib.factoryConfig.warning_log.write("Advertize failed")

    current_qc_data=glideFactoryLib.factoryConfig.qc_stats.get_data()
    for client_name in current_qc_data.keys():
        client_qc_data=current_qc_data[client_name]

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
            glideFactoryInterface.advertizeGlideinClientMonitoring(factory_name,glidein_name,entry_name,client_name,jobAttributes.data.copy(),params,client_monitors.copy())
        except:
            glideFactoryLib.factoryConfig.warning_log.write("Advertize of '%s' failed"%client_name)
        

    return

############################################################
def iterate_one(do_advertize,
                glideinDescript,jobDescript,jobAttributes,jobParams):
    done_something = find_and_perform_work(glideinDescript,jobDescript,jobParams)

    if do_advertize or done_something:
        glideFactoryLib.factoryConfig.activity_log.write("Advertize")
        advertize_myself(glideinDescript,jobDescript,jobAttributes,jobParams)
    
    return done_something

############################################################
def iterate(cleanupObj,sleep_time,advertize_rate,
            glideinDescript,jobDescript,jobAttributes,jobParams):
    is_first=1
    count=0;

    glideFactoryLib.factoryConfig.log_stats=glideFactoryMonitoring.condorLogSummary()
    while 1:
        glideFactoryLib.factoryConfig.activity_log.write("Iteration at %s" % time.ctime())
        try:
            glideFactoryLib.factoryConfig.log_stats.reset()
            glideFactoryLib.factoryConfig.qc_stats=glideFactoryMonitoring.condorQStats()

            done_something=iterate_one(count==0,
                                       glideinDescript,jobDescript,jobAttributes,jobParams)
            
            glideFactoryLib.factoryConfig.activity_log.write("Writing stats")
            write_stats()
        except:
            if is_first:
                raise
            else:
                # if not the first pass, just warn
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                glideFactoryLib.factoryConfig.warning_log.write("Exception at %s: %s" % (time.ctime(),tb))
                
        cleanupObj.cleanup()
        glideFactoryLib.factoryConfig.activity_log.write("Sleep")
        time.sleep(sleep_time)
        count=(count+1)%advertize_rate
        is_first=0
        
        
############################################################
def main(sleep_time,advertize_rate,startup_dir,entry_name):
    startup_time=time.time()

    # create log files in the glidein log directory
    activity_log=logSupport.DayLogFile(os.path.join(startup_dir,"entry_%s/log/factory_info"%entry_name))
    warning_log=logSupport.DayLogFile(os.path.join(startup_dir,"entry_%s/log/factory_err"%entry_name))
    glideFactoryLib.factoryConfig.activity_log=activity_log
    glideFactoryLib.factoryConfig.warning_log=warning_log
    
    glideFactoryMonitoring.monitoringConfig.monitor_dir=os.path.join(startup_dir,"monitor/entry_%s"%entry_name)

    cleanupObj=logSupport.DirCleanup(os.path.join(startup_dir,"entry_%s/log"%entry_name),"(job\..*\.out)|(job\..*\.err)|(factory_info\..*)|(factory_err\..*)",
                                     7*24*3600,
                                     activity_log,warning_log)

    os.chdir(startup_dir)
    glideinDescript=glideFactoryConfig.GlideinDescript()
    if not (entry_name in string.split(glideinDescript.data['Entries'],',')):
        raise RuntimeError, "Entry '%s' not supported: %s"%(entry_name,glideinDescript.data['Entries'])
    jobDescript=glideFactoryConfig.JobDescript(entry_name)
    jobAttributes=glideFactoryConfig.JobAttributes(entry_name)
    jobParams=glideFactoryConfig.JobParams(entry_name)

    # check lock file
    lock_file="entry_%s/glideinWMS.lock"%entry_name
    if not os.path.exists(lock_file): #create a lock file if needed
        fd=open(lock_file,"w")
        fd.close()

    fd=open(lock_file,"r+")
    try:
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        fd.close()
        raise RuntimeError, "Another glidein factory already running for entry '%s'"%entry_name
    fd.seek(0)
    fd.truncate()
    fd.write("PID: %s\nStarted: %s\n"%(os.getpid(),time.ctime(startup_time)))
    fd.flush()
    
    # start
    try:
        try:
            try:
                iterate(cleanupObj,sleep_time,advertize_rate,
                        glideinDescript,jobDescript,jobAttributes,jobParams)
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
            except:
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                glideFactoryLib.factoryConfig.warning_log.write("Failed to deadvertize of (%s,%s,%s)"%(glideinDescript.data['FactoryName'],
                                                                                                       glideinDescript.data['GlideinName'],
                                                                                                       jobDescript.data['EntryName']))
                glideFactoryLib.factoryConfig.warning_log.write("Exception at %s: %s" % (time.ctime(),tb))
    finally:
        fd.close()

    
############################################################
#
# S T A R T U P
#
############################################################

if __name__ == '__main__':
    signal.signal(signal.SIGTERM,signal.getsignal(signal.SIGINT))
    signal.signal(signal.SIGQUIT,signal.getsignal(signal.SIGINT))
    main(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3],sys.argv[4])
 
