#
# Description:
#   This module implements the functions needed to keep the
#   required number of idle glideins
#
# Author:
#   Igor Sfiligoi (Sept 19th 2006)
#

import condorMonitor,condorExe

#
# Return a dictionary of schedds containing interesting jobs
# Each element is a condorQ
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate constraint
#
def getCondorQ(schedd_names,constraint=None,format_list=None):
    if format_list!=None:
        format_list=condorMonitor.complete_format_list(format_list,[('JobStatus','i'),('EnteredCurrentStatus','i'),('ServerTime','i')])
    return getCondorQConstrained(schedd_names,"(JobStatus=?=1)||(JobStatus=?=2)",constraint,format_list)


#
# Return a dictionary of schedds containing idle jobs
# Each element is a condorQ
#
# Use the output of getCondorQ
#
def getIdleCondorQ(condorq_dict):
    out={}
    for schedd_name in condorq_dict.keys():
        sq=condorMonitor.SubQuery(condorq_dict[schedd_name],lambda el:(el.has_key('JobStatus') and (el['JobStatus']==1)))
        sq.load()
        out[schedd_name]=sq
    return out

#
# Return a dictionary of schedds containing running jobs
# Each element is a condorQ
#
# Use the output of getCondorQ
#
def getRunningCondorQ(condorq_dict):
    out={}
    for schedd_name in condorq_dict.keys():
        sq=condorMonitor.SubQuery(condorq_dict[schedd_name],lambda el:(el.has_key('JobStatus') and (el['JobStatus']==2)))
        sq.load()
        out[schedd_name]=sq
    return out

#
# Return a dictionary of schedds containing old jobs
# Each element is a condorQ
#
# Use the output of getCondorQ
#
def getOldCondorQ(condorq_dict,min_age):
    out={}
    for schedd_name in condorq_dict.keys():
        sq=condorMonitor.SubQuery(condorq_dict[schedd_name],lambda el:(el.has_key('ServerTime') and el.has_key('EnteredCurrentStatus') and ((el['ServerTime']-el['EnteredCurrentStatus'])>=min_age)))
        sq.load()
        out[schedd_name]=sq
    return out

#
# Return the number of jobs in the dictionary
# Use the output of getCondorQ
#
def countCondorQ(condorq_dict):
    count=0
    for schedd_name in condorq_dict.keys():
        count+=len(condorq_dict[schedd_name].fetchStored())
    return count

#
# Get the number of jobs that match each glidein
#
# match_str = '(job["MIN_NAME"]<glidein["MIN_NAME"]) && (job["ARCH"]==glidein["ARCH"])'
# condorq_dict = output of getidlqCondorQ
# glidein_dict = output of interface.findGlideins
#
# Returns:
#  dictionary of glidein name
#   where elements are number of idle jobs matching
def countMatch(match_str,condorq_dict,glidein_dict):
    match_obj=compile(match_str,"<string>","eval")
    out_glidein_counts={}
    for glidename in glidein_dict:
        glidein=glidein_dict[glidename]
        glidein_count=0
        for schedd in condorq_dict.keys():
            condorq=condorq_dict[schedd]
            condorq_data=condorq.fetchStored()
            schedd_count=0
            for jid in condorq_data.keys():
                job=condorq_data[jid]
                if eval(match_obj):
                    schedd_count+=1
                pass
            glidein_count+=schedd_count
            pass
        out_glidein_counts[glidename]=glidein_count
        pass
    return out_glidein_counts


#
# Return a dictionary of collectors containing interesting classads
# Each element is a condorStatus
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate constraint
#
def getCondorStatus(collector_names,constraint=None,format_list=None):
    if format_list!=None:
        format_list=condorMonitor.complete_format_list(format_list,[('State','s'),('Activity','s'),('EnteredCurrentState','i'),('EnteredCurrentActivity','i'),('LastHeardFrom','i'),('GLIDEIN_Factory','s'),('GLIDEIN_Name','s'),('GLIDEIN_Entry_Name','s'),('GLIDEIN_Client','s')])
    return getCondorStatusConstrained(collector_names,'IS_MONITOR_VM=!=True',constraint,format_list)

#
# Return a dictionary of collectors containing idle(unclaimed) vms
# Each element is a condorStatus
#
# Use the output of getCondorStatus
#
def getIdleCondorStatus(status_dict):
    out={}
    for collector_name in status_dict.keys():
        sq=condorMonitor.SubQuery(status_dict[collector_name],lambda el:(el.has_key('State') and el.has_key('Activity') and (el['State']=="Unclaimed") and (el['Activity']=="Idle")))
        sq.load()
        out[collector_name]=sq
    return out

#
# Return a dictionary of collectors containing running(claimed) vms
# Each element is a condorStatus
#
# Use the output of getCondorStatus
#
def getRunningCondorStatus(status_dict):
    out={}
    for collector_name in status_dict.keys():
        sq=condorMonitor.SubQuery(status_dict[collector_name],lambda el:(el.has_key('State') and el.has_key('Activity') and (el['State']=="Claimed") and (el['Activity'] in ("Busy","Retiring"))))
        sq.load()
        out[collector_name]=sq
    return out

#
# Return a dictionary of collectors containing idle(unclaimed) vms
# Each element is a condorStatus
#
# Use the output of getCondorStatus
#
def getClientCondorStatus(status_dict,frontend_name,request_name):
    client_name="%s@%s"%(request_name,frontend_name)
    out={}
    for collector_name in status_dict.keys():
        sq=condorMonitor.SubQuery(status_dict[collector_name],lambda el:(el.has_key('GLIDECLIENT_Name') and (el['GLIDECLIENT_Name']==client_name)))

        sq.load()
        out[collector_name]=sq
    return out

#
# Return the number of vms in the dictionary
# Use the output of getCondorStatus
#
def countCondorStatus(status_dict):
    count=0
    for collector_name in status_dict.keys():
        count+=len(status_dict[collector_name].fetchStored())
    return count

############################################################
#
# I N T E R N A L - Do not use
#
############################################################

#
# Return a dictionary of schedds containing jobs of a certain type 
# Each element is a condorQ
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate additional constraint
#
def getCondorQConstrained(schedd_names,type_constraint,constraint=None,format_list=None):
    out_condorq_dict={}
    for schedd in schedd_names:
        condorq=condorMonitor.CondorQ(schedd)
        full_constraint=type_constraint[0:] #make copy
        if constraint!=None:
            full_constraint="(%s) && (%s)"%(full_constraint,constraint)

        try:
            condorq.load(full_constraint,format_list)
        except condorExe.ExeError, e:

            continue # if schedd not found it is equivalent to no jobs in the queue
        if len(condorq.fetchStored())>0:
            out_condorq_dict[schedd]=condorq
    return out_condorq_dict

#
# Return a dictionary of collectors containing classads of a certain kind 
# Each element is a condorStatus
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate additional constraint
#
def getCondorStatusConstrained(collector_names,type_constraint,constraint=None,format_list=None):
    out_status_dict={}
    for collector in collector_names:
        status=condorMonitor.CondorStatus(pool_name=collector)
        full_constraint=type_constraint[0:] #make copy
        if constraint!=None:
            full_constraint="(%s) && (%s)"%(full_constraint,constraint)

        try:
            status.load(full_constraint,format_list)
        except condorExe.ExeError, e:
            continue # if collector not found it is equivalent to no classads
        if len(status.fetchStored())>0:
            out_status_dict[collector]=status
    return out_status_dict

