#
# Description: general purpose XML decoder
#
# Author:
#  Igor Sfiligoi (Mar 27th, 2007)
#

import xml.dom.minidom

# convert a XML file into a dictionary
# ignore text sections
def xmlfile2dict(fname):
    doc=xml.dom.minidom.parse(fname)

    data=domel2dict(doc.documentElement)

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
#   <temperature F="100" C="40"/>
#  </test>
# becomes
#  {u'date': u'1/2/07',
#   u'params': {u'y': u'88',
#               u'x': u'12',
#               u'what': u'xx'},
#   u'temperature': {u'C': u'40',
#                    u'F': u'100'}
#  }
#  
def xmlstring2dict(str):
    doc=xml.dom.minidom.parseString(str)

    data=domel2dict(doc.documentElement)

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
    els=[]
    for el in basic_els:
         if el.nodeType==el.ELEMENT_NODE:
            els.append(el)

    return els

def getXMLAttributes(element):
    ael=element.attributes
    
    attrs={}
    attr_len=ael.length
    for i in range(attr_len):
        attr=ael.item(i)
        attrs[attr.nodeName]=attr.nodeValue

    return attrs

def is_singular_of(mysin,myplu):
    if myplu[-1]!='s':
        return False # if myplu does not end in s, it is not plural
    if (mysin+"s")==myplu: # regular, like attr/attrs
        return True
    if (mysin[-1]=='s') and ((mysin+"es")==myplu): # if ending with an s, like miss/misses
        return True
    if (mysin[-1]=='y') and ((mysin[:-1]+"ies")==myplu): # if ending with an y, like entry/entries
        return True
    # else, no luck
    return False

def domel2dict(doc):
    myname=doc.nodeName
    data=getXMLAttributes(doc) # first insert attributes

    # insert all the subelements
    els=getXMLElements(doc)
    for el in els:
        tag = el.tagName
        #print tag
        eldata=domel2dict(el)
        if (is_singular_of(tag,myname) and        # subelements, like "param" - "params"
            (len(eldata.keys())==2) and eldata.has_key("name") and eldata.has_key("value")): # it is a name/value pair
            data[eldata['name']]=eldata['value']
        elif (is_singular_of(tag,myname) and        # subelements, like "param" - "params"
              eldata.has_key("name")):              # it ihas a name, but not a value
            data[eldata['name']]=eldata
            del eldata['name']
        else: #just a regular subtree
            data[tag]=eldata
    return data


def xmlfile2dict(fname):
    doc=xml.dom.minidom.parse(fname)

    data=domel2dict(doc.documentElement)

    return data


#x=xmlfile2dict("../create/config_examples/simple_test1.xml")
#print x
