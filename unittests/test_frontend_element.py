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
        self.frontendDescript = glideinwms.frontend.glideinFrontendConfig.FrontendDescript('fixtures/frontend')

        with mock.patch.object(glideinFrontendConfig.ConfigFile, 'load') as m_load:
            # simpler data structures
            self.attrDescript = glideinwms.frontend.glideinFrontendConfig.AttrsDescript('', '')
            self.paramsDescript = glideinwms.frontend.glideinFrontendConfig.ParamsDescript('', '')

            # bases for derived data structures
            elementDescriptBase = glideinwms.frontend.glideinFrontendConfig.ElementDescript('', '')
            signatureDescript = glideinwms.frontend.glideinFrontendConfig.SignatureDescript('')
            signatureDescript.data = {
                'group_group1': ('ad0f57615c3df8bbb2130d96cfdf09363f4bd3ed', 'description.e98f4o.cfg'),
                'main': ('7cea6e20d5a4e65e9468937f27511e3e44c72735', 'description.e98f4o.cfg')}

        self.paramsDescript.data = {'USE_MATCH_AUTH': 'True', 'GLIDECLIENT_Rank': '1', 'GLIDEIN_Collector': 'frontend:9620-9640'}
        self.paramsDescript.const_data = {
            'USE_MATCH_AUTH': ('CONST', 'True'), 'GLIDEIN_Collector': ('CONST', 'frontend:9620-9640'),
            'GLIDECLIENT_Rank': ('CONST', '1')}

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

        with mock.patch.object(glideinFrontendConfig, 'SignatureDescript') as m_signatureDescript:
            m_signatureDescript.return_value = signatureDescript
            self.groupSignatureDescript = glideinwms.frontend.glideinFrontendConfig.GroupSignatureDescript('', 'group1')

        with mock.patch.object(glideinFrontendConfig, 'ElementDescript') as m_elementDescript:
            with mock.patch.object(glideinFrontendConfig, 'FrontendDescript') as m_feDescript:
                m_elementDescript.return_value = elementDescriptBase
                m_feDescript.return_value = self.frontendDescript
                self.elementDescript = glideinwms.frontend.glideinFrontendConfig.ElementMergedDescript('', 'group1')

    @mock.patch('glideinwms.frontend.glideinFrontendConfig.ElementMergedDescript')
    @mock.patch('glideinwms.frontend.glideinFrontendConfig.ParamsDescript')
    @mock.patch('glideinwms.frontend.glideinFrontendConfig.GroupSignatureDescript')
    @mock.patch('glideinwms.frontend.glideinFrontendConfig.AttrsDescript')
    def test_foo(self, m_AttrsDescript, m_GroupSignatureDescript, m_ParamsDescript, m_ElementMergedDescript):
        m_AttrsDescript.return_value = self.attrDescript
        m_GroupSignatureDescript.return_value = self.groupSignatureDescript
        m_ParamsDescript.return_value = self.paramsDescript
        m_ElementMergedDescript = self.elementDescript

        gfe = glideinFrontendElement.glideinFrontendElement(1, '/tmp/work_dir', 'group1', 'dingus')
#        cq = gfe.get_condor_q('schedd1')

if __name__ == '__main__':
    unittest.main()
    

