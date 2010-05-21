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
import glideinFrontendPlugins

############################################################
def check_parent(parent_pid):
    if os.path.exists('/proc/%s'%parent_pid):
        return # parent still exists, we are fine
    
    glideinFrontendLib.log_files.logWarning("Parent died, exit.")
    raise KeyboardInterrupt,"Parent died"

############################################################
def write_stats(stats):
    for k in stats.keys():
        stats[k].write_file();

############################################################
# Will log the factory_stat_arr (tuple composed of 10 numbers)
# and return a sum of factory_stat_arr+old_factory_stat_arr
def log_and_sum_factory_line(factory,is_down,factory_stat_arr,old_factory_stat_arr):
    # if numbers are too big, reduce them to either k or M for presentation
    form_arr=[]
    for i in factory_stat_arr:
        if i<100000:
            form_arr.append("%5i"%i)
        elif i<10000000:
            form_arr.append("%4ik"%(i/1000))
        else:
            form_arr.append("%4iM"%(i/1000000))

    if is_down:
        down_str="Down"
    else:
        down_str="Up  "

    glideinFrontendLib.log_files.logActivity(("%s(%s %s) %s(%s) | %s %s %s | %s %s "%tuple(form_arr))+
                                             ("%s %s"%(down_str,factory)))

    new_arr=[]
    for i in range(len(factory_stat_arr)):
        new_arr.append(factory_stat_arr[i]+old_factory_stat_arr[i])
    return new_arr

def init_factory_stats_arr():
    new_arr=[]
    for i in range(10):
        new_arr.append(0)
    return new_arr

def log_factory_header():
    glideinFrontendLib.log_files.logActivity("     Jobs in schedd queues      |      Glideins     |   Request   ")
    glideinFrontendLib.log_files.logActivity("Idle ( eff   old )  Run ( max ) | Total Idle   Run  | Idle MaxRun Down Factory")

############################################################
def iterate_one(client_name,elementDescript,paramsDescript,signatureDescript,x509_proxy_plugin,stats):
    frontend_name=elementDescript.frontend_data['FrontendName']
    group_name=elementDescript.element_data['GroupName']
    security_name=elementDescript.merged_data['SecurityName']

    web_url=elementDescript.frontend_data['WebURL']

    # query condor
    glidein_dict={}
    factory_constraint=elementDescript.merged_data['FactoryQueryExpr']
    factory_pools=elementDescript.merged_data['FactoryCollectors']
    for factory_pool in factory_pools:
        factory_pool_node=factory_pool[0]
        factory_identity=factory_pool[1]
        my_identity_at_factory_pool=factory_pool[2]
        try:
            factory_glidein_dict=glideinFrontendInterface.findGlideins(factory_pool_node,None,signatureDescript.signature_type,factory_constraint,x509_proxy_plugin!=None,get_only_matching=True)
        except RuntimeError,e:
            if factory_pool_node!=None:
                glideinFrontendLib.log_files.logWarning("Failed to talk to factory_pool %s. See debug log for more details."%factory_pool_node)
                glideinFrontendLib.log_files.logDebug("Failed to talk to factory_pool %s: %s"%(factory_pool_node, e))
            else:
                glideinFrontendLib.log_files.logWarning("Failed to talk to factory_pool. See debug log for more details.")
                glideinFrontendLib.log_files.logDebug("Failed to talk to factory_pool: %s"%e)
            # failed to talk, like empty... maybe the next factory will have something
            factory_glidein_dict={}
             
        for glidename in factory_glidein_dict.keys():
            if (not factory_glidein_dict[glidename]['attrs'].has_key('AuthenticatedIdentity')) or (factory_glidein_dict[glidename]['attrs']['AuthenticatedIdentity']!=factory_identity):
                glideinFrontendLib.log_files.logWarning("Found an untrusted factory %s at %s; ignoring."%(glidename,factory_pool_node))
                if factory_glidein_dict[glidename]['attrs'].has_key('AuthenticatedIdentity'):
                    glideinFrontendLib.log_files.logDebug("Found an untrusted factory %s at %s; identity mismatch '%s'!='%s'"%(glidename,factory_pool_node,factory_glidein_dict[glidename]['attrs']['AuthenticatedIdentity'],factory_identity))
            else:
                glidein_dict[(factory_pool_node,glidename,my_identity_at_factory_pool)]=factory_glidein_dict[glidename]

    ## schedd
    condorq_format_list=elementDescript.merged_data['JobMatchAttrs']
    if x509_proxy_plugin!=None:
        condorq_format_list=list(condorq_format_list)+list(x509_proxy_plugin.get_required_job_attributes())

    condorq_dict=glideinFrontendLib.getCondorQ(elementDescript.merged_data['JobSchedds'],
                                               elementDescript.merged_data['JobQueryExpr'],
                                               condorq_format_list)

    status_format_list=[]
    if x509_proxy_plugin!=None:
        status_format_list=list(status_format_list)+list(x509_proxy_plugin.get_required_classad_attributes())

    status_dict=glideinFrontendLib.getCondorStatus([None],'True',status_format_list) # use the main collector... all adds must go there

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

    # extract the public key, if present
    for glideid in glidein_dict.keys():
        glidein_el=glidein_dict[glideid]
        if not glidein_el['attrs'].has_key('PubKeyType'): # no pub key at all
            pass # no public key, nothing to do
        elif glidein_el['attrs']['PubKeyType']=='RSA': # only trust RSA for now
            try:
                glidein_el['attrs']['PubKeyObj']=pubCrypto.PubRSAKey(str(string.replace(glidein_el['attrs']['PubKeyValue'],'\\n','\n')))
            except:
                # if no valid key, just notify...
                # if key needed, will handle the error later on
                glideinFrontendLib.log_files.logWarning("Factory '%s@%s': invalid RSA key"%(glideid[1],glideid[0]))
        else:
            # don't know what to do with this key, notify the admin
            # if key needed, will handle the error later on
            glideinFrontendLib.log_files.logActivity("Factory '%s@%s': unsupported pub key type '%s'"%(glideid[1],glideid[0],glidein_el['attrs']['PubKeyType']))

    # get the proxy
    x509_proxies_data=None
    if x509_proxy_plugin!=None:
        proxy_security_classes=elementDescript.merged_data['ProxySecurityClasses']
        x509_proxy_list=x509_proxy_plugin.get_proxies(condorq_dict,condorq_dict_types,
                                                      status_dict,status_dict_types)
        glideinFrontendLib.log_files.logActivity("Using %i proxies"%len(x509_proxy_list))
        
        x509_proxies_data=[]
        for x509_proxy_list_el in x509_proxy_list:
            proxy_idx,proxy_fname=x509_proxy_list_el

            # should check if proxy has a refresh script, and call it
            # elementDescript.merged_data['ProxyRefreshScripts']
            # To be implemented

            try:
                proxy_fd=open(proxy_fname,'r')
                try:
                    proxy_data=proxy_fd.read()
                finally:
                    proxy_fd.close()
                if proxy_security_classes.has_key(proxy_fname):
                    proxy_security_class=proxy_security_classes[proxy_fname]
                else:
                    proxy_security_class=proxy_idx
                x509_proxies_data.append((proxy_idx,proxy_data,proxy_security_class))
            except:
                glideinFrontendLib.log_files.logWarning("Could not read proxy file '%s'"%proxy_fname)
                pass # do nothing else, just warn
        if len(x509_proxies_data)==0:
            glideinFrontendLib.log_files.logWarning("All proxies failed, not advertizing")
            return
        
        # ignore glidein factories that do not have a public key
        # have no way to give them the proxy
        for glideid in glidein_dict.keys():
            glidein_el=glidein_dict[glideid]
            if not glidein_el['attrs'].has_key('PubKeyObj'):
                glideinFrontendLib.log_files.logActivity("Ignoring factory '%s@%s': does not have a valid key, but x509_proxy specified"%(glideid[1],glideid[0]))
                del glidein_dict[glideid]


    # here we have all the data needed to build a GroupAdvertizeType object
    descript_obj=glideinFrontendInterface.FrontendDescript(client_name,frontend_name,group_name,
                                                           web_url,
                                                           signatureDescript.frontend_descript_fname, signatureDescript.group_descript_fname,
                                                           signatureDescript.signature_type, signatureDescript.frontend_descript_signature, signatureDescript.group_descript_signature,
                                                           x509_proxies_data)
    # reuse between loops might be a good idea, but this will work for now
    key_builder=glideinFrontendInterface.Key4AdvertizeBuilder()

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


    advertizer=glideinFrontendInterface.MultiAdvertizeWork(descript_obj)
    log_factory_header()
    total_up_stats_arr=init_factory_stats_arr()
    total_down_stats_arr=init_factory_stats_arr()
    for glideid in condorq_dict_types['Idle']['count'].keys():
        factory_pool_node=glideid[0]
        request_name=glideid[1]
        my_identity=str(glideid[2]) # get rid of unicode
        glideid_str="%s@%s"%(request_name,factory_pool_node)
        glidein_el=glidein_dict[glideid]

        glidein_in_downtime=False
        if glidein_el['attrs'].has_key('GLIDEIN_In_Downtime'):
            glidein_in_downtime=(glidein_el['attrs']['GLIDEIN_In_Downtime']=='True')

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
        this_stats_arr=(count_jobs['Idle'],effective_idle,count_jobs['OldIdle'],count_jobs['Running'],max_running,
                        count_status['Total'],count_status['Idle'],count_status['Running'],
                        glidein_min_idle,glidein_max_run)
        if glidein_in_downtime:
            total_down_stats_arr=log_and_sum_factory_line(glideid_str,glidein_in_downtime,this_stats_arr,total_down_stats_arr)
        else:
            total_up_stats_arr=log_and_sum_factory_line(glideid_str,glidein_in_downtime,this_stats_arr,total_up_stats_arr)

        # get the parameters
        glidein_params=copy.deepcopy(paramsDescript.const_data)
        for k in paramsDescript.expr_data.keys():
            kexpr=paramsDescript.expr_objs[k]
            # convert kexpr -> kval
            glidein_params[k]=glideinFrontendLib.evalParamExpr(kexpr,paramsDescript.const_data,glidein_el)

        glidein_monitors={}
        for t in count_jobs.keys():
            glidein_monitors[t]=count_jobs[t]
        for t in count_status.keys():
            glidein_monitors['Glideins%s'%t]=count_status[t]
        if descript_obj.need_encryption():
            key_obj=key_builder.get_key_obj(my_identity,
                                            glidein_el['attrs']['PubKeyID'],glidein_el['attrs']['PubKeyObj'])
        else:
            if (glidein_el['attrs'].has_key('PubKeyObj') and glidein_el['attrs'].has_key('PubKeyID')):
                # still want to encript the security_name
                key_obj=key_builder.get_key_obj(my_identity,
                                                glidein_el['attrs']['PubKeyID'],glidein_el['attrs']['PubKeyObj'])
            else:
                # if no proxies, encryption is not required
                key_obj=None

        advertizer.add(factory_pool_node,
                       request_name,request_name,
                       glidein_min_idle,glidein_max_run,glidein_params,glidein_monitors,
                       key_obj,glidein_params_to_encrypt=None,security_name=security_name)
    # end for glideid in condorq_dict_types['Idle']['count'].keys()

    # Print the totals
    # Ignore the resulting sum
    log_factory_header()
    log_and_sum_factory_line('Sum of useful factories',False,tuple(total_up_stats_arr),total_down_stats_arr)
    log_and_sum_factory_line('Sum of down factories',True,tuple(total_down_stats_arr),total_up_stats_arr)
        
    try:
        glideinFrontendLib.log_files.logActivity("Advertizing %i requests"%advertizer.get_queue_len())
        advertizer.do_advertize()
        glideinFrontendLib.log_files.logActivity("Done advertizing")
    except glideinFrontendInterface.MultiExeError, e:
        glideinFrontendLib.log_files.logWarning("Advertizing failed for %i requests. See debug log for more details."%len(e.arr))
        for ee in e.arr:
            glideinFrontendLib.log_files.logDebug("Advertizing failed: %s"%ee)
        
    except RuntimeError, e:
      glideinFrontendLib.log_files.logWarning("Advertizing failed. See debug log for more details.")
      glideinFrontendLib.log_files.logDebug("Advertizing failed: %s"%e)
    except:
      glideinFrontendLib.log_files.logWarning("Advertizing failed: Reason unknown")
      tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                      sys.exc_info()[2])
      glideinFrontendLib.log_files.logDebug("Advertizing failed: %s"%string.join(tb,''))

    return

############################################################
def iterate(parent_pid,elementDescript,paramsDescript,signatureDescript,x509_proxy_plugin):
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
            check_parent(parent_pid)
            glideinFrontendLib.log_files.logActivity("Iteration at %s" % time.ctime())
            try:
                # recreate every time (an easy way to start from a clean state)
                stats['group']=glideinFrontendMonitoring.groupStats()
                
                done_something=iterate_one(published_frontend_name,elementDescript,paramsDescript,signatureDescript,x509_proxy_plugin,stats)
                
                glideinFrontendLib.log_files.logActivity("Writing stats")
                try:
                    write_stats(stats)
                except KeyboardInterrupt:
                    raise # this is an exit signal, pass through
                except:
                    # never fail for stats reasons!
                    tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                    sys.exc_info()[2])
                    glideinFrontendLib.log_files.logWarning("Unhandled exception, ignoring. See debug log for more details.")
                    glideinFrontendLib.log_files.logDebug("Exception at %s: %s" % (time.ctime(),string.join(tb,'')))
            except KeyboardInterrupt:
                raise # this is an exit signal, pass trough
            except:
                if is_first:
                    raise
                else:
                    # if not the first pass, just warn
                    tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                    sys.exc_info()[2])
                    glideinFrontendLib.log_files.logWarning("Unhandled exception, ignoring. See debug log for more details.")
                    glideinFrontendLib.log_files.logDebug("Exception at %s: %s" % (time.ctime(),string.join(tb,'')))
                
            is_first=0
            
            # do it just before the sleep
            glideinFrontendLib.log_files.cleanup()

            glideinFrontendLib.log_files.logActivity("Sleep")
            time.sleep(sleep_time)
    finally:
        glideinFrontendLib.log_files.logActivity("Deadvertize my ads")
        for factory_pool in factory_pools:
            factory_pool_node=factory_pool[0]
            try:
                glideinFrontendInterface.deadvertizeAllWork(factory_pool_node,published_frontend_name)
            except:
                pass # just ignore errors... this was cleanup

############################################################
def main(parent_pid, work_dir, group_name):
    startup_time=time.time()

    elementDescript=glideinFrontendConfig.ElementMergedDescript(work_dir,group_name)

    # the log dir is shared between the frontend main and the groups, so use a subdir
    log_dir=os.path.join(elementDescript.frontend_data['LogDir'],"group_%s"%group_name)

    # Configure the process to use the proper LogDir as soon as you get the info
    glideinFrontendLib.log_files=glideinFrontendLib.LogFiles(log_dir,
                                                             float(elementDescript.frontend_data['LogRetentionMaxDays']),
                                                             float(elementDescript.frontend_data['LogRetentionMinDays']),
                                                             float(elementDescript.frontend_data['LogRetentionMaxMBs']))

    paramsDescript=glideinFrontendConfig.ParamsDescript(work_dir,group_name)
    signatureDescript=glideinFrontendConfig.GroupSignatureDescript(work_dir,group_name)

    glideinFrontendMonitoring.monitoringConfig.monitor_dir=os.path.join(work_dir,"monitor/group_%s"%group_name)

    if len(elementDescript.merged_data['Proxies'])>0:
        if not glideinFrontendPlugins.proxy_plugins.has_key(elementDescript.merged_data['ProxySelectionPlugin']):
            glideinFrontendLib.log_files.logWarning("Invalid ProxySelectionPlugin '%s', supported plugins are %s"%(elementDescript.merged_data['ProxySelectionPlugin']),glideinFrontendPlugins.proxy_plugins.keys())
            return 1
        x509_proxy_plugin=glideinFrontendPlugins.proxy_plugins[elementDescript.merged_data['ProxySelectionPlugin']](os.path.join(work_dir,"group_%s"%group_name),elementDescript.merged_data['Proxies'])
    else:
        # no proxies, will try to use the factory one
        x509_proxy_plugin=None

    # set the condor configuration and GSI setup globally, so I don't need to worry about it later on
    os.environ['CONDOR_CONFIG']=elementDescript.frontend_data['CondorConfig']
    os.environ['_CONDOR_CERTIFICATE_MAPFILE']=elementDescript.element_data['MapFile']
    os.environ['X509_USER_PROXY']=elementDescript.frontend_data['ClassAdProxy']

    # create lock file
    pid_obj=glideinFrontendPidLib.ElementPidSupport(work_dir,group_name)

    pid_obj.register(parent_pid)
    try:
        try:
            glideinFrontendLib.log_files.logActivity("Starting up")
            iterate(parent_pid,elementDescript,paramsDescript,signatureDescript,x509_proxy_plugin)
        except KeyboardInterrupt:
            glideinFrontendLib.log_files.logActivity("Received signal...exit")
        except:
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            glideinFrontendLib.log_files.logWarning("Unhandled exception, dying. See debug log for more details.")
            glideinFrontendLib.log_files.logDebug("Exception at %s, dying: %s" % (time.ctime(),string.join(tb,'')))
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
    main(sys.argv[1],sys.argv[2],sys.argv[3])
 
