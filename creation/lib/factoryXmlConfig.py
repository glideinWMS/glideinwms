import os
from xml.dom.minidom import parse
import collections

ENTRY_INDENT = 6
ENTRY_DIR = 'entries.d'

class XmlElementIterator(collections.Iterator):
    def __init__(self, attributes):
        self.i = 0
        self.attributes = attributes
    def next(self):
        if self.i >= self.attributes.length:
            raise StopIteration
        cur_key = self.attributes.item(self.i).name
        self.i += 1
        return cur_key

class XmlElement(collections.Mapping):
    def __init__(self, xml):
        self.xml = xml
        self.children = []

    def __getitem__(self, key):
        return self.xml.getAttribute(key)

    def __contains__(self, key):
        return self.xml.hasAttribute(key)

    def __str__(self):
        return self.xml.toxml()

    def __iter__(self):
        return XmlElementIterator(self.xml.attributes)

    def __len__(self):
        return self.xml.attributes.length

    def get_child(self, tag):
        child = None
        for c in self.children:
            if c.xml.tagName == tag:
                child = c
                break
        return child

    def get_child_list(self, tag):
        child = self.get_child(tag)
        if child is None:
            return None
        return child.children

    def find(self, tag):
        found = []
        self._find(tag, found)
        return found

    def _find(self, tag, found):
        for c in self.children:
            if c.xml.tagName == tag:
                found.append(c)
            c._find(tag, found)

class XmlAttrElement(XmlElement):
    def get_val(self):
        if (not self[u'type'] in ("string","int","expr")):
            raise RuntimeError, "Wrong attribute type '%s', must be either 'int' or 'string'"%self[u'type']

        if self[u'type'] in ("string","expr"):
            return str(self[u'value'])
        else:
            return int(self[u'value'])

class XmlFileElement(XmlElement):
    # this function converts a file element to the expected dictionary used in
    # cgWParamDict.add_file_unparsed()
    def to_dict(self):
        file_dict = {}
        if u'absfname' in self:
            file_dict[u'absfname'] = self[u'absfname']
        else:
            file_dict[u'absfname'] = None
        if u'after_entry' in self:
            file_dict[u'after_entry'] = self[u'after_entry']
        if u'const' in self:
            file_dict[u'const'] = self[u'const']
        else:
            file_dict[u'const'] = u'False'
        if u'executable' in self:
            file_dict[u'executable'] = self[u'executable']
        else:
            file_dict[u'executable'] = u'False'
        if u'relfname' in self:
            file_dict[u'relfname'] = self[u'relfname']
        else:
            file_dict[u'relfname'] = None
        if u'untar' in self:
            file_dict[u'untar'] = self[u'untar']
        else:
            file_dict[u'untar'] = u'False'
        if u'wrapper' in self:
            file_dict[u'wrapper'] = self[u'wrapper']
        else:
            file_dict[u'wrapper'] = u'False'
        uopts = self.get_child(u'untar_options')
        if uopts is not None:
            uopt_dict = {}
            if u'absdir_outattr' in uopts:
                uopt_dict[u'absdir_outattr'] = uopts[u'absdir_outattr']
            else:
                uopt_dict[u'absdir_outattr'] = None
            if u'dir' in uopts:
                uopt_dict[u'dir'] = uopts[u'dir']
            else:
                uopt_dict[u'dir'] = None
            uopt_dict[u'cond_attr'] = uopts[u'cond_attr']
            file_dict[u'untar_options'] = uopt_dict

        return file_dict

class XmlEntry(XmlElement):
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

class FactoryXmlConfig(XmlElement):
    def __init__(self, file):
        super(FactoryXmlConfig, self).__init__(None)
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

        self.dom = d1
        self.xml = d1.documentElement
        build_tree(self)

    def unlink(self):
        self.dom.unlink()

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
            for sc in self.get_child(u'security').find(u'security_class'):
                self.client_log_dirs[sc[u'username']] = os.path.join(client_dir,
                    u"user_%s" % sc[u'username'], u"glidein_%s" % glidein_name)

        return self.client_log_dirs

    def get_client_proxy_dirs(self):
        if self.client_proxy_dirs == None:
            self.client_proxy_dirs = {}
            client_dir = self.get_child(u'submit')[u'base_client_proxies_dir']
            glidein_name = self[u'glidein_name']
            for sc in self.get_child(u'security').find(u'security_class'):
                self.client_proxy_dirs[sc[u'username']] = os.path.join(client_dir,
                    u"user_%s" % sc[u'username'], u"glidein_%s" % glidein_name)

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

def build_tree(element):
    for c in element.xml.childNodes:
        if c.nodeType == c.ELEMENT_NODE:
            if c.tagName == u'attr':
                element.children.append(XmlAttrElement(c)) 
            elif c.tagName == u'file':
                element.children.append(XmlFileElement(c)) 
            elif c.tagName == u'entry':
                element.children.append(XmlEntry(c))
            else:
                element.children.append(XmlElement(c))

            build_tree(element.children[-1])
