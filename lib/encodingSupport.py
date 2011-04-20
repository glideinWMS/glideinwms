import base64

supported_encoding_types = ['b16', 'b32', 'b64']

class EncodingTypeError(Exception):
    """Encoding type exception

    @ivar encoding_type: The encoding type that was specified
    @ivar supported_types: A list of the supported encoding types
    """
    def __init__(self, encoding_type, supported_types):
        message = "Invalid encoding type specified: %s.  Supported encoding" \
                  " types are: %s" % (encoding_type, supported_encoding_types)
        # Call the base class constructor with the parameters it needs
        Exception.__init__(self, message)

def encode_data(data, encoding="b64", url_safe=False):
    """This function encodes data using the base64 library.

    @raise EncodingTypeError: This exception occurs if an invalid encoding type
        is specified
    """
    encoded_data = ""
    if encoding in supported_encoding_types:
        if encoding == "b16":
            encoded_data = base64.b16encode(data)
        elif encoding == "b32":
            encoded_data = base64.b32encode(data)
        else:  # We assume that the encoding type is the default (b64)
            if url_safe:
                encoded_data = base64.urlsafe_b64encode(data)
            else:
                encoded_data = base64.b64encode(data)
        return encoded_data
    else:
        raise EncodingTypeError(encoding, supported_encoding_types)

def decode_data(encoded_data, encoding="b64", url_safe=False):
    """This function decodes previously encoded data using the base64 library
    or base64 compatible library.  For security purposes, some optional
    parameters are not allowed in some of the supported encoding types.  See
    U{http://docs.python.org/library/base64.html}

    @raise EncodingTypeError: This exception occurs if an invalid encoding type
        is specified
    @raise TypeError: This exception occurs if data is incorrectly padded or if
        there are non-alphabet characters present in the string.
    """
    decoded_data = ""
    if encoding in supported_encoding_types:
        if encoding == "b16":
            decoded_data = base64.b16decode(encoded_data)
        elif encoding == "b32":
            decoded_data = base64.b32decode(encoded_data)
        else:  # We assume that the encoding type is the default (b64)
            if url_safe:
                decoded_data = base64.urlsafe_b64decode(encoded_data)
            else:
                decoded_data = base64.b64decode(encoded_data)
        return decoded_data
    else:
        raise EncodingTypeError(encoding, supported_encoding_types)
