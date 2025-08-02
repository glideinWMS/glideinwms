#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This script downloads HTCondor tarballs from the official HTCondor website.

Exit codes:
  0: All good.
  1: Configuration file does not exist.
  2: The XML file specified in XML_OUT is missing or cannot be written to disk.
  3: Cannot find XML_OUT file when using --checklatest.
  4: XML file needs to be updated because a newer version is present on the website.

A configuration file is specified through the GET_TARBALLS_CONFIG environment variable.
Alternatively, the script looks for a file named get_tarballs.yaml in the same directory
as get_tarballs.py.

This is a sample configuration file:

DESTINATION_DIR: "/var/lib/gwms-factory/condor/"
TARBALL_BASE_URL: "https://research.cs.wisc.edu/htcondor/tarball/"
DEFAULT_TARBALL_VERSION: [ "9.0.16" ] # Can be set to "latest"
CONDOR_TARBALL_LIST:
   - MAJOR_VERSION: "9.0"
     WHITELIST: [ "9.0.7", "9.0.16", "latest" ]
   - MAJOR_VERSION: "10.0"
     WHITELIST: [ "latest" ]
   - MAJOR_VERSION: "10.x"
     DOWNLOAD_LATEST: True # Same as adding "latest" to a WHITELIST. Default False
   - MAJOR_VERSION: "23.0"
     WHITELIST: [ "23.0.0" ]
   - MAJOR_VERSION: "23.x"
     WHITELIST: [ "23.0.0" ]
FILENAME_LIST: [ "condor-{version}-x86_64_CentOS7-stripped.tar.gz", "condor-{version}-x86_64_CentOS8-stripped.tar.gz", "condor-{version}-x86_64_AlmaLinux8-stripped.tar.gz", "condor-{version}-x86_64_Ubuntu18-stripped.tar.gz", "condor-{version}-x86_64_Ubuntu20-stripped.tar.gz", "condor-{version}-aarch64_Stream8-stripped.tar.gz", "condor-{version}-ppc64le_CentOS8-stripped.tar.gz", "condor-{version}-ppc64le_AlmaLinux8-stripped.tar.gz", "condor-{version}-aarch64_AlmaLinux8-stripped.tar.gz" ]
OS_MAP: { "CentOS7":"default,rhel7,linux-rhel7", "CentOS8":"rhel8,linux-rhel8", "AlmaLinux8":"rhel8,linux-rhel8", "Ubuntu18":"ubuntu18,linux-ubuntu18", "Ubuntu20":"ubuntu20,linux-ubuntu20"}
ARCH_MAP: { "x86_64":"default", "ppc64le":"ppc64le", "aarch64":"aarch64" }
XML_OUT: "/etc/gwms-factory/config.d/01-condor-tarballs.xml"

# Not specifying BLACKLIST or WHITELIST download everything
# Blacklist is ignored if whitelist is specified as well
# WHITELIST: download only those releases
# BLACKLIST: do not download the releases but download all the rest
"""

import argparse
import hashlib
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET

from collections import UserDict
from distutils.version import StrictVersion
from html.parser import HTMLParser
from urllib import request
from urllib.error import HTTPError
from urllib.parse import urljoin

import yaml


class TarballManager(HTMLParser):
    """Manages HTCondor tarballs for a major release (e.g.: 23.0).

    In the constructor, it builds a list of releases by parsing the major
    release web page looking for minor releases (e.g.: 23.0.0) that have
    been released (they have a release directory). The list of releases are
    solely used for validation purposes, and to know the latest release.

    It then offers a method to download a tarball and save it locally,
    and a method to generate the xml snippet to add to the glideinWMS.xml
    tarball configuration section.

    Attributes:
        releases (list): List of release version strings.
        release_dirs (dict): Mapping from release version to its corresponding directory (e.g., "release", "beta").
        filenames (list): List of tarball filename templates.
        release_url (str): Base URL for the major release.
        destination (str): Local destination directory for downloads.
        downloaded_files (list): List of paths to successfully downloaded tarballs.
        latest_version (str): Latest version found among the available releases.
        verbose (bool): If True, prints verbose messages.
    """

    def __init__(self, release_url, filenames, destination, verbose=False):
        """Create a TarballManager object.

        Parses the tarball HTCondor web page to build a list of available releases,
        saved into self.releases.
        Calls the .feed() function from HTMLParser that in turn calls the overridden
        handle_data() function.

        Args:
            release_url (str): The main url where to begin looking for releases. It has to be the url
                of a major release, for example: https://research.cs.wisc.edu/htcondor/tarball/23.0/
                The list of available releases are here: https://research.cs.wisc.edu/htcondor/tarball/
            filenames (list): A list of strings indicating the tarballs that need to be downloaded for each release found.
                As an example, [ "condor-{version}-x86_64_CentOS7-stripped.tar.gz", "condor-{version}-x86_64_CentOS8-stripped.tar.gz" ]
                will download the x86_64 CentOS7 and CentOS8 tarballs by looking for urls that looks like:
                https://research.cs.wisc.edu/htcondor/tarball/23.0/23.0.0/release/condor-23.0.0-x86_64_CentOS7-stripped.tar.gz
                The substring {version} gets expanded to the current version.
          destination (str): the directory where files will be downloaded when the download_tarballs method is called
          verbose (bool, optional): More printouts when files are being downloaded if True. Defaults to False.
        """
        super().__init__()
        self.releases = []
        self.release_dirs = {}
        self.filenames = filenames
        self.release_url = release_url
        self.destination = destination
        self.downloaded_files = []
        self.latest_version = None  # absolute latest, does not consider whitelists and blacklists
        self.verbose = verbose

        fp = request.urlopen(self.release_url)
        mybytes = fp.read()
        self.feed(mybytes.decode("utf-8"))
        if len(self.releases) == 0:
            print(f"Cannot find any release in {self.release_url}")
        else:
            self.releases.sort(key=StrictVersion)
            self.latest_version = self.releases[-1]

    def _add_release(self, version, release_dir):
        """Attempt to add a release version if its directory exists. Private function.

        Adds the release to `self.releases`

        Args:
            version (str): Condor version string, e.g., "23.0.1".
            release_dir (str): Directory to check for the release (e.g., "release", "beta", "update").

        Returns:
            bool: True if the release directory exists and the release was added; False otherwise.
        """
        try:
            request.urlopen(self.release_url + "/" + version + release_dir)
        except HTTPError as err:
            if err.getcode() != 404:
                raise
        else:
            version = version[:-1]  # -1 to remove trailing
            self.releases.append(version)
            self.release_dirs[version] = release_dir
            return True
        return False

    def handle_data(self, data):
        """Handle HTML data to extract release version information.

        Internal method. Overrides `HTMLParser.handle_data()`.

        Args:
            data (str): A string containing HTML data.
        """
        if re.match(r"\d+\.\d+\.\d+/", data):
            added = self._add_release(data, "release")
            # For condor feature releases (i.e., middle number not 0), we allow beta releases
            if not added and data.split(".")[1] != "0":
                added = self._add_release(data, "beta")
                # Prior to HTCondor version 24 the beta directory was called "update"
                if not added:
                    self._add_release(data, "update")

    def download_tarballs(self, version):
        """Download tarballs for a specific HTCondor version.

        Download a specific set of condor tarballs from the release_url link.
        All the OS and architecture tarballs for the specified condor version are downloaded.
        The set of OS and architecture files are specified in the constructor using filenames.

        The method also checks the tarball checksum (by downloading the sha256sum.txt file).
        If a tarball already exist and its checksum is correct then it is skipped.
        If a specific os/architecture tarball is not available it is skipped, and a message is
        printed on stdout if verbose has been set to True in the constructor.

        Args:
            version (str): The HTCondor version to download (e.g., "23.0.1").
        """
        desturl = os.path.join(
            self.release_url, version, self.release_dirs[version] + "/"
        )  # urljoin needs nested call and manual adding of "/".. It sucks.
        checksums = {}
        with tempfile.TemporaryDirectory() as tmp_dir:
            hash_file = os.path.join(tmp_dir, "sha256sum.txt")
            request.urlretrieve(urljoin(desturl, "sha256sum.txt"), hash_file)

            with open(hash_file) as hf:
                for line in hf:
                    fhash, filename = line.split("  ")
                    checksums[filename.strip()] = fhash.strip()

        for fname in self.filenames:
            tname = fname.format(version=version)  # tarball name
            dest_file = os.path.join(self.destination, tname)
            if os.path.isfile(dest_file):
                if self.verify_checksum(tname, checksums):
                    self.verbose and print(f"\tFile {dest_file} already exists. Continuing with next file")
                    self.downloaded_files.append(dest_file)
                    continue
                else:
                    print(
                        f"\tRe-downloading {dest_file} since it exists but it has a wrong checksum (or checkusm does not exist)"
                    )

            try:
                request.urlretrieve(urljoin(desturl, tname), dest_file)
            except HTTPError as err:
                if err.getcode() == 404:
                    self.verbose and print(f"\tFile {tname} is not available at {desturl}. Continuing with next file")
                    continue
                else:
                    raise
            isok = self.verify_checksum(tname, checksums)
            if isok:
                print(f"\tFile {tname} successfully downloaded")
                self.downloaded_files.append(dest_file)
            elif isok is False:
                print(f"\tChecksum verification failed for file {tname} at {desturl}. Continuing with next file")
            elif isok is None:
                print(
                    f"\tFile {tname} successfully downloaded but checksum not available at {desturl} (check 'sha256sum.txt')"
                )

    def verify_checksum(self, tname, checksums):
        """Verify the SHA256 checksum of a downloaded tarball. Internal function.

        Args:
            tname (str): The tarball filename.
            checksums (dict): Dictionary mapping filenames to their expected SHA256 hashes.

        Returns:
            bool or None: True if the checksum matches, False if it does not, None if the expected checksum is missing.
        """
        dest_file = os.path.join(self.destination, tname)
        with open(dest_file, "rb") as f:
            tar_content = f.read()
            actual_checksum = hashlib.sha256(tar_content).hexdigest()

        try:
            return actual_checksum == checksums[tname]
        except KeyError:
            return None

    def generate_xml(self, os_map, arch_map, whitelist, blacklist, default_tarball_version):
        """Generate an XML snippet for the tarball configuration.

        The XML snippet is intended for inclusion in the <condor_tarballs> section of the glideinWMS.xml file.

        Args:
            os_map (dict): Mapping of OS names in tarball filenames to XML os attribute values.
                See OS_MAP in the configuration template.
            arch_map (dict): Mapping of architecture names in tarball filenames to XML arch attribute values.
                See ARCH_MAP in the configuration template.
            whitelist (list): List of versions to include. If non-empty, only these versions are used.
                Can be "latest" to download the latest version.
            blacklist (list): List of versions to exclude.
            default_tarball_version (list): List of default tarball versions. If a version is in this list,
                ",default" will be added to the version attribute in the XML.

        Returns:
            str: An XML snippet containing multiple <condor_tarball> elements.
        """
        xml_snippet = '      <condor_tarball arch="{arch}" os="{os}" tar_file="{dest_file}" version="{version}"/>\n'

        if whitelist != []:
            latest_version = sorted(whitelist, key=StrictVersion)[-1]
        else:
            versions = list(set(self.releases) - set(blacklist))
            latest_version = sorted(versions, key=StrictVersion)[-1]

        out = ""
        for dest_file in self.downloaded_files:
            _, sversion, os_arch, _ = os.path.basename(dest_file).split("-")
            arch, opsystem = os_arch.rsplit("_", 1)
            version = sversion  # sversion = "split" version
            if sversion == latest_version:
                major, minor, _ = sversion.split(".")
                version += "," + major + ".0.x" if minor == "0" else "," + major + ".x"
            if sversion in default_tarball_version:
                version += ",default"
            out += xml_snippet.format(arch=arch_map[arch], os=os_map[opsystem], dest_file=dest_file, version=version)
        return out


class Config(UserDict):
    """Configuration container for tarball download settings.

    Loads configuration from a YAML file, validates it and stores it into a dictionary.
    The configuration file is determined by the GET_TARBALLS_CONFIG environment variable
    or by a default file (get_tarballs.yaml) in the script directory.
    """

    def __init__(self):
        """Build the dictionary using yaml.load. The configuration file is located by
        looking at the environment variable GET_TARBALLS_CONFIG, or by looking for
        a file named get_tarballs.yaml in the script directory (os.path.abspath(__file__))
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file = os.environ.get("GET_TARBALLS_CONFIG", False) or os.path.join(script_dir, "get_tarballs.yaml")
        if not os.path.isfile(config_file):
            print(f"Configuration file {config_file} does not exist")
            sys.exit(1)
        with open(config_file) as cf:
            config = yaml.load(cf, Loader=yaml.FullLoader)
        super().__init__(config)
        self.validate()

    def validate(self):
        """Validate and normalize the configuration.

        Sorts whitelists and blacklists for each major release in the configuration.
        """
        for major_dict in self["CONDOR_TARBALL_LIST"]:
            if "WHITELIST" not in major_dict:
                major_dict["WHITELIST"] = []
            if "BLACKLIST" not in major_dict:
                major_dict["BLACKLIST"] = []
            if "latest" in major_dict["WHITELIST"]:
                major_dict["WHITELIST"].remove("latest")
                major_dict["DOWNLOAD_LATEST"] = True
            major_dict["WHITELIST"].sort(key=StrictVersion)
            major_dict["BLACKLIST"].sort(key=StrictVersion)


def save_xml(dest_xml_file, xml):
    """Save the generated XML snippet to disk with proper XML structure.

    Args:
        dest_xml_file (str): The destination file path for the XML output.
        xml (str): The XML snippet to save.
    """
    with open(dest_xml_file, "w") as fd:
        fd.write("<glidein>\n")
        fd.write("   <condor_tarballs>\n")
        fd.write(xml)
        fd.write("   </condor_tarballs>\n")
        fd.write("</glidein>\n")


def parse_opts():
    """Parse command-line options for the tarball downloader.

    Options:
        --verbose: Enable verbose logging.
        --checklatest: Check that each major version 'latest' is present in the XML output.

    Returns:
        argparse.Namespace: Parsed command-line options.
    """
    parser = argparse.ArgumentParser(
        prog="get_tarballs", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--verbose", action="store_true", help="Be more loud when downloading tarballs file")
    parser.add_argument(
        "--checklatest", action="store_true", help="Check that each of the major version 'latest' is in the xml"
    )

    args = parser.parse_args()

    return args


def checklatest(config, verbose):
    """Validates that the "latest" tarball versions specified in the configuration are present
    in the XML file and match the actual latest versions available from the condor website.

    Args:
        config (dict): The configuration dictionary
        verbose (bool): If True, prints detailed logs for debugging purposes.

    Returns:
        int: Exit code:
            0 if all "latest" tarball versions are up to date.
            1 if any "latest" tarball version is missing in the XML.
            2 if the XML file specified in XML_OUT is missing or cannot be written.
            3 if the XML file cannot be found when using --checklatest.
            4 if the XML file needs updating due to a newer version on the website.

    Behavior:
        - Parses the XML file specified in `XML_OUT` to extract the versions of the current tarballs.
        - Identifies the major versions in `CONDOR_TARBALL_LIST` that require "latest" tarballs.
        - Checks if the "latest" tarball version from the condor website is present in the XML file.
    """
    xml_out = config.get("XML_OUT")
    if not os.path.exists(xml_out):
        print(f"Cannot find tarball xml file {xml_out}")
        return 3

    tree = ET.parse(xml_out)
    root = tree.getroot()
    version_list = []
    for tarball in root.findall(".//condor_tarball"):
        version_list += tarball.get("version").split(",")
    version_list = set(version_list)
    if verbose:
        lines = "\n".join(sorted(version_list))  # chr(10).join() is not portable, better to define the var outside
        print(f"Found the following tarballs in {xml_out}:\n{lines}\n")

    print(f"Searching for condor major versions that need 'latest' tarballs in {xml_out}\n")
    for major_dict in config["CONDOR_TARBALL_LIST"]:
        major_version = major_dict["MAJOR_VERSION"]
        if not major_dict.get("DOWNLOAD_LATEST", False):
            verbose and print(f"Skipping version {major_version} because it does not need 'latest' tarballs\n")
            continue
        manager = TarballManager(
            urljoin(config["TARBALL_BASE_URL"], major_version), config["FILENAME_LIST"], config["DESTINATION_DIR"]
        )
        verbose and print(
            f'Available releases for major version {major_dict["MAJOR_VERSION"]} are:\n{manager.releases}.\nLatest tarball in xml file is {manager.latest_version}. All good.\n'
        )

        if manager.latest_version not in version_list:
            print(
                f'Latest version {manager.latest_version} found at "{config["TARBALL_BASE_URL"]}" is not present in "{xml_out}"'
            )
            return 4

    print("All tarballs are up to date")
    return 0


def main():
    """Main function for downloading HTCondor tarballs.

    Parses command-line options and loads configuration. If the --checklatest option is
    specified, it checks that the XML output is up to date. Otherwise, it downloads tarballs
    for each major release, verifies checksums, generates an XML snippet for the tarball configuration,
    and saves the XML snippet to the file specified in XML_OUT.

    Returns:
        int: Exit code:
            0: Success.
            2: XML output file error.
            4: XML file needs update.
    """
    args = parse_opts()
    config = Config()
    release_url = config["TARBALL_BASE_URL"]
    default_tarball_version = config["DEFAULT_TARBALL_VERSION"]
    xml = ""

    if args.checklatest is True:
        return checklatest(config, args.verbose)

    for major_dict in config["CONDOR_TARBALL_LIST"]:
        print(f'Handling major version {major_dict["MAJOR_VERSION"]}')
        major_version = major_dict["MAJOR_VERSION"]
        manager = TarballManager(
            urljoin(release_url, major_version), config["FILENAME_LIST"], config["DESTINATION_DIR"], args.verbose
        )
        # If necessary, add the latest version to the whitelist now that we know the latest version for this major set of releases
        if major_dict.get("DOWNLOAD_LATEST", False):
            major_dict["WHITELIST"].append(manager.latest_version)
        if major_dict["WHITELIST"] != []:
            # Just get whitelisted versions
            for version in set(major_dict["WHITELIST"]):
                manager.download_tarballs(version)
        else:
            # Get everything but the blacklisted
            to_download = sorted(set(manager.releases) - set(major_dict["BLACKLIST"]), key=StrictVersion)
            for version in to_download:
                manager.download_tarballs(version)
        if config.get("XML_OUT") is not None:
            xml += manager.generate_xml(
                config["OS_MAP"],
                config["ARCH_MAP"],
                major_dict["WHITELIST"],
                major_dict["BLACKLIST"],
                manager.latest_version if default_tarball_version == "latest" else default_tarball_version,
            )

    if config.get("XML_OUT") is not None:
        try:
            save_xml(config["XML_OUT"], xml)
        except OSError as ioex:
            print(f'Cannot write file {config["XML_OUT"]} when trying to save xml tarball output: {str(ioex)}')
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
