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
import sys,os,os.path,copy
import fcntl
import traceback
import time,string
sys.path.append(os.path.join(sys.path[0],"../lib"))

import symCrypto,pubCrypto

import glideinFrontendConfig
import glideinFrontendInterface
import glideinFrontendLib
import glideinFrontendPidLib
import glideinFrontendMonitoring

############################################################
def write_stats(stats):
    for k in stats.keys():
        stats[k].write_file();

############################################################
def iterate_one(client_name,elementDescript,paramsDescript,signatureDescript,stats):
    if elementDescript.frontend_data.has_key('X509Proxy'):
        x509_proxy=elementDescript.frontend_data['X509Proxy']
    else:
        x509_proxy=None

    frontend_name=elementDescript.frontend_data['FrontendName']
    group_name=elementDescript.element_data['GroupName']

    web_url=elementDescript.frontend_data['WebURL']

    # query condor
    glidein_dict={}
    factory_constraint=elementDescript.merged_data['FactoryQueryExpr']
    factory_pools=elementDescript.merged_data['FactoryCollectors']
    for factory_pool in factory_pools:
        factory_glidein_dict=glideinFrontendInterface.findGlideins(factory_pool,signatureDescript.signature_type,factory_constraint,x509_proxy!=None)
        for glidename in factory_glidein_dict.keys():
            glidein_dict[(factory_pool,glidename)]=factory_glidein_dict[glidename]

    condorq_dict=glideinFrontendLib.getCondorQ(elementDescript.merged_data['JobSchedds'],
                                               elementDescript.merged_data['JobQueryExpr'],
                                               elementDescript.merged_data['JobMatchAttrs'])


    status_dict=glideinFrontendLib.getCondorStatus(paramsDescript.const_data['GLIDEIN_Collector'].split(','),1,[]) # in theory the collector could be an expression, but for now we require it to be a constant

    condorq_dict_idle=glideinFrontendLib.getIdleCondorQ(condorq_dict)
    condorq_dict_old_idle=glideinFrontendLib.getOldCondorQ(condorq_dict_idle,600)
    condorq_dict_running=glideinFrontendLib.getRunningCondorQ(condorq_dict)

    condorq_dict_types={'Idle':{'dict':condorq_dict_idle,'abs':glideinFrontendLib.countCondorQ(condorq_dict_old_idle)},
                        'OldIdle':{'dict':condorq_dict_old_idle,'abs':glideinFrontendLib.countCondorQ(condorq_dict_old_idle)},
                        'Running':{'dict':condorq_dict_running,'abs':glideinFrontendLib.countCondorQ(condorq_dict_running)}}
    condorq_dict_abs=glideinFrontendLib.countCondorQ(condorq_dict);
    

    stats['group'].logJobs({'Total':condorq_dict_abs,
                            'Idle':condorq_dict_types['Idle']['abs'],
                            'OldIdle':condorq_dict_types['OldIdle']['abs'],
                            'Running':condorq_dict_types['Running']['abs']})

    glideinFrontendLib.log_files.logActivity("Jobs found total %i idle %i (old %i) running %i"%(condorq_dict_abs,
                                                                                                condorq_dict_types['Idle']['abs'],
                                                                                                condorq_dict_types['OldIdle']['abs'],
                                                                                                condorq_dict_types['Running']['abs']))

    status_dict_idle=glideinFrontendLib.getIdleCondorStatus(status_dict)
    status_dict_running=glideinFrontendLib.getRunningCondorStatus(status_dict)

    status_dict_types={'Total':{'dict':status_dict,'abs':glideinFrontendLib.countCondorStatus(status_dict)},
                       'Idle':{'dict':status_dict_idle,'abs':glideinFrontendLib.countCondorStatus(status_dict_idle)},
                       'Running':{'dict':status_dict_running,'abs':glideinFrontendLib.countCondorStatus(status_dict_running)}}

    stats['group'].logSlots({'Total':status_dict_types['Total']['abs'],
                            'Idle':status_dict_types['Idle']['abs'],
                            'Running':status_dict_types['Running']['abs']})

    glideinFrontendLib.log_files.logActivity("Glideins found total %i idle %i running %i"%(status_dict_types['Total']['abs'],
                                                                                           status_dict_types['Idle']['abs'],
                                                                                           status_dict_types['Running']['abs']))

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
        
        # ignore glidein factories that do not have a public key
        # have no way to give them the proxy
        for glideid in glidein_dict.keys():
            glidein_el=glidein_dict[glideid]
            if not glidein_el['attrs'].has_key('PubKeyType'): # no pub key at all
                glideinFrontendLib.log_files.logActivity("Ignoring factory '%s@%s': no pub key support, but x509_proxy specified"%(glideid[1],glideid[0]))
                del glidein_dict[glideid]
            elif glidein_el['attrs']['PubKeyType']=='RSA': # only trust RSA for now
                try:
                    glidein_el['attrs']['PubKeyObj']=pubCrypto.PubRSAKey(str(string.replace(glidein_el['attrs']['PubKeyValue'],'\\n','\n')))
                except:
                    glideinFrontendLib.log_files.logWarning("Ignoring factory '%s@%s': invalid RSA key, but x509_proxy specified"%(glideid[1],glidein[0]))
                    del glidein_dict[glideid] # no valid key
            else:
                glideinFrontendLib.log_files.logActivity("Ignoring factory '%s@%s': unsupported pub key type '%s', but x509_proxy specified"%(glideid[1],glidein[0],glidein_el['attrs']['PubKeyType']))
                del glidein_dict[glideid] # not trusted
                

    glideinFrontendLib.log_files.logActivity("Match")

    for dt in condorq_dict_types.keys():
        condorq_dict_types[dt]['count']=glideinFrontendLib.countMatch(elementDescript.merged_data['MatchExprCompiledObj'],condorq_dict_types[dt]['dict'],glidein_dict)
        # is the semantics right?
        condorq_dict_types[dt]['total']=glideinFrontendLib.countCondorQ(condorq_dict_types[dt]['dict'])

    max_running=int(elementDescript.element_data['MaxRunningPerEntry'])
    fraction_running=float(elementDescript.element_data['FracRunningPerEntry'])
    max_idle=int(elementDescript.element_data['MaxIdlePerEntry'])
    reserve_idle=int(elementDescript.element_data['ReserveIdlePerEntry'])
    max_vms_idle=int(elementDescript.element_data['MaxIdleVMsPerEntry'])
    curb_vms_idle=int(elementDescript.element_data['CurbIdleVMsPerEntry'])
    
    total_running=condorq_dict_types['Running']['total']
    glideinFrontendLib.log_files.logActivity("Total matching idle %i (old %i) running %i limit %i"%(condorq_dict_types['Idle']['total'],condorq_dict_types['OldIdle']['total'],total_running,max_running))
    
    for glideid in condorq_dict_types['Idle']['count'].keys():
        factory_pool=glideid[0]
        request_name=glideid[1]
        glideid_str="%s@%s"%(request_name,factory_pool)
        glidein_el=glidein_dict[glideid]

        count_jobs={}
        for dt in condorq_dict_types.keys():
            count_jobs[dt]=condorq_dict_types[dt]['count'][glideid]

        count_status={}
        for dt in status_dict_types.keys():
            status_dict_types[dt]['client_dict']=glideinFrontendLib.getClientCondorStatus(status_dict_types[dt]['dict'],frontend_name,group_name,request_name)
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
        # we don't need more slots than number of jobs in the queue (unless the fraction is positive)
        glidein_max_run=int((count_jobs['Idle']+count_jobs['Running'])*fraction_running+1)
        glideinFrontendLib.log_files.logActivity("For %s Idle %i (effective %i old %i) Running %i"%(glideid_str,count_jobs['Idle'],effective_idle,count_jobs['OldIdle'],count_jobs['Running']))
        glideinFrontendLib.log_files.logActivity("Glideins for %s Total %s Idle %i Running %i"%(glideid_str,count_status['Total'],count_status['Idle'],count_status['Running']))
        glideinFrontendLib.log_files.logActivity("Advertize %s Request idle %i max_run %i"%(glideid_str,glidein_min_idle,glidein_max_run))

        # get the parameters
        glidein_params=copy.deepcopy(paramsDescript.const_data)
        for k in paramsDescript.expr_data.keys():
            kexpr=paramsDescript.expr_objs[k]
            # convert kexpr -> kval
            glidein_params[k]=glideinFrontendLib.evalParamExpr(kexpr,paramsDescript.const_data,glidein_el)

        try:
          glidein_monitors={}
          for t in count_jobs.keys():
              glidein_monitors[t]=count_jobs[t]
          for t in count_status.keys():
              glidein_monitors['Glideins%s'%t]=count_status[t]
          if x509_proxy!=None:
              glideinFrontendInterface.advertizeWork(factory_pool,client_name,frontend_name,group_name,request_name,request_name,
                                                     web_url,
                                                     signatureDescript.frontend_descript_fname, signatureDescript.group_descript_fname,
                                                     signatureDescript.signature_type, signatureDescript.frontend_descript_signature, signatureDescript.group_descript_signature,
                                                     glidein_min_idle,glidein_max_run,glidein_params,glidein_monitors,
                                                     glidein_el['attrs']['PubKeyID'],glidein_el['attrs']['PubKeyObj'],
                                                     None, # should reuse it, but none will work for now
                                                     {'x509_proxy':x509_data})
          else:
              glideinFrontendInterface.advertizeWork(factory_pool,client_name,frontend_name,group_name,request_name,request_name,
                                                     web_url,
                                                     signatureDescript.frontend_descript_fname, signatureDescript.group_descript_fname,
                                                     signatureDescript.signature_type, signatureDescript.frontend_descript_signature, signatureDescript.group_descript_signature,
                                                     glidein_min_idle,glidein_max_run,glidein_params,glidein_monitors)
        except:
          glideinFrontendLib.log_files.logWarning("Advertize %s failed"%glideid_str)

    return

############################################################
def iterate(elementDescript,paramsDescript,signatureDescript):
    sleep_time=int(elementDescript.frontend_data['LoopDelay'])
    
    factory_pools=elementDescript.merged_data['FactoryCollectors']

    frontend_name=elementDescript.frontend_data['FrontendName']
    group_name=elementDescript.element_data['GroupName']

    stats={}

    if not elementDescript.frontend_data.has_key('X509Proxy'):
        published_frontend_name='%s.%s'%(frontend_name,group_name)
    else:
        # if using a VO proxy, label it as such
        # this way we don't risk of using the wrong proxy on the other side
        # if/when we decide to stop using the proxy
        published_frontend_name='%s.XPVO_%s'%(frontend_name,group_name)

    try:
        is_first=1
        while 1: # will exit by exception
            glideinFrontendLib.log_files.logActivity("Iteration at %s" % time.ctime())
            try:
                # recreate every time (an easy way to start from a clean state)
                stats['group']=glideinFrontendMonitoring.groupStats()
                
                done_something=iterate_one(published_frontend_name,elementDescript,paramsDescript,signatureDescript,stats)
                
                glideinFrontendLib.log_files.logActivity("Writing stats")
                try:
                    write_stats(stats)
                except KeyboardInterrupt:
                    raise # this is an exit signal, pass through
                except:
                    # never fail for stats reasons!
                    tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                    sys.exc_info()[2])
                    glideinFrontendLib.log_files.logWarning("Exception at %s: %s" % (time.ctime(),tb))                
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
        for factory_pool in factory_pools:
            try:
                glideinFrontendInterface.deadvertizeAllWork(factory_pool,published_frontend_name)
            except:
                pass # just ignore errors... this was cleanup

############################################################
def main(parent_pid, work_dir, group_name):
    startup_time=time.time()

    glideinFrontendLib.log_files=glideinFrontendLib.LogFiles(os.path.join(work_dir,"group_%s/log"%group_name))

    elementDescript=glideinFrontendConfig.ElementMergedDescript(work_dir,group_name)
    paramsDescript=glideinFrontendConfig.ParamsDescript(work_dir,group_name)
    signatureDescript=glideinFrontendConfig.GroupSignatureDescript(work_dir,group_name)

    glideinFrontendMonitoring.monitoringConfig.monitor_dir=os.path.join(work_dir,"monitor/group_%s"%group_name)

    # create lock file
    pid_obj=glideinFrontendPidLib.ElementPidSupport(work_dir,group_name)

    pid_obj.register(parent_pid)
    try:
        try:
            glideinFrontendLib.log_files.logActivity("Starting up")
            iterate(elementDescript,paramsDescript,signatureDescript)
        except KeyboardInterrupt:
            glideinFrontendLib.log_files.logActivity("Received signal...exit")
        except:
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            glideinFrontendLib.log_files.logWarning("Exception at %s: %s" % (time.ctime(),tb))
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
 
