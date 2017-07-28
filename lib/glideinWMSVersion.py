#!/bin/env python

###############################################################################
# glideinWMSVersion.py
#
# Description:
#   Execute a ls command on a condor job working directory
#
# Usage:
#  glideinWMSVersion.py <Path to glideinWMS distribution> [<Checksum file>]
#
# Author:
#   Parag Mhashilkar (August 2010)
#
# License:
#  Fermitools
#
###############################################################################


from __future__ import print_function
from builtins import object
import os
import sys
try:
    # pylint: disable=E0611
    #  (hashlib methods are called dynamically)
    from hashlib import md5
    # pylint: enable=E0611
except ImportError:
    from md5 import md5

import string

class GlideinWMSDistro(object):

    class __impl(object):
        """ Implementation of the singleton interface """

        def __init__(self, dir, chksumFile='checksum'):
            self.versionIdentifier = 'GLIDEINWMS_VERSION'
            self.type="TARBALL"
            self.distroChksumFile = os.path.join(dir, 'etc', chksumFile)

            # If the default location does not exist, try RPM location
            if not os.path.exists(self.distroChksumFile):
                rpm_workdir = ''
                if chksumFile.endswith('.factory'):
                    rpm_workdir = '/var/lib/gwms-factory/work-dir/'
                elif chksumFile.endswith('.frontend'):
                    rpm_workdir = '/var/lib/gwms-frontend/vofrontend/'
                else:
                    rpm_workdir = 'UNKNOWN'

                self.distroChksumFile = os.path.join(rpm_workdir, chksumFile)
                self.type="RPM"
                if not os.path.exists(self.distroChksumFile):
                    self.type="UNKNOWN"

            try:
                self.createVersionString(dir)
            except:
                self._version = 'glideinWMS UNKNOWN'

        def createVersionString(self, dir):
            ver = 'UNKNOWN'
            patch = ""
            modifiedFiles = []

            # Load the distro file hastable
            distroFileHash = {}
            try:
                distroChksumFd = open(self.distroChksumFile)
                for line in distroChksumFd.readlines():
                    if not line.strip().startswith('#'):
                        file = os.path.normpath(((line.split('  '))[1]).strip())
                        hash = ((line.split('  '))[0]).strip()
                        distroFileHash[file] = hash
                    else:
                        idx = line.find(self.versionIdentifier)
                        if (idx >= 0) and (ver == 'UNKNOWN'):
                            v = (line[idx+len(self.versionIdentifier):]).strip()
                            if v != "":
                                ver = v
            finally:
                distroChksumFd.close()

            if ver != 'UNKNOWN':
                # Read the dir contents of distro and compute the md5sum
                computedFileHash = {}
                for file in list(distroFileHash.keys()):
                    fd = None
                    try:
                        if (self.type != "RPM"):
                            fd = open(os.path.join(dir, file), 'r')
                        else:
                            # In the RPM, all files are in site-packages
                            rpm_dir = os.path.dirname(
                                          os.path.dirname(
                                              sys.modules[__name__].__file__))
                            fd = open(os.path.join(rpm_dir,
                                                   os.path.dirname(file),
                                                   os.path.basename(file)), 'r')
                        chksum = md5(fd.read()).hexdigest()
                        if (chksum != distroFileHash[file]):
                            modifiedFiles.append(file)
                            patch = 'PATCHED'
                    except: #ignore missing files
                        pass
                    if fd:
                        fd.close()

            #if len(modifiedFiles) > 0:
            #    print "Modified files: %s" % string.join(modifiedFiles)

            self._version = string.strip("glideinWMS %s %s" % (ver, patch))

        def version(self):
            return self._version

    # storage for the instance reference
    __instance = None

    def __init__(self, dir, chksumFile='checksum'):
        if GlideinWMSDistro.__instance is None:
            GlideinWMSDistro.__instance = GlideinWMSDistro.__impl(dir, chksumFile=chksumFile)

        self.__dict__['_GlideinWMSDistro__instance'] = GlideinWMSDistro.__instance

    def __getattr__(self, attr):
        """ Delegate access to implementation """
        return getattr(self.__instance, attr)

    def __setattr__(self, attr, value):
        """ Delegate access to implementation """
        return setattr(self.__instance, attr, value)


def version(dir, chksumFile=None):
     return GlideinWMSDistro(dir, chksumFile=chksumFile).version()
#   version

def usage():
    print("Usage: glideinWMSVersion.py <Path to glideinWMS distribution> [<Checksum file>]")

##############################################################################
# MAIN
##############################################################################

if __name__ == '__main__':
    if len(sys.argv) == 2:
        print("%s " % (GlideinWMSDistro(sys.argv[1]).version()))
    elif len(sys.argv) == 3:
        print("%s " % (GlideinWMSDistro(sys.argv[1], chksumFile=sys.argv[2]).version()))
    else:
        usage()
        sys.exit(1)
