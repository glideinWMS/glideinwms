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

import base64
import enum
import gzip
import os
import pickle
import shutil
import sys
import tempfile

from abc import ABC, abstractmethod
from datetime import datetime
from hashlib import md5
from importlib import import_module
from io import BytesIO
from typing import Generic, Iterable, List, Mapping, Optional, Set, Type, TypeVar, Union

import jwt
import M2Crypto.EVP
import M2Crypto.X509

from glideinwms.lib import logSupport, pubCrypto, symCrypto
from glideinwms.lib.generators import Generator, load_generator
from glideinwms.lib.util import hash_nc, is_str_safe

sys.path.append("/etc/gwms-frontend/plugin.d")
plugins = {}

T = TypeVar("T")

SUPPORTED_AUTH_METHODS = [
    "grid_proxy",
    "x509_cert",
    "rsa_key",
    "auth_file",
    "username_password",
    "idtoken",
    "scitoken",
]


class CredentialError(Exception):
    """defining new exception so that we can catch only the credential errors here
    and let the "real" errors propagate up
    """


class CredentialType(enum.Enum):
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
    X509_PAIR = "x509_pair"
    USERNAME_PASSWORD = "username_password"

    @classmethod
    def from_string(cls, string: str) -> "CredentialPairType":
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
    # TODO: Better define these
    PILOT = "pilot"
    FACTORY = "factory"
    FRONTEND = "frontend"
    PAYLOAD = "payload"

    @classmethod
    def from_string(cls, string: str) -> "CredentialPurpose":
        string = string.lower()
        return CredentialPurpose(string)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class ParameterName(enum.Enum):
    VM_ID = "VMId"
    VM_TYPE = "VMType"
    GLIDEIN_PROXY = "GlideinProxy"
    REMOTE_USERNAME = "RemoteUsername"
    PROJECT_ID = "ProjectId"

    @classmethod
    def from_string(cls, string: str) -> "ParameterName":
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
    GENERATOR = "generator"
    STATIC = "static"

    @classmethod
    def from_string(cls, string: str) -> "ParameterType":
        string = string.lower()
        return ParameterType(string)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class TrustDomain(enum.Enum):
    GRID = "grid"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class Credential(ABC, Generic[T]):
    cred_type: Optional[CredentialType] = None
    classad_attribute: Optional[str] = None

    def __init__(
        self,
        string: Optional[bytes] = None,
        path: Optional[str] = None,
        purpose: Optional[CredentialPurpose] = None,
        trust_domain: Optional[TrustDomain] = None,
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
        return self._string

    @property
    def id(self) -> str:
        if not str(self.string):
            raise CredentialError("Credential not initialized")

        return hash_nc(f"{str(self.string)}{self.purpose}{self.trust_domain}{self.security_class}", 8)

    @staticmethod
    @abstractmethod
    def decode(string: bytes) -> T:
        pass

    @abstractmethod
    def valid(self) -> bool:
        pass

    def load_from_string(self, string: bytes) -> None:
        if not isinstance(string, bytes):
            raise CredentialError("Credential string must be bytes")
        try:
            self.decode(string)
        except Exception as err:
            raise CredentialError(f"Could not load credential from string: {string}") from err
        self._string = string

    def load_from_file(self, path: str) -> None:
        if not os.path.isfile(path):
            raise CredentialError(f"Credential file {self.path} does not exist")
        with open(path, "rb") as cred_file:
            self.load_from_string(cred_file.read())
        self.path = path

    def load(self, string: Optional[bytes] = None, path: Optional[str] = None) -> None:
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
        try:
            self.__renew__()
        except NotImplementedError:
            pass


class CredentialPair:
    cred_type: Optional[CredentialPairType] = None

    def __init__(
        self,
        string: Optional[bytes] = None,
        path: Optional[str] = None,
        private_string: Optional[bytes] = None,
        private_path: Optional[str] = None,
        purpose: Optional[CredentialPurpose] = None,
        trust_domain: Optional[TrustDomain] = None,
        security_class: Optional[str] = None,
    ) -> None:
        if len(self.__class__.__bases__) < 2 or not issubclass(self.__class__.__bases__[1], Credential):
            raise CredentialError("CredentialPair requires a Credential subclass as second base class")

        credential_class = self.__class__.__bases__[1]
        super(credential_class, self).__init__(
            string, path, purpose, trust_domain, security_class
        )  # pylint: disable=bad-super-call # type: ignore[call-arg]
        self.private_credential = credential_class(private_string, private_path, purpose, trust_domain, security_class)

    def renew(self) -> None:
        try:
            self.__renew__()  # pylint: disable=no-member # type: ignore[attr-defined]
            self.private_credential.__renew__()
        except NotImplementedError:
            pass


# Dictionary of Credentials
class CredentialDict(dict):
    def __setitem__(self, __k, __v):
        if not isinstance(__v, Credential):
            raise TypeError("Value must be a credential")
        super().__setitem__(__k, __v)
    
    def add(self, credential: Credential, id: Optional[str] = None):
        if not isinstance(credential, Credential):
            raise TypeError("Value must be a credential")
        self[id or credential.id] = credential
    
    def pack(self) -> bytes:
        return pickle.dumps(self)
    
    @staticmethod
    def unpack(data: bytes) -> "CredentialDict":
        obj = pickle.loads(data)
        if not isinstance(obj, CredentialDict):
            raise TypeError("Unpacked object is not a CredentialDict")
        return obj

    @classmethod
    def from_list(cls, credentials: Iterable[Credential]) -> "CredentialDict":
        obj = cls()
        for credential in credentials:
            obj.add(credential)
        return obj


class Parameter:
    param_type = ParameterType.STATIC

    def __init__(self, name: ParameterName, value: str):
        if not isinstance(name, ParameterName):
            raise TypeError("Name must be a ParameterName")
        self._name = name
        self._value = value

    @property
    def name(self) -> ParameterName:
        return self._name

    @property
    def value(self):
        return self._value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self._name.value!r}, value={self._value!r}, param_type={self.param_type.value!r})"

    def __str__(self) -> str:
        return f"{self.name.value}={self.value}"


class ParameterGenerator(Parameter):
    param_type = ParameterType.GENERATOR

    def __init__(self, name: ParameterName, value: str):
        try:
            self._generator = load_generator(value)
        except ImportError as err:
            raise TypeError(f"Could not load generator: {value}") from err

        super().__init__(name, value)

    @property
    def value(self):
        return self._generator.generate()


class ParameterDict(dict):
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
        if not isinstance(parameter, Parameter):
            raise TypeError("Parameter must be a Parameter")
        self[parameter.name] = parameter


class CredentialGenerator(Credential[Credential]):
    cred_type = CredentialType.GENERATOR
    classad_attribute = "CredentialGenerator"

    def __init__(self, string: Optional[bytes] = None, path: Optional[str] = None) -> None:
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
    cred_type = CredentialType.TOKEN
    classad_attribute = "ScitokenId"  # TODO: We might want to change this name to "TokenId" in the future

    @property
    def scope(self) -> Optional[str]:
        return self._payload.get("scope", None) if self._payload else None

    @property
    def issue_time(self) -> Optional[datetime]:
        return datetime.fromtimestamp(self._payload.get("iat", None)) if self._payload else None

    @property
    def not_before_time(self) -> Optional[datetime]:
        return datetime.fromtimestamp(self._payload.get("nbf", None)) if self._payload else None

    @property
    def expiration_time(self) -> Optional[datetime]:
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
    cred_type = CredentialType.X509_CERT
    classad_attribute = "SubmitProxy"

    @property
    def pub_key(self) -> Optional[M2Crypto.EVP.PKey]:
        return self._payload.get_pubkey() if self._payload else None

    @property
    def not_before_time(self) -> Optional[datetime]:
        return self._payload.get_not_before().get_datetime() if self._payload else None

    @property
    def not_after_time(self) -> Optional[datetime]:
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
    cred_type = CredentialType.RSA_KEY
    classad_attribute = "RSAKey"

    @property
    def pub_key(self) -> Optional[pubCrypto.PubRSAKey]:
        return self._payload.PubRSAKey() if self._payload else None

    @property
    def pub_key_id(self) -> Optional[str]:
        return (
            md5(b" ".join((self.key_type.encode("utf-8"), self.pub_key.get()))).hexdigest()
            if self.key_type and self.pub_key
            else None
        )

    @property
    def key_type(self) -> Optional[str]:
        return "RSA" if self._payload else None

    @staticmethod
    def decode(string: bytes) -> pubCrypto.RSAKey:
        return pubCrypto.RSAKey(key_str=string)

    def valid(self) -> bool:
        return self._payload is not None and self.pub_key is not None and self.pub_key_id is not None

    def recreate(self) -> None:
        if self._payload is None:
            raise CredentialError("RSAKey not initialized")

        new_key = self._payload
        new_key.new()
        self.load_from_string(new_key.get())
        if self.path:
            self.save_to_file(self.path)

    def extract_sym_key(self, enc_sym_key) -> symCrypto.AutoSymKey:
        if self._payload is None:
            raise CredentialError("RSAKey not initialized")

        return symCrypto.AutoSymKey(self._payload.decrypt_hex(enc_sym_key))


class TextCredential(Credential[bytes]):
    cred_type = CredentialType.TEXT
    classad_attribute = "AuthFile"

    @staticmethod
    def decode(string: bytes) -> bytes:
        return string

    def valid(self) -> bool:
        return True


class X509Pair(CredentialPair, X509Cert):
    cred_type = CredentialPairType.X509_PAIR

    def __init__(
        self,
        string: Optional[bytes] = None,
        path: Optional[str] = None,
        private_string: Optional[bytes] = None,
        private_path: Optional[str] = None,
        purpose: Optional[CredentialPurpose] = None,
        trust_domain: Optional[TrustDomain] = None,
        security_class: Optional[str] = None,
    ) -> None:
        super().__init__(string, path, private_string, private_path, purpose, trust_domain, security_class)
        self.classad_attribute = "PublicCert"
        self.private_credential.classad_attribute = "PrivateCert"


class UsernamePassword(CredentialPair, TextCredential):
    cred_type = CredentialPairType.USERNAME_PASSWORD

    def __init__(
        self,
        string: Optional[bytes] = None,
        path: Optional[str] = None,
        private_string: Optional[bytes] = None,
        private_path: Optional[str] = None,
        purpose: Optional[CredentialPurpose] = None,
        trust_domain: Optional[TrustDomain] = None,
        security_class: Optional[str] = None,
    ) -> None:
        super().__init__(string, path, private_string, private_path, purpose, trust_domain, security_class)
        self.classad_attribute = "Username"
        self.private_credential.classad_attribute = "Password"


class RequestCredential:
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
        self.req_idle = req_idle
        self.req_max_run = req_max_run


class SecurityBundle:
    def __init__(self):
        self.credentials = CredentialDict()
        self.parameters = ParameterDict()

    def add_credential(self, credential, credential_id=None):
        self.credentials[credential_id or credential.id] = credential

    def add_parameter(self, parameter: Parameter):
        self.parameters.add(parameter)

    def load_from_element(self, element_descript):
        for path in element_descript.merged_data["Proxies"]:
            cred_type = credential_type_from_string(element_descript.merged_data["ProxyTypes"].get(path))
            purpose = element_descript.merged_data["CredentialPurposes"].get(path)
            trust_domain = element_descript.merged_data["ProxyTrustDomains"].get(path, "None")
            security_class = element_descript.merged_data["ProxySecurityClasses"].get(path, id)
            if isinstance(cred_type, CredentialType):
                credential = create_credential(
                    path=path,
                    purpose=CredentialPurpose.from_string(purpose),
                    trust_domain=trust_domain,
                    security_class=security_class,
                    cred_type=cred_type,
                )
            else:
                cred_key = element_descript.merged_data["ProxyKeyFiles"].get(path, None)
                credential = create_credential_pair(
                    path=path,
                    private_path=cred_key,
                    purpose=CredentialPurpose.from_string(purpose),
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
    def __init__(self, username, security_class):
        self.username = username
        self.security_class = security_class
        self.id = None  # id used for tacking the submit credentials
        self.cred_dir = ""  # location of credentials
        self.security_credentials = CredentialDict()
        self.identity_credentials = CredentialDict()
        self.parameters = ParameterDict()

    def add_security_credential(self, cred_id, cred_name=None, credential=None, prefix="credential_"):
        """
        Adds a security credential.
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

    def add_factory_credential(self, cred_id, credential):
        """
        Adds a factory provided security credential.
        """
        self.security_credentials[cred_id] = credential
        return True

    def add_identity_credential(self, cred_id, credential):
        """
        Adds an identity credential.
        """
        self.identity_credentials[cred_id] = credential
        return True

    def add_parameter(self, param_id: ParameterName, param_value):
        """
        Adds a parameter.
        """
        self.parameters[param_id] = param_value
        return True


class AuthenticationSet:
    _required_types: Set[Union[CredentialType, ParameterName]] = set()

    def __init__(self, cred_types: Iterable[CredentialType]):
        for cred_type in cred_types:
            if not isinstance(cred_type, CredentialType):
                raise TypeError(f"Invalid credential type: {cred_type}")
        self._required_types = set(cred_types)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"

    def __str__(self) -> str:
        return ",".join(str(cred_type) for cred_type in self._required_types)

    def supports(self, cred_type: Union[CredentialType, str]) -> bool:
        if isinstance(cred_type, str):
            cred_type = CredentialType.from_string(cred_type)
        return cred_type in self._required_types

    def satisfied_by(self, cred_types: Iterable[CredentialType]) -> bool:
        return self._required_types.issubset(cred_types)


class AuthenticationMethod:
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
        for group in auth_method.split(";"):
            if group.lower() == "any":
                self._requirements.append([])
            else:
                options = []
                for option in group.split(","):
                    try:
                        options.append(CredentialType.from_string(option))
                    except CredentialError:
                        try:
                            options.append(ParameterName.from_string(option))
                        except CredentialError:
                            raise CredentialError(f"Unknown authentication requirement: {option}")
                self._requirements.append(options)

    def match(self, credentials: Iterable[Credential]) -> Optional[AuthenticationSet]:
        if not self._requirements:
            return AuthenticationSet([])

        auth_set = []
        cred_types = {credential.cred_type for credential in credentials if credential.valid()}
        for group in self._requirements:
            for option in group:
                if option in cred_types:
                    auth_set.append(option)
                    break
                return None
        return AuthenticationSet(auth_set)


def credential_type_from_string(string: str) -> Union[CredentialType, CredentialPairType]:
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
    trust_domain: Optional[TrustDomain] = None,
    security_class: Optional[str] = None,
    cred_type: Optional[CredentialType] = None,
) -> Credential:
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
    trust_domain: Optional[TrustDomain] = None,
    security_class: Optional[str] = None,
    cred_type: Optional[CredentialPairType] = None,
) -> CredentialPair:
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


def get_scitoken(elementDescript, trust_domain):
    """Look for a local SciToken specified for the trust domain.

    Args:
        elementDescript (ElementMergedDescript): element descript
        trust_domain (string): trust domain for the element

    Returns:
        string, None: SciToken or None if not found
    """

    scitoken_fullpath = ""
    cred_type_data = elementDescript.element_data.get("ProxyTypes")
    trust_domain_data = elementDescript.element_data.get("ProxyTrustDomains")
    if not cred_type_data:
        cred_type_data = elementDescript.frontend_data.get("ProxyTypes")
    if not trust_domain_data:
        trust_domain_data = elementDescript.frontend_data.get("ProxyTrustDomains")
    if trust_domain_data and cred_type_data:
        cred_type_map = eval(cred_type_data)
        trust_domain_map = eval(trust_domain_data)
        for cfname in cred_type_map:
            if cred_type_map[cfname] == "scitoken":
                if trust_domain_map[cfname] == trust_domain:
                    scitoken_fullpath = cfname

    if os.path.exists(scitoken_fullpath):
        try:
            logSupport.log.debug(f"found scitoken {scitoken_fullpath}")
            stkn = ""
            with open(scitoken_fullpath) as fbuf:
                for line in fbuf:
                    stkn += line
            stkn = stkn.strip()
            return stkn
        except Exception as err:
            logSupport.log.exception(f"failed to read scitoken: {err}")

    return None


def generate_credential(elementDescript, glidein_el, group_name, trust_domain):
    """Generates a credential with a credential generator plugin provided for the trust domain.

    Args:
        elementDescript (ElementMergedDescript): element descript
        glidein_el (dict): glidein element
        group_name (string): group name
        trust_domain (string): trust domain for the element

    Returns:
        string, None: Credential or None if not generated
    """

    ### The credential generator plugin should define the following function:
    # def get_credential(log:logger, group:str, entry:dict{name:str, gatekeeper:str}, trust_domain:str):
    # Generates a credential given the parameter

    # Args:
    # log:logger
    # group:str,
    # entry:dict{
    #     name:str,
    #     gatekeeper:str},
    # trust_domain:str,
    # Return
    # tuple
    #     token:str
    #     lifetime:int seconds of remaining lifetime
    # Exception
    # KeyError - miss some information to generate
    # ValueError - could not generate the token

    generator = None
    generators = elementDescript.element_data.get("CredentialGenerators")
    trust_domain_data = elementDescript.element_data.get("ProxyTrustDomains")
    if not generators:
        generators = elementDescript.frontend_data.get("CredentialGenerators")
    if not trust_domain_data:
        trust_domain_data = elementDescript.frontend_data.get("ProxyTrustDomains")
    if trust_domain_data and generators:
        generators_map = eval(generators)
        trust_domain_map = eval(trust_domain_data)
        for cfname in generators_map:
            if trust_domain_map[cfname] == trust_domain:
                generator = generators_map[cfname]
                logSupport.log.debug(f"found credential generator plugin {generator}")
                try:
                    if not generator in plugins:
                        plugins[generator] = import_module(generator)
                    entry = {
                        "name": glidein_el["attrs"].get("EntryName"),
                        "gatekeeper": glidein_el["attrs"].get("GLIDEIN_Gatekeeper"),
                        "factory": glidein_el["attrs"].get("AuthenticatedIdentity"),
                    }
                    stkn, _ = plugins[generator].get_credential(logSupport, group_name, entry, trust_domain)
                    return cfname, stkn
                except ModuleNotFoundError:
                    logSupport.log.warning(f"Failed to load credential generator plugin {generator}")
                except Exception as e:  # catch any exception from the plugin to prevent the frontend from crashing
                    logSupport.log.warning(f"Failed to generate credential: {e}.")

    return None, None


# Helper for update_credential_file
def compress_credential(credential_data):
    compress_credential = None
    with BytesIO() as cfile:
        with gzip.GzipFile(fileobj=cfile, mode="wb") as f:
            # Calling a GzipFile object's close() method does not close fileobj, so cfile is available outside
            f.write(credential_data)
        compress_credential = base64.b64encode(cfile.getvalue())
    return compress_credential
