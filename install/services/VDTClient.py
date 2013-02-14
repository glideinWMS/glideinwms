#!/usr/bin/env python

import sys
import os
import os.path
import string
import time
import glob
#---------------------
from glideinwms.install.services import common
from glideinwms.install.services.VDT import VDT


class VDTClient(VDT):
  def __init__(self,section,inifile):
    VDT.__init__(self,section,inifile)
    self.vdt_services = ["fetch-crl", "vdt-rotate-logs", "vdt-update-certs",]

    #--------------------------
    #tested_platforms=('linux-rhel-3','SL-3','linux-rhel-4','SL-4','linux-fedora-4','linux-rhel-5','SL-5')
    #  platform_str="-pretend-platform %s"%platform
    self.vdt_packages = ['PPDG-Cert-Scripts','Globus-Client','VOMS-Client','MyProxy-Client','CA-Certificates-Updater']
    self.osg_packages = ['vo-client']

  #-------------------
  def install(self):
    common.logit("\nVerifying VDT client installation")
    common.logit("... validating vdt_location: %s" % self.vdt_location())
    common.check_for_value("vdt_location",self.vdt_location())
    if self.client_exists():
      common.logit("... installed in: %s" % self.vdt_location())
      return
    common.ask_continue("""... VDT client not found in: %s
This script is checking for the presence of 2 scripts:
  setup.sh and voms-proxy-init 
Is it OK to install it in this location""" % self.vdt_location())
    packages = ""
    for package in self.vdt_packages:
      packages = packages + "%s:%s " % (self.vdt_cache(),package)
    for package in self.osg_packages:
      packages = packages + "%s:%s " % (self.osg_cache(),package)
    
    common.logit("\n======== VDT Client install starting ==========")
    common.logit("The packages that will be installed are:")
    for package in packages.split(" "):
      common.logit("  %s" % package)
    self.install_vdt_package(packages)
    if self.client_exists():
      common.logit("... VDT client installation looks good")
    common.logit("======== VDT Client install complete ==========\n")
    common.ask_continue("Continue installation")

  #-------------------
  def client_exists(self):
    if not self.vdt_exists():
      return False

    err = 0
    if self.vdt_install_type == 'pacman':
      err = os.system(". %s/setup.sh && type voms-proxy-init >/dev/null 2>&1" % self.vdt_location())
    elif self.vdt_install_type == 'native':
      err = 0
    else:
      err = 1
    if err == 0:
      return True
    return False

##########################################
def main(argv):
  try:
    inifile = "/home/weigand/glidein/glideinWMS/install/weigand.ini"
    client = VDTClient("WMSCollector",inifile)
    client.install()
    print "Client exists: ",client.client_exists()
  except common.WMSerror:
    return 1
  except KeyboardInterrupt:
    common.logit("\n... looks like you aborted this script... bye.")
    return 1

####################################
if __name__ == '__main__':
  sys.exit(main(sys.argv))
