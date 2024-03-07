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
#   Contains information about credentials
#

"""
This module contains classes and functions for managing GlideinWMS credentials.
"""

import base64
import enum
import gzip
import os
import shutil
import tempfile

from abc import ABC, abstractmethod
from datetime import datetime
from hashlib import md5
from io import BytesIO
from typing import Generic, Iterable, List, Mapping, Optional, Set, Type, TypeVar, Union

import jwt
import M2Crypto.EVP
import M2Crypto.X509

from glideinwms.lib import logSupport, pubCrypto, symCrypto
from glideinwms.lib.generators import load_generator
from glideinwms.lib.util import hash_nc, is_str_safe

T = TypeVar("T")


##########################
### Credentials ##########
##########################


class CredentialError(Exception):
    """defining new exception so that we can catch only the credential errors here
    and let the "real" errors propagate up
    """


class CredentialType(enum.Enum):
    """
    Enum representing different types of credentials.
    """

    TOKEN = "token"
    X509_CERT = "x509_cert"
    RSA_KEY = "rsa_key"
    GENERATOR = "generator"
    TEXT = "text"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    @classmethod
    def from_string(cls, string: str) -> "CredentialType":
        """
        Converts a string representation of a credential type to a CredentialType object.

        Args:
            string (str): The string representation of the credential type.

        Returns:
            CredentialType: The corresponding CredentialType enum value.

        Raises:
            CredentialError: If the string does not match any known credential type.
        """

        extended_map = {"scitoken": cls.TOKEN, "grid_proxy": cls.X509_CERT, "auth_file": cls.TEXT}

        string = string.lower()

        try:
            return CredentialType(string)
        except ValueError:
            pass
        if string in extended_map:
            return extended_map[string]
        raise CredentialError(f"Unknown Credential type: {string}")


class CredentialPairType(enum.Enum):
    """
    Enum representing different types of credential pairs.
    """

    X509_PAIR = "x509_pair"
    USERNAME_PASSWORD = "username_password"

    @classmethod
    def from_string(cls, string: str) -> "CredentialPairType":
        """
        Converts a string representation of a credential type to a CredentialPairType object.

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


class CredentialPurpose(enum.Enum):
    """
    Enum representing different purposes for credentials.
    """

    REQUEST = "request"
    PAYLOAD = "payload"

    @classmethod
    def from_string(cls, string: str) -> "CredentialPurpose":
        """
        Converts a string representation of a CredentialPurpose to a CredentialPurpose object.

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
    """
    Represents a credential used for authentication or authorization purposes.

    Args:
        id (Optional[str]): The unique identifier of the credential.
        string (Optional[bytes]): The credential string.
        path (Optional[str]): The path to the credential file.
        purpose (Optional[CredentialPurpose]): The purpose of the credential.
        purpose_alias (Optional[str]): An alias for the purpose of the credential.
        trust_domain (Optional[str]): The trust domain of the credential.
        security_class (Optional[str]): The security class of the credential.

    Attributes:
        cred_type (Optional[CredentialType]): The type of the credential.
        classad_attribute (Optional[str]): The classad attribute associated with the credential.
        extension (Optional[str]): The file extension of the credential.

    Raises:
        CredentialError: If the credential cannot be initialized or loaded.

    """

    cred_type: Optional[CredentialType] = None
    classad_attribute: Optional[str] = None
    extension: Optional[str] = None

    def __init__(
        self,
        string: Optional[bytes] = None,
        path: Optional[str] = None,
        purpose: Optional[CredentialPurpose] = None,
        trust_domain: Optional[str] = None,
        security_class: Optional[str] = None,
    ) -> None:
        self._string = None
        self.path = path
        self.purpose = purpose
        self.trust_domain = trust_domain
        self.security_class = security_class
        if string or path:
            self.load(string, path)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(string={self.string!r}, path={self.path!r}, purpose={self.purpose!r}, trust_domain={self.trust_domain!r}, security_class={self.security_class!r})"

    def __str__(self) -> str:
        return self.string.decode() if self.string else ""

    def __renew__(self) -> None:
        raise NotImplementedError("Renewal not implemented for this credential type")

    @property
    def _payload(self) -> Optional[T]:
        return self.decode(self.string) if self.string else None

    @property
    def string(self) -> Optional[bytes]:
        """
        Credential string.
        """

        return self._string

    @property
    def id(self) -> str:
        """
        Credential unique identifier.
        """

        if not str(self.string):
            raise CredentialError("Credential not initialized")

        return hash_nc(f"{str(self.string)}{self.purpose}{self.trust_domain}{self.security_class}", 8)

    @property
    def purpose(self) -> Optional[CredentialPurpose]:
        """
        Credential purpose.
        """

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
        """
        Credential purpose alias.
        """

        if self._purpose[0]:
            return self._purpose[1] or self._purpose[0].value

    @staticmethod
    @abstractmethod
    def decode(string: bytes) -> T:
        """
        Decode the given string.

        Args:
            string (bytes): The string to decode.

        Returns:
            T: The decoded value.

        """

    @abstractmethod
    def valid(self) -> bool:
        """
        Check if the credentials are valid.

        Returns:
            bool: True if the credential is valid, False otherwise.
        """

    def load_from_string(self, string: bytes) -> None:
        """
        Load the credential from a string.

        Args:
            string (bytes): The credential string to load.

        Raises:
            CredentialError: If the input string is not of type bytes or if the credential cannot be loaded from the string.
        """

        if not isinstance(string, bytes):
            raise CredentialError("Credential string must be bytes")
        try:
            self.decode(string)
        except Exception as err:
            raise CredentialError(f"Could not load credential from string: {string}") from err
        self._string = string

    def load_from_file(self, path: str) -> None:
        """
        Load credentials from a file.

        Args:
            path (str): The path to the credential file.

        Raises:
            CredentialError: If the specified file does not exist.
        """

        if not os.path.isfile(path):
            raise CredentialError(f"Credential file {self.path} does not exist")
        with open(path, "rb") as cred_file:
            self.load_from_string(cred_file.read())
        self.path = path

    def load(self, string: Optional[bytes] = None, path: Optional[str] = None) -> None:
        """
        Load credentials from either a string or a file.

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
        """
        Save the credential to a file.

        Args:
            path (Optional[str]): The path to the file where the credential will be saved.
            permissions (int): The permissions to set for the saved file. Default is 0o600.
            backup (bool): Whether to create a backup of the existing file. Default is False.
            compress (bool): Whether to compress the credential before saving. Default is False.
            data_pattern (Optional[bytes]): A pattern to format the credential data before saving. Default is None.
            overwrite (bool): Whether to overwrite the existing file if it already exists. Default is True.
            continue_if_no_path (bool): If True, silently return if no path is specified. Default is False.

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
            # NOTE: NamedTemporaryFile is creted in private mode by default (0600)
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
                os.replace(fd.name, path)
        except OSError as err:
            raise CredentialError(f"Could not save credential to {path}: {err}") from err

    def renew(self) -> None:
        """
        Renews the credentials.

        This method attempts to renew the credentials by calling the private __renew__ method.
        If the __renew__ method is not implemented, it will silently pass.
        """
        try:
            self.__renew__()
        except NotImplementedError:
            pass


class CredentialPair:
    """
    Represents a pair of credentials, consisting of a public and private credential.

    NOTE: This class requires a Credential subclass as a second base class.

    Args:
        string (Optional[bytes]): The public credential as a byte string.
        path (Optional[str]): The path to the public credential file.
        private_string (Optional[bytes]): The private credential as a byte string.
        private_path (Optional[str]): The path to the private credential file.
        purpose (Optional[CredentialPurpose]): The purpose of the credentials.
        trust_domain (Optional[str]): The trust domain of the credentials.
        security_class (Optional[str]): The security class of the credentials.

    Attributes:
        cred_type (Optional[CredentialPairType]): The type of the credential pair.
        private_credential (Credential): The private credential associated with this pair.
        NOTE: Includes all attributes from the Credential class.
    """

    cred_type: Optional[CredentialPairType] = None

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
        if len(self.__class__.__bases__) < 2 or not issubclass(self.__class__.__bases__[1], Credential):
            raise CredentialError("CredentialPair requires a Credential subclass as second base class")

        credential_class = self.__class__.__bases__[1]
        super(credential_class, self).__init__(  # pylint: disable=bad-super-call # type: ignore[call-arg]
            string, path, purpose, trust_domain, security_class
        )  # pylint: disable=bad-super-call # type: ignore[call-arg]
        self.private_credential = credential_class(private_string, private_path, purpose, trust_domain, security_class)

    def renew(self) -> None:
        """
        Renews the credentials by calling the __renew__() method on both the public and private credentials.
        """

        try:
            self.__renew__()  # pylint: disable=no-member # type: ignore[attr-defined]
            self.private_credential.__renew__()
        except NotImplementedError:
            pass


# Dictionary of Credentials
class CredentialDict(dict):
    """
    A dictionary-like class for storing credentials.

    This class extends the built-in `dict` class and provides additional
    functionality for storing and retrieving `Credential` objects.
    """

    def __setitem__(self, __k, __v):
        if not isinstance(__v, Credential):
            raise TypeError("Value must be a credential")
        super().__setitem__(__k, __v)

    def add(self, credential: Credential, credential_id: Optional[str] = None):
        """
        Add a credential to the dictionary.

        Args:
            credential (Credential): The credential object to add.
            id (str, optional): The ID to use as the key in the dictionary.
                If not provided, the credential's ID will be used.
        """
        if not isinstance(credential, Credential):
            raise TypeError("Value must be a credential")
        self[credential_id or credential.id] = credential


class CredentialGenerator(Credential[Credential]):
    """
    Represents a credential generator used for generating credentials.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        classad_attribute (str): The classad attribute associated with the credential.
        path (str): The path of the credential file.
    """

    cred_type = CredentialType.GENERATOR
    classad_attribute = "CredentialGenerator"

    def __init__(
        self, string: Optional[bytes] = None, path: Optional[str] = None
    ) -> None:  # pylint: disable=super-init-not-called
        if not string:
            string = path.encode() if path else None
        if not string:
            raise CredentialError("No string or path specified")
        self._string = string
        self.path = None
        self.load(string)

    def __renew__(self) -> None:
        self.load(self._string)

    @property
    def _payload(self) -> Optional[Credential]:
        return self.decode(self._string) if self._string else None

    @property
    def string(self) -> Optional[bytes]:
        return self._payload.string if self._payload else None

    @staticmethod
    def decode(string: bytes) -> Credential:
        generator = load_generator(string.decode())
        return create_credential(generator.generate())

    def valid(self) -> bool:
        if self._payload:
            return self._payload.valid()
        return False

    def load_from_file(self, path: str) -> None:
        raise CredentialError("Cannot load CredentialGenerator from file")

    def load(self, string: Optional[bytes] = None, path: Optional[str] = None) -> None:
        if string:
            self.load_from_string(string)
            self.cred_type = self._payload.cred_type if self._payload else self.cred_type
            self.classad_attribute = self._payload.classad_attribute if self._payload else self.classad_attribute
            if path:
                self.path = path
        else:
            raise CredentialError("No string specified")


class Token(Credential[Mapping]):
    """
    Represents a token credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        classad_attribute (str): The name of the attribute in the classad.
        extension (str): The file extension for the token.
        scope (Optional[str]): The scope of the token.
        issue_time (Optional[datetime]): The issue time of the token.
        not_before_time (Optional[datetime]): The not-before time of the token.
        expiration_time (Optional[datetime]): The expiration time of the token.
    """

    cred_type = CredentialType.TOKEN
    classad_attribute = "ScitokenId"  # TODO: We might want to change this name to "TokenId" in the future
    extension = "jwt"

    @property
    def scope(self) -> Optional[str]:
        """
        Token scope.
        """
        return self._payload.get("scope", None) if self._payload else None

    @property
    def issue_time(self) -> Optional[datetime]:
        """
        Token issue time.
        """
        return datetime.fromtimestamp(self._payload.get("iat", None)) if self._payload else None

    @property
    def not_before_time(self) -> Optional[datetime]:
        """
        Token not-before time.
        """
        return datetime.fromtimestamp(self._payload.get("nbf", None)) if self._payload else None

    @property
    def expiration_time(self) -> Optional[datetime]:
        """
        Token expiration time.
        """
        return datetime.fromtimestamp(self._payload.get("exp", None)) if self._payload else None

    @staticmethod
    def decode(string: bytes) -> Mapping:
        return jwt.decode(string.decode().strip(), options={"verify_signature": False})

    def valid(self) -> bool:
        if self.not_before_time and self.expiration_time:
            return self.not_before_time < datetime.now() < self.expiration_time
        else:
            return False


class X509Cert(Credential[M2Crypto.X509.X509]):
    """
    Represents an X.509 certificate credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        classad_attribute (str): The attribute name used in ClassAds.
        extension (str): The file extension for the credential.
        pub_key (Optional[M2Crypto.EVP.PKey]): The public key of the certificate.
        not_before_time (Optional[datetime]): The not-before time of the certificate.
        not_after_time (Optional[datetime]): The not-after time of the certificate.
    """

    cred_type = CredentialType.X509_CERT
    classad_attribute = "SubmitProxy"
    extension = "pem"

    @property
    def pub_key(self) -> Optional[M2Crypto.EVP.PKey]:
        """
        X.509 public key.
        """
        return self._payload.get_pubkey() if self._payload else None

    @property
    def not_before_time(self) -> Optional[datetime]:
        """
        X.509 not-before time.
        """
        return self._payload.get_not_before().get_datetime() if self._payload else None

    @property
    def not_after_time(self) -> Optional[datetime]:
        """
        X.509 not-after time.
        """
        return self._payload.get_not_after().get_datetime() if self._payload else None

    @staticmethod
    def decode(string: bytes) -> M2Crypto.X509.X509:
        return M2Crypto.X509.load_cert_string(string)

    def valid(self) -> bool:
        if self.not_before_time and self.not_after_time:
            return self.not_before_time < datetime.now(self.not_before_time.tzinfo) < self.not_after_time
        else:
            return False


class RSAKey(Credential[pubCrypto.RSAKey]):
    """
    Represents an RSA key credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        classad_attribute (str): The attribute name used in ClassAds.
        extension (str): The file extension for the key.
        pub_key (Optional[pubCrypto.PubRSAKey]): The public key of the RSA key.
        pub_key_id (Optional[str]): The ID of the public key.
        key_type (Optional[str]): The type of the RSA key.
    """

    cred_type = CredentialType.RSA_KEY
    classad_attribute = "RSAKey"
    extension = "rsa"

    @property
    def pub_key(self) -> Optional[pubCrypto.PubRSAKey]:
        """
        RSA public key.
        """
        return self._payload.PubRSAKey() if self._payload else None

    @property
    def pub_key_id(self) -> Optional[str]:
        """
        RSA public key ID.
        """
        return (
            md5(b" ".join((self.key_type.encode("utf-8"), self.pub_key.get()))).hexdigest()
            if self.key_type and self.pub_key
            else None
        )

    @property
    def key_type(self) -> Optional[str]:
        """
        RSA key type.

        NOTE: This property always returns "RSA" if the key is initialized.
        """
        return "RSA" if self._payload else None

    @staticmethod
    def decode(string: bytes) -> pubCrypto.RSAKey:
        return pubCrypto.RSAKey(key_str=string)

    def valid(self) -> bool:
        return self._payload is not None and self.pub_key is not None and self.pub_key_id is not None

    def recreate(self) -> None:
        """
        Recreates the RSA key.

        Raises:
            CredentialError: If the RSA key is not initialized.
        """
        if self._payload is None:
            raise CredentialError("RSAKey not initialized")

        new_key = self._payload
        new_key.new()
        self.load_from_string(new_key.get())
        if self.path:
            self.save_to_file(self.path)

    def extract_sym_key(self, enc_sym_key) -> symCrypto.AutoSymKey:
        """
        Extracts the symmetric key using the RSA key.

        Args:
            enc_sym_key: The encrypted symmetric key.

        Returns:
            symCrypto.AutoSymKey: The extracted symmetric key.

        Raises:
            CredentialError: If the RSA key is not initialized.
        """
        if self._payload is None:
            raise CredentialError("RSAKey not initialized")

        return symCrypto.AutoSymKey(self._payload.decrypt_hex(enc_sym_key))


class TextCredential(Credential[bytes]):
    """
    Represents a text-based credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        classad_attribute (str): The attribute name used in ClassAds.
        extension (str): The file extension for the credential.
    """

    cred_type = CredentialType.TEXT
    classad_attribute = "AuthFile"
    extension = "txt"

    @staticmethod
    def decode(string: bytes) -> bytes:
        return string

    def valid(self) -> bool:
        return True


class X509Pair(CredentialPair, X509Cert):
    """
    Represents a pair of X509 certificates, consisting of a public certificate and a private certificate.

    This class extends both the `CredentialPair` and `X509Cert` classes.

    Args:
        string (Optional[bytes]): The public certificate as a byte string.
        path (Optional[str]): The path to the public certificate file.
        private_string (Optional[bytes]): The private certificate as a byte string.
        private_path (Optional[str]): The path to the private certificate file.
        purpose (Optional[CredentialPurpose]): The purpose of the credentials.
        trust_domain (Optional[str]): The trust domain of the credentials.
        security_class (Optional[str]): The security class of the credentials.

    Attributes:
        cred_type (CredentialPairType): The type of the credential pair.
        classad_attribute (str): The attribute name used in the ClassAd for the public certificate.
        private_credential (X509Cert): The private certificate associated with this pair.
        NOTE: Includes all attributes from the X509Cert class.
    """

    cred_type = CredentialPairType.X509_PAIR

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
        super().__init__(string, path, private_string, private_path, purpose, trust_domain, security_class)
        self.classad_attribute = "PublicCert"
        self.private_credential.classad_attribute = "PrivateCert"


class UsernamePassword(CredentialPair, TextCredential):
    """
    Represents a username and password credential pair.

    This class extends both the `CredentialPair` and `TextCredential` classes.

    Args:
        string (Optional[bytes]): The username as a byte string.
        path (Optional[str]): The path to the username file.
        private_string (Optional[bytes]): The password as a byte string.
        private_path (Optional[str]): The path to the password file.
        purpose (Optional[CredentialPurpose]): The purpose of the credentials.
        trust_domain (Optional[str]): The trust domain of the credentials.
        security_class (Optional[str]): The security class of the credentials.

    Attributes:
        cred_type (CredentialPairType): The type of the credential pair.
        classad_attribute (str): The classad attribute for the username.
        private_credential (Credential): The private credential object for the password.
        NOTE: Includes all attributes from the TextCredential class.
    """

    cred_type = CredentialPairType.USERNAME_PASSWORD

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
        super().__init__(string, path, private_string, private_path, purpose, trust_domain, security_class)
        self.classad_attribute = "Username"
        self.private_credential.classad_attribute = "Password"


class RequestCredential:
    """
    Represents an extended credential used for requesting resources.

    Args:
        credential (Credential): The credential object.

    Attributes:
        credential (Credential): The credential object.
        advertize (bool): Flag indicating whether to advertise the credential.
        req_idle (int): Number of idle jobs requested.
        req_max_run (int): Maximum number of running jobs requested.
    """

    def __init__(
        self,
        credential: Credential,
    ):
        self.credential = credential
        self.advertize: bool = True
        self.req_idle: int = 0
        self.req_max_run: int = 0

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(credential={self.credential!s}, advertize={self.advertize}, req_idle={self.req_idle}, req_max_run={self.req_max_run})"

    def __str__(self) -> str:
        return f"{self.credential!s}"

    def add_usage_details(self, req_idle=0, req_max_run=0):
        """
        Add usage details to the request.

        Args:
            req_idle (int): Number of idle jobs requested.
            req_max_run (int): Maximum number of running jobs requested.
        """
        self.req_idle = req_idle
        self.req_max_run = req_max_run


def credential_type_from_string(string: str) -> Union[CredentialType, CredentialPairType]:
    """
    Returns the credential type for a given string.

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
    cred_type: Union[CredentialType, CredentialPairType]
) -> Union[Type[Credential], Type[CredentialPair]]:
    """Returns the credential subclass for the given type.

    Args:
        cred_type (CredentialType): credential type

    Raises:
        CredentialError: if the credential type is unknown

    Returns:
        Credential: credential subclass
    """

    for c in [Credential, CredentialPair]:
        class_dict = {}
        for i in c.__subclasses__():
            class_dict[i.cred_type] = i
        try:
            return class_dict[cred_type]
        except KeyError:
            pass
    raise CredentialError(f"Unknown Credential type: {cred_type}")


def create_credential(
    string: Optional[bytes] = None,
    path: Optional[str] = None,
    purpose: Optional[CredentialPurpose] = None,
    trust_domain: Optional[str] = None,
    security_class: Optional[str] = None,
    cred_type: Optional[CredentialType] = None,
) -> Credential:
    """
    Creates a credential object.

    Args:
        string (bytes, optional): The credential as a byte string.
        path (str, optional): The path to the credential file.
        purpose (CredentialPurpose, optional): The purpose of the credential.
        trust_domain (str, optional): The trust domain of the credential.
        security_class (str, optional): The security class of the credential.
        cred_type (CredentialType, optional): The type of the credential.

    Returns:
        Credential: The credential object.
    """

    credential_types = [cred_type] if cred_type else CredentialType
    for cred_type in credential_types:
        try:
            credential_class = credential_of_type(cred_type)
            if issubclass(credential_class, Credential):
                return credential_class(string, path, purpose, trust_domain, security_class)
        except CredentialError:
            pass  # Credential type incompatible with input
        except Exception as err:
            raise CredentialError(f'Unexpected error loading credential: string="{string}", path="{path}"') from err
    raise CredentialError(f'Could not load credential: string="{string}", path="{path}"')


def create_credential_pair(
    string: Optional[bytes] = None,
    path: Optional[str] = None,
    private_string: Optional[bytes] = None,
    private_path: Optional[str] = None,
    purpose: Optional[CredentialPurpose] = None,
    trust_domain: Optional[str] = None,
    security_class: Optional[str] = None,
    cred_type: Optional[CredentialPairType] = None,
) -> CredentialPair:
    """
    Creates a credential pair object.

    Args:
        string (bytes, optional): The public credential as a byte string.
        path (str, optional): The path to the public credential file.
        private_string (bytes, optional): The private credential as a byte string.
        private_path (str, optional): The path to the private credential file.
        purpose (CredentialPurpose, optional): The purpose of the credentials.
        trust_domain (str, optional): The trust domain of the credentials.
        security_class (str, optional): The security class of the credentials.
        cred_type (CredentialPairType, optional): The type of the credential pair.

    Returns:
        CredentialPair: The credential pair object.
    """

    credential_types = [cred_type] if cred_type else CredentialPairType
    for cred_type in credential_types:
        try:
            credential_class = credential_of_type(cred_type)
            if issubclass(credential_class, CredentialPair):
                return credential_class(
                    string, path, private_string, private_path, purpose, trust_domain, security_class
                )
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
    """
    Returns the standard path for a credential.

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
    """
    Compresses a credential.

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


##########################
### Parameters ###########
##########################


class ParameterName(enum.Enum):
    """
    Enum representing different parameter names.
    """

    VM_ID = "VMId"
    VM_TYPE = "VMType"
    GLIDEIN_PROXY = "GlideinProxy"
    REMOTE_USERNAME = "RemoteUsername"
    PROJECT_ID = "ProjectId"

    @classmethod
    def from_string(cls, string: str) -> "ParameterName":
        """
        Converts a string representation of a parameter name to a ParameterName object.

        Args:
            string (str): The string representation of the parameter name.

        Returns:
            ParameterName: The corresponding ParameterName object.

        Raises:
            CredentialError: If the string does not match any known parameter name.
        """

        extended_map = {"vm_id": cls.VM_ID, "vm_type": cls.VM_TYPE}
        extended_map.update({param.value.lower(): param for param in cls})

        string = string.lower()

        try:
            return ParameterName(string)
        except ValueError:
            pass
        if string in extended_map:
            return extended_map[string]
        raise CredentialError(f"Unknown Parameter name: {string}")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class ParameterType(enum.Enum):
    """
    Enum representing different types of parameters.
    """

    GENERATOR = "generator"
    STATIC = "static"

    @classmethod
    def from_string(cls, string: str) -> "ParameterType":
        """
        Create a ParameterType object from a string representation.

        Args:
            string (str): The string representation of the ParameterType.

        Returns:
            ParameterType: The created ParameterType object.
        """

        string = string.lower()
        return ParameterType(string)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class Parameter:
    """
    Represents a parameter with a name and value.

    Args:
        name (ParameterName): The name of the parameter.
        value (str): The value of the parameter.

    Attributes:
        param_type (ParameterType): The type of the parameter.
        name (ParameterName): The name of the parameter.
        value (str): The value of the parameter.
    """

    param_type = ParameterType.STATIC

    def __init__(self, name: ParameterName, value: str):
        if not isinstance(name, ParameterName):
            raise TypeError("Name must be a ParameterName")
        self._name = name
        self._value = value

    @property
    def name(self) -> ParameterName:
        """
        Parameter name.
        """

        return self._name

    @property
    def value(self):
        """
        Parameter value.
        """

        return self._value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self._name.value!r}, value={self._value!r}, param_type={self.param_type.value!r})"

    def __str__(self) -> str:
        return f"{self.name.value}={self.value}"


class ParameterGenerator(Parameter):
    """
    A class representing a generator parameter.

    This class inherits from the base `Parameter` class and is used to define parameters
    that generate their values dynamically using a generator function.

    Args:
        name (ParameterName): The name of the parameter.
        generator (str): The name of the generator to use.

    Attributes:
        param_type (ParameterType): The type of the parameter (GENERATOR).
        name (ParameterName): The name of the parameter.
        value (str): The value of the parameter.
    """

    param_type = ParameterType.GENERATOR

    def __init__(self, name: ParameterName, generator: str):
        try:
            self._generator = load_generator(generator)
        except ImportError as err:
            raise TypeError(f"Could not load generator: {generator}") from err

        super().__init__(name, generator)

    @property
    def value(self):
        return self._generator.generate()


class ParameterDict(dict):
    """
    A dictionary subclass for storing parameters.

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
        """
        Adds a parameter to the dictionary.

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
    class_dict[ParameterType.STATIC] = Parameter
    try:
        return class_dict[param_type]
    except KeyError as err:
        raise CredentialError(f"Unknown Parameter type: {param_type}") from err


def create_parameter(name: ParameterName, value: str, param_type: Optional[ParameterType] = None) -> Parameter:
    """
    Creates a parameter.

    Args:
        name (ParameterName): The name of the parameter.
        value (str): The value of the parameter.
        param_type (ParameterType, optional): The type of the parameter.

    Returns:
        Parameter: The parameter object.
    """

    parameter_types = [param_type] if param_type else ParameterType
    for param_type in parameter_types:
        try:
            parameter_class = parameter_of_type(param_type)
            if issubclass(parameter_class, Parameter):
                return parameter_class(name, value)
        except TypeError:
            pass  # Parameter type incompatible with input
        except Exception as err:
            raise CredentialError(f'Unexpected error loading parameter: name="{name}", value="{value}"') from err
    raise CredentialError(f'Could not load parameter: name="{name}", value="{value}"')


##########################
### Tools ###############
##########################


class SecurityBundle:
    """
    Represents a security bundle used for submitting jobs.

    Args:
        username (str): The username for the security bundle.
        security_class (str): The security class for the security bundle.
    """

    def __init__(self):
        self.credentials = CredentialDict()
        self.parameters = ParameterDict()

    def add_credential(self, credential, credential_id=None):
        """
        Adds a credential to the security bundle.

        Args:
            credential (Credential): The credential to add.
            credential_id (str, optional): The ID to use as the key in the dictionary.
                If not provided, the credential's ID will be used.
        """

        self.credentials.add(credential, credential_id)

    def add_parameter(self, parameter: Parameter):
        """
        Adds a parameter to the security bundle.

        Args:
            parameter (Parameter): The parameter to add.
        """

        self.parameters.add(parameter)

    def load_from_element(self, element_descript):
        """
        Load the security bundle from an element descriptor.

        Args:
            element_descript (ElementDescriptor): The element descriptor to load from.
        """

        for path in element_descript.merged_data["Proxies"]:
            cred_type = credential_type_from_string(element_descript.merged_data["ProxyTypes"].get(path))
            purpose = element_descript.merged_data["CredentialPurposes"].get(path)
            trust_domain = element_descript.merged_data["ProxyTrustDomains"].get(path, "None")
            security_class = element_descript.merged_data["ProxySecurityClasses"].get(path, id)
            if isinstance(cred_type, CredentialType):
                credential = create_credential(
                    path=path,
                    purpose=purpose,
                    trust_domain=trust_domain,
                    security_class=security_class,
                    cred_type=cred_type,
                )
            else:
                cred_key = element_descript.merged_data["ProxyKeyFiles"].get(path, None)
                credential = create_credential_pair(
                    path=path,
                    private_path=cred_key,
                    purpose=purpose,
                    trust_domain=trust_domain,
                    security_class=security_class,
                    cred_type=cred_type,
                )
            self.add_credential(credential)
        for name, data in element_descript.merged_data["Parameters"].items():
            parameter = create_parameter(
                ParameterName.from_string(name), data["value"], ParameterType.from_string(data["type"])
            )
            self.add_parameter(parameter)


class SubmitBundle:
    """
    Represents a submit bundle used for submitting jobs.

    Args:
        username (str): The username for the submit bundle.
        security_class (str): The security class for the submit bundle.

    Attributes:
        username (str): The username for the submit bundle.
        security_class (str): The security class for the submit bundle.
        id (str): The ID used for tracking the submit credentials.
        cred_dir (str): The location of the credentials.
        security_credentials (CredentialDict): A dictionary of security credentials.
        identity_credentials (CredentialDict): A dictionary of identity credentials.
        parameters (ParameterDict): A dictionary of parameters.
    """

    def __init__(self, username: str, security_class: str):
        self.username = username
        self.security_class = security_class
        self.id = None  # id used for tacking the submit credentials
        self.cred_dir = ""  # location of credentials
        self.security_credentials = CredentialDict()
        self.identity_credentials = CredentialDict()
        self.parameters = ParameterDict()

    def add_security_credential(
        self,
        cred_id: str,
        cred_name: Optional[str] = None,
        credential: Optional[Credential] = None,
        prefix: Optional[str] = "credential_",
    ) -> bool:
        """
        Adds a security credential.

        Args:
            cred_id (str): The ID of the credential.
            cred_name (str, optional): The name of the credential file.
            credential (Credential, optional): The credential object.
            prefix (str, optional): The prefix to use when looking for the credential file.

        Returns:
            bool: True if the credential was added, otherwise False.
        """

        if credential:
            self.security_credentials[cred_id] = credential
            return True
        if cred_name:
            if not is_str_safe(cred_name):
                return False

            cred_path = os.path.join(self.cred_dir, f"{prefix}{cred_name}")
            if not os.path.isfile(cred_path):
                return False

            self.security_credentials[cred_id] = create_credential(path=cred_path)
            return True

        return False

    def add_factory_credential(self, cred_id: str, credential: Credential) -> bool:
        """
        Adds a factory provided security credential.

        Args:
            cred_id (str): The ID of the credential.
            credential (Credential): The credential object.

        Returns:
            bool: True if the credential was added, otherwise False.
        """

        self.security_credentials[cred_id] = credential
        return True

    def add_identity_credential(self, cred_id: str, credential: Credential) -> bool:
        """
        Adds an identity credential.

        Args:
            cred_id (str): The ID of the credential.
            credential (Credential): The credential object.

        Returns:
            bool: True if the credential was added, otherwise False.
        """

        self.identity_credentials[cred_id] = credential
        return True

    def add_parameter(self, param_id: ParameterName, param_value) -> bool:
        """
        Adds a parameter.

        Args:
            param_id (ParameterName): The ID of the parameter.
            param_value (str): The value of the parameter.

        Returns:
            bool: True if the parameter was added, otherwise False.
        """

        self.parameters[param_id] = param_value
        return True


class AuthenticationSet:
    """
    Represents a set of authentication requirements.

    Args:
        auth_set (Iterable[Union[CredentialType, CredentialPairType, ParameterName]]): The set of authentication requirements.
    """

    _required_types: Set[Union[CredentialType, CredentialPairType, ParameterName]] = set()

    def __init__(self, set_types: Iterable[CredentialType]):
        for item_type in set_types:
            if (
                not isinstance(item_type, CredentialType)
                and not isinstance(item_type, CredentialPairType)
                and not isinstance(item_type, ParameterName)
            ):
                raise TypeError(f"Invalid credential type: {item_type}")
        self._required_types = set(set_types)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"

    def __str__(self) -> str:
        return ",".join(str(cred_type) for cred_type in self._required_types)

    def supports(self, cred_type: Union[CredentialType, CredentialPairType, ParameterName, str]) -> bool:
        """
        Checks if the authentication set supports a given credential type.

        Args:
            cred_type (Union[CredentialType, CredentialPairType, ParameterName, str]): The credential type to check.

        Returns:
            bool: True if the credential type is supported, otherwise False.
        """

        if isinstance(cred_type, str):
            str_type = cred_type
            try:
                cred_type = CredentialType.from_string(str_type)
            except CredentialError:
                pass
            try:
                cred_type = CredentialPairType.from_string(str_type)
            except CredentialError:
                pass
            try:
                cred_type = ParameterName.from_string(str_type)
            except CredentialError:
                pass
        return cred_type in self._required_types

    def satisfied_by(self, cred_types: Iterable[CredentialType]) -> bool:
        """
        Checks if the authentication set is satisfied by a given set of credential types.

        Args:
            cred_types (Iterable[CredentialType]): The set of credential types to check.

        Returns:
            bool: True if the authentication set is satisfied, otherwise False.
        """

        return self._required_types.issubset(cred_types)


class AuthenticationMethod:
    """
    Represents an authentication method used for authenticating users.

    Args:
        auth_method (str): The authentication method.
    """

    def __init__(self, auth_method: str):
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
        """
        Loads the authentication method from a string.

        Args:
            auth_method (str): The authentication method.
        """

        for group in auth_method.split(";"):
            if group.lower() == "any":
                self._requirements.append([])
            else:
                options = []
                for option in group.split(","):
                    parsed_option = None
                    try:
                        parsed_option = CredentialType.from_string(option)
                    except CredentialError:
                        pass
                    try:
                        parsed_option = CredentialPairType.from_string(option)
                    except CredentialError:
                        pass
                    try:
                        parsed_option = ParameterName.from_string(option)
                    except CredentialError:
                        pass
                    if parsed_option:
                        options.append(parsed_option)
                    else:
                        raise CredentialError(f"Unknown authentication requirement: {option}")
                self._requirements.append(options)

    def match(self, security_bundle: SecurityBundle) -> Optional[AuthenticationSet]:
        """
        Matches the authentication method to a security bundle and returns the authentication set if the requirements are met.

        Args:
            security_bundle (SecurityBundle): The security bundle to match.

        Returns:
            Optional[AuthenticationSet]: The authentication set if the security bundle matches the requirements, otherwise None.
        """

        if not self._requirements:
            return AuthenticationSet([])

        auth_set = []
        sec_items = {credential.cred_type for credential in security_bundle.credentials.values() if credential.valid()}
        sec_items.update({parameter for parameter in security_bundle.parameters.keys()})
        for group in self._requirements:
            for option in group:
                if option in sec_items:
                    auth_set.append(option)
                    break
                return None
        return AuthenticationSet(auth_set)
