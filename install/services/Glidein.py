#!/bin/env python

import common
from Configuration import ConfigurationError

from Configuration import Configuration
from Configuration import ConfigurationError
import VDTClient
import traceback
import sys,os,os.path,string,time

#STARTUP_DIR=sys.path[0]
#sys.path.append(os.path.join(STARTUP_DIR,"../lib"))

class Glidein(Configuration):

  def __init__(self,inifile,ini_section,ini_options):
    self.ini_section = ini_section
    self.inifile     = inifile
    Configuration.__init__(self,inifile)
    self.validate_section(ini_section,ini_options)

    self.vdt = VDTClient.VDTClient(self.inifile)

  #---------------------
  def vdt_location(self):
    return self.vdt.vdt_location()
  #---------------------
  def glidein_install_dir(self):
    return self.option_value(self.ini_section,"glidein_install_dir")
  #---------------------
  def install_vdt_client(self):
    return self.option_value(self.ini_section,"install_vdt_client")
  #---------------------
  def install_location(self):
    return self.option_value(self.ini_section,"install_location")
  #---------------------
  def unix_acct(self):
    return self.option_value(self.ini_section,"unix_acct")
  #---------------------
  def service_name(self):
    return self.option_value(self.ini_section,"service_name")
  #---------------------
  def instance_name(self):
    return self.option_value(self.ini_section,"instance_name")
  #---------------------
  def service_dir(self):
    return "%s/%s_%s" % (self.install_location(),self.service_name(),self.instance_name())
  #---------------------
  def config_dir(self):
    return "%s.cfg" % (self.service_dir())
  #---------------------
  def config_file(self):
    return "%s/%s.xml" % (self.config_dir(),self.service_name())
  #---------------------
  def node(self):
    return self.option_value(self.ini_section,"node")
  #---------------------
  def gsi_authentication(self):
    return self.option_value(self.ini_section,"gsi_authentication")
  #---------------------
  def gsi_location(self):
    return self.option_value(self.ini_section,"cert_proxy_location")
  #---------------------
  def gsi_dn(self):
    return self.option_value(self.ini_section,"gsi_dn")
  #---------------------
  def use_vofrontend_proxy(self):
    return self.option_value(self.ini_section,"use_vofrontend_proxy")
  #---------------------
  def use_glexec(self):
    return self.option_value(self.ini_section,"use_glexec")
  #---------------------
  def use_ccb(self):
    return self.option_value(self.ini_section,"use_ccb")
  #---------------------
  def gcb_list(self):
    if self.option_value(self.ini_section,"gcb_list") == "n":
      return []
    return []
  #---------------------
  def ress_host(self):
    return self.option_value(self.ini_section,"ress_host")
  #---------------------
  def ress_constraint(self):
    return self.option_value(self.ini_section,"ress_constraint")
  #---------------------
  def bdii_host(self):
    return self.option_value(self.ini_section,"bdii_host")
  #---------------------
  def bdii_constraint(self):
    return self.option_value(self.ini_section,"bdii_constraint")
  #---------------------
  def ress_filter(self):
    return self.option_value(self.ini_section,"ress_filter")
  #---------------------
  def web_location(self):
    return self.option_value(self.ini_section,"web_location")
  #---------------------
  def web_url(self):
    return self.option_value(self.ini_section,"web_url")
  #---------------------
  def javascriptrrd(self):
    return self.option_value(self.ini_section,"javascriptrrd")
  #---------------------
  def flot(self):
    return self.option_value(self.ini_section,"flot")
  #---------------------
  def m2crypto(self):
    return self.option_value(self.ini_section,"m2crypto")
  #---------------------
  def javascriptrrd_tarball(self):
    return self.option_value(self.ini_section,"javascriptrrd_tarball")
  #---------------------
  def flot_tarball(self):
    return self.option_value(self.ini_section,"flot_tarball")
  #---------------------
  def m2crypto_tarball(self):
    return self.option_value(self.ini_section,"m2crypto_tarball")
  #---------------------
  def match_authentication(self):
    return self.option_value(self.ini_section,"match_authentication")

  #--------------------------------
  def __install_vdt_client__(self):
    if self.install_vdt_client() == "y":
      if self.vdt.client_exists():
        common.logit("... VDT client already exists: %s" % self.vdt.vdt_location())
      else:
        common.logit("... VDT client is not installed")
        self.vdt.install()
    else:
      common.logit("... VDT client install not requested.")

  #---------------------
  def validate_install(self):
    common.logit( "... validating")
    common.validate_node(self.node())
    common.validate_user(self.unix_acct())
    common.validate_gsi(self.gsi_dn(),self.gsi_authentication(),self.gsi_location())
    self.preinstallation_software_check()
    common.validate_install_location(self.install_location())

  #---------------------
  def preinstallation_software_check(self):
    common.logit("Pre-installation monitoring software check started")
    errors = 0
    #--- web location ---
    if not os.path.isdir(self.web_location()):
      common.logerr("... ERROR: web location does not exist: %s" % self.web_location())
    else:
      common.logit("... web location valid")

    ##-- rrdtool --
    module = "rrdtool"
    if common.module_exists(module):
      script = "rrdtool"
      err = os.system("which %s >/dev/null 2>&1" % script)
      if err == 0:
        common.logit("... %s available: " % (module))
        os.system("which %s " % script)
      else:
        errors = errors + 1
        common.logit("... ERROR: %s script needs to be available in PATH" % script)
    else:
      errors = errors + 1
      common.logit("... ERROR: %s not installed or not in PYTHONPATH" % module)

    ##-- M2Crypto --
    os.environ["PYTHONPATH"] = "%s:%s/%s" % (os.environ["PYTHONPATH"],self.m2crypto(),"usr/lib/python2.3/site-packages/")
    module = "M2Crypto"
    if common.module_exists(module):
      common.logit("... %s available" % module)
    else:
      errors = errors + 1
      common.logit("... ERROR: %s not installed or not in PYTHONPATH: %s" % (module,self.m2crypto()))

    ##-- javascriptrrd --
    filename = os.path.join(self.javascriptrrd(),"src/lib/rrdFile.js")
    if os.path.exists(filename):
      common.logit("... javascriptrrd available")
      common.logit(filename)
    else:
      errors = errors + 1
      common.logit("... ERROR: javascriptrrd not installed: %s not found" % filename)

    ##-- flot --
    filename =  os.path.join(self.flot(),"jquery.flot.js")
    if os.path.exists(filename):
      common.logit("... flot available")
      common.logit(filename)
    else:
      errors = errors + 1
      common.logit("... ERROR: flot not installed: %s not found" % filename)

    if errors > 0:
      common.logerr("%i required software modules not available." % errors)
    common.logit("Pre-installation monitoring software check completed")

    return 

  #---------------------
  def install_javascriptrrd(self):
    common.logit("... installing javascriptrrd")
    dir = (os.path.dirname(self.javascriptrrd()))
    common.make_directory(dir)
    tarball = self.javascriptrrd_tarball()
    if not os.path.exists(tarball):
      common.logerr("javascriptrrd tarball does not exist: %s" % tarball)
    common.logit("... using tarball: %s" % tarball)
    os.system("cd %s;tar zxf %s" % (dir,tarball))
    common.logit("... javascriptrrd installed")
    common.logit("")

  #---------------------
  def install_flot(self):
    common.logit("... installing flot")
    dir = (os.path.dirname(self.flot()))
    common.make_directory(dir)
    tarball = self.flot_tarball()
    if not os.path.exists(tarball):
      common.logerr("flot tarball does not exist: %s" % tarball)
    common.logit("... using tarball: %s" % tarball)
    os.system("cd %s;tar zxf %s" % (dir,tarball))
    common.logit("... flot installed")
    common.logit("")

  #---------------------
  def install_m2crypto(self):
    common.logit("... installing M2Crypto")
    dir = (os.path.dirname(self.m2crypto()))
    common.make_directory(dir)
    tarball = self.m2crypto_tarball()
    if not os.path.exists(tarball):
      common.logerr("M2Crypto tarball does not exist: %s" % tarball)
    common.logit("... using tarball: %s" % tarball)
    os.system("cd %s;tar zxf %s" % (dir,tarball))
    common.logit("... compiling M2Crypto")
    os.system("cd M2C*;python setup.py build")
    common.logit("... installing M2Crypto")
    os.system("cd %s*;python setup.py install --root %s" % (self.m2crypto(),self.m2crypto()))
    common.logit("... M2Crypto installed")
    common.logit("")

  #---------------------
  def create_web_directories(self):
    common.logit("Creating monitoring web directories in %s" % self.web_location())
    for sdir_name in ("stage","monitor"):
      sdir_fullpath=os.path.join(self.web_location(),sdir_name)
      if not os.path.exists(sdir_fullpath):
        try:
          os.mkdir(sdir_fullpath)
          common.logit("... %s created" % sdir_fullpath)
        except:
          common.logerr("Cannot create dir '%s'.\n.. %s must be writable by user %s." %s (dir_fullpath,self.web_location(),self.unix_acct()))
      else:
        common.logit("... %s already exists" % sdir_fullpath)
        #-- verify writable if aleady exists ---
        test_fname=os.path.join(sdir_fullpath,"test.txt")
        try:
          fd=open(test_fname,"w")
          fd.close()
          os.unlink(test_fname)
        except:
          common.logerr("web directory (%s) exists but not writable by user %s." %s (dir_fullpath,self.unix_acct()))
        yn = common.ask_yn("The %s directory already exists and may constain data.\nThis may cause a failure when you try to create the factory or frontend.\nDo you want to delete it." % sdir_fullpath)
        if yn == "y":
          err = os.system("rm -rf %s/*" % sdir_fullpath)
          if err != 0:
            common.logerr("Problem deleting %s files" % sdir_fullpath)
          common.logit("Files in %s  deleted\n" % sdir_fullpath)

#---------------------------
def show_line():
    x = traceback.extract_tb(sys.exc_info()[2])
    z = x[len(x)-1]
    return "%s line %s" % (z[2],z[1])
#---------------------------
def validate_args(args):
    import optparse
    usage = """Usage: %prog --ini ini_file
    
This will install a Factory service for glideinWMS using the ini file
specified.
"""
    print usage
    parser = optparse.OptionParser(usage)
    parser.add_option("-i", "--ini", dest="inifile",
                      help="ini file defining your configuration")
    (options, args) = parser.parse_args()
    if options.inifile == None:
        parser.error("--ini argument required")
    if not os.path.isfile(options.inifile):
      raise common.logerr("inifile does not exist: %s" % options.inifile)
    common.logit("Using ini file: %s" % options.inifile)
    return options

##########################################
def main(argv):
  try:
    options = validate_args(argv)
    valid_options = ["javascriptrrd",
"flot",
"m2crypto",
"javascriptrrd_tarball",
"flot_tarball",
"m2crypto_tarball",
]
    glidein = Glidein(options.inifile,"Factory",valid_options)
    #glidein.install_javascriptrrd()
    #glidein.install_flot()
    glidein.install_m2crypto()
  except KeyboardInterrupt:
    common.logit("\n... looks like you aborted this script... bye.");
    return 1
  except EOFError:
    common.logit("\n... looks like you aborted this script... bye.");
    return 1
  except ConfigurationError, e:
    print;print "ConfigurationError ERROR(should not get these): %s"%e;return 1
  except common.WMSerror:
    print;return 1
  return 0

#--------------------------
if __name__ == '__main__':
  sys.exit(main(sys.argv))

