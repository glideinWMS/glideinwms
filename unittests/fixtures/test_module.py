# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   This is a mock module for testing import_module

CONSTANT_ONE = "one"
CONSTANT_TWO = "two"
CONSTANT_THREE = "three"


class ClassOne:
    """This is a mock class for testing import_module"""

    def __init__(self):
        pass

    def method_one(self):
        """This is a mock method for testing import_module"""
        return "one"


def function_one():
    """This is a mock function for testing import_module"""
    return "one"


def function_two():
    """This is a mock function for testing import_module"""
    return "two"


def function_three():
    """This is a mock function for testing import_module"""
    return "three"
