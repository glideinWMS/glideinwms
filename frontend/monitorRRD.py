import shutil
import tempfile
import time, os
from glideinwms.frontend.glideinFrontendMonitoring import Monitoring_Output, sanitize
from glideinwms.lib import rrdSupport
from glideinwms.lib import logSupport


# PM: Nov 26, 2014
# There is a limit on rrd field names. Max allowed is 20 chars long.
# RRD enforces this limit while creating fields, but will not enforce the limits
# when trying to read from a field with name longer than 20 chars.
# Truncate the names for following to be in limits to avoid above issue.
frontend_status_attributes = {
    'Jobs':("Idle", "OldIdle", "Running", "Total", "Idle_3600"),
    'Glideins':("Idle", "Running", "Total"),
    'MatchedJobs':("Idle", "EffIdle", "OldIdle", "Running", "RunningHere"),
    'MatchedGlideins':("Total", "Idle", "Running", "Failed"),
    #'MatchedGlideins':("Total","Idle","Running","Failed","TCores","ICores","RCores"),
    'MatchedCores':("Total", "Idle", "Running"),
    'Requested':("Idle", "MaxRun")
}

frontend_total_type_strings = {
    'Jobs':'Jobs',
    'Glideins':'Glidein',
    'MatchedJobs':'MatchJob',
    'MatchedGlideins':'MatchGlidein',
    'MatchedCores':'MatchCore',
    'Requested':'Req'
}

frontend_job_type_strings = {
    'MatchedJobs':'MatchJob',
    'MatchedGlideins':'MatchGlidein',
    'MatchedCores':'MatchCore',
    'Requested':'Req'
}

# Default Configuration
DEFAULT_CONFIG = {"attributes": {
            'Jobs':("Idle", "OldIdle", "Running", "Total", "Idle_3600"),
            'Glideins':("Idle", "Running", "Total"),
            'MatchedJobs':("Idle", "EffIdle", "OldIdle", "Running", "RunningHere"),
            #'MatchedGlideins':("Total","Idle","Running","Failed","TotalCores","IdleCores","RunningCores"),
            'MatchedGlideins':("Total", "Idle", "Running", "Failed"),
            'MatchedCores':("Total", "Idle", "Running"),
            'Requested':("Idle", "MaxRun")
        },
    "rrd_step": 300,       #default to 5 minutes
    "rrd_heartbeat": 1800, #default to 30 minutes, should be at least twice the loop time
    "rrd_archives": [('AVERAGE', 0.8, 1, 740),      # max precision, keep 2.5 days
                           ('AVERAGE', 0.92, 12, 740),       # 1 h precision, keep for a month (30 days)
                           ('AVERAGE', 0.98, 144, 740)        # 12 hour precision, keep for a year
                           ],
    "states_names": ('Unmatched', 'MatchedUp', 'MatchedDown'),
    "factoryStats_attributes": {'Jobs':("Idle", "OldIdle", "Running", "Total"),
                         'Matched':("Idle", "OldIdle", "Running", "Total"),
                         'Requested':("Idle", "MaxRun"),
                         'Slots':("Idle", "Running", "Total")},
    "name": "monitorRRD"
}

DEFAULT_CONFIG_AGGR = {}


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

        # Used in verification
        self.rrd_problems_found = False

    def write_groupStats(self, total, factories_data, states_data, updated):
        self.updated = updated

        self.write_one_rrd("total", total)

        for fact in factories_data.keys():
            self.write_one_rrd("factory_%s" % sanitize(fact), factories_data[fact], 1)

        for fact in states_data.keys():
            self.write_one_rrd("state_%s" % sanitize(fact), states_data[fact], 1)

    def write_factoryStats(self, data, total_el, updated):
        self.updated = updated

        # update RRDs
        type_strings={'Status':'Status','Requested':'Req','ClientMonitor':'Client'}
        for fe in [None]+data.keys():
            if fe is None: # special key == Total
                fe_dir="total"
                fe_el=total_el
            else:
                fe_dir="frontend_"+fe
                fe_el=data[fe]

            val_dict={}

            #init, so that all get created properly
            for tp in self.config["factoryStats_attributes"].keys():
                tp_str=type_strings[tp]
                attributes_tp=self.config["factoryStats_attributes"][tp]
                for a in attributes_tp:
                    val_dict["%s%s"%(tp_str, a)]=None

            self.establish_dir(fe_dir)
            for tp in fe_el.keys():
                # type - Status, Requested or ClientMonitor
                if not (tp in self.config["factoryStats_attributes"].keys()):
                    continue

                tp_str=type_strings[tp]

                attributes_tp=self.config["factoryStats_attributes"][tp]

                fe_el_tp=fe_el[tp]
                for a in fe_el_tp.keys():
                    if a in attributes_tp:
                        a_el=fe_el_tp[a]
                        if not isinstance(a_el, dict): # ignore subdictionaries
                            val_dict["%s%s"%(tp_str, a)]=a_el

            self.write_rrd_multi("%s/Status_Attributes"%fe_dir,
                                             "GAUGE", self.updated, val_dict)

    def write_aggregation(self, global_fact_totals, updated, global_total, status):
        Monitoring_Output.establish_dir("total")
        self.write_one_rrd_aggr("total/Status_Attributes", updated, global_total, 0)

        for fact in global_fact_totals['factories'].keys():
            fe_dir = "total/factory_%s" % sanitize(fact)
            Monitoring_Output.establish_dir(fe_dir)
            self.write_one_rrd_aggr("%s/Status_Attributes" % fe_dir, updated, global_fact_totals['factories'][fact], 1)
        for fact in global_fact_totals['states'].keys():
            fe_dir = "total/state_%s" % sanitize(fact)
            Monitoring_Output.establish_dir(fe_dir)
            self.write_one_rrd_aggr("%s/Status_Attributes" % fe_dir, updated, global_fact_totals['states'][fact], 1)

    def verify(self, fix):
        if not (self.verifyRRD(fix["fix_rrd"])):
            self.verifyError = "Run with -fix_rrd option to update errors\n" \
                               "WARNING: back up your existing rrds before auto-fixing rrds"
            return True
        return False

    # Internal Functions

    ###############################
    # PRIVATE - Used by write_file
    # Write one RRD
    def write_one_rrd(self, name, data, fact=0):
        val_dict={}
        if fact==0:
            type_strings = {
                'Jobs':'Jobs',
                'Glideins':'Glidein',
                'MatchedJobs':'MatchJob',
                'MatchedGlideins':'MatchGlidein',
                'MatchedCores':'MatchCore',
                'Requested':'Req'
            }
        else:
            type_strings = {
                'MatchedJobs':'MatchJob',
                'MatchedGlideins':'MatchGlidein',
                'MatchedCores':'MatchCore',
                'Requested':'Req'
            }

        #init, so that all get created properly
        for tp in self.config["attributes"].keys():
            if tp in type_strings.keys():
                tp_str=type_strings[tp]
                attributes_tp=self.config["attributes"][tp]
                for a in attributes_tp:
                    val_dict["%s%s"%(tp_str, a)]=None


        for tp in data:
            # type - Jobs,Slots
            if not (tp in self.config["attributes"].keys()):
                continue
            if not (tp in type_strings.keys()):
                continue

            tp_str=type_strings[tp]

            attributes_tp=self.config["attributes"][tp]

            fe_el_tp=data[tp]
            for a in fe_el_tp.keys():
                if a in attributes_tp:
                    a_el=fe_el_tp[a]
                    if not isinstance(a_el, dict): # ignore subdictionaries
                        val_dict["%s%s"%(tp_str, a)]=a_el

        Monitoring_Output.establish_dir("%s"%name)
        self.write_rrd_multi("%s/Status_Attributes"%name,
                                         "GAUGE", self.updated, val_dict)

    def write_rrd_multi(self, relative_fname, ds_type, time, val_dict, min_val=None, max_val=None):
        """
        Create a RRD file, using rrdtool.
        """
        if self.rrd_obj.isDummy():
            return  # nothing to do, no rrd bin no rrd creation

        for tp in ((".rrd", self.config["rrd_archives"]),):
            rrd_ext, rrd_archives = tp
            fname = os.path.join(self.config["monitor_dir"], relative_fname + rrd_ext)
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
                    ds_arr.append((ds_name, ds_type, self.config["rrd_heartbeat"], min_val, max_val))
                self.rrd_obj.create_rrd_multi(fname,
                                              self.config["rrd_step"], rrd_archives,
                                              ds_arr)

            # print "Updating RRD "+fname
            try:
                self.rrd_obj.update_rrd_multi(fname, time, val_dict)
            except Exception as e:
                logSupport.log.error("Failed to update %s" % fname)
                # logSupport.log.exception(traceback.format_exc())
        return


    ####################################
    # PRIVATE - Used by aggregateStatus
    # Write one RRD
    def write_one_rrd_aggr(self, name, updated, data, fact=0):
        if fact == 0:
            type_strings = frontend_total_type_strings
        else:
            type_strings = frontend_job_type_strings

        # initialize the RRD dictionary, so it gets created properly
        val_dict = {}
        for tp in frontend_status_attributes.keys():
            if tp in type_strings.keys():
                tp_str = type_strings[tp]
                attributes_tp = frontend_status_attributes[tp]
                for a in attributes_tp:
                    val_dict["%s%s" % (tp_str, a)] = None

        for tp in data.keys():
            # type - status or requested
            if not (tp in frontend_status_attributes.keys()):
                continue
            if not (tp in type_strings.keys()):
                continue

            tp_str = type_strings[tp]
            attributes_tp = frontend_status_attributes[tp]

            tp_el = data[tp]

            for a in tp_el.keys():
                if a in attributes_tp:
                    a_el = int(tp_el[a])
                    if not isinstance(a_el, dict):  # ignore subdictionaries
                        val_dict["%s%s" % (tp_str, a)] = a_el

        Monitoring_Output.establish_dir("%s" % name)
        self.write_rrd_multi("%s" % name, "GAUGE", updated, val_dict)

    def verifyHelper(self, filename,dict, fix_rrd=False):
        """
        Helper function for verifyRRD.  Checks one file,
        prints out errors.  if fix_rrd, will attempt to
        dump out rrd to xml, add the missing attributes,
        then restore.  Original file is obliterated.

        @param filename: filename of rrd to check
        @param dict: expected dictionary
        @param fix_rrd: if true, will attempt to add missing attrs
        """
        if not os.path.exists(filename):
            print("WARNING: %s missing, will be created on restart" % (filename))
            return
        rrd_obj=rrdSupport.rrdSupport()
        (missing, extra)=rrd_obj.verify_rrd(filename, dict)
        for attr in extra:
            print("ERROR: %s has extra attribute %s" % (filename, attr))
            if fix_rrd:
                print("ERROR: fix_rrd cannot fix extra attributes")
        if not fix_rrd:
            for attr in missing:
                print("ERROR: %s missing attribute %s" % (filename, attr))
            if len(missing) > 0:
                self.rrd_problems_found=True
        if fix_rrd and (len(missing) > 0):
            (f, tempfilename)=tempfile.mkstemp()
            (out, tempfilename2)=tempfile.mkstemp()
            (restored, restoredfilename)=tempfile.mkstemp()
            backup_str=str(int(time.time()))+".backup"
            print("Fixing %s... (backed up to %s)" % (filename, filename+backup_str))
            os.close(out)
            os.close(restored)
            os.unlink(restoredfilename)
            #Use exe version since dump, restore not available in rrdtool
            dump_obj=rrdSupport.rrdtool_exe()
            outstr=dump_obj.dump(filename)
            for line in outstr:
                os.write(f, "%s\n"%line)
            os.close(f)
            rrdSupport.addDataStore(tempfilename, tempfilename2, missing)
            os.unlink(filename)
            outstr=dump_obj.restore(tempfilename2, restoredfilename)
            os.unlink(tempfilename)
            os.unlink(tempfilename2)
            shutil.move(restoredfilename, filename)
        if len(extra) > 0:
            self.rrd_problems_found=True

    def verifyRRD(self, fix_rrd=False):
        """
        Go through all known monitoring rrds and verify that they
        match existing schema (could be different if an upgrade happened)
        If fix_rrd is true, then also attempt to add any missing attributes.
        """
        # FROM: migration_3_1
        # dir=monitorAggregatorConfig.monitor_dir
        # total_dir=os.path.join(dir, "total")
        mon_dir = Monitoring_Output.global_config_aggr["monitor_dir"]

        status_dict = {}
        status_total_dict = {}
        for tp in frontend_status_attributes.keys():
            if tp in frontend_total_type_strings.keys():
                tp_str = frontend_total_type_strings[tp]
                attributes_tp = frontend_status_attributes[tp]
                for a in attributes_tp:
                    status_total_dict["%s%s" % (tp_str, a)] = None
            if tp in frontend_job_type_strings.keys():
                tp_str = frontend_job_type_strings[tp]
                attributes_tp = frontend_status_attributes[tp]
                for a in attributes_tp:
                    status_dict["%s%s" % (tp_str, a)] = None

        if not os.path.isdir(mon_dir):
            print("WARNING: monitor/ directory does not exist, skipping rrd verification.")
            return True
        # FROM: migration_3_1
        # for filename in os.listdir(dir):
        #     if (filename[:6]=="group_") or (filename=="total"):
        #         current_dir=os.path.join(dir, filename)
        #         if filename=="total":
        #             verifyHelper(os.path.join(current_dir,
        #                 "Status_Attributes.rrd"), status_total_dict, fix_rrd)
        #         for dirname in os.listdir(current_dir):
        #             current_subdir=os.path.join(current_dir, dirname)
        #             if dirname[:6]=="state_":
        #                 verifyHelper(os.path.join(current_subdir,
        #                     "Status_Attributes.rrd"), status_dict, fix_rrd)
        #             if dirname[:8]=="factory_":
        #                 verifyHelper(os.path.join(current_subdir,
        #                     "Status_Attributes.rrd"), status_dict, fix_rrd)
        #             if dirname=="total":
        #                 verifyHelper(os.path.join(current_subdir,
        #                     "Status_Attributes.rrd"), status_total_dict, fix_rrd)
        for dir_name, sdir_name, f_list in os.walk(mon_dir):
            for file_name in f_list:
                if file_name == 'Status_Attributes.rrd':
                    if os.path.basename(dir_name) == 'total':
                        self.verifyHelper(os.path.join(dir_name, file_name),
                                     status_total_dict, fix_rrd)
                    else:
                        self.verifyHelper(os.path.join(dir_name, file_name),
                                     status_dict, fix_rrd)

        return not self.rrd_problems_found