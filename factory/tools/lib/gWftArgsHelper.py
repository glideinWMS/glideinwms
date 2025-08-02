# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Argument parser helper"""


def str2int_range(in_str, min_val, max_val):
    """Convert a string to an integer and validate that it is within a specified range.

    Args:
        in_str (str): The string to convert to an integer.
        min_val (int): The minimum acceptable value.
        max_val (int): The maximum acceptable value.

    Returns:
        int: The converted integer if it is within the specified range.

    Raises:
        ValueError: If the string cannot be converted to an integer or if the resulting integer is not within the range [min, max].
    """
    try:
        val = int(in_str)
    except ValueError:
        raise ValueError("Must be a number.") from None
    if (val < min_val) or (val > max_val):
        raise ValueError("Must be in the range %i-%i." % (min_val, max_val))
    return val


def parse_date(time_str):
    """Parse a date string in the format YY/MM/DD (or YYYY/MM/DD) into a tuple of integers.

    Args:
        time_str (str): The date string to parse. Expected format is "YY/MM/DD" or "YYYY/MM/DD".

    Returns:
        tuple: A tuple (year, month, day) where year, month, and day are integers.

    Raises:
        ValueError: If the date string is not in the expected format or if any of the components are invalid.
    """
    arr = time_str.split("/")
    if len(arr) != 3:
        raise ValueError("Invalid date '%s'. Expected YY/MM/DD." % time_str)
    try:
        year = int(arr[0])
    except ValueError:
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

    return year, mon, day


def parse_time(time_str):
    """Parse a time string in the format hh:mm:ss into a tuple of integers.

    Args:
        time_str (str): The time string to parse. Expected format is "hh:mm:ss".

    Returns:
        tuple: A tuple (hour, minute, second) where each component is an integer.

    Raises:
        ValueError: If the time string is not in the expected format or if any of the components are invalid.
    """
    arr = time_str.split(":")
    if len(arr) != 3:
        raise ValueError("Invalid time '%s'. Expected hh:mm:ss." % time_str)
    try:
        hour = str2int_range(arr[0], 0, 23)
    except ValueError as e:
        raise ValueError(f"Invalid hour '{arr[0]}'. {e}") from None

    try:
        mins = str2int_range(arr[1], 0, 59)
    except ValueError as e:
        raise ValueError(f"Invalid minute '{arr[1]}'. {e}") from None

    try:
        sec = str2int_range(arr[2], 0, 59)
    except ValueError as e:
        raise ValueError(f"Invalid second '{arr[2]}'. {e}") from None

    return hour, mins, sec
