#
# Description:
#   This module implements the functions needed
#   to monitor the glidein factory
#
# Author:
#   Igor Sfiligoi (Dec 11th 2006)
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
        self.rrd_ds_name="val"
        self.rrd_archives=[('AVERAGE',0.8,1,60/5*24*2),      # max precision, keep 2 days
                           ('AVERAGE',0.92,6,2*24*45),       # 30 min precision, keep for a month and a half
                           ('AVERAGE',0.98,24,12*370)        # 2 hour precision, keep for a year
                           ]

        self.rrd_reports=[('hours',3600*4,0,1),        #four hour worth of data, max resolution, update at every slot
                          ('day',3600*24,0,6),        # a day worth of data, still high resolution, update as if it was medium res
                          ('week',3600*24*7,1,4),     # a week worth of data, medium resolution, update every 2 hours
                          ('month',3600*24*31,1,12),   # a month worth of data, medium resolution, update once a day
                          ('year',3600*24*365,2,7*12/4)   # a week worth of data, low resolution, update one a week
                          ]
        self.graph_sizes=[('small',200,75),
                          ('large',400,150),
                          ]
        
        # The name of the attribute that identifies the glidein
        self.lock_dir="./lock" # if None, will not lock
        self.monitor_dir="monitor/"
        self.log_dir="log/"

        self.wanted_graphs=['Basic']

        self.rrd_obj=LockedRRDSupport()
        self.attribute_rrd_recmp=re.compile("^(?P<tp>[a-zA-Z]+)_Attribute_(?P<attr>[a-zA-Z]+)\.rrd$")

        self.my_name="Unknown"

    def logCompleted(self,entered_dict):
        now=time.time()

        job_ids=entered_dict.keys()
        if len(job_ids)==0:
            return # nothing to do
        job_ids.sort()
        
        relative_fname="completed_jobs_%s.log"%time.strftime("%Y%m%d",time.localtime(now))
        fname=os.path.join(self.log_dir,relative_fname)
        fd=open(fname,"a")
        try:
            for job_id in job_ids:
                el=entered_dict[job_id]
                jobs_duration=el['jobs_duration']
                waste_mill=el['wastemill']
                fd.write(("<job %37s %17s %17s %22s>"%(('terminated="%s"'%timeConversion.getISO8601_Local(now)),
                                                       ('id="%s"'%job_id),
                                                       ('duration="%i"'%el['duration']),
                                                       ('condor_started="%s"'%(el['condor_started']==True))))+
                         ("<user %14s %17s %16s %19s/>"%(('jobsnr="%i"'%el['jobsnr']),
                                                         ('duration="%i"'%jobs_duration['total']),
                                                         ('goodput="%i"'%jobs_duration['goodput']),
                                                         ('terminated="%i"'%jobs_duration['terminated'])))+
                         ("<wastemill %17s %11s %16s %13s/></job>\n"%(('validation="%i"'%waste_mill['validation']),
                                                                      ('idle="%i"'%waste_mill['idle']),
                                                                      ('nosuccess="%i"'%waste_mill['nosuccess']),
                                                                      ('badput="%i"'%waste_mill['badput']))))
        finally:
            fd.close()

    def get_disk_lock(self):
        if self.lock_dir==None:
            return open("/dev/null","r") # locking not needed, but need to return a file

        disk_lock_fname=os.path.join(self.lock_dir,'monitor.disk.lock')
        disk_lock_fd=open(disk_lock_fname,"w")
        try:
            fcntl.flock(disk_lock_fd,fcntl.LOCK_EX)
        except:
            disk_lock_fd.close()
            raise
        
        return disk_lock_fd
    
    def get_graph_lock(self):
        if self.lock_dir==None:
            return open("/dev/null","r") # locking not needed, but need to return a file

        graph_lock_fname=os.path.join(self.lock_dir,'monitor.graph.lock')
        graph_lock_fd=open(graph_lock_fname,"w")
        try:
            fcntl.flock(graph_lock_fd,fcntl.LOCK_EX)
        except:
            graph_lock_fd.close()
            raise
        
        return graph_lock_fd
    
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

    def find_disk_frontends(self):
        frontends=[]
        fnames=os.listdir(self.monitor_dir)
        for fname in fnames:
            if fname[:9]=="frontend_":
                frontends.append(fname[9:])
        return frontends

    def write_rrd(self,relative_fname,ds_type,time,val,min=None,max=None):
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
                self.rrd_obj.create_rrd(fname,
                                        self.rrd_step,rrd_archives,
                                        (self.rrd_ds_name,ds_type,self.rrd_heartbeat,min,max))

            #print "Updating RRD "+fname
            try:
                self.rrd_obj.update_rrd(fname,time,val)
            except Exception,e:
                print "Failed to update %s"%fname
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
    
    #############################################################################
    def update_lock(self,ref_time,relative_lock_fname,
                    archive_id,freq):
        rrd_archive=self.rrd_archives[archive_id]

        lock_fname=os.path.join(self.monitor_dir,os.path.join('lock',relative_lock_fname))
        try:
            if os.path.getmtime(lock_fname)>(ref_time-self.rrd_step*rrd_archive[2]*freq):
                return # file too new to see any benefit from an update
        except OSError:
            pass # file does not exist -> will be created later on

        # touch lock file
        try:
            fd=open(lock_fname,"w")
            fd.close()
        except:
            pass # ignore errors

        return

    def rrd2graph(self,ref_time,relative_lock_fname,
                  relative_fname,
                  archive_id,freq,
                  period,width,height,
                  title,relative_rrd_files,cdef_arr=None,trend=None):
        """
        Convert one or more RRDs into a graph using
        rrdtool xport.

        rrd_files is a list of (rrd_id,rrd_fname,graph_style,color,description)
        """

        if self.rrd_obj.isDummy():
            return None # nothing to do, no rrd bin no rrd conversion
        
        fname=os.path.join(self.monitor_dir,relative_fname)      

        rrd_archive=self.rrd_archives[archive_id]

        lock_fname=os.path.join(self.monitor_dir,os.path.join('lock',relative_lock_fname))
        try:
            if os.path.getmtime(lock_fname)>(ref_time-self.rrd_step*rrd_archive[2]*freq):
                return None # file too new to see any benefit from an update
        except OSError:
            pass # file does not exist -> will be created later on

        #print "Converting RRD into "+fname

        # convert relative fnames to absolute ones
        rrd_files=[]
        for rrd_file in relative_rrd_files:
            rrd_fname_arr=string.split(rrd_file[1],'?id=',1)
            if len(rrd_fname_arr)==2:
                rrd_fname=rrd_fname_arr[0]
                rrd_ds_name=rrd_fname_arr[1]
            else:
                rrd_fname=rrd_file[1]
                rrd_ds_name=self.rrd_ds_name
            
            abs_rrd_fname=os.path.join(self.monitor_dir,rrd_fname)
            if not os.path.isfile(abs_rrd_fname):
                return None# at least one file missing, file creation would fail
            rrd_files.append((rrd_file[0],abs_rrd_fname,
                              rrd_ds_name,rrd_archive[0], #ds_type
                              rrd_file[2],rrd_file[3]))

        cmd_used=self.rrd_obj.rrd2graph_multi_now(fname+".tmp",
                                                  self.rrd_step*rrd_archive[2], # step in seconds
                                                  period,width,height,title,rrd_files,cdef_arr,trend)
        tmp2final(fname)
        return cmd_used

    # if trend_fraction!=None, the fraction of period to trend over
    # for example, if trend==10, it will be 360s in an hour graph, and 2.4hours in a day graph
    def graph_rrds(self,ref_time,base_lock_fname,parent,
                   base_fname,
                   relative_title,relative_rrd_files,cdef_arr=None,trend_fraction=None):
        """
        Create graphs out of the RRD files
        """

        if len(relative_rrd_files)<1:
            return # nothing to be done

        for r in self.rrd_reports:
            pname,period,idx,freq=r
            title=relative_title+" - last "+pname
            if trend_fraction==None:
                abs_trend=None
            else:
                if pname=='hours':
                    continue # don't produce trend graphs for short periods, they are identical to std graphs
                abs_trend=period/trend_fraction

            pname_other_list=[]
            for other_r in self.rrd_reports:
                other_pname=other_r[0]
                if other_pname!=pname:
                    pname_other_list.append(other_pname)
            
            for g in self.graph_sizes:
                gname,width,height=g
                cmd_used=None

                gname_other_list=[]
                for other_g in self.graph_sizes:
                    other_gname=other_g[0]
                    if other_gname!=gname:
                        gname_other_list.append(other_gname)
            
                try:
                    cmd_used=self.rrd2graph(ref_time,base_lock_fname+".%s.rrd2graph_lock"%pname,
                                            base_fname+".%s.%s.png"%(pname,gname),
                                            idx,freq,
                                            period,width,height,title,relative_rrd_files,cdef_arr,abs_trend)
                except RuntimeError,e:
                    print "WARNING - graph %s.%s.%s creation failed: %s"%(base_fname,pname,gname,e)
                    
                if cmd_used!=None:
                    try:
                        self.createGraphHtml(pname,gname,
                                             pname_other_list,gname_other_list,
                                             base_fname,"_creation.html",parent,
                                             cmd_used)
                    except:
                        print "WARNING - Failed creating graph html"
        return

    def createGraphHtml(self,
                        pname,gname,
                        pname_other_list,gname_other_list,
                        base_fname,ext_str,parent,
                        rrd2graph_args):
        lck=self.get_graph_lock()
        try:
            self.createGraphHtml_Notlocked(pname,gname,
                                           pname_other_list,gname_other_list,
                                           base_fname,ext_str,parent,
                                           rrd2graph_args)
        finally:
            lck.close()
        return
        
    def createGraphHtml_Notlocked(self,
                                  pname,gname,
                                  pname_other_list,gname_other_list,
                                  base_fname,ext_str,parent,
                                  rrd2graph_args):
       long_fname=os.path.join(self.monitor_dir,base_fname)
       base_png_name=base_fname+".%s.%s.png"%(pname,gname)
       long_png_name=os.path.join(self.monitor_dir,base_png_name)
       html_name=long_png_name+ext_str

       base_dir,short_png_name=os.path.split(long_png_name)
       base_dir2=os.path.split(base_dir)[0]
       short_fname=os.path.split(long_fname)[1]

       printout_args=[]
       for arg in rrd2graph_args[1:]: # ignore the first one, was the fname
           if string.find(arg,base_dir)>=0:
               arg=string.replace(arg,base_dir+"/","")
           elif (base_dir2!="") and (string.find(arg,base_dir2)>=0):
               arg=string.replace(arg,base_dir2+"/","../")
           printout_args.append("'%s'"%arg)
       args_string=string.join(printout_args)

       gname_other_links=[]
       for g in gname_other_list:
           gname_other_links.append('<a href="%s.%s.%s.png%s">%s</a>'%(short_fname,pname,g,ext_str,g))
       pname_other_links=[]
       for p in pname_other_list:
           pname_other_links.append('<a href="%s.%s.%s.png%s">%s</a>'%(short_fname,p,gname,ext_str,p))
       
       fd=open(html_name,"w")
       try:
           fd.write("<html>\n<head><title>%s</title></head>\n"%short_png_name)
           fd.write("<body>\n")
           fd.write("<table border=0 width=100%><tr>\n")
           fd.write('<td align=left>[<a href="0%s.%s.%s.html">All %s</a>]</td>\n'%(parent,pname,gname,parent))
           fd.write("<td align=center>[%s]</td>\n"%string.join(gname_other_links,'|'))
           fd.write("<td align=right>[%s]</td>\n"%string.join(pname_other_links,'|'))
           fd.write("</tr></table>\n")
           fd.write('<img src="%s">\n<p>\n'%short_png_name)
           fd.write('Created with:\n</p>')
           fd.write('<p STYLE="margin-left: 1.0in; text-indent: -1.0in; font-family: monospace">\n')
           fd.write("rrdtool graph '%s' %s\n"%(short_png_name,args_string))
           fd.write("</p>\n")
           fd.write("</body>\n</html>\n")
       finally:
           fd.close()
       return
   

    def update_locks(self,ref_time,base_lock_fname):
        for r in self.rrd_reports:
            pname,period,idx,freq=r
            self.update_lock(ref_time,base_lock_fname+".%s.rrd2graph_lock"%pname,idx,freq)
        return


#########################################################################################################################################
#
#  condorQStats
#
#  This class handles the data obtained from condor_q
#
#########################################################################################################################################

class condorQStats:
    def __init__(self):
        self.data={}
        self.updated=time.time()

        self.files_updated=None
        self.attributes={'Status':("Idle","Running","Held","Wait","Pending","IdleOther"),
                         'Requested':("Idle","MaxRun"),
                         'ClientMonitor':("InfoAge","Idle","Running","GlideinsIdle","GlideinsRunning","GlideinsTotal")}


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

        status_pairs=((1,"Idle"), (2,"Running"), (5,"Held"), (1001,"Wait"),(1002,"Pending"),(1100,"IdleOther"))
        for p in status_pairs:
            nr,str=p
            if qc_status.has_key(nr):
                el[str]=qc_status[nr]
            else:
                el[str]=0
        self.updated=time.time()

    def logRequest(self,client_name,requests,params):
        """
        requests is a dictinary of requests
        params is a dictinary of parameters

        At the moment, it looks only for
          'IdleGlideins'
          'MaxRunningGlideins'
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
        if requests.has_key('MaxRunningGlideins'):
            el['MaxRun']=requests['MaxRunningGlideins']

        el['Parameters']=copy.deepcopy(params)

        self.updated=time.time()

    def logClientMonitor(self,client_name,client_monitor,client_internals):
        """
        client_monitor is a dictinary of monitoring info
        client_internals is a dictinary of internals

        At the moment, it looks only for
          'Idle'
          'Running'
          'GlideinsIdle'
          'GlideinsRunning'
          'GlideinsTotal'
          'LastHeardFrom'
        """
        if self.data.has_key(client_name):
            t_el=self.data[client_name]
        else:
            t_el={}
            self.data[client_name]=t_el

        el={}
        t_el['ClientMonitor']=el

        for k in ('Idle','Running','GlideinsIdle','GlideinsRunning','GlideinsTotal'):
            if client_monitor.has_key(k):
                el[k]=client_monitor[k]

        if client_internals.has_key('LastHeardFrom'):
            el['InfoAge']=int(time.time()-long(client_internals['LastHeardFrom']))
            el['InfoAgeAvgCounter']=1 # used for totals since we need an avg in totals, not absnum 

        self.updated=time.time()

    def get_data(self):
        data1=copy.deepcopy(self.data)
        for f in data1.keys():
            fe=data1[f]
            for w in fe.keys():
                el=fe[w]
                for a in el.keys():
                    if a[-10:]=='AvgCounter': # do not publish avgcounter fields... they are internals
                        del el[a]
            
        return data1

    def get_xml_data(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        data=self.get_data()
        return xmlFormat.dict2string(data,
                                     dict_name="frontends",el_name="frontend",
                                     subtypes_params={"class":{'subclass_params':{'Requested':{'dicts_params':{'Parameters':{'el_name':'Parameter'}}}}}},
                                     indent_tab=indent_tab,leading_tab=leading_tab)

    def get_total(self):
        total={'Status':None,'Requested':None,'ClientMonitor':None}

        for f in self.data.keys():
            fe=self.data[f]
            for w in fe.keys():
                if total.has_key(w): # ignore eventual not supported classes
                    el=fe[w]
                    tel=total[w]

                    if tel==None:
                        # first one, just copy over
                        total[w]={}
                        tel=total[w]
                        for a in el.keys():
                            if type(el[a])==type(1): # copy only numbers
                                tel[a]=el[a]
                    else:
                        # successive, sum 
                        for a in el.keys():
                            if type(el[a])==type(1): # consider only numbers
                                if tel.has_key(a):
                                    tel[a]+=el[a]
                            # if other frontends did't have this attribute, ignore
                        # if any attribute from prev. frontends are not in the current one, remove from total
                        for a in tel.keys():
                            if not el.has_key(a):
                                del tel[a]
                            elif type(el[a])!=type(1):
                                del tel[a]
        
        for w in total.keys():
            if total[w]==None:
                del total[w] # remove entry if not defined
            else:
                tel=total[w]
                for a in tel.keys():
                    if a[-10:]=='AvgCounter':
                        # this is an average counter, calc the average of the referred element
                        # like InfoAge=InfoAge/InfoAgeAvgCounter
                        aorg=a[:-10]
                        tel[aorg]=tel[aorg]/tel[a]
                        # the avgcount totals are just for internal purposes
                        del tel[a]

        return total
    
    def get_xml_total(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        total=self.get_total()
        return xmlFormat.class2string(total,
                                      inst_name="total",
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
                 '<glideFactoryEntryQStats>\n'+
                 self.get_xml_updated(indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
                 self.get_xml_data(indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
                 self.get_xml_total(indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
                 "</glideFactoryEntryQStats>\n")
        monitoringConfig.write_file("schedd_status.xml",xml_str)

        data=self.get_data()
        total_el=self.get_total()

        # update RRDs
        for fe in [None]+data.keys():
            if fe==None: # special key == Total
                fe_dir="total"
                fe_el=total_el
            else:
                fe_dir="frontend_"+fe
                fe_el=data[fe]

            monitoringConfig.establish_dir(fe_dir)
            for tp in fe_el.keys():
                # type - Status, Requested or ClientMonitor
                if not (tp in self.attributes.keys()):
                    continue

                attributes_tp=self.attributes[tp]
                val_dict_tp={}
                for a in attributes_tp:
                    val_dict_tp[a]=None #init, so that gets created properly
                
                fe_el_tp=fe_el[tp]
                for a in fe_el_tp.keys():
                    if a in attributes_tp:
                        a_el=fe_el_tp[a]
                        if type(a_el)!=type({}): # ignore subdictionaries
                            val_dict_tp[a]=a_el
                
                monitoringConfig.write_rrd_multi("%s/%s_Attributes"%(fe_dir,tp),
                                                 "GAUGE",self.updated,val_dict_tp)

        self.files_updated=self.updated        
        return
    
    def create_support_history(self):
        global monitoringConfig
        data=self.get_data()
        total_el=self.get_total()

        # use the same reference time for all the graphs
        graph_ref_time=time.time()
        # remember to call update_locks before exiting this function

        # create human readable files for each entry + total
        for fe in [None]+data.keys():
            if fe==None: # special key == Total
                fe="total"
                fe_dir="total"
                fe_el=total_el
            else:
                fe_dir="frontend_"+fe
                fe_el=data[fe]


            # create graphs for RRDs
            create_status_graphs(graph_ref_time,fe_dir,)
            
        # create support index files
        for fe in data.keys():
            fe_dir="frontend_"+fe
            create_leaf_status_indexes("Entry client %s@%s"%(fe,monitoringConfig.my_name),monitoringConfig.monitor_dir,fe_dir,
                                       "../total","Entry total")

        # get the list of frontends
        frontend_list=monitoringConfig.find_disk_frontends()
        if len(frontend_list)==0:
            monitoringConfig.update_locks(graph_ref_time,"status")
            return # nothing to do, wait for some frontends

        frontend_list.sort()

        # create human readable files for total aggregating multiple entries 
        if 'Split' in monitoringConfig.wanted_graphs:
            create_split_graphs(self.attributes,graph_ref_time,frontend_list,"frontend_%s")

        # create support index files for total
        create_group_status_indexes("Entry %s"%monitoringConfig.my_name,
                                    monitoringConfig.monitor_dir,"total",
                                    "../../total","Factory total",
                                    frontend_list,"../frontend_%s")

        monitoringConfig.update_locks(graph_ref_time,"status")
        return

#########################################################################################################################################
#
#  condorLogSummary
#
#  This class handles the data obtained from parsing the glidein log files
#
#########################################################################################################################################

class condorLogSummary:
    def __init__(self):
        self.data={} # not used
        self.updated=time.time()
        self.updated_year=time.localtime(self.updated)[0]
        self.current_stats_data={}     # will contain dictionary client->dirSummary.data
        self.stats_diff={}             # will contain the differences
        self.job_statuses=('Running','Idle','Wait','Held','Completed','Removed') #const
        self.job_statuses_short=('Running','Idle','Wait','Held') #const

        self.files_updated=None
        self.history_files_updated=None

    def reset(self):
        # reserve only those that has been around this time
        new_stats_data={}
        for c in self.stats_diff.keys():
            new_stats_data[c]=self.current_stats_data[c]

        self.current_stats_data=new_stats_data

        # and flush out the differences
        self.stats_diff={}

    def diffTimes(self,end_time,start_time):
        year=self.updated_year
        try:
            start_list=[year,int(start_time[0:2]),int(start_time[3:5]),int(start_time[6:8]),int(start_time[9:11]),int(start_time[12:14]),0,0,-1]
            end_list=[year,int(end_time[0:2]),int(end_time[3:5]),int(end_time[6:8]),int(end_time[9:11]),int(end_time[12:14]),0,0,-1]
        except ValueError:
            return -1 #invalid

        try:
            start_ctime=time.mktime(start_list)
            end_ctime=time.mktime(end_list)
        except TypeError:
            return -1 #invalid

        if start_ctime<=end_ctime:
            return end_ctime-start_ctime

        # else must have gone over the year boundary
        start_list[0]-=1 #decrease start year
        try:
            start_ctime=time.mktime(start_list)
        except TypeError:
            return -1 #invalid

        return end_ctime-start_ctime

        
    def logSummary(self,client_name,stats):
        """
         stats - glideFactoryLogParser.dirSummaryTimingsOut
        """
        if self.current_stats_data.has_key(client_name):
            self.stats_diff[client_name]=stats.diff(self.current_stats_data[client_name])
        else:
            self.stats_diff[client_name]=None # should only compare agains a known result
        
        self.current_stats_data[client_name]=stats.data
        self.updated=time.time()
        self.updated_year=time.localtime(self.updated)[0]

    def get_stats_data_summary(self):
        stats_data={}
        for client_name in self.current_stats_data.keys():
            client_el=self.current_stats_data[client_name]
            out_el={}
            for s in self.job_statuses:
                if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
                    if ((client_el!=None) and (s in client_el.keys())):
                        count=len(client_el[s])
                    else:
                        count=0
                    out_el[s]=count
            stats_data[client_name]=out_el
        return stats_data

    def get_xml_stats_data(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        data=self.get_stats_data_summary()
        return xmlFormat.dict2string(data,
                                     dict_name="frontends",el_name="frontend",
                                     subtypes_params={"class":{}},
                                     indent_tab=indent_tab,leading_tab=leading_tab)

    # in: entered_list=self.stats_diff[client_name]['Entered']
    # out: entered_list[job_id]{'duration','condor_started','jobsnr',wastemill':{'validation','idle','nosuccess','badput'}}
    def get_completed_stats(self,entered_list):
        out_list={}

        for enle in entered_list:
            enle_job_id=enle[0]
            enle_running_time=enle[2]
            enle_last_time=enle[3]
            enle_difftime=self.diffTimes(enle_last_time,enle_running_time)

            # get stats
            enle_stats=enle[4]
            enle_condor_started=0
            enle_glidein_duration=enle_difftime # best guess
            if enle_stats!=None:
                enle_condor_started=enle_stats['condor_started']
                if enle_stats.has_key('glidein_duration'):
                    enle_glidein_duration=enle_stats['glidein_duration']
            if not enle_condor_started:
                # 100% waste_mill
                enle_nr_jobs=0
                enle_jobs_duration=0
                enle_goodput=0
                enle_terminated_duration=0
                enle_waste_mill={'validation':1000,
                                 'idle':0,
                                 'nosuccess':0, #no jobs run, no failures
                                 'badput':1000}
            else:
                #get waste_mill
                enle_condor_duration=enle_stats['condor_duration']
                if enle_condor_duration==None:
                    enle_condor_duration=0 # assume failed

                if enle_condor_duration>enle_glidein_duration: # can happen... Condor-G has its delays
                    enle_glidein_duration=enle_condor_duration

                # get waste numbers, in permill
                if (enle_condor_duration<5): # very short means 100% loss
                    enle_nr_jobs=0
                    enle_jobs_duration=0
                    enle_goodput=0
                    enle_terminated_duration=0
                    enle_waste_mill={'validation':1000,
                                     'idle':0,
                                     'nosuccess':0, #no jobs run, no failures
                                     'badput':1000}
                else:
                    if enle_stats.has_key('validation_duration'):
                        enle_validation_duration=enle_stats['validation_duration']
                    else:
                        enle_validation_duration=enle_difftime-enle_condor_duration
                    enle_condor_stats=enle_stats['stats']
                    enle_jobs_duration=enle_condor_stats['Total']['secs']
                    enle_nr_jobs=enle_condor_stats['Total']['jobsnr']
                    enle_waste_mill={'validation':1000.0*enle_validation_duration/enle_glidein_duration,
                                     'idle':1000.0*(enle_condor_duration-enle_jobs_duration)/enle_condor_duration}
                    enle_goodput=enle_condor_stats['goodZ']['secs']
                    if enle_goodput>enle_jobs_duration:
                        enle_goodput=enle_jobs_duration # cannot be more
                    if enle_jobs_duration>0:
                        enle_waste_mill['nosuccess']=1000.0*(enle_jobs_duration-enle_goodput)/enle_jobs_duration
                    else:
                        enle_waste_mill['nosuccess']=0 #no jobs run, no failures
                    enle_terminated_duration=enle_goodput+enle_condor_stats['goodNZ']['secs']
                    if enle_terminated_duration>enle_jobs_duration:
                        enle_terminated_duration=enle_jobs_duration # cannot be more
                    enle_waste_mill['badput']=1000.0*(enle_glidein_duration-enle_terminated_duration)/enle_glidein_duration

            out_list[enle_job_id]={'duration':enle_glidein_duration,'condor_started':enle_condor_started,
                                   'jobsnr':enle_nr_jobs,'jobs_duration':{'total':enle_jobs_duration,'goodput':enle_goodput,'terminated':enle_terminated_duration},
                                   'wastemill':enle_waste_mill}
        
        return out_list

    # in: entered_list=get_completed_data()
    # out: {'Lasted':{'2hours':...,...},'Failed':...,'JobsNr':...,
    #       'Waste':{'validation':{'0m':...,...},...},'WasteTime':{...:{...},...}}
    def summarize_completed_stats(self,entered_list):
        # summarize completed data
        count_entered_times={}
        for enle_timerange in getAllTimeRanges(): 
            count_entered_times[enle_timerange]=0 # make sure all are initialized

        count_jobnrs={}
        for enle_jobrange in getAllJobRanges(): 
            count_jobnrs[enle_jobrange]=0 # make sure all are initialized

        count_jobs_duration={'total':{},
                             'goodput':{},
                             'terminated':{}}
        for w in count_jobs_duration.keys():
            count_jobs_duration_w=count_jobs_duration[w]
            for enle_jobs_duration_w_range in getAllTimeRanges():
                count_jobs_duration_w[enle_jobs_duration_w_range]=0 # make sure all are intialized

        count_validation_failed=0
        count_waste_mill={'validation':{},
                          'idle':{},
                          'nosuccess':{}, #i.e. everything but jobs terminating with 0
                          'badput':{}} #i.e. everything but jobs terminating
        for w in count_waste_mill.keys():
            count_waste_mill_w=count_waste_mill[w]
            for enle_waste_mill_w_range in getAllMillRanges():
                count_waste_mill_w[enle_waste_mill_w_range]=0 # make sure all are intialized
        time_waste_mill={'validation':{},
                          'idle':{},
                          'nosuccess':{}, #i.e. everything but jobs terminating with 0
                          'badput':{}} #i.e. everything but jobs terminating
        for w in time_waste_mill.keys():
            time_waste_mill_w=time_waste_mill[w]
            for enle_waste_mill_w_range in getAllMillRanges():
                time_waste_mill_w[enle_waste_mill_w_range]=0 # make sure all are intialized

        for enle_job in entered_list.keys():
            enle=entered_list[enle_job]
            enle_waste_mill=enle['wastemill']
            enle_glidein_duration=enle['duration']
            enle_jobs_nr=enle['jobsnr']
            enle_jobs_duration=enle['jobs_duration']
            enle_condor_started=enle['condor_started']

            if not enle_condor_started:
                count_validation_failed+=1

            # find and save time range
            enle_timerange=getTimeRange(enle_glidein_duration)
            count_entered_times[enle_timerange]+=1

            # find and save job range
            enle_jobrange=getJobRange(enle_jobs_nr)
            count_jobnrs[enle_jobrange]+=1

            for w in enle_jobs_duration.keys():
                enle_jobs_duration_w_range=getTimeRange(enle_jobs_duration[w])
                count_jobs_duration[w][enle_jobs_duration_w_range]+=1

            # find and save waste range
            for w in enle_waste_mill.keys():
                if w=="duration":
                    continue # not a waste
                # find and save time range
                enle_waste_mill_w_range=getMillRange(enle_waste_mill[w])

                count_waste_mill_w=count_waste_mill[w]
                count_waste_mill_w[enle_waste_mill_w_range]+=1

                time_waste_mill_w=time_waste_mill[w]
                time_waste_mill_w[enle_waste_mill_w_range]+=enle_glidein_duration
        
        
        return {'Lasted':count_entered_times,'JobsNr':count_jobnrs,'Failed':count_validation_failed,'JobsDuration':count_jobs_duration,'Waste':count_waste_mill,'WasteTime':time_waste_mill}

    def get_data_summary(self):
        stats_data={}
        for client_name in self.stats_diff.keys():
            stats_el=self.current_stats_data[client_name]
            diff_el=self.stats_diff[client_name]
            out_el={'Current':{},'Entered':{},'Exited':{}}
            for s in self.job_statuses:
                if ((diff_el!=None) and (s in diff_el.keys())):
                    entered_list=diff_el[s]['Entered']
                    entered=len(entered_list)
                    exited=-len(diff_el[s]['Exited'])
                else:
                    entered=0
                    entered_list=[]
                    exited=0
                out_el['Entered'][s]=entered
                if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
                    if ((stats_el!=None) and (s in stats_el.keys())):
                        count=len(stats_el[s])
                    else:
                        count=0
                    out_el['Current'][s]=count
                    # and we can never get out of the terminal state
                    out_el['Exited'][s]=exited
                elif s=='Completed':
                    completed_stats=self.get_completed_stats(entered_list)
                    completed_counts=self.summarize_completed_stats(completed_stats)
                    out_el['CompletedCounts']=completed_counts
            stats_data[client_name]=out_el
        return stats_data

    def get_xml_data(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        data=self.get_data_summary()
        return xmlFormat.dict2string(data,
                                     dict_name="frontends",el_name="frontend",
                                     subtypes_params={"class":{'subclass_params':{'CompletedCounts':get_completed_stats_xml_desc()}
                                                               }},
                                     indent_tab=indent_tab,leading_tab=leading_tab)

    def get_stats_total(self):
        total={'Wait':None,'Idle':None,'Running':None,'Held':None}
        for k in total.keys():
            tdata=[]
            for client_name in self.current_stats_data.keys():
                sdata=self.current_stats_data[client_name]
                if ((sdata!=None) and (k in sdata.keys())):
                    tdata=tdata+sdata[k]
            total[k]=tdata
        return total

    def get_stats_total_summary(self):
        in_total=self.get_stats_total()
        out_total={}
        for k in in_total.keys():
            out_total[k]=len(in_total[k])
        return out_total

    def get_xml_stats_total(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        total=self.get_stats_total_summary()
        return xmlFormat.class2string(total,
                                      inst_name="total",
                                      indent_tab=indent_tab,leading_tab=leading_tab)

    def get_diff_total(self):
        total={'Wait':None,'Idle':None,'Running':None,'Held':None,'Completed':None,'Removed':None}
        for k in total.keys():
            total[k]={'Entered':[],'Exited':[]}
            tdata=total[k]
            for client_name in self.stats_diff.keys():
                sdiff=self.stats_diff[client_name]
                if ((sdiff!=None) and (k in sdiff.keys())):
                    for e in tdata.keys():
                        tdata[e]=tdata[e]+sdiff[k][e]
        return total

    def get_total_summary(self):
        stats_total=self.get_stats_total()
        diff_total=self.get_diff_total()
        out_total={'Current':{},'Entered':{},'Exited':{}}
        for k in diff_total.keys():
            out_total['Entered'][k]=len(diff_total[k]['Entered'])
            if stats_total.has_key(k):
                out_total['Current'][k]=len(stats_total[k])
                # if no current, also exited does not have sense (terminal state)
                out_total['Exited'][k]=len(diff_total[k]['Exited'])
            elif k=='Completed':
                completed_stats=self.get_completed_stats(diff_total[k]['Entered'])
                completed_counts=self.summarize_completed_stats(completed_stats)
                out_total['CompletedCounts']=completed_counts

        return out_total

    def get_xml_total(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        total=self.get_total_summary()
        return xmlFormat.class2string(total,
                                      inst_name="total",
                                      subclass_params={'CompletedCounts':get_completed_stats_xml_desc()},
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
                 '<glideFactoryEntryLogSummary>\n'+
                 self.get_xml_updated(indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
                 self.get_xml_data(indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
                 self.get_xml_total(indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
                 "</glideFactoryEntryLogSummary>\n")
        monitoringConfig.write_file("log_summary.xml",xml_str)

        # update rrds
        stats_data_summary=self.get_stats_data_summary()
        stats_total_summary=self.get_stats_total_summary()
        for client_name in [None]+self.stats_diff.keys():
            if client_name==None:
                fe_dir="total"
                sdata=stats_total_summary
                sdiff=self.get_diff_total()
            else:
                fe_dir="frontend_"+client_name
                sdata=stats_data_summary[client_name]
                sdiff=self.stats_diff[client_name]

            monitoringConfig.establish_dir(fe_dir)
            val_dict_counts={}
            val_dict_entered={}
            val_dict_exited={}
            val_dict_completed={}
            val_dict_waste={}
            val_dict_wastetime={}
            for s in self.job_statuses:
                if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
                    count=sdata[s]
                    val_dict_counts[s]=count

                if ((sdiff!=None) and (s in sdiff.keys())):
                    entered_list=sdiff[s]['Entered']
                    entered=len(entered_list)
                    exited=-len(sdiff[s]['Exited'])
                else:
                    entered_list=[]
                    entered=0
                    exited=0
                    
                val_dict_entered[s]=entered
                if not (s in ('Completed','Removed')): # Always 0 for them
                    val_dict_exited[s]=exited
                elif s=='Completed':
                    completed_stats=self.get_completed_stats(entered_list)
                    if client_name!=None: # do not repeat for total
                        monitoringConfig.logCompleted(completed_stats)
                    completed_counts=self.summarize_completed_stats(completed_stats)

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

            #end for s in self.job_statuses

            # write the data to disk
            monitoringConfig.write_rrd_multi("%s/Log_Counts"%fe_dir,
                                             "GAUGE",self.updated,val_dict_counts)                            
            monitoringConfig.write_rrd_multi("%s/Log_Entered"%fe_dir,
                                             "ABSOLUTE",self.updated,val_dict_entered)
            monitoringConfig.write_rrd_multi("%s/Log_Exited"%fe_dir,
                                             "ABSOLUTE",self.updated,val_dict_exited)
            monitoringConfig.write_rrd_multi("%s/Log_Completed_Stats"%fe_dir,
                                             "ABSOLUTE",self.updated,val_dict_completed)
            monitoringConfig.write_rrd_multi("%s/Log_Completed_Waste"%fe_dir,
                                             "ABSOLUTE",self.updated,val_dict_waste)
            monitoringConfig.write_rrd_multi("%s/Log_Completed_WasteTime"%fe_dir,
                                             "ABSOLUTE",self.updated,val_dict_wastetime)


        self.files_updated=self.updated
        return
    
    def create_support_history(self):
        global monitoringConfig

        if (self.history_files_updated!=None) and ((self.files_updated-self.history_files_updated)<30):
            # history files updated recently, no need to redo it
            return 

        want_trend='Trend' in monitoringConfig.wanted_graphs

        # use the same reference time for all the graphs
        graph_ref_time=time.time()
        # remember to call update_locks before exiting this function

        # create graphs for RRDs
        for client_name in [None]+self.stats_diff.keys():
            if client_name==None:
                fe_dir="total"
            else:
                fe_dir="frontend_"+client_name
            create_log_graphs(graph_ref_time,"logsummary",fe_dir)
                                

        # Crate split graphs for total
        frontend_list=monitoringConfig.find_disk_frontends()
        create_log_split_graphs(graph_ref_time,"logsummary","frontend_%s",frontend_list)

        larr_long=['Log']
        larr_short=['Log']
        if want_trend:
            larr_long.append('Log50')

        larr_sl=(larr_short,larr_long)

        # create support index files
        for client_name in self.stats_diff.keys():
            fe_dir="frontend_"+client_name

            for rp in monitoringConfig.rrd_reports:
                period=rp[0]
                long_period=period!='hours'
                larr=larr_sl[long_period] # don't show trends for hours, they are identical to std graphs
                for sz in monitoringConfig.graph_sizes:
                    size=sz[0]
                    fname=os.path.join(monitoringConfig.monitor_dir,"%s/0Log.%s.%s.html"%(fe_dir,period,size))
                    #if (not os.path.isfile(fname)): #create only if it does not exist
                    if 1: # create every time, it is small and works over reconfigs
                        fd=open(fname,"w")
                        fd.write("<html>\n<head>\n")
                        fd.write("<title>Entry client %s@%s log stats over last %s</title>\n"%(client_name,monitoringConfig.my_name,period));
                        fd.write("</head>\n<body>\n")
                        fd.write('<table width="100%"><tr>\n')
                        fd.write('<td colspan=4 valign="top" align="left"><h1>Entry client %s@%s log stats over last %s</h1></td>\n'%(client_name,monitoringConfig.my_name,period))
                        
                        fd.write("</tr><tr>\n")
                        
                        fd.write('<td>[<a href="../total/0Log.%s.%s.html">Entry total</a>]</td>\n'%(period,size))
                        
                        link_arr=[]
                        for ref_sz in monitoringConfig.graph_sizes:
                            ref_size=ref_sz[0]
                            if size!=ref_size:
                                link_arr.append('<a href="0Log.%s.%s.html">%s</a>'%(period,ref_size,ref_size))
                        fd.write('<td align="center">[%s]</td>\n'%string.join(link_arr,' | '));

                        link_arr=[]
                        for ref_rp in monitoringConfig.rrd_reports:
                            ref_period=ref_rp[0]
                            if period!=ref_period:
                                link_arr.append('<a href="0Log.%s.%s.html">%s</a>'%(ref_period,size,ref_period))
                        fd.write('<td align="right">[%s]</td>\n'%string.join(link_arr,' | '));

                        fd.write('<td align="right">[<a href="0Status.%s.%s.html">Status</a> | <a href="0Terminated.%s.%s.html">Terminated</a>]</td>\n'%(period,size,period,size))
                        
                        fd.write("</tr></table>\n")
                        
                        fd.write("<p>\n<table>\n")
                        for s in self.job_statuses:
                            if (not (s in ('Completed','Removed'))): # special treatement
                                fd.write('<tr valign="top">')
                                fd.write('<td>%s</td>'%img2html("Log_%s_Count.%s.%s.png"%(s,period,size)))
                                fd.write('<td>%s</td>'%img2html("Log_%s_Diff.%s.%s.png"%(s,period,size)))
                                if want_trend and long_period:
                                    fd.write('<td>%s</td>'%img2html("Log50_%s_Diff.%s.%s.png"%(s,period,size)))
                                fd.write('</tr>\n')                            
                        fd.write('<tr valign="top">')
                        fd.write('<td></td>')
                        for l in larr:
                            fd.write('<td>%s</td>'%img2html("%s_Removed_Diff.%s.%s.png"%(l,period,size)))
                        fd.write('</tr>\n')
                        fd.write("</table>\n</p>\n")
                        fd.write("</p>\n")
                        fd.write("</body>\n</html>\n")
                        fd.close()
                        pass

                    fname=os.path.join(monitoringConfig.monitor_dir,"%s/0Terminated.%s.%s.html"%(fe_dir,period,size))
                    #if (not os.path.isfile(fname)): #create only if it does not exist
                    if 1: # create every time, it is small and works over reconfigs
                        fd=open(fname,"w")
                        fd.write("<html>\n<head>\n")
                        fd.write("<title>Entry client %s@%s terminated glideins over last %s</title>\n"%(client_name,monitoringConfig.my_name,period));
                        fd.write("</head>\n<body>\n")
                        fd.write('<table width="100%"><tr>\n')
                        fd.write('<td colspan=4 valign="top" align="left"><h1>Entry client %s@%s terminated glideins over last %s</h1></td>\n'%(client_name,monitoringConfig.my_name,period))
                        
                        fd.write("</tr><tr>\n")
                        
                        fd.write('<td>[<a href="../total/0Terminated.%s.%s.html">Entry total</a>]</td>\n'%(period,size))
                        
                        link_arr=[]
                        for ref_sz in monitoringConfig.graph_sizes:
                            ref_size=ref_sz[0]
                            if size!=ref_size:
                                link_arr.append('<a href="0Terminated.%s.%s.html">%s</a>'%(period,ref_size,ref_size))
                        fd.write('<td align="center">[%s]</td>\n'%string.join(link_arr,' | '));

                        link_arr=[]
                        for ref_rp in monitoringConfig.rrd_reports:
                            ref_period=ref_rp[0]
                            if period!=ref_period:
                                link_arr.append('<a href="0Terminated.%s.%s.html">%s</a>'%(ref_period,size,ref_period))
                        fd.write('<td align="right">[%s]</td>\n'%string.join(link_arr,' | '));

                        fd.write('<td align="right">[<a href="0Status.%s.%s.html">Status</a> | <a href="0Log.%s.%s.html">Log stats</a>]</td>\n'%(period,size,period,size))
                        
                        fd.write("</tr></table>\n")
                        
                        fd.write("<p><table>\n")
                        for sa in (('Diff','Entered_JobsNr'),('Entered_Lasted','Entered_JobsLasted'),('Entered_Goodput','Entered_Terminated')):
                            fd.write('<tr valign="top">')
                            for l in larr:
                                for s in sa:
                                    fd.write('<td>%s</td>'%img2html("%s_Completed_%s.%s.%s.png"%(l,s,period,size)))
                            fd.write('</tr>\n')
                        fd.write("</table>\n</p>\n")

                        fd.write("<h2>Statistics about wasted resources</h2>\n")
                        fd.write("<p><table>\n")
                        for s in ('validation','idle',
                                  'nosuccess','badput',):
                            fd.write('<tr valign="top">')
                            for l in larr:
                                for w in ('Waste','WasteTime'):
                                    fd.write('<td>%s</td>'%img2html("%s_Completed_Entered_%s_%s.%s.%s.png"%(l,w,s,period,size)))
                            fd.write('</tr>\n')
                        
                        fd.write("</table>\n</p>\n")

                        if (client_name==None) and ('Split' in monitoringConfig.wanted_graphs):
                            # total has also the split graphs
                            fd.write("<p><hr><p><table>")
                            for s in self.job_statuses:
                                if (not (s in ('Completed','Removed'))): # special treatement
                                    fd.write('<tr valign="top">')
                                    for w in ['Count','Diff']:
                                        fd.write('<td>%s</td>'%img2html("Split_Log_%s_%s.%s.%s.png"%(s,w,period,size)))
                                    if s=='Running':
                                        fd.write('<td>%s</td>'%img2html("Split_Log_%s_%s.%s.%s.png"%('Completed','Diff',period,size)))
                                    elif s=='Held':
                                        fd.write('<td>%s</td>'%img2html("Split_Log_%s_%s.%s.%s.png"%('Removed','Diff',period,size)))
                                    fd.write('</tr>\n')                            
                            fd.write("</table>")
                            

                        fd.write("<p>\n<table><tr valign='top'>\n")
                        fd.write("<td>\n")
                        fd.write("Legenda of wasted:\n<ul>\n")
                        fd.write(" <li>Validation - Time spent before starting Condor\n")
                        fd.write(" <li>Idle - Time spent by Condor in idle state\n")
                        fd.write(" <li>Nosuccess - Time spent by user jobs that did not return with error code 0 \n")
                        fd.write(" <li>Badput - Time spent by the glidein not running user jobs\n")
                        fd.write("</ul></td>\n")
                        fd.write("<td>\n")
                        fd.write("Scale:\n<ul>\n")
                        fd.write(" <li>Completed - Number of jobs completed per second \n")
                        fd.write(" <li>Lasted - Number of jobs of certain size per second \n")
                        fd.write(" <li>Waste - Number of jobs in that state per second \n")
                        fd.write(" <li>WasteTime - Waste * glidein length \n")
                        fd.write("</ul></td>\n")
                        fd.write("</tr></table>\n")
                        fd.write("</p>\n")
                        fd.write("</body>\n</html>\n")
                        fd.close()
                        pass
                    pass # for sz
                pass # for rp
            pass # for client_name

        # create support index file for total
        create_log_total_index("Entry %s"%monitoringConfig.my_name,"frontend","../frontend_%s",frontend_list,('../../total','Factory total'))

        monitoringConfig.update_locks(graph_ref_time,"logsummary")
        self.history_files_updated=self.files_updated
        return

############### P R I V A T E ################

def getUnitVal(u):
    if u=="Unknown":
        return 0
    if u=="TooShort":
        return 1
    if u=="m":
        return 2
    if u=="mins":
        return 3
    if u=="hours":
        return 4
    if u=="TooLong":
        return 5
    return 100 # just for protection

# compare (nr,unit) pairs
def cmpPairs(e1,e2):
    # first compare units
    u1=getUnitVal(e1[1])
    u2=getUnitVal(e2[1])
    ucmp=cmp(u1,u2)
    if ucmp!=0:
        return ucmp

    # units equal, compare numbers
    try:
        n1=int(e1[0])
    except:
        n1=10000
    try:
        n2=int(e2[0])
    except:
        n2=10000
    return cmp(n1,n2)

##################################################
def getTimeRange(absval):
        if absval<1:
            return 'Unknown'
        if absval<240:
            return 'TooShort'
        if absval>(180*3600): # limit valid times to 180 hours
            return 'TooLong'
        # start with 7.5 min, and than exp2
        logval=int(math.log(absval/450.0,2)+0.49)
        level=math.pow(2,logval)*450.0
        if level<3600:
            return "%imins"%(int(level/60+0.49))
        else:
            return "%ihours"%(int(level/3600+0.49))

def getAllTimeRanges():
        return ('Unknown','TooShort','7mins','15mins','30mins','1hours','2hours','4hours','8hours','16hours','32hours','64hours','128hours','TooLong')
    
def getJobRange(absval):
        if absval<1:
            return 'None'
        if absval==1:
            return '1job'
        if absval>45: # limit valid times to 45
            return 'Many'
        logval=int(math.log(absval,2)+0.49)
        level=int(math.pow(2,logval))
        return "%ijobs"%level

def getAllJobRanges():
        return ('None','1job','2jobs','4jobs','8jobs','16jobs','32jobs','Many')
    
def getAllTimeRangeGroups():
        return {'Unknown':('Unknown',),'lt15mins':('TooShort','7mins'),'15mins-50mins':('15mins','30mins'),'50mins-30hours':('1hours','2hours','4hours','8hours','16hours'),'30hours-100hours':('32hours','64hours'),'gt100hours':('128hours','TooLong')}
            
def getMillRange(absval):
        if absval<0.5:
            return '0m'
        # make sure 1000 gets back to 1000
        logval=int(math.log(absval*1.024,2)+0.49)
        level=int(math.pow(2,logval)/1.024)
        return "%im"%level

def getAllMillRanges():
        return ('0m','1m','3m','7m','15m','31m','62m','125m','250m','500m','1000m')            

def getAllMillRangeGroups():
        return {'lt100m':('0m','1m','3m','7m','15m','31m','62m'),'100m-400m':('125m','250m'),'gt400m':('500m','1000m')}            

def getGroupsVal(u):
    if u=="Unknown":
        return 0
    if u[0:1]=="l":
        return 1
    if u[0:1]=="g":
        return 1000
    if u[2:3]=='h':
        return int(u[0:1])+100
    else:
        return int(u[0:1])+10

##################################################
def get_completed_stats_xml_desc():
    return {'dicts_params':{'Lasted':{'el_name':'TimeRange'},
                            'JobsNr':{'el_name':'Range'}},
            'subclass_params':{'JobsDuration':{'dicts_params':{'total':{'el_name':'TimeRange'},
                                                               'goodput':{'el_name':'TimeRange'},
                                                               'terminated':{'el_name':'TimeRange'}}},
                               'Waste':{'dicts_params':{'idle':{'el_name':'Fraction'},
                                                        'validation':{'el_name':'Fraction'},
                                                        'badput':{'el_name':'Fraction'},
                                                        'nosuccess':{'el_name':'Fraction'}}},
                               'WasteTime':{'dicts_params':{'idle':{'el_name':'Fraction'},
                                                            'validation':{'el_name':'Fraction'},
                                                            'badput':{'el_name':'Fraction'},
                                                            'nosuccess':{'el_name':'Fraction'}}}
                               }
            }

##################################################
def create_status_graphs(graph_ref_time,fe_dir):
    want_held='Held' in monitoringConfig.wanted_graphs
    want_infoage='InfoAge' in monitoringConfig.wanted_graphs

    monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                "%s/Idle"%fe_dir,
                                "Idle glideins",
                                [("Requested","%s/Requested_Attributes.rrd?id=Idle"%fe_dir,"AREA","00FFFF"),
                                 ("Idle","%s/Status_Attributes.rrd?id=Idle"%fe_dir,"LINE2","0000FF"),
                                 ("Wait","%s/Status_Attributes.rrd?id=Wait"%fe_dir,"LINE2","FF00FF"),
                                 ("Pending","%s/Status_Attributes.rrd?id=Pending"%fe_dir,"LINE2","00FF00"),
                                 ("IdleOther","%s/Status_Attributes.rrd?id=IdleOther"%fe_dir,"LINE2","FF0000")])
    monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                "%s/Running"%fe_dir,
                                "Running glideins",
                                [("Running","%s/Status_Attributes.rrd?id=Running"%fe_dir,"AREA","00FF00"),
                                 ("ClientGlideins","%s/ClientMonitor_Attributes.rrd?id=GlideinsTotal"%fe_dir,"LINE2","000000"),
                                 ("ClientRunning","%s/ClientMonitor_Attributes.rrd?id=GlideinsRunning"%fe_dir,"LINE2","0000FF")])
    monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                "%s/MaxRun"%fe_dir,
                                "Max running glideins requested",
                                [("MaxRun","%s/Requested_Attributes.rrd?id=MaxRun"%fe_dir,"AREA","008000")])
    if want_held:
        monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                    "%s/Held"%fe_dir,
                                    "Held glideins",
                                    [("Held","%s/Status_Attributes.rrd?id=Held"%fe_dir,"AREA","c00000")])
    monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                "%s/ClientIdle"%fe_dir,
                                "Idle client jobs",
                                [("Idle","%s/ClientMonitor_Attributes.rrd?id=Idle"%fe_dir,"AREA","00FFFF"),
                                 ("Requested","%s/Requested_Attributes.rrd?id=Idle"%fe_dir,"LINE2","0000FF")])
    monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                "%s/ClientRunning"%fe_dir,
                                "Running client jobs",
                                [("Running","%s/ClientMonitor_Attributes.rrd?id=Running"%fe_dir,"AREA","00FF00")])
    if want_infoage:
        monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                    "%s/InfoAge"%fe_dir,
                                    "Client info age",
                                    [("InfoAge","%s/ClientMonitor_Attributes.rrd?id=InfoAge"%fe_dir,"LINE2","000000")])
    return

##################################################
def create_leaf_status_indexes(title_name,
                               base_dir,sub_dir,
                               parent_dir,parent_name):
    want_held='Held' in monitoringConfig.wanted_graphs
    want_infoage='InfoAge' in monitoringConfig.wanted_graphs

    glidein_graphs=['Running','Idle']
    if want_held:
        glidein_graphs.append('Held')
    frontend_graphs=['ClientIdle','ClientRunning']
    if want_infoage:
        frontend_graphs.append('InfoAge')


    for rp in monitoringConfig.rrd_reports:
                period=rp[0]
                for sz in monitoringConfig.graph_sizes:
                    size=sz[0]
                    fname=os.path.join(base_dir,"%s/0Status.%s.%s.html"%(sub_dir,period,size))
                    #if (not os.path.isfile(fname)): #create only if it does not exist
                    if 1: # create every time, it is small and works over reconfigs 
                        fd=open(fname,"w")
                        fd.write("<html>\n<head>\n")
                        fd.write("<title>%s status over last %s</title>\n"%(title_name,period));
                        fd.write("</head>\n<body>\n")
                        fd.write('<table width="100%"><tr>\n')
                        fd.write('<td colspan=4 valign="top" align="left"><h1>%s status over last %s</h1></td>\n'%(title_name,period))
                        

                        fd.write("</tr><tr>\n")
                        
                        if (parent_dir!=None) and (parent_name!=None):
                            fd.write('<td>[<a href="%s/0Status.%s.%s.html">%s</a>]</td>\n'%(parent_dir,period,size,parent_name))
                        
                        link_arr=[]
                        for ref_sz in monitoringConfig.graph_sizes:
                            ref_size=ref_sz[0]
                            if size!=ref_size:
                                link_arr.append('<a href="0Status.%s.%s.html">%s</a>'%(period,ref_size,ref_size))
                        fd.write('<td align="center">[%s]</td>\n'%string.join(link_arr,' | '));

                        link_arr=[]
                        for ref_rp in monitoringConfig.rrd_reports:
                            ref_period=ref_rp[0]
                            if period!=ref_period:
                                link_arr.append('<a href="0Status.%s.%s.html">%s</a>'%(ref_period,size,ref_period))
                        fd.write('<td align="center">[%s]</td>\n'%string.join(link_arr,' | '));

                        fd.write('<td align="right">[<a href="0Log.%s.%s.html">Log stats</a> | <a href="0Terminated.%s.%s.html">Terminated</a>]</td>\n'%(period,size,period,size))
                        
                        fd.write("</tr></table>\n")

                        fd.write('<a name="glidein_stats">\n')
                        fd.write("<h2>Glidein stats</h2>\n")
                        fd.write("<table>")
                        for s in glidein_graphs:
                            fd.write('<tr valign="top">')
                            fd.write('<td>%s</td>'%img2html("%s.%s.%s.png"%(s,period,size)))
                            if s=='Running':
                                s1='MaxRun'
                                fd.write('<td>%s</td>'%img2html("%s.%s.%s.png"%(s1,period,size)))
                            fd.write('</tr>\n')                            
                        fd.write("</table>")
                        fd.write('<a name="client_stats">\n')
                        fd.write("<h2>Frontend (client) stats</h2>\n")
                        fd.write("<table>")
                        for s in frontend_graphs:
                            fd.write('<tr valign="top">')
                            fd.write('<td>%s</td>'%img2html("%s.%s.%s.png"%(s,period,size)))
                            fd.write('</tr>\n')                            
                        fd.write("</table>")
                        fd.write("</body>\n</html>\n")
                        fd.close()
                        pass
    return


##################################################
def create_group_status_indexes(title_name,
                                base_dir,sub_dir,
                                parent_dir,parent_name, # can be None
                                elements,element_format):
    want_split='Split' in monitoringConfig.wanted_graphs
    want_held='Held' in monitoringConfig.wanted_graphs
    want_infoage='InfoAge' in monitoringConfig.wanted_graphs

    for rp in monitoringConfig.rrd_reports:
            period=rp[0]
            for sz in monitoringConfig.graph_sizes:
                size=sz[0]
                fname=os.path.join(base_dir,"%s/0Status.%s.%s.html"%(sub_dir,period,size))
                #if (not os.path.isfile(fname)): #create only if it does not exist
                if 1: # create every time, it is small and works over reconfigs
                    fd=open(fname,"w")
                    fd.write("<html>\n<head>\n")
                    fd.write("<title>%s status over last %s</title>\n"%(title_name,period));
                    fd.write("</head>\n<body>\n")
                    fd.write('<table width="100%"><tr>\n')
                    fd.write('<td valign="top" align="left"><h1>%s status over last %s</h1></td>\n'%(title_name,period))

                    link_arr=[]
                    for ref_sz in monitoringConfig.graph_sizes:
                        ref_size=ref_sz[0]
                        if size!=ref_size:
                            link_arr.append('<a href="0Status.%s.%s.html">%s</a>'%(period,ref_size,ref_size))
                    fd.write('<td align="center">[%s]</td>\n'%string.join(link_arr,' | '));

                    link_arr=[]
                    for ref_rp in monitoringConfig.rrd_reports:
                        ref_period=ref_rp[0]
                        if period!=ref_period:
                            link_arr.append('<a href="0Status.%s.%s.html">%s</a>'%(ref_period,size,ref_period))
                    fd.write('<td align="right">[%s]</td>\n'%string.join(link_arr,' | '));

                    fd.write('<td align="right">[<a href="0Log.%s.%s.html">Log stats</a> | <a href="0Terminated.%s.%s.html">Terminated</a>]</td>\n'%(period,size,period,size))
                        
                    fd.write("</tr><tr>\n")

                    if (parent_dir!=None) and (parent_name!=None):
                        fd.write('<td>[<a href="%s/0Status.%s.%s.html">%s</a>]</td>\n'%(parent_dir,period,size,parent_name))
                    link_arr=[]
                    for ref_fe in elements:
                        link_arr.append(('<a href="')+(element_format%ref_fe)+('/0Status.%s.%s.html">%s</a>'%(period,size,ref_fe)))
                    fd.write('<td colspan=3 align="right">[%s]</td>\n'%string.join(link_arr,' | '));

                    fd.write("</tr></table>\n")

                    fd.write('<a name="glidein_stats">\n')
                    fd.write("<h2>Glidein stats</h2>\n")
                    fd.write("<table>")
                    larr=[]
                    if want_split:
                        larr.append(('Running','Split_Status_Attribute_Running','Split_Requested_Attribute_MaxRun'))
                        larr.append(('Idle','Split_Status_Attribute_Idle','Split_Requested_Attribute_Idle'))
                        larr.append(('Split_Status_Attribute_Wait','Split_Status_Attribute_Pending','Split_Status_Attribute_IdleOther'))
                    else:
                        larr.append(('Running',))
                        larr.append(('Idle',))

                    if want_held:
                        if want_split:
                            larr.append(('Held','Split_Status_Attribute_Held'))
                        else:
                            larr.append(('Held',))
                    for l in larr:
                        fd.write('<tr valign="top">')
                        for s in l:
                            fd.write('<td>%s</td>'%img2html("%s.%s.%s.png"%(s,period,size)))
                        fd.write('</tr>\n')
                    fd.write("</table>")
                    fd.write('<a name="client_stats">\n')
                    fd.write("<h2>Frontend (client) stats</h2>\n")
                    fd.write("<table>")
                    larr=[]
                    if want_split:
                        larr.append(('ClientIdle','Split_ClientMonitor_Attribute_Idle'))
                        larr.append(('ClientRunning','Split_ClientMonitor_Attribute_Running'))
                    else:
                        larr.append(('ClientIdle',))
                        larr.append(('ClientRunning',))

                    if want_infoage:
                        if want_split:
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
    return


##################################################
def create_split_graphs(attributes,graph_ref_time,
                        elements,element_format):
    colors_base=[(0,1,0),(0,1,1),(1,1,0),(1,0,1),(0,0,1),(1,0,0)]
    colors_intensity=['ff','d0','a0','80','e8','b8']
    colors=[]
    for ci_i in colors_intensity:
        si_arr=['00',ci_i]
        for cb_i in colors_base:
            colors.append('%s%s%s'%(si_arr[cb_i[0]],si_arr[cb_i[1]],si_arr[cb_i[2]]))

    for tp in attributes.keys():
        # type - Status, Requested or ClientMonitor
        attributes_tp=attributes[tp]
                  
        for a in attributes_tp:
            # attribute - Idle, Running, ....
            rrd_fnames=[]
            idx=0
            for el in elements:
                area_name="STACK"
                if idx==0:
                    area_name="AREA"
                rrd_fnames.append((cleanup_rrd_name(el),(element_format%el)+("/%s_Attributes.rrd?id=%s"%(tp,a)),area_name,colors[idx%len(colors)]))
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

            try:
                monitoringConfig.graph_rrds(graph_ref_time,"status","Status",
                                            "total/Split_%s_Attribute_%s"%(tp,a),
                                            tstr,
                                            rrd_fnames)
            except:
                # just a warning
                print "Failed creating total/Split_%s_Attribute_%s"%(tp,a)
    
    return

##################################################
def create_log_graphs(ref_time,base_lock_name,fe_dir):
    want_trend='Trend' in monitoringConfig.wanted_graphs

    colors={"Wait":"00FFFF","Idle":"0000FF","Running":"00FF00","Held":"c00000"}
    r_colors=('c00000','ff4000', #>250
              'ffc000','fff800', #100-250
              'd8ff00','b0ff00','90ff00','60ff00','30ff00','00ff00','00c000') #<100
    r_colors_len=len(r_colors)
    time_colors=('000000','0c0000', # unknown and too short
                 'ff0000','ffc000', # 7 and 15 mins
                 'ffff00',          # 30 mins
                 'c0ff00','80f000','40d800','00c000','00c080','00e0d0','00ffff',
                 '0080f0','0000c0')          # 128hours, TooLong
    jobs_colors=('ff0000','d8ff00',           # 0 and 1
                 '00ff00','00c000',           # 2 and 4
                 '00e080','00ffd8','0080ff',  # 8,16,32
                 '0040a0')                    # Many
    
    for s in ('Wait','Idle','Running','Held','Completed','Removed'):
        rrd_files=[('Entered',"%s/Log_Entered.rrd?id=%s"%(fe_dir,s),"AREA","00ff00")]
        if not (s in ('Completed','Removed')): # always 0 for them
            rrd_files.append(('Exited',"%s/Log_Exited.rrd?id=%s"%(fe_dir,s),"AREA","ff0000"))

        monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                    "%s/Log_%s_Diff"%(fe_dir,s),
                                    "Difference in %s glideins"%s, rrd_files)
        if want_trend:
            monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                        "%s/Log50_%s_Diff"%(fe_dir,s),
                                        "Trend Difference in %s glideins"%s, rrd_files,trend_fraction=50)

        if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
            monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                        "%s/Log_%s_Count"%(fe_dir,s),
                                        "%s glideins"%s,
                                        [(s,"%s/Log_Counts.rrd?id=%s"%(fe_dir,s),"AREA",colors[s])])
        elif s=="Completed":
            # create graph for time based info
            t_keys=getAllTimeRanges()

            for t in ('Lasted',):
                t_rrds=[]
                idx=0
                for t_k in t_keys:
                    t_k_color=time_colors[idx]
                    t_rrds.append((str(t_k),"%s/Log_Completed_Stats.rrd?id=%s_%s"%(fe_dir,t,t_k),"STACK",t_k_color))
                    idx+=1
                    
                monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                            "%s/Log_Completed_Entered_%s"%(fe_dir,t),
                                            "%s glideins"%t,t_rrds)
                if want_trend:
                    monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                                "%s/Log50_Completed_Entered_%s"%(fe_dir,t),
                                                "Trend %s glideins"%t,t_rrds,trend_fraction=50)
            
            for t in ('JobsLasted','Goodput','Terminated'):
                t_rrds=[]
                idx=0
                for t_k in t_keys:
                    t_k_color=time_colors[idx]
                    t_rrds.append((str(t_k),"%s/Log_Completed_Stats.rrd?id=%s_%s"%(fe_dir,t,t_k),"STACK",t_k_color))
                    idx+=1
                    
                monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                            "%s/Log_Completed_Entered_%s"%(fe_dir,t),
                                            "%s jobs in glideins"%t,t_rrds)
                if want_trend:
                    monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                                "%s/Log50_Completed_Entered_%s"%(fe_dir,t),
                                                "Trend %s jobs in glideins"%t,t_rrds,trend_fraction=50)
            
            # create graph for jobs
            t_keys=getAllJobRanges()

            for t in ('JobsNr',):
                t_rrds=[]
                idx=0
                for t_k in t_keys:
                    t_k_color=jobs_colors[idx]
                    t_rrds.append((str(t_k),"%s/Log_Completed_Stats.rrd?id=%s_%s"%(fe_dir,t,t_k),"STACK",t_k_color))
                    idx+=1
                    
                monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                            "%s/Log_Completed_Entered_%s"%(fe_dir,t),
                                            "%s per glidein"%t,t_rrds)
                if want_trend:
                    monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                                "%s/Log50_Completed_Entered_%s"%(fe_dir,t),
                                                "Trend %s per glidein"%t,t_rrds,trend_fraction=50)

            # create graphs for Waste and WasteTime
            for t in ('Waste','WasteTime'):
                t_keys=list(getAllMillRanges())
                t_keys.reverse()
                t_keys_len=len(t_keys)

                for t_t in ('badput','idle','nosuccess','validation'):
                    t_rrds=[]
                    idx=0
                    for t_k in t_keys:
                        t_k_color=r_colors[int(1.*(r_colors_len-1)*idx/(t_keys_len-1)+0.49)]
                        t_rrds.append((str(t_k),"%s/Log_Completed_%s.rrd?id=%s_%s"%(fe_dir,t,t_t,t_k),"STACK",t_k_color))
                        idx+=1

                    monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                                "%s/Log_Completed_Entered_%s_%s"%(fe_dir,t,t_t),
                                                "%s %s glideins"%(t,t_t),t_rrds)
                    if want_trend:
                        monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                                    "%s/Log50_Completed_Entered_%s_%s"%(fe_dir,t,t_t),
                                                    "Trend %s %s glideins"%(t,t_t),t_rrds,trend_fraction=50)
                
###################################

def create_log_split_graphs(ref_time,base_lock_name,subdir_template,subdir_list):
    if len(subdir_list)==0:
        return # nothing more to do, wait for some subdirs

    if not ('Split' in monitoringConfig.wanted_graphs):
        return # do not create split graphs

    subdir_list.sort()

    want_trend='Trend' in monitoringConfig.wanted_graphs

    mill_range_groups=getAllMillRangeGroups()
    mill_range_groups_keys=mill_range_groups.keys()
    mill_range_groups_keys.sort(lambda e1,e2:cmp(getGroupsVal(e1),getGroupsVal(e2)))
    
    time_range_groups=getAllTimeRangeGroups()
    time_range_groups_keys=time_range_groups.keys()
    time_range_groups_keys.sort(lambda e1,e2:cmp(getGroupsVal(e1),getGroupsVal(e2)))
    
    colors_intensity=['ff','d0','a0','80','e8','b8']
    dimcolors_intensity=['c0','a0','80','60','b0','90']

    colors_base=[(0,1,0),(0,1,1),(1,1,0),(1,0,1),(0,0,1),(1,0,0)]
    colors=[]
    for ci_i in colors_intensity:
        si_arr=['00',ci_i]
        for cb_i in colors_base:
            colors.append('%s%s%s'%(si_arr[cb_i[0]],si_arr[cb_i[1]],si_arr[cb_i[2]]))

    in_colors_base=[(0,1,0),(0,1,1),(0,2,0),(0,0,2),(0,1,2),(0,0,1)]
    in_colors=[]
    for ci_i in range(len(colors_intensity)):
        si_arr=['00',colors_intensity[ci_i],dimcolors_intensity[ci_i]]
        for cb_i in in_colors_base:
            in_colors.append('%s%s%s'%(si_arr[cb_i[0]],si_arr[cb_i[1]],si_arr[cb_i[2]]))

    out_colors_base=[(1,0,0),(1,1,0),(2,0,0),(1,0,1),(1,2,0),(1,2,2)]
    out_colors=[]
    for ci_i in range(len(colors_intensity)):
        si_arr=['00',colors_intensity[ci_i],dimcolors_intensity[ci_i]]
        for cb_i in out_colors_base:
            out_colors.append('%s%s%s'%(si_arr[cb_i[0]],si_arr[cb_i[1]],si_arr[cb_i[2]]))

    for s in ('Running','Idle','Wait','Held','Completed','Removed'):
            diff_rrd_files=[]
            count_rrd_files=[]

            idx=0
            for fe in subdir_list:
                fe_dir=subdir_template%fe
                diff_rrd_files.append(['Entered_%s'%cleanup_rrd_name(fe),"%s/Log_Entered.rrd?id=%s"%(fe_dir,s),"STACK",in_colors[idx%len(in_colors)]])
                idx=idx+1

            if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
                idx=0
                area_or_stack='AREA' # first must be area for exited
                for fe in subdir_list:
                    fe_dir=subdir_template%fe
                    diff_rrd_files.append(['Exited_%s'%cleanup_rrd_name(fe),"%s/Log_Exited.rrd?id=%s"%(fe_dir,s),area_or_stack,out_colors[idx%len(out_colors)]])
                    area_or_stack='STACK'
                    count_rrd_files.append([cleanup_rrd_name(fe),"%s/Log_Counts.rrd?id=%s"%(fe_dir,s),"STACK",colors[idx%len(colors)]])
                    idx=idx+1
                monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                            "total/Split_Log_%s_Count"%s,
                                            "%s glideins"%s,count_rrd_files)
           
            monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                        "total/Split_Log_%s_Diff"%s,
                                        "Difference in %s glideins"%s, diff_rrd_files)
            if want_trend:
                monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                            "total/Split_Log50_%s_Diff"%s,
                                            "Trend Difference in %s glideins"%s, diff_rrd_files,trend_fraction=50)

    if 'SplitTerm' in monitoringConfig.wanted_graphs:
        # create the completed split graphs
        range_groups=time_range_groups
        range_groups_keys=time_range_groups_keys
        for range_group in range_groups_keys:
            range_list=range_groups[range_group]
            diff_rrd_files=[]
            cdef_arr=[]
            idx=0
            for fe in subdir_list:
                fe_dir=subdir_template%fe
                cdef_formula="0"
                for range_val in range_list:
                    ds_id='%s_%s'%(cleanup_rrd_name(fe),range_val)
                    diff_rrd_files.append([ds_id,"%s/Log_Completed_Stats.rrd?id=Lasted_%s"%(fe_dir,range_val),"STACK","000000"]) # colors not used
                    cdef_formula=cdef_formula+(",%s,+"%ds_id)
                cdef_arr.append([cleanup_rrd_name(fe),cdef_formula,"STACK",colors[idx%len(colors)]])
                idx+=1

            monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                        "total/Split_Log_Completed_Entered_Lasted_%s"%range_group,
                                        "Lasted %s glideins"%range_group, diff_rrd_files,cdef_arr=cdef_arr)
            if want_trend:
                monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                            "total/Split_Log50_Completed_Entered_Lasted_%s"%range_group,
                                            "Trend Lasted %s glideins"%range_group, diff_rrd_files,cdef_arr=cdef_arr,trend_fraction=50)
        

        # repeat for waste
        range_groups=mill_range_groups
        range_groups_keys=mill_range_groups_keys
        for t in ('Waste','WasteTime'):
            for t_t in ('badput','idle','nosuccess','validation'):
                for range_group in range_groups_keys:
                    range_list=range_groups[range_group]
                    diff_rrd_files=[]
                    cdef_arr=[]
                    idx=0
                    for fe in subdir_list:
                        fe_dir=subdir_template%fe
                        cdef_formula="0"
                        for range_val in range_list:
                            ds_id='%s_%s'%(cleanup_rrd_name(fe),range_val)
                            diff_rrd_files.append([ds_id,"%s/Log_Completed_%s.rrd?id=%s_%s"%(fe_dir,t,t_t,range_val),"STACK","000000"]) # colors not used
                            cdef_formula=cdef_formula+(",%s,+"%ds_id)
                        cdef_arr.append([cleanup_rrd_name(fe),cdef_formula,"STACK",colors[idx%len(colors)]])
                        idx+=1

                    monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                                "total/Split_Log_Completed_Entered_%s_%s_%s"%(t,t_t,range_group),
                                                "%s %s %s glideins"%(t,t_t,range_group), diff_rrd_files,cdef_arr=cdef_arr)
                    if want_trend:
                        monitoringConfig.graph_rrds(ref_time,base_lock_name,"Log",
                                                    "total/Split_Log50_Completed_Entered_%s_%s_%s"%(t,t_t,range_group),
                                                    "Trend %s %s %s glideins"%(t,t_t,range_group), diff_rrd_files,cdef_arr=cdef_arr,trend_fraction=50)



###################################

def create_log_total_index(title,subdir_label,subdir_template,subdir_list,up_dir_and_title):
    lck=monitoringConfig.get_graph_lock()
    try:
        create_log_total_index_notlocked(title,subdir_label,subdir_template,subdir_list,up_dir_and_title)
    finally:
        lck.close()
    return


def create_log_total_index_notlocked(title,subdir_label,subdir_template,subdir_list,up_dir_and_title):
    subdir_list.sort()

    want_trend='Trend' in monitoringConfig.wanted_graphs
    
    mill_range_groups=getAllMillRangeGroups()
    mill_range_groups_keys=mill_range_groups.keys()
    mill_range_groups_keys.sort(lambda e1,e2:cmp(getGroupsVal(e1),getGroupsVal(e2)))
    
    time_range_groups=getAllTimeRangeGroups()
    time_range_groups_keys=time_range_groups.keys()
    time_range_groups_keys.sort(lambda e1,e2:cmp(getGroupsVal(e1),getGroupsVal(e2)))
    
    parr=['']
    if 'Split' in monitoringConfig.wanted_graphs:
        parr.append('Split_')

    larr_long=['Log']
    larr_short=['Log']
    if want_trend:
        larr_long.append('Log50')

    larr_sl=(larr_short,larr_long)

    fe_dir="total"
    for rp in monitoringConfig.rrd_reports:
                period=rp[0]
                long_period=period!='hours'
                larr=larr_sl[long_period] # don't show trends for hours, they are identical to std graphs
                for sz in monitoringConfig.graph_sizes:
                    size=sz[0]
                    fname=os.path.join(monitoringConfig.monitor_dir,"%s/0Log.%s.%s.html"%(fe_dir,period,size))
                    #if (not os.path.isfile(fname)): #create only if it does not exist
                    if 1: # create every time, it is small and works over reconfigs
                        fd=open(fname,"w")
                        fd.write("<html>\n<head>\n")
                        fd.write("<title>%s log stats over last %s</title>\n"%(title,period));
                        fd.write("</head>\n<body>\n")
                        fd.write('<table width="100%"><tr>\n')
                        fd.write('<td valign="top" align="left"><h1>%s log stats over last %s</h1></td>\n'%(title,period))
                        
                        link_arr=[]
                        for ref_sz in monitoringConfig.graph_sizes:
                            ref_size=ref_sz[0]
                            if size!=ref_size:
                                link_arr.append('<a href="0Log.%s.%s.html">%s</a>'%(period,ref_size,ref_size))
                        fd.write('<td align="center">[%s]</td>\n'%string.join(link_arr,' | '));

                        link_arr=[]
                        for ref_rp in monitoringConfig.rrd_reports:
                            ref_period=ref_rp[0]
                            if period!=ref_period:
                                link_arr.append('<a href="0Log.%s.%s.html">%s</a>'%(ref_period,size,ref_period))
                        fd.write('<td align="right">[%s]</td>\n'%string.join(link_arr,' | '));

                        fd.write('<td align="right">[<a href="0Status.%s.%s.html">Status</a> | <a href="0Terminated.%s.%s.html">Terminated</a>]</td>\n'%(period,size,period,size))
                        
                        fd.write("</tr><tr>\n")

                        if up_dir_and_title!=None:
                            fd.write('<td>[<a href="%s/0Log.%s.%s.html">%s</a>]</td>\n'%(up_dir_and_title[0],period,size,up_dir_and_title[1]))
                        else:
                            fd.write('<td></td>\n') # no uplink
                        link_arr=[]
                        for ref_fe in subdir_list:
                            link_arr.append(('<a href="'+subdir_template+'/0Log.%s.%s.html">%s</a>')%(ref_fe,period,size,ref_fe))
                        fd.write('<td colspan=3 align="right">[%s]</td>\n'%string.join(link_arr,' | '));

                        fd.write("</tr></table>\n")
                        
                        fd.write('<a name="glidein_status">\n')
                        fd.write("<p>\n<table>\n")
                        for s in ('Running','Idle','Wait','Held','Completed','Removed'):
                            if (not (s in ('Completed','Removed'))): # special treatement
                                fd.write('<tr valign="top">')
                                for p in parr:
                                    fd.write('<td>%s</td>'%img2html("%sLog_%s_Count.%s.%s.png"%(p,s,period,size)))
                                fd.write('</tr>\n')
                                fd.write('<tr valign="top">')
                                for l in larr:
                                    for p in parr:
                                        fd.write('<td>%s</td>'%img2html("%s%s_%s_Diff.%s.%s.png"%(p,l,s,period,size)))
                                fd.write('</tr>\n')                            
                        fd.write('<tr valign="top">')
                        for l in larr:
                            for p in parr:
                                fd.write('<td>%s</td>'%img2html("%s%s_Removed_Diff.%s.%s.png"%(p,l,period,size)))
                        fd.write('</tr>\n')
                        fd.write("</table>\n</p>\n")
                        fd.write("</p>\n")
                        fd.write("</body>\n</html>\n")
                        fd.close()
                        pass

                    fname=os.path.join(monitoringConfig.monitor_dir,"%s/0Terminated.%s.%s.html"%(fe_dir,period,size))
                    #if (not os.path.isfile(fname)): #create only if it does not exist
                    if 1: # create every time, it is small and works over reconfigs
                        fd=open(fname,"w")
                        fd.write("<html>\n<head>\n")
                        fd.write("<title>%s terminated glideins over last %s</title>\n"%(title,period));
                        fd.write("</head>\n<body>\n")
                        fd.write('<table width="100%"><tr>\n')
                        fd.write('<td valign="top" align="left"><h1>%s terminated glideins over last %s</h1></td>\n'%(title,period))
                        
                        link_arr=[]
                        for ref_sz in monitoringConfig.graph_sizes:
                            ref_size=ref_sz[0]
                            if size!=ref_size:
                                link_arr.append('<a href="0Terminated.%s.%s.html">%s</a>'%(period,ref_size,ref_size))
                        fd.write('<td align="center">[%s]</td>\n'%string.join(link_arr,' | '));

                        link_arr=[]
                        for ref_rp in monitoringConfig.rrd_reports:
                            ref_period=ref_rp[0]
                            if period!=ref_period:
                                link_arr.append('<a href="0Terminated.%s.%s.html">%s</a>'%(ref_period,size,ref_period))
                        fd.write('<td align="right">[%s]</td>\n'%string.join(link_arr,' | '));

                        fd.write('<td align="right">[<a href="0Status.%s.%s.html">Status</a> | <a href="0Log.%s.%s.html">Log stats</a>]</td>\n'%(period,size,period,size))
                        
                        fd.write("</tr><tr>\n")

                        if up_dir_and_title!=None:
                            fd.write('<td>[<a href="%s/0Terminated.%s.%s.html">%s</a>]</td>\n'%(up_dir_and_title[0],period,size,up_dir_and_title[1]))
                        else:
                            fd.write('<td></td>\n') # no uplink
                        link_arr=[]
                        for ref_fe in subdir_list:
                            link_arr.append(('<a href="'+subdir_template+'/0Terminated.%s.%s.html">%s</a>')%(ref_fe,period,size,ref_fe))
                        fd.write('<td colspan=3 align="right">[%s]</td>\n'%string.join(link_arr,' | '));

                        fd.write("</tr></table>\n")

                        fd.write("<p>\n<table>\n")
                        for sa in (('Diff','Entered_JobsNr'),('Entered_Lasted','Entered_JobsLasted'),('Entered_Goodput','Entered_Terminated')):
                            fd.write('<tr valign="top">')
                            for l in larr:
                                for s in sa:
                                    fd.write('<td>%s</td>'%img2html("%s_Completed_%s.%s.%s.png"%(l,s,period,size)))
                            fd.write('</tr>\n')
                        fd.write("</table>\n</p>\n")

                        fd.write("<h2>Statistics about wasted resources</h2>\n")
                        fd.write("<p><table>\n")
 
                        for s in ('validation','idle',
                                  'nosuccess','badput'):
                            fd.write('<tr valign="top">')
                            for l in larr:
                                for w in ('Waste','WasteTime'):
                                    fd.write('<td>%s</td>'%img2html("%s_Completed_Entered_%s_%s.%s.%s.png"%(l,w,s,period,size)))
                            fd.write('</tr>\n')
                        fd.write("</table>\n</p>\n")

                        if 'SplitTerm' in monitoringConfig.wanted_graphs:                        
                            fd.write('<a name="split_glidein_terminated">\n')
                            fd.write("<p>\n<h2>Terminated glideins by %s</h2>\n"%subdir_label)

                            for s in ('Entered_Lasted',):
                                fd.write("<p><table>\n")
                                range_groups_keys=time_range_groups_keys
                                for r in range_groups_keys:
                                    fd.write('<tr valign="top">')
                                    for l in larr:
                                        fd.write('<td>%s</td><td></td>'%img2html("Split_%s_Completed_%s_%s.%s.%s.png"%(l,s,r,period,size)))
                                    fd.write('</tr>\n')                        
                                fd.write("</table>\n</p>\n")

                            for s in ('validation','idle',
                                      'nosuccess','badput'):
                                fd.write("<p><table>\n")
                                range_groups_keys=mill_range_groups_keys
                                for r in range_groups_keys:
                                    fd.write('<tr valign="top">')
                                    for l in larr:
                                        for w in ('Waste','WasteTime'):
                                            fd.write('<td>%s</td>'%img2html("Split_%s_Completed_Entered_%s_%s_%s.%s.%s.png"%(l,w,s,r,period,size)))
                                    fd.write('</tr>\n')                        
                                fd.write("</table>\n</p>\n")

                        fd.write("<p>\n<table><tr valign='top'>\n")
                        fd.write("<td>\n")
                        fd.write("Legenda of wasted:\n<ul>\n")
                        fd.write(" <li>Validation - Time spent before starting Condor\n")
                        fd.write(" <li>Idle - Time spent by Condor in idle state\n")
                        fd.write(" <li>Nosuccess - Time spent by user jobs that did not return with error code 0 \n")
                        fd.write(" <li>Badput - Time spent by the glidein not running user jobs\n")
                        fd.write("</ul></td>\n")
                        fd.write("<td>\n")
                        fd.write("Scale:\n<ul>\n")
                        fd.write(" <li>Completed - Number of jobs completed per second \n")
                        fd.write(" <li>Lasted - Number of jobs of certain size per second \n")
                        fd.write(" <li>Waste - Number of jobs in that state per second \n")
                        fd.write(" <li>WasteTime - Waste * glidein length \n")
                        fd.write("</ul></td>\n")
                        fd.write("</tr></table>\n")
                        fd.write("</p>\n")
                        fd.write("</body>\n</html>\n")
                        fd.close()
                        pass
                    pass # for sz
                pass # for rp
    

def img2html(img_name):
    return '<a href="%s_creation.html"><img src="%s" border=0></a>'%(img_name,img_name)


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

class LockedRRDSupport(rrdSupport.rrdSupport):
    ###################################################################
    # The default was a NoOp, count use monitoringConfig.get_disk_lock
    #
    # Leave it no-op... else it takes forever to do the updates
    #def get_disk_lock(self,fname):
    #    return monitoringConfig.get_disk_lock()

    #############################################################
    # The default was a NoOp, use monitoringConfig.get_graph_lock
    def get_graph_lock(self,fname):
        return monitoringConfig.get_graph_lock()

    def __init__(self):
        rrdSupport.rrdSupport.__init__(self)
        if self.rrd_obj==None:
            print "Not using RRD" # just for debug purposes

def cleanup_rrd_name(s):
    return string.replace(string.replace(s,".","_"),"@","_")


##################################################

# global configuration of the module
monitoringConfig=MonitoringConfig()

