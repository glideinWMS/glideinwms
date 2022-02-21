#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
    glideinWMS
Purpose:
    unit test of glideinwms/factory/glideFactoryEntry.py
Author:
    Dennis Box, dbox@fnal.gov
"""


import os
import sys
import unittest

from unittest import mock

import xmlrunner

# from glideinwms.factory.glideFactoryEntry import X509Proxies
# from glideinwms.factory.glideFactoryEntry import check_and_perform_work
# from glideinwms.factory.glideFactoryEntry import unit_work_v3
# from glideinwms.factory.glideFactoryEntry import perform_work_v3
# from glideinwms.factory.glideFactoryEntry import write_descript
# from glideinwms.factory.glideFactoryEntry import termsignal
from glideinwms.factory.glideFactoryConfig import FrontendDescript, GlideinDescript
from glideinwms.unittests.unittest_utils import FakeLogger, TestImportError

try:
    import glideinwms.factory.glideFactoryEntry
    import glideinwms.factory.glideFactoryLib

    from glideinwms.factory.glideFactoryEntry import Entry

    # TODO - to remove - code commented in glideFactoryEntry.py because unused
    # from glideinwms.factory.glideFactoryEntry import dump_obj
except ImportError as err:
    raise TestImportError(str(err))


class TestEntry(unittest.TestCase):
    def setUp(self):
        self.testdir = os.getcwd()
        self.datadir = "fixtures/factory/work-dir"
        os.system("git checkout %s" % self.datadir)
        self.startup_dir = os.path.join(self.testdir, self.datadir)
        self.entry_name = "el8_osg34"
        os.chdir(self.datadir)
        self.monitorDir = os.path.join(self.startup_dir, "monitor/entry_%s" % self.entry_name)
        try:
            os.makedirs(self.monitorDir)
        except Exception:
            pass
        self.glidein_descript = GlideinDescript()
        self.frontend_descript = FrontendDescript()
        glideinwms.factory.glideFactoryEntry.logSupport.log = FakeLogger()

        self.entry = Entry(self.entry_name, self.startup_dir, self.glidein_descript, self.frontend_descript)
        os.chdir(self.testdir)

    def tearDown(self):
        os.chdir(self.testdir)

    def test___init__(self):
        self.assertTrue(isinstance(self.entry, Entry))

    @unittest.skip("for now")
    def test_advertise(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.advertise(downtime_flag))
        assert False  # TODO: implement your test here

    # TODO - to remove - code commented in glideFactoryEntry.py because unused
    # @unittest.skip('for now')
    # def test_dump(self):
    #     #entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
    #     #self.assertEqual(expected, entry.dump())
    #     assert False  # TODO: implement your test here

    def test_getGlideinConfiguredLimits(self):
        expected = {
            "DefaultPerFrontendMaxGlideins": 5000,
            "DefaultPerFrontendMaxHeld": 50,
            "DefaultPerFrontendMaxIdle": 100,
            "PerEntryMaxGlideins": 10000,
            "PerEntryMaxHeld": 1000,
            "PerEntryMaxIdle": 2000,
            "PerFrontendMaxGlideins": "",
            "PerFrontendMaxHeld": "",
            "PerFrontendMaxIdle": "",
        }

        tested = self.entry.getGlideinConfiguredLimits()

        self.assertEqual(expected, tested)

    def test_getGlideinExpectedCores(self):
        expected = 1
        self.assertEqual(expected, self.entry.getGlideinExpectedCores())

    def test_getLogStatsCurrentStatsData(self):
        expected = {}
        self.assertEqual(expected, self.entry.getLogStatsCurrentStatsData())

    def test_getLogStatsData(self):
        expected = {}
        stats_data = self.entry.gflFactoryConfig.log_stats.current_stats_data
        self.assertEqual(expected, self.entry.getLogStatsData(stats_data))

    def test_getLogStatsOldStatsData(self):
        expected = {}
        self.assertEqual(expected, self.entry.getLogStatsOldStatsData())

    def test_getState(self):
        self.entry.gflFactoryConfig.client_stats = mock.Mock()
        self.entry.gflFactoryConfig.qc_stats = mock.Mock()
        state = self.entry.getState()
        self.assertTrue("client_internals" in state)
        self.assertTrue("glidein_totals" in state)
        self.assertTrue("limits_triggered" in state)
        self.assertTrue("log_stats" in state)
        self.assertTrue("qc_stats" in state)
        self.assertTrue("rrd_stats" in state)
        # assert False # TODO: implement your test here

    @unittest.skip("4#@!&&*$%")
    def test_glideinsWithinLimits(self):
        expected = {}
        condorQ = mock.Mock()
        getQStatus = mock.Mock()
        getQStatus.return_value = {}
        glideinwms.factory.glideFactoryLib.getQStatus = getQStatus
        glideinTotals = mock.Mock()
        glideinTotals.entry_idle = 1
        glideinTotals.entry_max_idle = 1
        # glideinwms.factory.glideFactoryLib.GlideinTotals = glideinTotals
        condorQ.data = {"foo": "bar", "baz": "boing"}

        self.assertEqual(expected, self.entry.glideinsWithinLimits(condorQ))

    @unittest.skip("for now")
    def test_initIteration(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.initIteration(factory_in_downtime))
        assert False

    def test_isClientBlacklisted(self):
        self.assertEqual(False, self.entry.isClientBlacklisted("All"))

    def test_isClientInWhitelist(self):
        self.assertEqual(False, self.entry.isClientInWhitelist("All"))

    def test_isClientWhitelisted(self):
        self.assertEqual(False, self.entry.isClientWhitelisted("All"))

    @unittest.skip("for now")
    def test_isInDowntime(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.isInDowntime())
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_isSecurityClassAllowed(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.isSecurityClassAllowed(client_sec_name, proxy_sec_class))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_isSecurityClassInDowntime(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.isSecurityClassInDowntime(client_security_name, security_class))
        assert False  # TODO: implement your test here

    def test_loadContext(self):
        self.entry.loadContext()

    @unittest.skip("for now")
    def test_loadDowntimes(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.loadDowntimes())
        assert False  # TODO: implement your test here

    def test_loadWhitelist(self):
        self.entry.loadWhitelist()

    @unittest.skip("for now")
    def test_logLogStats(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.logLogStats(marker))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_queryQueuedGlideins(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.queryQueuedGlideins())
        assert False  # TODO: implement your test here

    def test_setDowntime(self):
        self.entry.loadDowntimes()
        self.entry.setDowntime(False)
        self.assertFalse(self.entry.isInDowntime())

    @unittest.skip("for now")
    def test_setLogStatsCurrentStatsData(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.setLogStatsCurrentStatsData(new_data))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_setLogStatsData(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.setLogStatsData(stats_data, new_data))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_setLogStatsOldStatsData(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.setLogStatsOldStatsData(new_data))
        assert False  # TODO: implement your test here

    def test_setState(self):
        self.entry.gflFactoryConfig.client_stats = mock.Mock()
        self.entry.gflFactoryConfig.qc_stats = mock.Mock()
        state = self.entry.getState()
        self.entry.setState(state)

    @unittest.skip("for now")
    def test_setState_old(self):
        # entry = Entry(name, startup_dir, glidein_descript, frontend_descript)
        # self.assertEqual(expected, entry.setState_old(state))
        assert False  # TODO: implement your test here

    def test_unsetInDowntime(self):
        self.entry.setDowntime(True)
        self.entry.unsetInDowntime()
        self.assertFalse(self.entry.isInDowntime())

    @unittest.skip("doeesnt work")
    def test_writeClassadsToFile(self):
        client_stats = mock.Mock()
        client_stats.current_qc_total = {}
        client_stats.get_total.return_value = {}
        self.entry.gflFactoryConfig.client_stats = client_stats
        downtime_flag = False
        append = False
        gf_filename = os.path.join(self.startup_dir, "gf_filename")
        gfc_filename = os.path.join(self.startup_dir, "gfc_filename")
        limits = self.entry.getGlideinConfiguredLimits()
        self.assertEqual({}, limits)
        limits["PubKeyObj"] = mock.Mock()
        self.entry.writeClassadsToFile(downtime_flag, gf_filename, gfc_filename, append)
        self.assertTrue(os.path.exists(gf_filename))

        self.assertTrue(os.path.exists(gfc_filename))

    def test_writeStats(self):
        self.entry.gflFactoryConfig.qc_stats = mock.Mock()
        self.entry.writeStats()

    # TODO - to remove - code commented in glideFactoryEntry.py because unused
    # def test_dump_obj(self):
    #     save_obj = sys.stdout
    #     sys.stdout = open("dump.data","w")
    #     dump_obj(self.entry)
    #     sys.stdout = save_obj
    #     self.assertTrue(os.path.exists("./dump.data"))
    #     os.remove("dump.data")


# TODO - to remove - code commented in glideFactoryEntry.py because unused
# class TestX509Proxies(unittest.TestCase):
#     @unittest.skip('for now')
#     def test___init__(self):
#         #x509_proxies = X509Proxies(frontendDescript, client_security_name)
#         assert False  # TODO: implement your test here
#
#     @unittest.skip('for now')
#     def test_add_fname(self):
#         # x509_proxies = X509Proxies(frontendDescript, client_security_name)
#         #  self.assertEqual(expected, x509_proxies.add_fname(x509_proxy_security_class, x509_proxy_identifier, x509_proxy_fname))
#         assert False  # TODO: implement your test here
#
#     @unittest.skip('for now')
#     def test_get_username(self):
#         # x509_proxies = X509Proxies(frontendDescript, client_security_name)
#         # self.assertEqual(expected, x509_proxies.get_username(x509_proxy_security_class))
#         assert False  # TODO: implement your test here


class TestCheckAndPerformWork(unittest.TestCase):
    @unittest.skip("for now")
    def test_check_and_perform_work(self):
        # self.assertEqual(expected, check_and_perform_work(factory_in_downtime, entry, work))
        assert False  # TODO: implement your test here


class TestUnitWorkV3(unittest.TestCase):
    @unittest.skip("for now")
    def test_unit_work_v3(self):
        # self.assertEqual(expected, unit_work_v3(entry, work, client_name, client_int_name, client_int_req, client_expected_identity, decrypted_params, params, in_downtime, condorQ))
        assert False  # TODO: implement your test here


class TestPerformWorkV3(unittest.TestCase):
    @unittest.skip("for now")
    def test_perform_work_v3(self):
        # self.assertEqual(expected, perform_work_v3(entry, condorQ, client_name, client_int_name, client_security_name, submit_credentials, remove_excess, idle_glideins, max_glideins, idle_lifetime, credential_username, glidein_totals, frontend_name, client_web, params))
        assert False  # TODO: implement your test here


class TestWriteDescript(unittest.TestCase):
    @unittest.skip("for now")
    def test_write_descript(self):
        # self.assertEqual(expected, write_descript(entry_name, entryDescript, entryAttributes, entryParams, monitor_dir))
        assert False  # TODO: implement your test here


class TestTermsignal(unittest.TestCase):
    @unittest.skip("for now")
    def test_termsignal(self):
        # self.assertEqual(expected, termsignal(signr, frame))
        assert False  # TODO: implement your test here


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
