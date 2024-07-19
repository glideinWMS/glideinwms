# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements functions that will act on Condor."""

import re

from . import condorExe, condorMonitor


##############################################
# Helper functions
def pool2str(pool_name):
    """
    Convert pool name to a string suitable for the Condor command line.

    Args:
        pool_name (str): The name of the pool.

    Returns:
        str: The pool name formatted for the command line.
    """
    if pool_name is not None:
        return "-pool %s " % pool_name
    else:
        return ""


def schedd2str(schedd_name):
    """
    Convert schedd name to a string suitable for the Condor command line.

    Args:
        schedd_name (str): The name of the schedd.

    Returns:
        str: The schedd name formatted for the command line.
    """
    if schedd_name is not None:
        return "-name %s " % schedd_name
    else:
        return ""


def cached_exe_cmd(cmd, arg_str, schedd_name, pool_name, schedd_lookup_cache):
    """
    Execute a cached Condor command.

    Args:
        cmd (str): The Condor command to execute.
        arg_str (str): The arguments for the command.
        schedd_name (str): The name of the schedd.
        pool_name (str): The name of the pool.
        schedd_lookup_cache: The cache for schedd lookups.

    Returns:
        str: The output of the Condor command.
    """
    if schedd_lookup_cache is None:
        schedd_lookup_cache = condorMonitor.NoneScheddCache()

    schedd_str, env = schedd_lookup_cache.getScheddId(schedd_name, pool_name)

    opts = f"{pool2str(pool_name)}{schedd_str}{arg_str}"
    return condorExe.exe_cmd(cmd, opts, env=env)


##############################################
#
# Submit a new job, given a submit file
# Works only when a single cluster is created
#
# returns ClusterId
#
def condorSubmitOne(
    submit_file, schedd_name=None, pool_name=None, schedd_lookup_cache=condorMonitor.local_schedd_cache
):
    """
    Submit a new job using a submit file. Works only when a single cluster is created.

    Args:
        submit_file (str): The path to the submit file.
        schedd_name (str, optional): The name of the schedd. Defaults to None.
        pool_name (str, optional): The name of the pool. Defaults to None.
        schedd_lookup_cache (optional): The cache for schedd lookups. Defaults to condorMonitor.local_schedd_cache.

    Returns:
        int: The ClusterId of the submitted job.
    """
    outstr = cached_exe_cmd("condor_submit", submit_file, schedd_name, pool_name, schedd_lookup_cache)

    # extract 'submitted to cluster xxx.' part
    j = re.search(r"submitted to cluster [0-9]+\.", " ".join(outstr))
    sstr = j.string[j.start(0) : j.end(0)]
    # extract the number
    j = re.search(r"[0-9]+", sstr)
    idstr = j.string[j.start(0) : j.end(0)]
    return int(idstr)


##############################################
#
# Remove a set of jobs from the queue
#
def condorRemove(
    constraint, schedd_name=None, pool_name=None, do_forcex=False, schedd_lookup_cache=condorMonitor.local_schedd_cache
):
    """
    Remove a set of jobs from the queue.

    Args:
        constraint (str): The constraint to match jobs for removal.
        schedd_name (str, optional): The name of the schedd. Defaults to None.
        pool_name (str, optional): The name of the pool. Defaults to None.
        do_forcex (bool, optional): If True, force removal. Defaults to False.
        schedd_lookup_cache (optional): The cache for schedd lookups. Defaults to condorMonitor.local_schedd_cache.

    Returns:
        str: The output of the condor_rm command.
    """
    opts = "-constraint '%s' " % constraint
    if do_forcex:
        opts += "-forcex "
    return cached_exe_cmd("condor_rm", opts, schedd_name, pool_name, schedd_lookup_cache)


##############################################
#
# Remove a job from the queue
#
def condorRemoveOne(
    cluster_or_uname,
    schedd_name=None,
    pool_name=None,
    do_forcex=False,
    schedd_lookup_cache=condorMonitor.local_schedd_cache,
):
    """
    Remove a single job from the queue.

    Args:
        cluster_or_uname (str): The ClusterId or username of the job to remove.
        schedd_name (str, optional): The name of the schedd. Defaults to None.
        pool_name (str, optional): The name of the pool. Defaults to None.
        do_forcex (bool, optional): If True, force removal. Defaults to False.
        schedd_lookup_cache (optional): The cache for schedd lookups. Defaults to condorMonitor.local_schedd_cache.

    Returns:
        str: The output of the condor_rm command.
    """
    opts = "%s " % cluster_or_uname
    if do_forcex:
        opts += "-forcex "
    return cached_exe_cmd("condor_rm", opts, schedd_name, pool_name, schedd_lookup_cache)


##############################################
#
# Hold a set of jobs from the queue
#
def condorHold(constraint, schedd_name=None, pool_name=None, schedd_lookup_cache=condorMonitor.local_schedd_cache):
    """
    Hold a set of jobs in the queue.

    Args:
        constraint (str): The constraint to match jobs for holding.
        schedd_name (str, optional): The name of the schedd. Defaults to None.
        pool_name (str, optional): The name of the pool. Defaults to None.
        schedd_lookup_cache (optional): The cache for schedd lookups. Defaults to condorMonitor.local_schedd_cache.

    Returns:
        str: The output of the condor_hold command.
    """
    opts = "-constraint '%s' " % constraint
    return cached_exe_cmd("condor_hold", opts, schedd_name, pool_name, schedd_lookup_cache)


##############################################
#
# Hold a job from the queue
#
def condorHoldOne(
    cluster_or_uname, schedd_name=None, pool_name=None, schedd_lookup_cache=condorMonitor.local_schedd_cache
):
    """
    Hold a single job in the queue.

    Args:
        cluster_or_uname (str): The ClusterId or username of the job to hold.
        schedd_name (str, optional): The name of the schedd. Defaults to None.
        pool_name (str, optional): The name of the pool. Defaults to None.
        schedd_lookup_cache (optional): The cache for schedd lookups. Defaults to condorMonitor.local_schedd_cache.

    Returns:
        str: The output of the condor_hold command.
    """
    opts = "%s " % cluster_or_uname
    return cached_exe_cmd("condor_hold", opts, schedd_name, pool_name, schedd_lookup_cache)


##############################################
#
# Release a set of jobs from the queue
#
def condorRelease(constraint, schedd_name=None, pool_name=None, schedd_lookup_cache=condorMonitor.local_schedd_cache):
    """
    Release a set of jobs from hold in the queue.

    Args:
        constraint (str): The constraint to match jobs for release.
        schedd_name (str, optional): The name of the schedd. Defaults to None.
        pool_name (str, optional): The name of the pool. Defaults to None.
        schedd_lookup_cache (optional): The cache for schedd lookups. Defaults to condorMonitor.local_schedd_cache.

    Returns:
        str: The output of the condor_release command.
    """
    opts = "-constraint '%s' " % constraint
    return cached_exe_cmd("condor_release", opts, schedd_name, pool_name, schedd_lookup_cache)


##############################################
#
# Release a job from the queue
#
def condorReleaseOne(
    cluster_or_uname, schedd_name=None, pool_name=None, schedd_lookup_cache=condorMonitor.local_schedd_cache
):
    """
    Release a single job from hold in the queue.

    Args:
        cluster_or_uname (str): The ClusterId or username of the job to release.
        schedd_name (str, optional): The name of the schedd. Defaults to None.
        pool_name (str, optional): The name of the pool. Defaults to None.
        schedd_lookup_cache (optional): The cache for schedd lookups. Defaults to condorMonitor.local_schedd_cache.

    Returns:
        str: The output of the condor_release command.
    """
    opts = "%s " % cluster_or_uname
    return cached_exe_cmd("condor_release", opts, schedd_name, pool_name, schedd_lookup_cache)


##############################################
#
# Issue a condor_reschedule
#
def condorReschedule(schedd_name=None, pool_name=None, schedd_lookup_cache=condorMonitor.local_schedd_cache):
    """
    Issue a condor_reschedule command.

    Args:
        schedd_name (str, optional): The name of the schedd. Defaults to None.
        pool_name (str, optional): The name of the pool. Defaults to None.
        schedd_lookup_cache (optional): The cache for schedd lookups. Defaults to condorMonitor.local_schedd_cache.
    """
    cached_exe_cmd("condor_reschedule", "", schedd_name, pool_name, schedd_lookup_cache)
    return


##############################################
# Helper functions of condorAdvertise
def usetcp2str(use_tcp):
    """
    Convert use_tcp flag to a string suitable for the Condor command line.

    Args:
        use_tcp (bool): If True, use TCP.

    Returns:
        str: The use_tcp flag formatted for the command line.
    """
    if use_tcp:
        return "-tcp "
    else:
        return ""


def ismulti2str(is_multi):
    """
    Convert is_multi flag to a string suitable for the Condor command line.

    Args:
        is_multi (bool): If True, indicate multiple.

    Returns:
        str: The is_multi flag formatted for the command line.
    """
    if is_multi:
        return "-multiple "
    else:
        return ""


##############################################
#
# Advertise a job to the queue
#
def condorAdvertise(classad_fname, command, use_tcp=False, is_multi=False, pool_name=None):
    """
    Advertise a job to the Condor queue.

    Args:
        classad_fname (str): The filename of the classad.
        command (str): The Condor command to advertise.
        use_tcp (bool, optional): If True, use TCP. Defaults to False.
        is_multi (bool, optional): If True, indicate multiple. Defaults to False.
        pool_name (str, optional): The name of the pool. Defaults to None.

    Returns:
        str: The output of the condor_advertise command.
    """
    cmd_opts = f"{pool2str(pool_name)}{usetcp2str(use_tcp)}{ismulti2str(is_multi)}{command} {classad_fname}"
    return condorExe.exe_cmd_sbin("condor_advertise", cmd_opts)
