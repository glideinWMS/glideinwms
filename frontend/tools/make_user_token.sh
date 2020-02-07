#!/bin/bash -x
# file: make_user_token.sh
# usage: make_user_token.sh (user)
# project: glideinwms
# author: Dennis Box, dbox@fnal.gov
#
ID=$1
if [ "$ID" = "root" ]; then
	echo usage $0 uid
	echo creates a condor token for user \$uid
    echo must be run as root
	exit 0
fi
HM=$(getent passwd ${ID} | awk 'BEGIN { FS = ":" } ; { print $6 }')
if [ "${HM}" = "" ]; then
    echo "user ${ID} seems not to have a home area. exiting"
    exit 1
fi
TD="${HM}/.condor/tokens.d"
TOKEN="${ID}.${HOSTNAME}.token"
mkdir -p "${TD}"
condor_token_create -identity "${ID}@${HOSTNAME}" -token ${TOKEN}
/bin/mv "$HOME/.condor/tokens.d/${TOKEN}" "${TD}"
chown -R "${ID}" "${HM}/.condor"
