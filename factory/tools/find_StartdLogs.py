#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Print out the StartdLogs for a certain date.

Usage:
    find_StartdLogs.py <factory> YY/MM/DD [hh:mm:ss]
"""

import os
import os.path
import sys

from glideinwms.factory import glideFactoryConfig
from glideinwms.factory.tools.lib import gWftArgsHelper, gWftLogParser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))


USAGE = "Usage: find_StartdLogs.py <factory> YY/MM/DD [hh:mm:ss]"


# return a GlideinDescript with
# factory_dir, date_arr and time_arr
def parse_args():
    """Parse command-line arguments to configure a GlideinDescript object.

    Expects at least two command-line arguments: the factory directory and a date
    in the format YY/MM/DD. Optionally, a time in the format hh:mm:ss can be provided.
    If the time is not provided, it defaults to (0, 0, 0).

    Raises:
        ValueError: If fewer than 3 command-line arguments are provided.
        ValueError: If the specified factory directory is not valid.

    Returns:
        glideFactoryConfig.GlideinDescript: A configured GlideinDescript object with the
            attributes 'factory_dir', 'date_arr', and 'time_arr' set.
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
    """Main function to print out the StartdLogs for a given factory and date.

    This function parses command-line arguments to create a glideFactoryConfig.GlideinDescript object,
    retrieves the list of log file paths using the provided factory directory,
    date, and optional time, and then prints each log file path followed by a separator
    and the contents of the Condor log identified by "CondorLog".

    If argument parsing fails, the usage message is printed to stderr and the process exits
    with a non-zero status code.
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
        sys.stdout.write("%s\n" % gWftLogParser.get_condor_log(fname, "CondorLog"))


if __name__ == "__main__":
    main()
