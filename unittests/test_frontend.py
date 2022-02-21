#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/creation/lib/cgWConsts.py

 Author:
   Burt Holtzman <burt@fnal.gov>
"""

#   [for rrdtool: pip install git+https://github.com/holzman/python-rrdtool]


import dis
import io
import re
import sys
import unittest

from unittest import mock

import xmlrunner

import glideinwms.frontend.glideinFrontendLib as glideinFrontendLib
import glideinwms.lib.condorExe
import glideinwms.lib.condorMonitor as condorMonitor

from glideinwms.frontend.glideinFrontendLib import getClientCondorStatusCredIdOnly, getClientCondorStatusPerCredId
from glideinwms.unittests.unittest_utils import FakeLogger

# todo
# def countMatch
# def evalParamExpr


def compareLambdas(func1, func2):
    def strip_line_number(code):
        r = re.match(r"\s*\d+\s+(.*)", code[0])
        code[0] = r.group(1)

    def disassemble(func):
        out = io.StringIO()
        err = io.StringIO()
        saved = (sys.stdout, sys.stderr)
        sys.stdout = out
        sys.stderr = err
        dis.dis(func)
        sys.stdout, sys.stderr = saved
        out.seek(0)
        return out.readlines()

    code1 = disassemble(func1)
    code2 = disassemble(func2)
    strip_line_number(code1)
    strip_line_number(code2)

    if code1 != code2:
        print("".join(code1))
        print("".join(code2))
    #        pass
    return code1 == code2


class FETestCaseBase(unittest.TestCase):
    def setUp(self):
        glideinwms.frontend.glideinFrontendLib.logSupport.log = FakeLogger()
        # Only condor cliens are mocked, not the python bindings
        condorMonitor.USE_HTCONDOR_PYTHON_BINDINGS = False
        with mock.patch("glideinwms.lib.condorExe.exe_cmd") as m_exe_cmd:
            f = open("cs.fixture")
            m_exe_cmd.return_value = f.readlines()
            self.status_dict = glideinFrontendLib.getCondorStatus(["coll1"])

        self.frontend_name = "fe_name"
        self.group_name = "group_name"
        self.request_name = "request_name"
        self.cred_id = 1234
        self.default_format = [
            ("JobStatus", "i"),
            ("EnteredCurrentStatus", "i"),
            ("ServerTime", "i"),
            ("RemoteHost", "s"),
        ]

        self.prepare_condorq_dict()

        self.glidein_dict_k1 = ("submit.local", "Site_Name1@v3_0@factory1", "frontend@factory1")
        self.glidein_dict_k2 = ("submit.local", "Site_Name2@v3_0@factory1", "frontend@factory1")
        self.glidein_dict_k3 = ("submit.local", "Site_Name3@v3_0@factory1", "frontend@factory1")
        self.glidein_dict = {
            self.glidein_dict_k1: {
                "attrs": {"GLIDEIN_Site": "Site_Name1", "GLIDEIN_CPUS": 1},
                "monitor": {},
                "params": {},
            },
            self.glidein_dict_k2: {
                "attrs": {"GLIDEIN_Site": "Site_Name2", "GLIDEIN_CPUS": 4},
                "monitor": {},
                "params": {},
            },
            self.glidein_dict_k3: {
                "attrs": {"GLIDEIN_Site": "Site_Name3", "GLIDEIN_CPUS": "aUtO"},
                "monitor": {},
                "params": {},
            },
        }

    def prepare_condorq_dict(self):
        with mock.patch("glideinwms.lib.condorMonitor.LocalScheddCache.iGetEnv") as m_iGetEnv:
            cq = condorMonitor.CondorQ(schedd_name="sched1", pool_name="pool1")

        with mock.patch("glideinwms.lib.condorExe.exe_cmd") as m_exe_cmd:
            f = open("cq.fixture")
            m_exe_cmd.return_value = f.readlines()
            cq.load()

        self.condorq_dict = {"sched1": cq}


class FETestCaseCount(FETestCaseBase):
    def setUp(self):
        super().setUp()

    def test_countMatch_missingKey(self):
        with mock.patch.object(glideinwms.frontend.glideinFrontendLib.logSupport.log, "debug") as m_debug:

            match_obj = compile('glidein["attrs"]["FOO"] == 3', "<string>", "eval")
            match_counts = glideinFrontendLib.countMatch(match_obj, self.condorq_dict, self.glidein_dict, {}, False)
            m_debug.assert_called_with(
                "Failed to evaluate resource match in countMatch. Possibly match_expr has "
                "errors and trying to reference job or site attribute(s) ''FOO'' in an inappropriate way."
            )

    def test_countMatch_otherException(self):
        with mock.patch.object(glideinwms.frontend.glideinFrontendLib.logSupport.log, "debug") as m_debug:
            match_obj = compile("3//0", "<string>", "eval")
            match_counts = glideinFrontendLib.countMatch(match_obj, self.condorq_dict, self.glidein_dict, {}, False)
            log_msg = m_debug.call_args[0]

            self.assertTrue("Most recent traceback" in str(log_msg), log_msg)
            self.assertTrue("ZeroDivisionError: integer division or modulo by zero" in str(log_msg), log_msg)

    def test_countMatch(self):
        match_expr = 'not "DESIRED_Sites" in job or glidein["attrs"].get("GLIDEIN_Site") in job["DESIRED_Sites"]'
        match_obj = compile(match_expr, "<string>", "eval")
        unmatched = (None, None, None)
        match_counts = glideinFrontendLib.countMatch(match_obj, self.condorq_dict, self.glidein_dict, {}, False)

        straight_match = match_counts[0]
        # straight match
        self.assertEqual(
            (
                straight_match[self.glidein_dict_k1],
                straight_match[self.glidein_dict_k2],
                straight_match[self.glidein_dict_k3],
            ),
            (10, 8, 4),
        )

        prop_match = match_counts[1]
        # proportional match
        self.assertEqual(
            (prop_match[self.glidein_dict_k1], prop_match[self.glidein_dict_k2], prop_match[self.glidein_dict_k3]),
            (7, 5, 2),
        )

        only_match = match_counts[2]
        # only match: elements can only run on this site
        self.assertEqual(
            (only_match[self.glidein_dict_k1], only_match[self.glidein_dict_k2], only_match[self.glidein_dict_k3]),
            (4, 2, 0),
        )

        uniq_match = match_counts[3]
        # uniq match: glideins requested based on unique subsets after
        # considering multicore
        self.assertEqual(
            (uniq_match[self.glidein_dict_k1], uniq_match[self.glidein_dict_k2], uniq_match[self.glidein_dict_k3]),
            (7, 2, 2),
        )

        # unmatched
        self.assertEqual(
            (straight_match[unmatched], prop_match[unmatched], only_match[unmatched], uniq_match[unmatched]),
            (1, 1, 1, 1),
        )

    def test_countMatchDowntime(self):
        self.glidein_dict[self.glidein_dict_k1]["attrs"]["GLIDEIN_In_Downtime"] = True
        # test_countMatch should give the same results unless we call countMatch with ignore_down_entries = False
        self.test_countMatch()
        match_expr = 'not "DESIRED_Sites" in job or glidein["attrs"].get("GLIDEIN_Site") in job["DESIRED_Sites"]'
        match_obj = compile(match_expr, "<string>", "eval")
        unmatched = (None, None, None)
        match_counts = glideinFrontendLib.countMatch(match_obj, self.condorq_dict, self.glidein_dict, {}, True)

        straight_match = match_counts[0]
        # glidein 1 is not matching anymore. There are more unmatched now
        self.assertEqual(
            (
                straight_match[self.glidein_dict_k1],
                straight_match[self.glidein_dict_k2],
                straight_match[self.glidein_dict_k3],
                straight_match[unmatched],
            ),
            (0, 8, 4, 5),
        )

    def test_countRealRunning_match(self):
        cq_run_dict = glideinFrontendLib.getRunningCondorQ(self.condorq_dict)
        glideinFrontendLib.appendRealRunning(cq_run_dict, self.status_dict)

        match_obj = compile("True", "<string>", "eval")
        actual = glideinFrontendLib.countRealRunning(match_obj, cq_run_dict, self.glidein_dict, {})
        expected = (
            {self.glidein_dict_k1: 1, self.glidein_dict_k2: 4, self.glidein_dict_k3: 0},
            {self.glidein_dict_k1: 1, self.glidein_dict_k2: 3, self.glidein_dict_k3: 0},
        )
        self.assertEqual(expected, actual)

        match_obj = compile("False", "<string>", "eval")
        actual = glideinFrontendLib.countRealRunning(match_obj, cq_run_dict, self.glidein_dict, {})
        expected = (
            {self.glidein_dict_k1: 0, self.glidein_dict_k2: 0, self.glidein_dict_k3: 0},
            {self.glidein_dict_k1: 0, self.glidein_dict_k2: 0, self.glidein_dict_k3: 0},
        )
        self.assertEqual(expected, actual)

        match_expr = 'glidein["attrs"].get("GLIDEIN_Site") in job.get("DESIRED_Sites", [])'
        match_obj = compile(match_expr, "<string>", "eval")
        actual = glideinFrontendLib.countRealRunning(match_obj, cq_run_dict, self.glidein_dict, {})
        expected = (
            {self.glidein_dict_k1: 1, self.glidein_dict_k2: 1, self.glidein_dict_k3: 0},
            {self.glidein_dict_k1: 1, self.glidein_dict_k2: 1, self.glidein_dict_k3: 0},
        )
        self.assertEqual(expected, actual)

    def test_countRealRunning_missingKey(self):
        cq_run_dict = glideinFrontendLib.getRunningCondorQ(self.condorq_dict)
        glideinFrontendLib.appendRealRunning(cq_run_dict, self.status_dict)

        with mock.patch.object(glideinwms.frontend.glideinFrontendLib.logSupport.log, "debug") as m_debug:
            match_obj = compile('glidein["attrs"]["FOO"] == 3', "<string>", "eval")
            actual = glideinFrontendLib.countRealRunning(match_obj, cq_run_dict, self.glidein_dict, {})
            m_debug.assert_any_call(
                "Failed to evaluate resource match in countRealRunning. Possibly match_expr has "
                "errors and trying to reference job or site attribute(s) ''FOO'' in an inappropriate way."
            )

    def test_countRealRunning_otherException(self):
        cq_run_dict = glideinFrontendLib.getRunningCondorQ(self.condorq_dict)
        glideinFrontendLib.appendRealRunning(cq_run_dict, self.status_dict)
        with mock.patch.object(glideinwms.frontend.glideinFrontendLib.logSupport.log, "debug") as m_debug:
            match_obj = compile("3/0", "<string>", "eval")
            actual = glideinFrontendLib.countRealRunning(match_obj, cq_run_dict, self.glidein_dict, {})
            log_msg = m_debug.call_args[0]

            self.assertTrue("Running glidein ids at " in str(log_msg), log_msg)
            self.assertTrue("total glideins: 0, total jobs 0, cluster matches: 0" in str(log_msg), log_msg)


class FETestCaseCondorStatus(FETestCaseBase):
    def test_getCondorStatus(self):
        with mock.patch("glideinwms.lib.condorExe.exe_cmd") as m_exe_cmd:
            f = open("cs.fixture")
            m_exe_cmd.return_value = f.readlines()
            condorStatus = glideinFrontendLib.getCondorStatus(
                ["coll1"], format_list=[("State", "s"), ("Activity", "s")], want_format_completion=True
            )

        machines = list(condorStatus["coll1"].stored_data.keys())
        self.assertCountEqual(
            machines,
            [
                "glidein_1@cmswn001.local",
                "glidein_2@cmswn002.local",
                "glidein_3@cmswn003.local",
                "glidein_4@cmswn004.local",
                "glidein_5@cmswn005.local",
                "glidein_1@cmswn006.local",
            ],
        )

    def test_getIdleCondorStatus(self):
        condorStatus = glideinFrontendLib.getIdleCondorStatus(self.status_dict)
        machines = list(condorStatus["coll1"].stored_data.keys())
        self.assertCountEqual(machines, ["glidein_4@cmswn004.local"])

    def test_getRunningCondorStatus(self):
        condorStatus = glideinFrontendLib.getRunningCondorStatus(self.status_dict)
        machines = list(condorStatus["coll1"].stored_data.keys())
        self.assertCountEqual(
            machines,
            [
                "glidein_1@cmswn001.local",
                "glidein_2@cmswn002.local",
                "glidein_3@cmswn003.local",
                "glidein_5@cmswn005.local",
                "glidein_1@cmswn006.local",
            ],
        )

    def test_getClientCondorStatus(self):
        condorStatus = glideinFrontendLib.getClientCondorStatus(
            self.status_dict, "frontend_v3", "maingroup", "Site_Name1@v3_0@factory1"
        )
        machines = list(condorStatus["coll1"].stored_data.keys())
        self.assertCountEqual(machines, ["glidein_1@cmswn001.local"])

    def test_getClientCondorStatusCredIdOnly(self):
        # need example with GLIDEIN_CredentialIdentifier
        pass

    def test_getClientCondorStatusPerCredId(self):
        # need example with GLIDEIN_CredentialIdentifier
        pass

    def test_countCondorStatus(self):
        self.assertEqual(glideinFrontendLib.countCondorStatus(self.status_dict), 6)

    def test_getFactoryEntryList(self):
        entries = glideinFrontendLib.getFactoryEntryList(self.status_dict)
        expected = [("Site_Name%s@v3_0@factory1" % (x), "frontend%s.local" % x) for x in range(1, 5)]
        expected.append(("Site_Name2@v3_0@factory1", "frontend1.local"))
        self.assertCountEqual(entries, expected)

    def test_getCondorStatusSchedds(self):
        with mock.patch("glideinwms.lib.condorExe.exe_cmd") as m_exe_cmd:
            f = open("cs.schedd.fixture")
            m_exe_cmd.return_value = f.readlines()
            condorStatus = glideinFrontendLib.getCondorStatusSchedds(["coll1"])
            self.assertCountEqual(
                list(condorStatus["coll1"].stored_data.keys()), ["schedd%s.local" % x for x in range(1, 4)]
            )


class FETestCaseMisc(FETestCaseBase):
    def test_uniqueSets(self):
        input = [
            {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
            {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
            {
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                33,
                34,
                35,
            },
            {11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30},
        ]

        expected = (
            [
                ({2}, {32, 33, 34, 35, 31}),
                ({0, 1, 2}, {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}),
                ({2, 3}, {11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30}),
            ],
            {
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                33,
                34,
                35,
            },
        )

        self.assertCountEqual(expected, glideinFrontendLib.uniqueSets(input))

    def test_hashJob(self):
        in1 = {1: "a", 2: "b", 3: "c"}
        in2 = [1, 3]
        expected = ((1, "a"), (3, "c"))
        self.assertCountEqual(expected, glideinFrontendLib.hashJob(in1, in2))

    def test_appendRealRunning(self):
        cq_run_dict = glideinFrontendLib.getRunningCondorQ(self.condorq_dict)
        glideinFrontendLib.appendRealRunning(cq_run_dict, self.status_dict)
        expected = ["Site_Name%s@v3_0@factory1@submit.local" % (x) for x in [1, 2, 2, 2, 2]]
        expected.append("UNKNOWN")

        self.assertCountEqual([x["RunningOn"] for x in list(cq_run_dict["sched1"].fetchStored().values())], expected)

    def test_getGlideinCpusNum(self):
        self.assertEqual(glideinFrontendLib.getGlideinCpusNum(self.glidein_dict[self.glidein_dict_k1]), 1)
        self.assertEqual(glideinFrontendLib.getGlideinCpusNum(self.glidein_dict[self.glidein_dict_k2]), 4)
        self.assertEqual(glideinFrontendLib.getGlideinCpusNum(self.glidein_dict[self.glidein_dict_k3]), 1)

    def test_evalParamExpr(self):
        self.assertIs(glideinFrontendLib.evalParamExpr("(30 + 40)", None, None), 70)


# @unittest.skip('yay')


class FETestCaseCondorQ(FETestCaseBase):
    def setUp(self):
        super().setUp()
        self.total_jobs = 13

    @mock.patch.object(glideinFrontendLib, "getClientCondorStatus")
    @mock.patch.object(glideinFrontendLib, "getClientCondorStatusCredIdOnly")
    def test_getClientCondorStatusPerCredId(self, m_getClientCondorStatusCredIdOnly, m_getClientCondorStatus):
        m_getClientCondorStatus.return_value = "test_condor_status"
        getClientCondorStatusPerCredId(
            self.status_dict, self.frontend_name, self.group_name, self.request_name, self.cred_id
        )
        m_getClientCondorStatus.assert_called_with(
            self.status_dict, self.frontend_name, self.group_name, self.request_name
        )
        m_getClientCondorStatusCredIdOnly.assert_called_with("test_condor_status", self.cred_id)

    @mock.patch.object(glideinFrontendLib.condorMonitor, "SubQuery")
    def test_getClientCondorStatusCredIdOnly(self, m_subquery):
        getClientCondorStatusCredIdOnly(self.status_dict, self.cred_id)
        self.assertEqual(m_subquery.call_args[0][0], list(self.status_dict.values())[0])

    @mock.patch.object(glideinFrontendLib, "getCondorQConstrained")
    def test_getCondorQ_no_constraints(self, m_getCondorQConstrained):
        schedd_names = ["test_sched1", "test_sched2"]

        glideinFrontendLib.getCondorQ(schedd_names, job_status_filter=None)
        m_getCondorQConstrained.assert_called_with(schedd_names, "True", None, None)

        glideinFrontendLib.getCondorQ(schedd_names)
        m_getCondorQConstrained.assert_called_with(schedd_names, "(JobStatus=?=1)||(JobStatus=?=2)", None, None)

        glideinFrontendLib.getCondorQ(schedd_names, job_status_filter=[5])
        m_getCondorQConstrained.assert_called_with(schedd_names, "(JobStatus=?=5)", None, None)

        constraint = "(JobStatus=?=1)||(JobStatus=?=2)"
        format_list = list((("x509UserProxyFirstFQAN", "s"),))
        glideinFrontendLib.getCondorQ(schedd_names, "True", format_list)
        m_getCondorQConstrained.assert_called_with(schedd_names, constraint, "True", format_list + self.default_format)

    @mock.patch.object(glideinFrontendLib.condorMonitor, "SubQuery")
    def test_oldCondorQ(self, m_SubQuery):
        condorq_dict = {"a": 42}
        min_age = "_"

        glideinFrontendLib.getOldCondorQ(condorq_dict, min_age)
        self.assertEqual(m_SubQuery.call_args[0][0], 42)
        self.assertTrue(
            compareLambdas(
                m_SubQuery.call_args[0][1],
                lambda el: (
                    "ServerTime" in el
                    and "EnteredCurrentStatus" in el
                    and ((el["ServerTime"] - el["EnteredCurrentStatus"]) >= min_age)
                ),
            )
        )

        # this just checks that the lambda is evaluating the min_age variable,
        # not dereferencing it!

    def test_getRunningCondorQ(self):
        condor_ids = list(glideinFrontendLib.getRunningCondorQ(self.condorq_dict)["sched1"].fetchStored().keys())

        self.assertCountEqual(condor_ids, [(12345, 3), (12345, 4), (12345, 5), (12345, 10), (12345, 11), (12345, 12)])

    def test_getIdleCondorQ(self):
        condor_ids = list(glideinFrontendLib.getIdleCondorQ(self.condorq_dict)["sched1"].fetchStored().keys())

        self.assertCountEqual(
            condor_ids, [(12345, 0), (12345, 1), (12345, 2), (12345, 6), (12345, 7), (12345, 8), (12345, 9)]
        )

    def test_getIdleVomsCondorQ(self):
        condor_ids = list(glideinFrontendLib.getIdleVomsCondorQ(self.condorq_dict)["sched1"].fetchStored().keys())

        self.assertEqual(condor_ids, [(12345, 2)])

    def test_getOldCondorQ(self):
        min_age = 100
        condor_ids = list(glideinFrontendLib.getOldCondorQ(self.condorq_dict, min_age)["sched1"].fetchStored().keys())
        self.assertEqual(condor_ids, [(12345, 0)])

    def test_countCondorQ(self):
        count = glideinFrontendLib.countCondorQ(self.condorq_dict)
        self.assertEqual(count, self.total_jobs)

    def test_getCondorQUsers(self):
        users = glideinFrontendLib.getCondorQUsers(self.condorq_dict)
        self.assertCountEqual(users, ["user1@fnal.gov", "user2@fnal.gov"])

    @mock.patch("glideinwms.lib.condorMonitor.LocalScheddCache.iGetEnv")
    @mock.patch("glideinwms.lib.condorExe.exe_cmd")
    def test_getCondorQ(self, m_exe_cmd, m_iGetEnv):
        f = open("cq.fixture")
        m_exe_cmd.return_value = f.readlines()

        cq = glideinFrontendLib.getCondorQ(["sched1"])
        condor_ids = list(cq["sched1"].fetchStored().keys())

        self.assertCountEqual(condor_ids, [(12345, x) for x in range(0, self.total_jobs)])


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
