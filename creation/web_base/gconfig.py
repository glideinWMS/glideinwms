#!main/gwms-python

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Implementation of funtions to interact with glidein_config or the HTCSS configuration in the Glidein
Similar to `add_config_line.source` (shell)

Must support Python 3 and should support also Python 2.7
Using a singleton (`_GLIDEIN_CONFIG`)

A previous implementation by CMS was incomplete and had some bugs (when attributes start w/ another attribute)
https://gitlab.cern.ch/CMSSI/CMSglideinWMSValidation/-/blob/production/export_siteconf_info.py
"""

import argparse
import os
import re
import sys
import tempfile

from datetime import datetime

# Singleton glidein_config dictionary
_GLIDEIN_CONFIG = None
BINARY_ENCODING = "utf_8"  # Use latin_1 instead?


def _log(verbose, msg):
    if verbose:
        #    print(msg, file=sys.stderr)   # SyntaxError in python2, cannot be caught even w/ try/except
        # Python 2 is not supporting `file=`
        sys.stderr.write(msg + "\n")


def force_str(inval):
    """Force string, for compatibility python 2-3

    Args:
        inval: input, str or bytes

    Returns:
        str: string encoded BINARY_ENCODING

    """
    if isinstance(inval, str):
        return inval
    return inval.encode(BINARY_ENCODING)


class GlideinConfigException(Exception):
    """Exception accessing glidein_config"""

    pass


class GlideinConfig:
    """Utility class to use the Glidein glidein_config file in custom scripts in Python

    Singleton. Assuming there is only one glidein_config.
    The file path is provided or taken from the "glidein_config" environment variable
    """

    def __init__(self, file_name=None, cached=True, exit_on_exception=True, verbose=True):
        self.verbose = verbose
        self.exit_on_exception = exit_on_exception
        if file_name is None:
            if "glidein_config" not in os.environ:
                self._log("No glidein_config environment variable present; defaulting value to './glidein_config'")
                self.file_name = "./glidein_config"
            else:
                self.file_name = os.environ["glidein_config"]
        else:
            self.file_name = file_name
        if not os.path.exists(self.file_name):
            self._log("Unable to locate the glidein configuration file %s; failing script." % self.file_name)
            if self.exit_on_exception:
                sys.exit(1)
            else:
                raise GlideinConfigException("Unable to locate the glidein configuration file '%s'" % self.file_name)
        self.cached = cached
        self.dict = {}
        if self.cached:
            self.load()

    def _log(self, msg):
        _log(self.verbose, msg)

    @staticmethod
    def _parseline(line):
        """Parse a line from the glidien_config file

        `#` are comments
        blank characters after the first space (including at the end of the line) are part of the value
        using lstrip(), and values of blanks are rejected
        the shell format is more rigid, spaces also on the left are not tolerated, blank values are returned

        Args:
            line (str): line to parse.

        Returns:
            list: (key, value) or None if the line was a comment or invalid
        """
        line = line.lstrip()
        if line.startswith("#"):
            return None
        info = line.split(" ", 1)
        if len(info) != 2 or info[1].strip() == "":
            return None
        return info

    def load(self):
        """Load the content of glidein_config in the cache dictionary (self.dict)"""
        new_dict = {}
        try:
            with open(self.file_name) as f:
                for line in f:
                    info = self._parseline(line)
                    if info is None:
                        continue
                    new_dict[info[0]] = info[1]
        except OSError:
            self._log("Unable read the glidein configuration file %s; failing script." % self.file_name)
            if self.exit_on_exception:
                sys.exit(1)
            else:
                raise GlideinConfigException("Unable to read the glidein configuration file '%s'" % self.file_name)
        self.dict = new_dict
        return new_dict

    def get(self, key, default=None):
        if self.cached:
            return self.dict.get(key, default)
        return self._get(key, default)

    def _get(self, key, default=None):
        try:
            with open(self.file_name) as f:
                ret = None
                # loop through all values to get the last occurrence. Alternatively use readlines and read in reverse
                for line in f:
                    info = self._parseline(line)
                    if info is not None and info[0] == key:
                        ret = info[1]
                if ret is not None:
                    return ret
        except OSError:
            self._log("Unable read the glidein configuration file %s; failing script." % self.file_name)
            if self.exit_on_exception:
                sys.exit(1)
            else:
                raise GlideinConfigException("Unable to read the glidein configuration file '%s'" % self.file_name)
        return default

    @staticmethod
    def get_config(file_name=None, cached=True):
        global _GLIDEIN_CONFIG

        if _GLIDEIN_CONFIG is not None:
            if cached == _GLIDEIN_CONFIG.cached and (file_name is None or file_name == _GLIDEIN_CONFIG.file_name):
                return _GLIDEIN_CONFIG
            else:
                # writing modified values if write on close
                pass
        _GLIDEIN_CONFIG = GlideinConfig(file_name, cached)
        return _GLIDEIN_CONFIG

    def add(self, key, value):
        if key is None or value is None:
            self._log("Invalid glidein configuration specified (name=%s; value=%s)" % (key, value))
            return
        tmp_fname = "%s.%s.tmp" % (self.file_name, os.getpid())  # same temp name structure as shell scripts
        try:
            with open(self.file_name) as fd:
                outlines = []
                linestart = "%s " % key
                for line in fd.readlines():
                    if not line.startswith(linestart):
                        outlines.append(line)
                outlines.append("%s %s\n" % (key, value))
            # conf_dir, conf_file = os.path.split(self.file_name)
            # with tempfile.NamedTemporaryFile(dir=conf_dir, prefix=conf_file, delete=False) as tempfd:
            with open(tmp_fname) as temp_fd:
                temp_fd.writelines([l.encode(BINARY_ENCODING) for l in outlines])
                temp_fd.flush()
                os.fsync(temp_fd.fileno())
            os.rename(tmp_fname, self.file_name)  # if only Py3.3+ os.replace(tmp_fname, self.file_name)
        except:
            # Make sure the temp file is deleted
            # Python 3.8+   my_file.unlink(missing_ok=True)
            try:
                os.unlink(tmp_fname)
            except OSError:
                pass
            self._log("Unable write %s to the glidein configuration file %s" % (key, self.file_name))
            if self.exit_on_exception:
                sys.exit(1)
            else:
                raise GlideinConfigException(
                    "Unable write %s to the glidein configuration file %s" % (key, self.file_name)
                )
        self._log("Set glidein config value of %s to %s." % (key, value))

    def add_safe(self, key, value):
        # TODO: add implementation w/ NFS safe lock mechanism like in shell
        self.add(key, value)


def gconfig_reload(fname=None):
    """Load all glidein_config file in a dictionary,
    parse from start to end and overwrite if repeat keys are encountered.
    Reload the dictionary also for cached dictionaries.

    Args:
        fname (str): path of the glidein_config file

    Returns:
        dict: key, value dictionary, freshly reloaded from file
    """
    return GlideinConfig.get_config(cached=True).load()


def gconfig_get(key, fname=None, default=None):
    # used stored cached dictionary
    return GlideinConfig.get_config(fname, cached=True).get(key, default)


def gconfig_add(key, value, fname=None):
    return GlideinConfig.get_config(fname, cached=True).add(key, value)


def add_config_line(key, value, fname=None):
    return gconfig_add(key, value, fname)


def gconfig_add_safe(key, value, fname=None):
    return GlideinConfig.get_config(fname, cached=True).add_safe(key, value)


# NFS safe file locking. TODO: implement for add_safe, see shell version in add_config_line.source
def _lock_file():
    pass


def _unlock_file():
    pass


def add_condor_config_var(name, value, kind="C", publish=True, condor_name=None, verbose=True, conf_fname=None):
    """Write a veriable to the HTCSS variables list (to include it in the HTCSS configuration)

    Args:
        name (str): attribute name
        value (str): attribute value
        kind: attribute type C (HTCondor expression), S (string), I (integer) (default:C)
        publish (bool): True to publish the attribute to HTCSS (default:True)
        condor_name (str): attribute name (if different from name) (default:None, same as name)
        verbose (bool): print extra messages to stderr if True (default:True)
        conf_fname (str): path of the glidein_config file (default:None, env['glidein_config'])

    Returns:
        True if successful, False otherwise
    """
    if name is None or value is None:
        _log(verbose, "Invalid condor configuration specified (name=%s; value=%s" % (str(name), str(value)))
        return False

    fname = gconfig_get("CONDOR_VARS_FILE", conf_fname)
    if fname is None:
        _log(verbose, "Warning: Missing condor vars file from configuration; ignoring (%s=%s)" % (name, value))
        return False

    has_whitespace = re.compile(r"\s")
    if has_whitespace.search(name):
        _log(verbose, "Ignoring specified name as it contains whitespace (name=%s)." % name)
        return False
    if has_whitespace.search(value):
        # TODO: Values can have whitespace in general (they are quotes)
        _log(verbose, "Ignoring specified value as it contains whitespace (value=%s)." % name)
        return False
    if condor_name and has_whitespace.search(condor_name):
        _log(
            verbose,
            "Ignoring specified HTCondor variable name as it contains whitespace (condor_name=%s)." % condor_name,
        )
        return False

    if condor_name is None:
        condor_name = name
    if publish:
        exp_condor = "Y"
    else:
        exp_condor = "N"

    vars_dir, vars_file = os.path.split(fname)
    tempfd = tempfile.NamedTemporaryFile(dir=vars_dir, prefix=vars_file, delete=False)
    try:
        with open(fname) as fd:
            for line in fd:
                if line.startswith("%s " % name):
                    continue
                tempfd.write(line.encode("utf8"))
            tempfd.write(("%s %s %s %s N %s -\n" % (name, kind, value, condor_name, exp_condor)).encode())
    except:
        _log(verbose, "Failed to read and update the condor variables file")
        os.unlink(tempfd.name)
        raise
    tempfd.close()
    fd.close()
    os.rename(tempfd.name, fname)

    _log(verbose, "Setting value of %s to %s." % (name, value))
    return True


def _complete_args(mandatory, args, defaults):
    """Auxiliary finction to facilitate variable arguments

    Args:
        mandatory (int): number of mandatory arguments
        args (list): arguments from the command line (list of str)
        defaults (list): default values, use None for the mandatory arguments

    Returns:
        list: modified `args`, with booleans when needed and completed
    """
    i = len(args)
    total = len(defaults)
    if i > total or i < mandatory:
        raise ValueError
    for j in range(i):
        if isinstance(defaults[j], bool):
            if args[j].upper() == "TRUE" or args[j].upper() == "T":
                args[j] = True
            else:
                args[j] = False
    while i < total:
        args.append(defaults[i])
        i += 1
    return args


def _get_status_header(fname, status):
    """Return the status header lines

    Args:
        fname (str): program name/ID
        status(str): program status, OK or ERROR

    Returns:
        list: list of header lines (str)
    """
    return [
        '<?xml version="1.0"?>',
        '<OSGTestResult id="%s" version="4.3.1">' % fname,
        "  <result>",
        "    <status>%s</status>" % status,
    ]


def _get_status_metric(name, value, timestamp):
    """Get a formatted string with a status metric

    Args:
        name (str): metric name
        value (str): metric value
        timestamp (str): timestamp string

    Returns:
        str: formatted status metric
    """
    return '    <metric name="%s" ts="%s" uri="local">%s</metric>' % (name, timestamp, value)


def _get_status_footer(error_detail=None):
    """Return the status footer lines

    Args:
        error_detail (str, None): error detail information

    Returns:
        list: list of status lines (str)
    """
    out = ["  </result>"]
    if error_detail:
        out += ["  <detail>", "    %s" % error_detail, "  </detail>"]
    out.append("</OSGTestResult>")
    return out


def status_report(name, success, error_msg=None, error_detail=None, parameters=None, fname="otrb_output.xml"):
    """Write an XML status report to "otrb_output.xml" like error_gen.sh

    Same as invoking (with all parameters quoted to preserve spaces):
        error_gen -ok key1 val1 key2 val2 ...
        error_gen -error error_msg error_detail key1 val1 key2 val2 ...

    Args:
        name (str): ID, script invoking the report
        success (bool): True for OK/-ok (script successful), False for ERROR/-error (reporting failure)
        error_msg (str, None): error message, if any
        error_detail (str, None): error detail, if any
        parameters (dict): status parameters
        fname (str): path of the status file
    """
    my_date = datetime.now()
    timestamp = my_date.strftime("%Y-%m-%dT%H:%M:%S%:z")
    if success:
        out = _get_status_header(name, "OK")
    else:
        out = _get_status_header(name, "ERROR")
        out.append(_get_status_metric("failure", error_msg, timestamp))
    if parameters:
        for k, v in parameters:
            out.append(_get_status_metric(k, v, timestamp))
    out += _get_status_footer(error_detail)
    with open(fname, "w") as f:
        f.writelines(["%s\n" % i for i in out])


def main():
    valid_commands = ["get", "add", "add_safe", "add_config_line", "add_condor_config_var"]
    # Check if invoked by glidein_startup.sh at setup
    if sys.argv[1] not in valid_commands and os.path.exists(sys.argv[1]):
        # assuming that the script was called with glidien_config as parameter if it is a file and there is error_gen
        error_gen = gconfig_get("ERROR_GEN_PATH", sys.argv[1])
        if error_gen:
            status_report("gconfig.py", True)
            sys.exit(0)
    # Help text
    description = "Pure Python implementation of gconfig utils (add_config_line.source).\nIt expects 'glidein_config' to be defined in the environment."
    usage = "gconfig [-h] command [args]"
    epilog = (
        "commands:\n"
        "  get key [glidein_config_file_name] [default_value]\n"
        "  add key value [glidein_config_file_name]\n"
        "  add_safe key value [glidein_config_file_name]\n"
        "  add_config_line key value [glidein_config_file_name] (same as add)\n"
        "  add_condor_config_var name value [kind=C] [publish=True] [condor_name] [verbose=True] [glidein_config_file_name]"
    )
    # Handle command line arguments
    parser = argparse.ArgumentParser()
    parser.description = description
    parser.usage = usage
    parser.epilog = epilog
    parser.formatter_class = argparse.RawTextHelpFormatter
    parser.add_argument("command", help="one of the commands listed below")
    args = parser.parse_args(sys.argv[1:2])
    function_args = sys.argv[2:]
    out = None
    try:
        # Pylint on GH is not understanding the expansion of the output of _complete_args() E1120,no-value-for-parameter
        # pylint: disable=no-value-for-parameter
        if args.command == "get":
            out = gconfig_get(*_complete_args(1, function_args, [None, None, None]))
            print(out)
        elif args.command == "add" or args.command == "add_config_line":
            gconfig_add(*_complete_args(2, function_args, [None, None, None]))
        elif args.command == "add_safe":
            gconfig_add_safe(*_complete_args(2, function_args, [None, None, None]))
        elif args.command == "add_condor_config_var":
            add_condor_config_var(*_complete_args(2, function_args, [None, None, "C", True, None, True, None]))
        else:
            print("error: command not implemented")
            sys.exit(1)
        # pylint: enable=no-value-for-parameter
    except ValueError:
        print("error: invalid arguments '%s'" % (function_args,))
        sys.exit(1)


if __name__ == "__main__":
    main()
