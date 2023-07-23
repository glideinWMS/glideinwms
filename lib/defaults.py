# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Collections of constants that are used throughout the GlideinWMS project
"""

# GlideinWMS has to be compatible across versions running on different Python interpreters
# Python 2 text files are the same as binary files except some newline handling
# and strings are the same as bytes
# To maintain this in Python 3 is possible to write binary files and use for the strings
# any encoding that preserves the bytes (0x80...0xff) through round-tripping from byte
# streams to Unicode and back, latin-1 is the best known of these (more compact).
# TODO: alt evaluate the use of latin-1 text files
BINARY_ENCODING = "latin_1"  # valid aliases (case insensitive)  latin-1, latin1, L1, iso-8859-1, 8859

# All strings should be ASCII, so ASCII or latin-1 (256 safe) should be OK
# Anyway M2Crypto uses 'utf_8' to implement AnyStr (union of bytes and str)
BINARY_ENCODING_CRYPTO = "utf_8"  # valid aliases: utf-8, utf8
BINARY_ENCODING_ASCII = "ascii"  # valid aliases: 646, us-ascii


def force_bytes(instr, encoding=BINARY_ENCODING_CRYPTO):
    """Forces the output to be bytes, encoding the input if it is a unicode string (str)

    AnyStr is str or bytes types

    Args:
        instr (AnyStr): string to be converted
        encoding (str): a valid encoding, utf_8, ascii, latin-1 (iso-8859-1')

    Returns:
        bytes: instr as bytes string

    Raises:
        ValueError: if it detects an improper str conversion (b'' around the string)
    """
    if isinstance(instr, str):
        # raise Exception("ALREADY str!")  # Use this for investigations
        if instr.startswith("b'"):
            raise ValueError(
                "Input was improperly converted into string (resulting in b'' characters added): %s" % instr
            )
        # If the encoding is known codecs can be used for more efficiency, e.g. codecs.latin_1_encode(x)[0]
        return instr.encode(encoding)
    return instr


def force_str(inbytes, encoding=BINARY_ENCODING_CRYPTO):
    """Forces the output to be str, decoding the input if it is a bytestring (bytes)

    AnyStr is str or bytes types

    Args:
        inbytes (AnyStr): string to be converted
        encoding (str): a valid encoding, utf8, ascii, latin-1

    Returns:
        str: instr as unicode string

    Raises:
        ValueError: if it detects an improper str conversion (b'' around the string) or
            the input is neither string or bytes
    """
    if isinstance(inbytes, str):
        # raise Exception("ALREADY str!")
        if inbytes.startswith("b'"):
            raise ValueError(
                "Input was improperly converted into string (resulting in b'' characters added): %s" % inbytes
            )
        return inbytes
    # if isinstance(inbytes, (bytes, bytearray)):
    try:
        return inbytes.decode(encoding)
    except AttributeError:
        # This is not bytes, bytearray (and was not str)
        raise ValueError(f"Input is not str or bytes: {type(inbytes)} ({inbytes})")
