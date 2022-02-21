#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
    glideinWMS
Purpose:
    unit test for glideinwms/factory/glideFactoryConfig.py
Author:
    Dennis Box, dbox@fnal.gov
"""


import os
import unittest

import xmlrunner

from glideinwms.factory.glideFactoryConfig import (
    ConfigFile,
    EntryConfigFile,
    FrontendDescript,
    GlideinDescript,
    GlideinKey,
    JobAttributes,
    JobDescript,
    JobParams,
    JoinConfigFile,
    SignatureFile,
)
from glideinwms.unittests.unittest_utils import TestImportError

try:
    from glideinwms.factory.glideFactoryConfig import FactoryConfig
except ImportError as err:
    raise TestImportError(str(err))


class TestFactoryConfig(unittest.TestCase):
    def setUp(self):
        self.testdir = os.getcwd()
        self.confdir = "fixtures/factory/work-dir"
        os.system("git checkout -q %s" % self.confdir)
        os.chdir(self.confdir)
        self.factory_config = FactoryConfig()
        self.entry_config = EntryConfigFile("el8_osg34", "attributes.cfg")
        self.job_descript = JobDescript(self.entry_config.entry_name)
        self.job_attrs = JobAttributes(self.entry_config.entry_name)
        self.job_params = JobParams(self.entry_config.entry_name)
        self.glidein_descript = GlideinDescript()
        self.frontend_descript = FrontendDescript()
        self.signatures = SignatureFile()
        os.chdir(self.testdir)

    def tearDown(self):
        os.chdir(self.testdir)
        rsafile = os.path.join(self.confdir, "rsa.key")
        if os.path.exists(rsafile):
            cmd = "git checkout -q %s " % rsafile
            os.system(cmd)

    def test__init__(self):
        self.assertTrue(isinstance(self.factory_config, FactoryConfig))

    def test_get_all_usernames(self):
        all = self.frontend_descript.get_all_usernames()
        self.assertEqual(["frontend"], all)

    def test_get_identity(self):
        id = self.frontend_descript.get_identity("vofrontend_service")
        self.assertEqual("vofrontend_service@fermicloud322.fnal.gov", id)

    def test_get_username(self):
        id = self.frontend_descript.get_username("vofrontend_service", "frontend")
        self.assertEqual("frontend", id)

    def test_get_all_frontend_sec_classes(self):
        id = self.frontend_descript.get_all_frontend_sec_classes()
        self.assertEqual(["vofrontend_service:frontend"], id)

    def test_get_frontend_name(self):
        id = self.frontend_descript.get_frontend_name("vofrontend_service@fermicloud322.fnal.gov")
        self.assertEqual("vofrontend_service", id)

    def test__contains__(self):
        self.assertFalse(self.frontend_descript.__contains__("bazzlesnort"))
        self.assertTrue(self.frontend_descript.__contains__("vofrontend_service"))

    def test_has_key(self):
        self.assertFalse("bazzlesnort" in self.frontend_descript)
        self.assertTrue("vofrontend_service" in self.frontend_descript)

    def test_str_(self):
        strdict = self.frontend_descript.__str__()
        self.assertTrue(isinstance(strdict, str))
        self.assertNotEqual("", strdict)

    def test_backup_and_load_old_key(self):
        os.chdir(self.confdir)
        self.glidein_descript.backup_and_load_old_key()
        os.chdir(self.testdir)

    def test_backup_rsa_key(self):
        os.chdir(self.confdir)
        self.glidein_descript.backup_rsa_key()
        os.chdir(self.testdir)

    def test_load_old_rsa_key(self):
        os.chdir(self.confdir)
        self.glidein_descript.load_old_rsa_key()
        os.chdir(self.testdir)

    def test_remove_old_key(self):
        os.chdir(self.confdir)
        self.glidein_descript.remove_old_key()
        os.chdir(self.testdir)

    def test_load_pub_key(self):
        os.chdir(self.confdir)
        self.glidein_descript.load_pub_key(True)
        os.chdir(self.testdir)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
