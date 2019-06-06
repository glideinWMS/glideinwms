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
    # Wait for 15 min trying ssh into the machine every 30 sec
    # When ssh is successfull, machine is usable
    local retries=0
    echo "Waiting for $fqdn to boot up "
    while [ $retries -lt 30 ] ; do
        tmpout=$(ssh -t -o StrictHostKeyChecking=no root@$fqdn hostname 2>/dev/null)
        if [ $? -ne 0  ] ; then
            echo -n "."
            sleep 10
            retries=$(expr $retries + 1)
        else
            return 0
        fi
    done
    return 1
}



function usage() {
    echo "Usage: `basename $0` <OPTIONS>"
    echo "  OPTIONS: "
    echo "  "
}




function help() {
    echo "$prog [OPTIONS]"
    echo
    echo "OPTIONS:"
    echo "--el             Redhat version to test (Default: 6)"
    echo "--vm_template    fermicloud template (Default: CLI_DynamicIP_SLF6_HOME"
    echo "--vm_name        name of vm (Default: $(whoami)-CLI_DynamicIP_SLF6_HOME"
    echo "--help           Print this help message"
}

######################################################################################
# Script starts here
######################################################################################
prog="`basename $0`"
# Following should be parameterized
el=6
# repo = release|development|testing
# ver = 3.3

# Read command line args
while [[ $# -gt 0 ]] ; do
    case "$1" in
        --el)
            el="${2:-6}"
            shift ;;
        --vm_template)
            vm_template="${2:-CLI_DynamicIP_SLF6_HOME}"
            shift ;;
        --vm_name)
            vm_name="${2}"
            shift ;;
        --help)
            help
            exit 0;;
        *)
            echo "Invalid option: $1" &2
            exit 1 ;;
    esac
    shift
done


[ "$el" = "7" ] &&  [ "$vm_template" = "" ] && vm_template="SLF${el}V_DynIP_Home"
[ "$el" = "6" ] &&  [ "$vm_template" = "" ] && vm_template="CLI_DynamicIP_SLF6Vanilla"



#for some reason this one is kicking me out, so do this...
SSH="ssh fermicloudui.fnal.gov"
$SSH exit 0
if [ $? -ne 0 ]; then
    SSH="ssh fcluigpvm02.fnal.gov"
fi

AUTO_INSTALL_SRC_DIR="$AUTO_INSTALL_SRC_BASE/deploy_config"
TS=`date +%s`

[ "$vm_name" = "" ] && vm_name="$(whoami)-$vm_template"

vmid=`launch_vm $vm_name $vm_template`

fqdn=`vm_hostname $vmid`

touch /tmp/installed.nodes
echo $vm_name $fqdn >> /tmp/installed.nodes

fqdn_status="down"
#if [ -z `ssh-keygen -F $fqdn` ]; then
#      ssh-keyscan -H $fqdn  >> ~/.ssh/known_hosts
#fi


is_vm_up $fqdn
[ $? -eq 0 ] && fqdn_status="up"


echo "VM Information"
echo "-------------------"
echo "vm_name     : $vm_name"
echo "vm_template : $vm_template"
echo "vmid   : $vmid"
echo "fqdn   : $fqdn"
echo "dn     : $vm_dn"
echo "status      : $fqdn_status"

export vm_name vm_template vmid fqdn dn status

