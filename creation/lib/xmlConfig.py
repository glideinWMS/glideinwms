import copy
import os

import collections
# collections.MutableMapping is not available in Python 2.4
try:
    mutablemap = collections.MutableMapping
except AttributeError:
    import UserDict
    mutablemap = UserDict.DictMixin

import xml.sax

INDENT_WIDTH = 3

LIST_TAGS = { 
    u'attrs': lambda d: d[u'name'],
    u'files': lambda d: d[u'absfname']
}

TAG_CLASS_MAPPING = {}
DOCUMENT_ROOT = None


class Handler(xml.sax.ContentHandler):
    # leave file=None when parsing default xml to ignore xml file and line numbers
    def __init__(self, file=None):
        self.root = None
        self.ancestry = []
        self.file = file

    def startElement(self, name, attrs):
        if self.file is None:
            if name in LIST_TAGS:
                el = ListElement(name, parent=self.ancestry[-1:])
            elif name in TAG_CLASS_MAPPING:
                el = TAG_CLASS_MAPPING[name](name)
                for k in attrs.keys():
                    el.attrs[k] = attrs[k]
            else:
                el = DictElement(name, parent=self.ancestry[-1:])
                for k in attrs.keys():
                    el.attrs[k] = attrs[k]
        else:
            # _locator is an undocumented feature of SAX...
            if name in LIST_TAGS:
                el = ListElement(name, self.file, self._locator.getLineNumber(), parent=self.ancestry[-1:])
            elif name in TAG_CLASS_MAPPING:
                el = TAG_CLASS_MAPPING[name](name, self.file, self._locator.getLineNumber(), parent=self.ancestry[-1:])
                for k in attrs.keys():
                    el.attrs[k] = attrs[k]
            else:
                el = DictElement(name, self.file, self._locator.getLineNumber(), parent=self.ancestry[-1:])
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
    def __init__(self, tag, file="default", line_no=None, parent=None):
        self.tag = tag
        self.file = file
        self.line_no = line_no
        self.parent = parent[0] if parent else None

    # children should override these (signature should be the same)
    def add_child(self, child):
        pass

    def clear_lists(self):
        pass

    def merge_defaults(self, default):
        pass

    def validate(self):
        pass

    def merge(self, other):
        pass


class DictElement(Element, mutablemap):
    def __init__(self, tag, *args, **kwargs):
        super(DictElement, self).__init__(tag, *args, **kwargs)
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
            if key not in self:
                self[key] = default[key]

    def merge_defaults(self, default):
        self.merge_default_attrs(default)
        for tag in default.children:
            # xml blob completely missing from config, add it
            if tag == 'entry_sets':
                import pdb
                pdb.set_trace()
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
        # after filling in defaults, validate the element
        self.validate()

    # this creates references into other rather than deep copies for efficiency
    def merge(self, other):
        self.attrs.update(other.attrs)

        for tag in other.children:
            # if completely missing just add it
            if tag not in self.children:
                self.children[tag] = other.children[tag]
            # otherwise merge what we have
            else:
                self.children[tag].merge(other.children[tag])

    def err_str(self, str):
        return '%s:%s: %s: %s' % (self.file, self.line_no, self.tag, str)

    def check_boolean(self, flag):
        if self[flag] != u'True' and self[flag] != u'False':
            raise RuntimeError(self.err_str('%s must be "True" or "False"' % flag))

    def check_missing(self, attr):
        if attr not in self:
            raise RuntimeError(self.err_str('missing "%s" attribute' % attr))


class ListElement(Element):
    def __init__(self, tag, *args, **kwargs):
        super(ListElement, self).__init__(tag, *args, **kwargs)
        self.children = []

    def get_children(self):
        return self.children

    def add_child(self, child):
        self.children.append(child)

    def clear_lists(self):
        self.children = []

    def merge_defaults(self, default):
        for child in self.children:
            try:
                child.merge_defaults(default.children[0])
            except:
                import pdb
                pdb.set_trace()
                raise

    def check_sort_key(self):
        for child in self.children:
            try:
                LIST_TAGS[self.tag](child)
            except KeyError, e:
                raise RuntimeError(child.err_str('missing "%s" attribute' % e.message))
                
    # this creates references into other rather than deep copies for efficiency
    def merge(self, other):
        self.check_sort_key()
        other.check_sort_key()
        self.children.sort(key=LIST_TAGS[self.tag]) 
        other.children.sort(key=LIST_TAGS[self.tag]) 

        new_children = []
        my_size = len(self.children)
        other_size = len(other.children)
        my_count = 0
        other_count = 0
        while my_count < my_size and other_count < other_size:
            my_key = LIST_TAGS[self.tag](self.children[my_count])
            other_key = LIST_TAGS[self.tag](other.children[other_count])
            if my_key < other_key:
                new_children.append(self.children[my_count])
                my_count += 1
            else:
                new_children.append(other.children[other_count])
                other_count += 1
                if my_key == other_key:
                    my_count += 1

        while my_count < my_size:
            new_children.append(self.children[my_count])
            my_count += 1
        while other_count < other_size:
            new_children.append(other.children[other_count])
            other_count += 1

        self.children = new_children


class AttrElement(DictElement):
    def get_val(self):
        if self[u'type'] in ("string", "expr"):
            return str(self[u'value'])
        else:
            return int(self[u'value'])

    def validate(self):
        self.check_missing(u'name')
        self.check_missing(u'value')
        if self[u'type'] != u'string' and self[u'type'] != u'int' and self[u'type'] != u'expr':
            raise RuntimeError(self.err_str('type must be "int", "string", or "expr"'))
        self.check_boolean(u'glidein_publish')
        self.check_boolean(u'job_publish')
        self.check_boolean(u'parameter')

TAG_CLASS_MAPPING.update({'attr': AttrElement})


class FileElement(DictElement):
    def validate(self):
        self.check_missing(u'absfname')
        if len(os.path.basename(self[u'absfname'])) < 1:
            raise RuntimeError(self.err_str('absfname is an invalid file path'))
        if u'relfname' in self and len(self[u'relfname']) < 1:
            raise RuntimeError(self.err_str('relfname cannot be empty'))

        self.check_boolean(u'const')
        self.check_boolean(u'executable')
        self.check_boolean(u'wrapper')
        self.check_boolean(u'untar')

        is_exec = eval(self[u'executable'])
        is_wrapper = eval(self[u'wrapper'])
        is_tar = eval(self[u'untar'])

        try:
            period = int(self[u'period'])
        except ValueError:
            raise RuntimeError(self.err_str('period must be an int'))

        if is_exec + is_wrapper + is_tar > 1:
            raise RuntimeError(self.err_str('must be exactly one of type "executable", "wrapper", or "untar"'))

        if (is_exec or is_wrapper or is_tar) and not eval(self[u'const']):
            raise RuntimeError(self.err_str('type "executable", "wrapper", or "untar" requires const="True"'))
        if not is_exec and period > 0:
            raise RuntimeError(self.err_str('cannot have execution period if type is not "executable"'))

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
