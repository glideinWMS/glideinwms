#!/bin/env python

import traceback
import sys,os,os.path,string,time
import stat
import re
import optparse
#-------------------------
import common
from Certificates  import Certificates  
from Condor        import Condor  
import WMSCollector
import VOFrontend
import Submit
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
"number_of_secondary_collectors",
"install_vdt_client",
]

class UserCollector(Condor):

  def __init__(self,inifile):
    global valid_options
    self.inifile = inifile
    self.ini_section = "UserCollector"
    Condor.__init__(self,self.inifile,self.ini_section,valid_options)
    #self.certificates = self.option_value(self.ini_section,"certificates")
    self.certificates = None
    self.wmscollector = None  # User collector object
    self.daemon_list = "MASTER, COLLECTOR, NEGOTIATOR"

  #--------------------------------
  def get_wmscollector(self):
    if self.wmscollector == None:
      self.wmscollector = WMSCollector.WMSCollector(self.inifile)

  #--------------------------------
  def install(self):
    self.verify_no_conflicts()
    common.logit ("======== %s install starting ==========" % self.ini_section)
    self.install_condor()
    common.logit ("======== %s install complete ==========" % self.ini_section)
    os.system("sleep 3")
    common.logit("")
    common.logit("You will need to have the User Collector running if you intend\nto install the other glideinWMS components.")
    yn = common.ask_yn("... would you like to start it now")
    cmd ="./manage-glideins  --start usercollector --ini %s" % (self.inifile)
    if yn == "y":
      common.run_script(cmd)
    else:
      common.logit("\nTo start the User Collector, you can run:\n %s" % cmd)



  #--------------------------------
  def configure_gsi_security(self):
    common.logit("")
    common.logit("Configuring GSI security")
    common.validate_gsi(self.gsi_dn(),self.gsi_authentication,self.gsi_location)
    #--- Submit access ---
    submit      = Submit.Submit(self.inifile)
    #--- VOFrontend access ---
    frontend = VOFrontend.VOFrontend(self.inifile)
    #--- create condor_mapfile entries ---
    condor_entries = """\
GSI "^%s$" %s
GSI "^%s$" %s
GSI "^%s$" %s""" % \
      (re.escape(self.gsi_dn()),    self.service_name(),
     re.escape(submit.gsi_dn()),  submit.service_name(),
   re.escape(frontend.gsi_dn()),frontend.service_name())
    #--- add in frontend proxy dns --
    cnt = 0
    for dn in frontend.glidein_proxies_dns():
      cnt = cnt + 1
      frontend_service_name = "%s_pilot_%d" % (frontend.service_name(),cnt)
      condor_entries = condor_entries + """
GSI "^%s$" %s""" % (re.escape(dn),frontend_service_name)

    self.__create_condor_mapfile__(condor_entries) 

#### ----------------------------------------------
#### No longer required effective with 7.5.1
#### ----------------------------------------------
#    #-- create the condor config file entries ---
#    gsi_daemon_entries = """\
## --- User collector user: %s
#GSI_DAEMON_NAME=%s
## --- Submit user: %s
#GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
## --- Frontend user: %s
#GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s""" % \
#       (self.unix_acct(),    self.gsi_dn(),
#      submit.unix_acct(),  submit.gsi_dn(),
#    frontend.unix_acct(),frontend.gsi_dn())
#    #-- add in the frontend glidein puilot proxies --
#    cnt = 0
#    for dn in frontend.glidein_proxies_dns():
#      cnt = cnt + 1
#      gsi_daemon_entries = gsi_daemon_entries + """
# --- Frontend pilot proxy: %s --
#GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s""" %  (cnt,dn)
#
#    #-- update the condor config file entries ---
#    self.__update_condor_config_gsi__(gsi_daemon_entries) 

  #--------------------------------
  def verify_no_conflicts(self):
    self.get_wmscollector()
    if self.node() <> self.wmscollector.node():
      return  # -- no problem, on separate nodes --
    if self.collector_port() == self.wmscollector.collector_port():
      common.logerr("The WMS collector and User collector are being installed \non the same node. They both are trying to use the same port: %s." % self.collector_port())
    if int(self.wmscollector.collector_port()) in self.secondary_collector_ports():
      common.logerr("The WMS collector and User collector are being installed \non the same node. The WMS collector port (%s) conflicts with one of the\nsecondary User collector ports that will be assigned: %s." % (self.wmscollector.collector_port(),self.secondary_collector_ports()))


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
def main(argv):
  try:
    options = validate_args(argv)
    user = UserCollector(options.inifile)
    user.install()
    #user.__create_initd_script__()
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

