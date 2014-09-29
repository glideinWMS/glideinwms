#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description: 
#   Frontend creation module
#   Classes and functions needed to handle dictionary files
#   created out of the parameter object
#

import os,os.path,shutil,string
import cvWDictFile,cWDictFile
import cvWConsts,cWConsts
import cvWCreate
from glideinwms.lib import x509Support

################################################
#
# This Class contains the main dicts
#
################################################

class frontendMainDicts(cvWDictFile.frontendMainDicts):
    def __init__(self,params,workdir_name):
        cvWDictFile.frontendMainDicts.__init__(self,params.work_dir,params.stage_dir,workdir_name,simple_work_dir=False,assume_groups=True,log_dir=params.log_dir)
        self.monitor_dir=params.monitor_dir
        self.add_dir_obj(cWDictFile.monitorWLinkDirSupport(self.monitor_dir,self.work_dir))
        self.monitor_jslibs_dir=os.path.join(self.monitor_dir,'jslibs')
        self.add_dir_obj(cWDictFile.simpleDirSupport(self.monitor_jslibs_dir,"monitor"))
        self.params=params
        self.active_sub_list=[]
        self.monitor_jslibs=[]
        self.monitor_htmls=[]
        self.client_security={}

    def populate(self,params=None):
        if params is None:
            params=self.params

        # put default files in place first
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.GRIDMAP_FILE,allow_overwrite=True) # this one must be loaded before factory runs setup_x509.sh
        
        # follow by the blacklist file
        file_name=cWConsts.BLACKLIST_FILE
        self.dicts['preentry_file_list'].add_from_file(file_name,(file_name,"nocache","TRUE",'BLACKLIST_FILE'),os.path.join(params.src_dir,file_name))

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh',"check_blacklist.sh"):
            self.dicts['preentry_file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        # put user files in stage
        for user_file in params.files:
            add_file_unparsed(user_file,self.dicts)

        # start expr is special
        start_expr=None

        # put user attributes into config files
        for attr_name in params.attrs.keys():
            if attr_name in ('GLIDECLIENT_Start','GLIDECLIENT_Group_Start'):
                if start_expr is None:
                    start_expr=params.attrs[attr_name].value
                elif not (params.attrs[attr_name].value in (None,'True')):
                    start_expr="(%s)&&(%s)"%(start_expr,params.attrs[attr_name].value)
                # delete from the internal structure... will use it in match section
                del params.data['attrs'][attr_name]
            else:
                add_attr_unparsed(attr_name, params,self.dicts,"main")

        real_start_expr=params.match.start_expr
        if start_expr is not None:
            if real_start_expr!='True':
                real_start_expr="(%s)&&(%s)"%(real_start_expr,start_expr)
            else:
                real_start_expr=start_expr
            # since I removed the attributes, roll back into the match.start_expr
            params.data['match']['start_expr']=real_start_expr
        
        self.dicts['consts'].add('GLIDECLIENT_Start',real_start_expr)
        
        # create GLIDEIN_Collector attribute
        self.dicts['params'].add_extended('GLIDEIN_Collector',False,str(calc_glidein_collectors(params.collectors)))
        populate_gridmap(params,self.dicts['gridmap'])

        if self.dicts['preentry_file_list'].is_placeholder(cWConsts.GRIDMAP_FILE): # gridmapfile is optional, so if not loaded, remove the placeholder
            self.dicts['preentry_file_list'].remove(cWConsts.GRIDMAP_FILE)

        # populate complex files
        populate_frontend_descript(self.work_dir,self.dicts['frontend_descript'],self.active_sub_list,params)
        populate_common_descript(self.dicts['frontend_descript'],params)

        # Apply multicore policy so frontend can deal with multicore
        # glideins and requests correctly
        apply_multicore_policy(self.dicts['frontend_descript'])

        # populate the monitor files
        javascriptrrd_dir = params.monitor.javascriptRRD_dir
        for mfarr in ((params.src_dir,'frontend_support.js'),
                      (javascriptrrd_dir,'javascriptrrd.wlibs.js')):
            mfdir,mfname=mfarr
            parent_dir = self.find_parent_dir(mfdir,mfname)
            mfobj=cWDictFile.SimpleFile(parent_dir,mfname)
            mfobj.load()
            self.monitor_jslibs.append(mfobj)

        for mfarr in ((params.src_dir,'frontendRRDBrowse.html'),
                      (params.src_dir,'frontendRRDGroupMatrix.html'),
                      (params.src_dir,'frontendGroupGraphStatusNow.html'),
                      (params.src_dir,'frontendStatus.html')):
            mfdir,mfname=mfarr
            mfobj=cWDictFile.SimpleFile(mfdir,mfname)
            mfobj.load()
            self.monitor_htmls.append(mfobj)

        spd = self.params.data
        useMonitorIndexPage = True
        if spd.has_key('frontend_monitor_index_page'):
            useMonitorIndexPage = spd['frontend_monitor_index_page'] in ('True', 'true', '1')
            
            if useMonitorIndexPage:
                mfobj = cWDictFile.SimpleFile(params.src_dir + '/frontend', 'index.html')
                mfobj.load()
                self.monitor_htmls.append(mfobj)

                for imgfil in ('frontendGroupGraphsNow.small.png',
                               'frontendRRDBrowse.small.png',
                               'frontendRRDGroupMatix.small.png',
                               'frontendStatus.small.png'):
                    mfobj = cWDictFile.SimpleFile(params.src_dir + '/frontend/images', imgfil)
                    mfobj.load()
                    self.monitor_htmls.append(mfobj)

        # Tell condor to advertise GLIDECLIENT_ReqNode
        self.dicts['vars'].add_extended('GLIDECLIENT_ReqNode','string',None,None,False,True,False)

        # derive attributes
        populate_common_attrs(self.dicts)

        # populate security data
        populate_main_security(self.client_security,params)

    def find_parent_dir(self,search_path,name):
        """ Given a search path, determine if the given file exists
            somewhere in the path.
            Returns: if found. returns the parent directory
                     if not found, raises an Exception
        """
        for root, dirs, files in os.walk(search_path,topdown=True):
            for filename in files:
                if filename == name:
                    return root
        raise RuntimeError,"Unable to find %(file)s in %(dir)s path" % \
                           { "file" : name,  "dir" : search_path, }

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            print "WARNING: main monitor base_dir has changed, stats may be lost: '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cvWDictFile.frontendMainDicts.reuse(self,other)

    def save(self,set_readonly=True):
        cvWDictFile.frontendMainDicts.save(self,set_readonly)
        self.save_monitor()
        self.save_client_security()


    ########################################
    # INTERNAL
    ########################################
    
    def save_monitor(self):
        for fobj in self.monitor_jslibs:
            fobj.save(dir=self.monitor_jslibs_dir,save_only_if_changed=False)
        for fobj in self.monitor_htmls:
            fobj.save(dir=self.monitor_dir,save_only_if_changed=False)
        return

    def save_client_security(self):
        # create a dummy mapfile so we have a reasonable default
        cvWCreate.create_client_mapfile(os.path.join(self.work_dir,cvWConsts.FRONTEND_MAP_FILE),
                                        self.client_security['proxy_DN'],[],[],[])
        # but the real mapfile will be (potentially) different for each
        # group, so frontend daemons will need to point to the real one at runtime
        cvWCreate.create_client_condor_config(os.path.join(self.work_dir,cvWConsts.FRONTEND_CONDOR_CONFIG_FILE),
                                              os.path.join(self.work_dir,cvWConsts.FRONTEND_MAP_FILE),
                                              self.client_security['collector_nodes'],
                                              self.params.security['classad_proxy'])
        return

################################################
#
# This Class contains the group dicts
#
################################################

class frontendGroupDicts(cvWDictFile.frontendGroupDicts):
    def __init__(self,params,sub_name,
                 summary_signature,workdir_name):
        cvWDictFile.frontendGroupDicts.__init__(self,params.work_dir,params.stage_dir,sub_name,summary_signature,workdir_name,simple_work_dir=False,base_log_dir=params.log_dir)
        self.monitor_dir=cvWConsts.get_group_monitor_dir(params.monitor_dir,sub_name)
        self.add_dir_obj(cWDictFile.monitorWLinkDirSupport(self.monitor_dir,self.work_dir))
        self.params=params
        self.client_security={}

    def populate(self,params=None):
        if params is None:
            params=self.params

        sub_params=params.groups[self.sub_name]

        # put default files in place first
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.CONSTS_FILE,allow_overwrite=True)
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.VARS_FILE,allow_overwrite=True)
        self.dicts['preentry_file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE,allow_overwrite=True) # this one must be loaded before any tarball

        # follow by the blacklist file
        file_name=cWConsts.BLACKLIST_FILE
        self.dicts['preentry_file_list'].add_from_file(file_name,(file_name,"nocache","TRUE",'BLACKLIST_FILE'),os.path.join(params.src_dir,file_name))

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh',"check_blacklist.sh"):
            self.dicts['preentry_file_list'].add_from_file(script_name,(cWConsts.insert_timestr(script_name),'exec','TRUE','FALSE'),os.path.join(params.src_dir,script_name))

        # put user files in stage
        for user_file in sub_params.files:
            add_file_unparsed(user_file,self.dicts)

        # start expr is special
        start_expr=None

        # put user attributes into config files
        for attr_name in sub_params.attrs.keys():
            if attr_name in ('GLIDECLIENT_Group_Start','GLIDECLIENT_Start'):
                if start_expr is None:
                    start_expr=sub_params.attrs[attr_name].value
                elif sub_params.attrs[attr_name].value is not None:
                    start_expr="(%s)&&(%s)"%(start_expr,sub_params.attrs[attr_name].value)
                # delete from the internal structure... will use it in match section
                del sub_params.data['attrs'][attr_name]
            else:
                add_attr_unparsed(attr_name, sub_params,self.dicts,self.sub_name)

        real_start_expr=sub_params.match.start_expr
        if start_expr is not None:
            if real_start_expr!='True':
                real_start_expr="(%s)&&(%s)"%(real_start_expr,start_expr)
            else:
                real_start_expr=start_expr
            # since I removed the attributes, roll back into the match.start_expr
            sub_params.data['match']['start_expr']=real_start_expr
        
        self.dicts['consts'].add('GLIDECLIENT_Group_Start',real_start_expr)

        # derive attributes
        populate_common_attrs(self.dicts)

        # populate complex files
        populate_group_descript(self.work_dir,self.dicts['group_descript'],
                                self.sub_name,sub_params)
        populate_common_descript(self.dicts['group_descript'],sub_params)

        # Apply group specific glexec policy
        apply_group_glexec_policy(self.dicts['group_descript'], sub_params, params)

        # populate security data
        populate_main_security(self.client_security,params)
        populate_group_security(self.client_security,params,sub_params)


    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            print "WARNING: group monitor base_dir has changed, stats may be lost: '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cvWDictFile.frontendGroupDicts.reuse(self,other)

    def save(self,set_readonly=True):
        cvWDictFile.frontendGroupDicts.save(self,set_readonly)
        self.save_client_security()

    ########################################
    # INTERNAL
    ########################################
    
    def save_client_security(self):
        # create the real mapfiles
        cvWCreate.create_client_mapfile(os.path.join(self.work_dir,cvWConsts.GROUP_MAP_FILE),
                                        self.client_security['proxy_DN'],
                                        self.client_security['factory_DNs'],
                                        self.client_security['schedd_DNs'],
                                        self.client_security['collector_DNs'])
        cvWCreate.create_client_mapfile(os.path.join(self.work_dir,cvWConsts.GROUP_WPILOTS_MAP_FILE),
                                        self.client_security['proxy_DN'],
                                        self.client_security['factory_DNs'],
                                        self.client_security['schedd_DNs'],
                                        self.client_security['collector_DNs'],
                                        self.client_security['pilot_DNs'])
        return

        
################################################
#
# This Class contains both the main and
# the group dicts
#
################################################

class frontendDicts(cvWDictFile.frontendDicts):
    def __init__(self,params,
                 sub_list=None): # if None, get it from params
        if sub_list is None:
            sub_list=params.groups.keys()

        self.params=params
        cvWDictFile.frontendDicts.__init__(self,params.work_dir,params.stage_dir,sub_list,simple_work_dir=False,log_dir=params.log_dir)

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

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.monitor_dir!=other.monitor_dir:
            print "WARNING: monitor base_dir has changed, stats may be lost: '%s'!='%s'"%(self.monitor_dir,other.monitor_dir)
        
        return cvWDictFile.frontendDicts.reuse(self,other)

    ###########
    # PRIVATE
    ###########

    def local_populate(self,params):
        return # nothing to do
        

    ######################################
    # Redefine methods needed by parent
    def new_MainDicts(self):
        return frontendMainDicts(self.params,self.workdir_name)

    def new_SubDicts(self,sub_name):
        return frontendGroupDicts(self.params,sub_name,
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

    if eval(user_file.after_entry,{},{}):
        file_list_idx='file_list'
    else:
        file_list_idx='preentry_file_list'

    if user_file.has_key('after_group'):
        if eval(user_file.after_group,{},{}):
            file_list_idx='aftergroup_%s'%file_list_idx

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

    is_parameter=eval(attr_obj.parameter,{},{})
    is_expr=(attr_obj.type=="expr")
    attr_val=params.extract_attr_val(attr_obj)
    
    if is_parameter:
        dicts['params'].add_extended(attr_name,is_expr,attr_val)
    else:
        dicts['consts'].add(attr_name,attr_val)

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
# Create the frontend descript file
def populate_frontend_descript(work_dir,
                               frontend_dict,active_sub_list,        # will be modified
                               params):
        
        frontend_dict.add('FrontendName',params.frontend_name)
        frontend_dict.add('WebURL',params.web_url)
        if hasattr(params,"monitoring_web_url") and (params.monitoring_web_url is not None):
            frontend_dict.add('MonitoringWebURL',params.monitoring_web_url)
        else:
            frontend_dict.add('MonitoringWebURL',params.web_url.replace("stage","monitor"))

        if params.security.classad_proxy is None:
            raise RuntimeError, "Missing security.classad_proxy"
        params.subparams.data['security']['classad_proxy']=os.path.abspath(params.security.classad_proxy)
        if not os.path.isfile(params.security.classad_proxy):
            raise RuntimeError, "security.classad_proxy(%s) is not a file"%params.security.classad_proxy
        frontend_dict.add('ClassAdProxy',params.security.classad_proxy)
        
        frontend_dict.add('SymKeyType',params.security.sym_key)

        active_sub_list[:] # erase all
        for sub in params.groups.keys():
            if eval(params.groups[sub].enabled,{},{}):
                active_sub_list.append(sub)
        frontend_dict.add('Groups',string.join(active_sub_list,','))

        frontend_dict.add('LoopDelay',params.loop_delay)
        frontend_dict.add('AdvertiseDelay',params.advertise_delay)
        frontend_dict.add('GroupParallelWorkers',params.group_parallel_workers)
        frontend_dict.add('RestartAttempts',params.restart_attempts)
        frontend_dict.add('RestartInterval',params.restart_interval)
        frontend_dict.add('AdvertiseWithTCP',params.advertise_with_tcp)
        frontend_dict.add('AdvertiseWithMultiple',params.advertise_with_multiple)

        frontend_dict.add('MonitorDisplayText',params.monitor_footer.display_txt)
        frontend_dict.add('MonitorLink',params.monitor_footer.href_link)

        frontend_dict.add('CondorConfig',os.path.join(work_dir,cvWConsts.FRONTEND_CONDOR_CONFIG_FILE))

        frontend_dict.add('LogDir',params.log_dir)
        frontend_dict.add('ProcessLogs', str(params.log_retention['process_logs']))
        
        frontend_dict.add('MaxIdleVMsTotal',params.config.idle_vms_total.max)
        frontend_dict.add('CurbIdleVMsTotal',params.config.idle_vms_total.curb)
        frontend_dict.add('MaxIdleVMsTotalGlobal',params.config.idle_vms_total_global.max)
        frontend_dict.add('CurbIdleVMsTotalGlobal',params.config.idle_vms_total_global.curb)
        frontend_dict.add('MaxRunningTotal',params.config.running_glideins_total.max)
        frontend_dict.add('CurbRunningTotal',params.config.running_glideins_total.curb)
        frontend_dict.add('MaxRunningTotalGlobal',params.config.running_glideins_total_global.max)
        frontend_dict.add('CurbRunningTotalGlobal',params.config.running_glideins_total_global.curb)

#######################
# Populate group descript
def populate_group_descript(work_dir,group_descript_dict,        # will be modified
                            sub_name,sub_params):

    group_descript_dict.add('GroupName',sub_name)

    group_descript_dict.add('MapFile',os.path.join(work_dir,cvWConsts.GROUP_MAP_FILE))
    group_descript_dict.add('MapFileWPilots',os.path.join(work_dir,cvWConsts.GROUP_WPILOTS_MAP_FILE))

    group_descript_dict.add('MaxRunningPerEntry',sub_params.config.running_glideins_per_entry.max)
    group_descript_dict.add('FracRunningPerEntry',sub_params.config.running_glideins_per_entry.relative_to_queue)
    group_descript_dict.add('MaxIdlePerEntry',sub_params.config.idle_glideins_per_entry.max)
    group_descript_dict.add('ReserveIdlePerEntry',sub_params.config.idle_glideins_per_entry.reserve)
    group_descript_dict.add('MaxIdleVMsPerEntry',sub_params.config.idle_vms_per_entry.max)
    group_descript_dict.add('CurbIdleVMsPerEntry',sub_params.config.idle_vms_per_entry.curb)
    group_descript_dict.add('MaxIdleVMsTotal',sub_params.config.idle_vms_total.max)
    group_descript_dict.add('CurbIdleVMsTotal',sub_params.config.idle_vms_total.curb)
    group_descript_dict.add('MaxRunningTotal',sub_params.config.running_glideins_total.max)
    group_descript_dict.add('CurbRunningTotal',sub_params.config.running_glideins_total.curb)
    group_descript_dict.add('MaxMatchmakers',sub_params.config.processing_workers.matchmakers)
    if (sub_params.attrs.has_key('GLIDEIN_Glexec_Use')):
        group_descript_dict.add('GLIDEIN_Glexec_Use',sub_params.attrs['GLIDEIN_Glexec_Use']['value'])


#####################################################
# Populate values common to frontend and group dicts
MATCH_ATTR_CONV={'string':'s','int':'i','real':'r','bool':'b'}


def apply_group_glexec_policy(descript_dict, sub_params, params):

    glidein_glexec_use = None
    query_expr = descript_dict['FactoryQueryExpr']
    match_expr = descript_dict['MatchExpr']
    ma_arr = []
    match_attrs = None

    # Consider GLIDEIN_Glexec_Use from Group level, else global
    if sub_params.attrs.has_key('GLIDEIN_Glexec_Use'):
        glidein_glexec_use = sub_params.attrs['GLIDEIN_Glexec_Use']['value']
    elif params.attrs.has_key('GLIDEIN_Glexec_Use'):
        glidein_glexec_use = params.attrs['GLIDEIN_Glexec_Use']['value']

    if (glidein_glexec_use):
        descript_dict.add('GLIDEIN_Glexec_Use', glidein_glexec_use)

        # Based on the value GLIDEIN_Glexec_Use consider the entries as follows
        # REQUIRED: Entries with GLEXEC_BIN set
        # OPTIONAL: Consider all entries irrespective of their GLEXEC config
        # NEVER   : Consider entries that do not want glidein to use GLEXEC
        if (glidein_glexec_use == 'REQUIRED'):
            query_expr = '(%s) && (GLEXEC_BIN=!=UNDEFINED) && (GLEXEC_BIN=!="NONE")' % query_expr
            match_expr = '(%s) and (glidein["attrs"].get("GLEXEC_BIN", "NONE") != "NONE")' % match_expr
            ma_arr.append(('GLEXEC_BIN', 's'))
        elif (glidein_glexec_use == 'NEVER'):
            match_expr = '(%s) and (glidein["attrs"].get("GLIDEIN_REQUIRE_GLEXEC_USE", "False") == "False")' % match_expr

        if ma_arr:
            match_attrs = eval(descript_dict['FactoryMatchAttrs']) + ma_arr
            descript_dict.add('FactoryMatchAttrs', repr(match_attrs),
                              allow_overwrite=True)

        descript_dict.add('FactoryQueryExpr', query_expr, allow_overwrite=True)
        descript_dict.add('MatchExpr', match_expr, allow_overwrite=True)


def apply_multicore_policy(descript_dict):
    match_expr = descript_dict['MatchExpr']

    # Only consider sites that provide enough GLIDEIN_CPUS jobs to run
    match_expr = '(%s) and (getGlideinCpusNum(glidein) >= int(job.get("RequestCpus", 1)))' % match_expr
    descript_dict.add('MatchExpr', match_expr, allow_overwrite=True)

    # Add GLIDEIN_CPUS to the list of attrs queried in glidefactory classad
    fact_ma = eval(descript_dict['FactoryMatchAttrs']) + [('GLIDEIN_CPUS', 's')]
    descript_dict.add('FactoryMatchAttrs', repr(fact_ma), allow_overwrite=True)

    # Add RequestCpus to the list of attrs queried in glidefactory classad
    job_ma = eval(descript_dict['JobMatchAttrs']) + [('RequestCpus', 'i')]
    descript_dict.add('JobMatchAttrs', repr(job_ma), allow_overwrite=True)


def get_pool_list(credential):
    pool_idx_len = credential['pool_idx_len']
    if pool_idx_len is None:
        pool_idx_len = 0
    else:
        pool_idx_len = int(pool_idx_len)
    pool_idx_list_unexpanded = credential['pool_idx_list'].split(',')
    pool_idx_list_expanded = []

    # Expand ranges in pool list
    for idx in pool_idx_list_unexpanded:
        if '-' in idx:
            idx_range = idx.split('-')
            for i in range(int(idx_range[0]), int(idx_range[1])+1):
                pool_idx_list_expanded.append(str(i))
        else:
            pool_idx_list_expanded.append(idx.strip())

    pool_idx_list_strings=[]
    for idx in pool_idx_list_expanded:
        pool_idx_list_strings.append(idx.zfill(pool_idx_len))
    return pool_idx_list_strings
    

def populate_common_descript(descript_dict,        # will be modified
                             params):

    for tel in (("factory","Factory"),("job","Job")):
        param_tname,str_tname=tel
        ma_arr=[]
        qry_expr = params.match[param_tname]['query_expr']

        descript_dict.add('%sQueryExpr'%str_tname,qry_expr)

        match_attrs=params.match[param_tname]['match_attrs']
        for attr_name in match_attrs.keys():
            attr_type=match_attrs[attr_name]['type']
            if not (attr_type in MATCH_ATTR_CONV.keys()):
                raise RuntimeError, "match_attr type '%s' not one of %s"%(attr_type,MATCH_ATTR_CONV.keys())
            ma_arr.append((str(attr_name),MATCH_ATTR_CONV[attr_type]))

        descript_dict.add('%sMatchAttrs'%str_tname,repr(ma_arr))

    if params.security.security_name is not None:
        descript_dict.add('SecurityName',params.security.security_name)

    collectors=[]
    for el in params.match.factory.collectors:
        if el['factory_identity'][-9:]=='@fake.org':
            raise RuntimeError, "factory_identity for %s not set! (i.e. it is fake)"%el['node']
        if el['my_identity'][-9:]=='@fake.org':
            raise RuntimeError, "my_identity for %s not set! (i.e. it is fake)"%el['node']
        cWDictFile.validate_node(el['node'])
        collectors.append((el['node'],el['factory_identity'],el['my_identity']))
    descript_dict.add('FactoryCollectors',repr(collectors))

    schedds=[]
    for el in params.match.job.schedds:
        cWDictFile.validate_node(el['fullname'])
        schedds.append(el['fullname'])
    descript_dict.add('JobSchedds',string.join(schedds,','))

    if params.security.proxy_selection_plugin is not None:
        descript_dict.add('ProxySelectionPlugin',params.security.proxy_selection_plugin)

    if len(params.security.credentials) > 0:
        proxies = []
        proxy_attrs=['security_class','trust_domain','type',
            'keyabsfname','pilotabsfname','vm_id','vm_type',
            'creation_script','update_frequency']
        proxy_attr_names={'security_class':'ProxySecurityClasses',
            'trust_domain':'ProxyTrustDomains',
            'type':'ProxyTypes','keyabsfname':'ProxyKeyFiles',
            'pilotabsfname':'ProxyPilotFiles',
            'vm_id':'ProxyVMIds','vm_type':'ProxyVMTypes',
            'creation_script':'ProxyCreationScripts',
            'update_frequency':'ProxyUpdateFrequency'}
        proxy_descript_values={}
        for attr in proxy_attrs:
            proxy_descript_values[attr]={}
        proxy_trust_domains = {}
        for pel in params.security.credentials:
            if pel['absfname'] is None:
                raise RuntimeError, "All proxies need a absfname!"
            if (pel['pool_idx_len'] is None) and (pel['pool_idx_list'] is None):
                # only one
                proxies.append(pel['absfname'])
                for attr in proxy_attrs:
                    if pel[attr] is not None:
                        proxy_descript_values[attr][pel['absfname']]=pel[attr]
            else: #pool
                pool_idx_list_expanded_strings = get_pool_list(pel)
                for idx in pool_idx_list_expanded_strings:
                    absfname = "%s%s" % (pel['absfname'], idx)
                    proxies.append(absfname)
                    for attr in proxy_attrs:
                        if pel[attr] is not None:
                            proxy_descript_values[attr][pel['absfname']]=pel[attr]

        descript_dict.add('Proxies', repr(proxies))
        for attr in proxy_attrs:
            if len(proxy_descript_values[attr].keys()) > 0:
                descript_dict.add(proxy_attr_names[attr], repr(proxy_descript_values[attr]))

    match_expr = params.match.match_expr
    descript_dict.add('MatchExpr', match_expr)


#####################################################
# Returns a string usable for GLIDEIN_Collector
def calc_glidein_collectors(collectors):
    collector_nodes = {}
    glidein_collectors = []

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
            glidein_collectors.append(string.join(collector_nodes[group]['secondary'], ","))
        else:
            glidein_collectors.append(string.join(collector_nodes[group]['primary'], ","))
    return string.join(glidein_collectors, ";")


#####################################################
# Populate gridmap to be used by the glideins
def populate_gridmap(params,gridmap_dict):
    collector_dns=[]
    for el in params.collectors:
        dn=el.DN
        if dn is None:
            raise RuntimeError,"DN not defined for pool collector %s"%el.node
        if not (dn in collector_dns): #skip duplicates
            collector_dns.append(dn)
            gridmap_dict.add(dn,'collector%i'%len(collector_dns))

    # Add also the frontend DN, so it is easier to debug
    if params.security.proxy_DN is not None:
        if not (params.security.proxy_DN in collector_dns):
            gridmap_dict.add(params.security.proxy_DN,'frontend')

#####################################################
# Populate security values
def populate_main_security(client_security,params):
    if params.security.proxy_DN is None:
        raise RuntimeError,"DN not defined for classad_proxy"    
    client_security['proxy_DN']=params.security.proxy_DN
    
    collector_dns=[]
    collector_nodes=[]
    for el in params.collectors:
        dn=el.DN
        if dn is None:
            raise RuntimeError,"DN not defined for pool collector %s"%el.node
        is_secondary=eval(el.secondary)
        if is_secondary:
            continue # only consider primary collectors for the main security config
        collector_nodes.append(el.node)
        collector_dns.append(dn)
    if len(collector_nodes)==0:
        raise RuntimeError,"Need at least one non-secondary pool collector"
    client_security['collector_nodes']=collector_nodes
    client_security['collector_DNs']=collector_dns

def populate_group_security(client_security,params,sub_params):
    factory_dns=[]
    for collectors in (params.match.factory.collectors, sub_params.match.factory.collectors):
      for el in collectors:
        dn=el.DN
        if dn is None:
            raise RuntimeError,"DN not defined for factory %s"%el.node
        # don't worry about conflict... there is nothing wrong if the DN is listed twice
        factory_dns.append(dn)
    client_security['factory_DNs']=factory_dns
    
    schedd_dns=[]
    for schedds in (params.match.job.schedds, sub_params.match.job.schedds):
      for el in schedds:
        dn=el.DN
        if dn is None:
            raise RuntimeError,"DN not defined for schedd %s"%el.fullname
        # don't worry about conflict... there is nothing wrong if the DN is listed twice
        schedd_dns.append(dn)
    client_security['schedd_DNs']=schedd_dns

    pilot_dns=[]
    for credentials in (params.security.credentials, sub_params.security.credentials):
        for pel in credentials:
            if pel['pilotabsfname'] is None:
                proxy_fname=pel['absfname']
            else:
                proxy_fname=pel['pilotabsfname']

            if (pel['pool_idx_len'] is None) and (pel['pool_idx_list'] is None):
                # only one
                dn=x509Support.extract_DN(proxy_fname)
                # don't worry about conflict... there is nothing wrong if the DN is listed twice
                pilot_dns.append(dn)
            else:
                # pool
                pool_idx_list_expanded_strings = get_pool_list(pel)
                for idx in pool_idx_list_expanded_strings:
                    real_proxy_fname = "%s%s" % (proxy_fname, idx)
                    dn=x509Support.extract_DN(real_proxy_fname)
                    # don't worry about conflict... there is nothing wrong if the DN is listed twice
                    pilot_dns.append(dn)
                
    client_security['pilot_DNs']=pilot_dns

#####################################################
# Populate attrs
# This is a digest of the other values

def populate_common_attrs(dicts):
    # there should be no conflicts, so does not matter in which order I put them together
    for k in dicts['params'].keys:
        dicts['attrs'].add(k,dicts['params'].get_true_val(k))
    for k in dicts['consts'].keys:
        dicts['attrs'].add(k,dicts['consts'].get_typed_val(k))
