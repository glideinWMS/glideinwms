#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Execute a ls command on a condor job working directory.

Usage:
    glideinWMSVersion.py <Path to glideinWMS distribution> [<Checksum file>]
"""

import os
import sys
from hashlib import md5


class GlideinWMSDistro:
    """Singleton class to handle GlideinWMS distribution checksum and versioning."""

    class __impl:
        """Implementation of the singleton interface."""

        def __init__(self, chksumFile="checksum"):
            """
            Args:
                chksumFile (str): Path to the checksum file. Defaults to "checksum".
            """
            self.versionIdentifier = "GLIDEINWMS_VERSION"

            rpm_workdir = ""
            if chksumFile.endswith(".factory"):
                rpm_workdir = "/var/lib/gwms-factory/work-dir/"
            elif chksumFile.endswith(".frontend"):
                rpm_workdir = "/var/lib/gwms-frontend/vofrontend/"
            else:
                rpm_workdir = "UNKNOWN"

            self.distroChksumFile = os.path.join(rpm_workdir, chksumFile)

            try:
                self.createVersionString()
            except Exception:
                self._version = "glideinWMS UNKNOWN"

        def createVersionString(self):
            """Creates the version string based on the checksum file and the current state of the distribution."""
            ver = "UNKNOWN"
            patch = ""
            modifiedFiles = []

            distroFileHash = {}
            with open(self.distroChksumFile) as distroChksumFd:
                for line in distroChksumFd.readlines():
                    if not line.strip().startswith("#"):
                        file = os.path.normpath(((line.split("  "))[1]).strip())
                        hash = ((line.split("  "))[0]).strip()
                        distroFileHash[file] = hash
                    else:
                        idx = line.find(self.versionIdentifier)
                        if (idx >= 0) and (ver == "UNKNOWN"):
                            v = (line[idx + len(self.versionIdentifier) :]).strip()
                            if v != "":
                                ver = v

            if ver != "UNKNOWN":
                for file in list(distroFileHash.keys()):
                    fd = None
                    try:
                        rpm_dir = os.path.dirname(os.path.dirname(sys.modules[__name__].__file__))
                        fd = open(os.path.join(rpm_dir, os.path.dirname(file), os.path.basename(file)))

                        chksum = md5(fd.read()).hexdigest()
                        if chksum != distroFileHash[file]:
                            modifiedFiles.append(file)
                            patch = "PATCHED"
                    except Exception:
                        pass
                    if fd:
                        fd.close()

            self._version = f"glideinWMS {ver} {patch}"

        def version(self):
            """Returns the current version string.

            Returns:
                str: The current version string.
            """
            return self._version

    __instance = None

    def __init__(self, chksumFile="checksum"):
        """
        Args:
            chksumFile (str): Path to the checksum file. Defaults to "checksum".
        """
        if GlideinWMSDistro.__instance is None:
            GlideinWMSDistro.__instance = GlideinWMSDistro.__impl(chksumFile=chksumFile)

        self.__dict__["_GlideinWMSDistro__instance"] = GlideinWMSDistro.__instance

    def __getattr__(self, attr):
        """Delegate access to implementation."""
        return getattr(self.__instance, attr)

    def __setattr__(self, attr, value):
        """Delegate access to implementation."""
        return setattr(self.__instance, attr, value)


def version(chksumFile=None):
    """Gets the GlideinWMS version.

    Args:
        chksumFile (str, optional): Path to the checksum file.

    Returns:
        str: The GlideinWMS version.
    """
    return GlideinWMSDistro(chksumFile=chksumFile).version()


def usage():
    """Prints the usage of the script."""
    print("Usage: glideinWMSVersion.py <Path to glideinWMS distribution> [<Checksum file>]")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(f"{GlideinWMSDistro().version()} ")
    elif len(sys.argv) == 2:
        print(f"{GlideinWMSDistro(chksumFile=sys.argv[1]).version()} ")
    else:
        usage()
        sys.exit(1)
