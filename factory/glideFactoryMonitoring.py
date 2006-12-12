#
# Description:
#   This module implements the functions needed
#   to monitor the glidein factory
#
# Author:
#   Igor Sfiligoi (Dec 11th 2006)
#

import os,os.path
import time
import xmlFormat

############################################################
#
# Configuration
#
############################################################

class MonitoringConfig:
    def __init__(self):
        # set default values
        # user should modify if needed

        # The name of the attribute that identifies the glidein
        self.monitor_dir="monitor/"

    def write_file(self,relative_fname,str):
        fname=os.path.join(self.monitor_dir,relative_fname)
        #print "Writing "+fname
        fd=open(fname+".tmp","w")
        try:
            fd.write(str+"\n")
        finally:
            fd.close()

        try:
            os.remove(fname+"~")
        except:
            pass

        try:
            os.rename(fname,fname+"~")
        except:
            pass

        os.rename(fname+".tmp",fname)


# global configuration of the module
monitoringConfig=MonitoringConfig()

############################################################
#
# Status 
#
############################################################

class condorQStats:
    def __init__(self):
        self.data={}
        self.updated=time.time()

    def logSchedd(self,client_name,qc_status):
        """
        qc_status is a dictionary of condor_status:nr_jobs
        """
        if self.data.has_key(client_name):
            el=self.data[client_name]
        else:
            el={}

        status_pairs=((1,"Idle"), (2,"Running"), (5,"Held"))
        for p in status_pairs:
            nr,str=p
            if qc_status.has_key(nr):
                el[str]=qc_status[nr]
            else:
                el[str]=0
        self.data[client_name]=el
        self.updated=time.time()

    def logRequest(self,client_name,requests):
        """
        requests is a dictinary of requests

        At the moment, it looks only for
          'IdleGlideins'
        """
        if self.data.has_key(client_name):
            el=self.data[client_name]
        else:
            el={}

        if requests.has_key('IdleGlideins'):
            el['RequestedIdle']=requests['IdleGlideins']

        self.data[client_name]=el
        self.updated=time.time()


    def get_data(self):
        return self.data

    def get_xml(self):
        return xmlFormat.dict2string(self.data,
                                     dict_name="glideins",el_name="frontend",
                                     params={"updated":long(self.updated)},
                                     subtypes_params={"class":{}})

    def write_file(self):
        global monitoringConfig
        return monitoringConfig.write_file("schedd_status.xml",self.get_xml())


    
    
