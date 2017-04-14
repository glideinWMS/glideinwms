#!/usr/bin/python -B

import os, sys
import subprocess, shlex
import traceback
import string
import shutil
import platform
#from pylint import lint




class ExeError(RuntimeError):

    def __init__(self,str):
        RuntimeError.__init__(self,str)


class Release:

    def __init__(self, ver, srcDir, relDir, rc, rpmRel):

        self.version = self.createTarballVersionString(ver, rc)
        self.sourceDir = srcDir
        self.releaseDir = os.path.join(relDir, self.version)
        self.releaseWebDir = os.path.join(self.releaseDir, 'www')
        self.tasks = []
        self.rc = rc
        self.buildRPMs = False
        try:
            # RPM related info
            self.rpmRelease = self.createRPMReleaseNVR(rpmRel, rc)
            self.rpmVersion = self.versionToRPMVersion(ver)
            self.rpmbuildDir = os.path.join(self.releaseDir, 'rpmbuild')
            self.rpmOSVersion = self.getElVersion()
            self.srpmFile = os.path.join(
                self.rpmbuildDir, 'SRPMS',
                'glideinwms-%s-%s.%s%s.src.rpm' % (self.rpmVersion,
                self.rpmRelease, self.rpmOSVersion[0], self.rpmOSVersion[1]))
            self.buildRPMs = True
        except:
            print 'RPMs will not be build for this platform'


    def createTarballVersionString(self, ver, rc):
        ver_str = '%s' % ver
        if rc:
            ver_str = '%s_rc%s' % (ver, rc)
        return ver_str


    def versionToRPMVersion(self, ver):
        if ver.startswith('v'):
            ver = ver[1:]
        ver = ver.replace('_', '.')
        return ver


    def createRPMReleaseNVR(self, rpmRel, rc):
        nvr = '%s' % rpmRel
        if rc:
            nvr = '0.%s.rc%s' % (rpmRel, rc)
        return nvr


    def getElVersion(self):
        if platform.system() != 'Linux':
            raise Exception('Unsupported OS: %s' % platform.system())

        el_string = 'el'
        distname, version, id = platform.linux_distribution()
        distmap = {
            'Fedora': 'fc',
            'Scientific Linux': 'el',
            'Red Hat': 'el'
        }
        dist = None
        for d in distmap:
            if distname.startswith(d):
                dist = distmap[d]
                break
        if dist is None:
            raise Exception('Unsupported distribution: %s' % distname)
        else:
            el_string = dist
        major_version = version.split('.')[0]

        return (el_string, major_version)


    def addTask(self, task):
        self.tasks.append(task)
    #def printReport(self):
    #   for task in self.releaseTasks.keys():
    #        print print "TASK: %-30s STATUS: %s" % (task, (tasklist[]).status)
    # printReport


    def executeTasks(self):
        for i in range(0, len(self.tasks)):
            task = self.tasks[i]
            print "************* Executing %s *************" % (self.tasks[i]).name
            task.execute()
            print "************* %s Status %s *************" % ((self.tasks[i]).name, (self.tasks[i]).status)

    def printReport(self):
        print 35*"_"
        print "TASK" + 20*" " + "STATUS"
        print 35*"_"
        for i in range(0, len(self.tasks)):
            print "%-23s %s" % ((self.tasks[i]).name, (self.tasks[i]).status)
        print 35*"_"


class TaskRelease:

    def __init__(self, name, rel):
        self.name = name
        self.release = rel
        self.status = 'INCOMPLETE'
    #   __init__

    def execute(self):
        raise ExeError('Action execute not implemented for task %s' % self.name)
    #   execute


class TaskClean(TaskRelease):

    def __init__(self, rel):
        TaskRelease.__init__(self, 'Clean', rel)
    #   __init__

    def execute(self):
        cmd = 'rm -rf %s' % self.release.releaseDir
        execute_cmd(cmd)
        self.status = 'COMPLETE'
    #   execute


class TaskSetupReleaseDir(TaskRelease):

    def __init__(self, rel):
        TaskRelease.__init__(self, 'SetupReleaseDir', rel)
    #   __init__

    def execute(self):
        create_dir(self.release.releaseDir)
        create_dir(self.release.releaseWebDir)
        self.status = 'COMPLETE'
    #   execute


class TaskPylint(TaskRelease):

    def __init__(self, rel):
        TaskRelease.__init__(self, 'Pylint', rel)
        self.rcFile = os.path.join(sys.path[0], '../etc/pylint.rc')
        self.fileList = []
        self.pylintArgs = ['-e', '--rcfile=%s'%self.rcFile]
    #   __init__

    def callback(self, dir, files):
        for file in files:
            if (file.endswith('.py')):
                self.fileList.append(os.path.join(dir, file))

    def index(self):
        stack = [self.release.sourceDir]
        while stack:
            dir = stack.pop()
            for file in os.listdir(dir):
                fullname = os.path.join(dir, file)
                if (file.endswith('.py')):
                    self.fileList.append(os.path.join(dir, file))
                if os.path.isdir(fullname) and not os.path.islink(fullname):
                    stack.append(fullname)

    def pylint(self):
        lint.Run(self.pylintArgs + self.fileList)

    def pylint1(self):
        #print self.fileList
        for file in self.fileList:
            print "Running pylint on %s" % file
            print self.pylintArgs + [file]
            lint.Run(self.pylintArgs + [file])


    def execute(self):
        self.index()
        self.pylint()
        self.status = 'COMPLETE'
    #   execute


class TaskTar(TaskRelease):

    def __init__(self, rel):
        TaskRelease.__init__(self, 'GlideinWMSTar', rel)
        self.excludes = PackageExcludes()
        self.releaseFilename = 'glideinWMS_%s.tgz' % self.release.version
        self.excludePattern = self.excludes.commonPattern
        self.tarExe = which('tar')
    #   __init__

    def execute(self):
        exclude = ""
        if len(self.excludePattern) > 0:
            exclude = "--exclude='" +  string.join(self.excludePattern, "' --exclude='") + "'"
        #cmd = 'cd %s/..; /bin/tar %s -czf %s/%s glideinwms' % \
        #      (self.release.sourceDir, exclude, self.release.releaseDir, self.releaseFilename)
        src_dir = '%s/../src/%s' % (self.release.releaseDir,
                                    self.release.version)
        cmd = 'rm -rf %s; mkdir -p %s; cp -r %s %s/glideinwms; cd %s; %s %s -czf %s/%s glideinwms' % \
              (src_dir, src_dir, self.release.sourceDir, src_dir, src_dir, self.tarExe, exclude, self.release.releaseDir, self.releaseFilename)
        print "%s" % cmd
        execute_cmd(cmd)
        self.status = 'COMPLETE'
    #   execute


class TaskFrontendTar(TaskTar):

    def __init__(self, rel):
        TaskTar.__init__(self, rel)
        self.name = 'FrontendTar'
        self.releaseFilename = 'glideinWMS_%s_frontend.tgz' % self.release.version
        self.excludePattern = self.excludes.frontendPattern

    #   __init__


class TaskFactoryTar(TaskTar):

    def __init__(self, rel):
        TaskTar.__init__(self, rel)
        self.name = 'FactoryTar'
        self.releaseFilename = 'glideinWMS_%s_factory.tgz' % self.release.version
        self.excludePattern = self.excludes.factoryPattern

    #   __init__


class TaskVersionFile(TaskRelease):

    def __init__(self, rel):
        TaskRelease.__init__(self, 'VersionFile', rel)
        self.releaseChksumFile = os.path.normpath(
                                     os.path.join(self.release.sourceDir,
                                                  'etc/checksum'))
        self.frontendChksumFile = os.path.normpath(
                                     os.path.join(self.release.sourceDir,
                                                  'etc/checksum.frontend'))
        self.factoryChksumFile = os.path.normpath(
                                     os.path.join(self.release.sourceDir,
                                                  'etc/checksum.factory'))
        self.excludes =  PackageExcludes()
        self.checksumFilePattern = 'etc/checksum*'
        self.chksumBin = os.path.normpath(os.path.join(sys.path[0],
                                                       'chksum.sh'))


    def execute(self):
        self.checksumRelease(self.releaseChksumFile,
                             self.excludes.commonPattern)
        self.checksumRelease(self.frontendChksumFile,
                             self.excludes.frontendPattern)
        self.checksumRelease(self.factoryChksumFile,
                             self.excludes.factoryPattern)
        self.status = 'COMPLETE'


    def checksumRelease(self, chksumFile, exclude):
        excludePattern = self.checksumFilePattern + " install/templates CVS config_examples " 
        if len(exclude) > 0:
            excludePattern = "\"" + "%s "%excludePattern + string.join(exclude, " ") + "\""
        cmd = "cd %s; %s %s %s %s" % (self.release.sourceDir, self.chksumBin,
                                      self.release.version, chksumFile,
                                      excludePattern)
        #print "--- %s" % chksumFile
        #print "--- %s" % cmd
        execute_cmd(cmd)


class TaskRPM(TaskTar):

    def __init__(self, rel):
        TaskTar.__init__(self, rel)
        self.name = 'GlideinwmsRPM'
        self.releaseFile = os.path.join(self.release.releaseDir,
                                        self.releaseFilename)
        self.rpmPkgDir = os.path.join(self.release.sourceDir,
                                      'build/packaging/rpm')
        self.specFileTemplate = os.path.join(self.rpmPkgDir, 'glideinwms.spec')
        self.specFile = os.path.join(self.release.rpmbuildDir, 'SPECS',
                                     'glideinwms.spec')
        #self.rpmmacrosFile = os.path.join(os.path.expanduser('~'),
        self.rpmmacrosFile = os.path.join(os.path.dirname(self.release.rpmbuildDir),
                                          '.rpmmacros')
        self.sourceFilenames = [
            'chksum.sh', 'factory_startup', 'frontend_startup', 'factory_startup_sl7', 'frontend_startup_sl7',
            'frontend.xml', 'glideinWMS.xml', 'gwms-factory.conf.httpd',
            'gwms-factory.sysconfig', 'gwms-frontend.conf.httpd',
            'gwms-frontend.sysconfig'
        ]

        self.rpmMacros = {
            '_topdir': self.release.rpmbuildDir,
            '_tmppath': '/tmp',
            '_source_filedigest_algorithm': 'md5',
            '_binary_filedigest_algorithm': 'md5',
            #'global __python': '%%{__python2}',
            #'py_byte_compile': '',
            #%py_byte_compile %{__python2} %{buildroot}%{_datadir}/mypackage/foo
        }
    #   __init__


    def createRPMBuildDirs(self):
        # Create directories required by rpmbuild
        rpm_dirs = ['BUILD', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS']
        for dir in rpm_dirs:
            create_dir(os.path.join(self.release.rpmbuildDir, dir))


    def createSpecFile(self):
        # No error checking because we want to fail in case of errors

        #shutil.copyfile(self.specFileTemplate, self.specFile)
        fdin = open(self.specFileTemplate, 'r')
        lines = fdin.readlines()
        fdin.close()
        fdout = open(self.specFile, 'w')

        for line in lines:
            line = line.replace('__GWMS_RPM_VERSION__', self.release.rpmVersion)
            line = line.replace('__GWMS_RPM_RELEASE__', self.release.rpmRelease)
            fdout.write(line)
        fdout.close()


    def stageSources(self):
        dest_dir = os.path.join(self.release.rpmbuildDir, 'SOURCES')
        # Copy the source tarball in place
        shutil.copy(os.path.join(self.release.releaseDir, self.releaseFilename),
                    os.path.join(dest_dir, 'glideinwms.tar.gz'))
        for f in self.sourceFilenames:
            shutil.copy(os.path.join(self.rpmPkgDir, f), dest_dir)


    def createRPMMacros(self):
        fd = open( self.rpmmacrosFile, 'w')
        for m in self.rpmMacros:
            fd.write('%%%s %s\n' % (m,  self.rpmMacros[m]))
        fd.close()


    def buildSRPM(self):
        cmd = 'rpmbuild -bs %s' % self.specFile
        for m in self.rpmMacros:
            cmd = '%s --define "%s %s"' % (cmd, m, self.rpmMacros[m])
        execute_cmd(cmd)


    def buildRPM(self):
        cmd = 'mock -r epel-%s-x86_64 --macro-file=%s -i python' % (self.release.rpmOSVersion[1], self.rpmmacrosFile)
        execute_cmd(cmd)
        cmd = 'mock --no-clean -r epel-%s-x86_64 --macro-file=%s --resultdir=%s/RPMS rebuild %s' % (self.release.rpmOSVersion[1], self.rpmmacrosFile, self.release.rpmbuildDir, self.release.srpmFile)
        execute_cmd(cmd)


    def buildRPMWithRPMBuild(self):
        cmd = 'rpmbuild -bb %s' % self.specFile
        for m in self.rpmMacros:
            cmd = '%s --define "%s %s"' % (cmd, m, self.rpmMacros[m])
        execute_cmd(cmd)


    def execute(self):
        if self.release.buildRPMs == False:
            self.status = 'SKIPPED'
        else:
            # First build the source tarball
            #TaskTar.execute(self)

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
            self.buildRPM()
            self.status = 'COMPLETE'


class PackageExcludes:

    def __init__(self):

        self.commonPattern = [
            'CVS',
            '.git',
            '.gitattributes',
            '.DS_Store',
            'unittests',
            'build',
            #'install/glideinWMS.ini',
            #'install/manage-glideins',
            #'install/services',
        ]

        # Patterns that need to be excluded from the factory tarball
        self.factoryPattern = [
            'CVS',
            '.git',
            '.gitattributes',
            '.DS_Store',
            'poolwatcher',
            'frontend',
            'unittests',
            'build',
            #'install/glideinWMS.ini',
            #'install/manage-glideins',
            #'install/services',
            'creation/create_frontend',
            'creation/reconfig_frontend',
            'creation/lib/cvW*',
            'creation/web_base/frontend*html',
            'creation/web_base/frontend*html',
        ]
        #    'glideinWMS/tools',

        # Patterns that need to be excluded from the frontend tarball
        # For frontend we still need 2 factory libs for frontend tools
        self.frontendPattern = [
            'CVS',
            '.git',
            '.gitattributes',
            '.DS_Store',
            'poolwatcher',
            'unittests',
            'build',
            #'install/glideinWMS.ini',
            #'install/manage-glideins',
            #'install/services',
            'factory/check*',
            'factory/glideFactory*Lib*',
            'factory/glideFactoryMon*',
            'factory/glideFactory.py',
            'factory/glideFactoryEntry.py',
            'factory/glideFactoryEntryGroup.py',
            'factory/glideFactoryLog*.py',
            'factory/test*',
            'factory/manage*',
            'factory/stop*',
            'factory/tools',
            'creation/create_glidein',
            'creation/reconfig_glidein',
            'creation/info_glidein',
            'creation/lib/cgW*',
            'creation/web_base/factory*html',
            'creation/web_base/collector_setup.sh',
            'creation/web_base/condor_platform_select.sh',
            'creation/web_base/condor_startup.sh',
            'creation/web_base/create_mapfile.sh',
            'creation/web_base/gcb_setup.sh',
            'creation/web_base/glexec_setup.sh',
            'creation/web_base/glidein_startup.sh',
            'creation/web_base/job_submit.sh',
            'creation/web_base/local_start.sh',
            'creation/web_base/setup_x509.sh',
            'creation/web_base/validate_node.sh',
        ]

############################################################
#
# P R I V A T E, do not use
#
############################################################

def create_dir(dir, mode=0755, errorIfExists=False):
    try:
        os.makedirs(dir, mode=0755)
    except OSError as (errno, stderror):
        if (errno == 17) and (errorIfExists == False):
            print 'Dir already exists reusing %s' % dir
        else:
            raise
    except Exception:
            raise

# can throw ExeError
def execute_cmd(cmd, stdin_data=None):
    child = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if stdin_data!=None:
        child.stdin.write(stdin_data)

    tempOut = child.stdout.readlines()
    tempErr = child.stderr.readlines()
    child.communicate()
    #child.childerr.close()
    try:
        errcode = child.wait()
    except OSError, e:
        if len(tempOut) != 0:
            # if there was some output, it is probably just a problem of timing
            # have seen a lot of those when running very short processes
            errcode = 0
        else:
            msg = "Error running '%s'\nStdout:%s\nStderr:%s\nException OSError: %s"%(cmd,tempOut,tempErr,e)
            print msg
            raise ExeError, msg
    if (errcode != 0):
        msg = "Error running '%s'\nStdout:%s\nStderr:%s\nException Error: %s"%(cmd,tempOut,tempErr,errcode)
        print msg
        raise ExeError, msg
    return tempOut


def which(program):
    """
    Implementation of which command in python.

    @return: Path to the binary
    @rtype: string
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

