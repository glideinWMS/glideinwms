#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This module implements the functions needed
#   to aggregate the monitoring fo the glidein factory
#
# Author:
#   Igor Sfiligoi (May 23rd 2007)
#

import copy
import time
import string
import os.path
import tempfile
import shutil
import time

from glideinwms.lib import timeConversion
from glideinwms.lib import xmlParse,xmlFormat
from glideinwms.lib import logSupport
from glideinwms.lib import rrdSupport
from glideinwms.factory import glideFactoryMonitoring
from glideinwms.factory import glideFactoryLib

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

    def config_factory(self,monitor_dir,entries, log):
        self.monitor_dir=monitor_dir
        self.entries=entries
        glideFactoryMonitoring.monitoringConfig.monitor_dir=monitor_dir
        glideFactoryMonitoring.monitoringConfig.log = log
        self.log = log

# global configuration of the module
monitorAggregatorConfig=MonitorAggregatorConfig()

def rrd_site(name):
    sname = name.split(".")[0]
    return "rrd_%s.xml" %sname

###########################################################
#
# Functions
#
###########################################################

status_attributes={'Status':("Idle","Running","Held","Wait","Pending","StageIn","IdleOther","StageOut"),
                   'Requested':("Idle","MaxGlideins"),
                   'ClientMonitor':("InfoAge","JobsIdle","JobsRunning","JobsRunHere","GlideIdle","GlideRunning","GlideTotal")}
type_strings={'Status':'Status','Requested':'Req','ClientMonitor':'Client'}

##############################################################################
rrd_problems_found=False
def verifyHelper(filename,dict, fix_rrd=False):
    """
    Helper function for verifyRRD.  Checks one file,
    prints out errors.  if fix_rrd, will attempt to
    dump out rrd to xml, add the missing attributes,
    then restore.  Original file is obliterated.

    @param filename: filename of rrd to check
    @param dict: expected dictionary
    @param fix_rrd: if true, will attempt to add missing attrs
    """
    global rrd_problems_found
    if not os.path.exists(filename):
        print "WARNING: %s missing, will be created on restart" % (filename)
        return
    rrd_obj=rrdSupport.rrdSupport()
    (missing,extra)=rrd_obj.verify_rrd(filename,dict)
    for attr in extra:
        print "ERROR: %s has extra attribute %s" % (filename,attr)
        if fix_rrd:
            print "ERROR: fix_rrd cannot fix extra attributes"
    if not fix_rrd:
        for attr in missing:
            print "ERROR: %s missing attribute %s" % (filename,attr)
        if len(missing) > 0:
            rrd_problems_found=True
    if fix_rrd and (len(missing) > 0):
        (f,tempfilename)=tempfile.mkstemp()
        (out,tempfilename2)=tempfile.mkstemp()
        (restored,restoredfilename)=tempfile.mkstemp()
        backup_str=str(int(time.time()))+".backup"
        print "Fixing %s... (backed up to %s)" % (filename,filename+backup_str)
        os.close(out)
        os.close(restored)
        os.unlink(restoredfilename)
        #Use exe version since dump, restore not available in rrdtool
        dump_obj=rrdSupport.rrdtool_exe()
        outstr=dump_obj.dump(filename)
        for line in outstr:
            os.write(f,"%s\n"%line)
        os.close(f)
        #Move file to backup location 
        shutil.move(filename,filename+backup_str)
        rrdSupport.addDataStore(tempfilename,tempfilename2,missing)
        outstr=dump_obj.restore(tempfilename2,restoredfilename)
        os.unlink(tempfilename)
        os.unlink(tempfilename2)
        shutil.move(restoredfilename,filename)
    if len(extra) > 0:
        rrd_problems_found=True

def verifyRRD(fix_rrd=False):
    """
    Go through all known monitoring rrds and verify that they
    match existing schema (could be different if an upgrade happened)
    If fix_rrd is true, then also attempt to add any missing attributes.
    """
    global rrd_problems_found
    global monitorAggregatorConfig
    dir=monitorAggregatorConfig.monitor_dir
    total_dir=os.path.join(dir,"total")
   
    status_dict={}
    completed_stats_dict={}
    completed_waste_dict={}
    counts_dict={}
 
    # initialize the RRD dictionaries to match the current schema for verification
    for tp in status_attributes.keys():
        if tp in type_strings.keys():
            tp_str=type_strings[tp]
            attributes_tp=status_attributes[tp]
            for a in attributes_tp:
                status_dict["%s%s"%(tp_str,a)]=None

    for jobrange in glideFactoryMonitoring.getAllJobRanges():
        completed_stats_dict["JobsNr_%s"%(jobrange)]=None
    for timerange in glideFactoryMonitoring.getAllTimeRanges():
        completed_stats_dict["Lasted_%s"%(timerange)]=None
        completed_stats_dict["JobsLasted_%s"%(timerange)]=None

    for jobtype in glideFactoryMonitoring.getAllJobTypes():
        for timerange in glideFactoryMonitoring.getAllMillRanges():
            completed_waste_dict["%s_%s"%(jobtype,timerange)]=None

    for jobtype in ('Entered','Exited','Status'):
        for jobstatus in ('Wait','Idle','Running','Held'):
            counts_dict["%s%s"%(jobtype,jobstatus)]=None
    for jobstatus in ('Completed','Removed'):
            counts_dict["%s%s"%('Entered',jobstatus)]=None

    verifyHelper(os.path.join(total_dir,
        "Status_Attributes.rrd"),status_dict, fix_rrd)
    verifyHelper(os.path.join(total_dir,
        "Log_Completed.rrd"),
        glideFactoryMonitoring.getLogCompletedDefaults(), fix_rrd)
    verifyHelper(os.path.join(total_dir,
        "Log_Completed_Stats.rrd"),completed_stats_dict, fix_rrd)
    verifyHelper(os.path.join(total_dir,
        "Log_Completed_WasteTime.rrd"),completed_waste_dict, fix_rrd)
    verifyHelper(os.path.join(total_dir,
        "Log_Counts.rrd"),counts_dict, fix_rrd)
    for filename in os.listdir(dir):
        if filename[:6]=="entry_":
            entrydir=os.path.join(dir,filename)
            for subfilename in os.listdir(entrydir):
                if subfilename[:9]=="frontend_":
                    current_dir=os.path.join(entrydir,subfilename)
                    verifyHelper(os.path.join(current_dir,
                        "Status_Attributes.rrd"),status_dict, fix_rrd)
                    verifyHelper(os.path.join(current_dir,
                        "Log_Completed.rrd"),
                        glideFactoryMonitoring.getLogCompletedDefaults(),fix_rrd)
                    verifyHelper(os.path.join(current_dir,
                        "Log_Completed_Stats.rrd"),completed_stats_dict,fix_rrd)
                    verifyHelper(os.path.join(current_dir,
                        "Log_Completed_WasteTime.rrd"),
                        completed_waste_dict,fix_rrd)
                    verifyHelper(os.path.join(current_dir,
                        "Log_Counts.rrd"),counts_dict,fix_rrd)
    return not rrd_problems_found



##############################################################################
def aggregateStatus(in_downtime):
    """
    Create an aggregate of status files, write it in an aggregate status file
    and in the end return the values

    @type in_downtime: boolean
    @param in_downtime: Entry downtime information

    @rtype: dict
    @return: Dictionary of status information
    """

    global monitorAggregatorConfig

    avgEntries=('InfoAge',)

    global_total={'Status':None,'Requested':None,'ClientMonitor':None}
    status={'entries':{},'total':global_total}
    status_fe={'frontends':{}} #analogous to above but for frontend totals

    # initialize the RRD dictionary, so it gets created properly
    val_dict={}
    for tp in global_total.keys():
        # type - status or requested
        if not (tp in status_attributes.keys()):
            continue

        tp_str=type_strings[tp]

        attributes_tp=status_attributes[tp]
        for a in attributes_tp:
            val_dict["%s%s"%(tp_str,a)]=None

    nr_entries=0
    nr_feentries={} #dictionary for nr entries per fe
    for entry in monitorAggregatorConfig.entries:
        # load entry status file
        status_fname=os.path.join(os.path.join(monitorAggregatorConfig.monitor_dir,'entry_'+entry),
                                  monitorAggregatorConfig.status_relname)
        try:
            entry_data=xmlParse.xmlfile2dict(status_fname)
        except IOError:
            continue # file not found, ignore

        # update entry
        status['entries'][entry]={'downtime':entry_data['downtime'], 'frontends':entry_data['frontends']}

        # update total
        if entry_data.has_key('total'):
            nr_entries+=1
            status['entries'][entry]['total']=entry_data['total']

            for w in global_total.keys():
                tel=global_total[w]
                if not entry_data['total'].has_key(w):
                    continue
                el=entry_data['total'][w]
                if tel is None:
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

        # update frontends
        if entry_data.has_key('frontends'):
            #loop on fe's in this entry
            for fe in entry_data['frontends'].keys():
                #compare each to the list of fe's accumulated so far
                if not status_fe['frontends'].has_key(fe):
                    status_fe['frontends'][fe]={}
                if not nr_feentries.has_key(fe):
                    nr_feentries[fe]=1 #already found one
                else:
                    nr_feentries[fe]+=1
                for w in entry_data['frontends'][fe].keys():
                    if not status_fe['frontends'][fe].has_key(w):                    
                        status_fe['frontends'][fe][w]={}
                    tela=status_fe['frontends'][fe][w]
                    ela=entry_data['frontends'][fe][w]
                    for a in ela.keys():
                        #for the 'Downtime' field (only bool), do logical AND of all site downtimes
                        # 'w' is frontend attribute name, ie 'ClientMonitor' or 'Downtime'
                        # 'a' is sub-field, such as 'GlideIdle' or 'status'
                        if w=='Downtime' and a=='status':
                            ela_val=(ela[a]!='False') # Check if 'True' or 'False' but default to True if neither
                            if tela.has_key(a):
                                try:
                                    tela[a]=tela[a] and ela_val
                                except:
                                    pass # just protect
                            else:
                                tela[a]=ela_val
                        else:
                            try:
                                #if there already, sum
                                if tela.has_key(a):
                                    tela[a]+=int(ela[a])
                                else:
                                    tela[a]=int(ela[a])
                            except:
                                pass #not an int, not Downtime, so do nothing
                                        
                        # if any attribute from prev. frontends are not in the current one, remove from total
                        for a in tela.keys():
                            if not ela.has_key(a):
                                del tela[a]        


    for w in global_total.keys():
        if global_total[w] is None:
            del global_total[w] # remove entry if not defined
        else:
            tel=global_total[w]
            for a in tel.keys():
                if a in avgEntries:
                    tel[a]=tel[a]/nr_entries # since all entries must have this attr to be here, just divide by nr of entries

    #do average for per-fe stat--'InfoAge' only
    for fe in status_fe['frontends'].keys():
        for w in status_fe['frontends'][fe].keys():
            tel=status_fe['frontends'][fe][w]
            for a in tel.keys():
                if a in avgEntries and nr_feentries.has_key(fe):
                    tel[a]=tel[a]/nr_feentries[fe] # divide per fe
            

    xml_downtime = xmlFormat.dict2string({}, dict_name = 'downtime', el_name = '', params = {'status':str(in_downtime)}, leading_tab = xmlFormat.DEFAULT_TAB)

    # Write xml files
    updated=time.time()
    xml_str=('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'+
             '<glideFactoryQStats>\n'+
             xmlFormat.time2xml(updated,"updated", indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xml_downtime + "\n" +
             xmlFormat.dict2string(status["entries"],dict_name="entries",el_name="entry",
                                   subtypes_params={"class":{"dicts_params":{"frontends":{"el_name":"frontend",
                                                                                          "subtypes_params":{"class":{"subclass_params":{"Requested":{"dicts_params":{"Parameters":{"el_name":"Parameter",
                                                                                                                                                                                    "subtypes_params":{"class":{}}}}}}}}}}}},
                                   leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.class2string(status["total"],inst_name="total",leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.dict2string(status_fe["frontends"],dict_name="frontends",el_name="frontend",
                                   subtypes_params={"class":{"subclass_params":{"Requested":{"dicts_params":{"Parameters":{"el_name":"Parameter",
                                                                                                                           "subtypes_params":{"class":{}}}}}}}},
                                   leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             "</glideFactoryQStats>\n")
    glideFactoryMonitoring.monitoringConfig.write_file(monitorAggregatorConfig.status_relname,xml_str)

    # Write rrds
    glideFactoryMonitoring.monitoringConfig.establish_dir("total")
    # Total rrd across all frontends and factories
    for tp in global_total.keys():
        # type - status or requested
        if not (tp in status_attributes.keys()):
            continue

        tp_str=type_strings[tp]
        attributes_tp=status_attributes[tp]

        tp_el=global_total[tp]

        for a in tp_el.keys():
            if a in attributes_tp:
                a_el=int(tp_el[a])
                val_dict["%s%s"%(tp_str,a)]=a_el

    glideFactoryMonitoring.monitoringConfig.write_rrd_multi("total/Status_Attributes",
                                                            "GAUGE",updated,val_dict)

    # Frontend total rrds across all factories
    for fe in status_fe['frontends'].keys():
        glideFactoryMonitoring.monitoringConfig.establish_dir("total/%s"%("frontend_"+fe))
        for tp in status_fe['frontends'][fe].keys():
            # type - status or requested
            if not (tp in type_strings.keys()):
                continue
            tp_str=type_strings[tp]
            attributes_tp=status_attributes[tp]

            tp_el=status_fe['frontends'][fe][tp]

            for a in tp_el.keys():
                if a in attributes_tp:
                    a_el=int(tp_el[a])
                    val_dict["%s%s"%(tp_str,a)]=a_el
        glideFactoryMonitoring.monitoringConfig.write_rrd_multi("total/%s/Status_Attributes"%("frontend_"+fe),
                                                            "GAUGE",updated,val_dict)



    return status

######################################################################################
def aggregateLogSummary():
    """
    Create an aggregate of log summary files, write it in an aggregate log 
    summary file and in the end return the values
    """

    global monitorAggregatorConfig

    # initialize global counters
    global_total={'Current':{},'Entered':{},'Exited':{},'CompletedCounts':{'Sum':{},'Waste':{},'WasteTime':{},'Lasted':{},'JobsNr':{},'JobsDuration':{}}}

    for s in ('Wait','Idle','Running','Held'):
        for k in ['Current','Entered','Exited']:
            global_total[k][s]=0

    for s in ('Completed','Removed'):
        for k in ['Entered']:
            global_total[k][s]=0

    for k in glideFactoryMonitoring.getAllJobTypes():
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

    el={}
    # KEL - why is the same el used twice (see above)
    for t in glideFactoryMonitoring.getAllTimeRanges():
        el[t]=0
    global_total['CompletedCounts']['JobsDuration']=el

    global_total['CompletedCounts']['Sum']={'Glideins':0,
                                            'Lasted':0,
                                            'FailedNr':0,
                                            'JobsNr':0,
                                            'JobsLasted':0,
                                            'JobsGoodput':0,
                                            'JobsTerminated':0,
                                            'CondorLasted':0}

    fe_total=copy.deepcopy(global_total) # same as above but for frontend totals
    
    #
    status={'entries':{},'total':global_total}
    status_fe={'frontends':{}} #analogous to above but for frontend totals

    nr_entries=0
    nr_feentries={} #dictionary for nr entries per fe
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
            out_fe_el['CompletedCounts']={'Waste':{},'WasteTime':{},'Lasted':{},'JobsNr':{},'JobsDuration':{},'Sum':{}}
            for tkey in fe_el['CompletedCounts']['Sum'].keys():
                out_fe_el['CompletedCounts']['Sum'][tkey]=int(fe_el['CompletedCounts']['Sum'][tkey])
            for k in glideFactoryMonitoring.getAllJobTypes():
                for w in ("Waste","WasteTime"):
                    out_fe_el['CompletedCounts'][w][k]={}
                    for t in glideFactoryMonitoring.getAllMillRanges():
                        out_fe_el['CompletedCounts'][w][k][t]=int(fe_el['CompletedCounts'][w][k][t]['val'])
            for t in glideFactoryMonitoring.getAllTimeRanges():
                out_fe_el['CompletedCounts']['Lasted'][t]=int(fe_el['CompletedCounts']['Lasted'][t]['val'])
            out_fe_el['CompletedCounts']['JobsDuration']={}
            for t in glideFactoryMonitoring.getAllTimeRanges():
                out_fe_el['CompletedCounts']['JobsDuration'][t]=int(fe_el['CompletedCounts']['JobsDuration'][t]['val'])
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
            local_total['CompletedCounts']={'Sum':{},'Waste':{},'WasteTime':{},'Lasted':{},'JobsNr':{},'JobsDuration':{}}
            for tkey in entry_data['total']['CompletedCounts']['Sum'].keys():
                local_total['CompletedCounts']['Sum'][tkey]=int(entry_data['total']['CompletedCounts']['Sum'][tkey])
                global_total['CompletedCounts']['Sum'][tkey]+=int(entry_data['total']['CompletedCounts']['Sum'][tkey])
            for k in glideFactoryMonitoring.getAllJobTypes():
                for w in ("Waste","WasteTime"):
                    local_total['CompletedCounts'][w][k]={}
                    for t in glideFactoryMonitoring.getAllMillRanges():
                        local_total['CompletedCounts'][w][k][t]=int(entry_data['total']['CompletedCounts'][w][k][t]['val'])
                        global_total['CompletedCounts'][w][k][t]+=int(entry_data['total']['CompletedCounts'][w][k][t]['val'])

            for t in glideFactoryMonitoring.getAllTimeRanges():
                local_total['CompletedCounts']['Lasted'][t]=int(entry_data['total']['CompletedCounts']['Lasted'][t]['val'])
                global_total['CompletedCounts']['Lasted'][t]+=int(entry_data['total']['CompletedCounts']['Lasted'][t]['val'])
            local_total['CompletedCounts']['JobsDuration']={}
            for t in glideFactoryMonitoring.getAllTimeRanges():
                local_total['CompletedCounts']['JobsDuration'][t]=int(entry_data['total']['CompletedCounts']['JobsDuration'][t]['val'])
                global_total['CompletedCounts']['JobsDuration'][t]+=int(entry_data['total']['CompletedCounts']['JobsDuration'][t]['val'])

            for t in glideFactoryMonitoring.getAllJobRanges():
                local_total['CompletedCounts']['JobsNr'][t]=int(entry_data['total']['CompletedCounts']['JobsNr'][t]['val'])
                global_total['CompletedCounts']['JobsNr'][t]+=int(entry_data['total']['CompletedCounts']['JobsNr'][t]['val'])

            status['entries'][entry]['total']=local_total
        
        # update frontends
        for fe in out_data:
            #compare each to the list of fe's accumulated so far
            if not (fe in status_fe['frontends']):
                status_fe['frontends'][fe]={}
            if not (fe in nr_feentries):
                nr_feentries[fe]=1 #already found one
            else:
                nr_feentries[fe]+=1

            # sum them up
            sumDictInt(out_data[fe],status_fe['frontends'][fe])

    # Write xml files
    # To do - Igor: Consider adding status_fe to the XML file
    updated=time.time()
    xml_str=('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'+
             '<glideFactoryLogSummary>\n'+
             xmlFormat.time2xml(updated,"updated", indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
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
    writeLogSummaryRRDs("total",status["total"])
    
    # Frontend total rrds across all factories
    for fe in status_fe['frontends']:
        writeLogSummaryRRDs("total/%s"%("frontend_"+fe),status_fe['frontends'][fe])

    return status

def sumDictInt(indict,outdict):
    for orgi in indict:
        i=str(orgi) # RRDs don't like unicode, so make sure we use strings
        if type(indict[i])==type(1):
            if not (i in outdict):
                outdict[i]=0
            outdict[i]+=indict[i]
        else:
            # assume it is a dictionary
            if not (i in outdict):
                outdict[i]={}

            sumDictInt(indict[i],outdict[i])

def writeLogSummaryRRDs(fe_dir,status_el):
    updated=time.time()

    sdata=status_el['Current']

    glideFactoryMonitoring.monitoringConfig.establish_dir(fe_dir)
    val_dict_counts={}
    val_dict_counts_desc={}
    val_dict_completed={}
    val_dict_stats={}
    val_dict_waste={}
    val_dict_wastetime={}
    for s in ('Wait','Idle','Running','Held','Completed','Removed'):
        if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
            count=sdata[s]
            val_dict_counts["Status%s"%s]=count
            val_dict_counts_desc["Status%s"%s]={'ds_type':'GAUGE'}

            exited=-status_el['Exited'][s]
            val_dict_counts["Exited%s"%s]=exited
            val_dict_counts_desc["Exited%s"%s]={'ds_type':'ABSOLUTE'}
            
        entered=status_el['Entered'][s]
        val_dict_counts["Entered%s"%s]=entered
        val_dict_counts_desc["Entered%s"%s]={'ds_type':'ABSOLUTE'}

        if s=='Completed':
            completed_counts=status_el['CompletedCounts']
            count_entered_times=completed_counts['Lasted']
            count_jobnrs=completed_counts['JobsNr']
            count_jobs_duration=completed_counts['JobsDuration']
            count_waste_mill=completed_counts['Waste']
            time_waste_mill=completed_counts['WasteTime']
            # save run times
            for timerange in count_entered_times.keys():
                val_dict_stats['Lasted_%s'%timerange]=count_entered_times[timerange]
                # they all use the same indexes
                val_dict_stats['JobsLasted_%s'%timerange]=count_jobs_duration[timerange]

            # save jobsnr
            for jobrange in count_jobnrs.keys():
                val_dict_stats['JobsNr_%s'%jobrange]=count_jobnrs[jobrange]

            # save simple vals
            for tkey in completed_counts['Sum'].keys():
                val_dict_completed[tkey]=completed_counts['Sum'][tkey]

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
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi_hetero("%s/Log_Counts"%fe_dir,
                                                            val_dict_counts_desc,updated,val_dict_counts)
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Completed"%fe_dir,
                                                            "ABSOLUTE",updated,val_dict_completed)
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Completed_Stats"%fe_dir,
                                                            "ABSOLUTE",updated,val_dict_stats)
    # Disable Waste RRDs... WasteTime much more useful
    #glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Completed_Waste"%fe_dir,
    #                                                        "ABSOLUTE",updated,val_dict_waste)
    glideFactoryMonitoring.monitoringConfig.write_rrd_multi("%s/Log_Completed_WasteTime"%fe_dir,
                                                            "ABSOLUTE",updated,val_dict_wastetime)

def aggregateRRDStats(log=logSupport.log):
    """
    Create an aggregate of RRD stats, write it files
    """

    global monitorAggregatorConfig
    factoryStatusData = glideFactoryMonitoring.FactoryStatusData()
    rrdstats_relname = glideFactoryMonitoring.rrd_list
    tab = xmlFormat.DEFAULT_TAB

    for rrd in rrdstats_relname:

        # assigns the data from every site to 'stats'
        stats = {}
        for entry in monitorAggregatorConfig.entries:
            rrd_fname = os.path.join(os.path.join(monitorAggregatorConfig.monitor_dir, 'entry_' + entry), rrd_site(rrd))
            try:
                stats[entry] = xmlParse.xmlfile2dict(rrd_fname, always_singular_list = {'timezone':{}})
            except IOError:
                log.debug("aggregateRRDStats %s exception: parse_xml, IOError"%rrd_fname)

        stats_entries=stats.keys()
        if len(stats_entries)==0:
            continue # skip this RRD... nothing to aggregate
        stats_entries.sort()

        # Get all the resolutions, data_sets and frontends... for totals
        resolution = set([])
        frontends = set([])
        data_sets = set([])
        for entry in stats_entries:
            entry_resolution = stats[entry]['total']['periods'].keys()
            if len(entry_resolution)==0:
                continue # not an interesting entry
            resolution=resolution.union(entry_resolution)
            entry_data_sets = stats[entry]['total']['periods'][entry_resolution[0]]
            data_sets=data_sets.union(entry_data_sets)
            entry_frontends = stats[entry]['frontends'].keys()
            frontends=frontends.union(entry_frontends)
            entry_data_sets = stats[entry]['total']['periods'][entry_resolution[0]]

        resolution=list(resolution)
        frontends=list(frontends)
        data_sets=list(data_sets)

        # create a dictionary that will hold the aggregate data
        clients = frontends + ['total']
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
                        if client == 'total':
                            try:
                                aggregate_output[client][res][data_set] += float(stats[entry][client]['periods'][res][data_set])
                            except KeyError:
                                missing_total_data = True
                                # well, some may be just missing.. can happen
                                #log.debug("aggregate_data, KeyError stats[%s][%s][%s][%s][%s]"%(entry,client,'periods',res,data_set))

                        else:
                            if stats[entry]['frontends'].has_key(client):
                                # not all the entries have all the frontends
                                try:
                                    aggregate_output[client][res][data_set] += float(stats[entry]['frontends'][client]['periods'][res][data_set])
                                except KeyError:
                                    missing_client_data = True
                                    # well, some may be just missing.. can happen
                                    #log.debug("aggregate_data, KeyError stats[%s][%s][%s][%s][%s][%s]" %(entry,'frontends',client,'periods',res,data_set))
        
        # We still need to determine what is causing these missing data in case it is a real issue
        # but using this flags will at least reduce the number of messages in the logs (see commented out messages above)
        if missing_total_data:
            log.debug("aggregate_data, missing total data from file %s" % rrd_site(rrd))
        if missing_client_data:
            log.debug("aggregate_data, missing client data from file %s" % rrd_site(rrd))
            

        # write an aggregate XML file

        # data from indivdual entries
        entry_str = tab + "<entries>\n"
        for entry in stats_entries:
            entry_name = entry.split("/")[-1]
            entry_str += 2 * tab + "<entry name = \"" + entry_name + "\">\n"
            entry_str += 3 * tab + '<total>\n'
            try:
                entry_str += (xmlFormat.dict2string(stats[entry]['total']['periods'], dict_name = 'periods', el_name = 'period', subtypes_params={"class":{}}, indent_tab = tab, leading_tab = 4 * tab) + "\n")
            except (NameError, UnboundLocalError):
                log.debug("total_data, NameError or TypeError")
            entry_str += 3 * tab + '</total>\n'

            entry_str += (3 * tab + '<frontends>\n')
            try:
                entry_frontends = stats[entry]['frontends'].keys()
                entry_frontends.sort()
                for frontend in entry_frontends:
                    entry_str += (4 * tab + '<frontend name=\"' +
                                  frontend + '\">\n')
                    try:
                        entry_str += (xmlFormat.dict2string(stats[entry]['frontends'][frontend]['periods'], dict_name = 'periods', el_name = 'period', subtypes_params={"class":{}}, indent_tab = tab, leading_tab = 5 * tab) + "\n")
                    except KeyError:
                        log.debug("frontend_data, KeyError")
                    entry_str += 4 * tab + '</frontend>\n'
            except TypeError:
                log.debug("frontend_data, TypeError")
            entry_str += (3 * tab + '</frontends>\n')
            entry_str += 2 * tab + "</entry>\n"
        entry_str += tab + "</entries>\n"

        # aggregated data
        total_xml_str = 2 * tab + '<total>\n'
        total_data = aggregate_output['total']
        try:
            total_xml_str += (xmlFormat.dict2string(total_data, dict_name = 'periods', el_name = 'period', subtypes_params={"class":{}}, indent_tab = tab, leading_tab = 4 * tab) + "\n")
        except (NameError, UnboundLocalError):
            log.debug("total_data, NameError or TypeError")
        total_xml_str += 2 * tab + '</total>\n'

        frontend_xml_str = (2 * tab + '<frontends>\n')
        try:
            for frontend in frontends:
                frontend_xml_str += (3 * tab + '<frontend name=\"' +
                                     frontend + '\">\n')
                frontend_data = aggregate_output[frontend]
                frontend_xml_str += (xmlFormat.dict2string(frontend_data, dict_name = 'periods', el_name = 'period', subtypes_params={"class":{}}, indent_tab = tab, leading_tab = 4 * tab) + "\n")
                frontend_xml_str += 3 * tab + '</frontend>\n'
        except TypeError:
            log.debug("frontend_data, TypeError")
        frontend_xml_str += (2 * tab + '</frontends>\n')

        data_str =  (tab + "<total>\n" + total_xml_str + frontend_xml_str +
                     tab + "</total>\n")

        # putting it all together
        updated = time.time()
        xml_str = ('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n' +
                   '<glideFactoryRRDStats>\n' +
                   xmlFormat.time2xml(updated,"updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB) + "\n" + entry_str +
                   data_str + '</glideFactoryRRDStats>')

        try:
            glideFactoryMonitoring.monitoringConfig.write_file(rrd_site(rrd), xml_str)
        except IOError:
            log.debug("write_file %s, IOError"%rrd_site(rrd))

    return



