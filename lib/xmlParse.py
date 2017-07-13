#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description: general purpose XML decoder
#
# Author:
#  Igor Sfiligoi (Mar 27th, 2007)
#

from builtins import range
from builtins import map
from builtins import zip
import xml.dom.minidom
from UserDict import UserDict

class CorruptXML(Exception):
    pass


# This Class was obtained from
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/107747
class OrderedDict(UserDict):
    def __init__(self, dict=None):
        self._keys = []
        UserDict.__init__(self, dict)

    def __delitem__(self, key):
        UserDict.__delitem__(self, key)
        self._keys.remove(key)

    def __setitem__(self, key, item):
        UserDict.__setitem__(self, key, item)
        if key not in self._keys:
            self._keys.append(key)

    def clear(self):
        UserDict.clear(self)
        self._keys = []

    def copy(self):
        dict = UserDict.copy(self)
        dict._keys = self._keys[:]
        return dict

    def items(self):
        return list(zip(self._keys, list(self.values())))

    def keys(self):
        return self._keys

    def popitem(self):
        try:
            key = self._keys[-1]
        except IndexError:
            raise KeyError('dictionary is empty')

        val = self[key]
        del self[key]

        return (key, val)

    def setdefault(self, key, failobj = None):
        UserDict.setdefault(self, key, failobj)
        if key not in self._keys:
            self._keys.append(key)

    def update(self, dict):
        UserDict.update(self, dict)
        for key in list(dict.keys()):
            if key not in self._keys:
                self._keys.append(key)

    def values(self):
        return list(map(self.get, self._keys))
    

# convert a XML file into a dictionary
# ignore text sections
def xmlfile2dict(fname,
                 use_ord_dict=False,        # if true, return OrderedDict instead of a regular dictionary
                 always_singular_list=[]):  # anything id listed here will be considered as a list

    try:
        doc=xml.dom.minidom.parse(fname)
    except xml.parsers.expat.ExpatError as e:
        raise CorruptXML("XML corrupt in file %s: %s" % (fname, e))

    data = domel2dict(doc.documentElement, use_ord_dict, always_singular_list)

    return data

# convert a XML string into a dictionary
# ignore text sections
#
# Example:
#  <test date="1/2/07">
#   <params what="xx">
#    <param name="x" value="12"/>
#    <param name="y" value="88"/>
#   </params>
#   <files>
#    <file absname="/tmp/abc.txt"/>
#    <file absname="/tmp/w.log" mod="-rw-r--r--"/>
#   </files>
#   <temperature F="100" C="40"/>
#  </test>
# becomes
#  {u'date': u'1/2/07',
#   u'params': {u'y': {u'value':u'88'},
#               u'x': {u'value':u'12'},
#               u'what': u'xx'},
#   u'files': [{u'absname':u'/tmp/abc.txt'},
#              {u'mod':u'-rw-r--r--',u'absname:u'/tmp/w.log'}],
#   u'temperature': {u'C': u'40',
#                    u'F': u'100'}
#  }
#  
def xmlstring2dict(instr,
                   use_ord_dict=False,        # if true, return OrderedDict instead of a regular dictionary
                   always_singular_list=[]):  # anything id listed here will be considered as a list
    doc = xml.dom.minidom.parseString(instr)

    data = domel2dict(doc.documentElement, use_ord_dict, always_singular_list)

    return data

########################################################
#
# I N T E R N A L
#
# Do not use directly
#
########################################################

def getXMLElements(element):
    basic_els = element.childNodes

    # look only for element nodes
    els = []
    for el in basic_els:
        if el.nodeType == el.ELEMENT_NODE:
            els.append(el)

    return els

def getXMLAttributes(element, use_ord_dict):
    ael = element.attributes
    
    if use_ord_dict:
        attrs = OrderedDict()
    else:
        attrs = {}
    attr_len = ael.length
    for i in range(attr_len):
        attr = ael.item(i)
        attrs[attr.nodeName] = attr.nodeValue

    return attrs

def is_singular_of(mysin, myplu, always_singular_list=[]):
    if mysin in always_singular_list:
        return True
    if myplu[-1] != 's':
        # if myplu does not end in s, it is not plural
        return False
    if (mysin + "s") == myplu:
        # regular, like attr/attrs
        return True
    if (mysin[-1] == 's') and ((mysin + "es") == myplu):
        # if ending with an s, like miss/misses
        return True
    if (mysin[-1] == 'y') and ((mysin[:-1] + "ies") == myplu):
        # if ending with an y, like entry/entries
        return True
    # else, no luck
    return False

def domel2dict(doc, use_ord_dict=False, always_singular_list=[]):
    """Recursive function transforming XML elements in a dictionary or list.
    If the node is unique (or it has attributes and the kids have no 'name' attribute),
    then a dictionary with all the attributes is returned
    If the element is singular of the parent (english word is analyzed):
      if it has a 'name' attribute or the parent has attributes, a dictionary is added to the parent (name is the key)
      if if has no name and the parent is empty or a list, then is added to the parent (list)
    :param doc: document or ELEMENT_NODE
    :param use_ord_dict: use ordinate dictionary if True
    :param always_singular_list: these are considered unique singular even if the word is singular form of a plural
    :return: dictionary or list with the content
    """
    myname = doc.nodeName
    data = getXMLAttributes(doc, use_ord_dict) # first insert attributes

    # insert all the subelements
    els = getXMLElements(doc)
    for el in els:
        tag = el.tagName
        #print tag
        eldata = domel2dict(el, use_ord_dict, always_singular_list)
        if is_singular_of(tag, myname, always_singular_list): 
            # subelements, like "param" - "params"
            if "name" in eldata:
                data[eldata['name']] = eldata
                del eldata['name']
            elif ((data == {}) or              # first element, will define everything
                  (isinstance(data, list))):   # already a list
                # most probably one wants a list in this case
                if data == {}:
                    data = []
                data.append(eldata)
            else:
                # cannot use it as a list
                data[tag] = eldata
        else:
            #just a regular subtree
            data[tag] = eldata
    return data


