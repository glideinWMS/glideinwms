#
# Description:
#   This is the main of the glideinFactory
#
# Arguments:
#   $1 = poll period (in seconds)
#   $2 = advertize rate (every $2 loops)
#   $3 = glidein submit_dir
#
# Author:
#   Igor Sfiligoi (Sept 15th 2006)
#

import os
import os.path
import sys
import traceback
import time
import threading
sys.path.append("../lib")

import glideFactoryConfig
import glideFactoryLib
import glideFactoryMonitoring
import glideFactoryInterface
import glideFactoryLogParser
import logSupport
import copy

# this thread will be used for lazy updates of rrd history conversions
log_rrd_thread=None
qc_rrd_thread=None


############################################################
def perform_work(factory_name,glidein_name,schedd_name,
                 client_name,idle_glideins,params):
    if params.has_key("GLIDEIN_Collector"):
        condor_pool=params["GLIDEIN_Collector"]
    else:
        condor_pool=None
    
    #glideFactoryLib.factoryConfig.activity_log.write("QueryQ (%s,%s,%s,%s)"%(factory_name,glidein_name,client_name,schedd_name))
    condorQ=glideFactoryLib.getCondorQData(factory_name,glidein_name,client_name,schedd_name)
    #glideFactoryLib.factoryConfig.activity_log.write("QueryS (%s,%s,%s,%s)"%(factory_name,glidein_name,client_name,schedd_name))
    condorStatus=glideFactoryLib.getCondorStatusData(factory_name,glidein_name,client_name,condor_pool)
    #glideFactoryLib.factoryConfig.activity_log.write("Work")
    log_stats=glideFactoryLogParser.dirSummary("log",client_name)
    log_stats.load()

    glideFactoryLib.logStats(condorQ,condorStatus)
    glideFactoryLib.factoryConfig.log_stats.logSummary(client_name,log_stats)

    nr_submitted=glideFactoryLib.keepIdleGlideins(condorQ,idle_glideins,params)
    if nr_submitted>0:
        #glideFactoryLib.factoryConfig.activity_log.write("Submitted")
        return 1 # we submitted somthing, return immediately

    #glideFactoryLib.factoryConfig.activity_log.write("Sanitize")

    glideFactoryLib.sanitizeGlideins(condorQ,condorStatus)
    
    #glideFactoryLib.factoryConfig.activity_log.write("Work done")
    return 0
    

############################################################
def find_and_perform_work(jobDescript,JobParams):
    factory_name=jobDescript.data['FactoryName']
    glidein_name=jobDescript.data['GlideinName']

    #glideFactoryLib.factoryConfig.activity_log.write("Find work")
    work = glideFactoryInterface.findWork(factory_name,glidein_name)
    glideFactoryLib.logWorkRequests(work)
    
    if len(work.keys())==0:
        return 0 # nothing to be done

    #glideFactoryLib.factoryConfig.activity_log.write("Perform work")
    schedd_name=jobDescript.data['Schedd']

    done_something=0
    for work_key in work.keys():
        # merge work and default params
        params=work[work_key]['params']

        # add default values if not defined
        for k in jobParams.data.keys():
            if not (k in params.keys()):
                params[k]=jobParams.data[k]

        if work[work_key]['requests'].has_key('IdleGlideins'):
            done_something+=perform_work(factory_name,glidein_name,schedd_name,
                                         work_key,work[work_key]['requests']['IdleGlideins'],params)
        #else, it is malformed and should be skipped

    return done_something

############################################################
def iterate_one(do_advertize,
                jobDescript,jobAttributes,jobParams,current_qc_total):
    factory_name=jobDescript.data['FactoryName']
    glidein_name=jobDescript.data['GlideinName']

    if do_advertize:
        glideFactoryLib.factoryConfig.activity_log.write("Advertize")
        glidein_monitor_monitors={}
        for w in current_qc_total.keys():
            for a in current_qc_total[w].keys():
                glidein_monitor_monitors['Total%s%s'%(w,a)]=current_qc_total[w][a]
        try:
            glideFactoryInterface.advertizeGlidein(factory_name,glidein_name,jobAttributes.data.copy(),jobParams.data.copy(),glidein_monitor_monitors)
        except:
            glideFactoryLib.factoryConfig.warning_log.write("Advertize failed")
    
    done_something = find_and_perform_work(jobDescript,jobParams)
    return done_something

############################################################
def iterate(cleanupObj,sleep_time,advertize_rate,
            jobDescript,jobAttributes,jobParams):
    global log_rrd_thread,qc_rrd_thread
    is_first=1
    count=0;

    glideFactoryLib.factoryConfig.log_stats=glideFactoryMonitoring.condorLogSummary()
    while 1:
        glideFactoryLib.factoryConfig.activity_log.write("Iteration at %s" % time.ctime())
        try:
            if glideFactoryLib.factoryConfig.qc_stats!=None:
                old_qc_total=glideFactoryLib.factoryConfig.qc_stats.get_total()
            else:
                old_qc_total={}
            
            glideFactoryLib.factoryConfig.log_stats.reset()
            glideFactoryLib.factoryConfig.qc_stats=glideFactoryMonitoring.condorQStats()
            done_something=iterate_one(count==0,
                                       jobDescript,jobAttributes,jobParams,old_qc_total)
            
            glideFactoryLib.factoryConfig.activity_log.write("Writing stats")
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
def main(sleep_time,advertize_rate,startup_dir):
    # create log files in the glidein log directory
    activity_log=logSupport.DayLogFile(os.path.join(startup_dir,"log/factory_info"))
    warning_log=logSupport.DayLogFile(os.path.join(startup_dir,"log/factory_err"))
    glideFactoryLib.factoryConfig.activity_log=activity_log
    glideFactoryLib.factoryConfig.warning_log=warning_log
    
    glideFactoryMonitoring.monitoringConfig.monitor_dir=os.path.join(startup_dir,"monitor")

    cleanupObj=logSupport.DirCleanup(os.path.join(startup_dir,"log"),"(job\..*\.out)|(job\..*\.err)|(factory_info\..*)|(factory_err\..*)",
                                     7*24*3600,
                                     activity_log,warning_log)

    os.chdir(startup_dir)
    jobDescript=glideFactoryConfig.JobDescript()
    jobAttributes=glideFactoryConfig.JobAttributes()
    jobParams=glideFactoryConfig.JobParams()

    iterate(cleanupObj,sleep_time,advertize_rate,
            jobDescript,jobAttributes,jobParams)

############################################################
#
# S T A R T U P
#
############################################################

if __name__ == '__main__':
    main(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])
 
