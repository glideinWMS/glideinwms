#
# Description:
#   This module implements the functions needed
#   to monitor the VO frontend
#
# Author:
#   Igor Sfiligoi (Mar 19th 2009)
#

import os,os.path
import re,time,copy,string,math,random,fcntl
import xmlFormat,timeConversion
import rrdSupport

############################################################
#
# Configuration
#
############################################################

class MonitoringConfig:
    def __init__(self):
        # set default values
        # user should modify if needed
        self.rrd_step=300       #default to 5 minutes
        self.rrd_heartbeat=1800 #default to 30 minutes, should be at least twice the loop time
        self.rrd_archives=[('AVERAGE',0.8,1,1120),      # max precision, keep ~4 days
                           ('AVERAGE',0.92,9,1120),       # 45 min precision, keep for a month (35 days)
                           ('AVERAGE',0.98,96,1120)        # 8 hour precision, keep for a year
                           ]

        # The name of the attribute that identifies the glidein
        self.monitor_dir="monitor/"

        self.rrd_obj=rrdSupport.rrdSupport()

        self.my_name="Unknown"

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
    
    def establish_dir(self,relative_dname):
        dname=os.path.join(self.monitor_dir,relative_dname)      
        if not os.path.isdir(dname):
            os.mkdir(dname)
        return

    def write_rrd_multi(self,relative_fname,ds_type,time,val_dict,min=None,max=None):
        """
        Create a RRD file, using rrdtool.
        """
        if self.rrd_obj.isDummy():
            return # nothing to do, no rrd bin no rrd creation
        
        for tp in ((".rrd",self.rrd_archives),):
            rrd_ext,rrd_archives=tp
            fname=os.path.join(self.monitor_dir,relative_fname+rrd_ext)
            #print "Writing RRD "+fname
        
            if not os.path.isfile(fname):
                #print "Create RRD "+fname
                if min==None:
                    min='U'
                if max==None:
                    max='U'
                ds_names=val_dict.keys()
                ds_names.sort()

                ds_arr=[]
                for ds_name in ds_names:
                    ds_arr.append((ds_name,ds_type,self.rrd_heartbeat,min,max))
                self.rrd_obj.create_rrd_multi(fname,
                                              self.rrd_step,rrd_archives,
                                              ds_arr)

            #print "Updating RRD "+fname
            try:
                self.rrd_obj.update_rrd_multi(fname,time,val_dict)
            except Exception,e:
                print "Failed to update %s"%fname
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
        self.data={}
        self.updated=time.time()

        self.files_updated=None
        self.attributes={'Jobs':("Idle","OldIdle","Running","Total"),
                         'Slots':("Idle","Running","Total")}

    def logJobs(self,jobs_data):
        el={}
        self.data['Jobs']=el

        for k in self.attributes['Jobs']:
            if jobs_data.has_key(k):
                el[k]=jobs_data[k]
        self.updated=time.time()

    def logSlots(self,slots_data):
        el={}
        self.data['Slots']=el

        for k in self.attributes['Slots']:
            if slots_data.has_key(k):
                el[k]=slots_data[k]
        self.updated=time.time()

    def get_data(self):
        return copy.deepcopy(self.data)

    def get_xml_data(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        return xmlFormat.class2string(self.data,'<VOFrontendGroupStats>',
                                     indent_tab=indent_tab,leading_tab=leading_tab)

    def get_updated():
        return self.updated

    def get_xml_updated(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        xml_updated={"UTC":{"unixtime":timeConversion.getSeconds(self.updated),
                            "ISO8601":timeConversion.getISO8601_UTC(self.updated),
                            "RFC2822":timeConversion.getRFC2822_UTC(self.updated)},
                     "Local":{"ISO8601":timeConversion.getISO8601_Local(self.updated),
                              "RFC2822":timeConversion.getRFC2822_Local(self.updated),
                              "human":timeConversion.getHuman(self.updated)}}
        return xmlFormat.dict2string(xml_updated,
                                     dict_name="updated",el_name="timezone",
                                     subtypes_params={"class":{}},
                                     indent_tab=indent_tab,leading_tab=leading_tab)


    def write_file(self):
        global monitoringConfig

        if (self.files_updated!=None) and ((self.updated-self.files_updated)<5):
            # files updated recently, no need to redo it
            return 
        

        # write snaphot file
        xml_str=('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'+
                 '<VOFrontendGroupStats>\n'+
                 self.get_xml_updated(indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
                 xmlFormat.class2string(self.data['Jobs'],'Jobs',indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n",
                 xmlFormat.class2string(self.data['Slots'],'Slots',indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n",
                 "</VOFrontendGroupStats>\n")
        monitoringConfig.write_file("frontend_status.xml",xml_str)

        # update RRDs
        type_strings={'Jobs':'Jobs','Slots':'Slots'}
        for tp in self.data.keys():
            # type - Jobs,Slots
            if not (tp in self.attributes.keys()):
                continue

            tp_str=type_strings[tp]

            attributes_tp=self.attributes[tp]
            for a in attributes_tp:
                val_dict["%s%s"%(tp_str,a)]=None #init, so that gets created properly
                
            fe_el_tp=seld.data[tp]
            for a in fe_el_tp.keys():
                if a in attributes_tp:
                    a_el=fe_el_tp[a]
                    if type(a_el)!=type({}): # ignore subdictionaries
                        val_dict["%s%s"%(tp_str,a)]=a_el
                
        monitoringConfig.write_rrd_multi("%s/Status_Attributes"%fe_dir,
                                         "GAUGE",self.updated,val_dict)

        self.files_updated=self.updated        
        return

############### P R I V A T E ################

##################################################
def tmp2final(fname):
    try:
        os.remove(fname+"~")
    except:
        pass

    try:
        os.rename(fname,fname+"~")
    except:
        pass

    try:
      os.rename(fname+".tmp",fname)
    except:
      print "Failed renaming %s.tmp into %s"%(fname,fname)
    return


##################################################

# global configuration of the module
monitoringConfig=MonitoringConfig()

