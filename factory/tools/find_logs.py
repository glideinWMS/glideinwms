#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Find the logs for a certain date.

Usage:
    find_logs.py <factory> YY/MM/DD [hh:mm:ss]
"""


import os
import os.path
import sys

from glideinwms.factory import glideFactoryConfig
from glideinwms.factory.tools.lib import gWftArgsHelper, gWftLogParser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))


USAGE = "Usage: find_logs.py <factory> YY/MM/DD [hh:mm:ss]"


# return a GlideinDescript with
# factory_dir, date_arr and time_arr
def parse_args():
    """Parse command-line arguments and return a configured GlideinDescript object.

    This function expects at least two command-line arguments:
    the factory directory and a date in the format YY/MM/DD. An optional time in
    the format hh:mm:ss may be provided. If the time is not provided, it defaults to (0, 0, 0).

    Raises:
        ValueError: If there are not enough arguments or if the provided factory directory is invalid.

    Returns:
        glideFactoryConfig.GlideinDescript: An instance of GlideinDescript with its factory_dir, date_arr, and time_arr attributes set.
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
    """Retrieve and print log file paths for the specified Factory and date.

    This function parses command-line arguments to configure a glideFactoryConfig.GlideinDescript object,
    retrieves the list of log files corresponding to the specified entries, date, and time,
    and then prints each log file path.

    If argument parsing fails, the usage message is printed and the program exits with code 1.
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
        print(fname)


if __name__ == "__main__":
    main()
