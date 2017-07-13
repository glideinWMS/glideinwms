from __future__ import print_function
from builtins import str
import re
import sys
import types
import ConfigParser

class IniError(Exception): pass

def load_ini(ini_path):
    cp = ConfigParser.ConfigParser()
    # check to see if the file exists and is a valid ini file 
    try:
        cp.read(ini_path)
    except Exception as ex:
        raise IniError("Invalid ini file specified.\nInternal Error: %s" % ex)

    return cp

def cp_get(cp, section, option, default, throw_exception=False):
    """
    Helper function for ConfigParser objects which allows setting the default.

    ConfigParser objects throw an exception if one tries to access an option
    which does not exist; this catches the exception and returns the default
    value instead.

    @param cp: ConfigParser object
    @param section: Section of config parser to read
    @param option: Option in section to retrieve
    @param default: Default value if the section/option is not present.
    @param throw_exception: If set to True, overrides the default behavior and 
        throws an exception rather than returning the the value of default
    @returns: Value stored in CP for section/option, or default if it is not
        present.
    """
    if not isinstance(cp, ConfigParser.ConfigParser):
        raise IniError('cp_get called without a proper cp as first arg')

    if not section or not option:  # no use looking any deeper
        if throw_exception:
            raise IniError("Section %s or Option %s not specified" % (section, option))
        return default
    
    try:
        return cp.get(section, option)
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        if throw_exception:
            raise IniError("Section %s or Option %s do not exist" % (section, option))
        return default

def cp_getBoolean(cp, section, option, default=True, throw_exception=False):
    """
    Helper function for ConfigParser objects which allows setting the default.

    If the cp object has a section/option of the proper name, and if that value
    has a 'y' or 't', we assume it's supposed to be true.  Otherwise, if it
    contains a 'n' or 'f', we assume it's supposed to be true.
    
    If neither applies - or the option doesn't exist, return the default

    @param cp: ConfigParser object
    @param section: Section of config parser to read
    @param option: Option in section to retrieve
    @param default: Default value if the section/option is not present.
    @param throw_exception: If set to True, overrides the default behavior and 
        throws an exception rather than returning the the value of default
    @returns: Value stored in CP for section/option, or default if it is not
        present.
    """
    val = str(cp_get(cp, section, option, default, throw_exception=throw_exception)).lower()
    if val.find('t') >= 0 or val.find('y') >= 0 or val.find('1') >= 0:
        return True
    if val.find('f') >= 0 or val.find('n') >= 0 or val.find('0') >= 0:
        return False
    return default

def cp_getInt(cp, section, option, default, throw_exception=False):
    """
    Helper function for ConfigParser objects which allows setting the default.
    Returns an integer, or the default if it can't make one.

    @param cp: ConfigParser object
    @param section: Section of the config parser to read
    @param option: Option in section to retrieve
    @param default: Default value if the section/option is not present.
    @param throw_exception: If set to True, overrides the default behavior and 
        throws an exception rather than returning the the value of default
    @returns: Value stored in the CP for section/option, or default if it is
        not present.
    """
    try:
        return int(str(cp_get(cp, section, option, default, throw_exception=throw_exception)).strip())
    except:
        return default

split_re = re.compile("\s*,?\s*")
def cp_getList(cp, section, option, default, throw_exception=False):
    """
    Helper function for ConfigParser objects which allows setting the default.
    Returns a list, or the default if it can't make one.

    @param cp: ConfigParser object
    @param section: Section of the config parser to read
    @param option: Option in section to retrieve
    @param default: Default value if the section/option is not present.
    @param throw_exception: If set to True, overrides the default behavior and 
        throws an exception rather than returning the the value of default
    @returns: Value stored in the CP for section/option, or default if it is
        not present.
    """
    try:
        results = cp_get(cp, section, option, default, throw_exception=throw_exception)
        if isinstance(results, bytes):
            results = split_re.split(results)
        return results
    except:
        return list(default)


def configContents(cp, stream=sys.stderr):
    for section in cp.sections():
        print("[%s]" % section, file=stream)
        for option in cp.options(section):
            msg = "   %-25s : %s" % (option, cp.get(section, option))
            print(msg, file=stream)
        print(" ", file=stream)