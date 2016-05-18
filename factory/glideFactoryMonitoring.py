#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This module implements the functions needed
#   to monitor the glidein factory
#
# Author:
#   Igor Sfiligoi (Dec 11th 2006)
#

import os
import time
import copy
import math
from glideinwms.lib import xmlFormat
from glideinwms.lib import timeConversion
from glideinwms.lib import rrdSupport
from glideinwms.lib import logSupport
from glideinwms.lib import cleanupSupport
from glideinwms.factory import glideFactoryLib
from glideinwms.lib import util

# list of rrd files that each site has
rrd_list = ('Status_Attributes.rrd', 'Log_Completed.rrd', 'Log_Completed_Stats.rrd', 'Log_Completed_WasteTime.rrd', 'Log_Counts.rrd')

############################################################
#
# Configuration
#
############################################################

class MonitoringConfig:
    def __init__(self, log=logSupport.log):
        # set default values
        # user should modify if needed
        self.rrd_step = 300       #default to 5 minutes
        self.rrd_heartbeat = 1800 #default to 30 minutes, should be at least twice the loop time
        self.rrd_ds_name = "val"
        self.rrd_archives = [('AVERAGE', 0.8, 1, 740), # max precision, keep 2.5 days
                           ('AVERAGE', 0.92, 12, 740), # 1 h precision, keep for a month (30 days)
                           ('AVERAGE', 0.98, 144, 740)        # 12 hour precision, keep for a year
                           ]

        self.monitor_dir = "monitor/"

        self.log_dir = "log/"
        self.logCleanupObj = None

        self.rrd_obj = rrdSupport.rrdSupport()
        """@ivar: The name of the attribute that identifies the glidein """
        self.my_name = "Unknown"
        self.log = log

    def config_log(self, log_dir, max_days, min_days, max_mbs):
        self.log_dir = log_dir
        cleaner = cleanupSupport.PrivsepDirCleanupWSpace(
                      None , log_dir, "(completed_jobs_.*\.log)",
                      int(max_days * 24 * 3600), int(min_days * 24 * 3600),
                      long(max_mbs * (1024.0 * 1024.0)))
        cleanupSupport.cleaners.add_cleaner(cleaner)

    def logCompleted(self,client_name,entered_dict):
        """
        This function takes all newly completed glideins and
        logs them in logs/entry_Name/completed_jobs_date.log in an
        XML-like format.
    
        @type client_name: String
        @param client_name: the name of the frontend client 
        @type entered_dict: Dictionary of dictionaries
        @param entered_dict: This is the dictionary of all jobs that have "Entered" the "Completed" states.  It is indexed by job_id.  Each data is an info dictionary containing the keys: username, jobs_duration (subkeys:total,goodput,terminated), wastemill (subkeys:validation,idle,nosuccess,badput) , duration, condor_started, condor_duration, jobsnr
        """
        now=time.time()

        job_ids = entered_dict.keys()
        if len(job_ids) == 0:
            return # nothing to do
        job_ids.sort()

        relative_fname = "completed_jobs_%s.log" % time.strftime("%Y%m%d", time.localtime(now))
        fname = os.path.join(self.log_dir, relative_fname)
        fd = open(fname, "a")
        try:
            for job_id in job_ids:
                el=entered_dict[job_id]
                username=el['username']
                username=username.split(":")[0]
                jobs_duration=el['jobs_duration']
                waste_mill=el['wastemill']
                fd.write(("<job %37s %34s %22s %17s %17s %22s %24s>"%(('terminated="%s"'%timeConversion.getISO8601_Local(now)),
                                                                 ('client="%s"'%client_name),
                                                                 ('username="%s"'%username),
                                                                 ('id="%s"'%job_id),
                                                                 ('duration="%i"'%el['duration']),
                                                                 ('condor_started="%s"'%(el['condor_started']==True)),
                                                                 ('condor_duration="%i"'%el['condor_duration'])))+
                         ("<user %14s %17s %16s %19s/>"%(('jobsnr="%i"'%el['jobsnr']),
                                                         ('duration="%i"'%jobs_duration['total']),
                                                         ('goodput="%i"'%jobs_duration['goodput']),
                                                         ('terminated="%i"'%jobs_duration['terminated'])))+
                         ("<wastemill %17s %11s %16s %13s/></job>\n"%(('validation="%i"'%waste_mill['validation']),
                                                                      ('idle="%i"'%waste_mill['idle']),
                                                                      ('nosuccess="%i"'%waste_mill['nosuccess']),
                                                                      ('badput="%i"'%waste_mill['badput']))))
        finally:
            fd.close()

    def write_file(self, relative_fname, output_str):
        """ 
        Writes out a string to a file
        @param relative_fname: The relative path name to write out
        @param str: the string to write to the file
        """
        fname=os.path.join(self.monitor_dir,relative_fname)
        #print "Writing "+fname
        fd = open(fname + ".tmp", "w")
        try:
            fd.write(output_str + "\n")
        finally:
            fd.close()

        util.file_tmp2final(fname, mask_exceptions=(self.log.error, "Failed rename/write into %s" % fname))
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
            return # nothing to do, no rrd bin no rrd creation

        for tp in ((".rrd", self.rrd_archives),):
            rrd_ext, rrd_archives = tp
            fname = os.path.join(self.monitor_dir, relative_fname + rrd_ext)
            #print "Writing RRD "+fname

            if not os.path.isfile(fname):
                #print "Create RRD "+fname
                if min_val is None:
                    min_val = 'U'
                if max_val is None:
                    max_val = 'U'
                ds_names = val_dict.keys()
                ds_names.sort()

                ds_arr = []
                for ds_name in ds_names:
                    ds_arr.append((ds_name, ds_type, self.rrd_heartbeat, min_val, max_val))
                self.rrd_obj.create_rrd_multi(fname,
                                              self.rrd_step, rrd_archives,
                                              ds_arr)

            #print "Updating RRD "+fname
            try:
                self.rrd_obj.update_rrd_multi(fname, time, val_dict)
            except Exception, e: #@UnusedVariable
                self.log.exception("Failed to update %s: " % fname)
        return

    # like write_rrd_multi, but with each ds having each type
    # each element of ds_desc_dict is a dictionary with any of
    #  ds_type, min, max
    # if not present, the defaults are ('GAUGE','U','U')
    def write_rrd_multi_hetero(self, relative_fname, ds_desc_dict, time, val_dict):
        """
        Create a RRD file, using rrdtool.
        """
        if self.rrd_obj.isDummy():
            return # nothing to do, no rrd bin no rrd creation

        for tp in ((".rrd", self.rrd_archives),):
            rrd_ext, rrd_archives = tp
            fname = os.path.join(self.monitor_dir, relative_fname + rrd_ext)
            #print "Writing RRD "+fname

            if not os.path.isfile(fname):
                #print "Create RRD "+fname
                ds_names = val_dict.keys()
                ds_names.sort()

                ds_arr = []
                for ds_name in ds_names:
                    ds_desc = {'ds_type':'GAUGE', 'min':'U', 'max':'U'}
                    if ds_desc_dict.has_key(ds_name):
                        for k in ds_desc_dict[ds_name].keys():
                            ds_desc[k] = ds_desc_dict[ds_name][k]

                    ds_arr.append((ds_name, ds_desc['ds_type'], self.rrd_heartbeat, ds_desc['min'], ds_desc['max']))
                self.rrd_obj.create_rrd_multi(fname,
                                              self.rrd_step, rrd_archives,
                                              ds_arr)

            #print "Updating RRD "+fname
            try:
                self.rrd_obj.update_rrd_multi(fname, time, val_dict)
            except Exception, e: #@UnusedVariable
                self.log.exception("Failed to update %s: " % fname)
        return



#########################################################################################################################################
#
#  condorQStats
#
#  This class handles the data obtained from condor_q
#
#########################################################################################################################################

class condorQStats:
    def __init__(self, log=logSupport.log):
        self.data = {}
        self.updated = time.time()
        self.log = log

        self.files_updated = None
        self.attributes = {'Status':("Idle", "Running", "Held", "Wait", "Pending", "StageIn", "IdleOther", "StageOut"),
                         'Requested':("Idle", "MaxGlideins"),
                         'ClientMonitor':("InfoAge", "JobsIdle", "JobsRunning", "JobsRunHere", "GlideIdle", "GlideRunning", "GlideTotal")}
        # create a global downtime field since we want to propagate it in various places
        self.downtime = 'True'

    def logSchedd(self, client_name, qc_status):
        """
        qc_status is a dictionary of condor_status:nr_jobs
        """
        if self.data.has_key(client_name):
            t_el = self.data[client_name]
        else:
            t_el = {}
            self.data[client_name] = t_el

        if t_el.has_key('Status'):
            el = t_el['Status']
        else:
            el = {}
            t_el['Status'] = el

        status_pairs = ((1, "Idle"), (2, "Running"), (5, "Held"), (1001, "Wait"), (1002, "Pending"), (1010, "StageIn"), (1100, "IdleOther"), (4010, "StageOut"))
        for p in status_pairs:
            nr, status = p
            if not el.has_key(status):
                el[status] = 0
            if qc_status.has_key(nr):
                el[status] += qc_status[nr]

        self.updated = time.time()

    def logRequest(self, client_name, requests):
        """
        requests is a dictinary of requests
        params is a dictinary of parameters

        At the moment, it looks only for
          'IdleGlideins'
          'MaxGlideins'
        """
        if self.data.has_key(client_name):
            t_el = self.data[client_name]
        else:
            t_el = {}
            t_el['Downtime'] = {'status':self.downtime}
            self.data[client_name] = t_el

        if t_el.has_key('Requested'):
            el = t_el['Requested']
        else:
            el = {}
            t_el['Requested'] = el

        for reqpair in  (('IdleGlideins', 'Idle'), ('MaxGlideins', 'MaxGlideins')):
            org, new = reqpair
            if not el.has_key(new):
                el[new] = 0
            if requests.has_key(org):
                el[new] += requests[org]

        # Had to get rid of this
        # Does not make sense when one aggregates
        #el['Parameters']=copy.deepcopy(params)
        # Replacing with an empty list
        el['Parameters'] = {}

        self.updated = time.time()

    def logClientMonitor(self, client_name, client_monitor, client_internals,
                         fraction=1.0):
        """
        client_monitor is a dictinary of monitoring info
        client_internals is a dictinary of internals
        If fraction is specified it will be used to extract partial info

        At the moment, it looks only for
          'Idle'
          'Running'
          'RunningHere'
          'GlideinsIdle'
          'GlideinsRunning'
          'GlideinsTotal'
          'LastHeardFrom'
        """

        if self.data.has_key(client_name):
            t_el = self.data[client_name]
        else:
            t_el = {}
            self.data[client_name] = t_el

        if t_el.has_key('ClientMonitor'):
            el = t_el['ClientMonitor']
        else:
            el = {}
            t_el['ClientMonitor'] = el

        for karr in (('Idle', 'JobsIdle'), ('Running', 'JobsRunning'), ('RunningHere', 'JobsRunHere'), ('GlideinsIdle', 'GlideIdle'), ('GlideinsRunning', 'GlideRunning'), ('GlideinsTotal', 'GlideTotal')):
            ck, ek = karr
            if not el.has_key(ek):
                el[ek] = 0
            if client_monitor.has_key(ck):
                el[ek] += (client_monitor[ck] * fraction)
            elif ck == 'RunningHere':
                # for compatibility, if RunningHere not defined, use min between Running and GlideinsRunning
                if (client_monitor.has_key('Running') and client_monitor.has_key('GlideinsRunning')):
                    el[ek] += (min(client_monitor['Running'], client_monitor['GlideinsRunning']) * fraction)

        if not el.has_key('InfoAge'):
            el['InfoAge'] = 0
            el['InfoAgeAvgCounter'] = 0 # used for totals since we need an avg in totals, not absnum


        if client_internals.has_key('LastHeardFrom'):
            el['InfoAge'] += (int(time.time() - long(client_internals['LastHeardFrom'])) * fraction)
            el['InfoAgeAvgCounter'] += fraction

        self.updated = time.time()


    # call this after the last logClientMonitor
    def finalizeClientMonitor(self):
        # convert all ClinetMonitor numbers in integers
        # needed due to fraction calculations
        for client_name in self.data.keys():
            if self.data[client_name].has_key('ClientMonitor'):
                el = self.data[client_name]['ClientMonitor']
                for k in el.keys():
                    el[k] = int(round(el[k]))
        return

    def get_data(self):
        data1 = copy.deepcopy(self.data)
        for f in data1.keys():
            fe = data1[f]
            for w in fe.keys():
                el = fe[w]
                for a in el.keys():
                    if a[-10:] == 'AvgCounter': # do not publish avgcounter fields... they are internals
                        del el[a]

        return data1

    def get_xml_data(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        data = self.get_data()
        return xmlFormat.dict2string(data,
                                     dict_name="frontends", el_name="frontend",
                                     subtypes_params={"class":{'subclass_params':{'Requested':{'dicts_params':{'Parameters':{'el_name':'Parameter'}}}}}},
                                     indent_tab=indent_tab, leading_tab=leading_tab)

    def get_total(self):
        total = {'Status':None, 'Requested':None, 'ClientMonitor':None}

        for f in self.data.keys():
            fe = self.data[f]
            for w in fe.keys():
                if total.has_key(w): # ignore eventual not supported classes
                    el = fe[w]
                    tel = total[w]

                    if tel is None:
                        # first one, just copy over
                        total[w] = {}
                        tel = total[w]
                        for a in el.keys():
                            if type(el[a]) == type(1): # copy only numbers
                                tel[a] = el[a]
                    else:
                        # successive, sum
                        for a in el.keys():
                            if type(el[a]) == type(1): # consider only numbers
                                if tel.has_key(a):
                                    tel[a] += el[a]
                            # if other frontends did't have this attribute, ignore
                        # if any attribute from prev. frontends are not in the current one, remove from total
                        for a in tel.keys():
                            if not el.has_key(a):
                                del tel[a]
                            elif type(el[a]) != type(1):
                                del tel[a]

        for w in total.keys():
            if total[w] is None:
                del total[w] # remove entry if not defined
            else:
                tel = total[w]
                for a in tel.keys():
                    if a[-10:] == 'AvgCounter':
                        # this is an average counter, calc the average of the referred element
                        # like InfoAge=InfoAge/InfoAgeAvgCounter
                        aorg = a[:-10]
                        tel[aorg] = tel[aorg] / tel[a]
                        # the avgcount totals are just for internal purposes
                        del tel[a]

        return total

    def get_xml_total(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        total = self.get_total()
        return xmlFormat.class2string(total,
                                      inst_name="total",
                                      indent_tab=indent_tab, leading_tab=leading_tab)

    def get_xml_updated(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        return xmlFormat.time2xml(self.updated, "updated", indent_tab, leading_tab)

    def set_downtime(self, in_downtime):
        self.downtime = str(in_downtime)
        return

    def get_xml_downtime(self, leading_tab=xmlFormat.DEFAULT_TAB):
        xml_downtime = xmlFormat.dict2string({}, dict_name='downtime', el_name='', params={'status':self.downtime}, leading_tab=leading_tab)
        return xml_downtime

    def write_file(self, monitoringConfig=None):

        if monitoringConfig is None:
            monitoringConfig = globals()['monitoringConfig']

        if ( (self.files_updated is not None) and 
             ((self.updated - self.files_updated) < 5) ):
            # files updated recently, no need to redo it
            return


        # write snaphot file
        xml_str = ('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n' +
                 '<glideFactoryEntryQStats>\n' +
                 self.get_xml_updated(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                 self.get_xml_downtime(leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                 self.get_xml_data(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                 self.get_xml_total(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                 "</glideFactoryEntryQStats>\n")
        monitoringConfig.write_file("schedd_status.xml", xml_str)

        data = self.get_data()
        total_el = self.get_total()

        # update RRDs
        type_strings = {'Status':'Status', 'Requested':'Req', 'ClientMonitor':'Client'}
        for fe in [None] + data.keys():
            if fe is None: # special key == Total
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

            monitoringConfig.establish_dir(fe_dir)
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
                        if type(a_el) != type({}): # ignore subdictionaries
                            val_dict["%s%s" % (tp_str, a)] = a_el

            monitoringConfig.write_rrd_multi("%s/Status_Attributes" % fe_dir,
                                             "GAUGE", self.updated, val_dict)

        self.files_updated = self.updated
        return

#########################################################################################################################################
#
#  condorLogSummary
#
#  This class handles the data obtained from parsing the glidein log files
#
#########################################################################################################################################

class condorLogSummary:
    """
    This class handles the data obtained from parsing the glidein log files
    """

    def __init__(self, log=logSupport.log):
        self.data = {} # not used
        self.updated = time.time()
        self.updated_year = time.localtime(self.updated)[0]
        self.current_stats_data = {}     # will contain dictionary client->username->dirSummarySimple
        self.old_stats_data = {}
        self.stats_diff = {}             # will contain the differences
        self.job_statuses = ('Running', 'Idle', 'Wait', 'Held', 'Completed', 'Removed') #const
        self.job_statuses_short = ('Running', 'Idle', 'Wait', 'Held') #const

        self.files_updated = None
        self.log = log

    def reset(self):
        """
        Replaces old_stats_data with current_stats_data
        Sets current_stats_data to empty.
        This is called every iteration in order to later
        compare the diff of the previous iteration and current one
        to find any newly changed jobs (ie newly completed jobs)
        """
        # reserve only those that has been around this time
        new_stats_data = {}
        for c in self.stats_diff.keys():
            # but carry over all the users... should not change that often
            new_stats_data[c] = self.current_stats_data[c]

        self.old_stats_data = new_stats_data
        self.current_stats_data = {}

        # and flush out the differences
        self.stats_diff = {}

    def diffTimes(self, end_time, start_time):
        year = self.updated_year
        try:
            start_list = [year, int(start_time[0:2]), int(start_time[3:5]), int(start_time[6:8]), int(start_time[9:11]), int(start_time[12:14]), 0, 0, -1]
            end_list = [year, int(end_time[0:2]), int(end_time[3:5]), int(end_time[6:8]), int(end_time[9:11]), int(end_time[12:14]), 0, 0, -1]
        except ValueError:
            return -1 #invalid

        try:
            start_ctime = time.mktime(start_list)
            end_ctime = time.mktime(end_list)
        except TypeError:
            return -1 #invalid

        if start_ctime <= end_ctime:
            return end_ctime - start_ctime

        # else must have gone over the year boundary
        start_list[0] -= 1 #decrease start year
        try:
            start_ctime = time.mktime(start_list)
        except TypeError:
            return -1 #invalid

        return end_ctime - start_ctime


    def logSummary(self, client_name, stats):
        """
        log_stats taken during during an iteration of perform_work are
        added/merged into the condorLogSummary class here.

        @type stats: dictionary of glideFactoryLogParser.dirSummaryTimingsOut
        @param stats: Dictionary keyed by "username:client_int_name"
        client_int_name is needed for frontends with multiple groups
        """
        if not self.current_stats_data.has_key(client_name):
            self.current_stats_data[client_name] = {}

        for username in stats.keys():
            if not self.current_stats_data[client_name].has_key(username):
                self.current_stats_data[client_name][username] = stats[username].get_simple()
            else:
                self.current_stats_data[client_name][username].merge(stats[username])

        self.updated = time.time()
        self.updated_year = time.localtime(self.updated)[0]

    def computeDiff(self):
        """
        This function takes the current_stats_data from the current iteration
        and the old_stats_data from the last iteration (see reset() function)
        to create a diff of the data in the stats_diff dictionary.

        This stats_diff will be a dictionary with two entries for each
        status: "Entered" and "Exited" denoting which job ids have recently
        changed status, ie. 
        stats_diff[frontend][username:client_int_name]["Completed"]["Entered"]
        """
        for client_name in self.current_stats_data.keys():
            self.stats_diff[client_name]={}
            if self.old_stats_data.has_key(client_name):
                stats=self.current_stats_data[client_name]
                for username in stats.keys():
                    if self.old_stats_data[client_name].has_key(username):
                        self.stats_diff[client_name][username]=stats[username].diff(self.old_stats_data[client_name][username])

    def get_stats_data_summary(self):
        """
        Summarizes current_stats_data:
        Adds up current_stats_data[frontend][user:client][status]
        across all username keys.

        @return: returns dictionary stats_data[frontend][status]=count
        """
        stats_data={}
        for client_name in self.current_stats_data.keys():
            out_el = {}
            for s in self.job_statuses:
                if not (s in ('Completed', 'Removed')): # I don't have their numbers from inactive logs
                    count = 0
                    for username in self.current_stats_data[client_name].keys():
                        client_el = self.current_stats_data[client_name][username].data
                        if ((client_el is not None) and (s in client_el.keys())):
                            count += len(client_el[s])

                    out_el[s] = count
            stats_data[client_name] = out_el
        return stats_data

    def get_xml_stats_data(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        data = self.get_stats_data_summary()
        return xmlFormat.dict2string(data,
                                     dict_name="frontends", el_name="frontend",
                                     subtypes_params={"class":{}},
                                     indent_tab=indent_tab, leading_tab=leading_tab)

    # in: entered_list=self.stats_diff[*]['Entered']
    # out: entered_list[job_id]{'duration','condor_started','condor_duration','jobsnr',wastemill':{'validation','idle','nosuccess','badput'}}
    def get_completed_stats(self, entered_list):
        out_list = {}

        for enle in entered_list:
            enle_job_id = enle[0]
            enle_running_time = enle[2]
            enle_last_time = enle[3]
            enle_difftime = self.diffTimes(enle_last_time, enle_running_time)

            # get stats
            enle_stats = enle[4]
            username = 'unknown'
            enle_condor_started = 0
            enle_condor_duration = 0 # default is 0, in case it never started
            enle_glidein_duration = enle_difftime # best guess
            if enle_stats is not None:
                enle_condor_started = enle_stats['condor_started']
                if enle_stats.has_key('glidein_duration'):
                    enle_glidein_duration = enle_stats['glidein_duration']
                if enle_stats.has_key('username'):
                    username = enle_stats['username']
            if not enle_condor_started:
                # 100% waste_mill
                enle_nr_jobs = 0
                enle_jobs_duration = 0
                enle_goodput = 0
                enle_terminated_duration = 0
                enle_waste_mill = {'validation':1000,
                                 'idle':0,
                                 'nosuccess':0, #no jobs run, no failures
                                 'badput':1000}
            else:
                #get waste_mill
                enle_condor_duration = enle_stats['condor_duration']
                if enle_condor_duration is None:
                    enle_condor_duration = 0 # assume failed

                if enle_condor_duration > enle_glidein_duration: # can happen... Condor-G has its delays
                    enle_glidein_duration = enle_condor_duration

                # get waste numbers, in permill
                if (enle_condor_duration < 5): # very short means 100% loss
                    enle_nr_jobs = 0
                    enle_jobs_duration = 0
                    enle_goodput = 0
                    enle_terminated_duration = 0
                    enle_waste_mill = {'validation':1000,
                                     'idle':0,
                                     'nosuccess':0, #no jobs run, no failures
                                     'badput':1000}
                else:
                    if enle_stats.has_key('validation_duration'):
                        enle_validation_duration = enle_stats['validation_duration']
                    else:
                        enle_validation_duration = enle_difftime - enle_condor_duration
                    enle_condor_stats = enle_stats['stats']
                    enle_jobs_duration = enle_condor_stats['Total']['secs']
                    enle_nr_jobs = enle_condor_stats['Total']['jobsnr']
                    enle_waste_mill = {'validation':1000.0 * enle_validation_duration / enle_glidein_duration,
                                     'idle':1000.0 * (enle_condor_duration - enle_jobs_duration) / enle_condor_duration}
                    enle_goodput = enle_condor_stats['goodZ']['secs']
                    if enle_goodput > enle_jobs_duration:
                        enle_goodput = enle_jobs_duration # cannot be more
                    if enle_jobs_duration > 0:
                        enle_waste_mill['nosuccess'] = 1000.0 * (enle_jobs_duration - enle_goodput) / enle_jobs_duration
                    else:
                        enle_waste_mill['nosuccess'] = 0 #no jobs run, no failures
                    enle_terminated_duration = enle_goodput + enle_condor_stats['goodNZ']['secs']
                    if enle_terminated_duration > enle_jobs_duration:
                        enle_terminated_duration = enle_jobs_duration # cannot be more
                    enle_waste_mill['badput'] = 1000.0 * (enle_glidein_duration - enle_terminated_duration) / enle_glidein_duration

            out_list[enle_job_id] = {'username':username,
                                   'duration':enle_glidein_duration, 'condor_started':enle_condor_started, 'condor_duration':enle_condor_duration,
                                   'jobsnr':enle_nr_jobs, 'jobs_duration':{'total':enle_jobs_duration, 'goodput':enle_goodput, 'terminated':enle_terminated_duration},
                                   'wastemill':enle_waste_mill}

        return out_list

    # in: entered_list=get_completed_data()
    # out: {'Lasted':{'2hours':...,...},'Sum':{...:12,...},'JobsNr':...,
    #       'Waste':{'validation':{'0m':...,...},...},'WasteTime':{...:{...},...}}
    def summarize_completed_stats(self, entered_list):
        # summarize completed data
        count_entered_times = {}
        for enle_timerange in getAllTimeRanges():
            count_entered_times[enle_timerange] = 0 # make sure all are initialized

        count_jobnrs = {}
        for enle_jobrange in getAllJobRanges():
            count_jobnrs[enle_jobrange] = 0 # make sure all are initialized

        count_jobs_duration = {};
        for enle_jobs_duration_range in getAllTimeRanges():
            count_jobs_duration[enle_jobs_duration_range] = 0 # make sure all are intialized

        count_total=getLogCompletedDefaults()
        
        count_waste_mill={'validation':{},
                          'idle':{},
                          'nosuccess':{}, #i.e. everything but jobs terminating with 0
                          'badput':{}} #i.e. everything but jobs terminating
        for w in count_waste_mill.keys():
            count_waste_mill_w = count_waste_mill[w]
            for enle_waste_mill_w_range in getAllMillRanges():
                count_waste_mill_w[enle_waste_mill_w_range] = 0 # make sure all are intialized
        time_waste_mill = {'validation':{},
                          'idle':{},
                          'nosuccess':{}, #i.e. everything but jobs terminating with 0
                          'badput':{}} #i.e. everything but jobs terminating
        for w in time_waste_mill.keys():
            time_waste_mill_w = time_waste_mill[w]
            for enle_waste_mill_w_range in getAllMillRanges():
                time_waste_mill_w[enle_waste_mill_w_range] = 0 # make sure all are intialized

        for enle_job in entered_list.keys():
            enle = entered_list[enle_job]
            enle_waste_mill = enle['wastemill']
            enle_glidein_duration = enle['duration']
            enle_condor_duration = enle['condor_duration']
            enle_jobs_nr = enle['jobsnr']
            enle_jobs_duration = enle['jobs_duration']
            enle_condor_started = enle['condor_started']

            count_total['Glideins'] += 1
            if not enle_condor_started:
                count_total['FailedNr'] += 1

            # find and save time range
            count_total['Lasted'] += enle_glidein_duration
            enle_timerange = getTimeRange(enle_glidein_duration)
            count_entered_times[enle_timerange] += 1

            count_total['CondorLasted'] += enle_condor_duration

            # find and save job range
            count_total['JobsNr'] += enle_jobs_nr
            enle_jobrange = getJobRange(enle_jobs_nr)
            count_jobnrs[enle_jobrange] += 1

            if enle_jobs_nr > 0:
                enle_jobs_duration_range = getTimeRange(enle_jobs_duration['total'] / enle_jobs_nr)
            else:
                enle_jobs_duration_range = getTimeRange(-1)
            count_jobs_duration[enle_jobs_duration_range] += 1

            count_total['JobsLasted'] += enle_jobs_duration['total']
            count_total['JobsTerminated'] += enle_jobs_duration['terminated']
            count_total['JobsGoodput'] += enle_jobs_duration['goodput']

            # find and save waste range
            for w in enle_waste_mill.keys():
                if w == "duration":
                    continue # not a waste
                # find and save time range
                enle_waste_mill_w_range = getMillRange(enle_waste_mill[w])

                count_waste_mill_w = count_waste_mill[w]
                count_waste_mill_w[enle_waste_mill_w_range] += 1

                time_waste_mill_w = time_waste_mill[w]
                time_waste_mill_w[enle_waste_mill_w_range] += enle_glidein_duration


        return {'Lasted':count_entered_times, 'JobsNr':count_jobnrs, 'Sum':count_total, 'JobsDuration':count_jobs_duration, 'Waste':count_waste_mill, 'WasteTime':time_waste_mill}

    def get_data_summary(self):
        """
        Summarizes stats_diff data (computeDiff should have
        already been called)
        Sums over username in the dictionary
        stats_diff[frontend][username][entered/exited][status]
        to make stats_data[client_name][entered/exited][status]=count

        @return: dictionary[client_name][entered/exited][status]=count
        """
        stats_data={}
        for client_name in self.stats_diff.keys():
            out_el = {'Current':{}, 'Entered':{}, 'Exited':{}}
            for s in self.job_statuses:
                entered = 0
                entered_list = []
                exited = 0
                for username in self.stats_diff[client_name].keys():
                    diff_el = self.stats_diff[client_name][username]

                    if ((diff_el is not None) and (s in diff_el.keys())):
                        entered_list += diff_el[s]['Entered']
                        entered += len(diff_el[s]['Entered'])
                        exited -= len(diff_el[s]['Exited'])

                out_el['Entered'][s] = entered
                if not (s in ('Completed', 'Removed')): # I don't have their numbers from inactive logs
                    count = 0
                    for username in self.current_stats_data[client_name].keys():
                        stats_el = self.current_stats_data[client_name][username].data

                        if ((stats_el is not None) and (s in stats_el.keys())):
                            count += len(stats_el[s])
                    out_el['Current'][s] = count
                    # and we can never get out of the terminal state
                    out_el['Exited'][s] = exited
                elif s == 'Completed':
                    completed_stats = self.get_completed_stats(entered_list)
                    completed_counts = self.summarize_completed_stats(completed_stats)
                    out_el['CompletedCounts'] = completed_counts
            stats_data[client_name] = out_el
        return stats_data

    def get_xml_data(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        data = self.get_data_summary()
        return xmlFormat.dict2string(data,
                                     dict_name="frontends", el_name="frontend",
                                     subtypes_params={"class":{'subclass_params':{'CompletedCounts':get_completed_stats_xml_desc()}
                                                               }},
                                     indent_tab=indent_tab, leading_tab=leading_tab)

    def get_stats_total(self):
        """
        @return: Dictionary with keys (wait,idle,running,held)
        """
        total={'Wait':None,'Idle':None,'Running':None,'Held':None}
        for k in total.keys():
            tdata = []
            for client_name in self.current_stats_data.keys():
                for username in self.current_stats_data[client_name]:
                    sdata = self.current_stats_data[client_name][username].data
                    if ((sdata is not None) and (k in sdata.keys())):
                        tdata = tdata + sdata[k]
            total[k] = tdata
        return total

    def get_stats_total_summary(self):
        in_total = self.get_stats_total()
        out_total = {}
        for k in in_total.keys():
            out_total[k] = len(in_total[k])
        return out_total

    def get_xml_stats_total(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        total = self.get_stats_total_summary()
        return xmlFormat.class2string(total,
                                      inst_name="total",
                                      indent_tab=indent_tab, leading_tab=leading_tab)

    def get_diff_summary(self):
        """
        Flattens stats_diff differential data.

        @return: Dictionary of client_name with sub_keys Wait,Idle,Running,Held,Completed,Removed
        """
        out_data={}
        for client_name in self.stats_diff.keys():
            client_el = {'Wait':None, 'Idle':None, 'Running':None, 'Held':None, 'Completed':None, 'Removed':None}
            for k in client_el.keys():
                client_el[k] = {'Entered':[], 'Exited':[]}
                tdata = client_el[k]
                #flatten all usernames into one
                for username in self.stats_diff[client_name].keys():
                    sdiff = self.stats_diff[client_name][username]
                    if ((sdiff is not None) and (k in sdiff.keys())):
                        if k == 'Completed':
                            # for completed jobs, add the username
                            # not for the others since there is no adequate place in the object
                            for sdel in sdiff[k]['Entered']:
                                sdel[4]['username'] = username

                        for e in tdata.keys():
                            for sdel in sdiff[k][e]:
                                tdata[e].append(sdel)
            out_data[client_name] = client_el
        return out_data

    def get_diff_total(self):
        total = {'Wait':None, 'Idle':None, 'Running':None, 'Held':None, 'Completed':None, 'Removed':None}
        for k in total.keys():
            total[k] = {'Entered':[], 'Exited':[]}
            tdata = total[k]
            for client_name in self.stats_diff.keys():
                for username in self.stats_diff[client_name].keys():
                    sdiff = self.stats_diff[client_name][username]
                    if ((sdiff is not None) and (k in sdiff.keys())):
                        for e in tdata.keys():
                            tdata[e] = tdata[e] + sdiff[k][e]
        return total

    def get_total_summary(self):
        stats_total = self.get_stats_total()
        diff_total = self.get_diff_total()
        out_total = {'Current':{}, 'Entered':{}, 'Exited':{}}
        for k in diff_total.keys():
            out_total['Entered'][k] = len(diff_total[k]['Entered'])
            if stats_total.has_key(k):
                out_total['Current'][k] = len(stats_total[k])
                # if no current, also exited does not have sense (terminal state)
                out_total['Exited'][k] = len(diff_total[k]['Exited'])
            elif k == 'Completed':
                completed_stats = self.get_completed_stats(diff_total[k]['Entered'])
                completed_counts = self.summarize_completed_stats(completed_stats)
                out_total['CompletedCounts'] = completed_counts

        return out_total

    def get_xml_total(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        total = self.get_total_summary()
        return xmlFormat.class2string(total,
                                      inst_name="total",
                                      subclass_params={'CompletedCounts':get_completed_stats_xml_desc()},
                                      indent_tab=indent_tab, leading_tab=leading_tab)

    def get_xml_updated(self, indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=""):
        return xmlFormat.time2xml(self.updated, "updated", indent_tab, leading_tab)

    def write_file(self, monitoringConfig=None):

        if monitoringConfig is None:
            monitoringConfig = globals()['monitoringConfig']

        if ( (self.files_updated is not None) and 
             ((self.updated - self.files_updated) < 5) ):
            # files updated recently, no need to redo it
            return

        # write snaphot file
        xml_str = ('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n' +
                 '<glideFactoryEntryLogSummary>\n' +
                 self.get_xml_updated(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                 self.get_xml_data(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                 self.get_xml_total(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                 "</glideFactoryEntryLogSummary>\n")
        monitoringConfig.write_file("log_summary.xml", xml_str)

        # update rrds
        stats_data_summary = self.get_stats_data_summary()
        diff_summary = self.get_diff_summary()
        stats_total_summary = self.get_stats_total_summary()
        for client_name in [None] + diff_summary.keys():
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
                if not (s in ('Completed', 'Removed')): # I don't have their numbers from inactive logs
                    count = sdata[s]
                    val_dict_counts["Status%s" % s] = count
                    val_dict_counts_desc["Status%s" % s] = {'ds_type':'GAUGE'}

                if ((sdiff is not None) and (s in sdiff.keys())):
                    entered_list = sdiff[s]['Entered']
                    entered = len(entered_list)
                    exited = -len(sdiff[s]['Exited'])
                else:
                    entered_list = []
                    entered = 0
                    exited = 0

                val_dict_counts["Entered%s" % s] = entered
                val_dict_counts_desc["Entered%s" % s] = {'ds_type':'ABSOLUTE'}
                if not (s in ('Completed', 'Removed')): # Always 0 for them
                    val_dict_counts["Exited%s" % s] = exited
                    val_dict_counts_desc["Exited%s" % s] = {'ds_type':'ABSOLUTE'}
                elif s == 'Completed':
                    completed_stats = self.get_completed_stats(entered_list)
                    if client_name is not None: # do not repeat for total
                        monitoringConfig.logCompleted(client_name, completed_stats)
                    completed_counts = self.summarize_completed_stats(completed_stats)

                    # save simple vals
                    for tkey in completed_counts['Sum'].keys():
                        val_dict_completed[tkey] = completed_counts['Sum'][tkey]

                    count_entered_times = completed_counts['Lasted']
                    count_jobnrs = completed_counts['JobsNr']
                    count_jobs_duration = completed_counts['JobsDuration']
                    count_waste_mill = completed_counts['Waste']
                    time_waste_mill = completed_counts['WasteTime']
                    # save run times
                    for timerange in count_entered_times.keys():
                        val_dict_stats['Lasted_%s' % timerange] = count_entered_times[timerange]
                        # they all use the same indexes
                        val_dict_stats['JobsLasted_%s' % timerange] = count_jobs_duration[timerange]

                    # save jobsnr
                    for jobrange in count_jobnrs.keys():
                        val_dict_stats['JobsNr_%s' % jobrange] = count_jobnrs[jobrange]

                    # save waste_mill
                    for w in count_waste_mill.keys():
                        count_waste_mill_w = count_waste_mill[w]
                        for p in count_waste_mill_w.keys():
                            val_dict_waste['%s_%s' % (w, p)] = count_waste_mill_w[p]

                    for w in time_waste_mill.keys():
                        time_waste_mill_w = time_waste_mill[w]
                        for p in time_waste_mill_w.keys():
                            val_dict_wastetime['%s_%s' % (w, p)] = time_waste_mill_w[p]

            #end for s in self.job_statuses

            # write the data to disk
            monitoringConfig.write_rrd_multi_hetero("%s/Log_Counts" % fe_dir,
                                                    val_dict_counts_desc, self.updated, val_dict_counts)
            monitoringConfig.write_rrd_multi("%s/Log_Completed" % fe_dir,
                                             "ABSOLUTE", self.updated, val_dict_completed)
            monitoringConfig.write_rrd_multi("%s/Log_Completed_Stats" % fe_dir,
                                             "ABSOLUTE", self.updated, val_dict_stats)
            # Disable Waste RRDs... WasteTime much more useful
            #monitoringConfig.write_rrd_multi("%s/Log_Completed_Waste"%fe_dir,
            #                                 "ABSOLUTE",self.updated,val_dict_waste)
            monitoringConfig.write_rrd_multi("%s/Log_Completed_WasteTime" % fe_dir,
                                             "ABSOLUTE", self.updated, val_dict_wastetime)


        self.files_updated = self.updated
        return


###############################################################################
#
# factoryStatusData
# added by C.W. Murphy starting on 08/09/10
# this class handles the data obtained from the rrd files
#
###############################################################################

class FactoryStatusData:
    """documentation"""
    def __init__(self, log=logSupport.log, base_dir=None):
        self.data = {}
        for rrd in rrd_list:
            self.data[rrd] = {}
        # KEL why are we setting time here and not just getting the current time (like in Descript2XML)
        self.updated = time.time()
        self.tab = xmlFormat.DEFAULT_TAB
        self.resolution = (7200, 86400, 604800) # 2hr, 1 day, 1 week
        self.total = "total/"
        self.frontends = []
        if base_dir is None:
            self.base_dir = monitoringConfig.monitor_dir
        self.log = log

    def getUpdated(self):
        """returns the time of last update"""
        return xmlFormat.time2xml(self.updated, "updated", indent_tab=self.tab, leading_tab=self.tab)

    def fetchData(self, rrd_file, pathway, res, start, end):
        """Uses rrdtool to fetch data from the clients.  Returns a dictionary of lists of data.  There is a list for each element.

        rrdtool fetch returns 3 tuples: a[0], a[1], & a[2].
        [0] lists the resolution, start and end time, which can be specified as arugments of fetchData.
        [1] returns the names of the datasets.  These names are listed in the key.
        [2] is a list of tuples. each tuple contains data from every dataset.  There is a tuple for each time data was collected."""

        #use rrdtool to fetch data
        baseRRDSupport = rrdSupport.rrdSupport()
        try:
            fetched = baseRRDSupport.fetch_rrd(pathway + rrd_file, 'AVERAGE', resolution=res, start=start, end=end)
        except:
            # probably not created yet
            self.log.debug("Failed to load %s" % (pathway + rrd_file))
            return {}

        #converts fetched from tuples to lists
        fetched_names = list(fetched[1])

        fetched_data_raw = fetched[2][:-1] # drop the last entry... rrdtool will return one more than needed, and often that one is unreliable (in the python version)
        fetched_data = []
        for data in fetched_data_raw:
            fetched_data.append(list(data))

        #creates a dictionary to be filled with lists of data
        data_sets = {}
        for name in fetched_names:
            data_sets[name] = []

        #check to make sure the data exists
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
        """returns the data fetched by rrdtool in a xml readable format"""

        if monitoringConfig is None:
            monitoringConfig = globals()['monitoringConfig']

        folder = str(input_val)
        if folder == self.total:
            client = folder
        else:
            folder_name = folder.split('@')[-1]
            client = folder_name.join(["frontend_", "/"])
            if client not in self.frontends:
                self.frontends.append(client)

        for rrd in rrd_list:
            self.data[rrd][client] = {}
            for res_raw in self.resolution:
                # calculate the best resolution
                res_idx = 0
                rrd_res = monitoringConfig.rrd_archives[res_idx][2] * monitoringConfig.rrd_step
                period_mul = int(res_raw / rrd_res)
                while (period_mul >= monitoringConfig.rrd_archives[res_idx][3]):
                    # not all elements in the higher bucket, get next lower resolution
                    res_idx += 1
                    rrd_res = monitoringConfig.rrd_archives[res_idx][2] * monitoringConfig.rrd_step
                    period_mul = int(res_raw / rrd_res)

                period = period_mul * rrd_res

                self.data[rrd][client][period] = {}
                end = (int(time.time() / rrd_res) - 1) * rrd_res # round due to RRDTool requirements, -1 to avoid the last (partial) one
                start = end - period
                try:
                    fetched_data = self.fetchData(
                                       rrd_file=rrd,
                                       pathway=self.base_dir + "/" + client,
                                       start=start, end=end, res=rrd_res)
                    for data_set in fetched_data:
                        self.data[rrd][client][period][data_set] = self.average(fetched_data[data_set])
                except TypeError:
                    self.log.exception("FactoryStatusData:fetchData: ")

        return self.data

    def getXMLData(self, rrd):
        "writes an xml file for the data fetched from a given site."

        # create a string containing the total data
        total_xml_str = self.tab + '<total>\n'
        get_data_total = self.getData(self.total) 
        try:
            total_data = self.data[rrd][self.total]
            total_xml_str += (xmlFormat.dict2string(total_data, dict_name='periods', el_name='period', subtypes_params={"class":{}}, indent_tab=self.tab, leading_tab=2 * self.tab) + "\n")
        except (NameError, UnboundLocalError):
            self.log.exception("FactoryStatusData:total_data: ")
        total_xml_str += self.tab + '</total>\n'

        # create a string containing the frontend data
        frontend_xml_str = (self.tab + '<frontends>\n')
        for frontend in self.frontends:
            fe_name = frontend.split("/")[0]
            frontend_xml_str += (2 * self.tab +
                                 '<frontend name=\"' + fe_name + '\">\n')
            try:
                frontend_data = self.data[rrd][frontend]
                frontend_xml_str += (xmlFormat.dict2string(frontend_data, dict_name='periods', el_name='period', subtypes_params={"class":{}}, indent_tab=self.tab, leading_tab=3 * self.tab) + "\n")
            except (NameError, UnboundLocalError):
                self.log.exception("FactoryStatusData:frontend_data: ")
            frontend_xml_str += 2 * self.tab + '</frontend>'
        frontend_xml_str += self.tab + '</frontends>\n'

        data_str = total_xml_str + frontend_xml_str
        return data_str

    def writeFiles(self,  monitoringConfig=None):

        if monitoringConfig is None:
            monitoringConfig = globals()['monitoringConfig']

        for rrd in rrd_list:
            file_name = 'rrd_' + rrd.split(".")[0] + '.xml'
            xml_str = ('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n' +
                       '<glideFactoryEntryRRDStats>\n' +
                       self.getUpdated() + "\n" +
                       self.getXMLData(rrd) +
                       '</glideFactoryEntryRRDStats>')
            try:
                monitoringConfig.write_file(file_name, xml_str)
            except IOError:
                self.log.exception("FactoryStatusData:write_file: ")
        return

##############################################################################
#
#  create an XML file out of glidein.descript, frontend.descript,
#    entry.descript, attributes.cfg, and params.cfg
#
#############################################################################

class Descript2XML:
    def __init__(self, log=logSupport.log):
        self.tab = xmlFormat.DEFAULT_TAB
        self.entry_descript_blacklist = ('DowntimesFile', 'EntryName',
                                         'Schedd')
        self.frontend_blacklist = ('usermap',)
        self.glidein_whitelist = ('AdvertiseDelay',
                                  'FactoryName', 'GlideinName', 'LoopDelay',
                                  'PubKeyType', 'WebURL', 'MonitorDisplayText',
                                  'MonitorLink')
        self.log = log

    def frontendDescript(self, fe_dict):
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
            xml_str = xmlFormat.dict2string(fe_dict, dict_name="frontends", el_name="frontend", subtypes_params={"class":{}}, leading_tab=self.tab)
            return xml_str + "\n"
        except RuntimeError:
            self.log.exception("xmlFormat error in frontendDescript: ")
            return

    def entryDescript(self, e_dict):
        for key in self.entry_descript_blacklist:
            try:
                for entry in e_dict:
                    try:
                        del e_dict[entry]['descript'][key]
                    except KeyError:
                        continue
            except RuntimeError:
                self.log.exception("blacklist error in entryDescript: ")
        try:
            xml_str = xmlFormat.dict2string(e_dict, dict_name="entries", el_name="entry", subtypes_params={"class":{'subclass_params':{}}}, leading_tab=self.tab)
            return xml_str + "\n"
        except RuntimeError:
            self.log.exception("xmlFormat Error in entryDescript: ")
            return

    def glideinDescript(self, g_dict):
        w_dict = {}
        for key in self.glidein_whitelist:
            try:
                w_dict[key] = g_dict[key]
            except KeyError:
                continue
        try:
            a = xmlFormat.dict2string({'':w_dict}, dict_name="glideins", el_name="factory", subtypes_params={"class":{}})
            b = a.split("\n")[1]
            c = b.split('name="" ')
            xml_str = "".join(c)
            return xml_str + "\n"
        except (SyntaxError, RuntimeError):
            logSupport.log.exception("xmlFormat error in glideinDescript: ")
            return

    def getUpdated(self):
        """returns the time of last update"""
        return xmlFormat.time2xml(time.time(), "updated", indent_tab=self.tab, leading_tab=self.tab)

    def writeFile(self, path, xml_str, singleEntry=False):
        if singleEntry:
            root_el = 'glideFactoryEntryDescript'
        else:
            root_el = 'glideFactoryDescript'
        output = ('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n' +
                   '<' + root_el + '>\n' + self.getUpdated() + "\n" + xml_str +
                   '</' + root_el + '>')
        fname = path + 'descript.xml'
        f = open(fname + '.tmp', 'wb')
        try:
            f.write(output)
        finally:
            f.close()

        util.file_tmp2final(fname)
        return


############### P R I V A T E ################

##################################################
def getAllJobTypes():
        return ('validation','idle', 'badput', 'nosuccess')

def getLogCompletedDefaults():
        return {'Glideins':0, 'Lasted':0, 'FailedNr':0, 
            'JobsNr':0, 'JobsLasted':0, 'JobsTerminated':0, 
            'JobsGoodput':0, 'CondorLasted':0}

def getTimeRange(absval):
        if absval < 1:
            return 'Unknown'
        if absval < (25 * 60):
            return 'Minutes'
        if absval > (64 * 3600): # limit detail to 64 hours
            return 'Days'
        # start with 7.5 min, and than exp2
        logval = int(math.log(absval / 450.0, 4) + 0.49)
        level = math.pow(4, logval) * 450.0
        if level < 3600:
            return "%imins" % (int(level / 60 + 0.49))
        else:
            return "%ihours" % (int(level / 3600 + 0.49))

def getAllTimeRanges():
        return ('Unknown', 'Minutes', '30mins', '2hours', '8hours', '32hours', 'Days')

def getJobRange(absval):
        if absval < 1:
            return 'None'
        if absval == 1:
            return '1job'
        if absval == 2:
            return '2jobs'
        if absval < 9:
            return '4jobs'
        if absval < 30: # limit detail to 30 jobs
            return '16jobs'
        else:
            return 'Many'

def getAllJobRanges():
        return ('None', '1job', '2jobs', '4jobs', '16jobs', 'Many')

def getMillRange(absval):
        if absval < 2:
            return 'None'
        if absval < 15:
            return '5m'
        if absval < 60:
            return '25m'
        if absval < 180:
            return '100m'
        if absval < 400:
            return '250m'
        if absval < 700:
            return '500m'
        if absval > 998:
            return 'All'
        else:
            return 'Most'

def getAllMillRanges():
        return ('None', '5m', '25m', '100m', '250m', '500m', 'Most', 'All')

##################################################
def get_completed_stats_xml_desc():
    return {'dicts_params':{'Lasted':{'el_name':'TimeRange'},
                            'JobsDuration':{'el_name':'TimeRange'},
                            'JobsNr':{'el_name':'Range'}},
            'subclass_params':{'Waste':{'dicts_params':{'idle':{'el_name':'Fraction'},
                                                        'validation':{'el_name':'Fraction'},
                                                        'badput':{'el_name':'Fraction'},
                                                        'nosuccess':{'el_name':'Fraction'}}},
                               'WasteTime':{'dicts_params':{'idle':{'el_name':'Fraction'},
                                                            'validation':{'el_name':'Fraction'},
                                                            'badput':{'el_name':'Fraction'},
                                                            'nosuccess':{'el_name':'Fraction'}}}
                               }
            }



##################################################
# def tmp2final(fname):
#     """
#     KEL this exact method is also in glideinFrontendMonitoring.py
#     """
#     try:
#         os.remove(fname + "~")
#     except:
#         pass
#
#     try:
#         os.rename(fname, fname + "~")
#     except:
#         pass
#
#     try:
#         os.rename(fname + ".tmp", fname)
#     except:
#         print "Failed renaming %s.tmp into %s" % (fname, fname)
#     return


##################################################

# global configuration of the module
monitoringConfig = MonitoringConfig()

