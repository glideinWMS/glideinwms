import os
import sys
import unittest

if "GLIDEINWMS_LOCATION" in os.environ:
    sys.path.append(os.path.join(os.environ["GLIDEINWMS_LOCATION"],"lib"))
else:
    sys.path.append(os.path.join(sys.path[0],"../lib"))

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
