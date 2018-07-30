import time
import random

def pickAlgoDefault(submit_files, status_sf, jobDescript, nr_glideins, log):
    """
    Given the list of sub entries (aka submit files), and the status of each sub entry (how many idle + running etc)
    figures out how many glideins to submit for each sub entry.
    1) Shuffle the submit_files list
    2) Try to "depth-wise" fill all the subentries untillimits are reached

    @type submit_files: list
    @param submit_files: list of strings containing the name of the submit files for this entry set
    @type status_sf: dict
    @param status_sf: dictrionary where the keys are the submit files and the values is a condor states dict
    @type jobDescript: object
    @param jobDescript: will read here maximum number of idle/total fglideins for each sub entry
    @type nr_glideins: int
    @param nr_glideins: total number of glideins to submit to all the entries
    @type log: object
    @param log: logging object

    Return a dictionary where keys are the submit files, and values are int indicating how many glideins to submit
    """
    log.debug("submit_files %s, status_sf %s, jobDescript %s, nr_glideins %s, log %s" % (submit_files, status_sf, jobDescript, nr_glideins, log))
    # Create empty return dictionary
    res = dict((sf,0) for sf in submit_files) # e.g.: {'job.entry1.condor' : 0, 'job.entry2.condor' : 0}
    # At CERN /dev/random always returns the same seed
    random.seed(time.time())
    # Randomize the entries in case (for example) always: nr_glideins < len(submit_files)
    # Without randomization you would only send pilots to the first sub entries
    random.shuffle(submit_files)

    sf_idle_limit = int(jobDescript.data['PerEntryMaxIdle']) / len(submit_files)
    sf_run_limit = int(jobDescript.data['PerEntryMaxGlideins']) / len(submit_files)

    csf = 0 # current submit file
    for _ in range(nr_glideins):
        curr_sf = submit_files[csf] # e.g.: job.entryname.condor
        curr_states = status_sf.get(curr_sf, {})
        curr_assigned = res[curr_sf]
        if (curr_states.get(1, 0) + curr_assigned < sf_idle_limit) and \
           (curr_states.get(1, 0) + curr_states.get(2, 0) + curr_assigned < sf_run_limit):
            res[curr_sf] += 1
        # next glidein will be assigned to the next submit file
        csf = (csf + 1) % len(submit_files)

    return res
