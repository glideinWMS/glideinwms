
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

import logSupport
import glideFactoryLib

# list of rrd files that each site has
rrd_list = ('Status_Attributes.rrd', 'Log_Completed.rrd', 'Log_Completed_Stats.rrd', 'Log_Completed_WasteTime.rrd', 'Log_Counts.rrd')

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
        self.rrd_archives=[('AVERAGE',0.8,1,740),      # max precision, keep 2.5 days
                           ('AVERAGE',0.92,12,740),       # 1 h precision, keep for a month (30 days)
                           ('AVERAGE',0.98,144,740)        # 12 hour precision, keep for a year
                           ]

        # The name of the attribute that identifies the glidein
        self.monitor_dir="monitor/"

        
        self.log_dir="log/"
        self.logCleanupObj=None

        self.rrd_obj=rrdSupport.rrdSupport()

        self.my_name="Unknown"

    def config_log(self,log_dir,max_days,min_days,max_mbs):
        self.log_dir=log_dir
        glideFactoryLib.log_files.add_dir_to_cleanup(None,log_dir,
                                                     "(completed_jobs_\..*\.log)",
                                                     max_days,min_days,max_mbs)

    def logCompleted(self,client_name,entered_dict):
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
                username=el['username']
                jobs_duration=el['jobs_duration']
                waste_mill=el['wastemill']
                fd.write(("<job %37s %34s %22s %17s %17s %22s %24s>"%(('terminated="%s"'%timeConversion.getISO8601_Local(now)),
                                                                 ('client="%s"'%client_name),
                                                                 ('username="%s"'%username),
                                                                 ('id="%s"'%job_id),
                                                                 ('duration="%i"'%el['duration']),
                                                                 ('condor_started="%s"'%(el['condor_started']==True)),
                                                                 ('condor_duration="%i"'%el['condor_duration'])))+
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

    # like write_rrd_multi, but with each ds having each type
    # each element of ds_desc_dict is a dictionary with any of
    #  ds_type, min, max
    # if not present, the defaults are ('GAUGE','U','U')
    def write_rrd_multi_hetero(self,relative_fname,ds_desc_dict,time,val_dict):
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
                ds_names=val_dict.keys()
                ds_names.sort()

                ds_arr=[]
                for ds_name in ds_names:
                    ds_desc={'ds_type':'GAUGE','min':'U','max':'U'}
                    if ds_desc_dict.has_key(ds_name):
                        for k in ds_desc_dict[ds_name].keys():
                            ds_desc[k]=ds_desc_dict[ds_name][k]
                    
                    ds_arr.append((ds_name,ds_desc['ds_type'],self.rrd_heartbeat,ds_desc['min'],ds_desc['max']))
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

class condorQStats:
    def __init__(self):
        self.data={}
        self.updated=time.time()

        self.files_updated=None
        self.attributes={'Status':("Idle","Running","Held","Wait","Pending","StageIn","IdleOther","StageOut"),
                         'Requested':("Idle","MaxRun"),
                         'ClientMonitor':("InfoAge","JobsIdle","JobsRunning","GlideIdle","GlideRunning","GlideTotal")}


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

        status_pairs=((1,"Idle"), (2,"Running"), (5,"Held"), (1001,"Wait"),(1002,"Pending"),(1010,"StageIn"),(1100,"IdleOther"),(4010,"StageOut"))
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

        for karr in (('Idle','JobsIdle'),('Running','JobsRunning'),('GlideinsIdle','GlideIdle'),('GlideinsRunning','GlideRunning'),('GlideinsTotal','GlideTotal')):
            ck,ek=karr
            if client_monitor.has_key(ck):
                el[ek]=client_monitor[ck]

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
        type_strings={'Status':'Status','Requested':'Req','ClientMonitor':'Client'}
        for fe in [None]+data.keys():
            if fe==None: # special key == Total
                fe_dir="total"
                fe_el=total_el
            else:
                fe_dir="frontend_"+fe
                fe_el=data[fe]

            val_dict={}
            # Initialize,  so that all get created properly
            for tp in self.attributes.keys():
                tp_str=type_strings[tp]
                attributes_tp=self.attributes[tp]
                for a in attributes_tp:
                    val_dict["%s%s"%(tp_str,a)]=None               
            
            monitoringConfig.establish_dir(fe_dir)
            for tp in fe_el.keys():
                # type - Status, Requested or ClientMonitor
                if not (tp in self.attributes.keys()):
                    continue

                tp_str=type_strings[tp]

                attributes_tp=self.attributes[tp]
                
                fe_el_tp=fe_el[tp]
                for a in fe_el_tp.keys():
                    if a in attributes_tp:
                        a_el=fe_el_tp[a]
                        if type(a_el)!=type({}): # ignore subdictionaries
                            val_dict["%s%s"%(tp_str,a)]=a_el
                
            monitoringConfig.write_rrd_multi("%s/Status_Attributes"%fe_dir,
                                             "GAUGE",self.updated,val_dict)

        self.files_updated=self.updated        
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
        self.current_stats_data={}     # will contain dictionary client->username->dirSummary.data
        self.stats_diff={}             # will contain the differences
        self.job_statuses=('Running','Idle','Wait','Held','Completed','Removed') #const
        self.job_statuses_short=('Running','Idle','Wait','Held') #const

        self.files_updated=None

    def reset(self):
        # reserve only those that has been around this time
        new_stats_data={}
        for c in self.stats_diff.keys():
            # but carry over all the users... should not change that often
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
        self.stats_diff[client_name]={}
        if self.current_stats_data.has_key(client_name):
            for username in stats.keys():
                if self.current_stats_data[client_name].has_key(username):
                    self.stats_diff[client_name][username]=stats[username].diff(self.current_stats_data[client_name][username])

        self.current_stats_data[client_name]={}
        for username in stats.keys():
            self.current_stats_data[client_name][username]=stats[username].data
        
        self.updated=time.time()
        self.updated_year=time.localtime(self.updated)[0]

    def get_stats_data_summary(self):
        stats_data={}
        for client_name in self.current_stats_data.keys():
            out_el={}
            for s in self.job_statuses:
                if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
                    count=0
                    for username in self.current_stats_data[client_name].keys():
                        client_el=self.current_stats_data[client_name][username]
                        if ((client_el!=None) and (s in client_el.keys())):
                            count+=len(client_el[s])

                    out_el[s]=count
            stats_data[client_name]=out_el
        return stats_data

    def get_xml_stats_data(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        data=self.get_stats_data_summary()
        return xmlFormat.dict2string(data,
                                     dict_name="frontends",el_name="frontend",
                                     subtypes_params={"class":{}},
                                     indent_tab=indent_tab,leading_tab=leading_tab)

    # in: entered_list=self.stats_diff[*]['Entered']
    # out: entered_list[job_id]{'duration','condor_started','condor_duration','jobsnr',wastemill':{'validation','idle','nosuccess','badput'}}
    def get_completed_stats(self,entered_list):
        out_list={}

        for enle in entered_list:
            enle_job_id=enle[0]
            enle_running_time=enle[2]
            enle_last_time=enle[3]
            enle_difftime=self.diffTimes(enle_last_time,enle_running_time)

            # get stats
            enle_stats=enle[4]
            username='unknown'
            enle_condor_started=0
            enle_condor_duration=0 # default is 0, in case it never started
            enle_glidein_duration=enle_difftime # best guess
            if enle_stats!=None:
                enle_condor_started=enle_stats['condor_started']
                if enle_stats.has_key('glidein_duration'):
                    enle_glidein_duration=enle_stats['glidein_duration']
                if enle_stats.has_key('username'):
                    username=enle_stats['username']
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

            out_list[enle_job_id]={'username':username,
                                   'duration':enle_glidein_duration,'condor_started':enle_condor_started,'condor_duration':enle_condor_duration,
                                   'jobsnr':enle_nr_jobs,'jobs_duration':{'total':enle_jobs_duration,'goodput':enle_goodput,'terminated':enle_terminated_duration},
                                   'wastemill':enle_waste_mill}
        
        return out_list

    # in: entered_list=get_completed_data()
    # out: {'Lasted':{'2hours':...,...},'Sum':{...:12,...},'JobsNr':...,
    #       'Waste':{'validation':{'0m':...,...},...},'WasteTime':{...:{...},...}}
    def summarize_completed_stats(self,entered_list):
        # summarize completed data
        count_entered_times={}
        for enle_timerange in getAllTimeRanges(): 
            count_entered_times[enle_timerange]=0 # make sure all are initialized

        count_jobnrs={}
        for enle_jobrange in getAllJobRanges(): 
            count_jobnrs[enle_jobrange]=0 # make sure all are initialized

        count_jobs_duration={};
        for enle_jobs_duration_range in getAllTimeRanges():
            count_jobs_duration[enle_jobs_duration_range]=0 # make sure all are intialized

        count_total={'Glideins':0,
                     'Lasted':0,
                     'FailedNr':0,
                     'JobsNr':0,
                     'JobsLasted':0,
                     'JobsTerminated':0,
                     'JobsGoodput':0,
                     'CondorLasted':0}
        
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
            enle_condor_duration=enle['condor_duration']
            enle_jobs_nr=enle['jobsnr']
            enle_jobs_duration=enle['jobs_duration']
            enle_condor_started=enle['condor_started']

            count_total['Glideins']+=1
            if not enle_condor_started:
                count_total['FailedNr']+=1

            # find and save time range
            count_total['Lasted']+=enle_glidein_duration
            enle_timerange=getTimeRange(enle_glidein_duration)
            count_entered_times[enle_timerange]+=1

            count_total['CondorLasted']+=enle_condor_duration

            # find and save job range
            count_total['JobsNr']+=enle_jobs_nr
            enle_jobrange=getJobRange(enle_jobs_nr)
            count_jobnrs[enle_jobrange]+=1

            if enle_jobs_nr>0:
                enle_jobs_duration_range=getTimeRange(enle_jobs_duration['total']/enle_jobs_nr)
            else:
                enle_jobs_duration_range=getTimeRange(-1)
            count_jobs_duration[enle_jobs_duration_range]+=1

            count_total['JobsLasted']+=enle_jobs_duration['total']
            count_total['JobsTerminated']+=enle_jobs_duration['terminated']
            count_total['JobsGoodput']+=enle_jobs_duration['goodput']

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
        
        
        return {'Lasted':count_entered_times,'JobsNr':count_jobnrs,'Sum':count_total,'JobsDuration':count_jobs_duration,'Waste':count_waste_mill,'WasteTime':time_waste_mill}

    def get_data_summary(self):
        stats_data={}
        for client_name in self.stats_diff.keys():
            out_el={'Current':{},'Entered':{},'Exited':{}}
            for s in self.job_statuses:
                entered=0
                entered_list=[]
                exited=0
                for username in self.stats_diff[client_name].keys():
                    diff_el=self.stats_diff[client_name][username]
                
                    if ((diff_el!=None) and (s in diff_el.keys())):
                        entered_list+=diff_el[s]['Entered']
                        entered+=len(diff_el[s]['Entered'])
                        exited-=len(diff_el[s]['Exited'])

                out_el['Entered'][s]=entered
                if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
                    count=0
                    for username in self.current_stats_data[client_name].keys():
                        stats_el=self.current_stats_data[client_name][username]

                        if ((stats_el!=None) and (s in stats_el.keys())):
                            count+=len(stats_el[s])
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
                for username in self.current_stats_data[client_name]:
                    sdata=self.current_stats_data[client_name][username]
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

    def get_diff_summary(self):
        out_data={}
        for client_name in self.stats_diff.keys():
            client_el={'Wait':None,'Idle':None,'Running':None,'Held':None,'Completed':None,'Removed':None}
            for k in client_el.keys():
                client_el[k]={'Entered':[],'Exited':[]}
                tdata=client_el[k]
                #flatten all usernames into one
                for username in self.stats_diff[client_name].keys():
                    sdiff=self.stats_diff[client_name][username]
                    if ((sdiff!=None) and (k in sdiff.keys())):
                        for e in tdata.keys():
                            for sdel in sdiff[k][e]:
                                # for completed jobs, add the username
                                # not for the others since there is no adequate place in the object
                                if k=='Completed':
                                    sdel[4]['username']=username
                                tdata[e].append(sdel)
            out_data[client_name]=client_el
        return out_data

    def get_diff_total(self):
        total={'Wait':None,'Idle':None,'Running':None,'Held':None,'Completed':None,'Removed':None}
        for k in total.keys():
            total[k]={'Entered':[],'Exited':[]}
            tdata=total[k]
            for client_name in self.stats_diff.keys():
                for username in self.stats_diff[client_name].keys():
                    sdiff=self.stats_diff[client_name][username]
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
        diff_summary=self.get_diff_summary()
        stats_total_summary=self.get_stats_total_summary()
        for client_name in [None]+diff_summary.keys():
            if client_name==None:
                fe_dir="total"
                sdata=stats_total_summary
                sdiff=self.get_diff_total()
            else:
                fe_dir="frontend_"+client_name
                sdata=stats_data_summary[client_name]
                sdiff=diff_summary[client_name]

            monitoringConfig.establish_dir(fe_dir)
            val_dict_counts={}
            val_dict_counts_desc={}
            val_dict_completed={}
            val_dict_stats={}
            val_dict_waste={}
            val_dict_wastetime={}
            for s in self.job_statuses:
                if not (s in ('Completed','Removed')): # I don't have their numbers from inactive logs
                    count=sdata[s]
                    val_dict_counts["Status%s"%s]=count
                    val_dict_counts_desc["Status%s"%s]={'ds_type':'GAUGE'}

                if ((sdiff!=None) and (s in sdiff.keys())):
                    entered_list=sdiff[s]['Entered']
                    entered=len(entered_list)
                    exited=-len(sdiff[s]['Exited'])
                else:
                    entered_list=[]
                    entered=0
                    exited=0
                    
                val_dict_counts["Entered%s"%s]=entered
                val_dict_counts_desc["Entered%s"%s]={'ds_type':'ABSOLUTE'}
                if not (s in ('Completed','Removed')): # Always 0 for them
                    val_dict_counts["Exited%s"%s]=exited
                    val_dict_counts_desc["Exited%s"%s]={'ds_type':'ABSOLUTE'}
                elif s=='Completed':
                    completed_stats=self.get_completed_stats(entered_list)
                    if client_name!=None: # do not repeat for total
                        monitoringConfig.logCompleted(client_name,completed_stats)
                    completed_counts=self.summarize_completed_stats(completed_stats)

                    # save simple vals
                    for tkey in completed_counts['Sum'].keys():
                        val_dict_completed[tkey]=completed_counts['Sum'][tkey]

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
            monitoringConfig.write_rrd_multi_hetero("%s/Log_Counts"%fe_dir,
                                                    val_dict_counts_desc,self.updated,val_dict_counts)
            monitoringConfig.write_rrd_multi("%s/Log_Completed"%fe_dir,
                                             "ABSOLUTE",self.updated,val_dict_completed)
            monitoringConfig.write_rrd_multi("%s/Log_Completed_Stats"%fe_dir,
                                             "ABSOLUTE",self.updated,val_dict_stats)
            # Disable Waste RRDs... WasteTime much more useful
            #monitoringConfig.write_rrd_multi("%s/Log_Completed_Waste"%fe_dir,
            #                                 "ABSOLUTE",self.updated,val_dict_waste)
            monitoringConfig.write_rrd_multi("%s/Log_Completed_WasteTime"%fe_dir,
                                             "ABSOLUTE",self.updated,val_dict_wastetime)


        self.files_updated=self.updated
        return

    
###############################################################################
#
# factoryStatusData
# added by C.W. Murphy starting on 08/09/10
# this class handles the data obtained from the rrd files
#
###############################################################################

class FactoryStatusData:
    """documentation"""
    def __init__(self):
	self.data = {}
        for rrd in rrd_list:
            self.data[rrd] = {}
	self.updated = time.time()
        self.tab = xmlFormat.DEFAULT_TAB
        self.resolution = (7200, 86400, 604800) # 2hr, 1 day, 1 week
        self.total = "total/"
        self.frontends = []
        self.base_dir = monitoringConfig.monitor_dir

    def getUpdated(self):
	"""returns the time of last update"""
	local = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(self.updated))
	gmt = time.strftime("%a, %d %b %Y %H:%M:%S", time.gmtime(self.updated))
	xml_updated = {'Local':local, 'UTC':gmt, 'unixtime':self.updated}

	return xmlFormat.dict2string(xml_updated, dict_name = "updated", el_name = "timezone", subtypes_params = {"class":{}}, indent_tab = self.tab, leading_tab = self.tab)

    def fetchData(self, file, pathway, res, start, end):
        """Uses rrdtool to fetch data from the clients.  Returns a dictionary of lists of data.  There is a list for each element.

        rrdtool fetch returns 3 tuples: a[0], a[1], & a[2].
        [0] lists the resolution, start and end time, which can be specified as arugments of fetchData.
        [1] returns the names of the datasets.  These names are listed in the key.
        [2] is a list of tuples. each tuple contains data from every dataset.  There is a tuple for each time data was collected."""

	#use rrdtool to fetch data
        baseRRDSupport = rrdSupport.rrdSupport()
	fetched = baseRRDSupport.fetch_rrd(pathway + file, 'AVERAGE', resolution = res, start = start, end = end)
        
	#sometimes rrdtool returns extra tuples that don't contain data
        actual_res = fetched[0][2]
        actual_start = fetched[0][0]
        actual_end = fetched[0][1]
        num2slice = ((actual_end - end) - (actual_start - start)) / actual_res
        if num2slice > 0:
            fetched_data_raw = fetched[2][:-num2slice]
        else:
            fetched_data_raw = fetched[2]
        #converts fetched from tuples to lists
	fetched_names = list(fetched[1])
	fetched_data = []
	for data in fetched_data_raw:
		fetched_data.append(list(data))
	
	#creates a dictionary to be filled with lists of data
	data_sets = {}
	for name in fetched_names:
		data_sets[name] = []	

	#check to make sure the data exists
	for data_set in data_sets:
		index = fetched_names.index(data_set)	
		for data in fetched_data:
			if isinstance(data[index], (int, float)):
                            data_sets[data_set].append(data[index])
	return data_sets

    def average(self, list):
        try:
            if len(list) > 0:
                avg_list = sum(list) / len(list)
            else:
                avg_list = 0
            return avg_list
        except TypeError:
            glideFactoryLib.log_files.logDebug("average: TypeError")
            return

    def getData(self, input):
        """returns the data fetched by rrdtool in a xml readable format"""
        folder = str(input)
        if folder == self.total:
            client = folder
        else:
            folder_name = folder.split('@')[-1]
            client = folder_name.join(["frontend_","/"])
            if client not in self.frontends:
                self.frontends.append(client)
        
        for rrd in rrd_list:
            self.data[rrd][client] = {}
            for res in self.resolution:
                self.data[rrd][client][res] = {}
                end = int(time.time() / res) * res
                start = end - res
                try:
                    fetched_data = self.fetchData(file = rrd, pathway = self.base_dir + "/" + client, start = start, end = end, res = res)
                    for data_set in fetched_data:
                        self.data[rrd][client][res][data_set] = self.average(fetched_data[data_set])
                except TypeError:
                    glideFactoryLib.log_files.logDebug("FactoryStatusData:fetchData: TypeError")

        return self.data

    def getXMLData(self, rrd):
	"writes an xml file for the data fetched from a given site."

        # create a string containing the total data
        total_xml_str = self.tab + '<total>\n'
        get_data_total = self.getData(self.total)
        try:
            total_data = self.data[rrd][self.total]
            total_xml_str += (xmlFormat.dict2string(total_data, dict_name = 'periods', el_name = 'period', subtypes_params={"class":{}}, indent_tab = self.tab, leading_tab = 2 * self.tab) + "\n")
        except NameError, UnboundLocalError:
            glideFactoryLib.log_files.logDebug("FactoryStatusData:total_data: NameError or UnboundLocalError")
        total_xml_str += self.tab + '</total>\n'

        # create a string containing the frontend data
        frontend_xml_str = (self.tab + '<frontends>\n')
        for frontend in self.frontends:
            fe_name = frontend.split("/")[0]
            frontend_xml_str += (2 * self.tab +
                                 '<frontend name=\"' + fe_name + '\">\n')
            try:
                frontend_data = self.data[rrd][frontend]
                frontend_xml_str += (xmlFormat.dict2string(frontend_data, dict_name = 'periods', el_name = 'period', subtypes_params={"class":{}}, indent_tab = self.tab, leading_tab = 3 * self.tab) + "\n")
            except NameError, UnboundLocalError:
                glideFactoryLib.log_files.logDebug("FactoryStatusData:frontend_data: NameError or UnboundLocalError")
            frontend_xml_str += 2 * self.tab + '</frontend>'
        frontend_xml_str += self.tab + '</frontends>\n'
                  
        data_str =  total_xml_str + frontend_xml_str
        return data_str
    
    def writeFiles(self):
        for rrd in rrd_list:
            file_name = 'rrd_' + rrd.split(".")[0] + '.xml'
            xml_str = ('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n' +
                       '<glideFactoryEntryRRDStats>\n' +
                       self.getUpdated() + "\n" +
                       self.getXMLData(rrd) +
                       '</glideFactoryEntryRRDStats>')
            try:
                monitoringConfig.write_file(file_name, xml_str)
            except IOError:
                glideFactoryLib.log_files.logDebug("FactoryStatusData:write_file: IOError")
	return

    
############### P R I V A T E ################

##################################################
def getTimeRange(absval):
        if absval<1:
            return 'Unknown'
        if absval<(25*60):
            return 'Minutes'
        if absval>(64*3600): # limit detail to 64 hours
            return 'Days'
        # start with 7.5 min, and than exp2
        logval=int(math.log(absval/450.0,4)+0.49)
        level=math.pow(4,logval)*450.0
        if level<3600:
            return "%imins"%(int(level/60+0.49))
        else:
            return "%ihours"%(int(level/3600+0.49))

def getAllTimeRanges():
        return ('Unknown','Minutes','30mins','2hours','8hours','32hours','Days')
    
def getJobRange(absval):
        if absval<1:
            return 'None'
        if absval==1:
            return '1job'
        if absval==2:
            return '2jobs'
        if absval<9:
            return '4jobs'
        if absval<30: # limit detail to 30 jobs
            return '16jobs'
        else:
            return 'Many'

def getAllJobRanges():
        return ('None','1job','2jobs','4jobs','16jobs','Many')
    
def getMillRange(absval):
        if absval<2:
            return 'None'
        if absval<15:
            return '5m'
        if absval<60:
            return '25m'
        if absval<180:
            return '100m'
        if absval<400:
            return '250m'
        if absval<700:
            return '500m'
        if absval>998:
            return 'All'
        else:
            return 'Most'

def getAllMillRanges():
        return ('None','5m','25m','100m','250m','500m','Most','All')            

##################################################
def get_completed_stats_xml_desc():
    return {'dicts_params':{'Lasted':{'el_name':'TimeRange'},
                            'JobsDuration':{'el_name':'TimeRange'},
                            'JobsNr':{'el_name':'Range'}},
            'subclass_params':{'Waste':{'dicts_params':{'idle':{'el_name':'Fraction'},
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

