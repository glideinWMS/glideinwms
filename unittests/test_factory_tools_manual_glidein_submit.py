#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
    glideinWMS
Purpose:
    unit test for factory/tools/manual_glidein_submit.py
"""

import os
import shutil
import tempfile
import unittest

import xmlrunner

try:
    from glideinwms.unittests.unittest_utils import TestImportError
except ImportError:

    class TestImportError(Exception):
        pass


try:
    from glideinwms.factory.tools.manual_glidein_submit import get_submit_credentials
    from glideinwms.lib.symCrypto import SymAES256Key
except ImportError as err:
    raise TestImportError(str(err))


class TestGetSubmitCredentials(unittest.TestCase):
    def setUp(self):
        self.key = SymAES256Key()
        self.key.new()
        self.cred_dir = tempfile.mkdtemp()
        self.client_name = "frontend"
        self.entry = "TEST_ENTRY"

    def tearDown(self):
        shutil.rmtree(self.cred_dir)

    def make_ad(self, **params):
        """Return a glideclient classad with the given parameters encrypted with the test key."""
        ad = {"ClientName": self.client_name}
        for name, value in params.items():
            ad[f"GlideinEncParam{name}"] = self.key.encrypt_hex(value).decode("utf8")
        return ad

    def touch_cred(self, name):
        """Create a credential file in the test credentials directory and return its path."""
        path = os.path.join(self.cred_dir, name)
        with open(path, "w") as f:
            f.write("credential\n")
        return path

    def get_credentials(self, ad):
        return get_submit_credentials(ad, self.key, "pilot", "fepilot", self.cred_dir, self.entry)

    def test_proxy_request(self):
        """A request with a proxy uses it as the credential id and SubmitProxy credential."""
        proxy = self.touch_cred(f"credential_{self.client_name}_proxy-id")

        credentials = self.get_credentials(self.make_ad(SubmitProxy="proxy-id"))

        self.assertEqual(credentials.id, "proxy-id")
        self.assertEqual(credentials.security_credentials["SubmitProxy"], proxy)

    def test_scitoken_only_request(self):
        """A request with only a SciToken uses ScitokenId as the credential id and adds the token file."""
        token = self.touch_cred(f"credential_{self.client_name}_{self.entry}.scitoken")

        credentials = self.get_credentials(self.make_ad(ScitokenId="scitoken-id"))

        self.assertEqual(credentials.id, "scitoken-id")
        self.assertNotIn("SubmitProxy", credentials.security_credentials)
        self.assertEqual(credentials.identity_credentials["frontend_scitoken"], token)

    def test_scitoken_only_request_without_token_file(self):
        """A request with only a SciToken but no token file on disk has no usable credential."""
        credentials = self.get_credentials(self.make_ad(ScitokenId="scitoken-id"))

        self.assertIsNone(credentials)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
