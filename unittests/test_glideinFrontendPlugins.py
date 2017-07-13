#!/usr/bin/env python
from __future__ import absolute_import
from builtins import range
from builtins import str
import os
import sys
import shutil
import tempfile
import tarfile
import unittest2 as unittest
import xmlrunner

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest
from glideinwms.unittests.unittest_utils import create_temp_file
from glideinwms.unittests.unittest_utils import create_random_string
from glideinwms.unittests.unittest_utils import FakeLogger

from glideinwms.lib import condorMonitor
from glideinwms.lib import logSupport
from glideinwms.frontend import glideinFrontendPlugins
from glideinwms.frontend.glideinFrontendInterface import Credential

class fakeObj:
    def __init__(self):
        self.min_nr_glideins=10
        self.max_run_glideins=30

class fakeDescript:

    def __init__(self):
        self.merged_data={}
        self.merged_data['ProxySecurityClasses']={}
        self.merged_data['ProxyTrustDomains']={}
        self.merged_data['ProxyTypes']={}
        self.merged_data['ProxyKeyFiles']={}
        self.merged_data['ProxyPilotFiles']={}
        self.merged_data['ProxyVMIds']={}
        self.merged_data['ProxyVMTypes']={}
        self.merged_data['ProxyRemoteUsernames']={}
        self.merged_data['ProxyProjectIds']={}
        self.merged_data['ProxyCreationScripts']={}
        self.merged_data['ProxyUpdateFrequency']={}


    def addproxy(self, name):
        self.merged_data['ProxySecurityClasses'][name]="frontend"
        self.merged_data['ProxyTrustDomains'][name]="OSG"
        self.merged_data['ProxyTypes'][name]="grid_proxy"
        #self.merged_data['ProxyKeyFiles'][name]=
        #self.merged_data['ProxyPilotFiles'][name]=""
        #self.merged_data['ProxyVMIds'][name]=""
        #self.merged_data['ProxyVMTypes'][name]=""
        

class TestPlugins(unittest.TestCase):
    """
    Test the proxy plugins
    """
    def getCredlist(self):
        # Create fake Credentials
        rtnlist=[]
        for t in range(30):
            (f, proxyfile)= tempfile.mkstemp()
            os.close(f)
            self.elementDescript.addproxy(proxyfile)
            rtnlist.append(Credential(t, proxyfile, self.elementDescript))
        return rtnlist

    def killCredlist(self, list):
        for cred in list:
            os.remove(cred.filename)

    def setUp(self):
        logSupport.log = FakeLogger()
        self.config_dir="/tmp"
        #self.working_dir = tempfile.mkdtemp()
        self.credlist=[]
        # Create fake descript
        self.elementDescript=fakeDescript()
        self.createCondor()

    #Fake calling condor_q and condor_status
    def createCondor(self):
        self.condorq_dict={}
        self.condorstatus_dict={}
        key='schedd_job1@schedd1.domain.tld'
        key2='schedd1.domain.tld'
        key3='usercollector_service@schedd1.domain.tld'
        self.condorq_dict[key]=condorMonitor.CondorQ(key, schedd_lookup_cache=None)
        self.condorq_dict[key].stored_data={}
        for jid in range(10):
            user_str="user"+str(jid)+"@random.domain.tld"
            self.condorq_dict[key].stored_data[(jid, 0)]={}
            self.condorq_dict[key].stored_data[(jid, 0)]['User']=user_str
            self.condorq_dict[key].stored_data[(jid, 0)]['ClusterId']=0
            self.condorq_dict[key].stored_data[(jid, 0)]['ProcId']=jid
            self.condorq_dict[key].stored_data[(jid, 0)]['JobStatus']=1
            self.condorstatus_dict[user_str]={}
            self.condorstatus_dict[user_str]['MyType']='Submitter'
        entry_str="entry_name@instance@service@vofrontend_service-vofrontend_instance.main"
        self.condorstatus_dict[entry_str]={}
        self.condorstatus_dict[entry_str]['MyType']='glideresource'
        self.condorstatus_dict[key]={}
        self.condorstatus_dict[key]['MyType']='Scheduler'
        self.condorstatus_dict[key]['NumUsers']=0
        self.condorstatus_dict[key2]={}
        self.condorstatus_dict[key2]['MyType']='Negotiator'
        self.condorstatus_dict[key3]={}
        self.condorstatus_dict[key3]['MyType']='Collector'
        for k in list(self.condorstatus_dict.keys()):
            self.condorstatus_dict[k]['CurrentTime']='time()'

    def tearDown(self):
        if os.path.exists("/tmp/proxy_usermap_wr.dat"):
            os.remove("/tmp/proxy_usermap_wr.dat")
        if os.path.exists("/tmp/proxy_user_rr.dat"):
            os.remove("/tmp/proxy_user_rr.dat")

    def test_proxy_first(self):
        self.credlist=self.getCredlist()
        p=glideinFrontendPlugins.ProxyFirst(self.config_dir, self.credlist)
        p.update_usermap(self.condorq_dict, self.condorq_dict, 
            self.condorstatus_dict, self.condorstatus_dict)
        testlist=p.get_credentials(fakeObj(), "grid_proxy", "OSG")
        self.assertEqual(testlist, [self.credlist[0]])
        testlist=p.get_credentials(fakeObj(), "grid_proxy", "FAKE")
        self.assertEqual(testlist, [])
        self.killCredlist(self.credlist)

    def test_proxy_all(self):
        self.credlist=self.getCredlist()
        p=glideinFrontendPlugins.ProxyAll(self.config_dir, self.credlist)
        p.update_usermap(self.condorq_dict, self.condorq_dict, 
            self.condorstatus_dict, self.condorstatus_dict)
        testlist=p.get_credentials(fakeObj(), "grid_proxy", "OSG")
        self.assertEqual(testlist, self.credlist)
        testlist=p.get_credentials(fakeObj(), "grid_proxy", "FAKE")
        self.assertEqual(testlist, [])
        self.killCredlist(self.credlist)
    
    def test_proxy_userr(self):
        self.credlist=self.getCredlist()
        p=glideinFrontendPlugins.ProxyUserRR(self.config_dir, self.credlist)
        p.update_usermap(self.condorq_dict, self.condorq_dict, 
            self.condorstatus_dict, self.condorstatus_dict)
        testlist=p.get_credentials(fakeObj(), "grid_proxy", "OSG")
        self.assertEqual(testlist, self.credlist[0:10])
        self.killCredlist(self.credlist)

    def test_proxy_cardinality(self):
        self.credlist=self.getCredlist()
        p=glideinFrontendPlugins.ProxyUserCardinality(self.config_dir, self.credlist)
        p.update_usermap(self.condorq_dict, self.condorq_dict, 
            self.condorstatus_dict, self.condorstatus_dict)
        testlist=p.get_credentials(fakeObj(), "grid_proxy", "OSG")
        self.assertEqual(testlist, self.credlist[0:10])
        self.killCredlist(self.credlist)

    def test_proxy_usermap(self):
        self.credlist=self.getCredlist()
        p=glideinFrontendPlugins.ProxyUserMapWRecycling(self.config_dir, self.credlist)
        p.update_usermap(self.condorq_dict, self.condorq_dict, 
            self.condorstatus_dict, self.condorstatus_dict)
        testlist=p.get_credentials(fakeObj(), "grid_proxy", "OSG")
        self.assertEqual(testlist, self.credlist[0:10])
        self.killCredlist(self.credlist)


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
