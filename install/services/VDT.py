#!/bin/env python

import common
from Configuration import Configuration
#---------------------
import sys,os,os.path,string,time,glob

valid_options = [ "vdt_location",
"pacman_version",
"pacman_url",
"pacman_location",
]

class VDT(Configuration):
  def __init__(self,inifile):
    self.vdt_section = "VDT"
    Configuration.__init__(self,inifile)
    self.validate_section(self.vdt_section,valid_options)
    self.vdt_services = ["fetch-crl", "vdt-rotate-logs", "vdt-update-certs",]

  #--------------------------
  def install_vdt_package(self,packages):
#    if self.vdt_exists():
#      common.logerr("... VDT pacman installation already exists: %s" % self.vdt_location())
    self.__install_pacman__()
    common.make_directory(self.vdt_location(),self.unix_acct(),0755,empty_directory=True)
    #-- pacman get ---
    common.run_script("export VDTSETUP_AGREE_TO_LICENSES=y; source %s/setup.sh && cd %s && pacman -trust-all-caches -get %s" % (self.pacman_location(),self.vdt_location(),packages))
    #--- vdt-post-install --
    common.run_script("source %s/setup.sh && vdt-post-install" % (self.vdt_location()))

  #-------------------
  def vdt_exists(self):
    if os.path.isdir(self.vdt_location):
      if os.path.isfile("%s/%s" % self.vdt_location(),"setup.sh"):
        return True
    return False
  #-------------------------
  def osg_cache(self):
    return "http://software.grid.iu.edu/osg-1.2"
    #  return "OSG"
  #-------------------------
  def vdt_cache(self):
    return "http://vdt.cs.wisc.edu/vdt_200_cache"
    # return "http://vdt.cs.wisc.edu/vdt_1101_cache"
  #-------------------------
  def vdt_location(self):
    return self.option_value(self.vdt_section,"vdt_location")
  #-------------------
  def vdt_exists(self):
    if os.path.isdir(self.vdt_location()):
      if os.path.isfile("%s/%s" % (self.vdt_location(),"setup.sh")):
        return True
    return False

  #----------------
  # pacman methods
  #----------------
  #-------------------------
  def __install_pacman__(self):
    """ Installs pacman if not present. """
    if self.pacman_is_installed():
      common.logit("... %s already installed in %s" % (self.pacman_version(),self.pacman_location()))
    else: 
      common.logit("======== pacman install starting ==========")
      common.make_directory(self.pacman_parent(),self.unix_acct(),0755,empty_directory=True)
      common.logit("Installing pacman: %s" % (self.pacman_version()))
      common.run_script("cd %s && wget %s/%s.tar.gz && tar --no-same-owner -xzvf %s.tar.gz && rm -f  %s.tar.gz" %
        (self.pacman_parent(),self.pacman_url(),self.pacman_version(),self.pacman_version(),self.pacman_version()))
      if not self.pacman_is_installed():
        common.logerr("%s install failed.  No setup.sh file exists" % self.pacman_version)
      common.run_script("cd %s && source setup.sh" % (self.pacman_location()))
      common.logit("\n%s install complete" % self.pacman_version())
      common.logit("   in %s" % self.pacman_location())
      common.logit("======== pacman install complete ==========")
  #-------------------------
  def pacman_version(self):
    return self.option_value(self.vdt_section,"pacman_version")
  #-------------------------
  def pacman_url(self):
    return self.option_value(self.vdt_section,"pacman_url")
  #-------------------------
  def pacman_parent(self):
    return self.option_value(self.vdt_section,"pacman_location")
  #-------------------------
  def pacman_location(self):
    return "%s/%s" % (self.pacman_parent(),self.pacman_version())
  #-------------------------
  def pacman_is_installed(self):
    if os.path.isfile("%s/setup.sh" % self.pacman_location()):
      return True
    return False


##########################################
def main(argv):
  try:
    inifile = "/home/weigand/weigand-glidein/glideinWMS.ini"
    certs = Certificates(inifile,"WMSCollector")
    certs.install()
  except common.WMSerror:
    return 1

####################################
if __name__ == '__main__':
  sys.exit(main(sys.argv))


