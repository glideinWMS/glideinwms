"""
* Unittests should be placed in glideinWMS/unittests

* Unittests are branch/tag specific.  This allows the unittests to test for
    features that a specific tag or branch has but not other branches/tags.
    Once a feature is merged to head (and/or the current release branch), the
    corresponding unittest should be merged as well.

* Unless there is a compelling reason, the unittest should never call a binary
    outside the glideinWMS codebase.  In order to create accurate tests, all
    inputs should be well defined and "known".  All outputs should be derived
    from the inputs.  If you need output from outside sources, consider
    creating a "worker script" that returns known sample output.  Place the
    "worker script" in glideinWMS/unittests/worker_scripts.

* All unittest file names must follow the following convention:
    test_<your name>.py

    unittest_utils.py contains a function that will trigger all unittests that
    follow the file naming convention.

* All unittests should import unittest_utils.  This will setup the appropriate
    PYTHON_PATH for glideinWMS.  After the unittest import, all other imports
    can proceed as normal without having to specify or append to PYTHON_PATH.

    Note:  NMI will separate the unittest location from the source location.
    It defines $GLIDEINWMS_LOCATION.  unittest_utils.py handles this for you.

* All unittests must have the following code appended:
    def main():
        return runTest(<Unittest Class>)

    if __name__ == '__main__':
        sys.exit(main())

    The main function will be executed both when you directly run the unittest
    and when unittest_utils.runAllTests() funtion is called.  Replace
    <Unittest Class> with the class name.
"""
