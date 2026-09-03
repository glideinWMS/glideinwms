#!/usr/bin/env bats

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

[[ -z "$GWMS_SOURCEDIR" ]] && GWMS_SOURCEDIR=../..

setup() {
    source compat.bash
    glidein_config=fixtures/glidein_config
    source "$GWMS_SOURCEDIR"/creation/web_base/add_config_line.source
    source "$GWMS_SOURCEDIR"/creation/web_base/cvmfs_helper_funcs_ff.sh $glidein_config 2>&3 || true

    [[ -z "$CVMFS_ROOT" ]] && CVMFS_ROOT=fixtures/cvmfs
}

# unit tests for determine_cvmfsexec_mode_usage function
@test "Test cvmfsexec mode usage when unpriv. user namespaces is enabled" {
    # mocking the below two functions to ensure that
    # the test case uses what is defined above
    has_unpriv_userns() { echo "enabled"; }
    has_fuse() { echo "yes"; }

    run determine_cvmfsexec_mode_usage
    [[ $output == "3" ]] || false
    [ $status -eq 0 ]

    has_fuse() { echo "no"; }
    run determine_cvmfsexec_mode_usage
    [[ $output == "3" ]] || false
    [ $status -eq 0 ]

    has_fuse() { echo "error"; }
    run determine_cvmfsexec_mode_usage
    [[ $output == "3" ]] || false
    [ $status -eq 0 ]
}

@test "Test cvmfsexec mode usage when unpriv. user namespaces is disabled" {
    # mocking the below two functions to ensure that
    # the test case uses what is defined above
    has_unpriv_userns() { echo "disabled"; }
    has_fuse() { echo "yes"; }
    run determine_cvmfsexec_mode_usage
    [[ $output == "1" ]] || false
    [ $status -eq 0 ]

    has_fuse() { echo "no"; }
    run determine_cvmfsexec_mode_usage
    [[ ${lines[1]} == "0" ]] || false
    [ $status -eq 1 ]

    has_fuse() { echo "error"; }
    run determine_cvmfsexec_mode_usage
    [[ ${lines[1]} == "0" ]] || false
    [ $status -eq 1 ]
}

@test "Test cvmfsexec mode usage when unpriv. user namespaces is unavailable" {
    # mocking the below two functions to ensure that
    # the test case uses what is defined above
    has_unpriv_userns() { echo "unavailable"; }
    has_fuse() { echo "yes"; }
    run determine_cvmfsexec_mode_usage
    [[ $output == "1" ]] || false
    [ $status -eq 0 ]

    has_fuse() { echo "no"; }
    run determine_cvmfsexec_mode_usage
    [[ ${lines[1]} == "0" ]] || false
    [ $status -eq 1 ]

    has_fuse() { echo "error"; }
    run determine_cvmfsexec_mode_usage
    [[ ${lines[1]} == "0" ]] || false
    [ $status -eq 1 ]
}

@test "Test cvmfsexec mode usage when unpriv. user namespaces is error" {
    # mocking the below two functions to ensure that
    # the test case uses what is defined above
    has_unpriv_userns() { echo "error"; }
    has_fuse() { echo "yes"; }
    run determine_cvmfsexec_mode_usage
    [[ $output == "1" ]] || false
    [ $status -eq 0 ]

    has_fuse() { echo "no"; }
    run determine_cvmfsexec_mode_usage
    [[ ${lines[1]} == "0" ]] || false
    [ $status -eq 1 ]

    has_fuse() { echo "error"; }
    run determine_cvmfsexec_mode_usage
    [[ ${lines[1]} == "0" ]] || false
    [ $status -eq 1 ]
}

# unit tests for has_unpriv_userns function
@test "Test unprivileged user namespaces status 1" {
    # when unpriv. user namespaces is not supported but enabled (weird state)
    perform_system_check() { GWMS_IS_UNPRIV_USERNS_ENABLED=0; GWMS_IS_UNPRIV_USERNS_SUPPORTED=1; }
    run has_unpriv_userns
    [[ ${lines[1]} == "error" ]] || false
    [ $status -eq 1 ]
}

@test "Test unprivileged user namespaces status 2" {
    # when unpriv. user namespaces is supported and enabled
    perform_system_check() { GWMS_IS_UNPRIV_USERNS_ENABLED=0; GWMS_IS_UNPRIV_USERNS_SUPPORTED=0; }
    run has_unpriv_userns
    [[ ${lines[1]} == "enabled" ]] || false
    [ $status -eq 0 ]
}

@test "Test unprivileged user namespaces status 3" {
    # when unpriv. user namespaces is not supported and disabled
    perform_system_check() { GWMS_IS_UNPRIV_USERNS_ENABLED=1; GWMS_IS_UNPRIV_USERNS_SUPPORTED=1; }
    run has_unpriv_userns
    [[ ${lines[1]} == "unavailable" ]] || false
    [ $status -eq 1 ]
}

@test "Test unprivileged user namespaces status 4" {
    # when unpriv. user namespaces is supported but disabled
    perform_system_check() { GWMS_IS_UNPRIV_USERNS_ENABLED=1; GWMS_IS_UNPRIV_USERNS_SUPPORTED=0; }
    run has_unpriv_userns
    [[ ${lines[1]} == "disabled" ]] || false
    [ $status -eq 1 ]
}

# unit tests for has_fuse function
@test "Test fuse configuration status 1" {
    perform_system_check() { GWMS_IS_FUSE_INSTALLED=127; GWMS_IS_FUSERMOUNT=0; }
    run has_fuse
    [[ ${lines[1]} == "error" ]] || false
    [ $status -eq 1 ]
}

@test "Test fuse configuration status 2" {
    perform_system_check() { GWMS_IS_FUSE_INSTALLED=1; GWMS_IS_FUSERMOUNT=1; }
    run has_fuse
    [[ ${lines[1]} == "no" ]] || false
    [ $status -eq 1 ]
}

@test "Test fuse configuration status 3" {
    has_unpriv_userns() { echo "enabled"; }
    perform_system_check() { GWMS_IS_FUSE_INSTALLED=0; GWMS_IS_FUSERMOUNT=0; }
    run has_fuse
    [[ ${lines[1]} == "yes" ]] || false
    [ $status -eq 0 ]
}

@test "Test fuse configuration status 4" {
    has_unpriv_userns() { echo "enabled"; }
    perform_system_check() { GWMS_IS_FUSE_INSTALLED=0; GWMS_IS_FUSERMOUNT=1; }
    run has_fuse
    [[ ${lines[1]} == "error" ]] || false
    [ $status -eq 1 ]
}

# unit tests for setup_cvmfsexec_use function
@test "Test cvmfsexec use setup 1" {
    determine_cvmfsexec_mode_usage() { echo 0; }
    run setup_cvmfsexec_use
    [[ ${lines[-1]} == "0" ]] || false
}

@test "Test cvmfsexec use setup 2" {
    determine_cvmfsexec_mode_usage() { echo 1; }
    run setup_cvmfsexec_use
    [[ ${lines[-1]} == "1" ]] || false
}

@test "Test cvmfsexec use setup 3" {
    determine_cvmfsexec_mode_usage() { echo 2; }
    run setup_cvmfsexec_use
    [[ ${lines[-1]} == "2" ]] || false
}

@test "Test cvmfsexec use setup 4" {
    determine_cvmfsexec_mode_usage() { echo 3; }
    run setup_cvmfsexec_use
    [[ ${lines[-1]} == "3" ]] || false
}

# unit test for prepare_for_cvmfs_mount function
@test "Test preparation for CVMFS mount" {
    run prepare_for_cvmfs_mount
    [ $status -eq 1 ]

    mkdir -p fixtures/cvmfsexec
    perform_system_check() { GWMS_OS_DISTRO=os; GWMS_OS_VERSION_MAJOR=ver; GWMS_OS_KRNL_ARCH=arch; }
    run prepare_for_cvmfs_mount
    [ $status -eq 1 ]

    touch fixtures/cvmfsexec/cvmfsexec-default-osver-arch
    perform_system_check() { GWMS_OS_DISTRO=os; GWMS_OS_VERSION_MAJOR=ver; GWMS_OS_KRNL_ARCH=arch; }
    run prepare_for_cvmfs_mount
    [ $status -eq 0 ]
    rm -f fixtures/cvmfsexec/cvmfsexec-default-osver-arch
    rmdir fixtures/cvmfsexec
}

# unit tests for perform_cvmfs_mount function
@test "Test perform CVMFS mount 1" {
    perform_system_check() { GWMS_OS_DISTRO=debian; }
    run perform_cvmfs_mount
    [ $status -eq 2 ]

    perform_system_check() { GWMS_OS_DISTRO=ubuntu; }
    run perform_cvmfs_mount
    [ $status -eq 2 ]

    perform_system_check() { GWMS_OS_DISTRO=fedora; }
    run perform_cvmfs_mount
    [ $status -eq 2 ]
}

@test "Test perform CVMFS mount 2" {
    mkdir -p fixtures/cvmfsexec
    touch fixtures/cvmfsexec/cvmfsexec-default-rhelver-arch
    perform_system_check() { GWMS_OS_DISTRO=rhel; GWMS_OS_VERSION_MAJOR=ver; GWMS_OS_KRNL_ARCH=arch; }
    run perform_cvmfs_mount 3
    [ $status -eq 0 ]

    run perform_cvmfs_mount 2
    [ $status -eq 0 ]

    # if something goes wrong during mounting of CVMFS repos...
    mount_cvmfs_repos() { return 1; }
    run perform_cvmfs_mount 1
    [ $status -eq 1 ]

    # if mounting of CVMFS repos is a success...
    mount_cvmfs_repos() { return 0; }
    run perform_cvmfs_mount 1
    [ $status -eq 0 ]

    rm -f fixtures/cvmfsexec/cvmfsexec-default-rhelver-arch
    rmdir fixtures/cvmfsexec
}

# unit test for variables_reset function
@test "Test reset of variables" {
    variables_reset
    [ -z "$GWMS_SYSTEM_CHECK" ]
    [ -z "$GWMS_OS_DISTRO" ]
    [ -z "$GWMS_OS_NAME" ]
    [ -z "$GWMS_OS_VERSION_FULL" ]
    [ -z "$GWMS_IS_CVMFS_LOCAL_MNT" ]
    [ -z "$GWMS_IS_UNPRIV_USERNS_SUPPORTED" ]
    [ -z "$GWMS_IS_FUSE_INSTALLED" ]
}

# unit test for loginfo, logwarn and logerror functions
@test "Test logging messages" {
    run loginfo "Testing info level logging..."
    [[ "$output" =~ "INFO: Testing info level logging..." ]]

    run logwarn "Testing warn level logging..."
    [[ "$output" =~ "WARNING: Testing warn level logging..." ]]

    run logerror "Testing error level logging..."
    [[ "$output" =~ "ERROR: Testing error level logging..." ]]
}

# unit test for print_exit_status function
@test "Test printing of exit status" {
    run print_exit_status 0
    [[ "$output" == "yes" ]]

    run print_exit_status 1
    [[ "$output" == "no" ]]

    run print_exit_status 127
    [[ "$output" == "no" ]]
}

# unit test for print_os_info function
@test "Test printing of operating system information" {
    perform_system_check() {
       GWMS_OS_NAME="testOS"; GWMS_OS_DISTRO="testDistro"; GWMS_OS_VERSION_FULL="testVersion"; GWMS_OS_KRNL_ARCH="testKArch"; GWMS_OS_KRNL_NUM="testKNum"; GWMS_OS_KRNL_PATCH_NUM="testKPatch";
    }
    run print_os_info
    [[ "$output" =~ "Found testOS [testDistro] testVersion" ]]
    [[ "$output" =~ "testVersion-testKArch with kernel testKNum-testKPatch" ]]
}

# unit test for log_all_system_info function
@test "Test printing of all the system information" {
    perform_system_check() {
       GWMS_OS_NAME="testOS"; GWMS_OS_DISTRO="testDistro"; GWMS_OS_VERSION_FULL="testVersion";

       GWMS_OS_KRNL_VER="testKVer"; GWMS_OS_KRNL_MAJOR_REV="testKMajorRev"; GWMS_OS_KRNL_MINOR_REV="testKMinorRev"; GWMS_OS_KRNL_ARCH="testKArch"; GWMS_OS_KRNL_NUM="testKNum"; GWMS_OS_KRNL_PATCH_NUM="testKPatch";

       GWMS_IS_UNPRIV_USERNS_SUPPORTED=1; GWMS_IS_UNPRIV_USERNS_ENABLED=1; GWMS_IS_FUSE_INSTALLED=0; GWMS_IS_FUSERMOUNT=0; GWMS_IS_USR_IN_FUSE_GRP=1; GWMS_SYSTEM_CHECK=yes
    }

    run log_all_system_info
    [[ ${#lines[@]} -eq 19 ]] # checking for total number of lines in the output
    [[ ${lines[2]} =~ "INFO: Worker node details" ]]
    [[ ${lines[5]} =~ "INFO: Operating system name: testOS" ]]
    [[ ${lines[8]} =~ "INFO: Kernel version: testKVer" ]]
    [[ ${lines[13]} =~ "INFO: Unprivileged user namespaces supported: no" ]]
    [[ ${lines[14]} =~ "INFO: Unprivileged user namespaces enabled: no" ]]
    [[ ${lines[15]} =~ "INFO: FUSE installed: yes" ]]
    [[ ${lines[16]} =~ "INFO: fusermount available: yes" ]]
}

@test "Test to determine native CVMFS availability" {
    run detect_local_cvmfs
    [[ ${lines[-1]} =~ "INFO: Worker node has native CVMFS: no" ]]
}

@test "Test to determine mount point when CVMFS is mounted on demand" {
    # defining stub function for findmnt
    findmnt() {
        findmnt_output=$(cat $CVMFS_ROOT/findmnt_out.txt)
        echo "$findmnt_output"
        return 0
    }
    # export the function to override the actual `findmnt` command
    export -f findmnt

    run get_mount_point

    # unset the function as test is completed at this point
    unset -f findmnt
}

@test "Test for a pre-requisite full system check for on-demand CVMFS" {
    # defining a few stubs of utilities used in perform_system_check function
    arch() { echo "testKArch"; }
    uname() {
        echo "testKVer.8.testKMinorRev-testKPatch"; # following the EL9 convention
    }
    unshare() { return 127; }
    dnf() { return 1; }
    fusermount3() { return 0; }
    getent() { return 0; }
    cat() { echo "6480"; return 0; }

    # export the function to override the actual `arch`, `uname` system commands
    export -f arch
    export -f uname
    export -f unshare
    export -f dnf
    export -f fusermount3
    export -f getent
    export -f cat

    run perform_system_check
    run log_all_system_info

    # unset the exported functions from above as test is completed at this point
    unset -f arch
    unset -f uname
    unset -f unshare
    unset -f dnf
    unset -f fusermount3
    unset -f getent
    unset -f cat
}

# TODO: write unit test(s) for mount_cvmfs_repos function; needs further discussion
