#!/bin/bash

# Tool to automate the GlideinWMS rpm deployment and testing
# Author: Parag Mhashilkar
# 

function launch_vm() {
    local vm_name=$1
    local vm_template=$2
    local output="`$SSH onetemplate instantiate --name $vm_name $vm_template`"
    echo $output | awk -F' ' '{print $NF}'
}


function vm_hostname() {
    local vmid=$1
    $SSH onehostname $vmid
}


function is_vm_up() {
    local fqdn=$1
    # Wait for 5 min trying ssh into the machine every 30 sec
    # When ssh is successfull, machine is usable
    local retries=0
    echo -n "Waiting for $fqdn to boot up ..."
    while [ $retries -lt 30 ] ; do
        tmpout=`ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no $fqdn hostname 2>&1`
        if [ "$tmpout" != "$fqdn" ] ; then
            echo -n "."
            sleep 30
            retries=`expr $retries + 1`
        else
            echo
            return 0
        fi
    done
    return 1
}


function write_common_functions() {
    local setup_script=$1

    cat >> $setup_script << EOF

yell() { echo "\$0: \$*" >&2; }
die() { yell "\$*"; exit 111; }
try() { echo "\$@"; "\$@" || die "FAILED \$*"; }


function start_logging() {
    logfile=\$1
    logpipe=\$logfile.pipe
    rm -f \$logfile \$logpipe

    mkfifo \$logpipe
    tee -a \$logfile < \$logpipe &
    logpid=\$!
    exec 3>&1 4>&2 > \$logpipe 2>&1
}

function stop_logging() {
    if [ -z "\$logpid" ]; then
        echo "Logging not yet started!"
        return 1
    fi
    exec 1>&3 3>&- 2>&4 4>&-
    wait \$logpid
    rm -f \$logpipe
    unset logpid
}

function patch_httpd_config() {
    echo "Customizing httpd.conf ..."
    cp $HTTPD_CONF $HTTPD_CONF.$TS
    sed -e 's/Options Indexes FollowSymLinks/Options FollowSymLinks/g' $HTTPD_CONF.$TS > $HTTPD_CONF
}

function patch_privsep_config() {
    factory_groups=\`id -Gn gfactory | tr " " ":"\`
    cp $PRIVSEP_CONF $PRIVSEP_CONF.$TS
    sed -e "s/valid-caller-gids = gfactory/valid-caller-gids = \$factory_groups/g" $PRIVSEP_CONF.$TS > $PRIVSEP_CONF
}

function install_rpms() {
    try yum install -y \$*
}


function install_osg() {
    yum clean all
    install_rpms $epel_release_rpm
    install_rpms $yum_rpm
    install_rpms $osg_release_rpm
    install_rpms fetch-crl osg-ca-certs httpd

    patch_httpd_config
}

function add_dn_to_condor_mapfile() {
    dn="\$1"
    user="$2"
    mapfile="/etc/condor/certs/condor_mapfile"
    tmpfile=\$mapfile.$TS
    
    echo "GSI \"\$dn\" \$2" > \$tmpfile
    cat \$mapfile >> \$tmpfile
    mv \$tmpfile \$mapfile
}

function start_services() {
     for service in \$* ; do
        /sbin/chkconfig \$service on
        /sbin/service \$service restart
     done
}

function start_common_services() {
     start_services "fetch-crl-boot fetch-crl-cron httpd condor"
}

function disable_selinux() {
    setenforce permissive
}

#disable_selinux
install_osg
EOF
}


function create_fact_install_script() {
    local setup_script=$1
    touch $setup_script
    chmod a+x $setup_script
    cat > $setup_script << EOF
#!/bin/bash

logfile=$FACT_LOG
#echo > \$logfile
#exec > >(tee -a \$logfile)
EOF

    write_common_functions $setup_script

    cat >> $setup_script << EOF

function configure_fact() {
    mkdir -p $ENTRIES_CONFIG_DIR
    cp $AUTO_INSTALL_SRC_DIR/Dev_Sites.xml $ENTRIES_CONFIG_DIR
    sed -e  s/__CONDOR_ARCH__/${condor_arch}/ -e s/__CONDOR_OS__/${condor_os}/ -e s/__CONDOR_VERSION__/${condor_version}/ $AUTO_INSTALL_SRC_DIR/Dev_Sites.xml > $ENTRIES_CONFIG_DIR/Dev_Sites.xml
    test -f /var/lib/gwms-factory/condor/$base_condor_tarball  && cd /var/lib/gwms-factory/condor/ && tar xvzf $base_condor_tarball 
    sed -e s/__CONDOR_DIR__/${base_condor_dir}/ -e s/__CONDOR_ARCH__/${condor_arch}/ -e s/__CONDOR_OS__/${condor_os}/ -e s/__CONDOR_VERSION__/${condor_version}/ $AUTO_INSTALL_SRC_DIR/Condor_Tarballs.xml > $ENTRIES_CONFIG_DIR/Condor_Tarballs.xml
    if [ -d $AUTO_INSTALL_SRC_DIR/patch/factory ]; then
        cd $AUTO_INSTALL_SRC_DIR/patch/factory
        for SRC in \$(find . -type f); do
            TGT=\$(echo \$SRC | sed -e 's/^\.//')
            echo patching \$SRC to \$TGT
            cp \$SRC \$TGT
        done
    fi

    if which systemctl > /dev/null 2>&1 ; then
        gwms-factory upgrade
    else
        /sbin/service gwms-factory upgrade
    fi
}


function verify_factory() {
    entries_enabled=\`grep "<entry " $ENTRIES_CONFIG_DIR/*.xml | grep "enabled=\\"True\\"" | wc -l\`
    entries_found=\`condor_status -subsystem glidefactory -af entryname | wc -l\`

    [ \$entries_enabled -ne \$entries_found ] && return 1
    return 0
}

uname -a
install_rpms $enable_repo glideinwms-factory${gwms_release} condor-python

patch_privsep_config

add_dn_to_condor_mapfile "$jobs_dn" testuser
add_dn_to_condor_mapfile "$vofe_dn" vofrontend_service
if [ "$vofe_dn" != "$vo_collector_dn" ]; then
    add_dn_to_condor_mapfile "$vo_collector_dn" condor
fi
add_dn_to_condor_mapfile "$fact_vm_dn" factory

configure_fact

start_common_services
sleep 10

start_services gwms-factory
sleep 20

fact_status="FAILED"
verify_factory
[ \$? -eq 0 ] && fact_status="SUCCESS"
echo "==================================="
echo "FACTORY VERIFICATION: \$fact_status"
EOF

}


function create_vofe_install_script() {
    local setup_script=$1
    touch $setup_script
    chmod a+x $setup_script
    cat > $setup_script << EOF
#!/bin/bash

logfile=$VOFE_LOG
#echo > \$logfile
#exec > >(tee -a \$logfile)
EOF

    write_common_functions $setup_script

    cat >> $setup_script << EOF

function setup_testuser() {
    user=testuser
    user_home=/var/lib/\$user
    groupadd \$user
    adduser -d \$user_home -g \$user \$user
    id \$user
    if [ "$jobs_proxy" = "" ]; then
        cp /tmp/frontend_proxy /tmp/grid_proxy
    fi
    chown \$user.\$user /tmp/grid_proxy 
    cp -r $AUTO_INSTALL_SRC_DIR/testjobs \$user_home
    chown -R \$user.\$user \$user_home
}

function configure_vofe() {
    sed -e "s|__WMSCOLLECTOR_FQDN__|$fact_fqdn|g" \
        -e "s|__VOCOLLECTOR_FQDN__|$vofe_fqdn|g" \
        -e "s|__WMSCOLLECTOR_DN__|$wms_collector_dn|g" \
        -e "s|__VOCOLLECTOR_DN__|$vo_collector_dn|g" \
        -e "s|__VOFE_DN__|$vofe_dn|g" \
        $AUTO_INSTALL_SRC_DIR/frontend-template-rpm.xml > /etc/gwms-frontend/frontend.xml

    if [ "$vofe_proxy" = "" ]; then
        grid-proxy-init -valid 48:0 -cert /etc/grid-security/hostcert.pem -key /etc/grid-security/hostkey.pem -out /tmp/frontend_proxy
        echo 00 \* \* \* \*   /usr/bin/grid-proxy-init -valid 48:0 -cert /etc/grid-security/hostcert.pem -key /etc/grid-security/hostkey.pem -out /tmp/host_proxy \; /bin/cp /tmp/host_proxy /tmp/frontend_proxy \; /bin/cp /tmp/host_proxy /tmp/vo_proxy \;/bin/cp /tmp/host_proxy /tmp/grid_proxy | crontab -
    fi
    chown frontend:frontend /tmp/frontend_proxy
    cp /tmp/frontend_proxy /tmp/vo_proxy
    chown frontend:frontend /tmp/vo_proxy
    if [ -d $AUTO_INSTALL_SRC_DIR/patch/frontend ]; then
       cd $AUTO_INSTALL_SRC_DIR/patch/frontend
       for SRC in \$(find . -type f); do
           TGT=\$(echo \$SRC | sed -e 's/^\.//')
           echo copying \$SRC to \$TGT
           cp \$SRC \$TGT
       done
    fi
    if which systemctl > /dev/null 2>&1 ; then
        gwms-frontend upgrade
    else
        /sbin/service gwms-frontend upgrade
    fi
}

function verify_vofe() {
    entries_found=\`condor_status -pool $fact_fqdn -subsystem glidefactory -af entryname | wc -l\`
    glideclients_created=\`condor_status -pool $fact_fqdn -any -constraint 'glideinmytype=="glideclient"' -af frontendname | wc -l\`

    [ \$glideclients_created -ne \$entries_found ] && return 1
    return 0
}

function submit_testjobs() {
    runuser -c "cd ~/testjobs; mkdir -p mkdir joboutput;  condor_submit ~/testjobs/testjob.glexec.jdf" testuser
}

install_rpms $enable_repo glideinwms-vofrontend${gwms_release} condor-python

add_dn_to_condor_mapfile "$jobs_dn" testuser
add_dn_to_condor_mapfile "$vofe_dn" vofrontend_service
if [ "$vofe_dn" != "$vo_collector_dn" ]; then
    add_dn_to_condor_mapfile "$vo_collector_dn" condor
fi
add_dn_to_condor_mapfile "$fact_vm_dn" factory

start_common_services
sleep 10

configure_vofe

start_services gwms-frontend
sleep 20
vofe_status="FAILED"

verify_vofe
[ \$? -eq 0 ] && vofe_status="SUCCESS"
echo "==================================="
echo "FRONTEND VERIFICATION: \$vofe_status"

if [ "\$vofe_status" = "SUCCESS" ]; then

    echo "Setting up testuser ..."
    setup_testuser
    submit_testjobs

fi
EOF

}


function create_daemon_list_script() {
    script=$1
    cat > $script << EOF
#!/bin/sh

wms_collector=\$1
user_collector=\$2

echo "========================================================================"
echo "                             WMS COLLECTOR"
echo "========================================================================"
condor_status -any -pool \$wms_collector
echo

echo "========================================================================"
echo "                             USER COLLECTOR"
echo "========================================================================"
condor_status -any -pool \$user_collector
EOF
    chmod a+x $script
}


function create_monitor_script() {
    script=$1
    cat > $script << EOF
#!/bin/sh

wms_collector=\$1
user_collector=\$2
loc=tail
lines=20

echo "========================================================================"
echo "                             USER JOB QUEUES"
echo "========================================================================"
condor_q -g -pool \$user_collector | \$loc -n\$lines

echo "========================================================================"
echo "                              GLIDEIN QUEUES"
echo "========================================================================"
condor_q -g -pool \$wms_collector | \$loc -n\$lines

echo "========================================================================"
echo "                          RESOURCES FOR USER JOBS"
echo "========================================================================"
condor_status -pool \$user_collector | \$loc -n\$lines

EOF
    chmod a+x $script
}

function monitor_progress() {
    #exe="$HOME/nfs-home/wspace/glideinWMS/tools/daemon-list.sh $HOME/nfs-home/wspace/glideinWMS/tools/monitor.sh"
    exe=/tmp/daemon-list.$TS.sh
    create_daemon_list_script $exe
    which condor_status > /dev/null 2>&1
    rc=$?
    [ $rc -eq 0 ] && [ -x $exe ] && xterm -e "watch -n5 $exe $fact_fqdn $vofe_fqdn" &
    exe=/tmp/monitor.$TS.sh
    create_monitor_script $exe
    [ $rc -eq 0 ] && [ -x $exe ] && xterm -e "watch -n5 $exe $fact_fqdn $vofe_fqdn" &
}


function print_report() {
    echo "REPORT"
}


function usage() {
    echo "Usage: `basename $0` <OPTIONS>"
    echo "  OPTIONS: "
    echo "  "
}


function read_arg_value() {
    default="$1"
    value="$2"
    if [ -z "$value" ] ; then
        echo "$value"
    else
        echo "$default"
    fi
}


function help() {
    echo "${prog} [OPTIONS]"
    echo
    echo "OPTIONS:"
    echo "--tag            GlideinWMS tag to test (Default: rpm)"
    echo "--el             Redhat version to test (Default: 6)"
    echo "--osg-version    OSG version to use (Default: 3.3)"
    echo "--osg-repo       OSG repo to use (Default: osg-development)"
    echo "--vm_template    fermicloud template (Default: CLI_DynamicIP_SLF6_HOME"
    echo "--monitor        Launch monitoring scripts in xterm"
    echo "--frontend-proxy Frontend proxy to use. Proxy from host DN is used by default"
    echo "--jobs-proxy     Proxy used to submit jobs. Proxy from host DN is used by default"
    echo "--condor-tarball Location of condor Tarball (local file or remote URL)"
    echo "--gwms-release   glideinwms rpm release (Default: latest)"
    echo "--help           Print this help message"
    echo ""
    echo "#examples"
    echo "#deploy SL6 frontend+factory version 3.2.17"
    echo "./deploy_glideinwms.sh --osg-repo osg --gwms-release 3.2.17"
    echo "#deploy SL7 latest in osg-development"
    echo "./deploy_glideinwms.sh --el 7"
}

######################################################################################
# Script starts here
######################################################################################
prog="`basename $0`"
# Following should be parameterized
tag="rpm"
el=6
# repo = release|development|testing
# ver = 3.3
osg_version="3.3"
osg_repo="osg-development"
launch_monitor="false"

# Read command line args
while [[ $# -gt 0 ]] ; do
    case "$1" in
        --tag)
            tag="${2:-rpm}"
            shift ;;
        --el)
            el="${2:-6}"
            shift ;;
        --osg-version)
            osg_version="${2:-3.3}"
            shift ;;
       --osg-repo)
            osg_repo="${2:-osg-development}"
            shift ;;
       --gwms-release)
            gwms_release="$2"
            shift ;;
        --monitor)
            launch_monitor="true"
            ;;
        --frontend-proxy)
            [ -f "$2" ] && vofe_proxy="$2"
            shift ;;
        --jobs-proxy)
            [ -f "$2" ] && jobs_proxy="$2"
            shift ;;
        --condor-tarball)
            condor_tarball="$2"
            shift ;;
        --vm_template)
            vm_template="${2:-CLI_DynamicIP_SLF6_HOME}"
            shift ;;
        --help)
            help
            exit 0;;
        *)
            echo "Invalid option: $1" 
            exit 1 ;;
    esac
    shift
done
enable_repo="--enablerepo=$osg_repo"

#yum_rpm=yum_priorities
#[ "$el" = "7" ] && yum_rpm=yum-plugin-priorities
yum_rpm=yum-plugin-priorities

[ "$el" = "7" ] &&  [ "$vm_template" = "" ] && vm_template="SLF${el}V_DynIP_Home"
[ "$el" = "6" ] &&  [ "$vm_template" = "" ] && vm_template="CLI_DynamicIP_SLF6_HOME"

[ "$gwms_release" != "" ] && [ "$(echo "$gwms_release" | grep '^-')" = "" ]  && gwms_release="-${gwms_release}"
#echo gwms_release=$gwms_release
#exit

osg_release_rpm="http://repo.grid.iu.edu/osg/$osg_version/osg-$osg_version-el$el-release-latest.rpm"
epel_release_rpm="http://dl.fedoraproject.org/pub/epel/epel-release-latest-$el.noarch.rpm"

condor_version="default"
condor_os="default"
condor_arch="default"

# Some constants
fact_vm_name="fact-el$el-$tag-test"
vofe_vm_name="vofe-el$el-$tag-test"
test -n "$condor_tarball"  && base_condor_tarball=`basename $condor_tarball` && base_condor_dir=`echo $base_condor_tarball | sed s/.tar.gz//`
test -n "$condor_tarball" && condor_version=$(echo $base_condor_tarball | sed s/condor-// | sed s/-.*//)
test -n "$condor_tarball" && condor_os=$(echo $base_condor_tarball | sed s/.*_// | sed s/-.*//)
test -n "$condor_tarball" && condor_arch=$(echo $base_condor_tarball | sed s/_${condor_os}.*// | sed s/condor-${condor_version}-//)
condor_os=$(echo $condor_os | sed s/RedHat/rhel/g)

#for some reason fermicloudui.fnal.gov is kicking me out, so 
#find one that doesnt...

SSH="ssh fcluigpvm01.fnal.gov"
$SSH exit 0
if [ $? -ne 0 ]; then
    SSH="ssh fcluigpvm02.fnal.gov"
fi

ENTRIES_CONFIG_DIR=/etc/gwms-factory/config.d
HTTPD_CONF=/etc/httpd/conf/httpd.conf
PRIVSEP_CONF=/etc/condor/privsep_config
AUTO_INSTALL_SRC_BASE="/tmp"
AUTO_INSTALL_SRC_DIR="$AUTO_INSTALL_SRC_BASE/deploy_config"
TS=`date +%s`


fact_vmid=`launch_vm $fact_vm_name $vm_template`
vofe_vmid=`launch_vm $vofe_vm_name $vm_template`

fact_fqdn=`vm_hostname $fact_vmid`
vofe_fqdn=`vm_hostname $vofe_vmid`

installed_node_list=/tmp/installed.nodes
touch $installed_node_list
echo $fact_vm_name $fact_fqdn >>  $installed_node_list
echo $vofe_vm_name $vofe_fqdn >>  $installed_node_list

fact_fqdn_status="down"
is_vm_up $fact_fqdn
[ $? -eq 0 ] && fact_fqdn_status="up"

vofe_fqdn_status="down"
is_vm_up $vofe_fqdn
[ $? -eq 0 ] && vofe_fqdn_status="up"


fact_vm_dn="`ssh root@$fact_fqdn openssl x509 -in /etc/grid-security/hostcert.pem -subject -noout | sed -e 's|subject= ||g'`"
vofe_vm_dn="`ssh root@$vofe_fqdn openssl x509 -in /etc/grid-security/hostcert.pem -subject -noout | sed -e 's|subject= ||g'`"

wms_collector_dn="$fact_vm_dn"
vo_collector_dn="$vofe_vm_dn"
if [ -z "$vofe_proxy" ]; then
    vofe_dn="$vo_collector_dn"
else
    # Extract the DN from the proxy
    subject="`openssl x509 -in $vofe_proxy -out -text -subject | sed -e 's|subject= ||g'`"
    issuer="`openssl x509 -in $vofe_proxy -out -text -issuer | sed -e 's|issuer= ||g'`"
    case "$subject" in
        *"$issuer"*) vofe_dn="$issuer" ;;
        *) voef_dn="$subject" ;;
    esac
fi

if [ -z "$jobs_proxy" ]; then
    jobs_dn="$vofe_dn"
else
    # Extract the DN from the proxy
    subject="`openssl x509 -in $jobs_proxy -out -text -subject | sed -e 's|subject= ||g'`"
    issuer="`openssl x509 -in $jobs_proxy -out -text -issuer | sed -e 's|issuer= ||g'`"
    case "$subject" in
        *"$issuer"*) jobs_dn="$issuer" ;;
        *) jobs_dn="$subject" ;;
    esac
fi


FACT_LOG=/tmp/fact_install.log
VOFE_LOG=/tmp/vofe_install.log
JOBS_LOG=/tmp/jobs_install.log

echo "==============================================================================="
echo "Deployment Options"
echo "------------------"
echo "prog        : $prog"
echo "tag         : $tag"
echo "el          : $el"
echo "osg_version : $osg_version"
echo "osg_repo    : $osg_repo"
echo "monitor     : $launch_monitor"
echo
echo "Factory Information"
echo "-------------------"
echo "fact_vm     : $fact_vm_name"
echo "vm_template : $vm_template"
echo "fact_vmid   : $fact_vmid"
echo "fact_fqdn   : $fact_fqdn"
echo "fact_dn     : $fact_vm_dn"
echo "wms_pool_dn : $wms_collector_dn"
echo
echo "Frontend Information"
echo "--------------------"
echo "vofe_vm     : $vofe_vm_name"
echo "vm_template : $vm_template"
echo "vofe_vmid   : $vofe_vmid"
echo "vofe_fqdn   : $vofe_fqdn"
echo "vofe_dn     : $vofe_dn"
echo "vofe_proxy  : $vofe_proxy"
echo "vo_pool_dn  : $vo_collector_dn"
echo "jobs_proxy  : $jobs_proxy"
echo "jobs_dn     : $jobs_dn"
echo "==============================================================================="
echo

# Create installation scripts
fact_install_script="/tmp/fact_install.$TS.sh"
vofe_install_script="/tmp/vofe_install.$TS.sh"


create_fact_install_script $fact_install_script
create_vofe_install_script $vofe_install_script

deploy_config_dir=`dirname $0`/deploy_config

echo "-------------------------- Factory Deployment Starting ------------------------"
scp -rC $deploy_config_dir root@$fact_fqdn:$AUTO_INSTALL_SRC_BASE
# Remotely run factory installation scripts
scp $fact_install_script root@$fact_fqdn:/tmp/fact_install.sh
if [ -n "$condor_tarball" ]; then
    ssh root@$fact_fqdn 'mkdir -p /var/lib/gwms-factory/condor/' 
    if [ -f "$condor_tarball" ]; then
        scp $condor_tarball root@$fact_fqdn:/var/lib/gwms-factory/condor/
        if [ $? -ne 0 ]; then
            echo "failed to copy $condor_tarball to $fact_fqdn, aborting installation"
            exit 1
        fi
    else
        cmd="/usr/bin/wget $condor_tarball -O /var/lib/gwms-factory/condor/$base_condor_tarball"
        echo wget command: ssh root@$fact_fqdn $cmd
        ssh root@$fact_fqdn "$cmd"
        if [ $? -ne 0 ]; then
            echo "failed to load condor_tarball $condor_tarball to $fact_fqdn, check URL"
            echo "aborting installation"
            exit 1
        fi
    fi
else
    echo "make sure rpm installation of condor on factory works with start_condor.sh see issue 15924"
fi
#test -f "$condor_tarball"  && ssh root@$fact_fqdn 'mkdir -p /var/lib/gwms-factory/condor/' && scp $condor_tarball root@$fact_fqdn:/var/lib/gwms-factory/condor/
echo "ssh root@$fact_fqdn /tmp/fact_install.sh " > /tmp/ssh_fact.$TS.sh
chmod +x /tmp/ssh_fact.$TS.sh
bash /tmp/ssh_fact.$TS.sh 2>&1 | tee -a  $FACT_LOG.$TS 
fact_install_status="fail"
vofe_install_status="wait"

#echo "Retrieving factory installation logs to $FACT_LOG.$TS"
#scp root@$fact_fqdn:$FACT_LOG $FACT_LOG.$TS
#echo $FACT_LOG > $FACT_LOG.$TS

echo "-------------------------- Factory Deployment Completed -----------------------"

# If factory verification failed, there is no point continuing with frontend
if [ "`tail -1 $FACT_LOG.$TS`" != "FACTORY VERIFICATION: SUCCESS" ] ; then
    echo "================================================================================"
    echo "Factory : VM_ID=$fact_vmid FQDN=$fact_fqdn VM_STATUS=$fact_fqdn_status VERIFICATION=$fact_install_status"
    echo "Frontend: VM_ID=$vofe_vmid FQDN=$vofe_fqdn VM_STATUS=$vofe_fqdn_status VERIFICATION=$vofe_install_status"
    echo "================================================================================"
    exit 1
fi

[ "$launch_monitor" = "true" ] && monitor_progress

fact_install_status="pass"
vofe_install_status="fail"

echo "-------------------------- Frontend Deployment Starting -----------------------"
# Stage necessart files and remotely run frontend installation script
scp -rC $deploy_config_dir root@$vofe_fqdn:$AUTO_INSTALL_SRC_BASE
scp $vofe_install_script root@$vofe_fqdn:/tmp/vofe_install.sh
[ "$vofe_proxy" != "" ] && scp $vofe_proxy root@$vofe_fqdn:/tmp/frontend_proxy
[ "$jobs_proxy" != "" ] && scp $jobs_proxy root@$vofe_fqdn:/tmp/grid_proxy

echo "ssh root@$vofe_fqdn /tmp/vofe_install.sh" > /tmp/ssh_frontend.$TS.sh
chmod +x /tmp/ssh_frontend.$TS.sh
bash /tmp/ssh_frontend.$TS.sh 2>&1 | tee -a  $VOFE_LOG.$TS 

echo "-------------------------- Frontend Deployment Completed ----------------------"
frontend_status=$(grep 'FRONTEND VERIFICATION: SUCCESS' $VOFE_LOG.$TS)

if [ "$frontend_status" = "FRONTEND VERIFICATION: SUCCESS"  ] ; then
    vofe_install_status="pass"
fi
mkdir -p $SPOOF/tmp
echo "export fact_fqdn=$fact_fqdn " > $SPOOF/tmp/setnodes.$TS.sh
echo "export vofe_fqdn=$vofe_fqdn " >> $SPOOF/tmp/setnodes.$TS.sh


echo "================================================================================"
echo "Factory : VM_ID=$fact_vmid FQDN=$fact_fqdn VM_STATUS=$fact_fqdn_status VERIFICATION=$fact_install_status"
echo "Frontend: VM_ID=$vofe_vmid FQDN=$vofe_fqdn VM_STATUS=$vofe_fqdn_status VERIFICATION=$vofe_install_status"
echo "================================================================================"
