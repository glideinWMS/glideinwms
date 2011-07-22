#
# Project:
#   glideinWMS
#
# File Version: 
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
# Helper functions
def pool2str(pool_name):
    if pool_name!=None:
        return "-pool %s "%pool_name
    else:
        return ""

def schedd2str(schedd_name):
    if schedd_name!=None:
        return "-name %s "%schedd_name
    else:
        return ""

##############################################
#
# Submit a new job, given a submit file
# Works only when a single cluster is created
#
# returns ClusterId
#
def condorSubmitOne(submit_file,schedd_name=None,pool_name=None):
    submit_opts="%s%s%s"%(pool2str(pool_name),schedd2str(schedd_name),submit_file)
    outstr=condorExe.exe_cmd("condor_submit",submit_opts)

    #extract 'submitted to cluster xxx.' part
    j = re.search(r'submitted to cluster [0-9]+\.', string.join(outstr))
    sstr = j.string[j.start(0):j.end(0)]
    #extract the number
    j = re.search(r'[0-9]+', sstr)
    idstr = j.string[j.start(0):j.end(0)]
    return int(idstr)

##############################################
#
# Remove a set of jobs from the queue
#
def condorRemove(constraint,schedd_name=None,pool_name=None):
    rm_opts="%s%s-constraint '%s'"%(pool2str(pool_name),schedd2str(schedd_name),constraint)
    return condorExe.exe_cmd("condor_rm",rm_opts)

##############################################
#
# Remove a job from the queue
#
def condorRemoveOne(cluster_or_uname,schedd_name=None,pool_name=None):
    rm_opts="%s%s%s"%(pool2str(pool_name),schedd2str(schedd_name),cluster_or_uname)
    return condorExe.exe_cmd("condor_rm",rm_opts)

##############################################
#
# Issue a condor_reschedule
#
def condorReschedule(schedd_name=None,pool_name=None):
    cmd_opts="%s%s"%(pool2str(pool_name),schedd2str(schedd_name))
    condorExe.exe_cmd("condor_reschedule",cmd_opts)
    return


##############################################
# Helper functions of condorAdvertise
def usetcp2str(use_tcp):
    if use_tcp:
        return "-tcp "
    else:
        return ""

def ismulti2str(is_multi):
    if is_multi:
        return "-multiple "
    else:
        return ""

##############################################
#
# Remove a job from the queue
#
def condorAdvertise(classad_fname,command,
                    use_tcp=False,is_multi=False,pool_name=None):
    cmd_opts="%s%s%s%s %s"%(pool2str(pool_name),usetcp2str(use_tcp),ismulti2str(is_multi),command,classad_fname)
    return condorExe.exe_cmd_sbin("condor_advertise",cmd_opts)
