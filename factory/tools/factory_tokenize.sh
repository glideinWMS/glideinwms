#!/bin/bash
# file: factory_tokenize.sh
# project: glideinwms
# purpose: upgrades and configures condor on a glideinwms factory to
#          a version that supports condor token-auth on entry
#          points that also support it
# author: Dennis Box, dbox@fnal.gov
#
me=$(whoami)
if [ "$me" != "root" ]; then
    echo "this script must be run as root.  It will upgrade condor"
    echo "to a version that supports token-auth"
    exit 1
fi
startdir=$(pwd)
srcdir=$(dirname $0)
yum -y --enablerepo osg-upcoming install condor
cd $srcdir
cd ../../frontend/tools/
for F in make_user_token.sh	my_condor_ping token_setup.sh; do
    cp $F  /usr/local/bin
done
mkdir -p /etc/condor/passwords.d /etc/condor/tokens.d
condor_file='/etc/condor/config.d/03_gwms_local.config'
echo 'ALLOW_READ = * ' >> $condor_file
echo 'ALLOW_DAEMON = $(ALLOW_WRITE)' >> $condor_file
echo 'ALLOW_ADVERTISE_MASTER = $(ALLOW_DAEMON)' >> $condor_file
echo 'SEC_DEFAULT_AUTHENTICATION_METHODS = FS,GSI ' >> $condor_file
echo 'ALL_DEBUG = D_SECURITY, D_FULLDEBUG  ' >> $condor_file
echo 'SEC_NEGOTIATOR_AUTHENTICATION_METHODS = $(SEC_DEFAULT_AUTHENTICATION_METHODS) ' >> $condor_file
echo 'SEC_DAEMON_AUTHENTICATION_METHODS = $(SEC_DEFAULT_AUTHENTICATION_METHODS) ' >> $condor_file
echo 'QUEUE_SUPER_USER = root, condor ' >> $condor_file
echo 'RUNTIME_CONFIG_ADMIN = condor@$(FULL_HOSTNAME), root@$(FULL_HOSTNAME) ' >> $condor_file
echo 'ALLOW_CONFIG = $(RUNTIME_CONFIG_ADMIN) ' >> $condor_file
openssl rand -base64 64 | condor_store_cred -u condor_pool@$HOSTNAME -f /etc/condor/passwords.d/POOL add
cd ~
make_user_token.sh root
/bin/cp .condor/tokens.d/root.$HOSTNAME.token /etc/condor/tokens.d/admin.token
systemctl restart condor
systemctl stop gwms-factory
/usr/sbin/gwms-factory upgrade
/usr/sbin/gwms-factory reconfig
systemctl start gwms-factory
cd $startdir

