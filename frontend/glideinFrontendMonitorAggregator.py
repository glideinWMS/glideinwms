from __future__ import print_function
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements the functions needed
#   to aggregate the monitoring fo the frontend
#
# Author:
#   Igor Sfiligoi (Mar 19th 2009)
#

import time
import os.path
import os
import tempfile
import shutil

from glideinwms.lib import logSupport
from glideinwms.lib import xmlParse, xmlFormat
from glideinwms.frontend import glideinFrontendMonitoring

def config_frontend(monitor_dir, groups):
    glideinFrontendMonitoring.Monitoring_Output.updateConfigAggr("monitor_dir", monitor_dir)
    glideinFrontendMonitoring.Monitoring_Output.updateConfigAggr("groups", groups)
    glideinFrontendMonitoring.Monitoring_Output.updateConfig("monitor_dir", monitor_dir)


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


##############################################################################
# create an aggregate of status files, write it in an aggregate status file
# end return the values
def aggregateStatus():

    type_strings = {
        'Jobs': 'Jobs',
        'Glideins': 'Glidein',
        'MatchedJobs': 'MatchJob',
        'MatchedGlideins': 'MatchGlidein',
        'MatchedCores': 'MatchCore',
        'Requested': 'Req'
    }
    global_total = {
        'Jobs': None,
        'Glideins': None,
        'MatchedJobs': None,
        'Requested': None,
        'MatchedGlideins': None,
        'MatchedCores': None,
    }
    status={'groups': {}, 'total': global_total}
    global_fact_totals = {}

    for fos in ('factories', 'states'):
        global_fact_totals[fos] = {}
    
    nr_groups = 0
    for group in glideinFrontendMonitoring.Monitoring_Output.global_config_aggr["groups"]:
        # load group status file
        status_fname = os.path.join(os.path.join(glideinFrontendMonitoring.Monitoring_Output.global_config_aggr["monitor_dir"], 'group_'+group),
                                    glideinFrontendMonitoring.Monitoring_Output.global_config_aggr["status_relname"])
        try:
            group_data=xmlParse.xmlfile2dict(status_fname)
        except xmlParse.CorruptXML as e:
            logSupport.log.error("Corrupt XML in %s; deleting (it will be recreated)." % (status_fname))
            os.unlink(status_fname)
            continue
        except IOError:
            continue  # file not found, ignore

        # update group
        status['groups'][group] = {}
        for fos in ('factories', 'states'):
            try:
                status['groups'][group][fos] = group_data[fos]
            except KeyError as e:
                # first time after upgrade factories may not be defined
                status['groups'][group][fos] = {}

        this_group=status['groups'][group]
        for fos in ('factories', 'states'):
          for fact in this_group[fos].keys():
            this_fact = this_group[fos][fact]
            if not fact in global_fact_totals[fos].keys():
                # first iteration through, set fact totals equal to the first group's fact totals
                global_fact_totals[fos][fact]={}
                for attribute in type_strings.keys():
                    global_fact_totals[fos][fact][attribute] = {}
                    if attribute in this_fact.keys():
                        for type_attribute in this_fact[attribute].keys():
                            this_type_attribute=this_fact[attribute][type_attribute]
                            try:
                                global_fact_totals[fos][fact][attribute][type_attribute] = int(this_type_attribute)
                            except:
                                pass
            else:
                # next iterations, factory already present in global fact totals, add the new factory values to the previous ones
                for attribute in type_strings.keys():
                    if attribute in this_fact.keys():
                        for type_attribute in this_fact[attribute].keys():
                            this_type_attribute = this_fact[attribute][type_attribute]
                            if isinstance(this_type_attribute, type(global_fact_totals[fos])):
                                # dict, do nothing
                                pass
                            else:
                                if attribute in global_fact_totals[fos][fact].keys() and type_attribute in global_fact_totals[fos][fact][attribute].keys():
                                   global_fact_totals[fos][fact][attribute][type_attribute] += int(this_type_attribute)
                                else:
                                   global_fact_totals[fos][fact][attribute][type_attribute] = int(this_type_attribute)
        #nr_groups+=1
        #status['groups'][group]={}

        if 'total' in group_data:
            nr_groups += 1
            status['groups'][group]['total'] = group_data['total']

            for w in global_total.keys():
                tel = global_total[w]
                if w not in group_data['total']:
                    continue
                #status['groups'][group][w]=group_data[w]
                el = group_data['total'][w]
                if tel is None:
                    # new one, just copy over
                    global_total[w] = {}
                    tel = global_total[w]
                    for a in el.keys():
                        tel[a] = int(el[a]) #coming from XML, everything is a string
                else:                
                    # successive, sum 
                    for a in el.keys():
                        if a in tel:
                            tel[a] += int(el[a])
                              
                    # if any attribute from prev. factories are not in the current one, remove from total
                    for a in tel.keys():
                        if a not in el:
                            del tel[a]


        
    for w in global_total.keys():
        if global_total[w] is None:
            del global_total[w] # remove group if not defined

    updated=time.time()

    # Write Data
    for out in glideinFrontendMonitoring.Monitoring_Output.out_list:
        out.write_aggregation(global_fact_totals, updated, global_total, status)

    return status
