#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   unit test for glideinwms/lib/util.py


import unittest

import xmlrunner

from glideinwms.lib.util import import_module, safe_boolcomp


class TestUtils(unittest.TestCase):
    def test_safe_boolcomp(self):
        self.assertTrue(safe_boolcomp("True", True))
        self.assertTrue(safe_boolcomp(True, True))
        self.assertTrue(safe_boolcomp("False", False))
        self.assertTrue(safe_boolcomp(False, False))
        self.assertFalse(safe_boolcomp("True", False))
        self.assertFalse(safe_boolcomp(True, False))
        self.assertFalse(safe_boolcomp("False", True))
        self.assertFalse(safe_boolcomp(False, True))
        self.assertFalse(safe_boolcomp("foo", True))
        self.assertFalse(safe_boolcomp("foo", False))

    def test_import_module(self):
        # Test import_module with a file path
        module = import_module("fixtures/testing_module.py")

        # Test import_module with a file name and a search path
        import_module("testing_module.py", ["fixtures"])
        import_module("testing_module.py", "fixtures")

        # Test import_module with a module name and a search path
        import_module("testing_module", ["fixtures"])
        import_module("testing_module", "fixtures")

        # Test import_module with a module path
        import_module("fixtures.testing_module")

        # Validate module contents
        self.assertEqual(module.CONSTANT_ONE, "one")
        self.assertEqual(module.CONSTANT_TWO, "two")
        self.assertEqual(module.CONSTANT_THREE, "three")
        self.assertEqual(module.ClassOne().method_one(), "one")
        self.assertEqual(module.function_one(), "one")
        self.assertEqual(module.function_two(), "two")
        self.assertEqual(module.function_three(), "three")

        # Test import_module with a bad name
        with self.assertRaises(ImportError):
            import_module("bad_name")

        # Test import_module with a bad path
        with self.assertRaises(ValueError):
            import_module("test", "bad_path")

        # Test import_module with a bad list of paths
        with self.assertRaises(ValueError):
            import_module("test", [1])


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
