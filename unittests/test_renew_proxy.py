#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
    glideinWMS
Purpose:
    unit test of glideinwms/frontend/gwms_renew_proxies.py
Author:
    Brian Lin <brianhlin@gmail.com>
"""

import unittest

from unittest import mock

import xmlrunner

from glideinwms.frontend import gwms_renew_proxies as proxy

VOMSES = """
"GLOW" "glow-voms.cs.wisc.edu" "15001" "/DC=org/DC=opensciencegrid/O=Open Science Grid/OU=Services/CN=glow-voms.cs.wisc.edu" "GLOW"
"osg" "voms.grid.iu.edu" "15027" "/DC=org/DC=opensciencegrid/O=Open Science Grid/OU=Services/CN=voms.grid.iu.edu" "osg"
"osg" "voms1.opensciencegrid.org" "15027" "/DC=org/DC=incommon/C=US/ST=WI/L=Madison/O=University of Wisconsin-Madison/OU=OCIS/CN=voms1.opensciencegrid.org" "osg"
"xenon.biggrid.nl" "voms.grid.sara.nl" "30008" "/O=dutchgrid/O=hosts/OU=sara.nl/CN=voms.grid.sara.nl" "xenon.biggrid.nl"
"""


# FIXME: Refactor _run_command to accept **kwargs instead
def get_opt_val(cmd, opt_name):
    """Given a command as a list, return the value of opt_name."""
    return cmd[cmd.index(opt_name) + 1]


class TestUtils(unittest.TestCase):
    """Test utility functions in gwms_renew_proxies"""

    def test_parse_vomses(self):
        name_map, uri_map = proxy.parse_vomses(VOMSES)
        for nocap, canonical in [("osg", "osg"), ("glow", "GLOW"), ("xenon.biggrid.nl", "xenon.biggrid.nl")]:
            self.assertEqual(name_map[nocap], canonical)
        for dn, uri in [
            ("/O=dutchgrid/O=hosts/OU=sara.nl/CN=voms.grid.sara.nl", "voms.grid.sara.nl:30008"),
            (
                "/DC=org/DC=opensciencegrid/O=Open Science Grid/OU=Services/CN=voms.grid.iu.edu",
                "voms.grid.iu.edu:15027",
            ),
            (
                "/DC=org/DC=incommon/C=US/ST=WI/L=Madison/O=University of Wisconsin-Madison/OU=OCIS/CN=voms1.opensciencegrid.org",
                "voms1.opensciencegrid.org:15027",
            ),
            (
                "/DC=org/DC=opensciencegrid/O=Open Science Grid/OU=Services/CN=glow-voms.cs.wisc.edu",
                "glow-voms.cs.wisc.edu:15001",
            ),
        ]:
            self.assertEqual(uri_map[dn], uri)

    @mock.patch("glideinwms.frontend.gwms_renew_proxies._run_command")
    def test_voms_proxy_init(self, mock_run_command):
        mock_proxy = mock.MagicMock()
        proxy.voms_proxy_init(mock_proxy)
        mock_run_command.assert_called_once()
        for option in ("-voms", "-order"):
            self.assertNotIn(option, mock_run_command.call_args[0][0])

    @mock.patch("glideinwms.frontend.gwms_renew_proxies._run_command")
    def test_voms_proxy_init_with_voms(self, mock_run_command):
        mock_proxy = mock.MagicMock()
        mock_voms_attr = mock.Mock()
        mock_voms_attr.name = "VoName"

        for role, expected_val in [("NULL", "name"), ("pilot", "voms")]:
            mock_voms_attr.fqan = f"/Role={role}/Capability=NULL"
            mock_voms_attr.voms = f"/{mock_voms_attr.name}{mock_voms_attr.fqan}"
            proxy.voms_proxy_init(mock_proxy, mock_voms_attr)

            command = mock_run_command.call_args[0][0]
            voms_opt = "-voms"
            order_opt = "-order"
            self.assertIn(voms_opt, command)
            self.assertEqual(get_opt_val(command, voms_opt), getattr(mock_voms_attr, expected_val))
            self.assertIn(order_opt, command)
            self.assertFalse("/Capability=" in get_opt_val(command, order_opt))


class TestVo(unittest.TestCase):
    """Test the VOMS attributes class"""

    def setUp(self):
        self.vo_name = "glideinwms"
        self.cmd = "/Role=NULL/Capability=NULL"

    def assertVomsAttr(self, vo, vo_name, cmd):
        self.assertEqual(vo.fqan, f"/{vo_name}{cmd}")
        self.assertEqual(vo.voms, f"{vo_name}:/{vo_name}{cmd}")

    def test_fqan_vo_prefix(self):
        vo = proxy.VO(self.vo_name, f"/{self.vo_name}{self.cmd}")
        self.assertVomsAttr(vo, self.vo_name, self.cmd)

    def test_fqan_without_vo_prefix(self):
        vo = proxy.VO(self.vo_name, self.cmd)
        self.assertVomsAttr(vo, self.vo_name, self.cmd)

    def test_fqan_malformed(self):
        self.assertRaises(ValueError, proxy.VO, self.vo_name, self.vo_name)


if __name__ == "__main__":
    ofl = "unittests-reports"
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=ofl))
