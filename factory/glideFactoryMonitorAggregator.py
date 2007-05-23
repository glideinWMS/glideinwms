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
    
    def write_file(self,relative_fname,str):
        fname=os.path.join(self.monitor_dir,relative_fname)
        #print "Writing "+fname
        fd=open(fname+".tmp","w")
        try:
            fd.write(str+"\n")
        finally:
            fd.close()

        tmp2final(fname)
        return
    

# global configuration of the module
monitorAggregatorConfig=MonitorAggregatorConfig()

###########################################################
#
# Functions
#
###########################################################


def aggregateStatus():
    global monitorAggregatorConfig

    global_total={'Status':None,'Requested':None}
    status={'entries':{},'total':global_total}
    for entry in monitorAggregatorConfig.entries:
        # load entry status file
        status_fname=os.path.join(os.path.join(monitorAggregatorConfig.monitor_dir,'entry_'+entry),
                                  monitorAggregatorConfig.status_relname)
        entry_data=xmlParse.xmlfile2dict(status_fname)

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

    xml_str=('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'+
             '<glideFactoryQStats>\n'+
             get_xml_updated(time.time(),indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.dict2string(status["entries"],dict_name="entries",el_name="entry",
                                   subtypes_params={"class":{"dicts_params":{"frontends":{"el_name":"frontend",
                                                                                          "subtypes_params":{"class":{"subclass_params":{"Requested":{"dicts_params":{"Parameters":{"el_name":"Parameter",
                                                                                                                                                                                    "subtypes_params":{"class":{}}}}}}}}}}}},
                                   leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             xmlFormat.class2string(status["total"],inst_name="total",leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
             "</glideFactoryQStats>\n")
    monitorAggregatorConfig.write_file(monitorAggregatorConfig.status_relname,xml_str)
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

def tmp2final(fname):
    try:
        os.remove(fname+"~")
    except:
        pass

    try:
        os.rename(fname,fname+"~")
    except:
        pass

    os.rename(fname+".tmp",fname)
    return


###########################################################
#
# CVS info
#
# $Id: glideFactoryMonitorAggregator.py,v 1.1 2007/05/23 19:42:06 sfiligoi Exp $
#
# Log:
#  $Log: glideFactoryMonitorAggregator.py,v $
#  Revision 1.1  2007/05/23 19:42:06  sfiligoi
#  Aggregator monitoring for the factory
#
#
###########################################################
