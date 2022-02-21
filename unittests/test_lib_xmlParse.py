#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# Description:
#   unit test for glideinwms/lib/xmlParse.py
#
# Author:
#   Dennis Box dbox@fnal.gov
#


import unittest
import xml

import xmlrunner

# TODO: should OrderedDict be removed, it is the one from the stdlib. But tests are texting XML conversion as well
#       should be directly: from collections import OrderedDict
from glideinwms.lib.xmlParse import (
    domel2dict,
    getXMLAttributes,
    getXMLElements,
    is_singular_of,
    OrderedDict,
    xmlfile2dict,
    xmlstring2dict,
)

xmlstr = """
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
xmlstr_dict_repr = """{'date': '1/2/07', 'params': {'what': 'xx', 'x': {'value': '12'}, 'y': {'value': '88'}}, 'files': [{'absname': '/tmp/abc.txt'}, {'absname': '/tmp/w.log', 'mod': '-rw-r--r--'}], 'temperature': {'F': '100', 'C': '40'}}"""

ordered_dict_values_repr = """['1/2/07', {'what': 'xx', 'x': {'value': '12'}, 'y': {'value': '88'}}, [{'absname': '/tmp/abc.txt'}, {'absname': '/tmp/w.log', 'mod': '-rw-r--r--'}], {'F': '100', 'C': '40'}]"""

ordered_dict_items_repr = """[('date', '1/2/07'), ('params', {'what': 'xx', 'x': {'value': '12'}, 'y': {'value': '88'}}), ('files', [{'absname': '/tmp/abc.txt'}, {'absname': '/tmp/w.log', 'mod': '-rw-r--r--'}]), ('temperature', {'F': '100', 'C': '40'})]"""

expected = ""


class TestOrderedDict(unittest.TestCase):
    def test___delitem__(self):
        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        od2 = ordered_dict.copy()
        ordered_dict.__delitem__("temperature")
        self.assertTrue("temperature" in od2)
        self.assertFalse("temperature" in ordered_dict)

    def test___init__(self):
        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        self.assertNotEqual(ordered_dict, None)

    def test___setitem__(self):
        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        ordered_dict.__setitem__("foo", "bar")
        self.assertTrue("foo" in ordered_dict)

    def test_clear(self):
        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        ordered_dict.clear()
        self.assertEqual("{}", ordered_dict.__repr__())

    def test_copy(self):
        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        od2 = ordered_dict.copy()
        self.assertEqual(od2.__repr__(), ordered_dict.__repr__())

    def test_items(self):
        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        self.assertEqual(ordered_dict_items_repr, list(ordered_dict.items()).__repr__())

    def test_keys(self):
        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        self.assertEqual("['date', 'params', 'files', 'temperature']", list(ordered_dict.keys()).__repr__())

    def test_popitem(self):
        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        self.assertEqual("('temperature', {'F': '100', 'C': '40'})", ordered_dict.popitem().__repr__())

    def test_setdefault(self):
        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        failobj = "not here"
        ordered_dict.setdefault("Dave", failobj)
        self.assertEqual(ordered_dict.get("Dave"), failobj)
        ordered_dict["Dave"] = "here"
        self.assertNotEqual(ordered_dict.get("Dave"), failobj)
        self.assertEqual(ordered_dict.get("Dave"), "here")

    def test_update(self):
        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        upd = {"foo": "bar"}
        ordered_dict.update(upd)
        self.assertTrue("foo" in ordered_dict)

    def test_values(self):

        dict1 = xmlstring2dict(xmlstr, use_ord_dict=False, always_singular_list=[])
        ordered_dict = OrderedDict(dict1)
        self.assertEqual(ordered_dict_values_repr, list(ordered_dict.values()).__repr__())


class TestXmlfile2dict(unittest.TestCase):
    def test_xmlfile2dict(self):
        infile = "fixtures/test_lib_parse.xml"
        dict1 = xmlfile2dict(infile, use_ord_dict=True, always_singular_list=[])
        self.assertEqual(xmlstr_dict_repr, dict1.__repr__())


class TestXmlstring2dict(unittest.TestCase):
    def test_xmlstring2dict(self):
        self.assertEqual(
            xmlstr_dict_repr, xmlstring2dict(xmlstr, use_ord_dict=True, always_singular_list=[]).__repr__()
        )


#
# These are all private
#


class TestGetXMLElements(unittest.TestCase):
    def test_get_xml_elements(self):
        doc = xml.dom.minidom.parseString("<xml><foo></foo></xml>")
        self.assertTrue("DOM Element: foo" in getXMLElements(doc.documentElement).__repr__())


class TestGetXMLAttributes(unittest.TestCase):
    def test_get_xml_attributes(self):
        doc = xml.dom.minidom.parseString("""<xml><foo><param name="x" value="12"/></foo></xml>""")
        self.assertEqual("{}", getXMLAttributes(doc.documentElement, use_ord_dict=True).__repr__())


class TestIsSingularOf(unittest.TestCase):
    def test_is_singular_of(self):

        self.assertEqual(True, is_singular_of(mysin="dog", myplu="dogs", always_singular_list=[]))
        self.assertEqual(True, is_singular_of(mysin="goose", myplu="geese", always_singular_list=["goose", "dog"]))
        self.assertEqual(False, is_singular_of(mysin="moose", myplu="meese", always_singular_list=["goose", "dog"]))
        self.assertEqual(True, is_singular_of(mysin="miss", myplu="misses", always_singular_list=["goose", "dog"]))
        self.assertEqual(True, is_singular_of(mysin="army", myplu="armies", always_singular_list=["goose", "dog"]))


class TestDomel2dict(unittest.TestCase):
    def test_domel2dict(self):
        doc = xml.dom.minidom.parseString(xmlstr)
        self.assertTrue(isinstance(domel2dict(doc.documentElement), dict))


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
