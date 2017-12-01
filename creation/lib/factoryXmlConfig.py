import os
import xml.sax
import xmlConfig

ENTRY_INDENT = 6
CONFIG_DIR = 'config.d'
FACTORY_DEFAULTS_XML = 'factory_defaults.xml'

xmlConfig.register_list_elements({
    u'allow_frontends': lambda d: d[u'name'],
    u'condor_tarballs': lambda d: "%s,%s,%s" % (d[u'arch'], d[u'os'], d[u'version']),
    u'entries': lambda d: d[u'name'],
    u'entry_sets': lambda d: d[u'alias'],
    u'frontends': lambda d: d[u'name'],
    u'infosys_refs': lambda d: d[u'ref'],
    u'monitorgroups': lambda d: d[u'group_name'],
    u'monitoring_collectors': lambda d: d[u'DN'],
    u'per_frontends': lambda d: d[u'name'],
    u'process_logs': lambda d: d[u'extension'],
    u'security_classes': lambda d: d[u'username'],
    u'submit_attrs': lambda d: d[u'name']
})


class FactAttrElement(xmlConfig.AttrElement):
    def validate(self):
        super(FactAttrElement, self).validate()
        self.check_boolean(u'const')
        self.check_boolean(u'publish')
        is_publish = eval(self[u'publish'])
        is_const = eval(self[u'const'])
        is_param = eval(self[u'parameter'])

        if is_publish and (not is_const and not is_param):
            raise RuntimeError(self.err_str('published attribute must either be "parameter" or "const"'))
        if not is_publish and (not is_const or not is_param):
            raise RuntimeError(self.err_str('unpublished attribute must be "const" "parameter"'))


xmlConfig.register_tag_classes({u'attr': FactAttrElement})


class FactFileElement(xmlConfig.FileElement):
    def validate(self):
        super(FactFileElement, self).validate()
        # only defined in factory global entries
        if u'after_entry' in self:
            self.check_boolean(u'after_entry')


xmlConfig.register_tag_classes({u'file': FactFileElement})


class CondTarElement(xmlConfig.DictElement):
    def validate(self):
        if u'tar_file' not in self and u'base_dir' not in self:
            raise RuntimeError(self.err_str('must either define "tar_file" or "base_dir"'))


xmlConfig.register_tag_classes({u'condor_tarball': CondTarElement})


class FrontendElement(xmlConfig.DictElement):
    def validate(self):
        self.check_missing(u'name')
        self.check_missing(u'identity')
        for sc in self.get_child_list(u'security_classes'):
            sc.check_missing(u'username')


xmlConfig.register_tag_classes({u'frontend': FrontendElement})


class EntryElement(xmlConfig.DictElement):
    def validate(self):
        self.check_missing(u'name')
        self.check_missing(u'gatekeeper')
        self.check_boolean(u'enabled')
        if isinstance(self.parent.parent, EntrySetElement):
            #no need to check more if the parent is an entryset
            return
        self.validate_sub_elements()

    def validate_sub_elements(self):
        for per_fe in self.get_child(u'config').get_child(u'max_jobs').get_child_list(u'per_frontends'):
            per_fe.check_missing(u'name')
        for submit_attr in self.get_child(u'config').get_child(u'submit').get_child_list(u'submit_attrs'):
            submit_attr.check_missing(u'name')
        for allowed_fe in self.get_child_list(u'allow_frontends'):
            allowed_fe.check_missing(u'name')
        for infosys in self.get_child_list(u'infosys_refs'):
            infosys.check_missing(u'ref')
            infosys.check_missing(u'server')
            infosys.check_missing(u'type')
        for group in self.get_child_list(u'monitorgroups'):
            group.check_missing(u'group_name')

    def getName(self):
        return self[u'name']

xmlConfig.register_tag_classes({u'entry': EntryElement})


class EntrySetElement(EntryElement):
    def validate(self):
        self.check_missing(u'alias')
        self.check_boolean(u'enabled')
        self.validate_sub_elements()

    def select(self, entry):
        self.selected_entry = entry

    def get(self, attrname):
        if getattr(self, 'selected_entry', False) and attrname in self.selected_entry:
            val = self.selected_entry[attrname]
        else:
            val = xmlConfig.DictElement.get(self, attrname)
        if val == None and attrname in self.get_child_list(u'entries')[0]:
            val = self.get_child_list(u'entries')[0][attrname]
#            val = [ x[attrname] for x in self.get_child_list(u'entries') ]
        return val

    def getName(self):
        """ The name for entry sets is actaully called alias """
        return self[u'alias']

xmlConfig.register_tag_classes({u'entry_set': EntrySetElement})




class Config(xmlConfig.DictElement):
    def __init__(self, tag, *args, **kwargs):
        super(Config, self).__init__(tag, *args, **kwargs)

        # dir paths should be set after validation in parse function
        self.submit_dir = None
        self.stage_dir = None
        self.monitor_dir = None
        self.log_dir = None
        self.client_log_dirs = None
        self.client_proxy_dirs = None
        self.web_url = None

    def validate(self):
        self.check_missing(u'factory_name')
        self.check_boolean(u'factory_versioning')
        for mon_coll in self.get_child_list(u'monitoring_collectors'):
            mon_coll.check_missing(u'DN')
            mon_coll.check_missing(u'node')

    #######################
    #
    # FactoryXmlConfig setter functions
    #
    ######################
    def set_submit_dir(self):
        if eval(self[u'factory_versioning']):
            self.submit_dir = os.path.join(self.get_child(u'submit')[u'base_dir'],
                                           u"glidein_%s" % self[u'glidein_name'])
        else:
            self.submit_dir = self.get_child(u'submit')[u'base_dir']

    def set_stage_dir(self):
        if eval(self[u'factory_versioning']):
            self.stage_dir = os.path.join(self.get_child(u'stage')[u'base_dir'],
                                          u"glidein_%s" % self[u'glidein_name'])
        else:
            self.stage_dir = self.get_child(u'stage')[u'base_dir']

    def set_monitor_dir(self):
        if eval(self[u'factory_versioning']):
            self.monitor_dir = os.path.join(self.get_child(u'monitor')[u'base_dir'],
                                            u"glidein_%s" % self[u'glidein_name'])
        else:
            self.monitor_dir = self.get_child(u'monitor')[u'base_dir']

    def set_log_dir(self):
        if eval(self[u'factory_versioning']):
            self.log_dir = os.path.join(self.get_child(u'submit')[u'base_log_dir'],
                                        u"glidein_%s" % self[u'glidein_name'])
        else:
            self.log_dir = self.get_child(u'submit')[u'base_log_dir']

    def set_client_log_dirs(self):
        self.client_log_dirs = {}
        client_dir = self.get_child(u'submit')[u'base_client_log_dir']
        glidein_name = self[u'glidein_name']
        for fe in self.get_child(u'security').get_child_list(u'frontends'):
            for sc in fe.get_child_list(u'security_classes'):
                self.client_log_dirs[sc[u'username']] = os.path.join(client_dir,
                                                                     u"user_%s" % sc[u'username'],
                                                                     u"glidein_%s" % glidein_name)

    def set_client_proxy_dirs(self):
        self.client_proxy_dirs = {}
        client_dir = self.get_child(u'submit')[u'base_client_proxies_dir']
        glidein_name = self[u'glidein_name']
        for fe in self.get_child(u'security').get_child_list(u'frontends'):
            for sc in fe.get_child_list(u'security_classes'):
                self.client_proxy_dirs[sc[u'username']] = os.path.join(client_dir,
                                                                       u"user_%s" % sc[u'username'],
                                                                       u"glidein_%s" % glidein_name)

    def set_web_url(self):
        if eval(self[u'factory_versioning']):
            self.web_url = os.path.join(self.get_child(u'stage')[u'web_base_url'],
                                        u"glidein_%s" % self[u'glidein_name'])
        else:
            self.web_url = self.get_child(u'stage')[u'web_base_url']

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
        return self.get_child_list(u'entries') + self.get_child_list(u'entry_sets')


xmlConfig.register_tag_classes({u'glidein': Config})
xmlConfig.register_root(u'glidein')


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
            if f.endswith('.xml'):
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
