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
    echo ""
    echo "usage: $0 config_file    reads config_file and performs above steps"
    echo "       $0 --help         print this message and exit"
    echo
    echo "sample config files in this directory are named osg_version-linux_major.config "
    echo "example 3.4-el7.config"
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

    source $1

    cmd="./deploy_glideinwms.sh"

    if [ "$OS_VERSION" != "" ]; then
        cmd="$cmd --el $OS_VERSION"
    fi

    if [ "$CONDOR_TARBALL" != "" ]; then
        cmd="$cmd --condor-tarball $CONDOR_TARBALL"
    fi

    if [ "$OSG_VERSION" != "" ]; then
        cmd="$cmd --osg-version $OSG_VERSION"
    fi

    if [ "$JOBS_PROXY" != "" ]; then
        cmd="$cmd --jobs-proxy $JOBS_PROXY"
    fi

    if [ "$FRONTEND_PROXY" != "" ]; then
        cmd="$cmd --frontend-proxy $FRONTEND_PROXY"
        if [ "$REGENERATE_FRONTEND_PROXY" != "" ]; then
            opts="-noregen -rfc -ignorewarn -valid 72:00 -bits 1024 "
            voms="fermilab:/fermilab/Role=Analysis"
            voms-proxy-init $opts -voms $voms -out $FRONTEND_PROXY
        fi
    fi

    if [ "$GWMS_RELEASE" != "" ]; then
        cmd="$cmd --gwms-release $GWMS_RELEASE"
    fi
    try $cmd
    cd deploy_utilities
    try ./monitor_job_progress.sh
    if [ "$PERFORM_UPGRADE" != "" ]; then
        try ./factory.clear_jobs.sh
        try ./frontend.clear_jobs.sh
        try ./factory.perform_upgrade.sh
        try ./frontend.perform_upgrade.sh
        try ./frontend.submit_jobs.sh
        try ./monitor_job_progress.sh
    fi
    ./factory.condor_errs.sh > /tmp/$COMBO_VERSION.factory.condor.errs
    ./frontend.condor_errs.sh  > /tmp/$COMBO_VERSION.frontend.condor.errs
    ./factory.exceptions.sh  > /tmp/$COMBO_VERSION.factory.exceptions
    ./frontend.exceptions.sh  > /tmp/$COMBO_VERSION.frontend.exceptions
}


main "$@"
