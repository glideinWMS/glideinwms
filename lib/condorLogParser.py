#
# Description:
#   This module implements classes and functions to parse
#   the condor log files.
#
# Author:
#   Igor Sfiligoi (Feb 1st 2007)
#

import os,os.path,stat
import re,mmap
import cPickle

# this class will keep track of:
#  - counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
#  - list of completed jobs
# It will also return the previously cached value, to be used for
# incremental counts
class logSummary:
    def __init__(self,logname):
        self.logname=logname
        self.cachename=logname+".scpk"

    # compare to cache, and tell if the log file has changed since last checked
    def has_changed(self):
        if os.path.isfile(self.logname):
            fstat=os.lstat(self.logname)
            logtime=fstat[stat.ST_MTIME]
        else:
            return False # does not exist, so it could not change
        
        if os.path.isfile(self.cachename):
            fstat=os.lstat(self.cachename)
            cachetime=fstat[stat.ST_MTIME]
        else:
            return True # no cache, so it has changed for sure
        
        # both exist -> check if log file is newer
        return (logtime>cachetime)

    # load from the most recent one, and update the cache if needed
    def load(self):
        if not self.has_changed():
            # cache is newer, just load the cache
            return self.loadCache()

        while 1: #could need more than one loop if the log file is changing
            fstat=os.lstat(self.logname)
            start_logtime=fstat[stat.ST_MTIME]
            del fstat
            
            self.loadFromLog()
            try:
                self.saveCache()
            except IOError:
                return # silently ignore, this was a load in the end
            # the log may have changed -> check
            fstat=os.lstat(self.logname)
            logtime=fstat[stat.ST_MTIME]
            del fstat
            if logtime<=start_logtime:
                return # OK, not changed, can exit
        
        return # should never reach this point

        
    def loadCache(self):
        fd=open(self.cachename,"r")
        self.data=cPickle.load(fd)
        fd.close()
        return

    def loadFromLog(self):
        tmpdata={}
        jobs = parseSubmitLogFastRaw(self.logname)
        status  = listAndInterpretRawStatuses(jobs)
        counts={}
        for s in status.keys():
            counts[s]=len(status[s])
        tmpdata['counts']=counts
        if status.has_key("Completed"):
            tmpdata['completed_jobs']=status['Completed']
        else:
            tmpdata['completed_jobs']=0
        self.data=tmpdata
        return

    ####### PRIVATE ###########
    def saveCache(self):
        # two steps; first create a tmp file, then rename
        tmpname=self.cachename+(".tmp_%i"%os.getpid())
        fd=open(tmpname,"w")
        cPickle.dump(self.data,fd)
        fd.close()

        try:
            os.remove(self.cachename)
        except:
            pass # may not exist
        os.rename(tmpname,self.cachename)
        
        return


##############################################################################
#
# Low level functions
#
##############################################################################

################################
#  Condor log parsing functions
################################

# read a condor submit log
# return a dictionary of jobStrings each having the last statusString
# for example {'1583.004': '000', '3616.008': '009'}
def parseSubmitLogFastRaw(fname):
    jobs={}
    
    size = os.path.getsize(fname)
    fd=open(fname,"r")
    buf=mmap.mmap(fd.fileno(),size,access=mmap.ACCESS_READ)

    count=0
    idx=0

    while (idx+5)<size: # else we are at the end of the file
        # format
        # 023 (123.2332.000) Bla
        
        # first 3 chars are status
        status=buf[idx:idx+3]
        idx+=5
        # extract job id 
        i1=buf.find(")",idx)
        if i1<0:
            break
        jobid=buf[idx:i1-4]
        idx=i1+1

        jobs[jobid]=status
        i1=buf.find("...",idx)
        if i1<0:
            break
        idx=i1+4 #the 3 dots plus newline

    buf.close()
    fd.close()
    return jobs

# convert the log representation into (ClusterId,ProcessId)
# Return (-1,-1) in case of error
def rawJobId2Nr(str):
    arr=str.split(".")
    if len(arr)>=2:
        return (int(arr[0]),int(arr[1]))
    else:
        return (-1,-1) #invalid

# Status codes
# 000 - Job submitted
# 001 - Job executing
# 002 - Error in executable
# 003 - Job was checkpointed
# 004 - Job was evicted
# 005 - Job terminated
# 006 - Image size of job updated
# 007 - Shadow exception
# 008 - <Not used>
# 009 - Job was aborted
# 010 - Job was suspended
# 011 - Job was unsuspended
# 012 - Job was held
# 013 - Job was released
# 014 - Parallel node executed (not used here)
# 015 - Parallel node terminated (not used here)
# 016 - POST script terminated
# 017 - Job submitted to Globus
# 018 - Globus submission failed
# 019 - Globus Resource Back Up
# 020 - Detected Down Globus Resource
# 021 - Remote error
# 022 - Remote system call socket lost 
# 023 - Remote system call socket reestablished
# 024 - Remote system call reconnect failure
# 025 - Grid Resource Back Up
# 026 - Detected Down Grid Resource
# 027 - Job submitted to grid resource

# reduce the syayus to either Wait, Idle, Running, Held, Completed or Removed
def interpretStatus(status):
    if status==5:
        return "Completed"
    elif status==9:
        return "Removed"
    elif status in (1,3,6,10,11,22,23):
        return "Running"
    elif status==12:
        return "Held"
    elif status in (0,20,26):
        return "Wait"
    else:
        return "Idle"

# given a dictionary of job statuses (like the one got from parseSubmitLogFastRaw)
# will return a dictionary of sstatus counts
# for example: {'009': 25170, '012': 418, '005': 1503}
def countStatuses(jobs):
    counts={}
    for e in jobs.values():
        try:
            counts[e]+=1
        except: # there are only a few possible values, so using exceptions is faster
            counts[e]=1
    return counts

# given a dictionary of job statuses (like the one got from parseSubmitLogFastRaw)
# will return a dictionary of sstatus counts
# for example: {'Completed': 30170, 'Removed': 148, 'Running': 5013}
def countAndInterpretRawStatuses(jobs_raw):
    outc={}
    tmpc=countStatuses(jobs_raw)
    for s in tmpc.keys():
        i_s=interpretStatus(int(s))
        try:
            outc[i_s]+=tmpc[s]
        except:  # there are only a few possible values, so using exceptions is faster
            outc[i_s]=tmpc[s]
    return outc

# given a dictionary of job statuses (like the one got from parseSubmitLogFastRaw)
# will return a dictionary of jobs in each status
# for example: {'009': ["1.003","2.001"], '012': ["418.001"], '005': ["1503.001","1555.002"]}
def listStatuses(jobs):
    status={}
    for k,e in jobs.items():
        try:
            status[e].append(k)
        except: # there are only a few possible values, so using exceptions is faster
            status[e]=[k]
    return status

# given a dictionary of job statuses (like the one got from parseSubmitLogFastRaw)
# will return a dictionary of jobs in each status
# for example: {'Completed': ["2.003","5.001"], 'Removed': ["41.001"], 'Running': ["408.003"]}
def listAndInterpretRawStatuses(jobs_raw):
    outc={}
    tmpc=listStatuses(jobs_raw)
    for s in tmpc.keys():
        i_s=interpretStatus(int(s))
        try:
            outc[i_s]+=tmpc[s]
        except:  # there are only a few possible values, so using exceptions is faster
            outc[i_s]=tmpc[s]
    return outc

# read a condor submit log
# return a dictionary of jobIds each having the last status
# for example {(1583,4)': 0, (3616,8): 9}
def parseSubmitLogFast(fname):
    jobs_raw=parseSubmitLogFastRaw(fname)
    jobs={}
    for k in jobs_raw.keys():
        jobs[rawJobId2Nr(k)]=int(jobs_raw[k])
    return jobs

