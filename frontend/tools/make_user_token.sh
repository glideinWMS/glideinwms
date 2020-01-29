#!/bin/bash -x
ID=$1
if [ "$ID" = "" ]; then
	echo usage $0 uid
	echo creates a condor token for user \$uid
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
