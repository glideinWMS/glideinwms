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

import condorMonitor
import condorManager

# returns a dictionary of jid,schedd_name,pool_name, timeout and argv
# the argv contains the arguments not parsed by the function
def parseArgs(argv):
    outdict={'schedd_name':None,'pool_name':None,
             'timeout':60} #default
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
            if jid==None:
                jid=ael
            else:
                # first unknown element
                # return the rest to the caller
                break
        i=i+1

    if jid==None:
        raise RuntimeError, 'JID not found'
    outdict['jid']=jid
    outdict['argv']=argv[i:]
    return outdict
    
# createMonitorFile is a callback with the following arguments:
#    (monitor_file_name,monitor_control_relname,argv,condor_status,remoteJobVM,monitorVM):
def monitor(jid,schedd_name,pool_name,
            timeout,
            createMonitorFile,argv):
    try:
        jid_cluster,jid_proc=string.split(jid,".",1)
    except:
        raise RuntimeError, 'Invalid JID %s, expected Cluster.Proc'%jid
    
    constraint="(ClusterId=?=%s) && (ProcId=?=%s)"%(jid_cluster,jid_proc)

    remoteVM=getRemoteVM(pool_name,schedd_name,constraint)
    monitorVM=getMonitorVM(remoteVM)

    condor_status=getCondorStatus(pool_name,remoteVM,monitorVM)
    validateCondorStatus(condor_status,remoteVM,monitorVM)

    if condor_status[monitorVM].has_key('GLEXEC_STARTER'):
        glexec_starter=condor_status[monitorVM]['GLEXEC_STARTER']
    else:
        glexec_starter=False #if not defined, assume no gLExec

    if glexec_starter:
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
        createMonitorFile(mfname,mc_relname,argv,condor_status,remoteVM,monitorVM)
        createSubmitFile(tmpdir,sname,mlog,mfname,mfout,mferr,
                         monitorVM,timeout,x509_file)
        jid=condorManager.condorSubmitOne(sname,schedd_name,pool_name)
        try:
            checkFile(mcname,timeout)
            printFile(mfout,sys.stdout)
            printFile(mferr,sys.stderr)
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

def getMonitorVM(remoteVM):
    rvm_arr=string.split(remoteVM,"@",1)
    if len(rvm_arr)!=2:
        raise RuntimeError, "Not running on a multi-VM resource"
    vm,host=rvm_arr
    if vm!="vm2":
        raise RuntimeError, "Not running on a supported glidein (%s!=vm2)"%vm
    return "%s@%s"%("vm1",host)

def getCondorStatus(pool_name,jobVM,monitorVM):
    cs=condorMonitor.CondorStatus(pool_name=pool_name)
    data=cs.fetch(constraint='(Name=="%s") || (Name=="%s")'%(jobVM,monitorVM))
    return data

def validateCondorStatus(condor_status,jobVM,monitorVM):
    if not condor_status.has_key(jobVM):
        raise RuntimeError, "Job claims it runs on %s, but cannot find it!"%jobVM
    if not condor_status.has_key(monitorVM):
        raise RuntimeError, "No monitoring VM found (should be %s)"%monitorVM

    if ((not condor_status[monitorVM].has_key('HAS_MONITOR_VM')) or
        (condor_status[monitorVM]['HAS_MONITOR_VM']!=True)):
        raise RuntimeError, "The startd does not allow monitoring"

    if condor_status[monitorVM]['State']=='Claimed':
        raise RuntimeError, "Job cannot be monitored right now"

    if ((not condor_status[monitorVM].has_key('vm2_State')) or
        (condor_status[monitorVM]['vm2_State']!='Claimed')):
        raise RuntimeError, "Job cannot be yet monitored"

    if ((not condor_status[monitorVM].has_key('vm2_State')) or
        (condor_status[monitorVM]['vm2_Activity']=='Retiring')):
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
        if x509_file!=None:
            fd.write('x509userproxy = %s\n'%x509_file)
        fd.write('Requirements=(Name=?="%s")&&(Arch=!="Absurd")\n'%monitorVM)
        fd.write("periodic_remove=(CurrentTime>%li)\n"%(long(time.time())+timeout+30)) # karakiri after timeout+delta
        fd.write("queue\n")
    finally:
        fd.close()

def checkFile(fname,timeout):
    deadline=time.time()+timeout
    while (time.time()<deadline):
        if os.path.exists(fname):
            return True
        time.sleep(1)
    raise RuntimeError, "Command did not reply within timeout (%ss)"%timeout

def printFile(fname,outfd):
    fd=open(fname)
    try:
        data=fd.read()
        outfd.write(data)
    finally:
        fd.close()

