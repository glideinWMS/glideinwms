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
        for a in global_total[tp].keys():
            a_el=int(global_total[tp][a])
            glideFactoryMonitoring.monitoringConfig.write_rrd("total/%s_Attribute_%s"%(tp,a),
                                                              "GAUGE",updated,a_el)

    return status

##############################################################################
# create the history graphs and related index html file
def create_status_history():
    # create history XML files for RRDs
    attr_rrds=glideFactoryMonitoring.monitoringConfig.find_disk_attributes("total")
    # Temporarely DEPRECATE
    #for fname,tp,a in attr_rrds:
    #    glideFactoryMonitoring.monitoringConfig.report_rrds("total/%s"%fname,
    #                                                        [(a,"total/%s.rrd"%fname)])
    
    # use the same reference time for all the graphs
    graph_ref_time=time.time()
    # remember to call update_locks before exiting this function

    # create graphs for RRDs
    glideFactoryMonitoring.monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                                       "total/Idle",
                                                       "Idle glideins",
                                                       [("Requested","total/Requested_Attribute_Idle.rrd","AREA","00FFFF"),
                                                        ("Idle","total/Status_Attribute_Idle.rrd","LINE2","0000FF"),
                                                        ("Wait","total/Status_Attribute_Wait.rrd","LINE2","FF00FF"),
                                                        ("Pending","total/Status_Attribute_Pending.rrd","LINE2","00FF00"),
                                                        ("IdleOther","total/Status_Attribute_IdleOther.rrd","LINE2","FF0000")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                                       "total/Running",
                                                       "Running glideins",
                                                       [("Running","total/Status_Attribute_Running.rrd","AREA","00FF00"),
                                                        ("ClientGlideins","total/ClientMonitor_Attribute_GlideinsTotal.rrd","LINE2","000000"),
                                                        ("ClientRunning","total/ClientMonitor_Attribute_GlideinsRunning.rrd","LINE2","0000FF")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                                       "total/Held",
                                                       "Held glideins",
                                                       [("Held","total/Status_Attribute_Held.rrd","AREA","c00000")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                                       "total/ClientIdle",
                                                       "Idle client",
                                                       [("Idle","total/ClientMonitor_Attribute_Idle.rrd","AREA","00FFFF"),
                                                        ("Requested","total/Requested_Attribute_Idle.rrd","LINE2","0000FF")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                                       "total/ClientRunning",
                                                       "Running client jobs",
                                                       [("Running","total/ClientMonitor_Attribute_Running.rrd","AREA","00FF00")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                                       "total/InfoAge",
                                                       "Client info age",
                                                       [("InfoAge","total/ClientMonitor_Attribute_InfoAge.rrd","LINE2","000000")])

    # create split graphs
    colors_base=[(0,1,0),(0,1,1),(1,1,0),(1,0,1),(0,0,1),(1,0,0)]
    colors_intensity=['ff','d0','a0','80','e8','b8']
    colors=[]
    for ci_i in colors_intensity:
        si_arr=['00',ci_i]
        for cb_i in colors_base:
            colors.append('%s%s%s'%(si_arr[cb_i[0]],si_arr[cb_i[1]],si_arr[cb_i[2]]))

    if 'Split' in glideFactoryMonitoring.monitoringConfig.wanted_graphs:
      for fname,tp,a in attr_rrds:
        rrd_fnames=[]
        idx=0
        for entry in monitorAggregatorConfig.entries:
            area_name="STACK"
            if idx==0:
                area_name="AREA"
            rrd_fnames.append((string.replace(string.replace(entry,".","_"),"@","_"),"entry_%s/total/%s.rrd"%(entry,fname),area_name,colors[idx%len(colors)]))
            idx=idx+1

        if tp=="ClientMonitor":
            if a=="InfoAge":
                tstr="Client info age"
            else:
                tstr="%s client jobs"%a
        elif tp=="Status":
            tstr="%s glideins"%a
        else:
            tstr="%s %s glideins"%(tp,a)
        glideFactoryMonitoring.monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                                           "total/Split_%s"%fname,
                                                           tstr,
                                                           rrd_fnames)
        
        
    # create support index files
    fe="Factory Total"
    for rp in glideFactoryMonitoring.monitoringConfig.rrd_reports:
            period=rp[0]
            for sz in glideFactoryMonitoring.monitoringConfig.graph_sizes:
                size=sz[0]
                fname=os.path.join(monitorAggregatorConfig.monitor_dir,"total/0Status.%s.%s.html"%(period,size))
                #if (not os.path.isfile(fname)): #create only if it does not exist
                if 1: # create every time, it is small and works over reconfigs
                    fd=open(fname,"w")
                    fd.write("<html>\n<head>\n")
                    fd.write("<title>%s over last %s</title>\n"%(fe,period));
                    fd.write("</head>\n<body>\n")
                    fd.write('<table width="100%"><tr>\n')
                    fd.write('<td rowspan=2 valign="top" align="left"><h1>%s over last %s</h1></td>\n'%(fe,period));

                    link_arr=[]
                    for ref_sz in glideFactoryMonitoring.monitoringConfig.graph_sizes:
                        ref_size=ref_sz[0]
                        if size!=ref_size:
                            link_arr.append('<a href="0Status.%s.%s.html">%s</a>'%(period,ref_size,ref_size))
                    fd.write('<td align="center">[%s]</td>\n'%string.join(link_arr,' | '));

                    link_arr=[]
                    for ref_rp in glideFactoryMonitoring.monitoringConfig.rrd_reports:
                        ref_period=ref_rp[0]
                        if period!=ref_period:
                            link_arr.append('<a href="0Status.%s.%s.html">%s</a>'%(ref_period,size,ref_period))
                    fd.write('<td align="center">[%s]</td>\n'%string.join(link_arr,' | '));

                    fd.write('<td align="right">[<a href="0Log.%s.%s.html">Log</a>]</td>\n'%(period,size))
                        
                    fd.write("</tr><tr>\n")

                    fd.write("<td></td>\n") # no up link
                    link_arr=[]
                    for entry in monitorAggregatorConfig.entries:
                            link_arr.append('<a href="../entry_%s/total/0Status.%s.%s.html">%s</a>'%(entry,period,size,entry))
                    fd.write('<td colspan=3 align="right">[%s]</td>\n'%string.join(link_arr,' | '));


                    fd.write("</tr></table>\n")
                    fd.write('<a name="glidein_status">\n')
                    fd.write("<h2>Glidein stats</h2>\n")
                    fd.write("<table>")

                    larr=[]
                    if 'Split' in glideFactoryMonitoring.monitoringConfig.wanted_graphs:
                        larr.append(('Running','Split_Status_Attribute_Running','Split_Requested_Attribute_MaxRun'))
                        larr.append(('Idle','Split_Status_Attribute_Idle','Split_Requested_Attribute_Idle'))
                        larr.append(('Split_Status_Attribute_Wait','Split_Status_Attribute_Pending','Split_Status_Attribute_IdleOther'))
                    else:
                        larr.append(('Running',))
                        larr.append(('Idle',))

                    if 'Held' in glideFactoryMonitoring.monitoringConfig.wanted_graphs:
                        if 'Split' in glideFactoryMonitoring.monitoringConfig.wanted_graphs:
                            larr.append(('Held','Split_Status_Attribute_Held'))
                        else:
                            larr.append(('Held',))

                    for l in larr:
                        fd.write('<tr valign="top">')
                        for s in l:
                            fd.write('<td>%s</td>'%img2html("%s.%s.%s.png"%(s,period,size)))
                        fd.write('</tr>\n')                            
                    fd.write("</table>")
                    fd.write('<a name="client_status">\n')
                    fd.write("<h2>Frontend (client) stats</h2>\n")
                    fd.write("<table>")

                    larr=[]
                    if 'Split' in glideFactoryMonitoring.monitoringConfig.wanted_graphs:
                        larr.append(('ClientIdle','Split_ClientMonitor_Attribute_Idle'))
                        larr.append(('ClientRunning','Split_ClientMonitor_Attribute_Running'))
                    else:
                        larr.append(('ClientIdle',))
                        larr.append(('ClientRunning',))

                    if 'InfoAge' in glideFactoryMonitoring.monitoringConfig.wanted_graphs:
                        if 'Split' in glideFactoryMonitoring.monitoringConfig.wanted_graphs:
                            larr.append(('InfoAge','Split_ClientMonitor_Attribute_InfoAge'))
                        else:
                            larr.append(('InfoAge',))

                    for l in larr:
                        fd.write('<tr valign="top">')
                        for s in l:
                            fd.write('<td>%s</td>'%img2html("%s.%s.%s.png"%(s,period,size)))
                        fd.write('</tr>\n')                            
                    fd.write("</table>")
                    fd.write("</body>\n</html>\n")
                    fd.close()
                    pass

    glideFactoryMonitoring.monitoringConfig.update_locks(graph_ref_time,"status")
    return

######################################################################################
# create an aggregate of log summary files, write it in an aggregate log summary file
# end return the values
def aggregateLogSummary():
    global monitorAggregatorConfig

    # initialize global counters
    global_total={'Current':{},'Entered':{},'Exited':{},'CompletedCounts':{'Failed':0,'Waste':{},'WasteTime':{},'Lasted':{}}}
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

    #
    status={'entries':{},'total':global_total}
    nr_entries=0
    for entry in monitorAggregatorConfig.entries:
        # load entry log summary file
        status_fname=os.path.join(os.path.join(monitorAggregatorConfig.monitor_dir,'entry_'+entry),
                                  monitorAggregatorConfig.logsummary_relname)
        try:
            entry_data=xmlParse.xmlfile2dict(status_fname,always_singular_list=['Fraction','TimeRange'])
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
            out_fe_el['CompletedCounts']={'Waste':{},'WasteTime':{},'Lasted':{}}
            out_fe_el['CompletedCounts']['Failed']=int(fe_el['CompletedCounts']['Failed'])
            for k in ['idle', 'validation', 'badput', 'nosuccess']:
                for w in ("Waste","WasteTime"):
                    out_fe_el['CompletedCounts'][w][k]={}
                    for t in glideFactoryMonitoring.getAllMillRanges():
                        out_fe_el['CompletedCounts'][w][k][t]=int(fe_el['CompletedCounts'][w][k][t]['val'])
            for t in glideFactoryMonitoring.getAllTimeRanges():
                out_fe_el['CompletedCounts']['Lasted'][t]=int(fe_el['CompletedCounts']['Lasted'][t]['val'])
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
            local_total['CompletedCounts']={'Waste':{},'WasteTime':{},'Lasted':{}}
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
    for s in ('Wait','Idle','Running','Held','Completed','Removed'):
        if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
            count=sdata[s]
            glideFactoryMonitoring.monitoringConfig.write_rrd("%s/Log_%s_Count"%(fe_dir,s),
                                                              "GAUGE",updated,count)
            exited=-status["total"]['Exited'][s]
            glideFactoryMonitoring.monitoringConfig.write_rrd("%s/Log_%s_Exited"%(fe_dir,s),
                                                              "ABSOLUTE",updated,exited)
            
        entered=status["total"]['Entered'][s]
        glideFactoryMonitoring.monitoringConfig.write_rrd("%s/Log_%s_Entered"%(fe_dir,s),
                                                          "ABSOLUTE",updated,entered)

        if s=='Completed':
            completed_counts=status["total"]['CompletedCounts']
            count_entered_times=completed_counts['Lasted']
            count_validation_failed=completed_counts['Failed']
            count_waste_mill=completed_counts['Waste']
            time_waste_mill=completed_counts['WasteTime']
            # save run times
            for timerange in count_entered_times.keys():
                glideFactoryMonitoring.monitoringConfig.write_rrd("%s/Log_%s_Entered_Lasted_%s"%(fe_dir,s,timerange),
                                                   "ABSOLUTE",updated,count_entered_times[timerange])
            # save failures
            glideFactoryMonitoring.monitoringConfig.write_rrd("%s/Log_%s_Entered_Failed"%(fe_dir,s),
                                                              "ABSOLUTE",updated,count_validation_failed)

            # save waste_mill
            for w in count_waste_mill.keys():
                count_waste_mill_w=count_waste_mill[w]
                for p in count_waste_mill_w.keys():
                    glideFactoryMonitoring.monitoringConfig.write_rrd("%s/Log_%s_Entered_Waste_%s_%s"%(fe_dir,s,w,p),
                                                                      "ABSOLUTE",updated,count_waste_mill_w[p])
            for w in time_waste_mill.keys():
                time_waste_mill_w=time_waste_mill[w]
                for p in time_waste_mill_w.keys():
                    glideFactoryMonitoring.monitoringConfig.write_rrd("%s/Log_%s_Entered_WasteTime_%s_%s"%(fe_dir,s,w,p),
                                                                      "ABSOLUTE",updated,time_waste_mill_w[p])
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
    glideFactoryMonitoring.create_log_total_index("Factory total","entry","../entry_%s/total",monitorAggregatorConfig.entries,None)
    
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

