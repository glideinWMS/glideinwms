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
        self.rrd_archives=[('AVERAGE',0.8,1,740),      # max precision, keep 2.5 days
                           ('AVERAGE',0.92,12,740),       # 1 h precision, keep for a month (30 days)
                           ('AVERAGE',0.98,144,740)        # 12 hour precision, keep for a year
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
                         'Glideins':("Idle","Running","Total")}

    def logJobs(self,jobs_data):
        if not 'totals' in self.data:
            self.data['totals'] = {}

        el={}
        self.data['totals']['Jobs']=el

        for k in self.attributes['Jobs']:
            if jobs_data.has_key(k):
                el[k]=jobs_data[k]
        self.updated=time.time()

    def logGlideins(self,slots_data):
        if not 'totals' in self.data:
            self.data['totals'] = {}

        el={}
        self.data['totals']['Glideins']=el

        for k in self.attributes['Glideins']:
            if slots_data.has_key(k):
                el[k]=slots_data[k]
        self.updated=time.time()


    def logFactJobs(self, factory, idle, effIdle, oldIdle, running):
        if not 'factories' in self.data:
            self.data['factories'] = {}

        factories = self.data['factories']
        if not factory in factories:
            factories[factory] = {}

        factories[factory]['MatchedJobs'] = {'Idle': idle,
                                        'EffectiveIdle': effIdle,
                                        'OldIdle': oldIdle,
                                        'Running': running
                                        }

        self.update=time.time()

    def logFactDown(self, factory, isDown):
        if not 'factories' in self.data:
            self.data['factories'] = {}

        factories = self.data['factories']
        if not factory in factories:
            factories[factory] = {}

        if isDown:
            factories[factory]['Down'] = 'Down'
        else:
            factories[factory]['Down'] = 'Up'

        self.updated = time.time()

    def logFactSlots(self, factory, total, idle, running):
        if not 'factories' in self.data:
            self.data['factories'] = {}

        factories = self.data['factories']
        if not factory in factories:
            factories[factory] = {}

        factories[factory]['Slots'] = {'Total': total,
                                        'Idle': idle,
                                        'Running': running
                                        }

        self.update=time.time()
            
        
    def logFactReq(self, factory, reqIdle, reqMaxRun, params):
        if not 'factories' in self.data:
            self.data['factories'] = {}

        factories = self.data['factories']
        if not factory in factories:
            factories[factory] = {}
        

        factories[factory]['Requested'] = {'Idle': reqIdle,
                                           'MaxRun': reqMaxRun,
                                           'Parameters': copy.deepcopy(params)
                                           }

        self.updated = time.time()

    def get_data(self):
        return copy.deepcopy(self.data['factories'])

    def get_xml_data(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        data=self.get_data()
        return xmlFormat.dict2string(data,
                                     dict_name='factories', el_name='factory',
                                     subtypes_params={"class":{'subclass_params':{'Requested':{'dicts_params':{'Parameters':{'el_name':'Parameter'}}}}}},
                                       indent_tab=indent_tab,leading_tab=leading_tab)

        #return xmlFormat.class2string(self.data,'<VOFrontendGroupStats>',
        #                             indent_tab=indent_tab,leading_tab=leading_tab)

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

    def get_total(self):
        total={'MatchedJobs':None,'Requested':None,'Slots':None}

        for f in self.data['factories'].keys():
            fa=self.data['factories'][f]
            for w in fa.keys():
                if total.has_key(w): # ignore eventual not supported classes
                    el=fa[w]
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

        total.update(copy.deepcopy(self.data['totals']))
        return total

    def get_xml_total(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=""):
        total=self.get_total()
        return xmlFormat.class2string(total,
                                      inst_name="total",
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
                 self.get_xml_data(indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
                 self.get_xml_total(indent_tab=xmlFormat.DEFAULT_TAB,leading_tab=xmlFormat.DEFAULT_TAB)+"\n"+
                 "</VOFrontendGroupStats>\n")

        monitoringConfig.write_file("frontend_status.xml",xml_str)

        total_el = self.get_total()
        # update RRDs
        val_dict={}
        type_strings={'Jobs':'Jobs','Glideins':'Slots'}

        #init, so tha all get created properly
        for tp in self.attributes.keys():
            tp_str=type_strings[tp]
            attributes_tp=self.attributes[tp]
            for a in attributes_tp:
                val_dict["%s%s"%(tp_str,a)]=None
            
        
        for tp in total_el:
            # type - Jobs,Slots
            if not (tp in self.attributes.keys()):
                continue

            tp_str=type_strings[tp]

            attributes_tp=self.attributes[tp]
                
            fe_el_tp=total_el[tp]
            for a in fe_el_tp.keys():
                if a in attributes_tp:
                    a_el=fe_el_tp[a]
                    if type(a_el)!=type({}): # ignore subdictionaries
                        val_dict["%s%s"%(tp_str,a)]=a_el

        monitoringConfig.establish_dir("total")
        monitoringConfig.write_rrd_multi("total/Status_Attributes",
                                         "GAUGE",self.updated,val_dict)

        self.files_updated=self.updated        
        return

########################################################################
    
class factoryStats:
    def __init__(self):
        self.data={}
        self.updated=time.time()

        self.files_updated=None
        self.attributes={'Jobs':("Idle","OldIdle","Running","Total"),
                         'Matched':("Idle","OldIdle","Running","Total"),
                         'Requested':("Idle","MaxRun"),
                         'Slots':("Idle","Running","Total")}


    def logJobs(self,client_name,qc_status):
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
            
            #init, so that all get created properly
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

