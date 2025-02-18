#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This is a collection of utilities functions for file handling and other
"""

import contextlib
import os
import pickle
import re
import shutil
import string
import subprocess
import sys
import tempfile
import time

from base64 import b32encode

# imports and global for flattenDict
from collections.abc import Mapping

# imports for hash_nc
from hashlib import md5
from importlib.machinery import PathFinder
from importlib.util import module_from_spec, spec_from_file_location
from operator import add

from glideinwms.lib.defaults import BINARY_ENCODING_ASCII, force_bytes

#################################
# Dictionary functions
#################################


_FLAG_FIRST = object()

HOOK_PRE_RECONFIG_DIRNAME = "hooks.reconfig.pre"
HOOK_POST_RECONFIG_DIRNAME = "hooks.reconfig.post"


# From http://stackoverflow.com/questions/6027558/flatten-nested-python-dictionaries-compressing-keys
# Much faster than my first version
def flattenDict(d, join=add, lift=lambda x: x):
    """Flexible flattening of a dictionary.

    Args:
        d (dict): Dictionary to flatten.
        join (function): join function for the keys (allows to concatenate strings). Default is `add`.
        lift (function): lift function for the keys (allows to create tuples). Default is identity.

    Returns:
        list: List with flattened dictionary.

    >>> testData = {
        'a':1,
        'b':2,
        'c':{
            'aa':11,
            'bb':22,
            'cc':{
                'aaa':111
            }
        }
    }
    >>> from pprint import pprint as pp

    >>> pp(dict( flattenDict(testData, lift=lambda x:(x,)) ))
    {('a',): 1,
     ('b',): 2,
     ('c', 'aa'): 11,
     ('c', 'bb'): 22,
     ('c', 'cc', 'aaa'): 111}

    >>> pp(dict( flattenDict(testData, join=lambda a,b:a+'_'+b) ))
    {'a': 1, 'b': 2, 'c_aa': 11, 'c_bb': 22, 'c_cc_aaa': 111}

    >>> pp(dict( (v,k) for k,v in flattenDict(testData, lift=hash, join=lambda a,b:hash((a,b))) ))
    {1: 12416037344,
     2: 12544037731,
     11: 5470935132935744593,
     22: 4885734186131977315,
     111: 3461911260025554326}
    """
    results = []

    def visit(subdict, results, partialKey):
        for k, v in list(subdict.items()):
            newKey = lift(k) if partialKey == _FLAG_FIRST else join(partialKey, lift(k))
            if isinstance(v, Mapping):
                visit(v, results, newKey)
            else:
                results.append((newKey, v))

    visit(d, results, _FLAG_FIRST)
    return results


def dict_to_flat(in_dict, prefix="", suffix="", sep=""):
    """Flatten a multi-level dictionary to one level.

    The resulting keys are the string concatenation of the original ones.
    A separator can be added between keys.

    Notes:
        Value could be clobbered if there are duplicates in the strings resulting from concatenating keys, e.g.
        `{'a':{'b':1}, 'ab':2}`.
        A separator will not solve the problem if it is a valid character for the keys.

    Args:
        in_dict (dict): Input dictionary.
        prefix (str, optional): Prefix for the keys. Default is "".
        suffix (str, optional): Suffix for the keys. Default is "".
        sep (str, optional): Separator between keys. Default is "".

    Returns:
        str: Flattened dictionary.
    """
    if sep:
        out_list = flattenDict(in_dict, join=lambda a, b: a + sep + b)
    else:
        out_list = flattenDict(in_dict)
    if prefix or suffix:
        out_dict = {f"{prefix}{i[0]}{suffix}": i[1] for i in out_list}
    else:
        out_dict = dict(out_list)
    return out_dict


# First version, not performant
def dict_to_flat_slow(in_dict, prefix="", suffix=""):
    """Flatten a multi-level dictionary to one level.

    The resulting keys are the string concatenation of the original ones.

    Args:
        in_dict (dict): Input dictionary.
        prefix (str, optional): Prefix for the keys. Default is "".
        suffix (str, optional): Suffix for the keys. Default is "".

    Returns:
        str: Flattened dictionary.
    """
    out_dict = {}
    for k, v in list(in_dict.items()):
        if isinstance(v, dict):
            for k2, v2 in list(dict_to_flat(v).items()):
                out_dict[f"{prefix}{k}{k2}{suffix}"] = v2
        else:
            out_dict[f"{prefix}{k}{suffix}"] = v
    return out_dict


def dict_normalize(in_dict, keys=None, prefix="", suffix="", default=None):
    """Change the keys of a dictionary.

    Args:
        in_dict (dict): Input dictionary.
        keys (list, optional): Keys list, if None it is using `in_dict.keys()`. Default is None.
        prefix (str, optional): Prefix for the keys. Default is "".
        suffix (str, optional): Suffix for the keys. Default is "".
        default (Object, optional): Default value passed to get(). Default is None.

    Returns:
        dict: Normalized dictionary.

    """
    out_dict = {}
    if not keys:
        keys = list(in_dict.keys())
    for k in keys:  # glideFactoryMonitoring.getAllJobRanges():
        out_dict[f"{prefix}{k}{suffix}"] = in_dict.get(k, default)
    return out_dict


###################################
# Atomic writing of files
###################################

# TODO: to remove this comment block after all is OK (MM)
# Using Python >=3.6 as of 2023
# os.replace() is available, leaving this commented to make sure no other module is importing replace() from util
#
# Replace atomically the destination with the source
# replace(source, destination)
# try:
#     # Python 3.3+ provides os.replace which is guaranteed atomic and overwrites existing files
#     replace = os.replace  # pylint: disable=no-member
# except AttributeError:
#     # os.rename is atomic in POSIX systems (e.g. not on Windows or some non local file systems)
#     # This post covers at length the problem, including a working solution on Windows
#     # http://stupidpythonideas.blogspot.com/2014/07/getting-atomic-writes-right.html
#     replace = os.rename


class ExpiredFileException(Exception):
    """The file is too old to be used."""

    pass


# Avoiding print_function that may be in the built-in
def print_funct(*args, **kwargs):
    """Print function that can be used as mask exception (the print statement cannot be passed as parameter).

    Args:
        *args: list of what to print, converted into string and separated by `sep`.
        **kwargs: keywords, valid keyword: 'sep' separator. Everything else is ignored. Default 'sep' is space.
    """
    sep = " "
    try:
        sep = kwargs["sep"]
    except KeyError:
        pass
    print(sep.join([str(i) for i in args]))


# pylint: disable=misplaced-bare-raise
def conditional_raise(mask_exceptions):
    """Auxiliary function to handle conditional raising.

    Args:
        mask_exceptions: callback function and arguments to use if an exception happens (Default: None).
            The callback function can access the exception via sys.exc_info().
            If a function is not provided, the exception is re-risen,
            if provided it is called using `mask_exceptions[0](*mask_exceptions[1:])`.
    Returns:
        None
    """
    if mask_exceptions and hasattr(mask_exceptions[0], "__call__"):
        # protect and report
        mask_exceptions[0](*mask_exceptions[1:])
        return
    raise


# pylint: enable=misplaced-bare-raise


def file_pickle_dump(fname, content, tmp_type="PID", mask_exceptions=None, protocol=pickle.HIGHEST_PROTOCOL):
    """Serialize and save content.

    To avoid inconsistent content.

    Args:
        fname(str): file storing the serialized content.
        content: content to serialize.
        tmp_type(str, optional): tmp file type as defined in file_get_tmp (Default: PID, .$PID.tmp suffix).
        mask_exceptions(list, optional): callback function and arguments to use if an exception happens (Default: None).
          The callback function can access the exception via sys.exc_info().
          If a function is not provided, the exception is re-risen,
          if provided it is called using mask_exceptions[0](*mask_exceptions[1:]).
        protocol: Pickle protocol to be used (Default: pickle.HIGHEST_PROTOCOL, 5 as of py3.8).

    Returns:
        bool: True if the saving was successful, False or an exception otherwise.
    """
    tmp_fname = file_get_tmp(fname, tmp_type)
    try:
        with open(tmp_fname, "wb") as pfile:
            pickle.dump(content, pfile, protocol)
    except Exception:
        conditional_raise(mask_exceptions)
        return False
    else:
        file_tmp2final(fname, tmp_fname, mask_exceptions=mask_exceptions)
        return True


def file_pickle_load(fname, mask_exceptions=None, default=None, expiration=-1, remove_expired=False, last_time={}):
    """Load a serialized dictionary

    This implementation does not use file locking, it relies on the atomicity of file movement/replacement and deletion

    Args:
        fname: name of the file with the serialized data
        mask_exceptions: callback function and arguments to use if an exception happens (Default: None)
          The callback function can access the exception via sys.exc_info()
          If a function is not provided, the exception is re-risen
          if provided it is called using mask_exceptions[0](*mask_exceptions[1:])
        default: value returned if the unpickling fails (Default: None)
        expiration (int): input file expiration in seconds (Default: -1)
          -1 file never expires
          0  file always expires after reading
        remove_expired (bool): remove expired file (Default: False)
          NOTE: if you remove the obsolete file from the reader you may run into a race condition with undesired effects:
          1. the reader detects the obsolete file, 2. the writer writes a new version, 3. the reader deletes the new version
          This can happen only in cycles where there is an obsolete data file to start with, so the number of data files
          lost because of this is smaller than the occurrences of obsoleted files. When the expiration time is much bigger
          than the loop time of the writer this is generally acceptable.
        last_time (dict): last time a file has been used, persistent to keep history (Default: {}, first time called)
          Dictionary file_name->time

    Returns:
        Object: python objects (e.g. data dictionary)
    """
    data = default
    try:
        with open(fname, "rb") as fo:
            if expiration >= 0:
                # check date of file and time
                fname_time = os.path.getmtime(fname)
                current_time = time.time()
                if expiration > 0:
                    if fname_time < current_time - expiration:
                        # if expired raise ExpiredFile (w/ timestamp)
                        raise ExpiredFileException(
                            f"File {fname} expired, older then {expiration} seconds (file time: {fname_time})"
                        )
                else:
                    try:
                        if fname_time <= last_time[fname]:
                            # expired
                            raise ExpiredFileException(f"File {fname} already used at {last_time[fname]}")
                    except KeyError:
                        pass
                    last_time[fname] = fname_time
            data = pickle.load(fo)
    except ExpiredFileException:
        if remove_expired:
            # There may be a race removing a file updated in the mean time but
            # the file produced at the next iteration will be used
            try:
                os.remove(fname)
            except OSError:
                pass
        conditional_raise(mask_exceptions)
    except Exception:
        conditional_raise(mask_exceptions)
    return data


# One writer, avoid partial write due to code, OS or file system problems


def file_tmp2final(
    fname, tmp_fname=None, bck_fname=None, do_backup=True, mask_exceptions=None, log=None, do_print=False
):
    """Complete an atomic write by moving a file new version to its destination.

    If do_backup is True it removes the previous backup and copies the file to bak_fname.
    Moves tmp_fname to fname.

    Args:
        fname(str): name of the file
        tmp_fname(str|None): name of the temporary file with the new version of the content (Default: <fname>.tmp).
        bck_fname(str|None): name of a backup of the old version (Default: <fname>~).
        do_backup(bool): do a backup of the old version only if True (Default: True).
        mask_exceptions: callback function and arguments to use if an exception happens (Default: None).
            The callback function can access the exception via sys.exc_info().
            If a function is not provided, the exception is re-risen.
            if provided it is called using `mask_exceptions[0](*mask_exceptions[1:])`.
        log:
        do_print:

    Returns:
        bool: False if the move caused an exception. True otherwise.
    """
    if tmp_fname is None:
        tmp_fname = fname + ".tmp"
    if do_backup:
        if bck_fname is None:
            bck_fname = fname + "~"
        # Previous version had os.remove() followed by os.rename() both in their own try block
        # That solution could leave without fname if the program is interrupted right after backup
        try:
            shutil.copy2(fname, bck_fname)
        except Exception:
            pass
    try:
        os.replace(tmp_fname, fname)
    except Exception:
        # print "Failed renaming %s into %s" % (tmp_fname, fname)
        conditional_raise(mask_exceptions)
        return False
    return True


# If there are multiple writer it is important to have a unique tmp file name so that there are not
# overlapping writes (inconsistent version)
# A locking mechanism may be necessary if we want to avoid missing a version (do one write at the time and do not
# loose any previous write)
# TODO: currently many temporary files are in the work-dir and owned by only one process, which means that a locally
# unique name is sufficient. If this changes or if wor-dir is not on a local (POSIX) file system, temporary files
# may have to be moved to a shared place (/tmp) and handled more properly
def file_get_tmp(fname=None, tmp_type=None):
    """Get the name of a temporary file.

    Depending on the option chosen this may be unsafe:
    .tmp suffix is OK only if no one else will use this file.
    .$PID.tmp is OK if no multithreading is used and there are no safety concerns (name easy to guess, attacks prone).
    `tempfile` from `tempfile.mkstemp()` that guarantees uniqueness and safety.

    Args:
        fname (str, optional): Original file name.
        tmp_type (str, optional): Type of temporary file name. Default is ".tmp" suffix (None). Available types:
                   - None (or anything False) - '.tmp' suffix added to the file name (unsafe, may be conflicts if ).
                   - PID - '.$PID.tmp' suffix added to the file name.
                   - REAL (or anything else) - real tempfile (unique and safe, using `tempfile.mkstemp()`).

    Returns:
        str: Name of temporary file.

    """
    if not tmp_type:
        return fname + ".tmp"
    elif tmp_type == "PID":
        return f"{fname}.{os.getpid()}.tmp"
    else:
        f_dir = os.path.dirname(fname)
        f_name = os.path.basename(fname)
        tmp_file, tmp_fname = tempfile.mkstemp(suffix="tmp", prefix=f_name, dir=f_dir)
        # file is open, reopening it is OK
        return tmp_fname


# in classadSupport
# def generate_classad_filename(prefix='gwms_classad'):


def safe_boolcomp(value, expected):
    """Safely do a boolean comparison.

    This works even if the value you wantto compare is a string.

    Args:
        value: what you want to safely compare.
        expected (bool): What you want to compare `value` with.

    Returns:
        bool: True if str(value).lower() is True.
    """
    return str(value).lower() == str(expected).lower()


# DEV NOTE: merging of creation.lib.CWParamDict.is_true() and factory.tools.OSG_autoconf.is_true()
#   the first one required the argument to be a string. OK to drop that
def is_true(value):
    """Case-insensitive "True" string parsing helper.
    Return True for true (case-insensitive string representation matching), False otherwise.

    Args:
        value: argument to evaluate as True or False. Can be any type.

    Returns:
        bool: True if the string representation of value is "true"
    """

    return str(value).lower() == "true"


def str2bool(val):
    """Convert u"True" or u"False" to boolean or raise ValueError."""
    if val not in ["True", "False"]:
        # Not using ValueError intentionally: all config errors are RuntimeError
        raise RuntimeError("Found %s instead of 'True' of 'False'" % val)
    elif val == "True":
        return True
    else:
        return False


def handle_hooks(basedir, script_dir):
    """The function itaretes over the script_dir directory and executes any script found there."""
    dirname = os.path.join(basedir, script_dir)
    if not os.path.isdir(dirname):
        return
    for fname in sorted(os.listdir(dirname)):
        script_name = os.path.join(dirname, fname)
        if os.path.isfile(script_name) and os.access(script_name, os.X_OK):
            print("\nExecuting reconfigure hook: " + script_name)
            subprocess.call(script_name)


def hash_nc(data, len=None):
    """Returns a non-cryptographic MD5 hash encoded in base32.

    Args:
        data (AnyStr): Data to hash.
        len (int, optional): Hash length. Defaults to None.

    Returns:
        str: Hash.
    """
    # TODO set md5 usedforsecurity to False when updating to Python 3.9
    out = b32encode(md5(force_bytes(data)).digest()).decode(BINARY_ENCODING_ASCII)
    if len:
        out = out[:len]
    return out


def chmod(*args, **kwargs):
    """Wrapper for os.chmod that supresses PermissionError exceptions.

    Args:
        *args: Positional arguments to pass to os.chmod.
        **kwargs: Keyword arguments to pass to os.chmod.

    Returns:
        None
    """
    with contextlib.suppress(PermissionError):
        os.chmod(*args, **kwargs)


############################################################
# only allow simple strings
def is_str_safe(s):
    for c in s:
        if c not in ("._-@" + string.ascii_letters + string.digits):
            return False
    return True


def import_module(module, search_path=None):
    """Import a module by name or path.

    Args:
        module (str): Module name, module path, file name, or file path.
        search_path (str or list of str, optional): Search path for the module. Defaults to None.

    Raises:
        ValueError: Invalid search_path.
        ImportError: Failed to import the module.

    Returns:
        module: Imported module.
    """

    if search_path:
        if isinstance(search_path, str):
            search_path = [search_path]
        if not isinstance(search_path, list):
            raise ValueError("search_path must be a string or list of strings")
        for path in search_path:
            if not os.path.isdir(path):
                raise ValueError(f"Invalid search_path: '{path}'")

    try:
        name = re.sub(
            r"\.py[co]?$", "", os.path.basename(module)
        )  # Remove eventual .py/.pyc/.pyo extension from the file name (if a file is used)
        if os.path.isfile(module):
            spec = spec_from_file_location(name, module)
        else:
            if "." in name:
                # Break down the module path into its components and update the search path
                components = name.split(".")
                name = components[-1]
                path = os.path.join(*components[:-1])
                search_path = search_path or sys.path
                new_search_paths = []
                for p in search_path:
                    extended_p = os.path.join(p, path)
                    if os.path.isdir(extended_p):
                        new_search_paths.append(extended_p)
                search_path += new_search_paths
            spec = PathFinder.find_spec(name, search_path)
        imported_module = module_from_spec(spec)  # type: ignore[attr-defined]
        spec.loader.exec_module(imported_module)  # type: ignore[member-defined]
    except Exception as err:
        raise ImportError(f"Failed to import module {module}") from err

    return imported_module
