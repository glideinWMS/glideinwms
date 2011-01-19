#!/usr/bin/env python

import traceback
import sys,os,os.path,string,time
import stat,re
import xml.sax.saxutils
import xmlFormat
import optparse
#-------------------------
import common
import WMSCollector
import Factory
import Submit
import UserCollector
from Certificates  import Certificates
from Condor        import Condor
from Glidein       import Glidein
from Configuration import ConfigurationError
#-------------------------
os.environ["PYTHONPATH"] = ""

frontend_options = [ "hostname", 
"username", 
"service_name", 
"frontend_identity",
"condor_location", 
"install_location", 
"logs_dir", 
"instance_name", 
"x509_cert_dir",
"gsi_credential_type", 
"cert_proxy_location", 
"gsi_dn", 
"glidein_proxy_files", 
"glidein_proxy_dns", 
"condor_tarball", 
"condor_admin_email", 
"split_condor_config", 
"install_vdt_client", 
"glexec_use",
"group_name",
"match_string",
"userjob_constraints",
"web_location",
"web_url",
"javascriptrrd_location",
"match_authentication",
"expose_grid_env",
"glideinwms_location",
"vdt_location",
"pacman_location",
]

wmscollector_options = [ 
"hostname",
"service_name",
"gsi_dn",
]

factory_options = [ 
"username",
]

submit_options = [ 
"hostname",
"service_name",
"condor_location",
"gsi_dn"
]

usercollector_options = [ 
"hostname",
"service_name",
"gsi_dn",
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



class VOFrontend(Condor):

  def __init__(self,inifile,options=None):
    global valid_options
    self.inifile = inifile
    self.ini_section = "VOFrontend"
    if options == None:
      options = valid_options[self.ini_section]
    Condor.__init__(self,self.inifile,self.ini_section,options)
    self.certificates = None
    self.daemon_list = "" 
    self.glidein = Glidein(self.inifile,self.ini_section,options)
    #-- instances of other services ---
    self.wms           = None
    self.factory       = None
    self.usercollector = None
    self.submit        = None
    self.get_wms()
    self.get_factory()
    self.get_usercollector()
    self.get_submit()
    self.colocated_services = []

  #-- get service instances --------
  def get_wms(self):
    if self.wms == None:
      self.wms = WMSCollector.WMSCollector(self.inifile,valid_options["WMSCollector"])
  #--------------------------------
  def get_factory(self):
    if self.factory == None:
      self.factory = Factory.Factory(self.inifile,valid_options["Factory"])
  #--------------------------------
  def get_usercollector(self):
    if self.usercollector == None:
      self.usercollector = UserCollector.UserCollector(self.inifile,valid_options["UserCollector"])
  #--------------------------------
  def get_submit(self):
    if self.submit == None:
      self.submit = Submit.Submit(self.inifile,valid_options["Submit"])

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
    return self.option_value("Submit","gsi_dn")
  #--------------------------------
  def UserCollectorDN(self):
    return self.option_value("UserCollector","gsi_dn")
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
  def frontend_dir(self):
    return "%s/frontend_%s-%s" % (self.glidein.install_location(),self.glidein.service_name(),self.glidein.instance_name())
  #--------------------------------
  def env_script(self):
    return "%s/frontend.sh"  % (self.glidein.install_location())
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
  def cert_proxy_location(self):
    return self.option_value(self.ini_section,"cert_proxy_location")
  #--------------------------------
  def gsi_dn(self):
    return self.option_value(self.ini_section,"gsi_dn")
  #--------------------------------
  def service_name(self):
    return self.option_value(self.ini_section,"service_name")
  #--------------------------------
  def frontend_identity(self):
    return self.option_value(self.ini_section,"frontend_identity")
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
    self.get_wms()
    self.get_factory()
    self.get_usercollector()
    self.get_submit()
    common.logit ("======== %s install starting ==========" % self.ini_section)
    ## JGW Need to figure out how to re-installa and leave condor alone
    common.ask_continue("Continue")
    self.install_vdtclient()
    self.install_certificates()
    self.validate_frontend()
    self.determine_co_located_services()
    if len(self.colocated_services) == 0:
      self.validate_condor_install()
      self.install_condor()
      self.configure_condor()
    self.configure_frontend()
    common.logit ("\n======== %s install complete ==========\n" % self.ini_section)
    self.create_frontend()
    self.start()

  #-----------------------------
  def determine_co_located_services(self):
    """ The VOFrontend service can share the same instance of Condor with
        the UserCollector and/or Schedd services.  
        So we want to check and see if this is the case.  
        We will skip the installation of Condor and just perform the 
        configuration of the condor_config file.
    """
    common.logit("\nChecking for co-located services")
    # -- if not on same node, we don't have any co-located
    if self.hostname() <> self.usercollector.hostname() and \
       self.hostname() <> self.submit.hostname():
      common.logit("... no services are co-located on this host")
      return
    common.logit("""
The VOFrontend, Submit and/or the User Collector service are being installed on 
the same host and can share the same Condor instance, as well as certificates 
and VDT client instances.""")
    #--- Condor ---
    common.logit("...... VOFrontend Condor: %s" % self.condor_location())
    common.logit(".......... Submit Condor: %s" % self.submit.condor_location())
    common.logit("... UserCollector Condor: %s" % self.usercollector.condor_location())
    if self.condor_location() == self.usercollector.condor_location():
      self.colocated_services.append("usercollector")
    else:
      common.ask_continue("""
The condor_location for UserCollector service is different. 
Do you really want to keep them separate?  
If not, stop and fix your ini file condor_location.
Do you want to continue""")

    if self.condor_location() == self.submit.condor_location():
      self.colocated_services.append("submit")
    else:
      common.ask_continue("""
The condor_location for Submit service is different. 
Do you really want to keep them separate?  
If not, stop and fix your ini file condor_location.
Do you want to continue""")
    common.logit("\nChecking for co-located services complete\n")



  #---------------------------------
  def configure_frontend(self):
    common.logit ("\nConfiguring VOFrontend started\n")
    ## JGW need some check of gsi dn's in condor mapfile and condor_config
    ## for some co-located (or maybe just from ini file) services.
    ## Not quite sure how yet
    ## self.verify_condor_gsi_settings()
    ## see Factory.check_wmspool_gsi method
    config_data  = self.get_config_data()
    #gridmap_data = self.get_gridmap_data()
    #self.create_config(config_data,gridmap_data)
    self.create_config(config_data)
    self.create_env_script()
    common.logit ("\nConfiguring VOFrontend complete\n")

  #---------------------------------
  def validate_frontend(self):
    common.logit( "\nVOFrontend dependency and validation checking starting\n")
    ##  self.glidein.__install_vdt_client__()
    self.validate_glidein_proxies()
    self.validate_glexec_use()
    self.glidein.validate_install()
    self.validate_logs_dir()
    self.glidein.create_web_directories()
    common.logit( "\nVOFrontend dependency and validation checking complete")

  #---------------------------------
  def validate_glidein_proxies(self):
    common.logit("... validating glidein_proxies")
    proxies = self.glidein_proxy_files().split(" ")
    if len(self.glidein_proxy_dns()) <> len(proxies):
      common.logerr("""The number of glidein_proxy_files (%(proxy)s) must match the number of glidein_proxy_dns (%(dns)s).""" % \
          { "proxy" : len(proxies),
            "dns"   : len(self.glidein_proxy_dns()),
          })
    proxy_dns = self.glidein_proxy_dns()
    cnt = 0
    for proxy in proxies:
      common.logit("""    glidein_proxy_files[%(position)s]: %(proxy)s
glidein_proxy_dns[%(position)i]: %(option_dn)s """ % \
            { "position"   : cnt,
              "option_dn"  : proxy_dns[cnt],
              "proxy"      : proxy, })
      dn_in_file = common.get_gsi_dn("proxy",proxy)
      if dn_in_file <> proxy_dns[cnt]:
        common.logerr("""The DN in glidein_proxy_dns is incorrect.
Should be: %(dn_in_file)s""" % { "dn_in_file" : dn_in_file, })
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
    common.make_directory(self.logs_dir(),self.username(),0755,empty_required=True)

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
      dns[self.glidein.service_name()]      = self.glidein.gsi_dn()
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
    common.logit("... %s" % self.config_file())
    common.make_directory(self.config_dir(),self.username(),0755,empty_required=True)
    common.write_file("w",0644,self.config_file(),config_xml)
    #common.logit("Creating: %s" % self.grid_mapfile())
    #gridmap_fd = open(self.grid_mapfile(),"w")
    #try:
    #  for a_uid in gridmap_data.keys():
    #    gridmap_fd.write('"%s" %s\n' % (gridmap_data[a_uid],a_uid))
    #finally:
    #  gridmap_fd.close()
    common.logit("Configuration files complete")

  #-----------------------
  def start(self):
    startup_file = "%s/frontend_startup" % (self.frontend_dir())
    if os.path.isfile(startup_file): # indicates frontend has been created
      common.start_service(self.glideinwms_location(),self.ini_section,self.inifile) 

  #-----------------------
  def create_env_script(self):
    common.logit("\nCreating VO frontend env script.")
    data = """#!/bin/bash
source %(vdt_location)s/setup.sh
source %(condor_location)s/condor.sh
""" % { "vdt_location"    : self.glidein.vdt_location(),
        "condor_location" : self.condor_location(),}
    common.write_file("w",0644,self.env_script(),data)
    common.logit("VO frontend env script created: %s" % self.env_script() )


  #---------------------------------
  def create_frontend(self):
    yn=raw_input("Do you want to create the frontend now? (y/n) [n]: ")
    cmd1 = "source %s" % self.env_script()
    cmd2 = "%s/creation/create_frontend %s" % (self.glidein.glideinwms_location(),self.config_file())
    if yn=='y':
      common.run_script("%s;%s" % (cmd1,cmd2))
    else:
      common.logit("\nTo create the frontend, you need to run the following:\n  %s\n  %s" % (cmd1,cmd2))

  #----------------------------
  def get_user_schedds(self):
    common.logit("\n... checking user and submit hosts for schedds")
    cmd1 = "source %s/condor.sh" % self.condor_location()
    cmd2 = "condor_status -schedd -format '%s\n' Name "
    fd = os.popen("%s;%s" % (cmd1,cmd2))
    lines = fd.readlines()
    err = fd.close()
    if err != None: # collector not accessible
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
        common.logerr("Failed to fetch list of schedds running condor_status -schedd\n       Your collector and submit host's condor need to be running.\n       or you have not defined any schedds on the submit host.")

    while 1:
      common.logit("\nThe following schedds have been found:")
      for i in range(len(default_schedds)):
        common.logit(" [%i] %s"%(i+1,default_schedds[i]))
      yn = raw_input("Do you want to monitor all of them?: (y/n) ")
      if (yn != "y") and (yn != "n"):
        common.logit("... please answer y or n")
        os.system("sleep 1")
        continue
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
    common.logit("\nUsing:") 
    for i in range(len(schedds)):
      common.logit(" [%i] %s"%(i+1,schedds[i]))
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
%(indent3)s<match match_expr=%(match_string)s>
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
    data = """<frontend frontend_name="%s-%s">""" %\
              (self.glidein.service_name(),
               self.glidein.instance_name())
    data = data + """\
%s
%s
%s
%s
%s
%s
%s
%s
%s
</frontend>
""" % (self.config_work_data(),
       self.config_stage_data(),
       self.config_monitor_data(),
       self.config_collectors_data(),
       self.config_security_data(),
       self.config_match_data(schedds),
       self.config_attrs_data(), 
       self.config_groups_data(match_criteria),
       self.config_files_data(),)
    return data
  #---------------------------
  def config_work_data(self):
    return """
%(indent1)s<work base_dir="%(install_location)s" base_log_dir="%(logs_dir)s"/>""" % \
{ "indent1" : common.indent(1),
  "install_location" : self.glidein.install_location(),
  "logs_dir" : self.logs_dir(),
}
  #---------------------------
  def config_stage_data(self):
    return """
%(indent1)s<stage web_base_url="%(web_url)s/%(web_dir)s/stage" base_dir="%(web_location)s/stage"/>""" % \
{ "indent1"      : common.indent(1),
  "web_url"      : self.glidein.web_url(),
  "web_dir"      : os.path.basename(self.glidein.web_location()),
  "web_location" : self.glidein.web_location(),
}
  #---------------------------
  def config_monitor_data(self):
    return """
%(indent1)s<monitor base_dir="%(web_location)s/monitor" javascriptRRD_dir="%(javascriptrrd)s" flot_dir="%(flot)s" jquery_dir="%(flot)s"/>""" % \
{ "indent1"       : common.indent(1),
  "web_location"  : self.glidein.web_location(),
  "javascriptrrd" : self.glidein.javascriptrrd(),
  "flot"          : self.glidein.flot(),
}
  #---------------------------
  def config_collectors_data(self):
    data = """
%(indent1)s<collectors>
%(indent2)s<collector node="%(usercollector_node)s:%(usercollector_port)s" DN="%(usercollector_gsi_dn)s" secondary="False"/>""" %\
{ "indent1" : common.indent(1),
  "indent2" : common.indent(2),
  "usercollector_node"   : self.usercollector.hostname(),
  "usercollector_port"   : self.usercollector.collector_port(),
  "usercollector_gsi_dn" : self.usercollector.gsi_dn(),
}

    #--- secondary collectors -- 
    if self.usercollector.secondary_collectors() <> 0:
      first_port = self.usercollector.secondary_collector_ports()[0] 
      last_port  = self.usercollector.secondary_collector_ports()[int(self.usercollector.secondary_collectors()) - 1]
      port_range = "%s-%s" % (first_port,last_port)
      data = data + """%s<collector node="%s:%s" DN="%s" secondary="True"/>""" %\
          (common.indent(2),
           self.usercollector.hostname(),
           port_range,
           self.usercollector.gsi_dn())
    data = data + """%s</collectors>""" % common.indent(1)
    return data
  #--------------------------
  def config_security_data(self):
    data = """
%(indent1)s<security security_name="%(service_name)s" proxy_selection_plugin="ProxyAll" classad_proxy="%(cert_proxy_location)s" proxy_DN="%(gsi_dn)s">
%(indent2)s<proxies>""" % \
{ "indent1" : common.indent(1), 
  "indent2" : common.indent(2), 
  "service_name"        : self.service_name(), 
  "cert_proxy_location" : self.cert_proxy_location(), 
  "gsi_dn"              : self.gsi_dn(),
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
%(indent1)s<match>
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
  "wms_gsi_gn"        : self.wms.gsi_dn(),
  "factory_username" : self.factory.username(),
  "frontend_identity" : self.service_name(),
  "job_constraints"   : xmlFormat.xml_quoteattr(self.userjob_constraints()),
}

    for schedd in schedds:
      data = data + """
%(indent4)s<schedd fullname="%(schedd)s" DN="%(submit_gsi_dn)s"/>""" % \
{ "indent4"        : common.indent(4),
  "schedd"         : schedd,
  "submit_gsi_dn"  : self.submit.gsi_dn()
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
%(indent2)s<attr name="USE_MATCH_AUTH"          value="%(use_match_auth)s"  glidein_publish="False" job_publish="False" parameter="True" type="string"/> 
%(indent2)s<attr name="GLIDEIN_Entry_Start"     value="%(entry_start)s"     glidein_publish="False" job_publish="False" parameter="True" type="string"/>
%(indent2)s<attr name="GLIDEIN_Entry_Rank"      value="%(entry_rank)s"      glidein_publish="False" job_publish="False" parameter="True" type="string"/>
%(indent1)s</attrs> 
""" % \
{ "indent1"          : common.indent(1), 
  "indent2"          : common.indent(2), 
  "indent3"          : common.indent(3), 
  "glexec_use"       : self.glexec_use(),
  "expose_grid_env"  : self.expose_grid_env(),
  "use_match_auth"   : self.glidein.match_authentication() == "y",
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
    attr_re = re.compile("glidein\[\"attrs\"\]\[['\"](?P<attr>[^'\"]+)['\"]\]")
    idx = 0
    while 1:
      attr_obj = attr_re.search(self.match_string(),idx)
      if attr_obj == None:
        break # not found
      attr_el = attr_obj.group('attr')
      if not (attr_el in glidein_attrs):
        glidein_attrs.append(attr_el)
      idx = attr_obj.end()+1
    return glidein_attrs

  #---------------------------------
  def extract_job_attrs(self):
    job_attrs = []
    attr_re = re.compile("job\[['\"](?P<attr>[^'\"]+)['\"]\]")
    idx=0
    while 1:
      attr_obj = attr_re.search(self.match_string(),idx)
      if attr_obj == None:
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
    common.validate_gsi(self.gsi_dn(),self.gsi_credential_type(),self.cert_proxy_location())
    #--- create condor_mapfile entries ---
    condor_entries = ""
    condor_entries += common.mapfile_entry(self.gsi_dn(),               self.service_name())
    condor_entries += common.mapfile_entry(self.wms.gsi_dn(),           self.wms.service_name())
    condor_entries += common.mapfile_entry(self.submit.gsi_dn(),        self.submit.service_name())
    condor_entries += common.mapfile_entry(self.usercollector.gsi_dn(), self.usercollector.service_name())
    self.__create_condor_mapfile__(condor_entries)

#    NOT REALLY NEEDED AS THERE ARE NO DAEMONS ASSOCIATED WITH THIS SERVICE
#    #-- create the condor config file entries ---
#    gsi_daemon_entries = """\
## --- Submit user: %s
#GSI_DAEMON_NAME=%s
# --- WMS collector user: %s
#GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
# --- Submit user: %s
#GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
# --- Userpool user: %s
#GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
#""" % \
#          (self.gsi_dn(),         self.service_name(),
#       self.wms.gsi_dn(),     self.wms.service_name(),
#    self.submit.gsi_dn(),  self.submit.service_name(),
#  self.usercollector.gsi_dn(),self.usercollector.service_name())

#    #-- update the condor config file entries ---
#    self.__update_gsi_daemon_names__(gsi_daemon_entries)

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
  except ConfigurationError, e:
    print;print "ConfigurationError ERROR(should not get these): %s"%e;return 1
  except common.WMSerror:
    print;return 1
  return 0

#--------------------------
if __name__ == '__main__':
  sys.exit(main(sys.argv))

