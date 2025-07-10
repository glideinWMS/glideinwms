# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module contains the create_frontend params class"""

import copy
import os
import os.path
import socket

from glideinwms.lib.util import safe_boolcomp

# from collections import OrderedDict
from glideinwms.lib.xmlParse import OrderedDict

from . import cWParams

# from .matchPolicy import MatchPolicy


class VOFrontendSubParams(cWParams.CommonSubParams):
    # return attribute value in the proper python format
    def extract_attr_val(self, attr_obj):
        return extract_attr_val(attr_obj)


######################################################
# Params used by create_glideins and recreate_glideins
class VOFrontendParams(cWParams.CommonParams):
    # populate self.defaults
    def init_defaults(self):
        self.init_support_defaults()

        # VO scripts should start after the factory has been set completely
        # but there could be exceptions

        # Files/Validation/Custom scripts settings for frontend
        self.file_defaults["after_entry"] = (
            "True",
            "Bool",
            "Should this file be loaded after the factory entry ones?",
            None,
        )

        # Publishing attr specific to frontend
        self.attr_defaults["type"] = [
            "string",
            "string|int|expr",
            "What kind on data is value. (if expr, a python expression with access to frontend and glidein dictionaries)",
            None,
        ]

        # Config section exclusive to frontend group
        group_config_defaults = cWParams.CommentedOrderedDict()

        group_config_partitionable_glidein_defaults = cWParams.CommentedOrderedDict()
        group_config_partitionable_glidein_defaults["min_memory"] = [
            "2500",
            "MB",
            "Min memory in MB required for partitionable Glideins. If there is less, available (idle) cores are not counted.",
            None,
        ]
        group_config_defaults["partitionable_glidein"] = group_config_partitionable_glidein_defaults

        group_config_running_defaults = cWParams.CommentedOrderedDict()
        group_config_running_defaults["max"] = [
            "10000",
            "nr_jobs",
            "What is the max number of running glideins I want to get to",
            None,
        ]
        group_config_running_defaults["min"] = [
            "0",
            "nr_jobs",
            "Min number of running glideins with an empty/small queue.",
            None,
        ]
        group_config_running_defaults["relative_to_queue"] = [
            "1.15",
            "fraction",
            "Max relative to number of matching jobs in the queue.",
            None,
        ]
        group_config_defaults["running_glideins_per_entry"] = group_config_running_defaults
        common_config_ramp_up_attenuation_defaults = [
            "3",
            "float",
            "Glidein requests attenuation to favor stability and avoid over-provisioning. Idle requests are divided by this number.",
            None,
        ]
        group_config_defaults["ramp_up_attenuation"] = common_config_ramp_up_attenuation_defaults
        # This is a string because, we want to distinguish a value from missing (""), only a value overrides the corresponding  default or global setting
        group_config_defaults["ignore_down_entries"] = [
            "",
            "String",
            "If set to True or False the group setting will override the global value (or its default, False)."
            " When True the frontend will ignore down entries during matching counts",
            None,
        ]

        common_config_running_total_defaults = cWParams.CommentedOrderedDict()
        common_config_running_total_defaults["max"] = [
            "100000",
            "nr_jobs",
            "What is the max number of running glideins I want to get to - globally",
            None,
        ]
        common_config_running_total_defaults["curb"] = [
            "90000",
            "nr_jobs",
            "When should I start curbing glidein submission",
            None,
        ]
        group_config_defaults["running_glideins_total"] = common_config_running_total_defaults

        group_config_idle_defaults = cWParams.CommentedOrderedDict()
        group_config_idle_defaults["max"] = [
            "100",
            "nr_jobs",
            "How much pressure should I apply to the entry points",
            None,
        ]
        group_config_idle_defaults["reserve"] = ["5", "nr_jobs", "How much to overcommit.", None]
        group_config_defaults["idle_glideins_per_entry"] = group_config_idle_defaults

        group_config_lifetime_defaults = cWParams.CommentedOrderedDict()
        group_config_lifetime_defaults["max"] = [
            "0",
            "NR",
            "How long idle glideins are kept in the factory queue (seconds)",
            None,
        ]
        group_config_defaults["idle_glideins_lifetime"] = group_config_lifetime_defaults

        group_config_vms_defaults = cWParams.CommentedOrderedDict()
        group_config_vms_defaults["max"] = [
            "100",
            "nr_vms",
            "How many idle VMs should I tolerate, before stopping submitting glideins",
            None,
        ]
        group_config_vms_defaults["curb"] = [
            "5",
            "nr_vms",
            "How many idle VMs should I tolerate, before starting to curb submissions.",
            None,
        ]
        group_config_defaults["idle_vms_per_entry"] = group_config_vms_defaults

        # Global config section
        common_config_vms_total_defaults = cWParams.CommentedOrderedDict()
        common_config_vms_total_defaults["max"] = [
            "1000",
            "nr_jobs",
            "How many total idle VMs should I tolerate, before stopping submitting glideins",
            None,
        ]
        common_config_vms_total_defaults["curb"] = [
            "200",
            "nr_jobs",
            "How many total idle VMs should I tolerate, before starting to curb submissions.",
            None,
        ]
        group_config_defaults["idle_vms_total"] = common_config_vms_total_defaults

        group_config_proc_work_defaults = cWParams.CommentedOrderedDict()
        group_config_proc_work_defaults["matchmakers"] = [
            "3",
            "NR",
            "Max number of worker processes that will be doing the matchmaking",
            None,
        ]
        group_config_defaults["processing_workers"] = group_config_proc_work_defaults

        group_config_removal_defaults = cWParams.CommentedOrderedDict()
        group_config_removal_defaults["type"] = [
            "NO",
            "ALL|IDLE|WAIT|NO",
            "Trigger the removal of these glideins",
            None,
        ]
        group_config_removal_defaults["wait"] = [
            "0",
            "NR",
            "Time without requests to wait before triggering the removal (cycles)",
            None,
        ]
        group_config_removal_defaults["requests_tracking"] = [
            "False",
            "Bool",
            "Remove glideins as soon as the requests are less than the available glideins (instead of 0)",
            None,
        ]
        group_config_removal_defaults["margin"] = ["0", "NR", "How closely to follow the number of requests", None]
        group_config_defaults["glideins_removal"] = group_config_removal_defaults

        # not exported and order does not matter, can stay a regular dictionary
        sub_defaults = {
            "attrs": (OrderedDict(), "Dictionary of attributes", "Each attribute group contains", self.attr_defaults),
            "files": ([], "List of files", "Each file group contains", self.file_defaults),
        }

        # User Pool collectors
        collector_defaults = cWParams.CommentedOrderedDict()
        collector_defaults["node"] = (
            None,
            "nodename",
            "Factory collector node name (for example, fg2.my.org:9999)",
            None,
        )
        collector_defaults["DN"] = (
            None,
            "dn",
            "Factory collector distinguished name (subject) (for example, /DC=org/DC=myca/OU=Services/CN=fg2.my.org)",
            None,
        )
        collector_defaults["factory_identity"] = (
            "factory@fake.org",
            "authenticated_identity",
            "What is the AuthenticatedIdentity of the factory at the WMS collector",
            None,
        )
        collector_defaults["my_identity"] = (
            "me@fake.org",
            "authenticated_identity",
            "What is the AuthenticatedIdentity of my proxy at the WMS collector",
            None,
        )

        # User schedulers
        schedd_defaults = cWParams.CommentedOrderedDict()
        schedd_defaults["fullname"] = (None, "name", "User schedd name (for example, schedd_3@sb1.my.org)", None)
        schedd_defaults["DN"] = (
            None,
            "dn",
            "User schedd distinguished name (subject) (for example, /DC=org/DC=myca/OU=Services/CN=sb1.my.org)",
            None,
        )

        # match_attr for factory and job query_expr
        query_attrs_defaults = cWParams.CommentedOrderedDict()
        query_attrs_defaults["type"] = ("string", "string|int|real|bool", "Attribute type", None)

        # Factory and job query_expr
        fj_match_defaults = cWParams.CommentedOrderedDict()
        fj_match_defaults["query_expr"] = ["True", "CondorExpr", "Expression for selecting user jobs", None]
        fj_match_defaults["match_attrs"] = (
            OrderedDict(),
            "Dictionary of ClassAd attributes",
            "Each attribute contains",
            query_attrs_defaults,
        )

        # Factory match settings
        factory_match_defaults = copy.deepcopy(fj_match_defaults)
        factory_match_defaults["collectors"] = (
            [],
            "List of factory collectors",
            "Each collector contains",
            collector_defaults,
        )

        # Job match settings
        job_match_defaults = copy.deepcopy(fj_match_defaults)
        job_match_defaults["schedds"] = ([], "List of user schedds", "Each schedd contains", schedd_defaults)

        # Match section. Aka VO policies.
        match_defaults = cWParams.CommentedOrderedDict()
        match_defaults["factory"] = factory_match_defaults
        match_defaults["job"] = job_match_defaults
        match_defaults["match_expr"] = (
            "True",
            "PythonExpr",
            "Python expression for matching jobs to factory entries with access to job and glidein dictionaries",
            None,
        )
        match_defaults["start_expr"] = (
            "True",
            "CondorExpr",
            "Condor expression for matching jobs to glideins at runtime",
            None,
        )
        match_defaults["policy_file"] = (
            None,
            "PolicyFile",
            "External policy file where match_expr, query_expr, start_expr and match_attr are defined",
            None,
        )

        # Credential settings
        proxy_defaults = cWParams.CommentedOrderedDict()
        proxy_defaults["absfname"] = (None, "fname", "x509 proxy file name (see also pool_idx_list)", None)
        proxy_defaults["keyabsfname"] = (None, "fname", "for key files, file name of the key pair", None)
        proxy_defaults["pilotabsfname"] = (
            None,
            "fname",
            "to specify a different pilot proxy instead of using submit proxy",
            None,
        )
        proxy_defaults["type"] = (
            "grid_proxy",
            "credential type",
            "Type of credential: grid_proxy,cert_pair,key_pair,username_password,auth_file",
            None,
        )
        proxy_defaults["trust_domain"] = ("OSG", "grid_type", "Trust Domain", None)
        proxy_defaults["creation_script"] = (None, "command", "Script to re-create credential", None)
        proxy_defaults["update_frequency"] = (None, "int", "Update proxy when there is this much time left", None)
        proxy_defaults["remote_username"] = (None, "username", "User name at the remote resource", None)
        proxy_defaults["name"] = (
            None,
            "identifier",
            "Unique ID for the credential (defaults to absfname or generator)",
            None,
        )
        proxy_defaults["generator"] = (
            None,
            "module",
            "Python plug-in module containing the get_credential generator",
            None,
        )
        proxy_defaults["vm_id"] = (None, "vm_id", "VM Id", None)
        proxy_defaults["vm_type"] = (None, "vm_type", "VM Type", None)
        proxy_defaults["pool_idx_len"] = (
            None,
            "boolean",
            "Adds leading zeros to the suffix so all filenames the same length",
            None,
        )
        proxy_defaults["pool_idx_list"] = (None, "string", "List of indices, can include ranges of indices", None)
        proxy_defaults["security_class"] = (
            None,
            "id",
            "Proxies in the same security class can potentially access each other (Default: proxy_nr)",
            None,
        )
        proxy_defaults["vm_id_fname"] = (None, "fname", "to specify a vm id without reconfig", None)
        proxy_defaults["vm_type_fname"] = (None, "fname", "to specify a vm type without reconfig", None)
        proxy_defaults["project_id"] = (None, "string", "OSG Project ID. Ex TG-12345", None)

        security_defaults = cWParams.CommentedOrderedDict()
        security_defaults["proxy_selection_plugin"] = (
            None,
            "proxy_name",
            "Which credentials selection plugin should I use (ProxyAll if None)",
            None,
        )
        security_defaults["credentials"] = (
            [],
            "List of credentials",
            "Each credential element contains",
            proxy_defaults,
        )
        security_defaults["security_name"] = (
            None,
            "frontend_name",
            "What name will we advertise for security purposes?",
            None,
        )
        security_defaults["idtoken_lifetime"] = (
            None,
            "idtoken_lifetime",
            "The lifetime of the idtoken used connect WN startds to the VO collector (in hours)",
            None,
        )
        security_defaults["idtoken_keyname"] = (
            None,
            "idtoken_keyname",
            "The keyname used to generate the idtoken used by the startd to connect to the collector. also used for the filename.",
            None,
        )

        self.group_defaults = cWParams.CommentedOrderedDict()
        self.group_defaults["match"] = match_defaults
        self.group_defaults["enabled"] = ("True", "Bool", "Is this group enabled?", None)
        self.group_defaults["config"] = group_config_defaults
        self.group_defaults["attrs"] = sub_defaults["attrs"]
        self.group_defaults["files"] = sub_defaults["files"]
        self.group_defaults["security"] = copy.deepcopy(security_defaults)

        ###############################
        # Start defining the defaults
        self.defaults["downtimes_file"] = ("frontenddowntime", "string", "Frontend Downtime File", None)
        self.defaults["frontend_name"] = (socket.gethostname(), "ID", "VO Frontend name", None)
        self.defaults["frontend_versioning"] = (
            "True",
            "Bool",
            "Should we create versioned subdirectories of the type frontend_$frontend_name?",
            None,
        )

        self.defaults["frontend_monitor_index_page"] = (
            "True",
            "Bool",
            "Should we create an index.html in the monitoring web directory?",
            None,
        )

        work_defaults = cWParams.CommentedOrderedDict()
        work_defaults["base_dir"] = ("%s/frontstage" % os.environ["HOME"], "base_dir", "Frontend base dir", None)
        work_defaults["base_log_dir"] = ("%s/frontlogs" % os.environ["HOME"], "log_dir", "Frontend base log dir", None)
        self.defaults["work"] = work_defaults

        process_log_defaults = cWParams.CommentedOrderedDict()
        process_log_defaults["structured"] = ["False", "Bool", "True to use structured logs", None]
        process_log_defaults["min_days"] = [
            "3.0",
            "days",
            "Min number of days the logs must be preserved (even if they use too much space)",
            None,
        ]
        process_log_defaults["max_days"] = ["7.0", "days", "Max number of days the logs should be preserved", None]
        process_log_defaults["max_mbytes"] = ["100.0", "Mbytes", "Max number of Mbytes the logs can use", None]
        process_log_defaults["extension"] = ["all", "string", "name of the log extension", None]
        process_log_defaults["msg_types"] = ["INFO, WARN, ERR", "string", "types of log messages", None]
        process_log_defaults["backup_count"] = ["5", "string", "Number of backup logs to keep", None]
        process_log_defaults["compression"] = ["", "string", "Compression for backup log files", None]

        log_retention_defaults = cWParams.CommentedOrderedDict()
        log_retention_defaults["process_logs"] = (
            [],
            "Dictionary of log types",
            "Each log corresponds to a log file",
            copy.deepcopy(process_log_defaults),
        )
        self.defaults["log_retention"] = log_retention_defaults

        monitor_footer_defaults = cWParams.CommentedOrderedDict()
        monitor_footer_defaults["display_txt"] = [
            "",
            "string",
            "what will be displayed at the bottom of the monitoring page",
            None,
        ]
        monitor_footer_defaults["href_link"] = ["", "string", "where to link to", None]
        self.defaults["monitor_footer"] = monitor_footer_defaults

        self.defaults["loop_delay"] = ("60", "seconds", "Number of seconds between iterations", None)
        self.defaults["advertise_delay"] = ("5", "NR", "Advertise event NR loops", None)
        self.defaults["advertise_with_tcp"] = ("True", "Bool", "Should condor_advertise use TCP connections?", None)
        self.defaults["advertise_with_multiple"] = ("True", "Bool", "Should condor_advertise use -multiple?", None)
        self.defaults["enable_attribute_expansion"] = (
            "False",
            "Bool",
            "Should we expand attributes that contains a dollar?",
            None,
        )

        self.defaults["group_parallel_workers"] = (
            "2",
            "NR",
            "Max number of parallel workers that process the group policies",
            None,
        )

        self.defaults["restart_attempts"] = (
            "3",
            "NR",
            "Max allowed NR restarts every restart_interval before shutting down",
            None,
        )
        self.defaults["restart_interval"] = (
            "1800",
            "NR",
            "Time interval NR sec which allow max restart attempts",
            None,
        )

        stage_defaults = cWParams.CommentedOrderedDict()
        stage_defaults["base_dir"] = ("/var/www/html/vofrontend/stage", "base_dir", "Stage base dir", None)
        stage_defaults["web_base_url"] = (
            "http://%s/vofrontend/stage" % socket.gethostname(),
            "base_url",
            "Base Web server URL",
            None,
        )
        stage_defaults["use_symlink"] = ("True", "Bool", "Can I symlink stage dir from work dir?", None)
        self.defaults["stage"] = stage_defaults

        self.monitor_defaults["base_dir"] = (
            "/var/www/html/vofrontend/monitor",
            "base_dir",
            "Monitoring base dir",
            None,
        )
        self.monitor_defaults["web_base_url"] = (None, "web_base_url", "Monitoring base dir", None)
        self.defaults["monitor"] = self.monitor_defaults

        pool_collector_defaults = cWParams.CommentedOrderedDict()
        pool_collector_defaults["node"] = (
            None,
            "nodename",
            "Pool collector node name (for example, col1.my.org:9999)",
            None,
        )
        pool_collector_defaults["DN"] = (
            None,
            "dn",
            "Pool collector distinguished name (subject) (for example, /DC=org/DC=myca/OU=Services/CN=col1.my.org)",
            None,
        )
        pool_collector_defaults["secondary"] = (
            "False",
            "Bool",
            "Secondary nodes will be used by glideins, if present",
            None,
        )
        pool_collector_defaults["group"] = ("default", "string", "Collector group name useful to group HA setup", None)

        self.defaults["collectors"] = (
            [],
            "List of pool collectors",
            "Each proxy collector contains",
            pool_collector_defaults,
        )

        ccb_defaults = cWParams.CommentedOrderedDict()
        ccb_defaults["node"] = (None, "nodename", "CCB collector node name (for example, ccb1.my.org:9999)", None)
        ccb_defaults["DN"] = (
            None,
            "dn",
            "CCB collector distinguished name (subject) (for example, /DC=org/DC=myca/OU=Services/CN=ccb1.my.org)",
            None,
        )
        ccb_defaults["group"] = ("default", "string", "CCB collector group name useful to group HA setup", None)
        self.defaults["ccbs"] = ([], "List of CCB collectors", "Each CCB contains", ccb_defaults)

        self.defaults["security"] = copy.deepcopy(security_defaults)
        self.defaults["security"]["classad_proxy"] = (
            None,
            "fname",
            "File name of the proxy used for talking to the WMS collector",
            None,
        )
        self.defaults["security"]["proxy_DN"] = (
            None,
            "dn",
            "Distinguished name (subject) of the proxy (for example, /DC=org/DC=myca/OU=Services/CN=fe1.my.org)",
            None,
        )
        self.defaults["security"]["sym_key"] = (
            "aes_256_cbc",
            "sym_algo",
            "Type of symmetric key system used for secure message passing",
            None,
        )

        self.defaults["match"] = copy.deepcopy(match_defaults)
        # Change default match value
        # By default we want to look only for vanilla universe jobs
        # that are not monitoring jobs
        self.defaults["match"]["job"]["query_expr"][
            0
        ] = "(JobUniverse==5)&&(GLIDEIN_Is_Monitor =!= TRUE)&&(JOB_Is_Monitor =!= TRUE)"

        self.defaults["attrs"] = sub_defaults["attrs"]
        self.defaults["files"] = copy.deepcopy(sub_defaults["files"])
        # ordering is specific to global section of factory
        self.defaults["files"][3]["after_group"] = (
            "False",
            "Bool",
            "Should this file be loaded after the group ones?",
            None,
        )

        global_config_defaults = cWParams.CommentedOrderedDict()
        global_config_defaults["ramp_up_attenuation"] = copy.deepcopy(common_config_ramp_up_attenuation_defaults)
        global_config_defaults["ignore_down_entries"] = [
            "False",
            "Bool",
            "If set the frontend will ignore down entries during matching counts",
            None,
        ]
        global_config_defaults["idle_vms_total"] = copy.deepcopy(common_config_vms_total_defaults)
        global_config_defaults["idle_vms_total_global"] = copy.deepcopy(common_config_vms_total_defaults)
        global_config_defaults["running_glideins_total"] = copy.deepcopy(common_config_running_total_defaults)
        global_config_defaults["running_glideins_total_global"] = copy.deepcopy(common_config_running_total_defaults)
        self.defaults["config"] = global_config_defaults

        self.defaults["groups"] = (OrderedDict(), "Dictionary of groups", "Each group contains", self.group_defaults)

        # TODO: to be removed, used only by an unused method
        # Initialize the external policy modules data structure
        self.match_policy_modules = {
            "frontend": None,
            "groups": {},
        }

        # High Availability Configuration settings
        haf_defaults = cWParams.CommentedOrderedDict()
        haf_defaults["frontend_name"] = (None, "frontend_name", "Name of the frontend", None)

        ha_defaults = cWParams.CommentedOrderedDict()
        ha_defaults["ha_frontends"] = ([], "List of frontends in  HA mode", "Each element contains", haf_defaults)
        ha_defaults["enabled"] = ("False", "Bool", "Enable HA?", None)
        ha_defaults["check_interval"] = ("300", "NR", "How frequently should slav check if the master is down", None)
        # ha_defaults["activation_delay"]=('150', 'NR', 'How many sec to wait before slav activates after detecting that master is down', None)
        self.defaults["high_availability"] = ha_defaults

        return

    # return name of top element
    def get_top_element(self):
        return "frontend"

    def buildDir(self, frontendVersioning, basedir):
        # return either basedir or basedir/frontend_fename
        subdir = "frontend_%s" % self.frontend_name
        if frontendVersioning:
            return os.path.join(basedir, subdir)
        else:
            return basedir

    # validate data and add additional attributes if needed
    def derive(self):
        if len(list(self.groups.keys())) == 0:
            raise ValueError("No groups defined!")

        self.validate_names()

        frontendVersioning = False
        if "frontend_versioning" in self.data and safe_boolcomp(self.data["frontend_versioning"], True):
            frontendVersioning = True
        self.stage_dir = self.buildDir(frontendVersioning, self.stage.base_dir)
        self.monitor_dir = self.buildDir(frontendVersioning, self.monitor.base_dir)
        self.work_dir = self.buildDir(frontendVersioning, self.work.base_dir)
        self.log_dir = self.buildDir(frontendVersioning, self.work.base_log_dir)
        self.web_url = self.buildDir(frontendVersioning, self.stage.web_base_url)
        # print ("MMDB: %s, %s" % (type(self.monitor), self.monitor.data))
        if hasattr(self.monitor, "web_base_url") and (self.monitor.web_base_url is not None):
            self.monitoring_web_url = self.buildDir(frontendVersioning, self.monitor.web_base_url)
        else:
            self.monitoring_web_url = self.web_url.replace("stage", "monitor")

        # moved to cvWParamsDict after expansion:  self.derive_match_attrs()

        ####################
        has_collector = "GLIDEIN_Collector" in self.attrs
        if not has_collector:
            # collector not defined at global level, must be defined in every group
            has_collector = True
            for group_name in list(self.groups.keys()):
                has_collector &= "GLIDEIN_Collector" in self.groups[group_name].attrs

        if has_collector:
            raise RuntimeError("Attribute GLIDEIN_Collector cannot be defined by the user")

        ####################
        # MM TODO: should CCB be checked? it falls back to collector if missing (and collector is guaranteed from above)
        has_ccb = "GLIDEIN_CCB" in self.attrs
        if not has_collector:  # MM TODO: should this be has_ccb? But again, see above
            # collector not defined at global level, must be defined in every group
            has_ccb = True
            for group_name in list(self.groups.keys()):
                has_ccb &= "GLIDEIN_CCB" in self.groups[group_name].attrs

        if has_ccb:
            raise RuntimeError("Attribute GLIDEIN_CCB cannot be defined by the user")

        # issue 66, proceed if no proxy, assume JWT
        # if self.security.proxy_DN is None:
        #    raise RuntimeError("security.proxy_DN not defined")

        if len(self.collectors) == 0:
            raise RuntimeError("At least one pool collector is needed")

        ####################
        has_security_name = self.security.security_name is not None
        if not has_security_name:
            # security_name not defined at global level, look if defined in every group
            has_security_name = True
            for group_name in list(self.groups.keys()):
                has_security_name &= self.groups[group_name].security.security_name is not None

        if not has_security_name:
            # explicitly define one, so it will not change if config copied
            # it also makes the frontend admins aware of the name
            self.data["security"]["security_name"] = self.frontend_name

        ####################
        for i in range(len(self.security.credentials)):
            pel = self.subparams.data["security"]["credentials"][i]
            if pel["security_class"] is None:
                # define an explicit security, so the admin is aware of it
                pel["security_class"] = "frontend"
        group_names = list(self.groups.keys())
        for group_name in group_names:
            for i in range(len(self.groups[group_name].security.credentials)):
                pel = self.subparams.data["groups"][group_name]["security"]["credentials"][i]
                if pel["security_class"] is None:
                    # define an explicit security, so the admin is aware of it
                    pel["security_class"] = "group_%s" % group_name

        # verify and populate HA
        if safe_boolcomp(self.high_availability["enabled"], True):
            if len(self.high_availability["ha_frontends"]) == 1:
                haf = self.high_availability["ha_frontends"][0]
                if not haf["frontend_name"]:
                    raise RuntimeError(
                        "High availability is enabled but the configuration is missing frontend_name of the master ha_frontend."
                    )
            else:
                raise RuntimeError(
                    "Exactly one master ha_frontend information is needed when running this frontend in high_availability slave mode."
                )

    def get_xml_format(self):
        """
        Return xml formatting for the config
        """
        return {
            "lists_params": {
                "files": {"el_name": "file", "subtypes_params": {"class": {}}},
                "process_logs": {"el_name": "process_log", "subtypes_params": {"class": {}}},
                "collectors": {"el_name": "collector", "subtypes_params": {"class": {}}},
                "ccbs": {"el_name": "ccb", "subtypes_params": {"class": {}}},
                "schedds": {"el_name": "schedd", "subtypes_params": {"class": {}}},
                "ha_frontends": {"el_name": "ha_frontend", "subtypes_params": {"class": {}}},
                "credentials": {"el_name": "credential", "subtypes_params": {"class": {}}},
            },
            "dicts_params": {
                "attrs": {"el_name": "attr", "subtypes_params": {"class": {}}},
                "groups": {"el_name": "group", "subtypes_params": {"class": {}}},
                "match_attrs": {"el_name": "match_attr", "subtypes_params": {"class": {}}},
            },
        }

    def validate_names(self):
        """
        Validate frontend, group name and attr name
        """

        # glidein name does not have a reasonable default
        if self.frontend_name is None:
            raise RuntimeError("Missing frontend name")
        if self.frontend_name.find(" ") != -1:
            raise RuntimeError("Invalid frontend name '%s', contains a space." % self.frontend_name)
        if not cWParams.is_valid_name(self.frontend_name):
            raise RuntimeError("Invalid frontend name '%s', contains invalid characters." % self.frontend_name)
        if self.frontend_name.find(".") != -1:
            raise RuntimeError("Invalid frontend name '%s', contains a point." % self.frontend_name)

        group_names = list(self.groups.keys())
        for group_name in group_names:
            if group_name.find(" ") != -1:
                raise RuntimeError("Invalid group name '%s', contains a space." % group_name)
            if not cWParams.is_valid_name(group_name):
                raise RuntimeError("Invalid group name '%s', contains invalid characters." % group_name)
            if group_name[:4] == "XPVO":
                raise RuntimeError("Invalid group name '%s', starts with reserved sequence 'XPVO'." % group_name)
            if group_name.find(".") != -1:
                raise RuntimeError("Invalid group name '%s', contains a point." % group_name)

        attr_names = list(self.attrs.keys())
        for attr_name in attr_names:
            if not cWParams.is_valid_name(attr_name):
                raise RuntimeError("Invalid global attribute name '%s'." % attr_name)
        for group_name in group_names:
            attr_names = list(self.groups[group_name].attrs.keys())
            for attr_name in attr_names:
                if not cWParams.is_valid_name(attr_name):
                    raise RuntimeError(f"Invalid group '{group_name}' attribute name '{attr_name}'.")
        return

    # return attribute value in the proper python format
    def extract_attr_val(self, attr_obj):
        return extract_attr_val(attr_obj)

    def get_subparams_class(self):
        return VOFrontendSubParams

    # TODO: to be removed, this method seems unused
    def update_match_attrs(self):
        # Load global match_attrs from externally loaded match_policies
        if self.match_policy_modules["frontend"]:
            if self.match_policy_modules["frontend"].factoryMatchAttrs:
                self.match.factory.match_attrs.data = self.match_policy_modules["frontend"].factoryMatchAttrs
            if self.match_policy_modules["frontend"].jobMatchAttrs:
                self.match.job.match_attrs.data = self.match_policy_modules["frontend"].jobMatchAttrs

        # Load group match_attrs from externally loaded match_policies
        for group_name in list(self.groups.keys()):
            # Shorthand for easy access
            group_module = self.match_policy_modules["groups"].get(group_name)
            if group_module:
                if group_module.factoryMatchAttrs:
                    self.groups[group_name].match.factory.match_attrs.data = group_module.factoryMatchAttrs
                if group_module.jobMatchAttrs:
                    self.groups[group_name].match.job.match_attrs.data = group_module.jobMatchAttrs


####################################################################
# INTERNAL, do not use directly
# Use the class method instead
####################################################################


# return attribute value in the proper python format
def extract_attr_val(attr_obj):
    if attr_obj.type not in ("string", "int", "expr"):
        raise RuntimeError("Wrong attribute type '%s', must be either 'int', 'string' or 'expr'" % attr_obj.type)

    if attr_obj.type in ("string", "expr"):
        return str(attr_obj.value)
    else:
        return int(attr_obj.value)
