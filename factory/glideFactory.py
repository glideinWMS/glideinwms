import os,sys,time
import glideFactoryConfig
import glideFactoryLib
import glideFactoryInterface

# all logging to stdout
glideFactoryLib.factoryConfig.activity_log=sys.stdout
glideFactoryLib.factoryConfig.warining_log=sys.stderr

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
def iterate_one(jobDescript,jobAttributes,jobParams):
    factory_name=jobDescript.data['FactoryName']
    glidein_name=jobDescript.data['GlideinName']

    print "Advertize"
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
def iterate(jobDescript,jobAttributes,jobParams):
    while 1:
        print "Iteration at %s" % time.ctime()
        done_something=iterate_one(jobDescript,jobAttributes,jobParams)
        print "Sleep"
        time.sleep(30)
        
############################################################
def main(startup_dir):
    os.chdir(startup_dir)
    jobDescript=glideFactoryConfig.JobDescript()
    jobAttributes=glideFactoryConfig.JobAttributes()
    jobParams=glideFactoryConfig.JobParams()

    iterate(jobDescript,jobAttributes,jobParams)

############################################################
#
# S T A R T U P
#
############################################################

if __name__ == '__main__':
    main(sys.argv[1])
 
