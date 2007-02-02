#
# Description:
#   This module implements classes to track
#   changes in glidein status logs
#
# Author:
#   Igor Sfiligoi (Feb 2nd 2007)
#


import os, os.path
import condorLogParser

#class logSummary:
#    def __init__(self,condor_logname):
#        self.condor_logname=condor_logname
#        self.condor_summary=condorLogParser.logSummary(condor_logname)
#        self.cachename=condor_logname+".fctpk"
#
#
#    def has_changed(self):
#        # if the condor logs did not change, ???
#        return self.condor_summary.has_changed()
#
# Need a class that will give absolute values
# will need a cache where it keeps track of the active log files

class trackChanges:
    def __init__(self,dirname,log_prefix,log_suffix=".log"):
        self.dirname=dirname
        self.log_prefix=log_prefix
        self.log_suffix=log_suffix

    # return a list of log files
    def getFileList(self):
        prefix_len=len(self.log_prefix)
        suffix_len=len(self.log_suffix)
        files=[]
        fnames=os.listdir(self.dirname)
        for fname in fnames:
            if  ((fname[:prefix_len]==self.log_prefix) and
                 (fname[-suffix_len:]==self.log_suffix)):
                files.append(fname)
                pass
            pass
        return files

    # return a list of log files that has changed since last check
    def getChangedLogFiles(self):
        changed=[]
        
        fnames=self.getFileList()
        for fname in fnames:
            fsummary=condorLogParser.logSummary(os.path.join(self.dirname,fname))
            if fsummary.has_changed():
                changed.append(fname)
                pass
            pass
        
        return changed
    
    # return a list of jobs that changed status since the last check
    # res[status]["Entered"|"Exited"] = "345.002"
    def getChangedJobs(self):
        counts={}
        
        fnames=self.getChangedLogFiles()
        for fname in fnames:
            cached_status=condorLogParser.logSummary(os.path.join(self.dirname,fname))
            new_status=condorLogParser.logSummary(cached_status.logname)

            # first load cached data, they may not exist
            try:
                cached_status.loadCache()
                cached_data=cached_status.data
            except IOError:
                cached_data={}
                pass

            new_status.load()
            new_data=new_status.data
            
            for s in new_data.keys():
                new_s=new_data[s]
                if cached_data.has_key(s):
                    cached_s=cached_data[s]
                else:
                    cached_s=[]

                try:
                    counts_s=counts[s]
                except: # rare, efficient this way
                    counts_s={'Entered':[],'Exited':[]}
                    counts[s]=counts_s

                for j in new_s:
                    if not j in cached_s:
                        counts_s['Entered'].append(j)
                        pass
                    #else nothing to do
                    pass

                for j in cached_s:
                    if not j in new_s:
                        counts_s['Exited'].append(j)
                        pass
                    #else nothing to do
                    pass
                pass
            pass
        
        return counts

