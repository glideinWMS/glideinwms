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

# todo
#def appendRealRunning
#def countMatch
#def countRealRunning
#def evalParamExpr


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

#@unittest.skip('yay')
class FETestCaseCondorStatus(unittest.TestCase):
    def setUp(self):
        with mock.patch('glideinwms.lib.condorExe.exe_cmd') as m_exe_cmd:
            f = open('cs.fixture')
            m_exe_cmd.return_value = f.readlines()
            self.status_dict = glideinFrontendLib.getCondorStatus(['coll1'])

    def test_getCondorStatus(self):
        machines = self.status_dict['coll1'].stored_data.keys()
        self.assertItemsEqual(machines, ['glidein_1@cmswn001.local', 'glidein_2@cmswn002.local',
                                         'glidein_3@cmswn003.local', 'glidein_4@cmswn004.local'])

    def test_getIdleCondorStatus(self):
        condorStatus = glideinFrontendLib.getIdleCondorStatus(self.status_dict)
        machines = condorStatus['coll1'].stored_data.keys()
        self.assertItemsEqual(machines, ['glidein_4@cmswn004.local'])

    def test_getRunningCondorStatus(self):
        condorStatus = glideinFrontendLib.getRunningCondorStatus(self.status_dict)
        machines = condorStatus['coll1'].stored_data.keys()
        self.assertItemsEqual(machines, ['glidein_1@cmswn001.local', 'glidein_2@cmswn002.local',
                                         'glidein_3@cmswn003.local'])

    def test_getClientCondorStatus(self):
        condorStatus = glideinFrontendLib.getClientCondorStatus(
            self.status_dict, 'frontend_v3', 'maingroup', 'Site_Name1@v3_0@factory1')
        machines = condorStatus['coll1'].stored_data.keys()
        self.assertItemsEqual(machines, ['glidein_1@cmswn001.local'])

    def test_getClientCondorStatusCredIdOnly(self):
        # need example with GLIDEIN_CredentialIdentifier
        pass
    def test_getClientCondorStatusPerCredId(self):
        # need example with GLIDEIN_CredentialIdentifier
        pass

    def test_countCondorStatus(self):
        self.assertEqual(glideinFrontendLib.countCondorStatus(self.status_dict), 4)

    def test_getFactoryEntryList(self):
        entries = glideinFrontendLib.getFactoryEntryList(self.status_dict)
        self.assertItemsEqual(
            entries,
            [('Site_Name%s@v3_0@factory%s' % (x, x), 'frontend%s.local' % x) for x in xrange(1,5)])

    def test_getCondorStatusSchedds(self):
        with mock.patch('glideinwms.lib.condorExe.exe_cmd') as m_exe_cmd:
            f = open('cs.schedd.fixture')
            m_exe_cmd.return_value = f.readlines()
            condorStatus = glideinFrontendLib.getCondorStatusSchedds(['coll1'])
            self.assertItemsEqual(condorStatus['coll1'].stored_data.keys(),
                                  ['schedd%s.local' % x for x in xrange(1,4)])

class FETestCaseMisc(unittest.TestCase):
    def test_uniqueSets(self):
        input = \
        [set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]), set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
         set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
              21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]),
         set([11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30])]

        expected = \
            ([(set([2]), set([32, 33, 34, 35, 31])),
              (set([0, 1, 2]), set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])),
              (set([2, 3]), set([11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                                 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]))],
             set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                  21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]))

        self.assertItemsEqual(expected, glideinFrontendLib.uniqueSets(input))

    def test_hashJob(self):
        in1 = {1: 'a', 2: 'b', 3: 'c'}
        in2 = [1, 3]
        expected = ((1, 'a'), (3, 'c'))
        self.assertItemsEqual(expected,
                              glideinFrontendLib.hashJob(in1, in2))

    def test_appendRealRunning(self):
        glideinFrontendLib.appendRealRunning(self.condorq_dict, self.status_dict)

#@unittest.skip('yay')
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

    def test_getRunningCondorQ(self):
        condor_ids = \
            glideinFrontendLib.getRunningCondorQ(self.condorq_dict)['sched1'].fetchStored().keys()

        self.assertItemsEqual(condor_ids, [(12345, 3), (12345, 4)])


    def test_getIdleCondorQ(self):
        condor_ids = \
            glideinFrontendLib.getIdleCondorQ(self.condorq_dict)['sched1'].fetchStored().keys()

        self.assertItemsEqual(condor_ids, [(12345, 0), (12345, 1), (12345,2)])

    def test_getIdleVomsCondorQ(self):
        condor_ids = \
            glideinFrontendLib.getIdleVomsCondorQ(self.condorq_dict)['sched1'].fetchStored().keys()

        self.assertEqual(condor_ids, [(12345, 2)])

    def test_getIdleProxyCondorQ(self):
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
