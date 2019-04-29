#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import mock
import os
import unittest2 as unittest
import xmlrunner

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
import glideinwms
from glideinwms.unittests.unittest_utils import runTest
from glideinwms.frontend import glideinFrontendMonitoring
import glideinwms.lib.condorMonitor as condorMonitor
import glideinwms.lib.condorExe as condorExe
import glideinwms.lib.fork as fork
from glideinwms.frontend.glideinFrontendElement import CounterWrapper
from glideinwms.frontend.glideinFrontendElement import glideinFrontendElement
from glideinwms.frontend.glideinFrontendElement import write_stats
from glideinwms.frontend.glideinFrontendElement import log_and_sum_factory_line
from glideinwms.frontend.glideinFrontendElement import init_factory_stats_arr
from glideinwms.frontend.glideinFrontendElement import log_factory_header
from glideinwms.unittests.unittest_utils import FakeLogger


def condor_side_effect(*args, **kwargs):
    if 'condor_q' in args[0]:
        fnm = 'cq.fixture'
    elif 'schedd' in args[0].lower():
        fnm = 'cs.schedd.fixture'
    else:
        fnm = 'cs.fixture'

    fdd = open(fnm)
    lines = fdd.readlines()
    fdd.close()
    return lines


def query_factory_side_effect(*args, **kwargs):
    fnm = 'fixtures/frontend/query_factory.fixture'
    fdd = open(fnm)
    blob = fdd.read()
    fdd.close()
    return eval(blob)


class TestCounterWrapper(unittest.TestCase):

    def setUp(self):
        dd = {'a': 'b', 'c': 'd'}
        self.cw = CounterWrapper(dd)

    def test___contains__(self):
        self.assertTrue(self.cw.__contains__('a'))
        self.assertFalse(self.cw.__contains__('b'))

    def test___delitem__(self):
        self.cw.__delitem__('a')
        self.assertFalse(self.cw.__contains__('a'))
        self.assertTrue(self.cw.__contains__('c'))

    def test___getitem__(self):
        self.assertEqual('b', self.cw.__getitem__('a'))

    def test___setitem__(self):
        self.cw.__setitem__('e', 'f')
        self.assertTrue(self.cw.__contains__('e'))

    def test_has_key(self):
        self.assertTrue('a' in self.cw)
        self.assertFalse(self.cw.__contains__('b'))


class TestGlideinFrontendElement(unittest.TestCase):

    def setUp(self):
        forkm_inst_mock = mock.create_autospec(
            'glideinwms.lib.fork.ForkManager', instance=True)
        forkm_class_mock = mock.Mock(return_value=forkm_inst_mock)
        with mock.patch('glideinwms.lib.fork.ForkManager') as forkm_class_mock:
            parent_pid = 0
            work_dir = 'fixtures/frontend'
            group_name = 'group1'
            action = 'yada yada'
            condorMonitor.USE_HTCONDOR_PYTHON_BINDINGS = False
            condorMonitor.LocalScheddCache.iGetEnv = mock.Mock()
            condorExe.exe_cmd = mock.Mock()
            condorExe.exe_cmd.side_effect = condor_side_effect
            glideinwms.frontend.glideinFrontendLib.logSupport.log = FakeLogger()
            self.gfe = glideinFrontendElement(
                os.getpid(), work_dir, group_name, action)
            self.gfe.frontend_name = 'Frontend-master-v1_0'
            self.gfe.configure()
            init_factory_stats_arr()
            self.verbose = os.environ.get('DEBUG_OUTPUT')
            self.gfe.get_condor_q = mock.Mock()
            self.gfe.get_condor_q.side_effect = condor_side_effect
            self.gfe.get_condor_status = mock.Mock()
            self.gfe.get_condor_status.side_effect = condor_side_effect

    def test___init__(self):
        if self.verbose:
            print('\nglideinFrontendElement=%s' % self.gfe)
            print('\ndir glideinFrontendElement=%s' % dir(self.gfe))
            print('\nglideinFrontendElement.attr_dict=%s' % self.gfe.attr_dict)
        self.assertTrue(isinstance(self.gfe, glideinFrontendElement))

    def test_configure(self):
        self.gfe.configure()
        if self.verbose:
            print('\nc.glideinFrontendElement=%s' % self.gfe)
            print('\nc.dir glideinFrontendElement=%s' % dir(self.gfe))
            print(
                '\nc.glideinFrontendElement.attr_dict=%s' %
                self.gfe.attr_dict)

    def test_set_glidein_config_limits(self):
        self.gfe.set_glidein_config_limits()

    def test_init_factory_stats_arr(self):
        init_factory_stats_arr()

    def test_log_factory_header(self):
        log_factory_header()

    @unittest.skip('for now')
    def test_build_resource_classad(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.build_resource_classad(this_stats_arr, request_name, glidein_el, glidein_in_downtime, factory_pool_node, my_identity, limits_triggered))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_check_removal_type(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.check_removal_type(glideid, remove_excess_str))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_choose_remove_excess_type(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.choose_remove_excess_type(count_jobs, count_status, glideid))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_compute_glidein_max_run(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.compute_glidein_max_run(prop_jobs, real, idle_glideins))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_compute_glidein_min_idle(self):
        # g# lidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.compute_glidein_min_idle(count_status, total_glideins, total_idle_glideins, fe_total_glideins, fe_total_idle_glideins, global_total_glideins, global_total_idle_glideins, effective_idle, effective_oldidle, limits_triggered))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_count_factory_entries_without_classads(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.count_factory_entries_without_classads(total_down_stats_arr))
        assert False  # TODO: implement your test here

    def test_deadvertiseAllClassads(self):
        self.gfe.deadvertiseAllClassads()

    @unittest.skip('for now')
    def test_do_match(self):
        self.gfe.do_match()

    @unittest.skip('hhmmm')
    def test_get_condor_q(self):
        cq = self.gfe.get_condor_q('schedd1')
        self.assertItemsEqual(
            cq['schedd1'].fetchStored().keys(), [
                (29, x) for x in xrange(
                    0, 9)])
        if self.verbose:
            print('---beg--test_get_condorq-------------------------------')
            print('cq=%s' % cq)
            print('dir cq=%s' % dir(cq))
            print('---end--test_get_condorq-------------------------------')

    @unittest.skip('hhmmm')
    def test_get_status(self):
        status_dict, fe_counts, global_counts, status_schedd_dict = self.gfe.get_condor_status()
        if self.verbose:
            print('---beg--test_get_status-------------------------------')
            print('status_dict=%s' % status_dict)
            print('fe_counts=%s' % fe_counts)
            print('global_counts=%s' % global_counts)
            print('status_schedd_dict=%s' % status_schedd_dict)
            print('----end-test_get_status-------------------------------')

    @unittest.skip('for now')
    def test_identify_bad_schedds(self):
        self.gfe.identify_bad_schedds()

    @unittest.skip('for now')
    def test_identify_limits_triggered(self):
        # self.gfe.identify_limits_triggered(count_status, total_glideins,
        #                                   total_idle_glideins, fe_total_glideins, fe_total_idle_glideins,
        #                                   global_total_glideins, global_total_idle_glideins,
        #                                   limits_triggered)
        assert False

    @unittest.skip('for now')
    def test_iterate(self):
        self.gfe.action = 'run'
        self.gfe.query_factory = mock.Mock()
        self.gfe.query_factory.side_effect = query_factory_side_effect
        self.gfe.iterate()
        print('after iteration self.gfe=%s' % self.gfe)
        print('dir self.gfe=%s' % dir(self.gfe))
        print('after iteration self.gfe.stats=%s' % dir(self.gfe.stats))
        print('after iteration self.gfe.stats.items=%s' % self.gfe.stats.items)
        print(
            'after iteration self.gfe.stats.values=%s' %
            self.gfe.stats.values)

    @unittest.skip('see test_frontend_element.py to see how to mock this')
    def test_iterate_one(self):
        self.gfe.stats = {'group': glideinFrontendMonitoring.groupStats()}
        self.gfe.published_frontend_name = '%s.XPVO_%s' % (self.gfe.frontend_name,
                                                           self.gfe.group_name)
        #from glideinwms.lib.fork import fork_in_bg, wait_for_pids
        #from glideinwms.lib.fork import ForkManager

        forkm_inst_mock = mock.create_autospec(
            'glideinwms.lib.fork.ForkManager', instance=True)
        fork_you_mock = mock.MagicMock()
        with mock.patch('glideinwms.lib.fork') as fork_you_mock:
            fork_you_mock.ForkManager.return_value = fork_you_mock
            fork_you_mock.ForkManager.fork_and_collect.return_value = {}
            self.gfe.iterate_one()

        # test 'GLIDEIN_In_Downtime'
        for glidein_el in self.gfe.glidein_dict:
            pass
            # if is_true(glidein_el.get('attrs').get('GLIDEIN_In_Downtime')):
            # check output of line 700
            # self.stats['group'].logFactDown(glideid_str, glidein_in_downtime)
            # with fakelogger

        # test 'GLIDEIN_REQUIRE_VOMS'
        for glidein_el in self.gfe.glidein_dict:
            pass
            # if is_true(glidein_el.get('attrs').get('GLIDEIN_REQUIRE_VOMS')):
            # check output of line 623 logSupport.log.info("Voms proxy required, limiting idle glideins to: %i" % prop_jobs['Idle'])
        # test 'GLIDEIN_REQUIRE_GLEXEC_USE'
        for glidein_el in self.gfe.glidein_dict:
            pass
            # if is_true(glidein_el.get('attrs').get('GLIDEIN_REQUIRE_GLEXEC_USE')):
            # check output of line 623 logSupport.log.info("Voms proxy required, limiting idle glideins to: %i" % prop_jobs['Idle'])
        # or could check self.condorq_dict_types['Idle']['prop'][glideid] = self.condorq_dict_types[dt]['prop'][glideid]
        # where dt = 'VomsIdle' if GLIDEIN_REQUIRE_VOMS or dt = 'ProxyIdle' if
        # GLIDEIN_REQUIRE_GLEXEC_USE

    @unittest.skip('for now')
    def test_log_and_print_total_stats(self):
        # self.gfe.log_and_print_total_stats(
        #    total_up_stats_arr, total_down_stats_arr)
        assert False

    @unittest.skip('for now')
    def test_log_and_print_unmatched(self):
        # self.gfe.log_and_print_unmatched(total_down_stats_arr)
        assert False

    @unittest.skip('for now')
    def test_populate_condorq_dict_types(self):
        self.gfe.condorq_dict = {
            'Idle_3600': {
                'abs': 0, 'dict': {}}, 'IdleAll': {
                'abs': 0, 'dict': {}}, 'Running': {
                'abs': 0, 'dict': {}}, 'ProxyIdle': {
                    'abs': 0, 'dict': {}}, 'Idle': {
                        'abs': 0, 'dict': {}}, 'OldIdle': {
                            'abs': 0, 'dict': {}}, 'VomsIdle': {
                                'abs': 0, 'dict': {}}}
        self.gfe.blacklist_schedds = []
        self.gfe.populate_condorq_dict_types()

    @unittest.skip('grr')
    def test_populate_pubkey(self):
        self.gfe.populate_pubkey()

    @unittest.skip('for now')
    def test_populate_status_dict_types(self):
        self.gfe.populate_status_dict_types()

    @unittest.skip('for now')
    def test_query_entries(self):
        # self.gfe.query_entries(factory_pool)
        assert False

    @unittest.skip('for now')
    def test_query_factory(self):
        # self.gfe.query_factory(factory_pool)
        assert False

    @unittest.skip('for now')
    def test_query_factoryclients(self):
        # self.gfe.query_factoryclients(factory_pool)
        assert False

    @unittest.skip('for now')
    def test_query_globals(self):
        # self.gfe.query_globals(factory_pool)
        assert False

    @unittest.skip('for now')
    def test_subprocess_count_dt(self):
        #self.gfe.subprocess_count_dt(dt)
        assert False

    @unittest.skip('for now')
    def test_subprocess_count_glidein(self):
        #self.gfe.subprocess_count_glidein(glidein_list)
        assert False

    @unittest.skip('for now')
    def test_subprocess_count_real(self):
        # self.gfe.subprocess_count_real()
        assert False

    @unittest.skip('for now')
    def test_write_stats(self):
        #write_stats(stats)
        assert False

    @unittest.skip('for now')
    def test_log_and_sum_factory_line(self):
        # log_and_sum_factory_line(
        #     factory,
        #     is_down,
        #     factory_stat_arr,
        #     old_factory_stat_arr)
        assert False

    @unittest.skip('for now')
    def test_expand__d_d(self):
        # expand_DD(qstr, attr_dict)
        assert False

    @unittest.skip('grr')
    def test_check_removal_type_config(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.check_removal_type_config(glideid))
        assert False  # TODO: implement your test here

    @unittest.skip('grr')
    def test_decide_removal_type(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.decide_removal_type(count_jobs, count_status, glideid))
        assert False  # TODO: implement your test here

    @unittest.skip('grr')
    def test_get_condor_status(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.get_condor_status())
        assert False  # TODO: implement your test here

    @unittest.skip('grr')
    def test_main(self):
        # glidein_frontend_element = glideinFrontendElement(parent_pid, work_dir, group_name, action)
        # self.assertEqual(expected, glidein_frontend_element.main())
        assert False  # TODO: implement your test here


class TestCheckParent(unittest.TestCase):
    @unittest.skip('grr')
    def test_check_parent(self):
        # self.assertEqual(expected, check_parent(parent_pid))
        assert False  # TODO: implement your test here




class TestLogAndSumFactoryLine(unittest.TestCase):
    @unittest.skip('grr')
    def test_log_and_sum_factory_line(self):
        # self.assertEqual(expected, log_and_sum_factory_line(factory, is_down, factory_stat_arr, old_factory_stat_arr))
        assert False  # TODO: implement your test here


class TestInitFactoryStatsArr(unittest.TestCase):
    @unittest.skip('grr')
    def test_init_factory_stats_arr(self):
        # self.assertEqual(expected, init_factory_stats_arr())
        assert False  # TODO: implement your test here


class TestLogFactoryHeader(unittest.TestCase):
    @unittest.skip('grr')
    def test_log_factory_header(self):
        # self.assertEqual(expected, log_factory_header())
        assert False  # TODO: implement your test here


class TestExpandDD(unittest.TestCase):
    @unittest.skip('grr')
    def test_expand__d_d(self):
        # self.assertEqual(expected, expand_DD(qstr, attr_dict))
        assert False  # TODO: implement your test here


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
