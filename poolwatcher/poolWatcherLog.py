#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: poolWatcherLog.py,v 1.2.20.1 2010/08/31 18:49:17 parag Exp $
#
# Description:
#   This module implements the classes needed
#   to handle the status log files
#
# Author:
#   Igor Sfiligoi (Feb 13th 2007)
#

import time

event_description={0:"VM registered",
                   1:"VM claimed",
                   4:"VM free",
                   5:"VM disappeared",
                   12:"VM in Owner state",
                   13:"VM left Owner state"}

class watcherLogWriter:
    def __init__(self,basename,ext=".log"):
        self.basename=basename
        self.ext=ext

    def logPing(self):
        time_str=time.strftime("%m/%d %H:%M:%S",time.localtime())
        self.writeEntry("008 (*) (*) (*) %s Ping"%time_str)
        return

    def logNewVM(self, VM, DaemonStartTime,
                 vm_attributes={},     # attr_name:value pairs
                 timestamp=None):   # use current time if None
        event_comments=[]
        attr_keys=vm_attributes.keys()
        attr.keys.sort()
        for k in attr_keys:
            event_comments.append("VMAttr %s = %s"%(k,vm_attributes[k]))
        return self.logEvent(0, VM, DaemonStartTime, event_comments,timestamp)
    
    def logClaimed(self, VM, DaemonStartTime,
                   job_attributes={},     # attr_name:value pairs
                   timestamp=None):   # use current time if None
        event_comments=[]
        attr_keys=job_attributes.keys()
        attr.keys.sort()
        for k in attr_keys:
            event_comments.append("JobAttr %s = %s"%(k,job_attributes[k]))
        return self.logEvent(1, VM, DaemonStartTime, event_comments,timestamp)
    
    def logReleased(self, VM, DaemonStartTime,
                    last_known_claimed=None, # None means unknown
                    timestamp=None):         # use current time if None
        lkc_comments=[]
        if last_known_claimed!=None:
            lkc_comments.append("LastKnownClaimed: "+time.strftime("%m/%d %H:%M:%S",time.localtime(last_known_claimed))))
        return self.logEvent(4, VM, DaemonStartTime,lkc_comments,timestamp)

    def logDisappeared(self, VM, DaemonStartTime,
                       last_known_existed=None, # None means unknown
                       timestamp=None):   # use current time if None
        lke_comments=[]
        if last_known_existed!=None:
            lke_comments.append("LastKnownExisted: "+time.strftime("%m/%d %H:%M:%S",time.localtime(last_known_existed))))
        return self.logEvent(5, VM, DaemonStartTime,lke_comments,timestamp)
    

    ### PR I V A T E ###
    def logEvent(self, event, VM, DaemonStartTime,
                 comments=[],
                 timestamp=None):
        global event_description
        if timestamp==None:
            timestamp=time.time()
        time_str=time.strftime("%m/%d %H:%M:%S",time.localtime(timestamp))

        comment_str=""
        for comment in comments:
            comment_str+="\n    "+comment #start in a new line
        return self.writeEntry(DaemonStartTime,"%03i (%s#%s) %s %s%s"%(event,VM,DaemonStartTime,time_str,event_description[event],comment_str))

    def writeEntry(self,DaemonStartTime,entry):
        fd=open(self.logName(DaemonStartTime),"a")
        try:
            fd.write("%s\n...\n"%entry)
        finally:
            fd.close()
        return

    def logName(self,DaemonStartTime):
        time_str=time.strftime("%Y%m%d",time.localtime(long(DaemonStartTime)))
        return "%s%s%s"%(self.basename,time_str,self.ext)

class watcherLogReader:
    def __init__(self,basename,ext=".log"):
        self.basename=basename
        self.ext=ext
