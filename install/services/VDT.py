#!/usr/bin/env python

import common
from Configuration import Configuration
#---------------------
import sys
import os
import os.path
import pwd
import string
import time
import glob

valid_options = [ "vdt_location",
"pacman_location",
"pacman_url",
]

class VDT(Configuration):
  def __init__(self,section,inifile):
    self.section = section 
    Configuration.__init__(self,inifile)
    self.validate_section(self.section,valid_options)
    self.vdt_services  = ["fetch-crl", "vdt-rotate-logs", "vdt-update-certs",]
    self.messagesDict = { "pacman_url"      : self.pacman_url(),
                          "pacman_urlfile"  : self.pacman_urlfile(),
                          "pacman_location" : self.pacman_location(),
                          "pacman_parent"   : self.pacman_parent(),
                          "pacman_tarball"  : self.pacman_tarball(),
                          "vdt_location"    : self.vdt_location(),
                          }
    # Means to identify if this is a native (rpm/deb) installation of vdt
    # self.vdt_install_type = 'pacman | 'native'
    self.vdt_install_type = 'pacman'

  #-------------------------
  def osg_cache(self):
    return "http://software.grid.iu.edu/osg-1.2"
  #-------------------------
  def vdt_cache(self):
    return "http://vdt.cs.wisc.edu/vdt_200_cache"
  #-------------------------
  def username(self):
    return pwd.getpwuid(os.getuid())[0]
  #-------------------------
  def vdt_location(self):
    return  self.option_value(self.section,"vdt_location")
  #-------------------------
  def pacman_url(self):
    return  self.option_value(self.section,"pacman_url")
  #-------------------------
  def pacman_location(self):
    return self.option_value(self.section,"pacman_location")
  #-------------------------
  def pacman_version(self):
    return os.path.basename(self.pacman_location())
  #-------------------------
  def pacman_tarball(self):
    return "%s.tar.gz" % self.pacman_version()
  #-------------------------
  def pacman_urlfile(self):
    return  "%s/%s" % (self.pacman_url(),self.pacman_tarball())
  #-------------------------
  def pacman_parent(self):
    return os.path.dirname(self.pacman_location())
  #-------------------------
  def pacman_is_installed(self):
    common.check_for_value("pacman_location",self.pacman_location())
    if os.path.isfile("%s/setup.sh" % self.pacman_location()):
      return True
    return False
  #-------------------
  def vdt_exists(self):
    # VDT pacman install
    if os.path.isdir(self.vdt_location()):
      if os.path.isfile("%s/%s" % (self.vdt_location(),"setup.sh")):
        return True

    # VDT rpm/native install
    if os.path.exists('/usr/bin/osg-version'):
        vdt_install_type = 'native'
        return True

    return False

  #--------------------------
  def install_vdt_package(self,packages):
    """ Installs specified VDT packages. """
    self.install_pacman()
    common.logit("... validating vdt_location: %s" % self.vdt_location())
    common.check_for_value("vdt_location",self.vdt_location())
    common.make_directory(self.vdt_location(),self.username(),0755)
    #-- install vdt packages ---
    self.messagesDict["packages"] = packages
    common.logit("... installing VDT packages")
    common.run_script("export VDTSETUP_AGREE_TO_LICENSES=y; . %(pacman_location)s/setup.sh && cd %(vdt_location)s && pacman -trust-all-caches -get %(packages)s" % self.messagesDict)
    #--- vdt-post-install --
    common.run_script(". %(vdt_location)s/setup.sh && vdt-post-install" % self.messagesDict)

  #-------------------------
  def install_pacman(self):
    """ Installs pacman if not present. """
    common.logit("... validating pacman_location: %s" % self.pacman_location())
    common.check_for_value("pacman_location",self.pacman_location())
    if self.pacman_is_installed():
      os.system("sleep 2")
      return #-- no need to install pacman--
    common.ask_continue("""
Pacman is required and does not appear to be installed in:
  %(pacman_location)s
... continue with pacman installation""" % self.messagesDict )
    common.logit("""
======== pacman install starting ========== """)
    common.check_for_value("pacman_location",self.pacman_location())
    if os.path.exists(self.pacman_location()):
      common.logerr("""The pacman_location for the pacman installation already exists 
and should not.  This script was looking for a setup.sh in that directory 
and it did not exist.  If a valid pacman distribution, it may be corrupt or the 
pacman_location  is incorrect.  Please verify.""") 
    common.logit("... validating pacman_url: %s" % self.pacman_url())
    common.check_for_value("pacman_url",self.pacman_url())
    if not common.wget_is_valid(self.pacman_urlfile()):
      common.logerr("""A pacman tarball of this name does not exist at:
    %(pacman_urlfile)s
... please verify.""" %  self.messagesDict)
    os.system("sleep 2")
    common.make_directory(self.pacman_parent(),self.username(),0755)
    common.run_script("cd %(pacman_parent)s && wget %(pacman_urlfile)s && tar --no-same-owner -xzf %(pacman_tarball)s && rm -f  %(pacman_tarball)s" % self.messagesDict)
    if not self.pacman_is_installed():
      common.logerr("Pacman install failed. No setup.sh file exists in: %(pacman_location)s" % self.messagesDict)
    common.logit("""... pacman requires the setup script to be sourced to initialize 
    some variables in it for subsequent use.""")
    common.run_script("cd %(pacman_location)s && . setup.sh" % self.messagesDict)
    common.logit("\nPacman successfully installed: %(pacman_location)s" % self.messagesDict)
    common.logit("======== pacman install complete ==========\n")
    os.system("sleep 2")

##########################################
def main(argv):
  try:
    section = "WMSCollector"
    inifile = "/home/weigand/glidein-ini/glidein-all-xen21-doug.ini"
    vdt = VDT(section, inifile)
    vdt.install_pacman()
  except common.WMSerror:
    return 1

####################################
if __name__ == '__main__':
  sys.exit(main(sys.argv))


