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
    def __init__(self,params,workdir_name):
        cgWDictFile.glideinMainDicts.__init__(self,params.submit_dir,params.stage_dir,workdir_name,
                                              params.log_dir,
                                              params.client_log_dirs,params.client_proxies_dirs)
        self.monitor_dir=params.monitor_dir
        self.add_dir_obj(cWDictFile.monitorWLinkDirSupport(self.monitor_dir,self.work_dir))
        self.monitor_jslibs_dir=os.path.join(self.monitor_dir,'jslibs')
        self.add_dir_obj(cWDictFile.simpleDirSupport(self.monitor_jslibs_dir,"monitor"))
        self.monitor_images_dir=os.path.join(self.monitor_dir,'images')
        self.add_dir_obj(cWDictFile.simpleDirSupport(self.monitor_images_dir,"monitor"))
        self.params=params
        self.active_sub_list=[]
        self.monitor_jslibs=[]
        self.monitor_images=[]
        self.monitor_htmls=[]

    def populate(self,params=None):
        if params is None:
            params=self.params

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
            self.dicts['file_list'].add_from_file(file_name,(cWConsts.insert_timestr(file_name),"regular","TRUE",'FALSE'),os.path.join(params.src_dir,file_name))
        self.dicts['description'].add("condor_config","condor_config")
        self.dicts['description'].add("condor_config.multi_schedd.include","condor_config_multi_include")
        self.dicts['description'].add("condor_config.dedicated_starter.include","condor_config_main_include")
        self.dicts['description'].add("condor_config.monitor.include","condor_config_monitor_include")
        self.dicts['description'].add("condor_config.check.include","condor_config_check_include")
        self.dicts['vars'].load(params.src_dir,'condor_vars.lst',change_self=False,set_not_changed=False)

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
            self.dicts['file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        #load condor tarballs
        # only one will be downloaded in the end... based on what condor_platform_select.sh decides
        for condor_idx in range(len(params.condor_tarballs)):
            condor_el=params.condor_tarballs[condor_idx]

            # condor_el now is a combination of csv version+os+arch
            # Get list of valid tarballs for this condor_el
            # Register the tarball, but make download conditional to cond_name

            condor_el_valid_tarballs = get_valid_condor_tarballs([condor_el])
            condor_fname = cWConsts.insert_timestr(cgWConsts.CONDOR_FILE % condor_idx)
            condor_tarfile = ""
            condor_fd = None

            if condor_el.tar_file is not None:
                # Condor tarball available. Just add it to the list of tarballs
                # with every possible condor_platform string
                condor_tarfile = condor_el.tar_file
            else:
                # Create a new tarball as usual
                condor_fd = cgWCreate.create_condor_tar_fd(condor_el.base_dir)
                condor_tarfile = os.path.join(self.dicts['file_list'].dir,
                                              condor_fname)
                # insert the newly created tarball fname back into the config
                params.subparams.data['condor_tarballs'][condor_idx]['tar_file'] = condor_tarfile

            for tar in condor_el_valid_tarballs:
                condor_platform = "%s-%s-%s" % (tar['version'], tar['os'],
                                                tar['arch'])
                cond_name = "CONDOR_PLATFORM_%s" % condor_platform
                condor_platform_fname = cgWConsts.CONDOR_FILE % condor_platform

                if condor_fd is None:
                    # tar file exists. Just use it
                    self.dicts['file_list'].add_from_file(
                        condor_platform_fname, (condor_fname,
                                                "untar", cond_name,
                                                cgWConsts.CONDOR_ATTR),
                        condor_el.tar_file)
                else:
                    # This is addition of new tarfile
                    # Need to rewind fd everytime
                    condor_fd.seek(0)
                    self.dicts['file_list'].add_from_fd(
                        condor_platform_fname,
                        (condor_fname,"untar",cond_name,cgWConsts.CONDOR_ATTR),
                        condor_fd)

                self.dicts['untar_cfg'].add(condor_platform_fname,
                                            cgWConsts.CONDOR_DIR)
                # Add cond_name in the config, so that it is known 
                # But leave it disabled by default
                self.dicts['consts'].add(cond_name, "0",
                                         allow_overwrite=False)
            if condor_fd is not None:
                condor_fd.close()

        #
        # Note:
        #  We expect the collector info to be coming in as parameter
        #  as FE consts file is not available at this time
        #

        # add the basic standard params
        self.dicts['params'].add("GLIDEIN_Collector",'Fake')

        # add the factory monitoring collector parameter, if any collectors are defined
        # this is purely a factory thing
        factory_monitoring_collector=calc_monitoring_collectors_string(params.monitoring_collectors)
        if factory_monitoring_collector is not None:
            self.dicts['params'].add('GLIDEIN_Factory_Collector',str(factory_monitoring_collector))
        populate_gridmap(params,self.dicts['gridmap'])
        
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
            self.dicts['file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        # make sure condor_startup does not get executed ahead of time under normal circumstances
        # but must be loaded early, as it also works as a reporting script in case of error
        self.dicts['description'].add(cgWConsts.CONDOR_STARTUP_FILE,"last_script")

        #
        # At this point in the glideins, condor_advertize should be able to talk to the FE collector
        #

        # put user files in stage
        for file in params.files:
            add_file_unparsed(file,self.dicts)

        # put user attributes into config files
        for attr_name in params.attrs.keys():
            add_attr_unparsed(attr_name, params,self.dicts,"main")

        # add additional system scripts
        for script_name in after_file_list_scripts:
            self.dicts['after_file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        # populate complex files
        populate_factory_descript(self.work_dir,self.dicts['glidein'],self.active_sub_list,params)
        populate_frontend_descript(self.dicts['frontend_descript'],params)


        # populate the monitor files
        javascriptrrd_dir = params.monitor.javascriptRRD_dir
        for mfarr in ((params.src_dir,'factory_support.js'),
                      (javascriptrrd_dir,'javascriptrrd.wlibs.js')):
            mfdir,mfname=mfarr
            parent_dir = self.find_parent_dir(mfdir,mfname)
            mfobj=cWDictFile.SimpleFile(parent_dir,mfname)
            mfobj.load()
            self.monitor_jslibs.append(mfobj)

        for mfarr in ((params.src_dir,'factoryRRDBrowse.html'),
                      (params.src_dir,'factoryRRDEntryMatrix.html'),
                      (params.src_dir,'factoryStatus.html'),
                      (params.src_dir,'factoryLogStatus.html'),
                      (params.src_dir,'factoryCompletedStats.html'),
                      (params.src_dir,'factoryStatusNow.html'),
                      (params.src_dir,'factoryEntryStatusNow.html')):
            mfdir,mfname=mfarr
            mfobj=cWDictFile.SimpleFile(mfdir,mfname)
            mfobj.load()
            self.monitor_htmls.append(mfobj)            
        
        # add the index page and its images
        mfobj=cWDictFile.SimpleFile(params.src_dir + '/factory/', 'index.html')
        mfobj.load()
        self.monitor_htmls.append(mfobj)
        for imgfile in ('factoryCompletedStats.png',
                        'factoryEntryStatusNow.png',
                        'factoryLogStatus.png',
                        'factoryRRDBrowse.png',
                        'factoryRRDEntryMatrix.png',
                        'factoryStatus.png',
                        'factoryStatusNow.png'):
            mfobj=cWDictFile.SimpleFile(params.src_dir + '/factory/images/', imgfile)
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
        self.save_monitor_config(self.work_dir,self.dicts['glidein'],self.params)


    ########################################
    # INTERNAL
    ########################################
    
    def save_pub_key(self):
        if self.params.security.pub_key=='None':
            pass # nothing to do
        elif self.params.security.pub_key=='RSA':
            rsa_key_fname=os.path.join(self.work_dir,cgWConsts.RSA_KEY)

            if not os.path.isfile(rsa_key_fname):
                # create the key only once

                # touch the file with correct flags first
                # I have no way to do it in  RSAKey class
                fd=os.open(rsa_key_fname,os.O_CREAT,0600)
                os.close(fd)
                
                key_obj=pubCrypto.RSAKey()
                key_obj.new(int(self.params.security.key_length))
                key_obj.save(rsa_key_fname)            
        else:
            raise RuntimeError,"Invalid value for security.pub_key(%s), must be either None or RSA"%self.params.security.pub_key

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
    def save_monitor_config(self, work_dir, glidein_dict, params):
        monitor_config_file = os.path.join(params.monitor_dir, cgWConsts.MONITOR_CONFIG_FILE)
        monitor_config_line = []
        
        monitor_config_fd = open(monitor_config_file,'w')
        monitor_config_line.append("<monitor_config>")
        monitor_config_line.append("  <entries>")
        try:
            try:
                for sub in params.entries.keys():
                    if eval(params.entries[sub].enabled,{},{}):
                        monitor_config_line.append("    <entry name=\"%s\">" % sub)
                        monitor_config_line.append("      <monitorgroups>")                
                        for group in params.entries[sub].monitorgroups:
                            monitor_config_line.append("        <monitorgroup group_name=\"%s\">" % group['group_name'])
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
    def __init__(self,params,sub_name,
                 summary_signature,workdir_name):
        cgWDictFile.glideinEntryDicts.__init__(self,params.submit_dir,params.stage_dir,sub_name,summary_signature,workdir_name,
                                               params.log_dir,params.client_log_dirs,params.client_proxies_dirs)
                                               
        self.monitor_dir=cgWConsts.get_entry_monitor_dir(params.monitor_dir,sub_name)
        self.add_dir_obj(cWDictFile.monitorWLinkDirSupport(self.monitor_dir,self.work_dir))
        self.params=params

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
        
    
    def populate(self,params=None):
        if params is None:
            params=self.params
        sub_params=params.entries[self.sub_name]

        # put default files in place first
        self.dicts['file_list'].add_placeholder(cWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball

        # follow by the blacklist file
        file_name=cWConsts.BLACKLIST_FILE
        self.dicts['file_list'].add_from_file(file_name,(file_name,"nocache","TRUE",'BLACKLIST_FILE'),os.path.join(params.src_dir,file_name))

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh',"check_blacklist.sh"):
            self.dicts['file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        #load system files
        self.dicts['vars'].load(params.src_dir,'condor_vars.lst.entry',change_self=False,set_not_changed=False)
        
        
        # put user files in stage
        for user_file in sub_params.files:
            add_file_unparsed(user_file,self.dicts)

        # Add attribute for voms

        # put user attributes into config files
        for attr_name in sub_params.attrs.keys():
            add_attr_unparsed(attr_name, sub_params,self.dicts,self.sub_name)

        # put standard attributes into config file
        # override anything the user set
        for dtype in ('attrs','consts'):
            self.dicts[dtype].add("GLIDEIN_Gatekeeper",sub_params.gatekeeper,allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_GridType",sub_params.gridtype,allow_overwrite=True)
            # MERGENOTE:
            # GLIDEIN_REQUIRE_VOMS publishes an attribute so that users without VOMS proxies
            #   can avoid sites that require VOMS proxies (using the normal Condor Requirements
            #   string. 
            self.dicts[dtype].add("GLIDEIN_REQUIRE_VOMS",sub_params.config.restrictions.require_voms_proxy,allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_REQUIRE_GLEXEC_USE",sub_params.config.restrictions.require_glidein_glexec_use,allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_TrustDomain",sub_params.trust_domain,allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_SupportedAuthenticationMethod",sub_params.auth_method,allow_overwrite=True)
            if sub_params.rsl is not None:
                self.dicts[dtype].add('GLIDEIN_GlobusRSL',sub_params.rsl,allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_SlotsLayout", sub_params.config.submit.slots_layout, allow_overwrite=True)


        self.dicts['vars'].add_extended("GLIDEIN_REQUIRE_VOMS","boolean",sub_params.config.restrictions.require_voms_proxy,None,False,True,True)
        self.dicts['vars'].add_extended("GLIDEIN_REQUIRE_GLEXEC_USE","boolean",sub_params.config.restrictions.require_glidein_glexec_use,None,False,True,True)

        # populate infosys
        for infosys_ref in sub_params.infosys_refs:
            self.dicts['infosys'].add_extended(infosys_ref['type'],infosys_ref['server'],infosys_ref['ref'],allow_overwrite=True)

        # populate monitorgroups
        for monitorgroup in sub_params.monitorgroups:
            self.dicts['mongroup'].add_extended(monitorgroup['group_name'],allow_overwrite=True)

        # populate complex files
        populate_job_descript(self.work_dir,self.dicts['job_descript'],
                              self.sub_name,sub_params)

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
        self.dicts['condor_jdl'].populate(cgWConsts.STARTUP_FILE, self.sub_name, params, sub_params)

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
    def __init__(self,params,
                 sub_list=None): # if None, get it from params
        if sub_list is None:
            sub_list=params.entries.keys()

        self.params=params
        cgWDictFile.glideinDicts.__init__(self,params.submit_dir,params.stage_dir,params.log_dir,params.client_log_dirs,params.client_proxies_dirs,sub_list)

        self.monitor_dir=params.monitor_dir
        self.active_sub_list=[]
        return

    def populate(self,params=None): # will update params (or self.params)
        if params is None:
            params=self.params
        
        self.main_dicts.populate(params)
        self.active_sub_list=self.main_dicts.active_sub_list

        self.local_populate(params)
        for sub_name in self.sub_list:
            self.sub_dicts[sub_name].populate(params)

        validate_condor_tarball_attrs(params)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            print "WARNING: monitor base_dir has changed, stats may be lost: '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cgWDictFile.glideinDicts.reuse(self,other)

    ###########
    # PRIVATE
    ###########

    def local_populate(self,params):
        # make sure all the schedds are defined
        # if not, define them, in place, so thet it get recorded
        global_schedd_names=string.split(params.schedd_name,',')

        # we will need to know how loaded are the schedds
        # so we properly load balance
        global_schedd_count={}
        for n in global_schedd_names:
            global_schedd_count[n]=0
        for sub_name in self.sub_list:
            if params.entries[sub_name].schedd_name is not None:
                try:
                    global_schedd_count[params.entries[sub_name].schedd_name]+=1
                except KeyError:
                    raise UnconfiguredScheddError(params.entries[sub_name].schedd_name)

        # now actually check the schedds
        for sub_name in self.sub_list:
            if params.entries[sub_name].schedd_name is None:
                # now find the least used one
                # NOTE: The self.sortit method should be removed, when SL4 and
                #       python 2.3.4 are no longer supported
                if sys.version_info < (2,4): # python 2.3.4 /SL4
                    gs = self.sortit(global_schedd_count)
                else:  # python 2.4+ / SL5
                    gs = global_schedd_count.keys()
                    gs.sort(key=global_schedd_count.__getitem__)
                min_schedd=gs[0]
                params.subparams.data['entries'][sub_name]['schedd_name']=min_schedd
                global_schedd_count[min_schedd]+=1
        return
        
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
        return glideinMainDicts(self.params,self.workdir_name)

    def new_SubDicts(self,sub_name):
        return glideinEntryDicts(self.params,sub_name,
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
    absfname=user_file.absfname
    if absfname is None:
        raise RuntimeError, "Found a file element without an absname: %s"%user_file
    
    relfname=user_file.relfname
    if relfname is None:
        relfname=os.path.basename(absfname) # defualt is the final part of absfname
    if len(relfname)<1:
        raise RuntimeError, "Found a file element with an empty relfname: %s"%user_file

    is_const=eval(user_file.const,{},{})
    is_executable=eval(user_file.executable,{},{})
    is_wrapper=eval(user_file.wrapper,{},{})
    do_untar=eval(user_file.untar,{},{})

    file_list_idx='file_list'
    if user_file.has_key('after_entry'):
        if eval(user_file.after_entry,{},{}):
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

        wnsubdir=user_file.untar_options.dir
        if wnsubdir is None:
            wnsubdir=string.split(relfname,'.',1)[0] # deafult is relfname up to the first .

        config_out=user_file.untar_options.absdir_outattr
        if config_out is None:
            config_out="FALSE"
        cond_attr=user_file.untar_options.cond_attr


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
def add_attr_unparsed(attr_name,params,dicts,description):
    try:
        add_attr_unparsed_real(attr_name,params,dicts)
    except RuntimeError,e:
        raise RuntimeError, "Error parsing attr %s[%s]: %s"%(description,attr_name,str(e))

def add_attr_unparsed_real(attr_name,params,dicts):
    attr_obj=params.attrs[attr_name]
    
    if attr_obj.value is None:
        raise RuntimeError, "Attribute '%s' does not have a value: %s"%(attr_name,attr_obj)
    
    do_publish=eval(attr_obj.publish,{},{})
    is_parameter=eval(attr_obj.parameter,{},{})
    is_const=eval(attr_obj.const,{},{})
    attr_val=params.extract_attr_val(attr_obj)
    
    if do_publish: # publish in factory ClassAd
        if is_parameter: # but also push to glidein
            if is_const:
                dicts['attrs'].add(attr_name,attr_val)
                dicts['consts'].add(attr_name,attr_val)
            else:
                dicts['params'].add(attr_name,attr_val)
        else: # only publish
            if (not is_const):
                raise RuntimeError, "Published attribute '%s' must be either a parameter or constant: %s"%(attr_name,attr_obj)
            
            dicts['attrs'].add(attr_name,attr_val)
            dicts['consts'].add(attr_name,attr_val)
    else: # do not publish, only to glidein
        if is_parameter:
            if is_const:
                dicts['consts'].add(attr_name,attr_val)
            else:
                raise RuntimeError, "Parameter attributes '%s' must be either a published or constant: %s"%(attr_name,attr_obj)
        else:
            raise RuntimeError, "Attributes '%s' must be either a published or parameters: %s"%(attr_name,attr_obj) 

    do_glidein_publish=eval(attr_obj.glidein_publish,{},{})
    do_job_publish=eval(attr_obj.job_publish,{},{})

    if do_glidein_publish or do_job_publish:
            # need to add a line only if will be published
            if dicts['vars'].has_key(attr_name):
                # already in the var file, check if compatible
                attr_var_el=dicts['vars'][attr_name]
                attr_var_type=attr_var_el[0]
                if (((attr_obj.type=="int") and (attr_var_type!='I')) or
                    ((attr_obj.type=="expr") and (attr_var_type=='I')) or
                    ((attr_obj.type=="string") and (attr_var_type=='I'))):
                    raise RuntimeError, "Types not compatible (%s,%s)"%(attr_obj.type,attr_var_type)
                attr_var_export=attr_var_el[4]
                if do_glidein_publish and (attr_var_export=='N'):
                    raise RuntimeError, "Cannot force glidein publishing"
                attr_var_job_publish=attr_var_el[5]
                if do_job_publish and (attr_var_job_publish=='-'):
                    raise RuntimeError, "Cannot force job publishing"
            else:
                dicts['vars'].add_extended(attr_name,attr_obj.type,None,None,False,do_glidein_publish,do_job_publish)

###################################
# Create the glidein descript file
def populate_factory_descript(work_dir,
                              glidein_dict,active_sub_list,        # will be modified
                              params):
        
        down_fname=os.path.join(work_dir,'glideinWMS.downtimes')

        glidein_dict.add('FactoryCollector',params.factory_collector)
        glidein_dict.add('FactoryName',params.factory_name)
        glidein_dict.add('GlideinName',params.glidein_name)
        glidein_dict.add('WebURL',params.web_url)
        glidein_dict.add('PubKeyType',params.security.pub_key)
        glidein_dict.add('OldPubKeyGraceTime',params.security.reuse_oldkey_onstartup_gracetime)
        glidein_dict.add('MonitorUpdateThreadCount',params.monitor.update_thread_count)
        glidein_dict.add('RemoveOldCredFreq', params.security.remove_old_cred_freq)
        glidein_dict.add('RemoveOldCredAge', params.security.remove_old_cred_age)
        del active_sub_list[:] # clean

        for sub in params.entries.keys():
            if eval(params.entries[sub].enabled,{},{}):
                active_sub_list.append(sub)

        glidein_dict.add('Entries',string.join(active_sub_list,','))
        glidein_dict.add('AdvertiseWithTCP',params.advertise_with_tcp)
        glidein_dict.add('AdvertiseWithMultiple',params.advertise_with_multiple)
        glidein_dict.add('AdvertiseWithTCP',params.advertise_with_tcp)
        glidein_dict.add('AdvertiseWithMultiple',params.advertise_with_multiple)
        glidein_dict.add('LoopDelay',params.loop_delay)
        glidein_dict.add('AdvertiseDelay',params.advertise_delay)
        glidein_dict.add('RestartAttempts',params.restart_attempts)
        glidein_dict.add('RestartInterval',params.restart_interval)
        glidein_dict.add('AdvertiseDelay',params.advertise_delay)
        glidein_dict.add('EntryParallelWorkers',params.entry_parallel_workers)
        glidein_dict.add('LogDir',params.log_dir)
        glidein_dict.add('ClientLogBaseDir',params.submit.base_client_log_dir)
        glidein_dict.add('ClientProxiesBaseDir',params.submit.base_client_proxies_dir)
        glidein_dict.add('DowntimesFile',down_fname)
        
        glidein_dict.add('MonitorDisplayText',params.monitor_footer.display_txt)
        glidein_dict.add('MonitorLink',params.monitor_footer.href_link)
        
        monitoring_collectors=calc_primary_monitoring_collectors(params.monitoring_collectors)
        if monitoring_collectors is not None:
            glidein_dict.add('PrimaryMonitoringCollectors',str(monitoring_collectors))

        for lel in (("job_logs",'JobLog'),("summary_logs",'SummaryLog'),("condor_logs",'CondorLog')):
            param_lname,str_lname=lel
            for tel in (("max_days",'MaxDays'),("min_days",'MinDays'),("max_mbytes",'MaxMBs')):
                param_tname,str_tname=tel
                glidein_dict.add('%sRetention%s'%(str_lname,str_tname),params.log_retention[param_lname][param_tname])

        glidein_dict.add('ProcessLogs', str(params.log_retention['process_logs']))

#######################
def populate_job_descript(work_dir, job_descript_dict, 
                          sub_name, sub_params):
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

    job_descript_dict.add('EntryName', sub_name)
    job_descript_dict.add('GridType', sub_params.gridtype)
    job_descript_dict.add('Gatekeeper', sub_params.gatekeeper)
    job_descript_dict.add('AuthMethod', sub_params.auth_method)
    job_descript_dict.add('TrustDomain', sub_params.trust_domain)
    if sub_params.vm_id is not None:
        job_descript_dict.add('EntryVMId', sub_params.vm_id)
    if sub_params.vm_type is not None:
        job_descript_dict.add('EntryVMType', sub_params.vm_type)
    if sub_params.rsl is not None:
        job_descript_dict.add('GlobusRSL', sub_params.rsl)
    job_descript_dict.add('Schedd', sub_params.schedd_name)
    job_descript_dict.add('StartupDir', sub_params.work_dir)
    if sub_params.proxy_url is not None:
        job_descript_dict.add('ProxyURL', sub_params.proxy_url)
    job_descript_dict.add('Verbosity', sub_params.verbosity)
    job_descript_dict.add('DowntimesFile', down_fname)
    job_descript_dict.add('PerEntryMaxGlideins', sub_params.config.max_jobs.per_entry.glideins)
    job_descript_dict.add('PerEntryMaxIdle', sub_params.config.max_jobs.per_entry.idle)
    job_descript_dict.add('PerEntryMaxHeld', sub_params.config.max_jobs.per_entry.held)
    job_descript_dict.add('DefaultPerFrontendMaxGlideins', sub_params.config.max_jobs.default_per_frontend.glideins)
    job_descript_dict.add('DefaultPerFrontendMaxIdle', sub_params.config.max_jobs.default_per_frontend.idle)
    job_descript_dict.add('DefaultPerFrontendMaxHeld', sub_params.config.max_jobs.default_per_frontend.held)
    job_descript_dict.add('MaxSubmitRate', sub_params.config.submit.max_per_cycle)
    job_descript_dict.add('SubmitCluster', sub_params.config.submit.cluster_size)
    job_descript_dict.add('SubmitSlotsLayout', sub_params.config.submit.slots_layout)
    job_descript_dict.add('SubmitSleep', sub_params.config.submit.sleep)
    job_descript_dict.add('MaxRemoveRate', sub_params.config.remove.max_per_cycle)
    job_descript_dict.add('RemoveSleep', sub_params.config.remove.sleep)
    job_descript_dict.add('MaxReleaseRate', sub_params.config.release.max_per_cycle)
    job_descript_dict.add('ReleaseSleep', sub_params.config.release.sleep)
    job_descript_dict.add('RequireVomsProxy',sub_params.config.restrictions.require_voms_proxy)
    job_descript_dict.add('RequireGlideinGlexecUse',sub_params.config.restrictions.require_glidein_glexec_use)
   
    # Add the frontend specific job limits to the job.descript file
    max_held_frontend = ""
    max_idle_frontend = ""
    max_glideins_frontend = ""
    for frontend_name in sub_params.config.max_jobs.per_frontends.keys():
        el = sub_params.config.max_jobs.per_frontends[frontend_name]
        max_held_frontend += frontend_name + ";" + el.held + ","
        max_idle_frontend += frontend_name + ";" + el.idle + ","
        max_glideins_frontend += frontend_name + ";" + el.glideins + ","
    job_descript_dict.add("PerFrontendMaxGlideins", max_glideins_frontend[:-1])
    job_descript_dict.add("PerFrontendMaxHeld", max_held_frontend[:-1])
    job_descript_dict.add("PerFrontendMaxIdle", max_idle_frontend[:-1])
    
    #  If the configuration has a non-empty frontend_allowlist
    #  then create a white list and add all the frontends:security_classes
    #  to it.
    white_mode = "Off"
    allowed_vos = ""
    for X in sub_params.allow_frontends.keys():
        white_mode = "On"
        allowed_vos = allowed_vos + X + ":" + sub_params.allow_frontends[X].security_class + ","
    job_descript_dict.add("WhitelistMode", white_mode)
    job_descript_dict.add("AllowedVOs", allowed_vos[:-1])


###################################
# Create the frontend descript file
def populate_frontend_descript(frontend_dict,     # will be modified
                               params):
    for fe in params.security.frontends.keys():
        fe_el=params.security.frontends[fe]

        ident=fe_el['identity']
        if ident is None:
            raise RuntimeError, 'security.frontends[%s][identity] not defined, but required'%fe

        maps={}
        for sc in fe_el['security_classes'].keys():
            sc_el=fe_el['security_classes'][sc]
            username=sc_el['username']
            if username is None:
                raise RuntimeError, 'security.frontends[%s].security_classes[%s][username] not defined, but required'%(fe,sc)
            maps[sc]=username
        
        frontend_dict.add(fe,{'ident':ident,'usermap':maps})



#####################################################
# Populate gridmap to be used by the glideins
def populate_gridmap(params,gridmap_dict):
    collector_dns=[]
    for el in params.monitoring_collectors:
        dn=el.DN
        if dn is None:
            raise RuntimeError,"DN not defined for monitoring collector %s"%el.node
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

def validate_condor_tarball_attrs(params):
    valid_tarballs = get_valid_condor_tarballs(params.condor_tarballs)

    common_version = "default"
    common_os = "default"
    common_arch = "default"
    if (params.attrs.has_key('CONDOR_VERSION')):
        common_version = params.attrs['CONDOR_VERSION']['value']
    if (params.attrs.has_key('CONDOR_OS')):
        common_os = params.attrs['CONDOR_OS']['value']
    if (params.attrs.has_key('CONDOR_ARCH')):
        common_arch = params.attrs['CONDOR_ARCH']['value']

    # Check the configuration for every entry
    for entry in params.entries.keys():
        my_version = common_version
        my_os = common_os
        my_arch = common_arch
        match_found = False        

        if (params.entries[entry].attrs.has_key('CONDOR_VERSION')):
            my_version = params.entries[entry].attrs['CONDOR_VERSION']['value']
        if (params.entries[entry].attrs.has_key('CONDOR_OS')):
            my_os = params.entries[entry].attrs['CONDOR_OS']['value']
        if (params.entries[entry].attrs.has_key('CONDOR_ARCH')):
            my_arch = params.entries[entry].attrs['CONDOR_ARCH']['value']

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
            raise RuntimeError, "Condor (version=%s, os=%s, arch=%s) for entry %s could not be resolved from <glidein><condor_tarballs>...</condor_tarballs></glidein> configuration." % (my_version, my_os, my_arch, entry)



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
        if not collector_nodes.has_key(el.group):
            collector_nodes[el.group] = {'primary': [], 'secondary': []}
        if eval(el.secondary):
            cWDictFile.validate_node(el.node,allow_prange=True)
            collector_nodes[el.group]['secondary'].append(el.node)
        else:
            cWDictFile.validate_node(el.node)
            collector_nodes[el.group]['primary'].append(el.node)

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
        if not eval(el.secondary):
            # only consider the primary collectors
            cWDictFile.validate_node(el.node)
            # we only expect one per group
            if collector_nodes.has_key(el.group):
                raise RuntimeError, "Duplicate primary monitoring collector found for group %s"%el.group
            collector_nodes[el.group]=el.node
    
    if len(collector_nodes)==0:
        return None
    else:
        return string.join(collector_nodes.values(), ",")

