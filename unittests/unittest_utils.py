import os
import sys
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
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"],"lib"))
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"],"factory"))
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"],"frontend"))
else:
    sys.path.append(os.path.join(unittest_dir,"../lib"))
    sys.path.append(os.path.join(unittest_dir,"../factory"))
    sys.path.append(os.path.join(unittest_dir,"../frontend"))

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
