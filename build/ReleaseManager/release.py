#!/usr/bin/env python3
# It used to be python3 -B, but that is interpreted as single string as opposed to a list of arguments.

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import sys
import os
import argparse
from argparse import RawDescriptionHelpFormatter

# Necessary to allow relative import when started as executable
if __name__ == "__main__" and __package__ is None:
    # append the parent directory to the path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "ReleaseManager"
    # This was suggested on line but seems not needed
    # mod = __import__("ReleaseManager")
    # sys.modules["ReleaseManager"] = mod

try:
    from . import ReleaseManagerLib
except (SystemError, ImportError):
    # Try also absolute import. Should not be needed
    import ReleaseManagerLib


def manager_version():
    try:
        if os.path.exists("/var/lib/gwms-factory/work-dir/checksum.factory"):
            chksum_file = "checksum.factory"
        elif os.path.exists("/var/lib/gwms-frontend/vofrontend/checksum.frontend"):
            chksum_file = "checksum.frontend"
        else:
            return "UNKNOWN"
        from glideinwms.lib import glideinWMSVersion
    except ImportError:
        return "UNKNOWN"
    try:
        return glideinWMSVersion.GlideinWMSDistro(chksum_file).version()
    except RuntimeError:
        return "UNKNOWN"


def usage():
    help_str = [
        "%s <version> <SourceDir> <ReleaseDir>" % os.path.basename(sys.argv[0]),
        "NOTE that this script works on the files in your current directory tree",
        "- no git operations like clone/checkout are performed",
        "- files you changed are kept so",
        "- if using big files you should run 'bigfiles.sh -pr' before invoking this script",
        "  and 'bigfiles -R' after, to ripristinate the symlinks before a commit"
        "Example: Release Candidate rc3 for v3.2.11 (ie version v3_2_11_rc3)",
        "         Generate tarball: glideinWMS_v3_2_11_rc3*.tgz",
        "         Generate rpms   : glideinWMS-*-v3.2.11-0.3.rc3.*.rpm",
        "release.py --release-version=3_2_11 --rc=3 --source-dir=/home/parag/glideinwms --release-dir=/var/tmp/release",
        "Example: Development post Release Candidate rc3 for v3.2.11 (ie version v3_2_11_rc3)",
        "         Generate tarball: glideinWMS_v3_2_11_rc3*.tgz (same as regular v3_2_11 RC3)",
        "         Generate rpms   : glideinWMS-*-v3.2.11-0.3.rc3.2.*.rpm (should be between RC3 and RC4)",
        "release.py --release-version=3_2_11 --rc=3 --source-dir=/home/parag/glideinwms --release-dir=/var/tmp/release --rpm-release=2",
        "",
        "Example: Final Release v3.2.11",
        "         Generate tarball: glideinWMS_v3_2_11*.tgz",
        "         Generate rpms   : glideinwms-*-v3.2.11-3.*.rpm",
        "release.py --release-version=3_2_11 --source-dir=/home/parag/glideinwms --release-dir=/var/tmp/release --rpm-release=3",
        "",
    ]
    return "\n".join(help_str)


def parse_opts(argv):
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        description=usage(),
        conflict_handler="resolve",
        formatter_class=RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--release-version",
        action="store",
        required=True,
        metavar="<release version>",
        help="GlideinWMS version to release (format w/ underscores, for tarball, RPM version derived from it)",
    )
    parser.add_argument(
        "--source-dir",
        action="store",
        required=True,
        metavar="<source directory>",
        help="directory containing the GlideinWMS source code",
    )
    parser.add_argument(
        "--release-dir",
        default="/tmp/release",
        action="store",
        metavar="<release directory>",
        help="directory to store release tarballs and webpages",
    )
    parser.add_argument(
        "--rc", default=None, action="store", metavar="<Release Candidate Number>", help="Release Candidate"
    )
    parser.add_argument(
        "--rpm-release",
        default=None,
        action="store",
        metavar="<RPM Release Number>",
        help="RPM Release Number",
    )
    parser.add_argument(
        "--skip-rpm",
        dest="skip_rpm",
        action="store_true",
        help="Skip the RPM building step even if all tools are available",
    )
    parser.add_argument(
        "--no-mock", dest="use_mock", action="store_false", help="Set to use rpmbuild instead of mock to build the RPM"
    )
    parser.add_argument(
        "--python-version",
        default="python36",
        action="store",
        metavar="<Python version>",
        help="Python version (default: python36)",
    )
    parser.add_argument("--verbose", action="store_true", help="Set to see more details of the release building")
    parser.add_argument("-v", "--version", action="version", version=manager_version())

    options = parser.parse_args()
    return options


def main(argv):
    options = parse_opts(argv)
    # sys.exit(1)
    ver = options.release_version
    src_dir = options.source_dir
    rel_dir = options.release_dir
    rc = options.rc
    rpm_rel = options.rpm_release
    python_version = options.python_version
    skip_rpm = options.skip_rpm
    use_mock = options.use_mock
    is_verbose = options.verbose

    print("___________________________________________________________________")
    print("Creating following GlideinWMS release")
    print(
        "Version=%s\nSourceDir=%s\nReleaseDir=%s\nReleaseCandidate=%s\nRPMRelease=%s\nPython=%s"
        % (ver, src_dir, rel_dir, rc, rpm_rel, python_version)
    )
    print("___________________________________________________________________")
    print()
    rel = ReleaseManagerLib.Release(ver, src_dir, rel_dir, rc, rpm_rel, skip_rpm)

    rel.addTask(ReleaseManagerLib.TaskClean(rel))
    rel.addTask(ReleaseManagerLib.TaskSetupReleaseDir(rel))
    rel.addTask(ReleaseManagerLib.TaskVersionFile(rel))
    rel.addTask(ReleaseManagerLib.TaskTar(rel))
    rel.addTask(ReleaseManagerLib.TaskDocumentation(rel))
    rel.addTask(ReleaseManagerLib.TaskRPM(rel, python_version, use_mock, is_verbose))

    rel.executeTasks()
    rel.printReport()


if __name__ == "__main__":
    main(sys.argv)
