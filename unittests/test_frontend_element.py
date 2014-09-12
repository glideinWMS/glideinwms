#!/usr/bin/env python

from glideinwms.frontend.glideinFrontendLib import getClientCondorStatus
from glideinwms.frontend.glideinFrontendLib import getClientCondorStatusCredIdOnly
from glideinwms.frontend.glideinFrontendLib import getClientCondorStatusPerCredId
import glideinwms.lib.condorExe
import glideinwms.lib.condorMonitor as condorMonitor
import glideinwms.frontend.glideinFrontendLib as glideinFrontendLib
import glideinwms.frontend.glideinFrontendConfig as glideinFrontendConfig
import glideinwms.frontend.glideinFrontendElement as glideinFrontendElement

from unittest_utils import FakeLogger

import mock
import unittest2 as unittest
import dis
import inspect
import re
import sys
import StringIO

class FEElementTestCase(unittest.TestCase):
    def setUp(self):
        glideinwms.frontend.glideinFrontendLib.logSupport.log = FakeLogger()

        with mock.patch.object(glideinFrontendConfig.ConfigFile, 'load') as m_load:
            self.attrDescript = glideinwms.frontend.glideinFrontendConfig.AttrsDescript('', '')
            elementDescriptBase = glideinwms.frontend.glideinFrontendConfig.ElementDescript('', '')

        self.attrDescript.data = {
            'GLIDEIN_Glexec_Use': 'OPTIONAL', 'GLIDECLIENT_Rank': '1', 'GLIDEIN_Expose_Grid_Env': 'True',
            'GLIDECLIENT_Start': 'True', 'USE_MATCH_AUTH': 'True', 'GLIDECLIENT_Group_Start': 'True',
            'GLIDEIN_Collector': 'frontend:9620-9640'}

        elementDescriptBase.data = {
            'GLIDEIN_Glexec_Use': 'OPTIONAL', 'MapFile': '/var/lib/gwms-frontend/vofrontend/group_main/group.mapfile',
            'MaxRunningTotal': '100000', 'JobMatchAttrs': '[]', 'JobSchedds': '', 'FactoryCollectors': '[]',
            'MaxIdleVMsPerEntry': '100', 'CurbRunningTotal': '90000', 'ReserveIdlePerEntry': '5', 'MaxRunningPerEntry': '10000',
            'JobQueryExpr': 'True', 'MaxIdleVMsTotal': '1000', 'FactoryMatchAttrs': '[]', 'MaxIdlePerEntry': '100',
            'FracRunningPerEntry': '1.15', 'FactoryQueryExpr': 'True', 'MatchExpr': 'True', 'CurbIdleVMsTotal': '200',
            'GroupName': 'group1', 'MaxMatchmakers': '3',
            'MapFileWPilots': '/var/lib/gwms-frontend/vofrontend/group_main/group_wpilots.mapfile', 'CurbIdleVMsPerEntry': '5'}

        self.frontendDescript = glideinwms.frontend.glideinFrontendConfig.FrontendDescript('fixtures/frontend')

        with mock.patch.object(glideinFrontendConfig, 'ElementDescript') as m_elementDescript:
            with mock.patch.object(glideinFrontendConfig, 'FrontendDescript') as m_feDescript:
                m_elementDescript.return_value = elementDescriptBase
                m_feDescript.return_value = self.frontendDescript
                self.elementDescript = glideinwms.frontend.glideinFrontendConfig.ElementMergedDescript('', 'group1')


#        print self.elementDescript.data



    @mock.patch('glideinwms.frontend.glideinFrontendConfig.ElementMergedDescript')
    @mock.patch('glideinwms.frontend.glideinFrontendConfig.ParamsDescript')
    @mock.patch('glideinwms.frontend.glideinFrontendConfig.GroupSignatureDescript')
    @mock.patch('glideinwms.frontend.glideinFrontendConfig.AttrsDescript')
    def test_foo(self, m_AttrsDescript, m_GroupSignatureDescript, m_ParamsDescript, m_ElementMergedDescript):
        m_AttrsDescript.return_value = self.attrDescript
#        m_ParamsDecript.return_value = self.attrDescript
#        m_AttrsDescript.return_value = self.attrDescript
#        m_AttrsDescript.return_value = self.attrDescript
        pass

#        self.elementDescript = glideinFrontendConfig.ElementMergedDescript('fixtures/frontend', 'group1')
#        print dir(self.elementDescript)
#        m_ad.return_value = self.attrDescript
        gfe = glideinFrontendElement.glideinFrontendElement(1, '/tmp/work_dir', 'group1', 'dingus')
#        cq = gfe.get_condor_q('schedd1')


#        print cq
        #gfe.populate_condorq_dict_types()


#        self.paramsDescript = glideinFrontendConfig.ParamsDescript(self.work_dir, self.group_name)
#        self.signatureDescript = glideinFrontendConfig.GroupSignatureDescript(self.work_dir, self.group_name)
#        self.attr_dict = glideinFrontendConfig.AttrsDescript(self.work_dir,self.group_name).data

if __name__ == '__main__':
    unittest.main()
    

