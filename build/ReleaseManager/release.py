#!/usr/bin/python -B

from __future__ import print_function
import sys
import os
# import getopt
import optparse

#sys.path.append(os.path.join(sys.path[0], '../lib'))
import ReleaseManagerLib


def usage():
    usage_str = "%s [options]" % os.path.basename(sys.argv[0])
    usage_str += """
    Prepare GlideinWMS files for release. 
    By default tries to build also the RPM if tools (rpmbuild, mock) are available, use --no-rpm to skip.
    Misconfigured RPM tools may cause errors in the RPM building process.
    Options release-version and source-dir are mandatory.

Example 1: If you will build the RPM with OSG tools
           Release v3.2.11 (final or release candidate)
release.py --no-rpm --release-version=3_2_11 --source-dir=/home/user/glideinwms --release-dir=/var/tmp/release 

Example 2: Release Candidate rc3 for v3.2.11 (ie version v3_2_11_rc3)
           Generate tarball: glideinWMS_v3_2_11_rc3*.tgz
           Generate rpms   : glideinWMS-*-v3.2.11-0.3.rc3-*.rpm
release.py --release-version=3_2_11 --rc=4 --source-dir=/home/user/glideinwms --release-dir=/var/tmp/release --rpm-release=4 --rpm-version=3.2.11

Example 3: Final Release v3.2.11
           Generate tarball: glideinWMS_v3_2_11*.tgz
           Generate rpms   : glideinWMS-*-v3.2.11-1-*.rpm
release.py --release-version=3_2_11 --source-dir=/home/user/glideinwms --release-dir=/var/tmp/release --rpm-release=3 --rpm-version=3.2.11

"""
    return usage_str


def parse_opts(argv):
    parser = optparse.OptionParser(usage=usage(),
                                   version='v0.3',
                                   conflict_handler="resolve")
    parser.add_option('--release-version',
                      dest='relVersion',
                      action='store',
                      metavar='<release version>',
                      help='glideinwms version to release (used for tar ball name and for package directory in release-osg)')
    parser.add_option('--source-dir',
                      dest='srcDir',
                      action='store',
                      metavar='<source directory>',
                      help='directory containing the glideinwms source code (absolute path)')
    parser.add_option('--release-dir',
                      dest='relDir',
                      default='/tmp/release',
                      action='store',
                      metavar='<release directory>',
                      help='directory to store release tarballs and webpages (absolute path)')
    parser.add_option('--rc',
                      dest='rc',
                      default=None,
                      action='store',
                      metavar='<Release Candidate Number>',
                      help='Release Candidate number (in tar file and spec file)')
    parser.add_option('--no-rpm',
                      dest='build_rpm',
                      default=True,
                      action='store_false',
                      metavar='<Release Candidate Number>',
                      help='Release Candidate number (in tar file and spec file)')
    parser.add_option('--rpm-release',
                      dest='rpmRel',
                      default=1,
                      action='store',
                      metavar='<RPM Release Number>',
                      help='RPM Release Number in spec file')
    parser.add_option('--rpm-version',
                      dest='rpmVer',
                      default=None,
                      action='store',
                      metavar='<Product Version in RPM filename>',
                      help='Product Version in RPM filename and spec file')

    # it could be help, required are checked below
    # if len(argv) < 4:
    #    print("ERROR: Insufficient arguments specified")
    #    parser.print_help()
    #    sys.exit(1)
    options, remainder = parser.parse_args(argv)
    if len(remainder) > 1:
        parser.print_help()
    if not required_args_present(options):
        print("ERROR: Missing required arguments")
        parser.print_help()
        sys.exit(1)
    return options


def required_args_present(options):
    """check_required_args"""
    try:
        if ((options.relVersion is None) or
            (options.srcDir is None) or
            (options.relDir is None)
           ):
            return False
    except AttributeError:
        return False
    return True


# def main(ver, srcDir, relDir):
def main(argv):
    options = parse_opts(argv)
    # sys.exit(1)
    ver = options.relVersion
    srcDir = options.srcDir
    relDir = options.relDir
    rc = options.rc
    rpmRel = options.rpmRel
    rpmVer = options.rpmVer

    print("___________________________________________________________________")
    print("Creating following glideinwms release")
    print("Version=%s\nSourceDir=%s\nReleaseDir=%s\nReleaseCandidate=%s\nRPMVersion=%s (%s)\nRPMRelease=%s" % (ver, srcDir, relDir, rc, rpmVer, ver, rpmRel))
    print("___________________________________________________________________")
    print()
    rel = ReleaseManagerLib.Release(ver, srcDir, relDir, rc, rpmRel, rpmVer)

    rel.addTask(ReleaseManagerLib.TaskClean(rel))
    rel.addTask(ReleaseManagerLib.TaskSetupReleaseDir(rel))
    # rel.addTask(ReleaseManagerLib.TaskPylint(rel))
    rel.addTask(ReleaseManagerLib.TaskVersionFile(rel))
    rel.addTask(ReleaseManagerLib.TaskTar(rel))
    rel.addTask(ReleaseManagerLib.TaskFrontendTar(rel))
    rel.addTask(ReleaseManagerLib.TaskFactoryTar(rel))
    if options.build_rpm:
        rel.addTask(ReleaseManagerLib.TaskRPM(rel))

    rel.executeTasks()
    rel.printReport()


if __name__ == "__main__":
    main(sys.argv)
