#!/bin/sh
CONDOR_LOCATION=~gcondor/master/usersubmit
#CONDOR_LOCATION=/home/testuserparag/v2.3.2/glidecondor
#CONDOR_LOCATION=/home/frontendparag/v2.2.3/glidecondor
#CONDOR_LOCATION=/home/frontendparag/glidecondor
#CONDOR_LOCATION=/home/condorparag/glidecondor

export X509_CERT_DIR=/etc/grid-security/certificates
export X509_USER_PROXY=~/security/grid_proxy

source $CONDOR_LOCATION/condor.sh
umask 0022
