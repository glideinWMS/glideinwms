#!/usr/bin/env python3
# It used to be python3 -B, but that is interpreted as single string as opposed to a list of arguments.

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import sys
import os
import optparse

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
except (SystemError, ImportError) as e:
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
    help = [
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
    return "\n".join(help)


def parse_opts(argv):
    parser = optparse.OptionParser(usage=usage(), version=manager_version(), conflict_handler="resolve")
    parser.add_option(
        "--release-version",
        dest="relVersion",
        action="store",
        metavar="<release version>",
        help="GlideinWMS version to release (format w/ underscores, for tarball, RPM version derived from it)",
    )
    parser.add_option(
        "--source-dir",
        dest="srcDir",
        action="store",
        metavar="<source directory>",
        help="directory containing the glideinwms source code",
    )
    parser.add_option(
        "--release-dir",
        dest="relDir",
        default="/tmp/release",
        action="store",
        metavar="<release directory>",
        help="directory to store release tarballs and webpages",
    )
    parser.add_option(
        "--rc", dest="rc", default=None, action="store", metavar="<Release Candidate Number>", help="Release Candidate"
    )
    parser.add_option(
        "--rpm-release",
        dest="rpmRel",
        default=None,
        action="store",
        metavar="<RPM Release Number>",
        help="RPM Release Number",
    )
    parser.add_option(
        "--no-mock", dest="use_mock", action="store_false", help="Set to use rpmbuild instead of mock to build the RPM"
    )
    parser.add_option(
        "--python-version",
        dest="python_version",
        default="python36",
        action="store",
        metavar="<Python version>",
        help="Python version (default: python36)",
    )

    if len(argv) == 2 and argv[1] in ["-v", "--version"]:
        parser.print_version()
        sys.exit()
    if len(argv) < 4:
        print("ERROR: Insufficient arguments specified")
        parser.print_help()
        sys.exit(1)
    options, remainder = parser.parse_args(argv)
    if len(remainder) > 1:
        parser.print_help()
    if not required_args_present(options):
        print("ERROR: Missing required arguments")
        parser.print_help()
        sys.exit(1)
    return options


def required_args_present(options):
    try:
        if (options.relVersion is None) or (options.srcDir is None) or (options.relDir is None):
            return False
    except AttributeError:
        return False
    return True


#   check_required_args


# def main(ver, srcDir, relDir):
def main(argv):
    options = parse_opts(argv)
    # sys.exit(1)
    ver = options.relVersion
    srcDir = options.srcDir
    relDir = options.relDir
    rc = options.rc
    rpmRel = options.rpmRel
    python_version = options.python_version
    use_mock = options.use_mock

    print("___________________________________________________________________")
    print("Creating following GlideinWMS release")
    print(
        "Version=%s\nSourceDir=%s\nReleaseDir=%s\nReleaseCandidate=%s\nRPMRelease=%s\nPython=%s"
        % (ver, srcDir, relDir, rc, rpmRel, python_version)
    )
    print("___________________________________________________________________")
    print()
    rel = ReleaseManagerLib.Release(ver, srcDir, relDir, rc, rpmRel)

    rel.addTask(ReleaseManagerLib.TaskClean(rel))
    rel.addTask(ReleaseManagerLib.TaskSetupReleaseDir(rel))
    rel.addTask(ReleaseManagerLib.TaskVersionFile(rel))
    rel.addTask(ReleaseManagerLib.TaskTar(rel))
    rel.addTask(ReleaseManagerLib.TaskRPM(rel, python_version, use_mock))

    rel.executeTasks()
    rel.printReport()


if __name__ == "__main__":
    main(sys.argv)
