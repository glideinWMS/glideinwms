# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements the functions needed to aggregate the monitoring of the Glidein Factory."""

import json
import os.path
import pickle
import time

from glideinwms.factory import glideFactoryMonitoring
from glideinwms.lib import logSupport, rrdSupport, xmlFormat, xmlParse

############################################################
#
# Configuration
#
############################################################


class MonitorAggregatorConfig:
    """Configuration for aggregating monitoring data.

    Attributes:
        monitor_dir (str): Directory where monitoring files are located.
        entries (list): List of entry names.
        status_relname (str): Filename for the status file.
        logsummary_relname (str): Filename for the log summary file.
        jobsummary_relname (str): Filename for the job summary pickle file.
        completed_data_relname (str): Filename for the completed data JSON file.
    """

    def __init__(self):
        """Initializes a new MonitorAggregatorConfig with default values."""
        # The name of the attribute that identifies the glidein
        self.monitor_dir = "monitor/"

        # list of entries
        self.entries = []

        # name of the status files
        self.status_relname = "schedd_status.xml"
        self.logsummary_relname = "log_summary.xml"
        self.jobsummary_relname = "job_summary.pkl"
        self.completed_data_relname = "completed_data.json"

    def config_factory(self, monitor_dir, entries, log):
        """Configure factory monitoring parameters.

        Args:
            monitor_dir (str): The monitoring directory.
            entries (list): The list of entry names.
            log (logging.Logger): Logger to use for monitoring.
        """
        self.monitor_dir = monitor_dir
        self.entries = entries
        glideFactoryMonitoring.monitoringConfig.monitor_dir = monitor_dir
        glideFactoryMonitoring.monitoringConfig.log = log
        self.log = log


# global configuration of the module
monitorAggregatorConfig = MonitorAggregatorConfig()


def rrd_site(name):
    """Return the RRD filename for a given site.

    Args:
        name (str): A name string that typically contains a dot. The first part is until the first dot.

    Returns:
        str: The RRD filename in the format "rrd_<first_part_of_name>.xml".
    """
    sname = name.split(".")[0]
    return "rrd_%s.xml" % sname


###########################################################
#
# Functions
#
###########################################################

status_attributes = {
    "Status": ("Idle", "Running", "Held", "Wait", "Pending", "StageIn", "IdleOther", "StageOut", "RunningCores"),
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
type_strings = {"Status": "Status", "Requested": "Req", "ClientMonitor": "Client"}

##############################################################################
# Function used by Factory reconfig/upgrade
# No logging available, output is to stdout/err


def verifyRRD(fix_rrd=False, backup=True):
    """Verify that all known monitoring RRDs match the existing schema.

    If the schema does not match (could be different if an upgrade happened) and fix_rrd is True,
    this function will attempt to add any missing attributes.
    Optionally, the old RRD is backed up before any modifications if backup is True.

    Args:
        fix_rrd (bool): If True, will attempt to add missing attributes.
        backup (bool): If True, backup the old RRD before fixing.

    Returns:
        bool: True if all RRD files are OK; False if there is a problem.
    """
    rrd_problems_found = False
    mon_dir = monitorAggregatorConfig.monitor_dir
    # Factory monitoring dictionaries
    status_dict = {}
    completed_stats_dict = {}
    completed_waste_dict = {}
    counts_dict = {}
    # initialize the RRD dictionaries to match the current schema for verification
    for tp in list(status_attributes.keys()):
        if tp in list(type_strings.keys()):
            tp_str = type_strings[tp]
            attributes_tp = status_attributes[tp]
            for a in attributes_tp:
                status_dict[f"{tp_str}{a}"] = None
    for jobrange in glideFactoryMonitoring.getAllJobRanges():
        completed_stats_dict[f"JobsNr_{jobrange}"] = None
    for timerange in glideFactoryMonitoring.getAllTimeRanges():
        completed_stats_dict[f"Lasted_{timerange}"] = None
        completed_stats_dict[f"JobsLasted_{timerange}"] = None
    for jobtype in glideFactoryMonitoring.getAllJobTypes():
        for timerange in glideFactoryMonitoring.getAllMillRanges():
            completed_waste_dict[f"{jobtype}_{timerange}"] = None
    for jobtype in ("Entered", "Exited", "Status"):
        for jobstatus in ("Wait", "Idle", "Running", "Held"):
            counts_dict[f"{jobtype}{jobstatus}"] = None
    for jobstatus in ("Completed", "Removed"):
        counts_dict[f"Entered{jobstatus}"] = None
    completed_dict = glideFactoryMonitoring.getLogCompletedDefaults()
    rrdict = {
        "Status_Attributes.rrd": status_dict,
        "Log_Completed.rrd": completed_dict,
        "Log_Completed_Stats.rrd": completed_stats_dict,
        "Log_Completed_WasteTime.rrd": completed_waste_dict,
        "Log_Counts.rrd": counts_dict,
    }
    # check all the existing files
    if not os.path.isdir(mon_dir):
        print(f"WARNING: monitor directory '{mon_dir}' does not exist, skipping rrd verification.")
        return True
    for dir_name, sdir_name, f_list in os.walk(mon_dir):
        for file_name in f_list:
            if file_name in list(rrdict.keys()):
                if rrdSupport.verifyHelper(os.path.join(dir_name, file_name), rrdict[file_name], fix_rrd, backup):
                    rrd_problems_found = True
    return not rrd_problems_found


##############################################################################
def aggregateStatus(in_downtime):
    """Aggregate status files and return overall status information.

    This function creates an aggregate of individual status files, writes it to an aggregate status file,
    and returns a dictionary containing the aggregate status information.

    Args:
        in_downtime (bool): Entry downtime information.

    Returns:
        dict: Dictionary of aggregated status information.
    """
    global monitorAggregatorConfig

    avgEntries = ("InfoAge",)

    global_total = {"Status": None, "Requested": None, "ClientMonitor": None}
    status = {"entries": {}, "total": global_total}
    status_fe = {"frontends": {}}  # analogous to above but for frontend totals
    completed_data_tot = {"entries": {}}

    # initialize the RRD dictionary, so it gets created properly
    val_dict = {}
    for tp in global_total:
        # values (RRD type) - Status or Requested
        if tp not in list(status_attributes.keys()):
            continue

        tp_str = type_strings[tp]

        attributes_tp = status_attributes[tp]
        for a in attributes_tp:
            val_dict[f"{tp_str}{a}"] = None

    nr_entries = 0
    nr_feentries = {}  # dictionary for nr entries per fe
    for entry in monitorAggregatorConfig.entries:
        # load entry status file
        status_fname = os.path.join(
            monitorAggregatorConfig.monitor_dir, f"entry_{entry}", monitorAggregatorConfig.status_relname
        )
        # load entry completed data file
        completed_data_fname = os.path.join(
            monitorAggregatorConfig.monitor_dir,
            f"entry_{entry}",
            monitorAggregatorConfig.completed_data_relname,
        )
        completed_data_fp = None
        try:
            # entry_data is a regular dictionary of nested dictionaries/lists returned form the XML parsed
            entry_data = xmlParse.xmlfile2dict(status_fname)
            completed_data_fp = open(completed_data_fname)
            completed_data = json.load(completed_data_fp)
        except OSError:
            continue  # file not found, ignore
        finally:
            if completed_data_fp:
                completed_data_fp.close()

        # update entry
        status["entries"][entry] = {"downtime": entry_data["downtime"], "frontends": entry_data["frontends"]}

        # update completed data
        completed_data_tot["entries"][entry] = completed_data["stats"]

        # to log when total dictionary is modified (in update total/frontend)
        tmp_list_removed = []

        # update total
        if "total" in entry_data:
            nr_entries += 1
            status["entries"][entry]["total"] = entry_data["total"]

            for w in list(global_total):  # making a copy of the keys because the dict is being modified (keys are not!)
                tel = global_total[w]
                if w not in entry_data["total"]:
                    continue
                el = entry_data["total"][w]
                if tel is None:
                    # new one, just copy over
                    tel = {}
                    for a in el:
                        # coming from XML, everything is a string
                        tel[a] = int(el[a])
                    global_total[w] = tel
                else:
                    # successive, sum
                    for a in el:
                        if a in tel:  # pylint: disable=unsupported-membership-test
                            tel[a] += int(el[a])  # pylint: disable=unsupported-assignment-operation
                    # if any attribute from prev. frontends is not in the current one, remove from total
                    for a in list(tel):  # making a copy of the keys because the dict is being modified
                        if a not in el:
                            del tel[a]  # pylint: disable=unsupported-delete-operation
                            tmp_list_removed.append(a)
                    if tmp_list_removed:
                        logSupport.log.debug(
                            "Elements removed from total status (%s: %s) because of %s: %s"
                            % (w, len(tel), entry, tmp_list_removed)
                        )
                        tmp_list_removed = []

        # update frontends
        if "frontends" in entry_data:
            # loop on fe's in this entry
            for fe in entry_data["frontends"]:
                # compare each to the list of fe's accumulated so far
                if fe not in status_fe["frontends"]:
                    status_fe["frontends"][fe] = {}
                    fe_first = True
                else:
                    fe_first = False
                # number of entries with this frontend
                if fe not in nr_feentries:
                    nr_feentries[fe] = 1  # first occurrence of frontend
                else:
                    nr_feentries[fe] += 1  # already found one
                for w in entry_data["frontends"][fe]:
                    # w is the entry name of the entry using the frontend
                    if w not in status_fe["frontends"][fe]:
                        status_fe["frontends"][fe][w] = {}
                    tela = status_fe["frontends"][fe][w]
                    ela = entry_data["frontends"][fe][w]
                    for a in ela:
                        # for the 'Downtime' field (only bool), do logical AND of all site downtimes
                        #  'w' is frontend attribute name, ie 'ClientMonitor' or 'Downtime'
                        #  'a' is sub-field, such as 'GlideIdle' or 'status'
                        if w == "Downtime" and a == "status":
                            ela_val = ela[a] != "False"  # Check if 'True' or 'False' but default to True if neither
                            try:
                                tela[a] = tela[a] and ela_val
                            except KeyError:
                                tela[a] = ela_val
                            except Exception:
                                pass  # just protect
                        else:
                            # All other fields could be numbers or something else
                            try:
                                # if is there already, sum
                                if a in tela:
                                    tela[a] += int(ela[a])
                                else:
                                    if fe_first:  # to avoid adding back attributes that were not in other frontends
                                        tela[a] = int(ela[a])
                            except Exception:
                                pass  # not an int, not Downtime, so do nothing
                    # if any attribute from prev. frontends is not in the current one, remove from total
                    if not fe_first and w != "Downtime":
                        for a in list(tela):  # making a copy of the keys because the dict is being modified
                            if a not in ela:
                                del tela[a]
                                tmp_list_removed.append(a)
                        if tmp_list_removed:
                            logSupport.log.debug(
                                "Elements removed from Frontend %s total status (%s: %s) because of %s: %s"
                                % (fe, w, len(tela), entry, tmp_list_removed)
                            )
                            tmp_list_removed = []

    for w in list(global_total):  # making a copy of the keys because the dict is being modified
        if global_total[w] is None:
            del global_total[w]  # remove entry if not defined
        else:
            tel = global_total[w]
            for a in tel:  # pylint: disable=not-an-iterable
                if a in avgEntries:
                    # since all entries must have this attr to be here, just divide by nr of entries
                    tel[a] = (
                        tel[a] // nr_entries
                    )  # pylint: disable=unsupported-assignment-operation,unsubscriptable-object

    # do average for per-fe stat--'InfoAge' only
    for fe in list(status_fe["frontends"].keys()):
        for w in list(status_fe["frontends"][fe].keys()):
            tel = status_fe["frontends"][fe][w]
            for a in list(tel.keys()):
                if a in avgEntries and fe in nr_feentries:
                    tel[a] = tel[a] // nr_feentries[fe]  # divide per fe

    xml_downtime = xmlFormat.dict2string(
        {}, dict_name="downtime", el_name="", params={"status": str(in_downtime)}, leading_tab=xmlFormat.DEFAULT_TAB
    )

    # Write xml files
    updated = time.time()
    xml_str = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
        + "<glideFactoryQStats>\n"
        + xmlFormat.time2xml(updated, "updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
        + "\n"
        + xml_downtime
        + "\n"
        + xmlFormat.dict2string(
            status["entries"],
            dict_name="entries",
            el_name="entry",
            subtypes_params={
                "class": {
                    "dicts_params": {
                        "frontends": {
                            "el_name": "frontend",
                            "subtypes_params": {
                                "class": {
                                    "subclass_params": {
                                        "Requested": {
                                            "dicts_params": {
                                                "Parameters": {"el_name": "Parameter", "subtypes_params": {"class": {}}}
                                            }
                                        }
                                    }
                                }
                            },
                        }
                    }
                }
            },
            leading_tab=xmlFormat.DEFAULT_TAB,
        )
        + "\n"
        + xmlFormat.class2string(status["total"], inst_name="total", leading_tab=xmlFormat.DEFAULT_TAB)
        + "\n"
        + xmlFormat.dict2string(
            status_fe["frontends"],
            dict_name="frontends",
            el_name="frontend",
            subtypes_params={
                "class": {
                    "subclass_params": {
                        "Requested": {
                            "dicts_params": {"Parameters": {"el_name": "Parameter", "subtypes_params": {"class": {}}}}
                        }
                    }
                }
            },
            leading_tab=xmlFormat.DEFAULT_TAB,
        )
        + "\n"
        + "</glideFactoryQStats>\n"
    )
    glideFactoryMonitoring.monitoringConfig.write_file(monitorAggregatorConfig.status_relname, xml_str)

    # write json
    glideFactoryMonitoring.monitoringConfig.write_completed_json(
        monitorAggregatorConfig.completed_data_relname.split(".")[0], updated, completed_data_tot
    )

    # Write rrds
    glideFactoryMonitoring.monitoringConfig.establish_dir("total")
    # Total rrd across all frontends and factories
    for tp in global_total:
        # values (RRD type) - Status or Requested
        if tp not in list(status_attributes.keys()):
            continue

        tp_str = type_strings[tp]
        attributes_tp = status_attributes[tp]

        tp_el = global_total[tp]

        for a in list(tp_el.keys()):
            if a in attributes_tp:
                a_el = int(tp_el[a])
                val_dict[f"{tp_str}{a}"] = a_el

    glideFactoryMonitoring.monitoringConfig.write_rrd_multi(
        os.path.join("total", "Status_Attributes"), "GAUGE", updated, val_dict
    )

    # Frontend total rrds across all factories
    for fe in list(status_fe["frontends"].keys()):
        glideFactoryMonitoring.monitoringConfig.establish_dir(os.path.join("total", f"frontend_{fe}"))
        for tp in list(status_fe["frontends"][fe].keys()):
            # values (RRD type) - Status or Requested
            if tp not in list(type_strings.keys()):
                continue
            tp_str = type_strings[tp]
            attributes_tp = status_attributes[tp]

            tp_el = status_fe["frontends"][fe][tp]

            for a in list(tp_el.keys()):
                if a in attributes_tp:
                    a_el = int(tp_el[a])
                    val_dict[f"{tp_str}{a}"] = a_el
        glideFactoryMonitoring.monitoringConfig.write_rrd_multi(
            os.path.join("total", f"frontend_{fe}", "Status_Attributes"), "GAUGE", updated, val_dict
        )

    return status


######################################################################################
def aggregateJobsSummary():
    """Aggregate job summary pickle files for each entry.

    This function loads the job summary pickle files for each entry, aggregates them per schedd/collector
    pair, and returns a dictionary with the aggregated information.

    Returns:
        dict: Dictionary of aggregated job summaries with keys as (schedd_name, collector_name) tuples.
              Each value is a dictionary mapping job identifiers (e.g. '2994.000') to a dictionary with statistics
              keys such as 'condor_duration', 'glidein_duration', 'condor_started', and 'numjobs'.

    Example of return value:
        ```
        {
            ('schedd_name','collector_name') : {
                '2994.000': {'condor_duration': 1328, 'glidein_duration': 1334, 'condor_started': 1, 'numjobs': 0},
                '2997.000': {'condor_duration': 1328, 'glidein_duration': 1334, 'condor_started': 1, 'numjobs': 0},
                ...
            },
            ('schedd_name','collector_name') : {
                '2003.000': {'condor_duration': 1328, 'glidein_duration': 1334, 'condor_started': 1, 'numjobs': 0},
                '206.000': {'condor_duration': 1328, 'glidein_duration': 1334, 'condor_started': 1, 'numjobs': 0},
                ...
            }
        }
        ```
    """
    jobinfo = {}
    for entry in monitorAggregatorConfig.entries:
        # load entry log summary file
        status_fname = os.path.join(
            monitorAggregatorConfig.monitor_dir,
            f"entry_{entry}",
            monitorAggregatorConfig.jobsummary_relname,
        )
        try:
            with open(status_fname, "rb") as fd:
                entry_joblist = pickle.load(fd)
        except OSError:
            # Errors with the file, e.g. FileNotFoundError, IsADirectoryError, PermissionError
            logSupport.log.debug(f"Missing file {status_fname}: ignoring and continuing")
            continue
        except (EOFError, pickle.UnpicklingError):
            # Errors with the file content
            logSupport.log.debug(f"Empty or corrupted pickle file {status_fname}: ignoring and continuing")
            continue
        schedd_name = entry_joblist.get("schedd_name", None)
        pool_name = entry_joblist.get("collector_name", None)
        jobinfo.setdefault((schedd_name, pool_name), {}).update(entry_joblist["joblist"])
    return jobinfo


######################################################################################
def aggregateLogSummary():
    """Aggregate log summary files and write an aggregate log summary.

    This function creates an aggregate of log summary files from all entries, writes the aggregate log summary XML file,
    and returns the aggregated log summary dictionary.

    Returns:
        dict: Dictionary containing aggregated log summary information.
    """
    global monitorAggregatorConfig

    # initialize global counters
    global_total = {
        "Current": {},
        "Entered": {},
        "Exited": {},
        "CompletedCounts": {"Sum": {}, "Waste": {}, "WasteTime": {}, "Lasted": {}, "JobsNr": {}, "JobsDuration": {}},
    }

    for s in ("Wait", "Idle", "Running", "Held"):
        for k in ["Current", "Entered", "Exited"]:
            global_total[k][s] = 0

    for s in ("Completed", "Removed"):
        for k in ["Entered"]:
            global_total[k][s] = 0

    for k in glideFactoryMonitoring.getAllJobTypes():
        for w in ("Waste", "WasteTime"):
            el = {}
            for t in glideFactoryMonitoring.getAllMillRanges():
                el[t] = 0
            global_total["CompletedCounts"][w][k] = el

    el = {}
    for t in glideFactoryMonitoring.getAllTimeRanges():
        el[t] = 0
    global_total["CompletedCounts"]["Lasted"] = el

    el = {}
    for t in glideFactoryMonitoring.getAllJobRanges():
        el[t] = 0
    global_total["CompletedCounts"]["JobsNr"] = el

    el = {}
    # KEL - why is the same el used twice (see above)
    for t in glideFactoryMonitoring.getAllTimeRanges():
        el[t] = 0
    global_total["CompletedCounts"]["JobsDuration"] = el

    global_total["CompletedCounts"]["Sum"] = {
        "Glideins": 0,
        "Lasted": 0,
        "FailedNr": 0,
        "JobsNr": 0,
        "JobsLasted": 0,
        "JobsGoodput": 0,
        "JobsTerminated": 0,
        "CondorLasted": 0,
    }

    status = {"entries": {}, "total": global_total}
    status_fe = {"frontends": {}}  # analogous to above but for frontend totals

    nr_entries = 0
    nr_feentries = {}  # dictionary for nr entries per fe
    for entry in monitorAggregatorConfig.entries:
        # load entry log summary file
        status_fname = os.path.join(
            monitorAggregatorConfig.monitor_dir,
            f"entry_{entry}",
            monitorAggregatorConfig.logsummary_relname,
        )

        try:
            entry_data = xmlParse.xmlfile2dict(status_fname, always_singular_list=["Fraction", "TimeRange", "Range"])
        except OSError:
            logSupport.log.debug(f"Missing file {status_fname}: ignoring and continuing")
            continue  # file not found, ignore

        # update entry
        out_data = {}
        for frontend in list(entry_data["frontends"].keys()):
            fe_el = entry_data["frontends"][frontend]
            out_fe_el = {}
            for k in ["Current", "Entered", "Exited"]:
                out_fe_el[k] = {}
                for s in list(fe_el[k].keys()):
                    out_fe_el[k][s] = int(fe_el[k][s])
            out_fe_el["CompletedCounts"] = {
                "Waste": {},
                "WasteTime": {},
                "Lasted": {},
                "JobsNr": {},
                "JobsDuration": {},
                "Sum": {},
            }
            for tkey in list(fe_el["CompletedCounts"]["Sum"].keys()):
                out_fe_el["CompletedCounts"]["Sum"][tkey] = int(fe_el["CompletedCounts"]["Sum"][tkey])
            for k in glideFactoryMonitoring.getAllJobTypes():
                for w in ("Waste", "WasteTime"):
                    out_fe_el["CompletedCounts"][w][k] = {}
                    for t in glideFactoryMonitoring.getAllMillRanges():
                        out_fe_el["CompletedCounts"][w][k][t] = int(fe_el["CompletedCounts"][w][k][t]["val"])
            for t in glideFactoryMonitoring.getAllTimeRanges():
                out_fe_el["CompletedCounts"]["Lasted"][t] = int(fe_el["CompletedCounts"]["Lasted"][t]["val"])
            out_fe_el["CompletedCounts"]["JobsDuration"] = {}
            for t in glideFactoryMonitoring.getAllTimeRanges():
                out_fe_el["CompletedCounts"]["JobsDuration"][t] = int(
                    fe_el["CompletedCounts"]["JobsDuration"][t]["val"]
                )
            for t in glideFactoryMonitoring.getAllJobRanges():
                out_fe_el["CompletedCounts"]["JobsNr"][t] = int(fe_el["CompletedCounts"]["JobsNr"][t]["val"])
            out_data[frontend] = out_fe_el

        status["entries"][entry] = {"frontends": out_data}

        # update total
        if "total" in entry_data:
            nr_entries += 1
            local_total = {}

            for k in ["Current", "Entered", "Exited"]:
                local_total[k] = {}
                for s in list(global_total[k].keys()):
                    local_total[k][s] = int(entry_data["total"][k][s])
                    global_total[k][s] += int(entry_data["total"][k][s])
            local_total["CompletedCounts"] = {
                "Sum": {},
                "Waste": {},
                "WasteTime": {},
                "Lasted": {},
                "JobsNr": {},
                "JobsDuration": {},
            }
            for tkey in list(entry_data["total"]["CompletedCounts"]["Sum"].keys()):
                local_total["CompletedCounts"]["Sum"][tkey] = int(entry_data["total"]["CompletedCounts"]["Sum"][tkey])
                global_total["CompletedCounts"]["Sum"][tkey] += int(entry_data["total"]["CompletedCounts"]["Sum"][tkey])
            for k in glideFactoryMonitoring.getAllJobTypes():
                for w in ("Waste", "WasteTime"):
                    local_total["CompletedCounts"][w][k] = {}
                    for t in glideFactoryMonitoring.getAllMillRanges():
                        local_total["CompletedCounts"][w][k][t] = int(
                            entry_data["total"]["CompletedCounts"][w][k][t]["val"]
                        )
                        global_total["CompletedCounts"][w][k][t] += int(
                            entry_data["total"]["CompletedCounts"][w][k][t]["val"]
                        )

            for t in glideFactoryMonitoring.getAllTimeRanges():
                local_total["CompletedCounts"]["Lasted"][t] = int(
                    entry_data["total"]["CompletedCounts"]["Lasted"][t]["val"]
                )
                global_total["CompletedCounts"]["Lasted"][t] += int(
                    entry_data["total"]["CompletedCounts"]["Lasted"][t]["val"]
                )
            local_total["CompletedCounts"]["JobsDuration"] = {}
            for t in glideFactoryMonitoring.getAllTimeRanges():
                local_total["CompletedCounts"]["JobsDuration"][t] = int(
                    entry_data["total"]["CompletedCounts"]["JobsDuration"][t]["val"]
                )
                global_total["CompletedCounts"]["JobsDuration"][t] += int(
                    entry_data["total"]["CompletedCounts"]["JobsDuration"][t]["val"]
                )

            for t in glideFactoryMonitoring.getAllJobRanges():
                local_total["CompletedCounts"]["JobsNr"][t] = int(
                    entry_data["total"]["CompletedCounts"]["JobsNr"][t]["val"]
                )
                global_total["CompletedCounts"]["JobsNr"][t] += int(
                    entry_data["total"]["CompletedCounts"]["JobsNr"][t]["val"]
                )

            status["entries"][entry]["total"] = local_total

        # update frontends
        for fe in out_data:
            # compare each to the list of fe's accumulated so far
            if fe not in status_fe["frontends"]:
                status_fe["frontends"][fe] = {}
            if fe not in nr_feentries:
                nr_feentries[fe] = 1  # already found one
            else:
                nr_feentries[fe] += 1

            # sum them up
            sumDictInt(out_data[fe], status_fe["frontends"][fe])

    # Write xml files
    # To do - Igor: Consider adding status_fe to the XML file
    updated = time.time()
    xml_str = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
        + "<glideFactoryLogSummary>\n"
        + xmlFormat.time2xml(updated, "updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
        + "\n"
        + xmlFormat.dict2string(
            status["entries"],
            dict_name="entries",
            el_name="entry",
            subtypes_params={
                "class": {
                    "dicts_params": {
                        "frontends": {
                            "el_name": "frontend",
                            "subtypes_params": {
                                "class": {
                                    "subclass_params": {
                                        "CompletedCounts": glideFactoryMonitoring.get_completed_stats_xml_desc()
                                    }
                                }
                            },
                        }
                    },
                    "subclass_params": {
                        "total": {
                            "subclass_params": {
                                "CompletedCounts": glideFactoryMonitoring.get_completed_stats_xml_desc()
                            }
                        }
                    },
                }
            },
            leading_tab=xmlFormat.DEFAULT_TAB,
        )
        + "\n"
        + xmlFormat.class2string(
            status["total"],
            inst_name="total",
            subclass_params={"CompletedCounts": glideFactoryMonitoring.get_completed_stats_xml_desc()},
            leading_tab=xmlFormat.DEFAULT_TAB,
        )
        + "\n"
        + "</glideFactoryLogSummary>\n"
    )
    glideFactoryMonitoring.monitoringConfig.write_file(monitorAggregatorConfig.logsummary_relname, xml_str)

    # Write rrds
    writeLogSummaryRRDs("total", status["total"])

    # Frontend total rrds across all factories
    for fe in status_fe["frontends"]:
        writeLogSummaryRRDs("total/%s" % ("frontend_" + fe), status_fe["frontends"][fe])

    return status


def sumDictInt(indict, outdict):
    """Sum the integer values from one dictionary into another.

    The input dictionary must contain only integers or nested dictionaries with the same constraint.

    Args:
        indict (dict): Input dictionary with integer values (or nested dictionaries).
        outdict (dict): Output dictionary where summed values will be stored.
    """
    for orgi in indict:
        i = str(orgi)  # RRDs don't like unicode, so make sure we use strings
        if isinstance(indict[i], int):
            if i not in outdict:
                outdict[i] = 0
            outdict[i] += indict[i]
        else:
            # assume it is a dictionary
            if i not in outdict:
                outdict[i] = {}
            sumDictInt(indict[i], outdict[i])


def writeLogSummaryRRDs(fe_dir, status_el):
    """Write aggregated log summary RRDs to disk.

    This function writes various RRD files (for counts, completed stats, and waste time - e.g. Log_Counts,
    Log_Completed, etc.) using the aggregated status data.

    Args:
        fe_dir (str): Directory path where RRDs will be written.
        status_el (dict): Aggregated status data.
    """
    updated = time.time()

    sdata = status_el["Current"]

    glideFactoryMonitoring.monitoringConfig.establish_dir(fe_dir)
    val_dict_counts = {}
    val_dict_counts_desc = {}
    val_dict_completed = {}
    val_dict_stats = {}
    val_dict_waste = {}
    val_dict_wastetime = {}
    for s in ("Wait", "Idle", "Running", "Held", "Completed", "Removed"):
        if s not in ("Completed", "Removed"):  # I don't have their numbers from inactive logs
            count = sdata[s]
            val_dict_counts["Status%s" % s] = count
            val_dict_counts_desc["Status%s" % s] = {"ds_type": "GAUGE"}

            exited = -status_el["Exited"][s]
            val_dict_counts["Exited%s" % s] = exited
            val_dict_counts_desc["Exited%s" % s] = {"ds_type": "ABSOLUTE"}

        entered = status_el["Entered"][s]
        val_dict_counts["Entered%s" % s] = entered
        val_dict_counts_desc["Entered%s" % s] = {"ds_type": "ABSOLUTE"}

        if s == "Completed":
            completed_counts = status_el["CompletedCounts"]
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

            # save simple vals
            for tkey in list(completed_counts["Sum"].keys()):
                val_dict_completed[tkey] = completed_counts["Sum"][tkey]

            # save waste_mill
            for w in list(count_waste_mill.keys()):
                count_waste_mill_w = count_waste_mill[w]
                for p in list(count_waste_mill_w.keys()):
                    val_dict_waste[f"{w}_{p}"] = count_waste_mill_w[p]

            for w in list(time_waste_mill.keys()):
                time_waste_mill_w = time_waste_mill[w]
                for p in list(time_waste_mill_w.keys()):
                    val_dict_wastetime[f"{w}_{p}"] = time_waste_mill_w[p]

    # write the data to disk
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi_hetero(
        "%s/Log_Counts" % fe_dir, val_dict_counts_desc, updated, val_dict_counts
    )
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi(
        "%s/Log_Completed" % fe_dir, "ABSOLUTE", updated, val_dict_completed
    )
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi(
        "%s/Log_Completed_Stats" % fe_dir, "ABSOLUTE", updated, val_dict_stats
    )
    # Disable Waste RRDs... WasteTime much more useful
    # glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Completed_Waste"%fe_dir,
    #                                                        "ABSOLUTE",updated,val_dict_waste)
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi(
        "%s/Log_Completed_WasteTime" % fe_dir, "ABSOLUTE", updated, val_dict_wastetime
    )


def aggregateRRDStats(log=logSupport.log):
    """Aggregate RRD statistics from monitoring and write the aggregate files.

    This function reads and aggregates RRD stats from each entry in the monitoring directory and writes the aggregate
    XML file for RRD statistics.

    Args:
        log (logging.Logger): Logger to use.
    """
    global monitorAggregatorConfig
    # not-used, no side effect. Leave in case want to add more monitoring: factoryStatusData = glideFactoryMonitoring.FactoryStatusData()
    rrdstats_relname = glideFactoryMonitoring.RRD_LIST
    tab = xmlFormat.DEFAULT_TAB

    for rrd in rrdstats_relname:
        # assigns the data from every site to 'stats'
        stats = {}
        for entry in monitorAggregatorConfig.entries:
            rrd_fname = os.path.join(monitorAggregatorConfig.monitor_dir, f"entry_{entry}", rrd_site(rrd))
            try:
                stats[entry] = xmlParse.xmlfile2dict(rrd_fname, always_singular_list={"timezone": {}})
            except FileNotFoundError:
                log.debug(
                    f"aggregateRRDStats {rrd_fname} exception: parse_xml, IOError, File not found (OK if first time)"
                )
            except OSError:
                log.debug(f"aggregateRRDStats {rrd_fname} exception: parse_xml, IOError")
                if not os.path.exists(rrd_fname):
                    log.debug(
                        f"aggregateRRDStats {rrd_fname} exception: parse_xml, IOError, File not found (OK if first time) - should have been FileNotFoundError"
                    )

        stats_entries = list(stats.keys())
        if len(stats_entries) == 0:
            continue  # skip this RRD... nothing to aggregate
        stats_entries.sort()

        # Get all the resolutions, data_sets and frontends... for totals
        resolution = set()
        frontends = set()
        data_sets = set()
        for entry in stats_entries:
            entry_resolution = list(stats[entry]["total"]["periods"].keys())
            if len(entry_resolution) == 0:
                continue  # not an interesting entry
            resolution = resolution.union(entry_resolution)
            entry_data_sets = stats[entry]["total"]["periods"][entry_resolution[0]]
            data_sets = data_sets.union(entry_data_sets)
            entry_frontends = list(stats[entry]["frontends"].keys())
            frontends = frontends.union(entry_frontends)
            entry_data_sets = stats[entry]["total"]["periods"][entry_resolution[0]]

        resolution = list(resolution)
        frontends = list(frontends)
        data_sets = list(data_sets)

        # create a dictionary that will hold the aggregate data
        clients = frontends + ["total"]
        aggregate_output = {}
        for client in clients:
            aggregate_output[client] = {}
            for res in resolution:
                aggregate_output[client][res] = {}
                for data_set in data_sets:
                    aggregate_output[client][res][data_set] = 0

        # assign the aggregate data to 'aggregate_output'
        missing_total_data = False
        missing_client_data = False
        for client in aggregate_output:
            for res in aggregate_output[client]:
                for data_set in aggregate_output[client][res]:
                    for entry in stats_entries:
                        if client == "total":
                            try:
                                aggregate_output[client][res][data_set] += float(
                                    stats[entry][client]["periods"][res][data_set]
                                )
                            except KeyError:
                                missing_total_data = True
                                # well, some may be just missing.. can happen
                                # log.debug("aggregate_data, KeyError stats[%s][%s][%s][%s][%s]"%(entry,client,'periods',res,data_set))

                        else:
                            if client in stats[entry]["frontends"]:
                                # not all the entries have all the frontends
                                try:
                                    aggregate_output[client][res][data_set] += float(
                                        stats[entry]["frontends"][client]["periods"][res][data_set]
                                    )
                                except KeyError:
                                    missing_client_data = True
                                    # well, some may be just missing.. can happen
                                    # log.debug("aggregate_data, KeyError stats[%s][%s][%s][%s][%s][%s]" %(entry,'frontends',client,'periods',res,data_set))

        # We still need to determine what is causing these missing data in case it is a real issue
        # but using this flags will at least reduce the number of messages in the logs (see commented out messages above)
        if missing_total_data:
            log.debug("aggregate_data, missing total data from file %s" % rrd_site(rrd))
        if missing_client_data:
            log.debug("aggregate_data, missing client data from file %s" % rrd_site(rrd))

        # write an aggregate XML file

        # data from individual entries
        entry_str = tab + "<entries>\n"
        for entry in stats_entries:
            entry_name = entry.split("/")[-1]
            entry_str += 2 * tab + '<entry name = "' + entry_name + '">\n'
            entry_str += 3 * tab + "<total>\n"
            try:
                entry_str += (
                    xmlFormat.dict2string(
                        stats[entry]["total"]["periods"],
                        dict_name="periods",
                        el_name="period",
                        subtypes_params={"class": {}},
                        indent_tab=tab,
                        leading_tab=4 * tab,
                    )
                    + "\n"
                )
            except (NameError, UnboundLocalError):
                log.debug("total_data, NameError or TypeError")
            entry_str += 3 * tab + "</total>\n"

            entry_str += 3 * tab + "<frontends>\n"
            try:
                entry_frontends = sorted(stats[entry]["frontends"].keys())
                for frontend in entry_frontends:
                    entry_str += 4 * tab + '<frontend name="' + frontend + '">\n'
                    try:
                        entry_str += (
                            xmlFormat.dict2string(
                                stats[entry]["frontends"][frontend]["periods"],
                                dict_name="periods",
                                el_name="period",
                                subtypes_params={"class": {}},
                                indent_tab=tab,
                                leading_tab=5 * tab,
                            )
                            + "\n"
                        )
                    except KeyError:
                        log.debug("frontend_data, KeyError")
                    entry_str += 4 * tab + "</frontend>\n"
            except TypeError:
                log.debug("frontend_data, TypeError")
            entry_str += 3 * tab + "</frontends>\n"
            entry_str += 2 * tab + "</entry>\n"
        entry_str += tab + "</entries>\n"

        # aggregated data
        total_xml_str = 2 * tab + "<total>\n"
        total_data = aggregate_output["total"]
        try:
            total_xml_str += (
                xmlFormat.dict2string(
                    total_data,
                    dict_name="periods",
                    el_name="period",
                    subtypes_params={"class": {}},
                    indent_tab=tab,
                    leading_tab=4 * tab,
                )
                + "\n"
            )
        except (NameError, UnboundLocalError):
            log.debug("total_data, NameError or TypeError")
        total_xml_str += 2 * tab + "</total>\n"

        frontend_xml_str = 2 * tab + "<frontends>\n"
        try:
            for frontend in frontends:
                frontend_xml_str += 3 * tab + '<frontend name="' + frontend + '">\n'
                frontend_data = aggregate_output[frontend]
                frontend_xml_str += (
                    xmlFormat.dict2string(
                        frontend_data,
                        dict_name="periods",
                        el_name="period",
                        subtypes_params={"class": {}},
                        indent_tab=tab,
                        leading_tab=4 * tab,
                    )
                    + "\n"
                )
                frontend_xml_str += 3 * tab + "</frontend>\n"
        except TypeError:
            log.debug("frontend_data, TypeError")
        frontend_xml_str += 2 * tab + "</frontends>\n"

        data_str = tab + "<total>\n" + total_xml_str + frontend_xml_str + tab + "</total>\n"

        # putting it all together
        updated = time.time()
        xml_str = (
            '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
            + "<glideFactoryRRDStats>\n"
            + xmlFormat.time2xml(
                updated, "updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB
            )
            + "\n"
            + entry_str
            + data_str
            + "</glideFactoryRRDStats>"
        )

        try:
            glideFactoryMonitoring.monitoringConfig.write_file(rrd_site(rrd), xml_str)
        except OSError:
            log.debug("write_file %s, IOError" % rrd_site(rrd))

    return
