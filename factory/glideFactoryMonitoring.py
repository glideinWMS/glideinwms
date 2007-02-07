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
        self.rrd_step=30        #default to 30 seconds
        self.rrd_heartbeat=120  #default to 1 minute, should be at least twice the loop time
        self.rrd_ds_name="val"
        self.rrd_archives=[('LAST',0.5,1,2*60*4),             # max precision, keep 4 hours at default step, 
                           ('AVERAGE',0.8,10,60/5*24*2),      # 5 min precision, keep 2 days
                           ('AVERAGE',0.92,60,2*24*45),       # 30 min precision, keep for a month and a half
                           ('AVERAGE',0.98,240,12*370)        # 2 hour precision, keep for a years
                           ]
        self.rrd_archives_small=[('LAST',0.5,1,2*60*2),       # max precision, keep 2 hours at default step, 
                                 ('AVERAGE',0.8,10,60/5*6),   # 5 min precision, keep 6 hours
                                 ('AVERAGE',0.92,60,2*24*2),  # 30 min precision, keep for 2 days
                                 ('AVERAGE',0.98,240,12*45)   # 2 hour precision, keep for a month and a half
                                 ]

        self.rrd_reports=[('hour',3600,0),          # an hour worth of data, max resolution
                          ('day',3600*24,1),        # a day worth of data, medium resolution
                          ('month',3600*24*31,2)    # a month worth of data, low resolution
                          ]
        self.graph_sizes=[('small',200,75),
                          ('medium',400,150),
                          ('large',800,300)
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

        tmp2final(fname)
        return
    
    def establish_dir(self,relative_dname):
        dname=os.path.join(self.monitor_dir,relative_dname)      
        if not os.path.isdir(dname):
            os.mkdir(dname)
        return
    
    def write_rrd(self,relative_fname,ds_type,time,val,min=None,max=None):
        """
        Create a RRD file, using rrdtool.
        """
        if self.rrd_bin==None:
            return # nothing to do, no rrd bin no rrd creation
        
        for tp in ((".rrd",self.rrd_archives),(".small.rrd",self.rrd_archives_small)):
            rrd_ext,rrd_archives=tp
            fname=os.path.join(self.monitor_dir,relative_fname+rrd_ext)
            #print "Writing RRD "+fname
        
            if not os.path.isfile(fname):
                #print "Create RRD "+fname
                if min==None:
                    min='U'
                if max==None:
                    max='U'
                create_rrd(self.rrd_bin,fname,
                           self.rrd_step,rrd_archives,
                           (self.rrd_ds_name,ds_type,self.rrd_heartbeat,min,max))

            #print "Updating RRD "+fname
            update_rrd(self.rrd_bin,fname,time,val)
        return
    
    #############################################################################

    def rrd2xml(self,relative_fname,archive_id,
                period,relative_rrd_files):
        """
        Convert one or more RRDs into an XML file using
        rrdtool xport.

        rrd_files is a list of (rrd_id,rrd_fname)
        """

        if self.rrd_bin==None:
            return # nothing to do, no rrd bin no rrd conversion
        
        fname=os.path.join(self.monitor_dir,relative_fname)      
        #print "Converting RRD into "+fname

        rrd_archive=self.rrd_archives[archive_id]

        # convert relative fnames to absolute ones
        rrd_files=[]
        for rrd_file in relative_rrd_files:
            rrd_files.append((rrd_file[0],os.path.join(self.monitor_dir,rrd_file[1])))

        rrd2xml(self.rrd_bin,fname+".tmp",
                self.rrd_step*rrd_archive[2], # step in seconds
                self.rrd_ds_name,
                rrd_archive[0], #ds_type
                period,rrd_files)
        tmp2final(fname)
        return

    def report_rrds(self,base_fname,
                    relative_rrd_files):
        """
        Create default XML files out of the RRD files
        """

        for r in self.rrd_reports:
            pname,period,idx=r
            self.rrd2xml(base_fname+".%s.xml"%pname,idx,
                         period,relative_rrd_files)
        return

    #############################################################################

    def rrd2graph(self,relative_fname,archive_id,
                  period,width,height,
                  title,relative_rrd_files):
        """
        Convert one or more RRDs into a graph using
        rrdtool xport.

        rrd_files is a list of (rrd_id,rrd_fname,graph_style,color,description)
        """

        if self.rrd_bin==None:
            return # nothing to do, no rrd bin no rrd conversion
        
        fname=os.path.join(self.monitor_dir,relative_fname)      
        #print "Converting RRD into "+fname

        rrd_archive=self.rrd_archives[archive_id]

        # convert relative fnames to absolute ones
        rrd_files=[]
        for rrd_file in relative_rrd_files:
            rrd_files.append((rrd_file[0],os.path.join(self.monitor_dir,rrd_file[1]),rrd_file[2],rrd_file[3]))

        rrd2graph(self.rrd_bin,fname+".tmp",
                  self.rrd_step*rrd_archive[2], # step in seconds
                  self.rrd_ds_name,
                  rrd_archive[0], #ds_type
                  period,width,height,title,rrd_files)
        tmp2final(fname)
        return

    def graph_rrds(self,base_fname,
                   relative_title,relative_rrd_files):
        """
        Create default XML files out of the RRD files
        """

        for r in self.rrd_reports:
            pname,period,idx=r
            title=relative_title+" - last "+pname
            for g in self.graph_sizes:
                gname,width,height=g
                self.rrd2graph(base_fname+".%s.%s.png"%(pname,gname),idx,
                               period,width,height,title,relative_rrd_files)
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
            t_el=self.data[client_name]
        else:
            t_el={}
            self.data[client_name]=t_el

        el={}
        t_el['Status']=el

        status_pairs=((1,"Idle"), (2,"Running"), (5,"Held"))
        for p in status_pairs:
            nr,str=p
            if qc_status.has_key(nr):
                el[str]=qc_status[nr]
            else:
                el[str]=0
        self.updated=time.time()

    def logRequest(self,client_name,requests):
        """
        requests is a dictinary of requests

        At the moment, it looks only for
          'IdleGlideins'
        """
        if self.data.has_key(client_name):
            t_el=self.data[client_name]
        else:
            t_el={}
            self.data[client_name]=t_el

        el={}
        t_el['Requested']=el

        if requests.has_key('IdleGlideins'):
            el['Idle']=requests['IdleGlideins']

        self.updated=time.time()


    def get_data(self):
        return self.data

    def get_xml(self):
        return xmlFormat.dict2string(self.data,
                                     dict_name="frontends",el_name="frontend",
                                     params={"updated":long(self.updated)},
                                     subtypes_params={"class":{}})

    def write_file(self):
        global monitoringConfig
        # write snaphot file
        monitoringConfig.write_file("schedd_status.xml",self.get_xml())
        # update RRDs
        for fe in self.data.keys():
            fe_dir="frontend_"+fe
            monitoringConfig.establish_dir(fe_dir)
            fe_el=self.data[fe]
            for tp in fe_el.keys():
                # type - status or requested
                for a in fe_el[tp].keys():
                    a_el=fe_el[tp][a]
                    monitoringConfig.write_rrd("%s/%s_Attribute_%s"%(fe_dir,tp,a),
                                               "GAUGE",self.updated,a_el)
        return
    
    def create_support_history(self):
        global monitoringConfig
        # create history XML files for RRDs
        for fe in self.data.keys():
            fe_dir="frontend_"+fe
            fe_el=self.data[fe]
            for tp in fe_el.keys():
                # type - status or requested
                for a in fe_el[tp].keys():
                    monitoringConfig.report_rrds("%s/%s_Attribute_%s"%(fe_dir,tp,a),
                                                 [(a,"%s/%s_Attribute_%s.rrd"%(fe_dir,tp,a))])
        # create graphs for RRDs
        for fe in self.data.keys():
            fe_dir="frontend_"+fe
            fe_el=self.data[fe]
            monitoringConfig.graph_rrds("%s/Idle"%fe_dir,
                                        "Idle glideins",
                                        [("Requested","%s/Requested_Attribute_Idle.rrd"%fe_dir,"AREA","00FFFF"),
                                         ("Idle","%s/Status_Attribute_Idle.rrd"%fe_dir,"LINE2","0000FF")])
            monitoringConfig.graph_rrds("%s/Running"%fe_dir,
                                        "Running glideins",
                                        [("Running","%s/Status_Attribute_Running.rrd"%fe_dir,"AREA","00FF00")])
            monitoringConfig.graph_rrds("%s/Held"%fe_dir,
                                        "Held glideins",
                                        [("Held","%s/Status_Attribute_Held.rrd"%fe_dir,"AREA","c00000")])

        return
    
class condorLogSummary:
    def __init__(self):
        self.data={}
        self.updated=time.time()
        self.current_stats_data={}     # will contain dictionary client->dirSummary.data
        self.stats_diff={}             # will contain the differences
        self.job_statuses=('Wait','Idle','Running','Held','Completed','Removed') #const

    def reset(self):
        # reserve only those that has been around this time
        new_stats_data={}
        for c in self.stats_diff.keys():
            new_stats_data[c]=self.current_stats_data[c]

        self.current_stats_data=new_stats_data

        # and flush out the differences
        self.stats_diff={}
        

    def logSummary(self,client_name,stats):
        """
         stats - glideFactoryLogParser.dirSummary
        """
        if self.current_stats_data.has_key(client_name):
            old_stats_data=self.current_stats_data[client_name]
        else:
            old_stats_data=None
        
        self.stats_diff[client_name]=stats.diff(old_stats_data)
        self.current_stats_data[client_name]=stats.data
        self.updated=time.time()

    def write_file(self):
        global monitoringConfig
        for client_name in self.stats_diff.keys():
            fe_dir="frontend_"+client_name
            monitoringConfig.establish_dir(fe_dir)
            sdata=self.current_stats_data[client_name]
            sdiff=self.stats_diff[client_name]
            for s in self.job_statuses:
                if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
                    if ((sdata!=None) and (s in sdata.keys())):
                        count=len(sdata[s])
                    else:
                        count=0
                    
                    monitoringConfig.write_rrd("%s/Log_%s_Count"%(fe_dir,s),
                                               "GAUGE",self.updated,count)

                if ((sdiff!=None) and (s in sdiff.keys())):
                    entered=len(sdiff[s]['Entered'])
                    exited=-len(sdiff[s]['Exited'])
                else:
                    entered=0
                    exited=0
                    
                monitoringConfig.write_rrd("%s/Log_%s_Entered"%(fe_dir,s),
                                           "ABSOLUTE",self.updated,entered)
                monitoringConfig.write_rrd("%s/Log_%s_Exited"%(fe_dir,s),
                                           "ABSOLUTE",self.updated,exited)
        return
    
    def create_support_history(self):
        global monitoringConfig
        # create history XML files for RRDs
        for client_name in self.stats_diff.keys():
            fe_dir="frontend_"+client_name
            for s in self.job_statuses:
                report_rrds=[('Entered',"%s/Log_%s_Entered.rrd"%(fe_dir,s)),
                             ('Exited',"%s/Log_%s_Exited.rrd"%(fe_dir,s))]
                if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
                    report_rrds.append(('Count',"%s/Log_%s_Count.rrd"%(fe_dir,s)))
                monitoringConfig.report_rrds("%s/Log_%s"%(fe_dir,s),report_rrds);

        # create graphs for RRDs
        colors={"Wait":"00FFFF","Idle":"0000FF","Running":"00FF00","Held":"c00000"}
        for client_name in self.stats_diff.keys():
            fe_dir="frontend_"+client_name
            for s in self.job_statuses:
                monitoringConfig.graph_rrds("%s/Log_%s_Diff"%(fe_dir,s),
                                            "Difference in "+s,
                                            [('Entered',"%s/Log_%s_Entered.rrd"%(fe_dir,s),"AREA","00ff00"),
                                             ('Exited',"%s/Log_%s_Exited.rrd"%(fe_dir,s),"AREA","ff0000")])

                if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
                    monitoringConfig.graph_rrds("%s/Log_%s_Count"%(fe_dir,s),
                                                s,
                                                [(s,"%s/Log_%s_Count.rrd"%(fe_dir,s)),"AREA",colors[s]])

############### P R I V A T E ################

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

def rrd2xml(rrdbin,xmlfname,
            rrd_step,ds_name,ds_type,
            period,rrd_files):
    now=long(time.time())
    start=((now-period)/rrd_step)*rrd_step
    end=((now-1)/rrd_step)*rrd_step
    cmdline='%s xport -s %li -e %li --step %i' % (rrdbin,start,end,rrd_step)
    for rrd_file in rrd_files:
        cmdline=cmdline+" DEF:%s=%s:%s:%s"%(rrd_file+(ds_name,ds_type))

    for rrd_file in rrd_files:
        ds_id=rrd_file[0]
        cmdline=cmdline+" XPORT:%s:%s"%(ds_id,ds_id)

    cmdline=cmdline+" >%s"%xmlfname

    #print cmdline
    outstr=iexe_cmd(cmdline)
    return

def rrd2graph(rrdbin,fname,
              rrd_step,ds_name,ds_type,
              period,width,height,
              title,rrd_files):
    now=long(time.time())
    start=((now-period)/rrd_step)*rrd_step
    end=((now-1)/rrd_step)*rrd_step
    cmdline='%s graph %s -s %li -e %li --step %i -l 0 -w %i -h %i --imgformat PNG --title "%s"' % (rrdbin,fname,start,end,rrd_step,width,height,title)
    for rrd_file in rrd_files:
        ds_id=rrd_file[0]
        ds_fname=rrd_file[1]
        cmdline=cmdline+" DEF:%s=%s:%s:%s"%(ds_id,ds_fname,ds_name,ds_type)

    for rrd_file in rrd_files:
        ds_id=rrd_file[0]
        ds_graph_type=rrd_file[2]
        ds_color=rrd_file[3]
        cmdline=cmdline+' "%s:%s#%s:%s"'%(ds_graph_type,ds_id,ds_color,ds_id)

    cmdline=cmdline+' "COMMENT:Created on %s"'%time.strftime("%b %d %H\:%M\:%S %Z %Y")

    #print cmdline
    outstr=iexe_cmd(cmdline)
    return

