###########################################################
#
# Desscription:
#   This module contains the create_frontend params class
#
# Author:
#   Igor Sfiligoi
#
##########################################################

import os
import copy
import sys
import os.path
import string
import socket
import types
import traceback
import xmlParse
import condorExe
import cWParams


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
        self.attr_defaults["expression"]=("False","Bool","Is this a python expression (and not a simple value)?",None)

        group_config_defaults=cWParams.commentedOrderedDict()
        group_config_defaults['max_running_jobs']=('10000',"nr_jobs","What is the max number of running jobs I want to get to",None)
        
        group_config_glideins_defaults=cWParams.commentedOrderedDict()
        group_config_glideins_defaults["max"]=['100',"nr_jobs","How much pressure should I apply to the entry points",None]
        group_config_glideins_defaults["reserve"]=['5',"nr_jobs","How much to overcommit.",None]
        group_config_defaults['idle_glideins_per_entry']=group_config_glideins_defaults

        group_config_vms_defaults=cWParams.commentedOrderedDict()
        group_config_vms_defaults["max"]=['100',"nr_jobs","How many idle VMs should I tollerate, before stopping submitting glideins",None]
        group_config_vms_defaults["curb"]=['5',"nr_jobs","When to start curbing submissions.",None]
        group_config_defaults['idle_vms_per_entry']=group_config_vms_defaults

        # not exported and order does not matter, can stay a regular dictionary
        sub_defaults={'attrs':(xmlParse.OrderedDict(),'Dictionary of attributes',"Each attribute group contains",self.attr_defaults),
                      'files':([],'List of files',"Each file group contains",self.file_defaults)}

        query_attrs_defaults=cWParams.commentedOrderedDict()
        query_attrs_defaults['type']=('s','s|i|r|b','Attribute type',None)

        match_defaults=cWParams.commentedOrderedDict()
        match_defaults["factories"]=(none,'list of names','List of glidein factory collectors (like gf1.my.org,fg2.my.org:9999)',None)
        match_defaults["factory_query_expr"]=('True','CondorExpr','Expression for selecting user jobs',None)
        match_defaults["factory_match_attrs"]=(xmlParse.OrderedDict(),"Dictionary of ClassAd attributes","Each attribute contains",query_attrs_defaults)
        match_defaults["job_schedds"]=(none,'list of names','List of job schedds (like sb1.my.org,schedd_3@sb1.my.org)',None)
        match_defaults["job_query_expr"]=['True','CondorExpr','Expression for selecting user jobs',None]
        match_defaults["job_match_attrs"]=(xmlParse.OrderedDict(),"Dictionary of ClassAd attributes","Each attribute contains",query_attrs_defaults)
        match_defaults["match_expr"]=('True','PythonExpr', 'Expression for matching jobs to factory entries',None)

        self.group_defaults=cWParams.commentedOrderedDict()
        self.group_defaults["match"]=match_defaults
        self.group_defaults["enabled"]=("True","Bool","Is this group enabled?",None)
        self.group_defaults["config"]=group_config_defaults
        self.group_defaults["attrs"]=sub_defaults['attrs']
        self.group_defaults["files"]=sub_defaults['files']
        self.group_defaults["downtimes"]=self.downtimes_defaults
        

        ###############################
        # Start defining the defaults
        self.defaults["frontend_name"]=(socket.gethostname(),'ID', 'VO Frontend name',None)

        work_defaults=cWParams.commentedOrderedDict()
        work_defaults["base_dir"]=(os.environ["HOME"],"base_dir","Frontend base dir",None)
        self.defaults["work"]=work_defaults

        log_retention_defaults=cWParams.commentedOrderedDict()
        log_retention_defaults["min_days"]=["3.0","days","Min number of days the logs must be preserved (even if they use too much space)",None]
        log_retention_defaults["max_days"]=["7.0","days","Max number of days the logs should be preserved",None]
        log_retention_defaults["max_mbytes"]=["100.0","Mbytes","Max number of Mbytes the logs can use",None]
        self.defaults["log_retention"]=log_retention_defaults

        self.defaults['loop_delay']=('60','seconds', 'Number of seconds between iterations',None)
        self.defaults['advertise_delay']=('5','NR', 'Advertize evert NR loops',None)

        stage_defaults=cWParams.commentedOrderedDict()
        stage_defaults["base_dir"]=("/var/www/html/vofrontend/stage","base_dir","Stage base dir",None)
        stage_defaults["web_base_url"]=("http://%s/vofrontend/stage"%socket.gethostname(),'base_url','Base Web server URL',None)
        stage_defaults["use_symlink"]=("True","Bool","Can I symlink stage dir from work dir?",None)
        self.defaults["stage"]=stage_defaults

        monitor_opts_default=cWParams.commentedOrderedDict()
        monitor_opts_default["want_split_graphs"]=("True","Bool","Should create split graphs?",None)
        monitor_opts_default["want_trend_graphs"]=("True","Bool","Should create trend graphs?",None)
        monitor_opts_default["want_infoage_graphs"]=("True","Bool","Should create infoage graphs?",None)

        
        monitor_default=cWParams.commentedOrderedDict()
        monitor_default["base_dir"]=("/var/www/html/vofrontend/monitor","base_dir","Monitoring base dir",None)
        monitor_default["frontend"]=copy.deepcopy(monitor_opts_default)
        monitor_default["group"]=copy.deepcopy(monitor_opts_default)
        self.defaults["monitor"]=monitor_default
        
        security_default=cWParams.commentedOrderedDict()
        security_default["sym_key"]=("aes_256_cbc","sym_algo","Type of symetric key system used for secure message passing",None)
        security_default["x509_proxy"]=(None,"fname","Where the x509 proxy will be found (if None, use factory one)",None)
        
        self.defaults["security"]=security_default
        
        self.defaults["match"]=copy.deepcopy(match_defaults)
        # by default we want to look only for vanilla universe jobs that are not monitoring jobs
        self.defaults["match"]["job_query_expr"][0]='(JobUniverse==5)&&(GLIDEIN_Is_Monitor =!= TRUE)&&(JOB_Is_Monitor =!= TRUE)'

        self.defaults["downtimes"]=self.downtimes_defaults

        self.defaults["attrs"]=sub_defaults['attrs']
        self.defaults["files"]=copy.deepcopy(sub_defaults['files'])
        # ordering is specific to global section of factory
        self.defaults["files"][3]["after_group"]=("False",'Bool','Should this file be loaded after the group ones?',None)

        self.defaults["groups"]=(xmlParse.OrderedDict(),"Dictionary of groups","Each group contains",self.group_defaults)
        
        return

    # return name of top element
    def get_top_element(self):
        return "frontend"

    # validate data and add additional attributes if needed
    def derive(self):
        # glidein name does not have a reasonable default
        if self.frontend_name==None:
            raise RuntimeError, "Missing frontend name"
        if not cWParams.is_valid_name(self.frontend_name):
            raise RuntimeError, "Invalid frontend name '%s'"%self.frontend_name

        frontend_subdir="frontend_%s"%self.frontend_name
        self.stage_dir=os.path.join(self.stage.base_dir,frontend_subdir)
        self.monitor_dir=os.path.join(self.monitor.base_dir,frontend_subdir)
        self.work_dir=os.path.join(self.work.base_dir,frontend_subdir)
        self.web_url=os.path.join(self.stage.web_base_url,frontend_subdir)

        group_names=self.groups.keys()
        for group_name in group_names:
            if not cWParams.is_valid_name(group_name):
                raise RuntimeError, "Invalid group name '%s'"%group_name

    # return xml formatting
    def get_xml_format(self):
        return {'lists_params':{'files':{'el_name':'file','subtypes_params':{'class':{}}}},
                'dicts_params':{'attrs':{'el_name':'attr','subtypes_params':{'class':{}}},'groups':{'el_name':'group','subtypes_params':{'class':{}}}}}



############################################################
#
# P R I V A T E - Do not use
# 
############################################################


