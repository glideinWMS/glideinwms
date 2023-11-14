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
import tempfile
import jwt
import M2Crypto
import os
import re
import shutil
import sys

from abc import ABC, abstractmethod
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from datetime import datetime
from importlib import import_module
from io import BytesIO
from hashlib import md5
from typing import Any, Generic, TypeVar, Optional, Union, Mapping, Iterable, List, Set, Type

from glideinwms.factory import glideFactoryInterface, glideFactoryLib
from glideinwms.lib import condorMonitor, logSupport, pubCrypto, symCrypto
from glideinwms.lib.generators import Generator, load_generator
from glideinwms.lib.util import hash_nc

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

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_string(cls, string: str) -> "CredentialType":
        extended_map = {"scitoken": cls.TOKEN, "grid_proxy": cls.X509_CERT}

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


class CredentialPurpose(enum.Enum):
    # TODO: Better define these
    PILOT = "pilot"
    FACTORY = "factory"
    FRONTEND = "frontend"


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


class TrustDomain(enum.Enum):
    GRID = "grid"


class Credential(ABC, Generic[T]):
    cred_type: Optional[CredentialType] = None
    classad_attribute: Optional[str] = None

    def __init__(self, string: Optional[bytes] = None, path: Optional[str] = None) -> None:
        self._string = None
        self.path = path
        if string or path:
            self.load(string, path)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(string={self.string!r}, path={self.path!r}"

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
    ) -> None:
        if len(self.__class__.__bases__) < 2 or not issubclass(self.__class__.__bases__[1], Credential):
            raise CredentialError("CredentialPair requires a Credential subclass as second base class")

        credential_class = self.__class__.__bases__[1]
        super(credential_class, self).__init__(string, path)  # type: ignore
        self.private_credential = credential_class(private_string, private_path)

    def renew(self) -> None:
        try:
            self.__renew__()  # type: ignore
            self.private_credential.__renew__()
        except NotImplementedError:
            pass


# Dictionary of Credentials
class CredentialDict(dict):
    def __setitem__(self, __k, __v):
        if not isinstance(__v, Credential):
            raise TypeError("Value must be a credential")
        super().__setitem__(__k, __v)


class Parameter:
    def __init__(self, name: ParameterName, value):
        if not isinstance(name, ParameterName):
            raise TypeError("Name must be a ParameterName")
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name.value!r}, value={self.value!r})"

    def __str__(self) -> str:
        return f"{self.name.value}={self.value}"


class ParameterDict(dict):
    def __setitem__(self, __k, __v):
        if not isinstance(__k, ParameterName):
            raise TypeError("Key must be a ParameterType")
        super().__setitem__(__k, __v)

    def add(self, parameter: Parameter):
        if not isinstance(parameter, Parameter):
            raise TypeError("Parameter must be a Parameter")
        self[parameter.name] = parameter.value


class CredentialGenerator(Credential[Credential]):
    cred_type = CredentialType.GENERATOR

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
            self.cred_type = self._payload.cred_type if self._payload else None
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
        return jwt.decode(string.strip(), verify=False)

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
        # return self._payload.get_not_before() if self._payload else None
        return x509.load_pem_x509_certificate(self.string, default_backend()).not_valid_before

    @property
    def not_after_time(self) -> Optional[datetime]:
        # return self._payload.get_not_after() if self._payload else None
        return x509.load_pem_x509_certificate(self.string, default_backend()).not_valid_after

    @staticmethod
    def decode(string: bytes) -> M2Crypto.X509.X509:
        return M2Crypto.X509.load_cert_string(string)

    def valid(self) -> bool:
        if self.not_before_time and self.not_after_time:
            return self.not_before_time < datetime.now() < self.not_after_time
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


# class TextCredential(Credential[bytes]):
#     cred_type = CredentialType.TOKEN
#     classad_attribute = "AuthFile"

#     @staticmethod
#     def decode(string: bytes) -> bytes:
#         return string

#     def valid(self) -> bool:
#         return True


class X509Pair(CredentialPair, X509Cert):
    cred_type = CredentialPairType.X509_PAIR

    def __init__(
        self,
        string: Optional[bytes] = None,
        path: Optional[str] = None,
        private_string: Optional[bytes] = None,
        private_path: Optional[str] = None,
    ) -> None:
        super().__init__(string, path, private_string, private_path)
        self.classad_attribute = "PublicCert"
        self.private_credential.classad_attribute = "PrivateCert"


# class UsernamePassword(CredentialPair, TextCredential):
#     cred_type = CredentialPairType.USERNAME_PASSWORD

#     def __init__(
#         self,
#         string: Optional[bytes] = None,
#         path: Optional[str] = None,
#         private_string: Optional[bytes] = None,
#         private_path: Optional[str] = None,
#     ) -> None:
#         super().__init__(string, path, private_string, private_path)
#         self.classad_attribute = "Username"
#         self.private_credential.classad_attribute = "Password"


class RequestCredential:
    def __init__(
        self,
        credential: Union[Credential, Generator],
        purpose: Optional[CredentialPurpose] = None,
        trust_domain: Optional[TrustDomain] = None,
        security_class: Optional[str] = None,
    ):
        self.credential = credential
        self.purpose = purpose
        self.trust_domain = trust_domain
        self.security_class = security_class
        self.advertize: bool = False
        self.req_idle: int = 0
        self.req_max_run: int = 0

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(credential={self.credential!r}, purpose={self.purpose!r}, trust_domain={self.trust_domain!r}, security_class={self.security_class!r})"

    def __str__(self) -> str:
        return f"{self.credential!s}"

    @property
    def id(self) -> str:
        if not str(self.credential):
            raise CredentialError("Credential not initialized")

        return hash_nc(f"{str(self.credential)}{self.purpose}{self.trust_domain}{self.security_class}", 8)

    @property
    def private_id(self) -> str:
        if not isinstance(self.credential, CredentialPair):
            raise CredentialError("Credential must be a CredentialPair")
        if not self.credential.private_credential.string:
            raise CredentialError("Private credential not initialized")
        return hash_nc(
            f"{self.credential.private_credential.string.decode()}{self.purpose}{self.trust_domain}{self.security_class}"
        )

    def add_usage_details(self, req_idle=0, req_max_run=0):
        self.req_idle = req_idle
        self.req_max_run = req_max_run


class RequestCredentialDict(dict):
    def __setitem__(self, __k, __v):
        if not isinstance(__v, RequestCredential):
            raise TypeError("Value must be a RequestBundleCredential")
        super().__setitem__(__k, __v)


class RequestBundle:
    def __init__(self):
        self.credentials = RequestCredentialDict()
        self.parameters = ParameterDict()

    def add_credential(self, credential, id=None, purpose=None, trust_domain=None, security_class=None):
        rbCredential = RequestCredential(credential, purpose, trust_domain, security_class)
        self.credentials[id or rbCredential.id] = rbCredential

    def add_parameter(self, name: str, value: str):
        self.parameters.add(Parameter(ParameterName.from_string(name), value))

    def load_from_element(self, element_descript):
        for path in element_descript.merged_data["Proxies"]:
            cred_type = element_descript.merged_data["ProxyTypes"].get(path, None)
            credential = create_credential(path=path, cred_type=CredentialType.from_string(cred_type))
            trust_domain = element_descript.merged_data["ProxyTrustDomains"].get(path, "None")
            security_class = element_descript.merged_data["ProxySecurityClasses"].get(path, id)
            self.add_credential(credential, trust_domain=trust_domain, security_class=security_class)
        for name, parameter in element_descript.merged_data["Parameters"].items():
            self.add_parameter(name, parameter["value"])


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
            if not glideFactoryLib.is_str_safe(cred_name):
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

    def load(self, auth_method: str):
        for group in auth_method.split(";"):
            if group.lower() == "any":
                self._requirements.append([])  # type: ignore
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

    class_dict = {}
    for i in Credential.__subclasses__():
        class_dict[i.cred_type] = i
    try:
        return class_dict[cred_type]
    except KeyError as err:
        raise CredentialError(f"Unknown Credential type: {cred_type}") from err


def create_credential(
    string: Optional[bytes] = None, path: Optional[str] = None, cred_type: Optional[CredentialType] = None
) -> Credential:
    credential_types = [cred_type] if cred_type else CredentialType
    for cred_type in credential_types:
        try:
            credential_class = credential_of_type(cred_type)
            if issubclass(credential_class, Credential):
                return credential_class(string, path)
        except CredentialError as err:
            pass  # Credential type incompatible with input
        except Exception as err:
            raise CredentialError(f'Unexpected error loading credential: string="{string}", path="{path}"') from err
    raise CredentialError(f'Could not load credential: string="{string}", path="{path}"')


def create_credential_pair(
    string: Optional[bytes] = None,
    path: Optional[str] = None,
    private_string: Optional[bytes] = None,
    private_path: Optional[str] = None,
    cred_type: Optional[CredentialPairType] = None,
) -> CredentialPair:
    credential_types = [cred_type] if cred_type else CredentialPairType
    for cred_type in credential_types:
        try:
            credential_class = credential_of_type(cred_type)
            if issubclass(credential_class, CredentialPair):
                return credential_class(string, path, private_string, private_path)
        except CredentialError as err:
            pass
        except Exception as err:
            raise CredentialError(
                f'Unexpected error loading credential pair: string="{string}", path="{path}", private_string="{private_string}", private_path="{private_path}"'
            ) from err
    raise CredentialError(
        f'Could not load credential pair: string="{string}", path="{path}", private_string="{private_string}", private_path="{private_path}"'
    )


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


def get_globals_classads(factory_collector=glideFactoryInterface.DEFAULT_VAL):
    if factory_collector == glideFactoryInterface.DEFAULT_VAL:
        factory_collector = glideFactoryInterface.factoryConfig.factory_collector

    status_constraint = '(GlideinMyType=?="glideclientglobal")'

    status = condorMonitor.CondorStatus("any", pool_name=factory_collector)
    status.require_integrity(True)  # important, this dictates what gets submitted

    status.load(status_constraint)

    data = status.fetchStored()
    return data


# Helper for update_credential_file
def compress_credential(credential_data):
    compress_credential = None
    with BytesIO() as cfile:
        with gzip.GzipFile(fileobj=cfile, mode="wb") as f:
            # Calling a GzipFile object's close() method does not close fileobj, so cfile is available outside
            f.write(credential_data)
        compress_credential = base64.b64encode(cfile.getvalue())
    return compress_credential


# TODO: This function may be deprecated in favor of Credential.save_to_file
# Helper for update_credential_file
def safe_update(fname, credential_data):
    if not os.path.isfile(fname):
        # new file, create
        # with os.open(fname, os.O_CREAT | os.O_WRONLY, 0o600) as file:
        with open(fname, "wb") as file:
            file.write(credential_data)

    else:
        # old file exists, check if same content
        with open(fname) as fl:
            old_data = fl.read()

        #  if proxy_data == old_data nothing changed, done else
        if not (credential_data == old_data):
            # proxy changed, neeed to update

            # create new file
            try:
                with open(fname + ".new", "wb") as file:
                    file.write(credential_data)
                    os.chmod(file.name, 0o600)
            except (TypeError, OSError) as err:
                logSupport.log.exception(f"Failed to write credential file: {err}")
                return

            # remove any previous backup file, if it exists
            try:
                os.remove(fname + ".old")
            except OSError:
                pass  # just protect

            # copy the old file to a tmp bck and rename new one to the official name
            try:
                shutil.copy2(fname, fname + ".old")
            except (OSError, shutil.Error):
                # file not found, permission error, same file
                pass  # just protect

            os.rename(fname + ".new", fname)


# Helper for process_global
def update_credential_file(username: str, client_id: str, credential_data: Credential, request_clientname: str):
    """
    Updates the credential file

    :param username: credentials' username
    :param client_id: id used for tracking the submit credentials
    :param credential_data: the credentials to be advertised
    :param request_clientname: client name passed by frontend
    :return:the credential file updated
    """

    proxy_dir = glideFactoryLib.factoryConfig.get_client_proxies_dir(username)
    fname_short = f"credential_{request_clientname}_{glideFactoryLib.escapeParam(client_id)}"
    fname = os.path.join(proxy_dir, fname_short)
    fname_compressed = "%s_compressed" % fname

    msg = "updating credential file %s" % fname
    logSupport.log.debug(msg)

    credential_data.save_to_file(fname)
    credential_data.save_to_file(fname_compressed, compress=True, data_pattern=b"glidein_credentials=%b")
    # Compressed+encoded credentials are used for GCE and AWS and have a key=value format (glidein_credentials= ...)

    return fname, fname_compressed


def get_key_obj(pub_key_obj, classad):
    """
    Gets the symmetric key object from the request classad

    @type pub_key_obj: object
    @param pub_key_obj: The factory public key object.  This contains all the encryption and decryption methods
    @type classad: dictionary
    @param classad: a dictionary representation of the classad
    """
    if "ReqEncKeyCode" in classad:
        try:
            sym_key_obj = pub_key_obj.extract_sym_key(classad["ReqEncKeyCode"])
            return sym_key_obj
        except Exception as err:
            logSupport.log.debug(f"\nclassad {classad}\npub_key_obj {pub_key_obj}\n")
            error_str = "Symmetric key extraction failed."
            logSupport.log.exception(error_str)
            raise CredentialError(error_str)
    else:
        error_str = "Classad does not contain a key. We cannot decrypt."
        raise CredentialError(f"{error_str}")


# Helper for process_global
def validate_frontend(classad, frontend_descript, pub_key_obj):
    """
    Validates that the frontend advertising the classad is allowed and that it
    claims to have the same identity that Condor thinks it has.

    @type classad: dictionary
    @param classad: a dictionary representation of the classad
    @type frontend_descript: class object
    @param frontend_descript: class object containing all the frontend information
    @type pub_key_obj: object
    @param pub_key_obj: The factory public key object.  This contains all the encryption and decryption methods

    @return: sym_key_obj - the object containing the symmetric key used for decryption
    @return: frontend_sec_name - the frontend security name, used for determining
    the username to use.
    """

    # we can get classads from multiple frontends, each with their own
    # sym keys.  So get the sym_key_obj for each classad
    sym_key_obj = get_key_obj(pub_key_obj, classad)
    authenticated_identity = classad["AuthenticatedIdentity"]

    # verify that the identity that the client claims to be is the identity that Condor thinks it is
    try:
        enc_identity = sym_key_obj.decrypt_hex(classad["ReqEncIdentity"]).decode("utf-8")
    except:
        error_str = "Cannot decrypt ReqEncIdentity."
        logSupport.log.exception(error_str)
        raise CredentialError(error_str)

    if enc_identity != authenticated_identity:
        error_str = "Client provided invalid ReqEncIdentity(%s!=%s). " "Skipping for security reasons." % (
            enc_identity,
            authenticated_identity,
        )
        raise CredentialError(error_str)
    try:
        frontend_sec_name = sym_key_obj.decrypt_hex(classad["GlideinEncParamSecurityName"]).decode("utf-8")
    except:
        error_str = "Cannot decrypt GlideinEncParamSecurityName."
        logSupport.log.exception(error_str)
        raise CredentialError(error_str)

    # verify that the frontend is authorized to talk to the factory
    expected_identity = frontend_descript.get_identity(frontend_sec_name)
    if expected_identity is None:
        error_str = "This frontend is not authorized by the factory.  Supplied security name: %s" % frontend_sec_name
        raise CredentialError(error_str)
    if authenticated_identity != expected_identity:
        error_str = "This frontend Authenticated Identity, does not match the expected identity"
        raise CredentialError(error_str)

    return sym_key_obj, frontend_sec_name


def process_global(classad, glidein_descript, frontend_descript):
    # Factory public key must exist for decryption
    pub_key_obj = glidein_descript.data["PubKeyObj"]
    if pub_key_obj is None:
        raise CredentialError("Factory has no public key.  We cannot decrypt.")

    try:
        # Get the frontend security name so that we can look up the username
        sym_key_obj, frontend_sec_name = validate_frontend(classad, frontend_descript, pub_key_obj)

        request_clientname = classad["ClientName"]

        # get all the credential ids by filtering keys by regex
        # this makes looking up specific values in the dict easier
        r = re.compile("^GlideinEncParamSecurityClass")
        mkeys = list(filter(r.match, list(classad.keys())))
        for key in mkeys:
            prefix_len = len("GlideinEncParamSecurityClass")
            cred_id = key[prefix_len:]

            cred_data = sym_key_obj.decrypt_hex(classad["GlideinEncParam%s" % cred_id])
            cred = create_credential(string=cred_data)
            security_class = sym_key_obj.decrypt_hex(classad[key]).decode("utf-8")
            username = frontend_descript.get_username(frontend_sec_name, security_class)
            if username == None:
                logSupport.log.error(
                    (
                        "Cannot find a mapping for credential %s of client %s. Skipping it. The security"
                        "class field is set to %s in the frontend. Please, verify the glideinWMS.xml and"
                        " make sure it is mapped correctly"
                    )
                    % (cred_id, classad["ClientName"], security_class)
                )
                continue

            msg = "updating credential for %s" % username
            logSupport.log.debug(msg)

            update_credential_file(username, cred_id, cred, request_clientname)
    except Exception as e:
        logSupport.log.debug(f"\nclassad {classad}\nfrontend_descript {frontend_descript}\npub_key_obj {pub_key_obj})")
        error_str = "Error occurred processing the globals classads."
        logSupport.log.exception(error_str)
        raise CredentialError(error_str)


# Not sure if this has to be abstract - probably better?
def check_security_credentials(auth_method, params, client_int_name, entry_name, scitoken_passthru=False):
    """
    Verify that only credentials for the given auth method are in the params

    Args:
        auth_method: (string): authentication method of an entry, defined in the config
        params: (dictionary): decrypted params passed in a frontend (client) request
        client_int_name (string): internal client name
        entry_name: (string): name of the entry
        scitoken_passthru: (bool): if True, scitoken present in credential. Override checks
                                for 'auth_method' and proceded with glidein request
    Raises:
    CredentialError: if the credentials in params don't match what is defined for the auth method
    """

    auth_method_list = auth_method.split("+")
    if not set(auth_method_list) & set(SUPPORTED_AUTH_METHODS):
        logSupport.log.warning(
            "None of the supported auth methods %s in provided auth methods: %s"
            % (SUPPORTED_AUTH_METHODS, auth_method_list)
        )
        return

    params_keys = set(params.keys())
    relevant_keys = {
        "SubmitProxy",
        "GlideinProxy",
        "Username",
        "Password",
        "PublicCert",
        "PrivateCert",
        "PublicKey",
        "PrivateKey",
        "VMId",
        "VMType",
        "AuthFile",
    }

    if "scitoken" in auth_method_list or "frontend_scitoken" in params and scitoken_passthru:
        # TODO  check validity
        # TODO  Specifically, Add checks that no undesired credentials are
        #       sent also when token is used
        return
    if "grid_proxy" in auth_method_list:
        if not scitoken_passthru:
            if "SubmitProxy" in params:
                # v3+ protocol
                valid_keys = {"SubmitProxy"}
                invalid_keys = relevant_keys.difference(valid_keys)
                if params_keys.intersection(invalid_keys):
                    raise CredentialError(
                        "Request from %s has credentials not required by the entry %s, skipping request"
                        % (client_int_name, entry_name)
                    )
            else:
                # No proxy sent
                raise CredentialError(
                    "Request from client %s did not provide a proxy as required by the entry %s, skipping request"
                    % (client_int_name, entry_name)
                )

    else:
        # Only v3+ protocol supports non grid entries
        # Verify that the glidein proxy was provided for non-proxy auth methods
        if "GlideinProxy" not in params and not scitoken_passthru:
            raise CredentialError("Glidein proxy cannot be found for client %s, skipping request" % client_int_name)

        if "x509_cert" in auth_method_list:
            # Validate both the public and private certs were passed
            if not (("PublicCert" in params) and ("PrivateCert" in params)):
                # if not ('PublicCert' in params and 'PrivateCert' in params):
                # cert pair is required, cannot service request
                raise CredentialError(
                    "Client '%s' did not specify the certificate pair in the request, this is required by entry %s, skipping "
                    % (client_int_name, entry_name)
                )
            # Verify no other credentials were passed
            valid_keys = {"GlideinProxy", "PublicCert", "PrivateCert", "VMId", "VMType"}
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError(
                    "Request from %s has credentials not required by the entry %s, skipping request"
                    % (client_int_name, entry_name)
                )

        elif "rsa_key" in auth_method_list:
            # Validate both the public and private keys were passed
            if not (("PublicKey" in params) and ("PrivateKey" in params)):
                # key pair is required, cannot service request
                raise CredentialError(
                    "Client '%s' did not specify the key pair in the request, this is required by entry %s, skipping "
                    % (client_int_name, entry_name)
                )
            # Verify no other credentials were passed
            valid_keys = {"GlideinProxy", "PublicKey", "PrivateKey", "VMId", "VMType"}
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError(
                    "Request from %s has credentials not required by the entry %s, skipping request"
                    % (client_int_name, entry_name)
                )

        elif "auth_file" in auth_method_list:
            # Validate auth_file is passed
            if not ("AuthFile" in params):
                # auth_file is required, cannot service request
                raise CredentialError(
                    "Client '%s' did not specify the auth_file in the request, this is required by entry %s, skipping "
                    % (client_int_name, entry_name)
                )
            # Verify no other credentials were passed
            valid_keys = {"GlideinProxy", "AuthFile", "VMId", "VMType"}
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError(
                    "Request from %s has credentials not required by the entry %s, skipping request"
                    % (client_int_name, entry_name)
                )

        elif "username_password" in auth_method_list:
            # Validate username and password keys were passed
            if not (("Username" in params) and ("Password" in params)):
                # username and password is required, cannot service request
                raise CredentialError(
                    "Client '%s' did not specify the username and password in the request, this is required by entry %s, skipping "
                    % (client_int_name, entry_name)
                )
            # Verify no other credentials were passed
            valid_keys = {"GlideinProxy", "Username", "Password", "VMId", "VMType"}
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError(
                    "Request from %s has credentials not required by the entry %s, skipping request"
                    % (client_int_name, entry_name)
                )

        else:
            # should never get here, unsupported main authentication method is checked at the beginning
            raise CredentialError("Inconsistency between SUPPORTED_AUTH_METHODS and check_security_credentials")

    # No invalid credentials found
    return
