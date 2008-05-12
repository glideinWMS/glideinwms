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

        # name of the status file
        self.status_relname="schedd_status.xml"

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

    global_total={'Status':None,'Requested':None}
    status={'entries':{},'total':global_total}
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
# create an aggregate of status files, write it in an aggregate status file
# end return the values
def create_status_history():
    # create history XML files for RRDs
    attr_rrds=glideFactoryMonitoring.monitoringConfig.find_disk_attributes("total")
    # Temporarely DEPRECATE
    #for fname,tp,a in attr_rrds:
    #    glideFactoryMonitoring.monitoringConfig.report_rrds("total/%s"%fname,
    #                                                        [(a,"total/%s.rrd"%fname)])

    # create graphs for RRDs
    glideFactoryMonitoring.monitoringConfig.graph_rrds("total/Idle",
                                                       "Idle glideins",
                                                       [("Requested","total/Requested_Attribute_Idle.rrd","AREA","00FFFF"),
                                                        ("Idle","total/Status_Attribute_Idle.rrd","LINE2","0000FF"),
                                                        ("Wait","total/Status_Attribute_Wait.rrd","LINE2","FF00FF"),
                                                        ("Pending","total/Status_Attribute_Pending.rrd","LINE2","00FF00"),
                                                        ("IdleOther","total/Status_Attribute_IdleOther.rrd","LINE2","FF0000")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds("total/Running",
                                                       "Running glideins",
                                                       [("Running","total/Status_Attribute_Running.rrd","AREA","00FF00")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds("total/Held",
                                                       "Held glideins",
                                                       [("Held","total/Status_Attribute_Held.rrd","AREA","c00000")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds("total/ClientIdle",
                                                       "Idle client",
                                                       [("Idle","total/ClientMonitor_Attribute_Idle.rrd","AREA","00FFFF"),
                                                        ("Requested","total/Requested_Attribute_Idle.rrd","LINE2","0000FF")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds("total/ClientRunning",
                                                       "Running client jobs",
                                                       [("Running","total/ClientMonitor_Attribute_Running.rrd","AREA","00FF00")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds("total/InfoAge",
                                                       "Client info age",
                                                       [("InfoAge","total/ClientMonitor_Attribute_InfoAge.rrd","LINE2","000000")])

    # create split graphs
    colors=['00ff00','00ffff','ffff00','ff00ff','0000ff','ff0000']
    for fname,tp,a in attr_rrds:
        rrd_fnames=[]
        idx=0
        for entry in monitorAggregatorConfig.entries:
            area_name="STACK"
            if idx==0:
                area_name="AREA"
            rrd_fnames.append((string.replace(string.replace(entry,".","_"),"@","_"),"entry_%s/total/%s.rrd"%(entry,fname),area_name,colors[idx%len(colors)]))
            idx=idx+1

        if tp=="Status":
            tstr=a
        else:
            tstr="%s %s"%(tp,a)
        glideFactoryMonitoring.monitoringConfig.graph_rrds("total/Split_%s"%fname,
                                                           "%s glideins"%tstr,
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
                    for entry in monitorAggregatorConfig.entries:
                            link_arr.append('<a href="../entry_%s/total/0Status.%s.%s.html">%s</a>'%(entry,period,size,entry))
                    fd.write('<td width="33%%" rowspan=2 align="right">[%s]</td>\n'%string.join(link_arr,' | '));

                    fd.write("</tr><tr>\n")

                    link_arr=[]
                    for ref_rp in glideFactoryMonitoring.monitoringConfig.rrd_reports:
                        ref_period=ref_rp[0]
                        if period!=ref_period:
                            link_arr.append('<a href="0Status.%s.%s.html">%s</a>'%(ref_period,size,ref_period))
                    fd.write('<td align="center">[%s]</td>\n'%string.join(link_arr,' | '));

                    fd.write("</tr></table>\n")
                    fd.write("<h2>Glidein stats</h2>\n")
                    fd.write("<table>")
                    for l in [('Idle','Split_Status_Attribute_Idle','Split_Requested_Attribute_Idle'),
                              ('Split_Status_Attribute_Wait','Split_Status_Attribute_Pending','Split_Status_Attribute_IdleOther'),
                              ('Running','Split_Status_Attribute_Running','Split_Requested_Attribute_MaxRun'),
                              ('Held','Split_Status_Attribute_Held')]:
                        fd.write('<tr valign="top">')
                        for s in l:
                            fd.write('<td><img src="%s.%s.%s.png"></td>'%(s,period,size))
                        fd.write('</tr>\n')                            
                    fd.write("</table>")
                    fd.write("<h2>Frontend (client) stats</h2>\n")
                    fd.write("<table>")
                    for l in [('ClientIdle','Split_ClientMonitor_Attribute_Idle'),
                              ('ClientRunning','Split_ClientMonitor_Attribute_Running'),
                              ('InfoAge','Split_ClientMonitor_Attribute_InfoAge')]:
                        fd.write('<tr valign="top">')
                        for s in l:
                            fd.write('<td><img src="%s.%s.%s.png"></td>'%(s,period,size))
                        fd.write('</tr>\n')                            
                    fd.write("</table>")
                    fd.write("</body>\n</html>\n")
                    fd.close()
                    pass

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


###########################################################
#
# CVS info
#
# $Id: glideFactoryMonitorAggregator.py,v 1.8 2008/05/12 00:10:55 sfiligoi Exp $
#
# Log:
#  $Log: glideFactoryMonitorAggregator.py,v $
#  Revision 1.8  2008/05/12 00:10:55  sfiligoi
#  Add new attrs to total
#
#  Revision 1.7  2008/05/12 00:09:49  sfiligoi
#  Add new attrs to total
#
#  Revision 1.6  2008/05/05 19:51:06  sfiligoi
#  Always re-create the index files to account for reconfigs
#
#  Revision 1.5  2007/09/26 20:04:21  sfiligoi
#  Disable history XMLs
#
#  Revision 1.4  2007/07/03 19:46:18  sfiligoi
#  Add support for MaxRunningGlideins
#
#  Revision 1.3  2007/05/24 14:34:51  sfiligoi
#  Add links between pages
#
#  Revision 1.2  2007/05/23 22:04:51  sfiligoi
#  Finalize aggregate monitoring
#
#  Revision 1.1  2007/05/23 19:42:06  sfiligoi
#  Aggregator monitoring for the factory
#
#
###########################################################
