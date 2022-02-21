#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
    glideinWMS
Purpose:
    unit test for glideinwms/frontend/glideinFrontendElement.py
Author:
    Dennis Box, dbox@fnal.gov
"""


import os
import unittest

from unittest import mock

import xmlrunner

import glideinwms
import glideinwms.lib.condorExe as condorExe
import glideinwms.lib.condorMonitor as condorMonitor

from glideinwms.frontend import glideinFrontendMonitoring
from glideinwms.frontend.glideinFrontendElement import (
    check_parent,
    CounterWrapper,
    glideinFrontendElement,
    init_factory_stats_arr,
    log_and_sum_factory_line,
    log_factory_header,
    write_stats,
)
from glideinwms.unittests.unittest_utils import FakeLogger

LOG_DATA = []


def log_side_effect(*args, **kwargs):
    LOG_DATA.append(args[0])


def condor_q_side_effect():
    fnm = "cs.schedd.fixture"
    return readit(fnm)


def condor_status_side_effect():
    fnm = "cs.fixture"
    return readit(fnm)


#    elif 'schedd' in args[0].lower():
#        fnm = 'cs.schedd.fixture'
#    else:
#        fnm = 'cs.fixture'


def readit(fnm):
    with open(fnm) as fdd:
        lines = fdd.readlines()
    return lines


def query_factory_side_effect(*args, **kwargs):
    fnm = "fixtures/frontend/query_factory.fixture"
    with open(fnm) as fdd:
        blob = fdd.read()
    return eval(blob)


class TestCounterWrapper(unittest.TestCase):
    def setUp(self):
        dd = {"a": "b", "c": "d"}
        self.cw = CounterWrapper(dd)

    def test___contains__(self):
        self.assertTrue(self.cw.__contains__("a"))
        self.assertFalse(self.cw.__contains__("b"))

    def test___delitem__(self):
        self.cw.__delitem__("a")
        self.assertFalse(self.cw.__contains__("a"))
        self.assertTrue(self.cw.__contains__("c"))
        del self.cw["c"]
        self.assertFalse("c" in self.cw)

    def test___getitem__(self):
        self.assertEqual("b", self.cw.__getitem__("a"))
        self.assertEqual("d", self.cw["c"])

    def test___setitem__(self):
        self.cw.__setitem__("e", "f")
        self.assertTrue(self.cw.__contains__("e"))
        self.cw["g"] = "h"
        self.assertTrue("g" in self.cw)

    def test_has_key(self):
        self.assertTrue("a" in self.cw)
        self.assertFalse(self.cw.__contains__("b"))


class TestGlideinFrontendElement(unittest.TestCase):
    def setUp(self):
        parent_pid = 0
        work_dir = "fixtures/frontend"
        group_name = "group1"
        action = "yada yada"
        condorMonitor.USE_HTCONDOR_PYTHON_BINDINGS = False
        condorMonitor.LocalScheddCache.iGetEnv = mock.Mock()
        # condorExe.exe_cmd = mock.Mock()
        # condorExe.exe_cmd.side_effect = condor_side_effect
        glideinwms.frontend.glideinFrontendLib.logSupport.log = FakeLogger()
        self.gfe = glideinFrontendElement(os.getpid(), work_dir, group_name, action)
        self.gfe.frontend_name = "Frontend-master-v1_0"
        # self.gfe.configure()
        init_factory_stats_arr()
        self.verbose = os.environ.get("DEBUG_OUTPUT")
        self.gfe.get_condor_q = mock.Mock()
        self.gfe.get_condor_q.side_effect = condor_q_side_effect
        self.gfe.get_condor_status = mock.Mock()
        self.gfe.get_condor_status.side_effect = condor_status_side_effect

    def test___init__(self):
        if self.verbose:
            print("\nglideinFrontendElement=%s" % self.gfe)
            print("\ndir glideinFrontendElement=%s" % dir(self.gfe))
            print("\nglideinFrontendElement.attr_dict=%s" % self.gfe.attr_dict)
        self.assertTrue(isinstance(self.gfe, glideinFrontendElement))

    def test_configure(self):
        v = "CONDOR_CONFIG"
        b_cc = os.environ.get(v)
        v = "_CONDOR_CERTIFICATE_MAPFILE"
        b_ccm = os.environ.get(v)
        v = "X509_USER_PROXY"
        b_xup = os.environ.get(v)
        self.gfe.configure()
        if self.verbose:
            print("\nc.glideinFrontendElement=%s" % self.gfe)
            print("\nc.dir glideinFrontendElement=%s" % dir(self.gfe))
            print("\nc.glideinFrontendElement.attr_dict=%s" % self.gfe.attr_dict)
        v = "CONDOR_CONFIG"
        a_cc = os.environ.get(v)
        v = "_CONDOR_CERTIFICATE_MAPFILE"
        a_ccm = os.environ.get(v)
        v = "X509_USER_PROXY"
        a_xup = os.environ.get(v)
        self.assertNotEqual(b_cc, a_cc)
        self.assertNotEqual(b_ccm, a_ccm)
        self.assertNotEqual(b_xup, a_xup)

    def test_set_glidein_config_limits(self):
        self.gfe.set_glidein_config_limits()

    def test_check_removal_config(self):
        glideid = None
        self.gfe.removal_type = "DISABLE"
        self.assertEqual("DISABLE", self.gfe.check_removal_type_config(glideid))
        self.gfe.removal_type = None
        self.assertEqual("NO", self.gfe.check_removal_type_config(glideid))

    def test_init_factory_stats_arr(self):
        arr = init_factory_stats_arr()
        for ind in range(16):
            self.assertEqual(arr[ind], 0)

    def test_log_factory_header(self):
        mockery = mock.MagicMock()
        glideinwms.frontend.glideinFrontendLib.logSupport.log = mockery
        mockery.info.side_effect = log_side_effect
        log_factory_header()
        self.assertEqual(len(LOG_DATA), 2)

    @unittest.skip("for now")
    def test_build_resource_classad(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.build_resource_classad(this_stats_arr, request_name, glidein_el, glidein_in_downtime, factory_pool_node, my_identity, limits_triggered))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_choose_remove_excess_type(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.choose_remove_excess_type(count_jobs, count_status, glideid))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_compute_glidein_max_run(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.compute_glidein_max_run(prop_jobs, real, idle_glideins))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_compute_glidein_min_idle(self):
        # g# lidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.compute_glidein_min_idle(count_status, total_glideins, total_idle_glideins, fe_total_glideins, fe_total_idle_glideins, global_total_glideins, global_total_idle_glideins, effective_idle, effective_oldidle, limits_triggered))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_count_factory_entries_without_classads(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.count_factory_entries_without_classads(total_down_stats_arr))
        assert False  # TODO: implement your test here

    def test_deadvertiseAllClassads(self):
        self.gfe.configure()
        self.gfe.deadvertiseAllClassads()

    @unittest.skip("for now")
    def test_identify_bad_schedds(self):
        self.gfe.identify_bad_schedds()

    @unittest.skip("for now")
    def test_identify_limits_triggered(self):
        # self.gfe.identify_limits_triggered(count_status, total_glideins,
        #                                   total_idle_glideins, fe_total_glideins, fe_total_idle_glideins,
        #                                   global_total_glideins, global_total_idle_glideins,
        #                                   limits_triggered)
        assert False

    @unittest.skip("for now")
    def test_iterate(self):
        self.gfe.configure()
        self.gfe.action = "run"
        self.gfe.query_factory = mock.Mock()
        self.gfe.query_factory.side_effect = query_factory_side_effect
        self.gfe.iterate()
        # print('after iteration self.gfe=%s' % self.gfe)
        # print('dir self.gfe=%s' % dir(self.gfe))
        print("after iteration self.gfe.stats=%s" % dir(self.gfe.stats))
        print('after iteration self.gfe.stats["group"].data=%s' % self.gfe.stats["group"].data)

    @unittest.skip("for now")
    def test_log_and_print_total_stats(self):
        # self.gfe.log_and_print_total_stats(
        #    total_up_stats_arr, total_down_stats_arr)
        assert False

    @unittest.skip("for now")
    def test_log_and_print_unmatched(self):
        # self.gfe.log_and_print_unmatched(total_down_stats_arr)
        assert False

    @unittest.skip("for now")
    def test_populate_condorq_dict_types(self):
        self.gfe.condorq_dict = {
            "Idle_3600": {"abs": 0, "dict": {}},
            "IdleAll": {"abs": 0, "dict": {}},
            "Running": {"abs": 0, "dict": {}},
            "Idle": {"abs": 0, "dict": {}},
            "OldIdle": {"abs": 0, "dict": {}},
            "VomsIdle": {"abs": 0, "dict": {}},
        }
        self.gfe.blacklist_schedds = []
        self.gfe.populate_condorq_dict_types()

    def test_populate_pubkey(self):
        globals_el = {"attrs": {"PubKeyValue": None, "PubKeyObj": None}}
        self.gfe.globals_dict = {"my_global_id": globals_el}
        self.gfe.populate_pubkey()
        key_obj = self.gfe.globals_dict["my_global_id"]["attrs"]["PubKeyObj"]
        self.assertTrue(isinstance(key_obj, glideinwms.lib.pubCrypto.PubRSAKey))

    def test_populate_status_dict_types(self):
        self.gfe.status_dict = {}
        self.gfe.populate_status_dict_types()
        expected = {
            "RunningCores": {"abs": 0, "dict": {}},
            "TotalCores": {"abs": 0, "dict": {}},
            "Running": {"abs": 0, "dict": {}},
            "IdleCores": {"abs": 0, "dict": {}},
            "Failed": {"abs": 0, "dict": {}},
            "Idle": {"abs": 0, "dict": {}},
            "Total": {"abs": 0, "dict": {}},
        }
        for key in expected:
            self.assertTrue(key in self.gfe.status_dict_types, self.gfe.status_dict_types)

    @unittest.skip("for now")
    def test_query_entries(self):
        # self.gfe.query_entries(factory_pool)
        assert False

    @unittest.skip("for now")
    def test_query_factory(self):
        # self.gfe.query_factory(factory_pool)
        assert False

    @unittest.skip("for now")
    def test_query_factoryclients(self):
        # self.gfe.query_factoryclients(factory_pool)
        assert False

    @unittest.skip("for now")
    def test_query_globals(self):
        # self.gfe.query_globals(factory_pool)
        assert False

    @unittest.skip("for now")
    def test_subprocess_count_dt(self):
        # self.gfe.subprocess_count_dt(dt)
        assert False

    @unittest.skip("for now")
    def test_subprocess_count_glidein(self):
        # self.gfe.subprocess_count_glidein(glidein_list)
        assert False

    @unittest.skip("for now")
    def test_subprocess_count_real(self):
        # self.gfe.subprocess_count_real()
        assert False

    @unittest.skip("for now")
    def test_write_stats(self):
        # write_stats(stats)
        assert False

    @unittest.skip("for now")
    def test_expand__d_d(self):
        # expand_DD(qstr, attr_dict)
        assert False

    @unittest.skip("grr")
    def test_decide_removal_type(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.decide_removal_type(count_jobs, count_status, glideid))
        assert False  # TODO: implement your test here

    @unittest.skip("grr")
    def test_get_condor_status(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.get_condor_status())
        assert False  # TODO: implement your test here

    @unittest.skip("grr")
    def test_main(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.main())
        assert False  # TODO: implement your test here


class TestCheckParent(unittest.TestCase):
    def test_check_parent(self):
        mockery = mock.MagicMock()
        glideinwms.frontend.glideinFrontendLib.logSupport.log = mockery
        mockery.info.side_effect = log_side_effect
        parent_pid = os.getppid()
        self.assertEqual(None, check_parent(parent_pid))
        assert True
        parent_pid = "force exception"
        try:
            check_parent(parent_pid)
        except KeyboardInterrupt:
            assert True
            return
        assert False


class TestLogAndSumFactoryLine(unittest.TestCase):
    def test_log_and_sum_factory_line(self):
        mockery = mock.MagicMock()
        glideinwms.frontend.glideinFrontendLib.logSupport.log = mockery
        mockery.info.side_effect = log_side_effect
        expected = [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
        factory = "OSG"
        is_down = False
        factory_stat_arr = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        old_factory_stat_arr = factory_stat_arr
        self.assertEqual(expected, log_and_sum_factory_line(factory, is_down, factory_stat_arr, old_factory_stat_arr))


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
