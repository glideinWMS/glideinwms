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
import time

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Generic, Mapping, Optional, Tuple, Type, TypeVar, Union

from glideinwms.lib.defaults import CACHE_DIR, PLUGINS_DIR
from glideinwms.lib.util import hash_nc, import_module

sys.path.append(PLUGINS_DIR)
_loaded_generators = {}  # All current generators. Updated via export_generator()
_generator_instances = defaultdict(dict)

T = TypeVar("T")


class GeneratorError(Exception):
    """Base class for generator exceptions"""


class GeneratorContextError(GeneratorError):
    """Exception validating a GeneratorContext"""


class GeneratorContext(dict):
    """Context for a generator"""

    def validate(self, valid_attributes: Mapping[str, Tuple[Union[Type, Tuple[Type], Any]]]):
        """Validate the context against a set of valid attributes.
        This method ensures that required attributes are present and that their types match the expected types.
        The expected types can be a type or a tuple containing one or more types and optionally `None`.
        If an attribute is missing, it will be set to a default value if provided.

        Args:
            valid_attributes (Mapping[str, Tuple[Type, Any]]): a mapping of attribute names to their expected types and default values.
                   If the default is missing, then the attribute has to have a value.

        Raises:
            GeneratorContextError: when a required attribute has an invalid type or is missing and has no default value.

        Example:
            context.validate({
                "user": (str),
                "group": (str,),
                "permissions": ((list, None), []),
            })
        """

        for attr, attr_validation in valid_attributes.items():
            if attr not in self:
                try:
                    self[attr] = attr_validation[1]
                except (TypeError, IndexError):
                    # No default in the context validation
                    raise GeneratorContextError(f"Missing required context attribute: {attr}")
            else:
                # Values in context validation are not validated to allow None also when not in the type list
                try:
                    attr_types = attr_validation[0]
                except (TypeError, IndexError):
                    attr_types = attr_validation
                if not isinstance(attr_types, tuple):
                    attr_types = (attr_types,)
                if self[attr] is None and None in attr_types:
                    continue
                if not isinstance(self[attr], tuple(attr_type for attr_type in attr_types if attr_type is not None)):
                    attr_types = tuple(attr_type.__name__ for attr_type in attr_types)
                    raise GeneratorContextError(
                        f"Invalid type for attribute '{attr}': "
                        f"expected one of '{attr_types}', got '{type(self[attr]).__name__}'"
                    )


class Generator(ABC, Generic[T]):
    """Base class for generators"""

    def __init__(self, context: Optional[Mapping] = None, instance_id: Optional[str] = None):
        self.snapshots = {}
        self.context = GeneratorContext(context)
        self.instance_id = instance_id or hash_nc(f"{time.time()}", 8)
        self.setup()

    def __str__(self):
        return f"{self.__class__.__name__}()"

    def __repr__(self):
        return str(self)

    def setup(self):
        """Setup method to be called at the generator's construction"""
        try:
            self._setup()
        except NotImplementedError:
            pass

    def generate(self, snapshot: Optional[str] = None, **kwargs) -> T:
        """
        Generates an item using the current context and any provided keyword arguments.

        Args:
            snapshot (str, optional): An optional identifier for the snapshot or state to use during generation. Defaults to None.
            **kwargs: Additional keyword arguments that may be used to customize the generation process.

        Returns:
            T: The generated item of type T, as determined by the implementation.
        """

        generated_value = self._generate(**kwargs)
        if snapshot:
            self.snapshots[snapshot] = generated_value

        return generated_value

    def get_snapshot(self, snapshot: str, default: Optional[any] = None) -> Optional[T]:
        """
        Retrieves a previously generated snapshot.

        Args:
            snapshot (str): The identifier for the snapshot to retrieve.
            default (Optional[any]): A default value to return if the snapshot does not exist.

        Returns:
            T: The previously generated item of type T, or None if the snapshot does not exist.

        Raises:
            GeneratorError: If the snapshot does not exist.
        """

        return self.snapshots.get(snapshot, default)

    def _setup(self):
        """Internal setup method to be called at the generator's construction"""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement the _setup method. " "Please implement it in the subclass."
        )

    @abstractmethod
    def _generate(self, **kwargs) -> T:
        """Internal method to generate an item using the context and keyword arguments"""
        return self.generate(**kwargs)


class CachedGenerator(Generator[T]):
    """Base class for cached generators"""

    def __init__(self, context: Optional[Mapping] = None, instance_id: Optional[str] = None):
        super().__init__(context, instance_id)
        file_type = self.context.get("type", "cache")
        self.context.validate(
            {
                "cache_dir": (str, CACHE_DIR),
                "cache_file": (
                    str,
                    os.path.join(
                        self.context.get("cache_dir", CACHE_DIR),
                        f"{self.__class__.__name__}_{self.instance_id}.{file_type}",
                    ),
                ),
                "cache_discriminator": (str, "snapshot"),
            }
        )
        self.cache_file = self.context["cache_file"]
        self.saved_cache_files = set()
        self.discriminator_list = [d.strip() for d in self.context["cache_discriminator"].split(",") if d.strip()]

    def generate(self, snapshot: Optional[str] = None, **kwargs) -> T:
        cache_file = self.dynamic_cache_file(snapshot, **kwargs) or self.cache_file
        loaded_value = self.load_from_cache(cache_file)
        if loaded_value is not None:
            if self.validate_cache(loaded_value):
                if snapshot:
                    self.snapshots[snapshot] = loaded_value
                return loaded_value
        generated_value = super().generate(snapshot, **kwargs)
        self.save_to_cache(cache_file, generated_value)
        self.saved_cache_files.add(cache_file)
        return generated_value

    def clear_cache(self):
        """Remove the cache file"""

        for cache_file in self.saved_cache_files:
            if os.path.exists(cache_file):
                os.remove(cache_file)
        self.saved_cache_files.clear()

    def dynamic_cache_file(self, snapshot: Optional[str] = None, **kwargs) -> Optional[str]:
        """Set a dynamic cache file name

        This method returns None by default. Override it in subclasses to provide
        a custom cache file name.
        When generating a cache file, the generator will first try to use the dynamic
        cache file name. If it is None, it will use the cache_file defined in the
        context or the default one.

        Args:
            snapshot (Optional[str]): an optional snapshot identifier
            **kwargs: keyword arguments passed to the generate method

        Returns:
            Optional[str]: the dynamic cache file name or None
        """

        discriminator = self.cache_discriminator(self.discriminator_list, snapshot=snapshot, **kwargs)
        if not discriminator:
            return None

        file_name, file_ext = os.path.splitext(self.cache_file)
        return f"{file_name}.{discriminator}{file_ext}"

    @abstractmethod
    def save_to_cache(self, cache_file: str, generated_value: T):
        """
        Save an item to the cache

        Args:
            cache_file (str): the cache file name
            generated_value (T): the item to save
        """

    @abstractmethod
    def load_from_cache(self, cache_file: str) -> Optional[T]:
        """
        Load an item from the cache

        Args:
            cache_file (str): the cache file name

        Returns:
            Optional[T]: the cached item or None if the cache file does not exist
        """

    @abstractmethod
    def validate_cache(self, cached_value: T) -> bool:
        """
        Validate the cache

        Args:
            cached_value (T): the cached item

        Returns:
            bool: True if the cache is valid, False otherwise
        """

    @classmethod
    def cache_discriminator(
        cls, discriminator_list: Union[str, list[str]], separator: str = ".", snapshot: Optional[str] = None, **kwargs
    ) -> Optional[str]:
        """Generate a cache discriminator string based on the provided discriminator and runtime arguments.
        This method constructs a string that uniquely identifies the cache entry based on the provided
        discriminator values and the attributes of the glidein element.

        Args:
            discriminator (Union[str, list[str]]): a string or a list of strings that specify the discriminator values
            separator (str): a string used to separate the discriminator values in the resulting string
            **kwargs: runtime arguments that include the glidein element and other necessary attributes

        Returns:
            Optional[str]: a string that uniquely identifies the cache entry, or None if the discriminator is not provided

        Raises:
            GeneratorError: if the discriminator is invalid or not in the expected format
        """

        discriminator_mapping = {
            "name": kwargs["glidein_el"]["attrs"].get("EntryName"),
            "group": kwargs["group_name"],
            "gatekeeper": kwargs["glidein_el"]["attrs"].get("GLIDEIN_Gatekeeper"),
            "factory": kwargs["glidein_el"]["attrs"].get("AuthenticatedIdentity"),
            "trust_domain": kwargs["glidein_el"]["attrs"].get("GLIDEIN_TrustDomain"),
            "snapshot": snapshot,
            "none": None,
        }

        if discriminator_list is None:
            return None

        if isinstance(discriminator_list, str):
            discriminator_list = [discriminator_list]

        for d in discriminator_list:
            if d not in discriminator_mapping:
                raise GeneratorError(f"Invalid discriminator '{d}'. Must be in {list(discriminator_mapping.keys())}.")

        return (
            separator.join(str(discriminator_mapping[d]) for d in discriminator_list if discriminator_mapping[d])
            or None
        )


def load_generator(module: str, context: Optional[Mapping] = None) -> Generator:
    """Load a generator from a module and optionally associate it with a context.

    Args:
        module (str): module that exports a generator

    Raises:
        ImportError: when a `Generator` object cannot be imported from `module`
        GeneratorError: when the setup or contextualization of a `Generator` object fail

    Returns:
        Generator: contextualized generator object
    """

    module_name = re.sub(r"\.py[co]?$", "", os.path.basename(module))  # Extract module name from path

    try:
        if module_name not in _loaded_generators:
            imported_module = import_module(module)
            if module_name not in _loaded_generators:
                # Imported module is not a generator, undo the import
                del imported_module
                raise ImportError(
                    f"Module {module} does not export a generator. Please call export_generator(generator) in the module."
                )
    except ImportError as e:
        raise ImportError(f"Failed to import module {module}") from e

    try:
        instance_id = hash_nc(f"{module_name}{str(context)}", 8)
        if instance_id not in _generator_instances[module_name]:
            _generator_instances[module_name][instance_id] = _loaded_generators[module_name](context, instance_id)
    except GeneratorError as e:
        raise GeneratorError(f"Failed to create generator from module {module}") from e
    except Exception as e:
        raise GeneratorError(f"Unhandled error in the _setup of generator from module {module}") from e

    return _generator_instances[module_name][instance_id]


def export_generator(generator: Type[Generator]):
    """Make a Generator object available to the generators module"""

    if not issubclass(generator, Generator):
        raise TypeError("generator must be a Generator object")
    module_fname = inspect.stack()[1].filename
    module_name = re.sub(r"\.py[co]?$", "", os.path.basename(module_fname))
    _loaded_generators[module_name] = generator  # Modifying global variable, OK because mutable


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
