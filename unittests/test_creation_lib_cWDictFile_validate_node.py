#!/usr/bin/env python
"""
Project:
   glideinWMS

 Description:
   unit test for validate_node from
   glideinwms/creation/lib/cWDictfile

 Author:
   Dennis Box dbox@fnal.gov
"""


from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner


from glideinwms.unittests.unittest_utils import TestImportError
try:
    from glideinwms.creation.lib.cWDictFile import validate_node
except ImportError as err:
    raise TestImportError(str(err))

GOOD_NODES = ['fermicloudui.fnal.gov:9618-9620',
              'fermicloudui.fnal.gov:9618?sock=collector30-40',
              'fermicloudui.fnal.gov:9618-9630',
              'fermicloudui.fnal.gov:9618?sock=collector30-50',
              'fermicloudui.fnal.gov:9618?sock=collector10-20',
              'fermicloudui.fnal.gov:9618?sock=collector',
              'fermicloudui.fnal.gov:9618?sock=collector30-40',
              'fermicloudui.fnal.gov:9618?sock=collector30',
              'fermicloudui.fnal.gov:9618?sock=collector',
              'fermicloudui.fnal.gov:9618?sock=collector&key1=val1',
              'name@fermicloudui.fnal.gov:9618?sock=schedd',
              'fermicloudui.fnal.gov:9618?sock=my5alpha0num',
              'fermicloudui.fnal.gov:9618?key1=val1&sock=collector&key2=val2',
              'jobsub-dev.fnal.gov:9618',
              'fermicloudui.fnal.gov:9618?sock=collector30-40&key=',
              'fermicloudui.fnal.gov',
              'fermicloudui.fnal.gov:9618',
              'fermicloudui.fnal.gov:9620-9640',
              'fermicloudui.fnal.gov:9618?sock=collect10',
              'fermicloudui.fnal.gov:9618?sock=collect10-20',
              'fermicloudui.fnal.gov:9618?var1=val1&sock=collect10-20&var2=val2',
              'fermicloudui.fnal.gov:9618?var1=val1&sock=collect10-20&var2=val2-6',
              'fermicloudui.fnal.gov:9618?var1=val1&sock=my5collect30-50',
              ]

BAD_NODES = ['fermicloudui.fnal.gov:9618-9620-9999'
             'fermicloudui.fnal.gov:9648-9630',
             'fermicloudui.fnal.gov:9618?sock=collector30-20',
             'fermicloudui.fnal.gov:9618-9620?sock=collector30-40',
             'I.dont.exist:9618',
             'jobsub-dev.fnal.gov:9618-9999-332',
             'I.dont.exist:9618?key1=val1&sock=collector&key2=val2',
             'fermicloudui.fnal.gov:9618-9620?sock=collector30-40&',
             ]


class Test_validate_node(unittest.TestCase):

    def test_good(self):
        for node in GOOD_NODES:
            try:
                validate_node(node, allow_range=True)
            except RuntimeError as e:
                raise e

    def test_bad(self):
        for node in BAD_NODES:
            try:
                validate_node(node, allow_range=True)
                raise RuntimeError('node %s validated, it should not')
            except RuntimeError as e:
                pass

    def test_range_not_allowed(self):
        for node in GOOD_NODES:
            try:
                validate_node(node, allow_range=False)
                raise RuntimeError('node %s validated, it should not')
            except RuntimeError as e:
                pass


if __name__ == '__main__':
    OFL = 'unittests-reports'
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=OFL))
