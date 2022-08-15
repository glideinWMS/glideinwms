<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

# GlideinWMS Changelog

Developers updated changelog. For curated release notes see doc/tags.yaml or https://glideinwms.fnal.gov/doc.prd/history.html

## v3.9.6 \[2022-07-dd\]

Changes since the last release

### New features / functionalities

-   Added `GLIDEIN_PERIODIC_SCRIPT` env variable: when set custom scripts run periodically, started by HTCSS startd cron

### Changed defaults / behaviours

-   Frontend configuration valid (reconfig/upgrade successful) even if some HTCSS schedds are not in DNS. Failing only if all schedds are unknown to DNS.

### Deprecated / removed options and commands

-   To make `glidein_config` more robust and resistant to concurrent interactions the handling function to use in custom scripts have been updated:
    -   `add_config_line`, `add_config_line_safe` and custom parsing or writing from/to `glidein_config` are deprecated and will be removed form future versions (a change in format will make custom read not work correctly)
    -   `gconfig_add` and `gconfig_add_safe` replace the current `add_config_line` and `add_config_line_safe` respectively
    -   `gconfig_get` should be used to retrieve values form `glidein_config`
    -   During the transition period both new and old functions will work

### Security Related Fixes

### Bug Fixes

-   Fixed `glidien_config` corrupted by concurrent custom scripts run via HTCSS startd cron (#163)
-   Fixed `setup_x509.sh` not to write to stdout when running as periodic script in HTCSS start cron (issues #162, #164 )
-   Fixed setup_x509.sh creates proxy file in directory used for tokens (issue 201)
-   Fixed unnecessary proxy/hostcert.pem workaround in frontend config (issue #66)
-   Fixed analyze_entries and python3 readiness (issue #194)
-   Fixed gwms-renew-proxies service should check if local VOMS cert is expired (issue #21)

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
