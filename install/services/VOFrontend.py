#!/bin/env python

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

valid_options = [ "node", 
"unix_acct", 
"service_name", 
"condor_location", 
"install_location", 
"logs_location", 
"instance_name", 
"gsi_authentication", 
"cert_proxy_location", 
"gsi_dn", 
"glidein_proxies", 
"glidein_proxies_dns", 
"condor_tarball", 
"condor_admin_email", 
"split_condor_config", 
"install_vdt_client", 
"glexec_use",
"match_string",
"web_location",
"web_url",
"javascriptrrd",
"flot",
"m2crypto",
"javascriptrrd_tarball",
"flot_tarball",
"m2crypto_tarball",
"match_authentication",
"expose_grid_env",
"glidein_install_dir",
]

class VOFrontend(Condor):

  def __init__(self,inifile):
    global valid_options
    self.inifile = inifile
    self.ini_section = "VOFrontend"
    Condor.__init__(self,self.inifile,self.ini_section,valid_options)
    #self.certificates = self.option_value(self.ini_section,"certificates")
    self.certificates = None
    self.daemon_list = "MASTER" 

    self.glidein = Glidein(self.inifile,self.ini_section,valid_options)
    self.config_dir   = "%s/instance_%s.cfg" % (self.glidein.install_location(),self.glidein.instance_name())
    self.config_file  = "%s/glidein.xml" % (self.config_dir)
    self.grid_mapfile = "%s/grid_mapfile" % (self.config_dir)

    self.frontend_dir = "%s/frontend_%s-%s" % (self.glidein.install_location(),self.glidein.service_name(),self.glidein.instance_name())
    self.env_script   = "%s/frontend.sh"  % (self.glidein.install_location())
    #-- instances of other services ---
    self.wms      = None
    self.factory  = None
    self.userpool = None
    self.submit   = None

  #-- get service instances --------
  def get_wms(self):
    if self.wms == None:
      self.wms = WMSCollector.WMSCollector(self.inifile)
  def get_factory(self):
    if self.factory == None:
      self.factory = Factory.Factory(self.inifile)
  def get_userpool(self):
    if self.userpool == None:
      self.userpool = UserCollector.UserCollector(self.inifile)
  def get_submit(self):
    if self.submit == None:
      self.submit = Submit.Submit(self.inifile)
  #--------------------------------
  def WMSCollector(self):
    return self.option_value("WMSCollector","node")
  #--------------------------------
  def WMSCollector_unix_acct(self):
    return self.option_value("Factory","unix_acct")
  #--------------------------------
  def UserCollector(self):
    return self.option_value("UserCollector","node")
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
  def logs_location(self):
    return self.option_value(self.ini_section,"logs_location")
  #--------------------------------
  def match_string(self):
    return self.option_value(self.ini_section,"match_string")
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
  def expose_grid_env(self):
    return self.option_value(self.ini_section,"expose_grid_env")
  #--------------------------------
  def glexec_use(self):
    return string.upper(self.option_value(self.ini_section,"glexec_use"))
  #--------------------------------
  def glidein_proxies(self):
    return   self.option_value(self.ini_section,"glidein_proxies")
  #--------------------------------
  def glidein_proxies_dns(self):
    dns = self.option_value(self.ini_section,"glidein_proxies_dns")
    dn_list = string.split(dns,";")
    return dn_list
    

  #--------------------------------
  def install(self):
    self.get_wms()
    self.get_factory()
    self.get_userpool()
    self.get_submit()
    common.logit ("======== %s install starting ==========" % self.ini_section)
    ## JGW Need to figure out how to re-installa and leave condor alone
    self.validate_install()
    self.glidein.validate_install()
    self.glidein.__install_vdt_client__()
    self.glidein.create_web_directories()
    common.make_directory(self.install_location(),self.unix_acct(),0755,empty_required=True)
    common.make_directory(self.logs_location(),self.unix_acct(),0755,empty_required=True)
    self.install_condor()
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
    self.create_frontend()
    self.start()
    common.logit ("======== %s install complete ==========" % self.ini_section)

  #---------------------------------
  def validate_install(self):
    #-- glexec use values ---
    valid_glexec_use_values = [ "REQUIRED","OPTIONAL","NEVER" ]
    if self.glexec_use() not in valid_glexec_use_values:
      common.logerr("The glexec_use value specified (%s) in the ini file is invalid.\n      Valid values are: %s" % (self.glexec_use(),valid_glexec_use_values)) 

  #---------------------------------
  def get_config_data(self):
    common.logit("\nCollecting  configuration file data. It will be question/answer time.")
    schedds         = self.get_user_schedds()
    job_constraints = self.get_job_constraints()
    match_criteria  = self.get_match_criteria()
    config_xml = self.config_data(schedds,job_constraints,match_criteria)
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
The frontend proxy, user pool collector and submit node DNs are required in
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
    common.make_directory(self.config_dir,self.unix_acct(),0755,empty_required=True)
    common.write_file("w",0644,self.config_file,config_xml)
    #common.logit("Creating: %s" % self.grid_mapfile)
    #gridmap_fd = open(self.grid_mapfile,"w")
    #try:
    #  for a_uid in gridmap_data.keys():
    #    gridmap_fd.write('"%s" %s\n' % (gridmap_data[a_uid],a_uid))
    #finally:
    #  gridmap_fd.close()
    common.logit("Configuration files complete")

  #-----------------------
  def start(self):
    startup_file = "%s/frontend_startup" % (self.frontend_dir)
    cmd1 = "source %s" % self.env_script
    cmd2 = "cd %s;./frontend_startup start" % (self.frontend_dir)
    common.logit("\nTo start the frontend you need to run the following:\n  %s\n  %s" % (cmd1,cmd2))
    if os.path.isfile(startup_file):
      yn = "n"
      yn = raw_input("\nDo you want to start the frontend now? (y/n) [%s]: " % yn)
      if yn == "y":
        common.run_script("%s;%s" % (cmd1,cmd2))
      

  #-----------------------
  def create_env_script(self):
    common.logit("\nCreating VO frontend env script.")
    data = """#!/bin/bash
source %s/setup.sh
export PYTHONPATH=%s/usr/lib/python2.3/site-packages:$PYTHONPATH
source %s/condor.sh
""" % (self.glidein.vdt_location(),self.glidein.m2crypto(),self.condor_location())
    common.write_file("w",0644,self.env_script,data)
    common.logit("VO frontend env script created: %s" % self.env_script )


  #---------------------------------
  def create_frontend(self):
    yn=raw_input("Do you want to create the frontend now? (y/n) [n]: ")
    cmd1 = "source %s" % self.env_script
    cmd2 = "%s/creation/create_frontend %s" % (self.glidein.glidein_install_dir(),self.config_file)
    if yn=='y':
      common.run_script("%s;%s" % (cmd1,cmd2))
    else:
      common.logit("\nTo create the frontend, you need to run the following:\n  %s\n  %s" % (cmd1,cmd2))

  #----------------------------
  def get_user_schedds(self):
    common.logit("\n... checking user and submit nodes for schedds")
    cmd1 = "source %s/condor.sh" % self.condor_location()
    cmd2 = "condor_status -schedd -format '%s\n' Name "
    fd = os.popen("%s;%s" % (cmd1,cmd2))
    lines = fd.readlines()
    err = fd.close()
    if err != None: # collector not accessible
        common.logit("%s" % lines)
        common.logerr("Failed to fetch list of schedds running condor_status -schedd\n       Your user pool collector and submit node condor need to be running.")
    if len(lines) == 0: # submit schedds not accessible
        common.logerr("Failed to fetch list of schedds running condor_status -schedd\n       Your submit node condor needs to be running.")

    default_schedds=[]
    for line in lines:
        line = line[:-1] #remove newline
        if line != "":
            default_schedds.append(line)

    if len(default_schedds) == 0:
        common.logerr("Failed to fetch list of schedds running condor_status -schedd\n       Your collector and submit node condor need to be running.\n       or you have not defined any schedds on the submit node.")

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

  #----------------------------
  def get_job_constraints(self):
    default_job_constraint = "(JobUniverse==5)&&(GLIDEIN_Is_Monitor =!= TRUE)&&(JOB_Is_Monitor =!= TRUE)"
    job_constraint = raw_input("\nWhat kind of jobs do you want to monitor?: [%s] "%default_job_constraint)
    if job_constraint == "":
      job_constraint = default_job_constraint
    return job_constraint
                    

  #---------------------------------------
  def get_match_criteria(self):
    """ Determine the job constraints/matching criteria for submitting jobs."""
    #--- define group ---
    def_group_name="main"
    group_name = raw_input("\nGive a name to the main group: [%s] " % def_group_name)
    if group_name == "":
      group_name=def_group_name

    #-- match criteria ---
    print """
What expression do you want to use to match glideins to jobs?
It is an arbitrary python boolean expression using the dictionaries
glidein and job.

A simple example expression would be:
  glidein["attrs"]["GLIDEIN_Site"] in job["DESIRED_Sites"].split(",")

If you want to match all (OK for simple setups), specify True (the default)
"""
    default_match_str="True"
    match_str = raw_input("Match string: [%s] " % default_match_str)
    if match_str == "":
      match_str = default_match_str

  #-- factory attributes ----
    print """
What glidein/factory attributres are you using in the match expression?
I have computed my best estimate for your match string,
please verify and correct if needed.
"""
    default_factory_attributes = string.join(self.extract_factory_attrs(match_str),',')
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
    default_job_attributes = string.join(self.extract_job_attrs(match_str),',')
    job_attributes = raw_input("Job attributes: [%s] " % default_job_attributes)
    if job_attributes == "":
      job_attributes = default_job_attributes
    if job_attributes == "":
      job_attributes = []
    else:
      job_attributes = string.split(job_attributes,',')

    #--- create xml ----
    data  = """%s<group name="%s" enabled="True">""" % (common.indent(2),group_name)
    data = data + """%s<match match_expr=%s>""" % (common.indent(3),xmlFormat.xml_quoteattr(match_str))
    data = data + """%s%s""" % (common.indent(4),self.factory_data(factory_attributes))
    data = data + """%s%s""" % (common.indent(4),self.factory_data(job_attributes))
    data = data + """%s</match>""" % (common.indent(3))
    data = data + """%s</group>""" % (common.indent(2))
    return data 

  #-----------------------
  def factory_data(self,attributes):
    data = ""
    if len(attributes)>0:
      attr_query_arr=[]

      for attr in attributes:
        attr_query_arr.append("(%s=!=UNDEFINED)" % attr)
      data = data + """\
        <factory query_expr=%s>
          <match_attrs>
""" % xmlFormat.xml_quoteattr(string.join(attr_query_arr," && "))

      for attr in attributes:
        data = data + """\
            <match_attr name="%s" type="string"/>
""" % attr
      data = data + """\
          </match_attrs>
        </factory>
"""
    return data

  #-----------------------
  def job_data(self,attributes):
    data = ""
    if len(attributes)>0:
      attr_query_arr=[]
      for attr in attributes:
        attr_query_arr.append("(%s=!=UNDEFINED)" % attr)

      data = data + """\
        <job query_expr=%s>
          <match_attrs>
""" % xmlFormat.xml_quoteattr(string.join(attr_query_arr," && "))

      for attr in attributes:
        data = data + """\
            <match_attr name="%s" type="string"/>
""" % attr
      data = data + """\
          </match_attrs>
        </job>
"""
    return data


  #--------------------------------
  def config_data(self,schedds,job_constraints,match_criteria): 
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
       self.config_match_data(schedds,job_constraints),
       self.config_attrs_data(), 
       self.config_groups_data(match_criteria),
       self.config_files_data(),)
    return data
  #---------------------------
  def config_work_data(self):
    return """%s<work base_dir="%s" base_log_dir="%s"/>""" % (common.indent(1),self.glidein.install_location(),self.logs_location())
  #---------------------------
  def config_stage_data(self):
    return """%s<stage web_base_url="%s/%s/stage" base_dir="%s/stage"/>""" %\
           (common.indent(1),
            self.glidein.web_url(),
            os.path.basename(self.glidein.web_location()),
            self.glidein.web_location())
  #---------------------------
  def config_monitor_data(self):
    return """%s<monitor base_dir="%s/monitor" javascriptRRD_dir="%s" flot_dir="%s" jquery_dir="%s"/>""" %\
           (common.indent(1),
            self.glidein.web_location(),
            self.glidein.javascriptrrd(),
            self.glidein.flot(),
            self.glidein.flot())
  #---------------------------
  def config_collectors_data(self):
    data = """%s<collectors>""" % common.indent(1)
    data = data + """%s<collector node="%s:%s" DN="%s" secondary="False"/>""" %\
          (common.indent(2),
           self.userpool.node(),
           self.userpool.collector_port(),
           self.userpool.gsi_dn())
    #--- secondary collectors -- 
    if self.userpool.secondary_collectors() <> 0:
      first_port = self.userpool.secondary_collector_ports()[0] 
      last_port  = self.userpool.secondary_collector_ports()[int(self.userpool.secondary_collectors()) - 1]
      port_range = "%s-%s" % (first_port,last_port)
      data = data + """%s<collector node="%s:%s" DN="%s" secondary="True"/>""" %\
          (common.indent(2),
           self.userpool.node(),
           port_range,
           self.userpool.gsi_dn())
    data = data + """%s</collectors>""" % common.indent(1)
    return data
  #--------------------------
  def config_security_data(self):
    data = """%s<security security_name="%s" proxy_selection_plugin="ProxyAll" classad_proxy="%s" proxy_DN="%s">""" %\
             (common.indent(1), self.service_name(), self.cert_proxy_location(), self.gsi_dn())
    data = data + """%s<proxies>"""   % (common.indent(2))
    proxies = self.glidein_proxies()
    for proxy in proxies.split(" "):
      data = data + """%s<proxy absfname="%s"/>""" % (common.indent(3),proxy)
    data = data + """%s</proxies>"""  % (common.indent(2))
    data = data + """%s</security>""" % (common.indent(1))
    return data
  #--------------------------
  def config_match_data(self,schedds,job_constraints):
    data = """%s<match>"""             % (common.indent(1))
    data = data + """%s<factory>"""    % (common.indent(2))
    data = data + """%s<collectors>""" % (common.indent(3))
    data = data + """%s<collector node="%s" DN="%s" factory_identity="%s@%s" my_identity="%s@%s" comment="Define factory collectors globally for simplicity"/>""" %\
           (common.indent(4), self.wms.node(),self.wms.gsi_dn(),self.factory.unix_acct(),self.factory.node(),self.service_name(),self.factory.node())
    data = data + """%s</collectors>""" % (common.indent(3))
    data = data + """%s</factory>"""    % (common.indent(2))
    data = data + """%s<job query_expr=%s  comment="Define job constraint and schedds globally for simplicity">""" %\
           (common.indent(2),xmlFormat.xml_quoteattr(job_constraints))
    data = data + """%s<schedds>"""    % (common.indent(3))
    for schedd in schedds:
      data = data + """%s<schedd fullname="%s" DN="%s"/>""" % (common.indent(4),schedd,self.submit.gsi_dn())
    data = data + """%s</schedds>"""    % (common.indent(3))

    data = data + """%s</job>"""        % (common.indent(2))
    data = data + """%s</match>"""      % (common.indent(1))
    return data
  #------------------------------------------
  def config_attrs_data(self):
    data = """%s<attrs>""" % (common.indent(1))
    data = data + """%s<attr name="GLIDEIN_Glexec_Use" value="%s" glidein_publish="True" job_publish="True" parameter="False" type="string"/>""" %\
            (common.indent(2),self.glexec_use())
    data = data + """%s<attr name="GLIDEIN_Expose_Grid_Env" value="%s" glidein_publish="True" job_publish="True" parameter="False" type="string"/>""" %\
            (common.indent(2),self.expose_grid_env())
    data = data + """%s<attr name="USE_MATCH_AUTH" value="%s" glidein_publish="False" job_publish="False" parameter="True" type="string"/> """ %\
           (common.indent(2),self.glidein.match_authentication() == "y")
    data = data + """%s<attr name="GLIDEIN_Entry_Start" value="%s" glidein_publish="False" job_publish="False" parameter="True" type="string"/>""" %\
            (common.indent(2),"True")
    data = data + """%s<attr name="GLIDEIN_Entry_Rank" value="%s" glidein_publish="False" job_publish="False" parameter="True" type="string"/>""" %\
            (common.indent(2),"1")
    data = data + """%s</attrs>""" % (common.indent(1))
    return data
  #------------------------------------------
  def config_groups_data(self,match_criteria):
    data = """%s<groups>""" % (common.indent(1)) 
    data = data + """%s%s""" % (common.indent(2),match_criteria)
    data = data + """%s</groups>""" % (common.indent(1)) 
    return data
  #------------------------------------------
  def config_files_data(self):
    data = """%s<files>""" % (common.indent(1)) 
    data = data +"""%s</files>""" % (common.indent(1)) 
    return data

  #---------------------------------
  def extract_factory_attrs(self,match_str):
    glidein_attrs = []
    attr_re = re.compile("glidein\[\"attrs\"\]\[['\"](?P<attr>[^'\"]+)['\"]\]")
    idx = 0
    while 1:
      attr_obj = attr_re.search(match_str,idx)
      if attr_obj == None:
        break # not found
      attr_el = attr_obj.group('attr')
      if not (attr_el in glidein_attrs):
        glidein_attrs.append(attr_el)
      idx = attr_obj.end()+1
    return glidein_attrs

  #---------------------------------
  def extract_job_attrs(self,match_str):
    job_attrs = []
    attr_re = re.compile("job\[['\"](?P<attr>[^'\"]+)['\"]\]")
    idx=0
    while 1:
      attr_obj = attr_re.search(match_str,idx)
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
    common.validate_gsi(self.gsi_dn(),self.gsi_authentication,self.cert_proxy_location())
    #--- create condor_mapfile entries ---
    condor_mapfile = """\
GSI "^%s$" %s
GSI "^%s$" %s
GSI "^%s$" %s
GSI "^%s$" %s""" % \
          (re.escape(self.gsi_dn()),         self.service_name(),
       re.escape(self.wms.gsi_dn()),     self.wms.service_name(),
    re.escape(self.submit.gsi_dn()),  self.submit.service_name(),
  re.escape(self.userpool.gsi_dn()),self.userpool.service_name())

    self.__create_condor_mapfile__(condor_mapfile)

#### ----------------------------------------------
#### No longer required effective with 7.5.1
#### ----------------------------------------------
#    #-- create the condor config file entries ---
#    gsi_daemon_entries = """\
## --- Submit user: %s
#GSI_DAEMON_NAME=%s
## --- WMS collector user: %s
#GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
## --- Submit user: %s
#GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
## --- Userpool user: %s
#GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),%s
#""" % \
#          (self.gsi_dn(),         self.service_name(),
#       self.wms.gsi_dn(),     self.wms.service_name(),
#    self.submit.gsi_dn(),  self.submit.service_name(),
#  self.userpool.gsi_dn(),self.userpool.service_name())
#
#    #-- update the condor config file entries ---
#    self.__update_condor_config_gsi__(gsi_daemon_entries)

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

##########################################
def main(argv):
  try:
    options = validate_args(argv)
    vo = VOFrontend(options.inifile)
    #vo.install()
    vo.get_userpool()
    print vo.config_collectors_data()
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

