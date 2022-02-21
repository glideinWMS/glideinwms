#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
   Project: glideinwms
   File: test_creation_lib_cgWCreate.py
   Purpose: unit test of glideinwms/creation/lib/cgWCreate.py
   Author: Dennis Box, dbox@fnal.gov
"""

import unittest

import glideinwms.creation.lib.cgWCreate

from glideinwms.creation.lib.cgWCreate import GlideinSubmitDictFile
from glideinwms.creation.lib.factoryXmlConfig import (
    CondTarElement,
    Config,
    EntryElement,
    EntrySetElement,
    FactAttrElement,
    FactFileElement,
    FrontendElement,
    parse,
)

XML = "fixtures/factory/glideinWMS.xml"


# pylint: disable=maybe-no-member


class TestGlideinSubmitDictFile(unittest.TestCase):
    def setUp(self):
        self.conf = parse(XML)
        self.entry_name = "TEST_SITE_1"
        self.entry = None
        for entr in self.conf.get_entries():
            if self.entry_name == entr.getName():
                self.entry = entr

        self.gsdf = GlideinSubmitDictFile("fixtures/factory/work-dir", self.entry_name)

    def test_populate(self):
        self.gsdf.populate("an_exe", self.entry_name, self.conf, self.entry)

    def test_populate_standard_grid(self):
        rsl = "rsl"
        auth_method = "you look trustworthy, go ahead"
        gridtype = "gt2"
        entry_enabled = "True"
        try:
            self.gsdf.populate_standard_grid(rsl, auth_method, gridtype, entry_enabled, self.entry_name)
            assert False  # Should have thrown RunTimeError!!
        except RuntimeError as err:
            pass


# pylint: enable=maybe-no-member

if __name__ == "__main__":
    unittest.main()
