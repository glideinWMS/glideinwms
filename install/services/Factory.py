#!/bin/env python

import common
import WMSCollector
from Glidein       import Glidein
from Configuration import Configuration
from Configuration import ConfigurationError

import traceback
import sys,os,os.path,string,time
import xml.sax.saxutils

import optparse

#STARTUP_DIR=sys.path[0]
#sys.path.append(os.path.join(STARTUP_DIR,"../lib"))
os.environ["PYTHONPATH"] = ""

valid_options = [ "node", 
"unix_acct", 
"service_name", 
"install_location", 
"instance_name",
"gsi_authentication", 
"cert_proxy_location", 
"gsi_dn", 
"use_vofrontend_proxy", 
"use_glexec", 
"use_ccb", 
"gcb_list", 
"ress_host",
"ress_constraint",
"bdii_host",
"bdii_constraint",
"ress_filter",
"web_location",
"web_url",
"javascriptrrd",
"flot",
"m2crypto",
"javascriptrrd_tarball",
"flot_tarball",
"m2crypto_tarball",
"match_authentication",
"install_vdt_client",
"glidein_install_dir",
]

class Factory(Configuration):
  def __init__(self,inifile):
    global valid_options
    self.inifile = inifile
    self.ini_section = "Factory"
    Configuration.__init__(self,inifile)
    self.validate_section(self.ini_section,valid_options)
    self.wms = WMSCollector.WMSCollector(self.inifile)

    self.glidein = Glidein(self.inifile,self.ini_section,valid_options)

    self.config_entries_list = {} # Config file entries elements

    # the real directory is hardcoded in the createglidein script
    self.glidein_dir = "%s/glidein_%s" % (self.glidein.install_location(),self.glidein.instance_name())
    self.env_script = "%s/factory.sh" % self.glidein.install_location()

  #---------------------
  def install_location(self):
    return self.glidein.install_location()
  #---------------------
  def unix_acct(self):
    return self.glidein.unix_acct()
  #---------------------
  def node(self):
    return self.glidein.node()

  #---------------------
  def install(self):
    common.logit ("======== %s install starting ==========" % self.ini_section)
    self.glidein.validate_install()
    self.glidein.create_web_directories()
    self.glidein.__install_vdt_client__()
    self.get_config_entries_data()
    common.make_directory(self.glidein.install_location())
    self.create_config()
    self.create_env_script()
    self.create_glideins()
    self.start()
    common.logit ("======== %s install complete ==========" % self.ini_section)

#JGW  #-----------------------
  def start(self):
    cmd1 = "source %s" % self.env_script
    cmd2 = "cd %s;./factory_startup start" % (self.glidein_dir)
    common.logit("\nTo start the glideins you need to run the following:\n  %s\n  %s" % (cmd1,cmd2))
    if os.path.isdir(self.glidein_dir): #indicates the glideins have been created
      yn=raw_input("Do you want to start the glideins now? (y/n) [n]: ")
      if yn=='y':
        common.run_script("%s;%s" % (cmd1,cmd2))

#JGW  #-----------------------
  def create_env_script(self):
    common.logit("Creating env script.")
    data = """#!/bin/bash
source %s/setup.sh
export PYTHONPATH=%s/usr/lib/python2.3/site-packages:$PYTHONPATH
export X509_USER_PROXY=%s 
source %s/condor.sh
""" % (self.glidein.vdt_location(),self.glidein.m2crypto(),self.glidein.gsi_location(),self.wms.condor_location())
    common.write_file("w",0644,self.env_script,data)


#JGW  #-----------------------
  def create_glideins(self):
    yn=raw_input("Do you want to create the glideins now? (y/n) [n]: ")
    cmd1 = "source %s" % self.env_script
    cmd2 = "%s/creation/create_glidein %s" % (self.glidein.glidein_install_dir(),self.glidein.config_file())
    if yn=='y':
      common.run_script("%s;%s" % (cmd1,cmd2))
    else:
      common.logit("\nTo create the glideins, you need to run the following:\n  %s\n  %s" % (cmd1,cmd2))

  #-----------------------
  def schedds(self):
    collector_node = self.wms.node()
    schedd_list = []
    for filename in os.listdir(self.wms.condor_local()):
      if filename[0:6] == "schedd":
        schedd_list.append("%s@%s" % (filename,collector_node))
    return schedd_list

  #-------------------------
  def create_config(self):
    common.logit("Collecting  configuration file data. It will be question/answer time.")
    config_xml = self.config_data()
    common.logit("Creating configuration file")
    common.make_directory(self.glidein.config_dir())
    common.write_file("w",0644,self.glidein.config_file(),config_xml)

  #-------------------------
  def config_data(self):
    data = """\
<glidein factory_name="%s" 
         glidein_name="%s"
         loop_delay="60" advertise_delay="5"
         restart_attempts="3" restart_interval="1800"
         schedd_name="%s">
""" % (self.glidein.service_name(), self.glidein.instance_name(), string.join(self.schedds(),','))
    data = data + """\
%s
%s
%s
%s
%s
%s
%s
  <files>
  </files>
</glidein>
""" % (self.config_condor_data(),
       self.config_submit_data(),
       self.config_stage_data(),
       self.config_monitor_data(),
       self.config_security_data(),
       self.config_default_attr_data(),
       self.config_entries_data())
    return data
  #---------------
  def config_condor_data(self): 
    data = """%s<condor_tarballs>""" % (common.indent(1))
    indent = common.indent(2)
    data = data + """%s<condor_tarball arch="default" os="default" base_dir="%s"/> """ % (indent,self.wms.condor_location())
    data = data + """%s</condor_tarballs>""" % (common.indent(1))
    return data
  #---------------
  def config_submit_data(self): 
    indent = common.indent(1)
    return """%s<submit base_dir="%s"/>""" % (indent,self.glidein.install_location())
  #---------------
  def config_stage_data(self): 
    indent = common.indent(1)
    return """%s<stage web_base_url="%s/%s/stage" use_symlink="True" base_dir="%s/stage"/>""" % (indent,
              self.glidein.web_url(),os.path.basename(self.glidein.web_location()), self.glidein.web_location())
  #---------------
  def config_monitor_data(self): 
    indent = common.indent(1)
    return """%s<monitor base_dir="%s/monitor" javascriptRRD_dir="%s" flot_dir="%s" jquery_dir="%s"/>"""  % (indent,
       self.glidein.web_location(),  self.glidein.javascriptrrd(), self.glidein.flot(), self.glidein.flot())
  #---------------
  def config_security_data(self): 
    indent = common.indent(1)
    if self.glidein.use_vofrontend_proxy() == "y": # disable factory proxy
      data = """%s<security allow_proxy="frontend" key_length="2048" pub_key="RSA"/>""" % (indent)
    else: # allow both factory proxy and VO proxy
      data = """%s<security allow_proxy="factory,frontend" key_length="2048" pub_key="RSA"/>""" % (indent)
    return data

  #---------------
  def config_default_attr_data(self):
    data = """%s<attrs>""" % (common.indent(1))
    gcb_list = self.glidein.gcb_list()
    indent = common.indent(2)
    if self.glidein.use_ccb()  == "n":
      data = data + """%s<attr name="USE_CCB" value="False" const="True" type="string" glidein_publish="True" publish="True" job_publish="False" parameter="True"/>"""  % (indent)
      if len(gcb_list) > 0:  #-- using gcb ---
        data = data + """%s<attr name="GCB_LIST" value="%s" const="True" type="string" glidein_publish="False" publish="False" job_publish="False" parameter="True"/>""" % (indent,string.join(gcb_list,','))
      else:  #-- no gcb used ---
        data = data + """%s<attr name="GCB_ORDER" value="NONE" const="True" type="string" glidein_publish="True" publish="True" job_publish="False" parameter="True"/>""" % (indent)
    else: # no GCB if CCB used
      data = data + """%s<attr name="GCB_ORDER" value="NONE" const="True" type="string" glidein_publish="True" publish="True" job_publish="False" parameter="True"/>""" % (indent)
    # -- glexec --
    data = data + """%s<attr name="GLEXEC_JOB" value="True" const="True" type="string" glidein_publish="False" publish="True" job_publish="False" parameter="True"/>"""  % (indent)
    # -- match authentication --
    data = data + """%s<attr name="USE_MATCH_AUTH" value="%s" const="False" type="string" glidein_publish="False" publish="True" job_publish="False" parameter="True"/>""" % (indent, self.glidein.match_authentication() == "y")
    data = data + """%s</attrs>""" % (common.indent(1))
    return data


  #---------------
  def config_entries_data(self):
    data = """%s<entries>""" % (common.indent(1))
    sorted_entry_names =self.config_entries_list.keys()
    sorted_entry_names.sort()
    for entry_name in sorted_entry_names:
      entry_el=self.config_entries_list[entry_name]
      if entry_el['rsl']!="":
        rsl_str='rsl=%s' % xml.sax.saxutils.quoteattr(entry_el['rsl'])
      else:
        rsl_str=""
      data = data + """%s<!-- %s -->""" % (common.indent(2),entry_name)
      data = data + """%s<entry name="%s" gridtype="%s" gatekeeper="%s" %s work_dir="%s">""" % (common.indent(2),entry_name,entry_el['gridtype'],entry_el['gatekeeper'],rsl_str,entry_el['work_dir'])

      #--- infosys_refs --
      data = data + "%s<infosys_refs>" % (common.indent(3))
      for is_el in entry_el['is_ids']:
        data = data + """%s<infosys_ref type="%s" server="%s" ref="%s"/>""" % (common.indent(4),is_el['type'],is_el['server'],is_el['name'])
      data = data + """%s</infosys_refs>""" % (common.indent(3))

      #--- attrs ---
      data = data + """%s<attrs>""" % (common.indent(3))
      data = data + """%s<attr name="GLIDEIN_Site" value="%s"      const="True" type="string" glidein_publish="True"  publish="True"  job_publish="True"  parameter="True"/>""" % (common.indent(4),entry_el['site_name'])
      data = data + """%s<attr name="CONDOR_OS"    value="default" const="True" type="string" glidein_publish="False" publish="False" job_publish="False" parameter="True"/>""" % (common.indent(4))
      data = data + """%s<attr name="CONDOR_ARCH"  value="default" const="True" type="string" glidein_publish="False" publish="False" job_publish="False" parameter="True"/>""" % (common.indent(4))
      data = data + """%s<attr name="GLEXEC_BIN"   value="%s"      const="True" type="string" glidein_publish="False" publish="True"  job_publish="False" parameter="True"/>"""  % (common.indent(4),entry_el['glexec_path'])

      if self.glidein.use_ccb() =="y":
        # Put USE_CCB in the entries so that it is easy to disable it selectively
        data = data + """%s<attr name="USE_CCB" value="True" const="True" type="string" glidein_publish="True" publish="True" job_publish="False" parameter="True"/>""" % (common.indent(4))
      else:
        # Put GCB_ORDER in the entries so that it is easy to disable it selectively
        if len(self.glidein.gcb_list()) > 0:
          data = data + """%s<attr name="GCB_ORDER" value="RANDOM" const="False" type="string" glidein_publish="True" publish="True" job_publish="False" parameter="True"/>""" % (common.indent(4))

      data = data + """%s</attrs>""" % (common.indent(3))
      data = data + """%s</entry>\n""" % (common.indent(2))
      data = data + """%s</entries>""" % (common.indent(1))
    return data

  #----------------------------
  def get_config_entries_data(self):
    os.environ["PATH"] = "%s/bin:%s" %(self.wms.condor_location(),os.environ["PATH"])
    os.environ["CONDOR_CONFIG"] = self.wms.condor_config
    print os.environ["CONDOR_CONFIG"] 
 
    self.config_entries_list = {}  # config files entries elements
    while 1:
      yn=raw_input("Do you want to fetch entries from RESS?: (y/n) [n] ")
      if yn == 'y':
        ress_data     = self.get_ress_data()
        filtered_data = self.apply_filters_to_ress(ress_data)
        self.ask_user(filtered_data)
      yn=raw_input("Do you want to fetch entries from BDII?: (y/n) [n] ")
      if yn == 'y':
        bdii_data     = self.get_bdii_data()
        filtered_data = self.apply_filters_to_bdii(bdii_data)
        self.ask_user(filtered_data)
      yn=raw_input("Do you want to add manual entries?: (y/n) [n] ")
      if yn == 'y':
        self.additional_entry_points()
      if len(self.config_entries_list) > 0:
        break
      print "You have no entry points. You need at least 1... try again"
   

  #----------------------------
  def ask_user(self,ress_entries):
    ress_keys=ress_entries.keys()
    ress_keys.sort()

    print "Found %i additional entries" % len(ress_keys)
    yn = raw_input("Do you want to use them all?: (y/n) ")
    if yn=="y":
        # simply copy all of them
        for key in ress_keys:
            self.config_entries_list[key] = ress_entries[key]
        return

    print "This is the list of entries found in RESS:"
    for key in ress_keys:
        print "[%s] %s(%s)"%(string.ljust(key,20),ress_entries[key]['gatekeeper'],ress_entries[key]['rsl'])

    print "Select the indexes you want to include"
    print "Use a , separated list to include more than one"
    while 1:
      idxes = raw_input("Please select: ")
      idx_arr = idxes.split(',')
      problems = 0
      for idx in idx_arr:
        if not (idx in ress_keys):
          print "'%s' is not a valid index!" % idx
          problems=1
          break
      if problems:
        continue

      # got them
      break

    yn=raw_input("Do you want to customize them?: (y/n) ")
    if yn == "y":
      # customize them
      for idx in idx_arr:
        work_dir=raw_input("Work dir for '%s': [%s] " % (idx,ress_entries[idx]['work_dir']))
        if work_dir!="":
          ress_entries[idx]['work_dir'] = work_dir
        site_name=raw_input("Site name for '%s': [%s] " % (idx,ress_entries[idx]['site_name']))
        if site_name != "":
          ress_entries[idx]['site_name'] = site_name

      if config_glexec:
        glexec_path = raw_input("gLExec path for '%s': [%s] "%(idx,ress_entries[idx]['glexec_path']))
        if glexec_path != "":
          ress_entries[idx]['glexec_path'] = glexec_path

    for idx in idx_arr:
      self.config_entries_list[idx] = ress_entries[idx]

    return

  #----------------------------
  def apply_filters_to_ress(self,condor_data):
    #-- set up the  python filter ---
    python_filter_obj=compile(self.glidein.ress_filter(),"<string>","eval")

    #-- using glexec? ---
    if self.glidein.use_glexec() == "y":
        def_glexec_bin='OSG'
    else:
        def_glexec_bin='NONE'

    cluster_count={}
    ress_entries={}
    for condor_id in condor_data.keys():
      condor_el = condor_data[condor_id]
    
      if not eval(python_filter_obj,condor_el):
        continue # has not passed the filter

      cluster_name    = condor_el['GlueClusterName']
      gatekeeper_name = condor_el['GlueCEInfoContactString']
      rsl = '(queue=%s)(jobtype=single)'%condor_el['GlueCEName']
      site_name=condor_el['GlueSiteName']

      work_dir = "OSG"
      ress_id  = {'type':'RESS','server':self.glidein.ress_host(),'name':condor_id}
      entry_el = {'gatekeeper':gatekeeper_name,'rsl':rsl,'gridtype':'gt2',
        'work_dir':work_dir,'site_name':site_name,'glexec_path':def_glexec_bin,
        'is_ids':[ress_id]}

      cluster_arr = cluster_name.split('.')
      if len(cluster_arr)<2:
        continue # something is wrong here, at least a.b expected

      t_found = False
      for t in ress_entries.keys():
        test_el = ress_entries[t]
        if self.compare_entry_els(test_el,entry_el):
          # found a duplicate entry, just add the additional ress entry to the list
          test_el['is_ids'].append(ress_id)
          t_found = True
          break
      if t_found:
        # found a duplicate entry, see next el
        continue

      cluster_id = "ress_%s"%site_name

      count = 1
      if cluster_count.has_key(cluster_id):
        count = cluster_count[cluster_id] + 1
      cluster_count[cluster_id] = count

      if count == 1:
        key_name = cluster_id
      else:
        key_name="%s_%i" % (cluster_id,count)

        if count == 2: # rename id -> id_1
          key_name_tmp = "%s_1" % cluster_id
          ress_entries[key_name_tmp] = ress_entries[cluster_id]
          del ress_entries[cluster_id]

      ress_entries[key_name]=entry_el
    # -- end for loop --

    entries = self.discard_duplicate_entries(ress_entries)
    return entries

  #----------------------------
  def apply_filters_to_bdii(self,bdii_data):
    #-- set up the  python filter ---
    python_filter_obj=compile(self.glidein.ress_filter(),"<string>","eval")

    #-- using glexec? ---
    if self.glidein.use_glexec() == "y":
        def_glexec_bin='/opt/glite/sbin/glexec'
    else:
        def_glexec_bin='NONE'

    cluster_count={}
    bdii_entries={}
    for ldap_id in bdii_data.keys():
      el2=bdii_data[ldap_id]

      # LDAP returns everything in lists... convert to values (i.e. get first element from list)
      scalar_el={}
      for k in el2.keys():
        scalar_el[k]=el2[k][0]

      if not eval(python_filter_obj,scalar_el):
        continue # has not passed the filter

      work_dir="."
      gatekeeper="%s:%s/jobmanager-%s"%(el2['GlueCEHostingCluster'][0],el2['GlueCEInfoGatekeeperPort'][0],el2['GlueCEInfoJobManager'][0])
      rsl="(queue=%s)(jobtype=single)"%el2['GlueCEName'][0]

      site_name=el2['Mds-Vo-name'][0]
      cluster_id="bdii_%s"%site_name

      bdii_id={'type':'BDII','server':self.glidein.bdii_host(),'name':ldap_id}

      count=1
      if cluster_count.has_key(cluster_id):
        count=cluster_count[cluster_id]+1
      cluster_count[cluster_id]=count

      if count==1:
        key_name=cluster_id
      else:
        key_name="%s_%i"%(cluster_id,count)

        if count==2: # rename id -> id_1
          key_name_tmp="%s_1"%cluster_id
          bdii_entries[key_name_tmp]=bdii_entries[cluster_id]
          del bdii_entries[cluster_id]

      guess_glexec_bin=def_glexec_bin
      if guess_glexec_bin!='NONE':
        if el2['GlueCEHostingCluster'][0][-3:] in ('gov','edu'):
          # these should be OSG
          guess_glexec_bin='OSG'
        else:
          # I assume everybody else uses glite software
          guess_glexec_bin='/opt/glite/sbin/glexec'

      bdii_entries[key_name]={'gatekeeper':gatekeeper,'rsl':rsl,'gridtype':'gt2',
        'work_dir':work_dir,'site_name':site_name,
        'glexec_path':guess_glexec_bin, 'is_ids':[bdii_id]}
    #-- end for loop --

    entries = self.discard_duplicate_entries(bdii_entries)
    return entries

  #-------------------------------------------
  def discard_duplicate_entries(self,entries):
    #-- discarding bdii specific entries --
    for t in entries.keys():
      test_el = entries[t]
      t_found=False
      for l in self.config_entries_list.keys():
        l_el = self.config_entries_list[l]
        if self.compare_entry_els(test_el,l_el):
          # found a duplicate entry
          l_el['is_ids']+=test_el['is_ids']
          del entries[t] 
          t_found=True
          break
    return entries

  #----------------------------
  def compare_entry_els(self,el1,el2):
    for attr in ('gatekeeper','rsl'):
      if el1[attr]!=el2[attr]:
        return False
    return True

  #----------------------
  def additional_entry_points(self):
    print "Please list all additional glidein entry points,"
    while 1:
      print
      entry_name=raw_input("Entry name (leave empty when finished): ")
      if entry_name == "":
        if len(self.config_entries_list.keys()) < 1:
          print "You must instert at least one entry point"
          continue
        break

      if entry_name in self.config_entries_list.keys():
        print "You already inserted '%s'!" % entry_name
        continue
      gatekeeper_name = raw_input("Gatekeeper for '%s': " % entry_name)
      rsl_name        = raw_input("RSL for '%s': " % entry_name)
      work_dir        = raw_input("Work dir for '%s': " % entry_name)
      site_name       = raw_input("Site name for '%s': [%s] " % (entry_name,entry_name))
      if site_name == "":
        site_name = entry_name
      glexec_path = ""
      if self.glidein.use_glexec() == "y":
        glexec_path = raw_input("gLExec path for '%s': [OSG] " % entry_name)
        if glexec_path == "":
          glexec_path = 'OSG'
      else:
        glexec_path = "NONE"

      self.config_entries_list[entry_name]={'gatekeeper':gatekeeper_name,
                                            'rsl':rsl_name,
                                            'gridtype':'gt2',
                                            'work_dir':work_dir,
                                            'site_name':site_name,
                                            'glexec_path':glexec_path,
                                            'is_ids':[],}

  #----------------------------
  def get_ress_data(self):
    import condorMonitor
    #-- validate host ---
    if not common.url_is_valid(self.glidein.ress_host()):
      common.logerr("ReSS server (%s) in ress_host option is not valid or inaccssible." % self.glidein.ress_host())

    #-- get gatekeeper data from ReSS --
    condor_constraint='(GlueCEInfoContactString=!=UNDEFINED)&&(%s)' % self.glidein.ress_constraint()
    condor_obj=condorMonitor.CondorStatus(pool_name=self.glidein.ress_host())
    try:
      condor_obj.load(constraint=condor_constraint)
      condor_data=condor_obj.fetchStored()
    except Exception,e: 
      common.logerr(e)
    del condor_obj
    return condor_data

  #----------------------------
  def get_bdii_data(self):
    import ldapMonitor
    #-- validate host ---
    if not common.url_is_valid(self.glidein.bdii_host()):
      common.logerr("BDII server (%s) in bdii_host option is not valid or inaccssible." % self.glidein.bdii_host())

    #-- get gatekeeper data from BDII --
    try:
      bdii_obj=ldapMonitor.BDIICEQuery(self.glidein.bdii_host(),additional_filter_str=self.glidein.bdii_constraint())
      bdii_obj.load()
      bdii_data=bdii_obj.fetchStored()
    except Exception,e: 
      common.logerr(e)
    del bdii_obj
    return bdii_data


#---------------------------
def show_line():
    x = traceback.extract_tb(sys.exc_info()[2])
    z = x[len(x)-1]
    return "%s line %s" % (z[2],z[1])

#---------------------------
def validate_args(args):
    usage = """Usage: %prog --ini ini_file

This will install a Factory service for glideinWMS using the ini file
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

##################################################
def main(argv):
  try:
    options = validate_args(argv)
    factory = Factory(options.inifile)
    factory.install()
    #factory.create_glideins()
    #factory.create_env_script()
    #factory.start()
    #factory.validate_install()
    #factory.get_config_entries_data()
    #factory.create_config()
  except KeyboardInterrupt:
    common.logit("\n... looks like you aborted this script... bye.");
    return 1
  except EOFError:
    common.logit("\n... looks like you aborted this script... bye.");
    return 1
  except ConfigurationError, e:
    print;print "ConfigurationError ERROR(should not get these): %s"%e;return 1
  except common.WMSerror:
    print;return 1
  return 0

#-------------------------
if __name__ == '__main__':
  sys.exit(main(sys.argv))

