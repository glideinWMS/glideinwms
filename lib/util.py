#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This is a collection of utilities functions for file handling and other
#
# Author:
#   Marco Mambelli (some functions are from other modules and hardened)
#

from __future__ import print_function
from builtins import str
import os
import shutil
import cPickle as pickle
import tempfile
import time


#################################
# Dictionary functions
#################################

# imports and global for flattenDict
from collections import Mapping
from operator import add

_FLAG_FIRST = object()

# From http://stackoverflow.com/questions/6027558/flatten-nested-python-dictionaries-compressing-keys
# Much faster than my first version
def flattenDict(d, join=add, lift=lambda x: x):
    """Flexible flattening of a dictionary

    :param d: dictionary to flatten
    :param join: join function for the keys (allows to concatenate strings)
    :param lift: lift function for the keys (allows to create tuples)
    :return: list with flattened dictionary

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
    """Flatten a multi-level dictionary to one level
    The resulting keys are the string concatenation of the original ones
    A separator can be added between keys

    NOTE: Value could be clobbered if there are duplicates in the strings resulting form concatenating keys, e.g.
    {'a':{'b':1}, 'ab':2}
    A separator will not solve the problem if it is a valid character for the keys

    :param in_dict: input dictionary
    :param prefix: prefix for the keys (Default "")
    :param suffix: suffix for the keys (Default "")
    :param sep: separator between keys (Default: "")
    :return: flattened dictionary
    """
    if sep:
        out_list = flattenDict(in_dict, join=lambda a, b: a+sep+b)
    else:
        out_list = flattenDict(in_dict)
    if prefix or suffix:
        out_dict = dict([("%s%s%s" % (prefix, i[0], suffix), i[1]) for i in out_list])
    else:
        out_dict = dict(out_list)
    return out_dict


# First version, not performant
def dict_to_flat_slow(in_dict, prefix="", suffix=""):
    """Flatten a multi-level dictionary to one level
    The resulting keys are the string concatenation of the original ones

    :param in_dict: input dictionary
    :param prefix: prefix for the keys (Default "")
    :param suffix: suffix for the keys (Default "")
    :return: flattened dictionary
    """
    out_dict = {}
    for k, v in list(in_dict.items()):
        if isinstance(v, dict):
            for k2, v2 in list(dict_to_flat(v).items()):
                out_dict["%s%s%s%s" % (prefix, k, k2, suffix)] = v2
        else:
            out_dict["%s%s%s" % (prefix, k, suffix)] = v
    return out_dict


def dict_normalize(in_dict, keys=None, prefix="", suffix="", default=None):
    """Change the keys of a dictionary

    :param in_dict: input dictionary
    :param keys: key list, if None it is using in_dict.keys() (Default: None)
    :param prefix: prefix for the keys (Default "")
    :param suffix: suffix for the keys (Default "")
    :param default: default value passed to get (Default: None)
    :return: normalized dictionary
    """
    out_dict = {}
    if not keys:
        keys = list(in_dict.keys())
    for k in keys:  # glideFactoryMonitoring.getAllJobRanges():
        out_dict["%s%s%s" % (prefix, k, suffix)] = in_dict.get(k, default)
    return out_dict


###################################
# Atomic writing of files
###################################

# Replace atomically the destination with the source
# replace(source, destination)
try:
    # Python 3.3+ provides os.replace which is guaranteed atomic and overwrites existing files
    replace = os.replace  # pylint: disable=no-member
except AttributeError:
    # os.rename is atomic in POSIX systems (e.g. not on Windows or some non local file systems)
    # This post covers at length the problem, including a working solution on Windows
    # http://stupidpythonideas.blogspot.com/2014/07/getting-atomic-writes-right.html
    replace = os.rename


class ExpiredFileException(Exception):
    """The file is too old to be used
    """
    pass


# Avoiding print_function that may be in the built-in
def print_funct(*args, **kwargs):
    """Print function that can be used as mask exception (the print statement cannot be passed as parameter)

    :param args: list of what to print, converted into string and separated by 'sep'
    :param kwargs: keywords, valid keywords: 'sep' separator, default is space
    :return: None
    """
    sep = ' '
    try:
        sep = kwargs['sep']
    except KeyError:
        pass
    print(sep.join([str(i) for i in args]))


def conditional_raise(mask_exceptions):
    """Auxiliary function to handle conditional raising

    :param mask_exceptions: callback function and arguments to use if an exception happens (Default: None)
      The callback function can access the exception via sys.exc_info()
      If a function is not provided, the exception is re-risen
      if provided it is called using mask_exceptions[0](*mask_exceptions[1:])
    :return: None
    """
    if mask_exceptions and hasattr(mask_exceptions[0], '__call__'):
        # protect and report
        mask_exceptions[0](*mask_exceptions[1:])
        return
    raise


def file_pickle_dump(fname, content, tmp_type='PID', mask_exceptions=None, protocol=pickle.HIGHEST_PROTOCOL):
    """Serialize and save content

    To avoid inconsistent content
    @param fname: file storing the serialized content
    @param content: content to serialize
    @param tmp_type: tmp file type as defined in file_get_tmp (Default: PID, .$PID.tmp suffix)
    @param mask_exceptions: callback function and arguments to use if an exception happens (Default: None)
      The callback function can access the exception via sys.exc_info()
      If a function is not provided, the exception is re-risen
      if provided it is called using mask_exceptions[0](*mask_exceptions[1:])
    @param protocol: Pickle protocol to be used (Default: pickle.HIGHEST_PROTOCOL, 2)
    @return: True if the saving was successful, False or an exception otherwise
    """
    tmp_fname = file_get_tmp(fname, tmp_type)
    try:
        with open(tmp_fname, "w") as pfile:
            pickle.dump(content, pfile, protocol)
    except:
        conditional_raise(mask_exceptions)
        return False
    else:
        file_tmp2final(fname, tmp_fname, mask_exceptions=mask_exceptions)
        return True


def file_pickle_load(fname, mask_exceptions=None, default=None, expiration=-1, remove_expired=False, last_time={}):
    """Load a serialized dictionary

    This implementation does not use file locking, it relies on the atomicity of file movement/replacement and deletion
    @param fname: name of the file with the serialized data
    @param mask_exceptions: callback function and arguments to use if an exception happens (Default: None)
      The callback function can access the exception via sys.exc_info()
      If a function is not provided, the exception is re-risen
      if provided it is called using mask_exceptions[0](*mask_exceptions[1:])
    @param default: value returned if the unpickling fails (Default: None)
    @param expiration: input file expiration in seconds (Default: -1)
      -1 file never expires
      0  file always expires after reading
    @param remove_expired: remove expired file (Default: False)
      NOTE: if you remove the obsolete file from the reader you may run into a race condition with undesired effects:
      1. the reader detects the obsolete file, 2. the writer writes a new version, 3. the reader deletes the new version
      This can happen only in cycles where there is an obsolete data file to start with, so the number of data files
      lost because of this is smaller than the occurrences of obsoleted files. When the expiration time is much bigger
      than the loop time of the writer this is generally acceptable.
    @param last_time: last time a file has been used, persistent to keep history (Default: {}, first time called)
    @return: python objects (e.g. data dictionary)
    """
    data = default
    try:
        with open(fname, 'r') as fo:
            if expiration >= 0:
                # check date of file and time
                fname_time = os.path.getmtime(fname)
                current_time = time.time()
                if expiration > 0:
                    if fname_time < current_time - expiration:
                        # if expired raise ExpiredFile (w/ timestamp)
                        raise ExpiredFileException("File %s expired, older then %s seconds (file time: %s)" %
                                                   (fname, expiration, fname_time))
                else:
                    try:
                        if fname_time <= last_time[fname]:
                            # expired
                            raise ExpiredFileException("File %s already used at %s" % (fname, last_time[fname]))
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
            except:
                pass
        conditional_raise(mask_exceptions)
    except:
        conditional_raise(mask_exceptions)
    return data


# One writer, avoid partial write due to code, OS or file system problems
# from factory/glideFactoryMonitoring
#     KEL this exact method is also in glideinFrontendMonitoring.py
# TODO: replace all definitions with this one

def file_tmp2final(fname, tmp_fname=None, bck_fname=None, do_backup=True, mask_exceptions=None):
    """ Complete an atomic write by moving a file new version to its destination.

    If do_backup is True it removes the previous backup and copies the file to bak_fname.
    Moves tmp_fname to fname.

    :param fname: name of the file
    :param tmp_fname: name of the temporary file with the new version of the content (Default: <fname>.tmp)
    :param bck_fname: name of a backup of the old version (Default: <fname>~)
    :param do_backup: do a backup of the old version only if True (Default: True)
    :param mask_exceptions: callback function and arguments to use if an exception happens (Default: None)
      The callback function can access the exception via sys.exc_info()
      If a function is not provided, the exception is re-risen
      if provided it is called using mask_exceptions[0](*mask_exceptions[1:])
    :return: False if the move caused an exception. True otherwise
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
        except:
            pass
    try:
        replace(tmp_fname, fname)
    except:
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
    """Get the name of a temporary file
    Depending on the option chosen this may be unsafe:
    .tmp suffix is OK only if no one else will use this file
    .$PID.tmp is OK if no multithreading is used and there are no safety concerns (name easy to guess, attacks prone)
    tempfile from tempfile.mkstemp() that guarantees uniqueness and safety

    @param fname: original file name
    @param tmp_type: type of temporary file name (Default: None):
       - None (or anything False) - '.tmp' suffix added to the file name (unsafe, may be conflicts if )
       - PID - '.$PID.tmp' suffix added to the file name
       - REAL (or anything else) - real tempfile (unique and safe, using tempfile.mkstemp())
    @return: tamporary file name
    """
    if not tmp_type:
        return fname + ".tmp"
    elif tmp_type == "PID":
        return "%s.%s.tmp" % (fname, os.getpid())
    else:
        f_dir = os.path.dirname(fname)
        f_name = os.path.basename(fname)
        tmp_file, tmp_fname = tempfile.mkstemp(suffix='tmp', prefix=f_name, dir=f_dir)
        # file is open, reopening it is OK
        return tmp_fname


# in classadSupport
# def generate_classad_filename(prefix='gwms_classad'):
