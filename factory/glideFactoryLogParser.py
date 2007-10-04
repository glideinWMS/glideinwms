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

# for now it is just a constructor wrapper
# Further on it will need to implement glidein exit code checks
class dirSummaryTimings(condorLogParser.dirSummary):
    def __init__(self,dirname,client_name,inactive_files=None):
        condorLogParser.dirSummaryTimings.__init__(self,dirname,log_prefix="condor_activity_",log_suffix="_"+client_name+".log",inactive_files=inactive_files)
