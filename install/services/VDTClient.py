#!/bin/env python

import common
from VDT import VDT
#---------------------
import sys,os,os.path,string,time,glob


class VDTClient(VDT):
  def __init__(self,inifile):
    VDT.__init__(self,inifile)
    self.package = "client"
    self.vdt_services = ["fetch-crl", "vdt-rotate-logs", "vdt-update-certs",]

    #--------------------------
    #tested_platforms=('linux-rhel-3','SL-3','linux-rhel-4','SL-4','linux-fedora-4','linux-rhel-5','SL-5')
    #  platform_str="-pretend-platform %s"%platform
    self.vdt_packages = ['PPDG-Cert-Scripts','Globus-Client','VOMS-Client','MyProxy-Client','CA-Certificates-Updater']
    self.osg_packages = ['vo-client']

  #-------------------
  def install(self):
    if self.client_exists():
      common.logit("... client already installed")
      return
    packages = ""
    for package in self.vdt_packages:
      packages = packages + "%s:%s " % (self.vdt_cache(),package)
    for package in self.osg_packages:
      packages = packages + "%s:%s " % (self.osg_cache(),package)
    
    common.logit("======== VDT Client install starting ==========")
    for package in packages.split(" "):
      common.logit("%s" % package)
    self.install_vdt_package(packages)
    common.logit("======== VDT Client install complete ==========")

  #-------------------
  def client_exists(self):
    if not self.vdt_exists():
      return False
    err = os.system("source %s/setup.sh && type voms-proxy-init >/dev/null 2>&1" % self.vdt_location())
    if err != 0:
      return False
    return True


##########################################
def main(argv):
  try:
    inifile = "/home/weigand/weigand-glidein/glideinWMS.ini"
    client = VDTClient(inifile)
    client.install()
    print "Client exists: ",client.client_exists()
  except common.WMSerror:
    return 1

####################################
if __name__ == '__main__':
  sys.exit(main(sys.argv))


