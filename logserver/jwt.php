<?php
// SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
// SPDX-License-Identifier: Apache-2.0

/*  Script to test JWT generation and verification in PHP:
    php jwt.php // To run self test
    php jwt.php TOKEN  // To decode the token
    php jwt.php PAYLOAD TOKEN  // To encode PAYLOAD and save it to TOKEN
    Uses the configuration in logging_config.json:
    - secret_key_path (/var/lib/gwms-factory/server-credentials/jwt_secret.key)
    - secret_key (VG9rZVNlY3JldEtleQo=)
    - verbose (True)  // Print verbose output
    - debug (False)  // Print debug output
*/
// declare(strict_types=1);
use Firebase\JWT\JWT;
use Firebase\JWT\Key;
require_once('./vendor/autoload.php');

// Hardcoded parameters
$configFile = 'logging_config.json';
// Read and extract configuration
$config = json_decode(file_get_contents($configFile), true);
if (! $config) {
    trigger_error("Empty config ($configFile) - the file may be missing or be invalid JSON", E_USER_WARNING);
}
$secretKeyFile = $config['secret_key_path'] ?? '/var/lib/gwms-factory/server-credentials/jwt_secret.key';
$defaultSecretKey = $config['secret_key'] ?? 'VG9rZVNlY3JldEtleQo=';
$verbose = $config['verbose'] ?? True;
$debug = $config['debug'] ?? False;

if ($debug) {
    ini_set('display_errors', 1);
}

// $key = 'example_key';
$key = trim(file_get_contents($secretKeyFile)) ?: $defaultSecretKey;

$payload = [
    'iss' => 'http://example.org',
    'aud' => 'http://example.com',
    'iat' => 1356999524,
    'nbf' => 1357000000
];

echo "Encoding/decoding payload using key: <$key>\n";

if ($argc>1) {
    if ($argc==2) {
        echo "Decoding token in $argv[1]\n";
        $jwt = file_get_contents($argv[1]);
        print_r($jwt);
        $decoded = JWT::decode($jwt, new Key($key, 'HS256'));
        print_r($decoded);
    } else {
        echo "Encoding payload in $argv[1]\n";
        $payload = json_decode(file_get_contents($argv[1]));
        $payload_array = (array) $payload;
        $jwt = JWT::encode($payload_array, $key, 'HS256');
        print_r($jwt);
        echo "Saving token to $argv[2]\n";
        file_put_contents($argv[2], $jwt);
        $decoded = JWT::decode($jwt, new Key($key, 'HS256'));
        print_r($decoded);
    }
} else {
    echo "Encode/decode test with payload\n";
    $jwt = JWT::encode($payload, $key, 'HS256');
    print_r($jwt);
    $decoded = JWT::decode($jwt, new Key($key, 'HS256'));
    print_r($decoded);
}

?>
