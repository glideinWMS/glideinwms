#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module provides classes to represent and manage X.509 certificates.
"""

from datetime import datetime, timezone
from typing import Optional, Union

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric.types import CERTIFICATE_PUBLIC_KEY_TYPES

from glideinwms.lib.credentials import Credential, CredentialPair, CredentialPairType, CredentialType
from glideinwms.lib.defaults import force_bytes


class X509Cert(Credential[x509.Certificate]):
    """Represents an X.509 certificate credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        extension (str): The file extension for the credential.
        subject (Optional[str]): The subject (aka Distinguished Name (DN)) of the certificate.
        pub_key (Optional[CERTIFICATE_PUBLIC_KEY_TYPES]): The public key of the certificate.
        not_before_time (Optional[datetime]): The not-before time of the certificate.
        not_after_time (Optional[datetime]): The not-after time of the certificate.
    """

    cred_type = CredentialType.X509_CERT
    extension = "pem"

    @property
    def subject(self) -> Optional[str]:
        """X.509 subject."""
        return "/" + "/".join(self._payload.subject.rfc4514_string().split(",")[::-1]) if self._payload else None

    @property
    def pub_key(self) -> Optional[CERTIFICATE_PUBLIC_KEY_TYPES]:
        """X.509 public key."""
        return self._payload.public_key() if self._payload else None

    @property
    def not_before_time(self) -> Optional[datetime]:
        """X.509 not-before time."""
        try:
            return self._payload.not_valid_before_utc if self._payload else None
        except AttributeError:
            return self._payload.not_valid_before.replace(tzinfo=timezone.utc) if self._payload else None

    @property
    def not_after_time(self) -> Optional[datetime]:
        """X.509 not-after time."""
        try:
            return self._payload.not_valid_after_utc if self._payload else None
        except AttributeError:
            return self._payload.not_valid_after.replace(tzinfo=timezone.utc) if self._payload else None

    @property
    def _id_attribute(self) -> Optional[str]:
        return self.subject

    @staticmethod
    def decode(string: Union[str, bytes]) -> x509.Certificate:
        string = force_bytes(string)
        return x509.load_pem_x509_certificate(string)

    def invalid_reason(self) -> Optional[str]:
        """Checks if the credential is valid and returns a string if it is not.

        Following are the reasons for an invalid x509 certificate:
        1. Certificate was not initialized
        2. Certificate is not yet valid
        3. Expired certificate
        4. Lifetime of the certificate is too short.

        Note: This function checks only the validity of the certificate. This function does not perform verification of the certificate and validation of its chain of trust.

        Returns:
            str or None: A string value indicating the reason for invalidity or a `None` value (if x509 certificate is valid).
        """
        if not self._payload:
            return "Certificate not initialized."
        if datetime.now(self.not_before_time.tzinfo) < self.not_before_time:
            return "Certificate not yet valid."
        if datetime.now(self.not_after_time.tzinfo) > self.not_after_time:
            return "Certificate expired."
        if (self.not_after_time - datetime.now(self.not_after_time.tzinfo)).total_seconds() < self.minimum_lifetime:
            return "Certificate lifetime too short."
        return None  # no reason for invalidity found, so credential is valid


class X509Pair(CredentialPair, X509Cert):
    """Represents a pair of X509 certificates, consisting of a public certificate and a private certificate.

    This class extends both the `CredentialPair` and `X509Cert` classes.

    Attributes:
        cred_type (CredentialPairType): The type of the credential pair.
        private_credential (X509Cert): The private certificate associated with this pair.

    NOTE: Includes all attributes from the X509Cert class.
    """

    cred_type = CredentialPairType.X509_PAIR
    private_cred_type = CredentialType.RSA_PRIVATE_KEY
