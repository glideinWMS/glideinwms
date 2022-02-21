# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This module implements the functions needed
#   to monitor the VO frontend
#
# Author:
#   Igor Sfiligoi (Mar 19th 2009)
#

import copy
import fcntl
import math
import os
import os.path
import random
import re
import string
import time
import traceback

from glideinwms.lib import logSupport, rrdSupport, timeConversion, xmlFormat
from glideinwms.lib.defaults import BINARY_ENCODING

############################################################
#
# Configuration
#
############################################################


class MonitoringConfig:
    def __init__(self):
        # set default values
        # user should modify if needed
        self.rrd_step = 300  # default to 5 minutes
        self.rrd_heartbeat = 1800  # default to 30 minutes, should be at least twice the loop time
        self.rrd_archives = [
            ("AVERAGE", 0.8, 1, 740),  # max precision, keep 2.5 days
            ("AVERAGE", 0.92, 12, 740),  # 1 h precision, keep for a month (30 days)
            ("AVERAGE", 0.98, 144, 740),  # 12 hour precision, keep for a year
        ]

        # The name of the attribute that identifies the glidein
        self.monitor_dir = "monitor/"

        self.rrd_obj = rrdSupport.rrdSupport()

        self.my_name = "Unknown"

    def write_file(self, relative_fname, output_str):
        fname = os.path.join(self.monitor_dir, relative_fname)
        if not os.path.isdir(os.path.dirname(fname)):
            os.makedirs(os.path.dirname(fname))
        # print "Writing "+fname
        with open(fname + ".tmp", "w") as fd:
            fd.write(output_str + "\n")

        tmp2final(fname)
        return

    def establish_dir(self, relative_dname):
        dname = os.path.join(self.monitor_dir, relative_dname)
        if not os.path.isdir(dname):
            os.mkdir(dname)
        return

    def write_rrd_multi(self, relative_fname, ds_type, time, val_dict, min_val=None, max_val=None):
        """
        Create a RRD file, using rrdtool.
        """
        if self.rrd_obj.isDummy():
            return  # nothing to do, no rrd bin no rrd creation

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
            except Exception as e:
                logSupport.log.error("Failed to update %s" % fname)
                # logSupport.log.exception(traceback.format_exc())
        return


#########################################################################################################################################
#
#  condorQStats
#
#  This class handles the data obtained from condor_q
#
#########################################################################################################################################


class groupStats:
    def __init__(self):
        self.data = {"factories": {}, "states": {}, "totals": {}}
        self.updated = time.time()

        self.files_updated = None
        self.attributes = {
            "Jobs": ("Idle", "OldIdle", "Running", "Total", "Idle_3600"),
            "Glideins": ("Idle", "Running", "Total"),
            "MatchedJobs": ("Idle", "EffIdle", "OldIdle", "Running", "RunningHere"),
            #'MatchedGlideins':("Total","Idle","Running","Failed","TotalCores","IdleCores","RunningCores"),
            "MatchedGlideins": ("Total", "Idle", "Running", "Failed"),
            "MatchedCores": ("Total", "Idle", "Running"),
            "Requested": ("Idle", "MaxRun"),
        }
        # only these will be states, all other names are assumed to be factories
        self.states_names = ("Unmatched", "MatchedUp", "MatchedDown")

    def logJobs(self, jobs_data):
        el = {}
        self.data["totals"]["Jobs"] = el

        for k in self.attributes["Jobs"]:
            if k in jobs_data:
                el[k] = int(jobs_data[k])
        self.updated = time.time()

    def logGlideins(self, slots_data):
        el = {}
        self.data["totals"]["Glideins"] = el

        for k in self.attributes["Glideins"]:
            if k in slots_data:
                el[k] = int(slots_data[k])
        self.updated = time.time()

    def logMatchedJobs(self, factory, idle, effIdle, oldIdle, running, realRunning):
        factory_or_state_d = self.get_factory_dict(factory)

        factory_or_state_d["MatchedJobs"] = {
            self.attributes["MatchedJobs"][0]: int(idle),
            self.attributes["MatchedJobs"][1]: int(effIdle),
            self.attributes["MatchedJobs"][2]: int(oldIdle),
            self.attributes["MatchedJobs"][3]: int(running),
            self.attributes["MatchedJobs"][4]: int(realRunning),
        }

        self.update = time.time()

    def logFactDown(self, factory, isDown):
        factory_or_state_d = self.get_factory_dict(factory)

        if isDown:
            factory_or_state_d["Down"] = "Down"
        else:
            factory_or_state_d["Down"] = "Up"

        self.updated = time.time()

    def logMatchedGlideins(self, factory, total, idle, running, failed, totalcores, idlecores, runningcores):
        factory_or_state_d = self.get_factory_dict(factory)

        factory_or_state_d["MatchedGlideins"] = {
            self.attributes["MatchedGlideins"][0]: int(total),
            self.attributes["MatchedGlideins"][1]: int(idle),
            self.attributes["MatchedGlideins"][2]: int(running),
            self.attributes["MatchedGlideins"][3]: int(failed),
        }
        factory_or_state_d["MatchedCores"] = {
            self.attributes["MatchedCores"][0]: int(totalcores),
            self.attributes["MatchedCores"][1]: int(idlecores),
            self.attributes["MatchedCores"][2]: int(runningcores),
        }

        self.update = time.time()

    def logFactAttrs(self, factory, attrs, blacklist):
        factory_or_state_d = self.get_factory_dict(factory)

        factory_or_state_d["Attributes"] = {}
        for attr in attrs:
            if not attr in blacklist:
                factory_or_state_d["Attributes"][attr] = attrs[attr]

        self.update = time.time()

    def logFactReq(self, factory, reqIdle, reqMaxRun, params):
        factory_or_state_d = self.get_factory_dict(factory)

        factory_or_state_d["Requested"] = {
            self.attributes["Requested"][0]: int(reqIdle),
            self.attributes["Requested"][1]: int(reqMaxRun),
            "Parameters": copy.deepcopy(params),
        }

        self.updated = time.time()

    def get_factories_data(self):
        return copy.deepcopy(self.data["factories"])

    def get_xml_factories_data(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        data = self.get_factories_data()
        return xmlFormat.dict2string(
            data,
            dict_name="factories",
            el_name="factory",
            subtypes_params={
                "class": {"subclass_params": {"Requested": {"dicts_params": {"Parameters": {"el_name": "Parameter"}}}}}
            },
            indent_tab=indent_tab,
            leading_tab=leading_tab,
        )

    def get_states_data(self):
        return copy.deepcopy(self.data["states"])

    def get_xml_states_data(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        data = self.get_states_data()
        return xmlFormat.dict2string(
            data,
            dict_name="states",
            el_name="state",
            subtypes_params={
                "class": {"subclass_params": {"Requested": {"dicts_params": {"Parameters": {"el_name": "Parameter"}}}}}
            },
            indent_tab=indent_tab,
            leading_tab=leading_tab,
        )

    def get_xml_updated(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        return xmlFormat.time2xml(self.updated, "updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab="")

    def get_total(self):
        total = {
            "MatchedJobs": None,
            "Requested": None,
            "MatchedGlideins": None,
            "MatchedCores": None,
        }
        numtypes = (int, int, float)

        for f in list(self.data["factories"].keys()):
            fa = self.data["factories"][f]
            for w in list(fa.keys()):
                if w in total:  # ignore eventual not supported classes
                    el = fa[w]
                    tel = total[w]

                    if tel is None:
                        # first one, just copy over
                        total[w] = {}
                        tel = total[w]
                        for a in list(el.keys()):
                            if type(el[a]) in numtypes:  # copy only numbers
                                tel[a] = el[a]
                    else:
                        # successive, sum
                        for a in list(el.keys()):
                            if type(el[a]) in numtypes:  # consider only numbers
                                if a in tel:
                                    tel[a] += el[a]
                            # if other frontends did't have this attribute, ignore
                        # if any attribute from prev. frontends are not in the current one, remove from total
                        for a in list(tel.keys()):
                            if a not in el:
                                del tel[a]
                            elif not (type(el[a]) in numtypes):
                                del tel[a]

        for w in list(total.keys()):
            if total[w] is None:
                del total[w]  # remove entry if not defined

        total.update(copy.deepcopy(self.data["totals"]))
        return total

    def get_xml_total(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        total = self.get_total()
        return xmlFormat.class2string(total, inst_name="total", indent_tab=indent_tab, leading_tab=leading_tab)

    def write_file(self):
        global monitoringConfig

        if (self.files_updated is not None) and ((self.updated - self.files_updated) < 5):
            # files updated recently, no need to redo it
            return

        # write snaphot file
        xml_str = (
            '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
            + "<VOFrontendGroupStats>\n"
            + self.get_xml_updated(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + self.get_xml_factories_data(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + self.get_xml_states_data(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + self.get_xml_total(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + "</VOFrontendGroupStats>\n"
        )

        monitoringConfig.write_file("frontend_status.xml", xml_str)

        # update RRDs
        total_el = self.get_total()
        self.write_one_rrd("total", total_el)

        data = self.get_factories_data()
        for fact in list(data.keys()):
            self.write_one_rrd("factory_%s" % sanitize(fact), data[fact], 1)

        data = self.get_states_data()
        for fact in list(data.keys()):
            self.write_one_rrd("state_%s" % sanitize(fact), data[fact], 1)

        self.files_updated = self.updated
        return

    ################################################
    # PRIVATE - Used to select the right disctionary
    def get_factory_dict(self, factory):
        if factory in self.states_names:
            factories = self.data["states"]
        else:
            factories = self.data["factories"]
        if not factory in factories:
            factories[factory] = {}
        return factories[factory]

    ###############################
    # PRIVATE - Used by write_file
    # Write one RRD
    def write_one_rrd(self, name, data, fact=0):
        global monitoringConfig

        val_dict = {}
        if fact == 0:
            type_strings = {
                "Jobs": "Jobs",
                "Glideins": "Glidein",
                "MatchedJobs": "MatchJob",
                "MatchedGlideins": "MatchGlidein",
                "MatchedCores": "MatchCore",
                "Requested": "Req",
            }
        else:
            type_strings = {
                "MatchedJobs": "MatchJob",
                "MatchedGlideins": "MatchGlidein",
                "MatchedCores": "MatchCore",
                "Requested": "Req",
            }

        # init, so that all get created properly
        for tp in list(self.attributes.keys()):
            if tp in list(type_strings.keys()):
                tp_str = type_strings[tp]
                attributes_tp = self.attributes[tp]
                for a in attributes_tp:
                    val_dict[f"{tp_str}{a}"] = None

        for tp in data:
            # values (RRD type) - Jobs, Slots
            if not (tp in list(self.attributes.keys())):
                continue
            if not (tp in list(type_strings.keys())):
                continue

            tp_str = type_strings[tp]

            attributes_tp = self.attributes[tp]

            fe_el_tp = data[tp]
            for a in list(fe_el_tp.keys()):
                if a in attributes_tp:
                    a_el = fe_el_tp[a]
                    if not isinstance(a_el, dict):  # ignore subdictionaries
                        val_dict[f"{tp_str}{a}"] = a_el

        monitoringConfig.establish_dir("%s" % name)
        monitoringConfig.write_rrd_multi("%s/Status_Attributes" % name, "GAUGE", self.updated, val_dict)


########################################################################


class factoryStats:
    def __init__(self):
        self.data = {}
        self.updated = time.time()

        self.files_updated = None
        self.attributes = {
            "Jobs": ("Idle", "OldIdle", "Running", "Total"),
            "Matched": ("Idle", "OldIdle", "Running", "Total"),
            "Requested": ("Idle", "MaxRun"),
            "Slots": ("Idle", "Running", "Total"),
        }

    def logJobs(self, client_name, qc_status):
        if client_name in self.data:
            t_el = self.data[client_name]
        else:
            t_el = {}
            self.data[client_name] = t_el

        el = {}
        t_el["Status"] = el

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
            if nr in qc_status:
                el[status] = int(qc_status[nr])
            else:
                el[status] = 0
        self.updated = time.time()

    def logRequest(self, client_name, requests, params):
        """
        requests is a dictinary of requests
        params is a dictinary of parameters

        At the moment, it looks only for
          'IdleGlideins'
          'MaxRunningGlideins'
        """
        if client_name in self.data:
            t_el = self.data[client_name]
        else:
            t_el = {}
            self.data[client_name] = t_el

        el = {}
        t_el["Requested"] = el

        if "IdleGlideins" in requests:
            el["Idle"] = int(requests["IdleGlideins"])
        if "MaxRunningGlideins" in requests:
            el["MaxRun"] = int(requests["MaxRunningGlideins"])

        el["Parameters"] = copy.deepcopy(params)

        self.updated = time.time()

    def logClientMonitor(self, client_name, client_monitor, client_internals):
        """
        client_monitor is a dictinary of monitoring info
        client_internals is a dictinary of internals

        At the moment, it looks only for
          'Idle'
          'Running'
          'GlideinsIdle'
          'GlideinsRunning'
          'GlideinsTotal'
          'LastHeardFrom'
        """
        if client_name in self.data:
            t_el = self.data[client_name]
        else:
            t_el = {}
            self.data[client_name] = t_el

        el = {}
        t_el["ClientMonitor"] = el

        for karr in (
            ("Idle", "JobsIdle"),
            ("Running", "JobsRunning"),
            ("GlideinsIdle", "GlideIdle"),
            ("GlideinsRunning", "GlideRunning"),
            ("GlideinsTotal", "GlideTotal"),
        ):
            ck, ek = karr
            if ck in client_monitor:
                el[ek] = int(client_monitor[ck])

        if "LastHeardFrom" in client_internals:
            el["InfoAge"] = int(time.time() - int(client_internals["LastHeardFrom"]))
            el["InfoAgeAvgCounter"] = 1  # used for totals since we need an avg in totals, not absnum

        self.updated = time.time()

    def get_data(self):
        data1 = copy.deepcopy(self.data)
        for f in list(data1.keys()):
            fe = data1[f]
            for w in list(fe.keys()):
                el = fe[w]
                for a in list(el.keys()):
                    if a[-10:] == "AvgCounter":  # do not publish avgcounter fields... they are internals
                        del el[a]

        return data1

    def get_xml_data(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        data = self.get_data()
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

    def get_total(self):
        total = {"Status": None, "Requested": None, "ClientMonitor": None}
        numtypes = (int, int, float)

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
                            if type(el[a]) in numtypes:  # copy only numbers
                                tel[a] = el[a]
                    else:
                        # successive, sum
                        for a in list(el.keys()):
                            if type(el[a]) in numtypes:  # consider only numbers
                                if a in tel:
                                    tel[a] += el[a]
                            # if other frontends did't have this attribute, ignore
                        # if any attribute from prev. frontends are not in the current one, remove from total
                        for a in list(tel.keys()):
                            if a not in el:
                                del tel[a]
                            elif not (type(el[a]) in numtypes):
                                del tel[a]

        for w in list(total.keys()):
            if total[w] is None:
                del total[w]  # remove entry if not defined
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

        return total

    def get_xml_total(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        total = self.get_total()
        return xmlFormat.class2string(total, inst_name="total", indent_tab=indent_tab, leading_tab=leading_tab)

    def get_xml_updated(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        return xmlFormat.time2xml(self.updated, "updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab="")

    def write_file(self):
        global monitoringConfig

        if (self.files_updated is not None) and ((self.updated - self.files_updated) < 5):
            # files updated recently, no need to redo it
            return

        # write snaphot file
        xml_str = (
            '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
            + "<glideFactoryEntryQStats>\n"
            + self.get_xml_updated(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + self.get_xml_data(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + self.get_xml_total(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB)
            + "\n"
            + "</glideFactoryEntryQStats>\n"
        )
        monitoringConfig.write_file("schedd_status.xml", xml_str)

        data = self.get_data()
        total_el = self.get_total()

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

            # init, so that all get created properly
            for tp in list(self.attributes.keys()):
                tp_str = type_strings[tp]
                attributes_tp = self.attributes[tp]
                for a in attributes_tp:
                    val_dict[f"{tp_str}{a}"] = None

            monitoringConfig.establish_dir(fe_dir)
            for tp in list(fe_el.keys()):
                # values (RRD type) - Status, Requested or ClientMonitor
                if not (tp in list(self.attributes.keys())):
                    continue

                tp_str = type_strings[tp]

                attributes_tp = self.attributes[tp]

                fe_el_tp = fe_el[tp]
                for a in list(fe_el_tp.keys()):
                    if a in attributes_tp:
                        a_el = fe_el_tp[a]
                        if not isinstance(a_el, dict):  # ignore subdictionaries
                            val_dict[f"{tp_str}{a}"] = a_el

            monitoringConfig.write_rrd_multi("%s/Status_Attributes" % fe_dir, "GAUGE", self.updated, val_dict)

        self.files_updated = self.updated
        return


############### P R I V A T E ################

##################################################
def tmp2final(fname):
    """
    This exact method is also in glideFactoryMonitoring.py
    """
    try:
        os.remove(fname + "~")
    except:
        pass

    try:
        os.rename(fname, fname + "~")
    except:
        pass

    try:
        os.rename(fname + ".tmp", fname)
    except:
        print(f"Failed renaming {fname}.tmp into {fname}")
        logSupport.log.error(f"Failed renaming {fname}.tmp into {fname}")
    return


##################################################
def sanitize(name):
    good_chars = string.ascii_letters + string.digits + ".-"
    outarr = []
    for i in range(len(name)):
        if name[i] in good_chars:
            outarr.append(name[i])
        else:
            outarr.append("_")
    return "".join(outarr)


##################################################

# global configuration of the module
monitoringConfig = MonitoringConfig()


def write_frontend_descript_xml(frontendDescript, monitor_dir):
    """
    Writes out the frontend descript.xml file in the monitor web area.

    @type frontendDescript: FrontendDescript
    @param frontendDescript: contains the data in the frontend.descript file in the frontend instance dir
    @type monitor_dir: string
    @param monitor_dir: filepath the the monitor dir in the frontend instance dir
    """

    frontend_data = copy.deepcopy(frontendDescript.data)

    frontend_str = '<frontend FrontendName="%s"' % frontend_data["FrontendName"] + "/>"

    dis_link_txt = 'display_txt="{}"  href_link="{}"'.format(
        frontend_data["MonitorDisplayText"],
        frontend_data["MonitorLink"],
    )
    footer_str = "<monitor_footer " + dis_link_txt + "/>"

    output = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'
        + "<glideinFrontendDescript>\n"
        + xmlFormat.time2xml(
            time.time(), "updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB
        )
        + "\n"
        + xmlFormat.DEFAULT_TAB
        + frontend_str
        + "\n"
        + xmlFormat.DEFAULT_TAB
        + footer_str
        + "\n"
        + "</glideinFrontendDescript>"
    )

    fname = os.path.join(monitor_dir, "descript.xml")

    try:
        with open(fname + ".tmp", "wb") as f:
            f.write(output.encode(BINARY_ENCODING))

        tmp2final(fname)

    except OSError:
        logSupport.log.exception("Error writing out the frontend descript.xml: ")
