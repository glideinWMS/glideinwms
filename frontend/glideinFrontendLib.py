#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glideinFrontendLib.py,v 1.29.2.1.8.2.6.2 2010/11/19 23:32:03 sfiligoi Exp $
#
# Description:
#   This module implements the functions needed to keep the
#   required number of idle glideins
#   plus other miscelaneous functions
#
# Author:
#   Igor Sfiligoi (Sept 19th 2006)
#

import os.path
import sets,string
import condorMonitor,condorExe
import logSupport

class LogFiles:
    def __init__(self,log_dir,max_days,min_days,max_mbs):
        self.log_dir=log_dir
        self.activity_log=logSupport.DayLogFile(os.path.join(log_dir,"frontend"),"info.log")
        self.warning_log=logSupport.DayLogFile(os.path.join(log_dir,"frontend"),"err.log")
        self.debug_log=logSupport.DayLogFile(os.path.join(log_dir,"frontend"),"debug.log")
        self.cleanupObj=logSupport.DirCleanupWSpace(log_dir,"(frontend\.[0-9]*\.info\.log)|(frontend\.[0-9]*\.err\.log)|(frontend\.[0-9]*\.debug\.log)",
                                                    int(max_days*24*3600),int(min_days*24*3600),
                                                    long(max_mbs*(1024.0*1024.0)),
                                                    self.activity_log,self.warning_log)

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
        try:
            self.cleanupObj.cleanup()
        except:
            # logging must never throw an exception!
            self.logWarning("log cleanup failed.")

# someone needs to initialize this
# type LogFiles
log_files=None

#############################################################################################

#
# Return a dictionary of schedds containing interesting jobs
# Each element is a condorQ
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate constraint
#
def getCondorQ(schedd_names,constraint=None,format_list=None):
    if format_list!=None:
        format_list=condorMonitor.complete_format_list(format_list,[('JobStatus','i'),('EnteredCurrentStatus','i'),('ServerTime','i'),('RemoteHost','s')])
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

def appendRealRunning(condorq_dict, status_dict):
    for schedd_name in condorq_dict:
        condorq = condorq_dict[schedd_name].fetchStored()

        for jid in condorq:
            found = False
  
            if condorq[jid].has_key('RemoteHost'):
                remote_host = condorq[jid]['RemoteHost']

                for collector_name in status_dict:
                    condor_status = status_dict[collector_name].fetchStored()
                    if remote_host in condor_status:
                        # there is currently no way to get the factory collector from
                        #   condor status so this hack grabs the hostname of the schedd
                        schedd = condor_status[remote_host]['GLIDEIN_Schedd'].split('@')
                        if len(schedd) < 2:
                          break

                        # split by : to remove port number if there
                        fact_pool = schedd[1].split(':')[0]

                        condorq[jid]['RunningOn'] = "%s@%s@%s@%s" % (
                            condor_status[remote_host]['GLIDEIN_Entry_Name'],
                            condor_status[remote_host]['GLIDEIN_Name'],
                            condor_status[remote_host]['GLIDEIN_Factory'],
                            fact_pool)
                        found = True
                        break

            if not found:
                condorq[jid]['RunningOn'] = 'UNKNOWN'
        
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
# Return a set of users present in the dictionary
# Needs "User" attribute
#

def getCondorQUsers(condorq_dict):
    users_set=sets.Set()
    for schedd_name in condorq_dict.keys():
        condorq_data=condorq_dict[schedd_name].fetchStored()
        for jid in condorq_data.keys():
            job=condorq_data[jid]
            users_set.add(job['User'])
            
    return users_set

#
# Get the number of jobs that match each glidein
#
# match_obj = compile('(job["MIN_NAME"]<glidein["MIN_NAME"]) && (job["ARCH"]==glidein["ARCH"])',"<string>","eval")
# condorq_dict = output of getidlqCondorQ
# glidein_dict = output of interface.findGlideins
#
# Returns:
#  dictionary of glidein name
#   where elements are number of idle jobs matching
def countMatch(match_obj,condorq_dict,glidein_dict):
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

def countRealRunning(match_obj,condorq_dict,glidein_dict):
    out_glidein_counts={}
    for glidename in glidein_dict:
        # split by : to remove port number if there
        glide_str = "%s@%s" % (glidename[1],glidename[0].split(':')[0])
        glidein=glidein_dict[glidename]
        glidein_count=0
        for schedd in condorq_dict.keys():
            condorq=condorq_dict[schedd]
            condorq_data=condorq.fetchStored()
            schedd_count=0
            for jid in condorq_data.keys():
                job=condorq_data[jid]
                if eval(match_obj) and job['RunningOn'] == glide_str:
                    schedd_count+=1
                pass
            glidein_count+=schedd_count
            pass
        out_glidein_counts[glidename]=glidein_count
        pass
    return out_glidein_counts

#
# Convert frontend param expression in a value
#
# expr_obj = compile('glidein["MaxTimeout"]+frontend["MaxTimeout"]+600',"<string>","eval")
# frontend = the frontend const parameters
# glidein  = glidein factory parameters
#
# Returns:
#  The evaluated value
def evalParamExpr(expr_obj,frontend,glidein):
    return eval(expr_obj)

#
# Return a dictionary of collectors containing interesting classads
# Each element is a condorStatus
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate constraint
#
def getCondorStatus(collector_names,constraint=None,format_list=None):
    if format_list!=None:
        format_list=condorMonitor.complete_format_list(format_list,[('State','s'),('Activity','s'),('EnteredCurrentState','i'),('EnteredCurrentActivity','i'),('LastHeardFrom','i'),('GLIDEIN_Factory','s'),('GLIDEIN_Name','s'),('GLIDEIN_Entry_Name','s'),('GLIDECLIENT_Name','s'),('GLIDEIN_Schedd','s')])
    return getCondorStatusConstrained(collector_names,'(IS_MONITOR_VM=!=True)&&(GLIDEIN_Factory=!=UNDEFINED)&&(GLIDEIN_Name=!=UNDEFINED)&&(GLIDEIN_Entry_Name=!=UNDEFINED)',constraint,format_list)

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
def getClientCondorStatus(status_dict,frontend_name,group_name,request_name):
    client_name_old="%s@%s.%s"%(request_name,frontend_name,group_name)
    client_name_new="%s.%s"%(frontend_name,group_name)
    out={}
    for collector_name in status_dict.keys():
        sq=condorMonitor.SubQuery(status_dict[collector_name],lambda el:(el.has_key('GLIDECLIENT_Name') and ((el['GLIDECLIENT_Name']==client_name_old) or ((el['GLIDECLIENT_Name']==client_name_new) and (("%s@%s@%s"%(el['GLIDEIN_Entry_Name'],el['GLIDEIN_Name'],el['GLIDEIN_Factory']))==request_name)))))
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
        if schedd=='':
            log_files.logWarning("Skipping empty schedd name")
            continue
        condorq=condorMonitor.CondorQ(schedd)
        full_constraint=type_constraint[0:] #make copy
        if constraint!=None:
            full_constraint="(%s) && (%s)"%(full_constraint,constraint)

        try:
            condorq.load(full_constraint,format_list)
        except condorExe.ExeError, e:
            if schedd!=None:
                log_files.logWarning("Failed to talk to schedd %s. See debug log for more details."%schedd)
                log_files.logDebug("Failed to talk to schedd %s: %s"%(schedd, e))
            else:
                log_files.logWarning("Failed to talk to schedd. See debug log for more details.")
                log_files.logDebug("Failed to talk to schedd: %s"%e)
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
            if collector!=None:
                log_files.logWarning("Failed to talk to collector %s. See debug log for more details."%collector)
                log_files.logDebug("Failed to talk to collector %s: %s"%(collector, e))
            else:
                log_files.logWarning("Failed to talk to collector. See debug log for more details.")
                log_files.logDebug("Failed to talk to collector: %s"%e)
            continue # if collector not found it is equivalent to no classads
        if len(status.fetchStored())>0:
            out_status_dict[collector]=status
    return out_status_dict

