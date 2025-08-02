#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Print out the XML Result for a glidein output file.

Usage:
    cat_XMLResult.py [-raw] [-forcemulti] <logname>+
    If -raw is present, do not wrap multiple XMLs into a ResultSet.
    If -forcemulti is present, make it a ResultSet even if only one file is present.
"""

import os.path
import sys

from glideinwms.factory.tools.lib import gWftLogParser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))

USAGE = "Usage: cat_XMLResult.py -h|[-raw] [-forcemulti] <logname>+"


def main(args):
    """Parse command-line arguments and print the XML result(s) for glidein output file(s).

    This function processes the command-line arguments to determine whether to output
    a single XML result or combine multiple XML results into a ResultSet. If the "-raw"
    flag is provided, it omits XML comments. If the "-forcemulti" flag is provided, it
    forces the output to be a ResultSet even if only one log file is specified.

    Args:
        args (list): List of command-line arguments (excluding the script name).

    Raises:
        SystemExit: If no logname is provided or if there is an error reading a file.
    """
    raw_out = False
    force_multi = False

    while True:
        if len(args) < 1:
            sys.stderr.write("Missing logname.\n")
            sys.stderr.write("%s\n" % USAGE)
            sys.exit(1)

        if args[0] == "-h":
            print(USAGE)
            sys.exit(0)
        elif args[0] == "-raw":
            raw_out = True
            args = args[1:]
        elif args[0] == "-forcemulti":
            force_multi = True
            args = args[1:]
        else:
            break  # looks like I found a log name

    if (len(args) == 1) and (not force_multi):
        # single file, just pass through
        try:
            fname = args[0]
            out = gWftLogParser.get_xml_result(fname)
        except OSError as e:
            sys.stderr.write("Error reading file: %s\n" % e)
            sys.exit(1)
        except:
            raise
            sys.stderr.write("%s\n" % USAGE)
            sys.exit(1)

        for line in out.split("\n"):
            if raw_out and (line[:2] == "<?"):
                # skip comments for raw output
                continue
            if line[:15] == "<OSGTestResult ":
                # insert file name
                line = line[:15] + ('logname="%s" ' % fname) + line[15:]
            print(line)
    else:
        # multiple files, combine in a set
        xmls = []
        for i in range(len(args)):
            try:
                fname = args[i]
                rawx = gWftLogParser.get_xml_result(fname)
                if rawx == "":
                    # nothing found, warn
                    sys.stderr.write("No XML in file %s\n" % fname)
                    continue

                x = []
                for line in rawx.split("\n"):
                    if line[:2] == "<?":
                        # skip comments
                        continue
                    if line[:15] == "<OSGTestResult ":
                        # insert file name
                        line = line[:15] + ('logname="%s" ' % fname) + line[15:]
                    x.append("  " + line)
                if x[-1] == "  ":
                    x = x[:-1]
                xmls.append("\n".join(x))
            except OSError as e:
                # just warn
                sys.stderr.write("Error reading file: %s\n" % e)
            except:
                # serious error... die
                raise
            pass

        if len(xmls) == 0:
            sys.stderr.write("Could not read a single file!")
            sys.exit(1)
        if not raw_out:
            sys.stdout.write('<?xml version="1.0"?>\n')
            sys.stdout.write("<OSGTestResultSet>\n")

        for line in xmls:
            sys.stdout.write(line + "\n")

        if not raw_out:
            sys.stdout.write("</OSGTestResultSet>\n")


if __name__ == "__main__":
    main(sys.argv[1:])
