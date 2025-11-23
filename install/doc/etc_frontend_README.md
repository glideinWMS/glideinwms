<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

This directory contains the GlideinWMS configuration

System administrators should need to add or edit only files in this directory

-   frontend.xml is the main configuration file
-   cred.d contains credentials
    -   You can add here static credentials referred to in the configuration file
    -   passwords.d contains optional password files for the HTCondor pools (there are also in /var/lib/gwms-frontend/cred.d/passwords.d)
-   plugins.d are user-definable plugins, like the ones to generate SciTokens
-   hooks.reconfig.pre and hooks.reconfig.post are scripts executed before and after the reconfig and upgrade commands

Plugins and hooks may include hardcoded configuration and should be in human-readable format (e.g. shell or Python scripts)
