#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for factory/tools/get_tarballs.py."""

import hashlib
import os
import tempfile
import unittest

from argparse import Namespace
from unittest import mock
from urllib.error import HTTPError

try:
    import xmlrunner
except ImportError:
    xmlrunner = None

try:
    from glideinwms.unittests.unittest_utils import TestImportError
except ImportError:

    class TestImportError(Exception):
        pass


try:
    from glideinwms.factory.tools import get_tarballs
except ImportError as err:
    raise TestImportError(str(err))


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload


class TestGetTarballs(unittest.TestCase):
    """Test config validation and local main flow with mocked network."""

    def setUp(self):
        self._orig_env = os.environ.get("GET_TARBALLS_CONFIG")

    def tearDown(self):
        if self._orig_env is None:
            os.environ.pop("GET_TARBALLS_CONFIG", None)
        else:
            os.environ["GET_TARBALLS_CONFIG"] = self._orig_env

    def _base_config(self, destination_dir, xml_out):
        """Return an OSG-like config adapted for local tests."""
        return {
            "DESTINATION_DIR": destination_dir,
            "TARBALL_BASE_URL": "https://htcss-downloads.chtc.wisc.edu/tarball/",
            "DEFAULT_TARBALL_VERSION": ["23.0.28", "24.0.22"],
            "CONDOR_TARBALL_LIST": [
                {"MAJOR_VERSION": "23.0", "WHITELIST": ["23.0.28", "latest"]},
                {"MAJOR_VERSION": "24.0", "WHITELIST": ["24.0.22", "latest"]},
            ],
            "FILENAME_LIST": [
                "condor-{version}-x86_64_CentOS7-stripped.tar.gz",
                "condor-{version}-x86_64_AlmaLinux10-stripped.tar.gz",
            ],
            "OS_MAP": {
                "CentOS7": "rhel7,linux-rhel7",
                "AlmaLinux10": "rhel10,linux-rhel10",
            },
            "ARCH_MAP": {"x86_64": "default"},
            "XML_OUT": xml_out,
        }

    def _write_config(self, config_path, cfg):
        yaml_text = f'''DESTINATION_DIR: "{cfg["DESTINATION_DIR"]}"
TARBALL_BASE_URL: "{cfg["TARBALL_BASE_URL"]}"
DEFAULT_TARBALL_VERSION: ["23.0.28", "24.0.22"]
CONDOR_TARBALL_LIST:
  - MAJOR_VERSION: "23.0"
    WHITELIST: ["23.0.28", "latest"]
  - MAJOR_VERSION: "24.0"
    WHITELIST: ["24.0.22", "latest"]
FILENAME_LIST:
  - "condor-{{version}}-x86_64_CentOS7-stripped.tar.gz"
  - "condor-{{version}}-x86_64_AlmaLinux10-stripped.tar.gz"
OS_MAP:
  CentOS7: "rhel7,linux-rhel7"
  AlmaLinux10: "rhel10,linux-rhel10"
ARCH_MAP:
  x86_64: "default"
XML_OUT: "{cfg["XML_OUT"]}"
'''
        with open(config_path, "w") as fh:
            fh.write(yaml_text)

    def test_config_accepts_default_tarball_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = os.path.join(tmpdir, "tarballs")
            os.makedirs(destination)
            xml_out = os.path.join(tmpdir, "01-condor-tarballs.xml")
            cfg_path = os.path.join(tmpdir, "get_tarballs.yaml")
            cfg = self._base_config(destination, xml_out)
            self._write_config(cfg_path, cfg)
            os.environ["GET_TARBALLS_CONFIG"] = cfg_path

            conf = get_tarballs.Config()

            self.assertEqual(conf["DEFAULT_TARBALL_VERSION"], ["23.0.28", "24.0.22"])
            self.assertTrue(conf["CONDOR_TARBALL_LIST"][0].get("DOWNLOAD_LATEST", False))
            self.assertNotIn("latest", conf["CONDOR_TARBALL_LIST"][0]["WHITELIST"])

    def test_main_generates_xml_using_tmp_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = os.path.join(tmpdir, "tarballs")
            os.makedirs(destination)
            xml_out = os.path.join(tmpdir, "01-condor-tarballs.xml")
            cfg_path = os.path.join(tmpdir, "get_tarballs.yaml")
            cfg = self._base_config(destination, xml_out)
            self._write_config(cfg_path, cfg)
            os.environ["GET_TARBALLS_CONFIG"] = cfg_path

            available_by_version = {
                "23.0.28": {
                    "condor-23.0.28-x86_64_CentOS7-stripped.tar.gz": b"c7-23",
                },
                "24.0.22": {
                    "condor-24.0.22-x86_64_CentOS7-stripped.tar.gz": b"c7-24",
                    "condor-24.0.22-x86_64_AlmaLinux10-stripped.tar.gz": b"a10-24",
                },
            }

            release_pages = {
                "https://htcss-downloads.chtc.wisc.edu/tarball/23.0": b"23.0.28/",
                "https://htcss-downloads.chtc.wisc.edu/tarball/24.0": b"24.0.22/",
            }

            def fake_urlopen(url):
                if url in release_pages:
                    return _FakeResponse(release_pages[url])
                if url.endswith("/23.0.28/release") or url.endswith("/24.0.22/release"):
                    return _FakeResponse(b"")
                raise HTTPError(url, 404, "Not Found", None, None)

            def fake_urlretrieve(url, filename):
                if url.endswith("sha256sum.txt"):
                    version = "23.0.28" if "/23.0.28/" in url else "24.0.22"
                    lines = []
                    for tname, payload in available_by_version[version].items():
                        lines.append(f"{hashlib.sha256(payload).hexdigest()}  {tname}\n")
                    with open(filename, "w") as fh:
                        fh.writelines(lines)
                    return (filename, None)

                tname = os.path.basename(url)
                if "/23.0.28/" in url:
                    payload = available_by_version["23.0.28"].get(tname)
                else:
                    payload = available_by_version["24.0.22"].get(tname)

                if payload is None:
                    raise HTTPError(url, 404, "Not Found", None, None)

                with open(filename, "wb") as fh:
                    fh.write(payload)
                return (filename, None)

            with mock.patch.object(get_tarballs, "parse_opts", return_value=Namespace(verbose=False, checklatest=False)):
                with mock.patch.object(get_tarballs.request, "urlopen", side_effect=fake_urlopen):
                    with mock.patch.object(get_tarballs.request, "urlretrieve", side_effect=fake_urlretrieve):
                        rc = get_tarballs.main()

            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(xml_out))

            with open(xml_out) as fh:
                xml_text = fh.read()

            # AlmaLinux10 exists only in 24.0.22, so it should become default there.
            self.assertIn("condor-24.0.22-x86_64_AlmaLinux10-stripped.tar.gz", xml_text)
            self.assertIn('version="24.0.22,24.0.x,default"', xml_text)

            # CentOS7 exists in both 23.0.28 and 24.0.22. Only the first default in
            # DEFAULT_TARBALL_VERSION list should get ,default for this OS/arch pair.
            self.assertIn('condor-23.0.28-x86_64_CentOS7-stripped.tar.gz" version="23.0.28,23.0.x,default"', xml_text)
            self.assertIn('condor-24.0.22-x86_64_CentOS7-stripped.tar.gz" version="24.0.22,24.0.x"', xml_text)


if __name__ == "__main__":
    if xmlrunner is not None:
        unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
    else:
        unittest.main()
