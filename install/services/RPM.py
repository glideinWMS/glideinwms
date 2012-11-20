#!/usr/bin/env python

import traceback
import sys,os,os.path,string,time
import stat,re
import xml.sax.saxutils
import xmlFormat
import optparse
#-------------------------
import common
import Condor
from VOFrontend import VOFrontend
#-------------------------
os.environ["PYTHONPATH"] = ""

frontend_options = [ "install_type",
"hostname", 
"username", 
"service_name", 
"condor_location", 
"condor_config", 
"install_location", 
"logs_dir", 
"instance_name", 
"x509_cert_dir",
"x509_proxy", 
"x509_gsi_dn", 
"glidein_proxy_files", 
"glidein_proxy_dns", 
"condor_admin_email", 
"install_vdt_client", 
"glexec_use",
"group_name",
"match_string",
"userjob_constraints",
"web_location",
"web_url",
"expose_grid_env",
"glideinwms_location",
"vdt_location",
"pacman_location",
]

wmscollector_options = [ 
"hostname",
"service_name",
"x509_gsi_dn",
]

factory_options = [ 
"hostname",
"username",
"use_vofrontend_proxy",
]

submit_options = [ 
"hostname",
"service_name",
"condor_location",
"x509_gsi_dn"
]

usercollector_options = [ 
"hostname",
"service_name",
"x509_gsi_dn",
"condor_location",
"collector_port",
"number_of_secondary_collectors",
]

valid_options = { 
"VOFrontend"    : frontend_options,
"UserCollector" : usercollector_options,
"WMSCollector"  : wmscollector_options,
"Factory"       : factory_options,
"Submit"        : submit_options,
}



class RPM(VOFrontend):

  def __init__(self,inifile,optionsDict=None):
    global valid_options
    self.inifile = inifile
    self.ini_section = "VOFrontend"
    if optionsDict is not None:
      valid_options = optionsDict 
    VOFrontend.__init__(self,self.inifile,valid_options)
    self.schedd_name_suffix = "jobs"
    self.daemon_list = "COLLECTOR, NEGOTIATOR, SCHEDD" 
##    #-- instances of other services ---
    self.condor        = None
    self.get_condor()
    self.condor.set_daemon_list(self.daemon_list)
    self.condor.activate_userjob_classads()
    self.colocated_services = []

  #-- get service instances --------
  # NOTE: The RPM installation is using its own instance of Condor instead of
  #       The inherited instance from the VOFrontend in order to "fake" it
  #       out into thinking this is a UserCollector/Schedd service and perform
  #       the necessary validations and configurations for Condor.
  def get_condor(self):
    if self.condor is None:
      #self.condor = Condor.Condor(self.inifile,self.ini_section,valid_options["UserCollector"])
      self.condor = Condor.Condor(self.inifile,"UserCollector",valid_options["UserCollector"])

  #########################################################
  #--------------------------------
  def config_dir(self):
    return "/etc/gwms-frontend"
  #--------------------------------
  def config_file(self):
    return "%s/frontend.xml" % (self.config_dir())
  #--------------------------------
  def frontend_name(self):
    return "%s_OSG_gWMSFrontend" % (self.hostname().replace(".","-"))
  #--------------------------------
  def install(self):
     common.logerr("There is no '--install' for the OSG RPM Frontend")

  #--------------------------------
  def validate(self):
    self.get_wms()
    self.get_factory()
    self.get_usercollector()
    self.get_submit()
    self.condor.install_vdtclient()
    self.condor.install_certificates()
    self.condor.validate_condor_install()
    self.validate_frontend()

  #--------------------------------
  def configure(self):
    self.validate()
    self.condor.stop_condor()
    self.configure_condor()
    self.condor.start_condor()
    self.configure_frontend()
    if self.install_type() == "tarball":
      self.create_frontend()
    else:
      self.reconfig()
    self.start()

  #-----------------------------
  def configure_condor(self):
    common.logit("Configuring Condor")
    self.get_condor_config_data()
    self.condor.__create_condor_mapfile__(self.condor_mapfile_users())
    self.condor.__create_condor_config__()
    if self.install_type() == "tarball":
      self.condor.__create_initd_script__()
    common.logit("Configuration complete")

  #---------------------------
  def get_condor_config_data(self):
    self.condor.__check_condor_version__()
    self.condor.__condor_config_gwms_data__()
    self.condor.__condor_config_daemon_list__()
    self.condor.__condor_config_gsi_data__(self.condor_config_daemon_users())
    self.condor.__condor_config_negotiator_data__()
    self.condor.__condor_config_collector_data__()
    self.condor.__condor_config_secondary_collector_data__()
    self.condor.__condor_config_schedd_data__()
    self.condor.__condor_config_secondary_schedd_data__()
    self.condor.__condor_config_userjob_default_attributes_data__()

  #--------------------------------
  def condor_mapfile_users(self):
    users = []
    cnt = 0
    for dn in self.glidein_proxy_dns():
      cnt = cnt + 1
      comment  = "glidein_pilot_%d" % cnt
      
      users.append([comment,dn,comment])
    return users

  #--------------------------------
  def condor_config_daemon_users(self):
    users = []
    cnt = 0
    for dn in self.glidein_proxy_dns():
      cnt = cnt + 1
      comment  = "glidein_pilot_%d" % cnt
      
      users.append([comment,dn,comment])
    users.append(["WMSCollector",self.wms.x509_gsi_dn(),"wmscollector"])
    return users

#---------------------------
def show_line():
    x = traceback.extract_tb(sys.exc_info()[2])
    z = x[len(x)-1]
    return "%s line %s" % (z[2],z[1])

#---------------------------
def validate_args(args):
    usage = """Usage: %prog --ini ini_file

This will install a VO Frontend service for glideinWMS using the ini file
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

#-------------------------
def create_template():
  global valid_options
  print "; ------------------------------------------"
  print "; Submit minimal ini options template"
  for section in valid_options.keys():
    print "; ------------------------------------------"
    print "[%s]" % section
    for option in valid_options[section]:
      print "%-25s =" % option
    print

##########################################
def main(argv):
  try:
    #create_template()
    options = validate_args(argv)
    vo = VOFrontend(options.inifile)
    vo.get_new_config_group()
    #vo.validate_glidein_proxies()
    #vo.install()
    #vo.get_usercollector()
    #print vo.config_collectors_data()
    #vo.configure_gsi_security()
  except KeyboardInterrupt, e:
    common.logit("\n... looks like you aborted this script... bye.")
    return 1
  except EOFError:
    common.logit("\n... looks like you aborted this script... bye.");
    return 1
  except common.WMSerror:
    print;return 1
  return 0

#--------------------------
if __name__ == '__main__':
  sys.exit(main(sys.argv))

