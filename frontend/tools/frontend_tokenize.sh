#!/bin/bash
# file: frontend_tokenize.sh
# project: glideinwms
# purpose:  changes glideinwms frontend condor configuration to use token_auth
# author: Dennis Box, dbox@fnal.gov
#
ID=$(whoami)
if [ ! "${ID}" = "root" ]; then
    echo must be run by root
    echo changes glideinwms condor configuration to use token_auth
    exit 1
fi

origdir=`pwd`
cd `dirname $0`
rundir=`pwd`
yum -y --enablerepo osg-upcoming install condor
for F in make_user_token.sh	my_condor_ping ; do
    cp $F  /usr/local/bin/$F
done
cp ../../creation/frontend_condortoken /usr/sbin
mkdir -p /etc/condor/passwords.d /etc/condor/tokens.d
touch /etc/sudoers
echo "frontend ALL=(ALL) NOPASSWD:SETENV: /usr/sbin/condor_store_cred" >> /etc/sudoers
echo "frontend ALL=(ALL) NOPASSWD:SETENV: /usr/bin/condor_token_create" >> /etc/sudoers
condor_file='/etc/condor/config.d/03_gwms_local.config'
touch $condor_file
echo 'ALLOW_READ = * ' >> $condor_file
echo 'ALLOW_DAEMON = $(ALLOW_WRITE) ' >> $condor_file
echo "SEC_DEFAULT_AUTHENTICATION_METHODS = TOKEN,FS,GSI ">> $condor_file
echo "ALL_DEBUG = D_SECURITY, D_FULLDEBUG " >> $condor_file
echo 'SEC_NEGOTIATOR_AUTHENTICATION_METHODS = $(SEC_DEFAULT_AUTHENTICATION_METHODS) '>> $condor_file
echo 'SEC_DAEMON_AUTHENTICATION_METHODS = $(SEC_DEFAULT_AUTHENTICATION_METHODS) '>> $condor_file
echo "QUEUE_SUPER_USER = root, condor" >> $condor_file
echo 'RUNTIME_CONFIG_ADMIN = condor@$(FULL_HOSTNAME), root@$(FULL_HOSTNAME)' >> $condor_file
echo 'ALLOW_CONFIG = $(RUNTIME_CONFIG_ADMIN)' >> $condor_file
openssl rand -base64 64 | condor_store_cred -u condor_pool@$HOSTNAME -f /etc/condor/passwords.d/POOL add
for ID in frontend condor root; do
    make_user_token.sh $ID
done
/bin/cp .condor/tokens.d/root.$HOSTNAME.token /etc/condor/tokens.d/admin.token
systemctl stop condor
systemctl start condor
systemctl stop gwms-frontend
systemctl start gwms-frontend
systemctl reload gwms-frontend
cd $origdir
