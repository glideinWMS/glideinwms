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
#   Marco Mambelli (collecting functions in other modules and hardening them)
#

import os
import shutil


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
        for k, v in subdict.items():
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
    for k, v in in_dict.items():
        if isinstance(v, dict):
            for k2, v2 in dict_to_flat(v).items():
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
        keys = in_dict.keys()
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


# One writer, avoid partial write due to code, OS or file system problems
# from factory/glideFactoryMonitoring
#     KEL this exact method is also in glideinFrontendMonitoring.py
# TODO: replace all definitions with this one
# TODO: raise exception instead of just printout

def file_tmp2final(fname, tmp_fname=None, bck_fname=None, do_backup=True):
    """ Complete an atomic write by moving a file new version to its destination.

    If do_backup is True it removes the previous backup and copies the file to bak_fname.
    Moves tmp_fname to fname.

    :param fname: name of the file
    :param tmp_fname: name of the temporary file with the new version of the content (Default: <fname>.tmp)
    :param bck_fname: name of a backup of the old version (Default: <fname>~)
    :param do_backup: do a backup of the old version only if True (Default: True)
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
        print "Failed renaming %s into %s" % (tmp_fname, fname)
        return False
    return True


# If there are multiple writer it is important to have a unique tmp file name so that there are not
# overlapping writes (inconsistent version)
# A locking mechanism may be necessary if we want to avoid missing a version (do one write at the time and do not
# loose any previous write)
# TODO: currently many temporary files are in the work-dir and owned by only one process, which means that a locally
# unique name is sufficient. If this changes or if wor-dir is not on a local (POSIX) file system, temporary files
# may have to be moved to a shared place (/tmp) and handled more properly
def file_get_tmp():
    pass


# in classadSupport
# def generate_classad_filename(prefix='gwms_classad'):
