#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import mock
import unittest2 as unittest
import xmlrunner


from glideinwms.creation.lib import cgWParamDict 
from glideinwms.creation.lib import factoryXmlConfig
from glideinwms.creation.lib.cgWParamDict import add_file_unparsed 
from glideinwms.creation.lib.cgWParamDict import add_attr_unparsed 
from glideinwms.creation.lib.cgWParamDict import add_attr_unparsed_real 
from glideinwms.creation.lib.cgWParamDict import iter_to_dict 
from glideinwms.creation.lib.cgWParamDict import populate_factory_descript 
from glideinwms.creation.lib.cgWParamDict import populate_job_descript 
from glideinwms.creation.lib.cgWParamDict import populate_frontend_descript 
from glideinwms.creation.lib.cgWParamDict import populate_gridmap 
from glideinwms.creation.lib.cgWParamDict import validate_condor_tarball_attrs 
from glideinwms.creation.lib.cgWParamDict import old_get_valid_condor_tarballs 
from glideinwms.creation.lib.cgWParamDict import get_valid_condor_tarballs 
from glideinwms.creation.lib.cgWParamDict import itertools_product 
from glideinwms.creation.lib.cgWParamDict import calc_monitoring_collectors_string 
from glideinwms.creation.lib.cgWParamDict import calc_primary_monitoring_collectors 

XML = 'fixtures/factory/glideinWMS.xml'


class TestGlideinDicts(unittest.TestCase):

    def setUp(self):
        self.conf = factoryXmlConfig.parse(XML)
        self.cgpd = cgWParamDict.glideinDicts(self.conf) 
        self.cgpd.populate()

    def test__init__(self):
        self.assertTrue(isinstance(self.cgpd, cgWParamDict.glideinDicts))

    def test_new_MainDicts(self):
        nmd = self.cgpd.new_MainDicts()
        self.assertTrue(isinstance(nmd, cgWParamDict.glideinMainDicts))

    def test_new_SubDicts(self):
        nsd = self.cgpd.new_SubDicts('entry_osg34_el7')
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


class TestAddFileUnparsed(unittest.TestCase):
    @unittest.skip('for now')
    def test_add_file_unparsed(self):
        self.assertEqual(expected, add_file_unparsed(user_file, dicts, is_factory))
        # assert False TODO: implement your test here

class TestAddAttrUnparsed(unittest.TestCase):
    @unittest.skip('for now')
    def test_add_attr_unparsed(self):
        self.assertEqual(expected, add_attr_unparsed(attr, dicts, description))
        # assert False TODO: implement your test here

class TestAddAttrUnparsedReal(unittest.TestCase):
    @unittest.skip('for now')
    def test_add_attr_unparsed_real(self):
        self.assertEqual(expected, add_attr_unparsed_real(attr, dicts))
        # assert False TODO: implement your test here

class TestIterToDict(unittest.TestCase):
    @unittest.skip('for now')
    def test_iter_to_dict(self):
        self.assertEqual(expected, iter_to_dict(dictObject))
        # assert False TODO: implement your test here

class TestPopulateFactoryDescript(unittest.TestCase):
    @unittest.skip('for now')
    def test_populate_factory_descript(self):
        self.assertEqual(expected, populate_factory_descript(work_dir, glidein_dict, active_sub_list, disabled_sub_list, conf))
        # assert False TODO: implement your test here

class TestPopulateJobDescript(unittest.TestCase):
    @unittest.skip('for now')
    def test_populate_job_descript(self):
        self.assertEqual(expected, populate_job_descript(work_dir, job_descript_dict, sub_name, entry, schedd))
        # assert False TODO: implement your test here

class TestPopulateFrontendDescript(unittest.TestCase):
    @unittest.skip('for now')
    def test_populate_frontend_descript(self):
        self.assertEqual(expected, populate_frontend_descript(frontend_dict, conf))
        # assert False TODO: implement your test here

class TestPopulateGridmap(unittest.TestCase):
    @unittest.skip('for now')
    def test_populate_gridmap(self):
        self.assertEqual(expected, populate_gridmap(conf, gridmap_dict))
        # assert False TODO: implement your test here

class TestValidateCondorTarballAttrs(unittest.TestCase):
    @unittest.skip('for now')
    def test_validate_condor_tarball_attrs(self):
        self.assertEqual(expected, validate_condor_tarball_attrs(conf))
        # assert False TODO: implement your test here

class TestOldGetValidCondorTarballs(unittest.TestCase):
    @unittest.skip('for now')
    def test_old_get_valid_condor_tarballs(self):
        self.assertEqual(expected, old_get_valid_condor_tarballs(params))
        # assert False TODO: implement your test here

class TestGetValidCondorTarballs(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_valid_condor_tarballs(self):
        self.assertEqual(expected, get_valid_condor_tarballs(condor_tarballs))
        # assert False TODO: implement your test here

class TestItertoolsProduct(unittest.TestCase):
    @unittest.skip('for now')
    def test_itertools_product(self):
        self.assertEqual(expected, itertools_product(*args, **kwds))
        # assert False TODO: implement your test here

class TestCalcMonitoringCollectorsString(unittest.TestCase):
    @unittest.skip('for now')
    def test_calc_monitoring_collectors_string(self):
        self.assertEqual(expected, calc_monitoring_collectors_string(collectors))
        # assert False TODO: implement your test here

class TestCalcPrimaryMonitoringCollectors(unittest.TestCase):
    @unittest.skip('for now')
    def test_calc_primary_monitoring_collectors(self):
        self.assertEqual(expected, calc_primary_monitoring_collectors(collectors))
        # assert False TODO: implement your test here

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
