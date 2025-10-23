<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

## Changes Since Last Release OR vX.Y.Z \[yyyy-mm-dd\]

Changes since the last release

### New features / functionalities

-   Recognize EL/CentOS 10 worker nodes to select the correct HTCondor tarball (PR #600)
-   Factory monitoring now showing Client Requested Idle Glideins; only keeping track of Factory adjusted Idle (PR# #606, Issue #520)

### Changed defaults / behaviours

-   Example

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

### Testing / Development

### Known Issues

## v3.10.16 \[2025-09-29\]

Bug fix release. Mostly CVMFS and HTCondor job wrapper related.

### New features / functionalities

-   create_cvmfsexec_distros.sh updated adding EL9 to platforms and improved command syntax (Issue #549, PR #582)
-   Added new staticextra resource type – behaves like static (creates one dedicated slot per instance with a virtual CPU each), but instead of subtracting memory from the main partitionable slot, it adds memory to it (Issue #590, PR #591)
-   OSG_autoconf: Added mapping for EIC and CLAS12 and support for the new dedicated `OSG` collector parameter to set `EstimatedCPUs` replacing the use of the generic `CPUs` (PR #595)

### Changed defaults / behaviours

-   Added httpd configuration to enhance security by disabling version headers and trace (PR #578)
-   Since 3.10.15, all job wrapper scripts must be "POSIX" compatible to be able to run on small images with Busybox. Added a relaxation in 3.10.16, setting `set +o posix` when Bash is available (PR #587)

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Fixed incorrect glog_get_logfile_path_relative call in condor_startup.sh (PR #579)
-   Fixed Frontend reconfiguration failure when using "ALL" schedd (Issue #575, PR #580)
-   Fixed cvmfsexec failure when duplicate repositories are in the GLIDEIN_CVMFS_REPOS list (Issue #567, PR #585)
-   Fixed wrong exec command in wrapper script (Issue #584, PR #587)
-   Environment cleanup fixed. `PATH`, `LD_LIBRARY_PATH`, `PYTHONPATH`, and `LD_PRELOAD` are now correctly cleared when requested with `clearpaths` or `clearall` (Issue #592, PR #596)
-   Fixed maxWallTime not being set as a submit attribute by OSG_autoconf when an entry is whole node (PR #595)

### Testing / Development

### Known Issues

## v3.10.15 \[2025-07-18\]

Fixed v3.10.14 POSIX mode incompatibility error. Enhanced cvmfsexec mode 1 (mountrepo) to mount repos in
GLIDEIN_CVMFS_REPOS and to use Apptainer images from CVMFS.

### New features / functionalities

-   Added GLIDEIN_OVERLOAD_ENABLED to control partial CPU and memory overload (PR #536)
-   Added GLIDEIN_CVMFS_REPOS custom variable to define additional CVMFS repositories to mount (PR #547)
-   Added ramp_up_attenuation config parameter to control Glidein provisioning remap-up (PR #556)
-   Updates the pilot generation logic in OSG_autoconf to check the OSG_BatchSystem attribute from the OSG collector. If the batch system is set to "CONDOR", the resulting pilot entry will have work_dir set to "Condor" (PR #558)
-   Updates the pilot generation logic in OSG_autoconf to use the cpus attribute from the OSG collector to set GLIDEIN_ESTIMATED_CPUs (PR #560)

### Changed defaults / behaviours

-   The job wrappers in the Glidein are now running with the `/bin/sh` prompt instead of `/bin/bash`. They use Bash and `set +o posix` when possible, but there may be another shell.

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Retrieve and use CVMFS_MOUNT_DIR from glidein_config if not in the environment (PR #552)
-   Addressed POSIX mode problems and CVMFS path resolution (PR #555)

### Testing / Development

### Known Issues

-   Duplicate repositories in the GLIDEIN_CVMFS_REPOS list will fail cvmfsexec.

## v3.10.14 \[2025-06-20\]

Adds `precvmfs_file_list` priority to `*_file_list` priorities when using on-demand CVMFS setup.

### New features / functionalities

-   Added support for Ubuntu 24 workers (PR #529)
-   Add keyword ALL to query all schedulers known to the collector without listing them explicitly (Issue #510, PR #532)
-   Add keyword usertrace to the GLIDEIN_DEBUG_OPTIONS custom variable to enable shell tracing in user jobs and wrapper (PR #540)
-   Glideins can start containers with Busybox and no Bash, e.g. Alpine Linux. The Glidein itself still requires Bash (Issue #538, PR #540)

### Changed defaults / behaviours

-   Updated download/execution order of `cvmfs_setup.sh` during glidein startup using a new priority `precvmfs_file_list` (PR #528)

### Deprecated / removed options and commands

-   Removed compatibility with GWMS < 3.4.5

### Security Related Fixes

### Bug Fixes

-   Removed incorrect warning when setting SINGULARITY_BIN to keyword (PR #534)
-   Added `--skip-broken` to yumalldeps to avoid an error when incompatible packages are in the list (Issue #530, PR #534)
-   Added explicit retrieval from glidein_config of GLIDEIN_CONTAINER_ENV and GLIDEIN_CONTAINER_ENV_CLEARLIST in singularity_lib.sh (PR #535)
-   Fixed handling of Apptainer environment and image restrictions (PR #535, PR #539)
-   Added workaround for HTCondor setting PATH only as variable and not in the environment (PR #539)

### Testing / Development

-   Updated black and pre-commit actions to latest versions still supporting Python 3.6 (PR #534)

### Known Issues

## v3.10.13 \[2025-05-07\]

Quick release. Fixed a couple of bugs in 3.10.12

### New features / functionalities

### Changed defaults / behaviours

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Fixed a credential rewriting error caused by PR#511 and a path error in PR#515 (PR #519)

### Testing / Development

### Known Issues

## v3.10.12 \[2025-05-05\]

Added the ability to use a config directory for the Glidein's HTCondor. Clarified Glidein Job metrics.

### New features / functionalities

-   Exporting GLIDEIN_Name and GLIDEIN_UUID to the Glidein environment, for all scripts running inside the Glidein (PR #512)
-   HTCondor LOCAL_CONFIG_DIR support for the Glidein HTCondor daemons (PR #515)

### Changed defaults / behaviours

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Fixed misleading counts related to the number of jobs that run in the Glidein (Issue #456, PR #516)

### Testing / Development

-   Improved docstrings in the Factory module (PR #511)

### Known Issues

## v3.10.11 \[2025-03-24\]

stale_age allows to keep Glideins in queues for longer than one week.
Apptainer test now may be successful even if the default image is not available.
Check the changed defaults, including SINGULARITY_IMAGE_REQUIRED, APPTAINER_TEST_IMAGE and the redirection to https for monitoring pages.

### New features / functionalities

-   Added a test Apptainer image to use when the configured one is not available (PR #482)
-   Added a new configuration knob, stale_age, for Factory entries to control the age of the Glideins to be considered stale for certain statuses (PR #494)
-   Update get_tarballs to use new directory called beta (PR #495)
-   Support GPUs in the mapping of OSG_autoconf VOs (PR #496)
-   Made the Frontend library more friendly to other clients, e.g. Decision Engine (PR #504)

### Changed defaults / behaviours

-   The new variable SINGULARITY_IMAGE_REQUIRED defaults to false and allows to use Singularity/Apptainer also when the configured image is not available.
    The image must be provided by the job or a future custom script in order not to fail. (PR #482)
-   APPTAINER_TEST_IMAGE can be set to an always available Singularity/Apptainer image to use for testing.
    Defaults to oras://ghcr.io/apptainer/alpine:latest (PR #482)
-   Monitoring pages are now redirecting to https if available, i.e. mod_ssl is installed and mod_ssl.conf is present. This behavior was present in the past but had been lost, and now it has been reinstated. (PR #492, PR #502)
-   The default Frontend tokens key is now variable, $HOME/passwords.d/UPPERCASE_USERNAME. There is no actual change since this is /var/lib/gwms-frontend/passwords.d/FRONTEND for normal RPM installations. (PR #504)

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Protect processing of custom scripts in glidein_startup.sh against stdin interference (PR #498, Issue #500)
-   Some config files used in the RPM package, including the httpd ones, were obsolete and not the version in the source tree. (PR #492, PR #502)
-   Host IP is now searched in blacklist also when the host command is missing (PR #499, Issue #493)
-   Added missing HTCondor requirements in spec file (PR #502)
-   Unset CONDOR_INHERIT before condor startup to avoid any conflict in the condor configurations (PR #503, Issue #274)

### Testing / Development

-   Added new debug and timeout options to the release building scripts (PR #506)

### Known Issues

## v3.10.10 \[2025-01-24\]

Minor Factory operation features and bug fixes.

### New features / functionalities

-   Improved gfdiff tool interface and changed diff algorithm (PR #476)
-   Added option to check if new HTCondor tarballs are available to get_tarballs (PR #477)

### Changed defaults / behaviours

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Fixed gfdiff issue with mergely interface (PR #476)
-   Fallback to cp/chown when cp -p does not work (It is unavailable on some containers) (PR #478)

### Testing / Development

### Known Issues

## v3.10.9 \[2025-01-16\]

Added support for the HTCondor distributed apptainer.
Fixed the Glidein logging and added a sample log server.
Fixed a few more bugs including allowing anonymous SSL authentication in the Frontend client config.

### New features / functionalities

-   Added custom JWT-authenticated log server example (new RPM glideinwms-logging) (Issue #398, PR #467)
-   Now using also Apptainer included in the HTCondor tar ball (Issue #364, PR #473)

### Changed defaults / behaviours

-   Always send SIGQUIT to HTCondor when the Glidein receives INT, TERM, QUIT signals. This speeds up the shutdown (PR #466)
-   Renamed Glidein Logging functions to glog\_...: glog_init, glog_setup, glog_write, glog_send (PR #467)
-   Apptainer downloaded in the HTCondor tar ball is now considered after the PATH in the search for a valid binary.
    The keyword CONDOR in the parameter SINGULARITY_BIN will make so that the HTCondor Apptainer is preferred
    ahead of the rest (PR #473)
-   Added RHEL9 to the list of default OSes used for the container images lookup. Now it is: default,rhel9,rhel7,rhel6,rhel8 (PR #473)

### Deprecated / removed options and commands

-   The original Glidein Logging functions (log_init_tokens, log_init, log_setup, log_write, send_logs_to_remote, ...) are no more available

### Security Related Fixes

### Bug Fixes

-   Fixed early truncation in log files configuration and inconsistent documentation (Issue #464, PR #462, PR #463)
-   Removed confusing tac broken pipe messages from the Glidein stderr (PR #465)
-   Fixed JWT logging credentials not transferred to the Glidein. This includes removal of DictFile.append() and use of add_environment() for JWT tokens (Issue #398, PR #467)
-   Fixed quotes in Glidein command line unpacking and replaced deprecated add_config_line commands (PR #468)
-   Allow anonymous SSL authentication for the dynamically generated client config in the Frontend (Issue #222, PR #470)
-   Checking also the apptainer binary in the SINGULARITY_BIN path, not only singularity (PR #473)

### Testing / Development

-   Improved the docstrings and some code in the lib files and few others with the help of AI (PR #471, PR #472)
-   Added --skip-rpm option in release.py to skip RPM building (PR #474)

### Known Issues

## v3.10.8 \[2024-11-21\]

Fixed a few bugs including shebang mangling and failed log files rotation.

### New features / functionalities

-   Advertising information about unprivileged user namespaces in Glidein classad (PR #416)
-   Added option --group-name option to manual_glidein_submit (PR #435)

### Changed defaults / behaviours

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Fixed root unable to remove other users' jobs in the Factory (PR #433)
-   HTCondor TRUST_DOMAIN configuration macro set to string to avoid Glidein config error (PR #420)
-   Disabled shebang mangling in rpm_build to avoid gwms-python not finding the shell (Issue #436, PR #437)
-   Dynamic creation of HTCondor IDTOKEN password (Issue #440, PR #441)
-   Autodetect CONDOR_OS in the manual_glidein_submit tool (Issue #449, PR #453)
-   Failed log rotation due to wrong file creation time (Issue #451, PR #457)

### Testing / Development

-   Replacing xmlrunner with unittest-xml-reporting (PR #428)
-   Updated the release upload script to work with osg-sw-submit (PR #439)

### Known Issues

## v3.10.7 \[2024-06-21\]

Added black hole detection and ability to set jobs minimum memory for resource provisioning.

### New features / functionalities

-   Apptainer cache and temporary directory set in the Glidein working directory (Issue #403, PR #404)
-   Ability to set a minimum required memory for partitionable Glideins. The default is the value used previously, 2500 MB (Issue #405, PR #406)
-   Blackhole Detection: stop accepting jobs if they are consumed at a rate higher than the configured limit and declare the Glidein a blackhole (Issue #331, PR #399)

### Changed defaults / behaviours

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Fixed Apptainer validation not considering uid_map w/o initial blank (Issue #395, PR #396)
-   Flattening error message in \_CONDOR_WRAPPER_ERROR_FILE and JobWrapperFailure Ad. This is a workaround for a bug in HTCondor (PR #400)
-   Fixed problem when check_signature in glidein_startup is not defined (PR #402)
-   get_tarballs look for HTCondor releases also in the update directory (Issue #412, PR #413)

### Testing / Development

-   Added Ruff to the linters in pre-commit and fixed all the flagged errors (PR #407)
-   Switched GitHub actions from SL7 to AlmaLinux9 and OSG23 (PR #408)

### Known Issues

-   We needed to revert PR #401, "Hardening of HTCondor configuration. Restricted authentication to exclude unauthenticated beside anonymous (PR #401)" because it broke authentication for normal functionalities

## v3.10.6 \[2024-01-25\]

Minor new features, mostly a bug fix release

### New features / functionalities

-   Add knobs to allow overloading of memory, GLIDEIN_OVERLOAD_MEMORY, and CPU, GLIDEIN_OVERLOAD_CPUS. (Issue #370, PR #374)
-   Added HTCondor tarball downloader (Issue #367, PR #366)
-   Added default (/bin,/usr/bin) when PATH is empty in glidein_startup.sh (PR #373)
-   Advertising Factory's HTCondor submit parameters (Issue #307, PR #382)

### Changed defaults / behaviours

-   The submit attributes (submit/submit_attrs) are now published in the glidefactory classad with the GlideinSubmit prefix followed by the attribute name and same value. If the attribute name starts with "+" this will be replaced by "\_PLUS\_", since only alphanumeric characters and "\_" are valid in ClassAd attribute names.

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Changed M2Crypto imports to be compatible with 0.40.0 the code must import also the components (PR #377)
-   Fixed PATHs handling in glidein_startup.sh (PR #379)
-   Fixed match policy_file import failure (Issue #378, PR #380)
-   Fixed syntax error in ClassAd used for gangliad configuration (Issue #368, PR #385)
-   Added extra logging to investigate file rotation problem (Issue #362, PR #389)
-   Fixed writing of missing dict files during upgrade (Issue #388, PR #391)

### Testing / Development

-   Python>=3.8 should be used as development environment, earlier versions are not supported by pre-commit. Code should still support any Python>=3.6.

### Known Issues

## v3.10.5 \[2023-9-27\]

Bug fix quick release

### New features / functionalities

### Changed defaults / behaviours

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Workaround for EL7 PyJWT bug, generating bytes instead of str (PR #355)
-   Fixed missing `cvmfsexec.cfg` files from Factory reconfig and improved cvmfsexec warnings (Issue #348, PR #356)
-   Added bash requirement to files using bashisms, notably `glidein_sitewms_setup.sh` (PR #358)
-   Fixed syntax errors in analyze_queues (PR #357)
-   Fixed setup_x509 to be successful w/ TRUST_DOMAIN set in the as Factory or Frontend parameter (PR #359)
-   GLIDEIN_SINGULARITY_BINARY_OVERRIDE set also with Frontend and Factory params, not only WN environment (PR #360)

### Testing / Development

### Known Issues

## v3.10.4 \[2023-9-14\]

Bug fix quick release

### New features / functionalities

### Changed defaults / behaviours

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Fixed missing arguments from rrdtool fetch call (Issue #351, PR #352)
-   gconfig.py to use `gwms-python`, not use `python3` (Issue #349, PR #350)
-   Fixed alternative Shell code still using the `python` (i.e. python2) interpreter (Issue #289, PR #353)

### Testing / Development

### Known Issues

## v3.10.3 \[2023-9-11\]

This release provides full functionality in EL9 and Python 3.9. Changes since v3.10.2

### New features / functionalities

-   Added support for Debian 11 and Ubuntu 22 worker nodes (PR #320)
-   Added structured logging. It is a hybrid format with some fields followed by a JSON dictionary. The exact format of the messages may change in the future, and we plan for it to become the default. Now it is disabled by default. Add `structured="True"` to all `<process_log>` elements (PR #333)
-   Add option to set xml output directory in OSG_autoconf (PR #319)
-   Allow OSG_autoconf to skip sites or CEs that are not present in the OSG collector (PR #315)
-   Add option to set num_factories in OSG_autoconf (Issue #344, PR #345)
-   Added the ability to clear a list of variables from the environment via GLIDEIN_CONTAINER_ENV_CLEARLIST before starting a container (Issue #341, PR #342)

### Changed defaults / behaviours

-   Added `cvmfsexec_distro` tag to be included in the factory configuration out-of-the-box (fresh installation) as well as through an upgrade; its behavior (on-demand cvmfsexec in disabled mode) remains unchanged (PR #312)

### Deprecated / removed options and commands

### Security Related Fixes

-   manual_glidein_submit now correctly sets idtokens in the EncryptedInputFiles (issue #283, PR #284)

### Bug Fixes

-   Removed `classad` from requirements.txt. The HTCSS team distributes only the `htcondor` library in PyPI which includes a different version of classad (PR #301)
-   Fixing Python 3.9 deprecations (`imp`, `getchildren()` in `xml.etree.ElementTree`) (PR #302, PR #303)
-   Populate missing Entry parameters for ARC CEs submissions (PR #304)
-   Modified the usage of subprocess module, for building/rebuilding cvmfsexec distributions, only when necessary (PR #309)
-   Fixed fetch_rrd crash in EL9 causing missing monitoring and glidefactoryclient classad information (Issue #338, PR #339)

### Testing / Development

### Known Issues

-   When generating cvmfsexec distribution for EL9 machine type on an EL7 machine, the factory reconfig and/or upgrade fails as a result of an error in `create_cvmfsexec_distros.sh`. This is possibly due to the tools for EL7 being unable to handle EL9 files (as per Dave Dykstra). Please exercise caution if using `rhel9-x86_64` in the `mtypes` list for the `cvmfsexec_distro` tag in factory configuration.
    -   Our workaround is to remove the EL9 machine type from the default list of machine types supported by the custom distros creation script. Add it back if you are running on an EL9 system and want an EL9 cvmfsexec distribution. (PR #312)

## v3.10.2 \[2023-5-10\]

### New features / functionalities

-   Add a parameter to control the name of the keyname for idtokens (PR #268)
-   Added a factory knob to allow control over rebuilding of cvmfsexec distributions (PR #272)
-   RHEL9 worker node are now recognized by condor_platform_select automatic OS detection (PR #285)

### Changed defaults / behaviours

-   Removed pre-reconfigure hook used for rebuilding cvmfsexec distributions whenever a factory reconfig/upgrade was run (Issue #262).
    -   Rebuilding of cvmfsexec distributions is disabled by default, unless enabled via the new factory knob.

### Deprecated / removed options and commands

### Security Related Fixes

### Bug Fixes

-   Use correct variable for `$exit_code` in `singularity_exec_simple` (PR #259)
-   Make sure default value does not overwrite the global one for idtoken_lifetime (PR #261)
-   Protect OSG_autoconf from OSG collector unavailability (PR #276)
-   Fixed jobs going in unknown state in factory monitoring. added QUEUING state for new ARC-CEs REST (PR #286)

### Testing / Development

### Known Issues

-   When using on-demand CVMFS, all Glideins after the first one on a node are failing (Issue #287)
    This happens because mountrepo and umountrepo work at the node level and subsequent Glideins see the mounts done by the first one and abort.
    To avoid problems use only whole-node Glideins when using on-demand CVMFS.
    All versions with on-demand CVMFS are affected.

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
