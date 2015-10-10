import collections

INDENT_WIDTH = 3

LIST_TAGS = set([ 
    u'attrs',
    u'files',
])

TAG_CLASS_MAPPINGS = {}

class Element(object):
    def __init__(self, doc, xml, level):
        self.doc = doc
        self.xml = xml
        self.level = level

    def __str__(self):
        return self.xml.toxml()

    # children should override this
    def build_tree(self):
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
                elif c.tagName in TAG_CLASS_MAPPINGS:
                    self.children[c.tagName] = (TAG_CLASS_MAPPINGS[c.tagName](self.doc, c, self.level + 1)) 
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
                if c.tagName in TAG_CLASS_MAPPINGS:
                    self.children.append(TAG_CLASS_MAPPINGS[c.tagName](self.doc, c, self.level + 1)) 
                else:
                    self.children.append(DictElement(self.doc, c, self.level + 1))

                self.children[-1].build_tree()

    def merge_defaults(self, default):
        for child in self.children:
            child.merge_defaults(default.children[0])

class AttrElement(DictElement):
    def get_val(self):
        if (not self[u'type'] in ("string","int","expr")):
            raise RuntimeError, "Wrong attribute type '%s', must be either 'int' or 'string'"%self[u'type']

        if self[u'type'] in ("string","expr"):
            return str(self[u'value'])
        else:
            return int(self[u'value'])

TAG_CLASS_MAPPINGS.update({'attr': AttrElement})

class FileElement(DictElement):
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

TAG_CLASS_MAPPINGS.update({u'file': FileElement})

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
    TAG_CLASS_MAPPINGS.update(map_dict)
