#!/usr/bin/python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import subprocess
import shutil
import platform

# platform.linux_distribution() was deprecated in 3.5 and removed in 3.8
# distro.linux_distribution() is a drop-in replacement but is deprecated and will be removed in distro 2.0
# The recommendation is to use distro.id(), distro.version(), distro.name()
try:
    import distro  # pylint: disable=import-error
except ImportError:
    distro = None


class ExeError(RuntimeError):
    def __init__(self, str):
        RuntimeError.__init__(self, str)


class Release:
    def __init__(self, ver, srcDir, relDir, rc, rpmRel, skip_rpm, timeout, is_verbose=False, is_debug=False):
        self.version = self.createTarballVersionString(ver, rc)
        self.sourceDir = srcDir
        self.releaseDir = os.path.join(relDir, self.version)
        self.releaseWebDir = os.path.join(self.releaseDir, "www")
        self.tasks = []
        self.rc = rc
        self.timeout = timeout
        self.verbose = is_verbose
        self.debug = is_debug
        self.buildRPMs = False
        try:
            # RPM related info
            self.rpmRelease = self.createRPMReleaseNVR(rpmRel, rc)
            self.rpmVersion = self.versionToRPMVersion(ver)
            self.rpmbuildDir = os.path.join(self.releaseDir, "rpmbuild")
            self.rpmOSVersion = self.getElVersion()
            # SRPM name has "el" also for AlmaLinux
            self.srpmFile = os.path.join(
                self.rpmbuildDir,
                "SRPMS",
                f"glideinwms-{self.rpmVersion}-{self.rpmRelease}.{self.rpmOSVersion[0]}{self.rpmOSVersion[1]}.src.rpm",
            )
            if skip_rpm:
                print("Skipping RPM build as requested.")
            else:
                self.buildRPMs = bool(which("rpmbuild"))
                if not self.buildRPMs:
                    print("'rpmbuild' not found, skipping RPM build")
        except Exception:
            print("RPMs will not be build for this platform")

    def createTarballVersionString(self, ver, rc):
        ver_str = "%s" % ver
        if rc:
            ver_str = f"{ver}_rc{rc}"
        return ver_str

    def versionToRPMVersion(self, ver):
        if ver.startswith("v"):
            ver = ver[1:]
        ver = ver.replace("_", ".")
        return ver

    def createRPMReleaseNVR(self, rpmRel, rc):
        if rc:
            nvr = f"0.{rc}.rc{rc}"
            if rpmRel:
                nvr = f"{nvr}.{rpmRel}"
        else:
            nvr = "1"
            if rpmRel:
                nvr = f"{rpmRel}"
        return nvr

    def getElVersion(self):
        if platform.system() != "Linux":
            raise Exception("Unsupported OS: %s" % platform.system())
        el_string = "el"
        if distro:
            # Deprecated - distname, version, id = distro.linux_distribution()
            distname = distro.name()  # If full_distribution_name is false, the result of distro.id()
            version = distro.version()
            dist_id = distro.codename()
        else:
            # TODO: remove the else branch once Py3.6 is no more supported
            distname, version, dist_id = platform.linux_distribution()  # pylint: disable=no-member
        # Check if mock profiles changed
        # As of Dec 2024 on AlmaLinux9: alma+epel-..., rhel+epel-..., centos-stream+epel-...
        # No profile has epel-... (maybe rhel-7 for sl7)
        distmap = {
            "Fedora": ("fc", "fedora"),
            "Scientific Linux": ("el", "epel"),
            "Red Hat": ("el", "rhel+epel"),
            "CentOS Stream": ("el", "centos-stream+epel"),
            "AlmaLinux": ("el", "alma+epel"),
            "RockyLinux": ("el", "rocky+epel"),
        }
        dist = None
        el_profile = None
        for d in distmap:
            if distname.startswith(d):
                dist = distmap[d][0]
                el_profile = distmap[d][1]
                break
        if dist is None:
            raise Exception("Unsupported distribution: %s" % distname)
        else:
            el_string = dist
        major_version = version.split(".")[0]
        return el_string, major_version, el_profile

    def addTask(self, task):
        self.tasks.append(task)

    # def printReport(self):
    #   for task in self.releaseTasks.keys():
    #        print print "TASK: %-30s STATUS: %s" % (task, (tasklist[]).status)

    def executeTasks(self):
        for i in range(0, len(self.tasks)):
            task = self.tasks[i]
            print("************* Executing %s *************" % (self.tasks[i]).name)
            task.execute()
            print(f"************* {(self.tasks[i]).name} Status {(self.tasks[i]).status} *************")

    def printReport(self):
        print(35 * "_")
        print("TASK" + 20 * " " + "STATUS")
        print(35 * "_")
        for i in range(0, len(self.tasks)):
            print("%-23s %s" % ((self.tasks[i]).name, (self.tasks[i]).status))
        print(35 * "_")


class TaskRelease:
    def __init__(self, name, rel):
        self.name = name
        self.release = rel
        self.status = "INCOMPLETE"

    def execute(self):
        raise ExeError("Action execute not implemented for task %s" % self.name)


class TaskClean(TaskRelease):
    def __init__(self, rel):
        TaskRelease.__init__(self, "Clean", rel)

    def execute(self):
        cmd = "rm -rf %s" % self.release.releaseDir
        execute_cmd(cmd)
        self.status = "COMPLETE"


class TaskSetupReleaseDir(TaskRelease):
    def __init__(self, rel):
        TaskRelease.__init__(self, "SetupReleaseDir", rel)

    def execute(self):
        create_dir(self.release.releaseDir)
        create_dir(self.release.releaseWebDir)
        self.status = "COMPLETE"


class TaskPylint(TaskRelease):
    def __init__(self, rel):
        TaskRelease.__init__(self, "Pylint", rel)
        self.rcFile = os.path.join(sys.path[0], "../etc/pylint.rc")
        self.fileList = []
        self.pylintArgs = ["-e", "--rcfile=%s" % self.rcFile]

    def callback(self, dir, files):
        for file in files:
            if file.endswith(".py"):
                self.fileList.append(os.path.join(dir, file))

    def index(self):
        stack = [self.release.sourceDir]
        while stack:
            dir = stack.pop()
            for file in os.listdir(dir):
                fullname = os.path.join(dir, file)
                if file.endswith(".py"):
                    self.fileList.append(os.path.join(dir, file))
                if os.path.isdir(fullname) and not os.path.islink(fullname):
                    stack.append(fullname)

    def pylint(self):
        # not currently called by packageManager, import was commented out above.
        # As pylint didn't like that, move it here to make it easier to either
        # delete whole thing or re-enable as desired
        #
        from pylint import lint

        lint.Run(self.pylintArgs + self.fileList)

    def pylint1(self):
        # print self.fileList
        from pylint import lint

        for file in self.fileList:
            print("Running pylint on %s" % file)
            print(self.pylintArgs + [file])
            lint.Run(self.pylintArgs + [file])

    def execute(self):
        self.index()
        self.pylint()
        self.status = "COMPLETE"


class TaskDocumentation(TaskRelease):
    def __init__(self, rel):
        TaskRelease.__init__(self, "GlideinWMSDocumentation", rel)
        self.doc_filename = f"glideinwms-doc.{self.release.version}.tar"
        self.gitExe = which("git")

    def execute(self):
        src_dir = f"{self.release.releaseDir}/../src/{self.release.version}/glideinwms"
        # The final directory does not matter. Each command execution starts form the same place
        cmd = f"cd {src_dir} && {self.gitExe} archive HEAD doc > {self.release.releaseDir}/{self.doc_filename}"
        if self.release.verbose:
            print("%s" % cmd)
        execute_cmd(cmd, timeout=self.release.timeout, is_debug=self.release.debug)
        self.status = "COMPLETE"


class TaskTar(TaskRelease):
    """Task building the release tarball.

    It uses the `PackageExcludes` class to define which paths in the source tree not to include.
    """

    def __init__(self, rel):
        TaskRelease.__init__(self, "GlideinWMSTar", rel)
        self.excludes = PackageExcludes()
        self.releaseFilename = f"glideinwms_{self.release.version}.tgz"
        self.excludePattern = self.excludes.commonPattern
        self.tarExe = which("tar")

    def execute(self):
        exclude = ""
        if len(self.excludePattern) > 0:
            exclude = "--exclude='" + "' --exclude='".join(self.excludePattern) + "'"
        src_dir = f"{self.release.releaseDir}/../src/{self.release.version}"
        # src_dir_gwms = f"{src_dir}/glideinwms"
        # cmd = 'cd %s/..; /bin/tar %s -czf %s/%s glideinwms' % \
        #      (self.release.sourceDir, exclude, self.release.releaseDir, self.releaseFilename)
        # Copy must include .git directory because of documentation archive command
        copy_command = f"mkdir -p {src_dir}; cp -r {self.release.sourceDir} {src_dir}/"
        # if bool(which("rsync")):
        #     copy_command = f"mkdir -p {src_dir_gwms}; rsync -al --exclude='.git' {self.release.sourceDir}/ {src_dir_gwms}/"
        cmd = "rm -rf {}; {}; cd {}; {} {} -czf {}/{} glideinwms".format(
            src_dir,
            copy_command,
            src_dir,
            self.tarExe,
            exclude,
            self.release.releaseDir,
            self.releaseFilename,
        )
        if self.release.verbose:
            print("%s" % cmd)
        execute_cmd(cmd, timeout=self.release.timeout, is_debug=self.release.debug)
        self.status = "COMPLETE"


class TaskVersionFile(TaskRelease):
    def __init__(self, rel):
        TaskRelease.__init__(self, "VersionFile", rel)
        self.releaseChksumFile = os.path.normpath(os.path.join(self.release.sourceDir, "etc/checksum"))
        self.frontendChksumFile = os.path.normpath(os.path.join(self.release.sourceDir, "etc/checksum.frontend"))
        self.factoryChksumFile = os.path.normpath(os.path.join(self.release.sourceDir, "etc/checksum.factory"))
        self.excludes = PackageExcludes()
        self.checksumFilePattern = "etc/checksum*"
        self.chksumBin = os.path.normpath(os.path.join(sys.path[0], "chksum.sh"))

    def execute(self):
        self.checksumRelease(self.releaseChksumFile, self.excludes.commonPattern)
        self.checksumRelease(self.frontendChksumFile, self.excludes.frontendPattern)
        self.checksumRelease(self.factoryChksumFile, self.excludes.factoryPattern)
        self.status = "COMPLETE"

    def checksumRelease(self, chksumFile, exclude):
        excludePattern = self.checksumFilePattern + " install/templates CVS config_examples "
        if len(exclude) > 0:
            excludePattern = '"' + "%s " % excludePattern + " ".join(exclude) + '"'
        cmd = "cd {}; {} {} {} {}".format(
            self.release.sourceDir,
            self.chksumBin,
            self.release.version,
            chksumFile,
            excludePattern,
        )
        # print "--- %s" % chksumFile
        # print "--- %s" % cmd
        execute_cmd(cmd, timeout=self.release.timeout, is_debug=self.release.debug)


class TaskRPM(TaskTar):
    def __init__(self, rel, python_version, use_mock=True, verbose=False):
        TaskTar.__init__(self, rel)
        self.name = "GlideinwmsRPM"
        self.verbose = verbose
        self.use_mock = use_mock
        self.python_version = python_version
        self.releaseFile = os.path.join(self.release.releaseDir, self.releaseFilename)
        self.rpmPkgDir = os.path.join(self.release.sourceDir, "build/packaging/rpm")
        self.specFileTemplate = os.path.join(self.rpmPkgDir, "glideinwms.spec")
        self.specFile = os.path.join(self.release.rpmbuildDir, "SPECS", "glideinwms.spec")
        # self.rpmmacrosFile = os.path.join(os.path.expanduser('~'),
        self.rpmmacrosFile = os.path.join(os.path.dirname(self.release.rpmbuildDir), ".rpmmacros")
        # Files in build/pkg/rpm to copy in the SOURCES directory
        self.sourceFilenames = [
            "chksum.sh",
            "factory_startup",
            "frontend_startup",
            "factory_startup_sl7",
            "frontend_startup_sl7",
            "frontend.xml",
            "glideinWMS.xml",
        ]
        self.rpmMacros = {
            "_topdir": self.release.rpmbuildDir,
            "_tmppath": "/tmp",
            "_source_filedigest_algorithm": "md5",
            "_binary_filedigest_algorithm": "md5",
            #'global __python': '%%{__python2}',
            #'py_byte_compile': '',
            # %py_byte_compile %{__python2} %{buildroot}%{_datadir}/mypackage/foo
        }

    #   __init__

    def createRPMBuildDirs(self):
        # Create directories required by rpmbuild
        rpm_dirs = ["BUILD", "RPMS", "SOURCES", "SPECS", "SRPMS"]
        for dirname in rpm_dirs:
            create_dir(os.path.join(self.release.rpmbuildDir, dirname))
        if self.verbose:
            print(f"RPM build directories created in {self.release.rpmbuildDir}")

    def createSpecFile(self):
        # No error checking because we want to fail in case of errors

        # shutil.copyfile(self.specFileTemplate, self.specFile)
        # fdin = open(self.specFileTemplate, 'r')
        with open(self.specFileTemplate, encoding="utf-8") as fdin:
            lines = fdin.readlines()

        with open(self.specFile, "w", encoding="utf-8") as fdout:
            for line in lines:
                line = line.replace("__GWMS_RPM_VERSION__", self.release.rpmVersion)
                line = line.replace("__GWMS_RPM_RELEASE__", self.release.rpmRelease)
                fdout.write(line)

    def stageSources(self):
        dest_dir = os.path.join(self.release.rpmbuildDir, "SOURCES")
        # Copy the source tarball in place
        shutil.copy(
            os.path.join(self.release.releaseDir, self.releaseFilename), os.path.join(dest_dir, "glideinwms.tar.gz")
        )
        for f in self.sourceFilenames:
            shutil.copy(os.path.join(self.rpmPkgDir, f), dest_dir)

    def createRPMMacros(self):
        with open(self.rpmmacrosFile, "w") as fd:
            for m in self.rpmMacros:
                fd.write(f"%{m} {self.rpmMacros[m]}\n")

    def buildSRPM(self):
        cmd = "rpmbuild -bs %s" % self.specFile
        for m in self.rpmMacros:
            cmd = f'{cmd} --define "{m} {self.rpmMacros[m]}"'
        if self.verbose:
            print(f"Building source RPM: {cmd}")
        execute_cmd(cmd, timeout=self.release.timeout, is_debug=self.release.debug)

    def buildRPM(self):
        # Check if mock profiles changed
        # As of Dec 2024 on AlmaLinux9: alma+epel-..., rhel+epel-..., centos-stream+epel-...
        # No profile has epel-... (maybe rhel-7 for sl7)
        cmd = "mock -r {}-{}-x86_64 --macro-file={} -i {}".format(
            self.release.rpmOSVersion[2],
            self.release.rpmOSVersion[1],
            self.rpmmacrosFile,
            self.python_version,
        )
        if self.verbose:
            print(f"Build mock environment: {cmd}")
        execute_cmd(cmd, timeout=self.release.timeout, is_debug=self.release.debug)
        cmd = "mock --no-clean -r {}-{}-x86_64 --macro-file={} --resultdir={}/RPMS rebuild {}".format(
            self.release.rpmOSVersion[2],
            self.release.rpmOSVersion[1],
            self.rpmmacrosFile,
            self.release.rpmbuildDir,
            self.release.srpmFile,
        )
        if self.verbose:
            print(f"Build RPM with mock: {cmd}")
        execute_cmd(cmd, timeout=self.release.timeout, is_debug=self.release.debug)

    def buildRPMWithRPMBuild(self):
        cmd = "rpmbuild -bb %s" % self.specFile
        for m in self.rpmMacros:
            cmd = f'{cmd} --define "{m} {self.rpmMacros[m]}"'
        if self.verbose:
            print(f"Build RPM without mock: {cmd}")
        execute_cmd(cmd, timeout=self.release.timeout, is_debug=self.release.debug)

    def execute(self):
        if not self.release.buildRPMs:
            self.status = "SKIPPED"
        else:
            if self.verbose:
                print(
                    f"Building RPM (version:{self.release.rpmVersion}, release:{self.release.rpmRelease}, use_mock:{self.use_mock})"
                )
            # First build the source tarball
            # TaskTar.execute(self)

            # Create rpmbuild dir structure
            self.createRPMBuildDirs()
            # Create spec file from the template
            self.createSpecFile()
            # Stage source files
            self.stageSources()
            # Create rpmmacros file
            self.createRPMMacros()
            # Create the srpm
            self.buildSRPM()
            # Create the rpm
            if self.use_mock:
                self.buildRPM()
            else:
                self.buildRPMWithRPMBuild()
            self.status = "COMPLETE"


class PackageExcludes:
    """Defines patterns excluded from tarball files (all, only in Factory, only in Frontend)."""

    def __init__(self):
        # Patterns excluded from all tarballs
        self.commonPattern = [
            "CVS",
            ".DS_Store",
            ".editorconfig",
            ".git",
            ".gitattributes",
            ".github",
            ".gitignore",
            ".gitmodules",
            ".mailmap",
            ".pep8speaks.yml",
            ".pre-commit-config.yaml",
            ".prettierignore",
            ".reuse",
            ".ruff_cache",
            ".tox",
            ".travis.yml",
            "build",
            "test",
            "unittests",
            "tox.ini",
        ]

        # Patterns that need to be excluded from the factory tarball
        self.factoryPattern = self.commonPattern + [
            "poolwatcher",
            "frontend",
            "creation/create_frontend",
            "creation/reconfig_frontend",
            "creation/lib/cvW*",
            "creation/web_base/frontend*html",
            "creation/web_base/frontend*html",
        ]
        #    'glideinWMS/tools',

        # Patterns that need to be excluded from the frontend tarball
        # For frontend we still need 2 factory libs for frontend tools
        self.frontendPattern = self.commonPattern + [
            "poolwatcher",
            "factory",
            # "factory/check*",
            # "factory/glideFactory*Lib*",
            # "factory/glideFactoryMon*",
            # "factory/glideFactory.py",
            # "factory/glideFactoryEntry.py",
            # "factory/glideFactoryEntryGroup.py",
            # "factory/glideFactoryLog*.py",
            # "factory/test*",
            # "factory/manage*",
            # "factory/stop*",
            # "factory/tools",
            "creation/create_glidein",
            "creation/reconfig_glidein",
            "creation/info_glidein",
            "creation/lib/cgW*",
            "creation/web_base/factory*html",
            "creation/web_base/collector_setup.sh",
            "creation/web_base/condor_platform_select.sh",
            "creation/web_base/condor_startup.sh",
            "creation/web_base/create_mapfile.sh",
            "creation/web_base/singularity_setup.sh",
            "creation/web_base/gconfig.py",
            "creation/web_base/glidein_startup.sh",
            "creation/web_base/job_submit.sh",
            "creation/web_base/local_start.sh",
            "creation/web_base/setup_x509.sh",
            "creation/web_base/validate_node.sh",
        ]


############################################################
#
# P R I V A T E, do not use
#
############################################################


def create_dir(dirname, mode=0o755, error_if_exists=False):
    try:
        os.makedirs(dirname, mode=mode)
    except OSError as e:
        if (e.errno == 17) and (error_if_exists is False):
            print("Dir already exists reusing %s" % dir)
        else:
            raise
    except Exception:
        raise


# can throw ExeError
def execute_cmd(cmd, stdin_data=None, timeout=60, is_debug=False):
    """Execute a command in a shell using subprocess.Popen
    The initial directory is the one of the Python script
    (the final directory at the end of the subprocess does not matter)

    Args:
        cmd (str): string containing the command to execute
        stdin_data (str): optional text written to stdin
        timeout (int): command timeout in seconds. Defaults to 60
        is_debug (bool): print debug output if True

    Returns:
        str: stdout of the command
    Raises:
        ExeError: when the command fails. The message is the command stderr
    """
    if is_debug:
        print(f"About to run: {cmd}")
    child = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if stdin_data is not None:
        child.stdin.write(stdin_data)

    temp_out = child.stdout.readlines()
    temp_err = child.stderr.readlines()
    child.communicate(timeout=timeout)
    # child.childerr.close()
    try:
        errcode = child.wait(timeout)
    except OSError as e:
        if len(temp_out) != 0:
            # if there was some output, it is probably just a problem of timing
            # have seen a lot of those when running very short processes
            errcode = 0
        else:
            msg = f"Error running '{cmd}'\nStdout:{temp_out}\nStderr:{temp_err}\nException OSError: {e}"
            print(msg)
            raise ExeError(msg)
    if is_debug:
        print(f"Completed ({errcode}):{temp_out}\nStderr:{temp_err}")
    if errcode != 0:
        msg = f"Error running '{cmd}'\nStdout:{temp_out}\nStderr:{temp_err}\nException Error: {errcode}"
        print(msg)
        raise ExeError(msg)
    return temp_out


def which(program):
    """Implementation of which command in python.

    Args:
        program (str): Command to search in the PATH

    Returns:
        str: Path to the binary

    """

    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None
