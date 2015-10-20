import copy
import os
import collections
import xml.sax

INDENT_WIDTH = 3

LIST_TAGS = set([ 
    u'attrs',
    u'files',
])

TAG_CLASS_MAPPING = {}
DOCUMENT_ROOT = None

class Handler(xml.sax.ContentHandler):
    def __init__(self):
        self.root = None
        self.ancestry = []

    def startElement(self, name, attrs):
        if name in LIST_TAGS:
            el = ListElement(name)
        elif name in TAG_CLASS_MAPPING:
            el = TAG_CLASS_MAPPING[name](name)
            for k in attrs.keys():
                el.attrs[k] = attrs[k]
        else:
            el = DictElement(name)
            for k in attrs.keys():
                el.attrs[k] = attrs[k]
        
        if name == DOCUMENT_ROOT:
            self.root = el
        else:
            self.ancestry[-1].add_child(el)

        self.ancestry.append(el)

    def endElement(self, name):
        self.ancestry.pop()

class Element(object):
    def __init__(self, tag):
        self.tag = tag

    def __str__(self):
        return self.xml.toxml()

    def first_line(self):
        return self.xml.toxml().splitlines()[0]

    # children should override these
    def add_child(self):
        pass
    def clear_lists(self):
        pass
    def merge_defaults(self):
        pass
    def validate(self):
        pass
    def validate_tree(self):
        pass

class DictElement(Element, collections.MutableMapping):
    def __init__(self, tag):
        super(DictElement, self).__init__(tag)
        self.attrs = {}
        self.children = {}

    def __getitem__(self, key):
        return self.attrs[key]

    def __setitem__(self, key, value):
        self.attrs[key] = value

    def __delitem__(self, key):
        del(self.attrs[key])

    def __contains__(self, key):
        return key in self.attrs

    def __iter__(self):
        return iter(self.attrs)

    def __len__(self):
        return len(self.attrs)

    def has_child(self, tag):
        return tag in self.children

    def get_child(self, tag):
        return self.children[tag]

    def get_child_list(self, tag):
        return self.get_child(tag).get_children()

    def add_child(self, child):
        self.children[child.tag] = child

    def clear_lists(self):
        for tag in self.children:
            self.children[tag].clear_lists()

    def merge_default_attrs(self, default):
        for key in default:
            if not key in self:
                self[key] = default[key]

    def merge_defaults(self, default):
        self.merge_default_attrs(default)
        for tag in default.children:
            # xml blob completely missing from config, add it
            if tag not in self.children:
                # if its an xml list that is missing just create a new empty one
                if isinstance(default.children[tag], ListElement):
                    self.children[tag] = type(default.children[tag])(tag)
                # otherwise clone from default
                else:
                    self.children[tag] = copy.deepcopy(default.children[tag])
                    # zero out any xml lists
                    self.children[tag].clear_lists()
            # or continue down the tree
            else:
                self.children[tag].merge_defaults(default.children[tag])

    def check_boolean(self, flag):
        if self[flag] != u'True' and self[flag] != u'False':
            raise RuntimeError, '%s must be "True" or "False": %s' % (flag, self.first_line())

    def check_missing(self, attr):
        if not attr in self:
            raise RuntimeError, 'missing "%s" attribute: %s' % (attr, self.first_line())

    def validate_tree(self):
        self.validate()
        for tag in self.children:
            self.children[tag].validate_tree()

class ListElement(Element):
    def __init__(self, tag):
        super(ListElement, self).__init__(tag)
        self.children = []

    def get_children(self):
        return self.children

    def add_child(self, child):
        self.children.append(child)

    def clear_lists(self):
        self.children = []

    def merge_defaults(self, default):
        for child in self.children:
            child.merge_defaults(default.children[0])

    def validate_tree(self):
        for child in self.children:
            child.validate_tree()

class AttrElement(DictElement):
    def get_val(self):
        if self[u'type'] in ("string","expr"):
            return str(self[u'value'])
        else:
            return int(self[u'value'])

    def validate(self):
        self.check_missing(u'name')
        self.check_missing(u'value')
        if self[u'type'] != u'string' and self[u'type'] != u'int' and self[u'type'] != u'expr':
            raise RuntimeError, 'type must be "int", "string", or "expr": %s' % self.first_line()
        self.check_boolean(u'glidein_publish')
        self.check_boolean(u'job_publish')
        self.check_boolean(u'parameter')

TAG_CLASS_MAPPING.update({'attr': AttrElement})

class FileElement(DictElement):
    def validate(self):
        self.check_missing(u'absfname')
        if len(os.path.basename(self[u'absfname'])) < 1:
            raise RuntimeError, 'absfname is an invalid file path: %s' % self.first_line()
        if u'relfname' in self and len(self[u'relfname']) < 1:
            raise RuntimeError, 'relfname cannot be empty: %s' % self.first_line()

        self.check_boolean(u'const')
        self.check_boolean(u'executable')
        self.check_boolean(u'wrapper')
        self.check_boolean(u'untar')

        is_exec = eval(self[u'executable'])
        is_wrapper = eval(self[u'wrapper'])
        is_tar = eval(self[u'untar'])
        if is_exec + is_wrapper + is_tar > 1:
            raise RuntimeError, 'file must be exactly one of type "executable", "wrapper", or "untar": %s' % self.first_line()

        if (is_exec or is_wrapper or is_tar) and not eval(self[u'const']):
            raise RuntimeError, 'file of type "executable", "wrapper", or "untar" requires const="True": %s' % self.first_line()

TAG_CLASS_MAPPING.update({u'file': FileElement})

#######################
#
# Module functions
#
######################

# any modules that choose to subclass from xmlConfig should register new xml tags
# and either flag them as being a list element, or associate with respective class type
# as needed
def register_root(tag):
    global DOCUMENT_ROOT
    DOCUMENT_ROOT = tag

def register_list_elements(tag_list):
    LIST_TAGS.update(tag_list)

def register_tag_classes(map_dict):
    TAG_CLASS_MAPPING.update(map_dict)
