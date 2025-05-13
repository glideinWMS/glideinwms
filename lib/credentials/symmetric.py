#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module provides classes to represent and manage symmetric keys.
"""


import binascii
import os

from typing import Optional, Union

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import algorithms, Cipher, modes

from glideinwms.lib.credentials import Credential, CredentialError, CredentialType
from glideinwms.lib.defaults import BINARY_ENCODING_CRYPTO, force_bytes


class SymmetricKey(Credential[Cipher]):
    """Represents a symmetric key credential.

    Attributes:
        cred_type (CredentialType): The type of the credential.
        extension (str): The file extension for the key.
    """

    CIPHER_NAME = "aes_256_cbc"

    cred_type = CredentialType.SYMMETRIC_KEY
    extension = "key"

    @property
    def cipher_name(self):
        """Returns the name of the cipher."""
        return self.string.split(b",")[0].split(b":")[1]

    @property
    def cipher_key(self):
        """Returns the cipher key."""
        return self.string.split(b",")[1].split(b":")[1]

    @property
    def cipher_iv(self):
        """Returns the cipher IV."""
        return self.string.split(b",")[2].split(b":")[1]

    @property
    def _id_attribute(self) -> Optional[str]:
        return self.string

    @staticmethod
    def decode(string: Union[str, bytes]) -> Cipher:
        string = force_bytes(string)
        key = binascii.unhexlify(string.split(b",")[1].split(b":")[1])
        iv = binascii.unhexlify(string.split(b",")[2].split(b":")[1])
        return Cipher(algorithms.AES(key), modes.CBC(iv))

    def invalid_reason(self) -> Optional[str]:
        if self._payload is None:
            return "Symmetric key not initialized."

    def get(self):
        """Returns the key and initialization vector.

        Returns:
            Tuple[bytes, bytes]: The key and IV.
        """

        return self.cipher_key, self.cipher_iv

    def get_wcrypto(self):
        """Returns the cipher name, key, and IV.

        Returns:
            Tuple[bytes, bytes, bytes]: The cipher name, key, and IV.
        """
        return self.cipher_name, self.cipher_key, self.cipher_iv

    def get_code(self):
        """Returns the cipher, key, and IV as a comma-separated string.

        Returns:
            str: The code for the symmetric key.
        """
        return self.string.decode(BINARY_ENCODING_CRYPTO)

    def new(self, random_iv=True):
        """Creates a new symmetric key.

        Returns:
            SymmetricKey: The new symmetric key.
        """
        if random_iv:
            iv = os.urandom(16)
        else:
            iv = b"0" * 16
        key = os.urandom(32)
        name = self.CIPHER_NAME
        return self.load_from_string(f"cipher:{name},key:{key.hex()},iv:{iv.hex()}")

    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """Encrypts the given data using the symmetric key.

        Args:
            data (Union[str, bytes]): The data to encrypt.

        Returns:
            bytes: The encrypted data.
        """
        if self._payload is None:
            raise CredentialError("SymmetricKey not initialized")

        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(force_bytes(data)) + padder.finalize()

        encryptor = self._payload.encryptor()
        return encryptor.update(padded_data) + encryptor.finalize()

    def encrypt_base64(self, data: Union[str, bytes]) -> bytes:
        """Encrypts the given data using the symmetric key and returns it as a base64-encoded string.

        Args:
            data (Union[str, bytes]): The data to encrypt.

        Returns:
            bytes: The base64-encoded encrypted data.
        """
        return binascii.b2a_base64(self.encrypt(data))

    def encrypt_hex(self, data: Union[str, bytes]) -> bytes:
        """Encrypts the given data using the symmetric key and returns it as a hex-encoded string.

        Args:
            data (Union[str, bytes]): The data to encrypt.

        Returns:
            bytes: The hex-encoded encrypted data.
        """
        return binascii.b2a_hex(self.encrypt(data))

    def decrypt(self, data: Union[str, bytes]) -> bytes:
        """Decrypts the given data using the symmetric key.

        Args:
            data (Union[str, bytes]): The data to decrypt.

        Returns:
            bytes: The decrypted data.
        """
        if self._payload is None:
            raise CredentialError("SymmetricKey not initialized")

        decryptor = self._payload.decryptor()
        decrypted_data = decryptor.update(force_bytes(data)) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(decrypted_data) + unpadder.finalize()

    def decrypt_base64(self, data: Union[str, bytes]) -> bytes:
        """Decrypts the given base64-encoded data using the symmetric key.

        Args:
            data (Union[str, bytes]): The base64-encoded data to decrypt.

        Returns:
            bytes: The decrypted data.
        """
        return self.decrypt(binascii.a2b_base64(data))

    def decrypt_hex(self, data: Union[str, bytes]) -> bytes:
        """Decrypts the given hex-encoded data using the symmetric key.

        Args:
            data (Union[str, bytes]): The hex-encoded data to decrypt.

        Returns:
            bytes: The decrypted data.
        """
        return self.decrypt(binascii.a2b_hex(data))
