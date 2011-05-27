import os
import sys
import unittest

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
    sys.path.append(os.path.join(sys.path[0],"../lib"))
    sys.path.append(os.path.join(sys.path[0],"../factory"))
    sys.path.append(os.path.join(sys.path[0],"../frontend"))

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
