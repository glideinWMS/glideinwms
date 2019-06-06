#!/bin/bash

# Tool to automate the GlideinWMS rpm deployment and testing
# rewritten to use puppet as much as possible
# Author: Dennis Box
# 
#TODO function patch_httpd_config ,disable_selinux,  
#TODO yum -y --enablerepo osg-development install glideinwms-switchboard


function usage() {
    echo "Usage: `basename $0` <OPTIONS>"
    echo "  OPTIONS: "
    echo "  "
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


#default values prior to readeing command line
tag="rpm"
el=6
osg_version="3.4"
osg_repo="osg-development"
launch_monitor="false"

# Read command line args
while [[ $# -gt 0 ]] ; do
    case "$1" in
        --tag) #rpm only supported tag
            tag="${2:-rpm}"
            shift ;;
        --el) #supported: 6 or 7
            el="${2:-6}"
            shift ;;
        --osg-version)# supported: 3.3 or 3.4
            osg_version="${2:-3.3}"
            shift ;;
       --osg-repo) # supported: see /etc/yum.repos.d osg, osg-development, osg-prerelease, etc
            osg_repo="${2:-osg-development}"
            shift ;;
       --gwms-release) # if specified, must match something from that --osg-repo
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
        --condor-tarball) #can either be /path/to/file or url:
            if [ "$condor_tarball" = "" ] ; then
               condor_tarball="$2"
            else
               condor_tarball2="$2"
            fi
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

yum_rpm=yum-plugin-priorities

[ "$el" = "7" ] &&  [ "$vm_template" = "" ] && vm_template="SLF${el}V_DynIP_Home"
[ "$el" = "6" ] &&  [ "$vm_template" = "" ] && vm_template="CLI_DynamicIP_SLF6_HOME"

[ "$gwms_release" != "" ] && [ "$(echo "$gwms_release" | grep '^-')" = "" ]  && gwms_release="-${gwms_release}"



# Some constants
fact_vm_name="fact-el$el-$tag-test"
vofe_vm_name="vofe-el$el-$tag-test"



TS=`date +%s`


#spin up a factory on fermicloud
source ./create_fermicloud_vm2.sh --el $el --vm_template $vm_template --vm_name $fact_vm_name 
fact_fqdn=$fqdn
fact_vmid=$vmid

#spin up a frontend
source ./create_fermicloud_vm2.sh --el $el --vm_template $vm_template --vm_name $vofe_vm_name 
vofe_fqdn=$fqdn
vofe_vmid=$vmid

installed_node_list=/tmp/installed.nodes
touch $installed_node_list
echo $fact_vm_name $fact_fqdn >>  $installed_node_list
echo $vofe_vm_name $vofe_fqdn >>  $installed_node_list
echo "export fact_fqdn=${fact_fqdn} " > "${SPOOF}/tmp/setnodes.${TS}.sh"
echo "export vofe_fqdn=${vofe_fqdn} " >> "${SPOOF}/tmp/setnodes.${TS}.sh"



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
        *) vofe_dn="$subject" ;;
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



#puppet apply osg_client to factory, frontend
./install_module.sh $fact_fqdn osg_client
./install_module.sh $vofe_fqdn osg_client

if [ !  -z "$vofe_proxy" ]; then
    scp $vofe_proxy root@$vofe_fqdn:/tmp/frontend_proxy
    scp $vofe_proxy root@$vofe_fqdn:/tmp/vo_proxy
    scp $vofe_proxy root@$vofe_fqdn:/tmp/grid_proxy
fi

#puppet apply factory and frontend modules

./install_module.sh $fact_fqdn factory  "fact_fqdn => '$fact_fqdn', vofe_fqdn => '$vofe_fqdn', vofe_dn => '$vofe_dn'"
./install_module.sh $vofe_fqdn vofrontend  "fact_fqdn => '$fact_fqdn', vofe_fqdn => '$vofe_fqdn', vofe_dn =>'$vofe_dn'"


