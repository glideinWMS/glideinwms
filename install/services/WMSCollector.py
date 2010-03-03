#!/bin/env python

import traceback
import sys,os,os.path,string,time
import stat

import common
import optparse
from Certificates  import Certificates  
from Condor        import Condor
import VOFrontend
import Factory
from Configuration import ConfigurationError
#-------------------------
os.environ["PYTHONPATH"] = ""

valid_options = [ "node", 
"unix_acct", 
"service_name", 
"condor_location", 
"collector_port", 
"certificates",
"gsi_authentication", 
"cert_proxy_location", 
"gsi_dn", 
"condor_tarball", 
"condor_admin_email", 
"split_condor_config", 
"number_of_schedds",
"install_vdt_client",
]

class WMSCollector(Condor):

  def __init__(self,inifile):
    global valid_options
    self.inifile = inifile
    self.ini_section = "WMSCollector"
    Condor.__init__(self,self.inifile,self.ini_section,valid_options)
    #self.certificates = self.option_value(self.ini_section,"certificates")
    self.certificates = None
    self.daemon_list = "MASTER, COLLECTOR, NEGOTIATOR, SCHEDD"

  #--------------------------------
  def install(self):
    common.logit("======== %s install starting ==========" % self.ini_section)
    self.install_condor()
    common.logit("======== %s install complete ==========" % self.ini_section)
    os.system("sleep 3")
    common.logit("")
    common.logit("You will need to have the WMS Collector running if you intend\nto install the other glideinWMS components.")
    yn = common.ask_yn("... would you like to start it now")
    cmd ="./manage-glideins  --start wmscollector --ini %s" % (self.inifile)
    if yn == "y":
      common.run_script(cmd)
    else:
      common.logit("\nTo start the WMS Collector, you can run:\n %s" % cmd)


  #--------------------------------
  def configure_gsi_security(self):
    common.logit("")
    common.logit("Configuring GSI security")
    common.validate_gsi(self.gsi_dn(),self.gsi_authentication,self.gsi_location)
    #--- VOFrontend access ---
    frontend      = VOFrontend.VOFrontend(self.inifile)
    #--- Factory access ---
    factory      = Factory.Factory(self.inifile)
    #--- create condor_mapfile entries ---
    condor_entries = """\
GSI "%s" %s
GSI "%s" %s""" % \
       (self.gsi_dn(),self.service_name(),
        frontend.gsi_dn(),frontend.service_name())

    self.__create_condor_mapfile__(condor_entries) 

    #-- update the condor config file entries ---
    condor_config_entries = "%s" % self.gsi_dn()
    self.__update_condor_config_gsi__(condor_config_entries) 


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
def main(argv):
  try:
    options = validate_args(argv)
    wms = WMSCollector(options.inifile)
    wms.install()
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

