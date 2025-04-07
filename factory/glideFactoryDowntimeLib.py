# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements the functions needed to handle the downtimes.
"""

import fcntl
import os.path
import time

from glideinwms.lib import timeConversion


class DowntimeFile:
    """Handle a downtime file.

    This class implements the functions needed to handle a downtime file.
    The downtime file is space-separated and contains downtime information.
    The first line is a comment (starting with '#') that serves as a header:

        "#%-29s %-30s %-20s %-30s %-20s # %s\n" % ("Start", "End", "Entry", "Frontend", "Sec_Class", "Comment")

    Each non-comment line in the file must have at least two space-separated entries (start_time and end_time),
    expressed in Unix time (seconds since epoch). If end_time is "None", the downtime does not have
    a set expiration (i.e. it runs forever). Additional entries may be used to limit the scope
    (Entry, Frontend, Sec_Class names) and to add a comment. Missing scope values or, respectively, the keywords
    "factory", "All", "All" mean that there are no scope restrictions.
    """

    def __init__(self, fname):
        """Initialize a DowntimeFile instance.

        Args:
            fname (str or Path): The path to the downtime file.
        """
        self.fname = fname

    def read(self, raise_on_error=False):
        """Return a list of downtime periods.

        Each downtime period is represented as a tuple:
        (start_time, end_time, entry, frontend, security_class, comment).
        A value of None for end_time indicates that the downtime is indefinite ("forever").
        Timestamps are in seconds from Epoch (utime).

        Args:
            raise_on_error (bool, optional): If True, exceptions will be raised;
                otherwise, errors are masked and an empty list is returned if the file is missing.
                Defaults to False.

        Returns:
            list: A list of downtime periods. For example:
                [(1215339200, 1215439170, "entry name", "frontend name", "security_class name", "# comment message"),
                 (1215439271, None, "factory", "All", "All", "")].
                `[]` is returned when `raise_on_error` is False (default) and there is no downtime file
        """
        return _read(self.fname, raise_on_error)

    def print_downtime(self, entry="Any", check_time=None):
        """Print the downtime status for the specified entry.

        Args:
            entry (str, optional): The entry name to check. Defaults to "Any".
            check_time (int, optional): The time to check (in seconds since epoch).
                If None, the current time is used.

        Returns:
            None
        """
        return _print_downtime(self.fname, entry, check_time)

    # if check_time==None, use current time
    def check_downtime(self, entry="Any", frontend="Any", security_class="Any", check_time=None):
        """Check if a downtime period is active for the specified parameters.

        If check_time is None, the current time is used.

        Args:
            entry (str, optional): The entry name to check. Defaults to "Any".
            frontend (str, optional): The frontend name to check. Defaults to "Any".
            security_class (str, optional): The security class to check. Defaults to "Any".
            check_time (int, optional): The time to check (in seconds since epoch).
                Defaults to current time if None.

        Returns:
            bool: True if a downtime period is active, False otherwise.
        """
        (msg, rtn) = _check_downtime(self.fname, entry, frontend, security_class, check_time)
        self.downtime_comment = msg
        return rtn

    def add_period(
        self, start_time, end_time, entry="All", frontend="All", security_class="All", comment="", create_if_empty=True
    ):
        """Add a scheduled downtime period to the downtime file.

        This function adds a downtime period to the file while maintaining an exclusive lock (fcntl.LOCK_EX)
        on the file during the write operation. The default values for entry, Frontend, and security_class are "All".

        Args:
            start_time (int): The start time in seconds since the Epoch.
            end_time (int): The end time in seconds since the Epoch.
            entry (str, optional): The entry name or "All". Defaults to "All".
            frontend (str, optional): The Frontend name or "All". Defaults to "All".
            security_class (str, optional): The security class or "All". Defaults to "All".
            comment (str, optional): A comment to add. Defaults to an empty string.
            create_if_empty (bool, optional): If False, raises FileNotFoundError if the downtime file does not exist.
                Defaults to True.

        Returns:
            int: 0 upon successful addition.
        """
        return _add_period(self.fname, start_time, end_time, entry, frontend, security_class, comment, create_if_empty)

    def start_downtime(
        self,
        start_time=None,
        end_time=None,
        entry="All",
        frontend="All",
        security_class="All",
        comment="",
        create_if_empty=True,
    ):
        """Start a downtime period with an indefinite end time.

        If `start_time` is None, the current time is used. The default values for `entry`, `frontend`,
        and `security_class` are "All", meaning that there are no scope restrictions.

        Args:
            start_time (int or None): The start time in seconds since the epoch.
                If None, the current time is used.
            end_time (int or None): The end time in seconds since the epoch.
                If None, there is no set end time.
            entry (str, optional): The entry name or "All". Defaults to "All".
            frontend (str, optional): The Frontend name or "All". Defaults to "All".
            security_class (str, optional): The security class or "All". Defaults to "All".
            comment (str, optional): A comment to add. Defaults to an empty string.
            create_if_empty (bool, optional): If False, raises FileNotFoundError if the downtime file does not exist.
                Defaults to True.

        Returns:
            int: The result of `add_period` (typically 0).
        """
        if start_time is None:
            start_time = int(time.time())
        return self.add_period(start_time, end_time, entry, frontend, security_class, comment, create_if_empty)

    def end_downtime(self, end_time=None, entry="All", frontend="All", security_class="All", comment=""):
        """End an active downtime period.

        If `end_time` is None, the current time is used. "All" (default) is a wildcard for `entry`,
        `frontend`, and `security_class`, meaning that there are no scope restrictions.

        Args:
            end_time (int or None): The end time in seconds since the epoch.
                If None, the current time is used.
            entry (str, optional): The entry name or "All". Defaults to "All".
            frontend (str, optional): The frontend name or "All". Defaults to "All".
            security_class (str, optional): The security class or "All". Defaults to "All".
            comment (str, optional): A comment to add. Defaults to an empty string.

        Returns:
            int: The number of downtime records closed.
        """
        return _end_downtime(self.fname, end_time, entry, frontend, security_class, comment)

    def purge_old_periods(self, cut_time=None, raise_on_error=False):
        """Purge old downtime periods from the downtime file.

        If cut_time is None or 0, the current time is used.
        If cut_time is negative, it is interpreted as current_time - abs(cut_time).

        Args:
            cut_time (int, optional): The cutoff time in seconds since the Epoch.
                Defaults to current time if None or 0.
                Negative values are relative to the current time, `current_time-abs(cut_time)`
            raise_on_error (bool, optional): If True, exceptions are raised;
                otherwise, errors are masked. Defaults to False.

        Returns:
            int: The number of records purged.
        """
        return _purge_old_periods(self.fname, cut_time, raise_on_error)


#############################
# INTERNAL - Do not use
#############################


def _read(fname, raise_on_error=False):
    """Return a list of downtime periods from the specified file.

    Each downtime period is represented as a tuple:
    (start_time, end_time, entry, frontend, security_class, comment).
    A value of None for end_time indicates an indefinite downtime ("forever").

    Args:
        fname (str or Path): The downtime file.
        raise_on_error (bool, optional): If True, exceptions are raised;
            otherwise, errors are masked and an empty list is returned if the file is missing.
            Defaults to False.

    Returns:
        list: A list of downtime periods. For example:
            [(1215339200, 1215439170, "entry name", "frontend name", "security_class name", "# comment message"),
             (1215439271, None, "factory", "All", "All", "")].
            `[]` is returned when `raise_on_error` is False (default) and there is no downtime file

    Raises:
        OSError: if the file is missing or unreadable and  raise_on_error is True.
        ValueError: if the file is malformed and raise_on_error is True.
    """
    try:
        with open(fname) as fd:
            fcntl.flock(fd, fcntl.LOCK_SH)
            lines = fd.readlines()
    except OSError:
        if raise_on_error:
            raise  # re-rise the exact same exception like no except
        else:
            return []  # no file -> no downtimes

    out = []
    lnr = 0
    for long_line in lines:
        lnr += 1
        line = long_line.strip()
        if len(line) == 0:
            continue  # ignore empty lines
        if line[0:1] == "#":
            continue  # ignore comments
        arr = line.split()
        # Read in lines of the downtime file
        # Start End Entry Security_Class Comment
        if len(arr) < 2:
            if raise_on_error:
                raise ValueError("%s:%i: Expected pair, got '%s'" % (fname, lnr, line))
            else:
                continue  # ignore malformed lines
        try:
            start_time = timeConversion.extractISO8601_Local(arr[0])
        except ValueError as e:
            if raise_on_error:
                raise ValueError("%s:%i: 1st element: %s" % (fname, lnr, e)) from e
            else:
                continue  # ignore errors

        try:
            if arr[1] == "None":
                end_time = None
            else:
                end_time = timeConversion.extractISO8601_Local(arr[1])
        except ValueError as e:
            if raise_on_error:
                raise ValueError("%s:%i: 2nd element: %s" % (fname, lnr, e)) from e
            else:
                continue  # ignore errors

        # Addition.  If more arguments exists, parse
        # Entry, Frontend, Security_Class, Comment
        if len(arr) >= 3:
            entry = arr[2]
        else:
            entry = "factory"
        if len(arr) >= 4:
            frontend = arr[3]
        else:
            frontend = "All"
        if len(arr) >= 5:
            security_class = arr[4]
        else:
            security_class = "All"
        if len(arr) >= 6:
            comment = arr[5:]
        else:
            comment = ""

        out.append((start_time, end_time, entry, frontend, security_class, comment))
        # end for long_line in lines:

    return out


def _print_downtime(fname, entry="Any", check_time=None):
    """Print the downtime status for each entry.

    This function reads the downtime file and prints the downtime status.
    It prints "Down" along with downtime details for entries that are currently in downtime,
    and "Up" otherwise.

    Args:
        fname (str or Path): The downtime file.
        entry (str, optional): The specific entry to print status for. Defaults to "Any".
        check_time (int, optional): The time to check (in seconds since epoch).
            If None, the current time is used.
    """
    if check_time is None:
        check_time = int(time.time())
    time_list = _read(fname)
    downtime_keys = {}
    for time_tuple in time_list:
        if check_time < time_tuple[0]:
            continue  # check_time before start
        if (time_tuple[1] is not None) and (check_time > time_tuple[1]):
            continue
        if time_tuple[2] in downtime_keys:
            downtime_keys[time_tuple[2]] += "," + time_tuple[3] + ":" + time_tuple[4]
        else:
            downtime_keys[time_tuple[2]] = time_tuple[3] + ":" + time_tuple[4]
    if "All" in downtime_keys:
        for e in downtime_keys:
            if (e != "All") and (e != "factory"):
                downtime_keys[e] += "," + downtime_keys["All"]
    if entry == "Any":
        for e in downtime_keys:
            print("%-30s Down\t%s" % (e, downtime_keys[e]))
    else:
        if entry in downtime_keys:
            print("%-30s Down\t%s" % (entry, downtime_keys[entry]))
        else:
            if ("All" in downtime_keys) and (entry != "factory"):
                print("%-30s Down\t%s" % (entry, downtime_keys["All"]))
            else:
                print("%-30s Up  \tAll:All" % (entry))


def _check_downtime(fname, entry="Any", frontend="Any", security_class="Any", check_time=None):
    """Check if a downtime period is active at the specified time.

    If `check_time` is None, the current time is used.
    `entry`, `frontend`, and `security_class` can be used to restrict the scope.
    "All" is used as a wildcard for `entry`, `frontend`, and `security_class`,
    to avoid scope restrictions.

    Args:
        fname (str or Path): The downtime file.
        entry (str): The entry name to check, or "All".
        frontend (str): The frontend name to check, or "All".
        security_class (str): The security class to check, or "All".
        check_time (int, optional): The time to check (in seconds since epoch).
            If None, the current time is used.

    Returns:
        tuple: A tuple containing:
            - comment (str): The downtime comment or an empty string.
            - bool: True if a downtime period is active, False otherwise.
    """
    if check_time is None:
        check_time = int(time.time())
    time_list = _read(fname)
    for time_tuple in time_list:
        # make sure this is for the right entry
        if (time_tuple[2] != "All") and (entry != time_tuple[2]):
            continue
        if (time_tuple[2] == "All") and (entry == "factory"):
            continue
        # make sure that this time tuple applies to this security_class
        # If the security class does not match the downtime entry,
        #   this is not a relevant downtime
        #   UNLESS the downtime says All
        if (time_tuple[3] != "All") and (frontend != time_tuple[3]):
            continue
        if (time_tuple[4] != "All") and (security_class != time_tuple[4]):
            continue
        if check_time < time_tuple[0]:
            continue  # check_time before start
        comment = " ".join(time_tuple[5][1:])
        if time_tuple[1] is None:
            return comment, True  # downtime valid until the end of times, so here we go
        if check_time <= time_tuple[1]:
            return comment, True  # within limit

    return "", False  # not found a downtime window


def _add_period(
    fname, start_time, end_time, entry="All", frontend="All", security_class="All", comment="", create_if_empty=True
):
    """Add a downtime period to the specified downtime file.

    This function maintains an exclusive lock (fcntl.LOCK_EX) on the file while appending the new downtime period.

    Args:
        fname (str or Path): The downtime file.
        start_time (int): The start time in seconds since the Epoch.
        end_time (int): The end time in seconds since the Epoch.
        entry (str, optional): The entry name or "All". Defaults to "All".
        frontend (str, optional): The frontend name or "All". Defaults to "All".
        security_class (str, optional): The security class or "All". Defaults to "All".
        comment (str, optional): A comment to add. Defaults to an empty string.
        create_if_empty (bool, optional): If False, raises FileNotFoundError if the downtime file does not exist.
            Defaults to True.

    Returns:
        int: 0 upon successful addition.

    Raises:
        FileNotFoundError: if there is no downtime file and create_if_empty is False.
    """
    exists = os.path.isfile(fname)
    if (not exists) and (not create_if_empty):
        raise FileNotFoundError("[Errno 2] No such file or directory: '%s'" % fname)

    comment = comment.replace("\n", " ")
    comment = comment.replace("\r", " ")
    with open(fname, "a+") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if not exists:  # new file, create header
            fd.write(
                "#%-29s %-30s %-20s %-30s %-20s # %s\n" % ("Start", "End", "Entry", "Frontend", "Sec_Class", "Comment")
            )
        if end_time is not None:
            fd.write(
                "%-30s %-20s %-20s %-30s %-20s # %-20s\n"
                % (
                    timeConversion.getISO8601_Local(start_time),
                    timeConversion.getISO8601_Local(end_time),
                    entry,
                    frontend,
                    security_class,
                    comment,
                )
            )
        else:
            fd.write(
                "%-30s %-30s %-20s %-30s %-20s # %s\n"
                % (timeConversion.getISO8601_Local(start_time), "None", entry, frontend, security_class, comment)
            )
    return 0


def _purge_old_periods(fname, cut_time=None, raise_on_error=False):
    """Purge old downtime periods from the downtime file.

    If cut_time is None or 0, the current time is used.
    If cut_time is negative, it is interpreted as current_time - abs(cut_time).

    Args:
        fname (str or Path): The downtime file.
        cut_time (int, optional): The cutoff time in seconds since the Epoch.
            Defaults to current time if None.
            Negative values are relative to the current time, `current_time-abs(cut_time)`
        raise_on_error (bool, optional): If True, exceptions are raised; otherwise, errors are masked.
            Defaults to False.

    Returns:
        int: The number of records purged.

    Raises:
        OSError: if the file is missing or unreadable and  raise_on_error is True.
        ValueError: if the file is malformed and raise_on_error is True.
    """
    if cut_time is None:
        cut_time = int(time.time())
    elif cut_time <= 0:
        cut_time = int(time.time()) + cut_time

    try:
        fd = open(fname, "r+")
    except OSError:
        if raise_on_error:
            raise  # re-rise the exact same exception like no except
        else:
            return 0  # no file -> nothing to purge
    with fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        # read the old info
        inlines = fd.readlines()

        outlines = []
        lnr = 0
        cut_nr = 0
        for long_line in inlines:
            lnr += 1
            line = long_line.strip()
            if len(line) == 0:
                outlines.append(long_line)
                continue  # pass on empty lines
            if line[0:1] == "#":
                outlines.append(long_line)
                continue  # pass on comments
            arr = line.split()
            if len(arr) < 2:
                if raise_on_error:
                    raise ValueError("%s:%i: Expected pair, got '%s'" % (fname, lnr, line))
                else:
                    outlines.append(long_line)
                    continue  # pass on malformed lines

            try:
                if arr[1] == "None":
                    end_time = None
                else:
                    end_time = timeConversion.extractISO8601_Local(arr[1])
            except ValueError as e:
                if raise_on_error:
                    raise ValueError("%s:%i: 2nd element: %s" % (fname, lnr, e)) from e
                else:
                    outlines.append(long_line)
                    continue  # unknown, pass on

            if end_time is None:
                outlines.append(long_line)
                continue  # valid forever, pass on

            if end_time >= cut_time:
                outlines.append(long_line)
                continue  # end_time after cut_time, have to keep it

            # if we got here, the period ended before the cut date... cut it
            cut_nr += 1
            pass  # end for

        # go back to start to rewrite
        fd.seek(0)
        fd.writelines(outlines)
        fd.truncate()

    return cut_nr


def _end_downtime(fname, end_time=None, entry="All", frontend="All", security_class="All", comment=""):
    """End an active downtime period.

    If `end_time` is None, the current time is used.
    "All" (default) is used as a wildcard for `entry`, `frontend`, and `security_class`,
    to avoid scope restrictions.

    Args:
        fname (str or Path): The downtime file.
        end_time (int or None): The end time in seconds since the epoch.
            If None, the current time is used.
        entry (str, optional): The entry name or "All". Defaults to "All".
        frontend (str, optional): The frontend name or "All". Defaults to "All".
        security_class (str, optional): The security class or "All". Defaults to "All".
        comment (str, optional): A comment to add. Defaults to an empty string.

    Returns:
        int: The number of downtime records closed.
    """
    comment = comment.replace("\r", " ")
    comment = comment.replace("\n", " ")
    if end_time is None:
        end_time = int(time.time())

    try:
        fd = open(fname, "r+")
    except OSError:
        return 0  # no file -> nothing to end

    with fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        # read the old info
        inlines = fd.readlines()

        outlines = []
        lnr = 0
        closed_nr = 0
        for long_line in inlines:
            lnr += 1
            line = long_line.strip()
            if len(line) == 0:
                outlines.append(long_line)
                continue  # pass on empty lines
            if line[0:1] == "#":
                outlines.append(long_line)
                continue  # pass on comments
            arr = line.split()
            if len(arr) < 2:
                outlines.append(long_line)
                continue  # pass on malformed lines
            # make sure this is for the right entry
            if (entry != "All") and (len(arr) > 2) and (entry != arr[2]):
                outlines.append(long_line)
                continue
            if (entry == "All") and (len(arr) > 2) and ("factory" == arr[2]):
                outlines.append(long_line)
                continue
            if (frontend != "All") and (len(arr) > 3) and (frontend != arr[3]):
                outlines.append(long_line)
                continue
            # make sure that this time tuple applies to this security_class
            if (security_class != "All") and (len(arr) > 4) and (security_class != arr[4]):
                outlines.append(long_line)
                continue
            cur_start_time = 0
            if arr[0] != "None":
                cur_start_time = timeConversion.extractISO8601_Local(arr[0])
            if arr[1] != "None":
                cur_end_time = timeConversion.extractISO8601_Local(arr[1])
            # logic short circuit guarantees that cur_end_time is defined (arr[1] != 'None')
            if arr[1] == "None" or (
                (cur_start_time < int(time.time())) and (cur_end_time > end_time)  # pylint: disable=E0606
            ):
                # open period -> close
                outlines.append("%-30s %-30s" % (arr[0], timeConversion.getISO8601_Local(end_time)))
                if len(arr) > 2:
                    sep = " "
                    t = 2
                    for param in arr[2:]:
                        if t < 5:
                            outlines.append("%s%-20s" % (sep, param))
                        else:
                            outlines.append(f"{sep}{param}")
                        t = t + 1
                if comment != "":
                    outlines.append(f"; {comment}")
                outlines.append("\n")
                closed_nr += 1
            else:
                # closed just pass on
                outlines.append(long_line)
            # Keep parsing file, since there may be multiple downtimes
            # pass # end for

        # go back to start to rewrite
        fd.seek(0)
        fd.writelines(outlines)
        fd.truncate()

    return closed_nr
