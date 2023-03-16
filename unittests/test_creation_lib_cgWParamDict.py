#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
    glideinWMS
Description:
    unit test for glideinwms/creation/lib/cgWParamDict.py

Author:
    Dennis Box, dbox@fnal.gov
"""

import os
import sys
import unittest

from unittest import mock

import xmlrunner

from glideinwms.creation.lib import factoryXmlConfig
from glideinwms.creation.lib.cgWParamDict import (
    add_attr_unparsed,
    add_attr_unparsed_real,
    add_file_unparsed,
    calc_monitoring_collectors_string,
    calc_primary_monitoring_collectors,
    get_valid_condor_tarballs,
    iter_to_dict,
    itertools_product,
    old_get_valid_condor_tarballs,
    populate_factory_descript,
    populate_frontend_descript,
    populate_gridmap,
    populate_job_descript,
    validate_condor_tarball_attrs,
)
from glideinwms.creation.lib.cWParamDict import has_file_wrapper, has_file_wrapper_params
from glideinwms.unittests.unittest_utils import balanced_text, TestImportError

try:
    from glideinwms.creation.lib import cgWParamDict
except ImportError as err:
    raise TestImportError(str(err))

XML = "fixtures/factory/glideinWMS.xml"

# We assume that this module is in the unittest directory
module_globals = globals()
unittest_dir = os.path.dirname(os.path.realpath(module_globals["__file__"]))

if "GLIDEINWMS_LOCATION" in os.environ:
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"], "creation"))
else:
    sys.path.append(os.path.join(unittest_dir, "../creation"))


class TestGlideinDicts(unittest.TestCase):
    def setUp(self):
        self.conf = factoryXmlConfig.parse(XML)
        self.cgpd = cgWParamDict.glideinDicts(self.conf)
        self.cgpd.populate()

    def test__init__(self):
        self.assertTrue(isinstance(self.cgpd, cgWParamDict.glideinDicts))

    def test_submit_files_ok(self):
        work_dir = self.cgpd.work_dir
        for item in self.cgpd.sub_list:
            entry = "entry_%s" % item
            condir = os.path.join(work_dir, entry)
            confile = os.path.join(condir, "job.condor")
            self.assertTrue(os.path.exists(confile), "%s not found! " % confile)
            with open(confile) as cf:
                data = cf.readlines()
                rslt = balanced_text(data)
                self.assertEqual("Balanced", rslt, f"{rslt} {confile}")

    def test_new_MainDicts(self):
        nmd = self.cgpd.new_MainDicts()
        self.assertTrue(isinstance(nmd, cgWParamDict.glideinMainDicts))

    def test_new_SubDicts(self):
        nsd = self.cgpd.new_SubDicts("entry_osg34_el7")
        self.assertTrue(isinstance(nsd, cgWParamDict.glideinEntryDicts))

    def test_save(self):
        self.cgpd.save()

    def test_save_pub_key(self):
        nmd = self.cgpd.new_MainDicts()
        nmd.save_pub_key()

    def test_save_monitor(self):
        nmd = self.cgpd.new_MainDicts()
        nmd.save_monitor()

    def test_MainDicts_populate(self):
        nmd = self.cgpd.new_MainDicts()
        nmd.populate()

    def test_reuse(self):
        nmd = self.cgpd.new_MainDicts()
        self.cgpd.main_dicts.reuse(nmd)

    def test_has_file_wrapper(self):
        self.assertEqual(False, has_file_wrapper(self.cgpd.main_dicts))


class TestAddFileUnparsed(unittest.TestCase):
    @unittest.skip("for now")
    def test_add_file_unparsed(self):
        # self.assertEqual(
        #    expected, add_file_unparsed(
        #        user_file, dicts, is_factory))
        assert False  # TODO: implement your test here


class TeOBstAddAttrUnparsed(unittest.TestCase):
    @unittest.skip("for now")
    def test_add_attr_unparsed(self):
        # self.assertEqual(expected, add_attr_unparsed(attr, dicts, description))
        assert False  # TODO: implement your test here


class TestAddAttrUnparsedReal(unittest.TestCase):
    @unittest.skip("for now")
    def test_add_attr_unparsed_real(self):
        # self.assertEqual(expected, add_attr_unparsed_real(attr, dicts))
        assert False  # TODO: implement your test here


class TestIterToDict(unittest.TestCase):
    @unittest.skip("for now")
    def test_iter_to_dict(self):
        # self.assertEqual(expected, iter_to_dict(dictObject))
        assert False  # TODO: implement your test here


class TestPopulateFactoryDescript(unittest.TestCase):
    @unittest.skip("for now")
    def test_populate_factory_descript(self):
        # self.assertEqual(
        #    expected,
        #    populate_factory_descript(
        #        work_dir,
        #        glidein_dict,
        #        active_sub_list,
        #        disabled_sub_list,
        #        conf))
        assert False  # TODO: implement your test here


class TestPopulateJobDescript(unittest.TestCase):
    @unittest.skip("for now")
    def test_populate_job_descript(self):
        # self.assertEqual(
        #    expected,
        #    populate_job_descript(
        #        work_dir,
        #        job_descript_dict,
        #        sub_name,
        #        entry,
        #        schedd))
        assert False  # TODO: implement your test here


class TestPopulateFrontendDescript(unittest.TestCase):
    @unittest.skip("for now")
    def test_populate_frontend_descript(self):
        # self.assertEqual(
        #    expected, populate_frontend_descript(
        #        frontend_dict, conf))
        assert False  # TODO: implement your test here


class TestPopulateGridmap(unittest.TestCase):
    @unittest.skip("for now")
    def test_populate_gridmap(self):
        # self.assertEqual(expected, populate_gridmap(conf, gridmap_dict))
        assert False  # TODO: implement your test here


class TestValidateCondorTarballAttrs(unittest.TestCase):
    @unittest.skip("for now")
    def test_validate_condor_tarball_attrs(self):
        # self.assertEqual(expected, validate_condor_tarball_attrs(conf))
        assert False  # TODO: implement your test here


class TestOldGetValidCondorTarballs(unittest.TestCase):
    @unittest.skip("for now")
    def test_old_get_valid_condor_tarballs(self):
        # self.assertEqual(expected, old_get_valid_condor_tarballs(params))
        assert False  # TODO: implement your test here


class TestGetValidCondorTarballs(unittest.TestCase):
    @unittest.skip("for now")
    def test_get_valid_condor_tarballs(self):
        # self.assertEqual(expected, get_valid_condor_tarballs(condor_tarballs))
        assert False  # TODO: implement your test here


class TestItertoolsProduct(unittest.TestCase):
    @unittest.skip("for now")
    def test_itertools_product(self):
        # self.assertEqual(expected, itertools_product(*args, **kwds))
        assert False  # TODO: implement your test here


class TestCalcMonitoringCollectorsString(unittest.TestCase):
    @unittest.skip("for now")
    def test_calc_monitoring_collectors_string(self):
        # self.assertEqual(
        #    expected,
        #    calc_monitoring_collectors_string(collectors))
        assert False  # TODO: implement your test here


class TestCalcPrimaryMonitoringCollectors(unittest.TestCase):
    @unittest.skip("for now")
    def test_calc_primary_monitoring_collectors(self):
        # self.assertEqual(
        #    expected,
        #    calc_primary_monitoring_collectors(collectors))
        assert False  # TODO: implement your test here


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
