#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Contains the Generator base class and built-in generators
#

import os
import re
import sys

from abc import ABC, abstractmethod
from typing import Generic, List, Mapping, Optional, TypeVar

from glideinwms.lib.util import import_module

sys.path.append("/etc/gwms-frontend/plugin.d")
_loaded_generators = {}

T = TypeVar("T")


class Generator(ABC, Generic[T]):
    def __str__(self):
        return f"{self.__class__.__name__}()"

    def __repr__(self):
        return str(self)

    @abstractmethod
    def generate(self, arguments: Optional[Mapping] = None) -> T:
        pass


def load_generator(module: str) -> Generator:
    """Load a generator from a module

    Args:
        module (str): module that exports a generator

    Raises:
        ImportError: when a `Generator` object cannot be imported from `module`

    Returns:
        Generator: generator object
    """

    module_name = re.sub(r"\.py[co]?$", "", os.path.basename(module))  # Extract module name from path

    try:
        if not module_name in _loaded_generators:
            imported_module = import_module(module)
            if module_name not in _loaded_generators:
                del imported_module
                raise ImportError(f"Module {module} does not export a generator")
    except ImportError as e:
        raise ImportError(f"Failed to import module {module}") from e
    return _loaded_generators[module_name]


def export_generator(generator: Generator):
    """Make a Generator object available to the genearators module"""

    if not isinstance(generator, Generator):
        raise TypeError("generator must be a Generator object")
    _loaded_generators[generator.__module__] = generator


class RoundRobinGenerator(Generator[T]):
    def __init__(self, items: List[T]) -> None:
        self._items = items

    def generate(self) -> T:
        item = self._items.pop()
        self._items.insert(0, item)
        return item
