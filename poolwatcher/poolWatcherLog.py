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
                   5:"VM disappeared"}

class watcherLog:
    def __init__(self,basename,ext=".log"):
        self.basename=basename
        self.ext=ext

    def logPing(self):
        time_str=time.strftime("%m/%d %H:%M:%S",time.localtime())
        self.writeEntry("008 (*) (*) (*) %s Ping"%time_str)
        return

    def logEvent(self, event, VM, factory_name, glidein_name, schedd_name, cluster_id, proc_id,
                 comments=[]):
        global event_description
        time_str=time.strftime("%m/%d %H:%M:%S",time.localtime())

        comment_str=""
        for comment in comments:
            comment_str+="\n    "+comment #start in a new line
        self.writeEntry("%03i (%s) (%s@%s) (%s#%i.%03i) %s %s%s"%(event,VM,glidein_name,factory_name,schedd_name,cluster_id,proc_id,time_str,event_description[event],comment_str))

        return

    ### PR I V A T E ###
    def writeEntry(self,entry):
        fd=open(self.logName(),"a")
        try:
            fd.write("%s\n...\n"%entry)
        finally:
            fd.close()
        return

    def logName(self):
        time_str=time.strftime("%Y%m%d",time.localtime())
        return "%s%s%s"%(self.basename,time_str,self.ext)
