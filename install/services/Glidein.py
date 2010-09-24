#!/usr/bin/env python

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

    self.vdt = VDTClient.VDTClient(self.ini_section,self.inifile)

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
    return "%s/glidein_%s" % (self.install_location(),self.instance_name())
  #---------------------
  def config_dir(self):
    return "%s/glidein_%s.cfg" % (self.install_location(),self.instance_name())
  #---------------------
  def config_file(self):
    return "%s/factory.xml" % (self.config_dir())
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
  def bdii_host(self):
    return self.option_value(self.ini_section,"bdii_host")
  #---------------------
  def entry_vos(self):
    return self.option_value(self.ini_section,"entry_vos")
  #---------------------
  def ress_vo_constraint(self):
    constraint = '(GlueCEInfoContactString=!=UNDEFINED)'
    if len(self.entry_vos()) > 0:
      vos = string.split(self.entry_vos(),",")
      if len(vos) > 0:
        constraint = constraint + '&&('
        constraint = constraint + 'StringlistMember("VO:%s",GlueCEAccessControlBaseRule)' % vos[0].strip(' ')
        for vo in vos[1:]:
          constraint = constraint + '||StringlistMember("VO:%s",GlueCEAccessControlBaseRule)' % vo.strip(' ')
        constraint = constraint + ')'
    return constraint
  #---------------------
  def bdii_vo_constraint(self):
    constraint = None 
    if len(self.entry_vos()) > 0:
      vos = string.split(self.entry_vos(),",")
      constraint = '(|(GlueCEAccessControlBaseRule=VO:%s)' % vos[0]
      if len(vos) > 0:
        for vo in vos[1:]:
          constraint = constraint + '(GlueCEAccessControlBaseRule=VO:%s)' % vo.strip(' ')
        constraint = constraint + ')'
    return constraint
  #---------------------
  def entry_filters(self):
    return self.option_value(self.ini_section,"entry_filters")
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
      self.vdt.install()
    else:
      common.logit("... VDT client install not requested.")

  #---------------------
  def validate_install(self):
    common.validate_node(self.node())
    common.validate_user(self.unix_acct())
    common.validate_installer_user(self.unix_acct())
    self.validate_web_location()
    common.validate_gsi(self.gsi_dn(),self.gsi_authentication(),self.gsi_location())
    self.preinstallation_software_check()
    common.validate_install_location(self.install_location())

  #---------------------
  def validate_web_location(self):
    dir = self.web_location()
    common.logit("... validating web_location: %s" % dir)
    if not os.path.isdir(dir):
      common.logerr("web location (%s) does not exist.\n       It needs to be owned and writable by user(%s)" % (dir,self.unix_acct()))
    if common.not_writeable(dir):
      common.logerr("web location (%s) has wrong\n       ownership/permissions. It needs to be owned and writable by user(%s)" % (dir,self.unix_acct()))

  #---------------------
  def preinstallation_software_check(self):
    errors = 0
    ##-- rrdtool --
    msg = ""
    module = "rrdtool"
    if common.module_exists(module):
      script = "rrdtool"
      err = os.system("which %s >/dev/null 2>&1" % script)
      if err == 0:
        msg = "available"
      else:
        errors = errors + 1
        msg = "ERROR: %s script needs to be available in PATH" % script
    else:
      errors = errors + 1
      msg = "ERROR: %s not installed or not in PYTHONPATH" % module
    common.logit("... validating rrdtool: %s" % msg)

    ##-- M2Crypto --
    msg = ""
    os.environ["PYTHONPATH"] = "%s:%s/%s" % (os.environ["PYTHONPATH"],self.m2crypto(),"usr/lib/python2.3/site-packages/")
    module = "M2Crypto"
    if common.module_exists(module):
      msg = "available"
    else:
      errors = errors + 1
      msg = "ERROR: %s not installed or not in PYTHONPATH: %s" % (module,self.m2crypto())
    common.logit("... validating M2Crypto: %s" % msg)

    ##-- javascriptrrd --
    msg = ""
    filename = os.path.join(self.javascriptrrd(),"src/lib/rrdMultiFile.js")
    if os.path.exists(filename):
      msg = "available in %s" % filename
    else:
      errors = errors + 1
      msg = "ERROR: not installed: %s not found" % filename
    common.logit("... validating javascriptrrd: %s" % msg)

    ##-- flot --
    msg = ""
    filename =  os.path.join(self.flot(),"jquery.flot.js")
    if os.path.exists(filename):
      msg = "available in %s" % filename
    else:
      errors = errors + 1
      msg = "ERROR: not installed: %s not found" % filename
    common.logit("... validating flot: %s" % msg)

    if errors > 0:
      common.logerr("%i required software modules not available." % errors)

    return 

  #---------------------
  def install_javascriptrrd(self):
    common.logit("... installing javascriptrrd")
    dir = (os.path.dirname(self.javascriptrrd()))
    common.make_directory(dir,self.unix_acct(),0755,empty_required=True)
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
    common.make_directory(dir,self.unix_acct(),0755,empty_required=True)
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
    common.make_directory(dir,self.unix_acct(),0755,empty_required=True)
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
    common.logit("\nCreating monitoring web directories in %s" % self.web_location())
    for sdir_name in ("stage","monitor"):
      sdir_fullpath=os.path.join(self.web_location(),sdir_name)
      common.make_directory(sdir_fullpath,self.unix_acct(),0755,empty_required=True)
    common.logit("\nCreating monitoring web directories completed %s\n" % self.web_location())

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

