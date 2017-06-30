#
# Project:
#   glideinWMS
#
# File Version: 
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

import os
import os.path
import stat
import re
import mmap
import time

import util


# -------------- Single Log classes ------------------------

class cachedLogClass:
    """
    This is the base class for most Log Parsers in lib/condorLogParser
    and factory/glideFactoryLogParser. (I{virtual, do not use})
    
    The Constructor for inherited classes needs to define logname and cachename 
    (possibly by using clInit) as well as the methods
     loadFromLog, merge and isActive.
    init method to be used by real constructors
    """
    def clInit(self, logname, cache_dir, cache_ext):
        self.logname = logname
        if cache_dir is None:
            self.cachename = logname + cache_ext
        else:
            self.cachename = os.path.join(cache_dir, os.path.basename(logname)+cache_ext)

    def has_changed(self):
        """
        Compare to cache, and tell if the log file has changed 
        since last checked
        """
        if os.path.isfile(self.logname):
            fstat = os.lstat(self.logname)
            logtime = fstat[stat.ST_MTIME]
        else:
            return False  # does not exist, so it could not change
        
        if os.path.isfile(self.cachename):
            fstat = os.lstat(self.cachename)
            cachetime = fstat[stat.ST_MTIME]
        else:
            return True  # no cache, so it has changed for sure
        
        # both exist -> check if log file is newer
        return (logtime > cachetime)

    def load(self):
        """
        Load data from most recent file. Update the cache if needed.
        If the file has not changed, use the cache instead
        (typically named something like filename.ftstpk) in a pickle format.
        If file is newer, uses inherited class's loadFromLog method.
        Then, save in pickle cache.
        """
        if not self.has_changed():
            # cache is newer, just load the cache
            return self.loadCache()

        while True:  # could need more than one loop if the log file is changing
            fstat = os.lstat(self.logname)
            start_logtime = fstat[stat.ST_MTIME]
            del fstat
            
            self.loadFromLog()
            try:
                self.saveCache()
            except IOError:
                return  # silently ignore, this was a load in the end
            # the log may have changed -> check
            fstat = os.lstat(self.logname)
            logtime = fstat[stat.ST_MTIME]
            del fstat
            if logtime <= start_logtime:
                return  # OK, not changed, can exit
        
        return  # should never reach this point
        
    def loadCache(self):
        self.data = loadCache(self.cachename)
        return

    def loadFromLog(self):
        raise RuntimeError('loadFromLog not implemented!')
    
    ####### PRIVATE ###########
    def saveCache(self):
        saveCache(self.cachename, self.data)
        return

        
class logSummary(cachedLogClass):
    """
    This class will keep track of:
    jobs in various of statuses (Wait, Idle, Running, Held, Completed, Removed)
    This data is available in self.data dictionary
    for example 
    self.data={'Idle':['123.003','123.004'],'Running':['123.001','123.002']}
    """

    def __init__(self, logname, cache_dir):
        self.clInit(logname, cache_dir, ".cstpk")

    def loadFromLog(self):
        """
        Parse the condor activity log and interpret the globus status code.
        Stores in self.data
        """
        jobs = parseSubmitLogFastRaw(self.logname)
        self.data = listAndInterpretRawStatuses(jobs, listStatuses)
        return

    def isActive(self):
        active = False
        for k in self.data.keys():
            if not (k in ['Completed', 'Removed']):
                if len(self.data[k]) > 0:
                    active = True # it is enought that at least one non Completed/removed job exist
        return active

    def merge(self, other):
        """
        Merge self data with other info
        @return: merged data, may modify other
        """
        if other is None:
            return self.data
        elif self.data is None:
            return other
        else:
            for k in self.data.keys():
                try:
                    other[k] += self.data[k]
                except: # missing key
                    other[k] = self.data[k]
            return other

    def diff(self, other):
        """
        diff self data with other info.  Used to compare
        previous iteration with current iteration
        
        Performs symmetric difference on the two sets and
        creates a dictionary for each status.

        @return: data[status]['Entered'|'Exited'] - list of jobs
        """
        if other is None:
            outdata={}
            if self.data is not None:
                for k in self.data.keys():
                    outdata[k] = {'Exited':[], 'Entered':self.data[k]}
            return outdata
        elif self.data is None:
            outdata = {}
            for k in other.keys():
                outdata[k] = {'Entered':[], 'Exited':other[k]}
            return outdata
        else:
            outdata = {}
            
            keys = {} # keys will contain the merge of the two lists
            
            for s in (self.data.keys() + other.keys()):
                keys[s] = None

            for s in keys.keys():
                if s in self.data:
                    sel = self.data[s]
                else:
                    sel = []
                    
                if s in other:
                    oel = other[s]
                else:
                    oel = []

                outdata_s = {'Entered':[], 'Exited':[]}
                outdata[s] = outdata_s

                sset = set(sel)
                oset = set(oel)

                outdata_s['Entered'] = list(sset.difference(oset))
                outdata_s['Exited'] = list(oset.difference(sset))
            return outdata
            

class logCompleted(cachedLogClass):
    """
    This class will keep track of:
        - counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
        - list of completed jobs
    This data is available in self.data dictionary

    For example self.data=
    {'completed_jobs':['123.002','555.001'],
    'counts':{'Idle': 1145, 'Completed': 2}}
    """
    def __init__(self, logname, cache_dir):
        self.clInit(logname, cache_dir, ".clspk")

    def loadFromLog(self):
        """
        Load information from condor_activity logs
        Then parse globus statuses.
        Finally, parse and add counts.
        """
        tmpdata={}
        jobs = parseSubmitLogFastRaw(self.logname)
        status  = listAndInterpretRawStatuses(jobs, listStatuses)
        counts = {}
        for s in status.keys():
            counts[s] = len(status[s])
        tmpdata['counts'] = counts
        if "Completed" in status:
            tmpdata['completed_jobs'] = status['Completed']
        else:
            tmpdata['completed_jobs'] = []
        self.data = tmpdata
        return

    def isActive(self):
        active = False
        counts = self.data['counts']
        for k in counts.keys():
            if not (k in ['Completed', 'Removed']):
                if counts[k] > 0:
                    # Enough that at least one non Completed/removed job exist
                    active = True
        return active


    def merge(self, other):
        """
        Merge self data with other info
        @return: merged data, may modify other
        """
        if other is None:
            return self.data
        elif self.data is None:
            return other
        else:
            for k in self.data['counts'].keys():
                try:
                    other['counts'][k] += self.data['counts'][k]
                except: # missing key
                    other['counts'][k] = self.data['counts'][k]
            other['completed_jobs'] += self.data['completed_jobs']
            return other


    def diff(self, other):
        """
        Diff self.data with other info.
        For use in comparing previous iteration with current iteration

        Uses symmetric difference of sets.
        """
        if other is None:
            if self.data is not None:
                outcj={'Exited':[],'Entered':self.data['completed_jobs']}
                outdata={'counts':self.data['counts'],'completed_jobs':outcj}
            else:
                outdata = { 'counts':{},
                            'completed_jobs':{'Exited':[], 'Entered':[]}
                          }
            return outdata
        elif self.data is None:
            outcj = {'Entered':[], 'Exited':other['completed_jobs']}
            outct = {}
            for s in other['counts'].keys():
                outct[s] = -other['counts'][s]
            outdata = {'counts':outct, 'completed_jobs':outcj}
            return outdata
        else:
            outct = {}
            outcj = {'Entered':[], 'Exited':[]}
            outdata = {'counts':outct, 'completed_jobs':outcj}

            keys = {} # keys will contain the merge of the two lists
            for s in (self.data['counts'].keys() + other['counts'].keys()):
                keys[s] = None

            for s in keys.keys():
                if s in self.data['counts']:
                    sct = self.data['counts'][s]
                else:
                    sct = 0
                    
                if s in other['counts']:
                    oct = other['counts'][s]
                else:
                    oct = 0

                outct[s] = sct - oct

            sel = self.data['completed_jobs']
            oel = other['completed_jobs']
            sset = set(sel)
            oset = set(oel)

            outcj['Entered'] = list(sset.difference(oset))
            outcj['Exited'] = list(oset.difference(sset))

            return outdata

class logCounts(cachedLogClass):
    """
    This class will keep track of
    counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
    This data is available in self.data dictionary
    For example self.data={'Idle': 1145, 'Completed': 2}
    """

    def __init__(self, logname, cache_dir):
        self.clInit(logname, cache_dir, ".clcpk")

    def loadFromLog(self):
        jobs = parseSubmitLogFastRaw(self.logname)
        self.data = countAndInterpretRawStatuses(jobs)
        return

    def isActive(self):
        active = False
        for k in self.data.keys():
            if not (k in ['Completed', 'Removed']):
                if self.data[k] > 0:
                    # Enough that at least one non Completed/removed job exist
                    active = True
        return active


    def merge(self, other):
        """
        Merge self data with other info
        @return: merged data, may modify other
        """
        if other is None:
            return self.data
        elif self.data is None:
            return other
        else:
            for k in self.data.keys():
                try:
                    other[k] += self.data[k]
                except: # missing key
                    other[k] = self.data[k]
            return other

    def diff(self, other):
        """
        Diff self data with other info
        @return: diff of counts
        """
        if other is None:
            if self.data is not None:
                return self.data
            else:
                return {}
        elif self.data is None:
            outdata = {}
            for s in other.keys():
                outdata[s] = -other[s]
            return outdata
        else:
            outdata = {}
            
            keys = {} # keys will contain the merge of the two lists
            for s in (self.data.keys() + other.keys()):
                keys[s] = None

            for s in keys.keys():
                if s in self.data:
                    sel = self.data[s]
                else:
                    sel = 0
                    
                if s in other:
                    oel = other[s]
                else:
                    oel = 0

                outdata[s] = sel - oel

            return outdata

class logSummaryTimings(cachedLogClass):
    """
    This class will keep track of:
    jobs in various of statuses (Wait, Idle, Running, Held, Completed, Removed)
    This data is available in self.data dictionary
    for example 
    self.data={'Idle':['123.003','123.004'],'Running':['123.001','123.002']}
    """

    def __init__(self, logname, cache_dir):
        self.clInit(logname, cache_dir, ".ctstpk")

    def loadFromLog(self):
        jobs, self.startTime, self.endTime = parseSubmitLogFastRawTimings(self.logname)
        self.data = listAndInterpretRawStatuses(jobs, listStatusesTimings)
        return

    def isActive(self):
        active = False
        for k in self.data.keys():
            if not (k in ['Completed', 'Removed']):
                if len(self.data[k]) > 0:
                    # Enough that at least one non Completed/removed job exist
                    active = True
        return active

    def merge(self, other):
        """
        merge self data with other info
        @return: merged data, may modify other
        """
        if other is None:
            return self.data
        elif self.data is None:
            return other
        else:
            for k in self.data.keys():
                try:
                    other[k] += self.data[k]
                except: # missing key
                    other[k] = self.data[k]
            return other

    def diff(self, other):
        """
        diff self data with other info
        @return: data[status]['Entered'|'Exited'] - list of jobs
        """
        if other is None:
            outdata={}
            if self.data is not None:
                for k in self.data.keys():
                    outdata[k] = {'Exited':[], 'Entered':self.data[k]}
            return outdata
        elif self.data is None:
            outdata = {}
            for k in other.keys():
                outdata[k] = {'Entered':[], 'Exited':other[k]}
            return outdata
        else:
            outdata = {}
            
            keys = {} # keys will contain the merge of the two lists
            
            for s in (self.data.keys() + other.keys()):
                keys[s] = None

            for s in keys.keys():
                sel = []
                if s in self.data:
                    for sel_e in self.data[s]:
                        sel.append(sel_e[0])

                oel = []
                if s in other:
                    for oel_e in other[s]:
                        oel.append(oel_e[0])


                #################
                # Need to finish

                outdata_s = {'Entered':[], 'Exited':[]}
                outdata[s] = outdata_s

                sset = set(sel)
                oset = set(oel)

                entered_set = sset.difference(oset)
                entered = []
                if s in self.data:
                    for sel_e in self.data[s]:
                        if sel_e[0] in entered_set:
                            entered.append(sel_e)

                exited_set = oset.difference(sset)
                exited = []
                if s in other:
                    for oel_e in other[s]:
                        if oel_e[0] in exited_set:
                            exited.append(oel_e)


                outdata_s['Entered'] = entered
                outdata_s['Exited'] = exited
            return outdata
            
# -------------- Multiple Log classes ------------------------

class cacheDirClass:
    """
    This is the base class for all the directory log Parser
    classes.  It parses some/all log files in a directory.
    It should generally not be called directly.  Rather,
    call one of the inherited classes.
    """
    def __init__(self, logClass, dirname, log_prefix, log_suffix=".log",
                 cache_ext=".cifpk", inactive_files=None,
                 inactive_timeout=24*3600, cache_dir=None,
                 wrapperClass=None,username=None):
        """
        @param inactive_files: if None, will be reloaded from cache
        @param inactive_timeout: how much time must elapse before a file can be declared inactive
        @param cache_dir: If None, use dirname for the cache directory.
        """
        self.cdInit(logClass, dirname, log_prefix, log_suffix, cache_ext,
                    inactive_files, inactive_timeout, cache_dir,
                    wrapperClass=wrapperClass, username=username)

    def cdInit(self, logClass, dirname, log_prefix, log_suffix=".log",
               cache_ext=".cifpk", inactive_files=None,
               inactive_timeout=24*3600, cache_dir=None,
               wrapperClass=None,username=None):
        """
        @param logClass: this is an actual class, not an object
        @param inactive_files: if None, will be reloaded from cache
        @param inactive_timeout: how much time must elapse before a file can be
declared inactive
        @param cache_dir: If None, use dirname for the cache directory.
        """

        self.wrapperClass=wrapperClass
        self.username=username

        self.logClass=logClass
        self.dirname=dirname
        if cache_dir is None:
            cache_dir=dirname
        self.cache_dir=cache_dir
        self.log_prefix=log_prefix
        self.log_suffix=log_suffix
        self.inactive_timeout=inactive_timeout
        self.inactive_files_cache=os.path.join(cache_dir, log_prefix+log_suffix+cache_ext)
        if inactive_files is None:
            if os.path.isfile(self.inactive_files_cache):
                self.inactive_files = loadCache(self.inactive_files_cache)
            else:
                self.inactive_files = []
        else:
            self.inactive_files = inactive_files
        return
    

    def getFileList(self, active_only):
        """
        Lists the directory and returns files that match the
        prefix/suffix extensions and are active (modified within
        inactivity_timeout)

        @return: a list of log files
        """

        prefix_len=len(self.log_prefix)
        suffix_len=len(self.log_suffix)
        files=[]
        fnames=os.listdir(self.dirname)
        for fname in fnames:
            if  ((fname[:prefix_len] == self.log_prefix) and
                 (fname[-suffix_len:] == self.log_suffix) and
                 ((not active_only) or (not (fname in self.inactive_files))) 
                 ):
                files.append(fname)
        return files

    def has_changed(self):
        """
        Checks all the files in the list to see if any 
        have changed.

        @return: True/False
        """

        ch=False
        fnames=self.getFileList(active_only=True)
        for fname in fnames:
            if (self.wrapperClass is not None) and (self.username is not None):
                obj = self.wrapperClass.getObj(
                          logname=os.path.join(self.dirname, fname),
                          cache_dir=self.cache_dir,
                          username=self.username)
            else:
                obj=self.logClass(os.path.join(self.dirname, fname),
                                  self.cache_dir)

            ch=(ch or obj.has_changed()) # it is enough that one changes
        return ch

    
    def load(self,active_only=True):
        """
        For each file in the filelist, call the appropriate load()
        function for that file.  Merge all the data from all the files
        into temporary array mydata then set it to self.data.
        It will save the list of inactive_files it finds in a cache
        for quick access.

        This function should set self.data.
        """

        mydata=None
        new_inactives=[]

        # get list of log files
        fnames = self.getFileList(active_only)

        now = time.time()
        # load and merge data
        for fname in fnames:
            absfname=os.path.join(self.dirname, fname)
            if os.path.getsize(absfname)<1:
                continue # skip empty files
            last_mod=os.path.getmtime(absfname)
            if (self.wrapperClass is not None) and (self.username is not None):
                obj=self.wrapperClass.getObj(logname=absfname,
                                             cache_dir=self.cache_dir,
                                             username=self.username)
            else:
                obj=self.logClass(absfname, self.cache_dir)
            obj.load()
            mydata = obj.merge(mydata)
            if ( ((now-last_mod) > self.inactive_timeout) and 
                 (not obj.isActive()) ):
                new_inactives.append(fname)
        self.data = mydata

        # try to save inactive files in the cache
        # if one was looking at inactive only
        if active_only and (len(new_inactives)>0):
            self.inactive_files += new_inactives
            try:
                saveCache(self.inactive_files_cache, self.inactive_files)
            except IOError:
                return # silently ignore, this was a load in the end

        return

    def diff(self, other):
        """
        Diff self data with other info
        
        This is a virtual function that just calls the class 
        diff() function.
        """

        if (self.wrapperClass is not None) and (self.username is not None):
            dummyobj=self.wrapperClass.getObj(os.path.join(self.dirname,
                                                           'dummy.txt'),
                                              self.cache_dir, self.username)
        else:
            dummyobj=self.logClass(os.path.join(self.dirname, 'dummy.txt'),
                                   self.cache_dir)

        dummyobj.data=self.data # a little rough but works
        return  dummyobj.diff(other) 
        
class dirSummary(cacheDirClass):
    """
    This class will keep track of:
    jobs in various of statuses (Wait, Idle, Running, Held, Completed, Removed)
    This data is available in self.data dictionary
    For example, 
    self.data={'Idle':['123.003','123.004'],'Running':['123.001','123.002']}
    """

    def __init__(self,dirname,log_prefix,log_suffix=".log",cache_ext=".cifpk",
                 inactive_files=None,
                 inactive_timeout=24*3600,
                 cache_dir=None):
        """
        @param inactive_files: if ==None, will be reloaded from cache
        @param inactive_timeout: how much time must elapse before
        @param cache_dir: if None, use dirname
        """

        self.cdInit(logSummary, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir)


class dirCompleted(cacheDirClass):
    """
    This class will keep track of:
        - counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
        - list of completed jobs
    This data is available in self.data dictionary
    for example 
    self.data={'completed_jobs':['123.002','555.001'],
    'counts':{'Idle': 1145, 'Completed': 2}}
    """

    def __init__(self,dirname,log_prefix,log_suffix=".log",cache_ext=".cifpk",
                 inactive_files=None,
                 inactive_timeout=24*3600,
                 cache_dir=None):
        """
        @param inactive_files: if ==None, will be reloaded from cache
        @param inactive_timeout: how much time must elapse before
        @param cache_dir: if None, use dirname
        """

        self.cdInit(logCompleted, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir)


class dirCounts(cacheDirClass):
    """
    This class will keep track of
    counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
    These data is available in self.data dictionary
    for example self.data={'Idle': 1145, 'Completed': 2}
    """

    def __init__(self,dirname,log_prefix,log_suffix=".log",cache_ext=".cifpk",
                 inactive_files=None,
                 inactive_timeout=24*3600,
                 cache_dir=None):
        """
        @param inactive_files: if ==None, will be reloaded from cache
        @param inactive_timeout: how much time must elapse before
        @param cache_dir: if None, use dirname
        """

        self.cdInit(logCounts, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir)

class dirSummaryTimings(cacheDirClass):
    """
    This class will keep track of:
    jobs in various of statuses (Wait, Idle, Running, Held, Completed, Removed)
    This data is available in self.data dictionary
    For example self.data={'Idle':[('123.003','09/28 01:38:53', 
    '09/28 01:42:23', '09/28 08:06:33'),('123.004','09/28 02:38:53', 
    '09/28 02:42:23', '09/28 09:06:33')],
    'Running':[('123.001','09/28 01:32:53', '09/28 01:43:23', 
    '09/28 08:07:33'),('123.002','09/28 02:38:53', '09/28 03:42:23', 
    '09/28 06:06:33')]}
    """

    def __init__(self,dirname,log_prefix,log_suffix=".log",cache_ext=".cifpk",
                 inactive_files=None,
                 inactive_timeout=24*3600,
                 cache_dir=None):
        """
        @param inactive_files: if ==None, will be reloaded from cache
        @param inactive_timeout: how much time must elapse before
        @param cache_dir: if None, use dirname
        """

        self.cdInit(logSummaryTimings, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir)



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

def get_new_status(old_status, new_status):
    """
    Given a job with an old and new status,
    will return the appropriate status to register to the job.

    @param old_status: Globus job status
    @param new_status: Globus job status
    @return: Appropriate status for the job
    """

    # keep the old status unless you really want to change
    status = old_status

    if new_status in ('019', '020', '025', '026', '022', '023', '010', '011', '029', '030'):
        # these are intermediate states, so just flip a bit
        if new_status in ('020', '026', '022', '010', '029'): # connection lost
            status = str(int(old_status[0]) + 1) + old_status[1:]
        else:
            if old_status[0] != "0": # may have already fixed it, out of order
                status = str(int(old_status[0]) - 1) + old_status[1:]
            # else keep the old one
    elif new_status in ('004', '007', '024'):
        # this is an abort... back to idle/wait
        status='000'
    elif new_status in ('003', '006', '008', '028'):
        pass # do nothing, that was just informational
    else:
        # a significant status found, use it
        status = new_status
        
    return status

def parseSubmitLogFastRaw(fname):
    """
    Read a condor submit log.

    @return: a dictionary of jobStrings each having the last statusString
    For example {'1583.004': '000', '3616.008': '009'}
    """

    jobs={}
    
    size = os.path.getsize(fname)
    if size==0:
        # nothing to read, if empty
        return jobs
    
    fd=open(fname, "r")
    buf=mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)

    idx = 0

    while (idx+5) < size: # else we are at the end of the file
        # format
        # 023 (123.2332.000) Bla
        
        # first 3 chars are status
        status = buf[idx:idx+3]
        idx += 5
        # extract job id 
        i1 = buf.find(")", idx)
        if i1 < 0:
            break
        jobid = buf[idx:i1-4]
        idx = i1 + 1

        if jobid in jobs:
            jobs[jobid] = get_new_status(jobs[jobid], status)
        else:
            jobs[jobid] = status

        i1 = buf.find("...", idx)
        if i1 < 0:
            break
        idx = i1 + 4 #the 3 dots plus newline

    buf.close()
    fd.close()
    return jobs

def parseSubmitLogFastRawTimings(fname):
    """
    Read a condor submit log.  Returns a dictionary of jobStrings
    each having (the last statusString,firstTime,runningTime,lastTime)
    plus the first and last date in the file

    for example {'9568.001':('000', '09/28 01:38:53', '', '09/28 01:38:53'),'9868.003':('005', '09/28 01:48:52', '09/28 16:11:23', '09/28 20:31:53')},'09/28 01:38:53','09/28 20:31:53'

    @return: a dictionary of jobStrings
    """

    jobs = {}

    first_time = None
    last_time = None
    
    size = os.path.getsize(fname)
    if size==0:
        # nothing to read, if empty
        return jobs, first_time, last_time
    
    fd=open(fname, "r")
    buf=mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)

    idx = 0

    while (idx + 5) < size: # else we are at the end of the file
        # format
        # 023 (123.2332.000) MM/DD HH:MM:SS
        
        # first 3 chars are status
        status = buf[idx:idx+3]
        idx += 5
        # extract job id 
        i1 = buf.find(")", idx)
        if i1 < 0:
            break
        jobid = buf[idx:i1-4]
        idx = i1 + 2
        #extract time
        line_time = buf[idx:idx+14]
        idx += 16

        if first_time is None:
            first_time = line_time
        last_time = line_time
            
        if jobid in jobs:
            if status == '001':
                running_time = line_time
            else:
                running_time = jobs[jobid][2]
            jobs[jobid] = (get_new_status(jobs[jobid][0], status), jobs[jobid][1], running_time, line_time) #start time never changes
        else:
            jobs[jobid] = (status, line_time, '', line_time)

        i1 = buf.find("...", idx)
        if i1 < 0:
            break
        idx = i1 + 4 #the 3 dots plus newline

    buf.close()
    fd.close()
    return jobs, first_time, last_time

def parseSubmitLogFastRawCallback(fname, callback):
    """
    Read a condor submit log
    for each new event, call a callback
   
    @param fname: Condor submit file to parse 
    @param callname: def callback(new_status_str,timestamp_str,job_str)
    """

    jobs = {}

    size = os.path.getsize(fname)
    if size==0:
        # nothing to read, if empty
        return

    fd=open(fname, "r")
    buf=mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)

    idx = 0

    while (idx+5) < size: # else we are at the end of the file
        # format
        # 023 (123.2332.000) MM/DD HH:MM:SS
        
        # first 3 chars are status
        status = buf[idx:idx+3]
        idx += 5
        # extract job id 
        i1 = buf.find(")", idx)
        if i1 < 0:
            break
        jobid = buf[idx:i1-4]
        idx = i1 + 2
        #extract time
        line_time = buf[idx:idx+14]
        idx += 16

        if jobid in jobs:
            old_status=jobs[jobid]
            new_status = get_new_status(old_status, status)
            if new_status != old_status:
                callback(new_status, line_time, jobid)
                if new_status in ('005', '009'):
                    del jobs[jobid] #end of live, don't need it anymore
                else:
                    jobs[jobid] = new_status
        else:
            jobs[jobid] = status
            callback(status, line_time, jobid)

        i1 = buf.find("...", idx)
        if i1 < 0:
            break
        idx = i1 + 4 #the 3 dots plus newline

    buf.close()
    fd.close()
    return

def rawJobId2Nr(str):
    """
    Convert the log representation into (ClusterId,ProcessId)
    
    Return (-1,-1) in case of error
    """
    arr=str.split(".")
    if len(arr)>=2:
        return (int(arr[0]), int(arr[1]))
    else:
        return (-1, -1) #invalid

def rawTime2cTime(instr, year):
    """
    Convert the log representation into ctime

    @return: ctime or -1 in case of error
    """
    try:
        ctime = time.mktime((year, int(instr[0:2]), int(instr[3:5]), int(instr[6:8]), int(instr[9:11]), int(instr[12:14]), 0, 0, -1))
    except ValueError:
        return -1 #invalid
    return ctime

def rawTime2cTimeLastYear(instr):
    """
    Convert the log representation into ctime,
    works only for the past year

    @return: ctime or -1 in case of error
    """
    now=time.time()
    current_year=time.localtime(now)[0]
    ctime=rawTime2cTime(instr, current_year)
    if ctime<=now:
        return ctime
    else: # cannot be in the future... it must have been in the past year
        ctime = rawTime2cTime(instr, current_year-1)
        return ctime

def diffTimes(start_time, end_time, year):
    """
    Get two condor time strings and compute the difference
    The start_time must be before the end_time
    """
    start_ctime=rawTime2cTime(start_time, year)
    end_ctime=rawTime2cTime(end_time, year)
    if (start_time<0) or (end_time<0):
        return -1 #invalid
    
    return int(end_ctime) - int(start_ctime)

def diffTimeswWrap(start_time, end_time, year, wrap_time):
    """
    Get two condor time strings and compute the difference
    The start_time must be before the end_time
    """
    if start_time>wrap_time:
        start_year=year
    else:
        start_year = year + 1
    start_ctime = rawTime2cTime(start_time, start_year)

    if end_time > wrap_time:
        end_year = year
    else:
        end_year = year + 1
    end_ctime = rawTime2cTime(end_time, end_year)
    
    if (start_time<0) or (end_time<0):
        return -1 #invalid

    return int(end_ctime) - int(start_ctime)

def interpretStatus(status,default_status='Idle'):
    """
    Transform a integer globus status to 
    either Wait, Idle, Running, Held, Completed or Removed
    """
    if status==5:
        return "Completed"
    elif status == 9:
        return "Removed"
    elif status == 1:
        return "Running"
    elif status == 12:
        return "Held"
    elif status == 0:
        return "Wait"
    elif status == 17:
        return "Idle"
    else:
        return default_status

def countStatuses(jobs):
    """
    Given a dictionary of job statuses 
    (like the one got from parseSubmitLogFastRaw)
    will return a dictionary of sstatus counts

    for example: {'009': 25170, '012': 418, '005': 1503}
    """

    counts={}
    for e in jobs.values():
        try:
            counts[e] += 1
        except: 
            # there are only few possible values, so exceptions is faster
            counts[e] = 1
    return counts

def countAndInterpretRawStatuses(jobs_raw):
    """
    Given a dictionary of job statuses 
    (like the one got from parseSubmitLogFastRaw)
    will return a dictionary of status counts

    for example: {'Completed': 30170, 'Removed': 148, 'Running': 5013}

    @param jobs_raw: Dictionary of job statuses
    @return: Dictionary of status counts
    """

    outc={}
    tmpc=countStatuses(jobs_raw)
    for s in tmpc.keys():
        i_s = interpretStatus(int(s[1:])) # ignore flags
        try:
            outc[i_s] += tmpc[s]
        except:  
            # there are only few possible values, using exceptions is faster
            outc[i_s] = tmpc[s]
    return outc

def listStatuses(jobs):
    """
    Given a dictionary of job statuses 
    (like the one got from parseSubmitLogFastRaw)
    will return a dictionary of jobs in each status

    For example: {'009': ["1.003","2.001"], '012': ["418.001"], '005': ["1503.001","1555.002"]}

    @param jobs: Dictionary of job statuses
    @return: Dictionary of jobs in each status category
    """

    status={}
    for k, e in jobs.items():
        try:
            status[e].append(k)
        except: 
            # there are only few possible values, using exceptions is faster
            status[e] = [k]
    return status

def listStatusesTimings(jobs):
    """
    Given a dictionary of job statuses + timings 
    (like the one got from parseSubmitLogFastRawTimings)
    will return a dictionary of jobs +timings in each status

    For example: {'009': [("1.003",'09/28 01:38:53', '', '09/28 01:38:53'),("2.001",'09/28 03:38:53', '', '09/28 04:38:53')], '005': [("1503.001", '09/28 01:48:52', '09/28 16:11:23', '09/28 20:31:53'),("1555.002", '09/28 02:48:52', '09/28 18:11:23', '09/28 23:31:53')]}

    @param jobs: Dictionary of job statuses and timings
    @return: Dictionary of jobs+timings in each status category
    """

    status={}
    for k, e in jobs.items():
        try:
            status[e[0]].append((k,)+e[1:])
        except:
            # there are only few possible values, using exceptions is faster
            status[e[0]] = [(k,)+e[1:]]
    return status

def listAndInterpretRawStatuses(jobs_raw, invert_function):
    """
    Given a dictionary of job statuses 
    (whatever the invert_function recognises)
    will return a dictionary of jobs in each status 
    (syntax depends on the invert_function)

    for example with linvert_funtion==istStatuses:
    {'Completed': ["2.003","5.001"], 'Removed': ["41.001"], 
    'Running': ["408.003"]}

    @param jobs_raw: A dictionary of job statuses
    @param invert_function: function to turn a job status into "Completed","Removed","Running", etc
    @return: Dictionary of jobs in each category.
    """

    outc={}
    tmpc=invert_function(jobs_raw)
    for s in tmpc.keys():
        try:
            i_s = interpretStatus(int(s[1:])) #ignore flags
        except: # file corrupted, protect
            #print "lairs: Unexpect line: %s"%s
            continue
        try:
            outc[i_s] += tmpc[s]
        except:
            # there are only few possible values, using exceptions is faster
            outc[i_s] = tmpc[s]
    return outc

def parseSubmitLogFast(fname):
    """
    Reads a Condor submit log, return a dictionary of jobIds
    each having the last status.

    For example {(1583,4)': 0, (3616,8): 9}

    @param fname: filename to parse
    @return: Dictionary of jobIDs and last status
    """

    jobs_raw=parseSubmitLogFastRaw(fname)
    jobs={}
    for k in jobs_raw.keys():
        jobs[rawJobId2Nr(k)] = int(jobs_raw[k])
    return jobs

def parseSubmitLogFastTimings(fname,year=None): 
    """
    Reads a Condor submit log, return a dictionary of jobIds
    each having (the last status, seconds in queue, 
    if status==5, seconds running)

    For example {(1583,4)': (0,345,None), (3616,8): (5,7777,4532)}

    @param fname: filename to parse
    @param year: if no year, then use the current one
    @return: Dictionary of jobIDs
    """

    jobs_raw, first_time, last_time = parseSubmitLogFastRawTimings(fname)

    if year is None:
        year = time.localtime()[0]

    # it wrapped over, dates really in previous year
    year_wrap = (first_time>last_time)
    
    jobs = {}
    if year_wrap:
        year1 = year-1
        for k in jobs_raw.keys():
            el = jobs_raw[k]
            status = int(el[0])
            diff_time = diffTimeswWrap(el[1], el[3], year1, first_time)
            if status == 5:
                running_time = diffTimeswWrap(el[2], el[3], year1, first_time)
            else:
                running_time = None
            jobs[rawJobId2Nr(k)] = (status, diff_time, running_time)
    else:
        for k in jobs_raw.keys():
            el = jobs_raw[k]
            status = int(el[0])
            diff_time = diffTimes(el[1], el[3], year)
            if status == 5:
                running_time = diffTimes(el[2], el[3], year)
            else:
                running_time = None
            jobs[rawJobId2Nr(k)] = (status, diff_time, running_time)
        
    return jobs


################################
#  Cache handling functions
################################

def loadCache(fname):
    """
    Loads a pickle file from a filename and returns the resulting data.

    @param fname: Filename to load
    @return: data retrieved from file
    """
    try:
        data = util.file_pickle_load(fname)
    except Exception:
        raise RuntimeError("Could not read %s" % fname)
    return data


def saveCache(fname, data):
    """
    Creates a temporary file to store data in, then moves the file into 
    the correct place.  Uses pickle to store data.

    @param fname: Filename to write to.
    @param data: data to store in pickle format
    """
    util.file_pickle_dump(fname, data)
    return
