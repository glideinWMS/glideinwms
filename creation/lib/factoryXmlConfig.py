import os
from xml.dom.minidom import parse
import xmlConfig

ENTRY_INDENT = 6
ENTRY_DIR = 'entries.d'

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

class EntryElement(xmlConfig.DictElement):
    def get_max_per_frontends(self):
        per_frontends = {}
        for per_fe in self.get_child(u'config').get_child(u'max_jobs').get_child_list(u'per_frontends'):
            per_frontends[per_fe[u'name']] = per_fe
        return per_frontends

    def get_allowed_frontends(self):
        allowed_frontends = {}
        for allow_fe in self.get_child_list(u'allow_frontends'):
            fe_dict = {}
            fe_dict[u'security_class'] = allow_fe[u'security_class']
            allowed_frontends[allow_fe[u'name']] = fe_dict
        return allowed_frontends

    def get_submit_attrs(self):
        submit_attrs = {}
        for sub_attr in self.get_child(u'config').get_child(u'submit').get_child_list(u'submit_attrs'):
            attr_dict = {}
            attr_dict[u'value'] = sub_attr[u'value']
            submit_attrs[sub_attr[u'name']] = attr_dict
        return submit_attrs

xmlConfig.register_tag_classes({u'entry': EntryElement})

class Config(xmlConfig.DictElement):
    def __init__(self, file):
        super(Config, self).__init__(None, None, 0)
        self.file = file

        # cached variables to minimize dom accesses for better performance
        # these are looked up for each and every entry on reconfig
        self.submit_dir = None
        self.stage_dir = None
        self.monitor_dir = None
        self.log_dir = None
        self.client_log_dirs = None
        self.client_proxy_dirs = None

    def parse(self):
        d1 = parse(self.file)
        entry_dir_path = os.path.join(os.path.dirname(self.file), ENTRY_DIR)
        if os.path.exists(entry_dir_path):
            entries = d1.getElementsByTagName(u'entry')

            found_entries = {}
            for e in entries:
                found_entries[e.getAttribute(u'name')] = e

            files = sorted(os.listdir(entry_dir_path))
            for f in files:
                if f.endswith('.xml'):
                    d2 = parse(os.path.join(entry_dir_path, f))
                    merge_entries(d1, d2, found_entries)
                    d2.unlink()

        self.doc = d1
        self.xml = d1.documentElement
        self.build_tree()

    def unlink(self):
        self.doc.unlink()

    #######################
    #
    # FactoryXmlConfig getter functions
    #
    ######################
    def get_web_url(self):
        return os.path.join(self.get_child(u'stage')[u'web_base_url'],
            u"glidein_%s" % self[u'glidein_name'])

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
