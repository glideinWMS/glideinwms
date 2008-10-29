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

        group_config_defaults=xmlParse.OrderedDict()
        group_config_defaults['max_runnint_jobs']=('10000',"nr_jobs","Maximum number of concurrent glideins that should be running.",None)
        
        group_config_glideins_defaults=xmlParse.OrderedDict()
        group_config_glideins_defaults["max"]=['100',"nr_jobs","How much pressure should I apply to the entry points",None]
        group_config_glideins_defaults["reserve"]=['5',"nr_jobs","How much to overcommit.",None]
        group_config_defaults['idle_glideins_per_entry']=group_config_glideins_defaults

        group_config_vms_defaults=xmlParse.OrderedDict()
        group_config_vms_defaults["max"]=['100',"nr_jobs","How many idle VMs should I tollerate, before stopping submitting glideins",None]
        group_config_vms_defaults["curb"]=['5',"nr_jobs","When to start curbing submissions.",None]
        group_config_defaults['idle_vms_per_entry']=group_config_vms_defaults

        # not exported and order does not matter, can stay a regular dictionary
        sub_defaults={'attrs':(xmlParse.OrderedDict(),'Dictionary of attributes',"Each attribute group contains",self.attr_defaults),
                      'files':([],'List of files',"Each file group contains",self.file_defaults)}

        query_attrs_defaults=xmlParse.OrderedDict()
        query_attrs_defaults['type']=('s','s|i|r|b','Attribute type',None)

        match_defaults=xmlParse.OrderedDict()
        match_defaults["factory_query_expr"]=('True','CondorExpr','Expression for selecting user jobs',None)
        match_defaults["job_query_expr"]=['True','CondorExpr','Expression for selecting user jobs',None]
        match_defaults["job_query_attrs"]=(xmlParse.OrderedDict(),"Dictionary of ClassAd attributes","Each attribute contains",query_attrs_defaults)
        match_defaults["match_expr"]=('True','PythonExpr', 'Expression for matching jobs to factory entries',None)

        self.group_defaults=xmlParse.OrderedDict()
        self.group_defaults["match"]=match_defaults
        self.group_defaults["enabled"]=("True","Bool","Is this group enabled?",None)
        self.group_defaults["config"]=group_config_defaults
        self.group_defaults["attrs"]=sub_defaults['attrs']
        self.group_defaults["files"]=sub_defaults['files']
        self.group_defaults["downtimes"]=self.downtimes_defaults
        

        ###############################
        # Start defining the defaults
        self.defaults["frontend_name"]=(socket.gethostname(),'ID', 'VO Frontend name',None)

        submit_defaults=xmlParse.OrderedDict()
        submit_defaults["base_dir"]=(os.environ["HOME"],"base_dir","Submit base dir",None)
        self.defaults["submit"]=submit_defaults

        log_retention_defaults=xmlParse.OrderedDict()
        log_retention_defaults["min_days"]=["3.0","days","Min number of days the logs must be preserved (even if they use too much space)",None]
        log_retention_defaults["max_days"]=["7.0","days","Max number of days the logs should be preserved",None]
        log_retention_defaults["max_mbytes"]=["100.0","Mbytes","Max number of Mbytes the logs can use",None]
        self.defaults["log_retention"]=log_retention_defaults

        self.defaults['loop_delay']=('60','seconds', 'Number of seconds between iterations',None)
        self.defaults['advertise_delay']=('5','NR', 'Advertize evert NR loops',None)

        stage_defaults=xmlParse.OrderedDict()
        stage_defaults["base_dir"]=("/var/www/html/vofrontend/stage","base_dir","Stage base dir",None)
        stage_defaults["web_base_url"]=("http://%s/vofrontend/stage"%socket.gethostname(),'base_url','Base Web server URL',None)
        stage_defaults["use_symlink"]=("True","Bool","Can I symlink stage dir from submit dir?",None)
        self.defaults["stage"]=stage_defaults

        monitor_opts_default=xmlParse.OrderedDict()
        monitor_opts_default["want_split_graphs"]=("True","Bool","Should create split graphs?",None)
        monitor_opts_default["want_split_terminated_graphs"]=["False","Bool","Should create split terminated log graphs (CPU intensive)?",None]
        monitor_opts_default["want_trend_graphs"]=("True","Bool","Should create trend graphs?",None)
        monitor_opts_default["want_infoage_graphs"]=("True","Bool","Should create infoage graphs?",None)

        
        monitor_default=xmlParse.OrderedDict()
        monitor_default["base_dir"]=("/var/www/html/glidefactory/stage","base_dir","Monitoring base dir",None)
        monitor_default["factory"]=copy.deepcopy(monitor_opts_default)
        monitor_default["factory"]["want_split_terminated_graphs"][0]="True" # even if CPU intensive, it is just one
        monitor_default["group"]=copy.deepcopy(monitor_opts_default)
        self.defaults["monitor"]=monitor_default
        
        security_default=xmlParse.OrderedDict()
        security_default["pub_key"]=("None","None|RSA","Type of public key system used for secure message passing",None)
        security_default["key_length"]=("2048","bits","Key length in bits",None)
        security_default["allow_proxy"]=("factory,frontend","list","What proxies can be used for glidein submission? (list combination of factory,frontend)",None)
        
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

        glidein_subdir="glidein_%s"%self.glidein_name
        self.stage_dir=os.path.join(self.stage.base_dir,glidein_subdir)
        self.monitor_dir=os.path.join(self.monitor.base_dir,glidein_subdir)
        self.submit_dir=os.path.join(self.submit.base_dir,glidein_subdir)
        self.web_url=os.path.join(self.stage.web_base_url,glidein_subdir)

    # return xml formatting
    def get_xml_format(self):
        return {'lists_params':{'files':{'el_name':'file','subtypes_params':{'class':{}}},
                                'infosys_refs':{'el_name':'infosys_ref','subtypes_params':{'class':{}}}},
                'dicts_params':{'attrs':{'el_name':'attr','subtypes_params':{'class':{}}},'groups':{'el_name':'group','subtypes_params':{'class':{}}}}}



############################################################
#
# P R I V A T E - Do not use
# 
############################################################


