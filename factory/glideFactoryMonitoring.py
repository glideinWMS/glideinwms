# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements the functions needed to monitor the glidein factory"""

import copy
import json
import math
import os
import pickle
import re
import time

from glideinwms.lib import cleanupSupport, logSupport, rrdSupport, timeConversion, util, xmlFormat

# list of rrd files that each site has
RRD_LIST = (
    "Status_Attributes.rrd",
    "Log_Completed.rrd",
    "Log_Completed_Stats.rrd",
    "Log_Completed_WasteTime.rrd",
    "Log_Counts.rrd",
)


############################################################
#
# Configuration
#
############################################################


class MonitoringConfig:
    """Configuration for monitoring the glidein factory.

    This class stores default values for RRD parameters, log directories, and provides methods to write monitoring files.

    Attributes:
        rrd_step (int): The step (in seconds) for the RRD. Default is 300 seconds.
        rrd_heartbeat (int): The heartbeat (in seconds) for the RRD. Default is 1800 seconds.
        rrd_ds_name (str): The data source name for the RRD. Default is "val".
        rrd_archives (list): A list of tuples defining the RRD archive parameters.
        monitor_dir (str): The directory where monitoring files are stored. Default is "monitor/".
        log_dir (str): The directory where log files are stored. Default is "log/".
        logCleanupObj: An object for cleaning up log files (initially None).
        rrd_obj: An instance of rrdSupport.rrdSupport() for creating/updating RRD files.
        my_name (str): The name of the monitor (default "Unknown").
        log: The logger to use.
    """

    def __init__(self, log=logSupport.log):
        """Initialize a MonitoringConfig object with default values."""
        # set default values
        # user should modify if needed
        self.rrd_step = 300  # default to 5 minutes
        self.rrd_heartbeat = 1800  # default to 30 minutes, should be at least twice the loop time
        self.rrd_ds_name = "val"
        self.rrd_archives = [
            ("AVERAGE", 0.8, 1, 740),  # max precision, keep 2.5 days
            ("AVERAGE", 0.92, 12, 740),  # 1 h precision, keep for a month (30 days)
            ("AVERAGE", 0.98, 144, 740),  # 12 hour precision, keep for a year
        ]

        self.monitor_dir = "monitor/"

        self.log_dir = "log/"
        self.logCleanupObj = None

        self.rrd_obj = rrdSupport.rrdSupport()
        """@ivar: The name of the attribute that identifies the glidein """
        self.my_name = "Unknown"
        self.log = log

    def config_log(self, log_dir, max_days, min_days, max_mbs):
        """Configure the log directory and cleanup parameters.

        Args:
            log_dir (str): The directory for log files.
            max_days (int or float): Maximum retention time in days.
            min_days (int or float): Minimum retention time in days.
            max_mbs (int or float): Maximum size in MB.
        """
        self.log_dir = log_dir
        cleaner = cleanupSupport.DirCleanupWSpace(
            log_dir,
            r"(completed_jobs_.*\.log)",
            int(max_days * 24 * 3600),
            int(min_days * 24 * 3600),
            int(max_mbs * (1024.0 * 1024.0)),
        )
        cleanupSupport.cleaners.add_cleaner(cleaner)

    def logCompleted(self, client_name, entered_dict):
        """Log newly completed glideins in an XML-like format.

        This function takes all newly completed glideins and logs them in an XML-like file named
        "completed_jobs_<date>.log" in the log directory (logs/entry_Name/). It counts the jobs completed on a glidein
        but does not keep track of the cores received or used by the jobs.

        Args:
            client_name (str): The name of the frontend client.
            entered_dict (dict): A dictionary (keyed by job_id) of dictionaries for all jobs that have "Entered" the "Completed"
                states. Each inner dictionary contains keys such as "username", "jobs_duration" (with subkeys "total", "goodput", "terminated"),
                "wastemill" (with subkeys "validation", "idle", "nosuccess", "badput"), "duration", "condor_started", "condor_duration", and "jobsnr".
        """
        now = time.time()

        job_ids = list(entered_dict.keys())
        if len(job_ids) == 0:
            return  # nothing to do
        job_ids.sort()

        relative_fname = "completed_jobs_%s.log" % time.strftime("%Y%m%d", time.localtime(now))
        fname = os.path.join(self.log_dir, relative_fname)
        with open(fname, "a") as fd:
            for job_id in job_ids:
                el = entered_dict[job_id]
                username = el["username"]
                username = username.split(":")[0]
                jobs_duration = el["jobs_duration"]
                waste_mill = el["wastemill"]
                fd.write(
                    (
                        "<job %37s %34s %22s %17s %17s %22s %24s>"
                        % (
                            ('terminated="%s"' % timeConversion.getISO8601_Local(now)),
                            ('client="%s"' % client_name),
                            ('username="%s"' % username),
                            ('id="%s"' % job_id),
                            ('duration="%i"' % el["duration"]),
                            # Keep comparison, may be None
                            ('condor_started="%s"' % (el["condor_started"] == True)),  # noqa: E712
                            ('condor_duration="%i"' % el["condor_duration"]),
                        )
                    )
                    + (
                        "<user %14s %17s %16s %19s/>"
                        % (
                            ('jobsnr="%i"' % el["jobsnr"]),
                            ('duration="%i"' % jobs_duration["total"]),
                            ('goodput="%i"' % jobs_duration["goodput"]),
                            ('terminated="%i"' % jobs_duration["terminated"]),
                        )
                    )
                    + (
                        "<wastemill %17s %11s %16s %13s/></job>\n"
                        % (
                            ('validation="%i"' % waste_mill["validation"]),
                            ('idle="%i"' % waste_mill["idle"]),
                            ('nosuccess="%i"' % waste_mill["nosuccess"]),
                            ('badput="%i"' % waste_mill["badput"]),
                        )
                    )
                )

    def write_file(self, relative_fname, output_str):
        """Write a string or bytes to a file.

        Args:
            relative_fname (str): The relative file path to write to.
            output_str (str or bytes): The content to write.
        """
        # TODO: Fix str/bytes confusion in the pathname
        fname = os.path.join(self.monitor_dir, relative_fname)
        if isinstance(fname, bytes):
            fname = fname.decode("utf-8")

        # print "Writing "+fname

        # Check to see if the output_str represented as bytes
        if isinstance(output_str, (bytes, bytearray)):
            with open(fname + ".tmp", "wb") as fd:
                fd.write(output_str)
        else:
            with open(fname + ".tmp", "w") as fd:
                fd.write(output_str + "\n")

        util.file_tmp2final(fname, mask_exceptions=(self.log.error, "Failed rename/write into %s" % fname))
        return

    def write_completed_json(self, relative_fname, time, val_dict):
        """Write a dictionary to a JSON file.

        Args:
            relative_fname (str): The relative JSON file name (without extension) relative to `self.monitor_dir`.
            time (float): The timestamp, typically `self.updated`.
            val_dict (dict): The dictionary to dump as JSON.
        """
        fname = os.path.join(self.monitor_dir, relative_fname + ".json")
        data = {}
        data["time"] = time
        data["stats"] = val_dict

        try:
            f = None
            self.log.info(f"Writing {relative_fname} to {str(fname)}")
            f = open(fname, "w")
            json.dump(data, f)
            # f.write(json.dumps(data, indent=4))
        except OSError as e:
            self.log.err(f"unable to open and write to file {str(fname)} in write_completed_json: {str(e)}")
        finally:
            if f:
                f.close()

        return

    def establish_dir(self, relative_dname):
        """Ensure that a directory exists within the monitor directory.

        Args:
            relative_dname (str): The relative directory name.

        Returns:
            str: The full directory path.
        """
        dname = os.path.join(self.monitor_dir, relative_dname)
        # make a directory, its parents and rise no exception if already there
        os.makedirs(dname, exist_ok=True)
        return

    def write_rrd_multi(self, relative_fname, ds_type, time, val_dict, min_val=None, max_val=None):
        """Create or update an RRD file using rrdtool.

        Args:
            relative_fname (str): Relative file name (without extension) for the RRD file.
            ds_type (str): Data source type (e.g., "GAUGE").
            time (float): Timestamp for the RRD update.
            val_dict (dict): Dictionary of values to update.
            min_val (optional): Minimum value, default "U".
            max_val (optional): Maximum value, default "U".
        """
        if self.rrd_obj.isDummy():
            return  # nothing to do, no rrd bin no rrd creation

        # MM don't understand the need for this loop, there is only one element in the tuple, why not:
        # rrd_ext = ".rrd"
        # rrd_archives = self.rrd_archives
        for tp in ((".rrd", self.rrd_archives),):
            rrd_ext, rrd_archives = tp
            fname = os.path.join(self.monitor_dir, relative_fname + rrd_ext)
            # print "Writing RRD "+fname

            if not os.path.isfile(fname):
                # print "Create RRD "+fname
                if min_val is None:
                    min_val = "U"
                if max_val is None:
                    max_val = "U"
                ds_names = sorted(val_dict.keys())

                ds_arr = []
                for ds_name in ds_names:
                    ds_arr.append((ds_name, ds_type, self.rrd_heartbeat, min_val, max_val))
                self.rrd_obj.create_rrd_multi(fname, self.rrd_step, rrd_archives, ds_arr)

            # print "Updating RRD "+fname
            try:
                self.rrd_obj.update_rrd_multi(fname, time, val_dict)
            except Exception:
                self.log.exception("Failed to update %s: " % fname)
        return

    def write_rrd_multi_hetero(self, relative_fname, ds_desc_dict, time, val_dict):
        """Create or update an RRD file with heterogeneous data source definitions.

        This function is similar to write_rrd_multi but allows each data source (ds) to have its own type,
        minimum, and maximum values.
        Each element of ds_desc_dict is a dictionary with any of ds_type, min, max;
        if ds_desc_dict[name] is not present, the defaults are {'ds_type':'GAUGE', 'min':'U', 'max':'U'}

        Args:
            relative_fname (str): Relative file name (without extension) for the RRD file.
            ds_desc_dict (dict): Dictionary mapping data source names to their definitions.
            time (float): Timestamp for the update.
            val_dict (dict): Dictionary of values to update.
        """
        if self.rrd_obj.isDummy():
            return  # nothing to do, no rrd bin no rrd creation

        # MM don't understand the need for this loop, there is only one element in the tuple, why not:
        # rrd_ext = ".rrd"
        # rrd_archives = self.rrd_archives
        for tp in ((".rrd", self.rrd_archives),):
            rrd_ext, rrd_archives = tp
            fname = os.path.join(self.monitor_dir, relative_fname + rrd_ext)
            # print "Writing RRD "+fname

            if not os.path.isfile(fname):
                # print "Create RRD "+fname
                ds_names = sorted(val_dict.keys())

                ds_arr = []
                for ds_name in ds_names:
                    ds_desc = {"ds_type": "GAUGE", "min": "U", "max": "U"}
                    if ds_name in ds_desc_dict:
                        for k in list(ds_desc_dict[ds_name].keys()):
                            ds_desc[k] = ds_desc_dict[ds_name][k]

                    ds_arr.append((ds_name, ds_desc["ds_type"], self.rrd_heartbeat, ds_desc["min"], ds_desc["max"]))
                self.rrd_obj.create_rrd_multi(fname, self.rrd_step, rrd_archives, ds_arr)

            # print "Updating RRD "+fname
            try:
                self.rrd_obj.update_rrd_multi(fname, time, val_dict)
            except Exception:
                self.log.exception("Failed to update %s: " % fname)
        return


#######################################################################################################################
#
#  condorQStats
#
#  This class handles the data obtained from condor_q
#
#######################################################################################################################


# TODO: ['Downtime'] is added to the self.data[client_name] dictionary only if logRequest is called before logSchedd, logClientMonitor
#       This is inconsistent and should be changed, Redmine [#17244]
class condorQStats:
    """Handles aggregated HTCondor statistics from condor_q data.

    This is normally querying the Schedds submitting Glideins

    Attributes:
        data (dict): Aggregated statistics data.
        updated (float): Timestamp of the last update.
        log: Logger instance.
        files_updated: Timestamp when files were last updated.
        attributes (dict): Dictionary defining attributes for different categories.
        downtime (str): Global downtime status.
        expected_cores (int): Expected number of cores per glidein.
    """

    def __init__(self, log=logSupport.log, cores=1):
        """Initialize condorQStats object with empty data and default values.

        Args:
            log: Logger instance.
            cores (int, optional): Expected cores per glidein. Defaults to 1.
        """
        self.data = {}
        self.updated = time.time()
        self.log = log

        self.files_updated = None
        self.attributes = {
            "Status": (
                "Idle",
                "Running",
                "Held",
                "Wait",
                "Pending",
                "StageIn",
                "IdleOther",
                "StageOut",
                "RunningCores",
            ),
            "Requested": ("Idle", "AdjustedIdle", "MaxGlideins", "IdleCores", "MaxCores"),
            "ClientMonitor": (
                "InfoAge",
                "JobsIdle",
                "JobsRunning",
                "JobsRunHere",
                "GlideIdle",
                "GlideRunning",
                "GlideTotal",
                "CoresIdle",
                "CoresRunning",
                "CoresTotal",
            ),
        }
        # create a global downtime field since we want to propagate it in various places
        self.downtime = "True"
        self.expected_cores = (
            cores  # This comes from GLIDEIN_CPUS and GLIDEIN_ESTIMATED_CPUS, actual cores received may differ
        )

    def logSchedd(self, client_name, qc_status, qc_status_sf):
        """Aggregate and log in a dictionary HTCondor schedd-level statistics for a client.

        Args:
            client_name (str): The name of the client requesting the glideins.
            qc_status (dict): Dictionary mapping numeric statuses to job counts.
            qc_status_sf (dict): Dictionary mapping submit files to their qc_status dictionaries.

        Output via sideeffect:
            self.data[client_name]['Status'] is the status for all Glideins
            self.data[client_name]['StatusEntries'] is the Glidein status by Entry
        """
        if client_name in self.data:
            t_el = self.data[client_name]
        else:
            t_el = {}
            self.data[client_name] = t_el

        if "Status" in t_el:
            el = t_el["Status"]
        else:
            el = {}
            t_el["Status"] = el
        self.aggregateStates(qc_status, el)

        # And now aggregate states by submit file
        if "StatusEntries" in t_el:
            dsf = t_el["StatusEntries"]
        else:
            dsf = {}
            t_el["StatusEntries"] = dsf
        for sf in qc_status_sf:
            ksf = self.getEntryFromSubmitFile(sf)
            if ksf:
                elsf = dsf.setdefault(ksf, {})
                self.aggregateStates(qc_status_sf[sf], elsf)
        self.updated = time.time()

    @staticmethod
    def getEntryFromSubmitFile(submitFile):
        """Extract the entry name from a submit file name.

        The submit file name is expected to be of the form:
        'entry_T2_CH_CERN/job.CMSHTPC_T2_CH_CERN_ce301.condor'

        Args:
            submitFile (str): The submit file name.

        Returns:
            str: The extracted entry name, or an empty string if the pattern is not matched.
        """
        # Matches: anything that is not a dot, a dot, anything that is not a dot (captured),
        # another dot, and finally anything that is not a dot
        m = re.match(r"^[^\.]+\.([^\.]+)\.[^\.]+$", submitFile)
        return m.group(1) if m else ""

    def get_zero_data_element(self):
        """Return a dictionary with keys defined in `self.attributes`, all set to 0.

        Returns:
            dict: A dictionary with zero-initialized integer values.
        """
        empty_data = {}
        for k in self.attributes:
            empty_data[k] = {}
            for kk in self.attributes[k]:
                empty_data[k][kk] = 0
        return empty_data

    def aggregateStates(self, qc_status, el):
        """Aggregate state counts from a qc_status dictionary (condor_q) into another dictionary using state names.

        Args:
            qc_status (dict): Dictionary mapping numeric status codes to counts.
            el (dict): Dictionary to accumulate counts, with state names (e.g. 'Idle' instead of 1) as keys.
        """
        # Listing pairs with jobs counting as 1. Avoid duplicates with the list below
        # These numbers must be consistent w/ the one used to build qc_status
        status_pairs = (
            (1, "Idle"),
            (2, "Running"),
            (5, "Held"),
            (1001, "Wait"),
            (1002, "Pending"),
            (1010, "StageIn"),
            (1100, "IdleOther"),
            (4010, "StageOut"),
        )
        for p in status_pairs:
            nr, status = p
            # TODO: rewrite w/ if in ... else (after m31)
            if status not in el:
                el[status] = 0
            if nr in qc_status:
                el[status] += qc_status[nr]

        # Listing pairs counting the cores (expected_cores). Avoid duplicates with the list above
        # These numbers must be consistent w/ the one used to build qc_status
        status_pairs = ((2, "RunningCores"),)
        for p in status_pairs:
            nr, status = p
            # TODO: rewrite w/ if in ... else (after m31)
            if status not in el:
                el[status] = 0
            if nr in qc_status:
                el[status] += qc_status[nr] * self.expected_cores

    def logRequest(self, client_name, requests):
        """Log client Glidein requests.

        `requests` is a dictionary of requests. `params` is a dictionary of parameters
        Request contains only that (no real cores info). It is evaluated using GLIDEIN_CPUS

        Args:
            client_name (str): The client name.
            requests (dict): Dictionary of requests, expected to have keys 'IdleGlideins', 'AdjIdleGlideins' and 'MaxGlideins'.

        Updates:
            self.data[client_name]['Requested'] with the request counts.
        """
        if client_name in self.data:
            t_el = self.data[client_name]
        else:
            t_el = {}
            t_el["Downtime"] = {"status": self.downtime}
            self.data[client_name] = t_el

        if "Requested" in t_el:
            el = t_el["Requested"]
        else:
            el = {}
            t_el["Requested"] = el

        for reqpair in (("IdleGlideins", "Idle"), ("MaxGlideins", "MaxGlideins"), ("AdjIdleGlideins", "AdjustedIdle")):
            org, new = reqpair
            if new not in el:
                el[new] = 0
            if org in requests:
                el[new] += requests[org]
        for reqpair in (("IdleGlideins", "IdleCores"), ("MaxGlideins", "MaxCores")):
            org, new = reqpair
            if new not in el:
                el[new] = 0
            if org in requests:
                el[new] += requests[org] * self.expected_cores

        # Had to get rid of this
        # Does not make sense when one aggregates
        # el['Parameters']=copy.deepcopy(params)
        # Replacing with an empty list
        el["Parameters"] = {}

        self.updated = time.time()

    def logClientMonitor(self, client_name, client_monitor, client_internals, fraction=1.0):
        """Log monitoring data from the glideclient for a client.

        At the moment, it looks only for
          'Idle'
          'Running'
          'RunningHere'
          'GlideinsIdle', 'GlideinsIdleCores'
          'GlideinsRunning', 'GlideinsRunningCores'
          'GlideinsTotal', 'GlideinsTotalCores'
          'LastHeardFrom'

        Updates go in `self.data` (``self.data[client_name]['ClientMonitor']``)

        Args:
            client_name (str): The client name.
            client_monitor (dict): Monitoring data (GlideinMonitor... attributes from the glideclient ClassAd).
            client_internals (dict): Internal data (from the glideclient ClassAd).
            fraction (float, optional): Scaling factor for the values. Defaults to 1.0.
        """
        if client_name in self.data:
            t_el = self.data[client_name]
        else:
            t_el = {}
            self.data[client_name] = t_el

        if "ClientMonitor" in t_el:
            el = t_el["ClientMonitor"]
        else:
            el = {}
            t_el["ClientMonitor"] = el

        for karr in (
            ("Idle", "JobsIdle"),
            ("Running", "JobsRunning"),
            ("RunningHere", "JobsRunHere"),
            ("GlideinsIdle", "GlideIdle"),
            ("GlideinsRunning", "GlideRunning"),
            ("GlideinsTotal", "GlideTotal"),
            ("GlideinsIdleCores", "CoresIdle"),
            ("GlideinsRunningCores", "CoresRunning"),
            ("GlideinsTotalCores", "CoresTotal"),
        ):
            ck, ek = karr
            if ek not in el:
                el[ek] = 0
            if ck in client_monitor:
                el[ek] += int(client_monitor[ck]) * fraction
            elif ck == "RunningHere":
                # for compatibility, if RunningHere not defined, use min between Running and GlideinsRunning
                if "Running" in client_monitor and "GlideinsRunning" in client_monitor:
                    el[ek] += min(int(client_monitor["Running"]), int(client_monitor["GlideinsRunning"])) * fraction

        if "InfoAge" not in el:
            el["InfoAge"] = 0
            el["InfoAgeAvgCounter"] = 0  # used for totals since we need an avg in totals, not absnum

        if "LastHeardFrom" in client_internals:
            el["InfoAge"] += int(time.time() - int(client_internals["LastHeardFrom"])) * fraction
            el["InfoAgeAvgCounter"] += fraction

        self.updated = time.time()

    # call this after the last logClientMonitor
    def finalizeClientMonitor(self):
        """Round all client monitor values to the nearest integer."""
        # convert all ClinetMonitor numbers in integers
        # needed due to fraction calculations
        for client_name in list(self.data.keys()):
            if "ClientMonitor" in self.data[client_name]:
                el = self.data[client_name]["ClientMonitor"]
                for k in list(el.keys()):
                    el[k] = int(round(el[k]))
        return

    def get_data(self):
        """Return a deep copy of the monitoring data with internal average counters removed.

        Returns:
            dict: The monitoring data.
        """
        data1 = copy.deepcopy(self.data)
        for f in list(data1.keys()):
            fe = data1[f]
            for w in list(fe.keys()):
                el = fe[w]
                for a in list(el.keys()):
                    if a[-10:] == "AvgCounter":  # do not publish avgcounter fields... they are internals
                        del el[a]

        return data1

    @staticmethod
    def get_xml_data(data, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        """Convert monitoring data to an XML formatted string.

        Args:
            data (dict): The monitoring data (`self.get_data()`).
            indent_tab (str, optional): The indentation string. Defaults to xmlFormat.DEFAULT_TAB.
            leading_tab (str, optional): The leading indentation string. Defaults to "".

        Returns:
            str: XML formatted string.
        """
        return xmlFormat.dict2string(
            data,
            dict_name="frontends",
            el_name="frontend",
            subtypes_params={
                "class": {"subclass_params": {"Requested": {"dicts_params": {"Parameters": {"el_name": "Parameter"}}}}}
            },
            indent_tab=indent_tab,
            leading_tab=leading_tab,
        )

    def get_total(self, history={"set_to_zero": False}):
        """Compute and return a total summary of the monitoring data.

        Args:
            history (dict, optional): A dictionary used to track if totals have been set to zero.
                Defaults to {"set_to_zero": False}.

        Returns:
            dict: A dictionary with keys "Status", "Requested", and "ClientMonitor" containing aggregated counts.
        """
        total = {"Status": None, "Requested": None, "ClientMonitor": None}
        set_to_zero = False

        for f in list(self.data.keys()):
            fe = self.data[f]
            for w in list(fe.keys()):
                if w in total:  # ignore eventual not supported classes
                    el = fe[w]
                    tel = total[w]

                    if tel is None:
                        # first one, just copy over
                        total[w] = {}
                        tel = total[w]
                        for a in list(el.keys()):
                            if isinstance(el[a], int):  # copy only numbers
                                tel[a] = el[a]
                    else:
                        # successive, sum
                        for a in list(el.keys()):
                            if isinstance(el[a], int):  # consider only numbers
                                if a in tel:
                                    tel[a] += el[a]
                            # if other frontends did't have this attribute, ignore
                        # if any attribute from prev. frontends are not in the current one, remove from total
                        for a in list(tel.keys()):
                            if a not in el:
                                del tel[a]
                            elif not isinstance(el[a], int):
                                del tel[a]

        for w in list(total.keys()):
            if total[w] is None:
                if w == "Status":
                    total[w] = self.get_zero_data_element()[w]
                    set_to_zero = True
                else:
                    del total[w]  # remove entry if not defined unless is 'Status'
            else:
                tel = total[w]
                for a in list(tel.keys()):
                    if a[-10:] == "AvgCounter":
                        # this is an average counter, calc the average of the referred element
                        # like InfoAge=InfoAge/InfoAgeAvgCounter
                        aorg = a[:-10]
                        tel[aorg] = tel[aorg] // tel[a]
                        # the avgcount totals are just for internal purposes
                        del tel[a]

        if set_to_zero != history["set_to_zero"]:
            if set_to_zero:
                self.updated = time.time()
            history["set_to_zero"] = set_to_zero
        return total

    @staticmethod
    def get_xml_total(total, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        """Convert the total summary data to an XML string.

        Args:
            total (dict): The total summary data (`self.get_total()`).
            indent_tab (str, optional): Indentation for XML formatting. Defaults to xmlFormat.DEFAULT_TAB.
            leading_tab (str, optional): Leading indentation. Defaults to "".

        Returns:
            str: XML formatted total summary.
        """
        return xmlFormat.class2string(total, inst_name="total", indent_tab=indent_tab, leading_tab=leading_tab)

    def get_xml_updated(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        """Return an XML formatted string of the last update time.

        Args:
            indent_tab (str, optional): Indentation for XML formatting. Defaults to xmlFormat.DEFAULT_TAB.
            leading_tab (str, optional): Leading indentation. Defaults to "".

        Returns:
            str: XML formatted update time.
        """
        return xmlFormat.time2xml(self.updated, "updated", indent_tab, leading_tab)

    def set_downtime(self, in_downtime):
        """Set the downtime status.

        Args:
            in_downtime (bool): Downtime status.
        """
        self.downtime = str(in_downtime)
        return

    def get_xml_downtime(self, leading_tab=xmlFormat.DEFAULT_TAB):
        """Return an XML formatted string of the downtime status.

        Args:
            leading_tab (str, optional): Leading indentation. Defaults to xmlFormat.DEFAULT_TAB.

        Returns:
            str: XML formatted downtime information.
        """
        xml_downtime = xmlFormat.dict2string(
            {}, dict_name="downtime", el_name="", params={"status": self.downtime}, leading_tab=leading_tab
        )
        return xml_downtime

    def write_file(self, monitoringConfig=None, alt_stats=None):
        """Calculate a summary for the entry and write statistics to files.

        Args:
            monitoringConfig (MonitoringConfig, optional): Monitoring configuration object. Defaults to global monitoringConfig.
            alt_stats (condorQStats, optional): Alternative condorQStats object if `self` has no data.
        """
        if monitoringConfig is None:
            monitoringConfig = globals()["monitoringConfig"]

        if (self.files_updated is not None) and ((self.updated - self.files_updated) < 5):
            # files updated recently, no need to redo it
            return

        # Retrieve and calculate data
        data = self.get_data()

        if not data and alt_stats is not None:
            total_el = alt_stats.get_total()
        else:
            total_el = self.get_total()

        # write snapshot file
        xml_str = (
            '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
            + "<glideFactoryEntryQStats>\n"
            + self.get_xml_updated(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + self.get_xml_downtime(leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + self.get_xml_data(data, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + self.get_xml_total(total_el, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + "</glideFactoryEntryQStats>\n"
        )
        monitoringConfig.write_file("schedd_status.xml", xml_str)

        # update RRDs
        type_strings = {"Status": "Status", "Requested": "Req", "ClientMonitor": "Client"}
        for fe in [None] + list(data.keys()):
            if fe is None:  # special key == Total
                fe_dir = "total"
                fe_el = total_el
            else:
                fe_dir = "frontend_" + fe
                fe_el = data[fe]

            val_dict = {}
            # Initialize,  so that all get created properly
            for tp in list(self.attributes.keys()):
                tp_str = type_strings[tp]
                attributes_tp = self.attributes[tp]
                for a in attributes_tp:
                    val_dict[f"{tp_str}{a}"] = None

            monitoringConfig.establish_dir(fe_dir)
            for tp in list(fe_el.keys()):
                # values (RRD type) - Status, Requested or ClientMonitor
                if tp not in list(self.attributes.keys()):
                    continue

                tp_str = type_strings[tp]

                attributes_tp = self.attributes[tp]

                fe_el_tp = fe_el[tp]
                for a in list(fe_el_tp.keys()):
                    if a in attributes_tp:
                        a_el = fe_el_tp[a]
                        if not isinstance(a_el, dict):  # ignore subdictionaries
                            val_dict[f"{tp_str}{a}"] = a_el

            monitoringConfig.write_rrd_multi(os.path.join(fe_dir, "Status_Attributes"), "GAUGE", self.updated, val_dict)

        self.files_updated = self.updated
        return


######################################################################################################################
#
#  condorLogSummary
#
#  This class handles the data obtained from parsing the glidein log files
#
######################################################################################################################


class condorLogSummary:
    """Handles the data obtained from parsing the glidein log files.

    This class stores and aggregates statistics from parsed glidein log files,
    allowing the detection of state changes (e.g. completed jobs) across iterations.
    """

    def __init__(self, log=logSupport.log):
        """Initialize a condorLogSummary instance.

        Args:
            log: Logger instance to use (default: logSupport.log).
        """
        self.data = {}  # not used
        self.updated = time.time()
        self.updated_year = time.localtime(self.updated)[0]
        self.current_stats_data = {}  # will contain dictionary client->username->dirSummarySimple
        self.old_stats_data = {}
        self.stats_diff = {}  # will contain the differences
        self.job_statuses = ("Running", "Idle", "Wait", "Held", "Completed", "Removed")  # const
        self.job_statuses_short = ("Running", "Idle", "Wait", "Held")  # const

        self.files_updated = None
        self.log = log

    def reset(self):
        """Reset the current statistics and prepare for a new iteration.

        This method replaces the old statistics data (`old_stats_data`) with the current statistics
        data (`current_stats_data`), resets the current statistics to an empty dictionary, and clears the differences.
        It is called at the beginning of each iteration to allow later to compare with the previous iteration
        and find any newly changed jobs (ie newly completed jobs).
        """
        # reserve only those that has been around this time
        new_stats_data = {}
        for c in list(self.stats_diff.keys()):
            # but carry over all the users... should not change that often
            new_stats_data[c] = self.current_stats_data[c]

        self.old_stats_data = new_stats_data
        self.current_stats_data = {}

        # and flush out the differences
        self.stats_diff = {}

    def diffTimes(self, end_time, start_time):
        """Compute the difference in seconds between two time strings.

        The time strings are expected to be in a format where the first two characters
        represent minutes (or similar) and so on; if a ValueError or TypeError occurs,
        -1 is returned.

        Args:
            end_time (str): The ending time string.
            start_time (str): The starting time string.

        Returns:
            int: The difference in seconds between end_time and start_time, or -1 if invalid.
        """
        year = self.updated_year
        try:
            start_list = [
                year,
                int(start_time[0:2]),
                int(start_time[3:5]),
                int(start_time[6:8]),
                int(start_time[9:11]),
                int(start_time[12:14]),
                0,
                0,
                -1,
            ]
            end_list = [
                year,
                int(end_time[0:2]),
                int(end_time[3:5]),
                int(end_time[6:8]),
                int(end_time[9:11]),
                int(end_time[12:14]),
                0,
                0,
                -1,
            ]
        except ValueError:
            return -1  # invalid

        try:
            start_ctime = time.mktime(start_list)
            end_ctime = time.mktime(end_list)
        except TypeError:
            return -1  # invalid

        if start_ctime <= end_ctime:
            return end_ctime - start_ctime

        # else must have gone over the year boundary
        start_list[0] -= 1  # decrease start year
        try:
            start_ctime = time.mktime(start_list)
        except TypeError:
            return -1  # invalid

        return end_ctime - start_ctime

    def logSummary(self, client_name, stats):
        """Merge log statistics from a new iteration of `perform_work()` into `current_stats_data`.

        Args:
            client_name (str): The client name.
            stats (dict): Dictionary keyed by "username:client_int_name" containing log statistics
                (expected to be from a glideFactoryLogParser.dirSummaryTimingsOut instance via its
                get_simple() method).
        """
        if client_name not in self.current_stats_data:
            self.current_stats_data[client_name] = {}

        for username in list(stats.keys()):
            if username not in self.current_stats_data[client_name]:
                self.current_stats_data[client_name][username] = stats[username].get_simple()
            else:
                self.current_stats_data[client_name][username].merge(stats[username])

        self.updated = time.time()
        self.updated_year = time.localtime(self.updated)[0]

    def computeDiff(self):
        """Compute the difference between the current and previous iterations of log data.

        This method compares `current_stats_data` with `old_stats_data` (set via reset())
        and populates `stats_diff` with two entries for each status ("Entered" and "Exited")
        indicating which job ids have recently changed status.

        Example:
            `stats_diff[frontend][username:client_int_name]["Completed"]["Entered"]`

        `self.stats_diff` is created or updated
        """
        for client_name in list(self.current_stats_data.keys()):
            self.stats_diff[client_name] = {}
            if client_name in self.old_stats_data:
                stats = self.current_stats_data[client_name]
                for username in list(stats.keys()):
                    if username in self.old_stats_data[client_name]:
                        self.stats_diff[client_name][username] = stats[username].diff(
                            self.old_stats_data[client_name][username]
                        )

    def get_stats_data_summary(self):
        """Summarize the current log statistics data by aggregating counts over usernames.

        Adds up `current_stats_data[frontend][user:client][status]` across all username keys.

        Returns:
            dict: A dictionary mapping each client (Frontend) to a dictionary of counts for each status.
                  For example: {client_name: {"Running": count, "Idle": count, ...}}
        """
        stats_data = {}
        for client_name in list(self.current_stats_data.keys()):
            out_el = {}
            for s in self.job_statuses:
                if s not in ("Completed", "Removed"):  # I don't have their numbers from inactive logs
                    count = 0
                    for username in list(self.current_stats_data[client_name].keys()):
                        client_el = self.current_stats_data[client_name][username].data
                        if (client_el is not None) and (s in list(client_el.keys())):
                            count += len(client_el[s])

                    out_el[s] = count
            stats_data[client_name] = out_el
        return stats_data

    def get_xml_stats_data(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        """Convert the summarized log statistics data into an XML string.

        Args:
            indent_tab (str, optional): Indentation string. Defaults to xmlFormat.DEFAULT_TAB.
            leading_tab (str, optional): Leading indentation string. Defaults to "".

        Returns:
            str: XML formatted statistics data.
        """
        data = self.get_stats_data_summary()
        return xmlFormat.dict2string(
            data,
            dict_name="frontends",
            el_name="frontend",
            subtypes_params={"class": {}},
            indent_tab=indent_tab,
            leading_tab=leading_tab,
        )

    # in: entered_list=self.stats_diff[*]['Entered']
    # out: entered_list[job_id]{'duration','condor_started','condor_duration','jobsnr','wastemill':{'validation','idle','nosuccess','badput'}}
    def get_completed_stats(self, entered_list):
        """Extract completed job statistics from a list of job entries.

        Each job entry in entered_list is expected to be a tuple where:
          - Index 0 is the job ID.
          - Index 2 is the job's running time.
          - Index 3 is the job's last time.
          - Index 4 is a dictionary of additional statistics.

        Args:
            entered_list (list): List of job entries for which to extract statistics.
                For example: `self.stats_diff[*]['Entered']`

        Returns:
            dict: Dictionary mapping job IDs to their statistics, including duration, condor info,
                  number of jobs, jobs duration breakdown, and waste metrics.
                  For example:
                    ```
                    entered_list[job_id]{'duration','condor_started','condor_duration','jobsnr',
                                         'wastemill':{'validation','idle','nosuccess','badput'}}
                    ```
        """
        out_list = {}

        for enle in entered_list:
            enle_job_id = enle[0]
            enle_running_time = enle[2]
            enle_last_time = enle[3]
            enle_difftime = self.diffTimes(enle_last_time, enle_running_time)

            # get stats
            enle_stats = enle[4]
            username = "unknown"
            enle_condor_started = 0
            enle_condor_duration = 0  # default is 0, in case it never started
            enle_glidein_duration = enle_difftime  # best guess
            if enle_stats is not None:
                enle_condor_started = enle_stats["condor_started"]
                if "glidein_duration" in enle_stats:
                    enle_glidein_duration = enle_stats["glidein_duration"]
                if "username" in enle_stats:
                    username = enle_stats["username"]
            if not enle_condor_started:
                # 100% waste_mill
                enle_nr_jobs = 0
                enle_jobs_duration = 0
                enle_goodput = 0
                enle_terminated_duration = 0
                enle_waste_mill = {
                    "validation": 1000,
                    "idle": 0,
                    "nosuccess": 0,  # no jobs run, no failures
                    "badput": 1000,
                }
            else:
                # get waste_mill
                enle_condor_duration = enle_stats["condor_duration"]
                if enle_condor_duration is None:
                    enle_condor_duration = 0  # assume failed

                if enle_condor_duration > enle_glidein_duration:  # can happen... Condor-G has its delays
                    enle_glidein_duration = enle_condor_duration

                # get waste numbers, in permill
                if enle_condor_duration < 5:  # very short means 100% loss
                    enle_nr_jobs = 0
                    enle_jobs_duration = 0
                    enle_goodput = 0
                    enle_terminated_duration = 0
                    enle_waste_mill = {
                        "validation": 1000,
                        "idle": 0,
                        "nosuccess": 0,  # no jobs run, no failures
                        "badput": 1000,
                    }
                else:
                    if "validation_duration" in enle_stats:
                        enle_validation_duration = enle_stats["validation_duration"]
                    else:
                        enle_validation_duration = enle_difftime - enle_condor_duration
                    enle_condor_stats = enle_stats["stats"]
                    enle_jobs_duration = enle_condor_stats["Total"]["secs"]
                    enle_nr_jobs = enle_condor_stats["Total"]["jobsnr"]
                    enle_waste_mill = {
                        "validation": 1000.0 * enle_validation_duration / enle_glidein_duration,
                        "idle": 1000.0 * (enle_condor_duration - enle_jobs_duration) / enle_condor_duration,
                    }
                    enle_goodput = enle_condor_stats["goodZ"]["secs"]
                    if enle_goodput > enle_jobs_duration:
                        enle_goodput = enle_jobs_duration  # cannot be more
                    if enle_jobs_duration > 0:
                        enle_waste_mill["nosuccess"] = 1000.0 * (enle_jobs_duration - enle_goodput) / enle_jobs_duration
                    else:
                        enle_waste_mill["nosuccess"] = 0  # no jobs run, no failures
                    enle_terminated_duration = enle_goodput + enle_condor_stats["goodNZ"]["secs"]
                    if enle_terminated_duration > enle_jobs_duration:
                        enle_terminated_duration = enle_jobs_duration  # cannot be more
                    enle_waste_mill["badput"] = (
                        1000.0 * (enle_glidein_duration - enle_terminated_duration) / enle_glidein_duration
                    )

            out_list[enle_job_id] = {
                "username": username,
                "duration": enle_glidein_duration,
                "condor_started": enle_condor_started,
                "condor_duration": enle_condor_duration,
                "jobsnr": enle_nr_jobs,
                "jobs_duration": {
                    "total": enle_jobs_duration,
                    "goodput": enle_goodput,
                    "terminated": enle_terminated_duration,
                },
                "wastemill": enle_waste_mill,
            }

        return out_list

    # in: entered_list=get_completed_data()
    # out: {'Lasted':{'2hours':...,...},'Sum':{...:12,...},'JobsNr':...,
    #       'Waste':{'validation':{'0m':...,...},...},'WasteTime':{...:{...},...}}
    def summarize_completed_stats(self, entered_list):
        """Summarize completed job statistics from a list of job entries.

        Args:
            entered_list (list): List of job entries (as returned by get_completed_stats).

        Returns:
            dict: A dictionary summarizing completed statistics with keys:
                - 'Lasted': counts of jobs by time range.
                - 'JobsNr': counts of jobs by job range.
                - 'Sum': overall totals.
                - 'JobsDuration': counts by job duration range.
                - 'Waste': waste metrics per category.
                - 'WasteTime': waste time metrics per category.
        """
        # summarize completed data
        count_entered_times = {}
        for enle_timerange in getAllTimeRanges():
            count_entered_times[enle_timerange] = 0  # make sure all are initialized

        count_jobnrs = {}
        for enle_jobrange in getAllJobRanges():
            count_jobnrs[enle_jobrange] = 0  # make sure all are initialized

        count_jobs_duration = {}
        for enle_jobs_duration_range in getAllTimeRanges():
            count_jobs_duration[enle_jobs_duration_range] = 0  # make sure all are initialized

        count_total = getLogCompletedDefaults()

        count_waste_mill = {
            "validation": {},
            "idle": {},
            "nosuccess": {},  # i.e. everything but jobs terminating with 0
            "badput": {},
        }  # i.e. everything but jobs terminating
        for w in list(count_waste_mill.keys()):
            count_waste_mill_w = count_waste_mill[w]
            for enle_waste_mill_w_range in getAllMillRanges():
                count_waste_mill_w[enle_waste_mill_w_range] = 0  # make sure all are initialized
        time_waste_mill = {
            "validation": {},
            "idle": {},
            "nosuccess": {},  # i.e. everything but jobs terminating with 0
            "badput": {},
        }  # i.e. everything but jobs terminating
        for w in list(time_waste_mill.keys()):
            time_waste_mill_w = time_waste_mill[w]
            for enle_waste_mill_w_range in getAllMillRanges():
                time_waste_mill_w[enle_waste_mill_w_range] = 0  # make sure all are initialized

        for enle_job in list(entered_list.keys()):
            enle = entered_list[enle_job]
            enle_waste_mill = enle["wastemill"]
            enle_glidein_duration = enle["duration"]
            enle_condor_duration = enle["condor_duration"]
            enle_jobs_nr = enle["jobsnr"]
            enle_jobs_duration = enle["jobs_duration"]
            enle_condor_started = enle["condor_started"]

            count_total["Glideins"] += 1
            if not enle_condor_started:
                count_total["FailedNr"] += 1

            # find and save time range
            count_total["Lasted"] += enle_glidein_duration
            enle_timerange = getTimeRange(enle_glidein_duration)
            count_entered_times[enle_timerange] += 1

            count_total["CondorLasted"] += enle_condor_duration

            # find and save job range
            count_total["JobsNr"] += enle_jobs_nr
            enle_jobrange = getJobRange(enle_jobs_nr)
            count_jobnrs[enle_jobrange] += 1

            if enle_jobs_nr > 0:
                enle_jobs_duration_range = getTimeRange(enle_jobs_duration["total"] // enle_jobs_nr)
            else:
                enle_jobs_duration_range = getTimeRange(-1)
            count_jobs_duration[enle_jobs_duration_range] += 1

            count_total["JobsLasted"] += enle_jobs_duration["total"]
            count_total["JobsTerminated"] += enle_jobs_duration["terminated"]
            count_total["JobsGoodput"] += enle_jobs_duration["goodput"]

            # find and save waste range
            for w in list(enle_waste_mill.keys()):
                if w == "duration":
                    continue  # not a waste
                # find and save time range
                enle_waste_mill_w_range = getMillRange(enle_waste_mill[w])

                count_waste_mill_w = count_waste_mill[w]
                count_waste_mill_w[enle_waste_mill_w_range] += 1

                time_waste_mill_w = time_waste_mill[w]
                time_waste_mill_w[enle_waste_mill_w_range] += enle_glidein_duration

        return {
            "Lasted": count_entered_times,
            "JobsNr": count_jobnrs,
            "Sum": count_total,
            "JobsDuration": count_jobs_duration,
            "Waste": count_waste_mill,
            "WasteTime": time_waste_mill,
        }

    def get_data_summary(self):
        """Summarize the differential statistics data across all clients.

        This method aggregates the stats_diff dictionary over all usernames for each client,
        resulting in a summary with counts for "Current", "Entered", and "Exited" for each status.

        Sums over username in the dictionary `stats_diff[frontend][username][entered/exited][status]`
        to make `stats_data[client_name][entered/exited][status]=count`.

        Returns:
            dict: Dictionary of summarized data in the form:
                  {client_name: {"Current": {...}, "Entered": {...}, "Exited": {...}}}
        """
        stats_data = {}
        for client_name in list(self.stats_diff.keys()):
            out_el = {"Current": {}, "Entered": {}, "Exited": {}}
            for s in self.job_statuses:
                entered = 0
                entered_list = []
                exited = 0
                for username in list(self.stats_diff[client_name].keys()):
                    diff_el = self.stats_diff[client_name][username]

                    if (diff_el is not None) and (s in list(diff_el.keys())):
                        entered_list += diff_el[s]["Entered"]
                        entered += len(diff_el[s]["Entered"])
                        exited -= len(diff_el[s]["Exited"])

                out_el["Entered"][s] = entered
                if s not in ("Completed", "Removed"):  # I don't have their numbers from inactive logs
                    count = 0
                    for username in list(self.current_stats_data[client_name].keys()):
                        stats_el = self.current_stats_data[client_name][username].data

                        if (stats_el is not None) and (s in list(stats_el.keys())):
                            count += len(stats_el[s])
                    out_el["Current"][s] = count
                    # and we can never get out of the terminal state
                    out_el["Exited"][s] = exited
                elif s == "Completed":
                    completed_stats = self.get_completed_stats(entered_list)
                    completed_counts = self.summarize_completed_stats(completed_stats)
                    out_el["CompletedCounts"] = completed_counts
            stats_data[client_name] = out_el
        return stats_data

    def get_xml_data(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        """Convert the summarized differential data to an XML formatted string.

        Args:
            indent_tab (str, optional): Indentation string. Defaults to xmlFormat.DEFAULT_TAB.
            leading_tab (str, optional): Leading indentation string. Defaults to "".

        Returns:
            str: XML formatted string of the summarized data.
        """
        data = self.get_data_summary()
        return xmlFormat.dict2string(
            data,
            dict_name="frontends",
            el_name="frontend",
            subtypes_params={"class": {"subclass_params": {"CompletedCounts": get_completed_stats_xml_desc()}}},
            indent_tab=indent_tab,
            leading_tab=leading_tab,
        )

    def get_stats_total(self):
        """Aggregate and return total statistics data for all clients.

        Returns:
            dict: Dictionary with keys (e.g. "Wait", "Idle", "Running", "Held") mapped to lists of data.
        """
        total = {"Wait": None, "Idle": None, "Running": None, "Held": None}
        for k in list(total.keys()):
            tdata = []
            for client_name in list(self.current_stats_data.keys()):
                for username in self.current_stats_data[client_name]:
                    sdata = self.current_stats_data[client_name][username].data
                    if (sdata is not None) and (k in list(sdata.keys())):
                        tdata = tdata + sdata[k]
            total[k] = tdata
        return total

    def get_stats_total_summary(self):
        """Compute a summary of the total statistics.

        Returns:
            dict: Dictionary mapping each status to the count of items in the total data.
        """
        in_total = self.get_stats_total()
        out_total = {}
        for k in list(in_total.keys()):
            out_total[k] = len(in_total[k])
        return out_total

    def get_xml_stats_total(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        """Convert the total statistics summary to an XML formatted string.

        Args:
            indent_tab (str, optional): Indentation string. Defaults to xmlFormat.DEFAULT_TAB.
            leading_tab (str, optional): Leading indentation string. Defaults to "".

        Returns:
            str: XML formatted string of the total statistics.
        """
        total = self.get_stats_total_summary()
        return xmlFormat.class2string(total, inst_name="total", indent_tab=indent_tab, leading_tab=leading_tab)

    def get_diff_summary(self):
        """Flatten and return the differential statistics (stats_diff) data.

        Returns:
            dict: A dictionary mapping client names to sub-dictionaries with keys "Wait", "Idle", "Running",
                  "Held", "Completed", and "Removed", each containing "Entered" and "Exited" lists.
        """
        out_data = {}
        for client_name in list(self.stats_diff.keys()):
            client_el = {"Wait": None, "Idle": None, "Running": None, "Held": None, "Completed": None, "Removed": None}
            for k in list(client_el.keys()):
                client_el[k] = {"Entered": [], "Exited": []}
                tdata = client_el[k]
                # flatten all usernames into one
                for username in list(self.stats_diff[client_name].keys()):
                    sdiff = self.stats_diff[client_name][username]
                    if (sdiff is not None) and (k in list(sdiff.keys())):
                        if k == "Completed":
                            # for completed jobs, add the username
                            # not for the others since there is no adequate place in the object
                            for sdel in sdiff[k]["Entered"]:
                                sdel[4]["username"] = username

                        for e in list(tdata.keys()):
                            for sdel in sdiff[k][e]:
                                tdata[e].append(sdel)  # pylint: disable=unsubscriptable-object
            out_data[client_name] = client_el
        return out_data

    def get_diff_total(self):
        """Aggregate the differential statistics across all clients.

        Returns:
            dict: Dictionary with keys "Wait", "Idle", "Running", "Held", "Completed", "Removed"
                  each containing aggregated "Entered" and "Exited" lists.
        """
        total = {"Wait": None, "Idle": None, "Running": None, "Held": None, "Completed": None, "Removed": None}
        for k in list(total.keys()):
            total[k] = {"Entered": [], "Exited": []}
            tdata = total[k]
            for client_name in list(self.stats_diff.keys()):
                for username in list(self.stats_diff[client_name].keys()):
                    sdiff = self.stats_diff[client_name][username]
                    if (sdiff is not None) and (k in list(sdiff.keys())):
                        for e in list(tdata.keys()):
                            tdata[e] = (  # pylint: disable=unsupported-assignment-operation
                                tdata[e] + sdiff[k][e]  # pylint: disable=unsubscriptable-object
                            )
        return total

    def get_total_summary(self):
        """Compute a total summary by combining current statistics with differential statistics.

        Returns:
            dict: Dictionary with keys "Current", "Entered", and "Exited" for each status.
        """
        stats_total = self.get_stats_total()
        diff_total = self.get_diff_total()
        out_total = {"Current": {}, "Entered": {}, "Exited": {}}
        for k in list(diff_total.keys()):
            out_total["Entered"][k] = len(diff_total[k]["Entered"])  # pylint: disable=unsubscriptable-object
            if k in stats_total:
                out_total["Current"][k] = len(stats_total[k])
                # if no current, also exited does not have sense (terminal state)
                out_total["Exited"][k] = len(diff_total[k]["Exited"])  # pylint: disable=unsubscriptable-object
            elif k == "Completed":
                completed_stats = self.get_completed_stats(
                    diff_total[k]["Entered"]  # pylint: disable=unsubscriptable-object
                )
                completed_counts = self.summarize_completed_stats(completed_stats)
                out_total["CompletedCounts"] = completed_counts

        return out_total

    def get_xml_total(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        """Convert the total summary to an XML formatted string.

        Args:
            indent_tab (str, optional): Indentation string. Defaults to xmlFormat.DEFAULT_TAB.
            leading_tab (str, optional): Leading indentation string. Defaults to "".

        Returns:
            str: XML formatted total summary.
        """
        total = self.get_total_summary()
        return xmlFormat.class2string(
            total,
            inst_name="total",
            subclass_params={"CompletedCounts": get_completed_stats_xml_desc()},
            indent_tab=indent_tab,
            leading_tab=leading_tab,
        )

    def get_xml_updated(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        """Return an XML formatted string of the last update time.

        Args:
            indent_tab (str, optional): Indentation string. Defaults to xmlFormat.DEFAULT_TAB.
            leading_tab (str, optional): Leading indentation string. Defaults to "".

        Returns:
            str: XML formatted update time.
        """
        return xmlFormat.time2xml(self.updated, "updated", indent_tab, leading_tab)

    def write_file(self, monitoringConfig=None):
        """Write a snapshot XML file, log_summary.xml, for the log summary data and update the corresponding RRDs.

        Args:
            monitoringConfig (MonitoringConfig, optional): Monitoring configuration object.
                Defaults to the global monitoringConfig.
        """
        if monitoringConfig is None:
            monitoringConfig = globals()["monitoringConfig"]

        if (self.files_updated is not None) and ((self.updated - self.files_updated) < 5):
            # files updated recently, no need to redo it
            return

        # write snapshot file
        xml_str = (
            '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
            + "<glideFactoryEntryLogSummary>\n"
            + self.get_xml_updated(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + self.get_xml_data(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + self.get_xml_total(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + "</glideFactoryEntryLogSummary>\n"
        )
        monitoringConfig.write_file("log_summary.xml", xml_str)

        # update rrds
        stats_data_summary = self.get_stats_data_summary()
        diff_summary = self.get_diff_summary()
        stats_total_summary = self.get_stats_total_summary()
        for client_name in [None] + list(diff_summary.keys()):
            if client_name is None:
                fe_dir = "total"
                sdata = stats_total_summary
                sdiff = self.get_diff_total()
            else:
                fe_dir = "frontend_" + client_name
                sdata = stats_data_summary[client_name]
                sdiff = diff_summary[client_name]

            monitoringConfig.establish_dir(fe_dir)
            val_dict_counts = {}
            val_dict_counts_desc = {}
            val_dict_completed = {}
            val_dict_stats = {}
            val_dict_waste = {}
            val_dict_wastetime = {}
            for s in self.job_statuses:
                if s not in ("Completed", "Removed"):  # I don't have their numbers from inactive logs
                    count = sdata[s]
                    val_dict_counts["Status%s" % s] = count
                    val_dict_counts_desc["Status%s" % s] = {"ds_type": "GAUGE"}

                if (sdiff is not None) and (s in list(sdiff.keys())):
                    entered_list = sdiff[s]["Entered"]
                    entered = len(entered_list)
                    exited = -len(sdiff[s]["Exited"])
                else:
                    entered_list = []
                    entered = 0
                    exited = 0

                val_dict_counts["Entered%s" % s] = entered
                val_dict_counts_desc["Entered%s" % s] = {"ds_type": "ABSOLUTE"}
                if s not in ("Completed", "Removed"):  # Always 0 for them
                    val_dict_counts["Exited%s" % s] = exited
                    val_dict_counts_desc["Exited%s" % s] = {"ds_type": "ABSOLUTE"}
                elif s == "Completed":
                    completed_stats = self.get_completed_stats(entered_list)
                    if client_name is not None:  # do not repeat for total
                        monitoringConfig.logCompleted(client_name, completed_stats)
                    completed_counts = self.summarize_completed_stats(completed_stats)

                    # save simple vals
                    for tkey in list(completed_counts["Sum"].keys()):
                        val_dict_completed[tkey] = completed_counts["Sum"][tkey]

                    count_entered_times = completed_counts["Lasted"]
                    count_jobnrs = completed_counts["JobsNr"]
                    count_jobs_duration = completed_counts["JobsDuration"]
                    count_waste_mill = completed_counts["Waste"]
                    time_waste_mill = completed_counts["WasteTime"]
                    # save run times
                    for timerange in list(count_entered_times.keys()):
                        val_dict_stats["Lasted_%s" % timerange] = count_entered_times[timerange]
                        # they all use the same indexes
                        val_dict_stats["JobsLasted_%s" % timerange] = count_jobs_duration[timerange]

                    # save jobsnr
                    for jobrange in list(count_jobnrs.keys()):
                        val_dict_stats["JobsNr_%s" % jobrange] = count_jobnrs[jobrange]

                    # save waste_mill
                    for w in list(count_waste_mill.keys()):
                        count_waste_mill_w = count_waste_mill[w]
                        for p in list(count_waste_mill_w.keys()):
                            val_dict_waste[f"{w}_{p}"] = count_waste_mill_w[p]

                    for w in list(time_waste_mill.keys()):
                        time_waste_mill_w = time_waste_mill[w]
                        for p in list(time_waste_mill_w.keys()):
                            val_dict_wastetime[f"{w}_{p}"] = time_waste_mill_w[p]

            # end for s in self.job_statuses

            # write the data to disk
            monitoringConfig.write_rrd_multi_hetero(
                os.path.join(fe_dir, "Log_Counts"), val_dict_counts_desc, self.updated, val_dict_counts
            )
            monitoringConfig.write_rrd_multi(
                os.path.join(fe_dir, "Log_Completed"), "ABSOLUTE", self.updated, val_dict_completed
            )
            monitoringConfig.write_completed_json(
                os.path.join(fe_dir, "Log_Completed"), self.updated, val_dict_completed
            )
            monitoringConfig.write_rrd_multi(
                os.path.join(fe_dir, "Log_Completed_Stats"), "ABSOLUTE", self.updated, val_dict_stats
            )
            monitoringConfig.write_completed_json(
                os.path.join(fe_dir, "Log_Completed_Stats"), self.updated, val_dict_stats
            )
            # Disable Waste RRDs... WasteTime much more useful
            # monitoringConfig.write_rrd_multi(os.path.join(fe_dir, "Log_Completed_Waste"),
            #                                 "ABSOLUTE",self.updated,val_dict_waste)
            monitoringConfig.write_rrd_multi(
                os.path.join(fe_dir, "Log_Completed_WasteTime"), "ABSOLUTE", self.updated, val_dict_wastetime
            )
            monitoringConfig.write_completed_json(
                os.path.join(fe_dir, "Log_Completed_WasteTime"), self.updated, val_dict_wastetime
            )

        self.aggregate_frontend_data(self.updated, diff_summary)

        self.files_updated = self.updated
        return

    def aggregate_frontend_data(self, updated, diff_summary):
        """Aggregate frontend log data from individual Frontends into a single entry level file.

        Aggregates the completed/stats/wastetime data into completed_data.json.

        Args:
            updated (float): The update timestamp.
            diff_summary (dict): Differential summary data from get_diff_summary().
        """
        entry_data = {"frontends": {}}

        for frontend in list(diff_summary.keys()):
            fe_dir = "frontend_" + frontend

            completed_filename = os.path.join(monitoringConfig.monitor_dir, fe_dir, "Log_Completed.json")
            completed_stats_filename = os.path.join(monitoringConfig.monitor_dir, fe_dir, "Log_Completed_Stats.json")
            completed_wastetime_filename = os.path.join(
                monitoringConfig.monitor_dir, fe_dir, "Log_Completed_WasteTime.json"
            )

            try:
                with open(completed_filename) as completed_fp:
                    completed_data = json.load(completed_fp)
                with open(completed_stats_filename) as completed_stats_fp:
                    completed_stats_data = json.load(completed_stats_fp)
                with open(completed_wastetime_filename) as completed_wastetime_fp:
                    completed_wastetime_data = json.load(completed_wastetime_fp)

                entry_data["frontends"][frontend] = {
                    "completed": completed_data,
                    "completed_stats": completed_stats_data,
                    "completed_wastetime": completed_wastetime_data,
                }
            except OSError as e:
                self.log.info("Could not find files to aggregate in frontend %s" % fe_dir)
                self.log.info(str(e))
                continue

        monitoringConfig.write_completed_json("completed_data", updated, entry_data)

    def write_job_info(self, scheddName, collectorName):
        """Extract and write job monitoring information for completed jobs.

        This method iterates over the differential statistics (stats_diff) and collects monitoring
        information for completed jobs. It then completes a dictionary with the following keys and
        writes it into a pickle file:
            - 'schedd_name': scheddName
            - 'collector_name': collectorName
            - 'joblist': A dictionary mapping job IDs to monitoring information (condor_duration, glidein_duration,
              condor_started, numjobs, activation_claims, etc.).

        Example dictionary:
        ```
        {
            'schedd_name': 'name',
            'collector_name': 'name',
            'joblist' : {
                '2994.000': {'condor_duration': 1328, 'glidein_duration': 1334, 'condor_started': 1, 'numjobs': 0,
                '2997.000': {'condor_duration': 1328, 'glidein_duration': 1334, 'condor_started': 1, 'numjobs': 0
                ...
            }
        }
        ```

        Args:
            scheddName (str): The HTCondor schedd name.
            collectorName (str): The collector name.
        """
        jobinfo = {
            "schedd_name": scheddName,
            "collector_name": collectorName,
            "joblist": {},
        }
        for _sec_name, sndata in self.stats_diff.items():
            for _frname, frdata in sndata.items():
                for state, jobs in frdata.items():
                    if state == "Completed":
                        for job in jobs["Entered"]:
                            jobid = job[0]
                            jobstats = job[4]
                            # This is the dictionary that is going to be written out as a monitoring classad
                            jobinfo["joblist"][jobid] = {
                                # activation_claims is a new key in 3.2.19. Using "get" For backward compatiobility,
                                # but it can be removed in future versions
                                "activation_claims": jobstats.get("activations_claims", "unknown"),
                                "glidein_duration": jobstats["glidein_duration"],
                                # condor_duration could be missing if the glidein had problems and condor was not started
                                # set it to 0
                                # and set condor_started to None if missing
                                "condor_duration": jobstats.get("condor_duration", 0),
                                "condor_started": jobstats.get("condor_started", None),
                                "numjobs": jobstats.get("stats", {}).get("Total", {}).get("jobsnr", "unknown"),
                            }

        # cannot use monitorAggregatorConfig.jobsummary_relname, looks like a circular import
        monitoringConfig.write_file("job_summary.pkl", pickle.dumps(jobinfo))


###############################################################################
#
# factoryStatusData
# added by C.W. Murphy starting on 08/09/10
# this class handles the data obtained from the rrd files
#
###############################################################################


class FactoryStatusData:
    """Handles data obtained from RRD files for the Factory status.

    Attributes:
        data (dict): Dictionary to store RRD data.
        updated (float): Last update timestamp.
        tab (str): Indentation string for XML formatting.
        resolution (tuple): Tuple of resolutions (in seconds).
        total (str): Identifier for total data.
        frontends (list): List of frontend identifiers.
        base_dir (str): Base directory for monitoring data.
        log (logging.Logger): Logger instance.
    """

    def __init__(self, log=logSupport.log, base_dir=None):
        """Initialize FactoryStatusData object with default values.

        Args:
            log (logging.Logger): Logger instance.
            base_dir (str, optional): Base directory for monitoring files. Defaults to monitorAggregatorConfig.monitor_dir.
        """
        self.data = {}
        for rrd in RRD_LIST:
            self.data[rrd] = {}
        # KEL why are we setting time here and not just getting the current time (like in Descript2XML)
        self.updated = time.time()
        self.tab = xmlFormat.DEFAULT_TAB
        self.resolution = (7200, 86400, 604800)  # 2hr, 1 day, 1 week
        self.total = "total/"
        self.frontends = []
        if base_dir is None:
            self.base_dir = monitoringConfig.monitor_dir
        self.log = log

    def getUpdated(self):
        """Return an XML formatted string representing the last update time.

        Returns:
            str: XML formatted update time.
        """
        return xmlFormat.time2xml(self.updated, "updated", indent_tab=self.tab, leading_tab=self.tab)

    def fetchData(self, rrd_file, pathway, res, start, end):
        """Fetch data from an RRD file using rrdtool.

        rrdtool fetch returns 3 tuples: a[0], a[1], and a[2].
        [0] lists the resolution, start and end time, which can be specified as arguments of fetchData.
        [1] returns the names of the datasets.  These names are listed in the key.
        [2] is a list of tuples. each tuple contains data from every dataset.  There is a tuple for each time data was collected.

        Args:
            rrd_file (str): The RRD file name.
            pathway (str): The path to the RRD file.
            res (int): Resolution.
            start (int): Start time.
            end (int): End time.

        Returns:
            dict: Dictionary with dataset names as keys and lists of data as values. There is a list for each element.
        """
        # use rrdtool to fetch data
        baseRRDSupport = rrdSupport.rrdSupport()
        try:
            fetched = baseRRDSupport.fetch_rrd(pathway + rrd_file, "AVERAGE", resolution=res, start=start, end=end)
        except Exception:
            # probably not created yet
            self.log.debug("Failed to load %s" % (pathway + rrd_file))
            return {}

        # converts fetched from tuples to lists
        fetched_names = list(fetched[1])

        fetched_data_raw = fetched[2][
            :-1
        ]  # drop the last entry... rrdtool will return one more than needed, and often that one is unreliable (in the python version)
        fetched_data = []
        for data in fetched_data_raw:
            fetched_data.append(list(data))

        # creates a dictionary to be filled with lists of data
        data_sets = {}
        for name in fetched_names:
            data_sets[name] = []

        # check to make sure the data exists
        all_empty = True
        for data_set in data_sets:
            index = fetched_names.index(data_set)
            for data in fetched_data:
                if isinstance(data[index], (int, float)):
                    data_sets[data_set].append(data[index])
                    all_empty = False

        if all_empty:
            # probably not updated recently
            return {}
        else:
            return data_sets

    def average(self, input_list):
        """Calculate the average of a list of numbers.

        Args:
            input_list (list): A list of numeric values.

        Returns:
            float: The average value, or 0 if the list is empty.
        """
        try:
            if len(input_list) > 0:
                avg_list = sum(input_list) / len(input_list)
            else:
                avg_list = 0
            return avg_list
        except TypeError:
            self.log.exception("glideFactoryMonitoring average: ")
            return

    def getData(self, input_val, monitoringConfig=None):
        """Retrieve RRD data for the specified client fetched by rrdtool.

        This function updates the internal RRD data dictionary for the client and
        appends the client to the list of frontends if not there. It also returns the data dictionary.

        Where this side effect is used:
        - totals are updated in Entry.writeStats (writing the XML)
        - frontend data in check_and_perform_work

        Args:
            input_val (str): The data identifier (totals or a client).
            monitoringConfig (MonitoringConfig, optional): Monitoring configuration. Defaults to global monitoringConfig.

        Returns:
            dict: Dictionary containing the RRD data.
        """
        if monitoringConfig is None:
            monitoringConfig = globals()["monitoringConfig"]

        folder = str(input_val)
        if folder == self.total:
            client = folder
        else:
            folder_name = folder.split("@")[-1]
            client = folder_name.join(["frontend_", "/"])
            if client not in self.frontends:
                self.frontends.append(client)

        for rrd in RRD_LIST:
            self.data[rrd][client] = {}
            for res_raw in self.resolution:
                # calculate the best resolution
                res_idx = 0
                rrd_res = monitoringConfig.rrd_archives[res_idx][2] * monitoringConfig.rrd_step
                period_mul = int(res_raw / rrd_res)
                while period_mul >= monitoringConfig.rrd_archives[res_idx][3]:
                    # not all elements in the higher bucket, get next lower resolution
                    res_idx += 1
                    rrd_res = monitoringConfig.rrd_archives[res_idx][2] * monitoringConfig.rrd_step
                    period_mul = int(res_raw / rrd_res)

                period = period_mul * rrd_res

                self.data[rrd][client][period] = {}
                end = (
                    int(time.time() / rrd_res) - 1
                ) * rrd_res  # round due to RRDTool requirements, -1 to avoid the last (partial) one
                start = end - period
                try:
                    fetched_data = self.fetchData(
                        rrd_file=rrd, pathway=self.base_dir + "/" + client, start=start, end=end, res=rrd_res
                    )
                    for data_set in fetched_data:
                        self.data[rrd][client][period][data_set] = self.average(fetched_data[data_set])
                except TypeError:
                    self.log.exception("FactoryStatusData:fetchData: ")

        return self.data

    def getXMLData(self, rrd):
        """Return an XML formatted string for the specified RRD data (all clients and total from a given site).

        This method also triggers the side effect of updating the internal total data (from `getData(self.total)`):
        - modifies the rrd data dictionary (all RRDs) for the total for this entry
        - and appends the total (self.total aka 'total/') to the list of clients (frontends)

        Args:
            rrd (str): The RRD file name.

        Returns:
            str: XML formatted string of the RRD data.
        """
        # create a string containing the total data
        total_xml_str = self.tab + "<total>\n"
        # this is invoked to trigger the side effect but the data is retrieved directly from self.data dict below
        get_data_total = self.getData(self.total)  # noqa: F841  # keep, side effect needed
        try:
            total_data = self.data[rrd][self.total]
            total_xml_str += (
                xmlFormat.dict2string(
                    total_data,
                    dict_name="periods",
                    el_name="period",
                    subtypes_params={"class": {}},
                    indent_tab=self.tab,
                    leading_tab=2 * self.tab,
                )
                + "\n"
            )
        except (NameError, UnboundLocalError):
            self.log.exception("FactoryStatusData:total_data: ")
        total_xml_str += self.tab + "</total>\n"

        # create a string containing the frontend data
        frontend_xml_str = self.tab + "<frontends>\n"
        for frontend in self.frontends:
            fe_name = frontend.split("/")[0]
            frontend_xml_str += 2 * self.tab + '<frontend name="' + fe_name + '">\n'
            try:
                frontend_data = self.data[rrd][frontend]
                frontend_xml_str += (
                    xmlFormat.dict2string(
                        frontend_data,
                        dict_name="periods",
                        el_name="period",
                        subtypes_params={"class": {}},
                        indent_tab=self.tab,
                        leading_tab=3 * self.tab,
                    )
                    + "\n"
                )
            except (NameError, UnboundLocalError):
                self.log.exception("FactoryStatusData:frontend_data: ")
            frontend_xml_str += 2 * self.tab + "</frontend>"
        frontend_xml_str += self.tab + "</frontends>\n"

        data_str = total_xml_str + frontend_xml_str
        return data_str

    def writeFiles(self, monitoringConfig=None):
        """Write XML and RRD files for the site (Factory entry) status data.

        This method writes an XML file for the fetched data and updates the RRD files.

        NOTE: this method triggers the side effect of updating the rrd for totals (via getXMLData/getData)

        Args:
            monitoringConfig (MonitoringConfig, optional): The monitoring configuration object. Defaults to global monitoringConfig.
        """
        if monitoringConfig is None:
            monitoringConfig = globals()["monitoringConfig"]

        for rrd in RRD_LIST:
            file_name = "rrd_" + rrd.split(".")[0] + ".xml"
            xml_str = (
                '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
                + "<glideFactoryEntryRRDStats>\n"
                + self.getUpdated()
                + "\n"
                + self.getXMLData(rrd)
                + "</glideFactoryEntryRRDStats>"
            )
            try:
                monitoringConfig.write_file(file_name, xml_str)
            except OSError:
                self.log.exception("FactoryStatusData:write_file: ")
        return


##############################################################################
#
#  create an XML file out of glidein.descript, frontend.descript,
#    entry.descript, attributes.cfg, and params.cfg
#
#############################################################################


class Descript2XML:
    """Create the descript.xml XML file from configuration files.

    This class creates an XML file using data from glidein.descript, frontend.descript,
    entry.descript, attributes.cfg, and params.cfg. The resulting XML file will contain
    the elements glideFactoryDescript and glideFactoryEntryDescript.

    TODO: The XML is used by ... "the monioring page"?

    Attributes:
        tab (str): Indentation string for XML formatting.
        entry_descript_blacklist (tuple): Keys to remove from entry descriptions.
        frontend_blacklist (tuple): Keys to remove from frontend descriptions.
        glidein_whitelist (tuple): Keys to include from the glidein description.
        log (logging.Logger): Logger instance.
    """

    def __init__(self, log=logSupport.log):
        """Initialize a Descript2XML object with default blacklists and whitelists."""
        self.tab = xmlFormat.DEFAULT_TAB
        self.entry_descript_blacklist = ("DowntimesFile", "EntryName", "Schedd")
        self.frontend_blacklist = ("usermap",)
        self.glidein_whitelist = (
            "AdvertiseDelay",
            "FactoryName",
            "GlideinName",
            "LoopDelay",
            "PubKeyType",
            "WebURL",
            "MonitorDisplayText",
            "MonitorLink",
        )
        self.log = log

    def frontendDescript(self, fe_dict):
        """Process the frontend description dictionary by removing blacklisted keys and convert it to XML.

        Args:
            fe_dict (dict): Dictionary of frontend descriptions.

        Returns:
            str: XML formatted string of frontend descriptions.
        """
        for key in self.frontend_blacklist:
            try:
                for frontend in fe_dict:
                    try:
                        del fe_dict[frontend][key]
                    except KeyError:
                        continue
            except RuntimeError:
                self.log.exception("blacklist error frontendDescript: ")
        try:
            xml_str = xmlFormat.dict2string(
                fe_dict, dict_name="frontends", el_name="frontend", subtypes_params={"class": {}}, leading_tab=self.tab
            )
            return xml_str + "\n"
        except RuntimeError:
            self.log.exception("xmlFormat error in frontendDescript: ")
            return

    def entryDescript(self, e_dict):
        """Process the entry description dictionary by removing blacklisted keys and convert it to XML.

        Args:
            e_dict (dict): Dictionary of entry descriptions.

        Returns:
            str: XML formatted string of entry descriptions.
        """
        for key in self.entry_descript_blacklist:
            try:
                for entry in e_dict:
                    try:
                        del e_dict[entry]["descript"][key]
                    except KeyError:
                        continue
            except RuntimeError:
                self.log.exception("blacklist error in entryDescript: ")
        try:
            xml_str = xmlFormat.dict2string(
                e_dict,
                dict_name="entries",
                el_name="entry",
                subtypes_params={"class": {"subclass_params": {}}},
                leading_tab=self.tab,
            )
            return xml_str + "\n"
        except RuntimeError:
            self.log.exception("xmlFormat Error in entryDescript: ")
            return

    def glideinDescript(self, g_dict):
        """Process the glidein description dictionary, filtering by the whitelist, and convert it to XML.

        Args:
            g_dict (dict): Glidein description dictionary.

        Returns:
            str: XML formatted string for the glidein description.
        """
        w_dict = {}
        for key in self.glidein_whitelist:
            try:
                w_dict[key] = g_dict[key]
            except KeyError:
                continue
        try:
            a = xmlFormat.dict2string(
                {"": w_dict}, dict_name="glideins", el_name="factory", subtypes_params={"class": {}}
            )
            b = a.split("\n")[1]
            c = b.split('name="" ')
            xml_str = "".join(c)
            return xml_str + "\n"
        except (SyntaxError, RuntimeError):
            logSupport.log.exception("xmlFormat error in glideinDescript: ")
            return

    def getUpdated(self):
        """Return an XML formatted string representing the time of last update (current time).

        Returns:
            str: XML string with the current update time.
        """
        return xmlFormat.time2xml(time.time(), "updated", indent_tab=self.tab, leading_tab=self.tab)

    def writeFile(self, path, xml_str, singleEntry=False):
        """Write the XML content to the descript.xml file.

        Args:
            path (str): Directory path where the file will be written.
            xml_str (str): The XML content.
            singleEntry (bool, optional): If True, use "glideFactoryEntryDescript" as root element;
                otherwise use "glideFactoryDescript". Defaults to False.
        """
        if singleEntry:
            root_el = "glideFactoryEntryDescript"
        else:
            root_el = "glideFactoryDescript"
        output = (
            '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
            + "<"
            + root_el
            + ">\n"
            + self.getUpdated()
            + "\n"
            + xml_str
            + "</"
            + root_el
            + ">"
        )
        fname = path + "descript.xml"
        with open(fname + ".tmp", "wb") as f:
            f.write(output.encode("utf-8"))

        util.file_tmp2final(fname)
        return


############### P R I V A T E ################


##################################################
def getAllJobTypes():
    """Return a tuple of all job types.

    Returns:
        tuple: ("validation", "idle", "badput", "nosuccess")
    """
    return ("validation", "idle", "badput", "nosuccess")


def getLogCompletedDefaults():
    """Return default values for completed log statistics, all set to 0.

    Returns:
        dict: Default completed statistics.
    """
    return {
        "Glideins": 0,
        "Lasted": 0,
        "FailedNr": 0,
        "JobsNr": 0,
        "JobsLasted": 0,
        "JobsTerminated": 0,
        "JobsGoodput": 0,
        "CondorLasted": 0,
    }


def getTimeRange(absval):
    """Return a time range label based on the absolute value.

    Args:
        absval (int): Absolute time value.

    Returns:
        str: A label such as "Minutes", "Days", or a formatted string.
    """
    if absval < 1:
        return "Unknown"
    if absval < (25 * 60):
        return "Minutes"
    if absval > (64 * 3600):  # limit detail to 64 hours
        return "Days"
    # start with 7.5 min, and than exp2
    logval = int(math.log(absval / 450.0, 4) + 0.49)
    level = math.pow(4, logval) * 450.0
    if level < 3600:
        return "%imins" % (int(level / 60 + 0.49))
    else:
        return "%ihours" % (int(level / 3600 + 0.49))


def getAllTimeRanges():
    """Return a tuple of all time range labels.

    Returns:
        tuple: ("Unknown", "Minutes", "30mins", "2hours", "8hours", "32hours", "Days")
    """
    return "Unknown", "Minutes", "30mins", "2hours", "8hours", "32hours", "Days"


def getJobRange(absval):
    """Return a job range label based on the absolute value.

    Args:
        absval (int): Absolute job number.

    Returns:
        str: A label such as "1job", "2jobs", "4jobs", etc.
    """
    if absval < 1:
        return "None"
    if absval == 1:
        return "1job"
    if absval == 2:
        return "2jobs"
    if absval < 9:
        return "4jobs"
    if absval < 30:  # limit detail to 30 jobs
        return "16jobs"
    else:
        return "Many"


def getAllJobRanges():
    """Return a tuple of all job range labels.

    Returns:
        tuple: ("None", "1job", "2jobs", "4jobs", "16jobs", "Many")
    """
    return "None", "1job", "2jobs", "4jobs", "16jobs", "Many"


def getMillRange(absval):
    """Return a minutes (mill) range label based on the absolute value.

    Args:
        absval (int): Absolute mill value.

    Returns:
        str: A label such as "5m", "25m", "100m", etc.
    """
    if absval < 2:
        return "None"
    if absval < 15:
        return "5m"
    if absval < 60:
        return "25m"
    if absval < 180:
        return "100m"
    if absval < 400:
        return "250m"
    if absval < 700:
        return "500m"
    if absval > 998:
        return "All"
    else:
        return "Most"


def getAllMillRanges():
    """Return a tuple of all minutes (mill) range labels.

    Returns:
        tuple: ("None", "5m", "25m", "100m", "250m", "500m", "Most", "All")
    """
    return "None", "5m", "25m", "100m", "250m", "500m", "Most", "All"


##################################################
def get_completed_stats_xml_desc():
    """Return a dictionary describing the XML structure for completed stats.

    Returns:
        dict: XML descriptor for completed stats.
    """
    return {
        "dicts_params": {
            "Lasted": {"el_name": "TimeRange"},
            "JobsDuration": {"el_name": "TimeRange"},
            "JobsNr": {"el_name": "Range"},
        },
        "subclass_params": {
            "Waste": {
                "dicts_params": {
                    "idle": {"el_name": "Fraction"},
                    "validation": {"el_name": "Fraction"},
                    "badput": {"el_name": "Fraction"},
                    "nosuccess": {"el_name": "Fraction"},
                }
            },
            "WasteTime": {
                "dicts_params": {
                    "idle": {"el_name": "Fraction"},
                    "validation": {"el_name": "Fraction"},
                    "badput": {"el_name": "Fraction"},
                    "nosuccess": {"el_name": "Fraction"},
                }
            },
        },
    }


##################################################
# global configuration of the module
monitoringConfig = MonitoringConfig()
