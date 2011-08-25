#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This module implements the functions needed to keep the
#   required number of idle glideins
#   It also has support for glidein sanitizing
#
# Author:
#   Igor Sfiligoi (Sept 7th 2006)
#

import os
import time
import re
import pwd
import binascii
import condorExe
import condorPrivsep
import logSupport
import condorMonitor
import glideFactoryConfig
import base64
import string
import timeConversion

from tarSupport import GlideinTar

MY_USERNAME = pwd.getpwuid(os.getuid())[0]

############################################################
#
# Configuration
#
############################################################

class FactoryConfig:
    def __init__(self):
        # set default values
        # user should modify if needed

        # The name of the attribute that identifies the glidein
        self.factory_schedd_attribute = "GlideinFactory"
        self.glidein_schedd_attribute = "GlideinName"
        self.entry_schedd_attribute = "GlideinEntryName"
        self.client_schedd_attribute = "GlideinClient"
        #self.x509id_schedd_attribute = "GlideinX509Identifier"
        self.credential_id_schedd_attribute = "GlideinCredentialIdentifier"
        #self.x509secclass_schedd_attribute = "GlideinX509SecurityClass"
        self.credential_secclass_schedd_attribute = "GlideinSecurityClass"

        self.factory_startd_attribute = "GLIDEIN_Factory"
        self.glidein_startd_attribute = "GLIDEIN_Name"
        self.entry_startd_attribute = "GLIDEIN_Entry_Name"
        self.client_startd_attribute = "GLIDEIN_Client"
        self.schedd_startd_attribute = "GLIDEIN_Schedd"
        self.clusterid_startd_attribute = "GLIDEIN_ClusterId"
        self.procid_startd_attribute = "GLIDEIN_ProcId"

        self.count_env = 'GLIDEIN_COUNT'

        self.submit_fname = "job_submit.sh"


        # Stale value settings, in seconds
        self.stale_maxage = { 1:7 * 24 * 3600, # 1 week for idle
                            2:31 * 24 * 3600, # 1 month for running
                           - 1:2 * 3600}         # 2 hours for unclaimed (using special value -1 for this)

        # Sleep times between commands
        self.submit_sleep = 0.2
        self.remove_sleep = 0.2
        self.release_sleep = 0.2

        # Max commands per cycle
        self.max_submits = 100
        self.max_cluster_size = 10
        self.max_removes = 5
        self.max_releases = 20

        # monitoring objects
        # create them for the logging to occur
        self.client_internals = None
        self.client_stats = None # this one is indexed by client name
        self.qc_stats = None     # this one is indexed by security class
        self.log_stats = None
        self.rrd_stats = None

        self.supported_signtypes = ['sha1']

        # who am I
        self.factory_name = None
        self.glidein_name = None
        # do not add the entry_name, as we may decide someday to share
        # the same process between multiple entries

        # used directories
        self.submit_dir = None
        self.log_base_dir = None
        self.client_log_base_dir = None
        self.client_proxies_base_dir = None

    def config_whoamI(self, factory_name, glidein_name):
        self.factory_name = factory_name
        self.glidein_name = glidein_name

    def config_dirs(self, submit_dir, log_base_dir, client_log_base_dir, client_proxies_base_dir):
        self.submit_dir = submit_dir
        self.log_base_dir = log_base_dir
        self.client_log_base_dir = client_log_base_dir
        self.client_proxies_base_dir = client_proxies_base_dir

    def config_submit_freq(self, sleepBetweenSubmits, maxSubmitsXCycle):
        self.submit_sleep = sleepBetweenSubmits
        self.max_submits = maxSubmitsXCycle

    def config_remove_freq(self, sleepBetweenRemoves, maxRemovesXCycle):
        self.remove_sleep = sleepBetweenRemoves
        self.max_removes = maxRemovesXCycle

    def get_client_log_dir(self, entry_name, username):
        log_dir = os.path.join(self.client_log_base_dir, "user_%s/glidein_%s/entry_%s" % (username, self.glidein_name, entry_name))
        return log_dir

    def get_client_proxies_dir(self, username):
        proxy_dir = os.path.join(self.client_proxies_base_dir, "user_%s/glidein_%s" % (username, self.glidein_name))
        return proxy_dir


# global configuration of the module
factoryConfig = FactoryConfig()

############################################################
#
def secClass2Name(client_security_name, proxy_security_class):
    return "%s_%s" % (client_security_name, proxy_security_class)

############################################################
#

############################################################
#
# User functions
#
############################################################

#
# Get Condor data, given the glidein name
# To be passed to the main functions
#

def getCondorQData(entry_name,
                   client_name, # if None, return all clients
                   schedd_name,
                   factory_schedd_attribute=None, # if None, use the global one
                   glidein_schedd_attribute=None, # if None, use the global one
                   entry_schedd_attribute=None, # if None, use the global one
                   client_schedd_attribute=None, # if None, use the global one
                   credential_secclass_schedd_attribute=None): # if None, use the global one
    global factoryConfig

    if factory_schedd_attribute == None:
        fsa_str = factoryConfig.factory_schedd_attribute
    else:
        fsa_str = factory_schedd_attribute

    if glidein_schedd_attribute == None:
        gsa_str = factoryConfig.glidein_schedd_attribute
    else:
        gsa_str = glidein_schedd_attribute

    if entry_schedd_attribute == None:
        esa_str = factoryConfig.entry_schedd_attribute
    else:
        esa_str = entry_schedd_attribute

    if client_schedd_attribute == None:
        csa_str = factoryConfig.client_schedd_attribute
    else:
        csa_str = client_schedd_attribute

    if credential_secclass_schedd_attribute == None:
        xsa_str = factoryConfig.credential_secclass_schedd_attribute
    else:
        xsa_str = credential_secclass_schedd_attribute

    if client_name == None:
        client_constraint = ""
    else:
        client_constraint = ' && (%s =?= "%s")' % (csa_str, client_name)

    cred_id_str = factoryConfig.credential_id_schedd_attribute

    q_glidein_constraint = '(%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s")%s && (%s =!= UNDEFINED)' % \
        (fsa_str, factoryConfig.factory_name, gsa_str, factoryConfig.glidein_name, esa_str, entry_name, client_constraint, cred_id_str)
    q_glidein_format_list = [("JobStatus", "i"), ("GridJobStatus", "s"), ("ServerTime", "i"), ("EnteredCurrentStatus", "i"),
                             (factoryConfig.credential_id_schedd_attribute, "s"), ("HoldReasonCode", "i"), ("HoldReasonSubCode", "i"),
                             (csa_str, "s"), (xsa_str, "s")]

    q = condorMonitor.CondorQ(schedd_name)
    q.factory_name = factoryConfig.factory_name
    q.glidein_name = factoryConfig.glidein_name
    q.entry_name = entry_name
    q.client_name = client_name
    q.load(q_glidein_constraint, q_glidein_format_list)
    return q


def getQProxSecClass(condorq, client_name, proxy_security_class,
                     client_schedd_attribute=None, # if None, use the global one
                     credential_secclass_schedd_attribute=None): # if None, use the global one
    """
    Get the current queue status for client and security class.
    """

    if client_schedd_attribute == None:
        csa_str = factoryConfig.client_schedd_attribute
    else:
        csa_str = client_schedd_attribute

    if credential_secclass_schedd_attribute == None:
        xsa_str = factoryConfig.credential_secclass_schedd_attribute
    else:
        xsa_str = credential_secclass_schedd_attribute

    entry_condorQ = condorMonitor.SubQuery(condorq, lambda d:(d.has_key(csa_str) and (d[csa_str] == client_name) and
                                                           d.has_key(xsa_str) and (d[xsa_str] == proxy_security_class)))
    entry_condorQ.schedd_name = condorq.schedd_name
    entry_condorQ.factory_name = condorq.factory_name
    entry_condorQ.glidein_name = condorq.glidein_name
    entry_condorQ.entry_name = condorq.entry_name
    entry_condorQ.client_name = condorq.client_name
    entry_condorQ.load()
    return entry_condorQ

def getQStatus(condorq):
    qc_status = condorMonitor.Summarize(condorq, hash_status).countStored()
    return qc_status

def getQStatusStale(condorq):
    qc_status = condorMonitor.Summarize(condorq, hash_statusStale).countStored()
    return qc_status

def getCondorStatusData(entry_name, client_name, pool_name=None,
                        factory_startd_attribute=None, # if None, use the global one
                        glidein_startd_attribute=None, # if None, use the global one
                        entry_startd_attribute=None, # if None, use the global one
                        client_startd_attribute=None):  # if None, use the global one
    global factoryConfig

    if factory_startd_attribute == None:
        fsa_str = factoryConfig.factory_startd_attribute
    else:
        fsa_str = factory_startd_attribute

    if glidein_startd_attribute == None:
        gsa_str = factoryConfig.glidein_startd_attribute
    else:
        gsa_str = glidein_startd_attribute

    if entry_startd_attribute == None:
        esa_str = factoryConfig.entry_startd_attribute
    else:
        esa_str = entry_startd_attribute

    if client_startd_attribute == None:
        csa_str = factoryConfig.client_startd_attribute
    else:
        csa_str = client_startd_attribute

    status_glidein_constraint = '(%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s") && (%s =?= "%s")' % \
        (fsa_str, factoryConfig.factory_name, gsa_str, factoryConfig.glidein_name, esa_str, entry_name, csa_str, client_name)
    status = condorMonitor.CondorStatus(pool_name=pool_name)
    status.factory_name = factoryConfig.factory_name
    status.glidein_name = factoryConfig.glidein_name
    status.entry_name = entry_name
    status.client_name = client_name
    status.load(status_glidein_constraint)
    return status


#
# Create/update the proxy file
# returns the proxy fname
def update_x509_proxy_file(entry_name, username, client_id, proxy_data):

    proxy_dir = factoryConfig.get_client_proxies_dir(username)
    fname_short = 'x509_%s.proxy' % escapeParam(client_id)
    fname = os.path.join(proxy_dir, fname_short)

    if username != MY_USERNAME:
        # use privsep
        # all args go through the environment, so they are protected
        update_proxy_env = ['HEXDATA=%s' % binascii.b2a_hex(proxy_data), 'FNAME=%s' % fname]
        for var in ('PATH', 'LD_LIBRARY_PATH', 'PYTHON_PATH'):
            if os.environ.has_key(var):
                update_proxy_env.append('%s=%s' % (var, os.environ[var]))

        try:
            condorPrivsep.execute(username, factoryConfig.submit_dir, os.path.join(factoryConfig.submit_dir, 'update_proxy.py'), ['update_proxy.py'], update_proxy_env)
        except condorPrivsep.ExeError, e:
            raise RuntimeError, "Failed to update proxy %s in %s (user %s): %s" % (client_id, proxy_dir, username, e)
        except:
            raise RuntimeError, "Failed to update proxy %s in %s (user %s): Unknown privsep error" % (client_id, proxy_dir, username)
        return fname
    else:
        # do it natively when you can
        if not os.path.isfile(fname):
            # new file, create
            fd = os.open(fname, os.O_CREAT | os.O_WRONLY, 0600)
            try:
                os.write(fd, proxy_data)
            finally:
                os.close(fd)
            return fname

        # old file exists, check if same content
        fl = open(fname, 'r')
        try:
            old_data = fl.read()
        finally:
            fl.close()
        if proxy_data == old_data:
            # nothing changed, done
            return fname

        #
        # proxy changed, neeed to update
        #

        # remove any previous backup file
        try:
            os.remove(fname + ".old")
        except:
            pass # just protect

        # create new file
        fd = os.open(fname + ".new", os.O_CREAT | os.O_WRONLY, 0600)
        try:
            os.write(fd, proxy_data)
        finally:
            os.close(fd)

        # move the old file to a tmp and the new one into the official name
        try:
            os.rename(fname, fname + ".old")
        except:
            pass # just protect
        os.rename(fname + ".new", fname)
        return fname

    # end of update_x509_proxy_file
    # should never reach this point

#
# Main function
#   Will keep the required number of Idle glideins
#
class ClientWebNoGroup:
    def __init__(self, client_web_url, client_signtype, client_descript, client_sign):

        if not (client_signtype in factoryConfig.supported_signtypes):
            raise ValueError, "Signtype '%s' not supported!" % client_signtype

        self.url = client_web_url
        self.signtype = client_signtype
        self.descript = client_descript
        self.sign = client_sign

    def get_glidein_args(self):
        return ["-clientweb", self.url, "-clientsign", self.sign, "-clientsigntype",
                self.signtype, "-clientdescript", self.descript]


class ClientWeb(ClientWebNoGroup):
    def __init__(self, client_web_url, client_signtype, client_descript, client_sign,
                 client_group, client_group_web_url, client_group_descript, client_group_sign):

        ClientWebNoGroup.__init__(self, client_web_url, client_signtype, client_descript, client_sign)
        self.group_name = client_group
        self.group_url = client_group_web_url
        self.group_descript = client_group_descript
        self.group_sign = client_group_sign

    def get_glidein_args(self):
        return (ClientWebNoGroup.get_glidein_args(self) +
                ["-clientgroup", self.group_name, "-clientwebgroup", self.group_url, "-clientsigngroup",
                 self.group_sign, "-clientdescriptgroup", self.group_descript])


def keepIdleGlideins(client_condorq, client_int_name,
                     in_downtime, remove_excess_wait, remove_excess_idle, remove_excess_running,
                     min_nr_idle, max_nr_running, max_held,
                     submit_credentials,
                     client_web, # None means client did not pass one, backwards compatibility
                     params):
    """
    Looks at the status of the queue and determines how many glideins to submit.  Returns the number of newly submitted glideins.

    @type client_condorq: CondorQ
    @param client_condorq: Condor queue filtered by security class
    @type client_int_name: string
    @param client_int_name: internal representation of the client name
    @type in_downtime: boolean
    @param in_downtime: is this entry in downtime
    @type remove_excess_wait: boolean
    @param remove_excess_wait: remove unsubmitted glideins
    @type remove_excess_idle: boolean
    @param remove_excess_idle: remove idle glideins
    @type remove_excess_running: boolean
    @param remove_excess_running: remove running glideins
    @type min_nr_idle: int
    @param min_nr_idle: min number of idle glideins needed
    @type max_nr_running: int
    @param max_nr_running: max number of running glideins allowed
    @type max_held: int
    @param max_held: max number of held glidiens allowed
    @type submit_credentials: SubmitCredentials
    @param submit_credentials: all the information needed to submit the glideins
    @type client_web: glideFactoryLib.ClientWeb or glideFactoryLib.ClientWebNoGroup
    @param client_web: client web values
    @type params: dict
    @param params: params from the entry configuration or frontend to be passed to the glideins

    Can throw a condorExe.ExeError
    """

    global factoryConfig

    # filter out everything but the proper credential identifier
    condorq = condorMonitor.SubQuery(client_condorq, lambda d:(d[factoryConfig.credential_id_schedd_attribute] == submit_credentials.id))
    condorq.schedd_name = client_condorq.schedd_name
    condorq.factory_name = client_condorq.factory_name
    condorq.glidein_name = client_condorq.glidein_name
    condorq.entry_name = client_condorq.entry_name
    condorq.client_name = client_condorq.client_name
    condorq.load()
    condorq.credentials_id = submit_credentials.id

    # First check if we have enough glideins in the queue

    # Count glideins by status
    qc_status = getQStatus(condorq)

    #   Held==JobStatus(5)
    held_glideins = 0
    if qc_status.has_key(5):
        held_glideins = qc_status[5]

    #   Idle==Jobstatus(1)
    sum_idle_count(qc_status)
    idle_glideins = qc_status[1]

    #   Running==Jobstatus(2)
    if qc_status.has_key(2):
        running_glideins = qc_status[2]
    else:
        running_glideins = 0

    logSupport.log.debug("Before submission, the queue contains:")
    logSupport.log.debug("   %i idle glideins")
    logSupport.log.debug("   %i running glideins")
    logSupport.log.debug("   %i held glideins")
    logSupport.log.debug("Before submission, the request contains:")
    logSupport.log.debug("   %i min nr idle glideins")
    logSupport.log.debug("   %i max nr running glideins")
    logSupport.log.debug("   %i max held glideins")
        
    # if idle is < min idle and (either no max specified or running + idle is < max)
    if ((idle_glideins < min_nr_idle) and ((max_nr_running == None) or ((running_glideins + idle_glideins) < max_nr_running))):
        # need more glideins, submit
        stat_str = "min_idle=%i, idle=%i, running=%i" % (min_nr_idle, idle_glideins, running_glideins)
        if max_nr_running != None:
            stat_str = "%s, max_running=%i" % (stat_str, max_nr_running)
        logSupport.log.info("Need more glideins: %s" % stat_str)

        if in_downtime:  #MERGENOTE -- check v2 around line 526
            logSupport.log.info("In downtime, not submitting")
            return 0

        if held_glideins > max_held:
            logSupport.log.info("Too many held (%s>%s), not submitting" % (held_glideins, max_held))
            return 0

        add_glideins = min_nr_idle - idle_glideins
        if ((max_nr_running != None) and ((running_glideins + idle_glideins + add_glideins) > max_nr_running)):
            # never exceed max_nr_running
            add_glideins = max_nr_running - (running_glideins + idle_glideins)

        try:
            logSupport.log.debug("Submitting %i glideins" % add_glideins)
            submitGlideins(condorq.entry_name, client_int_name, add_glideins, submit_credentials, client_web, params)
            return add_glideins # exit, some submitted
        except RuntimeError, e:
            logSupport.log.warning("%s" % e)
            return 0 # something is wrong... assume 0 and exit
        except:
            logSupport.log.warning("Unexpected error in glideFactoryLib.submitGlideins")
            return 0 # something is wrong... assume 0 and exit

    elif (((remove_excess_wait or remove_excess_idle) and (idle_glideins > min_nr_idle)) or
          (remove_excess_running and ((max_nr_running != None) and  #make sure there is a max
            ((running_glideins + idle_glideins) > max_nr_running)))):
        # too many glideins, remove
        remove_nr = idle_glideins - min_nr_idle
        if (remove_excess_running and ((max_nr_running != None) and  #make sure there is a max
             ((running_glideins + idle_glideins) > max_nr_running))):

            remove_all_nr = (running_glideins + idle_glideins) - max_nr_running
            if remove_all_nr > remove_nr:
                # if we are past max_run, then min_idle does not make sense to start with
                remove_nr = remove_all_nr

        idle_list = extractIdleUnsubmitted(condorq)

        if remove_excess_wait and (len(idle_list) > 0):
            # remove unsubmitted first, if any
            if len(idle_list) > remove_nr:
                idle_list = idle_list[:remove_nr] #shorten

            stat_str = "min_idle=%i, idle=%i, unsubmitted=%i" % (min_nr_idle, idle_glideins, len(idle_list))
            logSupport.log.info("Too many glideins: %s" % stat_str)
            logSupport.log.info("Removing %i unsubmitted idle glideins" % len(idle_list))
            removeGlideins(condorq.schedd_name, idle_list)
            return 1 # stop here... the others will be retried in next round, if needed

        idle_list = extractIdleQueued(condorq)
        if remove_excess_idle and (len(idle_list) > 0):
            # no unsubmitted, go for all the others now
            if len(idle_list) > remove_nr:
                idle_list = idle_list[:remove_nr] #shorten
            stat_str = "min_idle=%i, idle=%i, unsubmitted=%i" % (min_nr_idle, idle_glideins, 0)
            logSupport.log.info("Too many glideins: %s" % stat_str)
            logSupport.log.info("Removing %i idle glideins" % len(idle_list))
            removeGlideins(condorq.schedd_name, idle_list)
            return 1 # exit, even if no submitted

        if remove_excess_running:
            # no idle left, remove anything you can

            stat_str = "idle=%i, running=%i, max_running=%i" % (idle_glideins, running_glideins, max_nr_running)
            logSupport.log.info("Too many glideins: %s" % stat_str)

            run_list = extractRunSimple(condorq)
            if len(run_list) > remove_nr:
                run_list = run_list[:remove_nr] #shorten
            logSupport.log.info("Removing %i running glideins" % len(run_list))

            rm_list = run_list

            #
            # Remove Held as well
            # No reason to keep them alive if we are about to kill running glideins anyhow
            #

            logSupport.log.info("No glideins requested.")
            # Check if there are held glideins that are not recoverable
            unrecoverable_held_list = extractUnrecoverableHeldSimple(condorq)
            if len(unrecoverable_held_list) > 0:
                logSupport.log.info("Removing %i unrecoverable held glideins" % len(unrecoverable_held_list))
                rm_list += unrecoverable_held_list

            # Check if there are held glideins
            held_list = extractRecoverableHeldSimple(condorq)
            if len(held_list) > 0:
                logSupport.log.info("Removing %i held glideins" % len(held_list))
                rm_list += held_list

            removeGlideins(condorq.schedd_name, rm_list)
            return 1 # exit, even if no submitted

    elif remove_excess_running and (max_nr_running == 0) and (held_glideins > 0):
        # no glideins desired, remove all held
        # (only held should be left at this point... idle and running addressed above)

        # Check if there are held glideins that are not recoverable
        unrecoverable_held_list = extractUnrecoverableHeldSimple(condorq)
        if len(unrecoverable_held_list) > 0:
            logSupport.log.info("Removing %i unrecoverable held glideins" % len(unrecoverable_held_list))

        # Check if there are held glideins
        held_list = extractRecoverableHeldSimple(condorq)
        if len(held_list) > 0:
            logSupport.log.info("Removing %i held glideins" % len(held_list))

        removeGlideins(condorq.schedd_name, unrecoverable_held_list + held_list)
        return 1 # exit, even if no submitted

    return 0

#
# Sanitizing function
#   Can be used if we the glidein connect to a reachable Collector
#

def sanitizeGlideins(condorq, status):
    global factoryConfig

    # Check if some glideins have been in idle state for too long
    stale_list = extractStale(condorq, status)
    if len(stale_list) > 0:
        logSupport.log.warning("Found %i stale glideins" % len(stale_list))
        removeGlideins(condorq.schedd_name, stale_list)

    # Check if some glideins have been in running state for too long
    runstale_list = extractRunStale(condorq)
    if len(runstale_list) > 0:
        logSupport.log.warning("Found %i stale (>%ih) running glideins" % (len(runstale_list), factoryConfig.stale_maxage[2] / 3600))
        removeGlideins(condorq.schedd_name, runstale_list)

    # Check if there are held glideins that are not recoverable
    unrecoverable_held_list = extractUnrecoverableHeld(condorq, status)
    if len(unrecoverable_held_list) > 0:
        logSupport.log.warning("Found %i unrecoverable held glideins" % len(unrecoverable_held_list))
        removeGlideins(condorq.schedd_name, unrecoverable_held_list, force=False)

    # Check if there are held glideins
    held_list = extractRecoverableHeld(condorq, status)
    if len(held_list) > 0:
        logSupport.log.warning("Found %i held glideins" % len(held_list))
        releaseGlideins(condorq.schedd_name, held_list)

    # Now look for VMs that have not been claimed for a long time
    staleunclaimed_list = extractStaleUnclaimed(condorq, status)
    if len(staleunclaimed_list) > 0:
        logSupport.log.warning("Found %i stale unclaimed glideins" % len(staleunclaimed_list))
        removeGlideins(condorq.schedd_name, staleunclaimed_list)

    #
    # A check of glideins in "Running" state but not in status
    # should be implemented, too
    # However, it needs some sort of history to account for
    # temporary network outages
    #

    return

def sanitizeGlideinsSimple(condorq):
    global factoryConfig

    # Check if some glideins have been in idle state for too long
    stale_list = extractStaleSimple(condorq)
    if len(stale_list) > 0:
        logSupport.log.warning("Found %i stale glideins" % len(stale_list))
        removeGlideins(condorq.schedd_name, stale_list)

    # Check if some glideins have been in running state for too long
    runstale_list = extractRunStale(condorq)
    if len(runstale_list) > 0:
        logSupport.log.warning("Found %i stale (>%ih) running glideins" % (len(runstale_list), factoryConfig.stale_maxage[2] / 3600))
        removeGlideins(condorq.schedd_name, runstale_list)

    # Check if there are held glideins that are not recoverable
    unrecoverable_held_list = extractUnrecoverableHeldSimple(condorq)
    if len(unrecoverable_held_list) > 0:
        logSupport.log.warning("Found %i unrecoverable held glideins" % len(unrecoverable_held_list))
        removeGlideins(condorq.schedd_name, unrecoverable_held_list, force=False)

    # Check if there are held glideins
    held_list = extractRecoverableHeldSimple(condorq)
    if len(held_list) > 0:
        logSupport.log.warning("Found %i held glideins" % len(held_list))
        releaseGlideins(condorq.schedd_name, held_list)

    return

def logStats(condorq, condorstatus, client_int_name, client_security_name, proxy_security_class):
    global factoryConfig
    #
    # First check if we have enough glideins in the queue
    #

    # Count glideins by status
    qc_status = getQStatus(condorq)
    sum_idle_count(qc_status)
    if condorstatus != None:
        s_running_str = " collector running %s" % len(condorstatus.fetchStored().keys())
    else:
        s_running_str = "" # not monitored

    logSupport.log.info("Client %s (secid: %s_%s) schedd status %s%s" % (client_int_name, client_security_name,
                                                                         proxy_security_class, qc_status, s_running_str))
    if factoryConfig.qc_stats != None:
        client_log_name = secClass2Name(client_security_name, proxy_security_class)
        factoryConfig.client_stats.logSchedd(client_int_name, qc_status)
        factoryConfig.qc_stats.logSchedd(client_log_name, qc_status)

    return

#def logWorkRequests(work):
#    for work_key in work.keys():
#        if work[work_key]['requests'].has_key('IdleGlideins'):
#            log_files.logActivity(Support.log.infoesting %i glideins"%(work[work_key]['internals']["ClientName"],work[work_key]['requests']['IdleGlideins']))
#            log_files.logActivilogSupport.log.infok[work_key]['params'])
#            log_files.logActivilogSupport.log.info Names: %s"%work[work_key]['params_decrypted'].keys()) # cannot log decrypted ones... they are most likely sensitive
#            factoryConfig.qc_stats.logRequest(work[work_key]['internals']["ClientName"],work[work_key]['requests'],work[work_key]['params'])
#            factoryConfig.qc_stats.logClientMonitor(work[work_key]['internals']["ClientName"],work[work_key]['monitor'],work[work_key]['internals'])

def logWorkRequest(client_int_name, client_security_name, proxy_security_class,
                   req_idle, req_max_run, work_el, fraction=1.0):
    # temporary workaround; the requests should always be processed at the caller level
    if work_el['requests'].has_key('RemoveExcess'):
        remove_excess = work_el['requests']['RemoveExcess']
    else:
        remove_excess = 'NO'

    client_log_name = secClass2Name(client_security_name, proxy_security_class)

    logSupport.log.info("Client %s (secid: %s) requesting %i glideins, max running %i, remove excess '%s'" % (client_int_name, client_log_name, req_idle, req_max_run, remove_excess))
    logSupport.log.info("  Params: %s" % work_el['params'])
    logSupport.log.info("  Decrypted Param Names: %s" % work_el['params_decrypted'].keys()) # cannot log decrypted ones... they are most likely sensitive

    reqs = {'IdleGlideins':req_idle, 'MaxRunningGlideins':req_max_run}
    factoryConfig.client_stats.logRequest(client_int_name, reqs)
    factoryConfig.qc_stats.logRequest(client_log_name, reqs)

    factoryConfig.client_stats.logClientMonitor(client_int_name, work_el['monitor'], work_el['internals'], fraction)
    factoryConfig.qc_stats.logClientMonitor(client_log_name, work_el['monitor'], work_el['internals'], fraction)

############################################################
#
# I N T E R N A L - Do not use
#
############################################################

#condor_status_strings = {0:"Wait",1:"Idle", 2:"Running", 3:"Removed", 4:"Completed", 5:"Held", 6:"Suspended", 7:"Assigned"}
#myvm_status_strings = {-1:"Unclaimed}

#
# Hash functions
#

def get_status_glideidx(el):
    global factoryConfig
    return (el[factoryConfig.clusterid_startd_attribute], el[factoryConfig.procid_startd_attribute])

# Split idle depending on GridJobStatus
#   1001 : Unsubmitted
#   1002 : Submitted/Pending
#   1010 : Staging in
#   1100 : Other
#   4010 : Staging out
# All others just return the JobStatus
def hash_status(el):
    job_status = el["JobStatus"]
    if job_status == 1:
        # idle jobs, look of GridJobStatus
        if el.has_key("GridJobStatus"):
            grid_status=el["GridJobStatus"]
            if grid_status in ("PENDING","INLRMS: Q","PREPARED","SUBMITTING","IDLE","SUSPENDED","REGISTERED"):
                return 1002
            elif grid_status in ("STAGE_IN", "PREPARING", "ACCEPTING"):
                return 1010
            else:
                return 1100
        else:
            return 1001
    elif job_status == 2:
        # count only real running, all others become Other
        if el.has_key("GridJobStatus"):
            grid_status=el["GridJobStatus"]
            if grid_status in ("ACTIVE","REALLY-RUNNING","INLRMS: R","RUNNING"):
                return 2
            elif grid_status in ("STAGE_OUT", "INLRMS: E", "EXECUTED", "FINISHING", "DONE"):
                return 4010
            else:
                return 1100
        else:
            return 2
    else:
        # others just pass over
        return job_status

# helper function that sums up the idle states
def sum_idle_count(qc_status):
    #   Idle==Jobstatus(1)
    #   Have to integrate all the variants
    qc_status[1] = 0
    for k in qc_status.keys():
        if (k >= 1000) and (k < 1100):
            qc_status[1] += qc_status[k]
    return

def hash_statusStale(el):
    global factoryConfig
    age = el["ServerTime"] - el["EnteredCurrentStatus"]
    jstatus = el["JobStatus"]
    if factoryConfig.stale_maxage.has_key(jstatus):
        return [jstatus, age > factoryConfig.stale_maxage[jstatus]]
    else:
        return [jstatus, 0] # others are not stale


#
# diffList == base_list - subtract_list
#

def diffList(base_list, subtract_list):
    if len(subtract_list) == 0:
        return base_list # nothing to do

    out_list = []
    for i in base_list:
        if not (i in subtract_list):
            out_list.append(i)

    return out_list

#
# Extract functions
# Will compare with the status info to make sure it does not show good ones
#

# return list of glidein clusters within the search list
def extractRegistered(q, status, search_list):
    global factoryConfig
    sdata = status.fetchStored(lambda el:(el[factoryConfig.schedd_startd_attribute] == q.schedd_name) and (get_status_glideidx(el) in search_list))

    out_list = []
    for vm in sdata.keys():
        el = sdata[vm]
        i = get_status_glideidx(el)
        if not (i in out_list): # prevent duplicates from multiple VMs
            out_list.append(i)

    return out_list


def extractStale(q, status):
    # first find out the stale idle jids
    #  hash: (Idle==1, Stale==1)
    qstale = q.fetchStored(lambda el:(hash_statusStale(el) == [1, 1]))
    qstale_list = qstale.keys()

    # find out if any "Idle" glidein is running instead (in condor_status)
    sstale_list = extractRegistered(q, status, qstale_list)

    return diffList(qstale_list, sstale_list)

def extractStaleSimple(q):
    # first find out the stale idle jids
    #  hash: (Idle==1, Stale==1)
    qstale = q.fetchStored(lambda el:(hash_statusStale(el) == [1, 1]))
    qstale_list = qstale.keys()

    return qstale_list

def extractUnrecoverableHeld(q, status):
    # first find out the held jids that are not recoverable
    #  Held==5 and glideins are not recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld = q.fetchStored(lambda el:(el["JobStatus"] == 5 and isGlideinUnrecoverable(el)))
    qheld_list = qheld.keys()

    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list = extractRegistered(q, status, qheld_list)
    return diffList(qheld_list, sheld_list)

def extractUnrecoverableHeldSimple(q):
    #  Held==5 and glideins are not recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld = q.fetchStored(lambda el:(el["JobStatus"] == 5 and isGlideinUnrecoverable(el)))
    qheld_list = qheld.keys()
    return qheld_list

def extractRecoverableHeld(q, status):
    # first find out the held jids
    #  Held==5 and glideins are recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld = q.fetchStored(lambda el:(el["JobStatus"] == 5 and not isGlideinUnrecoverable(el)))
    qheld_list = qheld.keys()

    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list = extractRegistered(q, status, qheld_list)

    return diffList(qheld_list, sheld_list)

def extractRecoverableHeldSimple(q):
    #  Held==5 and glideins are recoverable
    #qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld = q.fetchStored(lambda el:(el["JobStatus"] == 5 and not isGlideinUnrecoverable(el)))
    qheld_list = qheld.keys()
    return qheld_list

def extractHeld(q, status):

    # first find out the held jids
    #  Held==5
    qheld = q.fetchStored(lambda el:el["JobStatus"] == 5)
    qheld_list = qheld.keys()

    # find out if any "Held" glidein is running instead (in condor_status)
    sheld_list = extractRegistered(q, status, qheld_list)

    return diffList(qheld_list, sheld_list)

def extractHeldSimple(q):
    #  Held==5
    qheld = q.fetchStored(lambda el:el["JobStatus"] == 5)
    qheld_list = qheld.keys()
    return qheld_list

def extractIdleSimple(q):
    #  Idle==1
    qidle = q.fetchStored(lambda el:el["JobStatus"] == 1)
    qidle_list = qidle.keys()
    return qidle_list

def extractIdleUnsubmitted(q):
    #  1001 == Unsubmitted
    qidle = q.fetchStored(lambda el:hash_status(el) == 1001)
    qidle_list = qidle.keys()
    return qidle_list

def extractIdleQueued(q):
    #  All 1xxx but 1001
    qidle = q.fetchStored(lambda el:(hash_status(el) in (1002, 1010, 1100)))
    qidle_list = qidle.keys()
    return qidle_list

def extractNonRunSimple(q):
    #  Run==2
    qnrun = q.fetchStored(lambda el:el["JobStatus"] != 2)
    qnrun_list = qnrun.keys()
    return qnrun_list

def extractRunSimple(q):
    #  Run==2
    qrun = q.fetchStored(lambda el:el["JobStatus"] == 2)
    qrun_list = qrun.keys()
    return qrun_list

def extractRunStale(q):
    # first find out the stale running jids
    #  hash: (Running==2, Stale==1)
    qstale = q.fetchStored(lambda el:(hash_statusStale(el) == [2, 1]))
    qstale_list = qstale.keys()

    # no need to check with condor_status
    # these glideins were running for too long, period!
    return qstale_list

# helper function of extractStaleUnclaimed
def group_unclaimed(el_list):
    out = {"nr_vms":0, "nr_unclaimed":0, "min_unclaimed_time":1024 * 1024 * 1024}
    for el in el_list:
        out["nr_vms"] += 1
        if el["State"] == "Unclaimed":
            out["nr_unclaimed"] += 1
            unclaimed_time = el["LastHeardFrom"] - el["EnteredCurrentState"]
            if unclaimed_time < out["min_unclaimed_time"]:
                out["min_unclaimed_time"] = unclaimed_time
    return out

def extractStaleUnclaimed(q, status):
    global factoryConfig
    # first find out the active running jids
    #  hash: (Running==2, Stale==0)
    qsearch = q.fetchStored(lambda el:(hash_statusStale(el) == [2, 0]))
    search_list = qsearch.keys()

    # find out if any "Idle" glidein is running instead (in condor_status)
    global factoryConfig
    sgroup = condorMonitor.Group(status, lambda el:get_status_glideidx(el), group_unclaimed)
    sgroup.load(lambda el:(el[factoryConfig.schedd_startd_attribute] == q.schedd_name) and (get_status_glideidx(el) in search_list))
    sdata = sgroup.fetchStored(lambda el:(el["nr_unclaimed"] > 0) and (el["min_unclaimed_time"] > factoryConfig.stale_maxage[-1]))

    return sdata.keys()

############################################################
#
# Action functions
#
############################################################

def schedd_name2str(schedd_name):
    if schedd_name == None:
        return ""
    else:
        return "-name %s" % schedd_name

extractJobId_recmp = re.compile("^(?P<count>[0-9]+) job\(s\) submitted to cluster (?P<cluster>[0-9]+)\.$")
def extractJobId(submit_out):
    for line in submit_out:
        found = extractJobId_recmp.search(line[:-1])
        if found != None:
            return (long(found.group("cluster")), int(found.group("count")))
    raise condorExe.ExeError, "Could not find cluster info!"

escape_table = {'.':'.dot,',
                ',':'.comma,',
                '&':'.amp,',
                '\\':'.backslash,',
                '|':'.pipe,',
                "`":'.fork,',
                '"':'.quot,',
                "'":'.singquot,',
                '=':'.eq,',
                '+':'.plus,',
                '-':'.minus,',
                '<':'.lt,',
                '>':'.gt,',
                '(':'.open,',
                ')':'.close,',
                '{':'.gopen,',
                '}':'.gclose,',
                '[':'.sopen,',
                ']':'.sclose,',
                '#':'.comment,',
                '$':'.dollar,',
                '*':'.star,',
                '?':'.question,',
                '!':'.not,',
                '~':'.tilde,',
                ':':'.colon,',
                ';':'.semicolon,',
                ' ':'.nbsp,'}
def escapeParam(param_str):
    global escape_table
    out_str = ""
    for c in param_str:
        if escape_table.has_key(c):
            out_str = out_str + escape_table[c]
        else:
            out_str = out_str + c
    return out_str


# submit N new glideins
def submitGlideins(entry_name, client_name, nr_glideins,
                   submit_credentials, client_web, # None means client did not pass one, backwards compatibility
                   params):
    global factoryConfig

    # get the username
    username = submit_credentials.username

    # Need information from glidein.descript, job.descript, and signatures.sha1
    jobDescript = glideFactoryConfig.JobDescript(entry_name)
    schedd = jobDescript.data["Schedd"]

    # List of job ids that have been submitted - initialize to empty array
    submitted_jids = []

    # if we are requesting more than the maximum glideins that we can submit at one time,
    # then set to the max submit number
    if nr_glideins > factoryConfig.max_submits:
        nr_glideins = factoryConfig.max_submits

    try:
        exe_env = get_submit_environment(entry_name, client_name, submit_credentials, client_web, params)
    except Exception, e:
        msg = "Failed to setup execution environment.  Error:" % str(e)
        logSupport.log.error(msg)
        raise RuntimeError, msg

    try:
        nr_submitted = 0
        while (nr_submitted < nr_glideins):
            if nr_submitted != 0:
                time.sleep(factoryConfig.submit_sleep)

            nr_to_submit = (nr_glideins - nr_submitted)
            if nr_to_submit > factoryConfig.max_cluster_size:
                nr_to_submit = factoryConfig.max_cluster_size

            exe_env.append('GLIDEIN_COUNT=%s' % nr_to_submit)

            # check to see if the username for the proxy is the same as the factory username
            if username != MY_USERNAME:
                # no? use privsep
                # need to push all the relevant env variables through
                for var in os.environ.keys():
                    if ((var in ('PATH', 'LD_LIBRARY_PATH', 'X509_CERT_DIR')) or (var[:8] == '_CONDOR_') or (var[:7] == 'CONDOR_')):
                        if os.environ.has_key(var):
                            exe_env.append('%s=%s' % (var, os.environ[var]))
                try:
                    args = ["condor_submit", "-name", schedd, "entry_%s/job.condor" % entry_name]

                    msg = "About to submit using condorPrivsep::\n" \
                          "   username: %s\n" \
                          "   submit directory: %s\n" \
                          "   command: condor_submit\n" \
                          "   args: %s\n" \
                          "   exe_env: %s\n" \
                          "" % (username, factoryConfig.submit_dir, str(args), str(exe_env))
                    logSupport.log.debug(msg)

                    submit_out = condorPrivsep.condor_execute(username, factoryConfig.submit_dir, "condor_submit", args, env=exe_env)
                except condorPrivsep.ExeError, e:
                    submit_out = []
                    msg = "condor_submit failed (user %s): %s" % (username, str(e))
                    logSupport.log.error(msg)
                    raise RuntimeError, msg
                except:
                    submit_out = []
                    msg = "condor_submit failed (user %s): Unknown privsep error" % username
                    logSupport.log.error(msg)
                    raise RuntimeError, msg
            else:
                # avoid using privsep, if possible
                try:
                    env = "; ".join(exe_env)
                    submit_out = condorExe.iexe_cmd("%s; condor_submit -name %s entry_%s/job.condor" % (env, schedd, entry_name))
                except condorExe.ExeError, e:
                    submit_out = []
                    msg = "condor_submit failed: %s" % str(e)
                    logSupport.log.error(msg)
                    raise RuntimeError, msg
                except Exception, e:
                    submit_out = []
                    msg = "condor_submit failed: Unknown error: %s" % str(e)
                    logSupport.log.error(msg)
                    raise RuntimeError, msg


            cluster, count = extractJobId(submit_out)
            for j in range(count):
                submitted_jids.append((cluster, j))
            nr_submitted += count
    finally:
        # write out no matter what
        logSupport.log.info("Submitted %i glideins to %s: %s" % (len(submitted_jids), schedd, submitted_jids))

# remove the glideins in the list
def removeGlideins(schedd_name, jid_list, force=False):
    ####
    # We are assuming the gfactory to be
    # a condor superuser and thus does not need
    # identity switching to remove jobs
    ####

    global factoryConfig

    removed_jids = []

    schedd_str = schedd_name2str(schedd_name)
    is_not_first = 0
    for jid in jid_list:
        if is_not_first:
            is_not_first = 1
            time.sleep(factoryConfig.remove_sleep)
        try:
            condorExe.exe_cmd("condor_rm", "%s %li.%li" % (schedd_str, jid[0], jid[1]))
            removed_jids.append(jid)

            # Force the removal if requested
            if force == True:
                try:
                    logSupport.log.info("Forcing the removal of glideins in X state")
                    condorExe.exe_cmd("condor_rm", "-forcex %s %li.%li" % (schedd_str, jid[0], jid[1]))
                except condorExe.ExeError, e:
                    logSupport.log.warning("Forcing the removal of glideins in %s.%s state failed" % (jid[0], jid[1]))

        except condorExe.ExeError, e:
            # silently ignore errors, and try next one
            logSupport.log.warning("removeGlidein(%s,%li.%li): %s" % (schedd_name, jid[0], jid[1], e))

        if len(removed_jids) >= factoryConfig.max_removes:
            break # limit reached, stop


    logSupport.log.info("Removed %i glideins on %s: %s" % (len(removed_jids), schedd_name, removed_jids))

# release the glideins in the list
def releaseGlideins(schedd_name, jid_list):
    ####
    # We are assuming the gfactory to be
    # a condor superuser and thus does not need
    # identity switching to release jobs
    ####

    global factoryConfig

    released_jids = []

    schedd_str = schedd_name2str(schedd_name)
    is_not_first = 0
    for jid in jid_list:
        if is_not_first:
            is_not_first = 1
            time.sleep(factoryConfig.release_sleep)
        try:
            condorExe.exe_cmd("condor_release", "%s %li.%li" % (schedd_str, jid[0], jid[1]))
            released_jids.append(jid)
        except condorExe.ExeError, e:
            logSupport.log.warning("releaseGlidein(%s,%li.%li): %s" % (schedd_name, jid[0], jid[1], e))

        if len(released_jids) >= factoryConfig.max_releases:
            break # limit reached, stop
    logSupport.log.info("Released %i glideins on %s: %s" % (len(released_jids), schedd_name, released_jids))

def get_submit_environment(entry_name, client_name, submit_credentials, client_web, params):
    try:
        # Need information from glidein.descript, job.descript, and signatures.sha1
        glideinDescript = glideFactoryConfig.GlideinDescript()
        jobDescript = glideFactoryConfig.JobDescript(entry_name)
        signatures = glideFactoryConfig.SignatureFile()

        # this is the parameter list that will be added to the arguments for glidein_startup.sh
        params_str = ""
        # if client_web has been provided, get the arguments and add them to the string
        if client_web != None:
            params_str = " ".join(client_web.get_glidein_args())
        # add all the params to the argument string
        for k in params.keys():
            params_str += " -param_%s %s" % (k, params[k])

        exe_env = ['X509_USER_PROXY=%s' % submit_credentials.security_credentials["SubmitProxy"]]
        exe_env.append('GLIDEIN_ENTRY_NAME=%s' % entry_name)
        exe_env.append('GLIDEIN_CLIENT=%s' % client_name)
        exe_env.append('GLIDEIN_SEC_CLASS=%s' % submit_credentials.security_class)

        # Glidein username (for client logs)
        exe_env.append('GLIDEIN_USER=%s' % submit_credentials.username)
        
        # Credential id, required for querying the condor q
        exe_env.append('GLIDEIN_CREDENTIAL_ID=%s' % submit_credentials.id)        

        # Entry Params (job.descript)
        schedd = jobDescript.data["Schedd"]
        verbosity = jobDescript.data["Verbosity"]
        startup_dir = jobDescript.data["StartupDir"]

        exe_env.append('GLIDEIN_SCHEDD=%s' % schedd)
        exe_env.append('GLIDEIN_VERBOSITY=%s' % verbosity)
        exe_env.append('GLIDEIN_STARTUP_DIR=%s' % startup_dir)

        submit_time = timeConversion.get_time_in_format(time_format="%Y%m%d")
        exe_env.append('GLIDEIN_LOGNR=%s' % str(submit_time))

        # Main Params (glidein.descript
        glidein_name = glideinDescript.data["GlideinName"]
        factory_name = glideinDescript.data["FactoryName"]
        web_url = glideinDescript.data["WebURL"]

        exe_env.append('GLIDEIN_NAME=%s' % glidein_name)
        exe_env.append('FACTORY_NAME=%s' % factory_name)
        exe_env.append('WEB_URL=%s' % web_url)
    
        # Security Params (signatures.sha1)
        # sign_type has always been hardcoded... we can change in the future if need be
        sign_type = "sha1"
        exe_env.append('SIGN_TYPE=%s' % sign_type)
    
        main_descript = signatures.data["main_descript"]
        main_sign = signatures.data["main_sign"]

        entry_descript = signatures.data["entry_%s_descript" % entry_name]
        entry_sign = signatures.data["entry_%s_sign" % entry_name]

        exe_env.append('MAIN_DESCRIPT=%s' % main_descript)
        exe_env.append('MAIN_SIGN=%s' % main_sign)
        exe_env.append('ENTRY_DESCRIPT=%s' % entry_descript)
        exe_env.append('ENTRY_SIGN=%s' % entry_sign)
    
        # Build the glidein pilot arguments
        glidein_arguments = "-v %s -name %s -entry %s -clientname %s -schedd %s " \
                            "-factory %s -web %s -sign %s -signentry %s -signtype %s " \
                            "-descript %s -descriptentry %s -dir %s -param_GLIDEIN_Client %s %s" % \
                            (verbosity, glidein_name, entry_name, client_name,
                             schedd, factory_name, web_url, main_sign, entry_sign,
                             sign_type, main_descript, entry_descript, startup_dir,
                             client_name, params_str)

        # get my (entry) type
        grid_type = jobDescript.data["GridType"]
        if grid_type == "ec2":
            exe_env.append('AMI_ID=%s' % params["AmiId"])
            exe_env.append('INSTANCE_TYPE=%s' % params["InstanceType"])
            exe_env.append('ACCESS_KEY_FILE=%s' % submit_credentials.security_credentials["PublicKey"])
            exe_env.append('SECRET_KEY_FILE=%s' % submit_credentials.security_credentials["PrivateKey"])
    
            # get the proxy
            full_path_to_proxy = submit_credentials.security_credentials["SubmitProxy"]
            proxy_file = os.path.basename(full_path_to_proxy)
            proxy_dir = os.path.dirname(full_path_to_proxy)
    
            cat_cmd = "/bin/cat"
            args = [cat_cmd, proxy_file]
            proxy_contents = condorPrivsep.execute(submit_credentials.username, proxy_dir, cat_cmd, args)
    
            ini_template = "[glidein_startup]\n" \
                            "args = %s\n" \
                            "webbase = %s\n" \
                            "proxy_file_name = pilot_proxy\n"
    
            if jobDescript.has_key("shutdownVM"):
                disable_shutdown = jobDescript["shutdownVM"]
                if disable_shutdown: ini_template += "disable_shutdown = True"
            ini = ini_template % (glidein_arguments, web_url)
    
            tarball = GlideinTar()
            tarball.add_string("glidein_userdata", ini)
            tarball.add_string("pilot_proxy", proxy_contents)
            binary_string = tarball.create_tar_blob()
            encoded_tarball = base64.b64encode(binary_string)
            exe_env.append('USER_DATA=%s' % encoded_tarball)
    
        else:
            # we add this here because the macros will be expanded when used in the gt2 submission
            # we don't add the macros to the arguments for the EC2 submission since condor will never 
            # see the macros
            glidein_arguments += " -cluster $(Cluster) -subcluster $(Process)"
            exe_env.append('GLIDEIN_ARGUMENTS="%s"' % glidein_arguments)
            # RSL is definitely not for cloud entries
            glidein_rsl = "none"
            if jobDescript.data.has_key('GlobusRSL'):
                glidein_rsl = jobDescript.data['GlobusRSL']
                # Replace placeholder for project id
                if 'TG_PROJECT_ID' in glidein_rsl:
                    glidein_rsl = glidein_rsl.replace('TG_PROJECT_ID', submit_credentials.identity_credentials['ProjectId'])

            if not (glidein_rsl == "none"):
                exe_env.append('GLIDEIN_RSL=%s' % glidein_rsl)
    
        return exe_env
    except Exception, e:
        msg = "   Error setting up submission environment: %s" % str(e)
        logSupport.log.debug(msg)

# Get list of CondorG job status for held jobs that are not recoverable
def isGlideinUnrecoverable(jobInfo):
    """
    This function looks at the glidein job's information and returns if the
    CondorG job is unrecoverable.

    This is useful to change to status of glidein (CondorG job) from hold to
    idle.

    @type jobInfo: dictionary
    @param jobInfo: Dictionary containing glidein job's classad information

    @rtype: bool
    @return: True if job is unrecoverable, False if recoverable
    """

    # CondorG held jobs have HeldReasonCode 2
    # CondorG held jobs with following HeldReasonSubCode are not recoverable
    # 0   : Job failed, no reason given by GRAM server
    # 4   : jobmanager unable to set default to the directory requested
    # 7   : authentication with the remote server failed
    # 8   : the user cancelled the job
    # 9   : the system cancelled the job
    # 10  : globus_xio_gsi: Token size exceeds limit
    # 17  : the job failed when the job manager attempted to run it
    # 22  : the job manager failed to create an internal script argument file
    # 31  : the job manager failed to cancel the job as requested
    # 47  : the gatekeeper failed to run the job manager
    # 48  : the provided RSL could not be properly parsed
    # 76  : cannot access cache files in ~/.globus/.gass_cache,
    #       check permissions, quota, and disk space
    # 79  : connecting to the job manager failed. Possible reasons: job
    #       terminated, invalid job contact, network problems, ...
    # 121 : the job state file doesn't exist
    # 122 : could not read the job state file

    unrecoverable = False
    # Dictionary of {HeldReasonCode: HeldReasonSubCode}
    unrecoverableCodes = {2: [ 0, 2, 4, 5, 7, 8, 9, 10, 14, 17,
                               22, 27, 28, 31, 37, 47, 48,
                               72, 76, 79, 81, 86, 87,
                               121, 122 ]}

    if jobInfo.has_key('HoldReasonCode') and jobInfo.has_key('HoldReasonSubCode'):
        code = jobInfo['HoldReasonCode']
        subCode = jobInfo['HoldReasonSubCode']
        if (unrecoverableCodes.has_key(code) and (subCode in unrecoverableCodes[code])):
            unrecoverable = True
    return unrecoverable

############################################################
# only allow simple strings
def is_str_safe(s):
    for c in s:
        if not c in ('._-@' + string.ascii_letters + string.digits):
            return False
    return True
