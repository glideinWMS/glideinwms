#!/bin/bash
cd `dirname $0`
source ./setup.sh
ssh root@$vofe_fqdn yum -y --enablerepo osg-development upgrade glideinwms-vofrontend 
ssh root@$vofe_fqdn 'if `which systemctl> /dev/null 2>&1` ;then systemctl stop gwms-frontend.service;  gwms-frontend upgrade ; systemctl start  gwms-frontend.service;  else service gwms-frontend upgrade; fi' 
ssh root@$vofe_fqdn 'if `which systemctl> /dev/null 2>&1` ;then gwms-frontend reconfig ; else service gwms-frontend reconfig; fi' 
