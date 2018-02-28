#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function
import traceback
import sys, os, os.path, string, time
import optparse

from . import common
from .Configuration import ConfigurationError
from .Configuration import Configuration
from .Configuration import ConfigurationError
from . import VDTClient

#STARTUP_DIR=sys.path[0]
#sys.path.append(os.path.join(STARTUP_DIR,"../lib"))

class Glidein(Configuration):

  def __init__(self, inifile, ini_section, ini_options):
    self.ini_section = ini_section
    self.inifile     = inifile
    Configuration.__init__(self, self.inifile)
    self.validate_section(self.ini_section, ini_options)

    self.vdt = None

    self.javascriptrrd_dir = None
    self.flot_dir          = None
    self.jquery_dir        = None

  #---------------------
  def get_vdt(self):
    if self.vdt == None:
      self.vdt = VDTClient.VDTClient(self.ini_section, self.inifile)
  #---------------------
  def vdt_location(self):
    self.get_vdt()
    return self.vdt.vdt_location()
  #---------------------
  def glideinwms_location(self):
    return self.option_value(self.ini_section, "glideinwms_location")
  #---------------------
  def install_vdt_client(self):
    return self.option_value(self.ini_section, "install_vdt_client")
  #---------------------
  def install_location(self):
    return self.option_value(self.ini_section, "install_location")
  #---------------------
  def username(self):
    return self.option_value(self.ini_section, "username")
  #---------------------
  def service_name(self):
    return self.option_value(self.ini_section, "service_name")
  #---------------------
  def instance_name(self):
    return self.option_value(self.ini_section, "instance_name")
  #---------------------
  def service_dir(self):
    return "%s/glidein_%s" % (self.install_location(), self.instance_name())
  #---------------------
  def hostname(self):
    return self.option_value(self.ini_section, "hostname")
  #---------------------
  def x509_gsi_dn(self):
    return self.option_value(self.ini_section, "x509_gsi_dn")
  #---------------------
  def use_glexec(self):
    return self.option_value(self.ini_section, "use_glexec")
  #---------------------
  def use_ccb(self):
    return self.option_value(self.ini_section, "use_ccb")
  #---------------------
  def ress_host(self):
    return self.option_value(self.ini_section, "ress_host")
  #---------------------
  def bdii_host(self):
    return self.option_value(self.ini_section, "bdii_host")
  #---------------------
  def entry_vos(self):
    return self.option_value(self.ini_section, "entry_vos")
  #---------------------
  def ress_vo_constraint(self):
    constraint = '(GlueCEInfoContactString=!=UNDEFINED)'
    if len(self.entry_vos()) > 0:
      vos = string.split(self.entry_vos(), ",")
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
      vos = string.split(self.entry_vos(), ",")
      constraint = '(|(GlueCEAccessControlBaseRule=VO:%s)' % vos[0]
      if len(vos) > 0:
        for vo in vos[1:]:
          constraint = constraint + '(GlueCEAccessControlBaseRule=VO:%s)' % vo.strip(' ')
        constraint = constraint + ')'
    return constraint
  #---------------------
  def entry_filters(self):
    return self.option_value(self.ini_section, "entry_filters")
  #---------------------
  def web_location(self):
    return self.option_value(self.ini_section, "web_location")
  #---------------------
  def web_url(self):
    return self.option_value(self.ini_section, "web_url")
  #---------------------
  def javascriptrrd_location(self):
    default = "/usr/share/javascriptrrd"
    location = self.option_value(self.ini_section, "javascriptrrd_location")
    if len(location) == 0:
      location = default
    return location

  #--------------------------------
  def __install_vdt_client__(self):
    if self.install_vdt_client() == "y":
      self.get_vdt()
      self.vdt.install()
    else:
      common.logit("... VDT client install not requested.")

  #---------------------
  def validate_web_location(self):
    dir = self.web_location()
    common.logit("... validating web_location: %s" % dir)
    common.make_directory(dir, self.username(), 0o755)
    for sdir_name in ("stage", "monitor"):
      sdir_fullpath=os.path.join(self.web_location(), sdir_name)
      common.make_directory(sdir_fullpath, self.username(), 0o755)


  #---------------------
  def validate_software_requirements(self):
    self.javascriptrrd_dir = self.set_javascriptrrd_dir("rrdMultiFile.js")
    self.jquery_dir        = self.set_javascriptrrd_dir("jquery.flot.tooltip.js")
    self.flot_dir          = self.set_javascriptrrd_dir("flot")
    self.verify_python_module("rrdtool")
    self.verify_python_module("M2Crypto")

  #-----------------------
  def verify_python_module(self, module):
    msg = "... validating %s: " % module
    if common.module_exists(module):
      msg += "available"
      common.logit(msg)
    else:
      common.logit(msg)
      common.logerr("This python module is required and not available.")

  #-----------------------
  def set_javascriptrrd_dir(self, filename):
    msg =  "... validating javascriptrrd_location for %s: " % filename
    fullpath = common.find_fullpath(self.javascriptrrd_location(), filename)
    if fullpath == None:
      common.logit(msg)
      common.logerr("""%s not found in %s path
Did you install the correct javascriptrrd rpm?
""" % (filename, self.javascriptrrd_location()))
    dir = os.path.dirname(fullpath)
    msg +="available"
    common.logit(msg)
    return dir

#---------------------------
def show_line():
    x = traceback.extract_tb(sys.exc_info()[2])
    z = x[len(x)-1]
    return "%s line %s" % (z[2], z[1])
#---------------------------
def validate_args(args):
    usage = """Usage: %prog --ini ini_file
    
This will install a Factory service for glideinWMS using the ini file
specified.
"""
    print(usage)
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
    valid_options = ["javascriptrrd_location", ]
    glidein = Glidein(options.inifile, "Factory", valid_options)
  except KeyboardInterrupt:
    common.logit("\n... looks like you aborted this script... bye.");
    return 1
  except EOFError:
    common.logit("\n... looks like you aborted this script... bye.");
    return 1
  except ConfigurationError as e:
    print();print("ConfigurationError ERROR(should not get these): %s"%e);return 1
  except common.WMSerror:
    print();return 1
  return 0

#--------------------------
if __name__ == '__main__':
  sys.exit(main(sys.argv))

