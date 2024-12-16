<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

# Glidein Logging Server

This is a simple server using the httpd server to receive Glidein logs via PUT

-   getjwt.py is a python script to generate tokens
-   put.php is a script to receive JWT authenticated HTTP PUT requests
-   jwt.php is a test script to generate or verify JWT tokens
-   logging.config.json is a config file for both PHP scripts
-   the httpd config to allow PUT is in build/packaging/rpm/gwms-logserver.conf.httpd

The `put.php` script requires the `uploads` and `uploads_unauthorized` sub-directories.
Both PHP scripts require PHP and php-fpm to be executed by the Web server:

```commandline
# run as root
dnf install php
dnf install php-fpm
systemctl start php-fpm
systemctl enable php-fpm httpd
```

Ref: https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/installing_and_using_dynamic_programming_languages/assembly_using-the-php-scripting-language_installing-and-using-dynamic-programming-languages
Both PHP scripts use [Firebase PHP-JWT](https://github.com/firebase/php-jwt)
installed via [Composer](https://getcomposer.org/download/)
as done i n[this tutorial](https://www.sitepoint.com/php-authorization-jwt-json-web-tokens/).

Once Apache 2.5 (now dev version) or 2.6 are available you can use
[mod_auth_jwt](https://httpd.apache.org/docs/trunk/mod/mod_autht_jwt.html) and
[mod_auth_bearer](https://httpd.apache.org/docs/trunk/mod/mod_auth_bearer.html)
to enable JWT bearer token authentication.

## Apache troubleshooting

You can use `apachectl configtest` to verify if your httpd configuration is correct
(Apache silently ignores bad config files).
More suggestions at
<https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/deploying_web_servers_and_reverse_proxies/setting-apache-http-server_deploying-web-servers-and-reverse-proxies>
E.g. you may need to set selinux context:

```commandline
# run as root
semanage fcontext -a -t httpd_sys_content_t "/srv/example.com(/.*)?"
restorecon -Rv /srv/example.com/
semanage fcontext -a -t httpd_sys_content_t "/srv/example.net(/.\*)?"
restorecon -Rv /srv/example.net/
```

To troubleshoot httpd you may increase the log level using `/etc/httpd/conf.d/temp_debug.conf` as
[suggested here](https://serverfault.com/a/1168882/1189965):

```
LogLevel trace4
GlobalLog "logs/debug.log" "%v:%p %h %l %u %t \"%r\" %>s %O file=%f"

# http://httpd.apache.org/docs/current/mod/mod_log_config.html#formats
# %v    The canonical ServerName of the server serving the request.
# %f    Filename.
```

To see the PHP error messages in `put.php` you need to edit `/etc/php.ini` and enable the Development options like:

```doctest
error_reporting = E_ALL
display_errors = On
display_startup_errors = On
```

Remember to disable that for production
