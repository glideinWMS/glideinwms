#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This script allows to compare two different entries in the GlideinWMS Factory."""


import argparse
import difflib
import re
import sys

import requests

from glideinwms.creation.lib.factoryXmlConfig import _parse


def parse_opts():
    """Parse the command line options for this command.

    Returns:
        argparse.Namespace: Parsed command-line options.
    """
    description = "Do a diff of two entries\n\n"

    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)

    # Positional arguments
    parser.add_argument(
        "conf_a", type=str, help="Configuration for the first entry.", default="/etc/gwms-factory/glideinWMS.xml"
    )

    parser.add_argument(
        "conf_b", type=str, help="Configuration for the second entry.", default="/etc/gwms-factory/glideinWMS.xml"
    )

    parser.add_argument("entry_a", type=str, help="Name of the first entry.")

    parser.add_argument(
        "entry_b",
        type=str,
        nargs="?",  # Makes this positional argument optional
        help="Name of the second entry (optional). Defaults to the first entry name.",
    )

    # Named argument
    parser.add_argument("--mergely", action="count", help="Only print the mergely link")

    options = parser.parse_args()

    # Set entry_b to entry_a if not provided
    if options.entry_b is None:
        options.entry_b = options.entry_a

    return options


def get_entry_text(entry, conf):
    """Extract the XML snippet for the specified entry from the configuration file.

    Args:
        entry (str): The name of the entry to extract.
        conf (str): Path to the configuration XML file.

    Returns:
        str: The XML snippet corresponding to the entry.
    """
    with open(conf) as fdesc:
        text = fdesc.read()
        # pylint: disable=no-member, maybe-no-member
        return re.search('.*( +<entry name="%s".*?</entry>)' % entry, text, re.DOTALL).group(1)


def handle_diff(text_a, text_b):
    """Print the unified diff between two texts using the diff command.

    Args:
        text_a (str): The first text.
        text_b (str): The second text.
    """
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()

    # Create a unified diff
    diff = difflib.unified_diff(lines_a, lines_b, fromfile="text_a", tofile="text_b", lineterm="")

    # Print the diff line by line
    for line in diff:
        print(line)


def handle_mergely(text_a, text_b):
    """Print a mergely.com link for the diff between two texts.

    Args:
        text_a (str): The left-hand side text.
        text_b (str): The right-hand side text.
    """
    url = "https://mergely.com/ajax/handle_save.php"

    payload = {"config": {}, "lhs_title": "", "lhs": text_a, "rhs_title": "", "rhs": text_b}

    # HTTP header field names are case-insensitive but MUST be converted to lowercase by the API
    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": "https://editor.mergely.com/",
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(str(payload))),
        "Origin": "https://editor.mergely.com",
        "Connection": "keep-alive",
    }

    res = requests.post(url, headers=headers, json=payload)

    print("http://www.mergely.com/" + res.headers["location"])


def main():
    """Main function to compare two entries.

    Parses command-line options, extracts XML snippets for two entries from their
    respective configuration files, prints the unified diff between them, and if the
    '--mergely' flag is set, prints a link to the mergely.com diff page.
    """
    options = parse_opts()

    entry_a = options.entry_a
    entry_b = options.entry_b

    conf_a = _parse(options.conf_a)
    conf_b = _parse(options.conf_b)

    # pylint: disable=no-member, maybe-no-member
    entry_a = [e for e in conf_a.get_entries() if e.getName() == entry_a]
    # pylint: disable=no-member, maybe-no-member
    entry_b = [e for e in conf_b.get_entries() if e.getName() == entry_b]
    if len(entry_a) != 1:
        print(f"Cannot find entry {options.entry_a} in the configuration file {options.conf_a}")
        sys.exit(1)
    if len(entry_b) != 1:
        print(f"Cannot find entry {options.entry_b} in the configuration file {options.conf_b}")
        sys.exit(1)

    text_a = get_entry_text(options.entry_a, options.conf_a)
    text_b = get_entry_text(options.entry_b, options.conf_b)
    handle_diff(text_a, text_b)
    if options.mergely:
        print()
        handle_mergely(text_a, text_b)


if __name__ == "__main__":
    main()
