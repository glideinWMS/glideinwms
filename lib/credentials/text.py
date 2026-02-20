#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module provides classes to represent and manage text credentials.
"""

from typing import Optional, Union

from glideinwms.lib.credentials import Credential, CredentialPair, CredentialPairType, CredentialPurpose, CredentialType
from glideinwms.lib.defaults import force_bytes


class TextCredential(Credential[bytes]):
    """Represents a text-based credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        extension (str): The file extension for the credential.
    """

    cred_type = CredentialType.TEXT
    extension = "txt"

    @property
    def _id_attribute(self) -> Optional[str]:
        return self.string

    @staticmethod
    def decode(string: Union[str, bytes]) -> bytes:
        return force_bytes(string)

    def invalid_reason(self) -> Optional[str]:
        """Checks if the credential is valid and returns a string if it is not.

        Following are the reasons for an invalid text-based credential:
        - the text-based credential is not initialized

        Note: This function checks only the validity of the credential but does not perform verification of the credential.

        Returns:
            str or None: A string value indicating the reason for invalidity or a `None` value (if text-based credential is valid).
        """
        if self._payload is None:
            return "Text credential not initialized."
        return None  # no reason for invalidity found, so credential is valid


class UsernamePassword(CredentialPair, TextCredential):
    """Represents a username and password credential pair.

    This class extends both the `CredentialPair` and `TextCredential` classes.

    Attributes:
        cred_type (CredentialPairType): The type of the credential pair.
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
        """Initialize a UsernamePassword object.

        Args:
            string (Optional[bytes]): The username as a byte string.
            path (Optional[str]): The path to the username file.
            private_string (Optional[bytes]): The password as a byte string.
            private_path (Optional[str]): The path to the password file.
            purpose (Optional[CredentialPurpose]): The purpose of the credentials.
            trust_domain (Optional[str]): The trust domain of the credentials.
            security_class (Optional[str]): The security class of the credentials.
        """

        super().__init__(string, path, private_string, private_path, purpose, trust_domain, security_class)
