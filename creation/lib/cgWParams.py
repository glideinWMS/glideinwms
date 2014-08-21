#
# Project:
#   glideinWMS
#
# File Version: 
#
# Desscription:
#   This module contains the create_glidein params class
#
# Author:
#   Igor Sfiligoi
#

import os
import copy
import sys
import os.path
import string
import socket
import types
import traceback
from glideinwms.lib import xmlParse
from glideinwms.lib import condorExe
import cWParams


######################################################
class GlideinParams(cWParams.CommonParams):
    """
    Contains all the factory configuration values as params.  Used in create_glideins and recreate_glideins.
    """

    def init_defaults(self):
        """
        Populates the defaults for all the factory configuration values.
        """

        self.init_support_defaults()

        # Defaults for allowing frontends in a whitelist
        # in the factory config (per entry point)
        self.allow_defaults = cWParams.commentedOrderedDict()
        self.allow_defaults["name"] = (None, "string", "frontend name", None)
        self.allow_defaults["security_class"] = ("All", "string", "security class", None)


        # publishing specific to factory
        self.attr_defaults["publish"] = ("True", "Bool", "Should it be published by the factory?", None)
        self.attr_defaults["const"] = ("True", "Bool", "Should it be constant? (Else it can be overriden by the frontend. Used only if parameter is True.)", None)

        self.infosys_defaults = cWParams.commentedOrderedDict()
        self.infosys_defaults["type"] = (None, "RESS|BDII", "Type of information system", None)
        self.infosys_defaults["server"] = (None, "host", "Location of the infosys server", None)
        self.infosys_defaults["ref"] = (None, "id", "Referenced for the entry point in the infosys", None)

        self.mongroup_defaults = cWParams.commentedOrderedDict()
        self.mongroup_defaults["group_name"] = (None, "groupname", "Name of the monitoring group", None)

        entry_config_defaults = cWParams.commentedOrderedDict()

        entry_config_max_jobs_defaults = cWParams.commentedOrderedDict()
        max_jobs_per_entry_defaults = cWParams.commentedOrderedDict()
        max_jobs_per_entry_defaults["glideins"] = ('10000', "nr", "Maximum number of concurrent glideins (per entry) that can be submitted.", None)
        max_jobs_per_entry_defaults["idle"] = ('2000', "nr", "Maximum number of idle glideins (per entry) allowed.", None)
        max_jobs_per_entry_defaults["held"] = ('1000', "nr", "Maximum number of held glideins (per entry) before forcing the cleanup.", None)
        entry_config_max_jobs_defaults['per_entry'] = max_jobs_per_entry_defaults
        max_jobs_default_per_frontend_defaults = cWParams.commentedOrderedDict()
        max_jobs_default_per_frontend_defaults["glideins"] = ('5000', "nr", "Maximum number of concurrent glideins (default per frontend) that can be submitted.", None)
        max_jobs_default_per_frontend_defaults["idle"] = ('100', "nr", "Maximum number of idle glideins (default per frontend) allowed.", None)
        max_jobs_default_per_frontend_defaults["held"] = ('50', "nr", "Maximum number of held glideins (default per frontend) before forcing the cleanup.", None)
        entry_config_max_jobs_defaults['default_per_frontend'] = max_jobs_default_per_frontend_defaults
        max_jobs_per_frontend_defaults = cWParams.commentedOrderedDict()
        max_jobs_per_frontend_defaults["name"] = (None, "string", "frontend name", None)
        max_jobs_per_frontend_defaults["held"] = ('50', "nr", "Maximum number of held glideins (for this frontend) before forcing the cleanup.", None)
        max_jobs_per_frontend_defaults["idle"] = ('100', "nr", "Maximum number of idle glideins (for this frontend) allowed.", None)
        max_jobs_per_frontend_defaults["glideins"] = ('5000', "nr", "Maximum number of concurrent glideins (per frontend) that can be submitted", None)
        entry_config_max_jobs_defaults["per_frontends"] = (xmlParse.OrderedDict(), 'Dictionary of frontends', "Each frontend entry contains", max_jobs_per_frontend_defaults)
        entry_config_defaults['max_jobs'] = entry_config_max_jobs_defaults


        entry_config_restrictions_defaults=cWParams.commentedOrderedDict()
        entry_config_restrictions_defaults["require_voms_proxy"]=("False","Bool","Whether this entry point requires a voms proxy",None)
        entry_config_restrictions_defaults["require_glidein_glexec_use"]=("False","Bool","Whether this entry requires glidein to use glexec",None)
        entry_config_defaults['restrictions']=entry_config_restrictions_defaults


        entry_config_queue_defaults = cWParams.commentedOrderedDict()
        entry_config_queue_defaults["max_per_cycle"] = ['100', "nr", "Maximum number of jobs affected per cycle.", None]
        entry_config_queue_defaults["sleep"] = ['0.2', "seconds", "Sleep between interactions with the schedd.", None]

        entry_config_defaults['submit'] = copy.deepcopy(entry_config_queue_defaults)
        entry_config_defaults['submit']['cluster_size'] = ['10', "nr", "Max number of jobs submitted in a single transaction.", None]
        entry_config_defaults['submit']['slots_layout'] = ['fixed', "string", "The way multiple slots should be setup.", None]


        self.submit_attrs = cWParams.commentedOrderedDict()
        self.submit_attrs["value"] = ("All", "string", "HTCondor classad value", None)
        entry_config_defaults['submit']['submit_attrs'] = (xmlParse.OrderedDict(), 'Dictionary of submit attributes', "Each attribute contains", self.submit_attrs)


        entry_config_defaults['remove'] = copy.deepcopy(entry_config_queue_defaults)
        entry_config_defaults['remove']['max_per_cycle'][0] = '5'
        entry_config_defaults['release'] = copy.deepcopy(entry_config_queue_defaults)
        entry_config_defaults['release']['max_per_cycle'][0] = '20'

        # not exported and order does not matter, can stay a regular dictionary
        sub_defaults = {'attrs':(xmlParse.OrderedDict(), 'Dictionary of attributes', "Each attribute entry contains", self.attr_defaults),
                      'files':([], 'List of files', "Each file entry contains", self.file_defaults),
                      'infosys_refs':([], 'List of information system references', "Each reference points to this entry", self.infosys_defaults),
                      'monitorgroups':([], 'List of monitoring groups', "Each group entry belongs to", self.mongroup_defaults)}


        self.entry_defaults = cWParams.commentedOrderedDict()
        self.entry_defaults["gatekeeper"] = (None, 'gatekeeper', 'Grid gatekeeper/resource', None)
        self.entry_defaults["gridtype"] = ('gt2', 'grid_type', 'Condor Grid type', None)
        self.entry_defaults["trust_domain"] = ('OSG', 'trust_domain', 'Entry trust domain', None)
        self.entry_defaults["auth_method"] = ('grid_proxy', 'auth_method', 'Type of auth method this entry supports', None)
        self.entry_defaults["vm_id"] = (None, 'vm_id', 'VM id this entry supports', None)
        self.entry_defaults["vm_type"] = (None, 'vm_type', 'VM type this entry supports', None)
        self.entry_defaults["rsl"] = (None, 'RSL', 'Globus gt2 RSL option', None)
        self.entry_defaults['schedd_name'] = (None, "ScheddName", "Which schedd to use (Overrides the global one if specified)", None)
        self.entry_defaults["work_dir"] = (".", ".|Condor|OSG|TMPDIR", "Where to start glidein", None)
        self.entry_defaults['proxy_url'] = (None, 'proxy_url', "Squid cache to use", None)
        self.entry_defaults['verbosity'] = ('std', 'std|nodebug|fast', "Verbosity level and timeout setting", None)
        self.entry_defaults["enabled"] = ("True", "Bool", "Is this entry enabled?", None)
        self.entry_defaults["config"] = entry_config_defaults
        self.entry_defaults["attrs"] = sub_defaults['attrs']
        self.entry_defaults["files"] = sub_defaults['files']
        self.entry_defaults["infosys_refs"] = sub_defaults['infosys_refs']
        self.entry_defaults["monitorgroups"] = copy.deepcopy(sub_defaults['monitorgroups'])
        self.entry_defaults["allow_frontends"] = (xmlParse.OrderedDict(), 'Dictionary of frontends', "Each frontend entry contains", self.allow_defaults)

        ###############################
        # Start defining the defaults
        self.defaults["factory_name"] = (socket.gethostname(), 'ID', 'Factory name', None)
        self.defaults["glidein_name"] = (None, 'ID', 'Glidein name', None)
        self.defaults['schedd_name'] = ("schedd_glideins@%s" % socket.gethostname(), "ScheddName", "Which schedd to use, can be a comma separated list", None)
        self.defaults['factory_collector'] = (None, "CollectorName", "Which collector should we use for factory ClassAds", None)
        self.defaults['factory_versioning'] = ('True', 'Bool', 'Should we create versioned subdirectories?', None)

        submit_defaults = cWParams.commentedOrderedDict()
        submit_defaults["base_dir"] = ("%s/glideinsubmit" % os.environ["HOME"], "base_dir", "Submit base dir", None)
        submit_defaults["base_log_dir"] = ("%s/glideinlog" % os.environ["HOME"], "log_dir", "Submit base log dir", None)
        submit_defaults["base_client_log_dir"] = ("%s/glideclientlog" % os.environ["HOME"], "client_dir", "Base dir for client logs, needs a user_<uid> subdir per frontend user", None)
        submit_defaults["base_client_proxies_dir"] = ("%s/glideclientproxies" % os.environ["HOME"], "client_dir", "Base dir for client proxies, needs a user_<uid> subdir per frontend user", None)
        self.defaults["submit"] = submit_defaults

        one_log_retention_defaults = cWParams.commentedOrderedDict()
        one_log_retention_defaults["min_days"] = ["3.0", "days", "Min number of days the logs must be preserved (even if they use too much space)", None]
        one_log_retention_defaults["max_days"] = ["7.0", "days", "Max number of days the logs should be preserved", None]
        one_log_retention_defaults["max_mbytes"] = ["100.0", "Mbytes", "Max number of Mbytes the logs can use", None]

        monitor_footer_defaults=cWParams.commentedOrderedDict()
        monitor_footer_defaults["display_txt"] = ["", "string", "what will be displayed at the bottom of the monitoring page", None]
        monitor_footer_defaults["href_link"] = ["", "string", "where to link to", None]
        self.defaults["monitor_footer"] = monitor_footer_defaults

        process_log_defaults = copy.deepcopy(one_log_retention_defaults)
        process_log_defaults['extension'] = ["all", "string", "name of the log extention", None]
        process_log_defaults['msg_types'] = ["INFO, WARN, ERR", "string", "types of log messages", None]
        process_log_defaults['backup_count'] = ["5", "string", "Number of backup logs to keep", None]

        log_retention_defaults = cWParams.commentedOrderedDict()
        log_retention_defaults["process_logs"] = ([], 'Dictionary of log types', "Each log corresponds to a log file", copy.deepcopy(process_log_defaults))
        log_retention_defaults["job_logs"] = copy.deepcopy(one_log_retention_defaults)
        log_retention_defaults["job_logs"]["min_days"][0] = "2.0"
        self.defaults['advertise_with_tcp'] = ('True', 'Bool', 'Should condor_advertise use TCP connections?', None)
        self.defaults['advertise_with_multiple'] = ('True', 'Bool', 'Should condor_advertise use -multiple?', None)
        log_retention_defaults["summary_logs"] = copy.deepcopy(one_log_retention_defaults)
        log_retention_defaults["summary_logs"]["max_days"][0] = "31.0"
        log_retention_defaults["condor_logs"] = copy.deepcopy(one_log_retention_defaults)
        log_retention_defaults["condor_logs"]["max_days"][0] = "14.0"
        self.defaults["log_retention"] = log_retention_defaults

        self.defaults['loop_delay'] = ('60', 'seconds', 'Number of seconds between iterations', None)
        self.defaults['advertise_delay'] = ('5', 'NR', 'Advertize evert NR loops', None)
        self.defaults['restart_attempts'] = ('3', 'NR', 'Max allowed NR restarts every restart_interval before shutting down', None)
        self.defaults['restart_interval'] = ('1800', 'NR', 'Time interval NR sec which allow max restart attempts', None)
        self.defaults['entry_parallel_workers'] = ('0', 'NR', 'Number of entries that will perform the work in parallel', None)

        stage_defaults = cWParams.commentedOrderedDict()
        stage_defaults["base_dir"] = ("/var/www/html/glidefactory/stage", "base_dir", "Stage base dir", None)
        stage_defaults["web_base_url"] = ("http://%s/glidefactory/stage" % socket.gethostname(), 'base_url', 'Base Web server URL', None)
        stage_defaults["use_symlink"] = ("True", "Bool", "Can I symlink stage dir from submit dir?", None)
        self.defaults["stage"] = stage_defaults

        self.monitor_defaults["base_dir"] = ("/var/www/html/glidefactory/monitor", "base_dir", "Monitoring base dir", None)
        # Default for rrd update threads
        self.monitor_defaults["update_thread_count"]=(os.sysconf('SC_NPROCESSORS_ONLN'),"update_thread_count","Number of rrd update threads. Defaults to cpu count.",None)
        self.defaults["monitor"] = self.monitor_defaults

        self.frontend_sec_class_defaults = cWParams.commentedOrderedDict()
        self.frontend_sec_class_defaults["username"] = (None, 'username', 'UNIX ID to be used for this security class', None)

        self.frontend_defaults = cWParams.commentedOrderedDict()
        self.frontend_defaults["identity"] = (None, 'identity', 'Authenticated Identity', None)
        self.frontend_defaults["security_classes"] = (xmlParse.OrderedDict(), "Dictionary of security class maps", "Each mapping contains", self.frontend_sec_class_defaults)

        monitoring_collector_defaults=cWParams.commentedOrderedDict()
        monitoring_collector_defaults["node"]=(None,"nodename","Factory monitoring collector node name (for example, col1.my.org:9999)",None)
        monitoring_collector_defaults["DN"]=(None,"dn","Factory collector distinguised name (subject) (for example, /DC=org/DC=myca/OU=Services/CN=col1.my.org)",None)
        monitoring_collector_defaults["secondary"]=("False","Bool","Secondary nodes will be used by glideins, if present",None)
        monitoring_collector_defaults["group"]=("default","string","Collector group name useful to group HA setup",None)

        self.defaults["monitoring_collectors"]=([],'List of factory monitoring collectors',"Each collector contains",monitoring_collector_defaults)

        security_default=cWParams.commentedOrderedDict()
        security_default["pub_key"]=("RSA","None|RSA","Type of public key system used for secure message passing",None)
        security_default["reuse_oldkey_onstartup_gracetime"]=("900","seconds","Time in sec old key can be used to decrypt requests from frontend",None)
        security_default["remove_old_cred_freq"] = ("24", "hours", "Frequency in hrs for cleaning unused credentials", None)
        security_default["remove_old_cred_age"] = ("30", "days", "Credentials older than this should be removed", None)
        security_default["key_length"]=("2048","bits","Key length in bits",None)
        security_default["frontends"]=(xmlParse.OrderedDict(),"Dictionary of frontend","Each frontend contains",self.frontend_defaults)

        self.defaults["security"] = security_default

        condor_defaults = cWParams.commentedOrderedDict()
        condor_defaults["os"] = ("default", "osname", "Operating System (like linux-rhel3)", None)
        condor_defaults["arch"] = ("default", "arch", "Architecture (like x86)", None)
        condor_defaults["version"] = ("default", "arch", "Architecture (like x86)", None)
        condor_defaults["tar_file"] = (None, "fname", "Tarball containing condor binaries (overrides base_dir if defined)", None)
        condor_defaults["base_dir"] = (None, "base_dir", "Condor distribution base dir (used only if tar_file undefined)", None)

        self.defaults["condor_tarballs"] = ([], 'List of condor tarballs', "Each entry contains", condor_defaults)

        self.defaults["attrs"] = sub_defaults['attrs']
        self.defaults["files"] = copy.deepcopy(sub_defaults['files'])
        # ordering is specific to global section of factory
        self.defaults["files"][3]["after_entry"] = ("False", 'Bool', 'Should this file be loaded after the entry ones?', None)

        self.defaults["entries"] = (xmlParse.OrderedDict(), "Dictionary of entries", "Each entry contains", self.entry_defaults)

        return

    # return name of top element
    def get_top_element(self):
        return "glidein"

    def buildDir(self, factoryVersioning, basedir):
        # return either basedir or basedir/frontend_fename
        glidein_subdir="glidein_%s"%self.glidein_name
        if factoryVersioning:
            return os.path.join(basedir, glidein_subdir)
        else:
            return basedir

    # validate data and add additional attributes if needed
    def derive(self):
        # glidein name does not have a reasonable default
        if self.glidein_name is None:
            raise RuntimeError, "Missing glidein name"
        if not cWParams.is_valid_name(self.glidein_name):
            raise RuntimeError, "Invalid glidein name '%s'"%self.glidein_name

        if self.factory_collector=="default":
            raise RuntimeError, '"default" is a reserved keyword, cannot be used as factory_collector'

        factoryVersioning = False
        if self.data.has_key('factory_versioning') and \
               self.data['factory_versioning'].lower() == 'true':
            factoryVersioning = True

        self.stage_dir=self.buildDir(factoryVersioning, self.stage.base_dir)
        self.monitor_dir=self.buildDir(factoryVersioning, self.monitor.base_dir)
        self.submit_dir=self.buildDir(factoryVersioning, self.submit.base_dir)
        self.log_dir=self.buildDir(factoryVersioning, self.submit.base_log_dir)
        self.web_url=self.buildDir(factoryVersioning, self.stage.web_base_url)

        self.client_log_dirs={}
        self.client_proxies_dirs={}
        for fename in self.security.frontends.keys():
            if not cWParams.is_valid_name(fename):
                raise RuntimeError, "Invalid frontend name '%s'"%fename
            if ' ' in self.security.frontends[fename].identity:
                raise RuntimeError, "Invalid frontend identity '%s'"%self.security.frontends[fename].identity

            for scname in self.security.frontends[fename].security_classes.keys():
                username=self.security.frontends[fename].security_classes[scname].username
                self.client_log_dirs[username]=self.buildDir(True, os.path.join(self.submit.base_client_log_dir,"user_%s"%username))
                self.client_proxies_dirs[username]=self.buildDir(True, os.path.join(self.submit.base_client_proxies_dir,"user_%s"%username))

        if not cWParams.is_valid_name(self.factory_name):
            raise RuntimeError, "Invalid factory name '%s'"%self.factory_name

        entry_names=self.entries.keys()
        for entry_name in entry_names:
            if not cWParams.is_valid_name(entry_name):
                raise RuntimeError, "Invalid entry name '%s'"%entry_name

        attr_names=self.attrs.keys()
        for attr_name in attr_names:
            if not cWParams.is_valid_name(attr_name):
                raise RuntimeError, "Invalid global attribute name '%s'."%attr_name
        for entry_name in entry_names:
            attr_names=self.entries[entry_name].attrs.keys()
            for attr_name in attr_names:
                if not cWParams.is_valid_name(attr_name):
                    raise RuntimeError, "Invalid entry '%s' attribute name '%s'."%(entry_name,attr_name)

    # return xml formatting
    def get_xml_format(self):
        return {
            'lists_params':{
                'condor_tarballs':{'el_name':'condor_tarball', 'subtypes_params':{'class':{}}},
                'files':{'el_name':'file','subtypes_params':{'class':{}}},
                'process_logs':{'el_name':'process_log','subtypes_params':{'class':{}}},
                'monitorgroups':{'el_name':'monitorgroup','subtypes_params':{'class':{}}},
                'monitoring_collectors':{'el_name':'monitoring_collector','subtypes_params':{'class':{}}},
                'infosys_refs':{'el_name':'infosys_ref','subtypes_params':{'class':{}}}
            },
            'dicts_params':{
                'attrs':{'el_name':'attr','subtypes_params':{'class':{}}},
                'per_frontends':{'el_name':'per_frontend','subtypes_params':{'class':{}}},
                'entries':{'el_name':'entry','subtypes_params':{'class':{}}},
                'allow_frontends':{'el_name':'allow_frontend','subtypes_params':{'class':{}}},
                'frontends':{'el_name':'frontend','subtypes_params':{'class':{}}},
                'security_classes':{'el_name':'security_class','subtypes_params':{'class':{}}},
                'submit_attrs':{'el_name':'submit_attr','subtypes_params':{'class':{}}},
            }
        }

############################################################
#
# P R I V A T E - Do not use
# 
############################################################

#####################################
# try to find out the base condor dir
def find_condor_base_dir():
    if condorExe.condor_bin_path is None:
        return None
    else:
        return os.path.dirname(condorExe.condor_bin_path)

