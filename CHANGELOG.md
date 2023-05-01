<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

## v3.10.2

### New features / functionalities

-   Add a parameter to control the name of the keyname for idtokens (PR #268)
-   Added a factory knob to allow control over rebuilding of cvmfsexec distributions (PR #272)
-   rhel9 worker node are now recognized by condor_platform_select automatic OS detection (PR #285)

### Changed defaults / behaviours

-   Removed pre-reconfigure hook used for rebuilding cvmfsexec distributions whenever a factory reconfig/upgrade was run (Issue #262).
    -   Rebuilding of cvmfsexec distributions is disabled by default, unless enabled via the new factory knob.

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Make sure default value does not overwrite global one for idtoken_lifetime (PR #261)
-   Protect OSG_autoconf from OSG collector unavailability (PR #276)

### Testing / Development

### Known Issues

## v3.10.1 \[2022-12-13\]

This release fixes a bug introduced in 3.10.0. Changes since the last release

### New features / functionalities

-   Added utility function to replace error_gen in python scripts (PR #254)
-   Improve the generation of JDL file for ARC CE REST interface

### Changed defaults / behaviours

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Fixed status reporting for `gconfig.py` (PR #254)

### Testing / Development

### Known Issues

## v3.10.0 \[2022-12-7\]

This is a production release following v3.9.6 with mostly bug fixes. Changes since the last release

### New features / functionalities

-   Use `SINGULARITY_DISABLE_PID_NAMESPACES` to conditionally include `--pid` in Singularity/Apptainer (OSG SOFTWARE-5340, PR #232)
-   When invoking singularity, inspect stderr and raising a warning if there are "FATAL" errors and the exit code is 0 (PR #235)
-   Added `gconfig.py` Python utilities to read and write glidein_config (PR #237)

### Changed defaults / behaviours

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Set PATH to default value instead of emptying it (PR #233)
-   Return correctly the default value in `gwms_from_config` instead of an empty string (PR #235)
-   Function `get_prop_str` returns the default value when the attribute is "undefined" (PR #235)
-   Fixed credential ID in Glideins not set for scitokens and causing incorrect monitoring values (PR #242)
-   Fixed typo in `singularity_lib.sh` (issue #249)

### Testing / Development

### Known Issues

## v3.9.6 \[2022-10-27\]

Changes since the last release

### New features / functionalities

-   Added token authentication to Glideins running in the Cloud (AWS and GCE). Now Glideins on all supported resources can authenticate back using IDTOKENS when using recent HTCSS versions.
-   Added `GLIDEIN_PERIODIC_SCRIPT` env variable: when set custom scripts run periodically, started by HTCSS startd cron
-   Added the possibility to set the Glidein HTCSS TRUST_DOMAIN as attribute in the Frontend configuration

### Changed defaults / behaviours

-   Frontend configuration valid (reconfig/upgrade successful) even if some HTCSS schedds are not in DNS. Failing only if all schedds are unknown to DNS.
-   Working and local tmp directories are removed during Glidein cleanup also when the start directory is missing. This result in a loss of Glidein final status information but avoids sandbox leaks on the Worker Node. (issue #189)
-   HTCSS DC_DAEMON_LIST equal to DAEMON_LIST only in the Factory, in all other GlideinWMS components only selected HTCSS daemons are added explicitly to it (issue #205)
-   Only the first collector in TRUST_DOMAIN is kept, following collectors are removed. This happens both in the Frontend token issuer and in the setting of the Glidein TRUST_DOMAIN (setup_x509.sh).

### Deprecated / removed options and commands

-   To make `glidein_config` more robust and resistant to concurrent interactions the handling function to use in custom scripts have been updated:
    -   `add_config_line`, `add_config_line_safe` and custom parsing or writing from/to `glidein_config` are deprecated and will be removed form future versions (a change in format will make custom read not work correctly)
    -   `gconfig_add` and `gconfig_add_safe` replace the current `add_config_line` and `add_config_line_safe` respectively
    -   `gconfig_get` should be used to retrieve values form `glidein_config`
    -   During the transition period both new and old functions will work

### Security Related Fixes

### Bug Fixes

-   Fixed glidien_config` corrupted by concurrent custom scripts run via HTCSS startd cron (#163)
-   Fixed setup_x509.sh` not to write to stdout when running as periodic script in HTCSS start cron (issues #162, #164 )
-   Fixed setup_x509.sh creates proxy file in directory used for tokens (issue #201)
-   Fixed GLIDEIN_START_DIR_ORIG and GLIDEIN_WORKSPACE_ORIG values in glidein_config
-   Fixed unnecessary proxy/hostcert.pem workaround in frontend config (issue #66)
-   Fixed analyze_entries and python3 readiness (issue #194)
-   Fixed gwms-renew-proxies service should check if local VOMS cert is expired (issue #21)
-   Fixed python3 check return value in case of exception (PR #211)
-   Fixed list_get_intersection in singularity_lib.sh that was requiring python2 (PR #212)
-   Unset SEC_PASSWORD_DIRECTORY in the Glidein HTCSS configuration, was causing warnings for unknown files (PR #226).

### Testing / Development

### Known Issues

## Template

This template section should stay at the bottom of the document.
Whenever a new release is cut, the section title should change, empty subsections removed, and a new "Changes Since Last Release" with the template subsections added on top.
This should be a description of the changes, not a Git log. Operators and users affecting changes are especially important to highlight.
Please classify the code changes using the listed subsections. If a new one is needed, add it also to the template.

## Changes Since Last Release OR vX.Y.Z \[yyyy-mm-dd\]

Changes since the last release

### New features / functionalities

-   item one of the list
-   item N

### Changed defaults / behaviours

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

### Testing / Development

### Known Issues
