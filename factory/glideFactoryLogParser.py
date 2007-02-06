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
class dirSummary(condorLogParser.dirSummary):
    def __init__(self,dirname,inactive_files=None):
        condorLogParser.dirSummary.__init__(self,dirname,log_prefix="condor_activity_",log_suffix=".log",inactive_files=incative_files)
