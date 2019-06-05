#!/usr/bin/env python
"""
Project:
   glideinWMS

Description:
   unit test for glideinwms/creation/lib/cvWCreate.py

Author:
   Dennis Box <dbox@fnal.gov>
"""

from __future__ import absolute_import
from __future__ import print_function
import os
import mock
import unittest2 as unittest
import xmlrunner

from glideinwms.creation.lib.cvWCreate import create_client_mapfile
from glideinwms.creation.lib.cvWCreate import create_client_condor_config
from glideinwms.creation.lib.cvWCreate import filter_unwanted_config_attrs
from glideinwms.creation.lib.cvWCreate import get_template


class Test_cvWCreate(unittest.TestCase):

    def test_create_client_mapfile(self):
        mapfile_fname = 'condor_mapfile'
        my_DN = "/DC=org/DC=incommon/C=US/ST=IL/L=Batavia/O=Fermi Research Alliance/OU=Fermilab/CN=fermicloud001.fnal.gov"
        factory_DNs = ["/DC=org/DC=incommon/C=US/ST=IL/L=Batavia/O=Fermi Research Alliance/OU=Fermilab/CN=fermicloud010.fnal.gov",
                       "/DC=org/DC=incommon/C=US/ST=IL/L=Batavia/O=Fermi Research Alliance/OU=Fermilab/CN=fermicloud011.fnal.gov",
                       ]
        schedd_DNs = ["/DC=org/DC=incommon/C=US/ST=IL/L=Batavia/O=Fermi Research Alliance/OU=Fermilab/CN=fermicloud020.fnal.gov",
                      "/DC=org/DC=incommon/C=US/ST=IL/L=Batavia/O=Fermi Research Alliance/OU=Fermilab/CN=fermicloud021.fnal.gov",
                      ]
        collector_DNs = [
            "/DC=org/DC=incommon/C=US/ST=IL/L=Batavia/O=Fermi Research Alliance/OU=Fermilab/CN=fermicloud030.fnal.gov"
        ]
        pilot_DNs = []
        create_client_mapfile(
            mapfile_fname,
            my_DN,
            factory_DNs,
            schedd_DNs,
            collector_DNs,
            pilot_DNs)

        self.assertTrue(os.path.exists(mapfile_fname))

        # the first 6 entries of the mapfile should have
        # these names, everything after that should be
        # named anonymous
        m_dat = [
            "me",
            "factory0",
            "factory1",
            "schedd0",
            "schedd1",
            "collector0",
            "anonymous"]
        idx = 0
        for line in open(mapfile_fname):
            parts = line.split()
            self.assertEqual(parts[-1], m_dat[idx])
            if idx + 1 < len(m_dat):
                idx += 1

        os.remove(mapfile_fname)

    def test_get_template(self):

        # test that we can fetch an existing template
        glideinWMS_dir = ".."
        template_name = 'gwms-factory.service'
        tmp = get_template(template_name, glideinWMS_dir)
        self.assertNotEqual(tmp, "")

        # test that fetching a nonexistent template throws
        # the correct Exception
        try:
            bad = get_template('I-dont-exist', glideinWMS_dir)
            assert False
        except IOError as ior:
            pass

    def test_create_client_condor_config(self):
        # use mock output from condor_config_val -dump
        # to create a condor_mapfile
        config_fname = 'condor_config'
        mapfile_fname = 'condor_mapfile'
        collector_nodes = ["fermicloud001.fnal.gov", "fermicloud002.fnal.gov"]
        classad_proxy = "/tmp/classad_proxy"

        with mock.patch('glideinwms.lib.condorExe.exe_cmd') as m_exe_cmd:
            with open('fixtures/frontend/ccvd.fixture', 'r') as fil:
                m_exe_cmd.return_value = fil.readlines()
                create_client_condor_config(
                    config_fname,
                    mapfile_fname,
                    collector_nodes,
                    classad_proxy)

        self.assertTrue(os.path.exists(config_fname))
        os.remove(config_fname)


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
