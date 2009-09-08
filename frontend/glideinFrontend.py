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
import string
sys.path.append(os.path.join(sys.path[0],"../lib"))

import glideinFrontendInterface
import glideinFrontendLib
import glideinFrontendPidLib
import logSupport

class LogFiles:
    def __init__(self,log_dir):
        self.log_dir=log_dir
        self.activity_log=logSupport.DayLogFile(os.path.join(log_dir,"frontend_info"))
        self.warning_log=logSupport.DayLogFile(os.path.join(log_dir,"frontend_err"))
        self.cleanupObj=logSupport.DirCleanup(log_dir,"(frontend_info\..*)|(frontend_err\..*)",
                                              7*24*3600,
                                              self.activity_log,self.warning_log)

    def logActivity(self,str):
        try:
            self.activity_log.write(str+"\n")
        except:
            # logging must never throw an exception!
            self.logWarning("logActivity failed, was logging: %s"%str,False)

    def logWarning(self,str, log_in_activity=True):
        try:
            self.warning_log.write(str+"\n")
        except:
            # logging must throw an exception!
            # silently ignore
            pass
        if log_in_activity:
            self.logActivity("WARNING: %s"%str)

# someone needs to initialize this
# type LogFiles
log_files=None

############################################################
def iterate_one(frontend_name,factory_pool,factory_constraint,
                x509_proxy,
                schedd_names,job_constraint,match_str,job_attributes,
                max_idle,reserve_idle,
                max_vms_idle,curb_vms_idle,
                max_running,reserve_running_fraction,
                glidein_params):
    global log_files

    # query condor
    glidein_dict=glideinFrontendInterface.findGlideins(factory_pool,factory_constraint,x509_proxy!=None)

    condorq_dict=glideinFrontendLib.getCondorQ(schedd_names,job_constraint,job_attributes)

    # may have many collectors
    user_collectors=[]
    for user_collector_el in glidein_params['GLIDEIN_Collector'].split(','):
        uce_arr=user_collector_el.split(':',1)
        if len(uce_arr)==1:
            # no port
            user_collectors.append(user_collector_el)
        else:
            uce_hname,uce_port=uce_arr
            ucep_arr=uce_port.split('-',1)
            if len(ucep_arr)==1:
                # no range
                user_collectors.append(user_collector_el)
            else:
                uce_port_low=int(ucep_arr[0])
                uce_port_high=int(ucep_arr[1])
                for p in range(uce_port_low,uce_port_high+1):
                    user_collectors.append("%s:%s"%(uce_hname,p))
    
    status_dict=glideinFrontendLib.getCondorStatus(user_collectors,1,[])

    condorq_dict_idle=glideinFrontendLib.getIdleCondorQ(condorq_dict)
    condorq_dict_old_idle=glideinFrontendLib.getOldCondorQ(condorq_dict_idle,600)
    condorq_dict_running=glideinFrontendLib.getRunningCondorQ(condorq_dict)

    condorq_dict_types={'Idle':{'dict':condorq_dict_idle},
                        'OldIdle':{'dict':condorq_dict_old_idle},
                        'Running':{'dict':condorq_dict_running}}

    log_files.logActivity("Jobs found total %i idle %i (old %i) running %i"%(glideinFrontendLib.countCondorQ(condorq_dict),glideinFrontendLib.countCondorQ(condorq_dict_idle),glideinFrontendLib.countCondorQ(condorq_dict_old_idle),glideinFrontendLib.countCondorQ(condorq_dict_running)))

    status_dict_idle=glideinFrontendLib.getIdleCondorStatus(status_dict)
    status_dict_running=glideinFrontendLib.getRunningCondorStatus(status_dict)

    status_dict_types={'Total':{'dict':status_dict},
                       'Idle':{'dict':status_dict_idle},
                       'Running':{'dict':status_dict_running}}

    log_files.logActivity("Glideins found total %i idle %i running %i"%(glideinFrontendLib.countCondorStatus(status_dict),glideinFrontendLib.countCondorStatus(status_dict_idle),glideinFrontendLib.countCondorStatus(status_dict_running)))

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
                log_files.logActivity("Ignoring factory '%s': no pub key support, but x509_proxy specified"%glidename)
                del glidein_dict[glidename]
            elif glidein_el['attrs']['PubKeyType']=='RSA': # only trust RSA for now
                try:
                    glidein_el['attrs']['PubKeyObj']=pubCrypto.PubRSAKey(str(string.replace(glidein_el['attrs']['PubKeyValue'],'\\n','\n')))
                except:
                    log_files.logWarning("Ignoring factory '%s': invalid RSA key, but x509_proxy specified"%glidename)
                    del glidein_dict[glidename] # no valid key
            else:
                log_files.logActivity("Ignoring factory '%s': unsupported pub key type '%s', but x509_proxy specified"%(glidename,glidein_el['attrs']['PubKeyType']))
                del glidein_dict[glidename] # not trusted
                

    log_files.logActivity("Match")

    for dt in condorq_dict_types.keys():
        condorq_dict_types[dt]['count']=glideinFrontendLib.countMatch(match_str,condorq_dict_types[dt]['dict'],glidein_dict)
        condorq_dict_types[dt]['total']=glideinFrontendLib.countCondorQ(condorq_dict_types[dt]['dict'])

    total_running=condorq_dict_types['Running']['total']
    log_files.logActivity("Total matching idle %i (old %i) running %i limit %i"%(condorq_dict_types['Idle']['total'],condorq_dict_types['OldIdle']['total'],total_running,max_running))
    
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
        log_files.logActivity("For %s Idle %i (effective %i old %i) Running %i"%(glidename,count_jobs['Idle'],effective_idle,count_jobs['OldIdle'],count_jobs['Running']))
        log_files.logActivity("Glideins for %s Total %s Idle %i Running %i"%(glidename,count_status['Total'],count_status['Idle'],count_status['Running']))
        log_files.logActivity("Advertize %s Request idle %i max_run %i"%(request_name,glidein_min_idle,glidein_max_run))

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
          log_files.logWarning("Advertize %s failed"%request_name)

    return

############################################################
def iterate(log_dir,sleep_time,
            frontend_name,factory_pool,factory_constraint,
            x509_proxy,
            schedd_names,job_constraint,match_str,job_attributes,
            max_idle,reserve_idle,
            max_vms_idle,curb_vms_idle,
            max_running,reserve_running_fraction,
            glidein_params):
    global log_files
    startup_time=time.time()

    if x509_proxy==None:
        published_frontend_name=frontend_name
    else:
        # if using a VO proxy, label it as such
        # this way we don't risk of using the wrong proxy on the other side
        # if/when we decide to stop using the proxy
        published_frontend_name='XPVO_%s'%frontend_name

    log_files=LogFiles(log_dir)

    # create lock file
    fd=glideinFrontendPidLib.register_frontend_pid(log_dir)
    
    try:
        try:
            try:
                log_files.logActivity("Starting up")
                is_first=1
                while 1:
                    log_files.logActivity("Iteration at %s" % time.ctime())
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
                            log_files.logWarning("Exception at %s: %s" % (time.ctime(),string.join(tb,'')))
                
                    is_first=0
                    log_files.logActivity("Sleep")
                    time.sleep(sleep_time)
            except KeyboardInterrupt:
                log_files.logActivity("Received signal...exit")
            except:
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                log_files.logWarning("Exception at %s: %s" % (time.ctime(),string.join(tb,'')))
                raise
        finally:
            try:
                log_files.logActivity("Deadvertize my ads")
                glideinFrontendInterface.deadvertizeAllWork(factory_pool,published_frontend_name)
            except:
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                log_files.logWarning("Failed to deadvertize my ads")
                log_files.logWarning("Exception at %s: %s" % (time.ctime(),string.join(tb,'')))
    finally:
        fd.close()

############################################################
def main(config_file):
    config_dict={'loop_delay':60,
                 'factory_constraint':None,
                 'job_constraint':'JobUniverse==5',
                 'match_string':'1',
                 'job_attributes':None,
                 'max_idle_glideins_per_entry':10,'reserve_idle_glideins_per_entry':5,
                 'max_idle_vms_per_entry':50,'curb_idle_vms_per_entry':10,
                 'max_running_jobs':10000,'reserve_running_fraction':0.05,
                 'x509_proxy':None}
    execfile(config_file,config_dict)
    iterate(config_dict['log_dir'],config_dict['loop_delay'],
            config_dict['frontend_name'],config_dict['factory_pool'],config_dict['factory_constraint'],
            config_dict['x509_proxy'],
            config_dict['schedd_names'], config_dict['job_constraint'],config_dict['match_string'],config_dict['job_attributes'],
            config_dict['max_idle_glideins_per_entry'],config_dict['reserve_idle_glideins_per_entry'],
            config_dict['max_idle_vms_per_entry'],config_dict['curb_idle_vms_per_entry'],
            config_dict['max_running_jobs'], config_dict['reserve_running_fraction'],
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
    main(sys.argv[1])
 
