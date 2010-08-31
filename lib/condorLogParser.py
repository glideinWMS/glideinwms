#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: condorLogParser.py,v 1.22.8.5.2.2 2010/08/31 18:49:17 parag Exp $
#
# Description:
#   This module implements classes and functions to parse
#   the condor log files.
#
# Author:
#   Igor Sfiligoi (Feb 1st 2007)
#

# NOTE:
# Inactive files are log files that have only completed or removed entries
# Such files will not change in the future
#

import os,os.path,stat
import re,mmap
import time
import cPickle,sets

# -------------- Single Log classes ------------------------

class cachedLogClass:
    # virtual, do not use
    # the Constructor needs to define logname and cachename (possibly by using clInit)
    # also loadFromLog, merge and isActive need to be implemented

    # init method to be used by real constructors
    def clInit(self,logname,cache_dir,cache_ext):
        self.logname=logname
        if cache_dir==None:
            self.cachename=logname+cache_ext
        else:
            self.cachename=os.path.join(cache_dir,os.path.basename(logname)+cache_ext)

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
        self.data=loadCache(self.cachename)
        return

    ####### PRIVATE ###########
    def saveCache(self):
        saveCache(self.cachename,self.data)
        return

        
# this class will keep track of:
#  jobs in various of statuses (Wait, Idle, Running, Held, Completed, Removed)
# These data is available in self.data dictionary
# for example self.data={'Idle':['123.003','123.004'],'Running':['123.001','123.002']}
class logSummary(cachedLogClass):
    def __init__(self,logname,cache_dir):
        self.clInit(logname,cache_dir,".cstpk")

    def loadFromLog(self):
        jobs = parseSubmitLogFastRaw(self.logname)
        self.data = listAndInterpretRawStatuses(jobs,listStatuses)
        return

    def isActive(self):
        active=False
        for k in self.data.keys():
            if not (k in ['Completed','Removed']):
                if len(self.data[k])>0:
                    active=True # it is enought that at least one non Completed/removed job exist
        return active

    # merge self data with other info
    # return merged data, may modify other
    def merge(self,other):
        if other==None:
            return self.data
        else:
            for k in self.data.keys():
                try:
                    other[k]+=self.data[k]
                except: # missing key
                    other[k]=self.data[k]
                pass
            return other

    # diff self data with other info
    # return data[status]['Entered'|'Exited'] - list of jobs
    def diff(self,other):
        if other==None:
            outdata={}
            if self.data!=None:
                for k in self.data.keys():
                    outdata[k]={'Exited':[],'Entered':self.data[k]}
            return outdata
        elif self.data==None:
            outdata={}
            for k in other.keys():
                outdata[k]={'Entered':[],'Exited':other[k]}
            return outdata
        else:
            outdata={}
            
            keys={} # keys will contain the merge of the two lists
            
            for s in (self.data.keys()+other.keys()):
                keys[s]=None

            for s in keys.keys():
                if self.data.has_key(s):
                    sel=self.data[s]
                else:
                    sel=[]
                    
                if other.has_key(s):
                    oel=other[s]
                else:
                    oel=[]

                outdata_s={'Entered':[],'Exited':[]}
                outdata[s]=outdata_s

                sset=sets.Set(sel)
                oset=sets.Set(oel)

                outdata_s['Entered']=list(sset.difference(oset))
                outdata_s['Exited']=list(oset.difference(sset))
            return outdata
            

# this class will keep track of:
#  - counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
#  - list of completed jobs
# These data is available in self.data dictionary
#   for example self.data={'completed_jobs':['123.002','555.001'],'counts':{'Idle': 1145, 'Completed': 2}}
class logCompleted(cachedLogClass):
    def __init__(self,logname,cache_dir):
        self.clInit(logname,cache_dir,".clspk")

    def loadFromLog(self):
        tmpdata={}
        jobs = parseSubmitLogFastRaw(self.logname)
        status  = listAndInterpretRawStatuses(jobs,listStatuses)
        counts={}
        for s in status.keys():
            counts[s]=len(status[s])
        tmpdata['counts']=counts
        if status.has_key("Completed"):
            tmpdata['completed_jobs']=status['Completed']
        else:
            tmpdata['completed_jobs']=[]
        self.data=tmpdata
        return

    def isActive(self):
        active=False
        counts=self.data['counts']
        for k in counts.keys():
            if not (k in ['Completed','Removed']):
                if counts[k]>0:
                    active=True # it is enought that at least one non Completed/removed job exist
        return active


    # merge self data with other info
    # return merged data, may modify other
    def merge(self,other):
        if other==None:
            return self.data
        else:
            for k in self.data['counts'].keys():
                try:
                    other['counts'][k]+=self.data['counts'][k]
                except: # missing key
                    other['counts'][k]=self.data['counts'][k]
                pass
            other['completed_jobs']+=self.data['completed_jobs']
            return other


    # diff self data with other info
    def diff(self,other):
        if other==None:
            if self.data!=None:
                outcj={'Exited':[],'Entered':self.data['completed_jobs']}
                outdata={'counts':self.data['counts'],'completed_jobs':outcj}
            else:
                outdata={'counts':{},'completed_jobs':{'Exited':[],'Entered':[]}}
            return outdata
        elif self.data==None:
            outcj={'Entered':[],'Exited':other['completed_jobs']}
            outct={}
            for s in other['counts'].keys():
                outct[s]=-other['counts'][s]
            outdata={'counts':outct,'completed_jobs':outcj}
            return outdata
        else:
            outct={}
            outcj={'Entered':[],'Exited':[]}
            outdata={'counts':outct,'completed_jobs':outcj}

            keys={} # keys will contain the merge of the two lists
            for s in (self.data['counts'].keys()+other['counts'].keys()):
                keys[s]=None

            for s in keys.keys():
                if self.data['counts'].has_key(s):
                    sct=self.data['counts'][s]
                else:
                    sct=0
                    
                if other['counts'].has_key(s):
                    oct=other['counts'][s]
                else:
                    oct=0

                outct[s]=sct-oct

            sel=self.data['completed_jobs']
            oel=other['completed_jobs']
            sset=sets.Set(sel)
            oset=sets.Set(oel)

            outcj['Entered']=list(sset.difference(oset))
            outcj['Exited']=list(oset.difference(sset))

            return outdata

# this class will keep track of
#  counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
# These data is available in self.data dictionary
#   for example self.data={'Idle': 1145, 'Completed': 2}
class logCounts(cachedLogClass):
    def __init__(self,logname,cache_dir):
        self.clInit(logname,cache_dir,".clcpk")

    def loadFromLog(self):
        tmpdata={}
        jobs = parseSubmitLogFastRaw(self.logname)
        self.data  = countAndInterpretRawStatuses(jobs)
        return

    def isActive(self):
        active=False
        for k in self.data.keys():
            if not (k in ['Completed','Removed']):
                if self.data[k]>0:
                    active=True # it is enought that at least one non Completed/removed job exist
        return active


    # merge self data with other info
    # return merged data, may modify other
    def merge(self,other):
        if other==None:
            return self.data
        else:
            for k in self.data.keys():
                try:
                    other[k]+=self.data[k]
                except: # missing key
                    other[k]=self.data[k]
                pass
            return other

    # diff self data with other info
    # return diff of counts
    def diff(self,other):
        if other==None:
            if self.data!=None:
                return self.data
            else:
                return {}
        elif self.data==None:
            outdata={}
            for s in other.keys():
                outdata[s]=-other[s]
            return outdata
        else:
            outdata={}
            
            keys={} # keys will contain the merge of the two lists
            for s in (self.data.keys()+other.keys()):
                keys[s]=None

            for s in keys.keys():
                if self.data.has_key(s):
                    sel=self.data[s]
                else:
                    sel=0
                    
                if other.has_key(s):
                    oel=other[s]
                else:
                    oel=0

                outdata[s]=sel-oel

            return outdata

# this class will keep track of:
#  jobs in various of statuses (Wait, Idle, Running, Held, Completed, Removed)
# These data is available in self.data dictionary
# for example self.data={'Idle':['123.003','123.004'],'Running':['123.001','123.002']}
class logSummaryTimings(cachedLogClass):
    def __init__(self,logname,cache_dir):
        self.clInit(logname,cache_dir,".ctstpk")

    def loadFromLog(self):
        jobs,self.startTime,self.endTime = parseSubmitLogFastRawTimings(self.logname)
        self.data = listAndInterpretRawStatuses(jobs,listStatusesTimings)
        return

    def isActive(self):
        active=False
        for k in self.data.keys():
            if not (k in ['Completed','Removed']):
                if len(self.data[k])>0:
                    active=True # it is enought that at least one non Completed/removed job exist
        return active

    # merge self data with other info
    # return merged data, may modify other
    def merge(self,other):
        if other==None:
            return self.data
        else:
            for k in self.data.keys():
                try:
                    other[k]+=self.data[k]
                except: # missing key
                    other[k]=self.data[k]
                pass
            return other

    # diff self data with other info
    # return data[status]['Entered'|'Exited'] - list of jobs
    def diff(self,other):
        if other==None:
            outdata={}
            if self.data!=None:
                for k in self.data.keys():
                    outdata[k]={'Exited':[],'Entered':self.data[k]}
            return outdata
        elif self.data==None:
            outdata={}
            for k in other.keys():
                outdata[k]={'Entered':[],'Exited':other[k]}
            return outdata
        else:
            outdata={}
            
            keys={} # keys will contain the merge of the two lists
            
            for s in (self.data.keys()+other.keys()):
                keys[s]=None

            for s in keys.keys():
                sel=[]
                if self.data.has_key(s):
                    for sel_e in self.data[s]:
                        sel.append(sel_e[0])

                oel=[]
                if other.has_key(s):
                    for oel_e in other[s]:
                        oel.append(oel_e[0])


                #################
                # Need to finish

                outdata_s={'Entered':[],'Exited':[]}
                outdata[s]=outdata_s

                sset=sets.Set(sel)
                oset=sets.Set(oel)

                entered_set=sset.difference(oset)
                entered=[]
                if self.data.has_key(s):
                    for sel_e in self.data[s]:
                        if sel_e[0] in entered_set:
                            entered.append(sel_e)

                exited_set=oset.difference(sset)
                exited=[]
                if other.has_key(s):
                    for oel_e in other[s]:
                        if oel_e[0] in exited_set:
                            exited.append(oel_e)


                outdata_s['Entered']=entered
                outdata_s['Exited']=exited
            return outdata
            
# -------------- Multiple Log classes ------------------------

# this is a generic class
# while usefull, you probably don't wnat ot use it directly
class cacheDirClass:
    def __init__(self,logClass,
                 dirname,log_prefix,log_suffix=".log",cache_ext=".cifpk",
                 inactive_files=None,         # if ==None, will be reloaded from cache
                 inactive_timeout=24*3600,   # how much time must elapse before a file can be declared inactive
                 cache_dir=None):            # if None, use dirname
        self.cdInit(logClass,dirname,log_prefix,log_suffix,cache_ext,inactive_files,inactive_timeout,cache_dir)

    def cdInit(self,logClass,
               dirname,log_prefix,log_suffix=".log",cache_ext=".cifpk",
               inactive_files=None,         # if ==None, will be reloaded from cache
               inactive_timeout=24*3600,    # how much time must elapse before a file can be declared inactive
               cache_dir=None):             # if None, use dirname
        self.logClass=logClass # this is an actual class, not an object
        self.dirname=dirname
        if cache_dir==None:
            cache_dir=dirname
        self.cache_dir=cache_dir
        self.log_prefix=log_prefix
        self.log_suffix=log_suffix
        self.inactive_timeout=inactive_timeout
        self.inactive_files_cache=os.path.join(cache_dir,log_prefix+log_suffix+cache_ext)
        if inactive_files==None:
            if os.path.isfile(self.inactive_files_cache):
                self.inactive_files=loadCache(self.inactive_files_cache)
            else:
                self.inactive_files=[]
        else:
            self.inactive_files=inactive_files
        return
    

    # return a list of log files
    def getFileList(self, active_only):
        prefix_len=len(self.log_prefix)
        suffix_len=len(self.log_suffix)
        files=[]
        fnames=os.listdir(self.dirname)
        for fname in fnames:
            if  ((fname[:prefix_len]==self.log_prefix) and
                 (fname[-suffix_len:]==self.log_suffix) and
                 ((not active_only) or (not (fname in self.inactive_files))) 
                 ):
                files.append(fname)
                pass
            pass
        return files

    # compare to cache, and tell if the log file has changed since last checked
    def has_changed(self):
        ch=False
        fnames=self.getFileList(active_only=True)
        for fname in fnames:
            obj=self.logClass(os.path.join(self.dirname,fname),self.cache_dir)
            ch=(ch or obj.has_changed()) # it is enough that one changes
        return ch

    
    def load(self,active_only=True):
        mydata=None
        new_inactives=[]

        # get list of log files
        fnames=self.getFileList(active_only)

        now=time.time()
        # load and merge data
        for fname in fnames:
            absfname=os.path.join(self.dirname,fname)
            if os.path.getsize(absfname)<1:
                continue # skip empty files
            last_mod=os.path.getmtime(absfname)
            obj=self.logClass(absfname,self.cache_dir)
            obj.load()
            mydata=obj.merge(mydata)
            if ((now-last_mod)>self.inactive_timeout) and (not obj.isActive()):
                new_inactives.append(fname)
                pass
            pass
        self.data=mydata

        # try to save inactive files in the cache
        # if one was looking at inactive only
        if active_only and (len(new_inactives)>0):
            self.inactive_files+=new_inactives
            try:
                saveCache(self.inactive_files_cache,self.inactive_files)
            except IOError:
                return # silently ignore, this was a load in the end

        return

    # diff self data with other info
    def diff(self,other):
        dummyobj=self.logClass(os.path.join(self.dirname,'dummy.txt'),self.cache_dir)
        dummyobj.data=self.data # a little rough but works
        return  dummyobj.diff(other) 
        
# this class will keep track of:
#  jobs in various of statuses (Wait, Idle, Running, Held, Completed, Removed)
# These data is available in self.data dictionary
# for example self.data={'Idle':['123.003','123.004'],'Running':['123.001','123.002']}
class dirSummary(cacheDirClass):
    def __init__(self,dirname,log_prefix,log_suffix=".log",cache_ext=".cifpk",
                 inactive_files=None,         # if ==None, will be reloaded from cache
                 inactive_timeout=24*3600,    # how much time must elapse before a file can be declared inactive
                 cache_dir=None):             # if None, use dirname
        self.cdInit(logSummary,dirname,log_prefix,log_suffix,cache_ext,inactive_files,inactive_timeout,cache_dir)


# this class will keep track of:
#  - counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
#  - list of completed jobs
# These data is available in self.data dictionary
#   for example self.data={'completed_jobs':['123.002','555.001'],'counts':{'Idle': 1145, 'Completed': 2}}
class dirCompleted(cacheDirClass):
    def __init__(self,dirname,log_prefix,log_suffix=".log",cache_ext=".cifpk",
                 inactive_files=None,         # if ==None, will be reloaded from cache
                 inactive_timeout=24*3600,    # how much time must elapse before a file can be declared inactive
                 cache_dir=None):             # if None, use dirname
        self.cdInit(logCompleted,dirname,log_prefix,log_suffix,cache_ext,inactive_files,inactive_timeout,cache_dir)


# this class will keep track of
#  counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
# These data is available in self.data dictionary
#   for example self.data={'Idle': 1145, 'Completed': 2}
class dirCounts(cacheDirClass):
    def __init__(self,dirname,log_prefix,log_suffix=".log",cache_ext=".cifpk",
                 inactive_files=None,         # if ==None, will be reloaded from cache
                 inactive_timeout=24*3600,    # how much time must elapse before a file can be declared inactive
                 cache_dir=None):             # if None, use dirname
        self.cdInit(logCounts,dirname,log_prefix,log_suffix,cache_ext,inactive_files,inactive_timeout,cache_dir)

# this class will keep track of:
#  jobs in various of statuses (Wait, Idle, Running, Held, Completed, Removed)
# These data is available in self.data dictionary
# for example self.data={'Idle':[('123.003','09/28 01:38:53', '09/28 01:42:23', '09/28 08:06:33'),('123.004','09/28 02:38:53', '09/28 02:42:23', '09/28 09:06:33')],'Running':[('123.001','09/28 01:32:53', '09/28 01:43:23', '09/28 08:07:33'),('123.002','09/28 02:38:53', '09/28 03:42:23', '09/28 06:06:33')]}
class dirSummaryTimings(cacheDirClass):
    def __init__(self,dirname,log_prefix,log_suffix=".log",cache_ext=".cifpk",
                 inactive_files=None,         # if ==None, will be reloaded from cache
                 inactive_timeout=24*3600,    # how much time must elapse before a file can be declared inactive
                 cache_dir=None):             # if None, use dirname
        self.cdInit(logSummaryTimings,dirname,log_prefix,log_suffix,cache_ext,inactive_files,inactive_timeout,cache_dir)



##############################################################################
#
# Low level functions
#
##############################################################################

################################
#  Condor log parsing functions
################################

# Status codes
# ------------
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
# 022 - Remote system diconnected 
# 023 - Remote system reconnected
# 024 - Remote system cannot recconect
# 025 - Grid Resource Back Up
# 026 - Detected Down Grid Resource
# 027 - Job submitted to grid resource
# 028 - Job ad information event triggered
# 029 - The job's remote status is unknown
# 030 - The job's remote status is known again

# Flags in the first char
# 0XX - No Flag
# YXX - Y is number of flags set

# will return the status to register to the job
def get_new_status(old_status,new_status):
    # keep the old status unless you really want to change
    status=old_status

    if new_status in ('019','020','025','026','022','023','010','011','029','030'):
        # these are intermediate states, so just flip a bit
        if new_status in ('020','026','022','010','029'): # connection lost
            status=str(int(old_status[0])+1)+old_status[1:]
        else:
            if old_status[0]!="0": # may have already fixed it, out of order
                status=str(int(old_status[0])-1)+old_status[1:]
            # else keep the old one
    elif old_status in ('003','006','008','028'):
        pass # do nothing, that was just informational
    else:
        # a significant status found, use it
        status=new_status
        
    return status

# read a condor submit log
# return a dictionary of jobStrings each having the last statusString
# for example {'1583.004': '000', '3616.008': '009'}
def parseSubmitLogFastRaw(fname):
    jobs={}
    
    size = os.path.getsize(fname)
    if size==0:
        # nothing to read, if empty
        return jobs
    
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

        if jobs.has_key(jobid):
            jobs[jobid]=get_new_status(jobs[jobid],status)
        else:
            jobs[jobid]=status

        i1=buf.find("...",idx)
        if i1<0:
            break
        idx=i1+4 #the 3 dots plus newline

    buf.close()
    fd.close()
    return jobs

# read a condor submit log
# return a dictionary of jobStrings
#  each having (the last statusString,firstTime,runningTime,lastTime)
# plus the first and last date in the file
# for example {'9568.001':('000', '09/28 01:38:53', '', '09/28 01:38:53'),'9868.003':('005', '09/28 01:48:52', '09/28 16:11:23', '09/28 20:31:53')},'09/28 01:38:53','09/28 20:31:53'
def parseSubmitLogFastRawTimings(fname):
    jobs={}

    first_time=None
    last_time=None
    
    size = os.path.getsize(fname)
    if size==0:
        # nothing to read, if empty
        return jobs,first_time,last_time
    
    fd=open(fname,"r")
    buf=mmap.mmap(fd.fileno(),size,access=mmap.ACCESS_READ)

    count=0
    idx=0

    while (idx+5)<size: # else we are at the end of the file
        # format
        # 023 (123.2332.000) MM/DD HH:MM:SS
        
        # first 3 chars are status
        status=buf[idx:idx+3]
        idx+=5
        # extract job id 
        i1=buf.find(")",idx)
        if i1<0:
            break
        jobid=buf[idx:i1-4]
        idx=i1+2
        #extract time
        line_time=buf[idx:idx+14]
        idx+=16

        if first_time==None:
            first_time=line_time
        last_time=line_time
            

        if jobs.has_key(jobid):
            if status=='001':
                running_time=line_time
            else:
                running_time=jobs[jobid][2]
            jobs[jobid]=(get_new_status(jobs[jobid][0],status),jobs[jobid][1],running_time,line_time) #start time never changes
        else:
            jobs[jobid]=(status,line_time,'',line_time)

        i1=buf.find("...",idx)
        if i1<0:
            break
        idx=i1+4 #the 3 dots plus newline

    buf.close()
    fd.close()
    return jobs,first_time,last_time

# read a condor submit log
# for each new event, call a callback
#   def callback(new_status_str,timestamp_str,job_str)
def parseSubmitLogFastRawCallback(fname,callback):
    jobs={}

    size = os.path.getsize(fname)
    if size==0:
        # nothing to read, if empty
        return

    fd=open(fname,"r")
    buf=mmap.mmap(fd.fileno(),size,access=mmap.ACCESS_READ)

    idx=0

    while (idx+5)<size: # else we are at the end of the file
        # format
        # 023 (123.2332.000) MM/DD HH:MM:SS
        
        # first 3 chars are status
        status=buf[idx:idx+3]
        idx+=5
        # extract job id 
        i1=buf.find(")",idx)
        if i1<0:
            break
        jobid=buf[idx:i1-4]
        idx=i1+2
        #extract time
        line_time=buf[idx:idx+14]
        idx+=16

        if jobs.has_key(jobid):
            new_status=get_new_status(jobs[jobid],status)
            if new_status!=status:
                callback(new_status,line_time,jobid)
                if new_status in ('005','009'):
                    del jobs[jobid] #end of live, don't need it anymore
                else:
                    jobs[jobid]=new_status
        else:
            jobs[jobid]=status
            callback(status,line_time,jobid)

        i1=buf.find("...",idx)
        if i1<0:
            break
        idx=i1+4 #the 3 dots plus newline

    buf.close()
    fd.close()
    return

# convert the log representation into (ClusterId,ProcessId)
# Return (-1,-1) in case of error
def rawJobId2Nr(str):
    arr=str.split(".")
    if len(arr)>=2:
        return (int(arr[0]),int(arr[1]))
    else:
        return (-1,-1) #invalid

# convert the log representation into ctime
# Return -1 in case of error
def rawTime2cTime(str,year):
    try:
        ctime=time.mktime((year,int(str[0:2]),int(str[3:5]),int(str[6:8]),int(str[9:11]),int(str[12:14]),0,0,-1))
    except ValueError:
        return -1 #invalid
    return ctime

# convert the log representation into ctime
# works only for the past year
# Return -1 in case of error
def rawTime2cTimeLastYear(str):
    now=time.time()
    current_year=time.localtime(now)[0]
    ctime=rawTime2cTime(str,current_year)
    if ctime<=now:
        return ctime
    else: # cannot be in the future... it must have been in the past year
        ctime=rawTime2cTime(str,current_year-1)
        return ctime

# get two condor time strings and compute the difference
# the fist must be before the end one
def diffTimes(start_time,end_time,year):
    start_ctime=rawTime2cTime(start_time,year)
    end_ctime=rawTime2cTime(end_time,year)
    if (start_time<0) or (end_time<0):
        return -1 #invalid
    
    return int(end_ctime)-int(start_ctime)

# get two condor time strings and compute the difference
# the fist must be before the end one
def diffTimeswWrap(start_time,end_time,year,wrap_time):
    if start_time>wrap_time:
        start_year=year
    else:
        start_year=year+1
    start_ctime=rawTime2cTime(start_time,start_year)

    if end_time>wrap_time:
        end_year=year
    else:
        end_year=year+1
    end_ctime=rawTime2cTime(end_time,end_year)
    
    if (start_time<0) or (end_time<0):
        return -1 #invalid

    return int(end_ctime)-int(start_ctime)

# reduce the syayus to either Wait, Idle, Running, Held, Completed or Removed
def interpretStatus(status,default_status='Idle'):
    if status==5:
        return "Completed"
    elif status==9:
        return "Removed"
    elif status==1:
        return "Running"
    elif status==12:
        return "Held"
    elif status==0:
        return "Wait"
    elif status==17:
        return "Idle"
    else:
        return default_status

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
        i_s=interpretStatus(int(s[1:])) # ignore flags
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
        except: # there are only a few possible values, so using exceptions for initialization is faster
            status[e]=[k]
    return status

# given a dictionary of job statuses + timings (like the one got from parseSubmitLogFastRawTimings)
# will return a dictionary of jobs +timings in each status
# for example: {'009': [("1.003",'09/28 01:38:53', '', '09/28 01:38:53'),("2.001",'09/28 03:38:53', '', '09/28 04:38:53')], '005': [("1503.001", '09/28 01:48:52', '09/28 16:11:23', '09/28 20:31:53'),("1555.002", '09/28 02:48:52', '09/28 18:11:23', '09/28 23:31:53')]}
def listStatusesTimings(jobs):
    status={}
    for k,e in jobs.items():
        try:
            status[e[0]].append((k,)+e[1:])
        except: # there are only a few possible values, so using exceptions for initialization is faster
            status[e[0]]=[(k,)+e[1:]]
    return status

# given a dictionary of job statuses (whatever the invert_function recognises)
# will return a dictionary of jobs in each status (syntax depends on the invert_function)
# for example with linvert_funtion==istStatuses:
#   {'Completed': ["2.003","5.001"], 'Removed': ["41.001"], 'Running': ["408.003"]}
def listAndInterpretRawStatuses(jobs_raw,invert_function):
    outc={}
    tmpc=invert_function(jobs_raw)
    for s in tmpc.keys():
        try:
          i_s=interpretStatus(int(s[1:])) #ignore flags
        except: # file corrupted, protect
         #print "lairs: Unexpect line: %s"%s
         continue
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

# read a condor submit log
# return a dictionary of jobIds
#  each having (the last status, seconds in queue, if status==5, seconds running)
# for example {(1583,4)': (0,345,None), (3616,8): (5,7777,4532)}
def parseSubmitLogFastTimings(fname,year=None): # if no year, then use the current one
    jobs_raw,first_time,last_time=parseSubmitLogFastRawTimings(fname)

    if year==None:
        year=time.localtime()[0]

    # it wrapped over, dates really in previous year
    year_wrap=(first_time>last_time)
    
    jobs={}
    if year_wrap:
        year1=year-1
        for k in jobs_raw.keys():
            el=jobs_raw[k]
            status=int(el[0])
            diff_time=diffTimeswWrap(el[1],el[3],year1,first_time)
            if status==5:
                running_time=diffTimeswWrap(el[2],el[3],year1,first_time)
            else:
                running_time=None
            jobs[rawJobId2Nr(k)]=(status,diff_time,running_time)
    else:
        for k in jobs_raw.keys():
            el=jobs_raw[k]
            status=int(el[0])
            diff_time=diffTimes(el[1],el[3],year)
            if status==5:
                running_time=diffTimes(el[2],el[3],year)
            else:
                running_time=None
            jobs[rawJobId2Nr(k)]=(status,diff_time,running_time)
        
    return jobs

################################
#  Cache handling functions
################################

def loadCache(fname):
    fd=open(fname,"r")
    data=cPickle.load(fd)
    fd.close()
    return data

def saveCache(fname,data):
    # two steps; first create a tmp file, then rename
    tmpname=fname+(".tmp_%i"%os.getpid())
    fd=open(tmpname,"w")
    cPickle.dump(data,fd)
    fd.close()

    try:
        os.remove(fname)
    except:
        pass # may not exist
    os.rename(tmpname,fname)
        
    return
