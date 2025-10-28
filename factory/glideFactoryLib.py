# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements the functions needed to keep the required number of idle glideins
and provides support for glidein sanitizing.
"""


import base64
import glob
import os
import pwd
import re
import string

# in codice commentato: import tempfile
import time

from itertools import groupby

import glideinwms.factory.glideFactorySelectionAlgorithms

from glideinwms.factory import glideFactoryConfig
from glideinwms.lib import (  # in codice commentato:, x509Support
    condorExe,
    condorManager,
    condorMonitor,
    logSupport,
    timeConversion,
)
from glideinwms.lib.defaults import BINARY_ENCODING

MY_USERNAME = pwd.getpwuid(os.getuid())[0]


############################################################
#
# Configuration
#
############################################################


class FactoryConfig:
    """Configuration class for the glidein Factory.

    This class stores default values and parameters needed for various
    operations such as querying, job submission, and log monitoring.
    """

    def __init__(self):
        """Initialize a FactoryConfig object with default values.

        Users should modify these attributes if needed.
        """
        # The name of the attribute that identifies the glidein
        self.factory_schedd_attribute = "GlideinFactory"
        self.glidein_schedd_attribute = "GlideinName"
        self.entry_schedd_attribute = "GlideinEntryName"
        self.client_schedd_attribute = "GlideinClient"
        self.frontend_name_attribute = "GlideinFrontendName"
        # self.x509id_schedd_attribute = "GlideinX509Identifier"
        self.credential_id_schedd_attribute = "GlideinCredentialIdentifier"
        # self.x509secclass_schedd_attribute = "GlideinX509SecurityClass"
        self.credential_secclass_schedd_attribute = "GlideinSecurityClass"

        self.factory_startd_attribute = "GLIDEIN_Factory"
        self.glidein_startd_attribute = "GLIDEIN_Name"
        self.entry_startd_attribute = "GLIDEIN_Entry_Name"
        self.client_startd_attribute = "GLIDEIN_Client"
        self.schedd_startd_attribute = "GLIDEIN_Schedd"
        self.clusterid_startd_attribute = "GLIDEIN_ClusterId"
        self.procid_startd_attribute = "GLIDEIN_ProcId"
        self.credential_id_startd_attribute = "GLIDEIN_CredentialIdentifier"

        self.count_env = "GLIDEIN_COUNT"

        # Stale value settings, in seconds
        self.stale_maxage = {
            1: 7 * 24 * 3600,  # 1 week for idle
            2: 31 * 24 * 3600,  # 1 month for running
            -1: 2 * 3600,
        }  # 2 hours for unclaimed (using special value -1 for this)

        # Sleep times between commands
        self.submit_sleep = 0.2
        self.remove_sleep = 0.2
        self.release_sleep = 0.2

        self.slots_layout = "partitionable"

        # Max commands per cycle
        self.max_submits = 100
        self.max_cluster_size = 10
        self.max_removes = 5
        self.max_releases = 20

        # release related limits
        self.max_release_count = 10
        self.min_release_time = 300

        # monitoring objects
        # create them for the logging to occur
        self.client_internals = None
        self.client_stats = None  # this one is indexed by client name
        self.qc_stats = None  # this one is indexed by security class
        self.log_stats = None
        self.rrd_stats = None

        self.supported_signtypes = ["sha1", "sha256"]

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
        """Configure Factory and glidein names.

        Args:
            factory_name (str): Name of the Factory.
            glidein_name (str): Name of the glidein.
        """
        self.factory_name = factory_name
        self.glidein_name = glidein_name

    def config_dirs(self, submit_dir, log_base_dir, client_log_base_dir, client_proxies_base_dir):
        """Configure directory paths.

        Args:
            submit_dir (str): Directory for submission.
            log_base_dir (str): Base directory for logs (Factory processes).
            client_log_base_dir (str): Base directory for client logs (HTCondor logs from glidein submission).
            client_proxies_base_dir (str): Base directory for client (glidein) credentials.
        """
        self.submit_dir = submit_dir
        self.log_base_dir = log_base_dir
        self.client_log_base_dir = client_log_base_dir
        self.client_proxies_base_dir = client_proxies_base_dir

    def config_submit_freq(self, sleep_between_submits, max_submits_x_cycle):
        """Configure submission frequency.

        Args:
            sleep_between_submits (float): Sleep time between submits.
            max_submits_x_cycle (int): Maximum number of submits per cycle.
        """
        self.submit_sleep = sleep_between_submits
        self.max_submits = max_submits_x_cycle

    def config_remove_freq(self, sleep_between_removes, max_removes_x_cycle):
        """Configure removal frequency.

        Args:
            sleep_between_removes (float): Sleep time between removals.
            max_removes_x_cycle (int): Maximum number of removals per cycle.
        """
        self.remove_sleep = sleep_between_removes
        self.max_removes = max_removes_x_cycle

    def get_client_log_dir(self, entry_name, username):
        """Get the client log directory.

        Args:
            entry_name (str): Name of the entry.
            username (str): Client username.

        Returns:
            str: Full path to the client log directory.
        """
        log_dir = os.path.join(
            self.client_log_base_dir, f"user_{username}", f"glidein_{self.glidein_name}", f"entry_{entry_name}"
        )
        return log_dir

    def get_client_proxies_dir(self, username):
        """Get the client credentials directory.

        Args:
            username (str): Client username.

        Returns:
            str: Full path to the client credentials directory.
        """
        proxy_dir = os.path.join(self.client_proxies_base_dir, f"user_{username}", f"glidein_{self.glidein_name}")
        return proxy_dir


# global configuration of the module
factoryConfig = FactoryConfig()


############################################################
def secClass2Name(client_security_name, proxy_security_class):
    """Get the name by concatenating with underscore client security name and credential security class.

    Args:
        client_security_name (str): The client's security name.
        proxy_security_class (str): The credential's security class.

    Returns:
        str: A string in the format "client_security_name_proxy_security_class".
    """
    return f"{client_security_name}_{proxy_security_class}"


############################################################


############################################################
#
# User functions
#
############################################################


def getCondorQData(entry_name, client_name, schedd_name, factoryConfig=None):
    """Get Condor queue data for a specific entry and client.

    Args:
        entry_name (str): The name of the entry.
        client_name (str): The client (Frontend) name. If None, returns data for all clients.
        schedd_name (str): HTCondor schedd name.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        condorMonitor.CondorQ: Condor queue object with loaded data.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    if client_name is None:
        client_constraint = ""
    else:
        client_constraint = f' && ({factoryConfig.client_schedd_attribute} =?= "{client_name}")'

    q_glidein_constraint = '({} =?= "{}") && ({} =?= "{}") && ({} =?= "{}"){} && ({} =!= UNDEFINED)'.format(
        factoryConfig.factory_schedd_attribute,
        factoryConfig.factory_name,
        factoryConfig.glidein_schedd_attribute,
        factoryConfig.glidein_name,
        factoryConfig.entry_schedd_attribute,
        entry_name,
        client_constraint,
        factoryConfig.credential_id_schedd_attribute,
    )
    q_glidein_format_list = [
        ("JobStatus", "i"),
        ("GridJobStatus", "s"),
        ("ServerTime", "i"),
        ("EnteredCurrentStatus", "i"),
        ("GlideinEntrySubmitFile", "s"),
        (factoryConfig.credential_id_schedd_attribute, "s"),
        ("HoldReasonCode", "i"),
        ("HoldReasonSubCode", "i"),
        ("HoldReason", "s"),
        ("NumSystemHolds", "i"),
        (factoryConfig.frontend_name_attribute, "s"),
        (factoryConfig.client_schedd_attribute, "s"),
        (factoryConfig.credential_secclass_schedd_attribute, "s"),
    ]

    q = condorMonitor.CondorQ(schedd_name)
    q.factory_name = factoryConfig.factory_name
    q.glidein_name = factoryConfig.glidein_name
    q.entry_name = entry_name
    q.client_name = client_name
    q.load(q_glidein_constraint, q_glidein_format_list)
    return q


def getCondorQCredentialList(factoryConfig=None):
    """Return a list of currently used credentials (proxies, ...) based on the glideins in the queue.

    Args:
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        list: List of credential file paths.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    q_glidein_constraint = '({} =?= "{}") && ({} =?= "{}") '.format(
        factoryConfig.factory_schedd_attribute,
        factoryConfig.factory_name,
        factoryConfig.glidein_schedd_attribute,
        factoryConfig.glidein_name,
    )

    cred_list = []

    try:
        q_cred_list = condorMonitor.condorq_attrs(
            q_glidein_constraint, ["x509userproxy", "EC2AccessKeyId", "EC2SecretAccessKey"]
        )
    except Exception:
        msg = "Unable to query condor for credential list.  The queue may just be empty (Condor bug)."
        logSupport.log.warning(msg)
        logSupport.log.exception(msg)
        q_cred_list = []  # no results found

    for cred_dict in q_cred_list:
        for key in cred_dict:
            cred_fpath = cred_dict[key]
            if cred_fpath not in cred_list:
                cred_list.append(cred_fpath)

    return cred_list


def getQCredentials(condorq, client_name, creds, client_sa, cred_secclass_sa, cred_id_sa):
    """Get a sub-query for jobs matching the specified client and credential.

    Args:
        condorq: condor_q query to select within.
        client_name (str): Client name (e.g. the Frontend requesting the jobs).
        creds: Credential object (to extract security class and ID).
        client_sa: Schedd attribute to compare the client name.
        cred_secclass_sa: Schedd attribute to compare the security class.
        cred_id_sa: Schedd attribute to compare the credential ID.

    Returns:
        condorMonitor.SubQuery: Sub-query object with jobs matching the criteria.
    """
    entry_condorQ = condorMonitor.SubQuery(
        condorq,
        lambda d: (
            (d.get(client_sa) == client_name)
            and (d.get(cred_secclass_sa) == creds.security_class)
            and (d.get(cred_id_sa) == creds.id)
        ),
    )
    entry_condorQ.schedd_name = condorq.schedd_name
    entry_condorQ.factory_name = condorq.factory_name
    entry_condorQ.glidein_name = condorq.glidein_name
    entry_condorQ.entry_name = condorq.entry_name
    entry_condorQ.client_name = condorq.client_name
    entry_condorQ.load()
    return entry_condorQ


# TODO: this was for v2 protocol - check if it is still used or to remove
def getQProxSecClass(
    condorq,
    client_name,
    proxy_security_class,
    client_schedd_attribute=None,
    credential_secclass_schedd_attribute=None,
    factoryConfig=None,
):
    """Get the current queue status for a client and a security class.

    Args:
        condorq (condorMonitor.CondorQ): Condor queue object.
        client_name (str): Client name.
        proxy_security_class (str): Credentials security class.
        client_schedd_attribute (str, optional): Schedd attribute for client name. Defaults to global config.
        credential_secclass_schedd_attribute (str, optional): Schedd attribute for security class. Defaults to global config.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        condorMonitor.SubQuery: Sub-query with jobs matching the specified client and security class.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    if client_schedd_attribute is None:
        csa_str = factoryConfig.client_schedd_attribute
    else:
        csa_str = client_schedd_attribute

    if credential_secclass_schedd_attribute is None:
        xsa_str = factoryConfig.credential_secclass_schedd_attribute
    else:
        xsa_str = credential_secclass_schedd_attribute

    # For v2 protocol
    entry_condorQ = condorMonitor.SubQuery(
        condorq,
        lambda d: (
            csa_str in d and (d[csa_str] == client_name) and xsa_str in d and (d[xsa_str] == proxy_security_class)
        ),
    )
    entry_condorQ.schedd_name = condorq.schedd_name
    entry_condorQ.factory_name = condorq.factory_name
    entry_condorQ.glidein_name = condorq.glidein_name
    entry_condorQ.entry_name = condorq.entry_name
    entry_condorQ.client_name = condorq.client_name
    entry_condorQ.load()
    return entry_condorQ


def getQClientNames(condorq, factoryConfig=None):
    """Return a dictionary grouping the condorQ by client names.

    Args:
        condorq (condorMonitor.CondorQ): Condor queue query object.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        dict: Dictionary grouping jobs by the client name (based on factoryConfig.client_schedd_attribute).
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]
    schedd_attribute = factoryConfig.client_schedd_attribute

    def group_key_func(val):
        try:
            return val[schedd_attribute]
        except KeyError:
            return None

    client_condorQ = condorMonitor.NestedGroup(condorq, group_key_func)
    client_condorQ.schedd_name = condorq.schedd_name
    client_condorQ.factory_name = condorq.factory_name
    client_condorQ.glidein_name = condorq.glidein_name
    client_condorQ.entry_name = condorq.entry_name
    client_condorQ.client_name = condorq.client_name  # Should be None
    client_condorQ.load()
    return client_condorQ


def getQStatusSF(condorq):
    """Return a dictionary mapping each submit file to a dictionary of job status counts.

    This is an approximate summary of job statuses (e.g. Idle jobs are not split by GridJobStatus).
    Use `getQStatus` for more detailed statuses.

    Args:
        condorq (condorMonitor.CondorQ): Condor queue query object.

    Returns:
        dict: Dictionary where keys are GlideinEntrySubmitFile(s) and values are dictionaries of jobStatus to number of jobs.
    """
    qc_status = {}
    submit_files = {v.get("GlideinEntrySubmitFile") for k, v in list(condorq.stored_data.items())} - {None}
    for sf in submit_files:
        sf_status = sorted(
            v["JobStatus"] for k, v in list(condorq.stored_data.items()) if v.get("GlideinEntrySubmitFile") == sf
        )
        qc_status[sf] = {key: len(list(group)) for key, group in groupby(sf_status)}
    return qc_status


def getQStatus(condorq):
    """Return a dictionary counting jobs in the Condor queue for each detailed job status.

    Uses `hash_status` to get the detailed job status.
    Idle jobs may be: 1001, 1002, 1010 depending on the GridJobStatus.
    Running maybe: 2 or 4010 if in stage-out.
    1100 is used for unknown GridJobStatus.

    Args:
        condorq (condorMonitor.CondorQ): Condor queue query object.

    Returns:
        dict: Dictionary mapping detailed job statuses (as returned by hash_status) to counts.
    """
    qc_status = condorMonitor.Summarize(condorq, hash_status).countStored(flat_hash=True)
    return qc_status


def getQStatusStale(condorq):
    """Return a dictionary of job statuses with a stale information flag.

    stale_info is 1 if the status information is old.

    Args:
        condorq (condorMonitor.CondorQ): Condor queue query object.

    Returns:
        dict: Dictionary mapping job statuses to counts, where each status includes a flag indicating if the status is stale.
    """
    qc_status = condorMonitor.Summarize(condorq, hash_statusStale).countStored(flat_hash=True)
    return qc_status


###########################
# This function is not used
###########################


def getCondorStatusData(
    entry_name,
    client_name,
    pool_name=None,
    factory_startd_attribute=None,
    glidein_startd_attribute=None,
    entry_startd_attribute=None,
    client_startd_attribute=None,
    factoryConfig=None,
):
    """Get Condor status data for a specific entry and client from the startd.

    Args:
        entry_name (str): Name of the entry.
        client_name (str): Client name.
        pool_name (str, optional): Pool name. Defaults to None.
        factory_startd_attribute (str, optional): Factory startd attribute. Defaults to None.
        glidein_startd_attribute (str, optional): Glidein startd attribute. Defaults to None.
        entry_startd_attribute (str, optional): Entry startd attribute. Defaults to None.
        client_startd_attribute (str, optional): Client startd attribute. Defaults to None.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        condorMonitor.CondorStatus: Condor status object loaded with data.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    if factory_startd_attribute is None:
        fsa_str = factoryConfig.factory_startd_attribute
    else:
        fsa_str = factory_startd_attribute

    if glidein_startd_attribute is None:
        gsa_str = factoryConfig.glidein_startd_attribute
    else:
        gsa_str = glidein_startd_attribute

    if entry_startd_attribute is None:
        esa_str = factoryConfig.entry_startd_attribute
    else:
        esa_str = entry_startd_attribute

    if client_startd_attribute is None:
        csa_str = factoryConfig.client_startd_attribute
    else:
        csa_str = client_startd_attribute

    status_glidein_constraint = '({} =?= "{}") && ({} =?= "{}") && ({} =?= "{}") && ({} =?= "{}")'.format(
        fsa_str,
        factoryConfig.factory_name,
        gsa_str,
        factoryConfig.glidein_name,
        esa_str,
        entry_name,
        csa_str,
        client_name,
    )

    status = condorMonitor.CondorStatus(pool_name=pool_name)
    status.factory_name = factoryConfig.factory_name
    status.glidein_name = factoryConfig.glidein_name
    status.entry_name = entry_name
    status.client_name = client_name
    status.load(status_glidein_constraint)

    return status


def update_x509_proxy_file(entry_name, username, client_id, proxy_data, factoryConfig=None):
    """Create or update the x509 proxy file.

    The file is updated safely (with a backup) if the new proxy data differs from the current data.
    The file path is constructed as directory and name:
      ``f"{factoryConfig.client_proxies_base_dir}/user_{username}/glidein_{factoryConfig.glidein_name}/entry_{entry_name}"``
      ``"x509_%s.proxy" % escapeParam(client_id)"``

    Proxy DN and VOMS extension are extracted but never used (?!)

    Args:
        entry_name (str): Entry name.
        username (str): Username (identity of the Frontend).
        client_id (str): Client ID.
        proxy_data (bytes): Proxy data in PEM format.
        factoryConfig (FactoryConfig, optional): Factory configuration.

    Returns:
        str: Full path to the updated proxy file.
    """
    # TODO: revise the safe write function. New file case is not atomic. There can be better option.
    #  Should be a common functionality provided in lib
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    # # TODO: This whole section seems to do nothing and should be removed (MM):
    # #  gets the DN, gets the voms exception and does nothing w/ those variables.
    # #  It is also silently protected for any failure, so not even the verification is important
    # #  Since dn and voms are extracted, should they be used in a log message or the file name?
    # dn = ""
    # voms = ""
    # tempfilename = ""
    # try:
    #     (f, tempfilename) = tempfile.mkstemp()
    #     os.write(f, proxy_data)
    #     os.close(f)
    # except:
    #     logSupport.log.error(f"Unable to create tempfile '{tempfilename}'!")
    #
    # try:
    #     dn = x509Support.extract_DN(tempfilename)  # not really used
    #
    #     voms_proxy_info = which("voms-proxy-info")
    #     if voms_proxy_info is not None:
    #         voms_list = condorExe.iexe_cmd(f"{voms_proxy_info} -fqan -file {tempfilename}")
    #         # sort output in case order of voms fqan changed
    #         voms = "\n".join(sorted(voms_list))
    # except:
    #     # If voms-proxy-info doesn't exist or errors out, just hash on dn
    #     voms = ""
    #
    # try:
    #     os.unlink(tempfilename)
    # except:
    #     logSupport.log.error("Unable to delete tempfile %s!" % tempfilename)
    # # TODO: end of the section to remove

    # proxy_dir = factoryConfig.get_client_proxies_dir(username)
    # Have to hack this since the above code was modified to support v3plus going forward
    proxy_dir = os.path.join(
        factoryConfig.client_proxies_base_dir,
        f"user_{username}",
        f"glidein_{factoryConfig.glidein_name}",
        f"entry_{entry_name}",
    )
    fname_short = "x509_%s.proxy" % escapeParam(client_id)
    fname = os.path.join(proxy_dir, fname_short)

    # We have no longer privilege separation so we do it natively
    if not os.path.isfile(fname):
        # new file, create
        fd = os.open(fname, os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(fd, proxy_data)  # proxy_data is a bytestring
        finally:
            os.close(fd)
        return fname

    # old file exists, check if same content
    with open(fname) as fl:
        old_data = fl.read()

    if proxy_data == old_data:
        # nothing changed, done
        return fname

    #
    # proxy changed, need to update
    #

    # remove any previous backup file
    try:
        os.remove(fname + ".old")
    except Exception:
        pass  # just protect

    # create new file
    fd = os.open(fname + ".new", os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, proxy_data)  # proxy_data is a bytestring
    finally:
        os.close(fd)

    # move the old file to a tmp and the new one into the official name
    try:
        os.rename(fname, fname + ".old")
    except OSError:
        pass  # just protect
    os.rename(fname + ".new", fname)
    return fname


#
# Main function
#   Will keep the required number of Idle glideins
#
class ClientWeb:
    """Represents client web configuration for glidein submission.

    This class holds the client web URL, signature type, description, and group information.
    It also provides a method to generate glidein command-line arguments (for the glidein_startup.sh script).
    """

    def __init__(
        self,
        client_web_url,
        client_signtype,
        client_descript,
        client_sign,
        client_group,
        client_group_web_url,
        client_group_descript,
        client_group_sign,
        factoryConfig=None,
    ):
        """Initialize a ClientWeb instance.

        Args:
            client_web_url (str): URL for client web.
            client_signtype (str): Client signature type.
            client_descript (str): Client description.
            client_sign (str): Client signature.
            client_group (str): Client group name.
            client_group_web_url (str): Client group web URL.
            client_group_descript (str): Client group description.
            client_group_sign (str): Client group signature.
            factoryConfig (FactoryConfig, optional): Factory configuration.
        """
        if factoryConfig is None:
            factoryConfig = globals()["factoryConfig"]

        if client_signtype not in factoryConfig.supported_signtypes:
            raise ValueError("Signtype '%s' not supported!" % client_signtype)

        self.url = client_web_url
        self.signtype = client_signtype
        self.descript = client_descript
        self.sign = client_sign

        self.group_name = client_group
        self.group_url = client_group_web_url
        self.group_descript = client_group_descript
        self.group_sign = client_group_sign

    def get_glidein_args(self):
        """Return a list of command-line arguments for glidein submission based on client web settings.

        Returns:
            list: List of command-line arguments.
        """
        return [
            "-clientweb",
            self.url,
            "-clientsign",
            self.sign,
            "-clientsigntype",
            self.signtype,
            "-clientdescript",
            self.descript,
            "-clientgroup",
            self.group_name,
            "-clientwebgroup",
            self.group_url,
            "-clientsigngroup",
            self.group_sign,
            "-clientdescriptgroup",
            self.group_descript,
        ]


def keepIdleGlideins(
    client_condorq,
    client_int_name,
    req_min_idle,
    req_max_glideins,
    idle_lifetime,
    remove_excess,
    submit_credentials,
    glidein_totals,
    frontend_name,
    client_web,
    params,
    log=logSupport.log,
    factoryConfig=None,
):
    """Determine how many new glideins to submit based on the queue status and client (Frontend) request.

    If the system has reached a limit (request, entry, frontend:security_class), and the client requests
    removal of excess glideins (RemoveExcess), this function will attempt to remove them.

    Args:
        client_condorq (CondorQ): Condor queue filtered by security class.
        client_int_name (str): Internal representation of the client name.
        req_min_idle (int): Minimum number of idle glideins requested by the Frontend.
        req_max_glideins (int): Maximum number of running glideins allowed by the Frontend.
        idle_lifetime (int): Time to wait before removing idle glideins.
        remove_excess (tuple): Tuple (remove_excess_str, remove_excess_margin) from the frontend request.
            remove_excess_str is a string with values NO, WAIT, IDLE, ALL.
            remove_excess_margin is an integer.
        submit_credentials (SubmitCredentials): Credentials needed to submit glideins.
        glidein_totals (GlideinTotals): Totals for the entry and Frontends.
        frontend_name (str): Frontend name ("frontend:sec_class" - used as key in glidein_totals).
        client_web (ClientWeb): Client web configuration.
        params (dict): Parameters from the entry or frontend configuration.
        log: Logger.
        factoryConfig: Factory configuration.

    Raises:
        condorExe.ExeError: In case of issues executing condor commands.

    Returns:
        int: Number of newly submitted glideins (or 0 if none submitted).
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    # Filter out everything but the proper credential identifier.
    # Need to determine how many more glideins are needed to match this
    # request min_idle and max_glidiens

    condorq = condorMonitor.SubQuery(
        client_condorq, lambda d: (d[factoryConfig.credential_id_schedd_attribute] == submit_credentials.id)
    )
    condorq.schedd_name = client_condorq.schedd_name
    condorq.factory_name = client_condorq.factory_name
    condorq.glidein_name = client_condorq.glidein_name
    condorq.entry_name = client_condorq.entry_name
    condorq.client_name = client_condorq.client_name
    condorq.credentials_id = submit_credentials.id
    condorq.load()

    # Check that have not exceeded max held for this security class
    if glidein_totals.has_sec_class_exceeded_max_held(frontend_name):
        # Too many held, don't submit
        log.info(
            "Too many held glideins for this frontend-security class: %i=held %i=max_held"
            % (
                glidein_totals.frontend_limits[frontend_name]["held"],
                glidein_totals.frontend_limits[frontend_name]["max_held"],
            )
        )
        # run sanitize... we have to get out of this mess
        return sanitizeGlideins(client_condorq, log=log, factoryConfig=factoryConfig)
        # we have done something... return non-0 so sanitize is not called again

    # Count glideins for this request credential by status
    qc_status = getQStatus(condorq)
    # Count by status and group by submit file glideins for this request credential
    qc_status_sf = getQStatusSF(condorq)

    # Held Glidein seem not to be used later
    # # Held==JobStatus(5)
    # q_held_glideins = 0
    # if 5 in qc_status:
    #     q_held_glideins = qc_status[5]
    # Idle==Jobstatus(1)
    sum_idle_count(qc_status)
    q_idle_glideins = qc_status[1]
    # Running==Jobstatus(2)
    q_running_glideins = 0
    if 2 in qc_status:
        q_running_glideins = qc_status[2]

    # Determine how many more idle glideins we need in requested idle (we may already have some)
    add_glideins = req_min_idle - q_idle_glideins

    if add_glideins <= 0:
        # Have enough idle, don't submit
        log.info("Have enough glideins: idle=%i req_idle=%i, not submitting" % (q_idle_glideins, req_min_idle))
        return clean_glidein_queue(
            remove_excess,
            glidein_totals,
            condorq,
            req_min_idle,
            req_max_glideins,
            frontend_name,
            log=log,
            factoryConfig=factoryConfig,
        )
    else:
        # Need more idle
        # Check that adding more idle doesn't exceed request max_glideins
        if q_idle_glideins + q_running_glideins + add_glideins >= req_max_glideins:
            # Exceeded limit, try to adjust

            add_glideins = req_max_glideins - q_idle_glideins - q_running_glideins

            # Have hit request limit, cannot submit
            if add_glideins < 0:
                log.info(
                    "Additional idle glideins %s needed exceeds request max_glideins limits %s, not submitting"
                    % (add_glideins, req_max_glideins)
                )
                return clean_glidein_queue(
                    remove_excess,
                    glidein_totals,
                    condorq,
                    req_min_idle,
                    req_max_glideins,
                    frontend_name,
                    log=log,
                    factoryConfig=factoryConfig,
                )
            elif add_glideins == 0:
                log.info(
                    "Additional idle glideins not needed, have met request max_glideins limits %s, not submitting"
                    % req_max_glideins
                )
                return clean_glidein_queue(
                    remove_excess,
                    glidein_totals,
                    condorq,
                    req_min_idle,
                    req_max_glideins,
                    frontend_name,
                    log=log,
                    factoryConfig=factoryConfig,
                )

    # Have a valid idle number to request
    # Check that adding more doesn't exceed frontend:sec_class and entry limits
    add_glideins = glidein_totals.can_add_idle_glideins(
        add_glideins, frontend_name, log=log, factoryConfig=factoryConfig
    )

    if add_glideins <= 0:
        # Have hit entry or frontend:sec_class limit, cannot submit
        log.info(
            "Additional %s idle glideins requested by %s exceeds frontend:security class limit for the entry, not submitting"
            % (req_min_idle, frontend_name)
        )
        return clean_glidein_queue(
            remove_excess,
            glidein_totals,
            condorq,
            req_min_idle,
            req_max_glideins,
            frontend_name,
            log=log,
            factoryConfig=factoryConfig,
        )
    else:
        # If we are requesting more than the maximum glideins that we can submit at one time, then set to the max submit number
        #   this helps to keep one frontend/request from getting all the glideins
        if add_glideins > factoryConfig.max_submits:
            add_glideins = factoryConfig.max_submits
            log.debug(
                "Additional idle glideins exceeded entry max submit limits %s, adjusted add_glideins to entry max submit rate"
                % factoryConfig.max_submits
            )

    try:
        log.debug("Submitting %i glideins" % add_glideins)
        submitGlideins(
            condorq.entry_name,
            client_int_name,
            add_glideins,
            idle_lifetime,
            frontend_name,
            submit_credentials,
            client_web,
            params,
            qc_status_sf,
            log=log,
            factoryConfig=factoryConfig,
        )
        glidein_totals.add_idle_glideins(add_glideins, frontend_name)
        return add_glideins  # exit, some submitted
    except RuntimeError as e:
        log.warning("%s" % e)
        return 0  # something is wrong... assume 0 and exit
    except Exception:
        log.warning("Unexpected error submitting glideins")
        log.exception("Unexpected error submitting glideins")
        return 0  # something is wrong... assume 0 and exit

    return 0


def clean_glidein_queue(
    remove_excess_tp,
    glidein_totals,
    condorQ,
    req_min_idle,
    req_max_glideins,
    frontend_name,
    log=logSupport.log,
    factoryConfig=None,
):
    """Clean up the glidein queue by removing excess glideins per the client (Frontend) request.

    This is not adjusting the glidein totals with what has been removed from the queue.  It may take a cycle (or more)
    for these totals to update so it would be difficult to reflect the true state of the system.

    TODO: req_min_idle=0 when remove_excess_tp.frontend_req_min_idle does not mean that a limit was reached in the Factory
        or some component (Factory/Entry) is in downtime. Check if the removal behavior should change

    Args:
        remove_excess_tp (tuple): Tuple containing remove_excess_str (one of NO, WAIT, IDLE, ALL), remove_excess_margin,
            and frontend_req_min_idle.
            remove_excess_str and remove_excess_margin are the removal request form the Frontend.
            The frontend_req_min_idle item of the tuple indicates the original Frontend pressure. We use this
            instead of req_min_idle for the IDLE pilot removal because the Factory could set req_min_idle to 0
            if an entry is in downtime, or the Factory limits are reached. We do not want to remove idle pilots in
            these cases!
        glidein_totals (GlideinTotals): Totals of glideins for the entry and Frontends.
        condorQ (condorMonitor.CondorQ): Condor queue object.
        req_min_idle (int): Minimum idle glideins requested by the frontend.
            (NOT USED, using frontend_req_min_idle in remove_excess_tp instead to avoid Factory limits effects)
        req_max_glideins (int): Maximum glideins allowed by the frontend.
        frontend_name (str): Frontend name. Used as key for glidein_totals.
        log: Logger.
        factoryConfig (FactoryConfig, optional): Factory configuration.

    Returns:
        int: 1 if some glideins were removed, 0 otherwise.
    """
    # TODO: could return the number of glideins removed

    remove_excess_str, remove_excess_margin, frontend_req_min_idle = remove_excess_tp

    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    # KEL passed the whole glidein totals obj in case we want to adjust
    # entry/fe:sec_class totals?
    sec_class_idle = glidein_totals.frontend_limits[frontend_name]["idle"]
    sec_class_held = glidein_totals.frontend_limits[frontend_name]["held"]
    sec_class_running = glidein_totals.frontend_limits[frontend_name]["running"]

    remove_excess_wait = False
    remove_excess_idle = False
    remove_excess_running = False
    if remove_excess_str == "WAIT":
        remove_excess_wait = True
    elif remove_excess_str == "IDLE":
        remove_excess_wait = True
        remove_excess_idle = True
    elif remove_excess_str == "ALL":
        remove_excess_wait = True
        remove_excess_idle = True
        remove_excess_running = True
    else:
        if remove_excess_str != "NO":
            log.info("Unknown RemoveExcess provided in the request '%s', assuming 'NO'" % remove_excess_str)

    if (
        (remove_excess_wait or remove_excess_idle) and (sec_class_idle > frontend_req_min_idle + remove_excess_margin)
    ) or ((remove_excess_running) and (sec_class_running + sec_class_idle > req_max_glideins + remove_excess_margin)):
        # too many Glideins, remove
        remove_nr = sec_class_idle - frontend_req_min_idle - remove_excess_margin
        if (
            remove_excess_running
            and sec_class_running + sec_class_idle > req_max_glideins + remove_excess_margin
            and sec_class_running + frontend_req_min_idle > req_max_glideins
        ):
            # sec_class_running + sec_class_idle - req_max_glideins - remove_excess_margin > remove_nr
            # too many running and running excess is bigger
            # if we are past max_run, then min_idle does not make sense to start with
            remove_nr = sec_class_running + sec_class_idle - req_max_glideins - remove_excess_margin

        idle_list = extractIdleUnsubmitted(condorQ)

        if remove_excess_wait and (len(idle_list) > 0):
            # remove unsubmitted first, if any
            if len(idle_list) > remove_nr:
                idle_list = idle_list[:remove_nr]  # shorten

            stat_str = "frontend_min_idle=%i, margin=%i, idle=%i, unsubmitted=%i" % (
                frontend_req_min_idle,
                remove_excess_margin,
                sec_class_idle,
                len(idle_list),
            )
            log.info("Too many glideins: %s" % stat_str)
            log.info("Removing %i unsubmitted idle glideins" % len(idle_list))
            if len(idle_list) > 0:
                removeGlideins(condorQ.schedd_name, idle_list, log=log, factoryConfig=factoryConfig)
                # Stop ... others will be retried in next round, if needed
                return 1

        idle_list = extractIdleQueued(condorQ)  # IdleQueued (+ IdleUnsubmitted makes all Idle)
        if remove_excess_idle and (len(idle_list) > 0):
            # no unsubmitted, go for all the others idle now
            if len(idle_list) > remove_nr:
                idle_list = idle_list[:remove_nr]  # shorten
            stat_str = "frontend_min_idle=%i, margin=%i, idle=%i, unsubmitted=%i" % (
                frontend_req_min_idle,
                remove_excess_margin,
                sec_class_idle,
                0,
            )
            log.info("Too many glideins: %s" % stat_str)
            log.info("Removing %i idle glideins" % len(idle_list))
            if len(idle_list) > 0:
                removeGlideins(condorQ.schedd_name, idle_list, log=log, factoryConfig=factoryConfig)
                return 1  # exit, even if no submitted

        if remove_excess_running:
            # no idle left, remove anything you can
            stat_str = "idle=%i, running=%i, margin=%i, max_running=%i" % (
                sec_class_idle,
                sec_class_running,
                remove_excess_margin,
                req_max_glideins,
            )
            log.info("Too many glideins: %s" % stat_str)

            run_list = extractRunSimple(condorQ)
            if len(run_list) > remove_nr:
                run_list = run_list[:remove_nr]  # shorten
            log.info("Removing %i running glideins" % len(run_list))

            rm_list = run_list

            # Remove Held as well. No reason to keep them alive
            # if we are about to kill running glideins anyhow

            # Check if there are held glideins that are not recoverable
            unrecoverable_held_list = extractUnrecoverableHeldSimple(condorQ, factoryConfig=factoryConfig)
            if len(unrecoverable_held_list) > 0:
                log.info("Removing %i unrecoverable held glideins" % len(unrecoverable_held_list))
                rm_list += unrecoverable_held_list

            # Check if there are held glideins
            held_list = extractRecoverableHeldSimple(condorQ)
            if len(held_list) > 0:
                log.info("Removing %i held glideins" % len(held_list))
                rm_list += held_list

            if len(rm_list) > 0:
                removeGlideins(condorQ.schedd_name, rm_list, log=log, factoryConfig=factoryConfig)
                return 1  # exit, even if no submitted
    elif (remove_excess_running) and (req_max_glideins == 0) and (sec_class_held > 0):
        # no glideins desired, remove all held
        # (only held should be left at this point... idle and running addressed above)

        # Check if there are held glideins that are not recoverable
        unrecoverable_held_list = extractUnrecoverableHeldSimple(condorQ, factoryConfig=factoryConfig)
        if len(unrecoverable_held_list) > 0:
            log.info("Removing %i unrecoverable held glideins" % len(unrecoverable_held_list))

        # Check if there are held glideins
        held_list = extractRecoverableHeldSimple(condorQ, factoryConfig=factoryConfig)
        if len(held_list) > 0:
            log.info("Removing %i held glideins" % len(held_list))

        if (len(unrecoverable_held_list) + len(held_list)) > 0:
            removeGlideins(
                condorQ.schedd_name, unrecoverable_held_list + held_list, log=log, factoryConfig=factoryConfig
            )
            return 1  # exit, even if no submitted

    return 0


def sanitizeGlideins(condorq, log=logSupport.log, factoryConfig=None):
    """Sanitize glideins in the queue by removing stale or held jobs.

    Checks for stale idle and running glideins, unrecoverable held glideins (with forcex)
    and held glideins within limits, and removes them accordingly.

    Args:
        condorq (condorMonitor.CondorQ): Condor queue object.
        log (logging.Logger): Logger.
        factoryConfig (FactoryConfig, optional): Factory configuration.

    Returns:
        int: 1 if any glideins were sanitized (removed), 0 otherwise.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    glideins_sanitized = 0
    # Check if some glideins have been in idle state for too long
    stale_list = extractStaleSimple(condorq)
    if len(stale_list) > 0:
        glideins_sanitized = 1
        log.warning("Found %i stale glideins" % len(stale_list))
        removeGlideins(condorq.schedd_name, stale_list, log=log, factoryConfig=factoryConfig)

    # Check if some glideins have been in running state for too long
    runstale_list = extractRunStale(condorq)
    if len(runstale_list) > 0:
        glideins_sanitized = 1
        log.warning(
            "Found %i stale (>%ih) running glideins" % (len(runstale_list), factoryConfig.stale_maxage[2] // 3600)
        )
        removeGlideins(condorq.schedd_name, runstale_list, log=log, factoryConfig=factoryConfig)

    # Check if there are held glideins that are not recoverable AND held for more than 20 iterations
    unrecoverable_held_forcex_list = extractUnrecoverableHeldForceX(condorq)
    if len(unrecoverable_held_forcex_list) > 0:
        glideins_sanitized = 1
        log.warning(
            "Found %i unrecoverable held glideins that have been held for over 20 iterations"
            % len(unrecoverable_held_forcex_list)
        )
        removeGlideins(
            condorq.schedd_name, unrecoverable_held_forcex_list, force=True, log=log, factoryConfig=factoryConfig
        )

    # Check if there are held glideins that are not recoverable
    unrecoverable_held_list = extractUnrecoverableHeldSimple(condorq)
    if len(unrecoverable_held_list) > 0:
        glideins_sanitized = 1
        log.warning("Found %i unrecoverable held glideins" % len(unrecoverable_held_list))
        unrecoverable_held_list_minus_forcex = list(set(unrecoverable_held_list) - set(unrecoverable_held_forcex_list))
        log.warning(
            "But removing only %i (unrecoverable held - unrecoverable held forcex)"
            % len(unrecoverable_held_list_minus_forcex)
        )
        removeGlideins(
            condorq.schedd_name, unrecoverable_held_list_minus_forcex, force=False, log=log, factoryConfig=factoryConfig
        )

    # Check if there are held glideins
    held_list = extractRecoverableHeldSimple(condorq, factoryConfig=factoryConfig)
    if len(held_list) > 0:
        glideins_sanitized = 1
        limited_held_list = extractRecoverableHeldSimpleWithinLimits(condorq, factoryConfig=factoryConfig)
        log.warning("Found %i held glideins, %i within limits" % (len(held_list), len(limited_held_list)))
        if len(limited_held_list) > 0:
            releaseGlideins(condorq.schedd_name, limited_held_list, log=log, factoryConfig=factoryConfig)

    return glideins_sanitized


def logStatsAll(condorq, log=logSupport.log, factoryConfig=None):
    """Add schedd statistics from all clients in the queue to the stored statistics.

    Sum to the current schedd statistics of this entry (from condor_q on the Factory)
    to the values already stored in factoryConfig.client_stats, factoryConfig.qc_stats
    Do that for all the clients that have jobs on this entry

    Args:
        condorq (condorMonitor.CondorQ): Condor queue object containing jobs for the entry (`data` attribute).
        log (logging.Logger): Logger.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to the global one.
            It contains schedd statistics (client_stats, qc_stats).
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    # group_by client_name the condorQ data
    clients_condorq = getQClientNames(condorq, factoryConfig)
    data = clients_condorq.fetchStored()

    for client_name, client_data in list(data.items()):
        # Count glideins by status
        # getQStatus() equivalent
        data_list = sorted(hash_status(v) for v in list(client_data.values()))
        qc_status = {key: len(list(group)) for key, group in groupby([i for i in data_list if i is not None])}
        # getQStatusSF() equivalent
        qc_status_sf = {}
        submit_files = {v.get("GlideinEntrySubmitFile") for k, v in list(client_data.items())} - {None}
        for sf in submit_files:
            sf_status = sorted(
                v["JobStatus"] for k, v in list(client_data.items()) if v.get("GlideinEntrySubmitFile") == sf
            )
            qc_status_sf[sf] = {key: len(list(group)) for key, group in groupby(sf_status)}

        sum_idle_count(qc_status)

        log.info(f"Inactive client {client_name} schedd status {qc_status}")
        # client_stats are the one actually used in classads and monitoring, ignoring factoryConfig.qc_stats
        factoryConfig.client_stats.logSchedd(client_name, qc_status, qc_status_sf)
        # factoryConfig.qc_stats.logSchedd(client_log_name, qc_status, qc_status_sf)

    return


def logStats(
    condorq, client_int_name, client_security_name, proxy_security_class, log=logSupport.log, factoryConfig=None
):
    """Add schedd statistics for a client and update stored statistics.

    Sum to the current schedd statistics of this entry (from condor_q on the Factory)
    to the values already stored in factoryConfig.client_stats, factoryConfig.qc_stats

    Args:
        condorq (condorMonitor.CondorQ): Condor queue object.
        client_int_name (str): Client internal name (the requester/Frontend).
        client_security_name (str): Client security name.
        proxy_security_class (str): Credential security class of the client.
        log (logging.Logger): Logger.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to the global one.
            It includes schedd statistics (client_stats, qc_stats).
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    # Count glideins by status
    qc_status = getQStatus(condorq)
    qc_status_sf = getQStatusSF(condorq)

    sum_idle_count(qc_status)

    log.info(
        "Client %s (secid: %s_%s) schedd status %s"
        % (client_int_name, client_security_name, proxy_security_class, qc_status)
    )

    # logStats is called always after logWorkRequest and other updates of qc_status, removing the check:
    # if factoryConfig.qc_stats is not None:
    client_log_name = secClass2Name(client_security_name, proxy_security_class)
    factoryConfig.client_stats.logSchedd(client_int_name, qc_status, qc_status_sf)
    factoryConfig.qc_stats.logSchedd(client_log_name, qc_status, qc_status_sf)

    return


def logWorkRequest(
    client_int_name,
    client_security_name,
    proxy_security_class,
    req_idle,
    adj_idle,
    req_max_run,
    remove_excess,
    work_el,
    fraction=1.0,
    log=logSupport.log,
    factoryConfig=None,
):
    """Log work requests from a client.

    Args:
        client_int_name (str): Client internal name.
        client_security_name (str): Client security name.
        proxy_security_class (str): Credential security class.
        req_idle (int): Requested number of idle glideins.
        req_max_run (int): Maximum number of running glideins.
        remove_excess (tuple): Tuple with remove_excess_str (str), and remove_excess_margin (int).
        work_el (dict): Work request element (dictionary with request details).
            Temporary workaround, the requests should always be processed at the caller level.
        fraction (float): Fraction for this entry.
        log (logging.Logger): Logger.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to the global one.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    client_log_name = secClass2Name(client_security_name, proxy_security_class)

    idle_lifetime = work_el["requests"].get("IdleLifetime", 0)

    log.info(
        "Client %s (secid: %s) requesting %i glideins, max running %i, idle lifetime %s, remove excess '%s', remove_excess_margin %s"
        % (client_int_name, client_log_name, req_idle, req_max_run, idle_lifetime, remove_excess[0], remove_excess[1])
    )
    # log.info("  Params: %s" % work_el["params"])
    # Do not log decrypted values ... they are most likely sensitive
    # Just log the keys for debugging purposes
    log.info("  Decrypted Param Names: %s" % list(work_el["params_decrypted"].keys()))
    # requests use GLIDEIN_CPUS and GLIDEIN_ESTIMATED_CPUS at the Frontend to estimate cores
    # TODO: this may change for multi_node requests (GLIDEIN_NODES)
    reqs = {"IdleGlideins": req_idle, "MaxGlideins": req_max_run, "AdjIdleGlideins": adj_idle}
    factoryConfig.client_stats.logRequest(client_int_name, reqs)
    factoryConfig.qc_stats.logRequest(client_log_name, reqs)

    factoryConfig.client_stats.logClientMonitor(client_int_name, work_el["monitor"], work_el["internals"], fraction)
    factoryConfig.qc_stats.logClientMonitor(client_log_name, work_el["monitor"], work_el["internals"], fraction)


############################################################
#
# I N T E R N A L - Do not use
#
############################################################

# condor_status_strings = {0:"Wait",1:"Idle", 2:"Running", 3:"Removed", 4:"Completed", 5:"Held", 6:"Suspended", 7:"Assigned"}
# myvm_status_strings = {-1:"Unclaimed}

#
# Hash functions
#


def get_status_glideidx(el):
    """Get the HTCondor identifiers, cluster and process ID, for a glidein job.

    Args:
        el (dict): Dictionary representing a glidein job.

    Returns:
        tuple: Tuple (clusterid, procid) extracted from the job dictionary.
    """
    global factoryConfig
    return el[factoryConfig.clusterid_startd_attribute], el[factoryConfig.procid_startd_attribute]


# Split Idle depending on GridJobStatus
#   1001 : Unsubmitted (aka Waiting)
#   1002 : Submitted/Pending
#   1010 : Staging in
#   1100 : Other
#   4010 : Staging out
# All others just return the JobStatus
def hash_status(el):
    """Compute a detailed job status code for a glidein job using JobStatus and GridJobStatus when available.

    For idle jobs (JobStatus == 1):
      - 1001: Unsubmitted (Waiting)
      - 1002: Submitted/Pending
      - 1010: Staging in
      - 1100: Other
    For running jobs (JobStatus == 2):
      - 2: Running (if GridJobStatus indicates active)
      - 4010: Staging out (if GridJobStatus indicates stage-out)
      - 1100: Otherwise
    For other statuses, returns the original JobStatus.

    Args:
        el (dict): Dictionary representing a glidein job.

    Returns:
        int: Detailed job status code.
    """
    job_status = el["JobStatus"]
    if job_status == 1:
        # idle jobs, look of GridJobStatus
        if "GridJobStatus" in el:
            grid_status = str(el["GridJobStatus"]).upper()
            if grid_status in (
                "PENDING",
                "INLRMS: Q",
                "PREPARED",
                "SUBMITTING",
                "IDLE",
                "SUSPENDED",
                "REGISTERED",
                "INLRMS:Q",
                "QUEUING",
            ):
                return 1002
            elif grid_status in ("STAGE_IN", "PREPARING", "ACCEPTING", "ACCEPTED"):
                return 1010
            else:
                return 1100
        else:
            return 1001
    elif job_status == 2:
        # count only real running, all others become Other
        if "GridJobStatus" in el:
            grid_status = str(el["GridJobStatus"]).upper()
            if grid_status in ("ACTIVE", "REALLY-RUNNING", "INLRMS: R", "RUNNING", "INLRMS:R"):
                return 2
            elif grid_status in (
                "STAGE_OUT",
                "INLRMS: E",
                "EXECUTED",
                "FINISHING",
                "FINISHED",
                "DONE",
                "INLRMS:E",
                "COMPLETED",
            ):
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
    """Add the summary of idle jobs to the statistics passed as input

    Sum idle glideins from detailed idle status codes (1000 to 1100) and update the total idle jobs (qc_status[1]).

    Args:
        qc_status (dict): Dictionary with job_status keys and job counts as values.

    Returns:
        dict: Updated qc_status with qc_status[1] set as the sum of idle variants.
    """
    #   Idle==Jobstatus(1)
    #   Have to integrate all the variants
    qc_status[1] = 0
    for k in list(qc_status.keys()):
        if (k >= 1000) and (k <= 1100):
            qc_status[1] += qc_status[k]
    return


def hash_statusStale(el):
    """Compute a stale status indicator for a glidein job.

    Calculates the age of the job from ServerTime and EnteredCurrentStatus.
    If the job's age exceeds the configured stale_maxage for its JobStatus,
    returns [JobStatus, 1]; otherwise, [JobStatus, 0].

    Args:
        el (dict): Dictionary representing a glidein job.

    Returns:
        list: List containing [JobStatus, stale_flag] (stale_flag is 1 if stale, 0 otherwise).
    """
    global factoryConfig
    age = el.get("ServerTime", time.time()) - el["EnteredCurrentStatus"]
    jstatus = el["JobStatus"]
    if jstatus in factoryConfig.stale_maxage:
        return [jstatus, age > factoryConfig.stale_maxage[jstatus]]
    else:
        return [jstatus, 0]  # others are not stale


# diffList == base_list - subtract_list
def diffList(base_list, subtract_list):
    """Return the difference between two lists.

    Args:
        base_list (list): The base list.
        subtract_list (list): The list of items to subtract.

    Returns:
        list: Items in base_list that are not in subtract_list.
    """
    if len(subtract_list) == 0:
        return base_list  # nothing to do

    out_list = []
    for i in base_list:
        if i not in subtract_list:
            out_list.append(i)

    return out_list


#
# Extract functions
# Will compare with the status info to make sure it does not show good ones
#


def extractStaleSimple(q, factoryConfig=None):
    """Extract the list of stale idle glideins (job IDs) from the queue.

    hash_statusStale returns 2 numbers: the first is 1 for Idle jobs, the second is 1 for stale jobs.
    So we are looking for glideins where hash_statusStale is [1, 1].

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        list: List of job IDs corresponding to stale idle glideins.
    """
    # first find out the stale idle jids
    #  hash: (Idle==1, Stale==1)
    qstale = q.fetchStored(lambda el: (hash_statusStale(el) == [1, 1]))
    qstale_list = list(qstale.keys())

    return qstale_list


def extractUnrecoverableHeldSimple(q, factoryConfig=None):
    """Extract job IDs of unrecoverable held glideins from the queue.

    Held jobs have status 5. isGlideinUnrecoverable uses HeldReasonCode and HoldReasonSubCode and other info
    to understand if a held glidein is recoverable.

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        list: List of job IDs for unrecoverable held glideins.
    """
    #  Held==5 and glideins are not recoverable
    # qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld = q.fetchStored(lambda el: (el["JobStatus"] == 5 and isGlideinUnrecoverable(el, factoryConfig=factoryConfig)))
    qheld_list = list(qheld.keys())
    return qheld_list


def extractUnrecoverableHeldForceX(q, factoryConfig=None):
    """Extract job IDs of unrecoverable held glideins that have been held for more than 20 iterations.

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        list: List of job IDs.
    """
    #  Held==5 and glideins are not recoverable AND been held for more than 20 iterations
    qheld = q.fetchStored(
        lambda el: (
            el["JobStatus"] == 5
            and isGlideinUnrecoverable(el, factoryConfig=factoryConfig)
            and isGlideinHeldNTimes(el, factoryConfig=factoryConfig, n=20)
        )
    )
    qheld_list = list(qheld.keys())
    return qheld_list


def extractRecoverableHeldSimple(q, factoryConfig=None):
    """Extract job IDs of recoverable held glideins from the queue.

    Held jobs have HTCondor status 5.

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        list: List of job IDs for recoverable held glideins.
    """
    #  Held==5 and glideins are recoverable
    # qheld=q.fetchStored(lambda el:(el["JobStatus"]==5 and not isGlideinUnrecoverable(el["HeldReasonCode"],el["HoldReasonSubCode"])))
    qheld = q.fetchStored(
        lambda el: (el["JobStatus"] == 5 and not isGlideinUnrecoverable(el, factoryConfig=factoryConfig))
    )
    qheld_list = list(qheld.keys())
    return qheld_list


def extractRecoverableHeldSimpleWithinLimits(q, factoryConfig=None):
    """Extract job IDs of recoverable held glideins within specified limits from the queue.

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        list: List of job IDs.
    """
    #  Held==5 and glideins are recoverable
    qheld = q.fetchStored(
        lambda el: (
            el["JobStatus"] == 5
            and not isGlideinUnrecoverable(el, factoryConfig=factoryConfig)
            and isGlideinWithinHeldLimits(el, factoryConfig=factoryConfig)
        )
    )
    qheld_list = list(qheld.keys())
    return qheld_list


def extractHeldSimple(q, factoryConfig=None):
    """Extract all held glideins (JobStatus == 5) from the queue.

    Args:
        q (condorMonitor.CondorQ): Condor queue object (dictionary of Glideins from condor_q).
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.
            Not used, kept to maintain a uniform interface.

    Returns:
        list: List of job IDs for held glideins.
    """
    #  Held==5
    qheld = q.fetchStored(lambda el: el["JobStatus"] == 5)
    qheld_list = list(qheld.keys())
    return qheld_list


def extractIdleSimple(q, factoryConfig=None):
    """Extract all idle glideins (JobStatus == 1) from the queue.

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.
            Not used, kept to maintain a uniform interface.

    Returns:
        list: List of job IDs for idle glideins.
    """
    #  Idle==1
    qidle = q.fetchStored(lambda el: el["JobStatus"] == 1)
    qidle_list = list(qidle.keys())
    return qidle_list


def extractIdleUnsubmitted(q, factoryConfig=None):
    """Extract from the queue idle glideins that are not yet submitted (Unsubmitted, aka Waiting - hash_status == 1001).

    hash_status 1xxx implies JobStatus 1.

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.
            Not used, kept to maintain a uniform interface.

    Returns:
        list: List of job IDs for idle not submitted glideins.
    """
    qidle = q.fetchStored(lambda el: hash_status(el) == 1001)  #  1001 == Unsubmitted (aka Waiting)
    qidle_list = list(qidle.keys())
    return qidle_list


def extractIdleQueued(q, factoryConfig=None):
    """Extract from the queue idle glideins that have been submitted (hash_status in {1002, 1010, 1100}).

    hash_status 1xxx (i.e. JobStatus 1) except 1001.

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.
            Not used, kept to maintain a uniform interface.

    Returns:
        list: List of job IDs for idle and submitted glideins.
    """
    qidle = q.fetchStored(lambda el: (hash_status(el) in (1002, 1010, 1100)))  #  All 1xxx but 1001
    qidle_list = list(qidle.keys())
    return qidle_list


def extractNonRunSimple(q, factoryConfig=None):
    """Extract all non-running glideins (JobStatus != 2) from the queue.

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration.

    Returns:
        list: List of job IDs for non-running glideins.
    """
    qnrun = q.fetchStored(lambda el: el["JobStatus"] != 2)  #  Run==2
    qnrun_list = list(qnrun.keys())
    return qnrun_list


def extractRunSimple(q, factoryConfig=None):
    """Extract all running glideins (JobStatus == 2) from the queue.

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration.

    Returns:
        list: List of job IDs for running glideins.
    """
    #  Run==2
    qrun = q.fetchStored(lambda el: el["JobStatus"] == 2)
    qrun_list = list(qrun.keys())
    return qrun_list


def extractRunStale(q, factoryConfig=None):
    """Extract IDs of stale running glideins from the queue.

    A glidein is considered running and stale if its hash_statusStale is [2, 1].

    Args:
        q (condorMonitor.CondorQ): Condor queue object.
        factoryConfig (FactoryConfig, optional): Factory configuration.

    Returns:
        list: List of job IDs for stale running glideins.
    """
    # first find out the stale running jids
    #  hash: (Running==2, Stale==1)
    qstale = q.fetchStored(lambda el: (hash_statusStale(el) == [2, 1]))
    qstale_list = list(qstale.keys())

    # these glideins were running for too long, period!
    return qstale_list


# TODO: remove this function from here and remove its unit test
# Seems unused (used only in unit test test_factory_glideFactoryLib.py). extractStaleUnclaimed is not in the code
# helper function of extractStaleUnclaimed
def group_unclaimed(el_list):
    """Helper function of extractStaleUnclaimed.
    Count total and unclaimed VMs (glidein jobs) based on their unclaimed status.

    Args:
        el_list (list): List of job information dictionaries.

    Returns:
        dict: Dictionary with keys 'nr_vms', 'nr_unclaimed', and 'min_unclaimed_time'.
    """
    out = {"nr_vms": 0, "nr_unclaimed": 0, "min_unclaimed_time": 1024 * 1024 * 1024}
    for el in el_list:
        out["nr_vms"] += 1
        if el["State"] == "Unclaimed":
            out["nr_unclaimed"] += 1
            unclaimed_time = el["LastHeardFrom"] - el["EnteredCurrentState"]
            if unclaimed_time < out["min_unclaimed_time"]:
                out["min_unclaimed_time"] = unclaimed_time
    return out


############################################################
#
# Action functions
#
############################################################


def schedd_name2str(schedd_name):
    """Convert a schedd name to a condor_q command-line argument string.

    Args:
        schedd_name (str or None): The schedd name.

    Returns:
        str: A string in the format "-name schedd_name" or an empty string.
    """
    if schedd_name is None:
        return ""
    else:
        return "-name %s" % schedd_name


extractJobId_recmp = re.compile(r"^(?P<count>[0-9]+) job\(s\) submitted to cluster (?P<cluster>[0-9]+)\.$")


def extractJobId(submit_out):
    """Extract the cluster ID and number of jobs from condor_submit output.

    Args:
        submit_out (list): List of strings from the condor_submit output.

    Raises:
        condorExe.ExeError: If no valid cluster information is found.

    Returns:
        tuple: A tuple (cluster, count) where cluster is the cluster ID (int) and count is the number of jobs submitted (int).
    """
    for line in submit_out:
        found = extractJobId_recmp.search(line.strip())
        if found:
            return (int(found.group("cluster")), int(found.group("count")))
    raise condorExe.ExeError("Could not find cluster info!")


escape_table = {
    ".": ".dot,",
    ",": ".comma,",
    "&": ".amp,",
    "\\": ".backslash,",
    "|": ".pipe,",
    "`": ".fork,",
    '"': ".quot,",
    "'": ".singquot,",
    "=": ".eq,",
    "+": ".plus,",
    "-": ".minus,",
    "<": ".lt,",
    ">": ".gt,",
    "(": ".open,",
    ")": ".close,",
    "{": ".gopen,",
    "}": ".gclose,",
    "[": ".sopen,",
    "]": ".sclose,",
    "#": ".comment,",
    "$": ".dollar,",
    "*": ".star,",
    "?": ".question,",
    "!": ".not,",
    "~": ".tilde,",
    ":": ".colon,",
    ";": ".semicolon,",
    " ": ".nbsp,",
}


def escapeParam(param_str):
    """Escape unsafe characters in a parameter string.

    Args:
        param_str (str): Input string to escape.

    Returns:
        str: Escaped string.
    """
    global escape_table
    out_str = ""
    for c in param_str:
        out_str = out_str + escape_table.get(c, c)
    return out_str


# submit N new glideins


def executeSubmit(log, factoryConfig, username, schedd, exe_env, submitFile):
    """Submit glideins using the condor_submit command in a custom environment.

    Args:
        log (logging.Logger): Logger object.
        factoryConfig (FactoryConfig): Factory configuration.
        username (str): Username for the credential.
        schedd (str): HTCondor schedd name.
        exe_env (list): List of environment variables.
        submitFile (str): Path to the submit file.

    Raises:
        RuntimeError: If condor_submit fails.

    Returns:
        list: List of strings from the condor_submit output.
    """
    # check to see if the username for the credential is
    # same as the factory username
    submit_out = []
    try:
        submit_out = condorExe.iexe_cmd(
            f"condor_submit -name {schedd} {submitFile}", child_env=env_list2dict(exe_env), log=log
        )
    except condorExe.ExeError as e:
        msg = "condor_submit failed: %s" % str(e)
        log.error(msg)
        raise RuntimeError(msg) from e
    except Exception as e:
        msg = "condor_submit failed: Unknown error: %s" % str(e)
        log.error(msg)
        raise RuntimeError(msg) from e
    return submit_out


def submitGlideins(
    entry_name,
    client_name,
    nr_glideins,
    idle_lifetime,
    frontend_name,
    submit_credentials,
    client_web,
    params,
    status_sf,
    log=logSupport.log,
    factoryConfig=None,
):
    """Submit new glideins by executing condor_submit.

    Call `executeSubmit` to run the HTCSS condor_submit command

    Args:
        entry_name (str): Name of the entry.
        client_name (str): Client (e.g. Frontend group) name.
        nr_glideins (int): Number of glideins to submit.
        idle_lifetime (int): Idle lifetime for glideins.
        frontend_name (str): Frontend name.
        submit_credentials (SubmitCredentials): Credentials for submission.
        client_web (ClientWeb): Client web object (or None).
        params (dict): Parameters from the entry or Frontend configuration.
        status_sf (dict): Dictionary with keys as GlideinEntrySubmitFile(s) and values as job status counts.
        log (logging.Logger): Logger. Defaults to the global logger.
        factoryConfig (FactoryConfig, optional): Factory configuration.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    # get the username
    username = submit_credentials.username

    # Need information from glidein.descript, job.descript, and signatures.sha1
    jobDescript = glideFactoryConfig.JobDescript(entry_name)
    schedd = jobDescript.data["Schedd"]
    algo_name = jobDescript.data.get("EntrySelectionAlgorithm", None)
    if algo_name and algo_name != "Default":
        log.debug(f"Selection algorithm name for entry {entry_name} is: {algo_name}")

    # List of job ids that have been submitted - initialize to empty array
    submitted_jids = []

    try:
        entry_env = get_submit_environment(
            entry_name,
            client_name,
            submit_credentials,
            client_web,
            params,
            idle_lifetime,
            log=log,
            factoryConfig=factoryConfig,
        )
    except Exception as e:
        msg = "Failed to setup execution environment."
        log.error(msg)
        log.exception(msg)
        raise RuntimeError(msg) from e

    if username != MY_USERNAME:
        # need to push all the relevant env variables through
        for var in os.environ:
            if (
                (var in ("PATH", "LD_LIBRARY_PATH", "X509_CERT_DIR"))
                or (var[:8] == "_CONDOR_")
                or (var[:7] == "CONDOR_")
            ):
                try:
                    entry_env.append(f"{var}={os.environ[var]}")
                except KeyError:
                    msg = """KeyError: '%s' not found in execution environment!!""" % (var)
                    log.warning(msg)
    try:
        submit_files = glob.glob("entry_%s/job.*condor" % entry_name)
        if algo_name:
            selection_function = getattr(
                glideinwms.factory.glideFactorySelectionAlgorithms, "selectionAlgo" + algo_name
            )
            submit_files = selection_function(submit_files, status_sf, jobDescript, nr_glideins, log)
        else:
            submit_files = {submit_files[0]: nr_glideins}

        for submit_file, nr_glideins_sf in list(submit_files.items()):
            nr_submitted = 0
            while nr_submitted < nr_glideins_sf:
                sub_env = []
                if nr_submitted != 0:
                    time.sleep(factoryConfig.submit_sleep)

                nr_to_submit = nr_glideins_sf - nr_submitted
                if nr_to_submit > factoryConfig.max_cluster_size:
                    nr_to_submit = factoryConfig.max_cluster_size

                sub_env.append("GLIDEIN_COUNT=%s" % nr_to_submit)
                sub_env.append("GLIDEIN_FRONTEND_NAME=%s" % frontend_name)
                sub_env.append("GLIDEIN_ENTRY_SUBMIT_FILE=%s" % submit_file)
                exe_env = entry_env + sub_env

                submit_out = executeSubmit(log, factoryConfig, username, schedd, exe_env, submit_file)

                cluster, count = extractJobId(submit_out)
                for j in range(count):
                    submitted_jids.append((cluster, j))
                nr_submitted += count
    finally:
        # write out no matter what
        log.info("Submitted %i glideins to %s: %s" % (len(submitted_jids), schedd, submitted_jids))


def removeGlideins(schedd_name, jid_list, force=False, log=logSupport.log, factoryConfig=None):
    """Remove glideins specified by job IDs.

    This function attempts to remove glidein jobs from the schedd.
    We are assuming gfactory (the Factory user) to be a HTCondor superuser or the only user owning jobs (Glideins)
    and thus does not need identity switching to remove jobs.

    Args:
        schedd_name (str): HTCondor schedd name.
        jid_list (list): List of job IDs (tuples) to remove.
        force (bool, optional): If True, force removal. Defaults to False.
        log (logging.Logger): Logger. Defaults to the global logger.
        factoryConfig (FactoryConfig, optional): Factory configuration.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    removed_jids = []

    is_not_first = 0
    for jid in jid_list:
        # Respect the max_removes limit and exit right away if required
        if len(removed_jids) >= factoryConfig.max_removes:
            break  # limit reached, stop

        if is_not_first:
            is_not_first = 1
            time.sleep(factoryConfig.remove_sleep)

        try:
            # this will put a job in X state so that the next condor_rm --forcex below should work
            condorManager.condorRemoveOne("%li.%li" % (jid[0], jid[1]), schedd_name)
            removed_jids.append(jid)

            # Force the removal if requested
            if force is True:
                try:
                    log.info("Forcing the removal of glideins in X state")
                    condorManager.condorRemoveOne("%li.%li" % (jid[0], jid[1]), schedd_name, do_forcex=True)
                except condorExe.ExeError:
                    log.warning(f"Forcing the removal of glideins in {jid[0]}.{jid[1]} state failed")

        except condorExe.ExeError as e:
            # silently ignore errors, and try next one
            log.warning("removeGlidein(%s,%li.%li): %s" % (schedd_name, jid[0], jid[1], e))

    log.info("Removed %i glideins on %s: %s" % (len(removed_jids), schedd_name, removed_jids))


def releaseGlideins(schedd_name, jid_list, log=logSupport.log, factoryConfig=None):
    """Release glideins specified by job IDs.

    We are assuming gfactory (the Factory user) to be a HTCondor superuser or the only user owning jobs (Glideins)
    and thus does not need identity switching to release jobs.

    Args:
        schedd_name (str): HTCondor schedd name.
        jid_list (list): List of job IDs (tuples) to release.
        log (logging.Logger): Logger.
        factoryConfig (FactoryConfig, optional): Factory configuration.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    released_jids = []

    is_not_first = 0
    for jid in jid_list:
        if len(released_jids) > factoryConfig.max_releases:
            break  # limit reached, stop

        if is_not_first:
            is_not_first = 1
            time.sleep(factoryConfig.release_sleep)
        try:
            condorManager.condorReleaseOne("%li.%li" % (jid[0], jid[1]), schedd_name)
            released_jids.append(jid)
        except condorExe.ExeError as e:
            log.warning("releaseGlidein(%s,%li.%li): %s" % (schedd_name, jid[0], jid[1], e))

    log.info("Released %i glideins on %s: %s" % (len(released_jids), schedd_name, released_jids))


def in_submit_environment(entry_name, exe_env):
    """Check if the entry name is present in the execution environment.

    Args:
        entry_name (str): Entry name.
        exe_env (list): List of environment strings.

    Returns:
        bool: True if an environment variable with the entry_name (uppercased) exists, False otherwise.
    """
    upper_name = "%s=" % entry_name.upper()
    for i in exe_env:
        if i.startswith(upper_name):
            return True
    return False


def get_submit_environment(
    entry_name,
    client_name,
    submit_credentials,
    client_web,
    params,
    idle_lifetime,
    log=logSupport.log,
    factoryConfig=None,
):
    """Set up the submission environment for glidein_startup.sh.

    Args:
        entry_name (str): Entry name.
        client_name (str): Client name.
        submit_credentials (SubmitCredentials): Submission credentials.
        client_web (ClientWeb): Client web object (or None).
        params (dict): Parameters from the entry configuration or frontend.
        idle_lifetime (int): Idle lifetime for glideins.
        log (logging.Logger): Logger.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        list: List of environment variables as strings.

    Raises:
        Exception: If the environment setup fails.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    try:
        glideinDescript = glideFactoryConfig.GlideinDescript()
        jobDescript = glideFactoryConfig.JobDescript(entry_name)
        jobAttributes = glideFactoryConfig.JobAttributes(entry_name)
        signatures = glideFactoryConfig.SignatureFile()

        exe_env = ["GLIDEIN_ENTRY_NAME=%s" % entry_name]
        if "frontend_scitoken" in submit_credentials.identity_credentials:
            exe_env.append("SCITOKENS_FILE=%s" % submit_credentials.identity_credentials["frontend_scitoken"])
        if "frontend_condortoken" in submit_credentials.identity_credentials:
            exe_env.append("IDTOKENS_FILE=%s" % submit_credentials.identity_credentials["frontend_condortoken"])
        else:
            # TODO: this ends up transferring an empty file called 'null' in the Glidein start dir. Find a better way
            exe_env.append("IDTOKENS_FILE=/dev/null")

        # The parameter list to be added to the arguments for glidein_startup.sh
        params_str = ""
        # if client_web has been provided, get the arguments and add them to the string
        if client_web is not None:
            params_str = " ".join(client_web.get_glidein_args())
        # add all the params to the argument string
        for k, v in params.items():
            # Remove the null parameters and warn
            if not str(v).strip():
                log.warning("Skipping empty job parameter (%s)" % k)
                continue
            exe_env.append(f"GLIDEIN_PARAM_{k}={str(v)}")
            params_str += f" -param_{k} {escapeParam(str(v))}"

        exe_env.append("GLIDEIN_CLIENT=%s" % client_name)
        exe_env.append("GLIDEIN_SEC_CLASS=%s" % submit_credentials.security_class)

        # Glidein username (for client logs)
        exe_env.append("GLIDEIN_USER=%s" % submit_credentials.username)

        # Credential id, required for querying the condor q
        exe_env.append("GLIDEIN_CREDENTIAL_ID=%s" % submit_credentials.id)

        # Entry Params (job.descript)
        schedd = jobDescript.data["Schedd"]
        verbosity = jobDescript.data["Verbosity"]
        startup_dir = jobDescript.data["StartupDir"]
        slots_layout = jobDescript.data["SubmitSlotsLayout"]
        max_walltime = jobAttributes.data.get("GLIDEIN_Max_Walltime")
        proxy_url = jobDescript.data.get("ProxyURL", None)

        exe_env.append("GLIDEIN_SCHEDD=%s" % schedd)
        exe_env.append("GLIDEIN_VERBOSITY=%s" % verbosity)
        exe_env.append("GLIDEIN_STARTUP_DIR=%s" % startup_dir)
        exe_env.append("GLIDEIN_SLOTS_LAYOUT=%s" % slots_layout)
        if max_walltime:
            exe_env.append("GLIDEIN_MAX_WALLTIME=%s" % max_walltime)

        submit_time = timeConversion.get_time_in_format(time_format="%Y%m%d")
        exe_env.append("GLIDEIN_LOGNR=%s" % str(submit_time))

        # Main Params (glidein.descript
        glidein_name = glideinDescript.data["GlideinName"]
        factory_name = glideinDescript.data["FactoryName"]
        web_url = glideinDescript.data["WebURL"]

        exe_env.append("GLIDEIN_NAME=%s" % glidein_name)
        exe_env.append("FACTORY_NAME=%s" % factory_name)
        exe_env.append("GLIDEIN_WEB_URL=%s" % web_url)
        exe_env.append("GLIDEIN_IDLE_LIFETIME=%s" % idle_lifetime)

        # Security Params (signatures.sha1)
        # sign_type has always been hardcoded... we can change in the future if need be
        sign_type = "sha1"
        exe_env.append("SIGN_TYPE=%s" % sign_type)

        main_descript = signatures.data["main_descript"]
        main_sign = signatures.data["main_sign"]

        entry_descript = signatures.data["entry_%s_descript" % entry_name]
        entry_sign = signatures.data["entry_%s_sign" % entry_name]

        exe_env.append("MAIN_DESCRIPT=%s" % main_descript)
        exe_env.append("MAIN_SIGN=%s" % main_sign)
        exe_env.append("ENTRY_DESCRIPT=%s" % entry_descript)
        exe_env.append("ENTRY_SIGN=%s" % entry_sign)

        # Specify how the slots layout should be
        slots_layout = jobDescript.data["SubmitSlotsLayout"]
        # Build the glidein pilot arguments
        glidein_arguments = str(
            "-v %s -name %s -entry %s -clientname %s -schedd %s -proxy %s "
            "-factory %s -web %s -sign %s -signentry %s -signtype %s "
            "-descript %s -descriptentry %s -dir %s -param_GLIDEIN_Client %s -submitcredid %s -slotslayout %s %s"
            % (
                verbosity,
                glidein_name,
                entry_name,
                client_name,
                schedd,
                proxy_url,
                factory_name,
                web_url,
                main_sign,
                entry_sign,
                sign_type,
                main_descript,
                entry_descript,
                startup_dir,
                client_name,
                submit_credentials.id,
                slots_layout,
                params_str,
            )
        )
        glidein_arguments = glidein_arguments.replace('"', '\\"')
        # log.debug("glidein_arguments: %s" % glidein_arguments)

        # get my (entry) type
        grid_type = jobDescript.data["GridType"]
        if grid_type.startswith("batch "):
            log.debug("submit_credentials.security_credentials: %s" % str(submit_credentials.security_credentials))
            # TODO: username, should this be only for batch or all key pair + username/password?
            try:
                # is always there and not empty for batch (is optional w/ Key pair or Username/password
                # otherwise could not be there (KeyError), be empty (AttributeError), bad format (IndexError)
                remote_username = submit_credentials.identity_credentials["RemoteUsername"]
                if remote_username:
                    exe_env.append("GLIDEIN_REMOTE_USERNAME=%s" % remote_username)
            except KeyError:
                pass
            exe_env.append(
                "GRID_RESOURCE_OPTIONS=--rgahp-key %s --rgahp-nopass"
                % submit_credentials.security_credentials["PrivateKey"]
            )
            exe_env.append("X509_USER_PROXY=%s" % submit_credentials.security_credentials["GlideinProxy"])
            exe_env.append(
                "X509_USER_PROXY_BASENAME=%s"
                % os.path.basename(submit_credentials.security_credentials["GlideinProxy"])
            )
            glidein_arguments += " -cluster $(Cluster) -subcluster $(Process)"
            # condor and batch (BLAH/BOSCO) submissions do not like arguments enclosed in quotes
            # - batch pbs would consider a single argument if quoted
            # - condor and batch condor would return a submission error
            # condor_submit will swallow the " character in the string.
            # condor_submit will include ' as a literal in the arguments string, causing breakage
            # Hence, use " for now.
            exe_env.append("GLIDEIN_ARGUMENTS=%s" % glidein_arguments)
        elif grid_type in ("ec2", "gce"):
            # do not uncomment these in production, it exposes secrets that
            # should not be logged
            # log.debug("params: %s" % str(params))
            # log.debug("submit_credentials.security_credentials: %s" % str(submit_credentials.security_credentials))
            # log.debug("submit_credentials.identity_credentials: %s" % str(submit_credentials.identity_credentials))

            try:
                exe_env.append("X509_USER_PROXY=%s" % submit_credentials.security_credentials["GlideinProxy"])

                exe_env.append("IMAGE_ID=%s" % submit_credentials.identity_credentials["VMId"])
                exe_env.append("INSTANCE_TYPE=%s" % submit_credentials.identity_credentials["VMType"])
                if grid_type == "ec2":
                    exe_env.append("ACCESS_KEY_FILE=%s" % submit_credentials.security_credentials["PublicKey"])
                    exe_env.append("SECRET_KEY_FILE=%s" % submit_credentials.security_credentials["PrivateKey"])
                    exe_env.append(
                        "CREDENTIAL_DIR=%s" % os.path.dirname(submit_credentials.security_credentials["PublicKey"])
                    )
                elif grid_type == "gce":
                    exe_env.append("GCE_AUTH_FILE=%s" % submit_credentials.security_credentials["AuthFile"])
                    exe_env.append("GRID_RESOURCE_OPTIONS=%s" % "$(gce_project_name) $(gce_availability_zone)")
                    exe_env.append(
                        "CREDENTIAL_DIR=%s" % os.path.dirname(submit_credentials.security_credentials["AuthFile"])
                    )

                try:
                    vm_max_lifetime = str(params["VM_MAX_LIFETIME"])
                except Exception:
                    # if no lifetime is specified, then default to 12 hours
                    # we can change this to a more "sane" default if we can
                    # agree to what is "sane"
                    vm_max_lifetime = str(43200)
                    log.debug("No lifetime set.  Defaulting to: %s" % vm_max_lifetime)

                try:
                    vm_disable_shutdown = str(params["VM_DISABLE_SHUTDOWN"])
                except Exception:
                    # By default assume we don't want to debug the VM
                    log.debug("No disable flag set.  Defaulting to: False")
                    vm_disable_shutdown = "False"

                # change proxy to token in template
                ini_template = """[glidein_startup]
args = %s
idtoken_file_name = credential_frontend.idtoken
proxy_file_name = pilot_proxy
webbase= %s

[vm_properties]
max_lifetime = %s
contextualization_type = %s
disable_shutdown = %s
admin_email = UNSUPPORTED
email_logs = False
"""

                ini = ini_template % (
                    glidein_arguments,
                    web_url,
                    vm_max_lifetime,
                    grid_type.upper(),
                    vm_disable_shutdown,
                )
                log.debug("Userdata ini file:\n%s" % ini)
                ini = base64.b64encode(ini.encode()).decode(BINARY_ENCODING)
                log.debug("Userdata ini file has been base64 encoded")
                exe_env.append("USER_DATA=%s" % ini)

                # get the proxy
                full_path_to_proxy = submit_credentials.security_credentials["GlideinProxy"]
                exe_env.append("GLIDEIN_PROXY_FNAME=%s" % full_path_to_proxy)

            except KeyError:
                msg = "Error setting up submission environment (bad key)"
                log.debug(msg)
                log.exception(msg)
                # Known error, can continue without the missing elements
                #  (from the one missing to the end of the section)
            except Exception:
                msg = "Error setting up submission environment (in %s section)" % grid_type
                log.debug(msg)
                log.exception(msg)
                # Unknown error, re-raise to stop the environment build
                raise
        else:
            proxy = submit_credentials.security_credentials.get("SubmitProxy", "")
            exe_env.append("X509_USER_PROXY=%s" % proxy)

            # TODO: we might review this part as we added this here because the macros were been expanded when used in the gt2 submission
            # we don't add the macros to the arguments for the EC2 submission since condor will never
            # see the macros
            glidein_arguments += " -cluster $(Cluster) -subcluster $(Process)"
            if grid_type == "condor":
                # batch grid type are handled above
                # condor_submit will swallow the " character in the string.
                exe_env.append("GLIDEIN_ARGUMENTS=%s" % glidein_arguments)
            else:
                exe_env.append('GLIDEIN_ARGUMENTS="%s"' % glidein_arguments)

            # RSL is definitely not for cloud entries
            glidein_rsl = ""
            if "GlobusRSL" in jobDescript.data:
                glidein_rsl = jobDescript.data["GlobusRSL"]

            if "project_id" in jobDescript.data["AuthMethod"]:
                # Append project id to the rsl
                glidein_rsl = "{}(project={})".format(glidein_rsl, submit_credentials.identity_credentials["ProjectId"])
                exe_env.append("GLIDEIN_PROJECT_ID=%s" % submit_credentials.identity_credentials["ProjectId"])

            exe_env.append("GLIDEIN_RSL=%s" % glidein_rsl)

        return exe_env
    except Exception as e:
        msg = "Error setting up submission environment: %s" % str(e)
        log.debug(msg)
        log.exception(msg)
        # Exception logged, continuing. No valid environment, returning None


def isGlideinWithinHeldLimits(jobInfo, factoryConfig=None):
    """Determine whether a glidein job is within held limits.

    Looks at the glidein job's information and returns if the CondorG (Grid universe) job can be released,
    e.g. it has not been released too many times or too recently.
    This is useful to limit how often held jobs are released.

    Args:
        jobInfo (dict): Dictionary containing glidein job's classad information.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.

    Returns:
        bool: True if the job is within held limits, False otherwise.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    # some basic sanity checks to start
    if "JobStatus" not in jobInfo:
        return True
    if jobInfo["JobStatus"] != 5:
        return True

    # assume within limits, unless released recently or has been released too often
    within_limits = True

    num_holds = 1
    if "NumSystemHolds" in jobInfo:
        num_holds = jobInfo["NumSystemHolds"]

    if num_holds > factoryConfig.max_release_count:
        within_limits = False

    if "ServerTime" in jobInfo and "EnteredCurrentStatus" in jobInfo:
        held_period = jobInfo["ServerTime"] - jobInfo["EnteredCurrentStatus"]
        if held_period < (num_holds * factoryConfig.min_release_time):
            # slower for repeat offenders
            within_limits = False

    return within_limits


# Get list of CondorG job status for held jobs that are not recoverable
def isGlideinUnrecoverable(jobInfo, factoryConfig=None, glideinDescript=None):
    """Determine whether a CondorG glidein job (Grid universe) is unrecoverable.

    This function uses HoldReasonCode and HoldReasonSubCode from jobInfo along with a list of recoverable
    exit codes specified in glideinDescript. If the job's codes are not listed as recoverable, the job is considered
    unrecoverable.
    Condor hold codes are available at:
    https://htcondor.readthedocs.io/en/latest/classad-attributes/job-classad-attributes.html

    In v3.6.2 the behavior of the function changed. Instead of having a list
    of unrecoverable codes in the function (that got outdated once the Globus Toolkit was
    deprecated), we consider each code unrecoverable by default and give the operators
    the possibility to specify a list of recoverable codes in the configuration.

    Args:
        jobInfo (dict): Dictionary containing glidein job's classad information.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.
        glideinDescript (GlideinDescript, optional): Glidein description object. Defaults to a new instance if None.

    Returns:
        bool: True if the job is unrecoverable, False otherwise.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    if glideinDescript is None:
        glideinDescript = glideFactoryConfig.GlideinDescript()

    recoverable = False
    recoverableCodes = {}
    for codestr in glideinDescript.data.get("RecoverableExitcodes", "").split(","):
        if not codestr:
            continue  # skip empty codes
        splitstr = codestr.split(" ")
        code = int(splitstr[0])
        recoverableCodes[code] = []
        for subcode in splitstr[1:]:
            recoverableCodes[code].append(int(subcode))

    try:
        code = jobInfo.get("HoldReasonCode")
        code = code and int(code)
    except ValueError:
        code = None
    try:
        subCode = jobInfo.get("HoldReasonSubCode")
        subCode = subCode and int(subCode)
    except ValueError:
        subcode = None
    # Keep around HoldReason for the future
    # holdreason = jobInfo.get('HoldReason')

    # Based on HoldReasonCode check if the job is recoverable
    if (code is not None) and (code in recoverableCodes):
        if len(recoverableCodes[code]) > 0:
            # Check the subcode if we have any
            if subCode in recoverableCodes[code]:
                recoverable = True
        else:
            recoverable = True

    # Following check with NumSystemHolds should only apply to recoverable jobs
    # If we have determined that job is unrecoverable, skip these checks
    if recoverable:
        num_holds = 1
        job_status = jobInfo.get("JobStatus")
        num_system_holds = jobInfo.get("NumSystemHolds")
        if (job_status is not None) and (num_system_holds is not None):
            if job_status == 5:
                num_holds = num_system_holds
        if num_holds > factoryConfig.max_release_count:
            recoverable = False

    return not recoverable


def isGlideinHeldNTimes(jobInfo, factoryConfig=None, n=20):
    """Check if a glidein job has been held for more than n iterations.

    This is useful to remove old unrecoverable glideins (CondorG jobs) with forcex option.

    Args:
        jobInfo (dict): Dictionary containing glidein job's classad information.
        factoryConfig (FactoryConfig, optional): Factory configuration. Defaults to global configuration.
        n (int, optional): Number of iterations threshold. Defaults to 20.

    Returns:
        bool: True if the job is held more than n iterations, False otherwise.
    """
    if factoryConfig is None:
        factoryConfig = globals()["factoryConfig"]

    greater_than_n_iterations = False
    nsysholds = jobInfo.get("NumSystemHolds")
    if nsysholds > n:
        greater_than_n_iterations = True

    return greater_than_n_iterations


############################################################
# only allow simple strings
def is_str_safe(s):
    """Check if a string contains only safe characters.

    Allowed characters are: letters, digits, and "._-@".

    Args:
        s (str): The string to check.

    Returns:
        bool: True if the string is safe, False otherwise.
    """
    for c in s:
        if c not in ("._-@" + string.ascii_letters + string.digits):
            return False
    return True


class GlideinTotals:
    """Class to keep track of all Glidein totals for an Entry and all Clients (Frontends)."""

    def __init__(self, entry_name, frontendDescript, jobDescript, entry_condorQ, log=logSupport.log):
        """Initialize GlideinTotals object.

        Args:
            entry_name (str): Name of the entry.
            frontendDescript (FrontendDescript): Frontend/Client description object.
            jobDescript (glideFactoryConfig.JobDescript): Job description object.
            entry_condorQ (condorMonitor.CondorQ): HTCondor queue object for the Entry.
            log (logging.Logger): Logger.
        """
        # Initialize entry limits
        self.entry_name = entry_name
        self.entry_max_glideins = int(jobDescript.data["PerEntryMaxGlideins"])
        self.entry_max_held = int(jobDescript.data["PerEntryMaxHeld"])
        self.entry_max_idle = int(jobDescript.data["PerEntryMaxIdle"])

        # Initialize default frontend-sec class limits
        self.default_fesc_max_glideins = int(jobDescript.data["DefaultPerFrontendMaxGlideins"])
        self.default_fesc_max_held = int(jobDescript.data["DefaultPerFrontendMaxHeld"])
        self.default_fesc_max_idle = int(jobDescript.data["DefaultPerFrontendMaxIdle"])

        # Count glideins by status
        # Initialized since the held and running won't ever change
        # To simplify idle requests, this variable is updated at the same time the frontend count is updated
        qc_status = getQStatus(entry_condorQ)
        self.entry_running = 0
        self.entry_held = 0
        self.entry_idle = 0
        if 2 in qc_status:  # Running==Jobstatus(2)
            self.entry_running = qc_status[2]
        if 5 in qc_status:  # Held==JobStatus(5)
            self.entry_held = qc_status[5]
        sum_idle_count(qc_status)
        if 1 in qc_status:  # Idle==Jobstatus(1)
            self.entry_idle = qc_status[1]

        all_frontends = frontendDescript.get_all_frontend_sec_classes()

        # Initialize frontend security class limits
        self.frontend_limits = {}
        for fe_sec_class in all_frontends:
            self.frontend_limits[fe_sec_class] = {
                "max_glideins": self.default_fesc_max_glideins,
                "max_held": self.default_fesc_max_held,
                "max_idle": self.default_fesc_max_idle,
            }

        # Get factory parameters for frontend-specific limits
        # Format: frontend1:sec_class1;number,frontend2:sec_class2;number

        limits_keynames = (
            ("PerFrontendMaxGlideins", "max_glideins"),
            ("PerFrontendMaxIdle", "max_idle"),
            ("PerFrontendMaxHeld", "max_held"),
        )

        for jd_key, max_glideinstatus_key in limits_keynames:
            fe_glideins_param = jobDescript.data[jd_key]

            if fe_glideins_param.find(";") != -1:
                for el in fe_glideins_param.split(","):
                    el_list = el.split(";")
                    try:
                        self.frontend_limits[el_list[0]][max_glideinstatus_key] = int(el_list[1])
                    except Exception:
                        log.warning(
                            "Invalid FrontendName:SecurityClassName combo '%s' encountered while finding '%s' from max_job_frontend"
                            % (el_list[0], max_glideinstatus_key)
                        )

        # Initialize frontend totals
        for fe_sec_class in self.frontend_limits:
            # Filter the queue for all glideins for this frontend:security_class (GLIDEIN_FRONTEND_NAME)
            fe_condorQ = condorMonitor.SubQuery(
                entry_condorQ, lambda d: (d[factoryConfig.frontend_name_attribute] == fe_sec_class)
            )
            fe_condorQ.schedd_name = entry_condorQ.schedd_name
            fe_condorQ.factory_name = entry_condorQ.factory_name
            fe_condorQ.glidein_name = entry_condorQ.glidein_name
            fe_condorQ.entry_name = entry_condorQ.entry_name
            fe_condorQ.load()

            # Count glideins by status
            qc_status = getQStatus(fe_condorQ)
            fe_running = 0
            fe_held = 0
            fe_idle = 0
            if 2 in qc_status:  # Running==Jobstatus(2)
                fe_running = qc_status[2]
            if 5 in qc_status:  # Held==JobStatus(5)
                fe_held = qc_status[5]
            sum_idle_count(qc_status)
            if 1 in qc_status:  # Idle==Jobstatus(1)
                fe_idle = qc_status[1]

            self.frontend_limits[fe_sec_class]["running"] = fe_running
            self.frontend_limits[fe_sec_class]["held"] = fe_held
            self.frontend_limits[fe_sec_class]["idle"] = fe_idle

    def can_add_idle_glideins(self, nr_glideins, frontend_name, log=logSupport.log, factoryConfig=factoryConfig):
        """Determine how many additional idle Glideins can be added respecting the Factory limits.

        Uses only the per-entry and per-client limits set in the Factory.
        Does not compare against the request max_glideins and does not update totals.

        Args:
            nr_glideins (int): Number of additional Glideins proposed by the `frontend_name` client.
            frontend_name (str): Frontend name (frontend:security class key).
            log (logging.Logger): Logger.
            factoryConfig (FactoryConfig, optional): Factory configuration.

        Returns:
            int: Number of additional Glideins allowed.
        """
        if factoryConfig is None:
            factoryConfig = globals()["factoryConfig"]

        nr_allowed = nr_glideins

        # Check entry idle limit
        if self.entry_idle + nr_allowed > self.entry_max_idle:
            # adjust to under the limit
            nr_allowed = self.entry_max_idle - self.entry_idle

        # Check entry total glideins
        if self.entry_idle + nr_allowed + self.entry_running > self.entry_max_glideins:
            nr_allowed = self.entry_max_glideins - self.entry_idle - self.entry_running

        fe_limit = self.frontend_limits[frontend_name]

        # Check frontend:sec_class idle limit
        if fe_limit["idle"] + nr_allowed > fe_limit["max_idle"]:
            nr_allowed = fe_limit["max_idle"] - fe_limit["idle"]

        # Check frontend:sec_class total glideins
        if fe_limit["idle"] + nr_allowed + fe_limit["running"] > fe_limit["max_glideins"]:
            nr_allowed = fe_limit["max_glideins"] - fe_limit["idle"] - fe_limit["running"]

        # Return
        return nr_allowed

    def add_idle_glideins(self, nr_glideins, frontend_name):
        """Update totals for idle glideins by adding the new glideins.

        Args:
            nr_glideins (int): Number of glideins to add.
            frontend_name (str): Frontend name.
        """
        self.entry_idle += nr_glideins
        self.frontend_limits[frontend_name]["idle"] += nr_glideins

    def get_max_held(self, frontend_name):
        """Get the maximum held glideins allowed for a given frontend:security class.

        Args:
            frontend_name (str): Frontend name.

        Returns:
            int: Maximum held glideins.
        """
        return self.frontend_limits[frontend_name]["max_held"]

    def has_sec_class_exceeded_max_held(self, frontend_name):
        """Check if a Frontend and security class has exceeded the maximum held glideins.

        Args:
            frontend_name (str): Frontend name.

        Returns:
            bool: True if held glideins exceed limit, False otherwise.
        """
        return self.frontend_limits[frontend_name]["held"] >= self.frontend_limits[frontend_name]["max_held"]

    def has_entry_exceeded_max_held(self):
        """Check if the entry has exceeded its maximum held glideins.

        Returns:
            bool: True if exceeded, False otherwise.
        """
        return self.entry_held >= self.entry_max_held

    def has_entry_exceeded_max_idle(self):
        """Check if the entry has exceeded its maximum idle glideins.

        Returns:
            bool: True if exceeded, False otherwise.
        """
        return self.entry_idle >= self.entry_max_idle

    def has_entry_exceeded_max_glideins(self):
        """Check if the entry has exceeded its total glideins limit (idle + running + held).

        Returns:
            bool: True if exceeded, False otherwise.
        """
        # max_glideins=total glidens for an entry.  Total is defined as idle+running+held
        return self.entry_idle + self.entry_running >= self.entry_max_glideins

    def __str__(self):
        """Return a string representation of the GlideinTotals (for testing purposes).

        Returns:
            str: Formatted string with totals and limits.
        """
        output = ""
        output += "GlideinTotals ENTRY NAME = %s\n" % self.entry_name
        output += "GlideinTotals ENTRY VALUES\n"
        output += "     total idle=%s\n" % self.entry_idle
        output += "     total held=%s\n" % self.entry_held
        output += "     total running=%s\n" % self.entry_running
        output += "GlideinTotals ENTRY MAX VALUES\n"
        output += "     entry max_idle=%s\n" % self.entry_max_idle
        output += "     entry max_held=%s\n" % self.entry_max_held
        output += "     entry max_glideins=%s\n" % self.entry_max_glideins
        output += "GlideinTotals DEFAULT FE-SC MAX VALUES\n"
        output += "     default frontend-sec class max_idle=%s\n" % self.default_fesc_max_idle
        output += "     default frontend-sec class max_held=%s\n" % self.default_fesc_max_held
        output += "     default frontend-sec class max_glideins=%s\n" % self.default_fesc_max_glideins

        for frontend in list(self.frontend_limits.keys()):
            fe_limit = self.frontend_limits[frontend]
            output += "GlideinTotals FRONTEND NAME = %s\n" % frontend
            output += "     idle = %s\n" % fe_limit["idle"]
            output += "     max_idle = %s\n" % fe_limit["max_idle"]
            output += "     held = %s\n" % fe_limit["held"]
            output += "     max_held = %s\n" % fe_limit["max_held"]
            output += "     running = %s\n" % fe_limit["running"]
            output += "     max_glideins = %s\n" % fe_limit["max_glideins"]

        return output


#######################################################


def set_condor_integrity_checks():
    os.environ["_CONDOR_SEC_DEFAULT_INTEGRITY"] = "REQUIRED"
    os.environ["_CONDOR_SEC_CLIENT_INTEGRITY"] = "REQUIRED"
    os.environ["_CONDOR_SEC_READ_INTEGRITY"] = "REQUIRED"
    os.environ["_CONDOR_SEC_WRITE_INTEGRITY"] = "REQUIRED"


#######################################################


def which(program):
    """Implementation of which command in Python. Search for the given program in the system PATH.

    Args:
        program (str): The program name.

    Returns:
        str or None: The full path to the executable if found, otherwise None.
    """

    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None


def days2sec(days):
    """Convert days to seconds.

    Args:
        days (float): Number of days.

    Returns:
        int: Equivalent seconds.
    """
    return int(days * 24 * 60 * 60)


def hrs2sec(hrs):
    """Convert hours to seconds.

    Args:
        hrs (float): Number of hours.

    Returns:
        int: Equivalent seconds.
    """
    return int(hrs * 60 * 60)


def env_list2dict(env, sep="="):
    """Convert a list of environment variable strings to a dictionary.

    Args:
        env (list): List of strings in the format "KEY=VALUE".
        sep (str, optional): Separator character. Defaults to "=".

    Returns:
        dict: Dictionary mapping keys to values.
    """
    env_dict = {}
    for ent in env:
        tokens = ent.split(sep, 1)
        if len(tokens) == 2:
            env_dict[tokens[0]] = tokens[1]
    return env_dict
