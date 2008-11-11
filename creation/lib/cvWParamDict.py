#######################################################
#
# VO Frontend creation module
# Classes and functions needed to handle dictionary files
# created out of the parameter object
#
#######################################################

import os,os.path,shutil,string
import cWParams
import cvWDictFile
import cgWCreate
import cvWConsts,cWConsts

# internal, can only be used for multiple inheritance
class frontendCommonDicts:
    def create_pd_dirs(self):
        try:
            os.mkdir(self.monitor_dir)
        except OSError,e:
            cvWDictFile.frontendCommonDicts.delete_dirs(self)
            raise RuntimeError,"Failed to create dir: %s"%e

        try:
            os.symlink(self.monitor_dir,os.path.join(self.submit_dir,"monitor"))
        except OSError, e:
            cvWDictFile.frontendCommonDicts.delete_dirs(self)
            shutil.rmtree(self.monitor_dir)
            raise RuntimeError,"Failed to create symlink %s: %s"%(os.path.join(self.submit_dir,"monitor"),e)

    def delete_pd_dirs(self):
        shutil.rmtree(self.monitor_dir)

class frontendMainDicts(frontendCommonDicts,cvWDictFile.frontendMainDicts):
    def __init__(self,params):
        cvWDictFile.frontendMainDicts.__init__(self,params.submit_dir,params.stage_dir)
        self.monitor_dir=params.monitor_dir
        self.params=params

    def create_dirs(self):
        cvWDictFile.frontendMainDicts.create_dirs(self)
        self.create_pd_dirs()

    def delete_dirs(self):
        cvWDictFile.frontendMainDicts.delete_dirs(self)
        self.delete_pd_dirs()

    def populate(self,params=None):
        if params==None:
            params=self.params

        # put default files in place first
        self.dicts['file_list'].add_placeholder(cWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cgWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball
        self.dicts['file_list'].add_placeholder(cWConsts.GRIDMAP_FILE,allow_overwrite=True) # this one must be loaded before setup_x509.sh
        
        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh','setup_x509.sh'):
            self.dicts['file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        #load condor tarball
        if params.condor.tar_file!=None: # condor tarball available
            self.dicts['file_list'].add_from_file(cgWConsts.CONDOR_FILE,(cWConsts.insert_timestr(cgWConsts.CONDOR_FILE),"untar","TRUE",cgWConsts.CONDOR_ATTR),params.condor.tar_file)
        else: # create a new tarball
            condor_fd=cgWCreate.create_condor_tar_fd(params.condor.base_dir)
            condor_fname=cWConsts.insert_timestr(cgWConsts.CONDOR_FILE)
            self.dicts['file_list'].add_from_fd(cgWConsts.CONDOR_FILE,(condor_fname,"untar","TRUE",cgWConsts.CONDOR_ATTR),condor_fd)
            condor_fd.close()
            params.subparams.data['condor']['tar_file']=os.path.join(self.dicts['file_list'].dir,condor_fname)
        self.dicts['untar_cfg'].add(cgWConsts.CONDOR_FILE,cgWConsts.CONDOR_DIR)

        #load system files
        for file_name in ('parse_starterlog.awk', "condor_config", "condor_config.multi_schedd.include", "condor_config.dedicated_starter.include", "condor_config.monitor.include" ):
            self.dicts['file_list'].add_from_file(file_name,(cWConsts.insert_timestr(file_name),"regular","TRUE",'FALSE'),os.path.join(params.src_dir,file_name))
        self.dicts['description'].add("condor_config","condor_config")
        self.dicts['description'].add("condor_config.multi_schedd.include","condor_config_multi_include")
        self.dicts['description'].add("condor_config.dedicated_starter.include","condor_config_main_include")
        self.dicts['description'].add("condor_config.monitor.include","condor_config_monitor_include")
        self.dicts['vars'].load(params.src_dir,'condor_vars.lst',change_self=False,set_not_changed=False)

        # put user files in stage
        for file in params.files:
            add_file_unparsed(file,self.dicts)

        # put user attributes into config files
        for attr_name in params.attrs.keys():
            add_attr_unparsed(attr_name, params.attrs[attr_name],self.dicts,"main")

        if self.dicts['file_list'].is_placeholder(cWConsts.GRIDMAP_FILE): # gridmapfile is optional, so if not loaded, remove the placeholder
            self.dicts['file_list'].remove(cWConsts.GRIDMAP_FILE)

        # add the basic standard params
        self.dicts['params'].add("GLIDEIN_Collector",'Fake')

        # add additional system scripts
        for script_name in ('collector_setup.sh','gcb_setup.sh','glexec_setup.sh'):
            self.dicts['after_file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))
                
        # this must be the last script in the list
        for script_name in (cgWConsts.CONDOR_STARTUP_FILE,):
            self.dicts['file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))
        self.dicts['description'].add(cgWConsts.CONDOR_STARTUP_FILE,"last_script")

        # if a user does not provide a file name, use the default one
        down_fname=params.downtimes.absfname
        if down_fname==None:
            down_fname=os.path.join(self.submit_dir,'factory.downtimes')

        # populate the glidein file
        glidein_dict=self.dicts['glidein']
        glidein_dict.add('FactoryName',params.factory_name)
        glidein_dict.add('GlideinName',params.glidein_name)
        glidein_dict.add('WebURL',params.web_url)
        glidein_dict.add('PubKeyType',params.security.pub_key)
        self.active_group_list=[]
        for group in params.groups.keys():
            if eval(params.groups[group].enabled,{},{}):
                self.active_group_list.append(group)
        glidein_dict.add('Groups',string.join(self.active_group_list,','))
        glidein_dict.add('LoopDelay',params.loop_delay)
        glidein_dict.add('AdvertiseDelay',params.advertise_delay)
        validate_job_proxy_source(params.security.allow_proxy)
        glidein_dict.add('AllowedJobProxySource',params.security.allow_proxy)
        glidein_dict.add('DowntimesFile',down_fname)
        for lel in (("logs",'Log'),("job_logs",'JobLog'),("summary_logs",'SummaryLog'),("condor_logs",'CondorLog')):
            param_lname,str_lname=lel
            for tel in (("max_days",'MaxDays'),("min_days",'MinDays'),("max_mbytes",'MaxMBs')):
                param_tname,str_tname=tel
                glidein_dict.add('%sRetention%s'%(str_lname,str_tname),params.log_retention[param_lname][param_tname])

        for el in (('Factory',params.monitor.factory),('Group',params.monitor.group)):
            prefix=el[0]
            dict=el[1]
            val="Basic,Held"
            if bool(eval(dict.want_split_graphs)):
                val+=",Split"
                # only if split enabled, can the split terminated be enabled
                if bool(eval(dict.want_split_terminated_graphs)):
                    val+=",SplitTerm"
            if bool(eval(dict.want_trend_graphs)):
                val+=",Trend"
            if bool(eval(dict.want_infoage_graphs)):
                val+=",InfoAge"
            glidein_dict.add('%sWantedMonitorGraphs'%prefix,val)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            raise RuntimeError,"Cannot change main monitor base_dir! '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cvWDictFile.frontendMainDicts.reuse(self,other)

    def save(self,set_readonly=True):
        cvWDictFile.frontendMainDicts.save(self,set_readonly)
        if self.params.security.pub_key=='None':
            pass # nothing to do
        elif self.params.security.pub_key=='RSA':
            import pubCrypto
            rsa_key_fname=os.path.join(self.submit_dir,cgWConsts.RSA_KEY)

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

class frontendGroupDicts(frontendCommonDicts,cvWDictFile.frontendGroupDicts):
    def __init__(self,
                 frontend_main_dicts, # must be an instance of frontendMainDicts
                 group_name):
        cvWDictFile.frontendGroupDicts.__init__(self,frontend_main_dicts,group_name)
        self.monitor_dir=cgWConsts.get_group_monitor_dir(frontend_main_dicts.monitor_dir,group_name)
        self.params=frontend_main_dicts.params

    def create_dirs(self):
        cvWDictFile.frontendGroupDicts.create_dirs(self)
        self.create_pd_dirs()

    def delete_dirs(self):
        cvWDictFile.frontendGroupDicts.delete_dirs(self)
        self.delete_pd_dirs()

    def erase(self):
        cvWDictFile.frontendGroupDicts.erase(self)
        self.dicts['condor_jdl']=cgWCreate.GlideinSubmitDictFile(self.submit_dir,cgWConsts.SUBMIT_FILE)
        
    def load(self): #will use frontend_main_dicts data, so it must be loaded first
        cvWDictFile.frontendGroupDicts.load(self)
        self.dicts['condor_jdl'].load()

    def save_final(self,set_readonly=True):
        summary_signature=self.frontend_main_dicts['summary_signature']
        group_stage_dir=cgWConsts.get_group_stage_dir("",self.group_name)
        
        self.dicts['condor_jdl'].finalize(summary_signature['main'][0],summary_signature[group_stage_dir][0],
                                          summary_signature['main'][1],summary_signature[group_stage_dir][1])
        self.dicts['condor_jdl'].save(set_readonly=set_readonly)
        
    
    def populate(self,schedd_name,params=None):
        if params==None:
            params=self.params

        group_params=params.groups[self.group_name]

        # put default files in place first
        self.dicts['file_list'].add_placeholder(cWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cgWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball

        # follow by the blacklist file
        file_name="nodes.blacklist"
        self.dicts['file_list'].add_from_file(file_name,(file_name,"nocache","TRUE",'BLACKLIST_FILE'),os.path.join(params.src_dir,file_name))

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh',"validate_node.sh"):
            self.dicts['file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        #load system files
        self.dicts['vars'].load(params.src_dir,'condor_vars.lst.group',change_self=False,set_not_changed=False)
        
        # put user files in stage
        for file in group_params.files:
            add_file_unparsed(file,self.dicts)

        # put user attributes into config files
        for attr_name in group_params.attrs.keys():
            add_attr_unparsed(attr_name, group_params.attrs[attr_name],self.dicts,self.group_name)

        # put standard attributes into config file
        # override anything the user set
        for dtype in ('attrs','consts'):
            self.dicts[dtype].add("GLIDEIN_Gatekeeper",group_params.gatekeeper,allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_GridType",group_params.gridtype,allow_overwrite=True)
            if group_params.rsl!=None:
                self.dicts[dtype].add('GLIDEIN_GlobusRSL',group_params.rsl,allow_overwrite=True)

        # populate infosys
        for infosys_ref in group_params.infosys_refs:
            self.dicts['infosys'].add_extended(infosys_ref['type'],infosys_ref['server'],infosys_ref['ref'],allow_overwrite=True)

        # populate complex files
        populate_job_descript(self.submit_dir,self.dicts['job_descript'],
                              self.group_name,group_params)

        self.dicts['condor_jdl'].populate(cgWConsts.STARTUP_FILE,
                                          params.factory_name,params.frontend_name,self.group_name,
                                          group_params.gridtype,group_params.gatekeeper,group_params.rsl,
                                          params.web_url,group_params.proxy_url,group_params.work_dir)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            raise RuntimeError,"Cannot change group monitor base_dir! '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cvWDictFile.frontendGroupDicts.reuse(self,other)

        
################################################
#
# This Class contains coth the main and
# the group dicts
#
################################################

class frontendDicts(cvWDictFile.frontendDicts):
    def __init__(self,params,
                 group_list=None): # if None, get it from params
        if group_list==None:
            group_list=params.groups.keys()

        self.params=params
        self.submit_dir=params.submit_dir
        self.stage_dir=params.stage_dir
        self.monitor_dir=params.monitor_dir

        self.main_dicts=frontendMainDicts(params)
        self.group_list=group_list[:]
        self.group_dicts={}
        for group_name in group_list:
            self.group_dicts[group_name]=frontendGroupDicts(self.main_dicts,group_name)
        self.active_group_list=[]
        return

    def populate(self,params=None): # will update params (or self.params)
        if params==None:
            params=self.params
        
        self.main_dicts.populate(params)
        self.active_group_list=self.main_dicts.active_group_list

        # make sure all the schedds are defined
        # if not, define them, in place, so thet it get recorded
        global_schedd_names=string.split(params.schedd_name,',')
        global_schedd_idx=0
        for group_name in self.group_list:
            if params.groups[group_name].schedd_name==None:
                # use one of the global ones if specific not provided
                schedd_name=global_schedd_names[global_schedd_idx%len(global_schedd_names)]
                global_schedd_idx=global_schedd_idx+1
                params.subparams.data['groups'][group_name]['schedd_name']=schedd_name

        for group_name in self.group_list:
            self.group_dicts[group_name].populate(params)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            raise RuntimeError,"Cannot change monitor base_dir! '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cvWDictFile.frontendDicts.reuse(self,other)

    ###########
    # PRIVATE
    ###########

    # return a new group object
    def new_group(self,group_name):
        return frontendGroupDicts(self.main_dicts,group_name)
    
############################################################
#
# P R I V A T E - Do not use
# 
############################################################

#############################################
# Add a user file residing in the stage area
# file as described by Params.file_defaults
def add_file_unparsed(file,dicts):
    absfname=file.absfname
    if absfname==None:
        raise RuntimeError, "Found a file element without an absname: %s"%file
    
    relfname=file.relfname
    if relfname==None:
        relfname=os.path.basename(absfname) # defualt is the final part of absfname
    if len(relfname)<1:
        raise RuntimeError, "Found a file element with an empty relfname: %s"%file

    is_const=eval(file.const,{},{})
    is_executable=eval(file.executable,{},{})
    is_wrapper=eval(file.wrapper,{},{})
    do_untar=eval(file.untar,{},{})

    file_list_idx='file_list'
    if file.has_key('after_group'):
        if eval(file.after_group,{},{}):
            file_list_idx='after_file_list'

    if is_executable: # a script
        if not is_const:
            raise RuntimeError, "A file cannot be executable if it is not constant: %s"%file
    
        if do_untar:
            raise RuntimeError, "A tar file cannot be executable: %s"%file

        if is_wrapper:
            raise RuntimeError, "A wrapper file cannot be executable: %s"%file

        dicts[file_list_idx].add_from_file(relfname,(cWConsts.insert_timestr(relfname),"exec","TRUE",'FALSE'),absfname)
    elif is_wrapper: # a sourceable script for the wrapper
        if not is_const:
            raise RuntimeError, "A file cannot be a wrapper if it is not constant: %s"%file
    
        if do_untar:
            raise RuntimeError, "A tar file cannot be a wrapper: %s"%file

        dicts[file_list_idx].add_from_file(relfname,(cWConsts.insert_timestr(relfname),"wrapper","TRUE",'FALSE'),absfname)
    elif do_untar: # a tarball
        if not is_const:
            raise RuntimeError, "A file cannot be untarred if it is not constant: %s"%file

        wnsubdir=file.untar_options.dir
        if wnsubdir==None:
            wnsubdir=string.split(relfname,'.',1)[0] # deafult is relfname up to the first .

        config_out=file.untar_options.absdir_outattr
        if config_out==None:
            config_out="FALSE"
        cond_attr=file.untar_options.cond_attr


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
def add_attr_unparsed(attr_name,attr_obj,dicts,description):
    try:
        add_attr_unparsed_real(attr_name,attr_obj,dicts)
    except RuntimeError,e:
        raise RuntimeError, "Error parsing attr %s[%s]: %s"%(description,attr_name,str(e))

def add_attr_unparsed_real(attr_name,attr_obj,dicts):
    if attr_obj.value==None:
        raise RuntimeError, "Attribute '%s' does not have a value: %s"%(attr_name,attr_obj)
    
    do_publish=eval(attr_obj.publish,{},{})
    is_parameter=eval(attr_obj.parameter,{},{})
    is_const=eval(attr_obj.const,{},{})
    attr_val=cWParams.extract_attr_val(attr_obj)
    
    if do_publish: # publish in factory ClassAd
        if is_parameter: # but also push to frontend
            if is_const:
                dicts['attrs'].add(attr_name,attr_val)
                dicts['consts'].add(attr_name,attr_val)
            else:
                dicts['params'].add(attr_name,attr_val)
        else: # only publish
            if (not is_const):
                raise RuntimeError, "Published attribute '%s' must be either a parameter or constant: %s"%(attr_name,attr_obj)
            
            dicts['attrs'].add(attr_name,attr_val)
    else: # do not publish, only to frontend
        if is_parameter:
            if is_const:
                dicts['consts'].add(attr_name,attr_val)
            else:
                raise RuntimeError, "Parameter attributes '%s' must be either a published or constant: %s"%(attr_name,attr_obj)
        else:
            raise RuntimeError, "Attributes '%s' must be either a published or parameters: %s"%(attr_name,attr_obj) 

    if is_parameter:
        do_glidein_publish=eval(attr_obj.glidein_publish,{},{})
        do_job_publish=eval(attr_obj.job_publish,{},{})

        if do_glidein_publish or do_job_publish:
            # need to add a line only if will be published
            if dicts['vars'].has_key(attr_name):
                # already in the var file, check if compatible
                attr_var_el=dicts['vars'][attr_name]
                attr_var_type=attr_var_el[0]
                if (((attr_obj.type=="int") and (attr_var_type!='I')) or
                    ((attr_obj.type=="string") and (attr_var_type=='I'))):
                    raise RuntimeError, "Types not compatible (%s,%s)"%(attr_obj.type,attr_var_type)
                attr_var_export=attr_var_el[4]
                if do_glidein_publish and (attr_var_export=='N'):
                    raise RuntimeError, "Cannot force glidein publishing"
                attr_var_job_publish=attr_var_el[5]
                if do_job_publish and (attr_var_job_publish=='-'):
                    raise RuntimeError, "Cannot force job publishing"
            else:
                dicts['vars'].add_extended(attr_name,attr_obj.type=="string",None,None,False,do_glidein_publish,do_job_publish)

#######################
# Populate job_descript
def populate_job_descript(submit_dir,job_descript_dict,        # will be modified
                          group_name,group_params):
    # if a user does not provide a file name, use the default one
    down_fname=group_params.downtimes.absfname
    if down_fname==None:
        down_fname=os.path.join(submit_dir,'group.downtimes')

    job_descript_dict.add('GroupName',group_name)
    job_descript_dict.add('GridType',group_params.gridtype)
    job_descript_dict.add('Gatekeeper',group_params.gatekeeper)
    if group_params.rsl!=None:
        job_descript_dict.add('GlobusRSL',group_params.rsl)
    job_descript_dict.add('Schedd',group_params.schedd_name)
    job_descript_dict.add('StartupDir',group_params.work_dir)
    if group_params.proxy_url!=None:
        job_descript_dict.add('ProxyURL',group_params.proxy_url)
    job_descript_dict.add('Verbosity',group_params.verbosity)
    job_descript_dict.add('DowntimesFile',down_fname)
    job_descript_dict.add('MaxRunning',group_params.config.max_jobs.running)
    job_descript_dict.add('MaxIdle',group_params.config.max_jobs.idle)
    job_descript_dict.add('MaxHeld',group_params.config.max_jobs.held)
    job_descript_dict.add('MaxSubmitRate',group_params.config.submit.max_per_cycle)
    job_descript_dict.add('SubmitCluster',group_params.config.submit.cluster_size)
    job_descript_dict.add('SubmitSleep',group_params.config.submit.sleep)
    job_descript_dict.add('MaxRemoveRate',group_params.config.remove.max_per_cycle)
    job_descript_dict.add('RemoveSleep',group_params.config.remove.sleep)
    job_descript_dict.add('MaxReleaseRate',group_params.config.release.max_per_cycle)
    job_descript_dict.add('ReleaseSleep',group_params.config.release.sleep)


    
#######################
# Simply symlink a file
def symlink_file(infile,outfile):
    try:
        os.symlink(infile,outfile)
    except IOError, e:
        raise RuntimeError, "Error symlink %s in %s: %s"%(infile,outfile,e)

#################################
# Check that it is a string list
# containing only valid groups
def validate_job_proxy_source(allow_proxy):
    recognized_sources=('factory','frontend')
    ap_list=allow_proxy.split(',')
    for source in ap_list:
        if not (source in recognized_sources):
            raise RuntimeError, "'%s' not a valid proxy source (valid list = %s)"%(source,recognized_sources)
    return
