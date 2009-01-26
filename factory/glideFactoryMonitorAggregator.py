#
# Description:
#   This module implements the functions needed
#   to aggregate the monitoring fo the glidein factory
#
# Author:
#   Igor Sfiligoi (May 23rd 2007)
#

import time,string,os.path
import timeConversion
import xmlParse,xmlFormat
import glideFactoryMonitoring


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
        self.status_relname="schedd_status.xml"
        self.logsummary_relname="log_summary.xml"

    def config_factory(self,monitor_dir,entries):
        self.monitor_dir=monitor_dir
        self.entries=entries
        glideFactoryMonitoring.monitoringConfig.monitor_dir=monitor_dir
    

# global configuration of the module
monitorAggregatorConfig=MonitorAggregatorConfig()

###########################################################
#
# Functions
#
###########################################################

status_attributes={'Status':("Idle","Running","Held","Wait","Pending","IdleOther"),
                   'Requested':("Idle","MaxRun"),
                   'ClientMonitor':("InfoAge","Idle","Running","GlideinsIdle","GlideinsRunning","GlideinsTotal")}

##############################################################################
# create an aggregate of status files, write it in an aggregate status file
# end return the values
def aggregateStatus():
    global monitorAggregatorConfig

    avgEntries=('InfoAge',)

    global_total={'Status':None,'Requested':None,'ClientMonitor':None}
    status={'entries':{},'total':global_total}
    nr_entries=0
    for entry in monitorAggregatorConfig.entries:
        # load entry status file
        status_fname=os.path.join(os.path.join(monitorAggregatorConfig.monitor_dir,'entry_'+entry),
                                  monitorAggregatorConfig.status_relname)
        try:
            entry_data=xmlParse.xmlfile2dict(status_fname)
        except IOError:
            continue # file not found, ignore

        # update entry 
        status['entries'][entry]={'frontends':entry_data['frontends']}

        # update total
        if entry_data.has_key('total'):
            nr_entries+=1
            status['entries'][entry]['total']=entry_data['total']

            for w in global_total.keys():
                tel=global_total[w]
                if not entry_data['total'].has_key(w):
                    continue 
                el=entry_data['total'][w]
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
                            
                        # if any attribute from prev. frontends are not in the current one, remove from total
                        for a in tel.keys():
                            if not el.has_key(a):
                                del tel[a]
        
    for w in global_total.keys():
        if global_total[w]==None:
            del global_total[w] # remove entry if not defined
        else:
            tel=global_total[w]
            for a in tel.keys():
                if a in avgEntries:
                    tel[a]=tel[a]/nr_entries # since all entries must have this attr to be here, just divide by nr of entries

    # Write xml files
    updated=time.time()
    xml_str=('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'+
             '<glideFactoryQStats>\n'+
             get_xml_updated(updated,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.dict2string(status["entries"],dict_name="entries",el_name="entry",
                                   subtypes_params={"class":{"dicts_params":{"frontends":{"el_name":"frontend",
                                                                                          "subtypes_params":{"class":{"subclass_params":{"Requested":{"dicts_params":{"Parameters":{"el_name":"Parameter",
                                                                                                                                                                                    "subtypes_params":{"class":{}}}}}}}}}}}},
                                   leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.class2string(status["total"],inst_name="total",leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             "</glideFactoryQStats>\n")
    glideFactoryMonitoring.monitoringConfig.write_file(monitorAggregatorConfig.status_relname,xml_str)

    # Write rrds
    glideFactoryMonitoring.monitoringConfig.establish_dir("total")
    for tp in global_total.keys():
        # type - status or requested
        if not (tp in status_attributes.keys()):
            continue

        attributes_tp=status_attributes[tp]
        val_dict_tp={}
        for a in attributes_tp:
            val_dict_tp[a]=None #init, so that gets created properly
                
        tp_el=global_total[tp]

        for a in tp_el.keys():
            if a in attributes_tp:
                a_el=int(tp_el[a])
                val_dict_tp[a]=a_el
        glideFactoryMonitoring.monitoringConfig.write_rrd_multi("total/%s_Attributes"%tp,
                                                                "GAUGE",updated,val_dict_tp)

    return status

##############################################################################
# create the history graphs and related index html file
def create_status_history():
    # use the same reference time for all the graphs
    graph_ref_time=time.time()
    # remember to call update_locks before exiting this function

    # create graphs for RRDs
    glideFactoryMonitoring.create_status_graphs(graph_ref_time,'total')

    # create split graphs
    if 'Split' in glideFactoryMonitoring.monitoringConfig.wanted_graphs:
        glideFactoryMonitoring.create_split_graphs(status_attributes,graph_ref_time,monitorAggregatorConfig.entries,"entry_%s/total")
        
    # create support index files
    glideFactoryMonitoring.create_group_status_indexes("Factory %s"%glideFactoryMonitoring.monitoringConfig.my_name,
                                                       monitorAggregatorConfig.monitor_dir,"total",
                                                       None,None, # no parent
                                                       monitorAggregatorConfig.entries,"../entry_%s/total")

    glideFactoryMonitoring.monitoringConfig.update_locks(graph_ref_time,"status")
    return

######################################################################################
# create an aggregate of log summary files, write it in an aggregate log summary file
# end return the values
def aggregateLogSummary():
    global monitorAggregatorConfig

    # initialize global counters
    global_total={'Current':{},'Entered':{},'Exited':{},'CompletedCounts':{'Failed':0,'Waste':{},'WasteTime':{},'Lasted':{},'JobsNr':{},'JobsDuration':{}}}

    for s in ('Wait','Idle','Running','Held'):
        for k in ['Current','Entered','Exited']:
            global_total[k][s]=0

    for s in ('Completed','Removed'):
        for k in ['Entered']:
            global_total[k][s]=0

    for k in ['idle', 'validation', 'badput', 'nosuccess']:
        for w in ("Waste","WasteTime"):
            el={}
            for t in glideFactoryMonitoring.getAllMillRanges():
                el[t]=0
            global_total['CompletedCounts'][w][k]=el

    el={}
    for t in glideFactoryMonitoring.getAllTimeRanges():
        el[t]=0
    global_total['CompletedCounts']['Lasted']=el

    el={}
    for t in glideFactoryMonitoring.getAllJobRanges():
        el[t]=0
    global_total['CompletedCounts']['JobsNr']=el

    for k in ['total', 'goodput', 'terminated']:
        el={}
        for t in glideFactoryMonitoring.getAllTimeRanges():
            el[t]=0
        global_total['CompletedCounts']['JobsDuration'][k]=el

    #
    status={'entries':{},'total':global_total}
    nr_entries=0
    for entry in monitorAggregatorConfig.entries:
        # load entry log summary file
        status_fname=os.path.join(os.path.join(monitorAggregatorConfig.monitor_dir,'entry_'+entry),
                                  monitorAggregatorConfig.logsummary_relname)
        try:
            entry_data=xmlParse.xmlfile2dict(status_fname,always_singular_list=['Fraction','TimeRange','Range'])
        except IOError:
            continue # file not found, ignore

        # update entry
        out_data={}
        for frontend in entry_data['frontends'].keys():
            fe_el=entry_data['frontends'][frontend]
            out_fe_el={}
            for k in ['Current','Entered','Exited']:
                out_fe_el[k]={}
                for s in fe_el[k].keys():
                    out_fe_el[k][s]=int(fe_el[k][s])
            out_fe_el['CompletedCounts']={'Waste':{},'WasteTime':{},'Lasted':{},'JobsNr':{},'JobsDuration':{}}
            out_fe_el['CompletedCounts']['Failed']=int(fe_el['CompletedCounts']['Failed'])
            for k in ['idle', 'validation', 'badput', 'nosuccess']:
                for w in ("Waste","WasteTime"):
                    out_fe_el['CompletedCounts'][w][k]={}
                    for t in glideFactoryMonitoring.getAllMillRanges():
                        out_fe_el['CompletedCounts'][w][k][t]=int(fe_el['CompletedCounts'][w][k][t]['val'])
            for t in glideFactoryMonitoring.getAllTimeRanges():
                out_fe_el['CompletedCounts']['Lasted'][t]=int(fe_el['CompletedCounts']['Lasted'][t]['val'])
            for k in ['total', 'goodput', 'terminated']:
                out_fe_el['CompletedCounts']['JobsDuration'][k]={}
                for t in glideFactoryMonitoring.getAllTimeRanges():
                    out_fe_el['CompletedCounts']['JobsDuration'][k][t]=int(fe_el['CompletedCounts']['JobsDuration'][k][t]['val'])
            for t in glideFactoryMonitoring.getAllJobRanges():
                out_fe_el['CompletedCounts']['JobsNr'][t]=int(fe_el['CompletedCounts']['JobsNr'][t]['val'])
            out_data[frontend]=out_fe_el
            
        status['entries'][entry]={'frontends':out_data}

        # update total
        if entry_data.has_key('total'):
            nr_entries+=1
            local_total={}

            for k in ['Current','Entered','Exited']:
                local_total[k]={}
                for s in global_total[k].keys():
                    local_total[k][s]=int(entry_data['total'][k][s])
                    global_total[k][s]+=int(entry_data['total'][k][s])
            local_total['CompletedCounts']={'Waste':{},'WasteTime':{},'Lasted':{},'JobsNr':{},'JobsDuration':{}}
            local_total['CompletedCounts']['Failed']=int(entry_data['total']['CompletedCounts']['Failed'])
            global_total['CompletedCounts']['Failed']+=int(entry_data['total']['CompletedCounts']['Failed'])
            for k in ['idle', 'validation', 'badput', 'nosuccess']:
                for w in ("Waste","WasteTime"):
                    local_total['CompletedCounts'][w][k]={}
                    for t in glideFactoryMonitoring.getAllMillRanges():
                        local_total['CompletedCounts'][w][k][t]=int(entry_data['total']['CompletedCounts'][w][k][t]['val'])
                        global_total['CompletedCounts'][w][k][t]+=int(entry_data['total']['CompletedCounts'][w][k][t]['val'])

            for t in glideFactoryMonitoring.getAllTimeRanges():
                local_total['CompletedCounts']['Lasted'][t]=int(entry_data['total']['CompletedCounts']['Lasted'][t]['val'])
                global_total['CompletedCounts']['Lasted'][t]+=int(entry_data['total']['CompletedCounts']['Lasted'][t]['val'])
            for k in ['total', 'goodput', 'terminated']:
                local_total['CompletedCounts']['JobsDuration'][k]={}
                for t in glideFactoryMonitoring.getAllTimeRanges():
                    local_total['CompletedCounts']['JobsDuration'][k][t]=int(entry_data['total']['CompletedCounts']['JobsDuration'][k][t]['val'])
                    global_total['CompletedCounts']['JobsDuration'][k][t]+=int(entry_data['total']['CompletedCounts']['JobsDuration'][k][t]['val'])

            for t in glideFactoryMonitoring.getAllJobRanges():
                local_total['CompletedCounts']['JobsNr'][t]=int(entry_data['total']['CompletedCounts']['JobsNr'][t]['val'])
                global_total['CompletedCounts']['JobsNr'][t]+=int(entry_data['total']['CompletedCounts']['JobsNr'][t]['val'])

            status['entries'][entry]['total']=local_total
        
    # Write xml files
    updated=time.time()
    xml_str=('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'+
             '<glideFactoryLogSummary>\n'+
             get_xml_updated(updated,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.dict2string(status["entries"],dict_name="entries",el_name="entry",
                                   subtypes_params={"class":{"dicts_params":{"frontends":{"el_name":"frontend",
                                                                                          "subtypes_params":{"class":{'subclass_params':{'CompletedCounts':glideFactoryMonitoring.get_completed_stats_xml_desc()}}}}},
                                                             "subclass_params":{"total":{"subclass_params":{'CompletedCounts':glideFactoryMonitoring.get_completed_stats_xml_desc()}}}
                                                             }
                                                    },
                                   leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.class2string(status["total"],inst_name="total",subclass_params={'CompletedCounts':glideFactoryMonitoring.get_completed_stats_xml_desc()},leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             "</glideFactoryLogSummary>\n")
    glideFactoryMonitoring.monitoringConfig.write_file(monitorAggregatorConfig.logsummary_relname,xml_str)

    # Write rrds
    fe_dir="total"
    sdata=status["total"]['Current']
    sdiff=status["total"]

    glideFactoryMonitoring.monitoringConfig.establish_dir(fe_dir)
    val_dict_counts={}
    val_dict_entered={}
    val_dict_exited={}
    val_dict_completed={}
    val_dict_waste={}
    val_dict_wastetime={}
    for s in ('Wait','Idle','Running','Held','Completed','Removed'):
        if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
            count=sdata[s]
            val_dict_counts[s]=count

            exited=-status["total"]['Exited'][s]
            val_dict_exited[s]=exited
            
        entered=status["total"]['Entered'][s]
        val_dict_entered[s]=entered

        if s=='Completed':
            completed_counts=status["total"]['CompletedCounts']
            count_entered_times=completed_counts['Lasted']
            count_jobnrs=completed_counts['JobsNr']
            count_jobs_duration=completed_counts['JobsDuration']
            count_validation_failed=completed_counts['Failed']
            count_waste_mill=completed_counts['Waste']
            time_waste_mill=completed_counts['WasteTime']
            # save run times
            for timerange in count_entered_times.keys():
                val_dict_completed['Lasted_%s'%timerange]=count_entered_times[timerange]
                # they all use the same indexes
                val_dict_completed['JobsLasted_%s'%timerange]=count_jobs_duration['total'][timerange]
                val_dict_completed['Goodput_%s'%timerange]=count_jobs_duration['goodput'][timerange]
                val_dict_completed['Terminated_%s'%timerange]=count_jobs_duration['terminated'][timerange]

            # save jobsnr
            for jobrange in count_jobnrs.keys():
                val_dict_completed['JobsNr_%s'%jobrange]=count_jobnrs[jobrange]
            # save failures
            val_dict_completed['Failed']=count_validation_failed

            # save waste_mill
            for w in count_waste_mill.keys():
                count_waste_mill_w=count_waste_mill[w]
                for p in count_waste_mill_w.keys():
                    val_dict_waste['%s_%s'%(w,p)]=count_waste_mill_w[p]

            for w in time_waste_mill.keys():
                time_waste_mill_w=time_waste_mill[w]
                for p in time_waste_mill_w.keys():
                    val_dict_wastetime['%s_%s'%(w,p)]=time_waste_mill_w[p]

    # write the data to disk
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Counts"%fe_dir,
                                                            "GAUGE",updated,val_dict_counts)                            
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Entered"%fe_dir,
                                                            "ABSOLUTE",updated,val_dict_entered)
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Exited"%fe_dir,
                                                            "ABSOLUTE",updated,val_dict_exited)
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Completed_Stats"%fe_dir,
                                                            "ABSOLUTE",updated,val_dict_completed)
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Completed_Waste"%fe_dir,
                                                            "ABSOLUTE",updated,val_dict_waste)
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Completed_WasteTime"%fe_dir,
                                                            "ABSOLUTE",updated,val_dict_wastetime)
    
    return status

##############################################################################
# create the history graphs and related index html file
def create_log_history():
    # use the same reference time for all the graphs
    graph_ref_time=time.time()
    # remember to call update_locks before exiting this function
    
    glideFactoryMonitoring.create_log_graphs(graph_ref_time,"logsummary","total")
    glideFactoryMonitoring.create_log_split_graphs(graph_ref_time,"logsummary","entry_%s/total",monitorAggregatorConfig.entries)
    
    # create support index file
    glideFactoryMonitoring.create_log_total_index("Factory %s"%glideFactoryMonitoring.monitoringConfig.my_name,"entry","../entry_%s/total",monitorAggregatorConfig.entries,None)
    
    glideFactoryMonitoring.monitoringConfig.update_locks(graph_ref_time,"logsummary")
    return

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


# import in local namespace
img2html=glideFactoryMonitoring.img2html

