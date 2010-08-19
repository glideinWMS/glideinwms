#!/bin/env python

import common
from Configuration import Configuration
from Configuration import ConfigurationError
from Certificates  import Certificates
import VDTClient
#---------------------
import sys,os,os.path,string,time
import tarfile
import shutil
import pwd
import stat


class Condor(Configuration):

  def __init__(self,inifile,ini_section,ini_options):
    self.ini_section = ini_section
    self.inifile     = inifile
    self.ini_options = ini_options
    Configuration.__init__(self,inifile)
    self.validate_section(ini_section,ini_options)

    self.condor_version      = None
    self.condor_tarball      = self.option_value(self.ini_section,"condor_tarball")
    self.admin_email         = self.option_value(self.ini_section,"condor_admin_email")
    self.split_condor_config = self.option_value(self.ini_section,"split_condor_config")
    self.gsi_location        = self.option_value(self.ini_section,"cert_proxy_location")
    self.gsi_authentication  = self.option_value(self.ini_section,"gsi_authentication")
    self.certificates        = None

    self.condor_config       = "%s/etc/condor_config" % self.condor_location()
    self.condor_config_local = "%s/condor_config.local" % (self.condor_local())
    self.initd_script        = "%s/%s.sh" % (self.condor_location(),self.service_name())

    #--- secondary schedd files --
    self.schedd_setup_file   = "new_schedd_setup.sh"
    self.schedd_init_file    = "init_schedd.sh"
    self.schedd_startup_file = "start_master_schedd.sh"
    self.schedd_initd_function = "return # no secondary schedds"

  #----------------------------------
  # methods for returning attributes
  #----------------------------------
  #----------------------------------
  def install_vdt_client(self):
    return self.option_value(self.ini_section,"install_vdt_client")
  #----------------------------------
  def condor_location(self):
    return self.option_value(self.ini_section,"condor_location")
  #----------------------------------
  def condor_cfg(self):
    if self.split_condor_config == "y":
      return self.condor_config_local
    else:
      return self.condor_config
  #----------------------------------
  def condor_local(self):
    return  "%s/condor_local" % self.condor_location()
  #----------------------------------
  def install_location(self):
    return self.option_value(self.ini_section,"install_location")
  #----------------------------------
  def gsi_dn(self):
    return self.option_value(self.ini_section,"gsi_dn")
  #---------------------
  def unix_acct(self):
    return self.option_value(self.ini_section,"unix_acct")
  #---------------------
  def service_name(self):
    return self.option_value(self.ini_section,"service_name")
  #---------------------
  def node(self):
    return self.option_value(self.ini_section,"node")
  #---------------------
  def condor_mapfile(self):
    return "%s/certs/condor_mapfile" % self.condor_location()
  #---------------------
  def privilege_separation(self):
    if self.has_option(self.ini_section,"privilege_separation"):
      return self.option_value(self.ini_section,"privilege_separation")
    return "n"
  #---------------------
  def match_authentication(self):
    if self.has_option(self.ini_section,"match_authentication"):
      return self.option_value(self.ini_section,"match_authentication")
    return "n"
  #---------------------
  def number_of_schedds(self):
    option = "number_of_schedds"
    if not self.has_option(self.ini_section,option):
      return int(0)
    return self.option_value(self.ini_section,option)
  #----------------------------------
  def collector_port(self):
    option = "collector_port"
    if not self.has_option(self.ini_section,option):
      return int(0)
    return self.option_value(self.ini_section,option)
  #---------------------
  def secondary_collectors(self):
    option = "number_of_secondary_collectors"
    if not self.has_option(self.ini_section,option):
      return int(0)
    return self.option_value(self.ini_section,option)
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
    if self.client_only_install() == True:
      common.logerr( "This is a client only install. Nothing to stop.")
    else: 
      common.logit( "... stopping condor as user %s" % self.unix_acct())
      common.run_script("%s stop" % self.initd_script)
  #--------------------------------
  def start_condor(self):
    if self.client_only_install() == True:
      common.logerr( "This is a client only install. Nothing to start.")
    else:
      common.logit( "... starting condor as user %s" % self.unix_acct())
      common.run_script("%s start" % self.initd_script)
  #--------------------------------
  def restart_condor(self):
    if self.client_only_install() == True:
      common.logerr( "This is a client only install. Nothing to restart.")
    else:
      common.logit( "... restarting condor as user %s" % self.unix_acct())
      common.run_script("%s restart" % self.initd_script)
   
  #--------------------------------
  def client_only_install(self):
    daemons = self.daemon_list.split(",")
    if len(daemons) > 1:
      return False
    return True

  #--------------------------------
  def install_condor(self):
    common.logit( "\nDependency and validation checking starting")
    self.__install_certificates__()
    self.__install_vdt_client__()
    self.__validate_condor_install__()
    common.logit( "Dependency and validation checking complete\n")
    self.__install_condor__()
    self.__setup_condor_env__()

    #-- put condor config in the environment 
    os.environ['CONDOR_CONFIG']="%s" % self.condor_config

    #-- put the CONDOR_LOCATION/bin in the PATH for the rest of the installation
    if os.environ.has_key('PATH'):
      os.environ['PATH']="%s/bin:%s" % (self.condor_location(),os.environ['PATH'])
    else:
      os.environ['PATH']="%s/bin:" % self.condor_location()

    self.update_condor_config()
    self.configure_secondary_schedds()
    self.__create_initd_script__()
    common.logit( "Condor install completed")

  #--------------------------------
  def update_condor_config(self):
    common.logit( "\nCondor_config update started")
    self.__setup_condor_config__()
    self.__update_condor_config_wms__()
    self.__update_condor_config_daemon__()
    self.configure_gsi_security()
    self.__update_condor_config_gsi__()
    self.__update_condor_config_schedd__()
    self.__update_condor_config_negotiator__()
    self.__update_condor_config_collector__()
    if self.ini_section == "WMSCollector":
      self.__update_condor_config_condorg__()
    self.update_condor_config_privsep()
    common.logit( "Condor_config update complete")

  #--------------------------------
  def __install_certificates__(self):
    """ Certificates are required for Condor GSI authentication. """
    certs = Certificates(self.inifile,self.ini_section)
    if not certs.certificates_exist():
      common.logit("... certificates do not exist.. starting installation")
      certs.install()
    self.certificates = certs.certificate_dir()
    common.logit("... certificates installed in: %s" % self.certificates)

  #--------------------------------
  def __install_vdt_client__(self):
    if self.install_vdt_client() == "y":
      vdt = VDTClient.VDTClient(self.inifile)
      if vdt.client_exists():
        common.logit("... VDT client already exists: %s" % vdt.vdt_location())
      else:
        common.logit("... VDT client is not installed")
        vdt.install()
    else:
      common.logit("... VDT client install not requested.")

  #--------------------------------
  def __validate_condor_install__(self):
    common.logit( "... validating Condor data")
    common.validate_node(self.node())
    common.validate_user(self.unix_acct())
    common.validate_email(self.admin_email)
    common.validate_gsi(self.gsi_dn(),self.gsi_authentication,self.gsi_location)
##    self.__validate_privilege_separation__()
    self.__validate_schedds__(self.number_of_schedds())
    self.__validate_collector_port__(self.collector_port())
    self.__validate_secondary_collectors__(self.secondary_collectors())
    self.__validate_condor_config__(self.split_condor_config)
    self.__validate_tarball__(self.condor_tarball)
    common.validate_install_location(self.condor_location())

  #--------------------------------
  def __setup_condor_env__(self):
    sh_profile = """
#-- Condor settings --
if ! echo ${PATH} | grep -q %s/bin ; then
  PATH=${PATH}:%s/bin
fi
export CONDOR_CONFIG=%s
""" % (self.condor_location(),self.condor_location(),self.condor_config)

    csh_profile = """
#-- Condor settings --
set path = ( $path %s/bin )
setenv CONDOR_CONFIG %s
""" % (self.condor_location(),self.condor_config)

    if os.getuid()==0: # different if root or not
      self.__setup_root_condor_env__(sh_profile,csh_profile)
    else:
      self.__setup_user_condor_env__(sh_profile,csh_profile)

  #--------------------------------
  def __setup_root_condor_env__(self,sh_profile,csh_profile):
    common.logit("... creating an /etc/condor/condor_config link IS NOT BEING DONE")
    ## #JGW --- this could go away if no root installs ----
    ## common.logit( "... setting up condor environment as root")
    ## #--  Put link into /etc/condor/condor_config --
    ## if not os.path.exists('/etc/condor'):
    ##     common.logit( "... creating /etc/condor/condor_config")
    ##     os.mkdir('/etc/condor')
    ## if os.path.islink('/etc/condor/condor_config') or os.path.exists('/etc/condor/condor_config'):
    ##     common.logit("...  an old version exists... replace it")
    ##     os.unlink('/etc/condor/condor_config')
    ## os.symlink(self.condor_config, '/etc/condor/condor_config')

    ## #--  put condor binaries in system wide path --
    ## filename = "/etc/profile.d/condor.sh"
    ## common.write_file("w",0644,filename,sh_profile) 
    ## filename = "/etc/profile.d/condor.csh"
    ## common.write_file("w",0644,filename,csh_profile) 

  #--------------------------------
  def __setup_user_condor_env__(self,sh_profile,csh_profile):
    common.logit( "... setting up condor environment as %s" % os.environ["LOGNAME"])
 
    common.logit("... appending to bashrc/cshrc scripts IS NOT BEING DONE")
    ##filename = "%s/.profile" % os.environ['HOME']
    ##common.write_file("a",0644,filename,sh_profile) 

    ##filename = "%s/.bashrc" % os.environ['HOME']
    ##common.write_file("a",0644,filename,sh_profile) 

    ##filename = "%s/.cshrc" % os.environ['HOME']
    ##common.write_file("a",0644,filename,csh_profile) 

    ##common.logit( "The Condor config has been put in your login files")
    ##common.logit( "Please remember to exit and reenter the terminal after the install")
 
  #--------------------------------
  def __install_condor__(self):
    common.logit("Condor install starting")
    common.logit("... install location: %s" % (self.condor_location()))
    try:
      tar_dir="%s/tar" % (self.condor_location())
      if not os.path.isdir(tar_dir):
        os.makedirs(tar_dir)
    except Exception,e:
      common.logerr("Condor installation failed. Cannot make %s directory: %s" % (tar_dir,e))
    
    try:
        common.logit( "... extracting from tarball")
        fd = tarfile.open(self.condor_tarball,"r:gz")
        #-- first create the regular files --
        for f in fd.getmembers():
            if not f.islnk():
                fd.extract(f,tar_dir)
        #-- then create the links --
        for f in fd.getmembers():
            if f.islnk():
                os.link(os.path.join(tar_dir,f.linkname),os.path.join(tar_dir,f.name))
        fd.close()

        common.logit( "... running condor_configure")
        install_str="%s/condor-%s/release.tar" % (tar_dir,self.condor_version)
        if not os.path.isfile(install_str):
            # Condor v7 changed the packaging
            install_str="%s/condor-%s"%(tar_dir,self.condor_version)
        #if not os.path.isfile(install_str):
        #    common.logerr(("Cannot find path to condor_configure(%s)" % (install_str))
        cmdline="cd %s/condor-%s;./condor_configure --install=%s --install-dir=%s --local-dir=%s --install-log=%s/condor_configure.log" % (tar_dir, self.condor_version, install_str, self.condor_location(), self.condor_local(), tar_dir)
        if os.getuid() == 0:
            cmdline="%s  --owner=%s" % (cmdline,self.unix_acct())
        common.run_script(cmdline)
    except Exception,e:
        shutil.rmtree(self.condor_location())
        common.logerr("Condor installation failed - %s" % (e))
    
    #--  installation files not needed anymore --
    shutil.rmtree(tar_dir)
    common.logit( "Condor install complete\n")

  #--------------------------------
  def __validate_schedds__(self,value):
    if self.daemon_list.find("SCHEDD") < 0:
      common.logit("...... no schedds")
      return # no schedd daemon
    common.logit("...... validating schedds: %s" % value)
    min = 0
    max = 99
    try:
      nbr = int(value)
    except:
      common.logerr("number of schedds is not a number: %s" % (value))
    if nbr < min:
      common.logerr("number of schedds is negative: %s" % (value))
    if nbr > max:
      common.logerr("number of schedds exceeds maximum allowed value: %s" % (value))

  #--------------------------------
  def __validate_secondary_collectors__(self,value):
    if self.daemon_list.find("COLLECTOR") < 0:
      common.logit("...... no secondary collectors")
      return # no collector daemon
    common.logit("...... validating secondary collectors: %s" % value)
    min = 0
    max = 399
    try:
      nbr = int(value)
    except:
      common.logerr("nbr of secondary collectors is not a number: %s" % (value))
    if nbr < min:
      common.logerr("nbr of secondary collectors is negative: %s" % (value))
    if nbr > max:
      common.logerr("nbr of secondary collectors exceeds maximum allowed value: %s" % (value))
 
  #--------------------------------
  def __validate_collector_port__(self,port):
    if self.daemon_list.find("COLLECTOR") < 0:
      common.logit("...... no collector")
      return # no collector daemon
    common.logit("...... validating collector port: %s" % port)
    collector_port = 0
    min = 1
    max = 65535
    root_port = 1024
    try:
      nbr = int(port)
    except:
      common.logerr("collector port option is not a number: %s" % (port))
    if nbr < min:
      common.logerr("collector port option is negative: %s" % (port))
    if nbr > max:
      common.logerr("collector port option exceeds maximum allowed value: %s" % (port))
    if nbr < root_port:
      if os.getuid() == 0:  #-- root user --
        common.logit("Ports less that %i are generally reserved." % (root_port))
        common.logit("You have specified port %s for the collector." % (port))
        yn = raw_input("Do you really want to use privileged port %s? (y/n): "% port)
        if yn != 'y':
          common.logerr("... exiting at your request")
      else: #-- non-root user --
        common.logerr("Collector port (%s) less than %i can only be used by root." % (port,root_port))
 
  #--------------------------------
  def __validate_condor_config__(self,value):
    common.logit("...... validating split_condor_config: %s" % value)
    if not value in ["y","n"]:
      common.logerr("Invalid split_condor_config value (%s)" % (value))

  #--------------------------------
  def __validate_tarball__(self,tarball):
    common.logit("...... validating condor tarball: %s" % tarball)
    if not os.path.isfile(tarball):
      common.logerr("File (%s) not found" % (tarball))
    try:
      fd=tarfile.open(tarball,"r:gz")
    except:
      common.logerr("File (%s) not a valid tar.gz file" % (tarball))
    try:
        try:
            first_dir=fd.getnames()[0]
            if (first_dir[:7]!="condor-") or (first_dir[-1]!='/'):
              common.logerr("File (%s) is not a condor tarball! (found (%s), expected 'condor-*/'" %(tarball,first_dir))
            self.condor_version=first_dir[7:-1]
            common.logit( "...... condor version %s" % (self.condor_version))
            try:
                fd.getmember(first_dir+"condor_configure")
            except:
                common.logerr("Filename (%s) missing %s" % (tarball,first_dir+"condor_configure"))
        except:
            common.logerr("File (%s) corrupted" % (condor_tarball))
    finally:
      fd.close()

  #--------------------------------
  def __create_condor_mapfile__(self,mapfile_entries=None):
    """ Creates the condor mapfile for GSI authentication"""
    common.logit("... creating Condor mapfile")
    if mapfile_entries == None:
      common.logit( "... No condor_mapfile file needed or entries specified.")
      return
    filename = self.condor_mapfile()
    common.make_directory(os.path.dirname(filename),pwd.getpwuid(os.getuid())[0],0755,empty_required=False)
    entries = """%s
GSI (.*) anonymous
FS (.*) \\1
""" % mapfile_entries
    common.write_file("w",0644,filename,entries)
    common.logit("... condor mapfile entries:")
    common.logit(os.system("cat %s" % filename))
    common.logit("... creating Condor mapfile complete.\n")

  #--------------------------------
  def __setup_condor_config__(self):
    """ If we are using a condor_config.local, then we will be populating the
        the one in condor_local
    """
    if self.split_condor_config == "y":
      #--- point the regular config to the local one ---
      cfg_data = """
########################################################
# Using local configuration file below
########################################################
LOCAL_CONFIG_FILE = %s
""" % (self.condor_config_local)
      common.logit( "... using condor config: %s" % (self.condor_config_local))
    else: 
      #-- else always update the main config --
      cfg_data = """
########################################################
# disable additional config files 
########################################################
LOCAL_CONFIG_FILE = 
"""
      common.logit( "... using condor config: %s" % (self.condor_config))

    #-- update the main config ---
    common.write_file("a",0644,self.condor_config,cfg_data)

  #--------------------------------
  def __update_condor_config_wms__(self):
    data = self.__condor_config_wms_data__()
    self.__append_to_condor_config__(data,"glideinWMS data")

  #--------------------------------
  def __update_condor_config_gsi__(self):
    data = self.__condor_config_gsi_data__()
    self.__append_to_condor_config__(data,"GSI")

  #--------------------------------
  def __update_condor_config_daemon__(self):
    data = self.__condor_config_daemon_data__()
    self.__append_to_condor_config__(data,"DAEMON")

  #--------------------------------
  def __update_condor_config_negotiator__(self):
    if self.daemon_list.find("NEGOTIATOR") >= 0:
      data = self.__condor_config_negotiator_data__()
      self.__append_to_condor_config__(data,"NEGOTIATOR")

  #--------------------------------
  def __update_condor_config_schedd__(self):
    if self.daemon_list.find("SCHEDD") >= 0:
      data = self.__condor_config_schedd_data__()
      #-- checking for zero swap space --
      rtn = os.system("free | tail -1 |awk '{ if ( $2 == 0 ) {exit 0} else {exit 1} }'")
      if rtn == 0:
        data = data + """
################
# No swap space 
################
RESERVED_SWAP = 0
"""
      self.__append_to_condor_config__(data,"SCHEDD")


  #--------------------------------
  def __update_condor_config_collector__(self):
    if self.daemon_list.find("COLLECTOR") >= 0:
      data = self.__condor_config_collector_data__()
      data = data + self.__condor_config_secondary_collector_data__()
    else: # no collector, identifies one to use
      data = """
####################################
# Collector for user submitted jobs
####################################
CONDOR_HOST = %s:%s
""" % (self.option_value("UserCollector","node"),self.option_value("UserCollector","collector_port"))
    self.__append_to_condor_config__(data,"COLLECTOR")

  #--------------------------------
  def __update_condor_config_condorg__(self):
    data = self.__condor_config_condorg_data__()
    self.__append_to_condor_config__(data,"CONDOR-G")

  #--------------------------------
  def update_condor_config_privsep(self):
    data = self.condor_config_privsep_data()
    self.__append_to_condor_config__(data,"Privilege Separation")

  #--------------------------------
  def __append_to_condor_config__(self,data,type):
    common.logit("... updating condor_config: %s entries" % type)
    if self.split_condor_config == "y":
      common.write_file("a",0644,self.condor_config_local,data)
    else:
      common.write_file("a",0644,self.condor_config,data)

  #--------------------------------
  def __create_initd_script__(self):
    if self.client_only_install() == True:
      common.logit("... client only install. No startup initd script required.")
    else:
      common.logit("\nCreating startup initd script")
      data = self.__initd_script__()
      common.write_file("w",0755,self.initd_script,data)

  #----------------------------------
  def configure_secondary_schedds(self):
    common.logit("\nConfiguring secondary schedd support.")
    if self.daemon_list.find("SCHEDD") < 0:
      common.logit("... no schedds daemons for this condor instance")
      return
    if self.number_of_schedds() == 0:
      common.logit("... no secondary schedds to configure")
      return
    self.__create_secondary_schedd_support_files__()
    self.schedd_initd_function = ""
    schedds = int(self.number_of_schedds())
    for i in range(schedds):
      schedd_name = "%s%i" % (self.schedd_name_suffix,i+1)
      #-- run the init script --
      user = pwd.getpwnam(self.unix_acct())
      condor_ids = "%s.%s" % (user[2],user[3])
      common.run_script("export CONDOR_IDS=%s;%s/%s %s" % (condor_ids,self.condor_location(),self.schedd_init_file,schedd_name))
      #-- add the start script to the condor initd function --
      data = "  $CONDOR_LOCATION/%s %s" % (self.schedd_startup_file,schedd_name)
      self.schedd_initd_function = "%s\n%s" % (self.schedd_initd_function,data)
    #-- recreate the initd script with the function --
    common.logit("\nConfiguring secondary schedd support complete.\n")

  #----------------------------------
  def __create_secondary_schedd_support_files__(self):
    common.logit("... creating secondary schedd support files")
    filename = "%s/%s" % (self.condor_location(),self.schedd_setup_file)
    data = self.__secondary_schedd_setup_file_data__()
    common.write_file("w",0644,filename,data)

    filename = "%s/%s" % (self.condor_location(),self.schedd_init_file)
    data = self.__secondary_schedd_init_file_data__()
    common.write_file("w",0755,filename,data)

    filename = "%s/%s" % (self.condor_location(),self.schedd_startup_file)
    data = self.__secondary_schedd_startup_file_data__()
    common.write_file("w",0755,filename,data)
    common.logit("... creating secondary schedd support files complete")

  #----------------------------------
  def __secondary_schedd_setup_file_data__(self):
    return """\
if [ $# -ne 1 ]
then
 echo "ERROR: arg1 should be schedd name."
 return 1
fi

LD=%s
export _CONDOR_SCHEDD_NAME=schedd_$1
export _CONDOR_MASTER_NAME=${_CONDOR_SCHEDD_NAME}
# SCHEDD and MASTER names MUST be the same (Condor requirement)
export _CONDOR_DAEMON_LIST="MASTER,SCHEDD"
export _CONDOR_LOCAL_DIR=$LD/$_CONDOR_SCHEDD_NAME
export _CONDOR_LOCK=$_CONDOR_LOCAL_DIR/lock
unset LD
""" % (self.condor_local())

  #----------------------------------
  def __secondary_schedd_init_file_data__(self):
    return """\
#!/bin/sh
CONDOR_LOCATION=%s
script=$CONDOR_LOCATION/%s
source $script $1
if [ "$?" != "0" ];then
  echo "ERROR in $script"
  exit 1
fi
# add whatever other config you need
# create needed directories
$CONDOR_LOCATION/sbin/condor_init
""" % (self.condor_location(),self.schedd_setup_file)

  #----------------------------------
  def __secondary_schedd_startup_file_data__(self):
    return """\
#!/bin/sh
CONDOR_LOCATION=%s
export CONDOR_CONFIG=$CONDOR_LOCATION/etc/condor_config
source $CONDOR_LOCATION/new_schedd_setup.sh $1
# add whatever other config you need
$CONDOR_LOCATION/sbin/condor_master
""" % (self.condor_location())

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
"""
    data = data + """
CONDOR_LOCATION=%s
if [ ! -d "$CONDOR_LOCATION" ];then
  failure
  exit 1
fi
#-- Condor settings --
if [ ! `echo ${PATH} | grep -q $CONDOR_LOCATION/bin` ]; then
  PATH=${PATH}:$CONDOR_LOCATION/bin
fi
export CONDOR_CONFIG=$CONDOR_LOCATION/etc/condor_config
if [ ! -f "$CONDOR_CONFIG" ];then
  echo "ERROR: CONDOR_CONFIG not found: $CONDOR_CONFIG"
  exit 1
fi
""" % (self.condor_location())

    data = data + """
#---- secondary schedd start function ---
start_secondary_schedds () {
%s
}
""" % (self.schedd_initd_function)

    data = data + """
#----
start () { 
   echo -n "Starting condor: "
   $CONDOR_LOCATION/sbin/condor_master 2>/dev/null 1>&2 && success || failure
   RETVAL=$?
   start_secondary_schedds
   echo
}
#----
stop () { 
   echo -n "Shutting down condor: "
   killall -q -9 condor_master condor_schedd condor_shadow condor_collector condor_negotiator condor_procd condor_gridmanager gahp_server 2>/dev/null 1>&2
   sleep 1
   # If a master is still alive, we have a problem
   killall condor_master 2>/dev/null 1>&2 && failure || success
   RETVAL=$?
   echo
}
#----
restart () { stop; start
}
#--------
prog=$(basename $0)

case $1 in
   start  ) start ;;
   stop   ) stop ;;
   restart) restart ;;
   status ) status $CONDOR_LOCATION/sbin/condor_master ;;
        * ) echo "Usage: $prog {start|stop|restart|status}"; exit 1 ;;
esac
exit $RETVAL
""" 
    return data

  #-----------------------------
  def __condor_config_wms_data__(self):
    return  """
######################################################
# Base configuration values for glideinWMS
######################################################
##  Contact (via email) when problems occur
CONDOR_ADMIN = %s
##########################################
#  With glideins, there is nothing shared
##########################################
UID_DOMAIN=$(FULL_HOSTNAME)
FILESYSTEM_DOMAIN=$(FULL_HOSTNAME)

####################################################################
#  Condor needs to create a few lock files to synchronize access to 
#  various log files.  Use the log directory so they are collocated
####################################################################
LOCK = $(LOG)

############################################################
## Security config
############################################################
############################
# Authentication settings
############################
SEC_DEFAULT_AUTHENTICATION = REQUIRED
SEC_DEFAULT_AUTHENTICATION_METHODS = FS
SEC_READ_AUTHENTICATION = OPTIONAL
SEC_CLIENT_AUTHENTICATION = OPTIONAL
DENY_WRITE = anonymous@*
DENY_ADMINISTRATOR = anonymous@*
DENY_DAEMON = anonymous@*
DENY_NEGOTIATOR = anonymous@*
DENY_CLIENT = anonymous@*
#
############################
# Privacy settings
############################
SEC_DEFAULT_ENCRYPTION = OPTIONAL
SEC_DEFAULT_INTEGRITY = REQUIRED
SEC_READ_INTEGRITY = OPTIONAL
SEC_CLIENT_INTEGRITY = OPTIONAL
SEC_READ_ENCRYPTION = OPTIONAL
SEC_CLIENT_ENCRYPTION = OPTIONAL
""" % (self.admin_email)


  #-----------------------------
  def __condor_config_gsi_data__(self):
    data = ""
    data =  data + """
############################################################
## GSI Security config
############################################################
############################
# Authentication settings
############################
SEC_DEFAULT_AUTHENTICATION_METHODS = FS,GSI

############################
# Grid Certificate directory
############################
GSI_DAEMON_TRUSTED_CA_DIR=%s
""" % (self.certificates)

    if self.gsi_authentication == "proxy":
      data = data + """
############################
# Credentials
############################
GSI_DAEMON_PROXY = %s 
""" % self.gsi_location
    else:
      data = data + """
############################
# Credentials
############################
GSI_DAEMON_CERT = %s
GSI_DAEMON_KEY  = %s
""" % (self.gsi_location,string.replace(self.gsi_location,"cert.pem","key.pem"))

    if self.condor_version >= "7.4":
      data = data + """
#####################################################
# With strong security, do not use IP based controls
#####################################################
HOSTALLOW_WRITE = *
ALLOW_WRITE = $(HOSTALLOW_WRITE)
"""
    else:
      data = data + """
#####################################################
# With strong security, do not use IP based controls
#####################################################
HOSTALLOW_WRITE = *
"""

    data = data + """
############################
# Set daemon cert location
############################
GSI_DAEMON_DIRECTORY = %s

#################################
# Where to find ID->uid mappings
#################################
CERTIFICATE_MAPFILE=%s
""" % ( os.path.dirname(self.condor_mapfile()),self.condor_mapfile())

#### ----------------------------------------------
#### No longer required effective with 7.5.1
#### ---------------------------------------------
#    if len(gsi_dns) > 0:
#      data =  data + """
######################################
## Whitelist of condor daemon DNs
######################################
#%s
#""" % (gsi_dns)
#
    return data

  #-----------------------------
  def __condor_config_daemon_data__(self):
    data = ""
    data =  data + """
######################################################
## daemons
######################################################
DAEMON_LIST   = %s """ % self.daemon_list

    if self.client_only_install() == True:
      data = data + """
#-- This machine should run no daemons
DAEMON_SHUTDOWN = True
"""
    else:
      data = data + """
#####################################
# Limit session caching to ~12h
#####################################
SEC_DAEMON_SESSION_DURATION = 50000

##########################################################
# Prepare the Shadow for use with glexec-enabled glideins
##########################################################
SHADOW.GLEXEC_STARTER = True
SHADOW.GLEXEC = /bin/false
""" 
      if self.match_authentication() == "y":
        data = data + """
#####################################
# Enable match authentication
#####################################
SEC_ENABLE_MATCH_PASSWORD_AUTHENTICATION=TRUE
""" 
    return data

  #-----------------------------
  def __condor_config_schedd_data__(self):
    data =  """
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
MAX_CONCURRENT_UPLOADS = 0
#--  but do limit downloads, as they are asyncronous
MAX_CONCURRENT_DOWNLOADS = 100

#--  Prevent checking on ImageSize
APPEND_REQ_VANILLA = (Memory>=1) && (Disk>=1)

#--  Prevent preemption
MAXJOBRETIREMENTTIME = $(HOUR) * 24 * 7
#-- GCB optimization
SCHEDD_SEND_VACATE_VIA_TCP = True
STARTD_SENDS_ALIVES = True
#-- Reduce disk IO - paranoid fsyncs are usully not needed
ENABLE_USERLOG_FSYNC = False
"""
    return data

  #-----------------------------
  def __condor_config_negotiator_data__(self):
    data = """
###########################################################
# Negotiator tuning
###########################################################
#-- Prefer newer claims as they are more likely to be alive
NEGOTIATOR_POST_JOB_RANK = MY.LastHeardFrom
#-- Increase negotiation frequency, as new glideins do not trigger a reschedule
NEGOTIATOR_INTERVAL = 60
NEGOTIATOR_MAX_TIME_PER_SUBMITTER=40
NEGOTIATOR_MAX_TIME_PER_PIESPIN=20
#-- Prevent preemption
PREEMPTION_REQUIREMENTS = False
#-- negotiator/GCB optimization
NEGOTIATOR_INFORM_STARTD = False
#-- Disable VOMS checking
NEGOTIATOR.USE_VOMS_ATTRIBUTES = False
"""
    if self.ini_section == "UserCollector":
      data = data + """
#-- Causes Negotiator to run faster. PREEMPTION_REQUIREMENTS and all 
#-- condor_startd rank expressions must be alse for 
#-- NEGOTIATOR_CONSIDER_PREEMPTION to be False
NEGOTIATOR_CONSIDER_PREEMPTION = False
"""
    return data

  #-----------------------------
  def __condor_config_collector_data__(self):
    data = """
###########################################################
# Collector Data
###########################################################
COLLECTOR_NAME = %s
COLLECTOR_HOST = $(CONDOR_HOST):%s
#-- disable VOMS checking
COLLECTOR.USE_VOMS_ATTRIBUTES = False
""" % (self.service_name(),self.collector_port())
    return data

  #-----------------------------
  def __condor_config_secondary_collector_data__(self):
    if self.secondary_collectors() == 0:
      return ""  # none
    data = """
#################################################
# Secondary collectors
#################################################"""
#-- define sub-collectors, ports and log files
    for nbr in range(int(self.secondary_collectors())):
      data = data + """
COLLECTOR%i = $(COLLECTOR)
COLLECTOR%i_ENVIRONMENT = "_CONDOR_COLLECTOR_LOG=$(LOG)/Collector%iLog"
COLLECTOR%i_ARGS = -f -p %i
""" % (nbr,nbr,nbr,nbr,self.secondary_collector_ports()[nbr])

    data = data + """
#-- Add subcollectors to the list of daemons  to start
DAEMON_LIST = $(DAEMON_LIST) \\
"""
    for nbr in range(int(self.secondary_collectors())):
      data = data + "COLLECTOR%i \\\n" % nbr

    data = data + """
#-- Forward ads to the main collector
#-- (this is ignored by the main collector, since the address matches itself)
CONDOR_VIEW_HOST = $(COLLECTOR_HOST)
"""
    return data

  #-----------------------------
  def __condor_config_condorg_data__(self):
    data = """
######################################################
## Condor-G tuning
######################################################
GRIDMANAGER_LOG = /tmp/GridmanagerLog.$(SCHEDD_NAME).$(USERNAME)
GRIDMANAGER_MAX_SUBMITTED_JOBS_PER_RESOURCE=5000
GRIDMANAGER_MAX_PENDING_SUBMITS_PER_RESOURCE=5000
GRIDMANAGER_MAX_PENDING_REQUESTS=500
"""
    return data

  #------------------------------------------
  #-- Must be populated in top level class --
  #-- if Privilege Separation used         --
  #------------------------------------------
  def condor_config_privsep_data(self):
    return ""

#--- end of Condor class ---------
####################################

def main(argv):
  try:
    condor = Condor("/home/weigand/myinstall/glideinWMS.ini")
    condor.install_condor()
  except ConfigurationError, e:
    print "ERROR: %s" % e;return 1
  except common.WMSerror, e:
    print "WMSError";return 1
  except Exception, e:
    print "ERROR: %s - %s" % (show_line(),e);return 1
  return 0



#--------------------------
if __name__ == '__main__':
  sys.exit(main(sys.argv))

    
