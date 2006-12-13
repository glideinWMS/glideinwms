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
from condorExe import iexe_cmd,ExeError # i know this is not the most appropriate use of it, but it works

############################################################
#
# Configuration
#
############################################################

class MonitoringConfig:
    def __init__(self):
        # set default values
        # user should modify if needed
        self.rrd_step=60        #default to 1 minute
        self.rrd_heartbeat=120  #default to 1 minute, should be at least twice the loop time
        self.rrd_ds_name="val"
        self.rrd_archives=[('LAST',0.5,1,3000),     # max precision, keep 2 days at default step, 
                           ('AVERAGE',0.8,10,6000), # 10 min precision, keep for a month and a half
                           ('AVERAGE',0.95,120,10000) # 2 hour precision, keep for a couple of years
                           ]


        # The name of the attribute that identifies the glidein
        self.monitor_dir="monitor/"

        try:
            self.rrd_bin=iexe_cmd("which rrdtool")[0][:-1]
        except ExeError,e:
            self.rrd_bin=None # not found


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

    def establish_dir(self,relative_dname):
        dname=os.path.join(self.monitor_dir,relative_dname)      
        if not os.path.isdir(dname):
            os.mkdir(dname)
        return
    
    def write_rrd(self,relative_fname,ds_type,time,val,min=None,max=None):
        if self.rrd_bin==None:
            return # nothing to do, no rrd bin no rrd creation
        
        fname=os.path.join(self.monitor_dir,relative_fname)      
        #print "Writing RRD "+fname
        
        if not os.path.isfile(fname):
            #print "Create RRD "+fname
            if min==None:
                min='U'
            if max==None:
                max='U'
            create_rrd(self.rrd_bin,fname,
                       self.rrd_step,self.rrd_archives,
                       (self.rrd_ds_name,ds_type,self.rrd_heartbeat,min,max))

        #print "Updating RRD "+fname
        update_rrd(self.rrd_bin,fname,time,val)
        return

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
        monitoringConfig.write_file("schedd_status.xml",self.get_xml())
        for fe in self.data.keys():
            fe_dir="frontend_"+fe
            monitoringConfig.establish_dir(fe_dir)
            fe_el=self.data[fe]
            for a in fe_el.keys():
                a_el=fe_el[a]
                monitoringConfig.write_rrd("%s/attribute_%s.rrd"%(fe_dir,a),"GAUGE",self.updated,a_el)
        return
    

    
    
############### P R I V A T E ################

def create_rrd(rrdbin,rrdfname,
               rrd_step,rrd_archives,
               rrd_ds):
    start_time=(long(time.time()-1)/rrd_step)*rrd_step # make the start time to be aligned on the rrd_step boundary - needed for optimal resoultion selection 
    #print (rrdbin,rrdfname,start_time,rrd_step)+rrd_ds
    cmdline='%s create %s -b %li -s %i DS:%s:%s:%i:%s:%s'%((rrdbin,rrdfname,start_time,rrd_step)+rrd_ds)
    for archive in rrd_archives:
        cmdline=cmdline+" RRA:%s:%g:%i:%i"%archive

    outstr=iexe_cmd(cmdline)
    return

def update_rrd(rrdbin,rrdfname,
               time,val):
    cmdline='%s update %s %li:%i'%(rrdbin,rrdfname,time,val)
    outstr=iexe_cmd(cmdline)
    return
