#!/bin/bash
# Version : $Rev: 45328 $
# root's public keys



PUB_KEY_URI=http://169.254.169.254/1.0/meta-data/public-keys/0/openssh-key
PUB_KEY_FROM_HTTP=/tmp/openssh_id.pub
PUB_KEY_FROM_EPHEMERAL=/mnt/openssh_id.pub
ROOT_AUTHORIZED_KEYS=/root/.ssh/authorized_keys



# We need somewhere to put the keys.
if [ ! -d /root/.ssh ] ; then
    mkdir -p /root/.ssh
    chmod 700 /root/.ssh
fi

# Fetch credentials...
echo "-----CREDENTIALS RETRIEVAL-----"|logger -s -t "ec2"

# First try http
echo "Attempting to retrieve public key from [$PUB_KEY_URI]"|logger -t "ec2" -s
curl --retry 3 --retry-delay 5 --silent --fail -o $PUB_KEY_FROM_HTTP $PUB_KEY_URI
if [ $? -eq 0 -a -e $PUB_KEY_FROM_HTTP ] ; then
    if ! grep -q -f $PUB_KEY_FROM_HTTP $ROOT_AUTHORIZED_KEYS
    then
        cat $PUB_KEY_FROM_HTTP >> $ROOT_AUTHORIZED_KEYS
        echo "New key added to authrozied keys file from parameters"|logger -t "ec2" -s
    else
        echo "Already have your key"|logger -t "ec2" -s
    fi
    rm -f $PUB_KEY_FROM_HTTP

elif [ -e $PUB_KEY_FROM_EPHEMERAL ] ; then
    echo "Meta-data fetch failed, trying from legacy ephemeral store location [$PUB_KEY_FROM_EPHEMERAL]"|logger -t "ec2" -s
    # Try back to ephemeral store if http failed.
    # NOTE: This usage is deprecated and will be removed in the future
    if ! grep -q -f $PUB_KEY_FROM_EPHEMERAL $ROOT_AUTHORIZED_KEYS
    then
        cat $PUB_KEY_FROM_EPHEMERAL >> $ROOT_AUTHORIZED_KEYS
        echo "New key added to authrozied keys file from ephemeral store"|logger -t "ec2" -s
    fi
    chmod 600 $PUB_KEY_FROM_EPHEMERAL

fi

if [ ! -f $ROOT_AUTHORIZED_KEYS ]
then
    echo "*!*!*! FATAL ERROR *!*!*! No able to find authorized_keys file [$ROOT_AUTHORIZED_KEYS]"|logger -t "ec2" -s
else
    echo "Setting permissions on $ROOT_AUTHORIZED_KEYS to 0600"|logger -t "ec2" -s
    chmod 600 $ROOT_AUTHORIZED_KEYS
fi
