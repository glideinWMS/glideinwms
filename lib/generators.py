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

import sys
import inspect

from abc import ABC, abstractmethod
from importlib import import_module
from typing import Generic, TypeVar, Optional, List, Mapping

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

    try:
        if not module in _loaded_generators:
            imported_module = import_module(module)
            if module not in _loaded_generators:
                del imported_module
                raise ImportError(f"Module {module} does not export a generator")
    except ImportError as e:
        raise ImportError(f"Failed to import module {module}") from e
    return _loaded_generators[module]


def export_generator(generator: Generator):
    """Make a Generator object available to the genearators module"""

    if not isinstance(generator, Generator):
        raise TypeError("generator must be a Generator object")
    module = inspect.getmodule(inspect.stack()[1][0])
    if not module:
        raise RuntimeError("Failed to get module name")
    _loaded_generators[module.__name__] = generator


class RoundRobinGenerator(Generator[T]):

    def __init__(self, items: List[T]) -> None:
        self._items = items
    
    def generate(self) -> T:
        item = self._items.pop()
        self._items.insert(0, item)
        return item
