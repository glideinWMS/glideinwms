#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module contains classes and functions for managing GlideinWMS credentials.
"""

import base64
import enum  # TODO: Use StrEnum starting from Python 3.11
import gzip
import os
import shutil
import tempfile

from abc import ABC, abstractmethod
from inspect import signature
from io import BytesIO
from typing import Generic, List, Mapping, Optional, Type, TypeVar, Union

from glideinwms.lib import logSupport, subprocessSupport
from glideinwms.lib.defaults import force_bytes
from glideinwms.lib.util import hash_nc

T = TypeVar("T")


class CredentialError(Exception):
    """Defining new exception so that we can catch only the credential errors here and let the "real" errors propagate up."""


@enum.unique
class CredentialType(enum.Enum):
    """Enum representing different types of credentials."""

    TOKEN = "token"
    SCITOKEN = "scitoken"
    IDTOKEN = "idtoken"
    X509_CERT = "x509_cert"
    RSA_PUBLIC_KEY = "rsa_public_key"
    RSA_PRIVATE_KEY = "rsa_private_key"
    SYMMETRIC_KEY = "symmetric_key"
    DYNAMIC = "dynamic"
    TEXT = "text"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    @classmethod
    def from_string(cls, string: str) -> "CredentialType":
        """Converts a string representation of a credential type to a CredentialType object.

        Args:
            string (str): The string representation of the credential type.

        Returns:
            CredentialType: The corresponding CredentialType enum value.

        Raises:
            CredentialError: If the string does not match any known credential type.
        """

        extended_map = {
            "grid_proxy": cls.X509_CERT,
            "rsa_key": cls.RSA_PUBLIC_KEY,
            "auth_file": cls.TEXT,
            "generator": cls.DYNAMIC,
        }

        string = string.lower()

        try:
            return CredentialType(string)
        except ValueError:
            pass
        if string in extended_map:
            return extended_map[string]
        raise CredentialError(f"Unknown Credential type: {string}")


@enum.unique
class CredentialPairType(enum.Enum):
    """Enum representing different types of credential pairs."""

    X509_PAIR = "x509_pair"
    KEY_PAIR = "key_pair"
    USERNAME_PASSWORD = "username_password"

    @classmethod
    def from_string(cls, string: str) -> "CredentialPairType":
        """Converts a string representation of a credential type to a CredentialPairType object.

        Args:
            string (str): The string representation of the credential type.

        Returns:
            CredentialPairType: The corresponding CredentialPairType object.

        Raises:
            CredentialError: If the string representation is not a valid credential type.
        """

        extended_map = {"cert_pair": cls.X509_PAIR}

        string = string.lower()

        try:
            return CredentialPairType(string)
        except ValueError:
            pass
        if string in extended_map:
            return extended_map[string]
        raise CredentialError(f"Unknown Credential type: {string}")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


@enum.unique
class CredentialPurpose(enum.Enum):
    """Enum representing different purposes for credentials."""

    REQUEST = "request"
    CALLBACK = "callback"
    PAYLOAD = "payload"

    @classmethod
    def from_string(cls, string: str) -> "CredentialPurpose":
        """Converts a string representation of a CredentialPurpose to a CredentialPurpose object.

        Args:
            string (str): The string representation of the CredentialPurpose.

        Returns:
            CredentialPurpose: The CredentialPurpose object.
        """

        string = string.lower()
        return CredentialPurpose(string)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class Credential(ABC, Generic[T]):
    """Represents a credential used for authentication or authorization purposes.

    Attributes:
        cred_type (Optional[CredentialType]): The type of the credential.
        extension (Optional[str]): The file extension of the credential.

    Raises:
        CredentialError: If the credential cannot be initialized or loaded.
    """

    cred_type: Optional[CredentialType] = None
    extension: Optional[str] = None

    def __init__(
        self,
        string: Optional[Union[str, bytes]] = None,
        path: Optional[str] = None,
        purpose: Optional[CredentialPurpose] = None,
        trust_domain: Optional[str] = None,
        security_class: Optional[str] = None,
        creation_script: Optional[str] = None,
        minimum_lifetime: Union[int, str] = 0,
    ) -> None:
        """Initialize a Credentials object.

        Args:
            string (Optional[Union[str, bytes]]): The credential string.
            path (Optional[str]): The path to the credential file.
            purpose (Optional[CredentialPurpose]): The purpose of the credential.
            trust_domain (Optional[str]): The trust domain of the credential.
            security_class (Optional[str]): The security class of the credential.
            creation_script (Optional[str]): The script to create the credential.
            minimum_lifetime (Union[int, str]): The minimum lifetime of the credential in seconds.
        """

        self._string = None
        self.path = path
        self.purpose = purpose
        self.trust_domain = trust_domain
        self.security_class = security_class
        self.creation_script = creation_script
        try:
            self.minimum_lifetime = int(minimum_lifetime)
        except ValueError as err:
            raise CredentialError(f"Invalid minimum lifetime: {minimum_lifetime}") from err
        if string or path:
            self.load(string, path)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(string={self.string!r}, path={self.path!r}, purpose={self.purpose!r}, trust_domain={self.trust_domain!r}, security_class={self.security_class!r})"

    def __str__(self) -> str:
        return self.string.decode() if self.string else ""

    def __renew__(self) -> None:
        if not self.creation_script:
            raise NotImplementedError("Renewal not implemented for this credential type")
        if self.valid:
            return
        try:
            subprocessSupport.iexe_cmd(self.creation_script)
        except RuntimeError as err:
            raise CredentialError(f"Error renewing or creating credential: {err}") from err
        self.load_from_file()

    @property
    def _payload(self) -> Optional[T]:
        return self.decode(self.string) if self.string else None

    @property
    def string(self) -> Optional[bytes]:
        """Credential string."""

        return self._string

    @property
    def id(self) -> str:
        """Credential unique identifier."""

        if not str(self.string):
            raise CredentialError("Credential not initialized")

        return hash_nc(
            f"{str(self._id_attribute)}{self.purpose}{self.trust_domain}{self.security_class}{self.cred_type}", 8
        )

    @property
    def purpose(self) -> Optional[CredentialPurpose]:
        """Credential purpose."""

        return self._purpose[0]

    @purpose.setter
    def purpose(self, value: Optional[Union[CredentialPurpose, str]]):
        if not value:
            self._purpose = (None, None)
        elif isinstance(value, CredentialPurpose):
            self._purpose = (value, None)
        elif isinstance(value, str):
            try:
                self._purpose = (CredentialPurpose.from_string(value), None)
            except ValueError:
                self._purpose = (CredentialPurpose.PAYLOAD, value)
        else:
            raise CredentialError(f"Invalid purpose: {value}")

    @property
    def purpose_alias(self) -> Optional[str]:
        """Credential purpose alias."""

        if self._purpose[0] is not None:
            return self._purpose[1] or self._purpose[0].value

    @property
    def valid(self) -> bool:
        """Whether the credential is valid."""
        return self.invalid_reason() is None

    @property
    @abstractmethod
    def _id_attribute(self) -> Optional[str]:
        """Attribute used to identify the credential."""

    @staticmethod
    @abstractmethod
    def decode(string: Union[str, bytes]) -> T:
        """Decode the given string to provide the credential.

        Args:
            string (bytes): The string to decode.

        Returns:
            T: The decoded value.
        """

    @abstractmethod
    def invalid_reason(self) -> Optional[str]:
        """Returns the reason why the credential is invalid.

        Returns:
            str: The reason why the credential is invalid. None if the credential is valid.
        """

    def load_from_string(self, string: Union[str, bytes]) -> None:
        """Load the credential from a string.

        Args:
            string (bytes): The credential string to load.

        Raises:
            CredentialError: If the input string is not of type bytes or if the credential cannot be loaded from the string.
        """

        string = force_bytes(string)
        if not isinstance(string, bytes):
            raise CredentialError("Credential string must be bytes")
        try:
            self.decode(string)
        except Exception as err:
            raise CredentialError(f"Could not load credential from string: {string}") from err
        self._string = string

    def load_from_file(self, path: Optional[str] = None) -> None:
        """Load credentials from a file.

        Args:
            path (str): The path to the credential file.

        Raises:
            CredentialError: If the specified file does not exist.
        """

        path = path or self.path

        if not os.path.isfile(path):
            raise CredentialError(f"Credential file {path} does not exist or wrong file or directory permissions")
        with open(path, "rb") as cred_file:
            self.load_from_string(cred_file.read())
        self.path = path

    def load(self, string: Optional[Union[str, bytes]] = None, path: Optional[str] = None) -> None:
        """Load credentials from either a string or a file.
        If both are defined, the string takes precedence.

        Args:
            string (Optional[bytes]): The credentials string to load.
            path (Optional[str]): The path to the file containing the credentials.

        Raises:
            CredentialError: If neither `string` nor `path` is specified.
        """

        if string:
            self.load_from_string(string)
            if path:
                self.path = path
        elif path:
            self.load_from_file(path)
        else:
            raise CredentialError("No string or path specified")

    def copy(self) -> "Credential":
        """Create a copy of the credential.

        Returns:
            Credential: The static credential.

        Raises:
            CredentialError: If the credential is not initialized.
        """

        if not self.string:
            raise CredentialError("Credential not initialized")
        return create_credential(
            string=self.string,
            path=self.path,
            purpose=self.purpose,
            trust_domain=self.trust_domain,
            security_class=self.security_class,
            cred_type=self.cred_type,
        )

    def save_to_file(
        self,
        path: Optional[str] = None,
        permissions: int = 0o600,
        backup: bool = False,
        compress: bool = False,
        data_pattern: Optional[bytes] = None,
        overwrite: bool = True,
        continue_if_no_path=False,
    ) -> None:
        """Save the credential to a file.

        Args:
            path (Optional[str]): The path to the file where the credential will be saved.
            permissions (int): The permissions to set for the saved file. Default is 0o600.
            backup (bool): Whether to create a backup of the existing file. Default is False.
            compress (bool): Whether to compress the credential before saving. Default is False.
            data_pattern (Optional[bytes]): A pattern to format the credential data before saving. Default is None.
            overwrite (bool): Whether to overwrite the existing file if it already exists. Default is True.
            continue_if_no_path (bool): If True, silently return without saving a file if no path is specified. Default is False.

        Raises:
            CredentialError: If the credential is not initialized or if there is an error saving the credential.
        """

        if not self.string:
            raise CredentialError("Credential not initialized")

        path = path or self.path
        if not path:
            if continue_if_no_path:
                return
            raise CredentialError("No path specified")

        if os.path.isfile(path) and not overwrite:
            return

        text = self.string
        if compress:
            text = compress_credential(text)
        if data_pattern:
            text = data_pattern % text

        try:
            # NOTE: NamedTemporaryFile is created in private mode by default (0600)
            with tempfile.NamedTemporaryFile(mode="wb", delete=False) as fd:
                os.chmod(fd.name, permissions)
                fd.write(text)
                fd.flush()
                if backup:
                    try:
                        shutil.copy2(path, f"{path}.old")
                    except FileNotFoundError as err:
                        logSupport.log.debug(
                            f"Tried to backup credential at {path} but file does not exist: {err}. Probably first time saving credential."
                        )
                shutil.move(fd.name, path)  # os.replace() may cause issues if moving across filesystems
        except OSError as err:
            raise CredentialError(f"Could not save credential to {path}: {err}") from err

    def renew(self) -> None:
        """Renews the credentials.

        This method attempts to renew the credentials by calling the private __renew__ method.
        If the __renew__ method is not implemented, it will silently pass.
        """
        try:
            self.__renew__()
        except NotImplementedError:
            pass


class CredentialPair:
    """Adds a private credential to the Credential of type T to the class that inherits from it.

    NOTE: This class serves as a base and cannot be instantiated directly. It must be inherited,
    with a subclass of `Credential` as the second base class.
    The resulting subclass will function as a credential of the second base class type,
    while also incorporating a private credential of the type specified in the `private_cred_type`
    attribute. This private credential is stored in the `private_credential` attribute.

    Attributes:
        cred_type (Optional[CredentialPairType]): The type of the credential pair.
        private_cred_type (CredentialType): The type of the private credential.
        private_credential (Credential): The private credential associated with this pair.

    NOTE: Includes all attributes from the Credential class.
    """

    def __init__(
        self,
        string: Optional[bytes] = None,
        path: Optional[str] = None,
        private_string: Optional[bytes] = None,
        private_path: Optional[str] = None,
        purpose: Optional[CredentialPurpose] = None,
        trust_domain: Optional[str] = None,
        security_class: Optional[str] = None,
    ) -> None:
        """Initialize a CredentialPair object.

        Args:
            string (Optional[bytes]): The string representation of the public credential.
            path (Optional[str]): The path to the public credential file.
            private_string (Optional[bytes]): The string representation of the private credential.
            private_path (Optional[str]): The path to the private credential file.
            purpose (Optional[CredentialPurpose]): The purpose of the credential.
            trust_domain (Optional[str]): The trust domain of the credential.
            security_class (Optional[str]): The security class of the credential.
        """

        if len(self.__class__.__bases__) < 2 or not issubclass(self.__class__.__bases__[1], Credential):
            raise CredentialError("CredentialPair requires a subclass of Credential as the second base class.")
        if self.private_cred_type not in CredentialType:
            raise CredentialError("private_cred_type must be a subclass of CredentialType")

        credential_class = self.__class__.__bases__[1]
        super(credential_class, self).__init__(  # pylint: disable=bad-super-call
            string, path, purpose, trust_domain, security_class
        )
        private_credential_class = credential_of_type(self.private_cred_type)  # pylint: disable=no-member
        self.private_credential = private_credential_class(
            private_string, private_path, purpose, trust_domain, security_class
        )

    def renew(self) -> None:
        """Renews the credentials by calling the __renew__() method on both the public and private credentials."""

        try:
            # noinspection PyUnresolvedReferences
            self.__renew__()  # pylint: disable=no-member # type: ignore[attr-defined]
            self.private_credential.__renew__()
        except NotImplementedError:
            pass

    def copy(self) -> "CredentialPair":
        """Create a copy of the credential pair.

        Returns:
            CredentialPair: The static credential pair.

        Raises:
            CredentialError: If the credential pair is not initialized.
        """

        if not self.string:  # pylint: disable=no-member # type: ignore[attr-defined]
            raise CredentialError("Credential pair not initialized")
        return create_credential_pair(
            string=self.string,  # pylint: disable=no-member # type: ignore[attr-defined]
            path=self.path,  # pylint: disable=no-member # type: ignore[attr-defined]
            private_string=self.private_credential.string,
            private_path=self.private_credential.path,
            purpose=self.purpose,  # pylint: disable=no-member # type: ignore[attr-defined]
            trust_domain=self.trust_domain,  # pylint: disable=no-member # type: ignore[attr-defined]
            security_class=self.security_class,  # pylint: disable=no-member # type: ignore[attr-defined]
            cred_type=self.cred_type,  # pylint: disable=no-member
        )

    private_cred_type = None


# Dictionary of Credentials
class CredentialDict(dict):
    """A dictionary-like class for storing credentials.

    This class extends the built-in `dict` class and provides additional
    functionality for storing and retrieving `Credential` objects.
    """

    def __setitem__(self, __k, __v):
        if not isinstance(__v, Credential):
            raise TypeError("Value must be a credential")
        super().__setitem__(__k, __v)

    def add(self, credential: Credential, credential_id: Optional[str] = None):
        """Add a credential to the dictionary.

        Args:
            credential (Credential): The credential object to add.
            id (str, optional): The ID to use as the key in the dictionary.
                If not provided, the credential's ID will be used.
        """
        if not isinstance(credential, Credential):
            raise TypeError("Value must be a credential")
        self[credential_id or credential.id] = credential

    def find(
        self,
        cred_type: Optional[Union[CredentialType, CredentialPairType]] = None,
        purpose: Optional[CredentialPurpose] = None,
    ) -> List[Credential]:
        """Find credentials in the dictionary.

        Args:
            type (Optional[Union[CredentialType, CredentialPairType]]): The type of credential to find.
            purpose (Optional[CredentialPurpose]): The purpose of the credential to find.

        Returns:
            List[Credential]: A list of credentials that match the specified type and purpose.
        """
        return [
            cred
            for cred in self.values()
            if (cred_type is None or cred.cred_type == cred_type) and (purpose is None or cred.purpose == purpose)
        ]


class RequestCredential:
    """Represents an extended credential used for requesting resources.

    Args:
        credential (Credential): The credential object.

    Attributes:
        credential (Credential): The credential object.
        advertise (bool): Flag indicating whether to advertise the credential.
        req_idle (int): Number of idle jobs requested.
        req_max_run (int): Maximum number of running jobs requested.
    """

    def __init__(
        self,
        credential: Credential,
    ):
        self.credential = credential
        self.advertise: bool = True
        self.req_idle: int = 0
        self.req_max_run: int = 0

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(credential={self.credential!s}, advertise={self.advertise}, req_idle={self.req_idle}, req_max_run={self.req_max_run})"

    def __str__(self) -> str:
        return f"{self.credential!s}"

    def add_usage_details(self, req_idle=0, req_max_run=0):
        """Add usage details to the request.

        Args:
            req_idle (int): Number of idle jobs requested.
            req_max_run (int): Maximum number of running jobs requested.
        """
        self.req_idle = req_idle
        self.req_max_run = req_max_run

    def get_usage_details(self):
        return self.req_idle, self.req_max_run


def credential_type_from_string(string: str) -> Union[CredentialType, CredentialPairType]:
    """Returns the credential type for a given string.

    Args:
        string (str): The string to parse.

    Raises:
        CredentialError: If the credential type is unknown.

    Returns:
        Union[CredentialType, CredentialPairType]: The credential type.
    """

    try:
        return CredentialType.from_string(string)
    except CredentialError:
        try:
            return CredentialPairType.from_string(string)
        except CredentialError:
            raise CredentialError(f"Unknown credential type: {string}")  # pylint: disable=raise-missing-from


def credential_of_type(
    cred_type: Union[CredentialType, CredentialPairType],
) -> Union[Type[Credential], Type[CredentialPair]]:
    """Returns the credential subclass for the given type.

    Args:
        cred_type (CredentialType): credential type

    Raises:
        CredentialError: if the credential type is unknown

    Returns:
        Credential: credential subclass
    """

    def subclasses_dict(classes):
        sc_dict = {}
        for cls in classes:
            for sc in cls.__subclasses__():
                sc_dict[sc.cred_type] = sc
                sc_dict.update(subclasses_dict([sc]))
        return sc_dict

    try:
        return subclasses_dict([Credential, CredentialPair])[cred_type]
    except KeyError as err:
        raise CredentialError(f"Unknown Credential type: {cred_type}") from err


def create_credential(
    string: Optional[Union[str, bytes]] = None,
    path: Optional[str] = None,
    purpose: Optional[CredentialPurpose] = None,
    trust_domain: Optional[str] = None,
    security_class: Optional[str] = None,
    cred_type: Optional[CredentialType] = None,
    creation_script: Optional[str] = None,
    minimum_lifetime: Union[int, str] = 0,
    context: Optional[Mapping] = None,
) -> Credential:
    """Creates a credential object.

    Args:
        string (bytes, optional): The credential as a byte string.
        path (str, optional): The path to the credential file.
        purpose (CredentialPurpose, optional): The purpose of the credential.
        trust_domain (str, optional): The trust domain of the credential.
        security_class (str, optional): The security class of the credential.
        cred_type (CredentialType, optional): The type of the credential.
        creation_script (str, optional): The script used to create the credential.
        minimum_lifetime (Union[int, str], optional): The minimum lifetime of the credential in seconds.
        context (Mapping, optional): The context to use for decoding the credential.

    Returns:
        Credential: The credential object.

    Raises:
        CredentialError: If the credential cannot be loaded.
    """

    credential_types = [cred_type] if cred_type else CredentialType
    for c_type in credential_types:
        try:
            credential_class = credential_of_type(c_type)
            if issubclass(credential_class, Credential):
                cred_args = signature(credential_class.__init__).parameters.values()
                cred_args = [param.name for param in cred_args if param.name != "self"]
                kwargs = {key: value for key, value in locals().items() if key in cred_args and value is not None}
                return credential_class(**kwargs)
        except CredentialError as err:
            # pass  # Credential type incompatible with input
            raise CredentialError(f'Could not load credential: string="{string}", path="{path}"') from err
        except Exception as err:
            raise CredentialError(f'Unexpected error loading credential: string="{string}", path="{path}"') from err
    raise CredentialError(f'Could not load credential: string="{string}", path="{path}"')


def create_credential_pair(
    string: Optional[Union[str, bytes]] = None,
    path: Optional[str] = None,
    private_string: Optional[bytes] = None,
    private_path: Optional[str] = None,
    purpose: Optional[CredentialPurpose] = None,
    trust_domain: Optional[str] = None,
    security_class: Optional[str] = None,
    cred_type: Optional[CredentialPairType] = None,
    creation_script: Optional[str] = None,
    minimum_lifetime: Union[int, str] = 0,
    context: Optional[Mapping] = None,
) -> CredentialPair:
    """Creates a credential pair object.

    Args:
        string (bytes, optional): The public credential as a byte string.
        path (str, optional): The path to the public credential file.
        private_string (bytes, optional): The private credential as a byte string.
        private_path (str, optional): The path to the private credential file.
        purpose (CredentialPurpose, optional): The purpose of the credentials.
        trust_domain (str, optional): The trust domain of the credentials.
        security_class (str, optional): The security class of the credentials.
        cred_type (CredentialPairType, optional): The type of the credential pair.
        creation_script (str, optional): The script used to create the credentials.
        minimum_lifetime (Union[int, str], optional): The minimum lifetime of the credentials in seconds.
        context (Mapping, optional): The context to use for decoding the credentials.

    Returns:
        CredentialPair: The credential pair object.

    Raises:
        CredentialError: If the credential pair cannot be loaded.
    """

    credential_types = [cred_type] if cred_type else CredentialPairType
    for c_type in credential_types:
        try:
            credential_class = credential_of_type(c_type)
            if issubclass(credential_class, CredentialPair):
                cred_args = signature(credential_class.__init__).parameters.values()
                cred_args = [param.name for param in cred_args if param.name != "self"]
                kwargs = {key: value for key, value in locals().items() if key in cred_args and value is not None}
                return credential_class(**kwargs)
        except CredentialError:
            pass
        except Exception as err:
            raise CredentialError(
                f'Unexpected error loading credential pair: string="{string}", path="{path}", private_string="{private_string}", private_path="{private_path}"'
            ) from err
    raise CredentialError(
        f'Could not load credential pair: string="{string}", path="{path}", private_string="{private_string}", private_path="{private_path}"'
    )


def standard_path(cred: Credential) -> str:
    """Returns the standard path for a credential.

    Args:
        cred (Credential): The credential object.

    Returns:
        str: The standard path for the credential.
    """

    if not cred.string:
        raise CredentialError("Credential not initialized")
    if not cred.path:
        raise CredentialError("Credential path not set")

    filename = os.path.basename(cred.path)
    if not filename:
        raise CredentialError("Credential path is not a file")

    filename = f"credential_{cred.purpose_alias}_{filename}.{cred.extension}"
    path = os.path.join(os.path.dirname(cred.path), filename)

    return path


def compress_credential(credential_data: bytes) -> bytes:
    """Compresses a credential.

    Args:
        credential_data (bytes): The credential data.

    Returns:
        bytes: The compressed credential.
    """

    with BytesIO() as cfile:
        with gzip.GzipFile(fileobj=cfile, mode="wb") as f:
            # Calling a GzipFile object's close() method does not close fileobj, so cfile is available outside
            f.write(credential_data)
        return base64.b64encode(cfile.getvalue())
