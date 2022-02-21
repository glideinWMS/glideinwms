#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   This tool displays the status of the glideinWMS pool
#   in a text format
#
# Arguments:
#   [-pool collector_node] Entries|Sites|Gatekeepers

import os.path
import sys

# import glideFactoryInterface
from glideinwms.frontend import glideinFrontendInterface

sys.path.append(os.path.join(sys.path[0], "../.."))


pool_name = None
factory_name = None
remove_condor_stats = True
remove_internals = True
txt_type = "Entries"

# parse arguments
alen = len(sys.argv)
i = 1
while i < alen:
    ael = sys.argv[i]
    if ael == "-pool":
        i = i + 1
        pool_name = sys.argv[i]
    elif ael == "-factory":
        i = i + 1
        factory_name = sys.argv[i]
    elif ael in ("Entries", "Sites", "Gatekeepers"):
        txt_type = ael
    elif ael == "-help":
        print("Usage:")
        print("wmsTxtView.py [-pool <node>[:<port>]] [-factory <factory>] [Entries|Sites|Gatekeepers] [-help]")
        sys.exit(1)
    else:
        raise RuntimeError("Unknown option '%s', try -help" % ael)
    i = i + 1

# get data
factory_constraints = None
if factory_name is not None:
    farr = factory_name.split("@")
    if len(farr) == 1:
        # just the generic factory name
        factory_constraints = 'FactoryName=?="%s"' % factory_name
    elif len(farr) == 2:
        factory_constraints = f'(FactoryName=?="{farr[1]}")&&(GlideinName=?="{farr[0]}")'
    elif len(farr) == 3:
        factory_constraints = '(FactoryName=?="{}")&&(GlideinName=?="{}")&&(EntryName=?="{}")'.format(
            farr[2],
            farr[1],
            farr[0],
        )
    else:
        raise RuntimeError("Invalid factory name; more than 2 @'s found")

glideins_obj = glideinFrontendInterface.findGlideins(pool_name, None, None, factory_constraints)

# Get a dictionary of
#  RequestedIdle
#  Idle
#  Running
txt_data = {}

# extract data
glideins = list(glideins_obj.keys())
for glidein in glideins:
    glidein_el = glideins_obj[glidein]

    if txt_type == "Entries":
        key = glidein
    elif txt_type == "Sites":
        key = glidein_el["attrs"]["GLIDEIN_Site"]
    elif txt_type == "Gatekeepers":
        key = glidein_el["attrs"]["GLIDEIN_Gatekeeper"]
    else:
        raise RuntimeError("Unknwon type '%s'" % txt_type)

    if key in txt_data:
        key_el = txt_data[key]
    else:
        key_el = {"RequestedIdle": 0, "Idle": 0, "Running": 0, "MaxGlideins": 0}
        txt_data[key] = key_el

    if "monitor" in glidein_el:
        if "TotalRequestedIdle" in glidein_el["monitor"]:
            key_el["RequestedIdle"] += glidein_el["monitor"]["TotalRequestedIdle"]
            key_el["Idle"] += glidein_el["monitor"]["TotalStatusIdle"]
            key_el["Running"] += glidein_el["monitor"]["TotalStatusRunning"]
            key_el["MaxGlideins"] += glidein_el["monitor"]["TotalRequestedMaxGlideins"]

# print data
txt_keys = sorted(txt_data.keys())

print("%s ReqIdle  Idle   Running  MaxGlideins" % "Entry".ljust(48))
print("================================================-=======-=======-=======-=======")
for key in txt_keys:
    key_el = txt_data[key]
    print(
        "%s %7i %7i %7i %7i"
        % (key.ljust(48), key_el["RequestedIdle"], key_el["Idle"], key_el["Running"], key_el["MaxGlideins"])
    )
