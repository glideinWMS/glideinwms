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
import os
import mock
import unittest2 as unittest
import xmlrunner
import jsonpickle
import glideinwms.lib.condorExe
import glideinwms.lib.condorMonitor as condorMonitor
from glideinwms.unittests.unittest_utils import FakeLogger
from glideinwms.unittests.unittest_utils import TestImportError
from glideinwms.lib.fork import ForkManager
from glideinwms.frontend import glideinFrontendMonitoring
from glideinwms.frontend import glideinFrontendInterface
from glideinwms.lib.util import safe_boolcomp

try:
    import glideinwms.frontend.glideinFrontendConfig as glideinFrontendConfig
    import glideinwms.frontend.glideinFrontendElement as glideinFrontendElement
except ImportError as err:
    raise TestImportError(str(err))

LOG_DATA = []
def log_info_side_effect(*args, **kwargs):
    """
    keep logSupport.log.info data in an array so we can search it later
    """
    LOG_DATA.append(args[0])


def uni_to_str_JSON(obj):
    """
    on some machines jsonpickle.decode() returns unicode strings
    and on others it returns ascii strings from the same data.
    The objects being tested here expect python strings, so convert them
    if necessary.  I am sure there is a better way to do this.
    """
    if isinstance(obj, dict):
        newobj = {}
        for key, value in obj.iteritems():
            keyobj = uni_to_str_JSON(key)
            newobj[keyobj] = uni_to_str_JSON(value)
    elif isinstance(obj, list):
        newobj = []
        for value in obj:
            newobj.append(uni_to_str_JSON(value))
    elif isinstance(obj, tuple):
        newobj = ()
        for value in obj:
            newobj = newobj + (uni_to_str_JSON(value),)
    elif isinstance(obj, unicode):
        newobj = str(obj)
    else:
        newobj = obj

    return newobj


def fork_and_collect_side_effect():
    """ 
    populate data structures in 
    glideinFrontendElement::iterate_one from
    json artifact in fixtures
    """
    with open('fixtures/frontend/pipe_out.iterate_one', 'r') as fd:
        json_str = fd.read()
        pipe_out_objs = uni_to_str_JSON(jsonpickle.decode(json_str, keys=True))
    for key in pipe_out_objs:
        try:
            keyobj = eval(key)
            pipe_out_objs[keyobj] = pipe_out_objs.pop(key)
        except BaseException:
            pass
    return pipe_out_objs


def bounded_fork_and_collect_side_effect():
    """ 
    populate data structures in glideinFrontendElement::do_match
    from json artifact in fixtures
    """
    with open('fixtures/frontend/pipe_out.do_match', 'r') as fd:
        json_str = fd.read()
        pipe_out_objs = uni_to_str_JSON(jsonpickle.decode(json_str, keys=True))
    for key in pipe_out_objs:
        try:
            keyobj = eval(key)
            pipe_out_objs[keyobj] = pipe_out_objs.pop(key)
        except BaseException:
            pass
    return pipe_out_objs


class FEElementTestCase(unittest.TestCase):
    def setUp(self):
        self.debug_output = os.environ.get('DEBUG_OUTPUT')
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

    def test_some_iterate_one_artifacts(self):
        """
        Mock our way into glideinFrontendElement:iterate_one() to test if
             glideinFrontendElement.glidein_dict['entry_point']['attrs']['GLIDEIN_REQUIRE_VOMS']
                and
             glideinFrontendElement.glidein_dict['entry_point']['attrs']['GLIDEIN_REQUIRE_GLEXEC_USE']
                and
             glideinFrontendElement.glidein_dict['entry_point']['attrs']['GLIDEIN_In_Downtime']

             are being evaluated correctly
        """

        self.gfe.stats = {'group': glideinFrontendMonitoring.groupStats()}
        self.gfe.published_frontend_name = '%s.XPVO_%s' % (
            self.gfe.frontend_name, self.gfe.group_name)
        mockery = mock.MagicMock()
        self.gfe.x509_proxy_plugin = mockery
        # keep logSupport.log.info in an array to search through later to
        # evaluate success
        glideinwms.frontend.glideinFrontendLib.logSupport.log = mockery
        mockery.info = log_info_side_effect

        # ForkManager mocked inside iterate_one, return data loaded from
        # fork_and_collect_side_effect
        # data loaded includes both legal True, False, 'True', 'False' , 'TRUE' etc
        # and obviously bad data 1, 0, etc

        with mock.patch.object(ForkManager, 'fork_and_collect',
                               return_value=fork_and_collect_side_effect()):
            with mock.patch.object(ForkManager, 'bounded_fork_and_collect',
                                   return_value=bounded_fork_and_collect_side_effect()):
                # also need to mock advertisers so they don't fork off jobs
                # it has nothing to do with what is being tested here
                with mock.patch.object(glideinFrontendInterface, 'MultiAdvertizeWork'):
                    with mock.patch('glideinFrontendInterface.ResourceClassadAdvertiser.advertiseAllClassads',
                                    return_value=None):
                        with mock.patch.object(glideinFrontendInterface, 'ResourceClassadAdvertiser'):
                            # finally run iterate_one and collect the log data
                            self.gfe.iterate_one()

        # go through glideinFrontendElement data structures
        # collecting data to match against log output
        glideid_list = sorted(
            self.gfe.condorq_dict_types['Idle']['count'].keys())
        glideids = []
        in_downtime = {}
        req_voms = {}
        req_glexec = {}
        for elm in glideid_list:
            if elm and elm[0]:
                glideid_str = "%s@%s" % (str(elm[1]), str(elm[0]))
                gdata = self.gfe.glidein_dict[elm]['attrs']
                glideids.append(glideid_str)
                in_downtime[glideid_str] = safe_boolcomp(
                    gdata.get('GLIDEIN_In_Downtime'), True)
                req_voms[glideid_str] = safe_boolcomp(
                    gdata.get('GLIDEIN_REQUIRE_VOMS'), True)
                req_glexec[glideid_str] = safe_boolcomp(
                    gdata.get('GLIDEIN_REQUIRE_GLEXEC_USE'), True)

        # run through the info log
        # if GLIDEIN_REQUIRE_VOMS was set to True, 'True', 'tRUE' etc for an entry:
        #    'Voms Proxy Required,' will appear in previous line of log
        # elif GLIDEIN_REQUIRE_GLEXEC_USE was set:
        #     'Proxy required (GLEXEC)' will appear in log
        idx = 0
        for lgln in LOG_DATA:
            parts = lgln.split()
            gid = parts[-1]
            if gid in glideids:
                upordown = parts[-2]
                fmt_str = "glideid:%s in_downtime:%s req_voms:%s "
                fmt_str += "req_glexec:%s\nlog_data:%s"
                state = fmt_str % (gid,
                                   in_downtime[gid],
                                   req_voms[gid],
                                   req_glexec[gid],
                                   LOG_DATA[idx - 1])
                if self.debug_output:
                    print('%s' % state)
                use_voms = req_voms[gid]
                use_glexec = req_glexec[gid]

                if in_downtime[gid]:
                    self.assertTrue(
                        upordown == 'Down', "%s logs this as %s" %
                        (gid, upordown))
                else:
                    self.assertTrue(
                        upordown == 'Up', "%s logs this as %s" %
                        (gid, upordown))

                if use_voms:
                    self.assertTrue(
                        'Voms proxy required,' in LOG_DATA[idx - 1], state)
                else:
                    self.assertFalse(
                        'Voms proxy required,' in LOG_DATA[idx - 1], state)
                    if use_glexec:
                        self.assertTrue(
                            'Proxy required (GLEXEC)' in LOG_DATA[idx - 1], state)
                    else:
                        self.assertFalse(
                            'Proxy required (GLEXEC)' in LOG_DATA[idx - 1], state)

            idx += 1

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
