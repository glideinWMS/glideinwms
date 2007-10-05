#
# Description:
#   This module implements classes to track
#   changes in glidein status logs
#
# Author:
#   Igor Sfiligoi (Feb 2nd 2007)
#


import os, os.path,time,stat
import mmap,re
import condorLogParser

rawJobId2Nr=condorLogParser.rawJobId2Nr
rawTime2cTime=condorLogParser.rawTime2cTime

# this class declares a job complete only after the output file has been received, too
# when a output file is found, it adds a 4th parameter to the completed jobs
# see extractLogData below for more details
class logSummaryTimingsOut(condorLogParser.logSummaryTimings):
    def __init__(self,logname):
        self.clInit(logname,".ftstpk")
        self.dirname=os.path.dirname(logname)
        self.now=time.time()
        self.year=time.localtime(now)[0]

    def loadFromLog(self):
        condorLogParser.logSummaryTimings.loadFromLog(self)
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

                file_ok=((fsize>0) and        # log files are ==0 only before Condor_G transfers them back
                         (ftime>end_time) and # same here
                         (ftime<(now-5)))       # make sure it is not being written into
            except OSError:
                #no file, report invalid
                file_ok=0

            if file_ok:
                try:
                    fdata=extractLogData(job_fullname)
                except:
                    fdata=None # just protect
                new_completed.append(el+(fdata,))
            else:
                if (now-end_time)<3600: # give him 1 hour to return the log files
                    new_waitout.append(el)
                else:
                    new_completed.append(el+(None,))
                
        self.data['CompletedNoOut']=new_waitout
        self.data['Completed']=new_completed
        return

# for now it is just a constructor wrapper
# Further on it will need to implement glidein exit code checks
class dirSummaryTimingsOut(condorLogParser.cacheDirClass):
    def __init__(self,dirname,client_name,inactive_files=None,inactive_timeout=24*3600):
        self.cdInit(logSummaryTimingsOut,dirname,"condor_activity_","_%s.log"%client_name,".cifpk",inactive_files,inactive_timeout)


#########################################################
#     P R I V A T E
#########################################################

ELD_RC_CONDOR_START=re.compile("=== Condor starting.*===")
ELD_RC_CONDOR_END=re.compile("=== Condor ended.*after (?P<secs>[0-9]+) ===")
ELD_RC_CONDOR_SLOT=re.compile("=== Stats of (?P<slot>\S+) ===(?P<content>.*)=== End Stats of (?P<slot2>\S+) ===",re.M|re.DOTALL)
ELD_RC_CONDOR_SLOT_CONTENT_COUNT=re.compile("Total(?P<name>.*)jobs (?P<jobsnr>[0-9]+) .*utilization (?P<secs>[0-9]+)")

KNOWN_SLOT_STATS=['Total','goodZ','goodNZ','badSignal','badOther']


# will return a dictionary
#  condor_started - Boolean, did condor even start (if false, no other entries)
#  condor_duration - integer, how long did it run
#  stats - dictionary of stats (as in KNOWN_SLOT_STATS), each having
#           jobsnr - integer, number of jobs started
#           secs   - integer, total number of secods used
# for example {'condor_started': 1, 'condor_duration': 20298,
#              'stats': {'badSignal': {'secs': 0, 'jobsnr': 0}, 'goodZ': {'secs': 19481, 'jobsnr': 1}, 'Total': {'secs': 19481, 'jobsnr': 1}, 'goodNZ': {'secs': 0, 'jobsnr': 0}, 'badOther': {'secs': 0, 'jobsnr': 0}}}
def extractLogData(fname):
    condor_starting=0
    condor_duration=None
    slot_stats={}
    for count_name in KNOWN_SLOT_STATS:
        slot_stats[count_name]={'jobsnr':0,'secs':0}

    size = os.path.getsize(fname)
    fd=open(fname,'r')
    try:
        buf=mmap.mmap(fd.fileno(),size,access=mmap.ACCESS_READ)
        try:
            start_re=ELD_RC_CONDOR_START.search(buf,0)
            if start_re!=None:
                condor_starting=1
                end_re=ELD_RC_CONDOR_END.search(buf,start_re.end()+1)
                if end_re!=None:
                    try:
                        condor_duration=int(end_re.group('secs'))
                    except:
                        condor_duration=None
                    slot_re=ELD_RC_CONDOR_SLOT.search(buf,end_re.end()+1)
                    while slot_re!=None:
                        slot_name=slot_re.group('slot')
                        if slot_name[-1]!='1': # ignore slot 1, it is used for monitoring only
                            slot_buf=slot_re.group('content')
                            count_re=ELD_RC_CONDOR_SLOT_CONTENT_COUNT.search(slot_buf,0)
                            while count_re!=None:
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
                                    
                                if jobsnr!=None: #check I had no errors in integer conversion
                                    if not slot_stats.has_key(count_name):
                                        slot_stats[count_name]={'jobsnr':0,'secs':0}

                                    slot_stats[count_name]['jobsnr']+=jobsnr
                                    slot_stats[count_name]['secs']+=secs

                                count_re=ELD_RC_CONDOR_SLOT_CONTENT_COUNT.search(slot_buf,count_re.end()+1)
                                #end while count_re
                            
                        slot_re=ELD_RC_CONDOR_SLOT.search(buf,slot_re.end()+1)
                        # end while slot_re
                    
        finally:
            buf.close()
    finally:
        fd.close()

    out={'condor_started':condor_starting}
    if condor_starting:
        if condor_duration!=None:
            out['condor_duration']=condor_duration
            out['stats']=slot_stats

    return out
