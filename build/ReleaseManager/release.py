#!/usr/bin/python -B

from __future__ import absolute_import
from __future__ import print_function
import sys
import os
# not used - import getopt
import optparse

from . import ReleaseManagerLib


def manager_version():
    try:
        from glideinwms.lib import glideinWMSVersion
    except ImportError:
        return "UNKNOWN"
    try:
        if os.path.exists("../etc/checksum.factory"):
            glidein_dir = "../etc"
            chksum_file = "checksum.factory"
        elif os.path.exists("/var/lib/gwms-factory/work-dir/checksum.factory"):
            glidein_dir = "/var/lib/gwms-factory/work-dir"
            chksum_file = "checksum.factory"
        elif os.path.exists("/var/lib/gwms-frontend/vofrontend/checksum.frontend"):
            glidein_dir = "/var/lib/gwms-frontend/vofrontend"
            chksum_file = "checksum.frontend"
        else:
            return "UNKNOWN"
        return glideinWMSVersion.GlideinWMSDistro(glidein_dir,
                                                  chksum_file).version()
    except RuntimeError:
        return "UNKNOWN"


def usage():

    help = ["%s <version> <SourceDir> <ReleaseDir>" % os.path.basename(sys.argv[0]),
            "Example: Release Candidate rc3 for v3.2.11 (ie version v3_2_11_rc3)",
            "         Generate tarball: glideinWMS_v3_2_11_rc3*.tgz",
            "         Generate rpms   : glideinWMS-*-v3.2.11-0.4.rc3-*.rpm",
            "release.py --release-version=3_2_11 --rc=4 --source-dir=/home/parag/glideinwms --release-dir=/var/tmp/release --rpm-release=4 --rpm-version=3.2.11",
            "",
            "Example: Final Release v3.2.11",
            "         Generate tarball: glideinWMS_v3_2_11*.tgz",
            "         Generate rpms   : glideinWMS-*-v3.2.11-3-*.rpm",
            "release.py --release-version=3_2_11 --source-dir=/home/parag/glideinwms --release-dir=/var/tmp/release --rpm-release=3 --rpm-version=3.2.11",
            "",
            ]
    return '\n'.join(help)


def parse_opts(argv):
    parser = optparse.OptionParser(usage=usage(),
                                   version=manager_version(),
                                   conflict_handler="resolve")
    parser.add_option('--release-version',
                      dest='relVersion',
                      action='store',
                      metavar='<release version>',
                      help='glideinwms version to release')
    parser.add_option('--source-dir',
                      dest='srcDir',
                      action='store',
                      metavar='<source directory>',
                      help='directory containing the glideinwms source code')
    parser.add_option('--release-dir',
                      dest='relDir',
                      default='/tmp/release',
                      action='store',
                      metavar='<release directory>',
                      help='directory to store release tarballs and webpages')
    parser.add_option('--rc',
                      dest='rc',
                      default=None,
                      action='store',
                      metavar='<Release Candidate Number>',
                      help='Release Candidate')
    parser.add_option('--rpm-release',
                      dest='rpmRel',
                      default=1,
                      action='store',
                      metavar='<RPM Release Number>',
                      help='RPM Release Number')
    parser.add_option('--rpm-version',
                      dest='rpmVer',
                      action='store',
                      metavar='<Product Version in RPM filename>',
                      help='Product Version in RPM filename')

    if len(argv) == 2 and argv[1] in ['-v', '--version']:
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
        if ((options.relVersion is None) or
            (options.srcDir is None) or
                (options.relDir is None)):
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

    print("___________________________________________________________________")
    print("Creating following glideinwms release")
    print(
        "Version=%s\nSourceDir=%s\nReleaseDir=%s\nReleaseCandidate=%s\nRPMRelease=%s" %
        (ver, srcDir, relDir, rc, rpmRel))
    print("___________________________________________________________________")
    print()
    rel = ReleaseManagerLib.Release(ver, srcDir, relDir, rc, rpmRel)

    rel.addTask(ReleaseManagerLib.TaskClean(rel))
    rel.addTask(ReleaseManagerLib.TaskSetupReleaseDir(rel))
    # rel.addTask(ReleaseManagerLib.TaskPylint(rel))
    rel.addTask(ReleaseManagerLib.TaskVersionFile(rel))
    rel.addTask(ReleaseManagerLib.TaskTar(rel))
    rel.addTask(ReleaseManagerLib.TaskFrontendTar(rel))
    rel.addTask(ReleaseManagerLib.TaskFactoryTar(rel))
    rel.addTask(ReleaseManagerLib.TaskRPM(rel))

    rel.executeTasks()
    rel.printReport()


if __name__ == "__main__":
    main(sys.argv)
