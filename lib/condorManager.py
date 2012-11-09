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
import condorMonitor
import condorExe

##############################################
# Helper functions
def pool2str(pool_name):
    if pool_name is not None:
        return "-pool %s "%pool_name
    else:
        return ""

def schedd2str(schedd_name):
    if schedd_name is not None:
        return "-name %s "%schedd_name
    else:
        return ""

def cached_exe_cmd(cmd, arg_str,
                   schedd_name, pool_name, schedd_lookup_cache):
    if schedd_lookup_cache is None:
        schedd_lookup_cache=condorMonitor.NoneScheddCache()

    schedd_str,env=schedd_lookup_cache.getScheddId(schedd_name, pool_name)

    opts="%s%s%s"%(pool2str(pool_name),schedd_str,arg_str)
    return condorExe.exe_cmd(cmd,opts,env=env)

##############################################
#
# Submit a new job, given a submit file
# Works only when a single cluster is created
#
# returns ClusterId
#
def condorSubmitOne(submit_file,schedd_name=None,pool_name=None,
                    schedd_lookup_cache=condorMonitor.local_schedd_cache):
    outstr=cached_exe_cmd("condor_submit",submit_file,
                          schedd_name, pool_name, schedd_lookup_cache)

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
def condorRemove(constraint,schedd_name=None,pool_name=None,
                 do_forcex=False,
                 schedd_lookup_cache=condorMonitor.local_schedd_cache):
    opts="-constraint '%s' "%constraint
    if do_forcex:
        opts+="-forcex "
    return cached_exe_cmd("condor_rm",opts,
                          schedd_name, pool_name, schedd_lookup_cache)

##############################################
#
# Remove a job from the queue
#
def condorRemoveOne(cluster_or_uname,schedd_name=None,pool_name=None,
                    do_forcex=False,
                    schedd_lookup_cache=condorMonitor.local_schedd_cache):
    opts="%s "%cluster_or_uname
    if do_forcex:
        opts+="-forcex "
    return cached_exe_cmd("condor_rm",opts,
                          schedd_name, pool_name, schedd_lookup_cache)

##############################################
#
# Hold a set of jobs from the queue
#
def condorHold(constraint,schedd_name=None,pool_name=None,
                 schedd_lookup_cache=condorMonitor.local_schedd_cache):
    opts="-constraint '%s' "%constraint
    return cached_exe_cmd("condor_hold",opts,
                          schedd_name, pool_name, schedd_lookup_cache)

##############################################
#
# Hold a job from the queue
#
def condorHoldOne(cluster_or_uname,schedd_name=None,pool_name=None,
                  schedd_lookup_cache=condorMonitor.local_schedd_cache):
    opts="%s "%cluster_or_uname
    return cached_exe_cmd("condor_hold",opts,
                          schedd_name, pool_name, schedd_lookup_cache)

##############################################
#
# Release a set of jobs from the queue
#
def condorRelease(constraint,schedd_name=None,pool_name=None,
                 schedd_lookup_cache=condorMonitor.local_schedd_cache):
    opts="-constraint '%s' "%constraint
    return cached_exe_cmd("condor_release",opts,
                          schedd_name, pool_name, schedd_lookup_cache)

##############################################
#
# Release a job from the queue
#
def condorReleaseOne(cluster_or_uname,schedd_name=None,pool_name=None,
                    schedd_lookup_cache=condorMonitor.local_schedd_cache):
    opts="%s "%cluster_or_uname
    return cached_exe_cmd("condor_release",opts,
                          schedd_name, pool_name, schedd_lookup_cache)

##############################################
#
# Issue a condor_reschedule
#
def condorReschedule(schedd_name=None,pool_name=None,
                     schedd_lookup_cache=condorMonitor.local_schedd_cache):
    cached_exe_cmd("condor_reschedule","",
                   schedd_name, pool_name, schedd_lookup_cache)
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
    


