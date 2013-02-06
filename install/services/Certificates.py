#!/usr/bin/env python

import common
from VDT import VDT
#---------------------
import sys
import os
import os.path
import string
import time
import glob
import pwd
import commands

#STARTUP_DIR=sys.path[0]
#sys.path.append(os.path.join(STARTUP_DIR,"../lib"))


class Certificates(VDT):
  def __init__(self,inifile,section):
    self.ini_section = section
    VDT.__init__(self,self.ini_section,inifile)
    self.option = "x509_cert_dir"
    self.package = "%s:CA-Certificates" % (self.vdt_cache())
    self.vdt_services = ["fetch-crl", "vdt-rotate-logs", "vdt-update-certs",]
   
  #-------------------
  def x509_cert_dir(self):
    """ Returns the full path the X509 certificates directory.  """
    cert_dir = self.option_value(self.ini_section,self.option)
    common.check_for_value("x509_cert_dir",cert_dir)
    return cert_dir

    ## ---------------------------------------------------------------------
    ## --- leaving this code here in the event it becomes a requirement the
    ## --- x509_cert_dir option is allowed to be empty.  I think it is not
    ## --- a good idea to do this.  It hides things when one does.
##        Population of the  x509_cert_dir option is optional.
##        If populated, it will be used.
##        If not populated, it will be assumed to be an OSG/VDT CA installation
##        and the value will be obtained from the X509_CERT_DIR variable set
##        in the VDT setup.sh script.
    ##if len(cert_dir) == 0:
    ##  cert_dir = self.get_x509_cert_dir_value()
    ##  if len(cert_dir) == 0:
    ##    common.logerr("""The %(option)s was empty and certificates do not appear to be 
##installed as a part of a VDT install based on your vdt_location option: 
##  %(vdt_location)s""" % \
##            { "option"       : self.option,
##              "vdt_location" : self.vdt_location(),})
    ## ---------------------------------------------------------------------

  #-------------------
  def install(self):
    """ Installs the VDT CA package if X509 CA certiificates do not already
        exist. 
    """
    common.logit("\nVerifying CA Certificates installation")
    common.logit("... validating %(option)s: %(dir)s" % \
                       { "option" : self.option,
                         "dir"    : self.x509_cert_dir()})
    if self.certificates_exist():
      common.logit("... CA Certificates exist with *.0 and *.r0 files")
      return
    common.ask_continue("""There were no certificate (*.0) or CRL (*.r0) files found.
These can be installed from the VDT using pacman.  
If you want to do this, these options must be set:
  vdt_location  pacman_url  pacman_location
Additionally your %(option)s should specify this location: 
   vdt_location/globus/TRUSTED_CA 
Is it OK to proceed with the installation of certificates with these settings.
If not, stop and correct the %(option)s""" % { "option"       : self.option, })

    common.logit("... verifying vdt_location: %s" % self.vdt_location())
    common.check_for_value("vdt_location",self.vdt_location())
    common.logit("... verifying pacman_location: %s" % self.pacman_location())
    common.check_for_value("pacman_location",self.pacman_location())
    common.logit("... verifying pacman_url: %s" % self.pacman_url())
    common.check_for_value("pacman_url",self.pacman_url())

    expected_x509_cert_dir = "%s/globus/TRUSTED_CA" % self.vdt_location()
    if self.x509_cert_dir() != expected_x509_cert_dir:
      common.logerr("""Sorry but the %(option)s must be set to %(expected)s""" % \
                       { "option"  : self.option,
                         "expected" : expected_x509_cert_dir,} )

    if common.not_writeable(os.path.dirname(self.vdt_location())):
      common.logerr("""You do not have permissions to create the vdt_location 
option specified: %(dir)s""" %  { "dir"    : self.vdt_location(),})
    common.logit(""" CA certificates install starting. The packages that will be installed are:
   %(package)s""" % { "package" : self.package,})
    self.install_vdt_package(self.package)
    common.logit("... retrieving certificates") 
    common.run_script(". %(vdt_location)s/setup.sh; %(vdt_location)s/vdt/bin/vdt-ca-manage setupca --location %(dir)s --url osg" % \
       { "vdt_location" : self.vdt_location(),
         "dir"          : os.path.dirname(self.x509_cert_dir())})
    self.create_crontab()
    if self.certificates_exist():
      common.logit("... certificate installation looks good")
    common.logit("\nCA certificates install complete\n")
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
      common.logit("\n...... %(service)s" % { "service" :service,})
      common.run_script(". %(vdt_location)s/setup.sh;vdt-control %(non_root_arg)s --enable %(service)s;vdt-control %(non_root_arg)s --on %(service)s" % \
           { "vdt_location" : self.vdt_location(),
             "non_root_arg" : non_root_arg,
             "service"      : service,} )
    common.logit("\nvdt-control --list")
    os.system(". %(vdt_location)s/setup.sh;vdt-control --list" % \
           { "vdt_location" : self.vdt_location(),})

    #-- show the cron entries added - extract the lines put in cron
    common.logit("\n... %(user)s crontab entries:" % \
         { "user" : pwd.getpwuid(os.getuid())[0],})
    services_file = "%(vdt_location)s/vdt/services/state" % \
         { "vdt_location" : self.vdt_location(),}
    try:
      fd = open(services_file,'r')
      lines = fd.readlines()
    except:
      common.logerr("Unable to read VDT services file: %(services_file)s" % 
         { "services_file" : services_file,})
    fd.close()
    fetch_crl_script = None
    for line in lines:
      els = line.split("\t")
      if (els[1] != 'cron'):
        continue # not a cron line
      if els[0] in self.vdt_services:
         common.logit("  %(cron_time)s %(cron_process)s" % \
             { "cron_time"    : els[4],
               "cron_process" : els[5].rstrip(),})
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
    """ Returns true if certificates already exist. 
        This is determined by loooking for *.r0 and *.0 files in the
        directory.
    """
    ca_files = glob.glob(os.path.join(self.x509_cert_dir(), '*.0'))
    crl_files = glob.glob(os.path.join(self.x509_cert_dir(), '*.r0'))
    if len(ca_files) > 0:
      if len(crl_files) > 0:
        return True
      common.logerr("""The %(option)s directory contains CA (*.0) files but
no CRL (*.r0) files.  This is not a satifactory condition.
Suggest you check this out before proceeding:
   %(dir)s""" % \
        { "option" : self.option,
           "dir"   : self.x509_cert_dir(),})
    #-- checking for other files to insure we are in the correct directory
    files = glob.glob(os.path.join(self.x509_cert_dir(), '*'))
    if len(files) > 0:
      common.logerr("""CA Certificates (%(option)s) files (*.0) do not exist in 
certificates directory BUT some other files do exist.  This does not make sense.
Suggest you check this out before proceeding:
   %(dir)s""" % \
        { "option" : self.option,
           "dir"   : self.x509_cert_dir(),})
    #-- looks good.. we can proceed with an install
    return False

  #-------------------
  def get_x509_cert_dir_value(self):
    """ Returns the X509_CERT_DIR variable from an OSG/VDT CA install.""" 
    cert_dir = ""
    vdt_script = "%s/setp.sh" % self.vdt_location()
    if os.path.exists(vdt_script):
      (status, cert_dir) = commands.getstatusoutput(". %s;echo $X509_CERT_DIR" % vdt_script)
      if status > 0:
        cert_dir = ""
    return cert_dir

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


