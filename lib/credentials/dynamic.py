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

    There can be multiple generated credentials within the same dynamic credential.
    Each dynamic credential object has only one generated credential,
    but it can generate and store into cache and load from cache multiple credentials.
    See `CredentialGenerator` and `CachedGenerator` for cache behavior (snapshot definition and
    use via `dynamic_cache_file()`).
    E.g. When generating per Entry IDTOKENs each dynamic credential object contains only one IDTOKEN, but the
    same generator and context can be used to generate/refresh multiple IDTOKENs, each a different snapshot,
    each cached on a different file. Different snapshots have different IDs, but the same snapshot when refreshed
    maintains the same ID.
    - different IDTOKENs are created using different attributes (e.g. Entry name) in `generate()`.
      A snapshot is defined and used
    - different IDTOKENs are accessed via snapshot (same attributes)

    Dynamic credentials have no `secret` because this is used by load (from file or string) and dynamic credentials
    use generators.  If needed a secret can be added in the context.
    TODO: evaluate if a secret should be always added and maybe encoded credentials become a special case of dynamic credentials

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
        # TODO: Evaluate if access to generated credentials trust_domain is needed
        #  Using @property and @trust_domain.setter
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
        """Return the generated credential attribute when not available in the generator (DynamicCredential)

        Args:
            attr (str): The name of the generated credential attribute.

        Returns:
            Any: Attribute's value

        Raises:
            AttributeError: if the credential has not been generated or the attribute is not available
        """
        if self._generated_credential is None:
            raise AttributeError(
                f"'{self.__class__.__name__}' credential not generated. No attribute '{attr}'"
            ) from None
        try:
            return getattr(self._generated_credential, attr)
        except Exception:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'") from None

    def __repr__(self) -> str:
        """Protecting representation for DynamicCredential, it may not have some attributes if not initialized"""
        if self._generated_credential is None:
            return f"{self.__class__.__name__}(<credential not generated>, string={self.string!r}, path={self.path!r}, secret=<not available>, purpose={self.purpose!r}, trust_domain={self.trust_domain!r}, security_class={self.security_class!r})"
        return f"{self.__class__.__name__}(generated={self._generated_credential.__class__.__name__},string={self.string!r}, path={self.path!r}, secret={self.secret!r}, purpose={self.purpose!r}, trust_domain={self.trust_domain!r}, security_class={self.security_class!r})"

    def debug_str(self) -> str:
        """Return a string representation of the dynamic credential for debugging.

        This method is safe from exception, so it may be used in error messages without the risk to mask exceptions.
        This method is also safe for logging, no secure content (string or secret) is printed.
        For dynamic credentials it adds the generated credential class, if already generated.

        Returns:
            str: The string representation of the credential, including ID and validity but excluding
                string and secret (safe for logging).
        """
        if self._generated_credential is None:
            generated = "<not generated>"
        else:
            generated = self._generated_credential.__class__.__name__
        return "{parent},generated={gen}".format(
            parent=super().debug_str(),
            gen=generated,
        )

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

    # TODO: Could there be confusion between secret and context?
    @staticmethod
    def decode(string: Union[str, bytes], context: Optional[Mapping] = None) -> Generator:
        """Load the credential generator module and return it.

        This implementation has the same number of parameters but different signature of the parent class.
        Dynamic credentials use context for the generation and do not use secret to decoding serialized credentials.
        If a secret is needed it should be added to the context and become one of the constructor arguments.

        Args:
            string: Generator module name or path. Can be in bytes.
            context: Context for the generator.

        Returns:
            Generator: contextualized generator object. This is a generator instance based on the context.
        """
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
        # TODO: check that fall-back to load_from_string is OK and no file loading is used for dynamic and no self.path is used
        self.load_from_string(path, context)

    def copy(self) -> Credential:
        if not self._generated_credential:
            raise CredentialError("Cannot copy. Credential not generated.")
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
        add_newline: bool = False,
    ) -> None:
        """Save to a file the generated credential, by invoking its method.

        Args:
            path (Optional[str]): The path to the file where the credential will be saved.
            permissions (int): The permissions to set for the saved file. Default is 0o600.
            backup (bool): Whether to create a backup of the existing file. Default is False.
            compress (bool): Whether to compress the credential before saving. Default is False.
            data_pattern (Optional[bytes]): A pattern to format the credential data before saving. Default is None.
            overwrite (bool): Whether to overwrite the existing file if it already exists. Default is True.
            continue_if_no_path (bool): If True, silently return without saving a file if no path is specified. Default is False.
            add_newline (bool): Whether to add a newline at the end of the saved file. Default is False.

        Raises:
            CredentialError: If the credential is not generated/initialized or if there is an error saving the credential.
        """
        if not self._generated_credential:
            raise CredentialError("Could not save. Credential not generated.")
        self._generated_credential.save_to_file(
            path=path,
            permissions=permissions,
            backup=backup,
            compress=compress,
            data_pattern=data_pattern,
            overwrite=overwrite,
            continue_if_no_path=continue_if_no_path,
            add_newline=add_newline,
        )

    def invalid_reason(self) -> Optional[str]:
        """Checks if the credential is valid and returns a string if it is not.

        Note: This function checks only the validity of the credential but does not perform verification of the credential.

        Returns:
            str or None: A string value indicating the reason for invalidity or a `None` value (if the Dynamic credential is valid).
        """
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
            default (Optional[any]): A default value to return if the snapshot does not exist.

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
