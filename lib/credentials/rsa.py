#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module provides classes to represent and manage RSA public and private keys.
"""

import binascii

from hashlib import md5
from typing import Optional, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.types import PRIVATE_KEY_TYPES, PUBLIC_KEY_TYPES

from glideinwms.lib.credentials import Credential, CredentialError, CredentialPair, CredentialPairType, CredentialType
from glideinwms.lib.credentials.symmetric import SymmetricKey
from glideinwms.lib.defaults import force_bytes

DEFAULT_PASSWORD = b"default"


class RSAPublicKey(Credential[PUBLIC_KEY_TYPES]):
    """Represents an RSA public key credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        extension (str): The file extension for the key.
        key_type (Optional[str]): The type of the RSA key.
    """

    cred_type = CredentialType.RSA_PUBLIC_KEY
    extension = "rsa"

    @property
    def key_type(self) -> Optional[str]:
        """RSA key type.

        NOTE: This property always returns "RSA" if the key is initialized.
        """
        return "RSA" if self._payload else None

    @property
    def _id_attribute(self) -> Optional[str]:
        return self.string

    @staticmethod
    def decode(string: Union[str, bytes]) -> PUBLIC_KEY_TYPES:
        string = force_bytes(string)
        if string.startswith(b"ssh-rsa"):
            return serialization.load_ssh_public_key(string, backend=default_backend())
        return serialization.load_pem_public_key(string, backend=default_backend())

    def invalid_reason(self) -> Optional[str]:
        """Checks if the credential is valid and returns a string if it is not.

        Following are the reasons for an invalid RSA Public Key:
        - RSA Public Key is not initialized

        Note: This function checks only the validity of the credential but does not perform verification of the credential.

        Returns:
            str or None: A string value indicating the reason for invalidity or a `None` value (if RSA public key is valid).
        """
        if not self._payload:
            return "RSA key not initialized."
        return None  # no reason for invalidity found, so credential is valid

    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """Encrypts the given data using the RSA key.

        Args:
            data (Union[str, bytes]): The data to encrypt.

        Returns:
            bytes: The encrypted data.
        """
        data = force_bytes(data)
        return self._payload.encrypt(
            data, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        )

    def encrypt_base64(self, data: Union[str, bytes]) -> bytes:
        """Encrypts the given data using the RSA key and returns the encrypted data in base64 format.

        Args:
            data (Union[str, bytes]): The data to encrypt.

        Returns:
            bytes: The base64 encoded encrypted data.
        """
        return binascii.b2a_base64(self.encrypt(data))

    def encrypt_hex(self, data: Union[str, bytes]) -> bytes:
        """Encrypts the given data using the RSA key and returns the encrypted data in hex format.

        Args:
            data (Union[str, bytes]): The data to encrypt.

        Returns:
            bytes: The hex encoded encrypted data.
        """
        return binascii.b2a_hex(self.encrypt(data))

    def verify(self, data: Union[str, bytes], signature: bytes) -> bool:
        """Verifies the given signature using the RSA key.

        Args:
            data (Union[str, bytes]): The data to verify.
            signature (bytes): The signature to verify.

        Raises:
            CredentialError: If the signature is invalid.
        """
        data = force_bytes(data)
        try:
            self._payload.verify(
                signature,
                data,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
        except InvalidSignature:
            return False
        except Exception as e:
            raise CredentialError(f"Error verifying signature: {e}") from e
        return True

    def verify_base64(self, data: Union[str, bytes], signature: bytes) -> bool:
        """Verifies the given base64 signature using the RSA key.

        Args:
            data (Union[str, bytes]): The data to verify.
            signature (bytes): The base64 signature to verify.

        Raises:
            CredentialError: If the signature is invalid.
        """
        return self.verify(data, binascii.a2b_base64(signature))

    def verify_hex(self, data: Union[str, bytes], signature: bytes) -> bool:
        """Verifies the given hex signature using the RSA key.

        Args:
            data (Union[str, bytes]): The data to verify.
            signature (bytes): The hex signature to verify.

        Raises:
            CredentialError: If the signature is invalid.
        """
        return self.verify(data, binascii.a2b_hex(signature))


class RSAPrivateKey(Credential[PRIVATE_KEY_TYPES]):
    """Represents an RSA private key credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        extension (str): The file extension for the key.
        pub_key (Optional[RSAPublicKey]): The public key of the RSA key.
        pub_key_id (Optional[str]): The ID of the public key.
        key_type (Optional[str]): The type of the RSA key.
    """

    cred_type = CredentialType.RSA_PRIVATE_KEY
    extension = "rsa"

    @property
    def pub_key(self) -> Optional[RSAPublicKey]:
        """RSA public key."""
        if not self._payload:
            return None
        pub_key_str = self._payload.public_key().public_bytes(
            encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return RSAPublicKey(string=pub_key_str)

    @property
    def pub_key_id(self) -> Optional[str]:
        """RSA public key ID."""
        if self.pub_key is None:
            return None
        return md5(b" ".join((self.key_type.encode("utf-8"), self.pub_key.string))).hexdigest()

    @property
    def _id_attribute(self) -> Optional[str]:
        return self.string

    @property
    def key_type(self) -> Optional[str]:
        """RSA key type.

        NOTE: This property always returns "RSA" if the key is initialized.
        """
        return "RSA" if self._payload else None

    @staticmethod
    def decode(string: Union[str, bytes]) -> PRIVATE_KEY_TYPES:
        string = force_bytes(string)
        if string.startswith(b"-----BEGIN OPENSSH PRIVATE KEY-----"):
            return serialization.load_ssh_private_key(string, password=None, backend=default_backend())
        return serialization.load_pem_private_key(string, password=DEFAULT_PASSWORD, backend=default_backend())

    def invalid_reason(self) -> Optional[str]:
        """Checks if the credential is valid and returns a string if it is not.

        Following are the reasons for an invalid RSA private key:
        1. RSA Private Key is not initialized
        2. RSA Public Key is not initialized
        3. RSA Public Key ID is not initialized

        Note: This function checks only the validity of the credential but does not perform verification of the credential.

        Returns:
            str or None: A string value indicating the reason for invalidity or a `None` value (if RSA private key is valid).
        """
        if not self._payload:
            return "RSA key not initialized."
        if not self.pub_key:
            return "RSA public key not initialized."
        if not self.pub_key_id:
            return "RSA public key ID not initialized."
        return None  # no reason for invalidity found, so credential is valid

    def recreate(self) -> None:
        """Recreates the RSA key.

        Raises:
            CredentialError: If the RSA key is not initialized.
        """
        if self._payload is None:
            raise CredentialError("RSAKey not initialized")

        self.new(self._payload.key_size)
        self.save_to_file()

    def extract_sym_key(self, enc_sym_key: Union[str, bytes]) -> SymmetricKey:
        """Extracts the symmetric key using the RSA key.

        Args:
            enc_sym_key (Union[str, bytes]): The encrypted symmetric key.

        Returns:
            SymmetricKey: The extracted symmetric key.

        Raises:
            CredentialError: If the RSA key is not initialized.
        """
        if self._payload is None:
            raise CredentialError("RSAKey not initialized")

        enc_sym_key = force_bytes(enc_sym_key)
        return SymmetricKey(self.decrypt(binascii.a2b_hex(enc_sym_key)))

    def new(self, key_length=None, exponent=65537):
        """Creates a new RSA key.

        Returns:
            RSAPrivateKey: The new RSA key.

        Raises:
            KeyError: If the key length is not specified.
        """
        if not key_length:
            raise KeyError("Key length must be specified.")
        new_key = rsa.generate_private_key(exponent, key_length).private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(DEFAULT_PASSWORD),
        )
        return self.load_from_string(string=new_key)

    def decrypt(self, data: Union[str, bytes]):
        """Decrypts the given data using the RSA key.

        Args:
            data (Union[str, bytes]): The data to decrypt.

        Returns:
            bytes: The decrypted data.

        Raises:
            CredentialError: If decryption fails with all padding schemes.
        """
        data = force_bytes(data)
        for padding_func in (
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
        ):
            try:
                return self._payload.decrypt(data, padding_func)
            except ValueError:
                continue
        raise CredentialError("Decryption failed with all padding schemes.")

    def decrypt_base64(self, data: Union[str, bytes]) -> bytes:
        """Decrypts the base64 encoded data using the RSA key and returns the decrypted binary data.

        Args:
            data (Union[str, bytes]): Base64 encoded data to decrypt.

        Returns:
            bytes: The decrypted data.
        """
        return self.decrypt(binascii.a2b_base64(data))

    def decrypt_hex(self, data: Union[str, bytes]) -> bytes:
        """Decrypts the hex encoded data using the RSA key and returns the decrypted binary data.

        Args:
            data (Union[str, bytes]): Hex encoded data to decrypt.

        Returns:
            bytes: The decrypted data.
        """
        return self.decrypt(binascii.a2b_hex(data))

    def sign(self, data: Union[str, bytes]) -> bytes:
        """Signs the given data using the RSA key.

        Args:
            data (Union[str, bytes]): The data to sign.

        Returns:
            bytes: The signed data.
        """
        data = force_bytes(data)
        return self._payload.sign(
            data, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256()
        )

    def sign_base64(self, data: Union[str, bytes]) -> bytes:
        """Signs the given data using the RSA key and returns the signature in base64 format.

        Args:
            data (Union[str, bytes]): The data to sign.

        Returns:
            bytes: The base64 encoded signature.
        """
        return binascii.b2a_base64(self.sign(data))

    def sign_hex(self, data: Union[str, bytes]) -> bytes:
        """Signs the given data using the RSA key and returns the signature in hex format.

        Args:
            data (Union[str, bytes]): The data to sign.

        Returns:
            bytes: The hex encoded signature.
        """
        return binascii.b2a_hex(self.sign(data))


class RSAKeyPair(CredentialPair, RSAPublicKey):
    """Represents a pair of RSA keys, consisting of a public key and a private key.

    This class extends both the `CredentialPair` and `RSAPublicKey` classes.

    Attributes:
        cred_type (CredentialPairType): The type of the credential pair.
        private_credential (RSAKey): The private key associated with this pair.

    NOTE: Includes all attributes from the RSAKey class.
    """

    cred_type = CredentialPairType.KEY_PAIR
    private_cred_type = CredentialType.RSA_PRIVATE_KEY
