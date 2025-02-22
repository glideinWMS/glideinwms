#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This is the main of the glideinFactory

Arguments:
   $1 = glidein submit_dir
"""

import copy
import fcntl

# import glob
import json
import math
import os
import resource
import secrets
import signal
import stat
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt

from M2Crypto.RSA import RSAError

from glideinwms.factory import (
    glideFactoryConfig,
    glideFactoryCredentials,
    glideFactoryDowntimeLib,
    glideFactoryEntryGroup,
    glideFactoryInterface,
    glideFactoryLib,
    glideFactoryMonitorAggregator,
    glideFactoryMonitoring,
    glideFactoryPidLib,
)
from glideinwms.lib import cleanupSupport, condorMonitor, glideinWMSVersion, logSupport, util
from glideinwms.lib.condorMonitor import CondorQEdit, QueryError

FACTORY_DIR = os.path.dirname(glideFactoryLib.__file__)


############################################################
def aggregate_stats(in_downtime):
    """
    Aggregate all the monitoring stats

    @type in_downtime: boolean
    @param in_downtime: Entry downtime information
    :return stats dictionary
    """
    stats = {}
    try:
        _ = glideFactoryMonitorAggregator.aggregateStatus(in_downtime)
    except Exception:
        # protect and report
        logSupport.log.exception("aggregateStatus failed: ")
    try:
        stats["LogSummary"] = glideFactoryMonitorAggregator.aggregateLogSummary()
    except Exception:
        # protect and report
        logSupport.log.exception("aggregateLogStatus failed: ")
    try:
        glideFactoryMonitorAggregator.aggregateRRDStats(log=logSupport.log)
    except Exception:
        # protect and report
        logSupport.log.exception("aggregateRRDStats failed: ")
    return stats


def update_classads():
    """Load the aggregate job summary pickle files, and then
    quedit the finished jobs adding a new classad called MONITOR_INFO with the monitor information.
    """
    jobinfo = glideFactoryMonitorAggregator.aggregateJobsSummary()
    for cnames, joblist in jobinfo.items():
        schedd_name = cnames[0]
        pool_name = cnames[1]
        try:
            qe = CondorQEdit(pool_name=pool_name, schedd_name=schedd_name)
            qe.executeAll(
                joblist=list(joblist.keys()),
                attributes=["MONITOR_INFO"] * len(joblist),
                values=list(map(json.dumps, list(joblist.values()))),
            )
        except QueryError as qerr:
            logSupport.log.error("Failed to add monitoring info to the glidein job classads: %s" % qerr)


def save_stats(stats, fname):
    """Serialize and save aggregated statistics so that each component (Factory and Entries)
    can retrieve and use them for logging and advertising.

    Args:
        stats (dict): Aggregated Factory statistics dictionary. stats is a dictionary pickled in binary format
            stats['LogSummary'] - log summary aggregated info
        fname (str): Name of the file to store the serialized data.
    """
    util.file_pickle_dump(
        fname, stats, mask_exceptions=(logSupport.log.exception, "Saving of aggregated statistics failed: ")
    )


# Added by C.W. Murphy to make descript.xml
def write_descript(glideinDescript, frontendDescript, monitor_dir):
    """Write the descript.xml file to the specified monitoring directory.

    Args:
        glideinDescript (glideFactoryConfig.GlideinDescript): Factory config's Glidein description object.
        frontendDescript (glideFactoryConfig.FrontendDescript): Factory config's Frontend description object.
        monitor_dir (str): Path to the monitoring directory.
    """

    glidein_data = copy.deepcopy(glideinDescript.data)
    frontend_data = copy.deepcopy(frontendDescript.data)
    entry_data = {}
    for entry in glidein_data["Entries"].split(","):
        entry_data[entry] = {}

        entryDescript = glideFactoryConfig.JobDescript(entry)
        entry_data[entry]["descript"] = entryDescript.data

        entryAttributes = glideFactoryConfig.JobAttributes(entry)
        entry_data[entry]["attributes"] = entryAttributes.data

        entryParams = glideFactoryConfig.JobParams(entry)
        entry_data[entry]["params"] = entryParams.data

    descript2XML = glideFactoryMonitoring.Descript2XML()
    xml_str = (
        descript2XML.glideinDescript(glidein_data)
        + descript2XML.frontendDescript(frontend_data)
        + descript2XML.entryDescript(entry_data)
    )

    try:
        descript2XML.writeFile(monitor_dir, xml_str)
    except OSError:
        logSupport.log.exception("Unable to write the descript.xml file: ")


############################################################


def generate_log_tokens(startup_dir, glidein_descript):
    """Generate the JSON Web Tokens used to authenticate with the remote HTTP log server.
    Note: tokens were generated for disabled entries too, not now

    Args:
        startup_dir (str|Path): Path to the glideinsubmit directory
        glidein_descript (glideFactoryConfig.GlideinDescript): Factory config's Glidein description object

    Returns:
        None

    Raises:
        IOError: If it can't open/read/write a file (key/token)
    """

    logSupport.log.info("Generating JSON Web Tokens for authentication with log server")

    # Get a list of all entries, enabled and disabled
    # TODO: there are more reliable ways to do so, i.e. reading the xml config
    # entries = [ed[len("entry_") :] for ed in glob.glob("entry_*") if os.path.isdir(ed)]
    # OK to generate tokens only for enabled entries
    entries = glidein_descript.data["Entries"].split(",")

    # Retrieve the factory secret key (manually delivered) for token generation
    credentials_dir = os.path.realpath(os.path.join(startup_dir, "..", "server-credentials"))
    jwt_key = os.path.join(credentials_dir, "jwt_secret.key")
    if not os.path.exists(jwt_key) or os.path.getsize(jwt_key) == 0:
        # Create a secret and log if it doesn't exist, otherwise needs a manual undocumented step to start factory
        # For HS256 JWT (HMAC 256) a 32 bytes string is needed. A PEM file like the one from RSAKey() would cause
        # jwt.exceptions.InvalidKeyError: The specified key is an asymmetric key or x509 certificate and
        # should not be used as an HMAC secret.
        # TODO: consider base64 encoding before saving sec_key (server code must be changed as well)
        # TODO: add support for multiple secrets from different servers (RSA asymmetric or HMAC symmetric)
        #       or should they provide (and refresh) tokens?
        logSupport.log.info(f"creating {jwt_key} - manually install this key for authenticating to external web sites")
        log_token_key = secrets.token_bytes(32)
        # The file system is not a safe place to store secrets, but this key is used to control access to the logserver
        # which reside on the file system. So someone with access to this key could access the logserver as well
        with open(jwt_key, "wb") as file:
            file.write(log_token_key)
        os.chmod(jwt_key, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        # TODO: chown gfactory:apache AND chmod u:rw,g:r

    try:
        with open(jwt_key, "rb") as keyfile:
            secret = keyfile.read()
    except OSError:
        logSupport.log.exception(f"Cannot find the key for JWT generation (must be manually deposited in {jwt_key}).")
        raise

    factory_name = glidein_descript.data["FactoryName"]

    # Issue a token for each entry-recipient pair
    for entry in entries:
        # Get the list of recipients
        if "GLIDEIN_LOG_RECIPIENTS_FACTORY" in glideFactoryConfig.JobParams(entry).data:
            log_recipients = glideFactoryConfig.JobParams(entry).data["GLIDEIN_LOG_RECIPIENTS_FACTORY"].split()
        else:
            log_recipients = []

        curtime = int(time.time())

        # Directory where to put tokens.tgz and url_dirs.desc
        entry_dir = os.path.join(credentials_dir, "entry_" + entry)
        # Directory where tokens are initially generated, before flushing them to tokens.tgz
        tokens_dir = os.path.join(entry_dir, "tokens")

        # Create the entry + tokens directories if they do not already exist
        if not os.path.exists(tokens_dir):
            try:
                os.makedirs(tokens_dir)
            except OSError as oe:
                logSupport.log.exception(
                    f"Unable to create JWT entry dir ({os.path.join(tokens_dir, entry)}): {oe.strerror}"
                )
                raise

        # Create the url_dirs.desc file
        open(os.path.join(entry_dir, "url_dirs.desc"), "w").close()

        for recipient_url in log_recipients:
            # Obtain a legal filename from the url, escaping "/" and other tricky symbols
            recipient_safe_url = urllib.parse.quote(recipient_url, "")

            # Generate the monitoring token
            # TODO: in the future must include Frontend tokens as well
            factory_token = "default.jwt"
            token_name = factory_token
            if not os.path.exists(os.path.join(tokens_dir, recipient_safe_url)):
                try:
                    os.makedirs(os.path.join(tokens_dir, recipient_safe_url))
                except OSError as oe:
                    logSupport.log.exception(
                        "Unable to create JWT recipient dir (%s): %s"
                        % (os.path.join(tokens_dir, recipient_safe_url), oe.strerror)
                    )
                    raise
            token_filepath = os.path.join(tokens_dir, recipient_safe_url, token_name)
            # Payload fields:
            # iss->issuer,      sub->subject,       aud->audience
            # iat->issued_at,   exp->expiration,    nbf->not_before
            token_payload = {
                "iss": factory_name,
                "sub": entry,
                "aud": recipient_safe_url,
                "iat": curtime,
                "exp": curtime + 604800,
                "nbf": curtime - 300,  # To compensate for possible clock skews
            }
            token = jwt.encode(token_payload, secret, algorithm="HS256")
            # TODO: PyJWT bug workaround. Remove this conversion once affected PyJWT is no more around
            #  PyJWT in EL7 (PyJWT <2.0.0) has a bug, jwt.encode() is declaring str as return type, but it is returning bytes
            #  https://github.com/jpadilla/pyjwt/issues/391
            if isinstance(token, bytes):
                token = token.decode("UTF-8")
            try:
                # Write the factory token
                with open(token_filepath, "w") as tkfile:
                    tkfile.write(token)
                # Write to url_dirs.desc
                with open(os.path.join(entry_dir, "url_dirs.desc"), "a") as url_dirs_desc:
                    url_dirs_desc.write(f"{recipient_url} {recipient_safe_url}\n")
            except OSError:
                logSupport.log.exception("Unable to create JWT file: ")
                raise

        # Create and write tokens.tgz
        try:
            tokens_tgz = tarfile.open(os.path.join(entry_dir, "tokens.tgz"), "w:gz", dereference=True)
            tokens_tgz.add(tokens_dir, arcname=os.path.basename(tokens_dir))
        except tarfile.TarError as terr:
            logSupport.log.exception("TarError: %s" % str(terr))
            raise
        tokens_tgz.close()


###########################################################


def entry_grouper(size, entries):
    """
    Group the entries into n smaller groups
    KNOWN ISSUE: Needs improvement to do better grouping in certain cases
    TODO: Migrate to itertools when only supporting python 2.6 and higher

    @type size: long
    @param size: Size of each subgroup
    @type entries: list
    @param size: List of entries

    @rtype: list
    @return: List of grouped entries. Each group is a list
    """

    list = []

    if size == 0:
        return list

    if len(entries) <= size:
        list.insert(0, entries)
    else:
        for group in range(len(entries) // size):
            list.insert(group, entries[group * size : (group + 1) * size])

        if size * len(list) < len(entries):
            list.insert(group + 1, entries[(group + 1) * size :])

    return list


############################################################
def is_crashing_often(startup_time, restart_interval, restart_attempts):
    """
    Check if the entry is crashing/dying often

    @type startup_time: long
    @param startup_time: Startup time of the entry process in second
    @type restart_interval: long
    @param restart_interval: Allowed restart interval in second
    @type restart_attempts: long
    @param restart_attempts: Number of allowed restart attempts in the interval

    @rtype: bool
    @return: True if entry process is crashing/dying often
    """

    crashing_often = True

    if len(startup_time) < restart_attempts:
        # We haven't exhausted restart attempts
        crashing_often = False
    else:
        # Check if the service has been restarted often
        if restart_attempts == 1:
            crashing_often = True
        elif (time.time() - startup_time[0]) >= restart_interval:
            crashing_often = False
        else:
            crashing_often = True

    return crashing_often


def is_file_old(filename, allowed_time):
    """
    Check if the file is older than given time

    @type filename: String
    @param filename: Full path to the file
    @type allowed_time: long
    @param allowed_time: Time is second

    @rtype: bool
    @return: True if file is older than the given time, else False
    """
    if time.time() > (os.path.getmtime(filename) + allowed_time):
        return True
    return False


############################################################
def clean_exit(children):
    count = 100000000  # set it high, so it is triggered at the first iteration
    sleep_time = 0.1  # start with very little sleep
    while len(list(children.keys())) > 0:
        count += 1
        if count > 4:
            # Send a term signal to the children
            # May need to do it several times, in case there are in the
            # middle of something
            count = 0
            logSupport.log.info("Killing EntryGroups %s" % list(children.keys()))
            for group in children:
                try:
                    os.kill(children[group].pid, signal.SIGTERM)
                except OSError:
                    logSupport.log.warning("EntryGroup %s already dead" % group)
                    del children[group]  # already dead

        logSupport.log.info("Sleep")
        time.sleep(sleep_time)
        # exponentially increase, up to 5 secs
        sleep_time = sleep_time * 2
        if sleep_time > 5:
            sleep_time = 5

        logSupport.log.info("Checking dying EntryGroups %s" % list(children.keys()))
        dead_entries = []
        for group in children:
            child = children[group]

            # empty stdout and stderr
            try:
                tempOut = child.stdout.read()
                if len(tempOut) != 0:
                    logSupport.log.warning(f"EntryGroup {group} STDOUT: {tempOut}")
            except OSError:
                pass  # ignore
            try:
                tempErr = child.stderr.read()
                if len(tempErr) != 0:
                    logSupport.log.warning(f"EntryGroup {group} STDERR: {tempErr}")
            except OSError:
                pass  # ignore

            # look for exited child
            if child.poll():
                # the child exited
                dead_entries.append(group)
                del children[group]
                tempOut = child.stdout.readlines()
                tempErr = child.stderr.readlines()
        if len(dead_entries) > 0:
            logSupport.log.info("These EntryGroups died: %s" % dead_entries)

    logSupport.log.info("All EntryGroups dead")


############################################################
def spawn(
    sleep_time,
    advertize_rate,
    startup_dir,
    glideinDescript,
    frontendDescript,
    entries,
    restart_attempts,
    restart_interval,
):
    """
    Spawn and track entry processes, restarting them as needed. Advertise glidefactoryglobal ClassAds every iteration.

    Args:
        sleep_time (int): Delay between iterations in seconds.
        advertize_rate (int): Rate at which entries advertise their ClassAds.
        startup_dir (str): Path to the glideinsubmit directory.
        glideinDescript (glideFactoryConfig.GlideinDescript): Factory config's Glidein description object.
        frontendDescript (glideFactoryConfig.FrontendDescript): Factory config's Frontend description object.
        entries (list): Sorted list of entry names.
        restart_interval (int): Allowed restart interval in seconds.
        restart_attempts (int): Number of allowed restart attempts within the interval.
    """

    children = {}

    # Number of glideFactoryEntry processes to spawn and directly relates to
    # number of concurrent condor_status processes
    #
    # NOTE: If number of entries gets too big, we may exceed the shell args
    #       limit. If that becomes an issue, move the logic to identify the
    #       entries to serve to the group itself.
    #
    # Each process will handle multiple entries split as follows
    #   - Sort the entries alphabetically. Already done
    #   - Divide the list into equal chunks as possible
    #   - Last chunk may get fewer entries
    entry_process_count = 1

    starttime = time.time()
    oldkey_gracetime = int(glideinDescript.data["OldPubKeyGraceTime"])
    oldkey_eoltime = starttime + oldkey_gracetime

    children_uptime = {}

    factory_downtimes = glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data["DowntimesFile"])

    logSupport.log.info("Available Entries: %s" % entries)

    group_size = int(math.ceil(float(len(entries)) / entry_process_count))
    entry_groups = entry_grouper(group_size, entries)

    def _set_rlimit(soft_l=None, hard_l=None):
        """Set new hard and soft open file limits

        If setting limits fails or no input parameters use inherited limits from parent process
        NOTE1: it is possible to raise limits up to [hard_l,hard_l] but once lowered they cannot be raised
        NOTE2: it may be better just to omit calling this function at all from subprocess -
               in which case it inherits limits from the parent process

        Args:
            soft_l (int): soft limit
            hard_l (int): hard limit

        Raises:
            Exception: if the limit setting fails
        """

        lim = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft_l is not None or hard_l is not None:
            if not hard_l:
                hard_l = soft_l
            if not soft_l:
                soft_l = hard_l
            try:
                new_lim = [soft_l, hard_l]
                resource.setrlimit(resource.RLIMIT_NOFILE, new_lim)
            except Exception:
                resource.setrlimit(resource.RLIMIT_NOFILE, lim)

    try:
        for group in range(len(entry_groups)):
            entry_names = ":".join(entry_groups[group])
            logSupport.log.info(f"Starting EntryGroup {group}: {entry_groups[group]}")

            # Converted to using the subprocess module
            command_list = [
                sys.executable,
                glideFactoryEntryGroup.__file__,
                str(os.getpid()),
                str(sleep_time),
                str(advertize_rate),
                startup_dir,
                entry_names,
                str(group),
            ]
            children[group] = subprocess.Popen(
                command_list,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                preexec_fn=_set_rlimit,
            )

            # Get the startup time. Used to check if the entry is crashing
            # periodically and needs to be restarted.
            children_uptime[group] = list()
            children_uptime[group].insert(0, time.time())

        logSupport.log.info("EntryGroup startup times: %s" % children_uptime)

        generate_log_tokens(startup_dir, glideinDescript)

        for group in children:
            # set it in non-blocking mode
            # since we will run for a long time, we do not want to block
            for fd in (children[group].stdout.fileno(), children[group].stderr.fileno()):
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        # If RemoveOldCredFreq <= 0, do not do credential cleanup.
        curr_time = 0  # To ensure curr_time is always initialized
        if int(glideinDescript.data["RemoveOldCredFreq"]) > 0:
            # Convert credential removal frequency from hours to seconds
            remove_old_cred_freq = int(glideinDescript.data["RemoveOldCredFreq"]) * 60 * 60
            curr_time = time.time()
            update_time = curr_time + remove_old_cred_freq

            # Convert credential removal age from days to seconds
            remove_old_cred_age = int(glideinDescript.data["RemoveOldCredAge"]) * 60 * 60 * 24

            # Create cleaners for old credential files
            logSupport.log.info("Adding cleaners for old credentials")
            cred_base_dir = glideinDescript.data["ClientProxiesBaseDir"]
            for username in frontendDescript.get_all_usernames():
                cred_user_instance_dirname = os.path.join(
                    cred_base_dir, "user_%s" % username, "glidein_%s" % glideinDescript.data["GlideinName"]
                )
                cred_cleaner = cleanupSupport.DirCleanupCredentials(
                    cred_user_instance_dirname, "(credential_*)", remove_old_cred_age
                )
                cleanupSupport.cred_cleaners.add_cleaner(cred_cleaner)

        iteration_basetime = time.time()
        while True:
            # retrieves WebMonitoringURL from glideclient classAd
            iteration_timecheck = time.time()
            iteration_timediff = iteration_timecheck - iteration_basetime

            if iteration_timediff >= 3600:  # every hour
                iteration_basetime = time.time()  # reset the start time
                fronmonpath = os.path.join(startup_dir, "monitor", "frontendmonitorlink.txt")
                fronmonconstraint = '(MyType=="glideclient")'
                fronmonformat_list = [("WebMonitoringURL", "s"), ("FrontendName", "s")]
                fronmonstatus = condorMonitor.CondorStatus(subsystem_name="any")
                fronmondata = fronmonstatus.fetch(constraint=fronmonconstraint, format_list=fronmonformat_list)
                fronmon_list_names = list(fronmondata.keys())
                if fronmon_list_names is not None:
                    urlset = set()
                    if os.path.exists(fronmonpath):
                        os.remove(fronmonpath)
                    for frontend_entry in fronmon_list_names:
                        fronmonelement = fronmondata[frontend_entry]
                        fronmonurl = fronmonelement["WebMonitoringURL"].encode("utf-8")
                        fronmonfrt = fronmonelement["FrontendName"].encode("utf-8")
                        if (fronmonfrt, fronmonurl) not in urlset:
                            urlset.add((fronmonfrt, fronmonurl))
                            with open(fronmonpath, "w") as fronmonf:
                                fronmonf.write(f"{fronmonfrt}, {fronmonurl}")

            # Record the iteration start time
            iteration_stime = time.time()

            # THIS IS FOR SECURITY
            # Make sure you delete the old key when its grace is up.
            # If a compromised key is left around and if attacker can somehow
            # trigger FactoryEntry process crash, we do not want the entry
            # to pick up the old key again when factory auto restarts it.
            if time.time() > oldkey_eoltime and glideinDescript.data["OldPubKeyObj"] is not None:
                glideinDescript.data["OldPubKeyObj"] = None
                glideinDescript.data["OldPubKeyType"] = None
                try:
                    glideinDescript.remove_old_key()
                    logSupport.log.info(
                        "Removed the old public key after its grace time of %s seconds" % oldkey_gracetime
                    )
                except Exception:
                    # Do not crash if delete fails. Just log it.
                    logSupport.log.warning("Failed to remove the old public key after its grace time")

            # Only removing credentials in the v3+ protocol
            # Affects Corral Frontend which only supports the v3+ protocol.
            # IF freq < zero, do not do cleanup.
            if int(glideinDescript.data["RemoveOldCredFreq"]) > 0 and curr_time >= update_time:
                logSupport.log.info("Checking credentials for cleanup")

                # Query queue for glideins. Don't remove proxies in use.
                try:
                    in_use_creds = glideFactoryLib.getCondorQCredentialList()
                    cleanupSupport.cred_cleaners.cleanup(in_use_creds)
                except Exception:
                    logSupport.log.exception("Unable to cleanup old credentials")

                update_time = curr_time + remove_old_cred_freq

            curr_time = time.time()

            logSupport.log.info("Checking for credentials %s" % entries)

            # Read in the frontend globals classad
            # Do this first so that the credentials are immediately
            # available when the Entries startup
            classads = {}
            try:
                classads = glideFactoryCredentials.get_globals_classads()
            except Exception:
                logSupport.log.error("Error occurred retrieving globals classad -- is Condor running?")

            for classad_key in classads:
                classad = classads[classad_key]
                try:
                    glideFactoryCredentials.process_global(classad, glideinDescript, frontendDescript)
                except Exception:
                    logSupport.log.exception("Error occurred processing the globals classads: ")

            logSupport.log.info("Checking EntryGroups %s" % list(children.keys()))
            for group in list(children):  # making a copy of the keys because the dict is being modified in the loop
                entry_names = ":".join(entry_groups[group])
                child = children[group]

                # empty stdout and stderr
                try:
                    tempOut = child.stdout.read()
                    if tempOut and len(tempOut) != 0:
                        logSupport.log.warning(f"EntryGroup {group} STDOUT: {tempOut}")
                except OSError:
                    pass  # ignore
                try:
                    tempErr = child.stderr.read()
                    if tempErr and len(tempErr) != 0:
                        logSupport.log.warning(f"EntryGroup {group} STDERR: {tempErr}")
                except OSError:
                    pass  # ignore

                # look for exited child
                if child.poll():
                    # the child exited
                    logSupport.log.warning("EntryGroup %s exited. Checking if it should be restarted." % (group))
                    tempOut = child.stdout.readlines()
                    tempErr = child.stderr.readlines()

                    if is_crashing_often(children_uptime[group], restart_interval, restart_attempts):
                        del children[group]
                        raise RuntimeError(
                            "EntryGroup '%s' has been crashing too often, quit the whole factory:\n%s\n%s"
                            % (group, tempOut, tempErr)
                        )
                    else:
                        # Restart the entry setting its restart time
                        logSupport.log.warning("Restarting EntryGroup %s." % (group))
                        del children[group]

                        command_list = [
                            sys.executable,
                            glideFactoryEntryGroup.__file__,
                            str(os.getpid()),
                            str(sleep_time),
                            str(advertize_rate),
                            startup_dir,
                            entry_names,
                            str(group),
                        ]
                        children[group] = subprocess.Popen(
                            command_list,
                            shell=False,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            close_fds=True,
                            preexec_fn=_set_rlimit,
                        )

                        if len(children_uptime[group]) == restart_attempts:
                            children_uptime[group].pop(0)
                        children_uptime[group].append(time.time())
                        for fd in (children[group].stdout.fileno(), children[group].stderr.fileno()):
                            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                        logSupport.log.warning(f"EntryGroup startup/restart times: {children_uptime}")

            # Aggregate Monitoring data periodically
            logSupport.log.info("Aggregate monitoring data")
            stats = aggregate_stats(factory_downtimes.checkDowntime())
            save_stats(stats, os.path.join(startup_dir, glideFactoryConfig.factoryConfig.aggregated_stats_file))

            # Aggregate job data periodically
            if glideinDescript.data.get("AdvertisePilotAccounting", False) in [
                "True",
                "1",
            ]:  # data attributes are strings
                logSupport.log.info("Starting updating job classads")
                update_classads()
                logSupport.log.info("Finishing updating job classads")

            # Advertise the global classad with the factory keys and Factory statistics
            try:
                # KEL TODO need to add factory downtime?
                glideFactoryInterface.advertizeGlobal(
                    glideinDescript.data["FactoryName"],
                    glideinDescript.data["GlideinName"],
                    glideFactoryLib.factoryConfig.supported_signtypes,
                    glideinDescript.data["PubKeyObj"],
                )
            except Exception as e:
                logSupport.log.exception("Error advertising global classads: %s" % e)

            cleanupSupport.cleaners.cleanup()

            iteration_etime = time.time()
            iteration_sleep_time = sleep_time - (iteration_etime - iteration_stime)
            if iteration_sleep_time < 0:
                iteration_sleep_time = 0
            logSupport.log.info("Sleep %s secs" % iteration_sleep_time)
            time.sleep(iteration_sleep_time)

        # end while 1:

    finally:
        # cleanup at exit
        logSupport.log.info("Received signal...exit")
        try:
            try:
                clean_exit(children)
            except Exception:
                # if anything goes wrong, hardkill the rest
                for group in children:
                    logSupport.log.info("Hard killing EntryGroup %s" % group)
                    try:
                        os.kill(children[group].pid, signal.SIGKILL)
                    except OSError:
                        pass  # ignore dead clients
        finally:
            logSupport.log.info("Deadvertize myself")
            try:
                glideFactoryInterface.deadvertizeFactory(
                    glideinDescript.data["FactoryName"], glideinDescript.data["GlideinName"]
                )
            except Exception:
                logSupport.log.exception("Factory deadvertize failed!")
            try:
                glideFactoryInterface.deadvertizeFactoryClientMonitoring(
                    glideinDescript.data["FactoryName"], glideinDescript.data["GlideinName"]
                )
            except Exception:
                logSupport.log.exception("Factory Monitoring deadvertize failed!")
        logSupport.log.info("All EntryGroups should be terminated")


def increase_process_limit(new_limit=10000):
    """Raise RLIMIT_NPROC to new_limit"""
    (soft, hard) = resource.getrlimit(resource.RLIMIT_NPROC)
    if soft < new_limit:
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (new_limit, hard))
            logSupport.log.info("Raised RLIMIT_NPROC from %d to %d" % (soft, new_limit))
        except ValueError:
            logSupport.log.info("Warning: could not raise RLIMIT_NPROC " "from %d to %d" % (soft, new_limit))
    else:
        logSupport.log.info("RLIMIT_NPROC already %d, not changing to %d" % (soft, new_limit))


############################################################
def main(startup_dir):
    """
    Reads in the configuration file and starts up the factory

    @type startup_dir: String
    @param startup_dir: Path to glideinsubmit directory
    """
    # Force integrity checks on all condor operations
    glideFactoryLib.set_condor_integrity_checks()

    glideFactoryInterface.factoryConfig.lock_dir = os.path.join(startup_dir, "lock")
    glideFactoryConfig.factoryConfig.glidein_descript_file = os.path.join(
        startup_dir, glideFactoryConfig.factoryConfig.glidein_descript_file
    )
    glideinDescript = glideFactoryConfig.GlideinDescript()
    frontendDescript = glideFactoryConfig.FrontendDescript()

    # set factory_collector at a global level, since we do not expect it to change
    glideFactoryInterface.factoryConfig.factory_collector = glideinDescript.data["FactoryCollector"]

    # Setup the glideFactoryLib.factoryConfig so that we can process the
    # globals classads
    glideFactoryLib.factoryConfig.config_whoamI(
        glideinDescript.data["FactoryName"], glideinDescript.data["GlideinName"]
    )
    glideFactoryLib.factoryConfig.config_dirs(
        startup_dir,
        glideinDescript.data["LogDir"],
        glideinDescript.data["ClientLogBaseDir"],
        glideinDescript.data["ClientProxiesBaseDir"],
    )

    # Set the Log directory
    logSupport.log_dir = os.path.join(glideinDescript.data["LogDir"], "factory")

    # Configure factory process logging
    logSupport.log = logSupport.get_logger_with_handlers("factory", logSupport.log_dir, glideinDescript.data)
    logSupport.log.info("Logging initialized")

    if glideinDescript.data["Entries"].strip() in ("", ","):
        # No entries are enabled. There is nothing to do. Just exit here.
        log_msg = "No Entries are enabled. Exiting."

        logSupport.log.error(log_msg)
        sys.exit(1)

    write_descript(glideinDescript, frontendDescript, os.path.join(startup_dir, "monitor/"))

    try:
        os.chdir(startup_dir)
    except Exception:
        logSupport.log.exception("Failed starting Factory. Unable to change to startup_dir: ")
        raise

    try:
        if is_file_old(glideinDescript.default_rsakey_fname, int(glideinDescript.data["OldPubKeyGraceTime"])):
            # First backup and load any existing key
            logSupport.log.info("Backing up and loading old key")
            glideinDescript.backup_and_load_old_key()
            # Create a new key for this run
            logSupport.log.info("Recreating and loading new key")
            glideinDescript.load_pub_key(recreate=True)
        else:
            # Key is recent enough. Just reuse it.
            logSupport.log.info("Key is recent enough, reusing for this run")
            glideinDescript.load_pub_key(recreate=False)
            logSupport.log.info("Loading old key")
            glideinDescript.load_old_rsa_key()
    except RSAError as e:
        logSupport.log.exception("Failed starting Factory. Exception occurred loading factory keys: ")
        key_fname = getattr(e, "key_fname", None)
        cwd = getattr(e, "cwd", None)
        if key_fname and cwd:
            logSupport.log.error("Failed to load RSA key %s with current working directory %s", key_fname, cwd)
            logSupport.log.error(
                "If you think the rsa key might be corrupted, try to remove it, and then reconfigure the factory to recreate it"
            )
        raise
    except OSError as ioe:
        logSupport.log.exception("Failed starting Factory. Exception occurred loading factory keys: ")
        if ioe.filename == "rsa.key" and ioe.errno == 2:
            logSupport.log.error("Missing rsa.key file. Please, reconfigure the factory to recreate it")
        raise
    except Exception:
        logSupport.log.exception("Failed starting Factory. Exception occurred loading factory keys: ")
        raise

    glideFactoryMonitorAggregator.glideFactoryMonitoring.monitoringConfig.my_name = "{}@{}".format(
        glideinDescript.data["GlideinName"],
        glideinDescript.data["FactoryName"],
    )

    glideFactoryInterface.factoryConfig.advertise_use_tcp = glideinDescript.data["AdvertiseWithTCP"] in ("True", "1")
    glideFactoryInterface.factoryConfig.advertise_use_multi = glideinDescript.data["AdvertiseWithMultiple"] in (
        "True",
        "1",
    )
    sleep_time = int(glideinDescript.data["LoopDelay"])
    advertize_rate = int(glideinDescript.data["AdvertiseDelay"])
    restart_attempts = int(glideinDescript.data["RestartAttempts"])
    restart_interval = int(glideinDescript.data["RestartInterval"])

    try:
        glideFactoryInterface.factoryConfig.glideinwms_version = glideinWMSVersion.GlideinWMSDistro(
            "checksum.factory"
        ).version()
    except Exception:
        logSupport.log.exception(
            "Non critical Factory error. Exception occurred while trying to retrieve the glideinwms version: "
        )

    entries = sorted(glideinDescript.data["Entries"].split(","))

    glideFactoryMonitorAggregator.monitorAggregatorConfig.config_factory(
        os.path.join(startup_dir, "monitor"), entries, log=logSupport.log
    )

    # create lock file
    pid_obj = glideFactoryPidLib.FactoryPidSupport(startup_dir)

    increase_process_limit()

    # start
    try:
        pid_obj.register()
    except glideFactoryPidLib.pidSupport.AlreadyRunning as err:
        pid_obj.load_registered()
        logSupport.log.exception(
            "Failed starting Factory. Instance with pid %s is already running. Exception during pid registration: %s"
            % (pid_obj.mypid, err)
        )
        raise
    # TODO: use a single try.. except.. finally when moving to Python 3.8 or above (dropping 3.6)
    try:
        try:
            # Spawn the EntryGroup processes handling the work
            spawn(
                sleep_time,
                advertize_rate,
                startup_dir,
                glideinDescript,
                frontendDescript,
                entries,
                restart_attempts,
                restart_interval,
            )
        # No need for special handling of KeyboardInterrupt
        # It is not in Exception so it will remain un-handled
        # except KeyboardInterrupt as e:
        #   raise e  # raise e is re-raising a different exceptoin from here? Use raise instead?
        except HUPException:
            # inside spawn(), outermost try will catch HUPException,
            # then the code within the finally clouse of spawn() will run
            # which will terminate glideFactoryEntryGroup children processes
            # and then the following 3 lines will be executed.
            logSupport.log.info("Received SIGHUP, reload config uid = %d" % os.getuid())
            # must empty the lock file so that when the thread returns from reconfig_glidein and
            # begins from the beginning, it will not error out which will happen
            # if the lock file is not empty
            pid_obj.relinquish()
            os.execv(
                os.path.join(FACTORY_DIR, "../creation/reconfig_glidein"),
                [
                    "reconfig_glidein",
                    "-update_scripts",
                    "no",
                    "-sighupreload",
                    "-xml",
                    "/etc/gwms-factory/glideinWMS.xml",
                ],
            )
            # TODO: verify. This is invoking reconfig but how is the Factory/EntryGroups re-started?
            #    Should there be an infinite loop around spawn?
        except Exception as e:
            # Exception excludes SystemExit, KeyboardInterrupt, GeneratorExit
            # Log the exception and exit
            logSupport.log.exception("Exception occurred spawning the factory: %s" % e)
    finally:
        pid_obj.relinquish()


############################################################
#
# S T A R T U P
#
############################################################
class HUPException(Exception):
    """Used to catch SIGHUP and trigger a reconfig"""

    pass


def termsignal(signr, frame):
    """Signal handler. Raise KeyboardInterrupt when receiving SIGTERN or SIGQUIT"""
    raise KeyboardInterrupt("Received signal %s" % signr)


def hupsignal(signr, frame):
    """Signal handler. Raise HUPException when receiving SIGHUP. Used to trigger a reconfig and restart."""
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    raise HUPException("Received signal %s" % signr)


if __name__ == "__main__":
    if os.getsid(os.getpid()) != os.getpgrp():
        os.setpgid(0, 0)
    signal.signal(signal.SIGTERM, termsignal)
    signal.signal(signal.SIGQUIT, termsignal)
    signal.signal(signal.SIGHUP, hupsignal)

    try:
        main(sys.argv[1])
    except KeyboardInterrupt as e:
        logSupport.log.info("Terminating: %s" % e)
