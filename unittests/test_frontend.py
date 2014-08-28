#!/usr/bin/env python

# virtualenv .venv
# cd .venv
# bin/activate.csh
# (just once): pip install mock unittest2

from glideinwms.frontend.glideinFrontendLib import getClientCondorStatus
from glideinwms.frontend.glideinFrontendLib import getClientCondorStatusCredIdOnly
from glideinwms.frontend.glideinFrontendLib import getClientCondorStatusPerCredId
import glideinwms.lib.condorExe
import glideinwms.lib.condorMonitor as condorMonitor
import glideinwms.frontend.glideinFrontendLib as glideinFrontendLib

import mock
import unittest2 as unittest
import dis
import inspect
import re
import sys
import StringIO


def compareLambdas(func1, func2):
    def strip_line_number(code):
        r = re.match('\s*\d+\s+(.*)', code[0])
        code[0] = r.group(1)

    def disassemble(func):
        out = StringIO.StringIO()
        err = StringIO.StringIO()
        saved = (sys.stdout, sys.stderr)
        sys.stdout = out
        sys.stderr = err
        dis.dis(func)
        sys.stdout, sys.stderr = saved
        out.seek(0)
        return out.readlines()

    code1 = disassemble(func1)
    code2 = disassemble(func2)
    strip_line_number(code1)
    strip_line_number(code2)

    if code1 != code2:
        print ''.join(code1)
        print ''.join(code2)
#        pass
    return code1 == code2

class FETestCaseCondorQ(unittest.TestCase):
    def prepare_condorq_dict(self):
        with mock.patch('glideinwms.lib.condorMonitor.LocalScheddCache.iGetEnv') as m_iGetEnv:
            cq = condorMonitor.CondorQ(schedd_name='sched1', pool_name='pool1')

        with mock.patch('glideinwms.lib.condorExe.exe_cmd') as m_exe_cmd:
            f = open('cq.fixture')
            m_exe_cmd.return_value = f.readlines()
            cq.load()

        self.condorq_dict = {'sched1': cq}

    def setUp(self):
        self.status_dict = {'coll1': '1001'}
        self.frontend_name = 'fe_name'
        self.group_name = 'group_name'
        self.request_name = 'request_name'
        self.cred_id = 1234
        self.default_format = [('JobStatus', 'i'), ('EnteredCurrentStatus', 'i'),
                               ('ServerTime', 'i'), ('RemoteHost', 's')]

        self.prepare_condorq_dict()

    @mock.patch.object(glideinFrontendLib, 'getClientCondorStatus')
    @mock.patch.object(glideinFrontendLib, 'getClientCondorStatusCredIdOnly')
    def test_getClientCondorStatusPerCredId(self,  m_getClientCondorStatusCredIdOnly, m_getClientCondorStatus):
        m_getClientCondorStatus.return_value = 'test_condor_status'
        getClientCondorStatusPerCredId(self.status_dict, self.frontend_name, self.group_name, self.request_name, self.cred_id)
        m_getClientCondorStatus.assert_called_with(self.status_dict, self.frontend_name, self.group_name, self.request_name)
        m_getClientCondorStatusCredIdOnly.assert_called_with('test_condor_status', self.cred_id)

    @mock.patch.object(glideinFrontendLib.condorMonitor, 'SubQuery')
    def test_getClientCondorStatusCredIdOnly(self, m_subquery):
        getClientCondorStatusCredIdOnly(self.status_dict, self.cred_id)
        self.assertEqual(m_subquery.call_args[0][0], self.status_dict.values()[0])

    @mock.patch.object(glideinFrontendLib, 'getCondorQConstrained')
    def test_getCondorQ_no_constraints(self, m_getCondorQConstrained):
        schedd_names = ['test_sched1', 'test_sched2']

        glideinFrontendLib.getCondorQ(schedd_names, job_status_filter=None)
        m_getCondorQConstrained.assert_called_with(schedd_names, 'True', None, None)

        glideinFrontendLib.getCondorQ(schedd_names)
        m_getCondorQConstrained.assert_called_with(schedd_names, '(JobStatus=?=1)||(JobStatus=?=2)', None, None)

        glideinFrontendLib.getCondorQ(schedd_names, job_status_filter=[5])
        m_getCondorQConstrained.assert_called_with(schedd_names, '(JobStatus=?=5)', None, None)

        constraint = '(JobStatus=?=1)||(JobStatus=?=2)'
        format_list = list((('x509UserProxyFirstFQAN','s'),))
        glideinFrontendLib.getCondorQ(schedd_names, 'True', format_list)
        m_getCondorQConstrained.assert_called_with(
            schedd_names,
            constraint,
            'True',
            format_list + self.default_format)

    @mock.patch.object(glideinFrontendLib.condorMonitor, 'SubQuery')
    def test_oldCondorQ(self, m_SubQuery):
        condorq_dict = {'a': 42}
        min_age = '_'

        glideinFrontendLib.getOldCondorQ(condorq_dict, min_age)
        self.assertEqual(m_SubQuery.call_args[0][0], 42)
        self.assertTrue(compareLambdas(m_SubQuery.call_args[0][1],
                                       lambda el:(el.has_key('ServerTime') and el.has_key('EnteredCurrentStatus') and ((el['ServerTime'] - el['EnteredCurrentStatus']) >= min_age))))

        # this just checks that the lambda is evaluating the min_age variable, not dereferencing it!

    def test_getRunningCondorq(self):
        condor_ids = \
            glideinFrontendLib.getRunningCondorQ(self.condorq_dict)['sched1'].fetchStored().keys()

        self.assertItemsEqual(condor_ids, [(12345, 3), (12345, 4)])


    def test_getIdleCondorq(self):
        condor_ids = \
            glideinFrontendLib.getIdleCondorQ(self.condorq_dict)['sched1'].fetchStored().keys()

        self.assertItemsEqual(condor_ids, [(12345, 0), (12345, 1), (12345,2)])

    def test_getIdleVomsCondorq(self):
        condor_ids = \
            glideinFrontendLib.getIdleVomsCondorQ(self.condorq_dict)['sched1'].fetchStored().keys()

        self.assertEqual(condor_ids, [(12345, 2)])

    def test_getIdleProxyCondorq(self):
        condor_ids = \
            glideinFrontendLib.getIdleProxyCondorQ(self.condorq_dict)['sched1'].fetchStored().keys()

        self.assertItemsEqual(condor_ids, [(12345, 1), (12345, 2)])

    def test_getOldCondorQ(self):
        min_age = 100
        condor_ids = \
            glideinFrontendLib.getOldCondorQ(self.condorq_dict, min_age)['sched1'].fetchStored().keys()
        self.assertEqual(condor_ids, [(12345, 0)])

    def test_countCondorQ(self):
        count = glideinFrontendLib.countCondorQ(self.condorq_dict)
        self.assertEqual(count, 5)

    def test_getCondorQUsers(self):
        users = glideinFrontendLib.getCondorQUsers(self.condorq_dict)
        self.assertItemsEqual(users, ['user1@fnal.gov', 'user2@fnal.gov'])

    @mock.patch('glideinwms.lib.condorMonitor.LocalScheddCache.iGetEnv')
    @mock.patch('glideinwms.lib.condorExe.exe_cmd')
    def test_getCondorQ(self, m_exe_cmd, m_iGetEnv):
        f = open('cq.fixture')
        m_exe_cmd.return_value = f.readlines()

        cq = glideinFrontendLib.getCondorQ(['sched1'])
        condor_ids = cq['sched1'].fetchStored().keys()

        self.assertItemsEqual(condor_ids, [(12345, x) for x in xrange(0,5)])

if __name__ == '__main__':
    unittest.main()
