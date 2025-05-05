#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module contains classes and functions for managing GlideinWMS security parameters.
"""

import enum

from abc import ABC, abstractmethod
from inspect import signature
from typing import Generic, Mapping, Optional, Type, TypeVar, Union

from glideinwms.lib.generators import Generator, load_generator

T = TypeVar("T")


class ParameterError(Exception):
    """Defining new exception so that we can catch only the parameter errors here and let the "real" errors propagate up."""


@enum.unique
class ParameterName(enum.Enum):
    """Enum representing different parameter names."""

    VM_ID = "VMId"
    VM_TYPE = "VMType"
    GLIDEIN_PROXY = "GlideinProxy"
    REMOTE_USERNAME = "RemoteUsername"
    PROJECT_ID = "ProjectId"

    @classmethod
    def from_string(cls, string: str) -> "ParameterName":
        """Converts a string representation of a parameter name to a ParameterName object.

        Args:
            string (str): The string representation of the parameter name.

        Returns:
            ParameterName: The corresponding ParameterName object.

        Raises:
            ParameterError: If the string does not match any known parameter name.
        """

        extended_map = {"vm_id": cls.VM_ID, "vm_type": cls.VM_TYPE, "project_id": cls.PROJECT_ID}
        extended_map.update({param.value.lower(): param for param in cls})

        string = string.lower()

        try:
            return ParameterName(string)
        except ValueError:
            pass
        if string in extended_map:
            return extended_map[string]
        raise ParameterError(f"Unknown Parameter name: {string}")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


@enum.unique
class ParameterType(enum.Enum):
    """Enum representing different types of parameters."""

    GENERATOR = "generator"
    INTEGER = "integer"
    EXPRESSION = "expression"
    STRING = "string"

    @classmethod
    def from_string(cls, string: str) -> "ParameterType":
        """Create a ParameterType object from a string representation.

        Args:
            string (str): The string representation of the ParameterType.

        Returns:
            ParameterType: The created ParameterType object.

        Raises:
            ParameterError: If the string does not match any known ParameterType.
        """

        extended_map = {"int": cls.INTEGER, "expr": cls.EXPRESSION, "str": cls.STRING}
        extended_map.update({param.value.lower(): param for param in cls})

        string = string.lower()

        try:
            return ParameterType(string)
        except ValueError:
            pass
        if string in extended_map:
            return extended_map[string]
        raise ParameterError(f"Unknown Parameter type: {string}")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class Parameter(ABC, Generic[T]):
    """Represents a parameter with a name and value.

    Attributes:
        param_type (ParameterType): The type of the parameter.
        name (ParameterName): The name of the parameter.
        value (str): The value of the parameter.
    """

    param_type = None

    def __init__(self, name: ParameterName, value: Union[T, str]):
        """Initialize a Parameter object.

        Args:
            name (ParameterName): The name of the parameter.
            value (str): The value of the parameter.
        """

        if not isinstance(name, ParameterName):
            raise TypeError("Parameter name must be a ParameterName")

        self._name = name
        self._value = self.parse_value(value)

    @property
    def name(self) -> ParameterName:
        """Parameter name."""

        return self._name

    @property
    def value(self) -> T:
        """Parameter value."""

        return self._value

    @property
    @abstractmethod
    def quoted_value(self) -> str:
        """Quoted parameter value."""

    @staticmethod
    @abstractmethod
    def parse_value(value: Union[T, str]) -> T:
        """Parse a value to the parameter type.

        Args:
            value: The value to parse.

        Returns:
            T: The parsed value.

        Raises:
            ValueError: If the value is invalid.
        """

    def copy(self) -> "Parameter":
        """Create a copy of the parameter.

        Returns:
            Parameter: The copied parameter.
        """

        return create_parameter(self._name, self._value, self.param_type)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self._name.value!r}, value={self._value!r}, param_type={self.param_type.value!r})"

    def __str__(self) -> str:
        return f"{self.name.value}={self.value}"


class ParameterGenerator(Parameter, Generator):
    """A class representing a generator parameter.

    This class inherits from the base `Parameter` class and is used to define parameters
    that generate their values dynamically using a generator function.

    Attributes:
        param_type (ParameterType): The type of the parameter (GENERATOR).
        name (ParameterName): The name of the parameter.
        value (str): The value of the parameter.
    """

    param_type = ParameterType.GENERATOR

    # noinspection PyMissingConstructor
    def __init__(self, name: ParameterName, value: str, context: Optional[Mapping] = None):
        """Initialize a ParameterGenerator object.

        Args:
            name (ParameterName): The name of the parameter.
            value (str): The value of the parameter.
            context (Mapping, optional): The context to use for the parameter.
        """

        if not isinstance(name, ParameterName):
            raise TypeError("Parameter name must be a ParameterName")

        self._generated_parameter: Optional[Parameter] = None
        self._name = name
        self._value = self.parse_value(value, context)
        if context and "type" in context:
            self.param_type = ParameterType.from_string(context.get("type"))

    @property
    def value(self) -> any:
        """Parameter value.

        NOTE: None until the parameter is generated.
        """

        return self._generated_parameter.value if self._generated_parameter else None

    @property
    def quoted_value(self) -> Optional[str]:
        """Quoted parameter value."""

        return self._generated_parameter.quoted_value if self._generated_parameter else None

    @staticmethod
    def parse_value(value: Union[Generator, str], context: Optional[Mapping]) -> Generator:
        """Parse the parameter value to a generator.

        Args:
            value (str): The value to parse.

        Returns:
            Generator: The parsed value.

        Raises:
            ImportError: If the generator could not be loaded.
        """

        try:
            if isinstance(value, Generator):
                return value
            return load_generator(value, context)
        except ImportError as err:
            raise ImportError(f"Could not load generator: {value}") from err

    def copy(self) -> Parameter:
        """Create a copy of the current generated parameter.

        NOTE: The resulting parameter is not a generator.

        Returns:
            Parameter: The copied parameter.
        """

        return create_parameter(self.name, self.value, self.param_type)

    def generate(self, **kwargs):
        """Generate the parameter value using the generator function.

        Args:
            **kwargs: Additional keyword arguments to pass to the generator function.
        """

        self._generated_parameter = create_parameter(self._name, self._value.generate(**kwargs), self.param_type)


class IntegerParameter(Parameter[int]):
    """Represents an integer parameter.

    This class extends the base `Parameter` class and is used to define parameters
    with integer values.

    Attributes:
        param_type (ParameterType): The type of the parameter (INTEGER).
        name (ParameterName): The name of the parameter.
        value (int): The value of the parameter.
    """

    param_type = ParameterType.INTEGER

    @property
    def quoted_value(self) -> str:
        """Quoted parameter value."""

        return str(self.value) if self.value else None

    @staticmethod
    def parse_value(value: Union[int, str]) -> int:
        """Parse a value to an integer."""
        try:
            return int(value)
        except ValueError as err:
            raise ValueError(f"Invalid integer value: {value}") from err


class StringParameter(Parameter[str]):
    """Represents a string parameter.

    This class extends the base `Parameter` class and is used to define parameters
    with string values.

    Attributes:
        param_type (ParameterType): The type of the parameter (STRING).
        name (ParameterName): The name of the parameter.
        value (str): The value of the parameter.
    """

    param_type = ParameterType.STRING

    @property
    def quoted_value(self) -> str:
        """Quoted parameter value."""

        return f'"{self.value}"' if self.value else None

    @staticmethod
    def parse_value(value: str) -> str:
        """Parse a value to a string.

        Args:
            value (str): The value to parse.
        """

        return str(value)


class ExpressionParameter(Parameter[str]):
    """Represents an expression parameter.

    This class extends the base `Parameter` class and is used to define parameters
    with expression values.

    Attributes:
        param_type (ParameterType): The type of the parameter (EXPRESSION).
        name (ParameterName): The name of the parameter.
        value (str): The value of the parameter.
    """

    param_type = ParameterType.EXPRESSION

    @property
    def quoted_value(self) -> str:
        """Quoted parameter value."""

        return self.value

    @staticmethod
    def parse_value(value: str) -> str:
        """Parse the parameter value.

        Args:
            value (str): The value to parse.

        Returns:
            str: The parsed value.
        """

        # TODO: Implement expression parsing

        return value


class ParameterDict(dict):
    """A dictionary subclass for storing parameters.

    This class extends the built-in `dict` class and provides additional functionality
    for storing and retrieving parameters. It enforces that keys must be of type `ParameterName`
    and values must be of type `Parameter`.
    """

    def __setitem__(self, __k, __v):
        if isinstance(__k, str):
            __k = ParameterName.from_string(__k)
        if not isinstance(__k, ParameterName):
            raise TypeError("Key must be a ParameterType")
        if not isinstance(__v, Parameter):
            raise TypeError("Value must be a Parameter")
        super().__setitem__(__k, __v)

    def __getitem__(self, __k):
        if isinstance(__k, str):
            __k = ParameterName.from_string(__k)
        if not isinstance(__k, ParameterName):
            raise TypeError("Key must be a ParameterType")
        return super().__getitem__(__k)

    def add(self, parameter: Parameter):
        """Adds a parameter to the dictionary.

        Args:
            parameter (Parameter): The parameter to add.
        """

        if not isinstance(parameter, Parameter):
            raise TypeError("Parameter must be a Parameter")
        self[parameter.name] = parameter


def parameter_of_type(param_type: ParameterType) -> Type[Parameter]:
    """Returns the parameter subclass for the given type.

    Args:
        param_type (ParameterType): parameter type

    Raises:
        CredentialError: if the parameter type is unknown

    Returns:
        Parameter: parameter subclass
    """

    class_dict = {}
    for i in Parameter.__subclasses__():
        class_dict[i.param_type] = i
    try:
        return class_dict[param_type]
    except KeyError as err:
        raise ParameterError(f"Unknown Parameter type: {param_type}") from err


def create_parameter(
    name: ParameterName, value: str, param_type: Optional[ParameterType] = None, context: Optional[Mapping] = None
) -> Parameter:
    """Creates a parameter.

    Args:
        name (ParameterName): The name of the parameter.
        value (str): The value of the parameter.
        param_type (ParameterType, optional): The type of the parameter.
        context (Mapping, optional): The context to use for the parameter.

    Returns:
        Parameter: The parameter object.
    """

    parameter_types = [param_type] if param_type else ParameterType
    for p_type in parameter_types:
        try:
            parameter_class = parameter_of_type(p_type)
            if issubclass(parameter_class, Parameter):
                param_args = signature(parameter_class.__init__).parameters.values()
                param_args = [param.name for param in param_args if param.name != "self"]
                kwargs = {key: value for key, value in locals().items() if key in param_args and value is not None}
                return parameter_class(**kwargs)
        except TypeError:
            pass  # Parameter type incompatible with input
        except Exception as err:
            raise ParameterError(f'Unexpected error loading parameter: name="{name}", value="{value}"') from err
    raise ParameterError(f'Could not load parameter: name="{name}", value="{value}"')
