#!/usr/bin/env python

from __future__ import print_function
import os
import sys
import tempfile
import random
import string
import unittest

# We assume that this module is in the unittest directory
module_globals = globals()
unittest_dir = os.path.dirname(os.path.realpath(module_globals["__file__"]))

"""
Check to see if $GLIDEINWMS_LOCATION is defined.  If it is, use that as the
base directory for glideinWMS source code.  If not, then assume the source is
one level above the current directory.  The reason of this is so that a
developer can write and execute unittests without having to setup a special
environment.  However, on nmi, the location of the tests may or may not be
tied to the location of glideinWMS source.  On nmi, the $GLIDEINWMS_LOCATION
will be defined instead.
"""
if "GLIDEINWMS_LOCATION" in os.environ:
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"], "lib"))
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"], "factory"))
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"], "frontend"))
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"], "factory/tools"))
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"], "install"))
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"], "install/services"))
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"], "poolwatcher"))
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"], "tools"))
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"], "tools/lib"))
else:
    sys.path.append(os.path.join(unittest_dir, "../lib"))
    sys.path.append(os.path.join(unittest_dir, "../factory"))
    sys.path.append(os.path.join(unittest_dir, "../frontend"))
    sys.path.append(os.path.join(unittest_dir, "../factory/tools"))
    sys.path.append(os.path.join(unittest_dir, "../install"))
    sys.path.append(os.path.join(unittest_dir, "../install/services"))
    sys.path.append(os.path.join(unittest_dir, "../poolwatcher"))
    sys.path.append(os.path.join(unittest_dir, "../tools"))
    sys.path.append(os.path.join(unittest_dir, "../tools/lib"))

def runTest(cls):
    """
    Given a test class, generate and run a test suite

    @param cls: Test class to use to generate a test suite.  It is assumed
        that the constructor for this class has signature cls(cp, site_name).
        If per_site=False, then the signature is assumed to be cls().
    @type cls: class
    """
    testSuite = unittest.TestLoader().loadTestsFromTestCase(cls)
    testRunner = unittest.TextTestRunner(verbosity=2)
    result = testRunner.run(testSuite)
    return not result.wasSuccessful()

def runAllTests():
    """
    We assume that this particular module is in the unittest directory
    Search the unittest directory for all files matching test_*.py.
    Attempt to import main()
    execute main()

    What kinds of safety checks do we need here?
    """
    def is_test(filename):
        if os.path.isfile(os.path.join(unittest_dir, filename)) and \
                filename.startswith("test_") and filename.endswith(".py"):
            return True
        return False

    test_modules = [f[:-3] for f in os.listdir(unittest_dir) if is_test(f)]
    modules = map(__import__, test_modules)
    for test in modules:
        test.main()

class FakeLogger:
    """
    Super simple logger for the unittests
    """

    def __init__(self):
        pass

    def debug(self, msg, *args):
        """
        Pass a debug message to stderr.
        
        Prints out msg % args.
        
        @param msg: A message string.
        @param args: Arguments which should be evaluated into the message.
        """
        print(str(msg) % args, file=sys.stderr)

    def info(self, msg, *args):
        """
        Pass an info-level message to stderr.
        
        @see: debug
        """
        print(str(msg) % args, file=sys.stderr)

    def warning(self, msg, *args):
        """
        Pass a warning-level message to stderr.

        @see: debug
        """
        print(str(msg) % args, file=sys.stderr)

    def error(self, msg, *args):
        """
        Pass an error message to stderr.

        @see: debug
        """
        print(str(msg) % args, file=sys.stderr)

    def exception(self, msg, *args):
        """
        Pass an exception message to stderr.

        @see: debug
        """
        print(str(msg) % args, file=sys.stderr)

def create_temp_file(file_suffix='', file_prefix='tmp', file_dir='/tmp',
                     text_access=True, write_path_to_file=True):
    fd, path = tempfile.mkstemp(suffix=file_suffix, prefix=file_prefix,
                                dir=file_dir, text=text_access)
    if write_path_to_file:
        os.write(fd, path)
    os.close(fd)
    return path

def create_random_string(length=8):
    char_set = string.ascii_uppercase + string.digits
    return ''.join(random.choice(char_set) for x in range(length))

if __name__ == "__main__":
    runAllTests()
