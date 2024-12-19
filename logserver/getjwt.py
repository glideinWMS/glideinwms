#!/bin/env python3
# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Print a JWT token
python getjwt.py -k your_secret_key -i https://your-issuer.com
Options
-k --key JWT signing key
-
"""

import argparse
import os
import socket
import time
import urllib.parse

import jwt


def log(msg: str):
    print(msg)


tokens_dir = "./"
this_host = socket.gethostname()
# Parse command-line arguments
parser = argparse.ArgumentParser(description="Generate a JWT token for the GlideinWMS logging.")
parser.add_argument("-k", "--key", default=None, help="Secret key for JWT signing (overrides the key-file).")
parser.add_argument("-K", "--key-file", required=False, help="Binary file containing the secret key for JWT signing.")
parser.add_argument(
    "-d", "--duration", type=int, default=604800, help="Duration of the token in seconds (default: 3600)."
)
parser.add_argument("-e", "--entry", default="TEST_TOKEN", help="Entry, for the Subject (sub) claim for the JWT.")
parser.add_argument("-f", "--factory", default=this_host, help="Factory, for Issuer (iss) claim for the JWT.")
parser.add_argument("-a", "--algorithm", default="HS256", help="JWT encoding algorithm.")
parser.add_argument(
    "-u", "--log-url", default=f"http://{this_host}/logging/put.php", help="Issuer (iss) claim for the JWT."
)
parser.add_argument("-o", "--output", default=None, help="Output file to write the JWT.")
args = parser.parse_args()
if args.key is None and not args.key_file:
    # log("ERROR: You must provide a key string or a key file")
    parser.error("ERROR: You must provide a key string or a key file")

curtime = int(time.time())

token_key = args.key
if token_key is None:
    if args.key_file:
        try:
            with open(args.key_file, "rb") as key_file:
                token_key = key_file.read()
        except OSError:
            log(f"ERROR: Unable to read token key from file: {args.key_file}")
            raise

# Define payload with issuer from arguments
# Payload fields:
# iss->issuer,      sub->subject,       aud->audience
# iat->issued_at,   exp->expiration,    nbf->not_before
payload = {
    "user_id": 123,  # Replace with actual user ID or other data
    "iss": args.factory,  # Set issuer from command-line argument
    "sub": args.entry,
    # Obtain a legal filename safe string from the url, escaping "/" and other tricky symbols
    "aud": urllib.parse.quote(args.log_url, ""),
    # "issued_at": curtime,
    "iat": curtime,
    "exp": curtime + args.duration,
    "nbf": curtime - 300,
}

# Generate JWT using secret key from arguments
print(f"Encoding token with key: <{token_key}>")
token = jwt.encode(payload, token_key, algorithm=args.algorithm)
# TODO: PyJWT bug workaround. Remove this conversion once affected PyJWT is no more around
#  PyJWT in EL7 (PyJWT <2.0.0) has a bug, jwt.encode() is declaring str as return type, but it is returning bytes
#  https://github.com/jpadilla/pyjwt/issues/391
if isinstance(token, bytes):
    token = token.decode("UTF-8")

if args.output is None:
    print(token)
else:
    token_filepath = os.path.join(tokens_dir, args.output)
    try:
        # Write the token to a text file
        with open(token_filepath, "w") as tkfile:
            tkfile.write(token)
        log(f"Token for {args.log_url} ({urllib.parse.quote(args.log_url, '')}) written to {token_filepath}")
    except OSError:
        log(f"ERROR: Unable to create JWT file: {token_filepath}")
        raise
