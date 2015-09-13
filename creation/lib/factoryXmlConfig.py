import os
from xml.dom.minidom import parse

ENTRY_INDENT = 6
ENTRY_DIR = 'entries.d'

class XmlElement:
    def __init__(self, xml):
        self.xml = xml

class XmlAttrElement(XmlElement):
    def extract_attr_val(self):
        if (not self.xml.getAttribute(u'type') in ("string","int","expr")):
            raise RuntimeError, "Wrong attribute type '%s', must be either 'int' or 'string'"%self.xml.getAttribute(u'type')

        if self.xml.getAttribute(u'type') in ("string","expr"):
            return str(self.xml.getAttribute(u'value'))
        else:
            return int(self.xml.getAttribute(u'value'))

class XmlFileElement(XmlElement):
    def to_dict(self):
        file_dict = {}
        if self.xml.hasAttribute(u'absfname'):
            file_dict[u'absfname'] = self.xml.getAttribute(u'absfname')
        else:
            file_dict[u'absfname'] = None
        if self.xml.hasAttribute(u'after_entry'):
            file_dict[u'after_entry'] = self.xml.getAttribute(u'after_entry')
        if self.xml.hasAttribute(u'const'):
            file_dict[u'const'] = self.xml.getAttribute(u'const')
        else:
            file_dict[u'const'] = u'False'
        if self.xml.hasAttribute(u'executable'):
            file_dict[u'executable'] = self.xml.getAttribute(u'executable')
        else:
            file_dict[u'executable'] = u'False'
        if self.xml.hasAttribute(u'relfname'):
            file_dict[u'relfname'] = self.xml.getAttribute(u'relfname')
        else:
            file_dict[u'relfname'] = None
        if self.xml.hasAttribute(u'untar'):
            file_dict[u'untar'] = self.xml.getAttribute(u'untar')
        else:
            file_dict[u'untar'] = u'False'
        if self.xml.hasAttribute(u'wrapper'):
            file_dict[u'wrapper'] = self.xml.getAttribute(u'wrapper')
        else:
            file_dict[u'wrapper'] = u'False'
        uopts = self.xml.getElementsByTagName(u'untar_options')
        if len(uopts) > 0:
            uopt_el = self.xml.getElementsByTagName(u'untar_options')[0]
            uopt_dict = {}
            if uopt_el.hasAttribute(u'absdir_outattr'):
                uopt_dict[u'absdir_outattr'] = uopt_el.getAttribute(u'absdir_outattr')
            else:
                uopt_dict[u'absdir_outattr'] = None
            if uopt_el.hasAttribute(u'dir'):
                uopt_dict[u'dir'] = uopt_el.getAttribute(u'dir')
            else:
                uopt_dict[u'dir'] = None
            uopt_dict[u'cond_attr'] = uopt_el.getAttribute(u'cond_attr')
            file_dict[u'untar_options'] = uopt_dict

        return file_dict

class XmlConfigElement(XmlElement):
    def get_attrs(self):
        attrs = []
        for n in self.xml.childNodes:
            if n.nodeType == n.ELEMENT_NODE and n.tagName == u'attrs':
                for attr in n.getElementsByTagName(u'attr'):
                    attrs.append(XmlAttrElement(attr))
                break
        return attrs

    def get_files(self):
        files = []
        for n in self.xml.childNodes:
            if n.nodeType == n.ELEMENT_NODE and n.tagName == u'files':
                for file in n.getElementsByTagName(u'file'):
                    files.append(XmlFileElement(file))
                break
        return files

class XmlEntry(XmlConfigElement):
    pass

class FactoryXmlConfig:
    def __init__(self, file):
        self.file = file
        self.dom = None

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
        if self.submit_dir == None:
            self.submit_dir = os.path.join(self.dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_dir'),
                u"glidein_%s" % self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))
        return self.submit_dir

    def get_stage_dir(self):
        if self.stage_dir == None:
            self.stage_dir = os.path.join(self.dom.getElementsByTagName(u'stage')[0].getAttribute(u'base_dir'),
                u"glidein_%s" % self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))
        return self.stage_dir

    def get_monitor_dir(self):
        if self.monitor_dir == None:
            self.monitor_dir = os.path.join(self.dom.getElementsByTagName(u'monitor')[0].getAttribute(u'base_dir'),
                u"glidein_%s" % self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))
        return self.monitor_dir

    def get_log_dir(self):
        if self.log_dir == None:
            self.log_dir  = os.path.join(self.dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_log_dir'),
                u"glidein_%s" % self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))
        return self.log_dir

    def get_web_url(self):
        if self.web_url == None:
            self.web_url = os.path.join(self.dom.getElementsByTagName(u'stage')[0].getAttribute(u'web_base_url'),
                u"glidein_%s" % self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))
        return self.web_url

    def get_client_log_dirs(self):
        if self.client_log_dirs == None:
            self.client_log_dirs = {}
            client_dir = self.dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_client_log_dir')
            glidein_name = self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name')
            for sc in self.dom.getElementsByTagName(u'security_class'):
                self.client_log_dirs[sc.getAttribute(u'username')] = os.path.join(client_dir,
                    u"user_%s" % sc.getAttribute(u'username'), u"glidein_%s" % glidein_name)

        return self.client_log_dirs

    def get_client_proxy_dirs(self):
        if self.client_proxy_dirs == None:
            self.client_proxy_dirs = {}
            client_dir = self.dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_client_proxies_dir')
            glidein_name = self.dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name')
            for sc in self.dom.getElementsByTagName(u'security_class'):
                self.client_proxy_dirs[sc.getAttribute(u'username')] = os.path.join(client_dir,
                    u"user_%s" % sc.getAttribute(u'username'), u"glidein_%s" % glidein_name)

        return self.client_proxy_dirs


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

