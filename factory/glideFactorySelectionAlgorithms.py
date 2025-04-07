# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This package contains a function to select which resource (entry) to use when the Glideins
can be submitted to multiple resources.
"""

import random
import time


def selectionAlgoDefault(submit_files, status_sf, jobDescript, nr_glideins, log):
    """Determines the number of glideins to submit for each sub entry.

    Each entry can have multiple submit files (sub entries).
    Given a list of sub entries (i.e. submit files) and the current status of each sub entry (number of idle and running glideins),
    this function shuffles the submit_files list and then assigns glideins in a round-robin (depth-wise) fashion until the limits are reached.

    Args:
        submit_files (list of str): List of strings containing the names of the submit files for this entry set.
        status_sf (dict): Dictionary where the keys are the submit file names and the values are condor state dictionaries.
        jobDescript (object): An object that contains Frontend description data. It is used to read the maximum number of idle and total glideins for each sub entry.
        nr_glideins (int): Total number of glideins to submit across all the entries.
        log (object): Logging object.

    Returns:
        dict: A dictionary where the keys are the submit file names and the values are integers indicating how many glideins to submit.
    """
    log.debug(
        "submit_files %s, status_sf %s, jobDescript %s, nr_glideins %s, log %s"
        % (submit_files, status_sf, jobDescript, nr_glideins, log)
    )
    # Create empty return dictionary
    res = {sf: 0 for sf in submit_files}  # e.g.: {'job.entry1.condor' : 0, 'job.entry2.condor' : 0}
    # At CERN /dev/random always returns the same seed
    random.seed(time.time())
    # Randomize the entries in case (for example) always: nr_glideins < len(submit_files)
    # Without randomization you would only send pilots to the first sub entries
    random.shuffle(submit_files)

    sf_idle_limit = int(jobDescript.data["PerEntryMaxIdle"]) // len(submit_files)
    sf_run_limit = int(jobDescript.data["PerEntryMaxGlideins"]) // len(submit_files)

    csf = 0  # current submit file
    for _ in range(nr_glideins):
        curr_sf = submit_files[csf]  # e.g.: job.entryname.condor
        curr_states = status_sf.get(curr_sf, {})
        curr_assigned = res[curr_sf]
        if (curr_states.get(1, 0) + curr_assigned < sf_idle_limit) and (
            curr_states.get(1, 0) + curr_states.get(2, 0) + curr_assigned < sf_run_limit
        ):
            res[curr_sf] += 1
        # next glidein will be assigned to the next submit file
        csf = (csf + 1) % len(submit_files)

    return res
