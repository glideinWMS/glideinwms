# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements classes to track changes in glidein status logs."""


import copy
import mmap
import os
import os.path
import re
import stat
import time

from glideinwms.lib import condorLogParser, logSupport

rawJobId2Nr = condorLogParser.rawJobId2Nr
rawTime2cTime = condorLogParser.rawTime2cTime


class logSummaryTimingsOutWrapper:
    """A wrapper class to lazily instantiate a logSummaryTimingsOut object."""

    def __init__(self):
        """Initialize the wrapper with a None object."""
        self.obj = None

    def get_obj(self, logname=None, cache_dir=None, username="all"):
        """Return a logSummaryTimingsOut object, creating it if necessary.

        Args:
            logname (str, optional): The log file name.
            cache_dir (str, optional): Directory to cache parsed results.
            username (str, optional): Username used in the file suffix. Defaults to "all".

        Returns:
            logSummaryTimingsOut: The instantiated logSummaryTimingsOut object.
        """
        if (logname is not None) and (cache_dir is not None):
            self.obj = logSummaryTimingsOut(logname, cache_dir, username)
        return self.obj


class logSummaryTimingsOut(condorLogParser.logSummaryTimings):
    """Logs timing and status of a job.

    This class declares a job complete only after the output file has been received.
    The format is slightly different from that of logSummaryTimings; it adds the directory name
    in the job ID. When an output file is found, it adds a 4th parameter to the completed jobs.
    See the extractLogData function for more details.
    """

    def __init__(self, logname, cache_dir, username):
        """Initialize a `logSummaryTimingsOut` instance.

        This method uses the `condorLogParser` `clInit` function to initialize the log summary.
        It also sets the directory name, cache directory, and current time information.

        Args:
            logname (str): Path to the log file.
            cache_dir (str): Directory for caching log data.
            username (str): Username used to form the file suffix.
        """
        self.clInit(logname, cache_dir, ".%s.ftstpk" % username)
        self.dirname = os.path.dirname(logname)
        self.cache_dir = cache_dir
        self.now = time.time()
        self.year = time.localtime(self.now)[0]

    def loadFromLog(self):
        """Load and post-process the log file.

        This method first calls the parent loadFromLog() to load the log content (from file or from cache).
        If new completed jobs exist, it performs post‑processing by checking the corresponding job output
        files (job.NUMBER.out) to verify if the job has finished and to extract additional data.
        It then updates the "Completed" and "CompletedNoOut" fields in self.data and
        appends the full job filename.

        Returns:
            None
        """
        condorLogParser.logSummaryTimings.loadFromLog(self)
        if "Completed" not in self.data:
            return  # nothing else to do
        org_completed = self.data["Completed"]
        new_completed = []
        new_waitout = []
        now = time.time()
        year = time.localtime(now)[0]
        for el in org_completed:
            job_id = rawJobId2Nr(el[0])
            job_fname = "job.%i.%i.out" % job_id
            job_fullname = os.path.join(self.dirname, job_fname)

            end_time = rawTime2cTime(el[3], year)
            if end_time > now:
                end_time = rawTime2cTime(el[3], year - 1)
            try:
                statinfo = os.stat(job_fullname)
                ftime = statinfo[stat.ST_MTIME]
                fsize = statinfo[stat.ST_SIZE]

                file_ok = (
                    (fsize > 0)
                    and (ftime > (end_time - 300))  # log files are ==0 only before Condor_G transfers them back
                    and (ftime < (now - 5))  # same here
                )  # make sure it is not being written into
            except OSError:
                # no file, report invalid
                file_ok = 0

            if file_ok:
                # try:
                #    fdata=extractLogData(job_fullname)
                # except Exception:
                #    fdata=None # just protect
                new_completed.append(el)
            else:
                if (now - end_time) < 3600:  # give him 1 hour to return the log files
                    new_waitout.append(el)
                else:
                    new_completed.append(el)

        self.data["CompletedNoOut"] = new_waitout
        self.data["Completed"] = new_completed

        # append log name prefix
        for k in list(self.data.keys()):
            new_karr = []
            for el in self.data[k]:
                job_id = rawJobId2Nr(el[0])
                job_fname = "job.%i.%i" % (job_id[0], job_id[1])
                job_fullname = os.path.join(self.dirname, job_fname)
                new_el = el + (job_fullname,)
                new_karr.append(new_el)
            self.data[k] = new_karr

        return

    def diff_raw(self, other):
        """Compute the symmetric difference between self.data and other.

        The method compares the job IDs in the two datasets and identifies for each status jobs that have
        either entered or exited that status between the two iterations.

        Args:
            other (dict): A dictionary of statuses to job lists representing previous iteration data.

        Returns:
            dict: A dictionary where each key corresponds to a status and each value is a dict with keys:
                  'Entered' (jobs present in self.data but not in other) and
                  'Exited' (jobs present in other but not in self.data).
        """
        if other is None:
            outdata = {}
            if self.data is not None:
                for k in list(self.data.keys()):
                    outdata[k] = {"Exited": [], "Entered": self.data[k]}
            return outdata
        elif self.data is None:
            outdata = {}
            for k in list(other.keys()):
                outdata[k] = {"Entered": [], "Exited": other[k]}
            return outdata
        else:
            outdata = {}

            keys = {}  # keys will contain the merge of the two lists

            for s in list(self.data.keys()) + list(other.keys()):
                keys[s] = None

            for s in list(keys.keys()):
                sel = []
                if s in self.data:
                    for sel_e in self.data[s]:
                        sel.append(sel_e[0])

                oel = []
                if s in other:
                    for oel_e in other[s]:
                        oel.append(oel_e[0])

                #################

                outdata_s = {"Entered": [], "Exited": []}
                outdata[s] = outdata_s

                sset = set(sel)
                oset = set(oel)

                entered_set = sset.difference(oset)
                entered = []
                if s in self.data:
                    for sel_e in self.data[s]:
                        if sel_e[0] in entered_set:
                            entered.append(sel_e)

                exited_set = oset.difference(sset)
                exited = []
                if s in other:
                    for oel_e in other[s]:
                        if oel_e[0] in exited_set:
                            exited.append(oel_e)

                outdata_s["Entered"] = entered
                outdata_s["Exited"] = exited
            return outdata

    # diff self data with other info
    # add glidein log data to Entered/Completed
    # return data[status]['Entered'|'Exited'] - list of jobs
    # completed jobs are augmented with data from the log
    def diff(self, other_data):
        """Compute the difference between current data and other_data to compare the current
        iteration data with previous iteration.

        Augments the "Entered" jobs in the "Completed" category with additional log data
        from the corresponding output file.
        Uses diff_raw to perform symmetric difference of self.data
        and other_data and puts it into data[status]['Entered'|'Exited']

        Args:
            other_data (dict): Previous iteration data.

        Returns:
            dict: Dictionary mapping each status to a dict with keys 'Entered' and 'Exited' containing job lists.
        """
        outdata = self.diff_raw(other_data)
        if "Completed" in outdata:
            outdata_s = outdata["Completed"]
            entered = outdata_s["Entered"]
            for i in range(len(entered)):
                sel_e = entered[i]
                job_fullname = sel_e[-1] + ".out"

                try:
                    fdata = _extract_log_data(job_fullname)
                except Exception:
                    fdata = copy.deepcopy(EMPTY_LOG_DATA)  # just protect

                entered[i] = sel_e[:-1] + (fdata, sel_e[-1])
        return outdata


class dirSummarySimple:
    """A simple summary of directory log data.

    This class acts as a wrapper around a log parser object and returns
    a simplified version of its data.
    Further work on this will need to implement glidein exit code checks
    """

    def __init__(self, obj):
        """Initialize the dirSummarySimple object.

        Args:
            obj: An object with a 'data' attribute (e.g., a log parser instance).
        """
        self.data = copy.deepcopy(obj.data)
        self.logClass = obj.logClass
        self.wrapperClass = obj.wrapperClass

        if obj.wrapperClass is not None:
            self.logClass = obj.wrapperClass.get_obj()
        else:
            logSupport.log.debug("== MISHANDLED LogParser Object! ==")

    def mk_temp_log_obj(self):
        """Create a temporary log object based on the current data.

        Returns:
            A temporary log object with its data set to the current summary.
        """
        if self.wrapperClass is not None:
            dummyobj = self.wrapperClass.get_obj(logname=os.path.join("/tmp", "dummy.txt"), cache_dir="/tmp")
        else:
            dummyobj = self.logClass(os.path.join("/tmp", "dummy.txt"), "/tmp")
        # dummyobj=self.logClass(os.path.join('/tmp','dummy.txt'),'/tmp')
        dummyobj.data = self.data  # a little rough but works
        return dummyobj

    def diff(self, other):
        """Compute the difference between this summary and another.

        Args:
            other: Another dirSummarySimple object.

        Returns:
            The difference data computed by the temporary log object.
        """
        dummyobj = self.mk_temp_log_obj()
        return dummyobj.diff(other.data)

    def merge(self, other):
        """Merge another summary into this one.

        Args:
            other: Another dirSummarySimple object.

        Returns:
            None. The data is merged into the `data` attribute of the object invoking this method.
        """
        dummyobj = self.mk_temp_log_obj()
        dummyobj.merge(copy.deepcopy(other.data))
        self.data = dummyobj.data


class dirSummaryTimingsOut(condorLogParser.cacheDirClass):
    """A class to summarize timings from condor_activity logs with output file checking.

    This class initializes an instance of cacheDirClass that selects all files named condor_activity...
    in a directory corresponding to a particular client and adds extra information from the job's output file.
    """

    def __init__(self, dirname, cache_dir, client_name, user_name, inactive_files=None, inactive_timeout=24 * 3600):
        """Initialize the dirSummaryTimingsOut instance.

        Args:
            dirname (str): Directory containing log files.
            cache_dir (str): Directory for caching.
            client_name (str): Client name.
            user_name (str): Username used to form the file suffix.
            inactive_files (list, optional): List of inactive files. Defaults to None.
            inactive_timeout (int, optional): Timeout in seconds for inactive files. Defaults to 24*3600.
        """
        self.cdInit(
            None,
            dirname,
            "condor_activity_",
            "_%s.log" % client_name,
            ".%s.cifpk" % user_name,
            inactive_files,
            inactive_timeout,
            cache_dir,
            wrapperClass=logSummaryTimingsOutWrapper(),
            username=user_name,
        )

    def get_simple(self):
        """Return a simplified directory summary for the desired client.

        Returns:
            dirSummarySimple: A simplified summary object.
        """
        try:
            obj = dirSummarySimple(self)
        except Exception:
            logSupport.log.exception("dirSummarySimple failed")
            raise

        return obj


class dirSummaryTimingsOutFull(condorLogParser.cacheDirClass):
    """A class to summarize timings from all condor_activity logs in a directory.

    This class uses a lambda function to initialize an instance of `cacheDirClass`.
    Unlike `dirSummaryTimingsOut`, this class does not filter by client name.
    """

    def __init__(self, dirname, cache_dir, inactive_files=None, inactive_timeout=24 * 3600):
        """Initialize the dirSummaryTimingsOutFull instance.

        Args:
            dirname (str): Directory containing log files.
            cache_dir (str): Directory for caching.
            inactive_files (list, optional): List of inactive files. Defaults to None.
            inactive_timeout (int, optional): Timeout in seconds for inactive files. Defaults to 24*3600.
        """
        self.cdInit(
            lambda ln, cd: logSummaryTimingsOut(ln, cd, "all"),
            dirname,
            "condor_activity_",
            ".log",
            ".all.cifpk",
            inactive_files,
            inactive_timeout,
            cache_dir,
        )

    def get_simple(self):
        """Return a simplified directory summary for all logs.

        Returns:
            dirSummarySimple: A simplified summary object.
        """
        return dirSummarySimple(self)


#########################################################
#     P R I V A T E
#########################################################

ELD_RC_VALIDATE_END = re.compile(b"=== Last script starting .* after validating for (?P<secs>[0-9]+) ===")
ELD_RC_CONDOR_START = re.compile(b"=== Condor starting.*===")
ELD_RC_CONDOR_END = re.compile(b"=== Condor ended.*after (?P<secs>[0-9]+) ===")
ELD_RC_CONDOR_SLOT = re.compile(
    rb"=== Stats of (?P<slot>\S+) ===(?P<content>.*)=== End Stats of (?P<slot2>\S+) ===", re.M | re.DOTALL
)
ELD_RC_CONDOR_SLOT_CONTENT_COUNT = re.compile(
    b"Total(?P<name>.*)jobs (?P<jobsnr>[0-9]+) .*utilization (?P<secs>[0-9]+)"
)
ELD_RC_CONDOR_SLOT_ACTIVATIONS_COUNT = re.compile(b"Total number of activations/claims: (?P<nr>[0-9]+)")
ELD_RC_GLIDEIN_END = re.compile(b"=== Glidein ending .* with code (?P<code>[0-9]+) after (?P<secs>[0-9]+) ===")

KNOWN_SLOT_STATS = ["Total", "goodZ", "goodNZ", "badSignal", "badOther"]

EMPTY_LOG_DATA = {"condor_started": 0, "glidein_duration": 0}


def _extract_log_data(fname):
    """Extract job log statistics from a job output file.

    Given a filename of a job file "path/job.NUMBER.out", extract statistics such as:
      - glidein_duration: How long the glidein ran.
      - validation_duration: How long the validation step took before HTCondor started.
      - condor_started: Boolean flag indicating whether HTCondor started.
      - condor_duration: How long HTCondor ran.
      - stats: A dictionary of various slot statistics (e.g. Total, goodZ, etc.), counting the jobs and duration
        (keys 'jobsnr' and 'secs').
    The last two are present only if condor_duration is True (1).

    Args:
        fname (str): Full path to the job output file.

    Returns:
        dict: A dictionary with keys:
            - glidein_duration (int): How long the glidein ran.
            - validation_duration (int): How long the validation step took before HTCondor started.
            - condor_started (int): Should be bool, 1 if HTCondor started, 0 otherwise
            - condor_duration (int): How long HTCondor ran
            - stats (dict): Detailed slot statistics (as in KNOWN_SLOT_STATS).

    Example of return value:
            ```
            {'glidein_duration':20305, 'validation_duration':6, 'condor_started':1,
             'condor_duration': 20298,
             'stats': {'badSignal': {'secs': 0, 'jobsnr': 0},
                       'goodZ': {'secs' : 19481, 'jobsnr': 1},
                       'Total': {'secs': 19481, 'jobsnr': 1},
                       'goodNZ': {'secs': 0, 'jobsnr': 0},
                       'badOther': {'secs': 0, 'jobsnr': 0}
                       }
            }
            ```

    """
    condor_starting = 0
    condor_duration = None
    validation_duration = None
    slot_stats = {}

    size = os.path.getsize(fname)
    if size < 10:
        return copy.deepcopy(EMPTY_LOG_DATA)
    with open(fname) as fd:
        buf = mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)
        try:
            buf_idx = 0
            validate_re = ELD_RC_VALIDATE_END.search(buf, buf_idx)
            if validate_re is not None:
                try:
                    validation_duration = int(validate_re.group("secs"))
                except (ValueError, TypeError):
                    validation_duration = None
                # Continue search after validate RE
                buf_idx = validate_re.end() + 1

            start_re = ELD_RC_CONDOR_START.search(buf, buf_idx)
            if start_re is not None:
                condor_starting = 1
                buf_idx = start_re.end() + 1
                end_re = ELD_RC_CONDOR_END.search(buf, buf_idx)
                if end_re is not None:
                    try:
                        condor_duration = int(end_re.group("secs"))
                    except (ValueError, TypeError):
                        condor_duration = None
                    buf_idx = end_re.end() + 1
                    slot_re = ELD_RC_CONDOR_SLOT.search(buf, buf_idx)
                    while slot_re is not None:
                        buf_idx = slot_re.end() + 1
                        slot_name = slot_re.group("slot").decode("utf-8")
                        if slot_name[-1] != "1":  # ignore slot 1, it is used for monitoring only
                            slot_buf = slot_re.group("content")
                            count_re = ELD_RC_CONDOR_SLOT_CONTENT_COUNT.search(slot_buf, 0)
                            while count_re is not None:
                                count_name = count_re.group("name").decode("utf-8")
                                # need to trim it, comes out with spaces
                                if count_name == " ":  # special case
                                    count_name = "Total"
                                else:
                                    count_name = count_name[1:-1]

                                try:
                                    jobsnr = int(count_re.group("jobsnr"))
                                    secs = int(count_re.group("secs"))
                                except (ValueError, TypeError):
                                    jobsnr = None

                                if jobsnr is not None:  # check I had no errors in integer conversion
                                    if count_name not in slot_stats:
                                        slot_stats[count_name] = {"jobsnr": jobsnr, "secs": secs}

                                count_re = ELD_RC_CONDOR_SLOT_CONTENT_COUNT.search(slot_buf, count_re.end() + 1)
                                # end while count_re

                        slot_re = ELD_RC_CONDOR_SLOT.search(buf, buf_idx)
                        # end while slot_re

            activations_re = ELD_RC_CONDOR_SLOT_ACTIVATIONS_COUNT.search(buf, buf_idx)
            if activations_re is not None:
                try:
                    num_activations = int(activations_re.group("nr"))
                except (ValueError, TypeError):
                    num_activations = None
                # Continue search after activations RE
                buf_idx = activations_re.end() + 1
            else:
                num_activations = None

            glidein_end_re = ELD_RC_GLIDEIN_END.search(buf, buf_idx)
            if glidein_end_re is not None:
                try:
                    glidein_duration = int(glidein_end_re.group("secs"))
                except (ValueError, TypeError):
                    glidein_duration = None
                # Continue search after glidein_end RE
                buf_idx = glidein_end_re.end() + 1
            else:
                glidein_duration = None

        finally:
            buf.close()

    out = {"condor_started": condor_starting}
    if validation_duration is not None:
        out["validation_duration"] = validation_duration
    # else:
    #   out['validation_duration']=1

    if glidein_duration is not None:
        out["glidein_duration"] = glidein_duration
    # else:
    #   out['glidein_duration']=2

    if num_activations is not None:
        out["activations_claims"] = num_activations
    if condor_starting:
        if condor_duration is not None:
            out["condor_duration"] = condor_duration
            out["stats"] = slot_stats

    return out
