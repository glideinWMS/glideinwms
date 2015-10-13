# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Glidein creation module
#   Classes and functions needed to handle dictionary files
#   created out of the parameter object
#

import os,os.path,shutil,string
import sys
import cgWDictFile,cWDictFile
import cgWCreate
import cgWConsts,cWConsts

WEB_BASE_DIR=os.path.join(os.path.dirname(__file__),"..","web_base")

from glideinwms.lib import pubCrypto

class UnconfiguredScheddError(Exception):

    def __init__(self, schedd):
        self.schedd = schedd
        self.err_str = "Schedd '%s' used by one or more entries is not configured." % (schedd)

    def __str__(self):
        return repr(self.err_str)

################################################
#
# This Class contains the main dicts
#
################################################

class glideinMainDicts(cgWDictFile.glideinMainDicts):
    def __init__(self,conf,workdir_name):
        submit_dir = conf.get_submit_dir()
        stage_dir = conf.get_stage_dir()
        monitor_dir = conf.get_monitor_dir()
        log_dir = conf.get_log_dir()
        client_log_dirs = conf.get_client_log_dirs()
        client_proxy_dirs = conf.get_client_proxy_dirs()
        cgWDictFile.glideinMainDicts.__init__(self,submit_dir,stage_dir,workdir_name,
                                              log_dir,
                                              client_log_dirs,client_proxy_dirs)
        self.monitor_dir=monitor_dir
        self.add_dir_obj(cWDictFile.monitorWLinkDirSupport(self.monitor_dir,self.work_dir))
        self.monitor_jslibs_dir=os.path.join(self.monitor_dir,'jslibs')
        self.add_dir_obj(cWDictFile.simpleDirSupport(self.monitor_jslibs_dir,"monitor"))
        self.monitor_images_dir=os.path.join(self.monitor_dir,'images')
        self.add_dir_obj(cWDictFile.simpleDirSupport(self.monitor_images_dir,"monitor"))
        self.conf=conf
        self.active_sub_list=[]
        self.monitor_jslibs=[]
        self.monitor_images=[]
        self.monitor_htmls=[]

    def populate(self):
        # put default files in place first       
        self.dicts['file_list'].add_placeholder('error_gen.sh',allow_overwrite=True)
        self.dicts['file_list'].add_placeholder('error_augment.sh',allow_overwrite=True)
        self.dicts['file_list'].add_placeholder('setup_script.sh',allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball
        self.dicts['file_list'].add_placeholder(cWConsts.GRIDMAP_FILE,allow_overwrite=True) # this one must be loaded before setup_x509.sh is run

        #load system files
        for file_name in ('error_gen.sh','error_augment.sh','parse_starterlog.awk', 'advertise_failure.helper',
                          "condor_config", "condor_config.multi_schedd.include", "condor_config.dedicated_starter.include", "condor_config.check.include", "condor_config.monitor.include"):
            self.dicts['file_list'].add_from_file(file_name,(cWConsts.insert_timestr(file_name),"regular","TRUE",'FALSE'),os.path.join(WEB_BASE_DIR,file_name))
        self.dicts['description'].add("condor_config","condor_config")
        self.dicts['description'].add("condor_config.multi_schedd.include","condor_config_multi_include")
        self.dicts['description'].add("condor_config.dedicated_starter.include","condor_config_main_include")
        self.dicts['description'].add("condor_config.monitor.include","condor_config_monitor_include")
        self.dicts['description'].add("condor_config.check.include","condor_config_check_include")
        self.dicts['vars'].load(WEB_BASE_DIR,'condor_vars.lst',change_self=False,set_not_changed=False)

        #
        # Note:
        #  We expect the condor platform info to be coming in as parameters
        #  as FE provided consts file is not available at this time
        #

        # add the basic standard params
        self.dicts['params'].add("GLIDEIN_Report_Failed",'NEVER')
        self.dicts['params'].add("CONDOR_OS",'default')
        self.dicts['params'].add("CONDOR_ARCH",'default')
        self.dicts['params'].add("CONDOR_VERSION",'default')

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('setup_script.sh','cat_consts.sh','condor_platform_select.sh'):
            self.dicts['file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(WEB_BASE_DIR,script_name))

        #load condor tarballs
        # only one will be downloaded in the end... based on what condor_platform_select.sh decides
        condor_tarballs = self.conf.get_child_list(u'condor_tarballs')
        for condor_idx in range(len(condor_tarballs)):
            condor_el=condor_tarballs[condor_idx]

            # condor_el now is a combination of csv version+os+arch
            # Get list of valid tarballs for this condor_el
            # Register the tarball, but make download conditional to cond_name

            condor_el_valid_tarballs = get_valid_condor_tarballs([condor_el])
            condor_fname = cWConsts.insert_timestr(cgWConsts.CONDOR_FILE % condor_idx)
            condor_tarfile = ""

            condor_tarfile = condor_el['tar_file']

            for tar in condor_el_valid_tarballs:
                condor_platform = "%s-%s-%s" % (tar['version'], tar['os'],
                                                tar['arch'])
                cond_name = "CONDOR_PLATFORM_%s" % condor_platform
                condor_platform_fname = cgWConsts.CONDOR_FILE % condor_platform

                self.dicts['file_list'].add_from_file(
                    condor_platform_fname, (condor_fname,
                                            "untar", cond_name,
                                            cgWConsts.CONDOR_ATTR),
                    condor_el['tar_file'])

                self.dicts['untar_cfg'].add(condor_platform_fname,
                                            cgWConsts.CONDOR_DIR)
                # Add cond_name in the config, so that it is known 
                # But leave it disabled by default
                self.dicts['consts'].add(cond_name, "0",
                                         allow_overwrite=False)

        #
        # Note:
        #  We expect the collector info to be coming in as parameter
        #  as FE consts file is not available at this time
        #

        # add the basic standard params
        self.dicts['params'].add("GLIDEIN_Collector",'Fake')

        # add the factory monitoring collector parameter, if any collectors are defined
        # this is purely a factory thing
        factory_monitoring_collector=calc_monitoring_collectors_string(self.conf.get_child_list(u'monitoring_collectors'))
        if factory_monitoring_collector is not None:
            self.dicts['params'].add('GLIDEIN_Factory_Collector',str(factory_monitoring_collector))
        populate_gridmap(self.conf,self.dicts['gridmap'])
        
        file_list_scripts = ['collector_setup.sh',
                             'create_temp_mapfile.sh',
                             'setup_x509.sh',
                             cgWConsts.CONDOR_STARTUP_FILE]
        after_file_list_scripts = ['check_proxy.sh',
                                   'create_mapfile.sh',
                                   'validate_node.sh',
                                   'setup_network.sh',
                                   'gcb_setup.sh',
                                   'glexec_setup.sh',
                                   'java_setup.sh',
                                   'glidein_memory_setup.sh',
                                   'glidein_cpus_setup.sh',
                                   'glidein_sitewms_setup.sh',
                                   'smart_partitionable.sh']
        # Only execute scripts once
        duplicate_scripts = set(file_list_scripts).intersection(after_file_list_scripts)
        if duplicate_scripts:
            raise RuntimeError, "Duplicates found in the list of files to execute '%s'" % ','.join(duplicate_scripts)

        # Load more system scripts
        for script_name in file_list_scripts:
            self.dicts['file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(WEB_BASE_DIR,script_name))

        # make sure condor_startup does not get executed ahead of time under normal circumstances
        # but must be loaded early, as it also works as a reporting script in case of error
        self.dicts['description'].add(cgWConsts.CONDOR_STARTUP_FILE,"last_script")

        #
        # At this point in the glideins, condor_advertize should be able to talk to the FE collector
        #

        # put user files in stage
        for file in self.conf.get_child_list(u'files'):
            add_file_unparsed(file.to_dict(),self.dicts)

        # put user attributes into config files
        for attr in self.conf.get_child_list(u'attrs'):
            add_attr_unparsed(attr,self.dicts,"main")

        # add additional system scripts
        for script_name in after_file_list_scripts:
            self.dicts['after_file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(WEB_BASE_DIR,script_name))

        # populate complex files
        populate_factory_descript(self.work_dir,self.dicts['glidein'],self.active_sub_list,self.conf)
        populate_frontend_descript(self.dicts['frontend_descript'],self.conf)


        # populate the monitor files
        javascriptrrd_dir = self.conf.get_child(u'monitor')[u'javascriptRRD_dir']
        for mfarr in ((WEB_BASE_DIR,'factory_support.js'),
                      (javascriptrrd_dir,'javascriptrrd.wlibs.js')):
            mfdir,mfname=mfarr
            parent_dir = self.find_parent_dir(mfdir,mfname)
            mfobj=cWDictFile.SimpleFile(parent_dir,mfname)
            mfobj.load()
            self.monitor_jslibs.append(mfobj)

        for mfarr in ((WEB_BASE_DIR,'factoryRRDBrowse.html'),
                      (WEB_BASE_DIR,'factoryRRDEntryMatrix.html'),
                      (WEB_BASE_DIR,'factoryStatus.html'),
                      (WEB_BASE_DIR,'factoryLogStatus.html'),
                      (WEB_BASE_DIR,'factoryCompletedStats.html'),
                      (WEB_BASE_DIR,'factoryStatusNow.html'),
                      (WEB_BASE_DIR,'factoryEntryStatusNow.html')):
            mfdir,mfname=mfarr
            mfobj=cWDictFile.SimpleFile(mfdir,mfname)
            mfobj.load()
            self.monitor_htmls.append(mfobj)            
        
        # add the index page and its images
        mfobj=cWDictFile.SimpleFile(WEB_BASE_DIR + '/factory/', 'index.html')
        mfobj.load()
        self.monitor_htmls.append(mfobj)
        for imgfile in ('factoryCompletedStats.png',
                        'factoryEntryStatusNow.png',
                        'factoryLogStatus.png',
                        'factoryRRDBrowse.png',
                        'factoryRRDEntryMatrix.png',
                        'factoryStatus.png',
                        'factoryStatusNow.png'):
            mfobj=cWDictFile.SimpleFile(WEB_BASE_DIR + '/factory/images/', imgfile)
            mfobj.load()
            self.monitor_images.append(mfobj)

        # populate the monitor configuration file
        #populate_monitor_config(self.work_dir,self.dicts['glidein'],params)

    def find_parent_dir(self,search_path,name):
        """ Given a search path, determine if the given file exists
            somewhere in the path.
            Returns: if found. returns the parent directory
                     if not found, raises an Exception
        """
        for root, dirs, files in os.walk(search_path,topdown=True):
            for file_name in files:
                if file_name == name:
                    return root
        raise RuntimeError,"Unable to find %(file)s in %(dir)s path" % \
                           { "file" : name,  "dir" : search_path, } 

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            print "WARNING: main monitor base_dir has changed, stats may be lost: '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cgWDictFile.glideinMainDicts.reuse(self,other)

    def save(self,set_readonly=True):
        cgWDictFile.glideinMainDicts.save(self,set_readonly)
        self.save_pub_key()
        self.save_monitor()
        self.save_monitor_config(self.work_dir,self.dicts['glidein'])


    ########################################
    # INTERNAL
    ########################################
    
    def save_pub_key(self):
        sec_el = self.conf[u'security']
        if u'pub_key' not in sec_el:
            pass # nothing to do
        elif sec_el[u'pub_key']=='RSA':
            rsa_key_fname=os.path.join(self.work_dir,cgWConsts.RSA_KEY)

            if not os.path.isfile(rsa_key_fname):
                # create the key only once

                # touch the file with correct flags first
                # I have no way to do it in  RSAKey class
                fd=os.open(rsa_key_fname,os.O_CREAT,0600)
                os.close(fd)
                
                key_obj=pubCrypto.RSAKey()
                key_obj.new(int(u'key_length' in sec_el))
                key_obj.save(rsa_key_fname)            
        else:
            raise RuntimeError,"Invalid value for security.pub_key(%s), must be either None or RSA"%sec_el[u'pub_key']

    def save_monitor(self):
        for fobj in self.monitor_jslibs:
            fobj.save(dir=self.monitor_jslibs_dir,save_only_if_changed=False)
        for fobj in self.monitor_images:
            fobj.save(dir=self.monitor_images_dir,save_only_if_changed=False)
        for fobj in self.monitor_htmls:
            fobj.save(dir=self.monitor_dir,save_only_if_changed=False)
        return

    ###################################
    # Create the monitor config file
    def save_monitor_config(self, work_dir, glidein_dict):
        monitor_config_file = os.path.join(self.conf.get_monitor_dir(), cgWConsts.MONITOR_CONFIG_FILE)
        monitor_config_line = []
        
        monitor_config_fd = open(monitor_config_file,'w')
        monitor_config_line.append("<monitor_config>")
        monitor_config_line.append("  <entries>")
        try:
            try:
                for entry in self.conf.get_child_list(u'entries'):
                    if eval(entry[u'enabled'],{},{}):
                        monitor_config_line.append("    <entry name=\"%s\">" % entry[u'name'])
                        monitor_config_line.append("      <monitorgroups>")                
                        for group in entry.get_child_list(u'monitorgroups'):
                            monitor_config_line.append("        <monitorgroup group_name=\"%s\">" % group[u'group_name'])
                            monitor_config_line.append("        </monitorgroup>")
                        
                        monitor_config_line.append("      </monitorgroups>")
                        monitor_config_line.append("    </entry>")
        
                monitor_config_line.append("  </entries>")
                monitor_config_line.append("</monitor_config>")
        
                for line in monitor_config_line:
                    monitor_config_fd.write(line + "\n")
            except IOError,e:
                raise RuntimeError,"Error writing into file %s"%monitor_config_file
        finally:
            monitor_config_fd.close()
    
################################################
#
# This Class contains the entry dicts
#
################################################

class glideinEntryDicts(cgWDictFile.glideinEntryDicts):
    def __init__(self,conf,sub_name,
                 summary_signature,workdir_name):
        submit_dir = conf.get_submit_dir()
        stage_dir = conf.get_stage_dir()
        monitor_dir = conf.get_monitor_dir()
        log_dir = conf.get_log_dir()
        client_log_dirs = conf.get_client_log_dirs()
        client_proxy_dirs = conf.get_client_proxy_dirs()
        cgWDictFile.glideinEntryDicts.__init__(self,submit_dir,stage_dir,sub_name,summary_signature,workdir_name,
                                               log_dir,client_log_dirs,client_proxy_dirs)
                                               
        self.monitor_dir=cgWConsts.get_entry_monitor_dir(monitor_dir,sub_name)
        self.add_dir_obj(cWDictFile.monitorWLinkDirSupport(self.monitor_dir,self.work_dir))
        self.conf=conf

    def erase(self):
        cgWDictFile.glideinEntryDicts.erase(self)
        self.dicts['condor_jdl']=cgWCreate.GlideinSubmitDictFile(self.work_dir,cgWConsts.SUBMIT_FILE)
        
    def load(self):
        cgWDictFile.glideinEntryDicts.load(self)
        self.dicts['condor_jdl'].load()

    def save_final(self,set_readonly=True):
        sub_stage_dir=cgWConsts.get_entry_stage_dir("",self.sub_name)
        
        self.dicts['condor_jdl'].finalize(self.summary_signature['main'][0],self.summary_signature[sub_stage_dir][0],
                                          self.summary_signature['main'][1],self.summary_signature[sub_stage_dir][1])
        self.dicts['condor_jdl'].save(set_readonly=set_readonly)
        
    
    def populate(self,entry,schedd):
        # put default files in place first
        self.dicts['file_list'].add_placeholder(cWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball

        # follow by the blacklist file
        file_name=cWConsts.BLACKLIST_FILE
        self.dicts['file_list'].add_from_file(file_name,(file_name,"nocache","TRUE",'BLACKLIST_FILE'),os.path.join(WEB_BASE_DIR,file_name))

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh',"check_blacklist.sh"):
            self.dicts['file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(WEB_BASE_DIR,script_name))

        #load system files
        self.dicts['vars'].load(WEB_BASE_DIR,'condor_vars.lst.entry',change_self=False,set_not_changed=False)
        
        
        # put user files in stage
        for user_file in entry.get_child_list(u'files'):
            add_file_unparsed(user_file.to_dict(),self.dicts)

        # Add attribute for voms

        # put user attributes into config files
        for attr in entry.get_child_list(u'attrs'):
            add_attr_unparsed(attr,self.dicts,self.sub_name)

        # put standard attributes into config file
        # override anything the user set

        config = entry.get_child(u'config')
        restrictions = config.get_child(u'restrictions')
        submit = config.get_child(u'submit')
        for dtype in ('attrs','consts'):
            self.dicts[dtype].add("GLIDEIN_Gatekeeper",entry[u'gatekeeper'],allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_GridType",entry[u'gridtype'],allow_overwrite=True)
            # MERGENOTE:
            # GLIDEIN_REQUIRE_VOMS publishes an attribute so that users without VOMS proxies
            #   can avoid sites that require VOMS proxies (using the normal Condor Requirements
            #   string. 
            self.dicts[dtype].add("GLIDEIN_REQUIRE_VOMS",restrictions[u'require_voms_proxy'],allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_REQUIRE_GLEXEC_USE",restrictions[u'require_glidein_glexec_use'],allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_TrustDomain",entry[u'trust_domain'],allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_SupportedAuthenticationMethod",entry[u'auth_method'],allow_overwrite=True)
            if u'rsl' in entry:
                self.dicts[dtype].add('GLIDEIN_GlobusRSL',entry[u'rsl'],allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_SlotsLayout", submit[u'slots_layout'], allow_overwrite=True)


        self.dicts['vars'].add_extended("GLIDEIN_REQUIRE_VOMS","boolean",restrictions[u'require_voms_proxy'],None,False,True,True)
        self.dicts['vars'].add_extended("GLIDEIN_REQUIRE_GLEXEC_USE","boolean",restrictions[u'require_glidein_glexec_use'],None,False,True,True)

        # populate infosys
        for infosys_ref in entry.get_child_list(u'infosys_refs'):
            self.dicts['infosys'].add_extended(infosys_ref[u'type'],infosys_ref[u'server'],infosys_ref[u'ref'],allow_overwrite=True)

        # populate monitorgroups
        for monitorgroup in entry.get_child_list(u'monitorgroups'):
            self.dicts['mongroup'].add_extended(monitorgroup[u'group_name'],allow_overwrite=True)

        # populate complex files
        populate_job_descript(self.work_dir,self.dicts['job_descript'],
                              self.sub_name,entry,schedd)

        ################################################################################################################
        # This is the original function call:
        #
        # self.dicts['condor_jdl'].populate(cgWConsts.STARTUP_FILE,
        #                                   params.factory_name,params.glidein_name,self.sub_name,
        #                                   sub_params.gridtype,sub_params.gatekeeper, sub_params.rsl, sub_params.auth_method,
        #                                   params.web_url,sub_params.proxy_url,sub_params.work_dir,
        #                                   params.submit.base_client_log_dir, sub_params.submit.submit_attrs)
        #
        # Almost all of the parameters are attributes of params and/or sub_params.  Instead of maintaining an ever
        # increasing parameter list for this function, lets just pass params, sub_params, and the 2 other parameters
        # to the function and call it a day.
        ################################################################################################################
        self.dicts['condor_jdl'].populate(cgWConsts.STARTUP_FILE, self.sub_name, self.conf, entry)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            print "WARNING: entry monitor base_dir has changed, stats may be lost: '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cgWDictFile.glideinEntryDicts.reuse(self,other)

################################################
#
# This Class contains both the main and
# the entry dicts
#
################################################

class glideinDicts(cgWDictFile.glideinDicts):
    def __init__(self,conf,
                 sub_list=None): # if None, get it from params
        if sub_list is None:
            sub_list = [e[u'name'] for e in conf.get_child_list(u'entries')]

        self.conf=conf
        submit_dir = conf.get_submit_dir()
        stage_dir = conf.get_stage_dir()
        monitor_dir = conf.get_monitor_dir()
        log_dir = conf.get_log_dir()
        client_log_dirs = conf.get_client_log_dirs()
        client_proxy_dirs = conf.get_client_proxy_dirs()
        cgWDictFile.glideinDicts.__init__(self,submit_dir,stage_dir,log_dir,client_log_dirs,client_proxy_dirs,sub_list)

        self.monitor_dir=monitor_dir
        self.active_sub_list=[]
        return

    def populate(self,other=None): # will update params (or self.params)
        self.main_dicts.populate()
        self.active_sub_list=self.main_dicts.active_sub_list

        schedds = self.conf[u'schedd_name'].split(u',')
        schedd_counts = {}
        for s in schedds:
            schedd_counts[s] = 0

        if other is not None:
            for e in other.sub_dicts:
                schedd = other.sub_dicts[e]['job_descript']['Schedd']
                if schedd in schedd_counts:
                    schedd_counts[schedd] += 1

        for entry in self.conf.get_child_list(u'entries'):
            entry_name = entry[u'name']
            if other is not None and entry_name in other.sub_dicts and other.sub_dicts[entry_name]['job_descript']['Schedd'] in schedd_counts:
                schedd = other.sub_dicts[entry_name]['job_descript']['Schedd']
            else:
                schedd_arr = [(k, schedd_counts[k]) for k in schedd_counts]
                schedd = sorted(schedd_arr, key=lambda x:x[1])[0][0]
                schedd_counts[schedd] += 1
            self.sub_dicts[entry_name].populate(entry, schedd)

        validate_condor_tarball_attrs(self.conf)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            print "WARNING: monitor base_dir has changed, stats may be lost: '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cgWDictFile.glideinDicts.reuse(self,other)

    ###########
    # PRIVATE
    ###########

    ######################################
    def sortit(self, unsorted_dict):
        """ A temporary method for sorting a dictionary based on
            the value of the dictionary item.  In python 2.4+,
            a 'key' arguement can be used in the 'sort' and 'sorted'
            functions.  This is not available in python 2.3.4/SL4
            platforms.
            Returns a sorted list of the dictionary items based on
            their value.
        """
        d = {}
        i = 0
        for key in unsorted_dict.keys():
            d[i] = (key,unsorted_dict[key])
            i = i + 1
        temp_list = [ (x[1][1], x[0]) for x in d.items() ]
        temp_list.sort()
        sortedList = []
        for (tmp, key) in temp_list:
            sortedList.append(d[key][0])
        return sortedList


    ######################################
    # Redefine methods needed by parent
    def new_MainDicts(self):
        return glideinMainDicts(self.conf,self.workdir_name)

    def new_SubDicts(self,sub_name):
        return glideinEntryDicts(self.conf,sub_name,
                                 self.main_dicts.get_summary_signature(),self.workdir_name)
        
############################################################
#
# P R I V A T E - Do not use
# 
############################################################

#############################################
# Add a user file residing in the stage area
# file as described by Params.file_defaults
def add_file_unparsed(user_file,dicts):
    absfname=user_file['absfname']
    if absfname is None:
        raise RuntimeError, "Found a file element without an absname: %s"%user_file
    
    relfname=user_file['relfname']
    if relfname is None:
        relfname=os.path.basename(absfname) # defualt is the final part of absfname
    if len(relfname)<1:
        raise RuntimeError, "Found a file element with an empty relfname: %s"%user_file

    is_const=eval(user_file['const'],{},{})
    is_executable=eval(user_file['executable'],{},{})
    is_wrapper=eval(user_file['wrapper'],{},{})
    do_untar=eval(user_file['untar'],{},{})

    file_list_idx='file_list'
    if user_file.has_key('after_entry'):
        if eval(user_file['after_entry'],{},{}):
            file_list_idx='after_file_list'

    if is_executable: # a script
        if not is_const:
            raise RuntimeError, "A file cannot be executable if it is not constant: %s"%user_file
    
        if do_untar:
            raise RuntimeError, "A tar file cannot be executable: %s"%user_file

        if is_wrapper:
            raise RuntimeError, "A wrapper file cannot be executable: %s"%user_file

        dicts[file_list_idx].add_from_file(relfname,(cWConsts.insert_timestr(relfname),"exec","TRUE",'FALSE'),absfname)
    elif is_wrapper: # a sourceable script for the wrapper
        if not is_const:
            raise RuntimeError, "A file cannot be a wrapper if it is not constant: %s"%user_file
    
        if do_untar:
            raise RuntimeError, "A tar file cannot be a wrapper: %s"%user_file

        dicts[file_list_idx].add_from_file(relfname,(cWConsts.insert_timestr(relfname),"wrapper","TRUE",'FALSE'),absfname)
    elif do_untar: # a tarball
        if not is_const:
            raise RuntimeError, "A file cannot be untarred if it is not constant: %s"%user_file

        wnsubdir=user_file['untar_options']['dir']
        if wnsubdir is None:
            wnsubdir=string.split(relfname,'.',1)[0] # deafult is relfname up to the first .

        config_out=user_file['untar_options']['absdir_outattr']
        if config_out is None:
            config_out="FALSE"
        cond_attr=user_file['untar_options']['cond_attr']


        dicts[file_list_idx].add_from_file(relfname,(cWConsts.insert_timestr(relfname),"untar",cond_attr,config_out),absfname)
        dicts['untar_cfg'].add(relfname,wnsubdir)
    else: # not executable nor tarball => simple file
        if is_const:
            val='regular'
            dicts[file_list_idx].add_from_file(relfname,(cWConsts.insert_timestr(relfname),val,'TRUE','FALSE'),absfname)
        else:
            val='nocache'
            dicts[file_list_idx].add_from_file(relfname,(relfname,val,'TRUE','FALSE'),absfname) # no timestamp if it can be modified

#######################
# Register an attribute
# attr_obj as described by Params.attr_defaults
def add_attr_unparsed(attr,dicts,description):
    try:
        add_attr_unparsed_real(attr,dicts)
    except RuntimeError,e:
        raise RuntimeError, "Error parsing attr %s[%s]: %s"%(description,attr[u'name'],str(e))

def add_attr_unparsed_real(attr,dicts):
    attr_name = attr[u'name']
    
    do_publish=eval(attr[u'publish'],{},{})
    is_parameter=eval(attr[u'parameter'],{},{})
    is_const=eval(attr[u'const'],{},{})
    attr_val=attr.get_val()
    
    if do_publish: # publish in factory ClassAd
        if is_parameter: # but also push to glidein
            if is_const:
                dicts['attrs'].add(attr_name,attr_val)
                dicts['consts'].add(attr_name,attr_val)
            else:
                dicts['params'].add(attr_name,attr_val)
        else: # only publish
            if (not is_const):
                raise RuntimeError, "Published attribute '%s' must be either a parameter or constant: %s"%(attr_name,attr)
            
            dicts['attrs'].add(attr_name,attr_val)
            dicts['consts'].add(attr_name,attr_val)
    else: # do not publish, only to glidein
        if is_parameter:
            if is_const:
                dicts['consts'].add(attr_name,attr_val)
            else:
                raise RuntimeError, "Parameter attributes '%s' must be either a published or constant: %s"%(attr_name,attr)
        else:
            raise RuntimeError, "Attributes '%s' must be either a published or parameters: %s"%(attr_name,attr) 

    do_glidein_publish=eval(attr[u'glidein_publish'],{},{})
    do_job_publish=eval(attr[u'job_publish'],{},{})

    if do_glidein_publish or do_job_publish:
            # need to add a line only if will be published
            if dicts['vars'].has_key(attr_name):
                # already in the var file, check if compatible
                attr_var_el=dicts['vars'][attr_name]
                attr_var_type=attr_var_el[0]
                if (((attr[u'type']=="int") and (attr_var_type!='I')) or
                    ((attr[u'type']=="expr") and (attr_var_type=='I')) or
                    ((attr[u'type']=="string") and (attr_var_type=='I'))):
                    raise RuntimeError, "Types not compatible (%s,%s)"%(attr[u'type'],attr_var_type)
                attr_var_export=attr_var_el[4]
                if do_glidein_publish and (attr_var_export=='N'):
                    raise RuntimeError, "Cannot force glidein publishing"
                attr_var_job_publish=attr_var_el[5]
                if do_job_publish and (attr_var_job_publish=='-'):
                    raise RuntimeError, "Cannot force job publishing"
            else:
                dicts['vars'].add_extended(attr_name,attr[u'type'],None,None,False,do_glidein_publish,do_job_publish)

###################################
# Create the glidein descript file
def populate_factory_descript(work_dir,
                              glidein_dict,active_sub_list,        # will be modified
                              conf):
        
        down_fname=os.path.join(work_dir,'glideinWMS.downtimes')

        sec_el = conf.get_child(u'security')
        sub_el = conf.get_child(u'submit')
        mon_foot_el = conf.get_child(u'monitor_footer')
        if u'factory_collector' in conf:
            glidein_dict.add('FactoryCollector',conf[u'factory_collector'])
        else:
            glidein_dict.add('FactoryCollector',None)
        glidein_dict.add('FactoryName',conf[u'factory_name'])
        glidein_dict.add('GlideinName',conf[u'glidein_name'])
        glidein_dict.add('WebURL',conf.get_web_url())
        glidein_dict.add('PubKeyType',sec_el[u'pub_key'])
        glidein_dict.add('OldPubKeyGraceTime',sec_el[u'reuse_oldkey_onstartup_gracetime'])
        glidein_dict.add('MonitorUpdateThreadCount',conf.get_child(u'monitor')[u'update_thread_count'])
        glidein_dict.add('RemoveOldCredFreq', sec_el[u'remove_old_cred_freq'])
        glidein_dict.add('RemoveOldCredAge', sec_el[u'remove_old_cred_age'])
        del active_sub_list[:] # clean

        for entry in conf.get_child_list(u'entries'):
            if eval(entry[u'enabled'],{},{}):
                active_sub_list.append(entry[u'name'])

        glidein_dict.add('Entries',string.join(active_sub_list,','))
        glidein_dict.add('AdvertiseWithTCP',conf[u'advertise_with_tcp'])
        glidein_dict.add('AdvertiseWithMultiple',conf[u'advertise_with_multiple'])
        glidein_dict.add('LoopDelay',conf[u'loop_delay'])
        glidein_dict.add('AdvertiseDelay',conf[u'advertise_delay'])
        glidein_dict.add('RestartAttempts',conf[u'restart_attempts'])
        glidein_dict.add('RestartInterval',conf[u'restart_interval'])
        glidein_dict.add('EntryParallelWorkers',conf[u'entry_parallel_workers'])
        glidein_dict.add('LogDir',conf.get_log_dir())
        glidein_dict.add('ClientLogBaseDir',sub_el[u'base_client_log_dir'])
        glidein_dict.add('ClientProxiesBaseDir',sub_el[u'base_client_proxies_dir'])
        glidein_dict.add('DowntimesFile',down_fname)
        
        glidein_dict.add('MonitorDisplayText',mon_foot_el[u'display_txt'])
        glidein_dict.add('MonitorLink',mon_foot_el[u'href_link'])
        
        monitoring_collectors=calc_primary_monitoring_collectors(conf.get_child_list(u'monitoring_collectors'))
        if monitoring_collectors is not None:
            glidein_dict.add('PrimaryMonitoringCollectors',str(monitoring_collectors))

        log_retention = conf.get_child(u'log_retention')
        for lel in (("job_logs",'JobLog'),("summary_logs",'SummaryLog'),("condor_logs",'CondorLog')):
            param_lname,str_lname=lel
            for tel in (("max_days",'MaxDays'),("min_days",'MinDays'),("max_mbytes",'MaxMBs')):
                param_tname,str_tname=tel
                glidein_dict.add('%sRetention%s'%(str_lname,str_tname),log_retention.get_child(param_lname)[param_tname])

        # convert to list of dicts so that str() below gives expected results
        proc_logs = []
        for pl in log_retention.get_child_list(u'process_logs'):
            proc_logs.append(dict(pl))
        glidein_dict.add('ProcessLogs', str(proc_logs))

#######################
def populate_job_descript(work_dir, job_descript_dict, 
                          sub_name, entry, schedd):
    """
    Modifies the job_descript_dict to contain the factory configuration values.
    
    @type work_dir: string
    @param work_dir: location of entry files
    @type job_descript_dict: dict
    @param job_descript_dict: contains the values of the job.descript file
    @type sub_name: string
    @param sub_name: entry name
    @type sub_params: dict
    @param sub_params: entry parameters
    """
    
    down_fname = os.path.join(work_dir, 'glideinWMS.downtimes')

    config = entry.get_child(u'config')
    max_jobs = config.get_child(u'max_jobs')

    job_descript_dict.add('EntryName', sub_name)
    job_descript_dict.add('GridType', entry[u'gridtype'])
    job_descript_dict.add('Gatekeeper', entry[u'gatekeeper'])
    job_descript_dict.add('AuthMethod', entry[u'auth_method'])
    job_descript_dict.add('TrustDomain', entry[u'trust_domain'])
    if u'vm_id' in entry:
        job_descript_dict.add('EntryVMId', entry[u'vm_id'])
    if u'vm_type' in entry:
        job_descript_dict.add('EntryVMType', entry[u'vm_type'])
    if u'rsl' in entry:
        job_descript_dict.add('GlobusRSL', entry[u'rsl'])
    job_descript_dict.add('Schedd', schedd)
    job_descript_dict.add('StartupDir', entry[u'work_dir'])
    if u'proxy_url' in entry:
        job_descript_dict.add('ProxyURL', entry[u'proxy_url'])
    job_descript_dict.add('Verbosity', entry[u'verbosity'])
    job_descript_dict.add('DowntimesFile', down_fname)
    per_entry = max_jobs.get_child(u'per_entry')
    job_descript_dict.add('PerEntryMaxGlideins', per_entry[u'glideins'])
    job_descript_dict.add('PerEntryMaxIdle', per_entry[u'idle'])
    job_descript_dict.add('PerEntryMaxHeld', per_entry[u'held'])
    def_per_fe = max_jobs.get_child(u'default_per_frontend')
    job_descript_dict.add('DefaultPerFrontendMaxGlideins', def_per_fe[u'glideins'])
    job_descript_dict.add('DefaultPerFrontendMaxIdle', def_per_fe[u'idle'])
    job_descript_dict.add('DefaultPerFrontendMaxHeld', def_per_fe[u'held'])
    submit = config.get_child(u'submit')
    job_descript_dict.add('MaxSubmitRate', submit[u'max_per_cycle'])
    job_descript_dict.add('SubmitCluster', submit[u'cluster_size'])
    job_descript_dict.add('SubmitSlotsLayout', submit[u'slots_layout'])
    job_descript_dict.add('SubmitSleep', submit[u'sleep'])
    remove = config.get_child(u'remove')
    job_descript_dict.add('MaxRemoveRate', remove[u'max_per_cycle'])
    job_descript_dict.add('RemoveSleep', remove[u'sleep'])
    release = config.get_child(u'release')
    job_descript_dict.add('MaxReleaseRate', release[u'max_per_cycle'])
    job_descript_dict.add('ReleaseSleep', release[u'sleep'])
    restrictions = config.get_child(u'restrictions')
    job_descript_dict.add('RequireVomsProxy',restrictions[u'require_voms_proxy'])
    job_descript_dict.add('RequireGlideinGlexecUse',restrictions[u'require_glidein_glexec_use'])
   
    # Add the frontend specific job limits to the job.descript file
    max_held_frontend = ""
    max_idle_frontend = ""
    max_glideins_frontend = ""
    per_frontends = entry.get_max_per_frontends()
    for frontend_name in per_frontends:
        el = per_frontends[frontend_name]
        max_held_frontend += frontend_name + ";" + el[u'held'] + ","
        max_idle_frontend += frontend_name + ";" + el[u'idle'] + ","
        max_glideins_frontend += frontend_name + ";" + el[u'glideins'] + ","
    job_descript_dict.add("PerFrontendMaxGlideins", max_glideins_frontend[:-1])
    job_descript_dict.add("PerFrontendMaxHeld", max_held_frontend[:-1])
    job_descript_dict.add("PerFrontendMaxIdle", max_idle_frontend[:-1])
    
    #  If the configuration has a non-empty frontend_allowlist
    #  then create a white list and add all the frontends:security_classes
    #  to it.
    white_mode = "Off"
    allowed_vos = ""
    allowed_frontends = entry.get_allowed_frontends()
    for X in allowed_frontends:
        white_mode = "On"
        allowed_vos = allowed_vos + X + ":" + allowed_frontends[X][u'security_class'] + ","
    job_descript_dict.add("WhitelistMode", white_mode)
    job_descript_dict.add("AllowedVOs", allowed_vos[:-1])


###################################
# Create the frontend descript file
def populate_frontend_descript(frontend_dict,     # will be modified
                               conf):
    for fe_el in conf.get_child(u'security').get_child_list(u'frontends'):
        fe_name = fe_el[u'name']

        ident=fe_el['identity']
        if ident is None:
            raise RuntimeError, 'security.frontends[%s][identity] not defined, but required'%fe_name

        maps={}
        for sc_el in fe_el.get_child_list(u'security_classes'):
            sc_name = sc_el[u'name']
            username=sc_el['username']
            if username is None:
                raise RuntimeError, 'security.frontends[%s].security_classes[%s][username] not defined, but required'%(fe_name,sc_name)
            maps[sc_name]=username
        
        frontend_dict.add(fe_name,{'ident':ident,'usermap':maps})



#####################################################
# Populate gridmap to be used by the glideins
def populate_gridmap(conf,gridmap_dict):
    collector_dns=[]
    for el in conf.get_child_list(u'monitoring_collectors'):
        dn=el[u'DN']
        if dn is None:
            raise RuntimeError,"DN not defined for monitoring collector %s"%el[u'node']
        if not (dn in collector_dns): #skip duplicates
            collector_dns.append(dn)
            gridmap_dict.add(dn,'fcollector%i'%len(collector_dns))

    # TODO: We should also have a Factory DN, for ease of debugging
    #       None available now, but we should add it


#####################
# Simply copy a file
def copy_file(infile,outfile):
    try:
        shutil.copy2(infile,outfile)
    except IOError, e:
        raise RuntimeError, "Error copying %s in %s: %s"%(infile,outfile,e)
 

###############################################
# Validate CONDOR_OS CONDOR_ARCH CONDOR_VERSION

def validate_condor_tarball_attrs(conf):
    valid_tarballs = get_valid_condor_tarballs(conf.get_child_list(u'condor_tarballs'))

    common_version = None
    common_os = None
    common_arch = None
    
    for attr in conf.get_child_list(u'attrs'):
        if attr[u'name'] == u'CONDOR_VERSION':
            common_version = attr[u'value']
        elif attr[u'name'] == u'CONDOR_OS':
            common_os = attr[u'value']
        elif attr[u'name'] == u'CONDOR_ARCH':
            common_arch = attr[u'value']
        if common_version is not None and common_os is not None and common_arch is not None:
            break

    if common_version is None:
        common_version = "default"
    if common_os is None:
        common_os = "default"
    if common_arch is None:
        common_arch = "default"

    # Check the configuration for every entry
    for entry in conf.get_child_list(u'entries'):
        my_version = None
        my_os = None
        my_arch = None
        match_found = False        

        for attr in entry.get_child_list(u'attrs'):
            if attr[u'name'] == u'CONDOR_VERSION':
                my_version = attr[u'value']
            elif attr[u'name'] == u'CONDOR_OS':
                my_os = attr[u'value']
            elif attr[u'name'] == u'CONDOR_ARCH':
                my_arch = attr[u'value']
            if my_version is not None and my_os is not None and my_arch is not None:
                break

        if my_version is None:
            my_version = common_version
        if my_os is None:
            my_os = common_os
        if my_arch is None:
            my_arch = common_arch

        # If either os or arch is auto, handle is carefully
        if ((my_os == "auto") and (my_arch == "auto")):
            for tar in valid_tarballs:
                if (tar['version'] == my_version):
                    match_found = True
                    break
        elif (my_os == "auto"):
            for tar in valid_tarballs:
                if ((tar['version'] == my_version) and (tar['arch'] == my_arch)):
                    match_found = True
                    break
        elif (my_arch == "auto"):
            for tar in valid_tarballs:
                if ((tar['version'] == my_version) and (tar['os'] == my_os)):
                    match_found = True
                    break
        else:
            tarball = { 'version': my_version, 
                        'os'     : my_os, 
                        'arch'   : my_arch
                      }
            if tarball in valid_tarballs:
                match_found = True

        if match_found == False:
            raise RuntimeError, "Condor (version=%s, os=%s, arch=%s) for entry %s could not be resolved from <glidein><condor_tarballs>...</condor_tarballs></glidein> configuration." % (my_version, my_os, my_arch, entry[u'name'])



####################################################
# Extract valid CONDOR_OS CONDOR_ARCH CONDOR_VERSION

def old_get_valid_condor_tarballs(params):
    valid_tarballs = []

    for t in params.condor_tarballs:
        tarball = { 'version': t['version'],
                    'os'     : t['os'],
                    'arch'   : t['arch']
                  }
        valid_tarballs.append(tarball)
    return valid_tarballs


def get_valid_condor_tarballs(condor_tarballs):
    valid_tarballs = []
    tarball_matrix = []

    for tar in condor_tarballs:
        # Each condor_tarball entry is a comma-separated list of possible
        # version, os, arch this tarball can be used
        version = tar['version'].split(',')
        os = tar['os'].split(',')
        arch = tar['arch'].split(',')

        # Generate the combinations (version x os x arch)
        matrix = list(itertools_product(version, os, arch))

        for tup in matrix:
            tarball = { 'version': tup[0].strip(),
                        'os'     : tup[1].strip(),
                        'arch'   : tup[2].strip()
                      }
            valid_tarballs.append(tarball)
    return valid_tarballs


def itertools_product(*args, **kwds):
    """
    itertools.product() from Python 2.6
    """

    pools = map(tuple, args) * kwds.get('repeat', 1)
    result = [[]]
    for pool in pools:
        result = [x+[y] for x in result for y in pool]
    for prod in result:
        yield tuple(prod)

#####################################################
# Returns a string usable for GLIDEIN_Factory_Collector
# Returns None if there are no collectors defined
def calc_monitoring_collectors_string(collectors):
    collector_nodes = {}
    monitoring_collectors = []

    for el in collectors:
        if not collector_nodes.has_key(el[u'group']):
            collector_nodes[el[u'group']] = {'primary': [], 'secondary': []}
        if eval(el[u'secondary']):
            cWDictFile.validate_node(el[u'node'],allow_prange=True)
            collector_nodes[el[u'group']]['secondary'].append(el[u'node'])
        else:
            cWDictFile.validate_node(el[u'node'])
            collector_nodes[el[u'group']]['primary'].append(el[u'node'])

    for group in collector_nodes.keys():
        if len(collector_nodes[group]['secondary']) > 0:
            monitoring_collectors.append(string.join(collector_nodes[group]['secondary'], ","))
        else:
            monitoring_collectors.append(string.join(collector_nodes[group]['primary'], ","))

    if len(monitoring_collectors)==0:
        return None
    else:
        return string.join(monitoring_collectors, ";")

# Returns a string listing the primary monitoring collectors
# Returns None if there are no collectors defined
def calc_primary_monitoring_collectors(collectors):
    collector_nodes = {}

    for el in collectors:
        if not eval(el[u'secondary']):
            # only consider the primary collectors
            cWDictFile.validate_node(el[u'node'])
            # we only expect one per group
            if collector_nodes.has_key(el[u'group']):
                raise RuntimeError, "Duplicate primary monitoring collector found for group %s"%el[u'group']
            collector_nodes[el[u'group']]=el[u'node']
    
    if len(collector_nodes)==0:
        return None
    else:
        return string.join(collector_nodes.values(), ",")

