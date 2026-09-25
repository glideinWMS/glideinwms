#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module provides classes to represent and manage tokens.
"""

import json

from datetime import datetime
from typing import Mapping, Optional, Union

import jwt

from glideinwms.lib.credentials import Credential, CredentialType


class Token(Credential[Mapping]):
    """Represents a token credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        extension (str): The file extension for the token.
        scope (Optional[str]): The scope of the token.
        issue_time (Optional[datetime]): The issue time of the token.
        not_before_time (Optional[datetime]): The not-before time of the token.
        expiration_time (Optional[datetime]): The expiration time of the token.
    """

    cred_type = CredentialType.TOKEN
    extension = "jwt"

    @property
    def subject(self) -> Optional[str]:
        """Token subject."""
        return self._payload.get("sub", None) if self._payload else None

    @property
    def scope(self) -> Optional[str]:
        """Token scope."""
        return self._payload.get("scope", None) if self._payload else None

    @property
    def issue_time(self) -> Optional[datetime]:
        """Token issue time."""
        return datetime.fromtimestamp(self._payload.get("iat", None)) if self._payload else None

    @property
    def not_before_time(self) -> Optional[datetime]:
        """Token not-before time."""
        return datetime.fromtimestamp(self._payload.get("nbf", None)) if self._payload else None

    @property
    def expiration_time(self) -> Optional[datetime]:
        """Token expiration time."""
        return datetime.fromtimestamp(self._payload.get("exp", None)) if self._payload else None

    @property
    def _id_attribute(self) -> Optional[str]:
        return self.subject

    @staticmethod
    def decode(string: Union[str, bytes], secret: Optional[Union[str, bytes]] = None) -> Mapping:
        """Decode a JWT token.

        Args:
            string (Union[str, bytes]): The string to decode.
            secret (Optional[Union[str, bytes]]): Since tokens are in clear, there should be no secrets.
                Always None, ignored. Added to respect the interface.

        Returns:
            Mapping: The decoded token as a dictionary.
        """
        if isinstance(string, bytes):
            string = string.decode()
        return jwt.decode(string.strip(), options={"verify_signature": False})

    def invalid_reason(self) -> Optional[str]:
        """Checks if the credential is valid and returns a string if it is not.

        Following are the reasons for an invalid token:
        1. Token was not initialized
        2. Token is not yet valid
        3. Expired token
        4. Lifetime of the token is too short.

        Note: This function checks only the validity of the credential but does not perform verification of the credential.

        Returns:
            str or None: A string value indicating the reason for invalidity or a `None` value (if token is valid).
        """
        if not self._payload:
            return "Token not initialized."
        if datetime.now() < self.not_before_time:
            return "Token not yet valid."
        if datetime.now() > self.expiration_time:
            return "Token expired."
        if (self.expiration_time - datetime.now()).total_seconds() < self.minimum_lifetime:
            return "Token lifetime too short."
        return None  # no reason for invalidity found, so credential is valid


class SciToken(Token):
    """Represents a SciToken credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        extension (str): The file extension for the token.
        scope (Optional[str]): The scope of the token.
        issue_time (Optional[datetime]): The issue time of the token.
        not_before_time (Optional[datetime]): The not-before time of the token.
        expiration_time (Optional[datetime]): The expiration time of the token.

    NOTE: This class is a subclass of the `Token` class.
    """

    cred_type = CredentialType.SCITOKEN
    extension = "scitoken"


class GlobusComputeToken(Token):
    """Represents a Globus Compute access-token credential.

    Globus Auth access tokens are opaque, not JWTs, so the expiration is carried
    explicitly in the stored JSON (access_token plus expires_at_seconds) rather
    than decoded from a payload.
    """

    cred_type = CredentialType.GLOBUS_COMPUTE_TOKEN
    extension = "globuscompute"

    @property
    def access_token(self) -> Optional[str]:
        """Globus Auth access token."""
        return self._payload.get("access_token") if self._payload else None

    @property
    def expiration_time(self) -> Optional[datetime]:
        expires_at = self._payload.get("expires_at_seconds") if self._payload else None
        return datetime.fromtimestamp(expires_at) if expires_at else None

    @property
    def _id_attribute(self) -> Optional[str]:
        return self._payload.get("resource_server") if self._payload else None

    @staticmethod
    def decode(string: Union[str, bytes]) -> Mapping:
        if isinstance(string, bytes):
            string = string.decode()
        return json.loads(string)

    def invalid_reason(self) -> Optional[str]:
        if not self._payload or not self._payload.get("access_token"):
            return "Globus Compute token not initialized."
        if self.expiration_time is None:
            return "Globus Compute token missing expiration."
        if datetime.now() > self.expiration_time:
            return "Globus Compute token expired."
        if (self.expiration_time - datetime.now()).total_seconds() < self.minimum_lifetime:
            return "Globus Compute token lifetime too short."
        return None


class IdToken(Token):
    """Represents an ID token credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        extension (str): The file extension for the token.
        scope (Optional[str]): The scope of the token.
        issue_time (Optional[datetime]): The issue time of the token.
        not_before_time (Optional[datetime]): The not-before time of the token.
        expiration_time (Optional[datetime]): The expiration time of the token.

    NOTE: This class is a subclass of the `Token` class.
    """

    cred_type = CredentialType.IDTOKEN
    extension = "idtoken"
