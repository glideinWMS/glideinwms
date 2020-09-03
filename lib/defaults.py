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
