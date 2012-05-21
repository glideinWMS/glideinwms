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

import time,string,os.path,copy
import timeConversion
import xmlParse,xmlFormat
import glideinFrontendMonitoring

############################################################
#
# Configuration
#
############################################################

class MonitorAggregatorConfig:
    def __init__(self):
        # The name of the attribute that identifies the glidein
        self.monitor_dir="monitor/"

        # list of entries
        self.entries=[]

        # name of the status files
        self.status_relname="frontend_status.xml"

    def config_frontend(self,monitor_dir,groups):
        self.monitor_dir=monitor_dir
        self.groups=groups
        glideinFrontendMonitoring.monitoringConfig.monitor_dir=monitor_dir
    

# global configuration of the module
monitorAggregatorConfig=MonitorAggregatorConfig()

###########################################################
#
# Functions
#
###########################################################

frontend_status_attributes={'Jobs':("Idle","OldIdle","Running","Total"),
                   'Glideins':("Idle","Running","Total"),
                   'MatchedJobs':("Idle","EffIdle","OldIdle","Running","RunningHere"),
                   'MatchedGlideins':("Total","Idle","Running"),
                   'Requested':("Idle","MaxRun")}

frontend_total_type_strings={'Jobs':'Jobs','Glideins':'Glidein','MatchedJobs':'MatchJob',
                      'MatchedGlideins':'MatchGlidein','Requested':'Req'}
frontend_job_type_strings={'MatchedJobs':'MatchJob',
                      'MatchedGlideins':'MatchGlidein','Requested':'Req'}

####################################
# PRIVATE - Used by aggregateStatus
# Write one RRD
def write_one_rrd(name,updated,data,fact=0):
    if fact==0:
        type_strings=frontend_total_type_strings
    else:
        type_strings=frontend_job_type_strings
        
    # initialize the RRD dictionary, so it gets created properly
    val_dict={}
    for tp in frontend_status_attributes.keys():
        if tp in type_strings.keys():
            tp_str=type_strings[tp]
            attributes_tp=frontend_status_attributes[tp]
            for a in attributes_tp:
                val_dict["%s%s"%(tp_str,a)]=None

    for tp in data.keys():
        # type - status or requested
        if not (tp in frontend_status_attributes.keys()):
            continue
        if not (tp in type_strings.keys()):
            continue

        tp_str=type_strings[tp]
        attributes_tp=frontend_status_attributes[tp]
                
        tp_el=data[tp]

        for a in tp_el.keys():
            if a in attributes_tp:
                a_el=int(tp_el[a])
                if type(a_el)!=type({}): # ignore subdictionaries
                    val_dict["%s%s"%(tp_str,a)]=a_el
                
    glideinFrontendMonitoring.monitoringConfig.establish_dir("%s"%name)
    glideinFrontendMonitoring.monitoringConfig.write_rrd_multi("%s"%name,
                                                               "GAUGE",updated,val_dict)

##############################################################################
# create an aggregate of status files, write it in an aggregate status file
# end return the values
def aggregateStatus():
    global monitorAggregatorConfig

    type_strings={'Jobs':'Jobs','Glideins':'Glidein','MatchedJobs':'MatchJob',
                  'MatchedGlideins':'MatchGlidein','Requested':'Req'}
    global_total={'Jobs':None,'Glideins':None,'MatchedJobs':None,'Requested':None,'MatchedGlideins':None}
    status={'groups':{},'total':global_total}
    global_fact_totals={}
    for fos in ('factories','states'):
        global_fact_totals[fos]={}
    
    nr_groups=0
    for group in monitorAggregatorConfig.groups:
        # load group status file
        status_fname=os.path.join(os.path.join(monitorAggregatorConfig.monitor_dir,'group_'+group),
                                  monitorAggregatorConfig.status_relname)
        try:
            group_data=xmlParse.xmlfile2dict(status_fname)
        except IOError:
            continue # file not found, ignore

        # update group
        status['groups'][group]={}
        for fos in ('factories','states'):
            try:
                status['groups'][group][fos]=group_data[fos]
            except KeyError, e:
                # first time after upgrade factories may not be defined
                status['groups'][group][fos]={}

        this_group=status['groups'][group]
        for fos in ('factories','states'):
          for fact in this_group[fos].keys():
            this_fact=this_group[fos][fact]
            if not fact in global_fact_totals[fos].keys():
                # first iteration through, set fact totals equal to the first group's fact totals
                global_fact_totals[fos][fact]={}
                for attribute in type_strings.keys():
                    if attribute in this_fact.keys():
                        global_fact_totals[fos][fact][attribute]={}
                        for type_attribute in this_fact[attribute].keys():
                            this_type_attribute=this_fact[attribute][type_attribute]
                            try:
                                global_fact_totals[fos][fact][attribute][type_attribute]=int(this_type_attribute)
                            except:
                                pass
            else:
                # next iterations, factory already present in global fact totals, add the new factory values to the previous ones
                for attribute in type_strings.keys():
                    if attribute in this_fact.keys():
                        for type_attribute in this_fact[attribute].keys():
                            this_type_attribute=this_fact[attribute][type_attribute]
                            if type(this_type_attribute)==type(global_fact_totals[fos]):
                                # dict, do nothing
                                pass
                            else:
                                if type_attribute in global_fact_totals[fos][fact][attribute].keys(): 
                                   global_fact_totals[fos][fact][attribute][type_attribute]+=int(this_type_attribute)
                                else:
                                   global_fact_totals[fos][fact][attribute][type_attribute]=int(this_type_attribute)
        #nr_groups+=1
        #status['groups'][group]={}

        if group_data.has_key('total'):
          nr_groups+=1
          status['groups'][group]['total']=group_data['total']

          for w in global_total.keys():
              tel=global_total[w]
              if not group_data['total'].has_key(w):
                  continue
              #status['groups'][group][w]=group_data[w]
              el=group_data['total'][w]
              if tel==None:
                  # new one, just copy over
                  global_total[w]={}
                  tel=global_total[w]
                  for a in el.keys():
                      tel[a]=int(el[a]) #coming from XML, everything is a string
              else:                
                  # successive, sum 
                  for a in el.keys():
                      if tel.has_key(a):
                          tel[a]+=int(el[a])
                              
                  # if any attribute from prev. factories are not in the current one, remove from total
                  for a in tel.keys():
                      if not el.has_key(a):
                          del tel[a]

    for w in global_total.keys():
        if global_total[w]==None:
            del global_total[w] # remove group if not defined

    # Write xml files


    updated=time.time()
    xml_str=('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'+
             '<VOFrontendStats>\n'+
             get_xml_updated(updated,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.dict2string(status["groups"],dict_name="groups",el_name="group",
                                   subtypes_params={"class":{"dicts_params":{"factories":{"el_name":"factory",
                                                                                          "subtypes_params":{"class":{"subclass_params":{"Requested":{"dicts_params":{"Parameters":{"el_name":"Parameter",
                                                                                                                                                                                    "subtypes_params":{"class":{}}}}}}}}},
                                                                             "states":{"el_name":"state",
                                                                                          "subtypes_params":{"class":{"subclass_params":{"Requested":{"dicts_params":{"Parameters":{"el_name":"Parameter",
                                                                                                                                                                                    "subtypes_params":{"class":{}}}}}}}}}
                                                                             }}},
                                   leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.class2string(status["total"],inst_name="total",leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+

             xmlFormat.dict2string(global_fact_totals['factories'],dict_name="factories",el_name="factory",
                                   subtypes_params={"class":{"subclass_params":{"Requested":{"dicts_params":{"Parameters":{"el_name":"Parameter",

       "subtypes_params":{"class":{}}}}}}}},
                                   leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.dict2string(global_fact_totals['states'],dict_name="states",el_name="state",
                                   subtypes_params={"class":{"subclass_params":{"Requested":{"dicts_params":{"Parameters":{"el_name":"Parameter",

       "subtypes_params":{"class":{}}}}}}}},
                                   leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             "</VOFrontendStats>\n")

    glideinFrontendMonitoring.monitoringConfig.write_file(monitorAggregatorConfig.status_relname,xml_str)

    # Write rrds

    glideinFrontendMonitoring.monitoringConfig.establish_dir("total")
    write_one_rrd("total/Status_Attributes",updated,global_total,0)

    for fact in global_fact_totals['factories'].keys():
        fe_dir="total/factory_%s"%glideinFrontendMonitoring.sanitize(fact)
        glideinFrontendMonitoring.monitoringConfig.establish_dir(fe_dir)
        write_one_rrd("%s/Status_Attributes"%fe_dir,updated,global_fact_totals['factories'][fact],1)
    for fact in global_fact_totals['states'].keys():
        fe_dir="total/state_%s"%glideinFrontendMonitoring.sanitize(fact)
        glideinFrontendMonitoring.monitoringConfig.establish_dir(fe_dir)
        write_one_rrd("%s/Status_Attributes"%fe_dir,updated,global_fact_totals['states'][fact],1)

    return status

#################        PRIVATE      #####################

def get_xml_updated(when,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
    xml_updated={"UTC":{"unixtime":timeConversion.getSeconds(when),
                        "ISO8601":timeConversion.getISO8601_UTC(when),
                        "RFC2822":timeConversion.getRFC2822_UTC(when)},
                 "Local":{"ISO8601":timeConversion.getISO8601_Local(when),
                          "RFC2822":timeConversion.getRFC2822_Local(when),
                          "human":timeConversion.getHuman(when)}}
    return xmlFormat.dict2string(xml_updated,
                                 dict_name="updated",el_name="timezone",
                                 subtypes_params={"class":{}},
                                 indent_tab=indent_tab,leading_tab=leading_tab)


