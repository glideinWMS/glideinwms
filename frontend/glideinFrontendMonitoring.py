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


from __future__ import print_function

import copy
import os
import os.path
import string
import time

from glideinwms.lib import logSupport
from glideinwms.lib import xmlFormat


class Monitoring_Output(object):
    out_list = []

    DEFAULT_CONFIG = {"monitor_dir": "monitor/",
                      "name": "Monitor_Name"}

    DEFAULT_CONFIG_AGGR = {"monitor_dir": "monitor/",
                           "groups": [],
                           "entries": [],
                           "status_relname": "frontend_status.xml"}

    global_config = copy.deepcopy(DEFAULT_CONFIG)
    global_config_aggr = copy.deepcopy(DEFAULT_CONFIG_AGGR)

    def __init__(self):
        self.config = copy.deepcopy(Monitoring_Output.DEFAULT_CONFIG)
        self.configAggr = copy.deepcopy(Monitoring_Output.DEFAULT_CONFIG_AGGR)

    # Override methods

    def write_groupStats(self, total, factories_data, states_data, updated):
        pass

    def write_factoryStats(self, data, total_el, updated):
        pass

    def write_aggregation(self, global_fact_totals, updated, global_total, status):
        pass

    def verify(self, fix):
        # fix is a dictionary that may contain parameters passed from reconfig
        # (ie. fix["fix_rrd"] = True # Then fix the RRD Files)
        return False

    # Common Methods
    def _updateConfig(self, key, value):
        if key in self.config:
            self.config[key] = value
        else:
            raise ValueError("Attempted to Update a Key that did not exsist")

    def _updateConfigAggr(self, key, value):
        if key in self.configAggr:
            self.configAggr[key] = value
        else:
            raise ValueError("Attempted to Update a Key that did not exsist")

    # Static Functions
    @staticmethod
    def createOutList():
        if not (Monitoring_Output.out_list):
            from glideinwms.frontend import monitorXML
            from glideinwms.frontend import monitorRRD
            monitorRRD_config = {}
            out = monitorRRD.Monitoring_Output({}, {})
            Monitoring_Output.out_list.append(out)
            out = monitorXML.Monitoring_Output({}, {})
            Monitoring_Output.out_list.append(out)

    @staticmethod
    def updateConfig(key, val, element=None):
        if element:
            element._updateConfig(key, val)
        else:
            if key in Monitoring_Output.global_config:
                Monitoring_Output.global_config[key] = val
            for out in Monitoring_Output.out_list:
                out._updateConfig(key, val)

    @staticmethod
    def updateConfigAggr(key, val, element=None):
        if element:
            element._updateConfigAggr(key, val)
        else:
            if key in Monitoring_Output.global_config_aggr:
                Monitoring_Output.global_config_aggr[key] = val
            for out in Monitoring_Output.out_list:
                out._updateConfigAggr(key, val)

    @staticmethod
    def write_file(relative_fname, output_str):
        fname = os.path.join(Monitoring_Output.global_config["monitor_dir"], relative_fname)
        if not os.path.isdir(os.path.dirname(fname)):
            os.makedirs(os.path.dirname(fname))
        # print "Writing "+fname
        fd = open(fname + ".tmp", "w")
        try:
            fd.write(output_str + "\n")
        finally:
            fd.close()

        tmp2final(fname)
        return

    @staticmethod
    def establish_dir(relative_dname):
        dname = os.path.join(Monitoring_Output.global_config["monitor_dir"], relative_dname)
        if not os.path.isdir(dname):
            os.mkdir(dname)
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
        self.data={'factories':{},'states':{},'totals':{}}
        self.updated=time.time()

        self.files_updated=None

        self.attributes = {
            'Jobs':("Idle", "OldIdle", "Running", "Total", "Idle_3600"),
            'Glideins':("Idle", "Running", "Total"),
            'MatchedJobs':("Idle", "EffIdle", "OldIdle", "Running", "RunningHere"),
            #'MatchedGlideins':("Total","Idle","Running","Failed","TotalCores","IdleCores","RunningCores"),
            'MatchedGlideins':("Total", "Idle", "Running", "Failed"),
            'MatchedCores':("Total", "Idle", "Running"),
            'Requested':("Idle", "MaxRun")
        }

        self.states_names=('Unmatched', 'MatchedUp', 'MatchedDown')


    def logJobs(self, jobs_data):
        el={}
        self.data['totals']['Jobs']=el

        for k in self.attributes['Jobs']:
            if k in jobs_data:
                el[k]=int(jobs_data[k])
        self.updated=time.time()

    def logGlideins(self, slots_data):
        el={}
        self.data['totals']['Glideins']=el

        for k in self.attributes['Glideins']:
            if k in slots_data:
                el[k]=int(slots_data[k])
        self.updated=time.time()


    def logMatchedJobs(self, factory, idle, effIdle, oldIdle, running, realRunning):
        factory_or_state_d = self.get_factory_dict(factory)

        factory_or_state_d['MatchedJobs'] = {self.attributes['MatchedJobs'][0]: int(idle),
                                             self.attributes['MatchedJobs'][1]: int(effIdle),
                                             self.attributes['MatchedJobs'][2]: int(oldIdle),
                                             self.attributes['MatchedJobs'][3]: int(running),
                                             self.attributes['MatchedJobs'][4]: int(realRunning)
                                            }

        self.update=time.time()

    def logFactDown(self, factory, isDown):
        factory_or_state_d = self.get_factory_dict(factory)

        if isDown:
            factory_or_state_d['Down'] = 'Down'
        else:
            factory_or_state_d['Down'] = 'Up'

        self.updated = time.time()

    def logMatchedGlideins(self, factory, total, idle, running, failed, totalcores, idlecores, runningcores):
        factory_or_state_d = self.get_factory_dict(factory)

        factory_or_state_d['MatchedGlideins'] = {
            self.attributes['MatchedGlideins'][0]: int(total),
            self.attributes['MatchedGlideins'][1]: int(idle),
            self.attributes['MatchedGlideins'][2]: int(running),
            self.attributes['MatchedGlideins'][3]: int(failed),
        }
        factory_or_state_d['MatchedCores'] = {
            self.attributes['MatchedCores'][0]: int(totalcores),
            self.attributes['MatchedCores'][1]: int(idlecores),
            self.attributes['MatchedCores'][2]: int(runningcores),
        }

        self.update=time.time()
            
    def logFactAttrs(self, factory, attrs, blacklist):
        factory_or_state_d = self.get_factory_dict(factory)

        factory_or_state_d['Attributes'] = {}
        for attr in attrs:
            if not attr in blacklist:
                factory_or_state_d['Attributes'][attr] = attrs[attr]

        self.update=time.time()
        
    def logFactReq(self, factory, reqIdle, reqMaxRun, params):
        factory_or_state_d = self.get_factory_dict(factory)

        factory_or_state_d['Requested'] = {self.attributes['Requested'][0]: int(reqIdle),
                                           self.attributes['Requested'][1]: int(reqMaxRun),
                                           'Parameters': copy.deepcopy(params)
                                           }

        self.updated = time.time()

    def get_factories_data(self):
        return copy.deepcopy(self.data['factories'])

    def get_states_data(self):
        return copy.deepcopy(self.data['states'])

    def get_total(self):
        total = {
            'MatchedJobs': None,
            'Requested': None,
            'MatchedGlideins': None,
            'MatchedCores': None,
        }
        numtypes=(type(1), type(1), type(1.0))

        for f in self.data['factories'].keys():
            fa=self.data['factories'][f]
            for w in fa.keys():
                if w in total: # ignore eventual not supported classes
                    el=fa[w]
                    tel=total[w]

                    if tel is None:
                        # first one, just copy over
                        total[w]={}
                        tel=total[w]
                        for a in el.keys():
                            if type(el[a]) in numtypes: # copy only numbers
                                tel[a]=el[a]
                    else:
                        # successive, sum 
                        for a in el.keys():
                            if type(el[a]) in numtypes: # consider only numbers
                                if a in tel:
                                    tel[a]+=el[a]
                            # if other frontends did't have this attribute, ignore
                        # if any attribute from prev. frontends are not in the current one, remove from total
                        for a in tel.keys():
                            if a not in el:
                                del tel[a]
                            elif not (type(el[a]) in numtypes):
                                del tel[a]
        
        for w in total.keys():
            if total[w] is None:
                del total[w] # remove entry if not defined

        total.update(copy.deepcopy(self.data['totals']))
        return total

    def write_data(self):
        if (self.files_updated is not None) and ((self.updated-self.files_updated)<5):
            # files updated recently, no need to redo it
            return

        # Prepare Data
        total = self.get_total()
        factories_data = self.get_factories_data()
        states_data = self.get_states_data()

        # Send Data
        for out in Monitoring_Output.out_list:
            out.write_groupStats(total, factories_data, states_data, self.updated)

        self.files_updated=self.updated        
        return

    ################################################
    # PRIVATE - Used to select the right disctionary
    def get_factory_dict(self, factory):
        if factory in self.states_names:
            factories = self.data['states']
        else:
            factories = self.data['factories']
        if not factory in factories:
            factories[factory] = {}
        return factories[factory]

########################################################################
    
class factoryStats:
    def __init__(self):
        self.data={}
        self.updated=time.time()

        self.files_updated=None

    def logJobs(self, client_name, qc_status):
        if client_name in self.data:
            t_el=self.data[client_name]
        else:
            t_el={}
            self.data[client_name]=t_el

        el={}
        t_el['Status']=el

        status_pairs=((1, "Idle"), (2, "Running"), (5, "Held"), (1001, "Wait"), (1002, "Pending"), (1010, "StageIn"), (1100, "IdleOther"), (4010, "StageOut"))
        for p in status_pairs:
            nr, status=p
            if nr in qc_status:
                el[status]=int(qc_status[nr])
            else:
                el[status]=0
        self.updated=time.time()

    def logRequest(self, client_name, requests, params):
        """
        requests is a dictinary of requests
        params is a dictinary of parameters

        At the moment, it looks only for
          'IdleGlideins'
          'MaxRunningGlideins'
        """
        if client_name in self.data:
            t_el=self.data[client_name]
        else:
            t_el={}
            self.data[client_name]=t_el

        el={}
        t_el['Requested']=el

        if 'IdleGlideins' in requests:
            el['Idle']=int(requests['IdleGlideins'])
        if 'MaxRunningGlideins' in requests:
            el['MaxRun']=int(requests['MaxRunningGlideins'])

        el['Parameters']=copy.deepcopy(params)

        self.updated=time.time()

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
            t_el=self.data[client_name]
        else:
            t_el={}
            self.data[client_name]=t_el

        el={}
        t_el['ClientMonitor']=el

        for karr in (('Idle', 'JobsIdle'), ('Running', 'JobsRunning'), ('GlideinsIdle', 'GlideIdle'), ('GlideinsRunning', 'GlideRunning'), ('GlideinsTotal', 'GlideTotal')):
            ck, ek=karr
            if ck in client_monitor:
                el[ek]=int(client_monitor[ck])

        if 'LastHeardFrom' in client_internals:
            el['InfoAge']=int(time.time()-long(client_internals['LastHeardFrom']))
            el['InfoAgeAvgCounter']=1 # used for totals since we need an avg in totals, not absnum

        self.updated=time.time()

    def get_data(self):
        data1=copy.deepcopy(self.data)
        for f in data1.keys():
            fe=data1[f]
            for w in fe.keys():
                el=fe[w]
                for a in el.keys():
                    if a[-10:]=='AvgCounter': # do not publish avgcounter fields... they are internals
                        del el[a]

        return data1

    def get_total(self):
        total={'Status':None,'Requested':None,'ClientMonitor':None}
        numtypes=(type(1), type(1), type(1.0))

        for f in self.data.keys():
            fe=self.data[f]
            for w in fe.keys():
                if w in total: # ignore eventual not supported classes
                    el=fe[w]
                    tel=total[w]

                    if tel is None:
                        # first one, just copy over
                        total[w]={}
                        tel=total[w]
                        for a in el.keys():
                            if type(el[a]) in numtypes: # copy only numbers
                                tel[a]=el[a]
                    else:
                        # successive, sum
                        for a in el.keys():
                            if type(el[a]) in numtypes: # consider only numbers
                                if a in tel:
                                    tel[a]+=el[a]
                            # if other frontends did't have this attribute, ignore
                        # if any attribute from prev. frontends are not in the current one, remove from total
                        for a in tel.keys():
                            if a not in el:
                                del tel[a]
                            elif not (type(el[a]) in numtypes):
                                del tel[a]

        for w in total.keys():
            if total[w] is None:
                del total[w] # remove entry if not defined
            else:
                tel=total[w]
                for a in tel.keys():
                    if a[-10:]=='AvgCounter':
                        # this is an average counter, calc the average of the referred element
                        # like InfoAge=InfoAge/InfoAgeAvgCounter
                        aorg=a[:-10]
                        tel[aorg]=tel[aorg]/tel[a]
                        # the avgcount totals are just for internal purposes
                        del tel[a]

        return total

    def write_file(self):

        if (self.files_updated is not None) and ((self.updated-self.files_updated)<5):
            # files updated recently, no need to redo it
            return

        # Prepare Data
        data=self.get_data()
        total_el=self.get_total()

        # Send Data
        for out in Monitoring_Output.out_list:
            out.write_factoryStats(data, total_el, self.updated)

        self.files_updated=self.updated
        return
    
############### P R I V A T E ################

##################################################
def tmp2final(fname):
    """
    This exact method is also in glideFactoryMonitoring.py
    """
    try:
        os.remove(fname+"~")
    except:
        pass

    try:
        os.rename(fname, fname+"~")
    except:
        pass

    try:
        os.rename(fname+".tmp", fname)
    except:
        print("Failed renaming %s.tmp into %s"%(fname, fname))
        logSupport.log.error("Failed renaming %s.tmp into %s" % (fname, fname))
    return


##################################################
def sanitize(name):
    good_chars=string.ascii_letters+string.digits+".-"
    outarr=[]
    for i in range(len(name)):
        if name[i] in good_chars:
            outarr.append(name[i])
        else:
            outarr.append("_")
    return string.join(outarr, "")

##################################################


def write_frontend_descript_xml(frontendDescript, monitor_dir):
    """
    Writes out the frontend descript.xml file in the monitor web area.
    
    @type frontendDescript: FrontendDescript
    @param frontendDescript: contains the data in the frontend.descript file in the frontend instance dir
    @type monitor_dir: string
    @param monitor_dir: filepath the the monitor dir in the frontend instance dir
    """
    
    frontend_data = copy.deepcopy(frontendDescript.data)
    
    frontend_str = '<frontend FrontendName="%s"' % frontend_data['FrontendName'] + '/>'

    dis_link_txt = 'display_txt="%s"  href_link="%s"' % (frontend_data['MonitorDisplayText'], frontend_data['MonitorLink'])
    footer_str = '<monitor_footer ' + dis_link_txt + '/>'
    
    output = '<?xml version="1.0" encoding="ISO-8859-1"?>\n\n' + \
                   '<glideinFrontendDescript>\n' \
                   + xmlFormat.time2xml(time.time(), "updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB) + "\n" \
                   + xmlFormat.DEFAULT_TAB + frontend_str + "\n" \
                   + xmlFormat.DEFAULT_TAB + footer_str + "\n" \
                   + '</glideinFrontendDescript>'

    fname = os.path.join(monitor_dir, 'descript.xml')
    
    try:
        f = open(fname + '.tmp', 'wb')
        try:
            f.write(output)
        finally:
            f.close()

        tmp2final(fname)
    
    except IOError:
        logSupport.log.exception("Error writing out the frontend descript.xml: ")


##################################################

Monitoring_Output.createOutList()
