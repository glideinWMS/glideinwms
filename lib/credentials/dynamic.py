#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module provides classes to generate credentials using the Generator module.
"""

from typing import Any, Generator, Mapping, Optional, Union

from glideinwms.lib.credentials import create_credential, Credential, CredentialError, CredentialPurpose, CredentialType
from glideinwms.lib.defaults import force_bytes
from glideinwms.lib.generators import load_generator


class DynamicCredential(Credential[Generator]):
    """Represents a dynamic credential used for generating credentials at runtime.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        path (str): The path of the credential file.
    """

    cred_type = CredentialType.DYNAMIC

    # noinspection PyMissingConstructor
    def __init__(  # pylint: disable=super-init-not-called
        self,
        string: Optional[Union[str, bytes]] = None,
        path: Optional[str] = None,
        purpose: Optional[CredentialPurpose] = None,
        trust_domain: Optional[str] = None,
        security_class: Optional[str] = None,
        creation_script: Optional[str] = None,
        minimum_lifetime: Union[int, str] = 0,
        context: Optional[Mapping] = None,
    ) -> None:
        """Initialize a Credentials object.

        Args:
            string (Optional[Union[str, bytes]]): The credential string.
            path (Optional[str]): The path to the credential file.
            purpose (Optional[CredentialPurpose]): The purpose of the credential.
            trust_domain (Optional[str]): The trust domain of the credential.
            security_class (Optional[str]): The security class of the credential.
            creation_script (Optional[str]): The script used to create the credential.
            minimum_lifetime (Union[int, str]): The minimum lifetime of the credential in seconds.
            context (Optional[Mapping]): The context of the generator.
        """

        self._string = None
        self._context = context
        self._generated_credential: Optional[Credential] = None
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
            self.load(string, path, context)

    def __getattr__(self, attr: str) -> Any:
        try:
            return getattr(self._generated_credential, attr)
        except Exception:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'") from None

    @property
    def _id_attribute(self) -> Optional[str]:
        return f"{self.string}{self.context}"

    @property
    def _payload(self) -> Optional[Generator]:
        return self.decode(self.string, self.context) if self.string and self.context else None

    @property
    def context(self) -> Optional[Mapping]:
        """The context of the generator."""

        return self._context

    @staticmethod
    def decode(string: Union[str, bytes], context: Optional[Mapping] = None) -> Generator:
        if isinstance(string, bytes):
            string = string.decode()
        return load_generator(string, context)

    def load(
        self, string: Optional[Union[str, bytes]] = None, path: Optional[str] = None, context: Optional[Mapping] = None
    ) -> None:
        if string:
            self.load_from_string(string, context)
            if path:
                self.path = path
        elif path:
            self.load_from_file(path, context)
        else:
            raise CredentialError("No string or path specified")

    def load_from_string(self, string: Union[str, bytes], context: Optional[Mapping] = None) -> None:
        string = force_bytes(string)
        if not isinstance(string, bytes):
            raise CredentialError("Credential string must be bytes")
        try:
            self.decode(string, context)
        except Exception as err:
            raise CredentialError(f"Could not load credential from string: {string}") from err
        self._string = string
        self._context = context
        if context and "type" in context:
            self.cred_type = CredentialType.from_string(context.get("type"))

    def load_from_file(self, path: str, context: Optional[Mapping] = None) -> None:
        self.load_from_string(path, context)

    def copy(self) -> Credential:
        if not self._generated_credential:
            raise CredentialError("Credential not generated.")
        return self._generated_credential.copy()

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
        if not self._generated_credential:
            raise CredentialError("Could not Credential not generated.")
        self._generated_credential.save_to_file(
            path=path,
            permissions=permissions,
            backup=backup,
            compress=compress,
            data_pattern=data_pattern,
            overwrite=overwrite,
            continue_if_no_path=continue_if_no_path,
        )

    def invalid_reason(self) -> Optional[str]:
        if self._generated_credential:
            return self._generated_credential.invalid_reason()
        if isinstance(self._payload, Generator):
            return None
        return "Credential not initialized."

    def generate(self, snapshot: Optional[str] = None, **kwargs):
        """Generate a credential using the generator.

        Args:
            snapshot (str): If provided, creates a snapshot of the generated credential.
            **kwargs: Additional keyword arguments to pass to the generator.

        Raises:
            CredentialError: If the generator is not initialized.
        """

        if not self._payload:
            raise CredentialError("Credential generator not initialized")

        generated_value = self._payload.generate(snapshot, **kwargs)
        if isinstance(generated_value, Credential):
            generated_value.purpose = self.purpose
            generated_value.trust_domain = self.trust_domain
            generated_value.security_class = self.security_class
            self._generated_credential = generated_value
            self.cred_type = generated_value.cred_type
        elif isinstance(generated_value, (str, bytes)):
            self._generated_credential = create_credential(
                string=generated_value,
                purpose=self.purpose,
                trust_domain=self.trust_domain,
                security_class=self.security_class,
                cred_type=self.cred_type,
            )
            self.cred_type = self._generated_credential.cred_type
        else:
            raise CredentialError(
                f"Invalid generated value: {generated_value}. Expected a Credential, or a string or bytes."
            )

    def get_snapshot(self, snapshot: str, default: Optional[any] = None) -> Optional[Credential]:
        """Retrieve a snapshot of the generated credential.

        Args:
            snapshot (str): The name of the snapshot to retrieve.

        Returns:
            Optional[Credential]: The snapshot of the generated credential, or None if not found.
        """

        snapshot_value = self._payload.get_snapshot(snapshot, default) if self._payload else None
        if not snapshot_value:
            return None
        elif isinstance(snapshot_value, Credential):
            return snapshot_value
        else:
            return create_credential(
                string=snapshot_value,
                purpose=self.purpose,
                trust_domain=self.trust_domain,
                security_class=self.security_class,
                cred_type=self.cred_type,
            )
