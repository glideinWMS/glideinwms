# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   Argument parser helper


def str2int_range(str, min, max):
    try:
        val = int(str)
    except ValueError as e:
        raise ValueError("Must be a number.") from None
    if (val < min) or (val > max):
        raise ValueError("Must be in the range %i-%i." % (min, max))
    return val


def parse_date(str):
    arr = str.split("/")
    if len(arr) != 3:
        raise ValueError("Invalid date '%s'. Expected YY/MM/DD." % str)
    try:
        year = int(arr[0])
    except ValueError as e:
        raise ValueError("Invalid year '%s'. Must be a number." % arr[0])
    if year < 100:
        year = year + 2000

    try:
        mon = str2int_range(arr[1], 1, 12)
    except ValueError as e:
        raise ValueError(f"Invalid month '{arr[1]}'. {e}") from None

    try:
        day = str2int_range(arr[2], 1, 31)
    except ValueError as e:
        raise ValueError(f"Invalid day '{arr[2]}'. {e}") from None

    return (year, mon, day)


def parse_time(str):
    arr = str.split(":")
    if len(arr) != 3:
        raise ValueError("Invalid time '%s'. Expected hh:mm:ss." % str)
    try:
        hour = str2int_range(arr[0], 0, 23)
    except ValueError as e:
        raise ValueError(f"Invalid hour '{arr[0]}'. {e}") from None

    try:
        min = str2int_range(arr[1], 0, 59)
    except ValueError as e:
        raise ValueError(f"Invalid minute '{arr[1]}'. {e}") from None

    try:
        sec = str2int_range(arr[2], 0, 59)
    except ValueError as e:
        raise ValueError(f"Invalid second '{arr[2]}'. {e}") from None

    return (hour, min, sec)
