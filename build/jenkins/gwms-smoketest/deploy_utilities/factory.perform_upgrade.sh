#!/bin/bash
cd `dirname $0`
source ./setup.sh
ssh -t root@$fact_fqdn yum -y --enablerepo osg-development upgrade glideinwms-factory 
ssh -t root@$fact_fqdn 'if `which systemctl> /dev/null 2>&1` ;then systemctl stop  gwms-factory.service;  gwms-factory upgrade; systemctl start  gwms-factory.service; else service gwms-factory upgrade; fi' 
ssh -t root@$fact_fqdn 'if `which systemctl> /dev/null 2>&1` ;then systemctl reload gwms-factory  ; else service gwms-factory upgrade; fi' 
ssh -t root@$fact_fqdn 'if `which systemctl> /dev/null 2>&1` ;then systemctl restart condor ; else service condor restart; fi' 
ssh -t root@$fact_fqdn 'if `which systemctl> /dev/null 2>&1` ;then systemctl restart gwms-factory ; else service gwms-factory restart; fi' 
