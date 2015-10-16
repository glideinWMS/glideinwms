import os
from xml.dom import minidom
import xmlConfig

ENTRY_INDENT = 6
ENTRY_DIR = 'entries.d'
FACTORY_DEFAULTS_XML = 'factory_defaults.xml'

xmlConfig.register_list_elements([ 
u'allow_frontends',
u'condor_tarballs',
u'entries',
u'frontends',
u'infosys_refs',
u'monitorgroups',
u'monitoring_collectors',
u'per_frontends',
u'process_logs',
u'security_classes',
u'submit_attrs'
])

class FactAttrElement(xmlConfig.AttrElement):
    def validate(self):
        super(FactAttrElement, self).validate()
        self.check_boolean(u'const')
        self.check_boolean(u'publish')

xmlConfig.register_tag_classes({u'attr': FactAttrElement})

class FactFileElement(xmlConfig.FileElement):
    def validate(self):
        super(FactFileElement, self).validate()
        # only defined in factory global entries
        if u'after_entry' in self:
            self.check_boolean(u'after_entry')

xmlConfig.register_tag_classes({u'file': FactFileElement})

class CondTarElement(xmlConfig.DictElement):
    # this will need an update when we re-implement base_dir
    def validate(self):
        self.check_missing(u'tar_file')

xmlConfig.register_tag_classes({u'condor_tarball': CondTarElement})

class EntryElement(xmlConfig.DictElement):
    def validate(self):
        self.check_missing(u'name')
        self.check_missing(u'gatekeeper')
        self.check_boolean(u'enabled')
        for infosys in self.get_child_list(u'infosys_refs'):
            infosys.check_missing(u'ref')
            infosys.check_missing(u'server')
            infosys.check_missing(u'type')
        for group in self.get_child_list(u'monitorgroups'):
            group.check_missing(u'group_name')

xmlConfig.register_tag_classes({u'entry': EntryElement})

class Config(xmlConfig.DictElement):
    def __init__(self, doc, xml, level):
        super(Config, self).__init__(doc, xml, level)
        self.file = file

        # cached variables to minimize dom accesses for better performance
        # these are looked up for each and every entry on reconfig
        self.submit_dir = None
        self.stage_dir = None
        self.monitor_dir = None
        self.log_dir = None
        self.client_log_dirs = None
        self.client_proxy_dirs = None

    def merge_defaults(self):
        # assume FACTORY_DEFAULTS_XML is in factoryXmlConfig module directory
        conf_def = _parse(os.path.join(os.path.dirname(__file__), FACTORY_DEFAULTS_XML))
        super(Config, self).merge_defaults(conf_def)
        conf_def.unlink()

    #######################
    #
    # FactoryXmlConfig getter functions
    #
    ######################
    def get_submit_dir(self):
        if self.submit_dir == None:
            self.submit_dir = os.path.join(self.get_child(u'submit')[u'base_dir'],
                u"glidein_%s" % self[u'glidein_name'])
        return self.submit_dir

    def get_stage_dir(self):
        if self.stage_dir == None:
            self.stage_dir = os.path.join(self.get_child(u'stage')[u'base_dir'],
                u"glidein_%s" % self[u'glidein_name'])
        return self.stage_dir

    def get_monitor_dir(self):
        if self.monitor_dir == None:
            self.monitor_dir = os.path.join(self.get_child(u'monitor')[u'base_dir'],
                u"glidein_%s" % self[u'glidein_name'])
        return self.monitor_dir

    def get_log_dir(self):
        if self.log_dir == None:
            self.log_dir  = os.path.join(self.get_child(u'submit')[u'base_log_dir'],
                u"glidein_%s" % self[u'glidein_name'])
        return self.log_dir

    def get_client_log_dirs(self):
        if self.client_log_dirs == None:
            self.client_log_dirs = {}
            client_dir = self.get_child(u'submit')[u'base_client_log_dir']
            glidein_name = self[u'glidein_name']
            for fe in self.get_child(u'security').get_child_list(u'frontends'):
                for sc in fe.get_child_list(u'security_classes'):
                    self.client_log_dirs[sc[u'username']] = os.path.join(client_dir,
                        u"user_%s" % sc[u'username'], u"glidein_%s" % glidein_name)

        return self.client_log_dirs

    def get_client_proxy_dirs(self):
        if self.client_proxy_dirs == None:
            self.client_proxy_dirs = {}
            client_dir = self.get_child(u'submit')[u'base_client_proxies_dir']
            glidein_name = self[u'glidein_name']
            for fe in self.get_child(u'security').get_child_list(u'frontends'):
                for sc in fe.get_child_list(u'security_classes'):
                    self.client_proxy_dirs[sc[u'username']] = os.path.join(client_dir,
                        u"user_%s" % sc[u'username'], u"glidein_%s" % glidein_name)

        return self.client_proxy_dirs

#######################
#
# Module functions
#
######################

def parse(file):
    conf = _parse(file)
    conf.merge_defaults()
    conf.validate_tree()
    return conf

# this parse function is for internal usage
# it does not merge defaults or validate
def _parse(file):
    d1 = minidom.parse(file)
    entry_dir_path = os.path.join(os.path.dirname(file), ENTRY_DIR)
    if os.path.exists(entry_dir_path):
        entries = d1.getElementsByTagName(u'entry')

        found_entries = {}
        for e in entries:
            found_entries[e.getAttribute(u'name')] = e

        files = sorted(os.listdir(entry_dir_path))
        for f in files:
            if f.endswith('.xml'):
                d2 = minidom.parse(os.path.join(entry_dir_path, f))
                merge_entries(d1, d2, found_entries)
                d2.unlink()

    conf = Config(d1, d1.documentElement, 0) 
    conf.build_tree()

    return conf

#######################
#
# Internal utility functions
#
######################

def merge_entries(d1, d2, found_entries):
    entries1 = d1.getElementsByTagName(u'entries')[0]
    entries2 = d2.getElementsByTagName(u'entries')[0]

    for e in entries2.getElementsByTagName(u'entry'):
        entry_name = e.getAttribute(u'name')
        entry_clone = d1.importNode(e, True)
        if entry_name in found_entries:
            entries1.replaceChild(entry_clone, found_entries[entry_name])
        else:
            line_break = d1.createTextNode(u'\n%*s' % (ENTRY_INDENT,' '))
            entries1.insertBefore(line_break, entries1.lastChild)
            entries1.insertBefore(entry_clone, entries1.lastChild)
            found_entries[entry_name] = entry_clone
