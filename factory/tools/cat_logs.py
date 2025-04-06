#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Print out the logs for a certain date

 Usage: cat_logs.py <factory> YY/MM/DD [hh:mm:ss]
"""

import os
import os.path
import sys

from glideinwms.factory import glideFactoryConfig
from glideinwms.factory.tools.lib import gWftArgsHelper, gWftLogParser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))

USAGE = "Usage: cat_logs.py <factory> YY/MM/DD [hh:mm:ss]"


# return a GlideinDescript with
# factory_dir, date_arr and time_arr
def parse_args():
    """Parse command-line arguments and return a GlideinDescript object.

    This function expects at least two command-line arguments: the factory directory and a date string in the format YY/MM/DD.
    Optionally, a time string in the format hh:mm:ss can be provided. It updates the factory configuration file path and
    creates a GlideinDescript object with attributes for factory_dir, date_arr, and time_arr.

    Raises:
        ValueError: If not enough arguments are provided or if the factory directory is invalid.

    Returns:
        glideFactoryConfig.GlideinDescript: The configured GlideinDescript object.
    """
    if len(sys.argv) < 3:
        raise ValueError("Not enough arguments!")

    factory_dir = sys.argv[1]
    try:
        glideFactoryConfig.factoryConfig.glidein_descript_file = os.path.join(
            factory_dir, glideFactoryConfig.factoryConfig.glidein_descript_file
        )
        glideinDescript = glideFactoryConfig.GlideinDescript()
    except Exception:
        raise ValueError("%s is not a factory!" % factory_dir)

    glideinDescript.factory_dir = factory_dir
    glideinDescript.date_arr = gWftArgsHelper.parse_date(sys.argv[2])
    if len(sys.argv) >= 4:
        glideinDescript.time_arr = gWftArgsHelper.parse_time(sys.argv[3])
    else:
        glideinDescript.time_arr = (0, 0, 0)

    return glideinDescript


def main():
    """Main function for printing glidein logs for a specific date.

    This function calls `parse_args()` to obtain a GlideinDescript object, retrieves the list of entries from it,
    and then uses gWftLogParser.get_glidein_logs() to obtain a list of log file paths with extension "err".
    Finally, it prints the path and content of each log file to stdout.
    """
    try:
        glideinDescript = parse_args()
    except ValueError as e:
        sys.stderr.write(f"{e}\n\n{USAGE}\n")
        sys.exit(1)
    entries = glideinDescript.data["Entries"].split(",")

    log_list = gWftLogParser.get_glidein_logs(
        glideinDescript.factory_dir, entries, glideinDescript.date_arr, glideinDescript.time_arr, "err"
    )
    for fname in log_list:
        sys.stdout.write("%s\n" % fname)
        sys.stdout.write("===========================================================\n")
        with open(fname) as fd:
            sys.stdout.write(fd.read())
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
