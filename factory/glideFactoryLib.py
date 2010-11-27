#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glideFactoryLib.py,v 1.55.2.13.2.1 2010/11/27 17:36:37 sfiligoi Exp $
#
# Description:
#   This module implements the functions needed to keep the
#   required number of idle glideins
#   It also has support for glidein sanitizing
#
# Author:
#   Igor Sfiligoi (Sept 7th 2006)
#

import os,sys
import time
import string
import re
import traceback
import pwd
import binascii
import condorExe,condorPrivsep
import logSupport
import condorMonitor

MY_USERNAME=pwd.getpwuid(os.getuid())[0]

############################################################
#
# Configuration
#
############################################################

class FactoryConfig:
    def __init__(self):
        # set default values
        # user should modify if needed

        # The name of the attribute that identifies the glidein
        self.factory_schedd_attribute = "GlideinFactory"
        self.glidein_schedd_attribute = "GlideinName"
        self.entry_schedd_attribute = "GlideinEntryName"
        self.client_schedd_attribute = "GlideinClient"
        self.x509id_schedd_attribute = "GlideinX509Identifier"

        self.factory_startd_attribute = "GLIDEIN_Factory"
        self.glidein_startd_attribute = "GLIDEIN_Name"
        self.entry_startd_attribute = "GLIDEIN_Entry_Name"
        self.client_startd_attribute = "GLIDEIN_Client"
        self.schedd_startd_attribute = "GLIDEIN_Schedd"
        self.clusterid_startd_attribute = "GLIDEIN_ClusterId"
        self.procid_startd_attribute = "GLIDEIN_ProcId"

        self.count_env = 'GLIDEIN_COUNT'

        self.submit_fname="job_submit.sh"


        # Stale value settings, in seconds
        self.stale_maxage={ 1:7*24*3600,      # 1 week for idle
                            2:31*24*3600,     # 1 month for running
                           -1:2*3600}         # 2 hours for unclaimed (using special value -1 for this)

        # Sleep times between commands
        self.submit_sleep = 0.2
        self.remove_sleep = 0.2
        self.release_sleep = 0.2

        # Max commands per cycle
        self.max_submits = 100
        self.max_cluster_size=10
        self.max_removes = 5
        self.max_releases = 20

        # monitoring objects
        # create them for the logging to occur
        self.client_internals = None
        self.qc_stats = None
        self.log_stats = None
        self.rrd_stats = None

        self.supported_signtypes=['sha1']

        # who am I
        self.factory_name=None
        self.glidein_name=None
        # do not add the entry_name, as we may decide someday to share
        # the same process between multiple entries

        # used directories
        self.submit_dir=None
        self.log_base_dir=None
        self.client_log_base_dir=None
        self.client_proxies_base_dir=None

    def config_whoamI(self,factory_name,glidein_name):
        self.factory_name=factory_name
        self.glidein_name=glidein_name

    def config_dirs(self,submit_dir,log_base_dir,client_log_base_dir,client_proxies_base_dir):
        self.submit_dir=submit_dir
        self.log_base_dir=log_base_dir
        self.client_log_base_dir=client_log_base_dir
        self.client_proxies_base_dir=client_proxies_base_dir

    def config_submit_freq(self,sleepBetweenSubmits,maxSubmitsXCycle):
        self.submit_sleep=sleepBetweenSubmits
        self.max_submits=maxSubmitsXCycle

    def config_remove_freq(self,sleepBetweenRemoves,maxRemovesXCycle):
        self.remove_sleep=sleepBetweenRemoves
        self.max_removes=maxRemovesXCycle

    def get_client_log_dir(self,entry_name,username):
        log_dir=os.path.join(self.client_log_base_dir,"user_%s/glidein_%s/entry_%s"%(username,self.glidein_name,entry_name))
        return log_dir

    def get_client_proxies_dir(self,entry_name,username):
        proxy_dir=os.path.join(self.client_proxies_base_dir,"user_%s/glidein_%s/entry_%s"%(username,self.glidein_name,entry_name))
        return proxy_dir


# global configuration of the module
factoryConfig=FactoryConfig()

############################################################
#
# Log files
#
# Consider moving them to a dedicated file
# since it is the only part in common between main and entries
#
############################################################

class PrivsepDirCleanupWSpace(logSupport.DirCleanupWSpace):
    def __init__(self,
                 username,         # if None, no privsep
                 dirname,
                 fname_expression, # regular expression, used with re.match
                 maxlife,          # max lifetime after which it is deleted
                 minlife,maxspace, # max space allowed for the sum of files, unless they are too young
                 activity_log,warning_log): # if None, no logging
        logSupport.DirCleanupWSpace.__init__(self,dirname,fname_expression,
                                             maxlife,minlife,maxspace,
                                             activity_log,warning_log)
        self.username=username

    def delete_file(self,fpath):
        if (self.username!=None) and (self.username!=MY_USERNAME):
            # use privsep
            # do not use rmtree as we do not want root privileges
            condorPrivsep.execute(self.username,os.path.dirname(fpath),'/bin/rm',['rm',fpath],stdout_fname=None)
        else:
            # use the native method, if possible
            os.unlink(fpath)

class LogFiles:
    def __init__(self,log_dir,max_days,min_days,max_mbs):
        self.log_dir=log_dir
        self.activity_log=logSupport.DayLogFile(os.path.join(log_dir,"factory"),"info.log")
        self.warning_log=logSupport.DayLogFile(os.path.join(log_dir,"factory"),"err.log")
        self.debug_log=logSupport.DayLogFile(os.path.join(log_dir,"factory"),"debug.log")
        # no need to use the privsep version
        self.cleanupObjs=[logSupport.DirCleanupWSpace(log_dir,"(factory\.[0-9]*\.info\.log)|(factory\.[0-9]*\.err\.log)|(factory\.[0-9]*\.debug\.log)",
                                                      int(max_days*24*3600),int(min_days*24*3600),
                                                      long(max_mbs*(1024.0*1024.0)),
                                                      self.activity_log,self.warning_log)]

    def logActivity(self,str):
        try:
            self.activity_log.write(str)
        except:
            # logging must never throw an exception!
            self.logWarning("logActivity failed, was logging: %s"%str,False)

    def logWarning(self,str, log_in_activity=True):
        try:
            self.warning_log.write(str)
        except:
            # logging must throw an exception!
            # silently ignore
            pass
        if log_in_activity:
            self.logActivity("WARNING: %s"%str)

    def logDebug(self,str):
        try:
            self.debug_log.write(str)
        except:
            # logging must never throw an exception!
            # silently ignore
            pass

    def cleanup(self):
        for cleanupObj in self.cleanupObjs:
            try:
                cleanupObj.cleanup()
            except:
                # logging must never throw an exception!
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                self.logWarning("%s cleanup failed."%cleanupObj.dirname)
                self.logDebug("%s cleanup failed: Exception %s"%(cleanupObj.dirname,string.join(tb,'')))
                
    #
    # Clients can add additional cleanup objects, if needed
    #
    def add_dir_to_cleanup(self,
                           username,       # if None, no privsep
                           dir_to_cleanup,fname_expression,
                           max_days,min_days,max_mbs):
        self.cleanupObjs.append(PrivsepDirCleanupWSpace(username,dir_to_cleanup,fname_expression,
                                                        int(max_days*24*3600),int(min_days*24*3600),
                                                        long(max_mbs*(1024.0*1024.0)),
                                                        self.activity_log,self.warning_log))
        

# someone needs to initialize this
# type LogFiles
log_files=None

############################################################
#
# User functions
#
############################################################

#
# Get Condor data, given the glidein name
# To be passed to the main functions
#

def getCondorQData(entry_name,
                   client_name,                    # if None, return all clients
                   schedd_name,
                   factory_schedd_attribute=None,  # if None, use the global one
                   glidein_schedd_attribute=None,  # if None, use the global one
                   entry_schedd_attribute=None,    # if None, use the global one
                   client_schedd_attribute=None):  # if None, use the global one
    global factoryConfig

    if factory_schedd_attribute==None:
        fsa_str=factoryConfig.factory_schedd_attribute
    else:
        fsa_str=factory_schedd_attribute

    if glidein_schedd_attribute==None:
        gsa_str=factoryConfig.glidein_schedd_attribute
    else:
        gsa_str=glidein_schedd_attribute
   
    if entry_schedd_attribute==None:
        esa_str=factoryConfig.entry_schedd_attribute
    else:
        esa_str=entry_schedd_attribute

    if client_schedd_attribute==None:
        csa_str=factoryConfig.client_schedd_attribute
    else:
        csa_str=client_schedd_attribute

    if client_name==None:
        client_constraint=""
    else:
        client_constraint=' && (%s =?= "%s")'%(csa_str,client_name)

    x509id_str=factoryConfig.x509id_schedd_attribute

    q_glidein_constraint='(%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s")%s && (%s =!= UNDEFINED)'%(fsa_str,factoryConfig.factory_name,gsa_str,factoryConfig.glidein_name,esa_str,entry_name,client_constraint,x509id_str)
    q_glidein_format_list=[("JobStatus","i"),("GridJobStatus","s"),("ServerTime","i"),("EnteredCurrentStatus","i"),(factoryConfig.x509id_schedd_attribute,"s"),("HoldReasonCode","i"), ("HoldReasonSubCode","i")]

    q=condorMonitor.CondorQ(schedd_name)
    q.factory_name=factoryConfig.factory_name
    q.glidein_name=factoryConfig.glidein_name
    q.entry_name=entry_name
    q.client_name=client_name
    q.load(q_glidein_constraint,q_glidein_format_list)
    return q

def getQStatus(condorq):
    qc_status=condorMonitor.Summarize(condorq,hash_status).countStored()
    return qc_status

def getQStatusStale(condorq):
    qc_status=condorMonitor.Summarize(condorq,hash_statusStale).countStored()
    return qc_status

def getCondorStatusData(entry_name,client_name,pool_name=None,
                        factory_startd_attribute=None,  # if None, use the global one
                        glidein_startd_attribute=None,  # if None, use the global one
                        entry_startd_attribute=None,    # if None, use the global one
                        client_startd_attribute=None):  # if None, use the global one
    global factoryConfig

    if factory_startd_attribute==None:
        fsa_str=factoryConfig.factory_startd_attribute
    else:
        fsa_str=factory_startd_attribute

    if glidein_startd_attribute==None:
        gsa_str=factoryConfig.glidein_startd_attribute
    else:
        gsa_str=glidein_startd_attribute

    if entry_startd_attribute==None:
        esa_str=factoryConfig.entry_startd_attribute
    else:
        esa_str=entry_startd_attribute

    if client_startd_attribute==None:
        csa_str=factoryConfig.client_startd_attribute
    else:
        csa_str=client_startd_attribute

    status_glidein_constraint='(%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s")'%(fsa_str,factoryConfig.factory_name,gsa_str,factoryConfig.glidein_name,esa_str,entry_name,csa_str,client_name)
    status=condorMonitor.CondorStatus(pool_name=pool_name)
    status.factory_name=factoryConfig.factory_name
    status.glidein_name=factoryConfig.glidein_name
    status.entry_name=entry_name
    status.client_name=client_name
    status.load(status_glidein_constraint)
    return status


#
# Create/update the proxy file
# returns the proxy fname
def update_x509_proxy_file(entry_name,username,client_id, proxy_data):
    proxy_dir=factoryConfig.get_client_proxies_dir(entry_name,username)
    fname_short='x509_%s.proxy'%escapeParam(client_id)
    fname=os.path.join(proxy_dir,fname_short)
    if username!=MY_USERNAME:
        # use privsep
        # all args go through the environment, so they are protected
        update_proxy_env=['HEXDATA=%s'%binascii.b2a_hex(proxy_data),'FNAME=%s'%fname]
        for var in ('PATH','LD_LIBRARY_PATH','PYTHON_PATH'):
            if os.environ.has_key(var):
                update_proxy_env.append('%s=%s'%(var,os.environ[var]))

        try:
            condorPrivsep.execute(username,factoryConfig.submit_dir,os.path.join(factoryConfig.submit_dir,'update_proxy.py'),['update_proxy.py'],update_proxy_env)
        except condorPrivsep.ExeError, e:
            raise RuntimeError,"Failed to update proxy %s in %s (user %s): %s"%(client_id,proxy_dir,username,e)
        except:
            raise RuntimeError,"Failed to update proxy %s in %s (user %s): Unknown privsep error"%(client_id,proxy_dir,username)
        return fname
    else:
        # do it natively when you can
        if not os.path.isfile(fname):
            # new file, create
            fd=os.open(fname,os.O_CREAT|os.O_WRONLY,0600)
            try:
                os.write(fd,proxy_data)
            finally:
                os.close(fd)
            return fname

        # old file exists, check if same content
        fl=open(fname,'r')
        try:
            old_data=fl.read()
        finally:
            fl.close()
        if proxy_data==old_data:
            # nothing changed, done
            return fname

        #
        # proxy changed, neeed to update
        #
        
        # remove any previous backup file
        try:
            os.remove(fname+".old")
        except:
            pass # just protect
    
        # create new file
        fd=os.open(fname+".new",os.O_CREAT|os.O_WRONLY,0600)
        try:
            os.write(fd,proxy_data)
        finally:
            os.close(fd)

        # move the old file to a tmp and the new one into the official name
        try:
            os.rename(fname,fname+".old")
        except:
            pass # just protect
        os.rename(fname+".new",fname)
        return fname

    # end of update_x509_proxy_file
    # should never reach this point
#
# Main function
#   Will keep the required number of Idle glideins
#
class ClientWebNoGroup:
    def __init__(self,client_web_url,
                 client_signtype,
                 client_descript,client_sign):
        if not (client_signtype in factoryConfig.supported_signtypes):
            raise ValueError, "Signtype '%s' not supported!"%client_signtype
        self.url=client_web_url
        self.signtype=client_signtype
        self.descript=client_descript
        self.sign=client_sign
        return

    def get_glidein_args(self):
        return ["-clientweb",self.url,"-clientsign",self.sign,"-clientsigntype",self.signtype,"-clientdescript",self.descript]


class ClientWeb(ClientWebNoGroup):
    def __init__(self,client_web_url,
                 client_signtype,
                 client_descript,client_sign,
                 client_group,client_group_web_url,
                 client_group_descript,client_group_sign):
        ClientWebNoGroup.__init__(self,client_web_url,
                                  client_signtype,
                                  client_descript,client_sign)
        self.group_name=client_group
        self.group_url=client_group_web_url
        self.group_descript=client_group_descript
        self.group_sign=client_group_sign
        return

    def get_glidein_args(self):
        return (ClientWebNoGroup.get_glidein_args(self)+
                ["-clientgroup",self.group_name,"-clientwebgroup",self.group_url,"-clientsigngroup",self.group_sign,"-clientdescriptgroup",self.group_descript])

# Returns number of newely submitted glideins
# Can throw a condorExe.ExeError exception
def keepIdleGlideins(client_condorq,client_int_name,
                     min_nr_idle,max_nr_running,max_held,submit_attrs,
                     x509_proxy_identifier,x509_proxy_fname,x509_proxy_username,
                     client_web, # None means client did not pass one, backwards compatibility
                     params):
    global factoryConfig

    # filter out everything but the proper x509_proxy_identifier
    condorq=condorMonitor.SubQuery(client_condorq,lambda d:(d[factoryConfig.x509id_schedd_attribute]==x509_proxy_identifier))
    condorq.schedd_name=client_condorq.schedd_name
    condorq.factory_name=client_condorq.factory_name
    condorq.glidein_name=client_condorq.glidein_name
    condorq.entry_name=client_condorq.entry_name
    condorq.client_name=client_condorq.client_name
    condorq.load()
    condorq.x509_proxy_identifier=x509_proxy_identifier

    #
    # First check if we have enough glideins in the queue
    #

    # Count glideins by status
    qc_status=getQStatus(condorq)

    #   Held==JobStatus(5)
    if qc_status.has_key(5):
        held_glideins=qc_status[5]
        if held_glideins>max_held:
            return 0 # too many held glideins, stop submitting new jobs

    #   Idle==Jobstatus(1)
    sum_idle_count(qc_status)
    idle_glideins=qc_status[1]

    #   Running==Jobstatus(2)
    if qc_status.has_key(2):
        running_glideins=qc_status[2]
    else:
        running_glideins=0

    if ((idle_glideins<min_nr_idle) and
        ((max_nr_running==None) or  #no max
         ((running_glideins+idle_glideins)<max_nr_running))):
        stat_str="min_idle=%i, idle=%i, running=%i"%(min_nr_idle,idle_glideins,running_glideins)
        if max_nr_running!=None:
            stat_str="%s, max_running=%i"%(stat_str,max_nr_running)
        log_files.logActivity("Need more glideins: %s"%stat_str)
        add_glideins=min_nr_idle-idle_glideins
        if ((max_nr_running!=None) and
            ((running_glideins+idle_glideins+add_glideins)>max_nr_running)):
            # never exceed max_nr_running
            add_glideins=max_nr_running-(running_glideins+idle_glideins)
        try:
            submitGlideins(condorq.entry_name,condorq.schedd_name,x509_proxy_username,
                           client_int_name,add_glideins,submit_attrs,
                           x509_proxy_identifier,x509_proxy_fname,
                           client_web,params)
            return add_glideins # exit, some submitted
        except RuntimeError, e:
            log_files.logWarning("%s"%e)
            return 0 # something is wrong... assume 0 and exit
        except:
            log_files.logWarning("Unexpected error in glideFactoryLib.submitGlideins")
            return 0 # something is wrong... assume 0 and exit

    return 0

#
# Sanitizing function
#   Can be used if we the glidein connect to a reachable Collector
#

def sanitizeGlideins(condorq,status):
    global factoryConfig

    # Check if some glideins have been in idle state for too long
    stale_list=extractStale(condorq,status)
    if len(stale_list)>0:
        log_files.logWarning("Found %i stale glideins"%len(stale_list))
        removeGlideins(condorq.schedd_name,stale_list)

    # Check if some glideins have been in running state for too long
    runstale_list=extractRunStale(condorq)
    if len(runstale_list)>0:
        log_files.logWarning("Found %i stale (>%ih) running glideins"%(len(runstale_list),factoryConfig.stale_maxage[2]/3600))
        removeGlideins(condorq.schedd_name,runstale_list)

    # Check if there are held glideins that are not recoverable
    unrecoverable_held_list=extractUnrecoverableHeld(condorq,status)
    if len(unrecoverable_held_list)>0:
        log_files.logWarning("Found %i unrecoverable held glideins"%len(unrecoverable_held_list))
        removeGlideins(condorq.schedd_name,unrecoverable_held_list,force=False)

    # Check if there are held glideins
    held_list=extractRecoverableHeld(condorq,status)
    if len(held_list)>0:
        log_files.logWarning("Found %i held glideins"%len(held_list))
        releaseGlideins(condorq.schedd_name,held_list)

    # Now look for VMs that have not been claimed for a long time
    staleunclaimed_list=extractStaleUnclaimed(condorq,status)
    if len(staleunclaimed_list)>0:
        log_files.logWarning("Found %i stale unclaimed glideins"%len(staleunclaimed_list))
        removeGlideins(condorq.schedd_name,staleunclaimed_list)


    #
    # A check of glideins in "Running" state but not in status
    # should be implemented, too
    # However, it needs some sort of history to account for
    # temporary network outages
    #

    return

def sanitizeGlideinsSimple(condorq):
    global factoryConfig

    # Check if some glideins have been in idle state for too long
    stale_list=extractStaleSimple(condorq)
    if len(stale_list)>0:
        log_files.logWarning("Found %i stale glideins"%len(stale_list))
        removeGlideins(condorq.schedd_name,stale_list)

    # Check if some glideins have been in running state for too long
    runstale_list=extractRunStale(condorq)
    if len(runstale_list)>0:
        log_files.logWarning("Found %i stale (>%ih) running glideins"%(len(runstale_list),factoryConfig.stale_maxage[2]/3600))
        removeGlideins(condorq.schedd_name,runstale_list)

    # Check if there are held glideins that are not recoverable
    unrecoverable_held_list=extractUnrecoverableHeldSimple(condorq)
    if len(unrecoverable_held_list)>0:
        log_files.logWarning("Found %i unrecoverable held glideins"%len(unrecoverable_held_list))
        removeGlideins(condorq.schedd_name,unrecoverable_held_list, force=False)

    # Check if there are held glideins
    held_list=extractRecoverableHeldSimple(condorq)
    if len(held_list)>0:
        log_files.logWarning("Found %i held glideins"%len(held_list))
        releaseGlideins(condorq.schedd_name,held_list)

    return

def logStats(condorq,condorstatus,client_int_name, security_name):
    global factoryConfig
    #
    # First check if we have enough glideins in the queue
    #

    # Count glideins by status
    qc_status=getQStatus(condorq)
    sum_idle_count(qc_status)
    if condorstatus!=None:
        s_running_str=" collector running %s"%len(condorstatus.fetchStored().keys())
    else:
        s_running_str="" # not monitored
    
    log_files.logActivity("Client %s (secid: %s) schedd status %s%s"%(client_int_name,security_name,qc_status,s_running_str))
    if factoryConfig.qc_stats!=None:
        factoryConfig.qc_stats.logSchedd(security_name,qc_status)
    
    return

def logWorkRequest(client_int_name, security_name,
                   req_idle, req_max_run,
                   work_el):
    log_files.logActivity("Client %s (secid: %s) requesting %i glideins, max running %i"%(client_int_name,security_name,req_idle,req_max_run))
    log_files.logActivity("  Params: %s"%work_el['params'])
    log_files.logActivity("  Decrypted Param Names: %s"%work_el['params_decrypted'].keys()) # cannot log decrypted ones... they are most likely sensitive
    factoryConfig.qc_stats.logRequest(security_name,work_el['requests'],work_el['params'])
    factoryConfig.qc_stats.logClientMonitor(security_name,work_el['monitor'],work_el['internals'])


############################################################
#
# I N T E R N A L - Do not use
#
############################################################

#condor_status_strings = {0:"Wait",1:"Idle", 2:"Running", 3:"Removed", 4:"Completed", 5:"Held", 6:"Suspended", 7:"Assigned"}
#myvm_status_strings = {-1:"Unclaimed}

#
# Hash functions
#

def get_status_glideidx(el):
    global factoryConfig
    return (el[factoryConfig.clusterid_startd_attribute],el[factoryConfig.procid_startd_attribute])

# Split idle depending on GridJobStatus
#   1001 : Unsubmitted
#   1002 : Submitted/Pending
#   1010 : Staging in
#   1100 : Other
#   4010 : Staging out
# All others just return the JobStatus
def hash_status(el):
    job_status=el["JobStatus"]
    if job_status==1:
        # idle jobs, look of GridJobStatus
        if el.has_key("GridJobStatus"):
            grid_status=el["GridJobStatus"]
            if grid_status in ("PENDING","INLRMS: Q","PREPARED","SUBMITTING"):
                return 1002
            elif grid_status in ("STAGE_IN","PREPARING","ACCEPTING"):
                return 1010
            else:
                return 1100
        else:
            return 1001
    elif job_status==2:
        # count only real running, all others become Other
        if el.has_key("GridJobStatus"):
            grid_status=el["GridJobStatus"]
            if grid_status in ("ACTIVE","REALLY-RUNNING","INLRMS: R"):
                return 2
            elif grid_status in ("STAGE_OUT","INLRMS: E","EXECUTED","FINISHING"):
                return 4010
            else:
                return 1100
        else:
            return 2        
    else:
        # others just pass over
        return job_status

# helper function that sums up the idle states
def sum_idle_count(qc_status):
    #   Idle==Jobstatus(1)
    #   Have to integrate all the variants
    qc_status[1]=0
    for k in qc_status.keys():
        if (k>=1000) and (k<1100):
            qc_status[1]+=qc_status[k]
    return

def hash_statusStale(el):
    global factoryConfig
    age=el["ServerTime"]-el["EnteredCurrentStatus"]
    jstatus=el["JobStatus"]
    if factoryConfig.stale_maxage.has_key(jstatus):
        return [jstatus,age>factoryConfig.stale_maxage[jstatus]]
    else:
        return [jstatus,0] # others are not stale


#
# diffList == base_list - subtract_list
#

def diffList(base_list, subtract_list):
    if len(subtract_list)==0:
        return base_list # nothing to do
    
    out_list=[]
    for i in base_list:
        if not (i in subtract_list):
            out_list.append(i)

    return out_list
    

#
# Extract functions
# Will compare with the status info to make sure it does not show good ones
#

# return list of glidein clusters within the search list
def extractRegistered(q,status,search_list):
    global factoryConfig
    sdata=status.fetchStored(lambda el:(el[factoryConfig.schedd_startd_attribute]==q.schedd_name) and (get_status_glideidx(el) in search_list))

    out_list=[]
    for vm in sdata.keys():
        el=sdata[vm]
        i=get_status_glideidx(el)
        if not (i in out_list): # prevent duplicates from multiple VMs
            out_list.append(i)

    return out_list


def extractStale(q,status):
    # first find out the stale idle jids
    #  hash: (Idle==1, Stale==1)
    qstale=q.fetchStored(lambda el:(hash_statusStale(el)==[1,1]))
    qstale_list=qstale.keys()
    
    # find out if any "Idle" glidein is running instead (in condor_status)
    sstale_list=extractRegistered(q,status,qstale_list)

    return diffList(qstale_list,sstale_list)

def extractStaleSimple(q):
    # first find out the stale idle jids
    #  hash: (Idle==1, Stale==1)
    qstale=q.fetchStored(lambda el:(hash_statusStale(el)==[1,1]))
    qstale_list=qstale.keys()
    
    return qstale_list

def extractUnrecoverableHeld(q,status):
    # first find out the held jids that are not recoverable
    #  Held==5 and glideins are not recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el)))
    qheld_list=qheld.keys()
    
    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list=extractRegistered(q,status,qheld_list)
    return diffList(qheld_list,sheld_list)

def extractUnrecoverableHeldSimple(q):
    #  Held==5 and glideins are not recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el)))
    qheld_list=qheld.keys()
    return qheld_list

def extractRecoverableHeld(q,status):
    # first find out the held jids
    #  Held==5 and glideins are recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el)))
    qheld_list=qheld.keys()
    
    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list=extractRegistered(q,status,qheld_list)

    return diffList(qheld_list,sheld_list)

def extractRecoverableHeldSimple(q):
    #  Held==5 and glideins are recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el)))
    qheld_list=qheld.keys()
    return qheld_list

def extractHeld(q,status):

    # first find out the held jids
    #  Held==5
    qheld=q.fetchStored(lambda el:el["JobStatus"]==5)
    qheld_list=qheld.keys()
    
    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list=extractRegistered(q,status,qheld_list)

    return diffList(qheld_list,sheld_list)

def extractHeldSimple(q):
    #  Held==5
    qheld=q.fetchStored(lambda el:el["JobStatus"]==5)
    qheld_list=qheld.keys()
    return qheld_list

def extractRunStale(q):
    # first find out the stale running jids
    #  hash: (Running==2, Stale==1)
    qstale=q.fetchStored(lambda el:(hash_statusStale(el)==[2,1]))
    qstale_list=qstale.keys()

    # no need to check with condor_status
    # these glideins were running for too long, period!
    return qstale_list 

# helper function of extractStaleUnclaimed
def group_unclaimed(el_list):
    out={"nr_vms":0,"nr_unclaimed":0,"min_unclaimed_time":1024*1024*1024}
    for el in el_list:
        out["nr_vms"]+=1
        if el["State"]=="Unclaimed":
            out["nr_unclaimed"]+=1
            unclaimed_time=el["LastHeardFrom"]-el["EnteredCurrentState"]
            if unclaimed_time<out["min_unclaimed_time"]:
                out["min_unclaimed_time"]=unclaimed_time
    return out

def extractStaleUnclaimed(q,status):
    global factoryConfig
    # first find out the active running jids
    #  hash: (Running==2, Stale==0)
    qsearch=q.fetchStored(lambda el:(hash_statusStale(el)==[2,0]))
    search_list=qsearch.keys()
    
    # find out if any "Idle" glidein is running instead (in condor_status)
    global factoryConfig
    sgroup=condorMonitor.Group(status,lambda el:get_status_glideidx(el),group_unclaimed)
    sgroup.load(lambda el:(el[factoryConfig.schedd_startd_attribute]==q.schedd_name) and (get_status_glideidx(el) in search_list))
    sdata=sgroup.fetchStored(lambda el:(el["nr_unclaimed"]>0) and (el["min_unclaimed_time"]>factoryConfig.stale_maxage[-1]))

    return sdata.keys()

############################################################
#
# Action functions
#
############################################################

def schedd_name2str(schedd_name):
    if schedd_name==None:
        return ""
    else:
        return "-name %s"%schedd_name

extractJobId_recmp = re.compile("^(?P<count>[0-9]+) job\(s\) submitted to cluster (?P<cluster>[0-9]+)\.$")
def extractJobId(submit_out):
    for line in submit_out:
        found = extractJobId_recmp.search(line[:-1])
        if found!=None:
            return (long(found.group("cluster")),int(found.group("count")))
    raise condorExe.ExeError, "Could not find cluster info!"

escape_table={'.':'.dot,',
              ',':'.comma,',
              '&':'.amp,',
              '\\':'.backslash,',
              '|':'.pipe,',
              "`":'.fork,',
              '"':'.quot,',
              "'":'.singquot,',
              '=':'.eq,',
              '+':'.plus,',
              '-':'.minus,',
              '<':'.lt,',
              '>':'.gt,',
              '(':'.open,',
              ')':'.close,',
              '{':'.gopen,',
              '}':'.gclose,',
              '[':'.sopen,',
              ']':'.sclose,',
              '#':'.comment,',
              '$':'.dollar,',
              '*':'.star,',
              '?':'.question,',
              '!':'.not,',
              '~':'.tilde,',
              ':':'.colon,',
              ';':'.semicolon,',
              ' ':'.nbsp,'}
def escapeParam(param_str):
    global escape_table
    out_str=""
    for c in param_str:
        if escape_table.has_key(c):
            out_str=out_str+escape_table[c]
        else:
            out_str=out_str+c
    return out_str
    

# submit N new glideins
def submitGlideins(entry_name,schedd_name,username,client_name,nr_glideins,submit_attrs,
                   x509_proxy_identifier,x509_proxy_fname,
                   client_web, # None means client did not pass one, backwards compatibility
                   params):
    global factoryConfig

    submitted_jids=[]

    if nr_glideins>factoryConfig.max_submits:
        nr_glideins=factoryConfig.max_submits

    submit_attrs_arr=[]
    for e in submit_attrs:
        submit_attrs_arr.append("'"+e+"'")
    submit_attrs_str = string.join(submit_attrs_arr," ")

    params_arr=[]
    for k in params.keys():
        params_arr.append(k)
        params_arr.append(escapeParam(str(params[k])))
    params_str=string.join(params_arr," ")

    client_web_arr=[]
    if client_web!=None:
        client_web_arr=client_web.get_glidein_args()
    client_web_str=string.join(client_web_arr," ")

    try:
        nr_submitted=0
        while (nr_submitted<nr_glideins):
            if nr_submitted!=0:
                time.sleep(factoryConfig.submit_sleep)

            nr_to_submit=(nr_glideins-nr_submitted)
            if nr_to_submit>factoryConfig.max_cluster_size:
                nr_to_submit=factoryConfig.max_cluster_size

            if username!=MY_USERNAME:
                # use privsep
                exe_env=['X509_USER_PROXY=%s'%x509_proxy_fname]
                # need to push all the relevant env variables through
                for var in os.environ.keys():
                    if ((var in ('PATH','LD_LIBRARY_PATH','X509_CERT_DIR')) or
                        (var[:8]=='_CONDOR_') or (var[:7]=='CONDOR_')):
                        if os.environ.has_key(var):
                            exe_env.append('%s=%s'%(var,os.environ[var]))
                try:
                    submit_out=condorPrivsep.execute(username,factoryConfig.submit_dir,
                                                     os.path.join(factoryConfig.submit_dir,factoryConfig.submit_fname),
                                                     [factoryConfig.submit_fname,entry_name,client_name,x509_proxy_identifier,"%i"%nr_to_submit,]+
                                                     client_web_arr+submit_attrs+
                                                     ['--']+params_arr,
                                                     exe_env)
                except condorPrivsep.ExeError, e:
                    submit_out=[]
                    raise RuntimeError, "condor_submit failed (user %s): %s"%(username,e)
                except:
                    submit_out=[]
                    raise RuntimeError, "condor_submit failed (user %s): Unknown privsep error"%username
            else:
                # avoid using privsep, if possible
                try:
                    submit_out=condorExe.iexe_cmd('export X509_USER_PROXY=%s;./%s "%s" "%s" "%s" %i %s %s -- %s'%(x509_proxy_fname,factoryConfig.submit_fname,entry_name,client_name,x509_proxy_identifier,nr_to_submit,client_web_str,submit_attrs_str,params_str))
                except condorExe.ExeError,e:
                    submit_out=[]
                    raise RuntimeError, "condor_submit failed: %s"%e
                except:
                    submit_out=[]
                    raise RuntimeError, "condor_submit failed: Unknown error"
                
                
            cluster,count=extractJobId(submit_out)
            for j in range(count):
                submitted_jids.append((cluster,j))
            nr_submitted+=count
    finally:
        # write out no matter what
        log_files.logActivity("Submitted %i glideins to %s: %s"%(len(submitted_jids),schedd_name,submitted_jids))

# remove the glideins in the list
def removeGlideins(schedd_name,jid_list,force=False):
    ####
    # We are assuming the gfactory to be
    # a condor superuser and thus does not need
    # identity switching to remove jobs
    ####

    global factoryConfig

    removed_jids=[]
    
    schedd_str=schedd_name2str(schedd_name)
    is_not_first=0
    for jid in jid_list:
        if is_not_first:
            is_not_first=1
            time.sleep(factoryConfig.remove_sleep)
        try:
            condorExe.exe_cmd("condor_rm","%s %li.%li"%(schedd_str,jid[0],jid[1]))
            removed_jids.append(jid)

            # Force the removal if requested
            if force == True:
                try:
                    log_files.logActivity("Forcing the removal of glideins in X state")
                    condorExe.exe_cmd("condor_rm","-forcex %s %li.%li"%(schedd_str,jid[0],jid[1]))
                except condorExe.ExeError, e:
                    log_files.logWarning("Forcing the removal of glideins in %s.%s state failed" % (jid[0],jid[1]))

        except condorExe.ExeError, e:
            # silently ignore errors, and try next one
            log_files.logWarning("removeGlidein(%s,%li.%li): %s"%(schedd_name,jid[0],jid[1],e))

        if len(removed_jids)>=factoryConfig.max_removes:
            break # limit reached, stop


    log_files.logActivity("Removed %i glideins on %s: %s"%(len(removed_jids),schedd_name,removed_jids))

# release the glideins in the list
def releaseGlideins(schedd_name,jid_list):
    ####
    # We are assuming the gfactory to be
    # a condor superuser and thus does not need
    # identity switching to release jobs
    ####

    global factoryConfig

    released_jids=[]
    
    schedd_str=schedd_name2str(schedd_name)
    is_not_first=0
    for jid in jid_list:
        if is_not_first:
            is_not_first=1
            time.sleep(factoryConfig.release_sleep)
        try:
            condorExe.exe_cmd("condor_release","%s %li.%li"%(schedd_str,jid[0],jid[1]))
            released_jids.append(jid)
        except condorExe.ExeError, e:
            log_files.logWarning("releaseGlidein(%s,%li.%li): %s"%(schedd_name,jid[0],jid[1],e))

        if len(released_jids)>=factoryConfig.max_releases:
            break # limit reached, stop
    log_files.logActivity("Released %i glideins on %s: %s"%(len(released_jids),schedd_name,released_jids))


# Get list of CondorG job status for held jobs that are not recoverable
def isGlideinUnrecoverable(jobInfo):
    # CondorG held jobs have HeldReasonCode 2
    # CondorG held jobs with following HeldReasonSubCode are not recoverable
    # 0   : Job failed, no reason given by GRAM server 
    # 4   : jobmanager unable to set default to the directory requested 
    # 7   : authentication with the remote server failed 
    # 8   : the user cancelled the job 
    # 9   : the system cancelled the job 
    # 10  : globus_xio_gsi: Token size exceeds limit
    # 17  : the job failed when the job manager attempted to run it
    # 22  : the job manager failed to create an internal script argument file
    # 31  : the job manager failed to cancel the job as requested 
    # 47  : the gatekeeper failed to run the job manager 
    # 48  : the provided RSL could not be properly parsed 
    # 76  : cannot access cache files in ~/.globus/.gass_cache,
    #       check permissions, quota, and disk space 
    # 79  : connecting to the job manager failed. Possible reasons: job
    #       terminated, invalid job contact, network problems, ... 
    # 121 : the job state file doesn't exist 
    # 122 : could not read the job state file
    
    unrecoverable = False
    # Dictionary of {HeldReasonCode: HeldReasonSubCode}
    unrecoverableCodes = {2: [ 0, 2, 4, 5, 7, 8, 9, 10, 14, 17, 
                               22, 27, 28, 31, 37, 47, 48, 
                               72, 76, 79, 81, 86, 87,
                               121, 122 ]}

    if jobInfo.has_key('HoldReasonCode') and jobInfo.has_key('HoldReasonSubCode'):
        code = jobInfo['HoldReasonCode']
        subCode = jobInfo['HoldReasonSubCode']
        if (unrecoverableCodes.has_key(code) and (subCode in unrecoverableCodes[code])):
            unrecoverable = True
    return unrecoverable
