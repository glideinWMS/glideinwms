# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements the basic functions needed to interface with rrdtool."""

import os
import shutil
import tempfile
import time

from . import defaults, subprocessSupport

try:
    import rrdtool  # pylint: disable=import-error
except ImportError:
    pass  # Will use the binary tools if the Python library is not available


class BaseRRDSupport:
    """Base class providing common support for working with RRD files."""

    def __init__(self, rrd_obj):
        """Initialize the BaseRRDSupport class.

        Args:
            rrd_obj (object): The RRD object, either from the rrdtool module or a command-line wrapper.
        """
        self.rrd_obj = rrd_obj

    def isDummy(self):
        """Check if the RRD object is a dummy (None).

        Returns:
            bool: True if the RRD object is None, False otherwise.
        """
        return self.rrd_obj is None

    def get_disk_lock(self, fname):
        """Get a disk lock for the specified file.

        This is a no-op in the base class. It should be overridden in child classes if needed.

        Args:
            fname (str): The filename to lock.

        Returns:
            DummyDiskLock: A dummy lock object.
        """
        return dummy_disk_lock()

    def get_graph_lock(self, fname):
        """Get a graph lock for the specified file.

        This is a no-op in the base class. It should be overridden in child classes if needed.

        Args:
            fname (str): The filename to lock.

        Returns:
            DummyDiskLock: A dummy lock object.
        """
        return dummy_disk_lock()

    def create_rrd(self, rrdfname, rrd_step, rrd_archives, rrd_ds):
        """Create a new RRD archive.

        Args:
            rrdfname (str): The file path name of the RRD archive.
            rrd_step (int): Base interval in seconds.
            rrd_archives (list): List of tuples containing archive settings. These are (in order):
                                 CF    - consolidation function (usually AVERAGE)
                                 xff   - xfiles factor (fraction that can be unknown)
                                 steps - how many of these primary data points are used to build a consolidated data point
                                 rows  - how many generations of data values are kept
            rrd_ds (tuple): Tuple containing data source settings. These are (in order):
                            ds-name   - attribute name
                            DST       - Data Source Type (usually GAUGE)
                            heartbeat - the maximum number of seconds that may pass between two updates before it becomes unknown
                            min       - min value
                            max       - max value

        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        self.create_rrd_multi(rrdfname, rrd_step, rrd_archives, (rrd_ds,))

    def create_rrd_multi(self, rrdfname, rrd_step, rrd_archives, rrd_ds_arr):
        """Create a new RRD archive with multiple data sources.

        Args:
            rrdfname (str): The file path name of the RRD archive.
            rrd_step (int): Base interval in seconds.
            rrd_archives (list): List of tuples containing archive settings. These are (in order):
                CF    - consolidation function (usually AVERAGE)
                xff   - xfiles factor (fraction that can be unknown)
                steps - how many of these primary data points are used to build a consolidated data point
                rows  - how many generations of data values are kept
            rrd_ds_arr (list): List of tuples containing data source settings. These are (in order):
                ds-name   - attribute name
                DST       - Data Source Type (usually GAUGE)
                heartbeat - the maximum number of seconds that may pass between two updates before it becomes unknown
                min       - min value
                max       - max value

        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        if self.rrd_obj is None:
            return  # nothing to do in this case

        # make the start time to be aligned on the rrd_step boundary
        # This is needed for optimal resolution selection
        start_time = (int(time.time() - 1) / rrd_step) * rrd_step
        # print (rrdfname,start_time,rrd_step)+rrd_ds
        args = [str(rrdfname), "-b", "%li" % start_time, "-s", "%i" % rrd_step]
        for rrd_ds in rrd_ds_arr:
            args.append("DS:%s:%s:%i:%s:%s" % rrd_ds)
        for archive in rrd_archives:
            args.append("RRA:%s:%g:%i:%i" % archive)

        lck = self.get_disk_lock(rrdfname)
        try:
            self.rrd_obj.create(*args)
        finally:
            lck.close()

    def update_rrd(self, rrdfname, time, val):
        """Update an RRD archive with a new value.

        Args:
            rrdfname (str): The file path name of the RRD archive.
            time (int): The time at which the value was taken.
            val (str): The value to update.
        """
        if self.rrd_obj is None:
            return  # nothing to do in this case

        lck = self.get_disk_lock(rrdfname)
        try:
            self.rrd_obj.update(str(rrdfname), "%li:%s" % (time, val))
        finally:
            lck.close()

    def update_rrd_multi(self, rrdfname, time, val_dict):
        """Update an RRD archive with multiple values.

        Args:
            rrdfname (str): The file path name of the RRD archive.
            time (int): The time at which the values were taken.
            val_dict (dict): A dictionary of data source names to values.
        """
        if self.rrd_obj is None:
            return  # nothing to do in this case

        args = [str(rrdfname)]
        ds_names = sorted(val_dict.keys())

        ds_names_real = []
        ds_vals = []

        for ds_name in ds_names:
            if val_dict[ds_name] is not None:
                ds_vals.append("%s" % val_dict[ds_name])
                ds_names_real.append(ds_name)

        if not ds_names_real:
            return

        args.append("-t")
        args.append(":".join(ds_names_real))
        args.append(("%li:" % time) + ":".join(ds_vals))

        lck = self.get_disk_lock(rrdfname)
        try:
            self.rrd_obj.update(*args)
        finally:
            lck.close()

    def rrd2graph(
        self,
        fname,
        rrd_step,
        ds_name,
        ds_type,
        start,
        end,
        width,
        height,
        title,
        rrd_files,
        cdef_arr=None,
        trend=None,
        img_format="PNG",
    ):
        """Create a graph file from a set of RRD files.

        Args:
            fname (str): The file path name of the graph file.
            rrd_step (int): The step to use in the RRD files.
            ds_name (str): The attribute to use in the RRD files.
            ds_type (str): The type of data source to use in the RRD files.
            start (int): The start time in Unix time format.
            end (int): The end time in Unix time format.
            width (int): The width of the graph.
            height (int): The height of the graph.
            title (str): The title of the graph.
            rrd_files (list): List of tuples, each containing RRD file information. Tuples with, in order:
                              rrd_id      - logical name of the RRD file (will be the graph label)
                              rrd_fname   - name of the RRD file
                              graph_type  - Graph type (LINE, STACK, AREA)
                              graph_color - Graph color in rrdtool format
            cdef_arr (list, optional): List of derived RRD values. Defaults to None.
                                       If present, only the cdefs will be plotted
                                       Each element is a tuple of (in order):
                                        rrd_id        - logical name of the RRD file (will be the graph label)
                                        cdef_formula  - Derived formula in rrdtool format
                                        graph_type    - Graph type (LINE, STACK, AREA)
                                        graph_color   - Graph color in rrdtool format
            trend (int, optional): Trend value in seconds. Defaults to None.
            img_format (str): The image format of the graph file. Defaults to "PNG".

        For more details see
            http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        if self.rrd_obj is None:
            return  # nothing to do in this case

        multi_rrd_files = [
            (rrd_file[0], rrd_file[1], ds_name, ds_type, rrd_file[2], rrd_file[3]) for rrd_file in rrd_files
        ]
        return self.rrd2graph_multi(
            fname, rrd_step, start, end, width, height, title, multi_rrd_files, cdef_arr, trend, img_format
        )

    def rrd2graph_now(
        self,
        fname,
        rrd_step,
        ds_name,
        ds_type,
        period,
        width,
        height,
        title,
        rrd_files,
        cdef_arr=None,
        trend=None,
        img_format="PNG",
    ):
        """Create a graph file from a set of RRD files for the current time.

        Args:
            fname (str): The file path name of the graph file.
            rrd_step (int): The step to use in the RRD files.
            ds_name (str): The attribute to use in the RRD files.
            ds_type (str): The type of data source to use in the RRD files.
            period (int): The time period for the graph.
            width (int): The width of the graph.
            height (int): The height of the graph.
            title (str): The title of the graph.
            rrd_files (list): List of tuples, each containing RRD file information. In order:
                rrd_id      - logical name of the RRD file (will be the graph label)
                rrd_fname   - name of the RRD file
                graph_type  - Graph type (LINE, STACK, AREA)
                graph_color - Graph color in rrdtool format
            cdef_arr (list, optional): List of derived RRD values. Defaults to None.
                                       If present, only the cdefs will be plotted
                                       Each element is a tuple of (in order)
                                           rrd_id        - logical name of the RRD file (will be the graph label)
                                           cdef_formula  - Derived formula in rrdtool format
                                           graph_type    - Graph type (LINE, STACK, AREA)
                                           graph_color   - Graph color in rrdtool format
            trend (int, optional): Trend value in seconds. Defaults to None.
            img_format (str): The image format of the graph file. Defaults to "PNG".

        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        now = int(time.time())
        start = ((now - period) / rrd_step) * rrd_step
        end = ((now - 1) / rrd_step) * rrd_step
        return self.rrd2graph(
            fname, rrd_step, ds_name, ds_type, start, end, width, height, title, rrd_files, cdef_arr, trend, img_format
        )

    def rrd2graph_multi(
        self, fname, rrd_step, start, end, width, height, title, rrd_files, cdef_arr=None, trend=None, img_format="PNG"
    ):
        """Create a graph file from a set of RRD files with multiple data sources.

        Args:
            fname (str): The file path name of the graph file.
            rrd_step (int): The step to use in the RRD files.
            start (int): The start time in Unix time format.
            end (int): The end time in Unix time format.
            width (int): The width of the graph.
            height (int): The height of the graph.
            title (str): The title of the graph.
            rrd_files (list): List of tuples, each containing RRD file information. In order:
                rrd_id      - logical name of the RRD file (will be the graph label)
                rrd_fname   - name of the RRD file
                ds_name     - Which attribute should I use in the RRD files
                ds_type     - Which type should I use in the RRD files
                graph_type  - Graph type (LINE, STACK, AREA)
                graph_color - Graph color in rrdtool format
            cdef_arr (list, optional): List of derived RRD values. Defaults to None.
                                       If present, only the cdefs will be plotted
                                       Each element is a tuple of (in order)
                                           rrd_id        - logical name of the RRD file (will be the graph label)
                                           cdef_formula  - Derived formula in rrdtool format
                                           graph_type    - Graph type (LINE, STACK, AREA)
                                           graph_color   - Graph color in rrdtool format
            trend (int, optional): Trend value in seconds. Defaults to None.
            img_format (str): The image format of the graph file. Defaults to "PNG".

        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        if self.rrd_obj is None:
            return  # nothing to do in this case

        args = [
            str(fname),
            "-s",
            "%li" % start,
            "-e",
            "%li" % end,
            "--step",
            "%i" % rrd_step,
            "-l",
            "0",
            "-w",
            "%i" % width,
            "-h",
            "%i" % height,
            "--imgformat",
            str(img_format),
            "--title",
            str(title),
        ]
        for rrd_file in rrd_files:
            ds_id = rrd_file[0]
            ds_fname = rrd_file[1]
            ds_name = rrd_file[2]
            ds_type = rrd_file[3]
            if trend is None:
                args.append(f"DEF:{ds_id}={ds_fname}:{ds_name}:{ds_type}")
            else:
                args.append(f"DEF:{ds_id}_inst={ds_fname}:{ds_name}:{ds_type}")
                args.append(f"CDEF:{ds_id}={ds_id}_inst,{trend},TREND")

        plot_arr = rrd_files
        if cdef_arr is not None:
            # plot the cdefs not the files themselves, when we have them
            plot_arr = cdef_arr
            for cdef_el in cdef_arr:
                ds_id = cdef_el[0]
                cdef_formula = cdef_el[1]
                # TODO: ds_graph_type and ds_color seem unused
                ds_graph_type = rrd_file[2]
                ds_color = rrd_file[3]
                args.append(f"CDEF:{ds_id}={cdef_formula}")
        else:
            plot_arr = [(rrd_file[0], None, rrd_file[4], rrd_file[5]) for rrd_file in rrd_files]

        if plot_arr[0][2] == "STACK":
            # add an invisible baseline to stack upon
            args.append("AREA:0")

        for plot_el in plot_arr:
            ds_id = plot_el[0]
            ds_graph_type = plot_el[2]
            ds_color = plot_el[3]
            args.append(f"{ds_graph_type}:{ds_id}#{ds_color}:{ds_id}")

        args.append("COMMENT:Created on %s" % time.strftime(r"%b %d %H\:%M\:%S %Z %Y"))

        try:
            lck = self.get_graph_lock(fname)
            try:
                self.rrd_obj.graph(*args)
            finally:
                lck.close()
        except Exception:
            print("Failed graph: %s" % str(args))

        return args

    def rrd2graph_multi_now(
        self, fname, rrd_step, period, width, height, title, rrd_files, cdef_arr=None, trend=None, img_format="PNG"
    ):
        """Create a graph file from a set of RRD files for the current time with multiple data sources.

        Args:
            fname (str): The file path name of the graph file.
            rrd_step (int): The step to use in the RRD files.
            period (int): The time period for the graph.
            width (int): The width of the graph.
            height (int): The height of the graph.
            title (str): The title of the graph.
            rrd_files (list): List of tuples, each containing RRD file information. In order:
                rrd_id      - logical name of the RRD file (will be the graph label)
                rrd_fname   - name of the RRD file
                ds_name     - Which attribute should I use in the RRD files
                ds_type     - Which type should I use in the RRD files
                graph_type  - Graph type (LINE, STACK, AREA)
                graph_color - Graph color in rrdtool format
            cdef_arr (list, optional): List of derived RRD values. Defaults to None.
                                       If present, only the cdefs will be plotted
                                       Each element is a tuple of (in order)
                                           rrd_id        - logical name of the RRD file (will be the graph label)
                                           cdef_formula  - Derived formula in rrdtool format
                                           graph_type    - Graph type (LINE, STACK, AREA)
                                           graph_color   - Graph color in rrdtool format
            trend (int, optional): Trend value in seconds. Defaults to None.
            img_format (str): The image format of the graph file. Defaults to "PNG".

        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html
        """
        now = int(time.time())
        start = int(((now - period) / rrd_step) * rrd_step)
        end = int(((now - 1) / rrd_step) * rrd_step)
        return self.rrd2graph_multi(
            fname, rrd_step, start, end, width, height, title, rrd_files, cdef_arr, trend, img_format
        )

    def fetch_rrd(self, filename, CF, resolution=None, start=None, end=None, daemon=None):
        """Fetch data from an RRD file.

        Fetch will analyze the RRD and try to retrieve the data in the resolution requested.

        Args:
            filename (str): The name of the RRD file to fetch data from.
            CF (str): The consolidation function to apply (AVERAGE, MIN, MAX, LAST).
            resolution (int, optional): The resolution of the data in seconds. Defaults to 300.
            start (int, optional): The start of the time series in Unix time. Defaults to end - 1 day.
            end (int, optional): The end of the time series in Unix time. Defaults to now.
            daemon (str, optional): The address of the rrdcached daemon. Defaults to None.
                                    If specified, a flush command is sent to the server before reading the
                                    RRD files. This allows rrdtool to return fresh data even
                                    if the daemon is configured to cache values for a long time.

        For more details see
          http://oss.oetiker.ch/rrdtool/doc/rrdcreate.en.html

        Returns:
            tuple: A tuple containing time info, headers, and data values.

        Raises:
            RuntimeError: If the consolidation function is invalid or if the RRD file does not exist.
        """
        if self.rrd_obj is None:
            return  # nothing to do in this case

        if CF not in ("AVERAGE", "MIN", "MAX", "LAST"):
            raise RuntimeError("Invalid consolidation function %s" % CF)
        args = [str(filename), str(CF)]
        if resolution is not None:
            args.append("-r")
            args.append(str(resolution))
        if end is not None:
            args.append("-e")
            args.append(str(end))
        if start is not None:
            args.append("-s")
            args.append(str(start))
        if daemon is not None:
            args.append("--daemon")
            args.append(str(daemon))

        if os.path.exists(filename):
            try:
                return self.rrd_obj.fetch(*args)
            except Exception as e:
                raise RuntimeError("Error when running rrdtool.fetch") from e
        else:
            raise RuntimeError(f"RRD file '{filename}' does not exist. Failing fetch_rrd.")

    def verify_rrd(self, filename, expected_dict):
        """Verify that an RRD file matches a dictionary of expected data sources (datastores).

        This will return a tuple of arrays ([missing],[extra]) attributes.

        Args:
            filename (str): The filename of the RRD to verify.
            expected_dict (dict): Dictionary of expected data sources.

        Returns:
            tuple: A tuple containing lists of missing and extra attributes.
        """
        rrd_info = self.rrd_obj.info(filename)
        rrd_dict = {}
        for key in list(rrd_info.keys()):
            # rrdtool 1.3
            if key[:3] == "ds[":
                rrd_dict[key[3:].split("]")[0]] = None
            # rrdtool 1.2
            if key == "ds":
                for dskey in list(rrd_info[key].keys()):
                    rrd_dict[dskey] = None
        missing = []
        extra = []
        for t in list(expected_dict.keys()):
            if t not in list(rrd_dict.keys()):
                missing.append(t)
        for t in list(rrd_dict.keys()):
            if t not in list(expected_dict.keys()):
                extra.append(t)
        return (missing, extra)


class ModuleRRDSupport(BaseRRDSupport):
    """Class using the rrdtool Python module for RRD operations (rrd_obj)."""

    def __init__(self):
        """Initialize the ModuleRRDSupport class."""
        super().__init__(rrdtool)


class ExeRRDSupport(BaseRRDSupport):
    """Class using the rrdtool command-line executable for RRD operations (rrd_obj)."""

    def __init__(self):
        """Initialize the ExeRRDSupport class."""
        super().__init__(rrdtool_exe())


class rrdSupport(BaseRRDSupport):
    """Class that tries to use the rrdtool Python module, falls back to the command-line tool, and
    falls back further to None (no RRD support)."""

    def __init__(self):
        """Initialize the rrdSupport class."""
        try:
            rrd_obj = rrdtool
        except NameError:
            try:
                rrd_obj = rrdtool_exe()
            except Exception:
                rrd_obj = None
        super().__init__(rrd_obj)


##################################################################
# INTERNAL, do not use directly
##################################################################
class DummyDiskLock:
    """Dummy lock class that does nothing, used as a placeholder."""

    def close(self):
        """Close the dummy lock."""
        return


def dummy_disk_lock():
    """Return a dummy disk lock.

    Returns:
        DummyDiskLock: A dummy lock object.
    """
    return DummyDiskLock()


def string_quote_join(arglist):
    """Join a list of arguments with quotes.

    Args:
        arglist (list | tuple): List of arguments to join.

    Returns:
        str: Joined arguments as a single string.
    """
    return " ".join(f'"{e}"' for e in arglist)


class rrdtool_exe:
    """Wrapper class around the rrdtool command-line client (binary) and
    is used in place of the rrdtool Python module, if not available.

    It provides also extra functions:
    dump: returns an array of lines with the DB content instead of saving the RRD in an XML file
    restore: allows the restore of a DB
    """

    def __init__(self):
        """Initialize the rrdtool_exe class."""
        self.rrd_bin = (subprocessSupport.iexe_cmd("which rrdtool").split("\n")[0]).strip()

    def create(self, *args):
        """Create a new RRD file.

        Args:
            *args: Arguments for the rrdtool create command.
        """
        cmdline = f"{self.rrd_bin} create {string_quote_join(args)}"
        outstr = subprocessSupport.iexe_cmd(cmdline)  # noqa: F841

    def update(self, *args):
        """Update an RRD file with new data.

        Args:
            *args: Arguments for the rrdtool update command.
        """
        cmdline = f"{self.rrd_bin} update {string_quote_join(args)}"
        outstr = subprocessSupport.iexe_cmd(cmdline)  # noqa: F841

    def info(self, *args):
        """Get information about an RRD file.

        Args:
            *args: Arguments for the rrdtool info command.

        Returns:
            dict: Dictionary of RRD file information.
        """
        cmdline = f"{self.rrd_bin} info {string_quote_join(args)}"
        outstr = subprocessSupport.iexe_cmd(cmdline).split("\n")
        outarr = {}
        for line in outstr:
            if "=" in line:
                linearr = line.split("=")
                outarr[linearr[0].strip()] = linearr[1].strip()
        return outarr

    def dump(self, *args):
        """Dump the contents of an RRD file (running the `rrd_tool dump` command).

        Input is usually just the file name.
        Output is a list of lines, as returned from rrdtool dump.
        This is different from the `dump` method provided by the `rrdtool` package (Python bindings)
        which outputs to a file or stdout.

        Args:
            *args: Arguments for the rrdtool dump command, joined in single string for the command line.
                   Example: `rrdtool dump <file_db_to_dump.rrd> <dst_file>`

        Returns:
            list: List of lines from the rrdtool dump output.
        """
        cmdline = f"{self.rrd_bin} dump {string_quote_join(args)}"
        return subprocessSupport.iexe_cmd(cmdline).split("\n")

    def restore(self, *args):
        """Restore an RRD file from a dump.

        Args:
            *args: Arguments for the rrdtool restore command.
                   Example: `rrdtool restore <src_file> <dst_file.rrd>`
        """
        cmdline = f"{self.rrd_bin} restore {string_quote_join(args)}"
        outstr = subprocessSupport.iexe_cmd(cmdline)  # noqa: F841
        return

    def graph(self, *args):
        """Create a graph from RRD data.

        Args:
            *args: Arguments for the rrdtool graph command.
        """
        cmdline = f"{self.rrd_bin} graph {string_quote_join(args)}"
        outstr = subprocessSupport.iexe_cmd(cmdline)  # noqa: F841
        return

    def fetch(self, *args):
        """Fetch data from an RRD file.

        Args:
            *args: Arguments for the rrdtool fetch command.

        Returns:
            tuple: A tuple containing time info, headers, and data values.
        """
        cmdline = f"{self.rrd_bin} fetch {string_quote_join(args)}"
        outstr = subprocessSupport.iexe_cmd(cmdline).split("\n")
        headers = tuple(outstr.pop(0).split())
        lines = []
        for line in outstr:
            if len(line) == 0:
                continue
            lines.append(tuple(float(i) if i != "-nan" else None for i in line.split()[1:]))
        tstep = int(outstr[2].split(":")[0]) - int(outstr[1].split(":")[0])
        ftime = int(outstr[1].split(":")[0]) - tstep
        ltime = int(outstr[-2].split(":")[0])
        times = (ftime, ltime, tstep)
        return times, headers, lines


def addDataStore(filenamein, filenameout, attrlist):
    """Add a list of data stores to an RRD export file.

    This function adds attributes to the end of an RRD row.

    Args:
        filenamein (str): Filename path of the RRD exported with rrdtool dump.
        filenameout (str): Filename path of the output XML with data stores added.
        attrlist (list): List of data stores to add.
    """
    with open(filenamein) as f, open(filenameout, "w") as out:
        parse = False
        writenDS = False
        for line in f:
            if "<rra>" in line and not writenDS:
                for a in attrlist:
                    out.write("<ds>\n")
                    out.write("<name> %s </name>\n" % a)
                    out.write("<type> GAUGE </type>\n")
                    out.write("<minimal_heartbeat> 1800 </minimal_heartbeat>\n")
                    out.write("<min> NaN </min>\n")
                    out.write("<max> NaN </max>\n")
                    out.write("<!-- PDP Status -->\n")
                    out.write("<last_ds> UNKN </last_ds>\n")
                    out.write("<value> 0 </value>\n")
                    out.write("<unknown_sec> 0 </unknown_sec>\n")
                    out.write("</ds>\n")
                writenDS = True
            if "</cdp_prep>" in line:
                for a in attrlist:
                    out.write("<ds><value> NaN </value>\n")
                    out.write("<unknown_datapoints> 0 </unknown_datapoints></ds>\n")
            if "</database>" in line:
                parse = False
            if parse:
                out.write(line[:-7])
                for a in attrlist:
                    out.write("<v> NaN </v>")
                out.write(line[-7:])
            else:
                out.write(line)
            if "<database>" in line:
                parse = True


def verifyHelper(filename, data_dict, fix_rrd=False, backup=True):
    """Helper function for verifyRRD to check and optionally fix an RRD file.

    Checks one file, prints out errors.
    if `fix_rrd is True`, will attempt to dump out rrd to xml, add the missing attributes, then restore.
    Original file is backed up with time stamp if `backup is True`, obliterated otherwise.

    This function is used by verifyRRD (in Factory and Frontend), invoked during reconfig/upgrade.
    No logging available, output is to stdout/err.

    Args:
        filename (str): Filename of the RRD to check.
        data_dict (dict): Expected dictionary of data sources.
        fix_rrd (bool, optional): Whether to attempt to fix missing attributes. Defaults to False.
        backup (bool, optional): Whether to back up the original RRD file. Defaults to True.

    Returns:
        bool: True if there were problems with the RRD file, False otherwise.
    """
    rrd_problems_found = False
    if not os.path.exists(filename):
        print(f"WARNING: {filename} missing, will be created on restart")
        return rrd_problems_found

    rrd_obj = rrdSupport()
    missing, extra = rrd_obj.verify_rrd(filename, data_dict)

    for attr in extra:
        print(f"ERROR: {filename} has extra attribute {attr}")
        if fix_rrd:
            print("ERROR: fix_rrd cannot fix extra attributes")

    if not fix_rrd:
        for attr in missing:
            print(f"ERROR: {filename} missing attribute {attr}")
        if missing:
            rrd_problems_found = True

    if fix_rrd and missing:
        # TODO: Change this code with the commented version below once Py>=3.10 (parenthesis support in with)
        # with (
        #     tempfile.NamedTemporaryFile(delete=False) as temp_file,
        #     tempfile.NamedTemporaryFile(delete=False) as temp_file2,
        #     tempfile.NamedTemporaryFile(delete=False) as restored_file,
        # ):
        with tempfile.NamedTemporaryFile(delete=False) as temp_file, tempfile.NamedTemporaryFile(
            delete=False
        ) as temp_file2:
            restored_file_name = temp_file2.name + "_restored"
            # Use exe version since dump, restore not available in rrdtool
            dump_obj = rrdtool_exe()
            outstr = dump_obj.dump(filename)
            with open(temp_file.name, "wb") as f:
                for line in outstr:
                    # dump is returning an array of strings decoded w/ utf-8
                    f.write(f"{line}\n".encode(defaults.BINARY_ENCODING_DEFAULT))
            # Make backup if desired
            if backup:
                backup_str = f"{int(time.time())}.backup"
                print(f"Fixing {filename}... (backed up to {filename + backup_str})")
                # Move file to back up location
                shutil.move(filename, filename + backup_str)
            else:
                print(f"Fixing {filename}... (no backup)")
                os.unlink(filename)
            # Add missing attributes
            addDataStore(temp_file.name, temp_file2.name, missing)
            dump_obj.restore(temp_file2.name, restored_file_name)
            shutil.move(restored_file_name, filename)
        os.unlink(temp_file.name)
        os.unlink(temp_file2.name)

    if extra:
        rrd_problems_found = True
    return rrd_problems_found
