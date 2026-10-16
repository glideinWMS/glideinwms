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
        """Token issue time. None if the token is undefined or the claim not defined"""
        if not self._payload:
            return None
        try:
            return datetime.fromtimestamp(self._payload["iat"])
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            # KeyError if the claim is not defined in the token
            # The other 4 errors are for invalid values or OS misconfigurations (from datetime.fromtimestamp)
            return None

    @property
    def not_before_time(self) -> Optional[datetime]:
        """Token not-before time. None if the token is undefined or the claim not defined"""
        if not self._payload:
            return None
        try:
            return datetime.fromtimestamp(self._payload["nbf"])
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            # KeyError if the claim is not defined in the token
            # The other 4 errors are for invalid values or OS misconfigurations (from datetime.fromtimestamp)
            return None

    @property
    def expiration_time(self) -> Optional[datetime]:
        """Token expiration time. None if the token is undefined or the claim not defined"""
        if not self._payload:
            return None
        try:
            return datetime.fromtimestamp(self._payload["exp"])
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            # KeyError if the claim is not defined in the token
            # The other 4 errors are for invalid values or OS misconfigurations (from datetime.fromtimestamp)
            return None

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
        2. Token is not yet valid (if not_before_time is provided)
        3. Expired token (if expiration_time is provided)
        4. Lifetime of the token is too short (if expiration_time is provided).

        Note: This function checks only the validity of the credential but does not perform verification of the credential.

        Returns:
            str or None: A string value indicating the reason for invalidity or a `None` value (if token is valid).
        """
        if not self._payload:
            return "Token not initialized."
        if self.not_before_time is not None and datetime.now() < self.not_before_time:
            return "Token not yet valid."
        if self.expiration_time is not None:
            if datetime.now() > self.expiration_time:
                return "Token expired."
            if (self.expiration_time - datetime.now()).total_seconds() < self.minimum_lifetime:
                return "Token lifetime too short."
        return None  # no reason for invalidity found, so credential is valid

    def save_to_file(
        self,
        path: Optional[str] = None,
        permissions: int = 0o600,
        backup: bool = False,
        compress: bool = False,
        data_pattern: Optional[bytes] = None,
        overwrite: bool = True,
        continue_if_no_path: bool = False,
        add_newline: bool = True,
    ) -> None:
        """Save the Token to a file. This method does exactly the same as the `save_to_file` method of the parent Credential class,
        except that it defaults to adding a newline at the end of the saved file.

        Args:
            path (Optional[str]): The path to the file where the Token will be saved.
            permissions (int): The permissions to set for the saved file. Default is 0o600.
            backup (bool): Whether to create a backup of the existing file. Default is False.
            compress (bool): Whether to compress the Token before saving. Default is False.
            data_pattern (Optional[bytes]): A pattern to format the Token data before saving. Default is None.
            overwrite (bool): Whether to overwrite the existing file if it already exists. Default is True.
            continue_if_no_path (bool): If True, silently return without saving a file if no path is specified. Default is False.
            add_newline (bool): Whether to add a newline at the end of the saved file. Default is True.

        Raises:
            CredentialError: If the credential is not initialized or if there is an error saving the credential.
        """
        super().save_to_file(
            path=path,
            permissions=permissions,
            backup=backup,
            compress=compress,
            data_pattern=data_pattern,
            overwrite=overwrite,
            continue_if_no_path=continue_if_no_path,
            add_newline=add_newline,
        )


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
