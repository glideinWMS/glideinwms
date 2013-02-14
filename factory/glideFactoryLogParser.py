#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements classes to track
#   changes in glidein status logs
#
# Author:
#   Igor Sfiligoi (Feb 2nd 2007)
#


import os
import os.path
import time
import stat
import copy
import mmap
import re
import sys
import traceback

from glideinwms.lib import condorLogParser
from glideinwms.factory import glideFactoryLib

rawJobId2Nr=condorLogParser.rawJobId2Nr
rawTime2cTime=condorLogParser.rawTime2cTime

class logSummaryTimingsOutWrapper:
    def __init__(self):
        self.obj = None

    def getObj(self, logname=None, cache_dir=None, username="all"):
        if (logname is not None) and (cache_dir is not None):
            self.obj = logSummaryTimingsOut(logname, cache_dir, username)
        return self.obj


class logSummaryTimingsOut(condorLogParser.logSummaryTimings):
    """
    Class logSummaryTimingsOut logs timing and status of a job.
    It declares a job complete only after the output file has been received
    The format is slightly different than the one of logSummaryTimings; 
    we add the dirname in the job id
    When a output file is found, it adds a 4th parameter to the completed jobs
    See extractLogData below for more details
    """
    def __init__(self,logname,cache_dir,username):
        """
        This class uses the condorLogParser clInit function to initialize
        """
        self.clInit(logname,cache_dir,".%s.ftstpk"%username)
        self.dirname=os.path.dirname(logname)
        self.cache_dir=cache_dir
        self.now=time.time()
        self.year=time.localtime(self.now)[0]

    def loadFromLog(self):
        """
        This class inherits from cachedLogClass.  So, load() will 
        first check the cached files.  If changed, it will call this function.
        This uses the condorLogParser to load the log, then does
        some post-processing to check the job.NUMBER.out files
        to see if the job has finished and to extract some data.
        """
        condorLogParser.logSummaryTimings.loadFromLog(self)
        if not self.data.has_key('Completed'):
            return # nothing else to fo
        org_completed=self.data['Completed']
        new_completed=[]
        new_waitout=[]
        now=time.time()
        year=time.localtime(now)[0]
        for el in org_completed:
            job_id=rawJobId2Nr(el[0])
            job_fname='job.%i.%i.out'%job_id
            job_fullname=os.path.join(self.dirname,job_fname)

            end_time=rawTime2cTime(el[3],year)
            if end_time>now:
                end_time=rawTime2cTime(el[3],year-1)
            try:
                statinfo=os.stat(job_fullname)
                ftime=statinfo[stat.ST_MTIME]
                fsize=statinfo[stat.ST_SIZE]

                file_ok=((fsize>0) and              # log files are ==0 only before Condor_G transfers them back
                         (ftime>(end_time-300)) and # same here
                         (ftime<(now-5)))           # make sure it is not being written into
            except OSError:
                #no file, report invalid
                file_ok=0

            if file_ok:
                #try:
                #    fdata=extractLogData(job_fullname)
                #except:
                #    fdata=None # just protect
                new_completed.append(el)
            else:
                if (now-end_time)<3600: # give him 1 hour to return the log files
                    new_waitout.append(el)
                else:
                    new_completed.append(el)
                
        self.data['CompletedNoOut']=new_waitout
        self.data['Completed']=new_completed

        # append log name prefix
        for k in self.data.keys():
            new_karr=[]
            for el in self.data[k]:
                job_id=rawJobId2Nr(el[0])
                job_fname='job.%i.%i'%(job_id[0],job_id[1])
                job_fullname=os.path.join(self.dirname,job_fname)
                new_el=el+(job_fullname,)
                new_karr.append(new_el)
            self.data[k]=new_karr

        return

    def diff_raw(self,other):
        """
        Diff self.data with other info,
        add glidein log data to Entered/Exited.
        Used to compare current data with previous iteration.

        Uses symmetric difference of sets to compare the two dictionaries.

        @type other: dictionary of statuses -> jobs
        @return: data[status]['Entered'|'Exited'] - list of jobs
        """
        if other is None:
            outdata={}
            if self.data is not None:
                for k in self.data.keys():
                    outdata[k]={'Exited':[],'Entered':self.data[k]}
            return outdata
        elif self.data is None:
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

                outdata_s={'Entered':[],'Exited':[]}
                outdata[s]=outdata_s

                sset=set(sel)
                oset=set(oel)

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


    def diff(self,other):
        """
        Diff self.data with other for use in comparing current
        iteration data with previous iteration.

        Uses diff_raw to perform symmetric difference of self.data
        and other and puts it into data[status]['Entered'|'Exited']
        Completed jobs are augmented with data from the log

        @return: data[status]['Entered'|'Exited'] - list of jobs 
        """
        outdata=self.diff_raw(other)
        if outdata.has_key("Completed"):
            outdata_s=outdata["Completed"]
            entered=outdata_s['Entered']
            for i in range(len(entered)):
                sel_e=entered[i]
                job_fullname=sel_e[-1]+'.out'

                try:
                    fdata=extractLogData(job_fullname)
                except:
                    fdata=copy.deepcopy(EMPTY_LOG_DATA) # just protect
                    
                entered[i]=(sel_e[:-1]+(fdata,sel_e[-1]))
        return outdata


class dirSummarySimple:
    """
    dirSummary Simple

    for now it is just a constructor wrapper
    Further on it will need to implement glidein exit code checks
    """
    def __init__(self,obj):
        self.data=copy.deepcopy(obj.data)
        self.logClass=obj.logClass
        self.wrapperClass=obj.wrapperClass

        if (obj.wrapperClass is not None):
            self.logClass = obj.wrapperClass.getObj()
        else:
            glideFactoryLib.log_files.logDebug("== MISHANDLED LogParser Object! ==")

    def mkTempLogObj(self):
        if (self.wrapperClass is not None):
            dummyobj = self.wrapperClass.getObj(
                           logname=os.path.join('/tmp','dummy.txt'),
                           cache_dir='/tmp')
        else:
            dummyobj = self.logClass(os.path.join('/tmp','dummy.txt'),'/tmp')
        #dummyobj=self.logClass(os.path.join('/tmp','dummy.txt'),'/tmp')
        dummyobj.data = self.data # a little rough but works
        return dummyobj

    # diff self data with other info
    def diff(self,other):
        dummyobj = self.mkTempLogObj()
        return  dummyobj.diff(other.data) 

    # merge other into myself
    def merge(self,other):
        dummyobj = self.mkTempLogObj()
        dummyobj.merge(copy.deepcopy(other.data))
        self.data = dummyobj.data

class dirSummaryTimingsOut(condorLogParser.cacheDirClass):
    """
    This class uses a lambda function to initialize an instance
    of cacheDirClass.
    The function chooses all condor_activity files in a directory
    that correspond to a particular client.
    """
    def __init__(self,dirname,cache_dir,client_name,user_name,inactive_files=None,inactive_timeout=24*3600):
        """
        self.cdInit(lambda ln,cd:logSummaryTimingsOut(ln,cd,user_name),dirname,"condor_activity_","_%s.log"%client_name,".%s.cifpk"%user_name,inactive_files,inactive_timeout,cache_dir)
        """
        #self.cdInit(logSummaryTimingsOutWrapper(), dirname, 
        self.cdInit(None, dirname, 
                    "condor_activity_", "_%s.log"%client_name, 
                    ".%s.cifpk"%user_name, inactive_files, inactive_timeout, 
                    cache_dir, wrapperClass=logSummaryTimingsOutWrapper(),
                    username=user_name)

    def get_simple(self):
        try:
            obj = dirSummarySimple(self)
        except:
            tb = traceback.format_exception(sys.exc_info()[0],
                                            sys.exc_info()[1],
                                            sys.exc_info()[2])
            glideFactoryLib.log_files.logDebug(tb)
            raise

        return obj
        

class dirSummaryTimingsOutFull(condorLogParser.cacheDirClass):
    """
    This class uses a lambda function to initialize an instance
    of cacheDirClass.
    The function chooses all condor_activity files in a directory
    regardless of client name.
    """
    def __init__(self,dirname,cache_dir,inactive_files=None,inactive_timeout=24*3600):
        self.cdInit(lambda ln,cd:logSummaryTimingsOut(ln,cd,"all"),dirname,"condor_activity_",".log",".all.cifpk",inactive_files,inactive_timeout,cache_dir)

    def get_simple(self):
        return dirSummarySimple(self)

#########################################################
#     P R I V A T E
#########################################################

ELD_RC_VALIDATE_END=re.compile("=== Last script starting .* after validating for (?P<secs>[0-9]+) ===")
ELD_RC_CONDOR_START=re.compile("=== Condor starting.*===")
ELD_RC_CONDOR_END=re.compile("=== Condor ended.*after (?P<secs>[0-9]+) ===")
ELD_RC_CONDOR_SLOT=re.compile("=== Stats of (?P<slot>\S+) ===(?P<content>.*)=== End Stats of (?P<slot2>\S+) ===",re.M|re.DOTALL)
ELD_RC_CONDOR_SLOT_CONTENT_COUNT=re.compile("Total(?P<name>.*)jobs (?P<jobsnr>[0-9]+) .*utilization (?P<secs>[0-9]+)")
ELD_RC_GLIDEIN_END=re.compile("=== Glidein ending .* with code (?P<code>[0-9]+) after (?P<secs>[0-9]+) ===")

KNOWN_SLOT_STATS=['Total','goodZ','goodNZ','badSignal','badOther']

EMPTY_LOG_DATA={'condor_started':0,'glidein_duration':0}

def extractLogData(fname):
    """
    Given a filename of a job file "path/job.NUMBER.out"
    extract the statistics of the job duration, etc.

    @param fname: Filename to extract
    @return: a dictionary with keys:
        - glidein_duration - integer, how long did the glidein run
        - validation_duration - integer, how long before starting condor
        - condor_started - Boolean, did condor even start 
          (if false, no further entries)
        - condor_duration - integer, how long did Condor run
        - stats - dictionary of stats (as in KNOWN_SLOT_STATS), each having
        - jobsnr - integer, number of jobs started
        - secs   - integer, total number of secods used
    For example {'glidein_duration':20305,'validation_duration':6,'condor_started' : 1, 'condor_duration': 20298, 'stats': {'badSignal': {'secs': 0, 'jobsnr': 0}, 'goodZ': {'secs' : 19481, 'jobsnr': 1}, 'Total': {'secs': 19481, 'jobsnr': 1}, 'goodNZ': {'secs': 0, 'jobsnr': 0}, 'badOther': {'secs': 0, 'jobsnr': 0}}}
    """
    condor_starting=0
    condor_duration=None
    validation_duration=None
    slot_stats={}

    size = os.path.getsize(fname)
    if size<10:
        return copy.deepcopy(EMPTY_LOG_DATA)
    fd=open(fname,'r')
    try:
        buf=mmap.mmap(fd.fileno(),size,access=mmap.ACCESS_READ)
        try:
            buf_idx=0
            validate_re=ELD_RC_VALIDATE_END.search(buf,buf_idx)
            if validate_re is not None:
                try:
                    validation_duration=int(validate_re.group('secs'))
                except:
                    validation_duration=None
                
                bux_idx=validate_re.end()+1
            
            start_re=ELD_RC_CONDOR_START.search(buf,buf_idx)
            if start_re is not None:
                condor_starting=1
                buf_idx=start_re.end()+1
                end_re=ELD_RC_CONDOR_END.search(buf,buf_idx)
                if end_re is not None:
                    try:
                        condor_duration=int(end_re.group('secs'))
                    except:
                        condor_duration=None
                    buf_idx=end_re.end()+1
                    slot_re=ELD_RC_CONDOR_SLOT.search(buf,buf_idx)
                    while slot_re is not None:
                        buf_idx=slot_re.end()+1
                        slot_name=slot_re.group('slot')
                        if slot_name[-1]!='1': # ignore slot 1, it is used for monitoring only
                            slot_buf=slot_re.group('content')
                            count_re=ELD_RC_CONDOR_SLOT_CONTENT_COUNT.search(slot_buf,0)
                            while count_re is not None:
                                count_name=count_re.group('name')
                                # need to trim it, comes out with spaces
                                if count_name==' ': # special case
                                    count_name='Total'
                                else:
                                    count_name=count_name[1:-1]

                                try:
                                    jobsnr=int(count_re.group('jobsnr'))
                                    secs=int(count_re.group('secs'))
                                except:
                                    jobsnr=None
                                    
                                if jobsnr is not None: #check I had no errors in integer conversion
                                    if not slot_stats.has_key(count_name):
                                        slot_stats[count_name]={'jobsnr':jobsnr,'secs':secs}

                                count_re=ELD_RC_CONDOR_SLOT_CONTENT_COUNT.search(slot_buf,count_re.end()+1)
                                #end while count_re
                            
                        slot_re=ELD_RC_CONDOR_SLOT.search(buf,buf_idx)
                        # end while slot_re
                    
            glidein_end_re=ELD_RC_GLIDEIN_END.search(buf,buf_idx)
            if glidein_end_re is not None:
                try:
                    glidein_duration=int(glidein_end_re.group('secs'))
                except:
                    glidein_duration=None
                bux_idx=glidein_end_re.end()+1
            else:
                glidein_duration=None
                
        finally:
            buf.close()
    finally:
        fd.close()

    out={'condor_started':condor_starting}
    if validation_duration is not None:
        out['validation_duration']=validation_duration
    #else:
    #   out['validation_duration']=1
    if glidein_duration is not None:
        out['glidein_duration']=glidein_duration
    #else:
    #   out['glidein_duration']=2
    if condor_starting:
        if condor_duration is not None:
            out['condor_duration']=condor_duration
            out['stats']=slot_stats

    return out
