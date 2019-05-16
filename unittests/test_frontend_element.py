#!/usr/bin/env python
"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/frontend/glideinFrontendElement

 Author:
   Burt Holzman <burt@fnal.gov>
"""


from __future__ import absolute_import
import mock
import unittest2 as unittest
import xmlrunner
import glideinwms.lib.condorExe
import glideinwms.lib.condorMonitor as condorMonitor
from glideinwms.unittests.unittest_utils import FakeLogger
from glideinwms.unittests.unittest_utils import TestImportError
try:
    import glideinwms.frontend.glideinFrontendConfig as glideinFrontendConfig
    import glideinwms.frontend.glideinFrontendElement as glideinFrontendElement
except ImportError as err:
    raise TestImportError(str(err))




class FEElementTestCase(unittest.TestCase):
    def setUp(self):
        glideinwms.frontend.glideinFrontendLib.logSupport.log = FakeLogger()
        condorMonitor.USE_HTCONDOR_PYTHON_BINDINGS = False
        self.frontendDescript = glideinwms.frontend.glideinFrontendConfig.FrontendDescript(
            'fixtures/frontend')

        with mock.patch.object(glideinFrontendConfig.ConfigFile, 'load') as m_load:
            # simpler data structures
            self.attrDescript = glideinwms.frontend.glideinFrontendConfig.AttrsDescript(
                '', '')
            self.paramsDescript = glideinwms.frontend.glideinFrontendConfig.ParamsDescript(
                '', '')

            # bases for derived data structures
            elementDescriptBase = glideinwms.frontend.glideinFrontendConfig.ElementDescript(
                '', '')
            signatureDescript = glideinwms.frontend.glideinFrontendConfig.SignatureDescript(
                '')
            signatureDescript.data = {
                'group_group1': (
                    'ad0f57615c3df8bbb2130d96cfdf09363f4bd3ed',
                    'description.e98f4o.cfg'),
                'main': (
                    '7cea6e20d5a4e65e9468937f27511e3e44c72735',
                    'description.e98f4o.cfg')}

        self.paramsDescript.data = {
            'USE_MATCH_AUTH': 'True',
            'GLIDECLIENT_Rank': '1',
            'GLIDEIN_Collector': 'frontend:9620-9640'}
        self.paramsDescript.const_data = {
            'USE_MATCH_AUTH': (
                'CONST',
                'True'),
            'GLIDEIN_Collector': (
                'CONST',
                'frontend:9620-9640'),
            'GLIDECLIENT_Rank': (
                'CONST',
                '1')}

        self.attrDescript.data = {
            'GLIDEIN_Glexec_Use': 'OPTIONAL',
            'GLIDECLIENT_Rank': '1',
            'GLIDEIN_Expose_Grid_Env': 'True',
            'GLIDECLIENT_Start': 'True',
            'USE_MATCH_AUTH': 'True',
            'GLIDECLIENT_Group_Start': 'True',
            'GLIDEIN_Collector': 'frontend:9620-9640'}

        elementDescriptBase.data = {
            'GLIDEIN_Glexec_Use': 'OPTIONAL',
            'MapFile': '/var/lib/gwms-frontend/vofrontend/group_main/group.mapfile',
            'MaxRunningTotal': '100000',
            'JobMatchAttrs': '[]',
            'JobSchedds': '',
            'FactoryCollectors': '[]',
            'MaxIdleVMsPerEntry': '100',
            'CurbRunningTotal': '90000',
            'ReserveIdlePerEntry': '5',
            'MaxRunningPerEntry': '10000',
            'JobQueryExpr': 'True',
            'MaxIdleVMsTotal': '1000',
            'FactoryMatchAttrs': '[]',
            'MaxIdlePerEntry': '100',
            'FracRunningPerEntry': '1.15',
            'FactoryQueryExpr': 'True',
            'MatchExpr': 'True',
            'CurbIdleVMsTotal': '200',
            'GroupName': 'group1',
            'MaxMatchmakers': '3',
            'MapFileWPilots': '/var/lib/gwms-frontend/vofrontend/group_main/group_wpilots.mapfile',
            'CurbIdleVMsPerEntry': '5',
            'MinRunningPerEntry': '0',
            'IdleLifetime': '0',
            'RemovalType': 'NO',
            'RemovalWait': '0',
            'RemovalRequestsTracking': 'False',
            'RemovalMargin': '0'}

        with mock.patch.object(glideinFrontendConfig, 'SignatureDescript') as m_signatureDescript:
            m_signatureDescript.return_value = signatureDescript
            self.groupSignatureDescript = glideinwms.frontend.glideinFrontendConfig.GroupSignatureDescript(
                '', 'group1')

        with mock.patch.object(glideinFrontendConfig, 'ElementDescript') as m_elementDescript:
            with mock.patch.object(glideinFrontendConfig, 'FrontendDescript') as m_feDescript:
                m_elementDescript.return_value = elementDescriptBase
                m_feDescript.return_value = self.frontendDescript
                self.elementDescript = glideinwms.frontend.glideinFrontendConfig.ElementMergedDescript(
                    '', 'group1')

        @mock.patch(
            'glideinwms.frontend.glideinFrontendConfig.ElementMergedDescript')
        @mock.patch('glideinwms.frontend.glideinFrontendConfig.ParamsDescript')
        @mock.patch(
            'glideinwms.frontend.glideinFrontendConfig.GroupSignatureDescript')
        @mock.patch('glideinwms.frontend.glideinFrontendConfig.AttrsDescript')
        def create_glideinFrontendElement(
                m_AttrsDescript,
                m_GroupSignatureDescript,
                m_ParamsDescript,
                m_ElementMergedDescript):
            m_AttrsDescript.return_value = self.attrDescript
            m_GroupSignatureDescript.return_value = self.groupSignatureDescript
            m_ParamsDescript.return_value = self.paramsDescript
            m_ElementMergedDescript.return_value = self.elementDescript

            self.gfe = glideinFrontendElement.glideinFrontendElement(
                1, '', 'group1', '')
            self.gfe.elementDescript = self.elementDescript

        # @mock.patch defines these so disable pylint complaint
        create_glideinFrontendElement()  # pylint: disable=no-value-for-parameter

    def test_get_condor_q(self):
        with mock.patch('glideinwms.lib.condorMonitor.LocalScheddCache.iGetEnv'):
            with mock.patch('glideinwms.lib.condorExe.exe_cmd') as m_exe_cmd:
                f = open('cq.fixture')
                m_exe_cmd.return_value = f.readlines()
                cq = self.gfe.get_condor_q('schedd1')

        self.assertItemsEqual(
            cq['schedd1'].fetchStored().keys(), [
                (12345, x) for x in xrange(
                    0, 13)])

    def test_compute_glidein_max_run(self):
        self.assertEqual(self.gfe.compute_glidein_max_run(
            {'Idle': 412}, 971, 0), 1591)
        self.assertEqual(self.gfe.compute_glidein_max_run(
            {'Idle': 100}, 100, 0), 230)
        self.assertEqual(self.gfe.compute_glidein_max_run(
            {'Idle': 100}, 0, 0), 115)
        self.assertEqual(
            self.gfe.compute_glidein_max_run({'Idle': 0}, 0, 0), 0)
        self.assertEqual(self.gfe.compute_glidein_max_run(
            {'Idle': 0}, 100, 100), 100)

    def test_populate_pubkey(self):
        """ test that good public keys get populated
            and bad public keys get removed
        """
        glideinwms.frontend.glideinFrontendLib.logSupport.log = mock.Mock()
        self.gfe.globals_dict = {'bad_id':{'attrs':{'PubKeyValue':0}},
                                 'good_id':{'attrs':{'PubKeyValue':"-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAw7Cq5VGe3w2kNZOvu41W\n3jB8N6GHbilV2pPEdOpu2sVOBnzsfg3l+9hY1cFMcWsIc7/hbyp8y5vuJAE6yXGq\nJ0MZZC8upOioTLzS7gFPQsdaJBO4bVsv4W6GNO92HqT0ll8At+VbmkZzRC5ThZXk\nj6bEfuxfRbUogReOKZyEp8wZK9jx8DXx/dLrx+gxqMLofGx5GRVXJd5pb9SgwzQU\nxrPi9H8rCQdxECP1bQ9M1YYDwqJcrsDsukqQR6TS53QLmV3rW3olc3zpoUc3aX77\niaKdn8c0FxkvE9emSBXyzaF2NTyKRZofDW6KyuIB1XP9PanRa6UztQqwcoyymf6B\nCwIDAQAB\n-----END PUBLIC KEY-----\n"}}
                                }
        self.gfe.populate_pubkey()
        self.assertTrue('bad_id' not in self.gfe.globals_dict,
                'Bad public key was not removed')
        self.assertTrue('good_id' in self.gfe.globals_dict,
                'good public key was removed when it shouldnt have been')
        self.assertTrue('PubKeyObj' in self.gfe.globals_dict['good_id']['attrs'],
                'public key object not populated when it should have been')


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
