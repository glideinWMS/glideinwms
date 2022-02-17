#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Check if a glideinFactory is running
#
# Arguments:
#   $1 = glidein submit_dir (i.e. factory dir)
#
# Author:
#   Igor Sfiligoi Jul 9th 2008
#


import sys

from glideinwms.factory import glideFactoryPidLib

try:
    startup_dir = sys.argv[1]
    factory_pid = glideFactoryPidLib.get_factory_pid(startup_dir)
except:
    print("Not running")
    sys.exit(1)

print("Running")
sys.exit(0)
