#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module provides classes to represent and manage tokens.
"""

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
    def decode(string: Union[str, bytes]) -> Mapping:
        if isinstance(string, bytes):
            string = string.decode()
        return jwt.decode(string.strip(), options={"verify_signature": False})

    def invalid_reason(self) -> Optional[str]:
        if not self._payload:
            return "Token not initialized."
        if datetime.now() < self.not_before_time:
            return "Token not yet valid."
        if datetime.now() > self.expiration_time:
            return "Token expired."
        if self.minimum_lifetime and (self.expiration_time - datetime.now()).total_seconds() < self.minimum_lifetime:
            return "Token lifetime too short."


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
