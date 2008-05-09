#!/bin/env python
#
# Description:
#   This is the main of the glideinFrontend
#
# Arguments:
#   $1 = poll period (in seconds)
#   $2 = advertize rate even if no changes (every $2 loops)
#   $3 = config file
#
# Author:
#   Igor Sfiligoi (Sept 19th 2006)
#

import signal
import os
import os.path
import sys
import fcntl
import traceback
import time
sys.path.append(os.path.join(sys.path[0],"../lib"))

import glideinFrontendInterface
import glideinFrontendLib
import logSupport

############################################################
def iterate_one(frontend_name,factory_pool,
                schedd_names,job_constraint,match_str,
                max_idle,reserve_idle,
                max_running,reserve_running_fraction,
                glidein_params):
    global activity_log
    glidein_dict=glideinFrontendInterface.findGlideins(factory_pool)
    condorq_dict_idle=glideinFrontendLib.getIdleCondorQ(schedd_names,job_constraint)
    condorq_dict_running=glideinFrontendLib.getRunningCondorQ(schedd_names,job_constraint)

    activity_log.write("Match")
    count_glideins_idle=glideinFrontendLib.countMatch(match_str,condorq_dict_idle,glidein_dict)
    count_glideins_running=glideinFrontendLib.countMatch(match_str,condorq_dict_running,glidein_dict)

    total_running=0
    for schedd in condorq_dict_running.keys():
        condorq=condorq_dict_running[schedd]
        condorq_data=condorq.fetchStored()
        total_running+=len(condorq_data.keys())
    activity_log.write("Total running %i limit %i"%(total_running,max_running))
        
    for glidename in count_glideins_idle.keys():
        request_name=glidename

        idle_jobs=count_glideins_idle[glidename]
        running_jobs=count_glideins_running[glidename]

        if total_running>=max_running:
            # have all the running jobs I wanted
            glidein_min_idle=0
        elif idle_jobs>0:
            glidein_min_idle=(idle_jobs/3)+reserve_idle # since it takes a few cycles to stabilize, ask for only one third
            if glidein_min_idle>max_idle:
                glidein_min_idle=max_idle # but never go above max
            if glidein_min_idle>(max_running-total_running+reserve_idle):
                glidein_min_idle=(max_running-total_running+reserve_idle) # don't go over the max_running
        else:
            # no idle, make sure the glideins know it
            glidein_min_idle=0 
        # we don't need more slots than number of jobs in the queue (modulo reserve)
        glidein_max_run=int((idle_jobs+running_jobs)*(0.99+reserve_running_fraction)+1)
        activity_log.write("For %s Idle %i Running %i"%(glidename,idle_jobs,running_jobs))
        activity_log.write("Advertize %s Request idle %i max_run %i"%(request_name,glidein_min_idle,glidein_max_run))

        try:
          glidein_monitors={"Idle":idle_jobs,"Running":running_jobs}
          glideinFrontendInterface.advertizeWork(factory_pool,frontend_name,request_name,glidename,glidein_min_idle,glidein_max_run,glidein_params,glidein_monitors)
        except:
          warning_log.write("Advertize %s failed"%request_name)

    return

############################################################
def iterate(log_dir,sleep_time,
            frontend_name,factory_pool,
            schedd_names,job_constraint,match_str,
            max_idle,reserve_idle,
            max_running,reserve_running_fraction,
            glidein_params):
    global activity_log,warning_log
    startup_time=time.time()

    activity_log=logSupport.DayLogFile(os.path.join(log_dir,"frontend_info"))
    warning_log=logSupport.DayLogFile(os.path.join(log_dir,"frontend_err"))
    cleanupObj=logSupport.DirCleanup(log_dir,"(frontend_info\..*)|(frontend_err\..*)",
                                     7*24*3600,
                                     activity_log,warning_log)
    

    lock_file=os.path.join(log_dir,"frontend.lock")
    if not os.path.exists(lock_file): #create a lock file if needed
        fd=open(lock_file,"w")
        fd.close()

    fd=open(lock_file,"r+")
    try:
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        fd.close()
        raise RuntimeError, "Another frontend already running"
    fd.seek(0)
    fd.truncate()
    fd.write("PID: %s\nStarted: %s\n"%(os.getpid(),time.ctime(startup_time)))
    fd.flush()
    
    try:
        try:
            try:
                activity_log.write("Starting up")
                is_first=1
                while 1:
                    activity_log.write("Iteration at %s" % time.ctime())
                    try:
                        done_something=iterate_one(frontend_name,factory_pool,schedd_names,job_constraint,match_str,
                                                   max_idle,reserve_idle,
                                                   max_running,reserve_running_fraction,
                                                   glidein_params)
                    except KeyboardInterrupt:
                        raise # this is an exit signal, pass trough
                    except:
                        if is_first:
                            raise
                        else:
                            # if not the first pass, just warn
                            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                            sys.exc_info()[2])
                            warning_log.write("Exception at %s: %s" % (time.ctime(),tb))
                
                    is_first=0
                    activity_log.write("Sleep")
                    time.sleep(sleep_time)
            except KeyboardInterrupt:
                activity_log.write("Received signal...exit")
            except:
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                warning_log.write("Exception at %s: %s" % (time.ctime(),tb))
                raise
        finally:
            try:
                activity_log.write("Deadvertize my ads")
                glideinFrontendInterface.deadvertizeAllWork(factory_pool,frontend_name)
            except:
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                warning_log.write("Failed to deadvertize my ads")
                warning_log.write("Exception at %s: %s" % (time.ctime(),tb))
    finally:
        fd.close()

############################################################
def main(sleep_time,advertize_rate,config_file):
    config_dict={}
    execfile(config_file,config_dict)
    iterate(config_dict['log_dir'],sleep_time,
            config_dict['frontend_name'],config_dict['factory_pool'],
            config_dict['schedd_names'], config_dict['job_constraint'],config_dict['match_string'],
            config_dict['max_idle_glideins_per_entry'], 5,
            config_dict['max_running_jobs'], 0.05,
            config_dict['glidein_params'])

############################################################
#
# S T A R T U P
#
############################################################

if __name__ == '__main__':
    # check that the GSI environment is properly set
    if not os.environ.has_key('X509_USER_PROXY'):
        raise RuntimeError, "Need X509_USER_PROXY to work!"
    if not os.environ.has_key('X509_CERT_DIR'):
        raise RuntimeError, "Need X509_CERT_DIR to work!"

    # make sure you use GSI for authentication
    os.environ['_CONDOR_SEC_DEFAULT_AUTHENTICATION_METHODS']='GSI'

    signal.signal(signal.SIGTERM,signal.getsignal(signal.SIGINT))
    signal.signal(signal.SIGQUIT,signal.getsignal(signal.SIGINT))
    main(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])
 
