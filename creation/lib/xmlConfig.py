import os
import collections

INDENT_WIDTH = 3

LIST_TAGS = set([ 
    u'attrs',
    u'files',
])

TAG_CLASS_MAPPING = {}

class Element(object):
    def __init__(self, doc, xml, level):
        self.doc = doc
        self.xml = xml
        self.level = level

    def __str__(self):
        return self.xml.toxml()

    def first_line(self):
        return self.xml.toxml().splitlines()[0]

    def unlink(self):
        self.doc.unlink()

    # children should override these
    def build_tree(self):
        pass
    def merge_defaults(self):
        pass
    def validate(self):
        pass
    def validate_tree(self):
        pass

class DictElementIterator(collections.Iterator):
    def __init__(self, attributes):
        self.i = 0
        self.attributes = attributes
    def next(self):
        if self.i >= self.attributes.length:
            raise StopIteration
        cur_key = self.attributes.item(self.i).name
        self.i += 1
        return cur_key

class DictElement(Element, collections.MutableMapping):
    def __init__(self, doc, xml, level):
        super(DictElement, self).__init__(doc, xml, level)
        self.children = {}

    def __getitem__(self, key):
        return self.xml.getAttribute(key)

    def __setitem__(self, key, value):
        self.xml.setAttribute(key, value)

    def __delitem__(self, key):
        self.xml.removeAttribute(key)

    def __contains__(self, key):
        return self.xml.hasAttribute(key)

    def __iter__(self):
        return DictElementIterator(self.xml.attributes)

    def __len__(self):
        return self.xml.attributes.length

    def has_child(self, tag):
        return tag in self.children

    def get_child(self, tag):
        return self.children[tag]

    def get_child_list(self, tag):
        return self.get_child(tag).get_children()

    def clear_lists(self):
        for tag in self.children:
            self.children[tag].clear_lists()

    def build_tree(self):
        for c in self.xml.childNodes:
            if c.nodeType == c.ELEMENT_NODE:
                if c.tagName in LIST_TAGS:
                    self.children[c.tagName] = ListElement(self.doc, c, self.level + 1)
                elif c.tagName in TAG_CLASS_MAPPING:
                    self.children[c.tagName] = (TAG_CLASS_MAPPING[c.tagName](self.doc, c, self.level + 1)) 
                else:
                    self.children[c.tagName] = DictElement(self.doc, c, self.level + 1)

                self.children[c.tagName].build_tree()

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
                    new_child = self.doc.createElement(tag)
                    self.children[tag] = type(default.children[tag])(self.doc, new_child, self.level + 1)
                # otherwise clone from default
                else:
                    new_child = self.doc.importNode(default.children[tag].xml, True)
                    self.children[tag] = type(default.children[tag])(self.doc, new_child, self.level + 1)
                    self.children[tag].build_tree()
                    # zero out any xml lists
                    self.children[tag].clear_lists()
                # put new xml element in the top of parent
                self.xml.insertBefore(new_child, self.xml.firstChild)
                # insert line break in front for readability
                line_break = self.doc.createTextNode(u'\n%*s' % (INDENT_WIDTH * (self.level + 1),' '))
                self.xml.insertBefore(line_break, self.xml.firstChild)
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
    def __init__(self, doc, xml, level):
        super(ListElement, self).__init__(doc, xml, level)
        self.children = []

    def get_children(self):
        return self.children

    def clear_lists(self):
        while self.xml.firstChild is not None:
            self.xml.removeChild(self.xml.firstChild).unlink()
        self.children = []

    def build_tree(self):
        for c in self.xml.childNodes:
            if c.nodeType == c.ELEMENT_NODE:
                # we are assuming you wont' have a list element directly inside another list elemement
                # so assume its either a custom mapping or a dict element
                if c.tagName in TAG_CLASS_MAPPING:
                    self.children.append(TAG_CLASS_MAPPING[c.tagName](self.doc, c, self.level + 1)) 
                else:
                    self.children.append(DictElement(self.doc, c, self.level + 1))

                self.children[-1].build_tree()

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
def register_list_elements(tag_list):
    LIST_TAGS.update(tag_list)

def register_tag_classes(map_dict):
    TAG_CLASS_MAPPING.update(map_dict)
