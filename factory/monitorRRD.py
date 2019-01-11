import time, os
from glideinwms.factory.glideFactoryMonitoring import Monitoring_Output
from glideinwms.lib import rrdSupport

# Default Configuration
DEFAULT_CONFIG = {"name": "monitorRRD"}

DEFAULT_CONFIG_AGGR = {}

# list of rrd files that each site has
rrd_list = ('Status_Attributes.rrd', 'Log_Completed.rrd', 'Log_Completed_Stats.rrd', 'Log_Completed_WasteTime.rrd', 'Log_Counts.rrd')

# noinspection PyRedeclaration
class Monitoring_Output(Monitoring_Output):
    def __init__(self, config, configAgg):
        # Get Default Config from Parent
        super(Monitoring_Output, self).__init__()

        # Set Default Config for this Child
        for key in DEFAULT_CONFIG:
            self.config[key] = DEFAULT_CONFIG[key]

        for key in DEFAULT_CONFIG_AGGR:
            self.configAggr[key] = DEFAULT_CONFIG_AGGR[key]

        # Set Config from Pass Parameters (from the Frontend XML Config File)
        for key in config:
            self.config[key] = config[key]

        for key in configAgg:
            self.configAggr[key] = configAgg[key]

        self.rrd_obj = rrdSupport.rrdSupport()

        self.updated = time.time()

        # Should be changed

        self.rrd_step = 300        # default to 5 minutes
        self.rrd_heartbeat = 1800  # default to 30 minutes, should be at least twice the loop time
        self.rrd_ds_name = "val"
        self.rrd_archives = [('AVERAGE', 0.8, 1, 740),  # max precision, keep 2.5 days
                             ('AVERAGE', 0.92, 12, 740),  # 1 h precision, keep for a month (30 days)
                             ('AVERAGE', 0.98, 144, 740)  # 12 hour precision, keep for a year
                             ]

        self.attributes = {'Status': (
        "Idle", "Running", "Held", "Wait", "Pending", "StageIn", "IdleOther", "StageOut", "RunningCores"),
                           'Requested': ("Idle", "MaxGlideins", "IdleCores", "MaxCores"),
                           'ClientMonitor': (
                           "InfoAge", "JobsIdle", "JobsRunning", "JobsRunHere", "GlideIdle", "GlideRunning",
                           "GlideTotal", "CoresIdle", "CoresRunning", "CoresTotal")}

    def write_condorQStats(self, data, total_el):
        # update RRDs
        type_strings = {'Status': 'Status', 'Requested': 'Req', 'ClientMonitor': 'Client'}
        for fe in [None] + data.keys():
            if fe is None:  # special key == Total
                fe_dir = "total"
                fe_el = total_el
            else:
                fe_dir = "frontend_" + fe
                fe_el = data[fe]

            val_dict = {}
            # Initialize,  so that all get created properly
            for tp in self.attributes.keys():
                tp_str = type_strings[tp]
                attributes_tp = self.attributes[tp]
                for a in attributes_tp:
                    val_dict["%s%s" % (tp_str, a)] = None

            self.establish_dir(fe_dir)
            for tp in fe_el.keys():
                # type - Status, Requested or ClientMonitor
                if not (tp in self.attributes.keys()):
                    continue

                tp_str = type_strings[tp]

                attributes_tp = self.attributes[tp]

                fe_el_tp = fe_el[tp]
                for a in fe_el_tp.keys():
                    if a in attributes_tp:
                        a_el = fe_el_tp[a]
                        if not isinstance(a_el, dict): # ignore subdictionaries
                            val_dict["%s%s" % (tp_str, a)] = a_el

            self.write_rrd_multi("%s/Status_Attributes" % fe_dir,
                                             "GAUGE", self.updated, val_dict)


    def write_condorLogSummary(self, fe_dir, val_dict_counts_desc, val_dict_counts, val_dict_completed, val_dict_stats, val_dict_wastetime):
        self.write_rrd_multi_hetero("%s/Log_Counts" % fe_dir,
                                                val_dict_counts_desc, self.updated, val_dict_counts)
        self.write_rrd_multi("%s/Log_Completed" % fe_dir,
                                         "ABSOLUTE", self.updated, val_dict_completed)
        self.write_completed_json("%s/Log_Completed" % fe_dir, self.updated, val_dict_completed)
        self.write_rrd_multi("%s/Log_Completed_Stats" % fe_dir,
                                         "ABSOLUTE", self.updated, val_dict_stats)
        self.write_completed_json("%s/Log_Completed_Stats" % fe_dir, self.updated, val_dict_stats)
        # Disable Waste RRDs... WasteTime much more useful
        # monitoringConfig.write_rrd_multi("%s/Log_Completed_Waste"%fe_dir,
        #                                 "ABSOLUTE",self.updated,val_dict_waste)
        self.write_rrd_multi("%s/Log_Completed_WasteTime" % fe_dir,
                                         "ABSOLUTE", self.updated, val_dict_wastetime)


    def write_aggregateStatus(self, global_total, status_attributes, type_strings, updated, val_dict, status_fe):
        self.establish_dir("total")
        # Total rrd across all frontends and factories
        for tp in global_total.keys():
            # type - status or requested
            if not (tp in status_attributes.keys()):
                continue

            tp_str = type_strings[tp]
            attributes_tp = status_attributes[tp]

            tp_el = global_total[tp]

            for a in tp_el.keys():
                if a in attributes_tp:
                    a_el = int(tp_el[a])
                    val_dict["%s%s" % (tp_str, a)] = a_el

        self.write_rrd_multi("total/Status_Attributes",
                                                                "GAUGE", updated, val_dict)

        # Frontend total rrds across all factories
        for fe in status_fe['frontends'].keys():
            self.establish_dir("total/%s" % ("frontend_" + fe))
            for tp in status_fe['frontends'][fe].keys():
                # type - status or requested
                if not (tp in type_strings.keys()):
                    continue
                tp_str = type_strings[tp]
                attributes_tp = status_attributes[tp]

                tp_el = status_fe['frontends'][fe][tp]

                for a in tp_el.keys():
                    if a in attributes_tp:
                        a_el = int(tp_el[a])
                        val_dict["%s%s" % (tp_str, a)] = a_el
            self.write_rrd_multi("total/%s/Status_Attributes" % ("frontend_" + fe),
                                                                    "GAUGE", updated, val_dict)


    def write_writeLogSummary(self, fe_dir, val_dict_counts_desc, updated, val_dict_counts, val_dict_completed, val_dict_stats, val_dict_wastetime):
        self.write_rrd_multi_hetero("%s/Log_Counts" % fe_dir,
                                                                       val_dict_counts_desc, updated, val_dict_counts)
        self.write_rrd_multi("%s/Log_Completed" % fe_dir,
                                                                "ABSOLUTE", updated, val_dict_completed)
        self.write_rrd_multi("%s/Log_Completed_Stats" % fe_dir,
                                                                "ABSOLUTE", updated, val_dict_stats)
        # Disable Waste RRDs... WasteTime much more useful
        # glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Completed_Waste"%fe_dir,
        #                                                        "ABSOLUTE",updated,val_dict_waste)
        self.write_rrd_multi("%s/Log_Completed_WasteTime" % fe_dir,
                                                                "ABSOLUTE", updated, val_dict_wastetime)


    # Internal Functions

    def write_rrd_multi(self, relative_fname, ds_type, time, val_dict, min_val=None, max_val=None):
        """
        Create a RRD file, using rrdtool.
        """
        if self.rrd_obj.isDummy():
            return  # nothing to do, no rrd bin no rrd creation

        # MM don't understand the need for this loop, there is only one element in the tuple, why not:
        # rrd_ext = ".rrd"
        # rrd_archives = self.rrd_archives
        for tp in ((".rrd", self.rrd_archives),):
            rrd_ext, rrd_archives = tp
            fname = os.path.join(Monitoring_Output.global_config["monitor_dir"], relative_fname + rrd_ext)
            # print "Writing RRD "+fname

            if not os.path.isfile(fname):
                # print "Create RRD "+fname
                if min_val is None:
                    min_val = 'U'
                if max_val is None:
                    max_val = 'U'
                ds_names = sorted(val_dict.keys())

                ds_arr = []
                for ds_name in ds_names:
                    ds_arr.append((ds_name, ds_type, self.rrd_heartbeat, min_val, max_val))
                self.rrd_obj.create_rrd_multi(fname,
                                              self.rrd_step, rrd_archives,
                                              ds_arr)

            # print "Updating RRD "+fname
            try:
                self.rrd_obj.update_rrd_multi(fname, time, val_dict)
            except Exception as e:  # @UnusedVariable
                Monitoring_Output.global_config["log"].exception("Failed to update %s: " % fname)
        return

    def write_rrd_multi_hetero(self, relative_fname, ds_desc_dict, time, val_dict):
        """Create a RRD file, using rrdtool.
        Like write_rrd_multi, but with each ds having each a specified type
        each element of ds_desc_dict is a dictionary with any of ds_type, min, max
        if ds_desc_dict[name] is not present, the defaults are {'ds_type':'GAUGE', 'min':'U', 'max':'U'}
        """
        if self.rrd_obj.isDummy():
            return  # nothing to do, no rrd bin no rrd creation

        # MM don't understand the need for this loop, there is only one element in the tuple, why not:
        # rrd_ext = ".rrd"
        # rrd_archives = self.rrd_archives
        for tp in ((".rrd", self.rrd_archives),):
            rrd_ext, rrd_archives = tp
            fname = os.path.join(Monitoring_Output.global_config["monitor_dir"], relative_fname + rrd_ext)
            # print "Writing RRD "+fname

            if not os.path.isfile(fname):
                # print "Create RRD "+fname
                ds_names = sorted(val_dict.keys())

                ds_arr = []
                for ds_name in ds_names:
                    ds_desc = {'ds_type': 'GAUGE', 'min': 'U', 'max': 'U'}
                    if ds_name in ds_desc_dict:
                        for k in ds_desc_dict[ds_name].keys():
                            ds_desc[k] = ds_desc_dict[ds_name][k]

                    ds_arr.append((ds_name, ds_desc['ds_type'], self.rrd_heartbeat, ds_desc['min'], ds_desc['max']))
                self.rrd_obj.create_rrd_multi(fname,
                                              self.rrd_step, rrd_archives,
                                              ds_arr)

            # print "Updating RRD "+fname
            try:
                self.rrd_obj.update_rrd_multi(fname, time, val_dict)
            except Exception as e:  # @UnusedVariable
                Monitoring_Output.global_config["log"].exception("Failed to update %s: " % fname)
        return