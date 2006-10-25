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
sys.path.append("../lib")

import glideFactoryConfig
import glideFactoryLib
import glideFactoryInterface
import logSupport


############################################################
def perform_work(factory_name,glidein_name,schedd_name,
                 client_name,idle_glideins,params):
    if params.has_key("GLIDEIN_Collector"):
        condor_pool=params["GLIDEIN_Collector"]
    else:
        condor_pool=None
    
    condorQ=glideFactoryLib.getCondorQData(factory_name,glidein_name,client_name,schedd_name)
    condorStatus=glideFactoryLib.getCondorStatusData(factory_name,glidein_name,client_name,condor_pool)

    glideFactoryLib.logStats(condorQ,condorStatus)

    nr_submitted=glideFactoryLib.keepIdleGlideins(condorQ,idle_glideins,params)
    if nr_submitted>0:
        return 1 # we submitted somthing, return immediately

    glideFactoryLib.sanitizeGlideins(condorQ,condorStatus)
    return 0
    

############################################################
def iterate_one(do_advertize,
                jobDescript,jobAttributes,jobParams):
    factory_name=jobDescript.data['FactoryName']
    glidein_name=jobDescript.data['GlideinName']

    if do_advertize:
        glideFactoryLib.factoryConfig.activity_log.write("Advertize")
        glideFactoryInterface.advertizeGlidein(factory_name,glidein_name,jobAttributes.data.copy(),jobParams.data.copy(),{})
    
    work = glideFactoryInterface.findWork(factory_name,glidein_name)
    if len(work.keys())==0:
        return 0 # nothing to be done

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
def iterate(sleep_time,advertize_rate,
            jobDescript,jobAttributes,jobParams):
    is_first=1
    count=0;
    while 1:
        glideFactoryLib.factoryConfig.activity_log.write("Iteration at %s" % time.ctime())
        try:
            done_something=iterate_one(count==0,
                                       jobDescript,jobAttributes,jobParams)
        except:
            if is_first:
                raise
            else:
                # if not the first pass, just warn
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                glideFactoryLib.factoryConfig.warning_log.write("Exception at %s: %s" % (time.ctime(),tb))
                
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
    glideFactoryLib.factoryConfig.warining_log=warning_log

    os.chdir(startup_dir)
    jobDescript=glideFactoryConfig.JobDescript()
    jobAttributes=glideFactoryConfig.JobAttributes()
    jobParams=glideFactoryConfig.JobParams()

    iterate(sleep_time,advertize_rate,
            jobDescript,jobAttributes,jobParams)

############################################################
#
# S T A R T U P
#
############################################################

if __name__ == '__main__':
    main(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])
 
