#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glideFactoryLogParser.py,v 1.15.12.1.2.2 2010/08/31 18:49:16 parag Exp $
#
# Description:
#   This module implements classes to track
#   changes in glidein status logs
#
# Author:
#   Igor Sfiligoi (Feb 2nd 2007)
#


import os, os.path,time,stat,sets
import mmap,re
import condorLogParser

rawJobId2Nr=condorLogParser.rawJobId2Nr
rawTime2cTime=condorLogParser.rawTime2cTime

# this class declares a job complete only after the output file has been received, too
# when a output file is found, it adds a 4th parameter to the completed jobs
# see extractLogData below for more details
class logSummaryTimingsOut(condorLogParser.logSummaryTimings):
    def __init__(self,logname,cache_dir,username):
        self.clInit(logname,cache_dir,".%s.ftstpk"%username)
        self.dirname=os.path.dirname(logname)
        self.cache_dir=cache_dir
        self.now=time.time()
        self.year=time.localtime(self.now)[0]

    def loadFromLog(self):
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
        return

    # diff self data with other info
    # add glidein log data to Entered/Completed
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
                            if s=="Completed":
                                job_id=rawJobId2Nr(sel_e[0])
                                job_fname='job.%i.%i.out'%job_id
                                job_fullname=os.path.join(self.dirname,job_fname)
                                
                                try:
                                    fdata=extractLogData(job_fullname)
                                except:
                                    fdata=None # just protect
                                    
                                entered.append(sel_e+(fdata,))
                            else:
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


# for now it is just a constructor wrapper
# Further on it will need to implement glidein exit code checks

# One client_name
class dirSummaryTimingsOut(condorLogParser.cacheDirClass):
    def __init__(self,dirname,cache_dir,client_name,user_name,inactive_files=None,inactive_timeout=24*3600):
        self.cdInit(lambda ln,cd:logSummaryTimingsOut(ln,cd,user_name),dirname,"condor_activity_","_%s.log"%client_name,".%s.cifpk"%user_name,inactive_files,inactive_timeout,cache_dir)

# All clients
class dirSummaryTimingsOutFull(condorLogParser.cacheDirClass):
    def __init__(self,dirname,cache_dir,inactive_files=None,inactive_timeout=24*3600):
        self.cdInit(lambda ln,cd:logSummaryTimingsOut(ln,cd,"all"),dirname,"condor_activity_",".log",".all.cifpk",inactive_files,inactive_timeout,cache_dir)


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


# will return a dictionary
#  glidein_duration - integer, how long did the glidein run
#  validation_duration - integer, how long did it take before starting condor
#  condor_started - Boolean, did condor even start (if false, no further entries)
#  condor_duration - integer, how long did Condor run
#  stats - dictionary of stats (as in KNOWN_SLOT_STATS), each having
#           jobsnr - integer, number of jobs started
#           secs   - integer, total number of secods used
# for example {'glidein_duration':20305,'validation_duration':6,'condor_started': 1, 'condor_duration': 20298,
#              'stats': {'badSignal': {'secs': 0, 'jobsnr': 0}, 'goodZ': {'secs': 19481, 'jobsnr': 1}, 'Total': {'secs': 19481, 'jobsnr': 1}, 'goodNZ': {'secs': 0, 'jobsnr': 0}, 'badOther': {'secs': 0, 'jobsnr': 0}}}
def extractLogData(fname):
    condor_starting=0
    condor_duration=None
    validation_duration=None
    slot_stats={}

    size = os.path.getsize(fname)
    if size<10:
        return {'condor_started':0,'glidein_duration':0}
    fd=open(fname,'r')
    try:
        buf=mmap.mmap(fd.fileno(),size,access=mmap.ACCESS_READ)
        try:
            buf_idx=0
            validate_re=ELD_RC_VALIDATE_END.search(buf,buf_idx)
            if validate_re!=None:
                try:
                    validation_duration=int(validate_re.group('secs'))
                except:
                    validation_duration=None
                
                bux_idx=validate_re.end()+1
            
            start_re=ELD_RC_CONDOR_START.search(buf,buf_idx)
            if start_re!=None:
                condor_starting=1
                buf_idx=start_re.end()+1
                end_re=ELD_RC_CONDOR_END.search(buf,buf_idx)
                if end_re!=None:
                    try:
                        condor_duration=int(end_re.group('secs'))
                    except:
                        condor_duration=None
                    buf_idx=end_re.end()+1
                    slot_re=ELD_RC_CONDOR_SLOT.search(buf,buf_idx)
                    while slot_re!=None:
                        buf_idx=slot_re.end()+1
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
                                        slot_stats[count_name]={'jobsnr':jobsnr,'secs':secs}

                                count_re=ELD_RC_CONDOR_SLOT_CONTENT_COUNT.search(slot_buf,count_re.end()+1)
                                #end while count_re
                            
                        slot_re=ELD_RC_CONDOR_SLOT.search(buf,buf_idx)
                        # end while slot_re
                    
            glidein_end_re=ELD_RC_GLIDEIN_END.search(buf,buf_idx)
            if glidein_end_re!=None:
                try:
                    glidein_duration=int(glidein_end_re.group('secs'))
                except:
                    glidein_duration=None
                
                bux_idx=glidein_end_re.end()+1
        finally:
            buf.close()
    finally:
        fd.close()

    out={'condor_started':condor_starting}
    if validation_duration!=None:
        out['validation_duration']=validation_duration
    #else:
    #   out['validation_duration']=1
    if glidein_duration!=None:
        out['glidein_duration']=glidein_duration
    #else:
    #   out['glidein_duration']=2
    if condor_starting:
        if condor_duration!=None:
            out['condor_duration']=condor_duration
            out['stats']=slot_stats

    return out
