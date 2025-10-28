#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Unit test for glideinwms/frontend/glideinFrontendElement"""


import os
import unittest

from unittest import mock

import jsonpickle
import xmlrunner

import glideinwms.lib.condorExe
import glideinwms.lib.condorMonitor as condorMonitor

from glideinwms.frontend import glideinFrontendInterface, glideinFrontendMonitoring
from glideinwms.lib.fork import ForkManager
from glideinwms.lib.util import safe_boolcomp
from glideinwms.unittests.unittest_utils import FakeLogger, TestImportError

try:
    import glideinwms.frontend.glideinFrontendConfig as glideinFrontendConfig
    import glideinwms.frontend.glideinFrontendElement as glideinFrontendElement
except ImportError as err:
    raise TestImportError(str(err))

LOG_INFO_DATA = []
LOG_EXCEPTION_DATA = []


def log_info_side_effect(*args, **kwargs):
    """
    keep logSupport.log.info data in an array so we can search it later
    """
    LOG_INFO_DATA.append(args[0])


def log_exception_side_effect(*args, **kwargs):
    """
    keep logSupport.log.exception  data in an array so we can search it later
    """
    LOG_EXCEPTION_DATA.append(args[0])


def refresh_entry_token_side_effect(*args, **kwargs):
    """
    place holder, needs more token testing stuff here
    """
    return """eyJhbGciOiJIUzI1NiIsImtpZCI6ImVsN19vc2czNSJ9.eyJleHAiOjE2MDAyODQ4MzAsImlhdCI6MTYwMDE5ODQzMCwiaXNzIjoiZmVybWljbG91ZDMyMi5mbmFsLmdvdjo5NjE4IiwianRpIjoiMDYxY2VmMzY4ZThjYTM5MmZhYzk3MDkxOTZhODQyN2MiLCJzY29wZSI6ImNvbmRvcjpcL1JFQUQgY29uZG9yOlwvV1JJVEUgY29uZG9yOlwvQURWRVJUSVNFX1NUQVJURCBjb25kb3I6XC9BRFZFUlRJU0VfU0NIRUREIGNvbmRvcjpcL0FEVkVSVElTRV9NQVNURVIiLCJzdWIiOiJmcm9udGVuZEBmZXJtaWNsb3VkMzIyLmZuYWwuZ292In0.8vukKGjZhGL2t_bFoAc5yqu8CfGEURTVD3WLTaXJuoM"""


def uni_to_str_JSON(obj):
    """
    on some machines jsonpickle.decode() returns unicode strings
    and on others it returns ascii strings from the same data.
    The objects being tested here expect python strings, so convert them
    if necessary.  I am sure there is a better way to do this.
    """
    if isinstance(obj, dict):
        newobj = {}
        for key, value in obj.items():
            keyobj = uni_to_str_JSON(key)
            newobj[keyobj] = uni_to_str_JSON(value)
    elif isinstance(obj, list):
        newobj = []
        for value in obj:
            newobj.append(uni_to_str_JSON(value))
    elif isinstance(obj, tuple):
        newobj = ()
        for value in obj:
            newobj = newobj + (uni_to_str_JSON(value),)
    elif isinstance(obj, str):
        newobj = str(obj)
    else:
        newobj = obj

    return newobj


def fork_and_collect_side_effect():
    """
    populate data structures in
    glideinFrontendElement::iterate_one from
    json artifact in fixtures
    """
    with open("fixtures/frontend/pipe_out.iterate_one") as fd:
        json_str = fd.read()
        pipe_out_objs = uni_to_str_JSON(jsonpickle.decode(json_str, keys=True))
    for key in pipe_out_objs:
        try:
            keyobj = eval(key)
            pipe_out_objs[keyobj] = pipe_out_objs.pop(key)
        except BaseException:
            pass
    return pipe_out_objs


def bounded_fork_and_collect_side_effect():
    """
    populate data structures in glideinFrontendElement::do_match
    from json artifact in fixtures
    """
    with open("fixtures/frontend/pipe_out.do_match") as fd:
        json_str = fd.read()
        pipe_out_objs = uni_to_str_JSON(jsonpickle.decode(json_str, keys=True))
    for key in pipe_out_objs:
        try:
            keyobj = eval(key)
            pipe_out_objs[keyobj] = pipe_out_objs.pop(key)
        except BaseException:
            pass
    return pipe_out_objs


class FEElementTestCase(unittest.TestCase):
    def setUp(self):
        self.debug_output = os.environ.get("DEBUG_OUTPUT")
        glideinwms.frontend.glideinFrontendLib.logSupport.log = FakeLogger()
        condorMonitor.USE_HTCONDOR_PYTHON_BINDINGS = False
        self.frontendDescript = glideinwms.frontend.glideinFrontendConfig.FrontendDescript("fixtures/frontend")

        with mock.patch.object(glideinFrontendConfig.ConfigFile, "load") as m_load:  # noqa: F841
            # simpler data structures
            self.attrDescript = glideinwms.frontend.glideinFrontendConfig.AttrsDescript("", "")
            self.paramsDescript = glideinwms.frontend.glideinFrontendConfig.ParamsDescript("", "")

            # bases for derived data structures
            elementDescriptBase = glideinwms.frontend.glideinFrontendConfig.ElementDescript("", "")
            signatureDescript = glideinwms.frontend.glideinFrontendConfig.SignatureDescript("")
            signatureDescript.data = {
                "group_group1": ("ad0f57615c3df8bbb2130d96cfdf09363f4bd3ed", "description.e98f4o.cfg"),
                "main": ("7cea6e20d5a4e65e9468937f27511e3e44c72735", "description.e98f4o.cfg"),
            }

        self.paramsDescript.data = {
            "USE_MATCH_AUTH": "True",
            "GLIDECLIENT_Rank": "1",
            "GLIDEIN_Collector": "frontend:9620-9640",
        }
        self.paramsDescript.const_data = {
            "USE_MATCH_AUTH": ("CONST", "True"),
            "GLIDEIN_Collector": ("CONST", "frontend:9620-9640"),
            "GLIDECLIENT_Rank": ("CONST", "1"),
        }

        self.attrDescript.data = {
            "GLIDECLIENT_Rank": "1",
            "GLIDEIN_Expose_Grid_Env": "True",
            "GLIDECLIENT_Start": "True",
            "USE_MATCH_AUTH": "True",
            "GLIDECLIENT_Group_Start": "True",
            "GLIDEIN_Collector": "frontend:9620-9640",
        }

        elementDescriptBase.data = {
            "MapFile": "/var/lib/gwms-frontend/vofrontend/group_main/group.mapfile",
            "MaxRunningTotal": "100000",
            "JobMatchAttrs": "[]",
            "JobSchedds": "",
            "FactoryCollectors": "[]",
            "MaxIdleVMsPerEntry": "100",
            "CurbRunningTotal": "90000",
            "ReserveIdlePerEntry": "5",
            "MaxRunningPerEntry": "10000",
            "JobQueryExpr": "True",
            "RampUpAttenuation": "3",
            "MaxIdleVMsTotal": "1000",
            "FactoryMatchAttrs": "[]",
            "MaxIdlePerEntry": "100",
            "FracRunningPerEntry": "1.15",
            "FactoryQueryExpr": "True",
            "MatchExpr": "True",
            "CurbIdleVMsTotal": "200",
            "PartGlideinMinMemory": "2500",
            "GroupName": "group1",
            "MaxMatchmakers": "3",
            "MapFileWPilots": "/var/lib/gwms-frontend/vofrontend/group_main/group_wpilots.mapfile",
            "CurbIdleVMsPerEntry": "5",
            "MinRunningPerEntry": "0",
            "IdleLifetime": "0",
            "RemovalType": "NO",
            "RemovalWait": "0",
            "RemovalRequestsTracking": "False",
            "RemovalMargin": "0",
        }

        with mock.patch.object(glideinFrontendConfig, "SignatureDescript") as m_signatureDescript:
            m_signatureDescript.return_value = signatureDescript
            self.groupSignatureDescript = glideinwms.frontend.glideinFrontendConfig.GroupSignatureDescript("", "group1")

        with mock.patch.object(glideinFrontendConfig, "ElementDescript") as m_elementDescript:
            with mock.patch.object(glideinFrontendConfig, "FrontendDescript") as m_feDescript:
                m_elementDescript.return_value = elementDescriptBase
                m_feDescript.return_value = self.frontendDescript
                self.elementDescript = glideinwms.frontend.glideinFrontendConfig.ElementMergedDescript("", "group1")

        @mock.patch("glideinwms.frontend.glideinFrontendConfig.ElementMergedDescript")
        @mock.patch("glideinwms.frontend.glideinFrontendConfig.ParamsDescript")
        @mock.patch("glideinwms.frontend.glideinFrontendConfig.GroupSignatureDescript")
        @mock.patch("glideinwms.frontend.glideinFrontendConfig.AttrsDescript")
        def create_glideinFrontendElement(
            m_AttrsDescript, m_GroupSignatureDescript, m_ParamsDescript, m_ElementMergedDescript
        ):
            m_AttrsDescript.return_value = self.attrDescript
            m_GroupSignatureDescript.return_value = self.groupSignatureDescript
            m_ParamsDescript.return_value = self.paramsDescript
            m_ElementMergedDescript.return_value = self.elementDescript

            self.gfe = glideinFrontendElement.glideinFrontendElement(1, "", "group1", "")
            self.gfe.elementDescript = self.elementDescript

        # @mock.patch defines these so disable pylint complaint
        create_glideinFrontendElement()  # pylint: disable=no-value-for-parameter

    def test_get_condor_q(self):
        with mock.patch("glideinwms.lib.condorMonitor.LocalScheddCache.iGetEnv"):
            with mock.patch("glideinwms.lib.condorExe.exe_cmd") as m_exe_cmd:
                f = open("cq.fixture")
                m_exe_cmd.return_value = f.readlines()
                cq = self.gfe.get_condor_q("schedd1")

        self.assertCountEqual(list(cq["schedd1"].fetchStored().keys()), [(12345, x) for x in range(0, 13)])

    def test_compute_glidein_max_run(self):
        self.assertEqual(self.gfe.compute_glidein_max_run({"Idle": 412}, 971, 0), 1591)
        self.assertEqual(self.gfe.compute_glidein_max_run({"Idle": 100}, 100, 0), 230)
        self.assertEqual(self.gfe.compute_glidein_max_run({"Idle": 100}, 0, 0), 115)
        self.assertEqual(self.gfe.compute_glidein_max_run({"Idle": 0}, 0, 0), 0)
        self.assertEqual(self.gfe.compute_glidein_max_run({"Idle": 0}, 100, 100), 100)

    def test_some_iterate_one_artifacts(self):
        """
        Mock our way into glideinFrontendElement:iterate_one() to test if
             glideinFrontendElement.glidein_dict['entry_point']['attrs']['GLIDEIN_REQUIRE_VOMS']
                and
             glideinFrontendElement.glidein_dict['entry_point']['attrs']['GLIDEIN_In_Downtime']

             are being evaluated correctly
        """

        self.gfe.stats = {"group": glideinFrontendMonitoring.groupStats()}
        self.gfe.published_frontend_name = f"{self.gfe.frontend_name}.XPVO_{self.gfe.group_name}"
        mockery = mock.MagicMock()
        self.gfe.x509_proxy_plugin = mockery
        # keep logSupport.log.info in an array to search through later to
        # evaluate success
        glideinwms.frontend.glideinFrontendLib.logSupport.log = mockery
        mockery.info = log_info_side_effect
        mockery.exception = log_exception_side_effect

        # ForkManager mocked inside iterate_one, return data loaded from
        # fork_and_collect_side_effect
        # data loaded includes both legal True, False, 'True', 'False' , 'TRUE' etc
        # and obviously bad data 1, 0, etc

        with mock.patch.object(ForkManager, "fork_and_collect", return_value=fork_and_collect_side_effect()):
            with mock.patch.object(
                ForkManager, "bounded_fork_and_collect", return_value=bounded_fork_and_collect_side_effect()
            ):
                # also need to mock advertisers so they don't fork off jobs
                # it has nothing to do with what is being tested here
                with mock.patch.object(glideinFrontendInterface, "MultiAdvertizeWork"):
                    with mock.patch(
                        "glideinFrontendInterface.ResourceClassadAdvertiser.advertiseAllClassads", return_value=None
                    ):
                        with mock.patch.object(glideinFrontendInterface, "ResourceClassadAdvertiser"):
                            with mock.patch.object(
                                self.gfe, "refresh_entry_token", return_value=refresh_entry_token_side_effect()
                            ):
                                # finally run iterate_one and collect the log data
                                self.gfe.iterate_one()

        # go through glideinFrontendElement data structures
        # collecting data to match against log output
        glideid_list = sorted(
            self.gfe.condorq_dict_types["Idle"]["count"].keys(),
            key=lambda x: ("", "", "") if x == (None, None, None) else x,
        )
        glideids = []
        in_downtime = {}
        req_voms = {}
        for elm in glideid_list:
            if elm and elm[0]:
                glideid_str = f"{str(elm[1])}@{str(elm[0])}"
                gdata = self.gfe.glidein_dict[elm]["attrs"]
                glideids.append(glideid_str)
                in_downtime[glideid_str] = safe_boolcomp(gdata.get("GLIDEIN_In_Downtime"), True)
                req_voms[glideid_str] = safe_boolcomp(gdata.get("GLIDEIN_REQUIRE_VOMS"), True)

        if self.debug_output:
            print("info log %s " % LOG_INFO_DATA)
            print("exception log %s " % LOG_EXCEPTION_DATA)

        # examine the exception log, only test_site_3 should have tried to create a condor_token
        # all sites except test_site_3 and test_fact_7 are in down time
        # test_fact_7 is advertising a condor version that doesn't support tokens
        for lgln in LOG_EXCEPTION_DATA:
            self.assertTrue("test_fact_3" in lgln)
            self.assertTrue("test_fact_7" not in lgln)
            self.assertTrue("test_fact_4" not in lgln)

        # run through the info log
        # if GLIDEIN_REQUIRE_VOMS was set to True, 'True', 'tRUE' etc for an entry:
        #    'Voms Proxy Required,' will appear in previous line of log (if GlExec is used)
        idx = 0
        for lgln in LOG_INFO_DATA:
            parts = lgln.split()
            gid = parts[-1]
            if gid in glideids:
                upordown = parts[-2]
                fmt_str = "glideid:%s in_downtime:%s req_voms:%s "
                fmt_str += "\nlog_data:%s"
                state = fmt_str % (gid, in_downtime[gid], req_voms[gid], LOG_INFO_DATA[idx - 1])
                if self.debug_output:
                    print("%s" % state)
                if in_downtime[gid]:
                    self.assertTrue(upordown == "Down", f"{gid} logs this as {upordown}")
                else:
                    self.assertTrue(upordown == "Up", f"{gid} logs this as {upordown}")
            idx += 1

    def test_populate_pubkey(self):
        """test that good public keys get populated
        and bad public keys get removed
        """
        glideinwms.frontend.glideinFrontendLib.logSupport.log = mock.Mock()
        # glideinwms.frontend.glideinFrontendLib.logSupport.log = FakeLogger()
        self.gfe.globals_dict = {
            "bad_id": {"attrs": {"PubKeyValue": "0"}},
            "good_id": {
                "attrs": {
                    "PubKeyValue": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAw7Cq5VGe3w2kNZOvu41W\n3jB8N6GHbilV2pPEdOpu2sVOBnzsfg3l+9hY1cFMcWsIc7/hbyp8y5vuJAE6yXGq\nJ0MZZC8upOioTLzS7gFPQsdaJBO4bVsv4W6GNO92HqT0ll8At+VbmkZzRC5ThZXk\nj6bEfuxfRbUogReOKZyEp8wZK9jx8DXx/dLrx+gxqMLofGx5GRVXJd5pb9SgwzQU\nxrPi9H8rCQdxECP1bQ9M1YYDwqJcrsDsukqQR6TS53QLmV3rW3olc3zpoUc3aX77\niaKdn8c0FxkvE9emSBXyzaF2NTyKRZofDW6KyuIB1XP9PanRa6UztQqwcoyymf6B\nCwIDAQAB\n-----END PUBLIC KEY-----\n"
                }
            },
        }
        self.gfe.populate_pubkey()
        self.assertTrue("bad_id" not in self.gfe.globals_dict, "Bad public key was not removed")
        self.assertTrue("good_id" in self.gfe.globals_dict, "good public key was removed when it shouldn't have been")
        self.assertTrue(
            "PubKeyObj" in self.gfe.globals_dict["good_id"]["attrs"],
            "public key object not populated when it should have been",
        )


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
