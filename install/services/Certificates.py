#!/bin/env python

import common
from VDT import VDT
#---------------------
import sys,os,os.path,string,time,glob

#import shutil
#import tarfile,readline,pwd
#import md5
#import getpass
#import re
#import xml.sax.saxutils
#import socket
#import stat
#import httplib
#import ftplib
#STARTUP_DIR=sys.path[0]
#sys.path.append(os.path.join(STARTUP_DIR,"../lib"))


class Certificates(VDT):
  def __init__(self,inifile,service):
    ini_section = "Certificates"
    VDT.__init__(self,inifile)
#    self.validate_section(ini_section,valid_options)
    self.cert_dir         = self.option_value(service,"certificates")

    self.package = "%s:CA-Certificates" % (self.vdt_cache())
    self.vdt_services = ["fetch-crl", "vdt-rotate-logs", "vdt-update-certs",]
   
  #-------------------
  def install(self):
    if self.certificates_exist():
      common.logit("... certificates already installed")
    else:
      common.logit("======== CA certificates install starting ==========")
      common.logit("%s" % self.package)
      self.install_vdt_package(self.package)
      common.logit("... retrieving certificates") 
      common.run_script("source %s/setup.sh; %s/vdt/bin/vdt-ca-manage setupca --location %s --url osg" % (self.vdt_location(),self.vdt_location(),self.cert_dir))
      self.create_crontab()
      common.logit("======== CA certificates install complete ==========")

  #-------------------
  def create_crontab(self):
    """ If installed as root, then the vdt-control script can be used.
        Otherwise, the crontab has to updated with a little more 
        difficulty with this method.

    """
    common.logit("... creating crontab entries")
#    if os.getuid() == 0:
#      for service in self.vdt_services:
#        self.enable_vdt_service(service)
#    else:
#
     # extract the lines to put in cron
    services_file = "%s/vdt/services/state" % (self.vdt_location())
    fd=open(services_file,'r')
    try:
      lines = fd.readlines()
    finally:
      fd.close()
    #except:
    #  common.logerr("Unable to read VDT services file: " % services)
    cron_lines=[]
    for line in lines:
      line = line.replace("\t"," ")
      els = line.split(None,9)
      if len(els) != 10:
        continue # ignore, not a good line
      if (els[1] != 'cron'):
        continue # not a cron line
      cron_lines.append(string.join(els[4:]))
      # -- also run it once by hand --
      common.logit("... testing %s" % (els[0]))
      common.run_script(els[9])
    # -- add them to cron --
    common.cron_append(cron_lines,tmp_dir=self.vdt_location())

  #-------------------
  def certificates_exist(self):
    """ Returns true of certificates already exist. """
    files = glob.glob(os.path.join(self.certificate_dir(), '*.0'))
    if len(files) == 0:
      return False
    return True

  #-------------------
  def certificate_dir(self):
    """ The certificates directory is determined by the VDT. 
        We have to get it from the X509 vaariable.
    """
    return os.path.join(self.cert_dir, 'certificates')

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


