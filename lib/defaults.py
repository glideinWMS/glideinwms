"""Collections of constants that are used throughout the GlideinWMS project
"""

# GlideinWMS has to be compatible across versions running on different Python interpreters
# Python 2 text files are the same as binary files except some newline handling
# and strings are the same as bytes
# To maintain this in Python 3 is possible to write binary files and use for the strings
# any encoding that preserves the bytes (0x80...0xff) through round-tripping from byte
# streams to Unicode and back, latin-1 is the best known of these (more compact).
# TODO: alt evaluate the use of latin-1 text files
BINARY_ENCODING = "latin-1"

# All strings should be ASCII, so ASCII or latin-1 (256 safe) should be OK
# Anyway M2Crypto uses 'utf8' to implement AnyStr (union of bytes and str)
BINARY_ENCODING_CRYPTO = 'utf8'


def force_bytes(instr):
    """Forces the output to be bytes, encoding the input if it is a unicode string (str)

    AnyStr is str or bytes types

    Args:
        instr (AnyStr):

    Returns:
        bytes: instr as bytes string

    Raises:
        ValueError: if it detects an improper str conversion (b'' around the string)
    """
    if isinstance(instr, str):
        # raise Exception("ALREAY str!")
        if instr.startswith("b'"):
            raise ValueError("Input was improperly converted into string (resulting in b'' characters added): %s" %
                             instr)
        return instr.encode(BINARY_ENCODING_CRYPTO)
    return instr
