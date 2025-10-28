# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import os
import xml.sax

import glideinwms.factory.glideFactorySelectionAlgorithms

from . import xmlConfig

ENTRY_INDENT = 6
CONFIG_DIR = "config.d"
FACTORY_DEFAULTS_XML = "factory_defaults.xml"

xmlConfig.register_list_elements(
    {
        "allow_frontends": lambda d: d["name"],
        "condor_tarballs": lambda d: "{},{},{}".format(d["arch"], d["os"], d["version"]),
        "entries": lambda d: d["name"],
        "entry_sets": lambda d: d["alias"],
        "frontends": lambda d: d["name"],
        "infosys_refs": lambda d: d["ref"],
        "monitorgroups": lambda d: d["group_name"],
        "monitoring_collectors": lambda d: d["DN"],
        "per_frontends": lambda d: d["name"],
        "process_logs": lambda d: d["extension"],
        "security_classes": lambda d: d["username"],
        "submit_attrs": lambda d: d["name"],
    }
)


# TODO: add a way to check for multi-attr constraints:
# TODO: e.g. GLIDEIN_ESTIMATED_CPUS should not be set if GLIDEIN_CPUS is not set or GLIDEIN_CPUS > 0
class FactAttrElement(xmlConfig.AttrElement):
    def validate(self):
        super().validate()
        self.check_boolean("const")
        self.check_boolean("publish")
        is_publish = eval(self["publish"])
        is_const = eval(self["const"])
        is_param = eval(self["parameter"])

        if is_publish and (not is_const and not is_param):
            raise RuntimeError(self.err_str('published attribute must either be "parameter" or "const"'))
        if not is_publish and (not is_const or not is_param):
            raise RuntimeError(self.err_str('unpublished attribute must be "const" "parameter"'))
        self.check_overwrite_soundness()

    def check_overwrite_soundness(self):
        """If the attribute is defined in the global attributes section then
        check that the "const" key is True/False for both
        """
        config = self.get_config_node()
        try:
            attrs = config.get_child("attrs")
        except KeyError:
            # No need to check if the configuration has no global attribute section
            return
        for att in attrs.get_children():
            if att["name"] == self["name"] and att["const"] != self["const"]:
                entry = "Global section" if isinstance(self.parent.parent, Config) else self.parent.parent.getName()
                raise RuntimeError(
                    '%s: attribute %s is already defined in the global section, but it is const="%s". '
                    "Please make sure the 'const' value is the same." % (entry, self["name"], att["const"])
                )


xmlConfig.register_tag_classes({"attr": FactAttrElement})


class FactFileElement(xmlConfig.FileElement):
    def validate(self):
        super().validate()
        # only defined in factory global entries
        if "after_entry" in self:
            self.check_boolean("after_entry")


xmlConfig.register_tag_classes({"file": FactFileElement})


class CondTarElement(xmlConfig.DictElement):
    def validate(self):
        if "tar_file" not in self and "base_dir" not in self:
            raise RuntimeError(self.err_str('must either define "tar_file" or "base_dir"'))


xmlConfig.register_tag_classes({"condor_tarball": CondTarElement})


class FrontendElement(xmlConfig.DictElement):
    def validate(self):
        self.check_missing("name")
        self.check_missing("identity")
        for sc in self.get_child_list("security_classes"):
            sc.check_missing("username")


xmlConfig.register_tag_classes({"frontend": FrontendElement})


class EntryElement(xmlConfig.DictElement):
    def validate(self):
        self.check_missing("name")
        self.check_missing("gatekeeper")
        self.check_boolean("enabled")
        # Using parent.parent because EntryElements are inside the <entries> tag
        # Hence the EntrySetElement is parent.parent
        if isinstance(self.parent.parent, EntrySetElement):
            # no need to check more if the parent is an entryset
            return
        self.validate_sub_elements()

    def validate_sub_elements(self):
        for per_fe in self.get_child("config").get_child("max_jobs").get_child_list("per_frontends"):
            per_fe.check_missing("name")
        for submit_attr in self.get_child("config").get_child("submit").get_child_list("submit_attrs"):
            submit_attr.check_missing("name")
        for allowed_fe in self.get_child_list("allow_frontends"):
            allowed_fe.check_missing("name")
        for infosys in self.get_child_list("infosys_refs"):
            infosys.check_missing("ref")
            infosys.check_missing("server")
            infosys.check_missing("type")
        for group in self.get_child_list("monitorgroups"):
            group.check_missing("group_name")

    def getName(self):
        return self["name"]


xmlConfig.register_tag_classes({"entry": EntryElement})


class EntrySetElement(EntryElement):
    def validate(self):
        self.check_missing("alias")
        self.check_boolean("enabled")
        self.validate_sub_elements()
        algo_name = self.get_child("config").children.get("entry_selection", {}).get("algorithm_name")
        if algo_name:
            if not (getattr(glideinwms.factory.glideFactorySelectionAlgorithms, "selectionAlgo" + algo_name, None)):
                raise RuntimeError(
                    "Function name selectionAlgo%s not found in the glideFactorySelectionAlgorithms module" % algo_name
                )

    def select(self, entry):
        self.selected_entry = entry

    def __contains__(self, item):
        try:
            _ = self[item]
            return True
        except KeyError:
            return False

    def __getitem__(self, attrname):
        if getattr(self, "selected_entry", False) and attrname in self.selected_entry:
            val = self.selected_entry[attrname]
        else:
            val = self.attrs.get(attrname)
        if val is None and attrname in self.get_child_list("entries")[0]:
            val = self.get_child_list("entries")[0][attrname]
        #            val = [ x[attrname] for x in self.get_child_list(u'entries') ]
        return val

    def get_subentries(self):
        return self.get_child_list("entries")

    def getName(self):
        """The name for entry sets is actually called alias"""
        return self["alias"]


xmlConfig.register_tag_classes({"entry_set": EntrySetElement})


class CvmfsexecDistroElement(xmlConfig.DictElement):
    def validate(self):
        # Using 'sources' attribute in the <cvmfsexec_distro> tag to control the enable/disable of building/rebuilding cvmfsexec distributions
        if not self.getSources():
            if self.getPlatforms():
                raise RuntimeError(
                    self.err_str(
                        "'platforms' attribute cannot have a value when 'sources' attribute is empty. \nTo add a cvmfsexec distribution, 'sources' must be a single value or a comma-separated list of values from the following options: {osg, egi, default}."
                    )
                )
        else:
            if not self.getPlatforms():
                self.setPlatforms()

    def getSources(self):
        return self["sources"]

    def getPlatforms(self):
        return self["platforms"]

    def setPlatforms(self):
        # TODO: periodically add rhel, suse and other derivatives as supported by cvmfsexec
        # NOTE: Although rhel9-x86_64 is supported, el7 tools might not work with el9 files (as suggested by Dave Dykstra) as of July 03, 2023
        self["platforms"] = "rhel9-x86_64,rhel8-x86_64,rhel7-x86_64,suse15-x86_64,rhel8-aarch64,rhel8-ppc64le"


xmlConfig.register_tag_classes({"cvmfsexec_distro": CvmfsexecDistroElement})


class Config(xmlConfig.DictElement):
    def __init__(self, tag, *args, **kwargs):
        super().__init__(tag, *args, **kwargs)

        # dir paths should be set after validation in parse function
        self.submit_dir = None
        self.stage_dir = None
        self.monitor_dir = None
        self.log_dir = None
        self.client_log_dirs = None
        self.client_proxy_dirs = None
        self.web_url = None

    def validate(self):
        self.check_missing("factory_name")
        self.check_boolean("factory_versioning")
        for mon_coll in self.get_child_list("monitoring_collectors"):
            mon_coll.check_missing("DN")
            mon_coll.check_missing("node")
        self.check_recoverable_exitcodes()

    def check_recoverable_exitcodes(self):
        try:
            for codestr in self.get("recoverable_exitcodes", "").split(","):
                if not codestr:
                    continue
                splitstr = codestr.split(" ")
                for subcode in splitstr:
                    int(subcode)
        except ValueError:
            raise RuntimeError("recoverable_exitcodes should be list of integers. See configuration.html for more info")

    #######################
    #
    # FactoryXmlConfig setter functions
    #
    ######################
    def set_submit_dir(self):
        if eval(self["factory_versioning"]):
            self.submit_dir = os.path.join(self.get_child("submit")["base_dir"], "glidein_%s" % self["glidein_name"])
        else:
            self.submit_dir = self.get_child("submit")["base_dir"]

    def set_stage_dir(self):
        if eval(self["factory_versioning"]):
            self.stage_dir = os.path.join(self.get_child("stage")["base_dir"], "glidein_%s" % self["glidein_name"])
        else:
            self.stage_dir = self.get_child("stage")["base_dir"]

    def set_monitor_dir(self):
        if eval(self["factory_versioning"]):
            self.monitor_dir = os.path.join(self.get_child("monitor")["base_dir"], "glidein_%s" % self["glidein_name"])
        else:
            self.monitor_dir = self.get_child("monitor")["base_dir"]

    def set_log_dir(self):
        if eval(self["factory_versioning"]):
            self.log_dir = os.path.join(self.get_child("submit")["base_log_dir"], "glidein_%s" % self["glidein_name"])
        else:
            self.log_dir = self.get_child("submit")["base_log_dir"]

    def set_client_log_dirs(self):
        self.client_log_dirs = {}
        client_dir = self.get_child("submit")["base_client_log_dir"]
        glidein_name = self["glidein_name"]
        for fe in self.get_child("security").get_child_list("frontends"):
            for sc in fe.get_child_list("security_classes"):
                self.client_log_dirs[sc["username"]] = os.path.join(
                    client_dir, "user_%s" % sc["username"], "glidein_%s" % glidein_name
                )

    def set_client_proxy_dirs(self):
        self.client_proxy_dirs = {}
        client_dir = self.get_child("submit")["base_client_proxies_dir"]
        glidein_name = self["glidein_name"]
        for fe in self.get_child("security").get_child_list("frontends"):
            for sc in fe.get_child_list("security_classes"):
                self.client_proxy_dirs[sc["username"]] = os.path.join(
                    client_dir, "user_%s" % sc["username"], "glidein_%s" % glidein_name
                )

    def set_web_url(self):
        if eval(self["factory_versioning"]):
            self.web_url = os.path.join(self.get_child("stage")["web_base_url"], "glidein_%s" % self["glidein_name"])
        else:
            self.web_url = self.get_child("stage")["web_base_url"]

    def set_num_factories(self):
        if eval(self["factory_versioning"]):
            self.num_factories = os.path.join(
                self.get_child("submit")["num_factories"], "glidein_%s" % self["glidein_name"]
            )
        else:
            self.num_factories = self.get_child("submit")["num_factories"]
        self.num_factories = int(self.num_factories)

    #######################
    #
    # FactoryXmlConfig getter functions
    #
    ######################
    def get_submit_dir(self):
        return self.submit_dir

    def get_stage_dir(self):
        return self.stage_dir

    def get_monitor_dir(self):
        return self.monitor_dir

    def get_log_dir(self):
        return self.log_dir

    def get_client_log_dirs(self):
        return self.client_log_dirs

    def get_client_proxy_dirs(self):
        return self.client_proxy_dirs

    def get_web_url(self):
        return self.web_url

    def get_entries(self):
        try:
            entries = self.get_child_list("entries")
        except KeyError:
            entries = []
        try:
            entry_sets = self.get_child_list("entry_sets")
        except KeyError:
            entry_sets = []
        return entries + entry_sets


xmlConfig.register_tag_classes({"glidein": Config})
xmlConfig.register_root("glidein")


#######################
#
# Module functions
#
######################


def parse(file):
    """parse a config file

    The root element (glidein) is registered as type Config

    :param file: file path
    :return: the document root
    :rtype: Config
    """

    # pylint: disable=maybe-no-member
    conf = _parse(file)

    conf_dir_path = os.path.join(os.path.dirname(file), CONFIG_DIR)
    if os.path.exists(conf_dir_path):
        files = sorted(os.listdir(conf_dir_path))
        for f in files:
            if f.endswith(".xml"):
                conf.merge(_parse(os.path.join(conf_dir_path, f)))

    # assume FACTORY_DEFAULTS_XML is in factoryXmlConfig module directory
    conf_def = _parse(os.path.join(os.path.dirname(__file__), FACTORY_DEFAULTS_XML), True)
    conf.merge_defaults(conf_def)

    # now that we are validated, set the directories
    conf.set_submit_dir()
    conf.set_stage_dir()
    conf.set_monitor_dir()
    conf.set_log_dir()
    conf.set_client_log_dirs()
    conf.set_client_proxy_dirs()
    conf.set_web_url()
    conf.set_num_factories()

    return conf


# this parse function is for internal usage
# it does not merge defaults or validate
def _parse(file, default=False):
    """
    The root element (glidein) is registered as type Config

    :param file: file path
    :param default: if True return a default configuration (no file)
    :return: the document root
    :rtype: Config
    """

    parser = xml.sax.make_parser()
    if default:
        handler = xmlConfig.Handler()
    else:
        handler = xmlConfig.Handler(file)
    parser.setContentHandler(handler)
    parser.parse(file)

    return handler.root
