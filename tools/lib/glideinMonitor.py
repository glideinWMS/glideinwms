#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements helper functions
#   used to perform pseudo-interactive monitoring
#
# Prerequisites:
#   The startd must be configured with exactly 2 slots, called vm
#   It must have cross-vm expressions State and RemoteUser enabled.
#   It also must advertize that has the monitor vm.
#
# Author:
#   Igor Sfiligoi (May 2007)
#

import string
import time
import tempfile
import shutil
import os
import os.path
import sys

# This should be done by the user of the module
#sys.path.append("../../lib")

from glideinwms.lib import condorMonitor
from glideinwms.lib import condorManager

# returns a dictionary of jid,schedd_name,pool_name, timeout and argv
# the argv contains the arguments not parsed by the function
def parseArgs(argv):
    outdict={'schedd_name':None,'pool_name':None,
             'timeout':130} #default
    jid=None
    alen=len(argv)
    i=0
    while i<alen:
        ael=argv[i]
        if ael=='-name':
            i=i+1
            outdict['schedd_name']=argv[i]
        elif ael=='-pool':
            i=i+1
            outdict['pool_name']=argv[i]
        elif ael=='-timeout':
            i=i+1
            outdict['timeout']=int(argv[i])
        else:
            if jid is None:
                jid=ael
            else:
                # first unknown element
                # return the rest to the caller
                break
        i=i+1

    if jid is None:
        raise RuntimeError, 'JID not found'
    outdict['jid']=jid
    outdict['argv']=argv[i:]
    return outdict
    
# createMonitorFile is a callback with the following arguments:
#    (monitor_file_name,monitor_control_relname,argv,condor_status,monitorVM):
def monitor(jid,schedd_name,pool_name,
            timeout,
            createMonitorFile,argv,
            stdout_fd=sys.stdout,
            stderr_fd=sys.stderr):
    try:
        jid_cluster,jid_proc=string.split(jid,".",1)
    except:
        raise RuntimeError, 'Invalid JID %s, expected Cluster.Proc'%jid
    
    constraint="(ClusterId=?=%s) && (ProcId=?=%s)"%(jid_cluster,jid_proc)

    remoteVM=getRemoteVM(pool_name,schedd_name,constraint)
    monitorVM=getMonitorVM(pool_name,remoteVM)

    condor_status=getMonitorVMStatus(pool_name,monitorVM)
    validateMonitorVMStatus(condor_status,monitorVM)

    if condor_status.has_key('GLEXEC_STARTER'):
        glexec_starter=condor_status['GLEXEC_STARTER']
    else:
        glexec_starter=False #if not defined, assume no gLExec for old way

    if condor_status.has_key('GLEXEC_JOB'):
        glexec_job=condor_status['GLEXEC_JOB']
    else:
        glexec_job=False #if not defined, assume no gLExec for new way

    if glexec_starter or glexec_job:
        if not os.environ.has_key('X509_USER_PROXY'):
            raise RuntimeError, "Job running on a gLExec enabled resource; X509_USER_PROXY must be defined"
        x509_file=os.environ['X509_USER_PROXY']
    else:
        x509_file=None
        

    tmpdir=tempfile.mkdtemp(prefix="glidein_intmon_")
    try:
        sname=os.path.join(tmpdir,"mon.submit")
        mfname=os.path.join(tmpdir,"mon.sh")
        mfout=os.path.join(tmpdir,"mon.out")
        mferr=os.path.join(tmpdir,"mon.err")
        mlog=os.path.join(tmpdir,"mon.log")
        mc_relname="mon.done"
        mcname=os.path.join(tmpdir,mc_relname)
        createMonitorFile(mfname,mc_relname,argv,condor_status,monitorVM)
        createSubmitFile(tmpdir,sname,mlog,mfname,mfout,mferr,
                         monitorVM,timeout,x509_file)
        jid=condorManager.condorSubmitOne(sname,schedd_name,pool_name)
        try:
            checkFile(mcname,schedd_name,pool_name,timeout,reschedule_freq=10)
            printFile(mfout,stdout_fd)
            printFile(mferr,stderr_fd)
        except:
            condorManager.condorRemoveOne(jid,schedd_name,pool_name)
            raise
    finally:
        shutil.rmtree(tmpdir)
    return

######## Internal ############



def getRemoteVM(pool_name,schedd_name,constraint):
    cq=condorMonitor.CondorQ(schedd_name=schedd_name,pool_name=pool_name)
    data=cq.fetch(constraint)
    if len(data.keys())==0:
        raise RuntimeError, "Job not found"
    if len(data.keys())>1:
        raise RuntimeError, "Can handle only one job at a time"
    el=data.values()[0]
    if (not el.has_key('JobStatus')) or (el['JobStatus']!=2):
        raise RuntimeError, "Job not running"
    if not el.has_key('RemoteHost'):
        raise RuntimeError, "Job still starting"
    
    return el['RemoteHost']

def getMonitorVM(pool_name,jobVM):
    cs=condorMonitor.CondorStatus(pool_name=pool_name)
    data=cs.fetch(constraint='(Name=="%s")'%jobVM,format_list=[('IS_MONITOR_VM','b'),('HAS_MONITOR_VM','b'),('Monitoring_Name','s')])
    if not data.has_key(jobVM):
        raise RuntimeError, "Job claims it runs on %s, but cannot find it!"%jobVM
    job_data=data[jobVM]
    if (not job_data.has_key('HAS_MONITOR_VM')) or (not job_data.has_key('IS_MONITOR_VM')):
        raise RuntimeError, "Slot %s does not support monitoring!"%jobVM
    if not (job_data['HAS_MONITOR_VM']==True):
        raise RuntimeError, "Slot %s does not support monitoring! HAS_MONITOR_VM not True."%jobVM
    if not (job_data['IS_MONITOR_VM']==False):
        raise RuntimeError, "Slot %s is a monitoring slot itself! Cannot monitor."%jobVM
    if not job_data.has_key('Monitoring_Name'):
        raise RuntimeError, "Slot %s does not publish the monitoring slot!"%jobVM

    return job_data['Monitoring_Name']

def getMonitorVMStatus(pool_name,monitorVM):
    cs=condorMonitor.CondorStatus(pool_name=pool_name)
    data=cs.fetch(constraint='(Name=="%s")'%monitorVM,
                  format_list=[('IS_MONITOR_VM','b'),('HAS_MONITOR_VM','b'),('State','s'),('Activity','s'),('vm2_State','s'),('vm2_Activity','s'),('GLEXEC_STARTER','b'),('USES_MONITOR_STARTD','b'),('GLEXEC_JOB','b')])
    if not data.has_key(monitorVM):
        raise RuntimeError, "Monitor slot %s does not exist!"%monitorVM

    return data[monitorVM]

def validateMonitorVMStatus(condor_status,monitorVM):
    if ((not condor_status.has_key('HAS_MONITOR_VM')) or
        (condor_status['HAS_MONITOR_VM']!=True)):
        raise RuntimeError, "Monitor slot %s does not allow monitoring"%monitorVM
    if not (condor_status['IS_MONITOR_VM']==True):
        raise RuntimeError, "Slot %s is not a monitoring slot!"%monitorVM

    # Since we will be queueing anyhow, do not check if it is ready right now 
    #if condor_status['State']=='Claimed':
    #    raise RuntimeError, "Job cannot be monitored right now"

    if condor_status['Activity']=='Retiring':
        raise RuntimeError, "Job cannot be monitored anymore"

    if condor_status.has_key('vm2_State'):
        # only if has vm2_State are cross VM states checked
        if condor_status['vm2_State']!='Claimed':
            raise RuntimeError, "Job cannot be yet monitored"
        if condor_status['vm2_Activity']=='Retiring':
            raise RuntimeError, "Job cannot be monitored anymore"

    return

def createSubmitFile(work_dir,sfile,mlog,
                     mfname,mfout,mferr,
                     monitorVM,timeout,x509_file=None):
    fd=open(sfile,"w")
    try:
        fd.write("universe=vanilla\n")
        fd.write("executable=%s\n"%mfname)
        fd.write("initialdir=%s\n"%work_dir)
        fd.write("output=%s\n"%mfout)
        fd.write("error=%s\n"%mferr)
        fd.write("log=%s\n"%mlog)
        fd.write("transfer_executable=True\n")
        fd.write("when_to_transfer_output=ON_EXIT\n")
        fd.write("notification=Never\n")
        fd.write("+GLIDEIN_Is_Monitor=True\n")
        fd.write("+Owner=Undefined\n")
        if x509_file is not None:
            fd.write('x509userproxy = %s\n'%x509_file)
        fd.write('Requirements=(Name=?="%s")&&(Arch=!="Absurd")\n'%monitorVM)
        fd.write("periodic_remove=(CurrentTime>%li)\n"%(long(time.time())+timeout+30)) # karakiri after timeout+delta
        fd.write("queue\n")
    finally:
        fd.close()

def checkFile(fname,schedd_name,pool_name,
              timeout,reschedule_freq):
    deadline=time.time()+timeout
    last_reschedule=time.time()
    while (time.time()<deadline):
        if (time.time()-last_reschedule)>=reschedule_freq:
            condorManager.condorReschedule(schedd_name,pool_name)
            last_reschedule=time.time()
        time.sleep(1)
        if os.path.exists(fname):
            return True
    raise RuntimeError, "Command did not reply within timeout (%ss)"%timeout

def printFile(fname,outfd):
    fd=open(fname)
    try:
        data=fd.read()
        outfd.write(data)
    finally:
        fd.close()

