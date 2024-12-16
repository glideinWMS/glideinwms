<?php
// SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
// SPDX-License-Identifier: Apache-2.0

/*  PHP script to implement file upload via PUT
    The file content is received via stdin (Apache PUT implementation)
    A JSON configuration is in logging_config.json, valid parameters are:
    - secret_key_path (/var/lib/gwms-factory/server-credentials/jwt_secret.key)
    - secret_key (VG9rZVNlY3JldEtleQo=)
    - default_file_name (glideinlog.txt)
    - uri_regex_file_name ()#logging/put.php/(\S+)#)
    - token_issuer (gethostname())  // Should be the Factory, assuming is the same host by default
    - upload_dir (uploads/)
    - upload_dir_unauthorized (uploads_unauthorized/)
    - require_authentication (True)
    - verbose (True)  // Print verbose output
    - debug (False)  // Print debug output
    The destination file name is retrieved from the URI:
    - as GET parameter fname, e.g.    ...put.php?fname=NAME
    - as path, e.g.  ...logging/put.php/NAME
    The authentication is via JWT
    - HS256 encoded JWT
    - iss must be the Factory
    - the key is stored in '/var/lib/gwms-factory/server-credentials/jwt_secret.key'
    - aud should be the Web server
    If requireAuthentication is False, files are uploaded also w/o valid JWT
*/

// declare(strict_types=1);
use Firebase\JWT\JWT;
use Firebase\JWT\Key;
require_once('../vendor/autoload.php');

// Hardcoded parameters
$configFile = '../logging_config.json';

// Read and extract configuration
$config = json_decode(file_get_contents($configFile), true);
if (! $config) {
    trigger_error("Empty config ($configFile) - the file may be missing or be invalid JSON", E_USER_WARNING);
}
$secretKeyFile = $config['secret_key_path'] ?? '/var/lib/gwms-factory/server-credentials/jwt_secret.key';
$defaultSecretKey = $config['secret_key'] ?? '';
$defaultFileName = $config['default_file_name'] ?? 'glideinlog.txt';
$uriRegexFileName = $config['uri_regex_file_name'] ?? '#logging/put.php/(\S+)#';
$tokenIssuer = $config["token_issuer"] ?? gethostname();  // Should be the factory
$uploadPath = $config['upload_dir'] ?? 'uploads/';
$uploadPathUnauthorized = $config['upload_dir_unauthorized'] ?? 'uploads_unauthorized/';
$requireAuthentication = $config['require_authentication'] ?? True;
$verbose = $config['verbose'] ?? True;
$debug = $config['debug'] ?? False;

if ($debug) {
    ini_set('display_errors', 1);
}

function filename_sanitizer($unsafeFilename){
  // our list of "unsafe characters", add/remove characters if necessary
  $dangerousCharacters = array(" ", '"', "'", "&", "/", "\\", "?", "#", "<", ">", "..");
  // every forbidden character is replaced by an underscore
  $safeFilename = str_replace($dangerousCharacters, '_', $unsafeFilename);
  return $safeFilename;
}

function auth_failed($headerCode, $msg){
    if ($GLOBALS['requireAuthentication']) {
        http_response_code($headerCode);
        echo "$headerCode: $msg\n";
        exit;
    }
    if ($GLOBALS['verbose']) {
        echo "$headerCode: $msg\n";
    }
}


/* The file name (default from the config file) is specified in the URI either as
   GET parameter fname   put.php?fname=NAME
   or as path  logging/put.php/NAME
   */
$fileName = $_GET['fname'] ?? $defaultFileName;
if (preg_match($uriRegexFileName, $_SERVER['REQUEST_URI'], $matches)) {
    $fileName = $matches[1];
}

// Not authorized unless the token verification is successful
$isAuthorized = False;
// Get authorization header and extract the token
$authorizationHeader = getallheaders()["Authorization"] ?? "";
//$token = preg_match("/Bearer (?P<token>[^\s]+)/", $authorizationHeader, $matches) ? $matches["token"] : "";
if (! preg_match('/Bearer\s(?P<token>\S+)/', $authorizationHeader, $matches)) {
    // No token in request
    auth_failed(400, 'Token not found in request');
    $jwt = "";
} else {
    $jwt = $matches["token"];
}
if (! $jwt) {
    // Unable to extract token from the authorization header
    auth_failed(400, 'Unable to extract token from the authorization header');
} else {
    try {
        // Read secret key from file or set to the default
        $secretKey = trim(file_get_contents($secretKeyFile)) ?: $defaultSecretKey;
        if (! $secretKey) {
            if ($debug) {
                echo "Server mis-configured. JWT key not defined."
            }
            auth_failed(500, 'Server error. Error decoding JWT');
        }
        $token = JWT::decode($jwt, new Key($secretKey, 'HS256'));
        $now = new DateTimeImmutable();
        $serverAddress = 'https://' . $_SERVER['SERVER_ADDR'];
        $serverName = 'https://' . $_SERVER['SERVER_NAME'];
        // Verify token (iss, aud and expiration)
        if ($token->iss !== $tokenIssuer ||
            ( ! str_starts_with($token->aud, urlencode($serverAddress)) &&
             ! str_starts_with($token->aud, urlencode($serverName))) ||
            $token->nbf > $now->getTimestamp() ||
            $token->exp < $now->getTimestamp())
        {
            if ($debug) {
                $res0 = ! str_starts_with($token->aud, urlencode($serverAddress)) &&
                    ! str_starts_with($token->aud, urlencode($serverName)) ? 'true' : 'false';
                $res1 = str_starts_with($token->aud, urlencode($serverAddress)) ? 'true' : 'false';
                $res2 = urlencode($serverAddress);
                $res3 = str_starts_with($token->aud, urlencode($serverName)) ? 'true' : 'false';
                $res4 = urlencode($serverName);
                $res5 = $token->nbf > $now->getTimestamp() ? 'true' : 'false';
                $res6 = $token->exp < $now->getTimestamp() ? 'true' : 'false';
                $res7 = $token->iss !== $tokenIssuer ? 'true' : 'false';
                echo "Authorization failed:\n- iss $res7: {$token->iss} VS {$tokenIssuer}\n".
                    "- aud $res0, addr $res1, name $res3: {$token->aud} VS $res2, $res4\n- nbf $res5\n- exp $res6\n";
            }
            auth_failed(401, 'Wrong authorization (wrong claims or token expired)');
        } else {
            $isAuthorized = True;
        }
    } catch (Firebase\JWT\SignatureInvalidException $e) {
        auth_failed(401, 'Invalid JWT signature');
    } catch (Exception $e) {
        auth_failed(500, 'Error decoding JWT');
    }
}

// debug variables printout
if ($debug) {
    var_dump( get_defined_vars() );
}

$fname = filename_sanitizer($fileName);
if (! $isAuthorized) {
    $uploadPath = $uploadPathUnauthorized;
}

// Save the file in the desired location and return error upon failure
try {
    // PUT data comes in on the stdin stream
    $putdata = fopen('php://input', 'r');

    if ($fp = fopen($uploadPath . $fname, 'w')) {
        // Read the data 1 KB at a time and write to the file
        while ($data = fread($putdata, 1024))
            fwrite($fp, $data);
        fclose($fp);
    } else {
        http_response_code(500);
        echo "500: Error opening the output file\n";
        exit;
    }
    fclose($putdata);
} catch (Exception $e) {
    http_response_code(500);
    echo "500: Error saving the upload file\n";
    exit;
}
?>
