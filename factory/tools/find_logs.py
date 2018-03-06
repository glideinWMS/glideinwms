#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Find the logs for a certain date
#
# Usage: find_logs.py <factory> YY/MM/DD [hh:mm:ss]
#

from __future__ import print_function
import sys
import os
import os.path
import time

STARTUP_DIR=sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))

from glideinwms.factory.tools.lib import gWftArgsHelper, gWftLogParser
from glideinwms.factory import glideFactoryConfig

USAGE="Usage: find_logs.py <factory> YY/MM/DD [hh:mm:ss]"

# return a GlideinDescript with
# factory_dir, date_arr and time_arr
def parse_args():
    if len(sys.argv)<3:
        raise ValueError("Not enough arguments!")

    factory_dir=sys.argv[1]
    try:
        glideFactoryConfig.factoryConfig.glidein_descript_file=os.path.join(factory_dir, glideFactoryConfig.factoryConfig.glidein_descript_file)
        glideinDescript=glideFactoryConfig.GlideinDescript()
    except:
        raise ValueError("%s is not a factory!"%factory_dir)

    glideinDescript.factory_dir=factory_dir
    glideinDescript.date_arr=gWftArgsHelper.parse_date(sys.argv[2])
    if len(sys.argv)>=4:
        glideinDescript.time_arr=gWftArgsHelper.parse_time(sys.argv[3])
    else:
        glideinDescript.time_arr=(0, 0, 0)

    return glideinDescript

def main():
    try:
        glideinDescript=parse_args()
    except ValueError as e:
        sys.stderr.write("%s\n\n%s\n"%(e, USAGE))
        sys.exit(1)
    entries=glideinDescript.data['Entries'].split(',')

    log_list=gWftLogParser.get_glidein_logs(glideinDescript.factory_dir, entries, glideinDescript.date_arr, glideinDescript.time_arr, "err")
    for fname in log_list:
        print(fname)
        


if __name__ == '__main__':
    main()
 
