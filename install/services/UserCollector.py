#!/usr/bin/env python

import traceback
import sys,os,os.path,string,time
import stat
import re
import optparse
#-------------------------
import common
#from Certificates  import Certificates  
from Condor        import Condor  
import WMSCollector
import Factory
import VOFrontend
import Submit
from Configuration import ConfigurationError
#-------------------------
os.environ["PYTHONPATH"] = ""

usercollector_options = [ "hostname", 
"username",
"service_name", 
"condor_tarball", 
"condor_location", 
"split_condor_config", 
"condor_admin_email", 
"collector_port", 
"number_of_secondary_collectors",
"x509_cert_dir",
"x509_cert", 
"x509_key", 
"x509_gsi_dn", 
"install_vdt_client",
"vdt_location",
"pacman_location",
]

wmscollector_options = [ "hostname",
"collector_port",
]

factory_options = [ 
"x509_gsi_dn",
"service_name",
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
                  "Factory"       : factory_options,
                  "Submit"        : submit_options,
                  "VOFrontend"    : frontend_options,
}



class UserCollector(Condor):

  def __init__(self,inifile,options=None):
    global valid_options
    self.inifile = inifile
    self.ini_section = "UserCollector"
    if options == None:
      options = valid_options[self.ini_section]
    Condor.__init__(self,self.inifile,self.ini_section,options)
    #self.certificates = self.option_value(self.ini_section,"certificates")
    self.wmscollector = None  # WMS collector object
    self.factory      = None  # Factory object
    self.submit       = None  # submit object
    self.frontend     = None  # VOFrontend object
    self.daemon_list = "COLLECTOR, NEGOTIATOR"
    self.colocated_services = []

  #--------------------------------
  def get_wmscollector(self):
    if self.wmscollector == None:
      self.wmscollector = WMSCollector.WMSCollector(self.inifile,valid_options["WMSCollector"])
  #--------------------------------
  def get_factory(self):
    if self.factory == None:
      self.factory = Factory.Factory(self.inifile,valid_options["Factory"])
  #--------------------------------
  def get_submit(self):
    if self.submit == None:
      self.submit = Submit.Submit(self.inifile,valid_options["Submit"])
  #--------------------------------
  def get_frontend(self):
    if self.frontend == None:
      self.frontend = VOFrontend.VOFrontend(self.inifile,valid_options["VOFrontend"])

  #--------------------------------
  def install(self):
    self.get_wmscollector()
    self.get_factory()
    self.get_submit()
    self.get_frontend()
    common.logit ("======== %s install starting ==========" % self.ini_section)
    common.ask_continue("Continue")
    self.install_vdtclient()
    self.install_certificates()
    self.validate_condor_install()
    self.verify_no_conflicts()
    self.validate_install_location()
    self.install_condor()
    self.configure_condor()
    common.logit ("======== %s install complete ==========" % self.ini_section)
    common.start_service(self.glideinwms_location(),self.ini_section,self.inifile)

  #-----------------------------
  def validate_install_location(self):
    common.validate_install_location(self.condor_location())

  #--------------------------------
  def configure_gsi_security(self):
    common.logit("")
    common.logit("Configuring GSI security")
    common.logit("... updating condor_mapfile")
    #--- create condor_mapfile entries if service is not collocated ---
    #--- if collocated, file system authentication is used          --- 
    condor_entries = ""
    for service in [self.frontend, self.submit,]:
      if service.hostname() <> self.hostname():
        condor_entries += common.mapfile_entry(service.x509_gsi_dn(),service.service_name())
    #--- add in frontend proxy dns for pilots --
    cnt = 0
    for dn in self.frontend.glidein_proxy_dns():
      cnt = cnt + 1
      frontend_service_name = "%s_pilot_%d" % (self.frontend.service_name(),cnt)
      condor_entries += common.mapfile_entry(dn,frontend_service_name)
    self.__create_condor_mapfile__(condor_entries) 

    #-- create the condor config file entries ---
    common.logit("... updating condor_config for GSI_DAEMON_NAMEs")
    gsi_daemon_entries = """\
# --- User collector user: %s
GSI_DAEMON_NAME=%s
# --- Submit user: %s
GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
# --- Frontend user: %s
GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s""" % \
       (self.service_name(),                self.x509_gsi_dn(),
      self.submit.service_name(),    self.submit.x509_gsi_dn(),
    self.frontend.service_name(),  self.frontend.x509_gsi_dn())

    #-- add in the frontend glidein pilot proxies --
    cnt = 0
    for dn in self.frontend.glidein_proxy_dns():
      cnt = cnt + 1
      gsi_daemon_entries += """
# --- Frontend pilot proxy: %s --
GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s""" %  (cnt,dn)

    #-- update the condor config file entries ---
    self.__update_gsi_daemon_names__(gsi_daemon_entries) 

  #--------------------------------
  def verify_no_conflicts(self):
    self.get_wmscollector()
    if self.hostname() <> self.wmscollector.hostname():
      return  # -- no problem, on separate hosts --
    if self.collector_port() == self.wmscollector.collector_port():
      common.logerr("The WMS collector and User collector are being installed \non the same node. They both are trying to use the same port: %s." % self.collector_port())
    if int(self.wmscollector.collector_port()) in self.secondary_collector_ports():
      common.logerr("The WMS collector and User collector are being installed \non the same node. The WMS collector port (%s) conflicts with one of the\nsecondary User collector ports that will be assigned: %s." % (self.wmscollector.collector_port(),self.secondary_collector_ports()))

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

#-------------------------
def create_template():
  global valid_options
  print "; ------------------------------------------"
  print "; UserCollector minimal ini options template"
  for section in valid_options.keys():
    print "; ------------------------------------------"
    print "[%s]" % section
    for option in valid_options[section]:
      print "%-25s =" % option
    print 

##########################################
def main(argv):
  try:
    create_template() 
    #options = validate_args(argv)
    #user = UserCollector(options.inifile)
    #user.start_me()
    #user.install()
    #user.configure_gsi_security()
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

