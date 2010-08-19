#!/bin/env python

import common
from VDT import VDT
#---------------------
import sys,os,os.path,string,time,glob,pwd

#STARTUP_DIR=sys.path[0]
#sys.path.append(os.path.join(STARTUP_DIR,"../lib"))


class Certificates(VDT):
  def __init__(self,inifile,section):
    self.ini_section = section
    VDT.__init__(self,self.ini_section,inifile)

    self.package = "%s:CA-Certificates" % (self.vdt_cache())
    self.vdt_services = ["fetch-crl", "vdt-rotate-logs", "vdt-update-certs",]
   
  #-------------------
  def certificates(self):
    return self.option_value(self.ini_section,"certificates")

  #-------------------
  def install(self):
    common.logit("\nVerifying CA Certificates installation")
    if self.certificates_exist():
      common.logit("... CA Certificates found in: %s" % self.certificate_dir())
      return
    common.ask_continue("""... CA Certificates not found in: %s
This script is checking for the presence of CA (*.0) and CRL (*.r0) files.
Is it OK to install it in this location""" % self.certificate_dir())
    common.logit("\n======== CA certificates install starting ==========")
    common.logit("The packages that will be installed are:")
    common.logit("  %s" % self.package)
    self.install_vdt_package(self.package)
    common.logit("... retrieving certificates") 
    common.run_script("source %s/setup.sh; %s/vdt/bin/vdt-ca-manage setupca --location %s --url osg" % (self.vdt_location(),self.vdt_location(),self.certificates()))
    self.create_crontab()
    if self.certificates_exist():
      common.logit("... certificate installation looks good")
    common.logit("======== CA certificates install complete ==========\n")
    common.ask_continue("Continue installation")

  #-------------------
  def create_crontab(self):
    """ Using the vdt-control script, enable and activate the crontab entries.
    """
    common.logit("... creating crontab entries using vdt-control script")
    #-- if not root, VDT requires a special arg to enable or activate a service
    if os.getuid() == 0:
      non_root_arg = ""
    else:
      non_root_arg = " --non-root"

    for service in self.vdt_services:
      common.logit("\n...... %s" % service)
      common.run_script("source %s/setup.sh;vdt-control %s --enable %s;vdt-control %s --on %s" % (self.vdt_location(),non_root_arg,service,non_root_arg,service))
    common.logit("\nvdt-control --list")
    os.system("source %s/setup.sh;vdt-control --list" % self.vdt_location())

    #-- show the cron entries added - extract the lines put in cron
    common.logit("\n... %s crontab entries:" % pwd.getpwuid(os.getuid())[0])
    services_file = "%s/vdt/services/state" % (self.vdt_location())
    try:
      fd = open(services_file,'r')
      lines = fd.readlines()
    except:
      common.logerr("Unable to read VDT services file: %s" % services_file)
    fd.close()
    fetch_crl_script = None
    for line in lines:
      els = line.split("\t")
      if (els[1] != 'cron'):
        continue # not a cron line
      if els[0] in self.vdt_services:
         common.logit("  %s %s" % (els[4],els[5].rstrip()))
      if els[0] == "fetch-crl":
        fetch_crl_script = els[5].rstrip()
    common.ask_continue("""\n... the glidein services require that CRL files (*.r0) be present
in the certificates directory.  Is it OK to run the script now?""")
    if fetch_crl_script == None:
      common.logerr("We have a problem.  There does not appear to be a cron entry for the CRL retrieval")
    common.run_script(fetch_crl_script) 
    common.logit("")

  #-------------------
  def certificates_exist(self):
    """ Returns true of certificates already exist. """
    ca_files = glob.glob(os.path.join(self.certificate_dir(), '*.0'))
    crl_files = glob.glob(os.path.join(self.certificate_dir(), '*.r0'))
    if len(ca_files) > 0:
      if len(crl_files) > 0:
        return True
      common.logerr("""The certificates directory contains CA (*.0) files but 
no CRL (*.r0) files.  This is not a satifactory condition.
Suggest you check this out before proceeding:
   %s""" % self.certificate_dir())
    #-- checking for other files to insure we are in the correct directory
    files = glob.glob(os.path.join(self.certificate_dir(), '*'))
    if len(files) > 0:
      common.logerr("""CA Certificates files (*.0) do not exist in certificates
directory BUT some other files do exist.  This does not make sense. 
Suggest you check this out before proceeding:
   %s""" % self.certificate_dir())
    #-- looks good.. we can proceed with an install
    return False

  #-------------------
  def certificate_dir(self):
    """ The certificates directory is determined by the VDT. 
        We have to get it from the X509 vaariable.
    """
    return os.path.join(self.certificates(), 'certificates')

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


