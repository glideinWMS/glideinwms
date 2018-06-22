#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner

import glideinwms.factory.glideFactoryLib 
from glideinwms.unittests.unittest_utils import FakeLogger
from glideinwms.factory.glideFactoryLib import FactoryConfig
from glideinwms.factory.glideFactoryLib import secClass2Name 
from glideinwms.factory.glideFactoryLib import getCondorQData 
from glideinwms.factory.glideFactoryLib import getCondorQCredentialList 
from glideinwms.factory.glideFactoryLib import getQCredentials 
from glideinwms.factory.glideFactoryLib import getQProxSecClass 
from glideinwms.factory.glideFactoryLib import getQStatusSF 
from glideinwms.factory.glideFactoryLib import getQStatus 
from glideinwms.factory.glideFactoryLib import getQStatusStale 
from glideinwms.factory.glideFactoryLib import getCondorStatusData 
from glideinwms.factory.glideFactoryLib import update_x509_proxy_file 
from glideinwms.factory.glideFactoryLib import ClientWeb 
from glideinwms.factory.glideFactoryLib import keepIdleGlideins 
from glideinwms.factory.glideFactoryLib import clean_glidein_queue 
from glideinwms.factory.glideFactoryLib import sanitizeGlideins 
from glideinwms.factory.glideFactoryLib import logStats 
from glideinwms.factory.glideFactoryLib import logWorkRequest 
from glideinwms.factory.glideFactoryLib import get_status_glideidx 
from glideinwms.factory.glideFactoryLib import hash_status 
from glideinwms.factory.glideFactoryLib import sum_idle_count 
from glideinwms.factory.glideFactoryLib import hash_statusStale 
from glideinwms.factory.glideFactoryLib import diffList 
from glideinwms.factory.glideFactoryLib import extractStaleSimple 
from glideinwms.factory.glideFactoryLib import extractUnrecoverableHeldSimple 
from glideinwms.factory.glideFactoryLib import extractUnrecoverableHeldForceX 
from glideinwms.factory.glideFactoryLib import extractRecoverableHeldSimple 
from glideinwms.factory.glideFactoryLib import extractRecoverableHeldSimpleWithinLimits 
from glideinwms.factory.glideFactoryLib import extractHeldSimple 
from glideinwms.factory.glideFactoryLib import extractIdleSimple 
from glideinwms.factory.glideFactoryLib import extractIdleUnsubmitted 
from glideinwms.factory.glideFactoryLib import extractIdleQueued 
from glideinwms.factory.glideFactoryLib import extractNonRunSimple 
from glideinwms.factory.glideFactoryLib import extractRunSimple 
from glideinwms.factory.glideFactoryLib import extractRunStale 
from glideinwms.factory.glideFactoryLib import group_unclaimed 
from glideinwms.factory.glideFactoryLib import schedd_name2str 
from glideinwms.factory.glideFactoryLib import extractJobId 
from glideinwms.factory.glideFactoryLib import escapeParam 
from glideinwms.factory.glideFactoryLib import executeSubmit 
from glideinwms.factory.glideFactoryLib import pickSubmitFile 
from glideinwms.factory.glideFactoryLib import submitGlideins 
from glideinwms.factory.glideFactoryLib import removeGlideins 
from glideinwms.factory.glideFactoryLib import releaseGlideins 
from glideinwms.factory.glideFactoryLib import in_submit_environment 
from glideinwms.factory.glideFactoryLib import get_submit_environment 
from glideinwms.factory.glideFactoryLib import isGlideinWithinHeldLimits 
from glideinwms.factory.glideFactoryLib import isGlideinUnrecoverable 
from glideinwms.factory.glideFactoryLib import isGlideinHeldNTimes 
from glideinwms.factory.glideFactoryLib import is_str_safe 
from glideinwms.factory.glideFactoryLib import GlideinTotals 
from glideinwms.factory.glideFactoryLib import set_condor_integrity_checks 
from glideinwms.factory.glideFactoryLib import which 
from glideinwms.factory.glideFactoryLib import days2sec 
from glideinwms.factory.glideFactoryLib import hrs2sec 
from glideinwms.factory.glideFactoryLib import env_list2dict 


class TestFactoryConfig(unittest.TestCase):

    def setUp(self):
        self.cnf = FactoryConfig()

    def test__init__(self):
        self.assertTrue(isinstance(self.cnf, FactoryConfig))

    def test_config_whoamI_(self):
        self.cnf.config_whoamI('my_factory','my_glidein')
        self.assertEqual(self.cnf.factory_name, 'my_factory')
        self.assertEqual(self.cnf.glidein_name, 'my_glidein')

    def test_get_condor_q_credential_list(self):
        glideinwms.factory.glideFactoryLib.logSupport.log = FakeLogger()
        getCondorQCredentialList(self.cnf)

class TestSecClass2Name(unittest.TestCase):
    @unittest.skip('for now')
    def test_sec_class2_name(self):
        self.assertEqual(expected, secClass2Name(client_security_name, proxy_security_class))
        # assert False TODO: implement your test here

class TestGetCondorQData(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_condor_q_data(self):
        self.assertEqual(expected, getCondorQData(entry_name, client_name, schedd_name, factoryConfig))
        # assert False TODO: implement your test here


class TestGetQCredentials(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_q_credentials(self):
        self.assertEqual(expected, getQCredentials(condorq, client_name, creds, client_sa, cred_secclass_sa, cred_id_sa))
        # assert False TODO: implement your test here

class TestGetQProxSecClass(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_q_prox_sec_class(self):
        self.assertEqual(expected, getQProxSecClass(condorq, client_name, proxy_security_class, client_schedd_attribute, credential_secclass_schedd_attribute, factoryConfig))
        # assert False TODO: implement your test here

class TestGetQStatusSF(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_q_status_s_f(self):
        self.assertEqual(expected, getQStatusSF(condorq))
        # assert False TODO: implement your test here

class TestGetQStatus(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_q_status(self):
        self.assertEqual(expected, getQStatus(condorq))
        # assert False TODO: implement your test here

class TestGetQStatusStale(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_q_status_stale(self):
        self.assertEqual(expected, getQStatusStale(condorq))
        # assert False TODO: implement your test here

class TestGetCondorStatusData(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_condor_status_data(self):
        self.assertEqual(expected, getCondorStatusData(entry_name, client_name, pool_name, factory_startd_attribute, glidein_startd_attribute, entry_startd_attribute, client_startd_attribute, factoryConfig))
        # assert False TODO: implement your test here

class TestUpdateX509ProxyFile(unittest.TestCase):
    @unittest.skip('for now')
    def test_update_x509_proxy_file(self):
        self.assertEqual(expected, update_x509_proxy_file(entry_name, username, client_id, proxy_data, factoryConfig))
        # assert False TODO: implement your test here

class TestClientWeb(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        client_web = ClientWeb(client_web_url, client_signtype, client_descript, client_sign, client_group, client_group_web_url, client_group_descript, client_group_sign, factoryConfig)
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_get_glidein_args(self):
        client_web = ClientWeb(client_web_url, client_signtype, client_descript, client_sign, client_group, client_group_web_url, client_group_descript, client_group_sign, factoryConfig)
        self.assertEqual(expected, client_web.get_glidein_args())
        # assert False TODO: implement your test here

class TestKeepIdleGlideins(unittest.TestCase):
    @unittest.skip('for now')
    def test_keep_idle_glideins(self):
        self.assertEqual(expected, keepIdleGlideins(client_condorq, client_int_name, req_min_idle, req_max_glideins, idle_lifetime, remove_excess, submit_credentials, glidein_totals, frontend_name, client_web, params, log, factoryConfig))
        # assert False TODO: implement your test here

class TestCleanGlideinQueue(unittest.TestCase):
    @unittest.skip('for now')
    def test_clean_glidein_queue(self):
        self.assertEqual(expected, clean_glidein_queue(remove_excess, glidein_totals, condorQ, req_min_idle, req_max_glideins, frontend_name, log, factoryConfig))
        # assert False TODO: implement your test here

class TestSanitizeGlideins(unittest.TestCase):
    @unittest.skip('for now')
    def test_sanitize_glideins(self):
        self.assertEqual(expected, sanitizeGlideins(condorq, log, factoryConfig))
        # assert False TODO: implement your test here

class TestLogStats(unittest.TestCase):
    @unittest.skip('for now')
    def test_log_stats(self):
        self.assertEqual(expected, logStats(condorq, client_int_name, client_security_name, proxy_security_class, log, factoryConfig))
        # assert False TODO: implement your test here

class TestLogWorkRequest(unittest.TestCase):
    @unittest.skip('for now')
    def test_log_work_request(self):
        self.assertEqual(expected, logWorkRequest(client_int_name, client_security_name, proxy_security_class, req_idle, req_max_run, work_el, fraction, log, factoryConfig))
        # assert False TODO: implement your test here

class TestGetStatusGlideidx(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_status_glideidx(self):
        self.assertEqual(expected, get_status_glideidx(el))
        # assert False TODO: implement your test here

class TestHashStatus(unittest.TestCase):
    @unittest.skip('for now')
    def test_hash_status(self):
        self.assertEqual(expected, hash_status(el))
        # assert False TODO: implement your test here

class TestSumIdleCount(unittest.TestCase):
    @unittest.skip('for now')
    def test_sum_idle_count(self):
        self.assertEqual(expected, sum_idle_count(qc_status))
        # assert False TODO: implement your test here

class TestHashStatusStale(unittest.TestCase):
    @unittest.skip('for now')
    def test_hash_status_stale(self):
        self.assertEqual(expected, hash_statusStale(el))
        # assert False TODO: implement your test here

class TestDiffList(unittest.TestCase):
    @unittest.skip('for now')
    def test_diff_list(self):
        self.assertEqual(expected, diffList(base_list, subtract_list))
        # assert False TODO: implement your test here

class TestExtractStaleSimple(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_stale_simple(self):
        self.assertEqual(expected, extractStaleSimple(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractUnrecoverableHeldSimple(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_unrecoverable_held_simple(self):
        self.assertEqual(expected, extractUnrecoverableHeldSimple(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractUnrecoverableHeldForceX(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_unrecoverable_held_force_x(self):
        self.assertEqual(expected, extractUnrecoverableHeldForceX(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractRecoverableHeldSimple(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_recoverable_held_simple(self):
        self.assertEqual(expected, extractRecoverableHeldSimple(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractRecoverableHeldSimpleWithinLimits(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_recoverable_held_simple_within_limits(self):
        self.assertEqual(expected, extractRecoverableHeldSimpleWithinLimits(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractHeldSimple(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_held_simple(self):
        self.assertEqual(expected, extractHeldSimple(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractIdleSimple(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_idle_simple(self):
        self.assertEqual(expected, extractIdleSimple(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractIdleUnsubmitted(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_idle_unsubmitted(self):
        self.assertEqual(expected, extractIdleUnsubmitted(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractIdleQueued(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_idle_queued(self):
        self.assertEqual(expected, extractIdleQueued(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractNonRunSimple(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_non_run_simple(self):
        self.assertEqual(expected, extractNonRunSimple(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractRunSimple(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_run_simple(self):
        self.assertEqual(expected, extractRunSimple(q, factoryConfig))
        # assert False TODO: implement your test here

class TestExtractRunStale(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_run_stale(self):
        self.assertEqual(expected, extractRunStale(q, factoryConfig))
        # assert False TODO: implement your test here

class TestGroupUnclaimed(unittest.TestCase):
    @unittest.skip('for now')
    def test_group_unclaimed(self):
        self.assertEqual(expected, group_unclaimed(el_list))
        # assert False TODO: implement your test here

class TestScheddName2str(unittest.TestCase):
    @unittest.skip('for now')
    def test_schedd_name2str(self):
        self.assertEqual(expected, schedd_name2str(schedd_name))
        # assert False TODO: implement your test here

class TestExtractJobId(unittest.TestCase):
    @unittest.skip('for now')
    def test_extract_job_id(self):
        self.assertEqual(expected, extractJobId(submit_out))
        # assert False TODO: implement your test here

class TestEscapeParam(unittest.TestCase):
    @unittest.skip('for now')
    def test_escape_param(self):
        self.assertEqual(expected, escapeParam(param_str))
        # assert False TODO: implement your test here

class TestExecuteSubmit(unittest.TestCase):
    @unittest.skip('for now')
    def test_execute_submit(self):
        self.assertEqual(expected, executeSubmit(log, factoryConfig, username, schedd, exe_env, submitFile))
        # assert False TODO: implement your test here

class TestPickSubmitFile(unittest.TestCase):
    @unittest.skip('for now')
    def test_pick_submit_file(self):
        self.assertEqual(expected, pickSubmitFile(submit_files, status_sf, nr_submitted_sf, log))
        # assert False TODO: implement your test here

class TestSubmitGlideins(unittest.TestCase):
    @unittest.skip('for now')
    def test_submit_glideins(self):
        self.assertEqual(expected, submitGlideins(entry_name, client_name, nr_glideins, idle_lifetime, frontend_name, submit_credentials, client_web, params, status_sf, log, factoryConfig))
        # assert False TODO: implement your test here

class TestRemoveGlideins(unittest.TestCase):
    @unittest.skip('for now')
    def test_remove_glideins(self):
        self.assertEqual(expected, removeGlideins(schedd_name, jid_list, force, log, factoryConfig))
        # assert False TODO: implement your test here

class TestReleaseGlideins(unittest.TestCase):
    @unittest.skip('for now')
    def test_release_glideins(self):
        self.assertEqual(expected, releaseGlideins(schedd_name, jid_list, log, factoryConfig))
        # assert False TODO: implement your test here

class TestInSubmitEnvironment(unittest.TestCase):
    @unittest.skip('for now')
    def test_in_submit_environment(self):
        self.assertEqual(expected, in_submit_environment(entry_name, exe_env))
        # assert False TODO: implement your test here

class TestGetSubmitEnvironment(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_submit_environment(self):
        self.assertEqual(expected, get_submit_environment(entry_name, client_name, submit_credentials, client_web, params, idle_lifetime, log, factoryConfig))
        # assert False TODO: implement your test here

class TestIsGlideinWithinHeldLimits(unittest.TestCase):
    @unittest.skip('for now')
    def test_is_glidein_within_held_limits(self):
        self.assertEqual(expected, isGlideinWithinHeldLimits(jobInfo, factoryConfig))
        # assert False TODO: implement your test here

class TestIsGlideinUnrecoverable(unittest.TestCase):
    @unittest.skip('for now')
    def test_is_glidein_unrecoverable(self):
        self.assertEqual(expected, isGlideinUnrecoverable(jobInfo, factoryConfig))
        # assert False TODO: implement your test here

class TestIsGlideinHeldNTimes(unittest.TestCase):
    @unittest.skip('for now')
    def test_is_glidein_held_n_times(self):
        self.assertEqual(expected, isGlideinHeldNTimes(jobInfo, factoryConfig, n))
        # assert False TODO: implement your test here

class TestIsStrSafe(unittest.TestCase):
    @unittest.skip('for now')
    def test_is_str_safe(self):
        self.assertEqual(expected, is_str_safe(s))
        # assert False TODO: implement your test here

class TestGlideinTotals(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        glidein_totals = GlideinTotals(entry_name, frontendDescript, jobDescript, entry_condorQ, log)
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test___str__(self):
        glidein_totals = GlideinTotals(entry_name, frontendDescript, jobDescript, entry_condorQ, log)
        self.assertEqual(expected, glidein_totals.__str__())
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_add_idle_glideins(self):
        glidein_totals = GlideinTotals(entry_name, frontendDescript, jobDescript, entry_condorQ, log)
        self.assertEqual(expected, glidein_totals.add_idle_glideins(nr_glideins, frontend_name))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_can_add_idle_glideins(self):
        glidein_totals = GlideinTotals(entry_name, frontendDescript, jobDescript, entry_condorQ, log)
        self.assertEqual(expected, glidein_totals.can_add_idle_glideins(nr_glideins, frontend_name, log, factoryConfig))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_get_max_held(self):
        glidein_totals = GlideinTotals(entry_name, frontendDescript, jobDescript, entry_condorQ, log)
        self.assertEqual(expected, glidein_totals.get_max_held(frontend_name))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_has_entry_exceeded_max_glideins(self):
        glidein_totals = GlideinTotals(entry_name, frontendDescript, jobDescript, entry_condorQ, log)
        self.assertEqual(expected, glidein_totals.has_entry_exceeded_max_glideins())
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_has_entry_exceeded_max_held(self):
        glidein_totals = GlideinTotals(entry_name, frontendDescript, jobDescript, entry_condorQ, log)
        self.assertEqual(expected, glidein_totals.has_entry_exceeded_max_held())
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_has_entry_exceeded_max_idle(self):
        glidein_totals = GlideinTotals(entry_name, frontendDescript, jobDescript, entry_condorQ, log)
        self.assertEqual(expected, glidein_totals.has_entry_exceeded_max_idle())
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_has_sec_class_exceeded_max_held(self):
        glidein_totals = GlideinTotals(entry_name, frontendDescript, jobDescript, entry_condorQ, log)
        self.assertEqual(expected, glidein_totals.has_sec_class_exceeded_max_held(frontend_name))
        # assert False TODO: implement your test here

class TestSetCondorIntegrityChecks(unittest.TestCase):
    def test_set_condor_integrity_checks(self):
        import os
        set_condor_integrity_checks()
        self.assertEqual( os.environ['_CONDOR_SEC_DEFAULT_INTEGRITY'], 'REQUIRED')

class TestWhich(unittest.TestCase):
    def test_which(self):
        lsloc = which('ls')
        self.assertTrue('/bin/ls' in lsloc )

class TestDays2sec(unittest.TestCase):
    def test_days2sec(self):
        self.assertEqual(259200, days2sec(3))

class TestHrs2sec(unittest.TestCase):
    def test_hrs2sec(self):
        self.assertEqual(7200, hrs2sec(2))

class TestEnvList2dict(unittest.TestCase):
    @unittest.skip('for now')
    def test_env_list2dict(self):
        self.assertEqual(expected, env_list2dict(env, sep))
        # assert False TODO: implement your test here

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
