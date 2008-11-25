#!/bin/env python
#
# Description:
#   This is the main of the glideinFrontend
#
# Arguments:
#   $1 = parent PID
#   $2 = work dir
#   $3 = group_name
#
# Author:
#   Igor Sfiligoi (was glideinFrontend.py until Nov 21, 2008)
#

import signal
import os
import os.path
import sys
import fcntl
import traceback
import time
import string
sys.path.append(os.path.join(sys.path[0],"../lib"))

import glideinFrontendInterface
import glideinFrontendLib
import glideinFrontendPidLib

############################################################
def iterate_one(frontend_name,factory_pool,factory_constraint,
                x509_proxy,
                schedd_names,job_constraint,match_str,job_attributes,
                max_idle,reserve_idle,
                max_vms_idle,curb_vms_idle,
                max_running,reserve_running_fraction,
                glidein_params):
    # query condor
    glidein_dict=glideinFrontendInterface.findGlideins(factory_pool,factory_constraint,x509_proxy!=None)

    condorq_dict=glideinFrontendLib.getCondorQ(schedd_names,job_constraint,job_attributes)
    status_dict=glideinFrontendLib.getCondorStatus(glidein_params['GLIDEIN_Collector'].split(','),1,[])

    condorq_dict_idle=glideinFrontendLib.getIdleCondorQ(condorq_dict)
    condorq_dict_old_idle=glideinFrontendLib.getOldCondorQ(condorq_dict_idle,600)
    condorq_dict_running=glideinFrontendLib.getRunningCondorQ(condorq_dict)

    condorq_dict_types={'Idle':{'dict':condorq_dict_idle},
                        'OldIdle':{'dict':condorq_dict_old_idle},
                        'Running':{'dict':condorq_dict_running}}

    glideinFrontendLib.log_files.logActivity("Jobs found total %i idle %i (old %i) running %i"%(glideinFrontendLib.countCondorQ(condorq_dict),glideinFrontendLib.countCondorQ(condorq_dict_idle),glideinFrontendLib.countCondorQ(condorq_dict_old_idle),glideinFrontendLib.countCondorQ(condorq_dict_running)))

    status_dict_idle=glideinFrontendLib.getIdleCondorStatus(status_dict)
    status_dict_running=glideinFrontendLib.getRunningCondorStatus(status_dict)

    status_dict_types={'Total':{'dict':status_dict},
                       'Idle':{'dict':status_dict_idle},
                       'Running':{'dict':status_dict_running}}

    glideinFrontendLib.log_files.logActivity("Glideins found total %i idle %i running %i"%(glideinFrontendLib.countCondorStatus(status_dict),glideinFrontendLib.countCondorStatus(status_dict_idle),glideinFrontendLib.countCondorStatus(status_dict_running)))

    # get the proxy
    if x509_proxy!=None:
        try:
            x509_fd=open(x509_proxy,'r')
            try:
                x509_data=x509_fd.read()
            finally:
                x509_fd.close()
        except:
            warning_log.write("Not advertizing, failed to read proxy '%s'"%x509_proxy)
            return
        
        import pubCrypto
        
        # ignore glidein factories that do not have a public key
        # have no way to give them the proxy
        for glidename in glidein_dict.keys():
            glidein_el=glidein_dict[glidename]
            if not glidein_el['attrs'].has_key('PubKeyType'): # no pub key at all
                glideinFrontendLib.log_files.logActivity("Ignoring factory '%s': no pub key support, but x509_proxy specified"%glidename)
                del glidein_dict[glidename]
            elif glidein_el['attrs']['PubKeyType']=='RSA': # only trust RSA for now
                try:
                    glidein_el['attrs']['PubKeyObj']=pubCrypto.PubRSAKey(str(string.replace(glidein_el['attrs']['PubKeyValue'],'\\n','\n')))
                except:
                    glideinFrontendLib.log_files.logWarning("Ignoring factory '%s': invalid RSA key, but x509_proxy specified"%glidename)
                    del glidein_dict[glidename] # no valid key
            else:
                glideinFrontendLib.log_files.logActivity("Ignoring factory '%s': unsupported pub key type '%s', but x509_proxy specified"%(glidename,glidein_el['attrs']['PubKeyType']))
                del glidein_dict[glidename] # not trusted
                

    glideinFrontendLib.log_files.logActivity("Match")

    for dt in condorq_dict_types.keys():
        condorq_dict_types[dt]['count']=glideinFrontendLib.countMatch(match_str,condorq_dict_types[dt]['dict'],glidein_dict)
        condorq_dict_types[dt]['total']=glideinFrontendLib.countCondorQ(condorq_dict_types[dt]['dict'])

    total_running=condorq_dict_types['Running']['total']
    glideinFrontendLib.log_files.logActivity("Total matching idle %i (old %i) running %i limit %i"%(condorq_dict_types['Idle']['total'],condorq_dict_types['OldIdle']['total'],total_running,max_running))
    
    for glidename in condorq_dict_types['Idle']['count'].keys():
        request_name=glidename
        glidein_el=glidein_dict[glidename]

        count_jobs={}
        for dt in condorq_dict_types.keys():
            count_jobs[dt]=condorq_dict_types[dt]['count'][glidename]

        count_status={}
        for dt in status_dict_types.keys():
            status_dict_types[dt]['client_dict']=glideinFrontendLib.getClientCondorStatus(status_dict_types[dt]['dict'],frontend_name,request_name)
            count_status[dt]=glideinFrontendLib.countCondorStatus(status_dict_types[dt]['client_dict'])


        # effective idle is how much more we need
        # if there are idle slots, subtract them, they should match soon
        effective_idle=count_jobs['Idle']-count_status['Idle']
        if effective_idle<0:
            effective_idle=0

        if total_running>=max_running:
            # have all the running jobs I wanted
            glidein_min_idle=0
        elif count_status['Idle']>=max_vms_idle:
            # enough idle vms, do not ask for more
            glidein_min_idle=0
        elif (effective_idle>0):
            glidein_min_idle=count_jobs['Idle']
            glidein_min_idle=glidein_min_idle/3 # since it takes a few cycles to stabilize, ask for only one third
            glidein_idle_reserve=count_jobs['OldIdle']/3 # do not reserve any more than the number of old idles for reserve (/3)
            if glidein_idle_reserve>reserve_idle:
                glidein_idle_reserve=reserve_idle

            glidein_min_idle+=glidein_idle_reserve
            
            if glidein_min_idle>max_idle:
                glidein_min_idle=max_idle # but never go above max
            if glidein_min_idle>(max_running-total_running+glidein_idle_reserve):
                glidein_min_idle=(max_running-total_running+glidein_idle_reserve) # don't go over the max_running
            if count_status['Idle']>=curb_vms_idle:
                glidein_min_idle/=2 # above first treshold, reduce
            if glidein_min_idle<1:
                glidein_min_idle=1
        else:
            # no idle, make sure the glideins know it
            glidein_min_idle=0 
        # we don't need more slots than number of jobs in the queue (modulo reserve)
        glidein_max_run=int((count_jobs['Idle']+count_jobs['Running'])*(0.99+reserve_running_fraction)+1)
        glideinFrontendLib.log_files.logActivity("For %s Idle %i (effective %i old %i) Running %i"%(glidename,count_jobs['Idle'],effective_idle,count_jobs['OldIdle'],count_jobs['Running']))
        glideinFrontendLib.log_files.logActivity("Glideins for %s Total %s Idle %i Running %i"%(glidename,count_status['Total'],count_status['Idle'],count_status['Running']))
        glideinFrontendLib.log_files.logActivity("Advertize %s Request idle %i max_run %i"%(request_name,glidein_min_idle,glidein_max_run))

        try:
          glidein_monitors={}
          for t in count_jobs.keys():
              glidein_monitors[t]=count_jobs[t]
          for t in count_status.keys():
              glidein_monitors['Glideins%s'%t]=count_status[t]
          if x509_proxy!=None:
              glideinFrontendInterface.advertizeWork(factory_pool,frontend_name,request_name,glidename,glidein_min_idle,glidein_max_run,glidein_params,glidein_monitors,
                                                     glidein_el['attrs']['PubKeyID'],glidein_el['attrs']['PubKeyObj'],
                                                     None, # should reuse it, but none will work for now
                                                     {'x509_proxy':x509_data})
          else:
              glideinFrontendInterface.advertizeWork(factory_pool,frontend_name,request_name,glidename,glidein_min_idle,glidein_max_run,glidein_params,glidein_monitors)
        except:
          glideinFrontendLib.log_files.logWarning("Advertize %s failed"%request_name)

    return

############################################################
def iterate(group_name,
            frontendDescript,elementDescript,paramsDescript,exprsDescript):
#    log_dir,sleep_time,
#            frontend_name,factory_pool,factory_constraint,
#            x509_proxy,
#            schedd_names,job_constraint,match_str,job_attributes,
#            max_idle,reserve_idle,
#            max_vms_idle,curb_vms_idle,
#            max_running,reserve_running_fraction,
#            glidein_params):
    sleep_time=int(frontendDescript.data['LoopDelay'])
    frontend_name=frontendDescript.data['FrontendName']

    if x509_proxy==None:
        published_frontend_name='%s@%s'%(group_name,frontend_name)
    else:
        # if using a VO proxy, label it as such
        # this way we don't risk of using the wrong proxy on the other side
        # if/when we decide to stop using the proxy
        published_frontend_name='XPVO_%s@%s'%(group_name,frontend_name)

    factory_pools=string.split(frontendDescript.data['FactoryCollectors'],',')+string.split(elementDescript.data['FactoryCollectors'],',')
    if len(factory_pools)==0:
        raise RuntimeError, "Need at least one factory collector, none provided"
    factory_constraint="(%s) && (%s)"%(frontendDescript.data['FactoryQueryExpr'],elementDescript.data['FactoryQueryExpr'])
    factory_attributes=eval(frontendDescript.data['FactoryMatchAtttrs'])+eval(elementDescript.data['FactoryMatchAtttrs']) # to be finished... should remove duplicates

    schedd_names=string.split(frontendDescript.data['JobSchedds'],',')+string.split(elementDescript.data['JobSchedds'],',')
    if len(schedd_names)==0:
        raise RuntimeError, "Need at least one job schedd, none provided"    
    job_constraint="(%s) && (%s)"%(frontendDescript.data['JobQueryExpr'],elementDescript.data['jobQueryExpr'])

    try:
        is_first=1
        while 1: # will exit by exception
            glideinFrontendLib.log_files.logActivity("Iteration at %s" % time.ctime())
            try:
                done_something=iterate_one(published_frontend_name,factory_pool,factory_constraint,
                                           x509_proxy,
                                           schedd_names,job_constraint,match_str,job_attributes,
                                           max_idle,reserve_idle,
                                           max_vms_idle,curb_vms_idle,
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
                    glideinFrontendLib.log_files.logWarning("Exception at %s: %s" % (time.ctime(),tb))
                
            is_first=0
            glideinFrontendLib.log_files.logActivity("Sleep")
            time.sleep(sleep_time)
    finally:
        glideinFrontendLib.log_files.logActivity("Deadvertize my ads")
        glideinFrontendInterface.deadvertizeAllWork(factory_pool,published_frontend_name)

############################################################
def main(parent_PID, work_dir, group_name):
    startup_time=time.time()

    glideinFrontendLib.log_files=LogFiles(os.path.join(work_dir,"group_%s/log"%group_name))

    frontendDescript=glideinFrontendConfig.FrontendDescript(work_dir)
    if not (group_name in string.split(frontendDescript.data['Groups'],',')):
        raise RuntimeError, "Group '%s' not supported: %s"%(group_name,frontendDescript.data['Groups'])
    elementDescript=glideinFrontendConfig.ElementDescript(work_dir,group_name)
    paramsDescript=glideinFrontendConfig.ParamsDescript(work_dir,group_name)
    exprsDescript=glideinFrontendConfig.ExprsDescript(work_dir,group_name)

    # create lock file
    pid_obj=glideinFrontendPidLib.ElementPidSupport(work_dir,group_name)

    pid_obj.register(parent_pid)
    try:
        try:
            glideinFrontendLib.log_files.logActivity("Starting up")
            iterate(group_name,
                    frontendDescript,elementDescript,paramsDescript,exprsDescript)
        except KeyboardInterrupt:
            glideinFrontendLib.log_files.logActivity("Received signal...exit")
        except:
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            glideinFrontendLib.log_files.logWarning("Exception at %s: %s" % (time.ctime(),tb))
    finally:
        pid_obj.relinquish()

        
    a(    config_dict['log_dir'],config_dict['loop_delay'],
            config_dict['frontend_name'],config_dict['factory_pool'],config_dict['factory_constraint'],
            config_dict['x509_proxy'],
            config_dict['schedd_names'], config_dict['job_constraint'],config_dict['match_string'],config_dict['job_attributes'],
            config_dict['max_idle_glideins_per_entry'],config_dict['reserve_idle_glideins_per_entry'],
            config_dict['max_idle_vms_per_entry'],config_dict['curb_idle_vms_per_entry'],
            config_dict['max_running_jobs'], 0.05,
            config_dict['glidein_params'])

############################################################
#
# S T A R T U P
#
############################################################

def termsignal(signr,frame):
    raise KeyboardInterrupt, "Received signal %s"%signr

if __name__ == '__main__':
    # check that the GSI environment is properly set
    if not os.environ.has_key('X509_USER_PROXY'):
        raise RuntimeError, "Need X509_USER_PROXY to work!"
    if not os.environ.has_key('X509_CERT_DIR'):
        raise RuntimeError, "Need X509_CERT_DIR to work!"

    # make sure you use GSI for authentication
    os.environ['_CONDOR_SEC_DEFAULT_AUTHENTICATION_METHODS']='GSI'

    signal.signal(signal.SIGTERM,termsignal)
    signal.signal(signal.SIGQUIT,termsignal)
    main(sys.argv[1],sys.argv[2],sys.argv[3])
 
