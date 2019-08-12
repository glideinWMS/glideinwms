#!/bin/bash
cd `dirname $0`
source ./setup.sh
ssh -t root@$vofe_fqdn sed -i /etc/gwms-frontend/frontend.xml -e 's/9620-9630/9618?sock=collector1-40/'
ssh -t root@$vofe_fqdn yum -y --enablerepo osg-development upgrade glideinwms-vofrontend 
ssh -t root@$vofe_fqdn 'if `which systemctl> /dev/null 2>&1` ;then systemctl stop gwms-frontend.service;  gwms-frontend upgrade ; systemctl start  gwms-frontend.service;  else service gwms-frontend upgrade; fi' 
ssh -t root@$vofe_fqdn 'if `which systemctl> /dev/null 2>&1` ;then systemctl restart condor ; else service condor restart; fi' 
ssh -t root@$vofe_fqdn 'if `which systemctl> /dev/null 2>&1` ;then systemctl reload gwms-frontend ; else service gwms-frontend reconfig; fi' 
ssh -t root@$vofe_fqdn 'if `which systemctl> /dev/null 2>&1` ;then systemctl restart gwms-frontend ; else service gwms-frontend restart; fi' 
