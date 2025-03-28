# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   This module implements the functions needed to
#   handle the downtimes

import fcntl
import os.path
import time

from glideinwms.lib import timeConversion


class DowntimeFile:
    """Handle a downtime file

    space separated  file with downtime information
    Each line has space-separated values
    The first line is a comment (starts with #) and header line :
     "#%-29s %-30s %-20s %-30s %-20s # %s\n" % ("Start", "End", "Entry", "Frontend", "Sec_Class", "Comment")
    Each non-comment line in the file has at least two entries
      start_time   end_time
      expressed in utime
    if end_time is None, the downtime does not have a set expiration
    (i.e. it runs forever)
    Additional entries are used to limit the scope (Entry, Frontend, Sec_Class) and to add a comment
    """

    def __init__(self, fname):
        self.fname = fname

    def read(self, raise_on_error=False):
        """Return a list of downtime periods (utimes)
        a value of None indicates "forever"
        for example: `[(1215339200,1215439170),(1215439271,None)]`

        Args:
            raise_on_error (bool): if not True mask all the exceptions

        Returns:
            list: list of downtime periods [(start, end), ...]
                a value of None indicates "forever", no start time, or no end time
                timestamps are in seconds from epoch (utime)
                `[]` returned when `raise_on_error` is False (default) and there is no downtime file
        """
        return read(self.fname, raise_on_error)

    def printDowntime(self, entry="Any", check_time=None):
        return printDowntime(self.fname, entry, check_time)

    # if check_time==None, use current time
    def checkDowntime(self, entry="Any", frontend="Any", security_class="Any", check_time=None):
        (msg, rtn) = checkDowntime(self.fname, entry, frontend, security_class, check_time)
        self.downtime_comment = msg
        return rtn

    def addPeriod(
        self, start_time, end_time, entry="All", frontend="All", security_class="All", comment="", create_if_empty=True
    ):
        """Add a scheduled downtime
        Maintin a lock (fcntl.LOCK_EX) on the downtime file while writing
        entry, frontend, and security_class default to "All"

        Args:
            start_time (int): start time in seconds from Epoch
            end_time (int): end time in seconds from Epoch
            entry (str): entry  name or "All"
            frontend (str): frontend name os "All"
            security_class (str): security class name or "All"
            comment (str): comment to add
            create_if_empty (bool): if False, raise FileNotFoundError if there is not already a downtime file

        Returns:
            int: 0
        """
        return addPeriod(self.fname, start_time, end_time, entry, frontend, security_class, comment, create_if_empty)

    def startDowntime(
        self,
        start_time=None,
        end_time=None,
        entry="All",
        frontend="All",
        security_class="All",
        comment="",
        create_if_empty=True,
    ):
        """start a downtime that we don't know when it will end
        if start_time==None, use current time
        entry, frontend, and security_class default to "All"

        Args:
            start_time (int|None): start time in seconds from Epoch
            end_time (int|None): end time in seconds from Epoch
            entry (str): entry  name or "All"
            frontend (str): frontend name os "All"
            security_class (str): security class name or "All"
            comment (str): comment to add
            create_if_empty (bool): if False, raise FileNotFoundError if there is not already a downtime file

        Returns:

        """
        if start_time is None:
            start_time = int(time.time())
        return self.addPeriod(start_time, end_time, entry, frontend, security_class, comment, create_if_empty)

    def endDowntime(self, end_time=None, entry="All", frontend="All", security_class="All", comment=""):
        """End a downtime (not a scheduled one)
        if end_time==None, use current time
        entry, frontend, and security_class default to "All"

        Args:
            end_time (int|None): end time in seconds from Epoch. If end_time==None, default, use current time
            entry (str): entry  name or "All"
            frontend (str): frontend name os "All"
            security_class (str): security class name or "All"
            comment (str): comment to add

        Returns:
            int: number of records closed
        """
        return endDowntime(self.fname, end_time, entry, frontend, security_class, comment)

    def purgeOldPeriods(self, cut_time=None, raise_on_error=False):
        """Purge old downtime periods
        if cut time<0, use current_time-abs(cut_time)

        Args:
            cut_time (int): cut time in seconds from epoch, if cut_time==None or 0, use current time,
                if cut time<0, use current_time-abs(cut_time)
            raise_on_error (bool): if not True, mask all exceptions

        Returns:
            int: number of records purged
        """
        return purgeOldPeriods(self.fname, cut_time, raise_on_error)


#############################
# INTERNAL - Do not use
#############################


def read(fname, raise_on_error=False):
    """Return a list of downtime periods (utimes)
    a value of None indicates "forever"
    for example: `[(1215339200,1215439170),(1215439271,None)]`

    Args:
        fname (str|Path): downtimes file
        raise_on_error (bool): if not True mask all the exceptions

    Returns:
        list: list of downtime periods [(start, end), ...]
            a value of None indicates "forever", no start time, or no end time
            timestamps are in seconds from epoch (utime)
            `[]` returned when `raise_on_error` is False (default) and there is no file
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
        if len(arr) >= 3:
            frontend = arr[3]
        else:
            frontend = "All"
        if len(arr) >= 4:
            security_class = arr[4]
        else:
            security_class = "All"
        if len(arr) >= 5:
            comment = arr[5:]
        else:
            comment = ""

        out.append((start_time, end_time, entry, frontend, security_class, comment))
        # end for long_line in lines:

    return out


def printDowntime(fname, entry="Any", check_time=None):
    if check_time is None:
        check_time = int(time.time())
    time_list = read(fname)
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


def checkDowntime(fname, entry="Any", frontend="Any", security_class="Any", check_time=None):
    """Check if there is a downtime at `check_time`
    if check_time==None, use current time
    "All" (default) is a wildcard for entry, frontend and security_class

    Args:
        fname (str|Path): Downtime file
        entry (str): entry  name or "All"
        frontend (str): frontend name os "All"
        security_class (str): security class name or "All"
        check_time: time to check in seconds from epoch, if check_time==None, use current time

    Returns:
        (str, bool): tuple with the comment string and True is in downtime
            or ("", False) is not in downtime
    """
    if check_time is None:
        check_time = int(time.time())
    time_list = read(fname)
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
            return (comment, True)  # downtime valid until the end of times, so here we go
        if check_time <= time_tuple[1]:
            return (comment, True)  # within limit

    return ("", False)  # not found a downtime window


def addPeriod(
    fname, start_time, end_time, entry="All", frontend="All", security_class="All", comment="", create_if_empty=True
):
    """Add a downtime period
    Maintin a lock (fcntl.LOCK_EX) on the downtime file while writing

    Args:
        fname (str|Path): downtime file
        start_time (int): start time in seconds from Epoch
        end_time (int): end time in seconds from Epoch
        entry (str): entry  name or "All"
        frontend (str): frontend name os "All"
        security_class (str): security class name or "All"
        comment (str): comment to add
        create_if_empty (bool): if False, raise FileNotFoundError if there is not already a downtime file

    Returns:
        int: 0
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


def purgeOldPeriods(fname, cut_time=None, raise_on_error=False):
    """Purge old rules using cut_time
    if cut_time==None or 0, use current time
    if cut time<0, use current_time-abs(cut_time)

    Args:
        fname (str|Path): downtime file
        cut_time (int): cut time in seconds from epoch, if cut_time==None or 0, use current time,
            if cut time<0, use current_time-abs(cut_time)
        raise_on_error (bool): if not True, mask all exceptions

    Returns:
        int: number of records purged
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


def endDowntime(fname, end_time=None, entry="All", frontend="All", security_class="All", comment=""):
    """End a downtime (not a scheduled one)
    if end_time==None, use current time
    "All" (default) is a wildcard for entry, frontend and security_class

    Args:
        fname (str|Path): Downtime file
        end_time (int): end time in seconds from epoch, if end_time==None, use current time
        entry (str): entry  name or "All"
        frontend (str): frontend name os "All"
        security_class (str): security class name or "All"
        comment (str): comment to add

    Returns:
        int: Number of downtime records closed
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
