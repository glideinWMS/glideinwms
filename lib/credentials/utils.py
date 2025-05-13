#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module provides utility classes and functions for working with credentials and parameters.
"""


from typing import Iterable, List, Mapping, Optional, Set, Union

from glideinwms.lib.credentials import (
    create_credential,
    create_credential_pair,
    create_parameter,
    Credential,
    credential_type_from_string,
    CredentialDict,
    CredentialError,
    CredentialPairType,
    CredentialType,
    Parameter,
    ParameterDict,
    ParameterError,
    ParameterName,
    ParameterType,
)


class SecurityBundle:
    """Represents a security bundle used for submitting jobs.

    Attributes:
        credentials (CredentialDict): The credentials in the security bundle.
        parameters (type(ParameterDict): The parameters in the security bundle.
    """

    def __init__(self):
        self.credentials = CredentialDict()
        self.parameters = ParameterDict()

    def add_credential(self, credential, credential_id=None):
        """Adds a credential to the security bundle.

        Args:
            credential (Credential): The credential to add.
            credential_id (str, optional): The ID to use as the key in the dictionary.
                If not provided, the credential's ID will be used.
        """

        self.credentials.add(credential, credential_id)

    def add_parameter(self, parameter: Parameter):
        """Adds a parameter to the security bundle.

        Args:
            parameter (Parameter): The parameter to add.
        """

        self.parameters.add(parameter)

    def load_from_element(self, element_descript):
        """Load the security bundle from an element descriptor.

        Args:
            element_descript (ElementDescriptor): The element descriptor to load from.
        """

        for path in element_descript["Proxies"]:
            cred_type = credential_type_from_string(element_descript["ProxyTypes"].get(path))
            purpose = element_descript["CredentialPurposes"].get(path)
            trust_domain = element_descript["ProxyTrustDomains"].get(path, "None")
            security_class = element_descript["ProxySecurityClasses"].get(path, "grid")
            creation_script = element_descript["CredentialCreationScripts"].get(path, None)
            minimum_lifetime = element_descript["CredentialMinimumLifetime"].get(path, None)
            context = load_context(element_descript["CredentialContexts"].get(path, None))
            if isinstance(cred_type, CredentialType):
                credential = create_credential(
                    path=path,
                    purpose=purpose,
                    trust_domain=trust_domain,
                    security_class=security_class,
                    cred_type=cred_type,
                    creation_script=creation_script,
                    minimum_lifetime=minimum_lifetime,
                    context=context,
                )
            else:
                cred_key = element_descript["ProxyKeyFiles"].get(path, None)
                credential = create_credential_pair(
                    path=path,
                    private_path=cred_key,
                    purpose=purpose,
                    trust_domain=trust_domain,
                    security_class=security_class,
                    cred_type=cred_type,
                    creation_script=creation_script,
                    minimum_lifetime=minimum_lifetime,
                    context=context,
                )
            self.add_credential(credential)
        for name, data in element_descript["Parameters"].items():
            parameter = create_parameter(
                ParameterName.from_string(name),
                data["value"],
                ParameterType.from_string(data["type"]),
                load_context(data["context"]),
            )
            self.add_parameter(parameter)


class SubmitBundle:
    """Represents a submit bundle used for submitting jobs.

    This includes Frontend-provided security credentials, identity credentials, and parameters,
    and Factory-provided security credentials.

    Attributes:
        username (str): The username for the submit bundle.
        security_class (str): The security class for the submit bundle.
        id (str): The ID used for tracking the submit credentials.
        cred_dir (str): The location of the credentials.
        auth_set (AuthenticationSet): The authentication requirements for the submit bundle.
        security_credentials (CredentialDict): A dictionary of security credentials.
        identity_credentials (CredentialDict): A dictionary of identity credentials.
        parameters (ParameterDict): A dictionary of parameters.
    """

    def __init__(self, username: str, security_class: str):
        """Initialize a Credentials object.

        Args:
            username (str): The username for the submit bundle.
            security_class (str): The security class for the submit bundle.

        """
        self.username = username
        self.security_class = security_class
        self.id = None
        self.cred_dir = ""
        self.auth_set: Optional[AuthenticationSet] = None
        self.security_credentials = CredentialDict()
        self.identity_credentials = CredentialDict()
        self.parameters = ParameterDict()

    def add_security_credential(
        self,
        credential: Credential,
        cred_id: str = None,
    ) -> bool:
        """Adds a security credential.

        Args:
            credential (Credential): The credential object.
            cred_id (str): The ID of the credential.

        Returns:
            bool: True if the credential was added, otherwise False.
        """

        try:
            self.security_credentials.add(credential, cred_id)
            return True
        except TypeError:
            return False

    def add_factory_credential(self, cred_id: str, credential: Credential) -> bool:
        """Adds a factory provided security credential.

        Args:
            cred_id (str): The ID of the credential.
            credential (Credential): The credential object.

        Returns:
            bool: True if the credential was added, otherwise False.
        """

        self.security_credentials[cred_id] = credential
        return True

    def add_identity_credential(self, credential: Credential, cred_id: Optional[str] = None) -> bool:
        """Adds an identity credential.

        Args:
            cred_id (str): The ID of the credential.
            credential (Credential): The credential object.

        Returns:
            bool: True if the credential was added, otherwise False.
        """

        try:
            self.identity_credentials.add(credential, cred_id)
            return True
        except TypeError:
            return False

    def add_parameter(self, parameter: Parameter) -> bool:
        """Adds a parameter.

        Args:
            parameter (Parameter): The parameter. You can define it using the ID and value.

        Returns:
            bool: True if the parameter was added, otherwise False.
        """

        try:
            self.parameters.add(parameter)
            return True
        except TypeError:
            return False


class AuthenticationSet:
    """Represents a set of authentication requirements."""

    _required_types: Set[Union[CredentialType, CredentialPairType, ParameterName]] = set()

    def __init__(self, auth_set: Iterable[Union[CredentialType, CredentialPairType, ParameterName]]):
        """Initialize the Credentials object.

        Args:
            auth_set: A collection of credential types, credential pair types, or parameter names.

        Raises:
            TypeError: If an invalid credential type is provided.
        """
        for auth_el in auth_set:
            if not isinstance(auth_el, (CredentialType, CredentialPairType, ParameterName)):
                raise TypeError(f"Invalid authentication element: {auth_el} ({type(auth_el)})")
        self._required_types = set(auth_set)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"

    def __str__(self) -> str:
        return ",".join(str(cred_type) for cred_type in self._required_types)

    def __contains__(self, auth_el: Union[CredentialType, CredentialPairType, ParameterName, str]) -> bool:
        return self.supports(auth_el)

    def supports(self, auth_el: Union[CredentialType, CredentialPairType, ParameterName, str]) -> bool:
        """Checks if the authentication set supports a given credential type.

        Args:
            auth_el (Union[CredentialType, CredentialPairType, ParameterName, str]): The authentication element to check.

        Returns:
            bool: True if the credential type is supported, otherwise False.
        """

        if isinstance(auth_el, str):
            try:
                return CredentialType.from_string(auth_el) in self._required_types
            except CredentialError:
                pass
            try:
                return CredentialPairType.from_string(auth_el) in self._required_types
            except CredentialError:
                pass
            try:
                return ParameterName.from_string(auth_el) in self._required_types
            except ParameterError:
                pass
        return auth_el in self._required_types

    def satisfied_by(self, auth_set: Iterable[Union[CredentialType, CredentialPairType, ParameterName]]) -> bool:
        """Checks if the authentication set is satisfied by a given set of credential types.

        Args:
            auth_set: A collection of credential types, credential pair types, or parameter names.

        Returns:
            bool: True if the authentication set is satisfied, otherwise False.
        """

        return self._required_types.issubset(auth_set)


class AuthenticationMethod:
    """Represents an authentication method used for authenticating users."""

    def __init__(self, auth_method: str):
        """Initialize the Credentials object.

        Args:
            auth_method (str): The authentication method.
        """

        self._requirements: List[List[Union[CredentialType, ParameterName]]] = []
        self.load(auth_method)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._requirements!r})"

    def __str__(self) -> str:
        return ";".join(str(auth_set) for auth_set in self._requirements)

    def __contains__(self, cred_type: Union[CredentialType, str]) -> bool:
        if isinstance(cred_type, str):
            cred_type = CredentialType.from_string(cred_type)
        return any(cred_type in group for group in self._requirements)

    def load(self, auth_method: str):
        """Loads the authentication method from a string.

        Args:
            auth_method (str): The authentication method.
        """

        for group in auth_method.split(";"):
            if group.lower() == "any":
                self._requirements.append([])
            else:
                options = []
                for option in group.split(","):
                    try:
                        options.append(CredentialType.from_string(option))
                        continue
                    except CredentialError:
                        pass
                    try:
                        options.append(CredentialPairType.from_string(option))
                        continue
                    except CredentialError:
                        pass
                    try:
                        options.append(ParameterName.from_string(option))
                        continue
                    except ParameterError:
                        pass
                    raise CredentialError(f"Unknown authentication requirement: {option}")
                self._requirements.append(options)

    def match(self, security_bundle: SecurityBundle) -> Optional[AuthenticationSet]:
        """Matches the authentication method to a security bundle and returns the authentication set if the requirements are met.

        Args:
            security_bundle (SecurityBundle): The security bundle to match.

        Returns:
            Optional[AuthenticationSet]: The authentication set if the security bundle matches the requirements, otherwise None.
        """

        if not self._requirements:
            return AuthenticationSet([])

        auth_set = []
        sec_items = {credential.cred_type for credential in security_bundle.credentials.values() if credential.valid}
        sec_items.update(security_bundle.parameters.keys())
        for group in self._requirements:
            # At least one group option must be in sec_items (select the first one)
            selected = False
            for option in group:
                if option in sec_items:
                    auth_set.append(option)
                    selected = True
                    break
            if not selected:
                return None
        return AuthenticationSet(auth_set)


def load_context(context: str) -> Optional[Mapping]:
    """Load a context from a string.

    Args:
        context (str): The context string.

    Returns:
        Mapping: The context as a mapping.
    """

    try:
        context = eval(context)  # pylint: disable=eval-used
        assert isinstance(context, Mapping)
        return context
    except Exception:  # pylint: disable=bare-except
        return None


def cred_path(cred: Optional[Union[Credential, str]]) -> Optional[str]:
    """Returns the path of a credential.

    Args:
        cred (Union[Credential, str]): The credential object or path.

    Returns:
        Optional[str]: The path of the credential.

    Raises:
        CredentialError: If the credential object is invalid.
    """

    if not cred:
        return None
    if issubclass(cred.__class__, Credential):
        return cred.path
    if isinstance(cred, str):
        return cred
    raise CredentialError("Invalid credential object")
