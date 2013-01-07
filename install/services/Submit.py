#!/usr/bin/env python

import traceback
import sys,os,os.path,string,time
import re
import stat
import optparse
#-------------------------
from glideinwms.install.services import common
from glideinwms.install.services import UserCollector
from glideinwms.install.services import VOFrontend
from glideinwms.install.services.Condor import Condor
from glideinwms.install.services.Configuration import ConfigurationError
#-------------------------
os.environ["PYTHONPATH"] = ""

submit_options = [ "hostname", 
"username",
"service_name", 
"condor_location", 
"x509_cert_dir",
"x509_cert", 
"x509_key", 
"x509_gsi_dn", 
"condor_tarball", 
"condor_admin_email", 
"number_of_schedds",
"schedd_shared_port",
"install_vdt_client",
"vdt_location",
"pacman_location",
]

usercollector_options = [ "hostname", 
"collector_port",
"service_name", 
"x509_gsi_dn",
"condor_location",
]

frontend_options = [ "hostname", 
"service_name", 
"x509_gsi_dn",
]

wmscollector_options = [] 
factory_options = [] 

valid_options = { "Submit"        : submit_options,
                  "UserCollector" : usercollector_options,
                  "VOFrontend"    : frontend_options,
                  "WMSCollector"  : wmscollector_options,
                  "Factory"       : factory_options,
}

class Submit(Condor):

  def __init__(self,inifile,optionsDict=None):
    global valid_options
    self.inifile = inifile
    self.ini_section = "Submit"
    if inifile == "template":  # for creating actions not requiring ini file
      return
    if optionsDict is not None:
      valid_options = optionsDict
    Condor.__init__(self,self.inifile,self.ini_section,valid_options[self.ini_section])
    self.userjob_classads_required = True
    self.schedd_name_suffix = "jobs"
    self.daemon_list = "SCHEDD"
    self.frontend      = None     # VOFrontend object
    self.usercollector = None     # User collector object
    self.colocated_services = []

    self.not_validated = True

  #--------------------------------
  def get_frontend(self):
    if self.frontend is None:
      self.frontend = VOFrontend.VOFrontend(self.inifile,valid_options)
  #--------------------------------
  def get_usercollector(self):
    if self.usercollector is None:
      self.usercollector = UserCollector.UserCollector(self.inifile,valid_options)
 
  #--------------------------------
  def install(self):
    common.logit ("======== %s install starting ==========" % self.ini_section)
    common.ask_continue("Continue")
    self.validate()
    if "usercollector" not in self.colocated_services:
      self.__install_condor__()
    self.configure()
    common.logit ("======== %s install complete ==========" % self.ini_section)
    if "usercollector" not in self.colocated_services:
      common.start_service(self.glideinwms_location(),self.ini_section,self.inifile) 
    else:
      self.stop_condor()
      self.start_condor()

  #-----------------------------
  def validate(self):
    if self.not_validated:
      self.get_frontend()
      self.get_usercollector() 
      self.determine_colocated_services()
      self.install_vdtclient()
      self.install_certificates() 
      self.validate_condor_install()
    self.not_validated = False

  #-----------------------------
  def configure(self):
    self.validate()   
    common.logit("Configuring Condor")
    self.get_condor_config_data()
    self.__create_condor_mapfile__(self.condor_mapfile_users())
    self.__create_condor_config__()
    self.__create_initd_script__()
    common.logit("Configuration complete")

  #-----------------------------
  def determine_colocated_services(self):
    """ The submit/schedd service can share the same instance of Condor with
        the UserCollector and/or VOFrontend.  So we want to check and see if
        this is the case.  We will skip the installation of Condor and just
        perform the configuration of the condor_config file.
    """
    if self.install_type() == "rpm":
      return # Not needed for RPM install
    services = ""
    # -- if not on same host, we don't have any co-located
    if self.hostname()           == self.usercollector.hostname():
      if  self.condor_location() == self.usercollector.condor_location():
        self.daemon_list += " %s" % self.usercollector.daemon_list
        self.colocated_services.append("usercollector")
      else:
        services += "User Collector "

    # -- determine services which are collocated ---
    if len(services) > 0:
      common.ask_continue("""These services are on the same node yet have different condor_locations:
  %s
Do you really want to continue.""" % services)
    if len(self.colocated_services) > 0:
      common.ask_continue("""These services are on the same node and share condor_locations:
  %(services)s
You will need the options from that service included in the %(section)s
of your ini file.
Do you want to continue.""" % { "services" : self.colocated_services,
                                "section"  : self.ini_section} )




  #--------------------------------
  def condor_mapfile_users(self):
    users = []
    if len(self.colocated_services) > 0:
      common.logit("... submit/schedd service colocated with UserCollector")
      common.logit("... no updates to condor mapfile required")
      return users
    users.append(["User Collector", self.usercollector.x509_gsi_dn(), self.usercollector.service_name()])
    users.append(["VOFrontend",     self.frontend.x509_gsi_dn(),      self.frontend.service_name()])
    return users

  #--------------------------------
  def condor_config_daemon_users(self):
    users = []
    if len(self.colocated_services) > 0:
      common.logit("... no updates to condor mapfile required")
      return users
    users.append(["Submit",        self.x509_gsi_dn(),               self.service_name()])
    users.append(["UserCollector", self.usercollector.x509_gsi_dn(), self.usercollector.service_name()])
    users.append(["VOFrontend",    self.frontend.x509_gsi_dn(),      self.frontend.service_name()])
    return users

  #-------------------------
  def create_template(self):
    global valid_options
    print "; ------------------------------------------"
    print "; Submit  minimal ini options template"
    for section in valid_options.keys():
      print "; ------------------------------------------"
      print "[%s]" % section
      for option in valid_options[section]:
        print "%-25s =" % option
      print

### END OF CLASS ###

#---------------------------
def show_line():
    x = traceback.extract_tb(sys.exc_info()[2])
    z = x[len(x)-1]
    return "%s line %s" % (z[2],z[1])

#---------------------------
def validate_args(args):
    usage = """Usage: %prog --ini ini_file

This will install a Submit service for glideinWMS using the ini file
specified.
"""
    print usage
    parser = optparse.OptionParser(usage)
    parser.add_option("-i", "--ini", dest="inifile",
                      help="ini file defining your configuration")
    (options, args) = parser.parse_args()
    if options.inifile is None:
        parser.error("--ini argument required")
    if not os.path.isfile(options.inifile):
      raise common.logerr("inifile does not exist: %s" % options.inifile)
    common.logit("Using ini file: %s" % options.inifile)
    return options

##########################################
def main(argv):
  try:
    pass
    #create_template()
    #options = validate_args(argv)
    #submit = Submit(options.inifile)
    #submit.install()
    #submit.configure_gsi_security()
    #submit.__validate_tarball__(submit.condor_tarball())
  except KeyboardInterrupt, e:
    common.logit("\n... looks like you aborted this script... bye.")
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

