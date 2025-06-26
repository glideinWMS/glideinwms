# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements the functions needed to aggregate the monitoring of the Frontend.

It provides configuration management, RRD file verification, and aggregation of monitoring data
across multiple groups for the GlideinWMS frontend.
"""
import os
import os.path
import time

from glideinwms.frontend import glideinFrontendMonitoring # type: ignore
from glideinwms.lib import logSupport, rrdSupport, xmlFormat, xmlParse # type: ignore

############################################################
#
# Configuration
#
############################################################

class MonitorAggregatorConfig:
    """Configuration class for monitoring aggregator.

    Attributes:
        monitor_dir (str): Directory where monitoring files are stored.
        entries (list): List of monitoring entries.
        status_relname (str): Name of the status XML file.
        groups (list): List of group names.
    """

    def __init__(self):
        """Initializes MonitorAggregatorConfig with default values."""
        # The name of the attribute that identifies the glidein
        self.monitor_dir = "monitor/"
       
        # list of entries
        self.entries = []
        
        # name of the status files
        self.status_relname = "frontend_status.xml"

    def config_frontend(self, monitor_dir, groups):
        """Configures the frontend monitoring directory and groups.

        Args:
            monitor_dir (str): Path to monitoring directory.
            groups (list): List of group names.
        """
        self.monitor_dir = monitor_dir
        self.groups = groups
        glideinFrontendMonitoring.monitoringConfig.monitor_dir = monitor_dir

# Global configuration instance
monitorAggregatorConfig = MonitorAggregatorConfig()
###########################################################
#
# Functions
#
###########################################################

# PM: Nov 26, 2014
# There is a limit on rrd field names. Max allowed is 20 chars long.
# RRD enforces this limit while creating fields, but will not enforce the limits
# when trying to read from a field with name longer than 20 chars.
# Truncate the names for following to be in limits to avoid above issue.
frontend_status_attributes = {
    "Jobs": ("Idle", "OldIdle", "Running", "Total", "Idle_3600"),
    "Glideins": ("Idle", "Running", "Total"),
    "MatchedJobs": ("Idle", "EffIdle", "OldIdle", "Running", "RunningHere"),
    "MatchedGlideins": ("Total", "Idle", "Running", "Failed"),
    "MatchedCores": ("Total", "Idle", "Running"),
    "Requested": ("Idle", "MaxRun"),
}

frontend_total_type_strings = {
    "Jobs": "Jobs",
    "Glideins": "Glidein",
    "MatchedJobs": "MatchJob",
    "MatchedGlideins": "MatchGlidein",
    "MatchedCores": "MatchCore",
    "Requested": "Req",
}

frontend_job_type_strings = {
    "MatchedJobs": "MatchJob",
    "MatchedGlideins": "MatchGlidein",
    "MatchedCores": "MatchCore",
    "Requested": "Req",
}

def verifyRRD(fix_rrd=False, backup=False):
    """Verifies that all monitoring RRDs match the expected schema, optionally fixing them.

    Args:
        fix_rrd (bool): If True, attempt to add missing attributes.
        backup (bool): If True, back up the old RRD before fixing.

    Returns:
        bool: True if all RRD files are OK or successfully fixed, False if a problem remains.
    """
    rrd_problems_found = False
    mon_dir = monitorAggregatorConfig.monitor_dir
    # Frontend monitoring dictionaries
    status_dict = {}
    status_total_dict = {}
    # initialize the RRD dictionaries to match the current schema for verification
    for tp in list(frontend_status_attributes.keys()):
        if tp in list(frontend_total_type_strings.keys()):
            tp_str = frontend_total_type_strings[tp]
            attributes_tp = frontend_status_attributes[tp]
            for a in attributes_tp:
                status_total_dict[f"{tp_str}{a}"] = None
        if tp in list(frontend_job_type_strings.keys()):
            tp_str = frontend_job_type_strings[tp]
            attributes_tp = frontend_status_attributes[tp]
            for a in attributes_tp:
                status_dict[f"{tp_str}{a}"] = None
    # check all the existing files
    if not os.path.isdir(mon_dir):
        print("WARNING: monitor/ directory does not exist, skipping rrd verification.")
        return True
    for dir_name, sdir_name, f_list in os.walk(mon_dir):
        for file_name in f_list:
            if file_name == "Status_Attributes.rrd":
                if os.path.basename(dir_name) == "total":
                    if rrdSupport.verifyHelper(os.path.join(dir_name, file_name), status_total_dict, fix_rrd, backup):
                        rrd_problems_found = True
                else:
                    if rrdSupport.verifyHelper(os.path.join(dir_name, file_name), status_dict, fix_rrd, backup):
                        rrd_problems_found = True
    return not rrd_problems_found

####################################
# PRIVATE - Used by aggregateStatus
# Write one RRD
def write_one_rrd(name, updated, data, fact=0):
    """Writes data to a single RRD file, initializing RRD schema if necessary.

    Args:
        name (str): Name or path of the RRD file.
        updated (float): Timestamp for the update.
        data (dict): Monitoring data to write.
        fact (int): If 0, use frontend_total_type_strings; otherwise use frontend_job_type_strings.
    """
    if fact == 0:
        type_strings = frontend_total_type_strings
    else:
        type_strings = frontend_job_type_strings

    val_dict = {}
    for tp in list(frontend_status_attributes.keys()):
        if tp in list(type_strings.keys()):
            tp_str = type_strings[tp]
            attributes_tp = frontend_status_attributes[tp]
            for a in attributes_tp:
                val_dict[f"{tp_str}{a}"] = None

    for tp in list(data.keys()):
        # values (RRD type) - Status or Requested
        if tp not in list(frontend_status_attributes.keys()):
            continue
        if tp not in list(type_strings.keys()):
            continue

        tp_str = type_strings[tp]
        attributes_tp = frontend_status_attributes[tp]
        
        tp_el = data[tp]
        for a in list(tp_el.keys()):
            if a in attributes_tp:
                a_el = int(tp_el[a])
                if not isinstance(a_el, dict):
                    val_dict[f"{tp_str}{a}"] = a_el

    glideinFrontendMonitoring.monitoringConfig.establish_dir("%s" % name)
    glideinFrontendMonitoring.monitoringConfig.write_rrd_multi("%s" % name, "GAUGE", updated, val_dict)
    
    
##############################################################################
# create an aggregate of status files, write it in an aggregate status file
# end return the values
    def aggregateStatus():
        global monitorAggregatorConfig

    type_strings = {
        "Jobs": "Jobs",
        "Glideins": "Glidein",
        "MatchedJobs": "MatchJob",
        "MatchedGlideins": "MatchGlidein",
        "MatchedCores": "MatchCore",
        "Requested": "Req",
    }
    global_total = {
        "Jobs": None,
        "Glideins": None,
        "MatchedJobs": None,
        "Requested": None,
        "MatchedGlideins": None,
        "MatchedCores": None,
    }
    status = {"groups": {}, "total": global_total}
    global_fact_totals = {}

    for fos in ("factories", "states"):
        global_fact_totals[fos] = {}

    nr_groups = 0
    for group in monitorAggregatorConfig.groups:
        # load group status file
        status_fname = os.path.join(
            monitorAggregatorConfig.monitor_dir, f"group_{group}", monitorAggregatorConfig.status_relname
        )
        try:
            group_data = xmlParse.xmlfile2dict(status_fname)
        except xmlParse.CorruptXML:
            logSupport.log.error("Corrupt XML in %s; deleting (it will be recreated)." % (status_fname))
            os.unlink(status_fname)
            continue
        except OSError:
            continue  # file not found, ignore

        # update group
        status["groups"][group] = {}
        for fos in ("factories", "states"):
            try:
                status["groups"][group][fos] = group_data[fos]
            except KeyError:
                # first time after upgrade factories may not be defined
                status["groups"][group][fos] = {}

        this_group = status["groups"][group]
        for fos in ("factories", "states"):
            for fact in list(this_group[fos].keys()):
                this_fact = this_group[fos][fact]
                if fact not in list(global_fact_totals[fos].keys()):
                    # first iteration through, set fact totals equal to the first group's fact totals
                    global_fact_totals[fos][fact] = {}
                    for attribute in list(type_strings.keys()):
                        global_fact_totals[fos][fact][attribute] = {}
                        if attribute in list(this_fact.keys()):
                            for type_attribute in list(this_fact[attribute].keys()):
                                this_type_attribute = this_fact[attribute][type_attribute]
                                try:
                                    global_fact_totals[fos][fact][attribute][type_attribute] = int(this_type_attribute)
                                except Exception:
                                    pass
                else:
                    # next iterations, factory already present in global fact totals, add the new factory values to the previous ones
                    for attribute in list(type_strings.keys()):
                        if attribute in list(this_fact.keys()):
                            for type_attribute in list(this_fact[attribute].keys()):
                                this_type_attribute = this_fact[attribute][type_attribute]
                                if isinstance(this_type_attribute, type(global_fact_totals[fos])):
                                    # dict, do nothing
                                    pass
                                else:
                                    if attribute in list(
                                        global_fact_totals[fos][fact].keys()
                                    ) and type_attribute in list(global_fact_totals[fos][fact][attribute].keys()):
                                        global_fact_totals[fos][fact][attribute][type_attribute] += int(
                                            this_type_attribute
                                        )
                                    else:
                                        global_fact_totals[fos][fact][attribute][type_attribute] = int(
                                            this_type_attribute
                                        )
        # nr_groups+=1
        # status['groups'][group]={}

        if "total" in group_data:
            nr_groups += 1
            status["groups"][group]["total"] = group_data["total"]

            for w in list(global_total.keys()):
                tel = global_total[w]
                if w not in group_data["total"]:
                    continue
                # status['groups'][group][w]=group_data[w]
                el = group_data["total"][w]
                if tel is None:
                    # new one, just copy over
                    global_total[w] = {}
                    tel = global_total[w]
                    for a in list(el.keys()):  # coming from XML, everything is a string
                        tel[a] = int(el[a])  # pylint: disable=unsupported-assignment-operation
                else:
                    # successive, sum
                    for a in list(el.keys()):
                        if a in tel:  # pylint: disable=unsupported-membership-test
                            tel[a] += int(el[a])  # pylint: disable=unsupported-assignment-operation

                    # if any attribute from prev. factories are not in the current one, remove from total
                    for a in list(tel.keys()):
                        if a not in el:
                            del tel[a]  # pylint: disable=unsupported-delete-operation

    for w in list(global_total.keys()):
        if global_total[w] is None:
            del global_total[w]  # remove group if not defined

    # Write xml files

    updated = time.time()
    xml_str = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
        + "<VOFrontendStats>\n"
        + xmlFormat.time2xml(updated, "updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
        + "\n"
        + xmlFormat.dict2string(
            status["groups"],
            dict_name="groups",
            el_name="group",
            subtypes_params={
                "class": {
                    "dicts_params": {
                        "factories": {
                            "el_name": "factory",
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
                        },
                        "states": {
                            "el_name": "state",
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
                        },
                    }
                }
            },
            leading_tab=xmlFormat.DEFAULT_TAB,
        )
        + "\n"
        + xmlFormat.class2string(status["total"], inst_name="total", leading_tab=xmlFormat.DEFAULT_TAB)
        + "\n"
        + xmlFormat.dict2string(
            global_fact_totals["factories"],
            dict_name="factories",
            el_name="factory",
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
        + xmlFormat.dict2string(
            global_fact_totals["states"],
            dict_name="states",
            el_name="state",
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
        + "</VOFrontendStats>\n"
    )

    glideinFrontendMonitoring.monitoringConfig.write_file(monitorAggregatorConfig.status_relname, xml_str)

    # Write rrds

    glideinFrontendMonitoring.monitoringConfig.establish_dir("total")
    write_one_rrd(os.path.join("total", "Status_Attributes"), updated, global_total, 0)

    for fact in list(global_fact_totals["factories"].keys()):
        fe_dir = os.path.join("total", f"factory_{glideinFrontendMonitoring.sanitize(fact)}")
        glideinFrontendMonitoring.monitoringConfig.establish_dir(fe_dir)
        write_one_rrd(os.path.join(fe_dir, "Status_Attributes"), updated, global_fact_totals["factories"][fact], 1)
    for fact in list(global_fact_totals["states"].keys()):
        fe_dir = os.path.join("total", f"state_{glideinFrontendMonitoring.sanitize(fact)}")
        glideinFrontendMonitoring.monitoringConfig.establish_dir(fe_dir)
        write_one_rrd(os.path.join(fe_dir, "Status_Attributes"), updated, global_fact_totals["states"][fact], 1)

    return status