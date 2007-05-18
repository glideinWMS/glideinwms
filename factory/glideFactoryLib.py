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
        self.stale_maxage={ 1:6*3600,         # 6 hours for idle
                            2:31*24*3600,     # 1 month for running
                           -1:2*3600}         # 2 hours for unclaimed (using special value -1 for this)

        # Sleep times between commands
        self.submit_sleep = 1.0
        self.remove_sleep = 1.0

        # Max commands per cycle
        self.max_submits = 100
        self.max_cluster_size=10
        self.max_removes = 5

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
                self.logWarning("logActivity failed, was logging: %s"+str)

    def logWarning(self,str):
        if self.warning_log!=None:
            try:
                self.warning_log.write(str+"\n")
            except:
                # logging must throw an exception!
                # silently ignore
                pass 


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
# Main function
#   Will keep the required number of Idle glideins
#

# Returns number of newely submitted glideins
# Can throw a condorExe.ExeError exception
def keepIdleGlideins(condorq,min_nr_idle,submit_attrs,params):
    global factoryConfig
    #
    # First check if we have enough glideins in the queue
    #

    # Count glideins by status
    qc_status=condorMonitor.Summarize(condorq,hash_status).countStored()
    #   Idle==Jobstatus(1)
    if qc_status.has_key(1):
        idle_glideins=qc_status[1]
    else:
        idle_glideins=0
    if idle_glideins<min_nr_idle:
        factoryConfig.logActivity("Need more glideins: min=%i, idle=%i"%(min_nr_idle,idle_glideins))
        submitGlideins(condorq.entry_name,condorq.schedd_name,condorq.client_name,min_nr_idle-idle_glideins,submit_attrs,params)
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

def logStats(condorq,condorstatus):
    global factoryConfig
    #
    # First check if we have enough glideins in the queue
    #

    # Count glideins by status
    qc_status=condorMonitor.Summarize(condorq,hash_status).countStored()
    s_running=len(condorstatus.fetchStored().keys())
    factoryConfig.logActivity("Client '%s', schedd status %s, collector running %i"%(condorq.client_name,qc_status,s_running))
    if factoryConfig.qc_stats!=None:
        factoryConfig.qc_stats.logSchedd(condorq.client_name,qc_status)
    
    return

def logWorkRequests(work):
    for work_key in work.keys():
        if work[work_key]['requests'].has_key('IdleGlideins'):
            factoryConfig.logActivity("Client '%s', requesting %i glideins"%(work_key,work[work_key]['requests']['IdleGlideins']))
            factoryConfig.logActivity("  Params: %s"%work[work_key]['params'])
            factoryConfig.qc_stats.logRequest(work_key,work[work_key]['requests'],work[work_key]['params'])


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

def hash_status(el):
    return el["JobStatus"]

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

def extractHeld(q,status):
    # first find out the stale idle jids
    #  Held==5
    qheld=q.fetchStored(lambda el:el["JobStatus"]==5)
    qheld_list=qheld.keys()
    
    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list=extractRegistered(q,status,qheld_list)

    return diffList(qheld_list,sheld_list)

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
def submitGlideins(entry_name,schedd_name,client_name,nr_glideins,submit_attrs,params):
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

            submit_out=condorExe.iexe_cmd('./job_submit.sh "%s" "%s" "%s" %i "dbg" %s -- %s'%(entry_name,schedd_name,client_name,nr_to_submit,submit_attrs_str,params_str))
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


###########################################################
#
# CVS info
#
# $Id: glideFactoryLib.py,v 1.20 2007/05/18 19:10:57 sfiligoi Exp $
#
# Log:
#  $Log: glideFactoryLib.py,v $
#  Revision 1.20  2007/05/18 19:10:57  sfiligoi
#  Add CVS tags
#
#
###########################################################
