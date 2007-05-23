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
    for fname,tp,a in attr_rrds:
        glideFactoryMonitoring.monitoringConfig.report_rrds("total/%s"%fname,
                                                            [(a,"total/%s.rrd"%fname)])

    # create graphs for RRDs
    glideFactoryMonitoring.monitoringConfig.graph_rrds("total/Idle",
                                                       "Idle glideins",
                                                       [("Requested","total/Requested_Attribute_Idle.rrd","AREA","00FFFF"),
                                                        ("Idle","total/Status_Attribute_Idle.rrd","LINE2","0000FF")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds("total/Running",
                                                       "Running glideins",
                                                       [("Running","total/Status_Attribute_Running.rrd","AREA","00FF00")])
    glideFactoryMonitoring.monitoringConfig.graph_rrds("total/Held",
                                                       "Held glideins",
                                                       [("Held","total/Status_Attribute_Held.rrd","AREA","c00000")])

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
                if (not os.path.isfile(fname)): #create only if it does not exist
                    fd=open(fname,"w")
                    fd.write("<html>\n<head>\n")
                    fd.write("<title>%s over last %s</title>\n"%(fe,period));
                    fd.write("</head>\n<body>\n")
                    fd.write("<h1>%s over last %s</h1>\n"%(fe,period));
                    fd.write("<table>")
                    for l in [('Idle','Split_Status_Attribute_Idle','Split_Requested_Attribute_Idle'),
                              ('Running','Split_Status_Attribute_Running'),
                              ('Held','Split_Status_Attribute_Held')]:
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
# $Id: glideFactoryMonitorAggregator.py,v 1.2 2007/05/23 22:04:51 sfiligoi Exp $
#
# Log:
#  $Log: glideFactoryMonitorAggregator.py,v $
#  Revision 1.2  2007/05/23 22:04:51  sfiligoi
#  Finalize aggregate monitoring
#
#  Revision 1.1  2007/05/23 19:42:06  sfiligoi
#  Aggregator monitoring for the factory
#
#
###########################################################
