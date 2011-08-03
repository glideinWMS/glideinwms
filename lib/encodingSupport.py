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
    """Encode data using the base64 library.

    @param data: Data to be encoded
    @param encoding: Encoding type.  Supported types are 'b16', 'b32', and 'b64'
        The default is 'b64'.
    @param url_safe: Only valid if encoding is 'b64'.  If True, this causes the
        encoding to be performed by the urlsafe_b64encode function. Default is
        False
    @param data: Data to be encoded
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
    """Decode previously encoded data using the base64 library or base64
    compatible library.  For security purposes, some optional parameters are
    not allowed in some of the supported encoding types.  See
    U{http://docs.python.org/library/base64.html}


    @param encoded_data: Encoded data that will be decoded
    @param encoding: Encoding type.  Supported types are 'b16', 'b32', and 'b64'
        The default is 'b64'.
    @param url_safe: Only valid if encoding is 'b64'.  If True, this causes the
        decoding to be performed by the urlsafe_b64decode function. Default is
        False
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
