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
import time
import string
import re
import condorExe
import condorMonitor


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

        self.factory_startd_attribute = "GLIDEIN_Factory"
        self.glidein_startd_attribute = "GLIDEIN_Name"
        self.entry_startd_attribute = "GLIDEIN_Entry_Name"
        self.client_startd_attribute = "GLIDEIN_Client"
        self.schedd_startd_attribute = "GLIDEIN_Schedd"
        self.clusterid_startd_attribute = "GLIDEIN_ClusterId"
        self.procid_startd_attribute = "GLIDEIN_ProcId"

        self.count_env = 'GLIDEIN_COUNT'


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

        # submit file name
        self.submit_file = "job.condor"

        # log files
        # default is None, any other value must implement the write(str) method
        self.activity_log = None
        self.warning_log = None

        # monitoring objects
        # create them for the logging to occur
        self.client_internals = None
        self.qc_stats = None
        self.log_stats = None

    def config_submit_freq(self,sleepBetweenSubmits,maxSubmitsXCycle):
        self.submit_sleep=sleepBetweenSubmits
        self.max_submits=maxSubmitsXCycle

    def config_remove_freq(self,sleepBetweenRemoves,maxRemovesXCycle):
        self.remove_sleep=sleepBetweenRemoves
        self.max_removes=maxRemovesXCycle

    #
    # The following are used by the module
    #

    def logActivity(self,str):
        if self.activity_log!=None:
            try:
                self.activity_log.write(str+"\n")
            except:
                # logging must never throw an exception!
                self.logWarning("logActivity failed, was logging: %s"+str,False)

    def logWarning(self,str, log_in_activity=True):
        if self.warning_log!=None:
            try:
                self.warning_log.write(str+"\n")
            except:
                # logging must throw an exception!
                # silently ignore
                pass
        if log_in_activity:
            self.logActivity("WARNING: %s"%str)


# global configuration of the module
factoryConfig=FactoryConfig()


############################################################
#
# User functions
#
############################################################

#
# Get Condor data, given the glidein name
# To be passed to the main functions
#

def getCondorQData(factory_name,glidein_name,entry_name,client_name,schedd_name,
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

    q_glidein_constraint='(%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s")'%(fsa_str,factory_name,gsa_str,glidein_name,esa_str,entry_name,csa_str,client_name)
    q=condorMonitor.CondorQ(schedd_name)
    q.factory_name=factory_name
    q.glidein_name=glidein_name
    q.entry_name=entry_name
    q.client_name=client_name
    q.load(q_glidein_constraint)
    return q

def getCondorStatusData(factory_name,glidein_name,entry_name,client_name,pool_name=None,
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

    status_glidein_constraint='(%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s")'%(fsa_str,factory_name,gsa_str,glidein_name,esa_str,entry_name,csa_str,client_name)
    status=condorMonitor.CondorStatus(pool_name=pool_name)
    status.factory_name=factory_name
    status.glidein_name=glidein_name
    status.entry_name=entry_name
    status.client_name=client_name
    status.load(status_glidein_constraint)
    return status


#
# Create/update the proxy file
# returns the proxy fname
def update_x509_proxy_file(client_id, proxy_data):
    fname=os.path.realpath('client_proxies/x509_%s.proxy'%escapeParam(client_id))

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
    
#
# Main function
#   Will keep the required number of Idle glideins
#

# Returns number of newely submitted glideins
# Can throw a condorExe.ExeError exception
def keepIdleGlideins(condorq,min_nr_idle,max_nr_running,max_held,submit_attrs,x509_proxy_fname,params):
    global factoryConfig
    #
    # First check if we have enough glideins in the queue
    #

    # Count glideins by status
    qc_status=condorMonitor.Summarize(condorq,hash_status).countStored()

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
        factoryConfig.logActivity("Need more glideins: %s"%stat_str)
        submitGlideins(condorq.entry_name,condorq.schedd_name,condorq.client_name,min_nr_idle-idle_glideins,submit_attrs,x509_proxy_fname,params)
        return min_nr_idle-idle_glideins # exit, some submitted

    # We have enough glideins in the queue
    # Now check we don't have problems

    # Check if we have stale idle glideins
    qc_stale=condorMonitor.Summarize(condorq,hash_statusStale).countStored()

    # Check if there are stuck running glideins
    #   Running==Jobstatus(2), Stale==1
    if qc_stale.has_key(2) and qc_stale[2].has_key(1):
        runstale_glideins=qc_stale[2][1]
    else:
        runstale_glideins=0
    if runstale_glideins>0:
        # remove the held glideins
        runstale_list=extractRunStale(condorq)
        factoryConfig.logWarning("Found %i stale (>%ih) running glideins"%(len(runstale_list),factoryConfig.stale_maxage[2]/3600))
        removeGlideins(condorq.schedd_name,runstale_list)

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
        factoryConfig.logWarning("Found %i stale glideins"%len(stale_list))
        removeGlideins(condorq.schedd_name,stale_list)

    # Check if there are held glideins
    held_list=extractHeld(condorq,status)
    if len(held_list)>0:
        factoryConfig.logWarning("Found %i held glideins"%len(held_list))
        removeGlideins(condorq.schedd_name,held_list)

    # Now look for VMs that have not been claimed for a long time
    staleunclaimed_list=extractStaleUnclaimed(condorq,status)
    if len(staleunclaimed_list)>0:
        factoryConfig.logWarning("Found %i stale unclaimed glideins"%len(staleunclaimed_list))
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
        factoryConfig.logWarning("Found %i stale glideins"%len(stale_list))
        removeGlideins(condorq.schedd_name,stale_list)

    # Check if there are held glideins
    held_list=extractHeldSimple(condorq)
    if len(held_list)>0:
        factoryConfig.logWarning("Found %i held glideins"%len(held_list))
        releaseGlideins(condorq.schedd_name,held_list)

    return

def logStats(condorq,condorstatus,client_int_name):
    global factoryConfig
    #
    # First check if we have enough glideins in the queue
    #

    # Count glideins by status
    qc_status=condorMonitor.Summarize(condorq,hash_status).countStored()
    sum_idle_count(qc_status)
    if condorstatus!=None:
        s_running=len(condorstatus.fetchStored().keys())
    else:
        s_running="?" # temporary glitch
    
    factoryConfig.logActivity("Client '%s', schedd status %s, collector running %s"%(client_int_name,qc_status,s_running))
    if factoryConfig.qc_stats!=None:
        factoryConfig.qc_stats.logSchedd(client_int_name,qc_status)
    
    return

def logWorkRequests(work):
    for work_key in work.keys():
        if work[work_key]['requests'].has_key('IdleGlideins'):
            factoryConfig.logActivity("Client '%s', requesting %i glideins"%(work[work_key]['internals']["ClientName"],work[work_key]['requests']['IdleGlideins']))
            factoryConfig.logActivity("  Params: %s"%work[work_key]['params'])
            factoryConfig.logActivity("  Decrypted Param Names: %s"%work[work_key]['params_decrypted'].keys()) # cannot log decrypted ones... they are most likely sensitive
            factoryConfig.qc_stats.logRequest(work[work_key]['internals']["ClientName"],work[work_key]['requests'],work[work_key]['params'])
            factoryConfig.qc_stats.logClientMonitor(work[work_key]['internals']["ClientName"],work[work_key]['monitor'],work[work_key]['internals'])


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
#   1100 : Other
# All others just return the JobStatus
def hash_status(el):
    job_status=el["JobStatus"]
    if job_status==1:
        # idle jobs, look of GridJobStatus
        if el.has_key("GridJobStatus"):
            grid_status=el["GridJobStatus"]
            if grid_status=="PENDING":
                return 1002
            else:
                return 1100
        else:
            return 1001
    elif job_status==2:
        # count only real running, all others become Other
        if el.has_key("GridJobStatus"):
            grid_status=el["GridJobStatus"]
            if grid_status=="ACTIVE":
                return 2
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
        if (k>=1000) and (k<2000):
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

def extractHeld(q,status):
    # first find out the stale idle jids
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
def submitGlideins(entry_name,schedd_name,client_name,nr_glideins,submit_attrs,x509_proxy_fname,params):
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

    try:
        nr_submitted=0
        while (nr_submitted<nr_glideins):
            if nr_submitted!=0:
                time.sleep(factoryConfig.submit_sleep)

            nr_to_submit=(nr_glideins-nr_submitted)
            if nr_to_submit>factoryConfig.max_cluster_size:
                nr_to_submit=factoryConfig.max_cluster_size

            try:
                submit_out=condorExe.iexe_cmd('export X509_USER_PROXY=%s;./job_submit.sh "%s" "%s" %i %s -- %s'%(x509_proxy_fname,entry_name,client_name,nr_to_submit,submit_attrs_str,params_str))
            except condorExe.ExeError,e:
                factoryConfig.logWarning("condor_submit failed: %s"%e);
                submit_out=[]
                
            cluster,count=extractJobId(submit_out)
            for j in range(count):
                submitted_jids.append((cluster,j))
            nr_submitted+=count
    finally:
        # write out no matter what
        factoryConfig.logActivity("Submitted %i glideins to %s: %s"%(len(submitted_jids),schedd_name,submitted_jids))

# remove the glideins in the list
def removeGlideins(schedd_name,jid_list):
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
        except condorExe.ExeError, e:
            factoryConfig.logWarning("removeGlidein(%s,%li.%li): %s"%(schedd_name,jid[0],jid[1],e))
            pass # silently ignore errors, and try next one

        if len(removed_jids)>=factoryConfig.max_removes:
            break # limit reached, stop
    factoryConfig.logActivity("Removed %i glideins on %s: %s"%(len(removed_jids),schedd_name,removed_jids))

# release the glideins in the list
def releaseGlideins(schedd_name,jid_list):
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
            factoryConfig.logWarning("releaseGlidein(%s,%li.%li): %s"%(schedd_name,jid[0],jid[1],e))
            pass # silently ignore errors, and try next one

        if len(released_jids)>=factoryConfig.max_releases:
            break # limit reached, stop
    factoryConfig.logActivity("Released %i glideins on %s: %s"%(len(released_jids),schedd_name,released_jids))


###########################################################
#
# CVS info
#
# $Id: glideFactoryLib.py,v 1.36.2.1 2009/03/05 16:10:19 sfiligoi Exp $
#
# Log:
#  $Log: glideFactoryLib.py,v $
#  Revision 1.36.2.1  2009/03/05 16:10:19  sfiligoi
#  Look at GridJobStatus also for jobs in Running JobStatus
#
#  Revision 1.36  2008/09/16 16:25:47  sfiligoi
#  Fix typo
#
#  Revision 1.35  2008/09/16 16:22:09  sfiligoi
#  Fix typo
#
#  Revision 1.34  2008/09/16 15:39:24  sfiligoi
#  Use x509 received from frontend
#
#  Revision 1.33  2008/09/09 20:22:27  sfiligoi
#  Fix typo
#
#  Revision 1.32  2008/09/05 20:54:50  sfiligoi
#  Merge in 1.31.2.2
#
#  Revision 1.31.2.2  2008/09/05 20:22:26  sfiligoi
#  Warning now writes both in err and info
#
#  Revision 1.31.2.1  2008/09/05 20:19:50  sfiligoi
#  Protect from condor_submit failures
#
#  Revision 1.31  2008/08/12 21:16:49  sfiligoi
#  Fix typo
#
#  Revision 1.30  2008/08/05 19:53:14  sfiligoi
#  Add support for entry max_jobs, max_idle and max_held
#
#  Revision 1.29  2008/07/29 18:53:24  sfiligoi
#  Verbosity in not passed as an argument anymore
#
#  Revision 1.28  2008/06/23 19:33:28  sfiligoi
#  Protect from too many held jobs (1000)
#
#  Revision 1.27  2008/05/11 19:44:19  sfiligoi
#  Add wait and pending
#
#  Revision 1.26  2008/05/11 17:14:57  sfiligoi
#  Add client monitor info to the web page
#
#  Revision 1.25  2008/03/28 17:41:45  sfiligoi
#  Make condor_status non essential
#
#  Revision 1.24  2007/12/17 21:28:49  sfiligoi
#  Change verbosity to std; with the new glidein_submit this makes more sense
#
#  Revision 1.23  2007/12/17 16:30:06  sfiligoi
#  Automatically extract the schedd name. Must be always the same, so it makes no sense to pass it as a parameter.
#
#  Revision 1.22  2007/10/09 16:15:42  sfiligoi
#  Use short client name
#
#  Revision 1.21  2007/07/03 19:46:18  sfiligoi
#  Add support for MaxRunningGlideins
#
#  Revision 1.20  2007/05/18 19:10:57  sfiligoi
#  Add CVS tags
#
#
###########################################################
