#!/bin/bash

usage(){
    echo ""
    echo "$0: a utility that does the following: "
    echo "1) install a glideinwms factory and fronted on fermicloud nodes"
    echo "2) submit jobs to frontend, wait for glideins to start "
    echo "3) wait for glideins to connect to frontend"
    echo "4) wait for user jobs to start running in glideins "
    echo "5) optionally, "
    echo "5a)   kill all glideins and user jobs,"
    echo "5b)   upgrade factory/frontend, "
    echo "5c)   repeat steps 2-4  for upgrade"
    echo "6) generate a report of condor and python errors for factory and frontend"
    echo ""
    echo "usage: $0 config_file    reads config_file and performs above steps"
    echo "       $0 --help         print this message and exit"
    echo
    echo "to run all the tests, do the following:"
    echo 'for CFG in $(ls *.cfg); do echo $CFG; ./smoke_test.sh ./$CFG | tee $CFG.out ; done '
    echo
    exit 0
}



yell() { echo "$0: $*" >&2; }
die() { yell "$*"; exit 111; }
try() { echo "$@"; "$@" || die "FAILED $*"; }

main() {
    if [ $# -ne 1 ] ;then
        usage
    fi

    if [ "$1" = "--help" ] ;then
        usage
    fi
    if [ "$X509_USER_PROXY" = "" ]; then
        kx509
        export X509_USER_PROXY=/tmp/krb5cc_`id -u`
    fi
    try source $1
    export PERFORM_UPGRADE=$(echo $PERFORM_UPGRADE | tr 'a-z' 'A-Z')
    echo DEPLOY_COMMAND is $DEPLOY_COMMAND
    echo PERFORM_UPGRADE is $PERFORM_UPGRADE
    try $DEPLOY_COMMAND
    cd deploy_utilities
    try ./monitor_job_progress.sh
    if [ "$PERFORM_UPGRADE" = "TRUE" ]; then
        try ./factory.clear_jobs.sh
        try ./frontend.clear_jobs.sh
        try ./factory.perform_upgrade.sh
        try ./frontend.perform_upgrade.sh
        try ./frontend.submit_jobs.sh
        try ./monitor_job_progress.sh
    fi
    try ./report.sh
    cd -
}


main "$@"
