#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module contains the Generator base class and built-in generators
"""


import inspect
import os
import re
import sys

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Generic, Mapping, Optional, Type, TypeVar

from glideinwms.lib.defaults import PLUGINS_DIR
from glideinwms.lib.util import hash_nc, import_module

sys.path.append(PLUGINS_DIR)
_loaded_generators = {}
_generator_instances = defaultdict(dict)

T = TypeVar("T")


class GeneratorError(Exception):
    """Base class for generator exceptions"""


class Generator(ABC, Generic[T]):
    """Base class for generators"""

    def __init__(self, context: Optional[Mapping] = None):
        self.context = context

    def __str__(self):
        return f"{self.__class__.__name__}()"

    def __repr__(self):
        return str(self)

    @abstractmethod
    def generate(self, **kwargs) -> T:
        """
        Generate an item using the context and keyword arguments
        """


def load_generator(module: str, context: Optional[Mapping] = None) -> Generator:
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
        if module_name not in _loaded_generators:
            imported_module = import_module(module)
            if module_name not in _loaded_generators:
                del imported_module
                raise ImportError(
                    f"Module {module} does not export a generator. Please call export_generator(generator) in the module."
                )
    except ImportError as e:
        raise ImportError(f"Failed to import module {module}") from e

    try:
        instance_id = hash_nc(f"{module_name}{str(context)}", 8)
        if instance_id not in _generator_instances:
            _generator_instances[module_name][instance_id] = _loaded_generators[module_name](context)
    except GeneratorError as e:
        raise GeneratorError(f"Failed to create generator from module {module}") from e

    return _generator_instances[module_name][instance_id]


def export_generator(generator: Type[Generator]):
    """Make a Generator object available to the genearators module"""

    if not issubclass(generator, Generator):
        raise TypeError("generator must be a Generator object")
    module_fname = inspect.stack()[1].filename
    module_name = re.sub(r"\.py[co]?$", "", os.path.basename(module_fname))
    _loaded_generators[module_name] = generator


def drop_generator(module: str) -> bool:
    """Remove a generator from the generators module"""

    dropped = False
    module_name = re.sub(r"\.py[co]?$", "", os.path.basename(module))
    if module_name in _loaded_generators:
        del _loaded_generators[module_name]
        dropped = True
    if module_name in _generator_instances:
        del _generator_instances[module_name]

    return dropped


def drop_generator_instance(generator: Generator) -> bool:
    """Remove a generator instance from the generators module"""

    for module_name, instances in _generator_instances.items():
        for instance in instances:
            if instances[instance] == generator:
                del instances[instance]
                if not instances:
                    del _generator_instances[module_name]
                return True

    return False
