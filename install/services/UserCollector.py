#!/usr/bin/env python

import traceback
import sys,os,os.path,string,time
import stat
import re
import optparse
#-------------------------
import common
from Condor import Condor  
import WMSCollector
import VOFrontend
import Factory
import Submit
from Configuration import ConfigurationError
#-------------------------
#os.environ["PYTHONPATH"] = ""

usercollector_options = [ "install_type",
"hostname", 
"username",
"service_name", 
"condor_tarball", 
"condor_location", 
"condor_admin_email", 
"x509_cert_dir",
"x509_cert", 
"x509_key", 
"x509_gsi_dn", 
"install_vdt_client",
"vdt_location",
"pacman_location",
]

wmscollector_options = [ "hostname",
]

submit_options = [ "hostname",
"service_name",
"x509_gsi_dn",
]

frontend_options = [ "hostname",
"service_name",
"x509_gsi_dn",
"glidein_proxy_dns",
]

valid_options = { "UserCollector" : usercollector_options,
                  "WMSCollector"  : wmscollector_options,
                  "Submit"        : submit_options,
                  "VOFrontend"    : frontend_options,
}



class UserCollector(Condor):

  def __init__(self,inifile,optionsDict=None):
    global valid_options
    self.inifile = inifile
    self.ini_section = "UserCollector"
    if inifile == "template":  # for creating actions not requiring ini file
      return
    if optionsDict != None:
      valid_options = optionsDict
    Condor.__init__(self,self.inifile,self.ini_section,valid_options[self.ini_section])
    #self.certificates = self.option_value(self.ini_section,"certificates")
    self.daemon_list = "COLLECTOR, NEGOTIATOR"
    self.colocated_services = []

    self.wmscollector = None  # WMS collector object
    self.submit       = None  # submit object
    self.frontend     = None  # VOFrontend object

    self.not_validated = True

  #--------------------------------
  def get_wmscollector(self):
    if self.wmscollector == None:
      self.wmscollector = WMSCollector.WMSCollector(self.inifile,valid_options)
  #--------------------------------
  def get_submit(self):
    if self.submit == None:
      self.submit = Submit.Submit(self.inifile,valid_options)
  #--------------------------------
  def get_frontend(self):
    if self.frontend == None:
      self.frontend = VOFrontend.VOFrontend(self.inifile,valid_options)
 
  #--------------------------------
  def install(self):
    common.logit ("======== %s install starting ==========" % self.ini_section)
    common.ask_continue("Continue")
    self.validate()
    self.__install_condor__()
    self.configure()
    common.logit ("======== %s install complete ==========" % self.ini_section)
    common.start_service(self.glideinwms_location(),self.ini_section,self.inifile)

  #-----------------------------
  def validate(self):
    if self.not_validated: 
      self.get_wmscollector() 
      self.get_submit() 
      self.get_frontend()
      self.verify_no_conflicts()
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

  #--------------------------------
  def condor_mapfile_users(self):
    users = []
    users.append(["Submit",      self.submit.x509_gsi_dn(),   self.submit.service_name()])
    users.append(["VOFrontend",self.frontend.x509_gsi_dn(), self.frontend.service_name()])
    #-- frontend pilot proxies ---
    for user in self.frontend.pilot_proxy_users():
      users.append(user)
    return users

  #--------------------------------
  def condor_config_daemon_users(self): 
    users = []
    users.append(["Submit",      self.submit.x509_gsi_dn(),  self.submit.service_name()])
    users.append(["VOFrontend",self.frontend.x509_gsi_dn(),self.frontend.service_name()]) 
    return users

  #--------------------------------
  def verify_no_conflicts(self):
    self.get_wmscollector()
    if self.hostname() <> self.wmscollector.hostname():
      return  # -- no problem, on separate hosts --
    if self.collector_port() == self.wmscollector.collector_port():
      common.logerr("""The WMS and User collector are being installed on the same node. 
They both are trying to use the same port: %(port)s.
If not already specified, you may need to specifiy a 'collector_port' option 
in your ini file for either the WMSCollector or UserCollector sections, or both.
If present, are you really installing both services on the same node.
""" %  { "port" : self.collector_port(),})

    if int(self.wmscollector.collector_port()) in self.secondary_collector_ports():
      common.logerr("""The WMS and User collector are being installed on the same node. 
The WMS collector port (%(wms_port)s) conflicts with one of the secondary 
User Collector ports that will be assigned: 
  %(secondary_ports)s.
If not already specified, you may need to specifiy a 'collector_port' option 
in your ini file for either the WMSCollector or UserCollector sections, or both.
If present, are you really installing both services on the same node.
""" % { "wms_port"        : self.wmscollector.collector_port(),
        "secondary_ports" : self.secondary_collector_ports(), })

  #-------------------------
  def create_template(self):
    global valid_options
    print "; ------------------------------------------"
    print "; UserCollector minimal ini options template"
    for section in valid_options.keys():
      print "; ------------------------------------------"
      print "[%s]" % section
      for option in valid_options[section]:
        print "%-25s =" % option
      print 

#--- END OF CLASS ---
###########################################
#---------------------------
def show_line():
    x = traceback.extract_tb(sys.exc_info()[2])
    z = x[len(x)-1]
    return "%s line %s" % (z[2],z[1])

#---------------------------
def validate_args(args):
    usage = """Usage: %prog --ini ini_file

This will install a User collector service for glideinWMS using the ini file
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
# Main function, primarily used for debugging, now commented
#
#def main(argv):
#  try:
#    create_template() 
    #options = validate_args(argv)
    #user = UserCollector(options.inifile)
    #user.start_me()
    #user.install()
    #user.configure_gsi_security()
#  except KeyboardInterrupt, e:
#    common.logit("\n... looks like you aborted this script... bye.")
#    return 1
#  except EOFError:
#    common.logit("\n... looks like you aborted this script... bye.");
#    return 1
#  except ConfigurationError, e:
#    print;print "ConfigurationError ERROR(should not get these): %s"%e;return 1
#  except common.WMSerror:
#    print;return 1
#  return 0


#--------------------------
if __name__ == '__main__':
  sys.exit(main(sys.argv))

