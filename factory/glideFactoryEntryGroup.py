#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This is the glideinFactoryEntryGroup. Common Tasks like querying collector
   and advertizing the work done by group are done here

Arguments:
   $1 = parent_pid (int): The pid for the Factory daemon
   $2 = sleep_time (int): The number of seconds to sleep between iterations
   $3 = advertize_rate (int): The rate at which advertising should occur (every $3 loops)
   $4 = startup_dir (str|Path): The "home" directory for the entry.
   $5 = entry_names (str): Colon separated list with the names of the entries this process should work on
   $6 = group_id (str): Group id, normally a number (with the "group_" prefix it forms the group name),
             It can change between Factory reconfigurations
"""

import os
import os.path
import pickle
import sys
import time

from glideinwms.factory import glideFactoryConfig as gfc
from glideinwms.factory import glideFactoryDowntimeLib, glideFactoryEntry
from glideinwms.factory import glideFactoryInterface as gfi
from glideinwms.factory import glideFactoryLib as gfl
from glideinwms.factory import glideFactoryPidLib
from glideinwms.lib import classadSupport, cleanupSupport, logSupport
from glideinwms.lib.fork import fetch_fork_result_list, ForkManager, print_child_processes
from glideinwms.lib.pidSupport import register_sighandler, unregister_sighandler

############################################################
# Memory foot print of a entry process when forked for check_and_perform_work
# Set a conservative limit of 500 MB (based on USCD 2.6 factory Pss of 115 MB)
#   plus a safety factor of 2

ENTRY_MEM_REQ_BYTES = 500000000 * 2
############################################################


class EntryGroup:
    def __init__(self):
        pass


############################################################
def check_parent(parent_pid, glideinDescript, my_entries):
    """
    Check to make sure that we aren't an orphaned process.  If Factory
    daemon has died, then clean up after ourselves and kill ourselves off.

    @type parent_pid: int
    @param parent_pid: pid for the Factory daemon process

    @type glideinDescript: glideFactoryConfig.GlideinDescript
    @param glideinDescript: Object that encapsulates glidein.descript in the Factory root directory

    @type my_entries: dict
    @param my_entries: Dictionary of entry objects keyed on entry name

    @raise KeyboardInterrupt: Raised when the Factory daemon cannot be found
    """

    if os.path.exists("/proc/%s" % parent_pid):
        return  # parent still exists, we are fine

    logSupport.log.info("Parent died, exit.")

    # there is nobody to clean up after ourselves... do it here
    logSupport.log.info("Deadvertize myself")

    for entry in list(my_entries.values()):
        # Deadvertise glidefactory classad
        try:
            gfi.deadvertizeGlidein(glideinDescript.data["FactoryName"], glideinDescript.data["GlideinName"], entry.name)
        except Exception:
            logSupport.log.warning("Failed to deadvertize entry '%s'" % entry.name)

        # Deadvertise glidefactoryclient classad
        try:
            gfi.deadvertizeAllGlideinClientMonitoring(
                glideinDescript.data["FactoryName"], glideinDescript.data["GlideinName"], entry.name
            )
        except Exception:
            logSupport.log.warning("Failed to deadvertize monitoring for entry '%s'" % entry.name)

    raise KeyboardInterrupt("Parent died. Quitting.")


############################################################
def find_work(factory_in_downtime, glideinDescript, frontendDescript, group_name, my_entries):
    """
    Find work for all the entries in the group

    @type factory_in_downtime:  boolean
    @param factory_in_downtime:  True if factory is in downtime

    @type glideinDescript: dict
    @param glideinDescript: Factory glidein config values

    @type frontendDescript: dict
    @param frontendDescript: Security mappings for frontend identities, security classes, and usernames

    @type group_name: string
    @param group_name: Name of the group

    @type my_entries: dict
    @param my_entries: Dictionary of entry objects keyed on entry name

    @return: Dictionary of work to do keyed on entry name
    @rtype: dict
    """

    pub_key_obj = glideinDescript.data["PubKeyObj"]
    old_pub_key_obj = glideinDescript.data["OldPubKeyObj"]

    logSupport.log.info("Finding work")
    work = gfi.findGroupWork(
        gfl.factoryConfig.factory_name,
        gfl.factoryConfig.glidein_name,
        list(my_entries.keys()),
        gfl.factoryConfig.supported_signtypes,
        pub_key_obj,
    )
    log_work_info(work, key="existing")

    # If old key is valid, find the work using old key as well and append it
    # to existing work dictionary
    if old_pub_key_obj is not None:
        work_oldkey = {}
        # still using the old key in this cycle
        logSupport.log.info("Old factory key is still valid. Trying to find work using old factory key.")
        work_oldkey = gfi.findGroupWork(
            gfl.factoryConfig.factory_name,
            gfl.factoryConfig.glidein_name,
            list(my_entries.keys()),
            gfl.factoryConfig.supported_signtypes,
            old_pub_key_obj,
        )
        log_work_info(work, key="old")

        # Merge the work_oldkey with work
        for w in work_oldkey:
            if w in work:
                # This should not happen but still as a safegaurd warn
                logSupport.log.warning(
                    "Work task for %s exists using existing key and old key. Ignoring the work from old key." % w
                )
                continue
            work[w] = work_oldkey[w]

    # Append empty work item for entries that do not have work
    # This is required to trigger glidein sanitization further in the code
    for ent in my_entries:
        if ent not in work:
            work[ent] = {}

    return work


def log_work_info(work, key=""):
    if key.strip() != "":
        logSupport.log.info(f"Work tasks grouped by entries using {key} factory key")
    else:
        logSupport.log.info("Work tasks grouped by entries")

    for entry in work:
        # Only log if there is work to do
        if len(work[entry]) > 0:
            logSupport.log.info(f"Entry: {entry} (Tasks: {len(work[entry])})")


def get_work_count(work):
    """
    Get total work to do i.e. sum of work to do for every entry

    @type work: dict
    @param work: Dictionary of work to do keyed on entry name

    @rtype: int
    @return: Total work to do.
    """

    count = 0
    for entry in work:
        count += len(work[entry])
    return count


def forked_check_and_perform_work(factory_in_downtime, entry, work):
    """
    Do the work assigned to an entry (glidein requests)
    @param factory_in_downtime: flag, True if the Factory is in downtime
    @param entry: entry object (glideFactoryEntry.Entry)
    @param work: work requests for the entry
    @return: dictionary with entry state + work_done
    """
    work_done = glideFactoryEntry.check_and_perform_work(factory_in_downtime, entry, work)

    # entry object now has updated info in the child process
    # This info is required for monitoring and advertising
    # Compile the return info from the updated entry object
    # Can't dumps the entry object directly, so need to extract
    # the info required.
    return_dict = compile_pickle_data(entry, work_done)
    return return_dict


def forked_update_entries_stats(factory_in_downtime, entries_list):
    """Update statistics for entries that have no work to do

    :param factory_in_downtime:
    :param entries_list:
    :return:
    """
    entries_updated = glideFactoryEntry.update_entries_stats(factory_in_downtime, entries_list)

    # entry objects now have updated info in the child process
    # This info is required for monitoring and advertising
    # Compile the return info from the updated entry object
    # Can't dumps the entry object directly, so need to extract
    # the info required.
    # Making the entries pickle-friendly

    return_dict = {"entries": [(e.name, e.getState()) for e in entries_updated]}
    # should set also e['work_done'] = 0 ?
    return return_dict


##############################################
# Functions managing the Entries life-cycle


def find_and_perform_work(do_advertize, factory_in_downtime, glideinDescript, frontendDescript, group_name, my_entries):
    """For all entries in this group, find work requests from the WMS collector,
    validate credentials, and requests Glideins.
    If an entry is in downtime, requested Glideins is zero.

    Args:
        do_advertize (bool): Advertise (publish the gfc ClassAd) event if no work is performed
        factory_in_downtime (bool): True if factory is in downtime
        glideinDescript (dict): Factory glidein config values
        frontendDescript (dict): Security mappings for frontend identities, security classes, and usernames
        group_name (str): Name of the group
        my_entries (dict): Dictionary of entry objects (glideFactoryEntry.Entry) keyed on entry name

    Returns:
        dict: Dictionary of work to do keyed using entry name
    """
    # Work done by group keyed by entry name. This will be returned back
    groupwork_done = {}

    # Step 1:
    # Find work to perform. Work is a dict work[entry_name][frontend]
    # We may or may not be able to perform all the work but that will be
    # checked later per entry
    # work includes all entries, empty value for entries w/ no work to do
    # to allow cleanup, ... (remove held glideins, ...)

    work = find_work(factory_in_downtime, glideinDescript, frontendDescript, group_name, my_entries)

    # Request from a Frontend group to an entry
    work_count = get_work_count(work)
    if work_count == 0:
        logSupport.log.info("No work found")
        if do_advertize:
            logSupport.log.info("Continuing to update monitoring info")
        else:
            return groupwork_done

    logSupport.log.info("Found %s total tasks to work on" % work_count)

    # Max number of children to fork at a time
    # Each child currently takes ~50 MB
    # Leaving 3GB for system, max number of children to fork is
    # (Memory - 3000)/50 = 100 (RAM: 8GB) & 250 (RAM: 16GB)
    parallel_workers = 0
    try:
        parallel_workers = int(glideinDescript.data["EntryParallelWorkers"])
    except KeyError:
        logSupport.log.debug(
            "EntryParallelWorkers not set -- factory probably needs a reconfig; setting to 0 for dynamic limits."
        )

    post_work_info = {}
    work_info_read_err = False

    if parallel_workers <= 0:
        logSupport.log.debug("Setting parallel_workers limit dynamically based on the available free memory")
        free_mem = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        parallel_workers = int(free_mem / float(ENTRY_MEM_REQ_BYTES))
        if parallel_workers < 1:
            parallel_workers = 1

    logSupport.log.debug("Setting parallel_workers limit of %s" % parallel_workers)

    forkm_obj = ForkManager()
    # Only fork of child processes for entries that have corresponding
    # work to do, ie glideclient classads.
    # TODO: #22163, change in 3.5 coordinate w/ find_work():
    #  change so that only the entries w/ work to do are returned in 'work'
    #  currently work contains all entries
    #  cleanup is still done correctly, handled also in the entries w/o work function (forked as single function)
    entries_without_work = []
    for ent in my_entries:
        if work.get(ent):
            entry = my_entries[ent]  # ent is the entry.name
            forkm_obj.add_fork(ent, forked_check_and_perform_work, factory_in_downtime, entry, work[ent])
        else:
            entries_without_work.append(ent)
    # Evaluate stats for entries without work only if these will be advertised
    # TODO: #22163, check if this is causing too much load
    # Since glideins only decrease for entries not receiving requests, a more efficient way
    # could be to advertise entries that had non 0 # of glideins at the previous round
    if do_advertize and len(entries_without_work) > 0:
        forkm_obj.add_fork(
            "GWMS_ENTRIES_WITHOUT_WORK",
            forked_update_entries_stats,
            factory_in_downtime,
            [my_entries[i] for i in entries_without_work],
        )
    t_begin = time.time()
    try:
        post_work_info = forkm_obj.bounded_fork_and_collect(parallel_workers)
        t_end = time.time() - t_begin
    except RuntimeError:
        # Expect all errors logged already
        work_info_read_err = True
        t_end = time.time() - t_begin

    # This caused  "ValueError: I/O operation on closed file." on a seek in logSupport.shouldRollover()
    # Children use fork.fork_in_bg which has logSupport.disable_rotate = True
    # Furthermore, all children should be completed, there should be no competition for log file rotation
    # TODO: investigate logs with process tree if this happens again
    try:
        logSupport.roll_all_logs()
    except ValueError as e:
        proc_id = os.getpid()
        logSupport.log.debug(f"Failed log rotation in process {proc_id}, process tree:\n{print_child_processes()}")
        logSupport.log.exception(f"Failed log rotation likely due to concurrent attempts: {e}")
    # Gather results from the forked children
    logSupport.log.info(
        "All children forked for glideFactoryEntry.check_and_perform_work terminated - took %s seconds. Loading post work state for the entry."
        % t_end
    )
    logSupport.log.debug(
        "All children forked for glideFactoryEntry.check_and_perform_work terminated - took %s seconds. Loading post work state for the entry."
        % t_end
    )

    for entry in my_entries:
        # Update the entry object from the post_work_info
        if (entry in post_work_info) and (len(post_work_info[entry]) > 0):
            groupwork_done[entry] = {"work_done": post_work_info[entry]["work_done"]}
            (my_entries[entry]).setState(post_work_info[entry])
        else:
            logSupport.log.debug("No work found for entry %s from any frontends" % entry)

    if (
        "GWMS_ENTRIES_WITHOUT_WORK" in post_work_info
        and len(post_work_info["GWMS_ENTRIES_WITHOUT_WORK"]["entries"]) > 0
    ):
        for entry, entry_state in post_work_info["GWMS_ENTRIES_WITHOUT_WORK"]["entries"]:
            (my_entries[entry]).setState(entry_state)

    if work_info_read_err:
        logSupport.log.debug(
            "Unable to process response from one or more children for check_and_perform_work. One or more forked processes may have failed and may not have client_stats updated"
        )
        logSupport.log.warning(
            "Unable to process response from one or more children for check_and_perform_work. One or more forked processes may have failed and may not have client_stats updated"
        )

    return groupwork_done


def iterate_one(do_advertize, factory_in_downtime, glideinDescript, frontendDescript, group_name, my_entries):
    """One iteration of the entry group

    Args:
        do_advertize (bool): True if glidefactory classads should be advertised
        factory_in_downtime (bool): True if factory is in downtime
        glideinDescript (dict): Factory glidein config values
        frontendDescript (dict): Security mappings for frontend identities, security classes, and usernames
        group_name (str): Name of the group
        my_entries (dict): Dictionary of entry objects (glideFactoryEntry.Entry) keyed on entry name

    Returns:
        int: Units of work performed (0 if no Glidein was submitted)
    """
    groupwork_done = {}
    done_something = 0

    for entry in list(my_entries.values()):
        entry.initIteration(factory_in_downtime)

    try:
        groupwork_done = find_and_perform_work(
            do_advertize, factory_in_downtime, glideinDescript, frontendDescript, group_name, my_entries
        )
    except Exception:
        logSupport.log.warning("Error occurred while trying to find and do work.")
        logSupport.log.exception("Exception: ")

    logSupport.log.debug("Group Work done: %s" % groupwork_done)

    # Classad files to use
    gf_filename = classadSupport.generate_classad_filename(prefix="gfi_adm_gf")
    gfc_filename = classadSupport.generate_classad_filename(prefix="gfi_adm_gfc")

    logSupport.log.info(
        f"Generating glidefactory ({gf_filename}) and glidefactoryclient ({gfc_filename}) classads as needed"
    )

    entries_to_advertise = []
    for entry in list(my_entries.values()):
        # Write classads to file if work was done or if advertise flag is set
        # Actual advertise is done using multi classad advertisement
        entrywork_done = 0
        if (entry.name in groupwork_done) and ("work_done" in groupwork_done[entry.name]):
            entrywork_done = groupwork_done[entry.name]["work_done"]
            done_something += entrywork_done

        if (do_advertize) or (entrywork_done > 0):
            entries_to_advertise.append(entry.name)
            entry.writeClassadsToFile(factory_in_downtime, gf_filename, gfc_filename)

        entry.unsetInDowntime()

    if (do_advertize) or (done_something > 0):
        logSupport.log.debug(
            "Generated glidefactory and glidefactoryclient classads for entries: %s" % ", ".join(entries_to_advertise)
        )
        # ADVERTISE: glidefactory classads
        gfi.advertizeGlideinFromFile(gf_filename, remove_file=True, is_multi=True)
        # ADVERTISE: glidefactoryclient classads
        gfi.advertizeGlideinClientMonitoringFromFile(gfc_filename, remove_file=True, is_multi=True)
    else:
        logSupport.log.info("Not advertising glidefactory and glidefactoryclient classads this round")

    return done_something


############################################################
def iterate(parent_pid, sleep_time, advertize_rate, glideinDescript, frontendDescript, group_name, my_entries):
    """Iterate over set of tasks until it is time to quit or die.
    The main "worker" function for the Factory Entry Group.

    Args:
        parent_pid (int): The pid for the Factory daemon
        sleep_time (int): The number of seconds to sleep between iterations
        advertize_rate (int): The rate at which advertising should occur
        glideinDescript (glideFactoryConfig.GlideinDescript): glidein.descript object in the Factory root dir
        frontendDescript (glideFactoryConfig.FrontendDescript): frontend.descript object in the Factory root dir
        group_name (str): Name of the group
        my_entries (dict): Dictionary of entry objects keyed on entry name
    """
    is_first = True  # In first iteration
    count = 0

    # Record the starttime so we know when to disable the use of old pub key
    starttime = time.time()

    # The grace period should be in the factory config. Use it to determine
    # the end of lifetime for the old key object. Hardcoded for now to 30 mins.
    oldkey_gracetime = int(glideinDescript.data["OldPubKeyGraceTime"])
    oldkey_eoltime = starttime + oldkey_gracetime

    factory_downtimes = glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data["DowntimesFile"])

    while True:
        # Check if parent is still active. If not cleanup and die.
        check_parent(parent_pid, glideinDescript, my_entries)

        cleanupSupport.cleaners.start_background_cleanup()

        # Check if its time to invalidate factory's old key
        if (time.time() > oldkey_eoltime) and (glideinDescript.data["OldPubKeyObj"] is not None):
            # Invalidate the use of factory's old key
            logSupport.log.info("Retiring use of old key.")
            logSupport.log.info(
                f"Old key was valid from {starttime} to {oldkey_eoltime} ie grace of ~{oldkey_gracetime} sec"
            )
            glideinDescript.data["OldPubKeyType"] = None
            glideinDescript.data["OldPubKeyObj"] = None

        # Check if the factory is in downtime. Group is in downtime only if the
        # factory is in downtime. Entry specific downtime is handled in entry
        factory_in_downtime = factory_downtimes.checkDowntime(entry="factory")

        # Record the iteration start time
        iteration_stime = time.time()
        iteration_stime_str = time.ctime()

        if factory_in_downtime:
            logSupport.log.info("Iteration at (in downtime) %s" % iteration_stime_str)
        else:
            logSupport.log.info("Iteration at %s" % iteration_stime_str)

        # PM: Shouldn't this be inside the else statement above?
        # Why do we want to execute this if we are in downtime?
        # Or do we want to execute only few steps here but code prevents us?
        try:
            done_something = iterate_one(  # noqa: F841
                count == 0, factory_in_downtime, glideinDescript, frontendDescript, group_name, my_entries
            )

            logSupport.log.info("Writing stats for all entries")

            try:
                pids = []
                # generate a list of entries for each CPU
                cpuCount = int(glideinDescript.data["MonitorUpdateThreadCount"])
                logSupport.log.info("Number of parallel writes for stats: %i" % cpuCount)

                entrylists = [list(my_entries.values())[cpu::cpuCount] for cpu in range(cpuCount)]

                # Fork's keyed by cpu number. Actual key is irrelevant
                pipe_ids = {}

                post_writestats_info = {}

                for cpu in range(cpuCount):
                    r, w = os.pipe()
                    unregister_sighandler()
                    pid = os.fork()
                    if pid:
                        # I am the parent
                        register_sighandler()
                        pids.append(pid)
                        os.close(w)
                        pipe_ids[cpu] = {"r": r, "pid": pid}
                    else:
                        # I am the child
                        os.close(r)
                        logSupport.disable_rotate = True
                        # Return the pickled entry object in form of dict
                        # return_dict[entry.name][entry.getState()]
                        return_dict = {}
                        for entry in entrylists[cpu]:
                            try:
                                entry.writeStats()
                                return_dict[entry.name] = entry.getState()
                            except Exception:
                                entry.log.warning(f"Error writing stats for entry '{entry.name}'")
                                entry.log.exception(f"Error writing stats for entry '{entry.name}': ")

                        try:
                            os.write(w, pickle.dumps(return_dict))
                        except Exception:
                            # Catch and log exceptions if any to avoid
                            # runaway processes.
                            logSupport.log.exception(f"Error writing pickled state for entries '{entrylists[cpu]}': ")
                        os.close(w)
                        # Exit without triggering SystemExit exception
                        # Note that this is skippihg also all the cleanup (files closing, finally clauses)
                        os._exit(0)

                try:
                    logSupport.log.info("Processing response from children after write stats")
                    post_writestats_info = fetch_fork_result_list(pipe_ids)
                except Exception:
                    logSupport.log.exception("Error processing response from one or more children after write stats")

                logSupport.roll_all_logs()

                for i in post_writestats_info:
                    for ent in post_writestats_info[i]:
                        (my_entries[ent]).setState(post_writestats_info[i][ent])
            except KeyboardInterrupt:
                raise  # this is an exit signal, pass through
            except Exception:
                # never fail for stats reasons!
                logSupport.log.exception("Error writing stats: ")
        except KeyboardInterrupt:
            raise  # this is an exit signal, pass through
        except Exception:
            if is_first:
                raise
            else:
                # If not the first pass, just warn
                logSupport.log.exception("Exception occurred in the main loop of Factory Group %s: " % group_name)

        cleanupSupport.cleaners.wait_for_cleanup()

        iteration_etime = time.time()
        iteration_sleep_time = sleep_time - (iteration_etime - iteration_stime)
        if iteration_sleep_time < 0:
            iteration_sleep_time = 0
        logSupport.log.info("Sleep %is" % iteration_sleep_time)
        time.sleep(iteration_sleep_time)

        count = (count + 1) % advertize_rate
        is_first = False  # Entering following iterations


############################################################


def main(parent_pid, sleep_time, advertize_rate, startup_dir, entry_names, group_id):
    """GlideinFactoryEntryGroup main function

    Setup logging, monitoring, and configuration information. Starts the Entry
    group main loop and handles cleanup at shutdown.

    Args:
        parent_pid (int): The pid for the Factory daemon
        sleep_time (int): The number of seconds to sleep between iterations
        advertize_rate (int): The rate at which advertising should occur
        startup_dir (str|Path): The "home" directory for the entry.
        entry_names (str): Colon separated list with the names of the entries this process should work on
        group_id (str): Group id, normally a number (with the "group_" prefix forms the group name),
            It can change between Factory reconfigurations

    """

    # Assume name to be group_[0,1,2] etc. Only required to create log_dir
    # where tasks common to the group will be stored. There is no other
    # significance to the group_name and number of entries supported by a group
    # can change between factory reconfigs
    group_name = "group_%s" % group_id

    os.chdir(startup_dir)

    # Set up the lock_dir
    gfi.factoryConfig.lock_dir = os.path.join(startup_dir, "lock")

    # Read information about the glidein and frontends
    glideinDescript = gfc.GlideinDescript()
    frontendDescript = gfc.FrontendDescript()

    # set factory_collector at a global level, since we do not expect it to change
    gfi.factoryConfig.factory_collector = glideinDescript.data["FactoryCollector"]

    # Load factory keys
    glideinDescript.load_pub_key()
    glideinDescript.load_old_rsa_key()

    # Dictionary of Entry objects this group will process
    my_entries = {}
    glidein_entries = glideinDescript.data["Entries"]

    # Initialize log files for entry groups
    logSupport.log_dir = os.path.join(glideinDescript.data["LogDir"], "factory")
    logSupport.log = logSupport.get_logger_with_handlers(group_name, logSupport.log_dir, glideinDescript.data)
    logSupport.log.info(f"Logging initialized for {group_name}")

    logSupport.log.info("Starting up")
    logSupport.log.info(f"Entries processed by {group_name}: {entry_names} ")

    # Check if all the entries in this group are valid
    for entry in entry_names.split(":"):
        if entry not in glidein_entries.split(","):
            msg = f"Entry '{entry}' not configured: {glidein_entries}"
            logSupport.log.warning(msg)
            raise RuntimeError(msg)

        # Create entry objects
        my_entries[entry] = glideFactoryEntry.Entry(entry, startup_dir, glideinDescript, frontendDescript)

    # Create lock file for this group and register its parent
    pid_obj = glideFactoryPidLib.EntryGroupPidSupport(startup_dir, group_name)
    pid_obj.register(parent_pid)

    try:
        try:
            try:
                iterate(
                    parent_pid, sleep_time, advertize_rate, glideinDescript, frontendDescript, group_name, my_entries
                )
            except KeyboardInterrupt:
                logSupport.log.info("Received signal...exit")
            except Exception:
                logSupport.log.exception("Exception occurred in iterate: ")
                raise
        finally:
            # No need to cleanup. The parent should be doing it
            logSupport.log.info("Dying")
    finally:
        pid_obj.relinquish()


################################################################################
# Pickle Friendly data
################################################################################


def compile_pickle_data(entry, work_done):
    """Extract the state of the entry after doing work

    Args:
        entry (Entry): Entry object
        work_done (int): Work done info

    Returns:
        dict: pickle-friendly version of the Entry (state of the Entry)
    """
    return_dict = entry.getState()
    return_dict["work_done"] = work_done
    return return_dict


############################################################
#
# S T A R T U P
#
############################################################

if __name__ == "__main__":
    register_sighandler()

    # Force integrity checks on all condor operations
    gfl.set_condor_integrity_checks()

    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6])
