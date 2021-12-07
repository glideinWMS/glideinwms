#!/bin/sh

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

CONDOR_LOCATION=/opt/glidecondor
export CONDOR_CONFIG=$CONDOR_LOCATION/etc/condor_config
source $CONDOR_LOCATION/new_schedd_setup.sh $1
# add whatever other config you need
$CONDOR_LOCATION/sbin/condor_master
