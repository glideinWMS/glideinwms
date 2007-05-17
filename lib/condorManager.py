#
# Description:
#   This module implements functions that will act on Condor
#
# Author:
#   Igor Sfiligoi (May 17th 2007)
#

import re
import string
import condorExe

##############################################
#
# Submit a new job, given a submit file
# Works only when a single cluster is created
#
# returns ClusterId
#
def condorSubmitOne(submit_file,schedd_name=None,pool_name=None):
    submit_opts=submit_file
    if schedd_name!=None:
        submit_opts="-name %s %s"%(schedd_name,submit_opts)
    if pool_name!=None:
        submit_opts="-pool %s %s"%(pool_name,submit_opts)
    outstr=condorExe.exe_cmd("condor_submit",submit_opts)

    #extract 'submitted to cluster xxx.' part
    j = re.search(r'submitted to cluster [0-9]+\.',string.join(outstr))
    sstr = j.string[j.start(0):j.end(0)]
    #extract the number
    j = re.search(r'[0-9]+',sstr)
    idstr = j.string[j.start(0):j.end(0)]
    return int(idstr)

##############################################
#
# Remove a set of jobs from the queue
#
def condorRemove(constraint,schedd_name=None,pool_name=None):
    rm_opts="-constraint '%s'"%constraint
    if schedd_name!=None:
        rm_opts="-name %s %s"%(schedd_name,rm_opts)
    if pool_name!=None:
        rm_opts="-pool %s %s"%(pool_name,rm_opts)
    return condorExe.exe_cmd("condor_rm",rm_opts)

##############################################
#
# Remove a job from the queue
#
def condorRemoveOne(cluster_or_uname,schedd_name=None,pool_name=None):
    rm_opts="%s"%cluster_or_uname
    if schedd_name!=None:
        rm_opts="-name %s %s"%(schedd_name,rm_opts)
    if pool_name!=None:
        rm_opts="-pool %s %s"%(pool_name,rm_opts)
    return condorExe.exe_cmd("condor_rm",rm_opts)

