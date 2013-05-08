#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements the functions needed to keep the
#   required number of idle glideins
#   It also has support for glidein sanitizing
#
# Author:
#   Igor Sfiligoi (Sept 7th 2006)
#

import os
import sys
import time
import string
import re
import traceback
import pwd
import binascii
import tempfile

from glideinwms.lib import condorExe
from glideinwms.lib import condorPrivsep
from glideinwms.lib import logSupport
from glideinwms.lib import condorMonitor
from glideinwms.lib import condorManager
from glideinwms.lib import x509Support
from glideinwms.factory import glideFactoryConfig

MY_USERNAME=pwd.getpwuid(os.getuid())[0]

# Someone needs to initialize following parameters

# type LogFiles
log_files = None
group_log_files = None

# Dictionary of log file objects for entries and groups
log_files_dict = {'entry': {}, 'group': {}}

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
        self.frontend_name_attribute = "GlideinFrontendName"
        self.x509id_schedd_attribute = "GlideinX509Identifier"
        self.x509secclass_schedd_attribute = "GlideinX509SecurityClass"

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

        # release related limits
        self.max_release_count = 10
        self.min_release_time = 300

        # monitoring objects
        # create them for the logging to occur
        self.client_internals = None
        self.client_stats = None # this one is indexed by client name
        self.qc_stats = None     # this one is indexed by security class
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
def secClass2Name(client_security_name,proxy_security_class):
    return "%s_%s"%(client_security_name,proxy_security_class)

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
        if (self.username is not None) and (self.username!=MY_USERNAME):
            # use privsep
            # do not use rmtree as we do not want root privileges
            condorPrivsep.execute(self.username,os.path.dirname(fpath),'/bin/rm',['rm',fpath],stdout_fname=None)
        else:
            # use the native method, if possible
            os.unlink(fpath)

class LogFiles:
    def __init__(self,log_dir,max_days,min_days,max_mbs,file_name='factory'):
        self.log_dir=log_dir
        self.activity_log=logSupport.DayLogFile(os.path.join(log_dir,file_name),"info.log")
        self.warning_log=logSupport.DayLogFile(os.path.join(log_dir,file_name),"err.log")
        self.debug_log=logSupport.DayLogFile(os.path.join(log_dir,file_name),"debug.log")
        self.admin_log=logSupport.DayLogFile(os.path.join(log_dir,file_name),"admin.log")
        # no need to use the privsep version
        # Don't clean up admin log.  More important to have record
        cleanup_regex = ''
        for ext in ('info', 'debug', 'err', 'admin'):
            cleanup_regex += '|(%s\.[0-9]*\.%s\.log)' % (file_name, ext)

        self.cleanupObjs=[
            logSupport.DirCleanupWSpace(
                log_dir, cleanup_regex.strip('|'),
                int(max_days*24*3600),int(min_days*24*3600),
                long(max_mbs*(1024.0*1024.0)),
                self.activity_log, self.warning_log)
        ]

    def logActivity(self,str):
        try:
            self.activity_log.write(str)
        except:
            # logging must never throw an exception!
            self.logWarning("logActivity failed, was logging: %s"%str,False)

    def logError(self, str, log_in_activity=True):
        self.logWarning(str, log_in_activity)

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
    
    def logAdmin(self,str):
        try:
            self.admin_log.write(str)
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
                   client_schedd_attribute=None,   # if None, use the global one
                   x509secclass_schedd_attribute=None, # if None, use the global one
                   factoryConfig=None):
    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    if factory_schedd_attribute is None:
        fsa_str=factoryConfig.factory_schedd_attribute
    else:
        fsa_str=factory_schedd_attribute

    if glidein_schedd_attribute is None:
        gsa_str=factoryConfig.glidein_schedd_attribute
    else:
        gsa_str=glidein_schedd_attribute
   
    if entry_schedd_attribute is None:
        esa_str=factoryConfig.entry_schedd_attribute
    else:
        esa_str=entry_schedd_attribute

    if client_schedd_attribute is None:
        csa_str=factoryConfig.client_schedd_attribute
    else:
        csa_str=client_schedd_attribute

    if x509secclass_schedd_attribute is None:
        xsa_str=factoryConfig.x509secclass_schedd_attribute
    else:
        xsa_str=x509secclass_schedd_attribute

    if client_name is None:
        client_constraint=""
    else:
        client_constraint=' && (%s =?= "%s")'%(csa_str,client_name)

    x509id_str=factoryConfig.x509id_schedd_attribute

    q_glidein_constraint='(%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s")%s && (%s =!= UNDEFINED)'%(fsa_str,factoryConfig.factory_name,gsa_str,factoryConfig.glidein_name,esa_str,entry_name,client_constraint,x509id_str)
    q_glidein_format_list=[("JobStatus","i"), ("GridJobStatus","s"), ("ServerTime","i"), ("EnteredCurrentStatus","i"), 
                           (factoryConfig.x509id_schedd_attribute,"s"), ("HoldReasonCode","i"), ("HoldReasonSubCode","i"), 
                           ("NumSystemHolds","i"),
                           (factoryConfig.frontend_name_attribute, "s"), 
                           (csa_str,"s"), (xsa_str,"s")]

    q=condorMonitor.CondorQ(schedd_name)
    q.factory_name=factoryConfig.factory_name
    q.glidein_name=factoryConfig.glidein_name
    q.entry_name=entry_name
    q.client_name=client_name
    q.load(q_glidein_constraint,q_glidein_format_list)
    return q

# fiter only a specific client and proxy security class
def getQProxSecClass(condorq,
                     client_name,
                     proxy_security_class,
                     client_schedd_attribute=None,  # if None, use the global one
                     x509secclass_schedd_attribute=None): # if None, use the global one
                     
    if client_schedd_attribute is None:
        csa_str=factoryConfig.client_schedd_attribute
    else:
        csa_str=client_schedd_attribute

    if x509secclass_schedd_attribute is None:
        xsa_str=factoryConfig.x509secclass_schedd_attribute
    else:
        xsa_str=x509secclass_schedd_attribute

    entry_condorQ=condorMonitor.SubQuery(condorq,lambda d:(d.has_key(csa_str) and (d[csa_str]==client_name) and
                                                           d.has_key(xsa_str) and (d[xsa_str]==proxy_security_class)))
    entry_condorQ.schedd_name=condorq.schedd_name
    entry_condorQ.factory_name=condorq.factory_name
    entry_condorQ.glidein_name=condorq.glidein_name
    entry_condorQ.entry_name=condorq.entry_name
    entry_condorQ.client_name=condorq.client_name
    entry_condorQ.load()
    return entry_condorQ

def getQStatus(condorq):
    qc_status=condorMonitor.Summarize(condorq,hash_status).countStored()
    return qc_status

def getQStatusStale(condorq):
    qc_status=condorMonitor.Summarize(condorq,hash_statusStale).countStored()
    return qc_status

###########################
# This function is not used
###########################

def getCondorStatusData(entry_name,client_name,pool_name=None,
                        factory_startd_attribute=None,  # if None, use the global one
                        glidein_startd_attribute=None,  # if None, use the global one
                        entry_startd_attribute=None,    # if None, use the global one
                        client_startd_attribute=None,
                        factoryConfig=None):  # if None, use the global one

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    if factory_startd_attribute is None:
        fsa_str=factoryConfig.factory_startd_attribute
    else:
        fsa_str=factory_startd_attribute

    if glidein_startd_attribute is None:
        gsa_str=factoryConfig.glidein_startd_attribute
    else:
        gsa_str=glidein_startd_attribute

    if entry_startd_attribute is None:
        esa_str=factoryConfig.entry_startd_attribute
    else:
        esa_str=entry_startd_attribute

    if client_startd_attribute is None:
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
def update_x509_proxy_file(entry_name, username, client_id, 
                           proxy_data, logfiles=log_files,
                           factoryConfig=None):

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    proxy_dir=factoryConfig.get_client_proxies_dir(entry_name,username)
    
    dn=""
    voms=""
    try:
        (f,tempfilename)=tempfile.mkstemp()
        os.write(f,proxy_data)
        os.close(f)
    except:
        logfiles.logWarning("Unable to create tempfile %s!" % tempfilename)
    
    try:
        dn = x509Support.extract_DN(tempfilename)

        voms_proxy_info = which('voms-proxy-info')
        if voms_proxy_info is not None:
            voms_list = condorExe.iexe_cmd("%s -fqan -file %s" % (voms_proxy_info, tempfilename))
            #sort output in case order of voms fqan changed
            voms='\n'.join(sorted(voms_list))
    except:
        #If voms-proxy-info doesn't exist or errors out, just hash on dn
        voms=""

    try:
        os.unlink(tempfilename)
    except:
        logfiles.logWarning("Unable to delete tempfile %s!" % tempfilename)

    hash_val=str(abs(hash(dn+voms))%1000000)

    fname_short='x509_%s_%s.proxy'%(escapeParam(client_id),hash_val)
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


def keepIdleGlideins(client_condorq, client_int_name, in_downtime,
                     remove_excess, req_min_idle, req_max_glideins,
                     glidein_totals, frontend_name, x509_proxy_identifier,
                     x509_proxy_fname,x509_proxy_username,
                     x509_proxy_security_class, client_web, params,
                     logfiles=log_files,
                     factoryConfig=None):
    """ 
    Submits more glideins if needed, else, clean up the queue.
    client_web = None means client did not pass one, backwards compatibility
    
    Returns number of newly submitted glideins
    Can throw a condorExe.ExeError exception
    """
    
    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    # filter out everything but the proper x509_proxy_identifier
    condorq=condorMonitor.SubQuery(client_condorq,lambda d:(d[factoryConfig.x509id_schedd_attribute]==x509_proxy_identifier))
    condorq.schedd_name=client_condorq.schedd_name
    condorq.factory_name=client_condorq.factory_name
    condorq.glidein_name=client_condorq.glidein_name
    condorq.entry_name=client_condorq.entry_name
    condorq.client_name=client_condorq.client_name
    condorq.load()
    condorq.x509_proxy_identifier=x509_proxy_identifier
    
    # Check that have not exceeded max held for this security class
    if glidein_totals.has_sec_class_exceeded_max_held(frontend_name):
        # Too many held, don't submit
        logfiles.logActivity("Too many held glideins for this frontend-security class: %i=held %i=max_held" % (glidein_totals.frontend_limits[frontend_name]['held'], glidein_totals.frontend_limits[frontend_name]['max_held']))
        # run sanitize... we have to get out of this mess
        sanitizeGlideinsSimple(condorq, logfiles=logfiles,
                               factoryConfig=factoryConfig)
        # we have done something... return non-0 so sanitize is not called again
        return 1
    
    # Count glideins for this request credential by status
    qc_status = getQStatus(condorq)
    
    # Held==JobStatus(5)
    q_held_glideins = 0
    if qc_status.has_key(5): 
        q_held_glideins = qc_status[5]
    # Idle==Jobstatus(1)
    sum_idle_count(qc_status)
    q_idle_glideins = qc_status[1]
    # Running==Jobstatus(2)
    q_running_glideins = 0
    if qc_status.has_key(2):
        q_running_glideins = qc_status[2]
    
    # Determine how many more idle glideins we need in requested idle (we may already have some)
    add_glideins = req_min_idle - q_idle_glideins  
       
    if add_glideins <= 0:
        # Have enough idle, don't submit
        logfiles.logActivity("Have enough glideins: idle=%i req_idle=%i, not submitting" % (q_idle_glideins, req_min_idle))
        return clean_glidein_queue(remove_excess, glidein_totals, condorq,
                                   req_min_idle, req_max_glideins, 
                                   frontend_name, logfiles=logfiles,
                                   factoryConfig=factoryConfig)
    else:
        # Need more idle
        
        # Check that adding more idle doesn't exceed request max_glideins
        if q_idle_glideins + q_held_glideins + q_running_glideins + add_glideins >= req_max_glideins:
            # Exceeded limit, try to adjust
            add_glideins = req_max_glideins - q_idle_glideins -  q_held_glideins - q_running_glideins
            
            if add_glideins <= 0:
                # Have hit request limit, cannot submit
                logfiles.logActivity("Additional idle glideins %s needed exceeds request max_glideins limits %s, not submitting" % (add_glideins, req_max_glideins))
                return clean_glidein_queue(remove_excess, glidein_totals,
                                           condorq, req_min_idle, 
                                           req_max_glideins, frontend_name,
                                           logfiles=logfiles,
                                           factoryConfig=factoryConfig)
        
    # Have a valid idle number to request
    # Check that adding more doesn't exceed frontend:sec_class and entry limits
    
    add_glideins = glidein_totals.can_add_idle_glideins(add_glideins, frontend_name)
    if add_glideins <= 0:
        # Have hit entry or frontend:sec_class limit, cannot submit
        logfiles.logActivity("Additional %s idle glideins requested by %s exceeds frontend:security class limit for the entry, not submitting" % (req_min_idle, frontend_name))
        return clean_glidein_queue(remove_excess, glidein_totals, condorq,
                                   req_min_idle, req_max_glideins, 
                                   frontend_name, logfiles=logfiles,
                                   factoryConfig=factoryConfig)
    else:
        # If we are requesting more than the maximum glideins that we can submit at one time, then set to the max submit number
        #   this helps to keep one frontend/request from getting all the glideins
        if add_glideins > factoryConfig.max_submits:
            add_glideins = factoryConfig.max_submits  
            logfiles.logDebug("Additional idle glideins exceeded entry max submit limits %s, adjusted add_glideins to entry max submit rate" % factoryConfig.max_submits)  
    
    try:
        submitGlideins(condorq.entry_name, condorq.schedd_name,
                       x509_proxy_username, client_int_name, add_glideins,
                       frontend_name, x509_proxy_identifier,
                       x509_proxy_security_class,x509_proxy_fname,
                       client_web, params, logfiles=logfiles,
                       factoryConfig=factoryConfig)
        glidein_totals.add_idle_glideins(add_glideins, frontend_name)
        return add_glideins # exit, some submitted
    except RuntimeError, e:
        logfiles.logWarning("%s" % e)
        return 0 # something is wrong... assume 0 and exit
    except:
        logfiles.logWarning("Unexpected error in glideFactoryLib.submitGlideins")
        return 0 # something is wrong... assume 0 and exit

    return 0

     
def clean_glidein_queue(remove_excess, glidein_totals, condorQ, req_min_idle,
                        req_max_glideins, frontend_name, logfiles=log_files,
                        factoryConfig=None):
    """
    Cleans up the glideins queue (removes any excesses) per the frontend request.
    
    We are not adjusting the glidein totals with what has been removed from the queue.  It may take a cycle (or more)
    for these totals to occur so it would be difficult to reflect the true state of the system.   
    """      
    
    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    sec_class_idle = glidein_totals.frontend_limits[frontend_name]['idle']
    sec_class_held = glidein_totals.frontend_limits[frontend_name]['held']
    sec_class_running = glidein_totals.frontend_limits[frontend_name]['running']
        
    remove_excess_wait = False
    remove_excess_idle = False
    remove_excess_running = False
    if remove_excess == 'WAIT':
        remove_excess_wait = True
    elif remove_excess == 'IDLE':
        remove_excess_wait = True
        remove_excess_idle = True
    elif remove_excess == 'ALL':
        remove_excess_wait = True
        remove_excess_idle = True
        remove_excess_running = True
    else:
        if remove_excess != 'NO':
            logfiles.logActivity("Unknown RemoveExcess provided in the request '%s', assuming 'NO'" % remove_excess)
        
    if (((remove_excess_wait or remove_excess_idle) and
           (sec_class_idle > req_min_idle)) or
          (remove_excess_running and 
           ((req_max_glideins is not None) and  #make sure there is a max
            ((sec_class_running + sec_class_idle) > req_max_glideins)))):
        # too many glideins, remove
        remove_nr = sec_class_idle - req_min_idle
        if (remove_excess_running and 
            ((req_max_glideins is not None) and  #make sure there is a max
             ((sec_class_running + sec_class_idle) > req_max_glideins))):
            remove_all_nr = (sec_class_running + sec_class_idle) - req_max_glideins
            if remove_all_nr > remove_nr:
                # if we are past max_run, then min_idle does not make sense to start with
                remove_nr = remove_all_nr
            
        idle_list = extractIdleUnsubmitted(condorQ)

        if remove_excess_wait and (len(idle_list) > 0):
            # remove unsubmitted first, if any
            if len(idle_list) > remove_nr:                
                idle_list = idle_list[:remove_nr] #shorten
            stat_str = "min_idle=%i, idle=%i, unsubmitted=%i" % (req_min_idle, sec_class_idle, len(idle_list))
            logfiles.logActivity("Too many glideins: %s" % stat_str)
            logfiles.logActivity("Removing %i unsubmitted idle glideins" % len(idle_list))
            if len(idle_list)>0:
                removeGlideins(condorQ.schedd_name, idle_list,
                               logfiles=logfiles,factoryConfig=factoryConfig)
                return 1 # stop here... the others will be retried in next round, if needed

        idle_list = extractIdleQueued(condorQ)
        if remove_excess_idle and (len(idle_list) > 0):
            # no unsubmitted, go for all the others now
            if len(idle_list) > remove_nr:                
                idle_list = idle_list[:remove_nr] #shorten
            stat_str = "min_idle=%i, idle=%i, unsubmitted=%i" % (req_min_idle, sec_class_idle, 0)
            logfiles.logActivity("Too many glideins: %s" % stat_str)
            logfiles.logActivity("Removing %i idle glideins" % len(idle_list))
            if len(idle_list)>0:
                removeGlideins(condorQ.schedd_name, idle_list,
                               logfiles=logfiles,factoryConfig=factoryConfig)
                return 1 # exit, even if no submitted

        if remove_excess_running:
            # no idle left, remove anything you can

            stat_str = "idle=%i, running=%i, max_running=%i" % (sec_class_idle, sec_class_running, req_max_glideins)
            logfiles.logActivity("Too many glideins: %s" % stat_str)

            run_list = extractRunSimple(condorQ)
            if len(run_list) > remove_nr:                
                run_list = run_list[:remove_nr] #shorten
            logfiles.logActivity("Removing %i running glideins" % len(run_list))

            rm_list = run_list

            #
            # Remove Held as well
            # No reason to keep them alive if we are about to kill running glideins anyhow
            #

            logfiles.logActivity("No glideins requested.")
            # Check if there are held glideins that are not recoverable
            unrecoverable_held_list = extractUnrecoverableHeldSimple(condorQ,factoryConfig=factoryConfig)
            if len(unrecoverable_held_list) > 0:
                logfiles.logActivity("Removing %i unrecoverable held glideins" % len(unrecoverable_held_list))
                rm_list += unrecoverable_held_list

            # Check if there are held glideins
            held_list = extractRecoverableHeldSimple(condorQ,
                                                     factoryConfig=factoryConfig)
            if len(held_list) > 0:
                logfiles.logActivity("Removing %i held glideins" % len(held_list))
                rm_list += held_list

            if len(rm_list)>0:
                removeGlideins(condorQ.schedd_name, rm_list, logfiles=logfiles,factoryConfig=factoryConfig)
                return 1 # exit, even if no submitted
    elif remove_excess_running and (req_max_glideins == 0) and (sec_class_held > 0):
        # no glideins desired, remove all held
        # (only held should be left at this point... idle and running addressed above)

        # Check if there are held glideins that are not recoverable
        unrecoverable_held_list = extractUnrecoverableHeldSimple(condorQ,factoryConfig=factoryConfig)
        if len(unrecoverable_held_list) > 0:
            logfiles.logActivity("Removing %i unrecoverable held glideins" % len(unrecoverable_held_list))

        # Check if there are held glideins
        held_list = extractRecoverableHeldSimple(condorQ,
                                                     factoryConfig=factoryConfig)
        if len(held_list) > 0:
            logfiles.logActivity("Removing %i held glideins" % len(held_list))

        if (len(unrecoverable_held_list)+len(held_list))>0:
            removeGlideins(condorQ.schedd_name,
                           unrecoverable_held_list + held_list,
                           logfiles=logfiles,factoryConfig=factoryConfig)
            return 1 # exit, even if no submitted
        
        
    return 0


#
# Sanitizing function
#   Can be used if we the glidein connect to a reachable Collector
#  This method is currently not used anywhere 
def sanitizeGlideins(condorq, status, logfiles=log_files,
                     factoryConfig=None):

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    # Check if some glideins have been in idle state for too long
    stale_list=extractStale(condorq,status,factoryConfig=factoryConfig)
    if len(stale_list)>0:
        logfiles.logWarning("Found %i stale glideins"%len(stale_list))
        removeGlideins(condorq.schedd_name, stale_list, logfiles=logfiles,factoryConfig=factoryConfig)

    # Check if some glideins have been in running state for too long
    runstale_list=extractRunStale(condorq)
    if len(runstale_list)>0:
        logfiles.logWarning("Found %i stale (>%ih) running glideins"%(len(runstale_list),factoryConfig.stale_maxage[2]/3600))
        removeGlideins(condorq.schedd_name, runstale_list, logfiles=logfiles,factoryConfig=factoryConfig)

    # Check if there are held glideins that are not recoverable
    unrecoverable_held_list=extractUnrecoverableHeld(condorq,status,factoryConfig=factoryConfig)
    if len(unrecoverable_held_list)>0:
        logfiles.logWarning("Found %i unrecoverable held glideins"%len(unrecoverable_held_list))
        removeGlideins(condorq.schedd_name, unrecoverable_held_list,
                       force=False, logfiles=logfiles,factoryConfig=factoryConfig)

    # Check if there are held glideins
    held_list=extractRecoverableHeld(condorq,status,factoryConfig=factoryConfig)
    if len(held_list)>0:
        limited_held_list=extractRecoverableHeldWithinLimits(condorq,status,factoryConfig=factoryConfig)
        logfiles.logWarning("Found %i held glideins, %i within limits"%(len(held_list),len(limited_held_list)))
        if len(limited_held_list)>0:
            releaseGlideins(condorq.schedd_name, limited_held_list,
                            logfiles=logfiles, factoryConfig=factoryConfig)

    # Now look for VMs that have not been claimed for a long time
    staleunclaimed_list=extractStaleUnclaimed(condorq,status,factoryConfig=factoryConfig)
    if len(staleunclaimed_list)>0:
        logfiles.logWarning("Found %i stale unclaimed glideins"%len(staleunclaimed_list))
        removeGlideins(condorq.schedd_name, staleunclaimed_list,
                       logfiles=logfiles,factoryConfig=factoryConfig)


    #
    # A check of glideins in "Running" state but not in status
    # should be implemented, too
    # However, it needs some sort of history to account for
    # temporary network outages
    #

    return

def sanitizeGlideinsSimple(condorq, logfiles=log_files, 
                          factoryConfig=None):

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    # Check if some glideins have been in idle state for too long
    stale_list=extractStaleSimple(condorq,factoryConfig=factoryConfig)
    if len(stale_list)>0:
        logfiles.logWarning("Found %i stale glideins"%len(stale_list))
        removeGlideins(condorq.schedd_name, stale_list, logfiles=logfiles,factoryConfig=factoryConfig)

    # Check if some glideins have been in running state for too long
    runstale_list=extractRunStale(condorq)
    if len(runstale_list)>0:
        logfiles.logWarning("Found %i stale (>%ih) running glideins"%(len(runstale_list),factoryConfig.stale_maxage[2]/3600))
        removeGlideins(condorq.schedd_name, runstale_list, logfiles=logfiles,factoryConfig=factoryConfig)

    # Check if there are held glideins that are not recoverable
    unrecoverable_held_list=extractUnrecoverableHeldSimple(condorq,factoryConfig=factoryConfig)
    if len(unrecoverable_held_list)>0:
        logfiles.logWarning("Found %i unrecoverable held glideins"%len(unrecoverable_held_list))
        removeGlideins(condorq.schedd_name, unrecoverable_held_list,
                       force=False, logfiles=logfiles)

    # Check if there are held glideins
    held_list=extractRecoverableHeldSimple(condorq,factoryConfig=factoryConfig)
    if len(held_list)>0:
        limited_held_list = extractRecoverableHeldSimpleWithinLimits(condorq,factoryConfig=factoryConfig)
        logfiles.logWarning("Found %i held glideins, %i within limits"%(len(held_list),len(limited_held_list)))
        if len(limited_held_list)>0:
            releaseGlideins(condorq.schedd_name, limited_held_list,
                            logfiles=logfiles, factoryConfig=factoryConfig)

    return

def logStats(condorq, condorstatus, client_int_name, client_security_name,
             proxy_security_class, logfiles=log_files,
             factoryConfig=None):

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    #
    # First check if we have enough glideins in the queue
    #

    # Count glideins by status
    qc_status=getQStatus(condorq)
    sum_idle_count(qc_status)
    if condorstatus is not None:
        s_running_str=" collector running %s"%len(condorstatus.fetchStored().keys())
    else:
        s_running_str="" # not monitored
    
    logfiles.logActivity("Client %s (secid: %s_%s) schedd status %s%s"%(client_int_name,client_security_name,proxy_security_class,qc_status,s_running_str))
    if factoryConfig.qc_stats is not None:
        client_log_name=secClass2Name(client_security_name,proxy_security_class)
        factoryConfig.client_stats.logSchedd(client_int_name,qc_status)
        factoryConfig.qc_stats.logSchedd(client_log_name,qc_status)
    
    return

def logWorkRequest(client_int_name, client_security_name,
                   proxy_security_class, req_idle, req_max_run,
                   work_el, fraction=1.0, logfiles=log_files,
                   factoryConfig=None):

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    # temporary workaround; the requests should always be processed at the caller level
    if work_el['requests'].has_key('RemoveExcess'):
        remove_excess=work_el['requests']['RemoveExcess']
    else:
        remove_excess='NO'

    client_log_name=secClass2Name(client_security_name,proxy_security_class)

    logfiles.logActivity("Client %s (secid: %s) requesting %i glideins, max running %i, remove excess '%s'"%(client_int_name,client_log_name,req_idle,req_max_run,remove_excess))
    logfiles.logActivity("  Params: %s"%work_el['params'])
    logfiles.logActivity("  Decrypted Param Names: %s"%work_el['params_decrypted'].keys()) # cannot log decrypted ones... they are most likely sensitive

    reqs={'IdleGlideins':req_idle,'MaxRunningGlideins':req_max_run}
    factoryConfig.client_stats.logRequest(client_int_name,reqs)
    factoryConfig.qc_stats.logRequest(client_log_name,reqs)

    factoryConfig.client_stats.logClientMonitor(client_int_name,work_el['monitor'],work_el['internals'],fraction)
    factoryConfig.qc_stats.logClientMonitor(client_log_name,work_el['monitor'],work_el['internals'],fraction)

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
            if grid_status in ("PENDING","INLRMS: Q","PREPARED","SUBMITTING","IDLE","SUSPENDED","REGISTERED","INLRMS:Q"):
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
            if grid_status in ("ACTIVE","REALLY-RUNNING","INLRMS: R","RUNNING","INLRMS:R"):
                return 2
            elif grid_status in ("STAGE_OUT","INLRMS: E","EXECUTED","FINISHING","DONE","INLRMS:E"):
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
def extractRegistered(q, status, search_list,
                      factoryConfig=None):
    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']
    sdata=status.fetchStored(lambda el:(el[factoryConfig.schedd_startd_attribute]==q.schedd_name) and (get_status_glideidx(el) in search_list))

    out_list=[]
    for vm in sdata.keys():
        el=sdata[vm]
        i=get_status_glideidx(el)
        if not (i in out_list): # prevent duplicates from multiple VMs
            out_list.append(i)

    return out_list


def extractStale(q,status,factoryConfig=None):
    # first find out the stale idle jids
    #  hash: (Idle==1, Stale==1)
    qstale=q.fetchStored(lambda el:(hash_statusStale(el)==[1,1]))
    qstale_list=qstale.keys()
    
    # find out if any "Idle" glidein is running instead (in condor_status)
    sstale_list=extractRegistered(q,status,qstale_list,factoryConfig=factoryConfig)

    return diffList(qstale_list,sstale_list)

def extractStaleSimple(q,factoryConfig=None):
    # first find out the stale idle jids
    #  hash: (Idle==1, Stale==1)
    qstale=q.fetchStored(lambda el:(hash_statusStale(el)==[1,1]))
    qstale_list=qstale.keys()
    
    return qstale_list

def extractUnrecoverableHeld(q,status,factoryConfig=None):
    # first find out the held jids that are not recoverable
    #  Held==5 and glideins are not recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el,factoryConfig=factoryConfig)))
    qheld_list=qheld.keys()
    
    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list=extractRegistered(q, status,qheld_list,
                                 factoryConfig=factoryConfig)
    return diffList(qheld_list,sheld_list)

def extractUnrecoverableHeldSimple(q,factoryConfig=None):
    #  Held==5 and glideins are not recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el,factoryConfig=factoryConfig)))
    qheld_list=qheld.keys()
    return qheld_list

def extractRecoverableHeld(q,status,factoryConfig=None):
    # first find out the held jids
    #  Held==5 and glideins are recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el,factoryConfig=factoryConfig)))
    qheld_list=qheld.keys()
    
    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list=extractRegistered(q,status,qheld_list,factoryConfig=factoryConfig)

    return diffList(qheld_list,sheld_list)

def extractRecoverableHeldWithinLimits(q,status,factoryConfig=None):
    # first find out the held jids
    #  Held==5 and glideins are recoverable
    qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el,factoryConfig=factoryConfig) and isGlideinWithinHeldLimits(el,factoryConfig=factoryConfig)))
    qheld_list=qheld.keys()
    
    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list=extractRegistered(q,status,qheld_list,factoryConfig=factoryConfig)

    return diffList(qheld_list,sheld_list)

def extractRecoverableHeldSimple(q,factoryConfig=None):
    #  Held==5 and glideins are recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el,factoryConfig=factoryConfig)))
    qheld_list=qheld.keys()
    return qheld_list

def extractRecoverableHeldSimpleWithinLimits(q,factoryConfig=None):
    #  Held==5 and glideins are recoverable
    qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el,factoryConfig=factoryConfig) and isGlideinWithinHeldLimits(el,factoryConfig=factoryConfig)))
    qheld_list=qheld.keys()
    return qheld_list

def extractHeld(q,status,factoryConfig=None):

    # first find out the held jids
    #  Held==5
    qheld=q.fetchStored(lambda el:el["JobStatus"]==5)
    qheld_list=qheld.keys()
    
    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list=extractRegistered(q,status,qheld_list,factoryConfig=factoryConfig)

    return diffList(qheld_list,sheld_list)

def extractHeldSimple(q):
    #  Held==5
    qheld=q.fetchStored(lambda el:el["JobStatus"]==5)
    qheld_list=qheld.keys()
    return qheld_list

def extractIdleSimple(q):
    #  Idle==1
    qidle=q.fetchStored(lambda el:el["JobStatus"]==1)
    qidle_list=qidle.keys()
    return qidle_list

def extractIdleUnsubmitted(q):
    #  1001 == Unsubmitted
    qidle=q.fetchStored(lambda el:hash_status(el)==1001)
    qidle_list=qidle.keys()
    return qidle_list

def extractIdleQueued(q):
    #  All 1xxx but 1001
    qidle=q.fetchStored(lambda el:(hash_status(el) in (1002,1010,1100)))
    qidle_list=qidle.keys()
    return qidle_list

def extractNonRunSimple(q):
    #  Run==2
    qnrun=q.fetchStored(lambda el:el["JobStatus"]!=2)
    qnrun_list=qnrun.keys()
    return qnrun_list

def extractRunSimple(q):
    #  Run==2
    qrun=q.fetchStored(lambda el:el["JobStatus"]==2)
    qrun_list=qrun.keys()
    return qrun_list

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

def extractStaleUnclaimed(q,status,factoryConfig=None):
    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    # first find out the active running jids
    #  hash: (Running==2, Stale==0)
    qsearch=q.fetchStored(lambda el:(hash_statusStale(el)==[2,0]))
    search_list=qsearch.keys()
    
    # find out if any "Idle" glidein is running instead (in condor_status)
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
    if schedd_name is None:
        return ""
    else:
        return "-name %s"%schedd_name

extractJobId_recmp = re.compile("^(?P<count>[0-9]+) job\(s\) submitted to cluster (?P<cluster>[0-9]+)\.$")
def extractJobId(submit_out):
    for line in submit_out:
        found = extractJobId_recmp.search(line.strip())
        if found is not None:
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
def submitGlideins(entry_name, schedd_name, username, client_name,
                   nr_glideins, frontend_name, x509_proxy_identifier,
                   x509_proxy_security_class, x509_proxy_fname,
                   client_web, params, logfiles=log_files,
                   factoryConfig=None):
    """
    client_web =  None means client did not pass one, backwards compatibility
    """

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    submitted_jids=[]

    if nr_glideins>factoryConfig.max_submits:
        nr_glideins=factoryConfig.max_submits

    params_arr=[]
    for k in params.keys():
        params_arr.append(k)
        params_arr.append(escapeParam(str(params[k])))
    params_str=string.join(params_arr," ")

    client_web_arr=[]
    if client_web is not None:
        client_web_arr=client_web.get_glidein_args()
    client_web_str=string.join(client_web_arr," ")

    # Allows for retrieving any entry description values
    jobDescript=glideFactoryConfig.JobDescript(entry_name)

    
    try:
        nr_submitted=0
        while (nr_submitted<nr_glideins):
            if nr_submitted!=0:
                time.sleep(factoryConfig.submit_sleep)

            nr_to_submit=(nr_glideins-nr_submitted)
            if nr_to_submit>factoryConfig.max_cluster_size:
                nr_to_submit=factoryConfig.max_cluster_size
                
            glidein_rsl = "none"
            if jobDescript.data.has_key('GlobusRSL'):   
                glidein_rsl = jobDescript.data['GlobusRSL']
                # Replace placeholder for project id 
                if params.has_key('ProjectId') and 'TG_PROJECT_ID' in glidein_rsl:
                    glidein_rsl = glidein_rsl.replace('TG_PROJECT_ID', params['ProjectId'])                
            
            if username!=MY_USERNAME:
                # use privsep
                exe_env=['X509_USER_PROXY=%s'%x509_proxy_fname]
                # need to push all the relevant env variables through
                for var in os.environ.keys():
                    if ((var in ('PATH','LD_LIBRARY_PATH','X509_CERT_DIR')) or
                        (var[:8]=='_CONDOR_') or (var[:7]=='CONDOR_')):
                        if os.environ.has_key(var):
                            exe_env.append('%s=%s'%(var,os.environ[var]))
                
                exe_env.append('GLIDEIN_FRONTEND_NAME=%s' % frontend_name)
                try:
                    #submit_out=condorPrivsep.execute(username,factoryConfig.submit_dir,
                    #                                 os.path.join(factoryConfig.submit_dir,factoryConfig.submit_fname),
                    #                                 [factoryConfig.submit_fname,entry_name,client_name,x509_proxy_security_class,x509_proxy_identifier,"%i"%nr_to_submit,glidein_rsl,]+
                    #                                 client_web_arr+submit_attrs+
                    #                                 ['--']+params_arr,
                    #                                 exe_env)
                    submit_out=condorPrivsep.execute(username,factoryConfig.submit_dir,
                                                     os.path.join(factoryConfig.submit_dir,factoryConfig.submit_fname),
                                                     [factoryConfig.submit_fname,entry_name,client_name,x509_proxy_security_class,x509_proxy_identifier,"%i"%nr_to_submit,glidein_rsl,]+
                                                     client_web_arr+
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
                    child_env = {
                        'X509_USER_PROXY': x509_proxy_fname,
                        'GLIDEIN_FRONTEND_NAME': frontend_name
                    }
                    submit_out=condorExe.iexe_cmd('./%s "%s" "%s" "%s" "%s" %i "%s" %s -- %s'%(factoryConfig.submit_fname,entry_name,client_name,x509_proxy_security_class,x509_proxy_identifier,nr_to_submit,glidein_rsl,client_web_str,params_str), child_env=child_env)
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
        logfiles.logActivity("Submitted %i glideins to %s: %s"%(len(submitted_jids),schedd_name,submitted_jids))

# remove the glideins in the list
def removeGlideins(schedd_name, jid_list, force=False,
                   logfiles=log_files,
                   factoryConfig=None):
    ####
    # We are assuming the gfactory to be
    # a condor superuser and thus does not need
    # identity switching to remove jobs
    ####

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    removed_jids=[]
    
    schedd_str=schedd_name2str(schedd_name)
    is_not_first=0

    for jid in jid_list:

        # Respect the max_removes limit and exit right away if required
        if len(removed_jids)>=factoryConfig.max_removes:
            break # limit reached, stop

        if is_not_first:
            is_not_first=1
            time.sleep(factoryConfig.remove_sleep)

        try:
            condorManager.condorRemoveOne("%li.%li"%(jid[0],jid[1]),schedd_name)
            removed_jids.append(jid)

            # Force the removal if requested
            if force == True:
                try:
                    logfiles.logActivity("Forcing the removal of glideins in X state")
                    condorManager.condorRemoveOne("%li.%li"%(jid[0],jid[1]),schedd_name,do_forcex=True)
                except condorExe.ExeError, e:
                    logfiles.logWarning("Forcing the removal of glideins in %s.%s state failed" % (jid[0],jid[1]))

        except condorExe.ExeError, e:
            # silently ignore errors, and try next one
            logfiles.logWarning("removeGlidein(%s,%li.%li): %s"%(schedd_name,jid[0],jid[1],e))


    logfiles.logActivity("Removed %i glideins on %s: %s"%(len(removed_jids),schedd_name,removed_jids))

# release the glideins in the list
def releaseGlideins(schedd_name, jid_list, logfiles=log_files,
                    factoryConfig=None):
    ####
    # We are assuming the gfactory to be
    # a condor superuser and thus does not need
    # identity switching to release jobs
    ####

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    released_jids=[]
    
    schedd_str=schedd_name2str(schedd_name)
    is_not_first=0
    for jid in jid_list:
        if is_not_first:
            is_not_first=1
            time.sleep(factoryConfig.release_sleep)
        try:
            condorManager.condorReleaseOne("%li.%li"%(jid[0],jid[1]),schedd_name)
            released_jids.append(jid)
        except condorExe.ExeError, e:
            logfiles.logWarning("releaseGlidein(%s,%li.%li): %s"%(schedd_name,jid[0],jid[1],e))

        if len(released_jids)>=factoryConfig.max_releases:
            break # limit reached, stop
    logfiles.logActivity("Released %i glideins on %s: %s"%(len(released_jids),schedd_name,released_jids))


def isGlideinWithinHeldLimits(jobInfo, factoryConfig=None):
    """
    This function looks at the glidein job's information and returns if the
    CondorG job can be released.

    This is useful to limit how often held jobs are released.

    @type jobInfo: dictionary
    @param jobInfo: Dictionary containing glidein job's classad information

    @rtype: bool
    @return: True if job is within limits, False if it is not
    """

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    # some basic sanity checks to start
    if not jobInfo.has_key('JobStatus'):
        return True
    if jobInfo['JobStatus']!=5:
        return True

    # assume within limits, unless released recently or has been released too often
    within_limits=True

    num_holds=1
    if jobInfo.has_key('NumSystemHolds'):
        num_holds=jobInfo['NumSystemHolds']
        
    if num_holds>factoryConfig.max_release_count:
        within_limits=False

    if jobInfo.has_key('ServerTime') and jobInfo.has_key('EnteredCurrentStatus'):
        held_period=jobInfo['ServerTime']-jobInfo['EnteredCurrentStatus']
        if held_period<(num_holds*factoryConfig.min_release_time): # slower for repeat offenders
            within_limits=False

    return within_limits

# Get list of CondorG job status for held jobs that are not recoverable
def isGlideinUnrecoverable(jobInfo, factoryConfig=None):
    """
    This function looks at the glidein job's information and returns if the
    CondorG job is unrecoverable.

    This is useful to change to status of glidein (CondorG job) from hold to
    idle.

    @type jobInfo: dictionary
    @param jobInfo: Dictionary containing glidein job's classad information

    @rtype: bool
    @return: True if job is unrecoverable, False if recoverable
    """

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
    # 121 : the job state file doesn't exist 
    # 122 : could not read the job state file

    if factoryConfig is None:
        factoryConfig = globals()['factoryConfig']

    unrecoverable = False
    # Dictionary of {HeldReasonCode: HeldReasonSubCode}
    unrecoverableCodes = {2: [ 0, 2, 4, 5, 7, 8, 9, 10, 14, 17, 
                               22, 27, 28, 31, 37, 47, 48, 
                               72, 76, 81, 86, 87,
                               121, 122 ]}

    if jobInfo.has_key('HoldReasonCode') and jobInfo.has_key('HoldReasonSubCode'):
        code = jobInfo['HoldReasonCode']
        subCode = jobInfo['HoldReasonSubCode']
        if (unrecoverableCodes.has_key(code) and (subCode in unrecoverableCodes[code])):
            unrecoverable = True

    num_holds=1
    if jobInfo.has_key('JobStatus') and jobInfo.has_key('NumSystemHolds'):
        if jobInfo['JobStatus']==5:
            num_holds=jobInfo['NumSystemHolds']

    if num_holds>factoryConfig.max_release_count:
        unrecoverable = True

    return unrecoverable

class GlideinTotals:
    """
    Keeps track of all glidein totals.  
    """
    def __init__(self, entry_name, frontendDescript,
                 jobDescript, entry_condorQ, logfiles=log_files):
                
        # Initialize entry limits
        self.entry_name = entry_name
        self.entry_max_glideins = int(jobDescript.data['MaxRunning'])
        self.entry_max_held = int(jobDescript.data['MaxHeld'])
        self.entry_max_idle = int(jobDescript.data['MaxIdle'])       

        # Initialize default frontend-sec class limits
        self.default_fesc_max_glideins = int(jobDescript.data['DefaultFESCMaxRunning'])
        self.default_fesc_max_held = int(jobDescript.data['DefaultFESCMaxHeld'])
        self.default_fesc_max_idle = int(jobDescript.data['DefaultFESCMaxIdle'])      
        self.logFiles = logfiles
     
        # Count glideins by status
        # Initialized since the held and running won't ever change
        # To simplify idle requests, this variable is updated at the same time the frontend count is updated
        qc_status = getQStatus(entry_condorQ)        
        self.entry_running = 0
        self.entry_held = 0
        self.entry_idle = 0
        if qc_status.has_key(2):  # Running==Jobstatus(2)
            self.entry_running = qc_status[2]
        if qc_status.has_key(5):  # Held==JobStatus(5)
            self.entry_held = qc_status[5]
        sum_idle_count(qc_status)
        if qc_status.has_key(1):  # Idle==Jobstatus(1)
            self.entry_idle = qc_status[1]
                
        all_frontends = frontendDescript.get_all_frontend_sec_classes()
        
        # Initialize frontend security class limits
        self.frontend_limits = {}
        for fe_sec_class in all_frontends:
            self.frontend_limits[fe_sec_class] = {'max_glideins':self.default_fesc_max_glideins, 
                                                  'max_held':self.default_fesc_max_held, 
                                                  'max_idle':self.default_fesc_max_idle} 

        # Get factory parameters for frontend-specific limits
        # Format: frontend1:sec_class1;number,frontend2:sec_class2;number

        limits_keynames = ( ('MaxRunningFrontends', 'max_glideins'),
                            ('MaxIdleFrontends', 'max_idle'),
                            ('MaxHeldFrontends', 'max_held') )

        for (jd_key, max_glideinstatus_key) in limits_keynames:
            fe_glideins_param = jobDescript.data[jd_key]

            if (fe_glideins_param.find(";") != -1):
                for el in fe_glideins_param.split(","):
                    el_list = el.split(";")
                    try:
                        self.frontend_limits[el_list[0]][max_glideinstatus_key] = int(el_list[1])
                    except:
                        self.logFiles.logWarning("Invalid FrontendName:SecurityClassName combo '%s' encountered while finding '%s' from max_job_frontend" % (el_list[0], max_glideinstatus_key))

        # Initialize frontend totals
        for fe_sec_class in self.frontend_limits:            
            # Filter the queue for all glideins for this frontend:security_class (GLIDEIN_FRONTEND_NAME)
            fe_condorQ = condorMonitor.SubQuery(entry_condorQ, lambda d:(d[factoryConfig.frontend_name_attribute] == fe_sec_class))
            fe_condorQ.schedd_name = entry_condorQ.schedd_name
            fe_condorQ.factory_name = entry_condorQ.factory_name
            fe_condorQ.glidein_name = entry_condorQ.glidein_name
            fe_condorQ.entry_name = entry_condorQ.entry_name
            fe_condorQ.load()

            # Count glideins by status       
            fe_running = 0
            fe_held = 0
            fe_idle = 0
            qc_status = getQStatus(fe_condorQ) 
            if qc_status.has_key(2):  # Running==Jobstatus(2)
                fe_running = qc_status[2]
            if qc_status.has_key(5):  # Held==JobStatus(5)
                fe_held = qc_status[5]
            sum_idle_count(qc_status)
            if qc_status.has_key(1):  # Idle==Jobstatus(1)
                fe_idle = qc_status[1]
            
            self.frontend_limits[fe_sec_class]['running'] = fe_running
            self.frontend_limits[fe_sec_class]['held'] = fe_held
            self.frontend_limits[fe_sec_class]['idle'] = fe_idle
            
                    
    def can_add_idle_glideins(self, nr_glideins, frontend_name):
        """
        Determines how many more glideins can be added.  Does not compare against request max_glideins.  Does not update totals.
        """
        nr_allowed = nr_glideins
        
        # Check entry idle limit
        if self.entry_idle + nr_allowed > self.entry_max_idle:
            # adjust to under the limit
            nr_allowed = self.entry_max_idle - self.entry_idle
        
        # Check entry total glideins 
        if self.entry_idle + nr_allowed + self.entry_running + self.entry_held > self.entry_max_glideins:
            nr_allowed = self.entry_max_glideins - self.entry_idle - self.entry_running 
        
        fe_limit = self.frontend_limits[frontend_name]
        
        # Check frontend:sec_class idle limit
        if fe_limit['idle'] + nr_allowed > fe_limit['max_idle']:
            nr_allowed = fe_limit['max_idle'] - fe_limit['idle']   
        
        # Check frontend:sec_class total glideins
        if fe_limit['idle'] + fe_limit['held'] + nr_allowed + fe_limit['running'] > fe_limit['max_glideins']:
            nr_allowed = fe_limit['max_glideins'] - fe_limit['idle'] - fe_limit['held'] - fe_limit['running']
        
        # Return
        return nr_allowed  
    
    def add_idle_glideins(self, nr_glideins, frontend_name):
        """
        Updates the totals with the additional glideins.
        """
        self.entry_idle += nr_glideins
        self.frontend_limits[frontend_name]['idle'] += nr_glideins

    def get_max_held(self, frontend_name):
        """
        Returns max held for the given frontend:sec_class.
        """
        return self.frontend_limits[frontend_name]['max_held']

    def has_sec_class_exceeded_max_held(self, frontend_name):
        """
        Compares the current held for a security class to the security class limit.
        """
        return self.frontend_limits[frontend_name]['held'] >= self.frontend_limits[frontend_name]['max_held']
    
    def has_entry_exceeded_max_held(self):
        return self.entry_held >= self.entry_max_held

    def has_entry_exceeded_max_idle(self):
        return self.entry_idle >= self.entry_max_idle
    
    def has_entry_exceeded_max_glideins(self):
        # max_glideins=total glidens for an entry.  Total is defined as idle+running+held
        return self.entry_idle + self.entry_running + self.entry_held >= self.entry_max_glideins
        

    def __str__(self):  
        """
        for testing purposes 
        """  
        output = ""
        output += "GlideinTotals ENTRY NAME = %s\n" % self.entry_name
        output += "GlideinTotals ENTRY VALUES\n"
        output += "     idle=%s\n" % self.entry_idle
        output += "     held=%s\n" % self.entry_held
        output += "     running=%s\n" % self.entry_running
        output += "GlideinTotals ENTRY MAX VALUES\n"
        output += "     max_idle=%s\n" % self.entry_max_idle 
        output += "     max_held=%s\n" % self.entry_max_held   
        output += "     max_glideins=%s\n" % self.entry_max_glideins 
        output += "GlideinTotals DEFAULT FE-SC MAX VALUES\n"
        output += "     default frontend-sec class max_idle=%s\n" % self.default_fesc_max_idle
        output += "     default frontend-sec class max_held=%s\n" % self.default_fesc_max_held
        output += "     default frontend-sec class max_glideins=%s\n" % self.default_fesc_max_glideins      
          
        for frontend in self.frontend_limits.keys():
            fe_limit = self.frontend_limits[frontend]
            output += "GlideinTotals FRONTEND NAME = %s\n" % frontend
            output += "     idle = %s\n" % fe_limit['idle']
            output += "     max_idle = %s\n" % fe_limit['max_idle']
            output += "     held = %s\n" % fe_limit['held']
            output += "     max_held = %s\n" % fe_limit['max_held']
            output += "     running = %s\n" % fe_limit['running']
            output += "     max_glideins = %s\n" % fe_limit['max_glideins']
                    
        return output
        

def set_condor_integrity_checks():
    os.environ['_CONDOR_SEC_DEFAULT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_CLIENT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_READ_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_WRITE_INTEGRITY'] = 'REQUIRED'


#######################################################

def which(program):
    """
    Implementation of which command in python.

    @return: Path to the binary
    @rtype: string
    """
    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None
