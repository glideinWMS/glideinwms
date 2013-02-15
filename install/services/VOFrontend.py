#!/usr/bin/env python

import traceback
import sys
import os
import os.path
import string
import time
import stat
import re
import xml.sax.saxutils
import optparse
#-------------------------
from glideinwms.lib import xmlFormat
import common
import WMSCollector
import Factory
import Submit
import UserCollector
import Glidein
from Condor import Condor
from Configuration import Configuration
from Configuration import ConfigurationError
#-------------------------
#os.environ["PYTHONPATH"] = ""

frontend_options = [ "install_type",
"hostname", 
"username", 
"service_name", 
"condor_location", 
"install_location", 
"logs_dir", 
"instance_name", 
"x509_cert_dir",
"x509_proxy", 
"x509_gsi_dn", 
"glidein_proxy_files", 
"glidein_proxy_dns", 
"condor_tarball", 
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
"javascriptrrd_location",
"vdt_location",
"pacman_location",
]

wmscollector_options = [ 
"hostname",
"service_name",
"x509_gsi_dn",
]

factory_options = [ 
"username",
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
]

valid_options = { 
"VOFrontend"    : frontend_options,
"UserCollector" : usercollector_options,
"WMSCollector"  : wmscollector_options,
"Factory"       : factory_options,
"Submit"        : submit_options,
}



class VOFrontend(Condor):

  def __init__(self,inifile,optionsDict=None):
    global valid_options
    self.inifile = inifile
    self.ini_section = "VOFrontend"
    if inifile == "template":  # for creating actions not requiring ini file
      return
    if optionsDict is not None:
      valid_options = optionsDict
    Condor.__init__(self,self.inifile,self.ini_section,valid_options[self.ini_section])
    self.daemon_list = "" 
    self.colocated_services = []
    self.not_validated = True  # switch so we only validate once

    #-- instances of other services ---
    self.glidein = Glidein.Glidein(self.inifile,self.ini_section,valid_options[self.ini_section])
    self.wms           = None
    self.factory       = None
    self.usercollector = None
    self.submit        = None

  #-- get service instances --------
  def get_wms(self):
    if self.wms is None:
      self.wms = WMSCollector.WMSCollector(self.inifile,valid_options)
  #--------------------------------
  def get_factory(self):
    if self.factory is None:
      self.factory = Factory.Factory(self.inifile,valid_options)
  #--------------------------------
  def get_usercollector(self):
    if self.usercollector is None:
      self.usercollector = UserCollector.UserCollector(self.inifile,valid_options)
  #--------------------------------
  def get_submit(self):
    if self.submit is None:
      self.submit = Submit.Submit(self.inifile,valid_options)

  #--------------------------------
  def WMSCollector(self):
    return self.option_value("WMSCollector","hostname")
  #--------------------------------
  def WMSCollector_username(self):
    return self.option_value("Factory","username")
  #--------------------------------
  def UserCollector(self):
    return self.option_value("UserCollector","hostname")
  #--------------------------------
  def SubmitDN(self):
    return self.option_value("Submit","x509_gsi_dn")
  #--------------------------------
  def UserCollectorDN(self):
    return self.option_value("UserCollector","x509_gsi_dn")
  #--------------------------------
  def Submit_service_name(self):
    return self.option_value("Submit","service_name")
  #--------------------------------
  def UserCollector_service_name(self):
    return self.option_value("UserCollector","service_name")
  #--------------------------------
  def config_dir(self):
    return "%s/instance_%s.cfg" % (self.glidein.install_location(),self.glidein.instance_name())
  #--------------------------------
  def config_file(self):
    return "%s/frontend.xml" % (self.config_dir())
  #--------------------------------
  def grid_mapfile(self):
    return "%s/grid_mapfile" % (self.config_dir())
  #--------------------------------
  def frontend_name(self):
    return "%s-%s" % (self.glidein.service_name(), self.glidein.instance_name())
  #--------------------------------
  def frontend_dir(self):
    return "%s/frontend_%s-%s" % (self.glidein.install_location(),self.glidein.service_name(),self.glidein.instance_name())
  #--------------------------------
  def env_script(self):
    return "%s/frontend.sh"  % (self.glidein.install_location())
  #--------------------------------
  def install_type(self):
    return self.option_value(self.ini_section,"install_type")
  #--------------------------------
  def hostname(self):
    return self.option_value(self.ini_section,"hostname")
  #--------------------------------
  def username(self):
    return self.option_value(self.ini_section,"username")
  #--------------------------------
  def logs_dir(self):
    return self.option_value(self.ini_section,"logs_dir")
  #--------------------------------
  def group_name(self):
    return self.option_value(self.ini_section,"group_name")
  #--------------------------------
  def match_string(self):
    return self.option_value(self.ini_section,"match_string")
  #--------------------------------
  def userjob_constraints(self):
    return self.option_value(self.ini_section,"userjob_constraints")
  #--------------------------------
  def x509_proxy(self):
    return self.option_value(self.ini_section,"x509_proxy")
  #--------------------------------
  def x509_gsi_dn(self):
    return self.option_value(self.ini_section,"x509_gsi_dn")
  #--------------------------------
  def service_name(self):
    return self.option_value(self.ini_section,"service_name")
  #--------------------------------
  def expose_grid_env(self):
    return self.option_value(self.ini_section,"expose_grid_env")
  #--------------------------------
  def glexec_use(self):
    return string.upper(self.option_value(self.ini_section,"glexec_use"))
  #--------------------------------
  def glidein_proxy_files(self):
    return   self.option_value(self.ini_section,"glidein_proxy_files")
  #--------------------------------
  def glidein_proxy_dns(self):
    dns = self.option_value(self.ini_section,"glidein_proxy_dns")
    dn_list = string.split(dns,";")
    list = []
    for dn in dn_list:
      list.append(dn.strip())
    return list
    
  #--------------------------------
  def get_new_config_group(self):
    """This method is intended to create a new group element after the initial 
       installation is complete.  It will create a file containing the group
       and job selection/matchin criteria.  This can then be manually merged 
       into the existing frontend configuration file.
    """
    filename = "%(config_dir)s/%(group)s.%(time)s" % \
         { "config_dir" : self.config_dir(),
           "group"      : self.group_name(),
           "time"       : common.time_suffix(),}
    common.write_file("w",0644,filename,self.get_match_criteria())

  #--------------------------------
  def install(self):
    common.logit ("======== %s install starting ==========" % self.ini_section)
    common.ask_continue("Continue")
    self.validate()
#    if self.install_type() == "tarball":
##      if len(self.colocated_services) == 0 or \
##         self.condor_is_installed() is False:
    self.__install_condor__()
    if self.install_type() == "tarball":
      self.verify_directories_empty()
    self.configure()
    common.logit ("\n======== %s install complete ==========\n" % self.ini_section)
    self.create_frontend()
    self.start()

  #-----------------------------
  def validate_needed_directories(self):
    self.glidein.validate_web_location()
    self.validate_logs_dir()
    common.validate_install_location(self.install_location())

  #-----------------------------
  def verify_directories_empty(self):
    """ This method attempts to clean up all directories so a fresh install
        can be accomplished successfully.
        It is consoldiated in a single check so as to only ask once and
        not for each directory.
    """
    if self.install_type == "rpm":
      return  # For RPM install we don't want to clean anything

    instance_dir = "frontend_%(service)s-%(instance)s" % \
                     { "service" : self.service_name(), 
                       "instance" : self.glidein.instance_name(), }
    #-- directories to check ---
    dirs = {}
    dirs["logs........"] = os.path.join(self.logs_dir(),instance_dir)
    dirs["install....."] = os.path.join(self.install_location(),instance_dir) 
    dirs["config......"] = self.config_dir()
    for subdir in ["monitor","stage"]:
      dirs["web %s " % subdir] = os.path.join(self.glidein.web_location(),subdir,instance_dir)
    #--- check them --
    for type in dirs.keys():
      if os.path.isdir(dirs[type]): 
        if len(os.listdir(dirs[type])) == 0:
          os.rmdir(dirs[type])
          del dirs[type]  # remove from dict
      else:
        del dirs[type]  # it does not exist, remove from dict

    #--- if all are empty, return      
    if len(dirs) == 0:
      os.system("sleep 3")
      return  # all directories are empty

    #--- See if we can remove them --- 
    common.logit("""The following directories must be empty for the install to succeed: """)
    types = dirs.keys()
    types.sort()
    for type in types:
      common.logit("""  %(type)s: %(dir)s""" % \
                        { "type" : type, "dir" : dirs[type] })
    common.ask_continue("... can we remove their contents")
    for type in dirs.keys():
      common.remove_dir_contents(dirs[type])
      os.rmdir(dirs[type])
    os.system("sleep 3")
    return
    
  #-----------------------------
  def validate(self):
    if self.not_validated:
      self.get_wms() 
      self.get_factory()
      self.get_submit()
      self.get_usercollector()
      self.determine_colocated_services()
      self.install_vdtclient()
      self.install_certificates()   
      self.validate_condor_install()
      self.validate_frontend()
    self.not_validated = False

  #---------------------------------
  def validate_frontend(self):
    common.logit( "\nVerifying VOFrontend options")
    common.validate_hostname(self.hostname())
    common.validate_user(self.username())
    if self.install_type() == "tarball":
      common.validate_installer_user(self.username())
    common.validate_gsi_for_proxy(self.x509_gsi_dn(),self.x509_proxy(),self.username())
    self.validate_glidein_proxies()
    self.validate_glexec_use()
    self.glidein.validate_software_requirements()
    if self.install_type() == "tarball":
      self.validate_needed_directories()
    common.logit( "Verification complete\n")
    os.system("sleep 2")

  #-----------------------------
  def configure(self):
    self.validate() 
    self.validate_condor_installation()
    self.configure_condor()
    self.configure_frontend()

  #---------------------------------
  def configure_condor(self):
##    if len(self.colocated_services) == 0:
    common.logit("Configuring Condor")
    self.get_condor_config_data()
    self.__create_condor_mapfile__(self.condor_mapfile_users())
    self.__create_condor_config__()
    self.__create_initd_script__()
    common.logit("Condor configuration complete")
    os.system("sleep 2")

  #---------------------------------
  def configure_frontend(self):
    common.logit ("\nConfiguring VOFrontend")
    config_data  = self.get_config_data()
    self.create_config(config_data)
    if self.install_type() == "tarball":
      self.create_env_script()
    common.logit ("VOFrontend configuration complete")
    os.system("sleep 2")

  #--------------------------------
  def condor_mapfile_users(self):
    users = []
    if self.client_only_install == True:
      return users  # no mapfile users when client only frontend
    if "usercollector" in self.colocated_services:
      users.append(["VOFrontend",self.x509_gsi_dn(),self.service_name()])
      for user in self.pilot_proxy_users():
        users.append(user)
    return users

  #--------------------------------
  def condor_config_daemon_users(self):
    users = []
    if self.client_only_install == True:
      return users  # no no daemon users when client only frontend
    return users

  #---------------------------------
  def pilot_proxy_users(self):
    users = []
    cnt = 0
    for dn in self.glidein_proxy_dns():
      cnt = cnt + 1
      service_name = "%s_pilot_%i" % (self.service_name(),cnt)
      users.append(["VOFrontend pilots", dn, service_name])
    return users


  #-----------------------------
  def determine_colocated_services(self):
    """ The VOFrontend service can share the same instance of Condor with
        the UserCollector and/or Schedd services.  
        So we want to check and see if this is the case.  
        We will skip the installation of Condor and just perform the 
        configuration of the condor_config file.
    """
    if self.install_type() == "rpm":
      return # Not needed for RPM install
    services = ""
    # -- if not on same node, we don't have any co-located
    if self.hostname()           == self.usercollector.hostname(): 
      if  self.condor_location() == self.usercollector.condor_location():
        self.daemon_list += " %s" % self.usercollector.daemon_list
        self.colocated_services.append("usercollector")
      else:
        services += "User Collector "

    if self.hostname()          == self.submit.hostname():
      if self.condor_location() == self.submit.condor_location():
        self.daemon_list += ", %s" % self.submit.daemon_list
        self.colocated_services.append("submit")
      else:
        services += "Submit "

    # -- determine services which are collocated ---
    if len(self.colocated_services) == 0:
      self.client_only_install = True
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


  #---------------------------------
  def validate_glidein_proxies(self):
    common.logit("... validating glidein_proxy_files and glidein_proxy_dns")
    reinstall_msg = """You will need to reinstall the UserCollector so these pilot dns are used for
authentification/authorizaton of the glidein pilots""" 
    reinstall_msg = """You will need to reinstall the UserCollector so these pilot dns are used for
authentification/authorizaton of the glidein pilots.""" 

    if len(self.glidein_proxy_files()) == 0:
      common.logerr("""The Factory requires that you 
provide proxies using the VOFrontend glidein_proxy_files and
glidein_proxy_dns option.  These are not populated.
%(reinstall)s.""" % \
          { "reinstall"      : reinstall_msg, })
    proxies = self.glidein_proxy_files().split(" ")
    if len(self.glidein_proxy_dns()) <> len(proxies):
      common.logerr("""The number of glidein_proxy_files (%(proxy)s) must match the number of glidein_proxy_dns (%(dns)s).
%(reinstall)s.""" % \
          { "proxy" : len(proxies),
            "dns"   : len(self.glidein_proxy_dns()),
            "reinstall"      : reinstall_msg, })
    proxy_dns = self.glidein_proxy_dns()
    cnt = 0
    for proxy in proxies:
      if len(proxy) == 0:
        break
      common.logit("""    glidein_proxy_files[%(position)s]: %(proxy)s
    glidein_proxy_dns[%(position)i]: %(option_dn)s.""" % \
            { "position"   : cnt,
              "option_dn"  : proxy_dns[cnt],
              "proxy"      : proxy, })
      dn_in_file = common.get_gsi_dn("proxy",proxy,self.username())
      if dn_in_file <> proxy_dns[cnt]:
        common.logerr("""The DN in glidein_proxy_dns is incorrect.
option: %(option_dn)s
  file: %(dn_in_file)s
%(reinstall)s.""" % \
             { "dn_in_file" : dn_in_file, 
               "option_dn"  : proxy_dns[cnt],
               "reinstall"  : reinstall_msg, 
             })
      cnt = cnt + 1 
    common.logit("")

  #---------------------------------
  def validate_glexec_use(self):
    common.logit("... validating glexec_use: %s" % self.glexec_use())
    valid_glexec_use_values = [ "REQUIRED","OPTIONAL","NEVER" ]
    if self.glexec_use() not in valid_glexec_use_values:
      common.logerr("The glexec_use value specified (%s) in the ini file is invalid.\n      Valid values are: %s" % (self.glexec_use(),valid_glexec_use_values))

  #---------------------------------
  def validate_logs_dir(self):
    common.logit("... validating logs_dir: %s" % self.logs_dir())
    common.make_directory(self.logs_dir(),self.username(),0755)

  #---------------------------------
  def get_config_data(self):
    common.logit("\nCollecting  configuration file data. It will be question/answer time.")
    schedds         = self.get_user_schedds()
    match_criteria  = self.get_match_criteria()
    config_xml = self.config_data(schedds,match_criteria)
    common.logit("\nAll configuration file data collected.")
    return config_xml

  #---------------------------------
  def get_gridmap_data(self):
    os.system("sleep 2")
    common.logit("\nCollecting  grid_mapfile data. More questions.")
    os.system("sleep 2")
    while 1:
      dns = {}
      dns[self.glidein.service_name()]      = self.glidein.x509_gsi_dn()
      dns[self.UserCollector_service_name()] = self.UserCollectorDN()
      dns[self.Submit_service_name()]        = self.SubmitDN()
      print """
The frontend proxy, user pool collector and submit host DNs are required in
your grid_mapfile.

If there are other DNs needed in the glidein grid_mapfile, please add all 
the DNs that this glidein will connect to.

Please insert all such DNs, together with a user nickname.
An empty DN entry means you are done.  """
      while 1:
        print
        a_dn =raw_input("DN (leave empty when finished): ")
        if a_dn == "":
          break # done
        a_uid = raw_input("nickname: ")
        if a_uid == "":
          print "... you need a nickname. Try Again"
          continue
        if a_uid.find(" ") >= 0:
          print "WARNING: Nickname cannot contain spaces ('%s'), please reinsert the DN with a different nickname." % a_uid
          continue
        if a_uid in dns.keys():
          print "WARNING: Cannot reuse '%s', please reinsert the DN with a different nickname." % a_uid
          continue
        dns[a_uid] = a_dn

      print """
The following DNs are in your grid_mapfile:"""
      for a_uid in dns.keys():
        print '"%s" %s' % (dns[a_uid],a_uid)
      yn = "n"
      yn = raw_input("Do you want to proceed or try again? (y/n) [%s]: " % yn)
      if yn == "y":
        break
      common.logit("... try again")
      
    return dns
      
  #---------------------------
  ## def create_config(self,config_xml,gridmap_data):
  def create_config(self,config_xml):
    common.logit("\nCreating configuration files")
    common.logit("   %s" % self.config_file())
    common.make_directory(self.config_dir(),self.username(),0755)
    common.write_file("w",0644,self.config_file(),config_xml,SILENT=True)

  #-----------------------
  def stop(self):
    if self.install_type() == 'rpm':
      common.run_script("service frontend_startup stop")
#    else:
#      startup_file = "%s/frontend_startup" % (self.frontend_dir())
#      if os.path.isfile(startup_file): # indicates frontend has been created
#        common.stop_service(self.glideinwms_location(),self.ini_section,self.inifile) 
  #-----------------------
  def start(self):
    if self.install_type() == 'rpm':
      common.run_script("service frontend_startup start")
    else:
      startup_file = "%s/frontend_startup" % (self.frontend_dir())
      if os.path.isfile(startup_file): # indicates frontend has been created
        common.start_service(self.glideinwms_location(),self.ini_section,self.inifile) 

  #-----------------------
  def reconfig(self):
    if self.install_type() == 'rpm':
      common.run_script("/etc/init.d/frontend_startup reconfig")
#    else:
#      startup_file = "%s/frontend_startup" % (self.frontend_dir())
#      if os.path.isfile(startup_file): # indicates frontend has been created
#        common.start_service(self.glideinwms_location(),self.ini_section,self.inifile) 
  #-----------------------
  def create_env_script(self):
    common.logit("\nCreating VO frontend env script.")
    data = """#!/bin/bash
. %(condor_location)s/condor.sh
export PYTHONPATH=$PYTHONPATH:%(install_location)s/..
""" % { "condor_location" : self.condor_location(),
        "install_location" : self.glideinwms_location(),}
    common.write_file("w",0644,self.env_script(),data)
    common.logit("VO frontend env script created: %s" % self.env_script() )


  #---------------------------------
  def create_frontend(self):
    yn=raw_input("Do you want to create the frontend now? (y/n) [n]: ")
    cmd1 = ". %s" % self.env_script()
    cmd2 = "%s/creation/create_frontend %s" % (self.glidein.glideinwms_location(),self.config_file())
    if yn=='y':
      common.run_script("%s;%s" % (cmd1,cmd2))
    else:
      common.logit("\nTo create the frontend, you need to run the following:\n  %s\n  %s" % (cmd1,cmd2))

  #----------------------------
  def get_user_schedds(self):
    common.logit("\n... checking user and submit hosts for schedds")
    if "submit" in self.colocated_services:
      return self.get_schedds_via_condor_config_val()
    else:
      return self.get_schedds_via_condor_status()

  #---------------------------
  def get_schedds_via_condor_config_val(self):
    cmd = ""
    if self.install_type() != "rpm":
      cmd += ". %s/condor.sh;" % self.condor_location()
    cmd += "condor_config_val -dump |grep _jobs |awk '{print $3}'"
    fd = os.popen(cmd)
    lines = fd.readlines()
    err = fd.close()
    if err is not None: # condor_config_val not working 
        common.logit("%s" % lines)
        common.logerr("""Failed to fetch list of schedds running condor_config_val.""")
    schedds = [self.hostname(),]
    for line in lines:
        line = line[:-1] #remove newline
        if line != "":
            schedds.append("%(line)s@%(hostname)s" % \
              {"line" : line, "hostname" : self.hostname(),})
    return self.select_schedds(schedds)

  #---------------------------
  def get_schedds_via_condor_status(self):
    cmd = ""
    if self.install_type() != "rpm":
      cmd += ". %s/condor.sh;" % self.condor_location()
    cmd += "condor_status -schedd -format '%s\n' Name "
    fd = os.popen(cmd)
    lines = fd.readlines()
    err = fd.close()
    if err is not None: # collector not accessible
        common.logit("%s" % lines)
        common.logerr("Failed to fetch list of schedds running condor_status -schedd\n       Your user pool collector and submit host condor need to be running.")
    if len(lines) == 0: # submit schedds not accessible
        common.logerr("Failed to fetch list of schedds running condor_status -schedd\n       Your submit host condor needs to be running.")

    default_schedds=[]
    for line in lines:
        line = line[:-1] #remove newline
        if line != "":
            default_schedds.append(line)

    if len(default_schedds) == 0:
        common.logerr("""Failed to fetch list of schedds running condor_status -schedd
Your collector and submit host's condor need to be running.
or you have not defined any schedds on the submit host.""")

    return self.select_schedds(default_schedds)
  
  #---------------------------
  def select_schedds(self,default_schedds):
    if len(default_schedds) == 1:
      schedds = default_schedds
    else:
      schedds = self.select_schedds_to_monitor(default_schedds)

    common.logit("\nThe following schedds will be used:")
    for i in range(len(schedds)):
      common.logit(" [%i] %s"%(i+1,schedds[i]))
    return schedds
    

  #------------------------------------
  def select_schedds_to_monitor(self,default_schedds):
    while 1:
      common.logit("\nThe following schedds have been found:")
      for i in range(len(default_schedds)):
        common.logit(" [%i] %s"%(i+1,default_schedds[i]))
      yn = common.ask_yn("Do you want to monitor all of them")
      if yn == "y":
        schedds = default_schedds
        break
      print "Select the schedd indexes you want to monitor"
      print "Use a , separated list to monitor more than one"

      while 1:
        problem = False
        schedds=[]
        idxes = raw_input("Please select: ")
        idx_arr = idxes.split(',')
        for i in range(len(idx_arr)):
          try:
            nr = int(idx_arr[i])
            if (nr < 1) or (nr > len(default_schedds)):
              common.logit("Index %i out of range" % nr)
              problem = True
              break
            schedds.append(default_schedds[nr-1])
          except:
            common.logit("'%s' is not a valid index!" % idx_arr[i])
            problem = True
            break
        if problem:
          os.system("sleep 1")
          continue
        # got them
        for i in range(len(schedds)):
         common.logit(" [%i] %s"%(i+1,schedds[i]))
        break
      yn = raw_input("Do you want to use these or try again?: (y/n) ")
      if yn == "y":
        break 
    return schedds

  #---------------------------------------
  def get_match_criteria(self):
    """ Determine the job constraints/matching criteria for submitting jobs."""
  #-- factory attributes ----
    print """
What glidein/factory attributres are you using in the match expression?
I have computed my best estimate for your match string,
please verify and correct if needed.
"""
    default_factory_attributes = string.join(self.extract_factory_attrs(),',')
    factory_attributes = raw_input("Factory attributes: [%s] "%default_factory_attributes)
    if factory_attributes == "":
        factory_attributes = default_factory_attributes
    if factory_attributes == "":
        factory_attributes = []
    else:
        factory_attributes = string.split(factory_attributes,',')

    #--- job_attributes --
    print """
What job attributes are you using in the match expression?
I have computed my best estimate for your match string,
please verify and correct if needed.
"""
    default_job_attributes = string.join(self.extract_job_attrs(),',')
    job_attributes = raw_input("Job attributes: [%s] " % default_job_attributes)
    if job_attributes == "":
      job_attributes = default_job_attributes
    if job_attributes == "":
      job_attributes = []
    else:
      job_attributes = string.split(job_attributes,',')

    #--- create xml ----
    data  = """
%(indent2)s<group name="%(group_name)s" enabled="True">
%(indent3)s<match match_expr=%(match_string)s start_expr="True">
%(factory_attributes)s
%(job_attributes)s
%(indent3)s</match>
%(indent2)s</group>
""" % \
{ "indent2" : common.indent(2),
  "indent3" : common.indent(3),
  "indent4" : common.indent(4),
  "group_name"         : self.group_name(),
  "match_string"       : xmlFormat.xml_quoteattr(self.match_string()),
  "factory_attributes" : self.factory_data(factory_attributes),
  "job_attributes"     : self.job_data(job_attributes),
}
    return data 

  #-----------------------
  def factory_data(self,attributes):
    data = ""
    if len(attributes)>0:
      attr_query_arr=[]

      for attr in attributes:
        attr_query_arr.append("(%s=!=UNDEFINED)" % attr)
      data = data + """\
%(indent4)s<factory query_expr=%(expr)s>
%(indent5)s<match_attrs> """ % \
 { "indent4" : common.indent(4),
   "indent5" : common.indent(5),
   "expr"    : xmlFormat.xml_quoteattr(string.join(attr_query_arr," && ")),}

      for attr in attributes:
        data = data + """
%(indent6)s<match_attr name="%(attr)s" type="string"/>
""" % { "indent6" : common.indent(6),
        "attr"    : attr, }

      data = data + """\
%(indent5)s</match_attrs>
%(indent4)s</factory>
""" % { "indent4" : common.indent(4),
        "indent5" : common.indent(5), }
    return data

  #-----------------------
  def job_data(self,attributes):
    data = ""
    if len(attributes)>0:
      attr_query_arr=[]
      for attr in attributes:
        attr_query_arr.append("(%s=!=UNDEFINED)" % attr)

      data = data + """\
%(indent4)s<job query_expr=%(expr)s>
%(indent5)s<match_attrs> """ % \
 { "indent4" : common.indent(4),
   "indent5" : common.indent(5),
   "expr"    : xmlFormat.xml_quoteattr(string.join(attr_query_arr," && ")),}

      for attr in attributes:
        data = data + """
%(indent6)s<match_attr name="%(attr)s" type="string"/>
""" % { "indent6" : common.indent(6),
        "attr"    : attr, }

      data = data + """\
%(indent5)s</match_attrs>
%(indent4)s</job>
""" % { "indent4" : common.indent(4),
        "indent5" : common.indent(5), }
    return data


  #--------------------------------
  def config_data(self,schedds,match_criteria): 
    data = """<frontend frontend_name="%s"
         advertise_delay="5"
         advertise_with_multiple="True"
         advertise_with_tcp="True"
         loop_delay="60"
         restart_attempts="3"
         restart_interval="1800" """ % (self.frontend_name())

    if self.install_type() == "rpm":
      data += ' frontend_versioning="False">'
    else:
      data += '>'

    data += """\
%(work)s
%(stage)s
%(monitor)s
%(collector)s
%(security)s
%(match)s
%(attrs)s
%(groups)s
%(files)s
</frontend>
""" % { "work"      : self.config_work_data(),
        "stage"     : self.config_stage_data(),
        "monitor"   : self.config_monitor_data(),
        "collector" : self.config_collectors_data(),
        "security"  : self.config_security_data(),
        "match"     : self.config_match_data(schedds),
        "attrs"     : self.config_attrs_data(), 
        "groups"    : self.config_groups_data(match_criteria),
        "files"     : self.config_files_data(),}
    return data
  #---------------------------
  def config_work_data(self):
    return """
%(indent1)s<work base_dir="%(install_location)s" 
%(indent1)s      base_log_dir="%(logs_dir)s"/>""" % \
{ "indent1"          : common.indent(1),
  "install_location" : self.glidein.install_location(),
  "logs_dir"         : self.logs_dir(),
}
  #---------------------------
  def config_stage_data(self):
    return """
%(indent1)s<stage web_base_url="%(web_url)s/%(web_dir)s/stage"
%(indent1)s       base_dir="%(web_location)s/stage"/>""" % \
{ "indent1"      : common.indent(1),
  "web_url"      : self.glidein.web_url(),
  "web_location" : self.glidein.web_location(),
  "web_dir" : os.path.basename(self.glidein.web_location()),
}
  #---------------------------
  def config_monitor_data(self):
    return """
%(indent1)s<monitor base_dir="%(web_location)s/monitor" 
%(indent1)s         javascriptRRD_dir="%(javascriptrrd)s" 
%(indent1)s         flot_dir="%(flot)s" 
%(indent1)s         jquery_dir="%(jquery)s"/>""" % \
{ "indent1"       : common.indent(1),
  "web_location"  : self.glidein.web_location(),
  "javascriptrrd" : self.glidein.javascriptrrd_dir,
  "jquery"        : self.glidein.jquery_dir,
  "flot"          : self.glidein.flot_dir,
}
  #---------------------------
  def config_collectors_data(self):
    data = """
%(indent1)s<collectors>
%(indent2)s<collector node="%(usercollector_node)s:%(usercollector_port)s" 
%(indent2)s           DN="%(usercollector_gsi_dn)s" 
%(indent2)s           secondary="False"/>
""" % \
{ "indent1"              : common.indent(1),
  "indent2"              : common.indent(2),
  "usercollector_node"   : self.usercollector.hostname(),
  "usercollector_port"   : self.usercollector.collector_port(),
  "usercollector_gsi_dn" : self.usercollector.x509_gsi_dn(),
}

    #--- secondary collectors -- 
    if self.usercollector.secondary_collectors() <> 0:
      first_port = self.usercollector.secondary_collector_ports()[0] 
      last_port  = self.usercollector.secondary_collector_ports()[int(self.usercollector.secondary_collectors()) - 1]
      port_range = "%s-%s" % (first_port,last_port)
      data += """
%(indent2)s<collector node="%(usercollector_node)s:%(usercollector_port)s"
%(indent2)s           DN="%(usercollector_gsi_dn)s" 
%(indent2)s           secondary="True"/>
%(indent1)s
""" % \
{ "indent1"              : common.indent(1),
  "indent2"              : common.indent(2),
  "usercollector_node"   : self.usercollector.hostname(),
  "usercollector_port"   : port_range,
  "usercollector_gsi_dn" :self.usercollector.x509_gsi_dn(),
}
    data += """</collectors>"""
    return data
  #--------------------------
  def config_security_data(self):
    data = """
%(indent1)s<security security_name="%(service_name)s" 
%(indent1)s          proxy_selection_plugin="ProxyAll" 
%(indent1)s          classad_proxy="%(x509_proxy)s" 
%(indent1)s          proxy_DN="%(x509_gsi_dn)s">
%(indent2)s<proxies>""" % \
{ "indent1"      : common.indent(1), 
  "indent2"      : common.indent(2), 
  "service_name" : self.service_name(), 
  "x509_proxy"   : self.x509_proxy(), 
  "x509_gsi_dn"  : self.x509_gsi_dn(),
}
    proxies = self.glidein_proxy_files()
    for proxy in proxies.split(" "):
      data = data + """
%(indent3)s<proxy security_class="frontend" absfname="%(proxy)s"/>""" % \
{ "indent3" : common.indent(3),
  "proxy"   : proxy
}
    data = data + """
%(indent2)s</proxies>
%(indent1)s</security>""" % \
{ "indent1" : common.indent(1), 
  "indent2" : common.indent(2), 
}
    return data

  #--------------------------
  def config_match_data(self,schedds):
    data = """
%(indent1)s<match match_expr="True" start_expr="True">
%(indent2)s<factory>
%(indent3)s<collectors>
%(indent4)s<collector node="%(wms_node)s:%(wms_collector_port)s" DN="%(wms_gsi_gn)s" factory_identity="%(factory_username)s@%(wms_node)s" my_identity="%(frontend_identity)s@%(wms_node)s" comment="Define factory collectors globally for simplicity"/>
%(indent3)s</collectors>
%(indent2)s</factory>
%(indent2)s<job query_expr=%(job_constraints)s  comment="Define job constraint and schedds globally for simplicity">
%(indent3)s<schedds>""" % \
{ "indent1"           : common.indent(1), 
  "indent2"           : common.indent(2), 
  "indent3"           : common.indent(3), 
  "indent4"           : common.indent(4), 
  "wms_node"          : self.wms.hostname(),
  "wms_collector_port": self.wms.collector_port(),
  "wms_gsi_gn"        : self.wms.x509_gsi_dn(),
  "factory_username" : self.factory.username(),
  "frontend_identity" : self.service_name(),
  "job_constraints"   : xmlFormat.xml_quoteattr(self.userjob_constraints()),
}

    for schedd in schedds:
      data = data + """
%(indent4)s<schedd fullname="%(schedd)s" DN="%(submit_gsi_dn)s"/>""" % \
{ "indent4"        : common.indent(4),
  "schedd"         : schedd,
  "submit_gsi_dn"  : self.submit.x509_gsi_dn()
}

    data = data + """
%(indent3)s</schedds>
%(indent2)s</job>
%(indent1)s</match>
""" % \
{ "indent1"          : common.indent(1), 
  "indent2"          : common.indent(2), 
  "indent3"          : common.indent(3), 
}
    return data
  #------------------------------------------
  def config_attrs_data(self):
    return """
%(indent1)s<attrs>
%(indent2)s<attr name="GLIDEIN_Glexec_Use"      value="%(glexec_use)s"      glidein_publish="True"  job_publish="True"  parameter="False" type="string"/>
%(indent2)s<attr name="GLIDEIN_Expose_Grid_Env" value="%(expose_grid_env)s" glidein_publish="True"  job_publish="True"  parameter="False" type="string"/>
%(indent2)s<attr name="USE_MATCH_AUTH"          value="True"              glidein_publish="False" job_publish="False" parameter="True" type="string"/> 
%(indent2)s<attr name="GLIDECLIENT_Rank"      value="%(entry_rank)s"      glidein_publish="False" job_publish="False" parameter="True" type="string"/>
%(indent1)s</attrs> 
""" % \
{ "indent1"          : common.indent(1), 
  "indent2"          : common.indent(2), 
  "indent3"          : common.indent(3), 
  "glexec_use"       : self.glexec_use(),
  "expose_grid_env"  : self.expose_grid_env(),
  "entry_start"       : "True",
  "entry_rank"       : "1",
}

  #------------------------------------------
  def config_groups_data(self,match_criteria):
    return """\
%(indent1)s<groups>
%(indent2)s%(match_criteria)s
%(indent1)s</groups>
""" % \
{ "indent1"          : common.indent(1), 
  "indent2"          : common.indent(2), 
  "match_criteria"  : match_criteria,
}

  #------------------------------------------
  def config_files_data(self):
    return """\
%(indent1)s<files>
%(indent1)s</files>
""" % \
{ "indent1"          : common.indent(1), 
  "indent2"          : common.indent(2), 
}

  #---------------------------------
  def extract_factory_attrs(self):
    glidein_attrs = []
    regex = (
      re.compile("glidein\[\"attrs\"\]\[['\"](?P<attr>[^'\"]+)['\"]\]"), 
      re.compile("glidein\[\"attrs\"\]\.get\(['\"](?P<attr>[^'\"]+)['\"\)]")
    )

    for attr_re in regex:
      idx = 0
      while 1:
        attr_obj = attr_re.search(self.match_string(),idx)
        if attr_obj is None:
          break # not found
        attr_el = attr_obj.group('attr')
        if not (attr_el in glidein_attrs):
          glidein_attrs.append(attr_el)
        idx = attr_obj.end()+1
    return glidein_attrs

  #---------------------------------
  def extract_job_attrs(self):
    job_attrs = []
    regex = (
      re.compile("job\.get\(['\"](?P<attr>[^'\"]+)['\"]\)"),
      re.compile("job\[['\"](?P<attr>[^'\"]+)['\"]\]")
    )


    for attr_re in regex:
      idx=0
      while 1:
        attr_obj = attr_re.search(self.match_string(),idx)
        if attr_obj is None:
          break # not found
        attr_el=attr_obj.group('attr')
        if not (attr_el in job_attrs):
          job_attrs.append(attr_el)
        idx = attr_obj.end()+1
    return job_attrs

  #--------------------------------
  def configure_gsi_security(self):
    common.logit("")
    common.logit("Configuring GSI security")
    if len(self.colocated_services) > 0:
      common.logit("... VOFrontend  service colocated with UserCollector and/or Submit/schedd")
      common.logit("... no updates to condor mapfile required")
      return
    #--- create condor_mapfile entries ---
    condor_entries = ""
    condor_entries += common.mapfile_entry(self.x509_gsi_dn(),   self.service_name())
    condor_entries += common.mapfile_entry(self.wms.x509_gsi_dn(),    self.wms.service_name())
    condor_entries += common.mapfile_entry(self.submit.x509_gsi_dn(), self.submit.service_name())
    condor_entries += common.mapfile_entry(self.usercollector.x509_gsi_dn(), self.usercollector.service_name())
    self.__create_condor_mapfile__(condor_entries)

  #-------------------------
  def create_template(self):
    global valid_options
    print "; ------------------------------------------"
    print "; %s minimal ini options template" % self.ini_section
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

##########################################
def main(argv):
  try:
    pass
    #create_template()
    #options = validate_args(argv)
    #vo = VOFrontend(options.inifile)
    #vo.get_new_config_group()
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
  except ConfigurationError, e:
    print;print "ConfigurationError ERROR(should not get these): %s"%e;return 1
  except common.WMSerror:
    print;return 1
  return 0

#--------------------------
if __name__ == '__main__':
  sys.exit(main(sys.argv))

