#!/usr/bin/env python

import common
from Configuration import Configuration
from Configuration import ConfigurationError
import Certificates  
import VDTClient
#---------------------
import sys,os,os.path,string,time,re
import popen2
import tarfile
import shutil
import pwd
import stat
import commands
import traceback


class Condor(Configuration):

  def __init__(self,inifile,ini_section,ini_options):
    self.ini_section = ini_section
    self.inifile     = inifile
    self.ini_options = ini_options
    Configuration.__init__(self,inifile)
    self.validate_section(self.ini_section,self.ini_options)

    self.use_gridmanager           = False
    self.userjob_classads_required = False
    self.daemon_list = None
    self.schedd_name_suffix = "jobs"
   
    self.client_only_install = False # VOFrontend is only one which will reset

    self.condor_version      = None
    self.condor_first_dir    = None

    #--- secondary schedd files --
    ## self.schedd_setup_file   = "new_schedd_setup.sh"
    ## self.schedd_init_file    = "init_schedd.sh"
    ## self.schedd_startup_file = "start_master_schedd.sh"
    self.schedd_initd_function = "return # no secondary schedds"

    #--- condor config data --
    self.condor_config_data = { "00_gwms_general"     : "",
                                "01_gwms_collectors"  : "",
                                "02_gwms_schedds"     : "",
                                "03_gwms_local"       : "",
                              }

    #-- classes used ---
    self.certs = None
    self.get_certs()

  #--- instantiate objects needed ----
  def get_certs(self):
    if self.certs == None:
      self.certs = Certificates.Certificates(self.inifile,self.ini_section)

  #-----------------------------------------------------------
  # abstract methods that must be defined in a parent class
  #-----------------------------------------------------------
  def condor_config_daemon_users(self):
    """ Abstract method that must be defined in the parent class. """
    common.logerr("""System error: A condor_config_daemon_users method must
be defined in the parent class.  This method returns a nested list of users
authorized to access Condor's daemon functions based on the service being
provided.  It is used to populate the Condor GSI_DAEMON_NAME attribute.

The format of the list is:
[["SERVICE 1","GSI_DN_1","NICKNAME_1"],["SERVICE 2","GSI_DN_2","NICKNAME_2"],]

This is an example of the result in the condor config file:
###################################
# Whitelist of condor daemon DNs
###################################
# --- SERVICE 1: NICKNAME_1
GSI_DAEMON_NAME=GSI_DN_1
# --- SERVICE 2: NICKNAME_2
GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),GSI_DN_2

If no specific entries are needed, an empty list should be returned.
""")
  #----------------------------------
  # methods for returning attributes
  #----------------------------------
  #----------------------------------
  def set_daemon_list(self,list):
    self.daemon_list = list
  #----------------------------------
  def install_type(self):
    return self.option_value(self.ini_section,"install_type")
  #----------------------------------
  def install_vdt_client(self):
    return self.option_value(self.ini_section,"install_vdt_client")
  #----------------------------------
  def condor_ids(self):
      user = pwd.getpwnam(self.username())
      return  "%s.%s" % (user[2],user[3])
  #----------------------------------
  def condor_location(self):
    return self.option_value(self.ini_section,"condor_location")
  #---------------------
  def condor_local(self):
    if self.install_type() == "tarball":
      return "%s/%s" % (self.condor_location(),"condor_local")
    elif self.install_type() == "rpm":
      return "%s/%s" % (self.condor_config_dir(),"condor_local")
    else: 
      common.logerr("Invalid install_type option in ini file.")
  #---------------------
  def condor_config_dir(self):
    if self.install_type() == "tarball":
      return "%s/%s" % (self.condor_location(),"etc")
    elif self.install_type() == "rpm":
      return "/etc/condor"
    else: 
      common.logerr("Invalid install_type option in ini file.")
  #----------------------------------
  def condor_config(self):
      return "%s/%s" % (self.condor_config_dir(),"condor_config")
  #----------------------------------
  def local_config_dir(self):
    if self.install_type() == "tarball":
      return "%s/%s" % (self.condor_location(),"config.d")
    elif self.install_type() == "rpm":
      return "/etc/condor/config.d" 
    else: 
      common.logerr("Invalid install_type option in ini file.")
  #---------------------
  def condor_mapfile(self):
    if self.install_type() == "tarball":
      return "%s/certs/condor_mapfile" % self.condor_location()
    elif self.install_type() == "rpm" :
      return "%s/certs/condor_mapfile" % self.condor_config_dir()
    else: 
      common.logerr("Invalid install_type option in ini file.")
  #----------------------------------
  def install_location(self):
    return self.option_value(self.ini_section,"install_location")
  #----------------------------------
  def glideinwms_location(self):
    return self.option_value(self.ini_section,"glideinwms_location")
  #----------------------------------
  def vdt_location(self):
    return self.option_value(self.ini_section,"vdt_location")
  #---------------------
  def username(self):
    return self.option_value(self.ini_section,"username")
  #---------------------
  def service_name(self):
    return self.option_value(self.ini_section,"service_name")
  #---------------------
  def hostname(self):
    return self.option_value(self.ini_section,"hostname")
  #---------------------
  def condor_tarball(self):
    return self.option_value(self.ini_section,"condor_tarball")
  #---------------------
  def admin_email(self):
    return self.option_value(self.ini_section,"condor_admin_email")
  #---------------------
  def x509_cert_dir(self):
    return self.certs.x509_cert_dir()
  #---------------------
  def x509_proxy(self):
    if self.has_option(self.ini_section,"x509_proxy"):
      return self.option_value(self.ini_section,"x509_proxy")
    common.logerr("The x509_proxy option is required for this service.")
  #---------------------
  def x509_cert(self):
    return self.option_value(self.ini_section,"x509_cert")
  #---------------------
  def x509_key(self):
    return self.option_value(self.ini_section,"x509_key")
  #----------------------------------
  def x509_gsi_dn(self):
    return self.option_value(self.ini_section,"x509_gsi_dn")
  #---------------------
  def initd_script(self):
    return  "%s/condor" % (self.condor_location())
  #---------------------
  def activate_userjob_classads(self):
    self.userjob_classads_required = True
  #---------------------
  def privilege_separation(self):
    if self.has_option(self.ini_section,"privilege_separation"):
      return self.option_value(self.ini_section,"privilege_separation")
    return "n"
  #---------------------
  def number_of_schedds(self):
    option = "number_of_schedds"
    if self.daemon_list.find("SCHEDD") > 0:
      if not self.has_option(self.ini_section,option):
        return int(1)
    value =  self.option_value(self.ini_section,option)
    if common.not_an_integer(value):
      common.logerr("%s option is not a number: %s" % (option,value))
    return int(value)
  #---------------------
  def schedd_shared_port(self):
    """ Returns the shared port number if specified, else zero."""
    option = "schedd_shared_port"
    if not self.has_option(self.ini_section,option):
      return int(0)
    value =  self.option_value(self.ini_section,option)
    if len(value) == 0:
      return int(0)
    if common.not_an_integer(value):
      common.logerr("%s option is not a number: %s" % (option,value))
    return int(value)
  #----------------------------------
  def collector_port(self):
    option = "collector_port"
    if not self.has_option(self.ini_section,option):
      return int(9618)
    value = self.option_value(self.ini_section,option)
    if common.not_an_integer(value):
      common.logerr("%s option is not a number: %s" % (option,value))
    return int(value)
  #---------------------
  def secondary_collectors(self):
    option = "number_of_secondary_collectors"
    if not self.has_option(self.ini_section,option):
      return int(0)
    value = self.option_value(self.ini_section,option)
    if common.not_an_integer(value):
      common.logerr("%s option is not a number: %s" % (option,value))
    return int(value)
  #---------------------
  def secondary_collector_ports(self):
    ports = []
    if self.secondary_collectors() == 0:
      return ports  # none
    collectors = int(self.secondary_collectors())
    for nbr in range(collectors):
      ports.append(int(self.collector_port()) + nbr + 1)
    return ports
  #--------------------------------
  def stop_condor(self):
    if self.client_only_install == True:
      common.logerr( "This is a client only install. Nothing to stop.")
    if self.install_type() == 'rpm':
      common.run_script("service condor stop")
    else: 
      if os.path.isfile(self.initd_script()):
        common.logit( "... stopping condor as user %s" % self.username())
        common.run_script("%s stop" % self.initd_script())
    common.run_script("sleep 2")

  #--------------------------------
  def start_condor(self):
    if self.client_only_install == True:
      common.logerr( "This is a client only install. Nothing to start.")
    if self.install_type() == 'rpm':
      common.run_script("service condor start")
    else: 
      if os.path.isfile(self.initd_script()):
        common.logit( "... starting condor as user %s" % self.username())
        common.run_script("%s start" % self.initd_script())
      else:
        common.logerr("Condor startup script does not exist: " % self.initd_script())
    common.run_script("sleep 10")
  #--------------------------------
  def restart_condor(self):
    if self.client_only_install == True:
      common.logerr( "This is a client only install. Nothing to restart.")
    if self.install_type() == 'rpm':
      common.run_script("service condor restart")
    else:
      if os.path.isfile(self.initd_script()):
        common.logit( "... restarting condor as user %s" % self.username())
        common.run_script("%s restart" % self.initd_script())
      else:
        common.logerr("Condor startup script does not exist: " % self.initd_script())
    common.run_script("sleep 10")

  #--------------------------------
  def install_certificates(self):
    """ Certificates are required for Condor GSI authentication. """
    self.get_certs()
    self.certs.install()

  #--------------------------------
  def install_vdtclient(self):
    if self.install_vdt_client() == "y":
      vdt = VDTClient.VDTClient(self.ini_section,self.inifile)
      vdt.install()
    else:
      common.logit("\n... VDT client install not requested.")

  #--------------------------------
  def validate_condor_install(self):
    common.logit( "\nVerifying Condor options")
    common.validate_install_type(self.install_type())
    self.__validate_tarball__(self.condor_tarball())
    common.validate_hostname(self.hostname())
    common.validate_user(self.username())
    common.validate_email(self.admin_email())
    if self.ini_section == "VOFrontend":
      common.validate_gsi_for_proxy(self.x509_gsi_dn(), self.x509_proxy() )
    else:
      common.validate_gsi_for_cert(self.x509_gsi_dn(), self.x509_cert(), self.x509_key() )
    self.__validate_collector_port__()
    self.__validate_secondary_collectors__()
    self.__validate_schedds__()
    self.__validate_schedd_shared_port__()
    self.__validate_needed_directories__()
    common.logit( "Verification complete\n")

  #--------------------------------
  def __validate_condor_location__(self):
    common.logit("... validating condor_location: %s" % self.condor_location())
    if self.install_type() == "tarball":
      common.make_directory(self.condor_location(),self.username(),0755)

  #--------------------------------
  def validate_condor_installation(self):
    file = "%s/condor.sh" % self.condor_location()
    if not os.path.isfile(file):
      common.logerr("""Condor does not appear to be installed. Cannot locate:
  %s""" % file)

  #--------------------------------
  def condor_is_installed(self):
    file = "%s/condor.sh" % self.condor_location()
    if os.path.isfile(file):
      return True
    else:
      return False

  #--------------------------------
  def get_condor_config_data(self):
    self.validate_condor_installation()
    self.__check_condor_version__()
    self.__condor_config_gwms_data__()
    self.__condor_config_daemon_list__()
    self.__condor_config_gsi_data__(self.condor_config_daemon_users())
    self.__condor_config_negotiator_data__()
    self.__condor_config_collector_data__()
    self.__condor_config_secondary_collector_data__()
    self.__condor_config_schedd_data__()
    self.__condor_config_secondary_schedd_data__()
    self.__condor_config_userjob_default_attributes_data__()

  #-------------------------------
  def __check_condor_version__(self):
    """ Gets the Condor version from a collocated Condor instance.
        Normally this would come from the tarball but no reason to use it
        if services are collocated.
    """
    common.logit("... checking Condor version")
    if self.condor_version <> None:
      common.logit("    Condor version: %s" % self.condor_version)
      return   # we already have it
    version_script = "%s/%s" % (self.condor_location(),"bin/condor_version")
    if not os.path.isfile(version_script):
      common.logerr("""Unable to determine condor version using: 
  %s
Is Condor really installed where you said it was or was it not successful?
Check the condor_location ini option for correctness.""" % version_script)
    
    cmds = "%s| awk '{print $2;exit}'" % version_script
    (status, self.condor_version) = commands.getstatusoutput(cmds)
    if status > 0:
      common.logerr("""Unable to determine Condor version using:
  %s""" % version_script)
    if self.condor_version == None:
      common.logerr("Still unable to determine condor_version")
    common.logit("    Condor version: %s" % self.condor_version)

  #--------------------------------
  def __install_condor__(self):
    if self.install_type() == "rpm":
      common.logerr("""Your 'install_type' option indicates this is an RPM install of Condor.
You can only use the '--configure/--validate' options for this type.
""")
    self.__validate_needed_directories__()
    self.__verify_directories_empty__()
    common.logit("\nCondor installation starting\n")
    common.logit("... install location: %s" % (self.condor_location()))
    try:
      tar_dir = "%s/tar" % (self.condor_location())
      if not os.path.isdir(tar_dir):
        os.makedirs(tar_dir)
    except Exception,e:
      common.logerr("Condor installation failed. Cannot make %s directory: %s" % (tar_dir,e))
    
    try:
        common.logit("... extracting tarball: %s" % self.condor_tarball())
        common.logit("    into: %s" % tar_dir)
        fd = tarfile.open(self.condor_tarball(),"r:gz")
        #-- first create the regular files --
        for f in fd.getmembers():
          if not f.islnk():
            fd.extract(f,tar_dir)
        #-- then create the links --
        for f in fd.getmembers():
          if f.islnk():
            os.link(os.path.join(tar_dir,f.linkname),os.path.join(tar_dir,f.name))
        fd.close()
        
        common.logit( "... running condor_configure\n")
        install_str = "%s/%s" % (tar_dir,self.condor_first_dir)
        if not os.path.isfile("%s/condor_configure" % install_str):
          common.logerr("Cannot find path to condor_configure in: %s" % (install_str))
        cmdline = """%(install_str)s/condor_configure --install=%(install_str)s \
--install-dir=%(condor_location)s  \
--local-dir=%(condor_local)s \
--install-log=%(tar_dir)s/condor_configure.log""" %  \
          {   "tar_dir"        : tar_dir,     
              "first_dir"      : self.condor_first_dir, 
              "install_str"    : install_str, 
              "condor_location": self.condor_location(),
              "condor_local"   : self.condor_local(), }

        if os.getuid() == 0:
            cmdline += " --owner=%s" % (self.username())
        common.run_script(cmdline)
    except Exception,e:
        #shutil.rmtree(self.condor_location())
        common.logerr("Condor installation failed - %s" % (e))
    
    #--  installation files not needed anymore --
    shutil.rmtree(tar_dir)

    #-- Moving contents of condor_local/condor_config.local to the main config
    #-- and dereferencing it in the main condor_config
    common.logit("""... copying contents of the condor_config.local file to the main condor_config.""")
    cmd = """cat %(condor_local)s/condor_config.local >> %(condor_config)s; > %(condor_local)s/condor_config.local; echo "LOCAL_CONFIG_FILE =" >> %(condor_config)s""" % \
           { "condor_local"  : self.condor_local(),
             "condor_config" : self.condor_config(),
           }
    common.run_script(cmd)
    common.logit("\nCondor installation complete")

  #-----------------------------
  def __validate_needed_directories__(self):
    self.__validate_condor_location__()

  #-----------------------------
  def __verify_directories_empty__(self):
    if self.install_type() == "rpm":
      return  # For RPM install we don't want to clean anything
    dirs = {}
    if len(os.listdir(self.condor_location())) > 0:
      dirs["condor_location"] = self.condor_location()
    if len(dirs) == 0:
      return  # all directories are empty
    common.logit("""The following directories must be empty for the install to succeed: """)
    for option in dirs.keys():
      common.logit("""  %(option)s: %(dir)s""" % \
                        { "option" : option, "dir" : dirs[option] })
    common.ask_continue("... can we remove their contents")
    for option in dirs.keys(): 
      common.remove_dir_contents(dirs[option])
    self.__validate_needed_directories__()

  #--------------------------------
  def __validate_schedds__(self):
    if self.daemon_list.find("SCHEDD") < 0:
      common.logit("... no schedds")
      return # no schedd daemon
    common.logit("... validating number_of_schedds: %s" % self.number_of_schedds())
    nbr = self.number_of_schedds()
    min = 1
    max = 99
    if nbr < min:
      common.logerr("You must have at least 1 schedd")
    if nbr > max:
      common.logerr("Number of schedds exceeds maximum allowed value: %s" % (nbr))

  #--------------------------------
  def __validate_secondary_collectors__(self):
    if self.daemon_list.find("COLLECTOR") < 0:
      common.logit("... no secondary collectors")
      return # no collector daemon
    common.logit("... validating number_of_secondary_collectors: %s" % self.secondary_collectors())
    nbr = self.secondary_collectors()
    min = 0
    max = 399
    if nbr < min:
      common.logerr("nbr of secondary collectors is negative: %s" % (nbr))
    if nbr > max:
      common.logerr("nbr of secondary collectors exceeds maximum allowed value: %s" % (nbr))
 
  #--------------------------------
  def __validate_collector_port__(self):
    if self.daemon_list.find("COLLECTOR") < 0:
      common.logit("... no COLLECTOR daemon")
      return # no collector daemon
    common.logit("... validating collector port: %s" % self.collector_port())
    self.__validate_port_value__(self.collector_port(),"collector_port") 

  #--------------------------------
  def __validate_schedd_shared_port__(self):
    if self.daemon_list.find("SCHEDD") < 0:
      common.logit("... no SCHEDD daemon")
      return # no schedd deamons
    if self.schedd_shared_port() == 0:
      common.logit("... validating schedd_shared_port: %s" % "not used")
      return
    common.logit("... validating schedd_shared_port: %s" % self.schedd_shared_port())
    if self.condor_version < "7.5.3":
      common.logerr("the schedd_shared_port option can only be used in Condor 7.5.3+")
    self.__validate_port_value__(self.schedd_shared_port(),"schedd_shared_port") 
  #-------------------------------
  def __validate_port_value__(self,port,option):
    min = 1
    max = 65535
    root_port = 1024
    if port < min:
      common.logerr("%s option must be a positive value: %s" % (option,port))
    if port > max:
      common.logerr("%s option exceeds maximum allowed value of %s" % (option,max))
    if port < root_port:
      if os.getuid() == 0:  #-- root user --
        common.logit("Ports less that %i are generally reserved for root." % (root_port))
        common.logit("You have specified port %s for the %s option." % (port,option))
        yn = raw_input("Do you really want to use a privileged port %s? (y/n): "% port)
        if yn != 'y':
          common.logerr("... exiting at your request")
      else: #-- non-root user --
        common.logit("Ports less that %i are generally reserved for root." % (root_port))
        common.logerr("You have specified a %s option of %s" % (option,port))

  #--------------------------------
  def __validate_tarball__(self,tarball):
    """ Attempts to verify that this is a valid Condor tarball.
        - the first level of the directory structure is the
          Condor release with a format 'condor-*'.
        - the tarball contains the condor-*/configure_condor script.
    """
    if self.install_type() == "rpm":
      self.__check_condor_version__()
      return
    common.logit("... validating condor tarball: %s" % tarball)
    if not os.path.isfile(tarball):
      common.logerr("File (%s) not found" % (tarball))
    try:
      fd = tarfile.open(tarball,"r:gz")
    except:
      common.logerr("File (%s) not a valid tar.gz file" % (tarball))
    try:
        try:
            first_entry = fd.next().name
            first_el=fd.getmember(first_entry)
            if (not first_el.isdir()):
              common.logwarn("File (%s) may not be a condor tarball! (found (%s), expected a subdirectory" % (tarball, first_entry))
              self.condor_first_dir = first_entry+'/'
            else:
              self.condor_first_dir = first_entry.split('/')[0]+'/'
            
            if ( self.condor_first_dir[:7] != "condor-"):
              common.logerr("File '%s' is not a condor tarball! (found '%s', expected 'condor-*/'" % (tarball, self.condor_first_dir))

            self.condor_version = re.sub("/","",first_entry.split('-')[1])
            common.logit( "... condor version: %s" % (self.condor_version))
            try:
                fd.getmember(self.condor_first_dir + "condor_configure")
            except:
                common.logerr("Condor tarball (%s) missing %s" % (tarball, self.condor_first_dir + "condor_configure"))
        except Exception,e:
            common.logerr("Condor tarball file is corrupted: %s" % (tarball))
    finally:
      fd.close()

  #--------------------------------
  def __create_condor_mapfile__(self,users):
    """ Creates the condor mapfile for GSI authentication"""
    if self.client_only_install == True:
      common.logit( "... No Condor mapfile file needed. Client only install")
      return
    mapfile_entries = self.__condor_mapfile_entries__(users)
    filename = self.condor_mapfile()
    common.logit("... creating Condor mapfile")
    common.logit("    %s" % filename)
    common.make_directory(os.path.dirname(filename),pwd.getpwuid(os.getuid())[0],0755)
    mapfile_entries += """GSI (.*) anonymous
FS (.*) \\1
""" 
    common.write_file("w",0644,filename,mapfile_entries,SILENT=True)
    common.logit("\nCondor mapfile entries:")
    common.logit("%s" % mapfile_entries)

  #-----------------------------
  def __condor_mapfile_entries__(self,users):
    data = ""
    for user in users:
      comment = user[0]
      dn      = user[1]
      user    = user[2]
      data   += common.mapfile_entry(dn,user)
    return data

  #--------------------------------
  def __create_condor_config__(self):
    """ This first updates the primary condor_config with either:
          a. the gwms condor_config file if a tarball install
          b. the config.d directory containing the gwms config files
        Then it creates the individual condor config files.
    """
    #if len(self.colocated_services) > 0:
    #  return  # we've already updated this
    common.logit("... updating: %s" % self.condor_config())
    common.logit("    to point to GWMS config files directory")
    cfg_data = """
########################################################
# Using local configuration file directory below
########################################################
LOCAL_CONFIG_FILE = 
LOCAL_CONFIG_DIR  = %s
""" % (self.local_config_dir())
    common.write_file("a",0644,self.condor_config(),cfg_data,SILENT=False)
    common.os.system("tail -5 %s" % self.condor_config())

    common.logit("\nCreating GWMS condor_config files in:")
    common.logit("%s" % self.local_config_dir())
    common.make_directory(self.local_config_dir(),self.username(),0755)
    types =  self.condor_config_data.keys()
    types.sort()
    for type in types:
      filename = "%s/%s.config" % (self.local_config_dir(),type)
      common.logit("    %s" % os.path.basename(filename))
      common.write_file("w",0644,filename,self.condor_config_data[type],SILENT=True)
    self.__create_secondary_schedd_dirs__()

  #--------------------------------
  def __create_initd_script__(self):
    if self.client_only_install == True:
      common.logit("... client only install. No startup initd script required.")
      return
    if self.install_type() == "rpm":
      common.logit("... This is an 'rpm' install. An initd script already exists.")
      return
    common.logit("")
    common.logit("Creating startup /etc/init.d script")
    common.logit("   %s" % self.initd_script())
    data = self.__initd_script__()
    common.write_file("w",0755,self.initd_script(),data,SILENT=True)

  #----------------------------------
  def __initd_script__(self):
    data = """#!/bin/sh
# condor   This is the Condor batch system
# chkconfig: 35 90 30
# description: Starts and stops Condor

# Source function library.
if [ -f /etc/init.d/functions ] ; then
  . /etc/init.d/functions
elif [ -f /etc/rc.d/init.d/functions ] ; then
  . /etc/rc.d/init.d/functions
else
  exit 0
fi

#-- Condor settings --
CONDOR_LOCATION=%(condor_location)s
if [ ! -d "$CONDOR_LOCATION" ];then
  echo "ERROR: CONDOR_LOCATION does not exist: $CONDOR_LOCATION"
  failure
  exit 1
fi
if [ ! `echo ${PATH} | grep -q $CONDOR_LOCATION/bin` ]; then
  PATH=${PATH}:$CONDOR_LOCATION/bin
fi
export CONDOR_CONFIG=$CONDOR_LOCATION/etc/condor_config
if [ ! -f "$CONDOR_CONFIG" ];then
  echo "ERROR: CONDOR_CONFIG not found: $CONDOR_CONFIG"
  failure
  exit 1
fi
CONDOR_MASTER=$CONDOR_LOCATION/sbin/condor_master
if [ ! -f "$CONDOR_MASTER" ];then
  echo "ERROR: cannot find $CONDOR_MASTER"
  failure
  exit 1
fi

#---- verify correct user is starting/stopping condor --
validate_user () {
  config_vals="GSI_DAEMON_CERT GSI_DAEMON_KEY GSI_DAEMON_PROXY"
  good="no"
  for gsi_type in $config_vals
  do
    file="$(condor_config_val $gsi_type 2>/dev/null)"
    if [ ! -z "$file" ];then
      if [ -r "$file" ];then
        owner=$(ls -l $file | awk '{print $3}')
        me="$(/usr/bin/whoami)"
        if [ "$me" = "$owner" ];then
          good="yes"
          break
        fi
      fi
    fi
  done
  if [ $good = "no" ];then
    echo "ERROR: GSI self authentication will fail." 
    echo "Check these Condor attributes and verify ownership."
    echo "    $config_vals"
    echo "Or you may be starting/stopping Condor as the wrong user."
    if [ -n "$owner" ];then
      echo "You should be starting  as user: $owner"
      echo "You are trying to start as user: $me"
    fi
    exit 1
  fi
}

### #---- secondary schedd start function ---
### start_secondary_schedds () {
### %(schedds)s
### }

#-- start --
start () { 
   validate_user
   condor_status
   [ "$RETVAL" = "0" ] && { echo "Condor is already running";return
}
   echo -n "Starting condor: "
   $CONDOR_MASTER 2>/dev/null 1>&2 && success || failure
   RETVAL=$?
###   start_secondary_schedds
   echo
   sleep 3
   condor_status
   [ "$RETVAL" != "0" ] && { echo "ERROR: Condor did not start correctly"
}
}

#-- stop --
stop () { 
   validate_user
   condor_status
   [ "$RETVAL" != "0" ] && { RETVAL=0; return
}
   echo -n "Shutting down condor: "
   killall -q -15 -exact $CONDOR_MASTER && success || failure
   sleep 3
   condor_status
   [ "$RETVAL" != "0" ] && { RETVAL=0; return  # the stop worked
}
   echo -n "Shutting down condor with SIGKILL: "
   # If a master is still alive, we have a problem
   killall -q -9 -exact $CONDOR_MASTER && success || failure
   condor_status
   RETVAL=$?
   [ "$RETVAL" != "0" ] && { RETVAL=0; return  # the stop worked
}
}
#-- restart --
restart () { 
   stop
   start
}

#-- status --
condor_status () { 
   pids="$(ps -ef |grep $CONDOR_MASTER |egrep -v grep | awk '{printf "%(format)s ", $2}')"
   echo
   if [ -z "$pids" ];then
     echo "$CONDOR_MASTER not running"
     RETVAL=1
   else
   echo "$CONDOR_MASTER running...
pids ($pids)"
     RETVAL=0
   fi
   echo
}

#--------
prog=$(basename $0)

case $1 in
   start  ) start ;;
   stop   ) stop ;;
   restart) restart ;;
   status ) condor_status ;;
        * ) echo "Usage: $prog {start|stop|restart|status}"; exit 1 ;;
esac
exit $RETVAL
""" % { "condor_location" : self.condor_location(),
        "schedds" : self.schedd_initd_function,
        "format" : "%s",
      }
    return data

  #-----------------------------
  def __condor_config_gwms_data__(self):
    type = "03_gwms_local"
    self.condor_config_data[type] +=  """
#-- Condor user: %(user)s
CONDOR_IDS = %(condor_ids)s
#--  Contact (via email) when problems occur
CONDOR_ADMIN = %(admin_email)s
""" % { "admin_email" : self.admin_email(), 
        "condor_ids"  : self.condor_ids(), 
        "user"        : self.username(), }

    type = "00_gwms_general"
    self.condor_config_data[type] +=  """
######################################################
# Base configuration values for glideinWMS
######################################################

#--  With glideins, there is nothing shared
UID_DOMAIN=$(FULL_HOSTNAME)
FILESYSTEM_DOMAIN=$(FULL_HOSTNAME)

#-- Condor lock files to synchronize access to  various 
#-- log files.  Using the log directory so they are collocated
LOCK = $(LOG)
""" 

  #-----------------------------
  def __condor_config_gsi_data__(self,users):
    type ="00_gwms_general"
    self.condor_config_data[type] += """
############################################################
## Security config
############################################################
#-- Authentication settings
SEC_DEFAULT_AUTHENTICATION = REQUIRED
SEC_DEFAULT_AUTHENTICATION_METHODS = FS,GSI
SEC_READ_AUTHENTICATION    = OPTIONAL
SEC_CLIENT_AUTHENTICATION  = OPTIONAL
DENY_WRITE         = anonymous@*
DENY_ADMINISTRATOR = anonymous@*
DENY_DAEMON        = anonymous@*
DENY_NEGOTIATOR    = anonymous@*
DENY_CLIENT        = anonymous@*

#--  Privacy settings
SEC_DEFAULT_ENCRYPTION = OPTIONAL
SEC_DEFAULT_INTEGRITY = REQUIRED
SEC_READ_INTEGRITY = OPTIONAL
SEC_CLIENT_INTEGRITY = OPTIONAL
SEC_READ_ENCRYPTION = OPTIONAL
SEC_CLIENT_ENCRYPTION = OPTIONAL
"""

    type ="03_gwms_local"
    self.condor_config_data[type] += """
############################
# GSI Security config
############################
#-- Grid Certificate directory
GSI_DAEMON_TRUSTED_CA_DIR=%(x509_cert_dir)s
""" % { "x509_cert_dir"   : self.x509_cert_dir(),
      }

    type ="03_gwms_local"
    if self.client_only_install == True:
      self.condor_config_data[type] += """
#-- Credentials
GSI_DAEMON_PROXY = %(proxy)s

#-- Condor mapfile
# This configuration should run no daemons
CERTIFICATE_MAPFILE=
""" % { "proxy"           : self.x509_proxy(),
      }
    else:
      self.condor_config_data[type] += """
#-- Credentials
GSI_DAEMON_CERT = %(cert)s
GSI_DAEMON_KEY  = %(key)s

#-- Condor mapfile
CERTIFICATE_MAPFILE=%(mapfile)s
""" % { "cert"           : self.x509_cert(),
        "key"            : self.x509_key(),
        "mapfile"        : self.condor_mapfile()
      }

    type ="00_gwms_general"
    if self.condor_version >= "7.4":
      self.condor_config_data[type] += """
#-- With strong security, do not use IP based controls
HOSTALLOW_WRITE = *
ALLOW_WRITE = $(HOSTALLOW_WRITE)
"""
    else:
      self.condor_config_data[type] += """
#-- With strong security, do not use IP based controls
HOSTALLOW_WRITE = *
"""
    type ="03_gwms_local"
    if self.client_only_install == True:
      self.condor_config_data[type] += """
############################################
# Whitelist of condor daemon DNs
# This configuration should run no daemons
############################################
GSI_DAEMON_NAME =
"""
    else:
      self.condor_config_data[type] += """
###################################
# Whitelist of condor daemon DNs
###################################"""
    
      attribute = "GSI_DAEMON_NAME="
      for user in users:
        comment = user[0]
        dn      = user[1]
        user    = user[2]
        self.condor_config_data[type] += """
# --- %(comment)s: %(user)s
%(attribute)s%(dn)s""" % \
          { "attribute" : attribute, 
            "comment"   : comment, 
            "user"      : user, 
            "dn"        : dn }
        attribute = "GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),"

  #-----------------------------
  def __condor_config_daemon_list__(self):
    type = "00_gwms_general"
    if self.client_only_install == True:
      self.condor_config_data[type] += """
###########################################
# Daemons
# This configuration should run no daemons
###########################################
DAEMON_LIST =
DAEMON_SHUTDOWN = True
"""
    else:
      self.condor_config_data[type] += """
########################
## Daemons
########################
DAEMON_LIST   = MASTER
DAEMON_LIST   = $(DAEMON_LIST), %(daemons)s
#-- Limit session caching to ~12h
SEC_DAEMON_SESSION_DURATION = 50000
""" %  { "daemons" : self.daemon_list, }

  #-----------------------------
  def __condor_config_schedd_data__(self):
    if self.daemon_list.find("SCHEDD") < 0:
      return  # no schedds
    type = "02_gwms_schedds"
    self.condor_config_data[type] +=  """
######################################################
## Schedd tuning
######################################################
#--  Allow up to 6k concurrent running jobs
MAX_JOBS_RUNNING        = 6000

#--  Start max of 50 jobs every 2 seconds
JOB_START_DELAY = 2
JOB_START_COUNT = 50

#--  Stop 30 jobs every seconds
#--  This is needed to prevent glexec overload, when used
#--  Works for Condor v7.3.1 and up only, but harmless for older versions
JOB_STOP_DELAY = 1
JOB_STOP_COUNT = 30

#--  Raise file transfer limits
#--  no upload limits, since JOB_START_DELAY limits that
MAX_CONCURRENT_UPLOADS = 100
#--  but do limit downloads, as they are asyncronous
MAX_CONCURRENT_DOWNLOADS = 100

#--  Prevent checking on ImageSize
APPEND_REQ_VANILLA = (Memory>=1) && (Disk>=1)
# New in 7.8.x
JOB_DEFAULT_REQUESTMEMORY=1
JOB_DEFAULT_REQUESTDISK=1

#--  Prevent preemption
MAXJOBRETIREMENTTIME = $(HOUR) * 24 * 7

#-- Enable match authentication
SEC_ENABLE_MATCH_PASSWORD_AUTHENTICATION = TRUE

#-- GCB optimization
SCHEDD_SEND_VACATE_VIA_TCP = True
STARTD_SENDS_ALIVES = True

#-- Reduce disk IO - paranoid fsyncs are usully not needed
ENABLE_USERLOG_FSYNC = False

#-- Prepare the Shadow for use with glexec-enabled glideins
SHADOW.GLEXEC_STARTER = True
SHADOW.GLEXEC = /bin/false

#-- limit size of shadow logs
MAX_SHADOW_LOG = 100000000

#-- Publish LOCAL_DIR so it is available in the schedd classads as needed
LOCAL_DIR_STRING="$(LOCAL_DIR)"
SCHEDD_EXPRS = $(SCHEDD_EXPRS) LOCAL_DIR_STRING
"""

    if self.use_gridmanager:
      self.condor_config_data[type] +=  """
#-- Condor-G tuning -----
GRIDMANAGER_MAX_SUBMITTED_JOBS_PER_RESOURCE=5000
GRIDMANAGER_MAX_PENDING_SUBMITS_PER_RESOURCE=5000
GRIDMANAGER_MAX_PENDING_REQUESTS=500
# Force Condor-G to re-delegate the proxy as soon as the FE provides one
# Defaulting to 1 week, since we do not expect proxies with longer lifetimes 
GRIDMANAGER_PROXY_REFRESH_TIME=604800
SCHEDD_ENVIRONMENT = "_CONDOR_GRIDMANAGER_LOG=$(LOG)/GridmanagerLog.$(USERNAME)"
"""
    
    if self.condor_version >= "7.5.3" and self.schedd_shared_port() > 0:
      self.condor_config_data[type] +=  """
#--  Enable shared_port_daemon 
SHADOW.USE_SHARED_PORT = True
SCHEDD.USE_SHARED_PORT = True
SHARED_PORT_ARGS = -p %(port)s
DAEMON_LIST = $(DAEMON_LIST), SHARED_PORT
""" % { "port" : self.schedd_shared_port(), }

      if self.condor_version <= "7.5.3":
        self.condor_config_data[type] += """
#-- Enable match authentication workaround for Condor ticket
#-- https://condor-wiki.cs.wisc.edu/index.cgi/tktview?tn=1481
SHADOW_WORKLIFE = 0
""" 

    #-- checking for zero swap space - affects schedd's only --
    rtn = os.system("free | tail -1 |awk '{ if ( $2 == 0 ) {exit 0} else {exit 1} }'")
    if rtn == 0:
      self.condor_config_data[type] +=  """
#-- No swap space 
RESERVED_SWAP = 0
"""

  #----------------------------------
  def __condor_config_secondary_schedd_data__(self):
    type = "02_gwms_schedds"
    if self.daemon_list.find("SCHEDD") < 0:
      return  # no schedds
    common.logit("\nConfiguring secondary schedd support.")
    if self.number_of_schedds() == 1:
      common.logit("... no secondary schedds to configure")
      return
    dc_daemon_list = "DC_DAEMON_LIST = + "
    self.condor_config_data[type] +=  """
#--- Secondary SCHEDDs ----"""
    if self.install_type() == "rpm":
       schedd_dir = "$(LOCAL_DIR)/lib/condor"
    else:
       schedd_dir = "$(LOCAL_DIR)"
    secondary_schedds = int(self.number_of_schedds()) - 1
    for i in range(secondary_schedds):
      i = i + 2
      name       = "schedd_%(suffix)s%(nbr)s" % \
                    { "nbr"    : i  ,
                      "suffix" : self.schedd_name_suffix, }
      local_name = "schedd%(suffix)s%(nbr)s" % \
                    { "nbr"    : i  ,
                      "suffix" : self.schedd_name_suffix, }
      self.condor_config_data[type] +=  """
%(upper_name)s       = $(SCHEDD)
%(upper_name)s_ARGS  = -local-name %(lower_name)s
SCHEDD.%(upper_name)s.SCHEDD_NAME   = %(name)s
SCHEDD.%(upper_name)s.SCHEDD_LOG    = $(LOG)/SchedLog.$(SCHEDD.%(upper_name)s.SCHEDD_NAME)
SCHEDD.%(upper_name)s.LOCAL_DIR     = %(schedd_dir)s/$(SCHEDD.%(upper_name)s.SCHEDD_NAME)
SCHEDD.%(upper_name)s.EXECUTE       = $(SCHEDD.%(upper_name)s.LOCAL_DIR)/execute
SCHEDD.%(upper_name)s.LOCK          = $(SCHEDD.%(upper_name)s.LOCAL_DIR)/lock
SCHEDD.%(upper_name)s.PROCD_ADDRESS = $(SCHEDD.%(upper_name)s.LOCAL_DIR)/procd_pipe
SCHEDD.%(upper_name)s.SPOOL         = $(SCHEDD.%(upper_name)s.LOCAL_DIR)/spool
SCHEDD.%(upper_name)s.JOB_QUEUE_LOG         = $(SCHEDD.%(upper_name)s.SPOOL)/job_queue.log
SCHEDD.%(upper_name)s.SCHEDD_ADDRESS_FILE   = $(SCHEDD.%(upper_name)s.SPOOL)/.schedd_address
SCHEDD.%(upper_name)s.SCHEDD_DAEMON_AD_FILE = $(SCHEDD.%(upper_name)s.SPOOL)/.schedd_classad 
%(upper_name)s_LOCAL_DIR_STRING     = "$(SCHEDD.%(upper_name)s.LOCAL_DIR)"
SCHEDD.%(upper_name)s.SCHEDD_EXPRS  = LOCAL_DIR_STRING
""" % \
      { "name"       : name,
        "upper_name" : local_name.upper(),
        "lower_name" : local_name.lower(),
        "schedd_dir" : schedd_dir, }

      if self.use_gridmanager:
        self.condor_config_data[type] +=  """
%(upper_name)s_ENVIRONMENT = "_CONDOR_GRIDMANAGER_LOG=$(LOG)/GridManagerLog.$(SCHEDD.%(upper_name)s.SCHEDD_NAME).$(USERNAME)" """ % { "upper_name" : local_name.upper(),}


      self.condor_config_data[type] +=  """
DAEMON_LIST = $(DAEMON_LIST), %(upper_name)s
""" % { "upper_name" : local_name.upper(),}

      dc_daemon_list += " %(upper_name)s" % { "upper_name" : local_name.upper()}
    #--- end of for loop --

    self.condor_config_data[type] +=  """
%s
""" % dc_daemon_list

  #-----------------------------
  def __create_secondary_schedd_dirs__(self):
    if self.daemon_list.find("SCHEDD") < 0:
      return  # no schedds
    if self.number_of_schedds() == 1:
      return
    common.logit("")
    common.logit("Creating secondary schedd directories")
    cmd = ""
    if self.install_type() == "tarball":
      cmd = ". %s/condor.sh ;" % self.condor_location()
    cmd += "%s/install/services/init_schedd.sh" % self.glideinwms_location()
    common.run_script(cmd)
    common.logit("")

  #-----------------------------
  def __condor_config_userjob_default_attributes_data__(self):
    type = "02_gwms_schedds"
    if self.daemon_list.find("SCHEDD") < 0:
      return  # no schedds
    if self.userjob_classads_required:
      self.condor_config_data[type] +=  """ 
#-- Default user job classad attributes --
JOB_Site               = "$$(GLIDEIN_Site:Unknown)"
JOB_GLIDEIN_Entry_Name = "$$(GLIDEIN_Entry_Name:Unknown)"
JOB_GLIDEIN_Name       = "$$(GLIDEIN_Name:Unknown)"
JOB_GLIDEIN_Factory    = "$$(GLIDEIN_Factory:Unknown)"
JOB_GLIDEIN_Schedd     = "$$(GLIDEIN_Schedd:Unknown)"
JOB_GLIDEIN_ClusterId  = "$$(GLIDEIN_ClusterId:Unknown)"
JOB_GLIDEIN_ProcId     = "$$(GLIDEIN_ProcId:Unknown)"
JOB_GLIDEIN_Site       = "$$(GLIDEIN_Site:Unknown)"

SUBMIT_EXPRS = $(SUBMIT_EXPRS) JOB_Site JOB_GLIDEIN_Entry_Name JOB_GLIDEIN_Name JOB_GLIDEIN_Factory JOB_GLIDEIN_Schedd JOB_GLIDEIN_Schedd JOB_GLIDEIN_ClusterId JOB_GLIDEIN_ProcId JOB_GLIDEIN_Site
"""

  #-----------------------------
  def __condor_config_negotiator_data__(self):
    type = "00_gwms_general"
    if self.daemon_list.find("NEGOTIATOR") < 0:
      return  # no negotiator
    self.condor_config_data[type] += """

###########################################################
# Negotiator tuning
###########################################################
#-- Prefer newer claims as they are more likely to be alive
NEGOTIATOR_POST_JOB_RANK = MY.LastHeardFrom

#-- Increase negotiation frequency, as new glideins do not trigger a reschedule
NEGOTIATOR_INTERVAL = 60
NEGOTIATOR_MAX_TIME_PER_SUBMITTER=60
NEGOTIATOR_MAX_TIME_PER_PIESPIN=20

#-- Prevent preemption
PREEMPTION_REQUIREMENTS = False

#-- negotiator/GCB optimization
NEGOTIATOR_INFORM_STARTD = False

#-- Disable VOMS checking
NEGOTIATOR.USE_VOMS_ATTRIBUTES = False

#-- Causes Negotiator to run faster. PREEMPTION_REQUIREMENTS and all 
#-- condor_startd rank expressions must be False for 
#-- NEGOTIATOR_CONSIDER_PREEMPTION to be False
NEGOTIATOR_CONSIDER_PREEMPTION = False

###########################################################
# Event logging (if desired) 
###########################################################
## EVENT_LOG=$(LOG)/EventLog
## EVENT_LOG_JOB_AD_INFORMATION_ATTRS=Owner,CurrentHosts,x509userproxysubject,AccountingGroup,GlobalJobId,QDate,JobStartDate,JobCurrentStartDate,JobFinishedHookDone,MATCH_EXP_JOBGLIDEIN_Site,RemoteHost
## EVENT_LOG_MAX_SIZE = 100000000 
"""

  #-----------------------------
  def __condor_config_collector_data__(self):
    type = "01_gwms_collectors"
    if self.daemon_list.find("COLLECTOR") >= 0:
      self.condor_config_data[type]  += """
###########################################################
# Collector Data
###########################################################
COLLECTOR_NAME = %(name)s
COLLECTOR_HOST = $(CONDOR_HOST):%(port)s

#-- disable VOMS checking
COLLECTOR.USE_VOMS_ATTRIBUTES = False

#-- allow more file descriptors (only works if Condor is started as root)
##COLLECTOR_MAX_FILE_DESCRIPTORS=20000
""" % { "name" : self.service_name(), 
        "port" : self.collector_port()
      }
    else: # no collector, identifies one to use
      self.condor_config_data[type]  += """
####################################
# Collector for user submitted jobs
####################################
CONDOR_HOST = %(host)s
COLLECTOR_HOST = $(CONDOR_HOST):%(port)s
""" % { "host" : self.option_value("UserCollector","hostname"),
        "port" : self.option_value("UserCollector","collector_port"),
      }

  #-----------------------------
  def __condor_config_secondary_collector_data__(self):
    if self.daemon_list.find("COLLECTOR") < 0:
      return  # no collector daemon
    if self.secondary_collectors() == 0:
      return   # no secondary collectors
    type = "01_gwms_collectors"
    self.condor_config_data[type]  += """
#################################################
# Secondary Collectors
#################################################
#-- Forward ads to the main collector
#-- (this is ignored by the main collector, since the address matches itself)
CONDOR_VIEW_HOST = $(COLLECTOR_HOST)
"""

    #-- define sub-collectors, ports and log files
    for nbr in range(int(self.secondary_collectors())):
      self.condor_config_data[type]  += """
COLLECTOR%(nbr)i = $(COLLECTOR)
COLLECTOR%(nbr)i_ENVIRONMENT = _CONDOR_COLLECTOR_LOG=$(LOG)/Collector%(nbr)iLog
COLLECTOR%(nbr)i_ARGS = -f -p %(port)i
""" % { "nbr"  :  nbr, 
        "port" : self.secondary_collector_ports()[nbr]
      }

    self.condor_config_data[type]  += """
#-- Subcollectors for  list of daemons to start
"""
    for nbr in range(int(self.secondary_collectors())):
      self.condor_config_data[type]  += """\
DAEMON_LIST = $(DAEMON_LIST), COLLECTOR%(nbr)i
""" % { "nbr" : nbr }


#--- end of Condor class ---------
####################################

def main(argv):
  try:
    print argv
    inifile = "/home/weigand/glidein-ini/glidein-all-xen21-doug.ini"
    section = "WMSCollector"
    options = {}
    condor = Condor(inifile,section,options)
    #condor.install_condor()
    condor.__validate_tarball__("/usr/local/tarballs/" + argv[1])
  except ConfigurationError, e:
    print "ERROR: %s" % e;return 1
  except common.WMSerror, e:
    print "WMSError";return 1
  except Exception, e:
    print traceback.print_exc()
  return 0



#--------------------------
if __name__ == '__main__':
  sys.exit(main(sys.argv))

    
