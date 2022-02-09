<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

# GlideinWMS

[![DOI](https://zenodo.org/badge/1833401.svg)](https://zenodo.org/badge/latestdoi/1833401)

![.github/workflows/pyunittest.yaml](https://github.com/GlideinWMS/glideinwms/workflows/.github/workflows/pyunittest.yaml/badge.svg)
![.github/workflows/pylint.yaml](https://github.com/GlideinWMS/glideinwms/workflows/.github/workflows/pylint.yaml/badge.svg)
![.github/workflows/bats.yaml](https://github.com/GlideinWMS/glideinwms/workflows/.github/workflows/bats.yaml/badge.svg)
![.github/workflows/pycodestyle.yaml](https://github.com/GlideinWMS/glideinwms/workflows/.github/workflows/pycodestyle.yaml/badge.svg)
![.github/workflows/build.yaml](https://github.com/GlideinWMS/glideinwms/workflows/.github/workflows/build.yaml/badge.svg)
![.github/workflows/reuse.yaml](https://github.com/GlideinWMS/glideinwms/workflows/.github/workflows/reuse.yaml/badge.svg)

The purpose of the GlideinWMS is to provide a simple way to access distributed computing resources, including Grid resources, institutional clusters, commercial clouds (AWS and GCE) and HPC resources. 
GlideinWMS is a Glidein Based WMS (Workload Management System) that works on top of HTCondor. Glideins, aka pilot jobs, are like placeholders, a mechanism by which one or more remote resources temporarily join a local HTCondor pool. The HTCondor system is used for scheduling and job control.

The code is available as RPM via the Open Science Grid yum repository
and is distributed under the Apache 2.0 license, see the [LICENSE](LICENSE) file.

For release notes, a detailed description and installation, configuration and use instructions see:
https://glideinwms.fnal.gov/

For build instruction and development guidlines see:
https://cdcvs.fnal.gov/redmine/projects/glideinwms/wiki

