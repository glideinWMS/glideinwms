#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner
import xml

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

from glideinwms.lib.xmlParse import OrderedDict 
from glideinwms.lib.xmlParse import xmlfile2dict 
from glideinwms.lib.xmlParse import xmlstring2dict 
from glideinwms.lib.xmlParse import getXMLElements 
from glideinwms.lib.xmlParse import getXMLAttributes 
from glideinwms.lib.xmlParse import is_singular_of 
from glideinwms.lib.xmlParse import domel2dict 

xmlstr="""
<test date="1/2/07">
  <params what="xx">
  <param name="x" value="12"/>
  <param name="y" value="88"/>
  </params>
  <files>
     <file absname="/tmp/abc.txt"/>
     <file absname="/tmp/w.log" mod="-rw-r--r--"/>
  </files>
  <temperature F="100" C="40"/>
</test>
"""
xmlstr_dict_repr="""{u'date': u'1/2/07', u'files': [{u'absname': u'/tmp/abc.txt'}, {u'absname': u'/tmp/w.log', u'mod': u'-rw-r--r--'}], u'params': {u'y': {u'value': u'88'}, u'x': {u'value': u'12'}, u'what': u'xx'}, u'temperature': {u'C': u'40', u'F': u'100'}}"""

ordered_dict_values_repr="""[u'1/2/07', [{u'absname': u'/tmp/abc.txt'}, {u'absname': u'/tmp/w.log', u'mod': u'-rw-r--r--'}], {u'y': {u'value': u'88'}, u'x': {u'value': u'12'}, u'what': u'xx'}, {u'C': u'40', u'F': u'100'}]"""

ordered_dict_items_repr="""[(u'date', u'1/2/07'), (u'files', [{u'absname': u'/tmp/abc.txt'}, {u'absname': u'/tmp/w.log', u'mod': u'-rw-r--r--'}]), (u'params', {u'y': {u'value': u'88'}, u'x': {u'value': u'12'}, u'what': u'xx'}), (u'temperature', {u'C': u'40', u'F': u'100'})]"""

expected=""


class TestOrderedDict(unittest.TestCase):

    def test___delitem__(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        od2 = ordered_dict.copy()
        ordered_dict.__delitem__('temperature')
        self.assertTrue('temperature' in od2)
        self.assertFalse('temperature' in ordered_dict)

    def test___init__(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        self.assertNotEqual(ordered_dict, None)

    def test___setitem__(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        ordered_dict.__setitem__("foo", "bar")
        self.assertTrue('foo' in ordered_dict)

    def test_clear(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        ordered_dict.clear()
        self.assertEqual('{}', ordered_dict.__repr__())

    def test_copy(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        od2 = ordered_dict.copy()
        self.assertEqual(od2.__repr__(), ordered_dict.__repr__())

    def test_items(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        self.assertEqual(ordered_dict_items_repr,
                         ordered_dict.items().__repr__())

    def test_keys(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        self.assertEqual("[u'date', u'files', u'params', u'temperature']",
                         ordered_dict.keys().__repr__())

    def test_popitem(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        self.assertEqual("(u'temperature', {u'C': u'40', u'F': u'100'})",
                         ordered_dict.popitem().__repr__())

    def test_setdefault(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        failobj = 'not here'
        ordered_dict.setdefault('Dave', failobj)
        self.assertEqual(ordered_dict.get('Dave'),failobj)
        ordered_dict['Dave'] = 'here'
        self.assertNotEqual(ordered_dict.get('Dave'),failobj)
        self.assertEqual(ordered_dict.get('Dave'),'here')

    def test_update(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        upd = {"foo":"bar"}
        ordered_dict.update(upd)
        self.assertTrue("foo" in ordered_dict)

    def test_values(self):
        dict1 =  xmlstring2dict(xmlstr, use_ord_dict=False,
                               always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        self.assertEqual(ordered_dict_values_repr,
                         ordered_dict.values().__repr__())


class TestXmlfile2dict(unittest.TestCase):

    def test_xmlfile2dict(self):
        infile="fixtures/test_lib_parse.xml"
        dict1 = xmlfile2dict(infile, use_ord_dict=True, always_singular_list=[])
        self.assertEqual(xmlstr_dict_repr, dict1.__repr__())


class TestXmlstring2dict(unittest.TestCase):

    def test_xmlstring2dict(self):
        self.assertEqual(xmlstr_dict_repr,
                         xmlstring2dict(xmlstr,
                                        use_ord_dict=True,
                                        always_singular_list=[]).__repr__())


class TestGetXMLElements(unittest.TestCase):

    def test_get_xml_elements(self):
        doc = xml.dom.minidom.parseString("<xml><foo></foo></xml>")
        self.assertTrue('DOM Element: foo' in  getXMLElements(doc.documentElement).__repr__())


class TestGetXMLAttributes(unittest.TestCase):

    def test_get_xml_attributes(self):
        doc = xml.dom.minidom.parseString("""<xml><foo><param name="x" value="12"/></foo></xml>""")
        self.assertEqual('{}' , getXMLAttributes(doc.documentElement, use_ord_dict=True).__repr__())



class TestIsSingularOf(unittest.TestCase):

    @unittest.skip('private method, not sure how to test')
    def test_is_singular_of(self):
        self.assertEqual(True, is_singular_of(mysin=None,
                                              myplu=None,
                                              always_singular_list=None))
 
class TestDomel2dict(unittest.TestCase):

    @unittest.skip('private method, not sure how to test')
    def test_domel2dict(self):
        self.assertEqual(expected, domel2dict(doc=None,
                                              use_ord_dict=None,
                                              always_singular_list=None))


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
