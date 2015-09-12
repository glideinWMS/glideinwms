import os
from xml.dom.minidom import parse

ENTRY_INDENT = 6
ENTRY_DIR = 'entries.d'

class FactoryXmlConfig:
    def __init__(self, file):
        self.file = file
        self.dom = None

    def parse(self):
        d1 = parse(self.file)
        entry_dir_path = os.path.join(os.path.dirname(self.file), ENTRY_DIR)
        if not os.path.exists(entry_dir_path):
            self.dom = d1
            return

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

        self.dom = d1

    def unlink(self):
        self.dom.unlink()

    #######################
    #
    # FactoryXmlConfig getter functions
    #
    ######################
    def get_submit_dir(self):
        return os.path.join(self.dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_dir'),
            u"glidein_%s" % self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))

    def get_stage_dir(self):
        return os.path.join(self.dom.getElementsByTagName(u'stage')[0].getAttribute(u'base_dir'),
            u"glidein_%s" % self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))

    def get_monitor_dir(self):
        return os.path.join(self.dom.getElementsByTagName(u'monitor')[0].getAttribute(u'base_dir'),
            u"glidein_%s" % self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))

    def get_log_dir(self):
        return os.path.join(self.dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_log_dir'),
            u"glidein_%s" % self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))

    def get_web_url(self):
        return os.path.join(self.dom.getElementsByTagName(u'stage')[0].getAttribute(u'web_base_url'),
            u"glidein_%s" % self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))

    def get_client_log_dirs(self):
        cl_dict = {}
        client_dir = self.dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_client_log_dir')
        glidein_name = self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name')
        for sc in self.dom.getElementsByTagName(u'security_class'):
            cl_dict[sc.getAttribute(u'username')] = os.path.join(client_dir,
                u"user_%s" % sc.getAttribute(u'username'), u"glidein_%s" % glidein_name)

        return cl_dict

    def get_client_proxy_dirs(self):
        cp_dict = {}
        client_dir = self.dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_client_proxies_dir')
        glidein_name = self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name')
        for sc in self.dom.getElementsByTagName(u'security_class'):
            cp_dict[sc.getAttribute(u'username')] = os.path.join(client_dir,
                u"user_%s" % sc.getAttribute(u'username'), u"glidein_%s" % glidein_name)

        return cp_dict


#######################
#
# Utility functions
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

