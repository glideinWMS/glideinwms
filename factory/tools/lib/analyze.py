# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Library for analyze_entries, analyze_queues and analyze_frontends.

This module provides helper functions for converting large numbers into a human‐readable
format (e.g., kilo/mega), printing dictionaries for debugging, and formatting summary
lines for output.
"""


# Convert particularly large numbers
#    into kilo/mega; keeps 3 sig figs
# Example: km(123456) returns "123 K"
#      and km(1234567) returns "1.23 M"
def km(z):
    """Convert a large number into a string with kilo, mega, or giga units.

    Keeps 3 significant figures.

    Examples:
        km(123456) returns "123.5K"
        km(1234567) returns "1.2M"

    Args:
        z (float or int): The number to convert.

    Returns:
        str: The converted number as a string with units.
    """
    if z < 0:
        neg = "-"
    else:
        neg = ""
    z = abs(z)

    x = int(z)
    w = z * 1.0e-3
    v = z * 1.0e-6
    t = z * 1.0e-9
    if x >= 1000:
        if x >= 1000 and x < 1000000:
            return f"{neg}{w:.1f}K"
        if x >= 1000000 and x < 1000000000:
            return f"{neg}{v:.1f}M"
        if x >= 1000000000:
            return f"{neg}{t:.1f}G"
    else:
        return f"{neg}{z:.1f}"


# prints a dictionary with \n and \t
#    between elements for ease of debugging.


def debug_print_dict(data):
    """Print a nested dictionary with indentation for debugging.

    The dictionary is printed with newlines and tab characters to improve readability.

    Args:
        data (dict): The dictionary to print.

    Returns:
        None
    """
    for period, p in data.items():
        print(period)
        for frontend, f in p.items():
            print("\t", frontend)
            for entry, e in f.items():
                print("\t\t", entry)
                for element, value in e.items():
                    print("\t\t\t", element, ":", value)
    return


# Prints a line formatted the following way:
# printline(1234, 7200 (2 days), total) returns:
# "1.2K (.34 hours - .17 slots - %XX of total)"
# Set div = 1 to omit percentage of total


def printline(x, div, period):
    """Format a summary line for display.

    Returns a formatted string containing the value of 'x' in human-readable units,
    along with its conversion to hours and slots, and optionally the percentage of total.

    For example, printline(1234, 7200, total) might return:
    " 1.2K (  0.3 hours -  0.2 slots -  XX% of total)"

    Args:
        x (float or int): The value to be converted.
        div (float or int): The divisor used for calculating percentages. Set div = 1 to omit percentage.
        period (float or int): The total period value used in slot calculation.

    Returns:
        str: A formatted string representing the summary line.
    """
    if div == 1:
        sp = ""
    else:
        try:
            sp = " - %2d%%" % ((float(x) / float(div)) * 100)
        except Exception:
            sp = " - NA%"
    return "%6s (%6s hours - %5s slots%s)" % (km(x), km(float(x) / 3600.0), km(float(x) / float(period)), sp)
