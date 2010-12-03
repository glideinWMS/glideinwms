#!/usr/bin/env python

import traceback
import sys,os,os.path,string,time
import stat
import re

import common
import optparse
from Certificates  import Certificates  
from Condor        import Condor
import VOFrontend
import Factory
import UserCollector
from Configuration import ConfigurationError
#-------------------------
os.environ["PYTHONPATH"] = ""

wmscollector_options = [ "node", 
"unix_acct", 
"service_name", 
"condor_location", 
"collector_port", 
"certificates",
"privilege_separation",
"frontend_users",
"gsi_authentication", 
"cert_proxy_location", 
"gsi_dn", 
"condor_tarball", 
"condor_admin_email", 
"split_condor_config", 
"number_of_schedds",
"glidein_install_dir",
"install_vdt_client",
"vdt_location",
"pacman_location",
]

frontend_options = [ "gsi_dn",
"service_name",
]

factory_options = [ "node",
"unix_acct",
]

usercollector_options = [ "node",
"collector_port",
"number_of_secondary_collectors",
]

valid_options = { "WMSCollector"  : wmscollector_options,
                  "Factory"       : factory_options,
                  "UserCollector" : usercollector_options,
                  "VOFrontend"    : frontend_options,
}




class WMSCollector(Condor):

  def __init__(self,inifile,options=None):
    global valid_options
    self.inifile = inifile
    self.ini_section = "WMSCollector"
    if options == None:
      options = valid_options[self.ini_section]
    Condor.__init__(self,self.inifile,self.ini_section,options)
    #self.certificates = self.option_value(self.ini_section,"certificates")
    #self.certificates = None
    self.schedd_name_suffix = "glideins"
    self.daemon_list = "COLLECTOR, NEGOTIATOR, SCHEDD"
    self.colocated_services = []
    self.frontend      = None     # VOFrontend object
    self.factory       = None     # Factory object
    self.usercollector = None     # User collector object
    self.privsep       = None     # Privilege Separation object

  #--------------------------------
  def get_frontend(self):
    if self.frontend == None:
      self.frontend = VOFrontend.VOFrontend(self.inifile,valid_options["VOFrontend"])
  #--------------------------------
  def get_factory(self):
    if self.factory == None:
      self.factory = Factory.Factory(self.inifile,valid_options["Factory"])
  #--------------------------------
  def get_usercollector(self):
    if self.usercollector == None:
      self.usercollector = UserCollector.UserCollector(self.inifile,valid_options["UserCollector"])
  #--------------------------------
  def get_privsep(self):
    if self.privilege_separation() == "y":
      import PrivilegeSeparation
      self.privsep = PrivilegeSeparation.PrivilegeSeparation(self.condor_location(),self.factory,[self.frontend,],self.frontend_users())
  #--------------------------------
  def frontend_users(self):
    mydict = {}
    if self.privilege_separation() == "y":
      #-- need to convert a string to a dictionary --
      s = self.option_value(self.ini_section,"frontend_users")
      t = s.replace(" ","").split(",")
      for a in t:
        b = a.split(":")
        if len(b) == 2:
          mydict[b[0]] = b[1]
    else:
      self.get_factory()
      self.get_frontend()
      mydict[self.frontend.service_name()] = self.factory.unix_acct()
    return mydict
  #--------------------------------
  def install(self):
    self.get_factory()
    self.get_frontend()
    common.logit("======== %s install starting ==========" % self.ini_section)
    common.ask_continue("Continue")
    self.get_privsep()
    self.verify_no_conflicts()
    ##  self.validate_install_location()
    self.install_vdtclient()
    self.install_certificates()
    self.validate_condor_install()
    self.install_condor()
    self.configure_condor()
    if self.privsep <> None:
      self.privsep.update()
    common.logit("======== %s install complete ==========" % self.ini_section)
    common.start_service(self.glidein_install_dir(),self.ini_section,self.inifile) 

  #-----------------------------
  def validate_install_location(self):
    common.validate_install_location(self.condor_location())

  #-----------------------------
  def condor_config_privsep_data(self):
    data = ""
    if self.privsep <> None:
      data =  self.privsep.condor_config_data()
    return data

  #--------------------------------
  def configure_gsi_security(self):
    common.logit("\nConfiguring GSI security")
    common.validate_gsi(self.gsi_dn(),self.gsi_authentication(),self.gsi_location())
    condor_entries = ""
    #-- frontends ---
    condor_entries += common.mapfile_entry(self.frontend.gsi_dn(), self.frontend.service_name())
    #--- wms entry ---
    condor_entries += common.mapfile_entry(self.gsi_dn(), self.unix_acct())
    self.__create_condor_mapfile__(condor_entries) 

    #-- update the condor config file entries ---
    gsi_daemon_entries = """\
# --- WMS collector user: %s ---
GSI_DAEMON_NAME=%s
# --- Factory user: %s ---
GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
# --- VOFrontend user: %s ---
GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
""" % (       self.unix_acct(),        self.gsi_dn(),
      self.factory.unix_acct(),        self.factory.gsi_dn(),
     self.frontend.service_name(),     self.frontend.gsi_dn())
    self.__update_gsi_daemon_names__(gsi_daemon_entries) 


  #--------------------------------
  def verify_no_conflicts(self):
    self.get_usercollector()
    if self.node() <> self.usercollector.node():
      return  # -- no problem, on separate nodes --
    if self.collector_port() == self.usercollector.collector_port():
      common.logerr("The WMS collector and User collector are being installed \non the same node. They both are trying to use the same port: %s." % self.collector_port())
    if int(self.collector_port()) in self.usercollector.secondary_collector_ports():
      common.logerr("The WMS collector and User collector are being installed \non the same node. The WMS collector port (%s) conflicts with one of the\nsecondary User collector ports that will be assigned: %s." % (self.collector_port(),self.usercollector.secondary_collector_ports()))

#---------------------------
def show_line():
    x = traceback.extract_tb(sys.exc_info()[2])
    z = x[len(x)-1]
    return "%s line %s" % (z[2],z[1])

#---------------------------
def validate_args(args):
    usage = """Usage: %prog --ini ini_file 

This will install a WMS collector service for glideinWMS using the ini file
specified.
"""
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
  print "; WMSCollector minimal ini options template"
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
    #wms = WMSCollector(options.inifile)
    #wms.install()
    #wms.__validate_collector_port__()
    #wms.__create_initd_script__()
    #wms.configure_gsi_security()
    #wms.configure_secondary_schedds()
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

