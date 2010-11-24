#!/usr/bin/env python

import traceback
import sys,os,os.path,string,time
import re
import stat
import optparse
import common
#-------------------------
from Condor        import Condor
import UserCollector
import VOFrontend
from Configuration import ConfigurationError
#-------------------------
os.environ["PYTHONPATH"] = ""

valid_options = [ "node", 
"unix_acct",
"service_name", 
"condor_location", 
"certificates",
"gsi_authentication", 
"cert_proxy_location", 
"gsi_dn", 
"match_authentication", 
"condor_tarball", 
"condor_admin_email", 
"split_condor_config", 
"number_of_schedds",
"install_vdt_client",
"vdt_location",
"pacman_location",
]

class Submit(Condor):

  def __init__(self,inifile,options=None):
    global valid_options
    if options <> None:
       valid_options = options
    self.inifile = inifile
    self.ini_section = "Submit"
    Condor.__init__(self,self.inifile,self.ini_section,valid_options)
    #self.certificates = self.option_value(self.ini_section,"certificates")
    self.certificates = None
    self.schedd_name_suffix = "jobs"
    self.daemon_list = "SCHEDD"
    self.frontend      = None     # VOFrontend object
    self.usercollector = None     # User collector object
    self.colocated_services = []



  #--------------------------------
  def get_frontend(self):
    if self.frontend == None:
      self.frontend = VOFrontend.VOFrontend(self.inifile)
  #--------------------------------
  def get_usercollector(self):
    if self.usercollector == None:
      self.usercollector = UserCollector.UserCollector(self.inifile)
  #--------------------------------
  def get_usercollector(self):
    if self.usercollector == None:
      self.usercollector = UserCollector.UserCollector(self.inifile)
 
  #--------------------------------
  def install(self):
    self.get_frontend()
    self.get_usercollector()
    common.logit ("======== %s install starting ==========" % self.ini_section)
    common.ask_continue("Continue")
    self.install_vdtclient()
    self.install_certificates()
    self.determine_co_located_services()
    self.validate_condor_install()
    if "usercollector" not in self.colocated_services:
      self.install_condor()
    self.configure_condor()
    common.logit ("======== %s install complete ==========" % self.ini_section)
    os.system("sleep 3")
    common.logit("")
    common.logit("You will need to have the Submit node schedds running if you intend\nto install the other glideinWMS components.")
    yn = common.ask_yn("... would you like to start it now")
    cmd = "%s/manage-glideins  --start submit --ini %s" % (self.glidein_install_dir(),self.inifile)
    if yn == "y":
      common.run_script(cmd)
    else:
      common.logit("\nTo start the Submit node schedds, you can run:\n %s" % cmd)

  #-----------------------------
  def determine_co_located_services(self):
    """ The submit/schedd service can share the same instance of Condor with
        the UserCollector and/or VOFrontend.  So we want to check and see if
        this is the case.  We will skip the installation of Condor and just
        perform the configuration of the condor_config file.
    """
    common.logit("\nChecking for co-located services")
    # -- if not on same node, we don't have any co-located
    if self.node() <> self.usercollector.node():
      common.logit("... no services are co-located on this node")
      return 
    common.logit("""
The Submit service and the User Collector service are being installed on the
same node and can share the same Condor instance, as well as certificates and
VDT client instances.""")
    #--- Condor ---
    common.logit(".......... Submit Condor: %s" % self.condor_location())
    common.logit("... UserCollector Condor: %s" % self.usercollector.condor_location())

    if self.condor_location() == self.usercollector.condor_location():
      self.colocated_services.append("usercollector") 
    else:
      common.ask_continue("""
The condor_location for UserCollector service is different. 
Do you really want to keep them separate?  
If not, stop and fix your ini file condor_location.
Do you want to continue""")
    
    #--- Certificates ---
#    if self.certificates == self.usercollector.certificates:
#      self.colocated_services.append("certificates") 
#      common.logit("... Certificates are shared: %s" % self.certificates())
#    else:
#      common.ask_continue("""
#The certificates for both services is different. Do you really want to keep
#them separate?  If not, stop and fix your ini file certificates option.
#Do you want to continue""")
#
#    #--- VDTClient ---
#    if self.vdt_location() == self.usercollector.vdt_location():
#      self.colocated_services.append("vdtclient") 
#      common.logit("... VDT client is shared: %s" % self.vdt_location())
#    else:
#      common.ask_continue("""
#The vdt_location for both services is different. Do you really want to keep
#them separate?  If not, stop and fix your ini file vdt_location option.
#Do you want to continue""")


  #--------------------------------
  def configure_gsi_security(self):
    common.logit("")
    common.logit("Configuring GSI security")
    if len(self.colocated_services) > 0:
      common.logit("... submit/schedd service colocated with UserCollector")
      common.logit("... no updates to condor mapfile required")
      return
    common.logit("... updating condor_mapfile")
    common.validate_gsi(self.gsi_dn(),self.gsi_authentication(),self.gsi_location())
    #--- create condor_mapfile entries ---
    condor_entries = """\
GSI "^%s$" %s
GSI "^%s$" %s
GSI "^%s$" %s""" % \
              (re.escape(self.gsi_dn()),              self.service_name(),
 re.escape(self.usercollector.gsi_dn()),self.usercollector.service_name(),
      re.escape(self.frontend.gsi_dn()),              self.frontend.service_name())

    self.__create_condor_mapfile__(condor_entries)

    #-- create the condor config file entries ---
    common.logit("... updating condor_config for GSI_DAEMON_NAMEs")
    gsi_daemon_entries = """\
# --- Submit user: %s
GSI_DAEMON_NAME=%s
# --- Userpool user: %s
GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
# --- Frontend user: %s
GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
""" % \
                 (self.unix_acct(),               self.gsi_dn(),
    self.usercollector.unix_acct(), self.usercollector.gsi_dn(),
         self.frontend.unix_acct(),      self.frontend.gsi_dn())

    #-- update the condor config file entries ---
    self.__update_gsi_daemon_names__(gsi_daemon_entries)


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
    submit = Submit(options.inifile)
    #submit.install()
    #submit.configure_gsi_security()
    submit.__validate_tarball__(submit.condor_tarball())
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

