#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module contains the create_frontend params class
#
# Author:
#   Igor Sfiligoi
#

import os
import copy
import sys  # not used
import os.path  # not needed (os is sufficient)
import string  # not used
import socket
import types  # not used
import traceback  # not used
from glideinwms.lib import xmlParse
from glideinwms.lib import condorExe  # not used
import cWParams


class VOFrontendSubParams(cWParams.CommonSubParams):
    # return attribute value in the proper python format
    def extract_attr_val(self,attr_obj):
        return extract_attr_val(attr_obj)

######################################################
# Params used by create_glideins and recreate_glideins
class VOFrontendParams(cWParams.CommonParams):
    # populate self.defaults
    def init_defaults(self):
        self.init_support_defaults()

        # VO scripts should start after the factory has been set completely up
        # but there could be exceptions
        self.file_defaults["after_entry"]=("True",'Bool','Should this file be loaded after the factory entry ones?',None)

        # publishing specific to frontend
        self.attr_defaults["type"]=["string","string|int|expr","What kind on data is value. (if expr, a python expression with access to frontend and glidein dictionaries)",None]

        group_config_defaults=cWParams.commentedOrderedDict()
        
        group_config_running_defaults=cWParams.commentedOrderedDict()
        group_config_running_defaults["max"]=['10000',"nr_jobs","What is the max number of running glideins I want to get to",None]
        group_config_running_defaults["min"]=['0',"nr_jobs","Min number of running glideins with an empty/small queue.",None]
        group_config_running_defaults["relative_to_queue"]=['1.15',"fraction","Max relative to number of matching jobs in the queue.",None]
        group_config_defaults['running_glideins_per_entry']=group_config_running_defaults

        common_config_running_total_defaults=cWParams.commentedOrderedDict()
        common_config_running_total_defaults["max"]=['100000',"nr_jobs","What is the max number of running glideins I want to get to - globally",None]
        common_config_running_total_defaults["curb"]=['90000',"nr_jobs","When should I start curbing glidein submission",None]
        group_config_defaults['running_glideins_total']=common_config_running_total_defaults

        group_config_idle_defaults=cWParams.commentedOrderedDict()
        group_config_idle_defaults["max"]=['100',"nr_jobs","How much pressure should I apply to the entry points",None]
        group_config_idle_defaults["reserve"]=['5',"nr_jobs","How much to overcommit.",None]
        group_config_defaults['idle_glideins_per_entry']=group_config_idle_defaults

        group_config_lifetime_defaults=cWParams.commentedOrderedDict()
        group_config_lifetime_defaults["max"]=['0',"NR","How long idle glideins are kept in the factory queue (seconds)",None]
        group_config_defaults['idle_glideins_lifetime']=group_config_lifetime_defaults

        group_config_vms_defaults=cWParams.commentedOrderedDict()
        group_config_vms_defaults["max"]=['100',"nr_vms","How many idle VMs should I tollerate, before stopping submitting glideins",None]
        group_config_vms_defaults["curb"]=['5',"nr_vms","How many idle VMs should I tollerate, before starting to curb submissions.",None]
        group_config_defaults['idle_vms_per_entry']=group_config_vms_defaults

        common_config_vms_total_defaults=cWParams.commentedOrderedDict()
        common_config_vms_total_defaults["max"]=['1000',"nr_jobs","How many total idle VMs should I tollerate, before stopping submitting glideins",None]
        common_config_vms_total_defaults["curb"]=['200',"nr_jobs","How many total idle VMs should I tollerate, before starting to curb submissions.",None]
        group_config_defaults['idle_vms_total']=common_config_vms_total_defaults

        group_config_proc_work_defaults=cWParams.commentedOrderedDict()
        group_config_proc_work_defaults["matchmakers"]=['3',"NR","Max number of worker processes that will be doing the matchmaking",None]
        group_config_defaults['processing_workers']=group_config_proc_work_defaults

        # not exported and order does not matter, can stay a regular dictionary
        sub_defaults={'attrs':(xmlParse.OrderedDict(),'Dictionary of attributes',"Each attribute group contains",self.attr_defaults),
                      'files':([],'List of files',"Each file group contains",self.file_defaults)}

        query_attrs_defaults=cWParams.commentedOrderedDict()
        query_attrs_defaults['type']=('string','string|int|real|bool','Attribute type',None)

        fj_match_defaults=cWParams.commentedOrderedDict()
        fj_match_defaults["query_expr"]=['True','CondorExpr','Expression for selecting user jobs',None]
        fj_match_defaults["match_attrs"]=(xmlParse.OrderedDict(),"Dictionary of ClassAd attributes","Each attribute contains",query_attrs_defaults)

        collector_defaults=cWParams.commentedOrderedDict()
        collector_defaults["node"]=(None,"nodename","Factory collector node name (for example, fg2.my.org:9999)",None)
        collector_defaults["DN"]=(None,"dn","Factory collector distinguised name (subject) (for example, /DC=org/DC=myca/OU=Services/CN=fg2.my.org)",None)
        collector_defaults["factory_identity"]=("factory@fake.org","authenticated_identity","What is the AuthenticatedIdentity of the factory at the WMS collector",None)
        collector_defaults["my_identity"]=("me@fake.org","authenticated_identity","What is the AuthenticatedIdentity of my proxy at the WMS collector",None)

        factory_match_defaults=copy.deepcopy(fj_match_defaults)
        factory_match_defaults["collectors"]=([],"List of factory collectors","Each collector contains",collector_defaults)

        schedd_defaults=cWParams.commentedOrderedDict()
        schedd_defaults["fullname"]=(None,"name","User schedd name (for example, schedd_3@sb1.my.org)",None)
        schedd_defaults["DN"]=(None,"dn","User schedd distinguised name (subject) (for example, /DC=org/DC=myca/OU=Services/CN=sb1.my.org)",None)

        job_match_defaults=copy.deepcopy(fj_match_defaults)
        job_match_defaults["schedds"]=([],"List of user schedds","Each schedd contains",schedd_defaults)

        match_defaults=cWParams.commentedOrderedDict()
        match_defaults["factory"]=factory_match_defaults
        match_defaults["job"]=job_match_defaults
        match_defaults["match_expr"]=('True','PythonExpr', 'Python expression for matching jobs to factory entries with access to job and glidein dictionaries',None)
        match_defaults["start_expr"]=('True','CondorExpr', 'Condor expression for matching jobs to glideins at runtime',None)


        proxy_defaults=cWParams.commentedOrderedDict()
        proxy_defaults["absfname"]=(None,"fname","x509 proxy file name (see also pool_idx_list)",None)
        proxy_defaults["keyabsfname"]=(None,"fname","for key files, file name of the key pair",None)
        proxy_defaults["pilotabsfname"]=(None,"fname","to specify a different pilot proxy instead of using submit proxy",None)
        proxy_defaults["type"]=("grid_proxy","proxy_type","Type of credential: grid_proxy,cert_pair,key_pair,username_password",None)
        proxy_defaults["trust_domain"]=("OSG","grid_type","Trust Domain",None)
        proxy_defaults["creation_script"]=(None,"command","Script to re-create credential",None)
        proxy_defaults["update_frequency"]=(None,"int","Update proxy when there is this much time left",None)
        proxy_defaults["remote_username"]=(None,"username","User name at the remote resource",None)
        proxy_defaults["vm_id"]=(None,"vm_id","VM Id",None)
        proxy_defaults["vm_type"]=(None,"vm_type","VM Type",None)
        proxy_defaults["pool_idx_len"]=(None,"boolean","Adds leading zeros to the suffix so all filenames the same length",None)
        proxy_defaults["pool_idx_list"]=(None,"string","List of indices, can include ranges of indices",None)
        proxy_defaults["security_class"]=(None,"id","Proxies in the same security class can potentially access each other (Default: proxy_nr)",None)
        proxy_defaults["project_id"] = (None,"string","OSG Project ID. Ex TG-12345", None)

        security_defaults=cWParams.commentedOrderedDict()
        security_defaults["proxy_selection_plugin"]=(None,"proxy_name","Which credentials selection plugin should I use (ProxyAll if None)",None)
        security_defaults["credentials"]=([],'List of credentials',"Each credential element contains",proxy_defaults)
        security_defaults["security_name"]=(None,"frontend_name","What name will we advertize for security purposes?",None)
        
        self.group_defaults=cWParams.commentedOrderedDict()
        self.group_defaults["match"]=match_defaults
        self.group_defaults["enabled"]=("True","Bool","Is this group enabled?",None)
        self.group_defaults["config"]=group_config_defaults
        self.group_defaults["attrs"]=sub_defaults['attrs']
        self.group_defaults["files"]=sub_defaults['files']
        self.group_defaults["security"]=copy.deepcopy(security_defaults)
        

        ###############################
        # Start defining the defaults
        self.defaults["downtimes_file"]=('frontenddowntime', 'string', 'Frontend Downtime File', None)
        self.defaults["frontend_name"]=(socket.gethostname(),'ID', 'VO Frontend name',None)
        self.defaults['frontend_versioning'] = ('True', 'Bool', 'Should we create versioned subdirectories of the type frontend_$frontend_name?', None)

        self.defaults['frontend_monitor_index_page'] = ('True', 'Bool', 'Should we create an index.html in the monitoring web directory?',None)
        
        work_defaults=cWParams.commentedOrderedDict()
        work_defaults["base_dir"]=("%s/frontstage"%os.environ["HOME"],"base_dir","Frontend base dir",None)
        work_defaults["base_log_dir"]=("%s/frontlogs"%os.environ["HOME"],"log_dir","Frontend base log dir",None)
        self.defaults["work"]=work_defaults

        process_log_defaults=cWParams.commentedOrderedDict()
        process_log_defaults["min_days"] = ["3.0","days","Min number of days the logs must be preserved (even if they use too much space)",None]
        process_log_defaults["max_days"] = ["7.0","days","Max number of days the logs should be preserved",None]
        process_log_defaults["max_mbytes"] = ["100.0","Mbytes","Max number of Mbytes the logs can use",None]
        process_log_defaults['extension'] = ["all", "string", "name of the log extention", None]
        process_log_defaults['msg_types'] = ["INFO, WARN, ERR", "string", "types of log messages", None]
        process_log_defaults['backup_count'] = ["5", "string", "Number of backup logs to keep", None]
        process_log_defaults['compression'] = ["", "string", "Compression for backup log files", None]
        
        log_retention_defaults = cWParams.commentedOrderedDict()
        log_retention_defaults["process_logs"] = ([], 'Dictionary of log types', "Each log corresponds to a log file", copy.deepcopy(process_log_defaults))
        self.defaults["log_retention"] = log_retention_defaults
        
        monitor_footer_defaults=cWParams.commentedOrderedDict()
        monitor_footer_defaults["display_txt"] = ["", "string", "what will be displayed at the bottom of the monitoring page", None]
        monitor_footer_defaults["href_link"] = ["", "string", "where to link to", None]
        self.defaults["monitor_footer"] = monitor_footer_defaults

        self.defaults['loop_delay']=('60','seconds', 'Number of seconds between iterations',None)
        self.defaults['advertise_delay']=('5','NR', 'Advertize evert NR loops',None)
        self.defaults['advertise_with_tcp']=('True','Bool', 'Should condor_advertise use TCP connections?',None)
        self.defaults['advertise_with_multiple']=('True','Bool', 'Should condor_advertise use -multiple?',None)

        self.defaults['group_parallel_workers']=('2','NR', 'Max number of parallel workers that process the group policies', None)

        self.defaults['restart_attempts']=('3','NR', 'Max allowed NR restarts every restart_interval before shutting down',None)
        self.defaults['restart_interval']=('1800','NR', 'Time interval NR sec which allow max restart attempts',None)

        stage_defaults=cWParams.commentedOrderedDict()
        stage_defaults["base_dir"]=("/var/www/html/vofrontend/stage","base_dir","Stage base dir",None)
        stage_defaults["web_base_url"]=("http://%s/vofrontend/stage"%socket.gethostname(),'base_url','Base Web server URL',None)
        stage_defaults["use_symlink"]=("True","Bool","Can I symlink stage dir from work dir?",None)
        self.defaults["stage"]=stage_defaults

        self.monitor_defaults["base_dir"]=("/var/www/html/vofrontend/monitor","base_dir","Monitoring base dir",None)
        self.monitor_defaults["web_base_url"]=(None,"web_base_url","Monitoring base dir",None)
        self.defaults["monitor"]=self.monitor_defaults
        
        pool_collector_defaults=cWParams.commentedOrderedDict()
        pool_collector_defaults["node"]=(None,"nodename","Pool collector node name (for example, col1.my.org:9999)",None)
        pool_collector_defaults["DN"]=(None,"dn","Pool collector distinguised name (subject) (for example, /DC=org/DC=myca/OU=Services/CN=col1.my.org)",None)
        pool_collector_defaults["secondary"]=("False","Bool","Secondary nodes will be used by glideins, if present",None)
        pool_collector_defaults["group"]=("default","string","Collector group name useful to group HA setup",None)

        self.defaults["collectors"]=([],'List of pool collectors',"Each proxy collector contains",pool_collector_defaults)

        ccb_defaults=cWParams.commentedOrderedDict()
        ccb_defaults["node"]=(None,"nodename","CCB collector node name (for example, ccb1.my.org:9999)",None)
        ccb_defaults["DN"]=(None,"dn","CCB collector distinguised name (subject) (for example, /DC=org/DC=myca/OU=Services/CN=ccb1.my.org)",None)
        ccb_defaults["group"]=("default","string","CCB collector group name useful to group HA setup",None)
        self.defaults["ccbs"]=([],'List of CCB collectors',"Each CCB contains",ccb_defaults)



        self.defaults["security"]=copy.deepcopy(security_defaults)
        self.defaults["security"]["classad_proxy"]=(None,"fname","File name of the proxy used for talking to the WMS collector",None)
        self.defaults["security"]["proxy_DN"]=(None,"dn","Distinguised name (subject) of the proxy (for example, /DC=org/DC=myca/OU=Services/CN=fe1.my.org)",None)
        self.defaults["security"]["sym_key"]=("aes_256_cbc","sym_algo","Type of symetric key system used for secure message passing",None)

        self.defaults["match"]=copy.deepcopy(match_defaults)
        # change default match value
        # by default we want to look only for vanilla universe jobs that are not monitoring jobs
        self.defaults["match"]["job"]["query_expr"][0]='(JobUniverse==5)&&(GLIDEIN_Is_Monitor =!= TRUE)&&(JOB_Is_Monitor =!= TRUE)'

        self.defaults["attrs"]=sub_defaults['attrs']
        self.defaults["files"]=copy.deepcopy(sub_defaults['files'])
        # ordering is specific to global section of factory
        self.defaults["files"][3]["after_group"]=("False",'Bool','Should this file be loaded after the group ones?',None)

        global_config_defaults=cWParams.commentedOrderedDict()
        global_config_defaults['idle_vms_total']=copy.deepcopy(common_config_vms_total_defaults)
        global_config_defaults['idle_vms_total_global']=copy.deepcopy(common_config_vms_total_defaults)
        global_config_defaults['running_glideins_total']=copy.deepcopy(common_config_running_total_defaults)
        global_config_defaults['running_glideins_total_global']=copy.deepcopy(common_config_running_total_defaults)
        self.defaults["config"]=global_config_defaults

        self.defaults["groups"]=(xmlParse.OrderedDict(),"Dictionary of groups","Each group contains",self.group_defaults)
        
        # High Availability Configuration settings


        haf_defaults = cWParams.commentedOrderedDict()
        haf_defaults['frontend_name'] = (None, 'frontend_name',
                                         'Name of the frontend', None)

        ha_defaults = cWParams.commentedOrderedDict()
        ha_defaults['ha_frontends'] = ([], 'List of frontends in  HA mode',
                                       'Each element contains', haf_defaults)
        ha_defaults["enabled"]=('False', 'Bool', 'Enable HA?', None)
        ha_defaults["check_interval"]=('300', 'NR', 'How frequently should slav check if the master is down', None)
        #ha_defaults["activation_delay"]=('150', 'NR', 'How many sec to wait before slav activates after detecting that master is down', None)
        self.defaults['high_availability'] = ha_defaults


        return

    # return name of top element
    def get_top_element(self):
        return "frontend"

    def buildDir(self,frontendVersioning, basedir):
    # return either basedir or basedir/frontend_fename
        subdir = "frontend_%s" % self.frontend_name
        if frontendVersioning:
            return os.path.join(basedir, subdir)
        else:
            return basedir


    # validate data and add additional attributes if needed
    def derive(self):
        if len(self.groups.keys())==0:
            raise "No groups defined!"
            
        self.validate_names()

        frontendVersioning = False
        if self.data.has_key('frontend_versioning') and \
               self.data['frontend_versioning'].lower() == 'true':
            frontendVersioning = True
        self.stage_dir=self.buildDir(frontendVersioning, self.stage.base_dir)
        self.monitor_dir=self.buildDir(frontendVersioning, self.monitor.base_dir)
        self.work_dir=self.buildDir(frontendVersioning, self.work.base_dir)
        self.log_dir=self.buildDir(frontendVersioning, self.work.base_log_dir)
        self.web_url=self.buildDir(frontendVersioning, self.stage.web_base_url)
        if hasattr(self.monitor,"web_base_url") and (self.monitor.web_base_url is not None):
            self.monitoring_web_url=self.buildDir(frontendVersioning, self.monitor.web_base_url)
        else:
            self.monitoring_web_url=self.web_url.replace("stage","monitor")


        self.derive_match_attrs()

        ####################
        has_collector=self.attrs.has_key('GLIDEIN_Collector')
        if not has_collector:
            # collector not defined at global level, must be defined in every group
            has_collector=True
            for  group_name in self.groups.keys():
                has_collector&=self.groups[group_name].attrs.has_key('GLIDEIN_Collector')

        if has_collector:
            raise RuntimeError, "Attribute GLIDEIN_Collector cannot be defined by the user"

        ####################
        has_ccb=self.attrs.has_key('GLIDEIN_CCB')
        if not has_collector:
            # collector not defined at global level, must be defined in every group
            has_ccb=True
            for  group_name in self.groups.keys():
                has_ccb&=self.groups[group_name].attrs.has_key('GLIDEIN_CCB')

        if has_ccb:
            raise RuntimeError, "Attribute GLIDEIN_CCB cannot be defined by the user"

        ####################
        if self.security.proxy_DN is None:
            raise RuntimeError, "security.proxy_DN not defined"

        if len(self.collectors)==0:
            raise RuntimeError, "At least one pool collector is needed"

        ####################
        has_security_name=(self.security.security_name is not None)
        if not has_security_name:
            # security_name not defined at global level, look if defined in every group
            has_security_name=True
            for  group_name in self.groups.keys():
                has_security_name&=(self.groups[group_name].security.security_name is not None)

        if not has_security_name:
            # explicity define one, so it will not change if config copied
            # it also makes the frontend admins aware of the name
            self.data['security']['security_name']=self.frontend_name

        ####################
        for i in range(len(self.security.credentials)):
            pel=self.subparams.data['security']['credentials'][i]
            if pel['security_class'] is None:
                # define an explicit security, so the admin is aware of it
                pel['security_class']="frontend"
        group_names=self.groups.keys()
        for group_name in group_names:
            for i in range(len(self.groups[group_name].security.credentials)):
                pel=self.subparams.data['groups'][group_name]['security']['credentials'][i]
                if pel['security_class'] is None:
                    # define an explicit security, so the admin is aware of it
                    pel['security_class']="group_%s"%group_name

        # verify and populate HA
        if self.high_availability['enabled'].lower() == 'true':
            if (len(self.high_availability['ha_frontends']) == 1):
                haf = self.high_availability['ha_frontends'][0]
                if not haf['frontend_name']:
                    raise RuntimeError, 'High availability is enabled but the configuration is missing frontend_name of the master ha_frontend.'
            else:
                raise RuntimeError, 'Exactly one master ha_frontend information is needed when running this frontend in high_availability slave mode.'


    # verify match data and create the attributes if needed
    def derive_match_attrs(self):
        self.validate_match('frontend',self.match.match_expr,
                            self.match.factory.match_attrs,self.match.job.match_attrs,self.attrs)

        group_names=self.groups.keys()
        for group_name in group_names:
            # merge general and group matches
            attrs_dict={}
            for attr_name in self.attrs.keys():
                attrs_dict[attr_name]=self.attrs[attr_name]
            for attr_name in self.groups[group_name].attrs.keys():
                attrs_dict[attr_name]=self.groups[group_name].attrs[attr_name]
            factory_attrs={}
            for attr_name in self.match.factory.match_attrs.keys():
                factory_attrs[attr_name]=self.match.factory.match_attrs[attr_name]
            for attr_name in self.groups[group_name].match.factory.match_attrs.keys():
                factory_attrs[attr_name]=self.groups[group_name].match.factory.match_attrs[attr_name]
            job_attrs={}
            for attr_name in self.match.job.match_attrs.keys():
                job_attrs[attr_name]=self.match.job.match_attrs[attr_name]
            for attr_name in self.groups[group_name].match.job.match_attrs.keys():
                job_attrs[attr_name]=self.groups[group_name].match.job.match_attrs[attr_name]
            match_expr="(%s) and (%s)"%(self.match.match_expr,self.groups[group_name].match.match_expr)
            self.validate_match('group %s'%group_name,match_expr,
                                factory_attrs,job_attrs,attrs_dict)

        return

    # return xml formatting
    def get_xml_format(self):
        return {'lists_params':{'files':{'el_name':'file','subtypes_params':{'class':{}}},
                                'process_logs':{'el_name':'process_log','subtypes_params':{'class':{}}},
                                'collectors':{'el_name':'collector','subtypes_params':{'class':{}}},
                                'ccbs':{'el_name':'ccb','subtypes_params':{'class':{}}},
                                'schedds':{'el_name':'schedd','subtypes_params':{'class':{}}},
                                'ha_frontends':{'el_name':'ha_frontend','subtypes_params':{'class':{}}},
                                'credentials':{'el_name':'credential','subtypes_params':{'class':{}}}},
                'dicts_params':{'attrs':{'el_name':'attr','subtypes_params':{'class':{}}},
                                'groups':{'el_name':'group','subtypes_params':{'class':{}}},
                                'match_attrs':{'el_name':'match_attr','subtypes_params':{'class':{}}}}}

    def validate_names(self):
        # glidein name does not have a reasonable default
        if self.frontend_name is None:
            raise RuntimeError, "Missing frontend name"
        if self.frontend_name.find(' ')!=-1:
            raise RuntimeError, "Invalid frontend name '%s', contains a space."%self.frontend_name
        if not cWParams.is_valid_name(self.frontend_name):
            raise RuntimeError, "Invalid frontend name '%s', contains invalid characters."%self.frontend_name
        if self.frontend_name.find('.')!=-1:
            raise RuntimeError, "Invalid frontend name '%s', contains a point."%self.frontend_name

        group_names=self.groups.keys()
        for group_name in group_names:
            if group_name.find(' ')!=-1:
                raise RuntimeError, "Invalid group name '%s', contains a space."%group_name
            if not cWParams.is_valid_name(group_name):
                raise RuntimeError, "Invalid group name '%s', contains invalid characters."%group_name
            if group_name[:4]=='XPVO':
                raise RuntimeError, "Invalid group name '%s', starts with reserved sequence 'XPVO'."%group_name
            if group_name.find('.')!=-1:
                raise RuntimeError, "Invalid group name '%s', contains a point."%group_name

        attr_names=self.attrs.keys()
        for attr_name in attr_names:
            if not cWParams.is_valid_name(attr_name):
                raise RuntimeError, "Invalid global attribute name '%s'."%attr_name
        for group_name in group_names:
            attr_names=self.groups[group_name].attrs.keys()
            for attr_name in attr_names:
                if not cWParams.is_valid_name(attr_name):
                    raise RuntimeError, "Invalid group '%s' attribute name '%s'."%(group_name,attr_name)
        return

    def validate_match(self,loc_str,
                       match_str,factory_attrs,job_attrs,attr_dict):
        env={'glidein':{'attrs':{}},'job':{},'attr_dict':{}}
        for attr_name in factory_attrs.keys():
            attr_type=factory_attrs[attr_name]['type']
            if attr_type=='string':
                attr_val='a'
            elif attr_type=='int':
                attr_val=1
            elif attr_type=='bool':
                attr_val=True
            elif attr_type=='real':
                attr_val=1.0
            else:
                raise RuntimeError, "Invalid %s factory attr type '%s'"%(loc_str,attr_type)
            env['glidein']['attrs'][attr_name]=attr_val
        for attr_name in job_attrs.keys():
            attr_type=job_attrs[attr_name]['type']
            if attr_type=='string':
                attr_val='a'
            elif attr_type=='int':
                attr_val=1
            elif attr_type=='bool':
                attr_val=True
            elif attr_type=='real':
                attr_val=1.0
            else:
                raise RuntimeError, "Invalid %s job attr type '%s'"%(loc_str,attr_type)
            env['job'][attr_name]=attr_val
        for attr_name in attr_dict.keys():
            attr_type=attr_dict[attr_name]['type']
            if attr_type=='string':
                attr_val='a'
            elif attr_type=='int':
                attr_val=1
            elif attr_type=='expr':
                attr_val='a'
            else:
                raise RuntimeError, "Invalid %s attr type '%s'"%(loc_str,attr_type)
            env['attr_dict'][attr_name]=attr_val
        try:
            match_obj=compile(match_str,"<string>","eval")
            eval(match_obj,env)
        except KeyError, e:
            raise RuntimeError, "Invalid %s match_expr '%s': Missing attribute %s"%(loc_str,match_str,e)
        except Exception, e:
            raise RuntimeError, "Invalid %s match_expr '%s': %s"%(loc_str,match_str,e)
            
        return


    # return attribute value in the proper python format
    def extract_attr_val(self,attr_obj):
        return extract_attr_val(attr_obj)

    def get_subparams_class(self):
        return VOFrontendSubParams
    
####################################################################
# INTERNAL, do not use directly
# Use the class method instead
#
# return attribute value in the proper python format
def extract_attr_val(attr_obj):
    if (not attr_obj.type in ("string","int","expr")):
        raise RuntimeError, "Wrong attribute type '%s', must be either 'int', 'string' or 'expr'"%attr_obj.type
    
    if attr_obj.type in ("string","expr"):
        return str(attr_obj.value)
    else:
        return int(attr_obj.value)
