#######################################################
#
# Glidein creation module
# Classes and functions needed to handle dictionary files
#
#######################################################

import os,os.path,string,copy
import cgWConsts,cWConsts
import cWDictFile


# values are (Type,System,Ref)
class InfoSysDictFile(cWDictFile.DictFile):
    def file_header(self,want_comments):
        if want_comments:
            return (cWDictFile.DictFile.file_header(self,want_comments)+"\n"+
                    ("# %s \t%30s \t%s \t\t%s\n"%('Type','Server','Ref','ID'))+
                    ("#"*78))
        else:
            return None

    # key can be None
    # in that case it will be composed out of value
    def add(self,key,val,allow_overwrite=0):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val
        if len(val)!=3:
            raise RuntimeError, "Values '%s' not (Type,System,Ref)"%str(val)

        if key==None:
            key="%s://%s/%s"%val
        return cWDictFile.DictFile.add(self,key,val,allow_overwrite)

    def add_extended(self,
                     infosys_type,
                     server_name,
                     ref_str,
                     allow_overwrite=0):
        self.add(None,(infosys_type,server_name,ref_str))
        
    def format_val(self,key,want_comments):
        return "%s \t%30s \t%s \t\t%s"%(self.vals[key][0],self.vals[key][1],self.vals[key][2],key)
        

    def parse_val(self,line):
        if len(line)==0:
            return #ignore emoty lines
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,3)
        if len(arr)==0:
            return # empty line
        if len(arr)!=4:
            raise RuntimeError,"Not a valid var line (expected 4, found %i elements): '%s'"%(len(arr),line)

        key=arr[-1]
        return self.add(key,arr[:-1])


class CondorJDLDictFile(cWDictFile.DictFile):
    def __init__(self,dir,fname,sort_keys=False,order_matters=False,jobs_in_cluster=None,
                 fname_idx=None):      # if none, use fname
        cWDictFile.DictFile.__init__(self,dir,fname,sort_keys,order_matters,fname_idx)
        self.jobs_in_cluster=jobs_in_cluster

    def file_footer(self,want_comments):
        if self.jobs_in_cluster==None:
            return "Queue"
        else:
            return "Queue %s"%self.jobs_in_cluster

    def format_val(self,key,want_comments):
        return "%s = %s"%(key,self.vals[key])

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,2)
        if len(arr)==0:
            return # empty line

        if arr[0]=='Queue':
            # this is the final line
            if len(arr)==1:
                # default
                self.jobs_in_cluster=None
            else:
                self.jobs_in_cluster=arr[1]
            return
            
        # should be a regular line
        if len(arr)<2:
            raise RuntimeError,"Not a valid Condor JDL line, too short: '%s'"%line
        if arr[1]!='=':
            raise RuntimeError,"Not a valid Condor JDL line, no =: '%s'"%line
        
        if len(arr)==2:
            return self.add(arr[0],"") # key = <empty>
        else:
            return self.add(arr[0],arr[2])

    def is_equal(self,other,         # other must be of the same class
                 compare_dir=False,compare_fname=False,
                 compare_keys=None): # if None, use order_matters
        if self.jobs_in_cluster==other.jobs_in_cluster:
            return cWDictFile.DictFile.is_equal(other,compare_dir,compare_fname,compare_keys)
        else:
            return False

################################################
#
# Functions that create default dictionaries
#
################################################

# internal, do not use from outside the module
def get_common_dicts(submit_dir,stage_dir):
    common_dicts={'attrs':cWDictFile.ReprDictFile(submit_dir,cgWConsts.ATTRS_FILE),
                  'description':cWDictFile.DescriptionDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.DESCRIPTION_FILE),fname_idx=cWConsts.DESCRIPTION_FILE),
                  'consts':cWDictFile.StrDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.CONSTS_FILE),fname_idx=cWConsts.CONSTS_FILE),
                  'params':cWDictFile.ReprDictFile(submit_dir,cgWConsts.PARAMS_FILE),
                  'vars':cWDictFile.VarsDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.VARS_FILE),fname_idx=cWConsts.VARS_FILE),
                  'untar_cfg':cWDictFile.StrDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.UNTAR_CFG_FILE),fname_idx=cWConsts.UNTAR_CFG_FILE),
                  'file_list':cWDictFile.FileDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.FILE_LISTFILE),fname_idx=cWConsts.FILE_LISTFILE),
                  "signature":cWDictFile.SHA1DictFile(stage_dir,cWConsts.insert_timestr(cWConsts.SIGNATURE_FILE),fname_idx=cWConsts.SIGNATURE_FILE)}
    refresh_description(common_dicts)
    return common_dicts

def get_main_dicts(submit_dir,stage_dir):
    main_dicts=get_common_dicts(submit_dir,stage_dir)
    main_dicts['summary_signature']=cWDictFile.SummarySHA1DictFile(submit_dir,cWConsts.SUMMARY_SIGNATURE_FILE)
    main_dicts['glidein']=cWDictFile.StrDictFile(submit_dir,cgWConsts.GLIDEIN_FILE)
    main_dicts['after_file_list']=cWDictFile.FileDictFile(stage_dir,cWConsts.insert_timestr(cWConsts.AFTER_FILE_LISTFILE),fname_idx=cWConsts.AFTER_FILE_LISTFILE)
    return main_dicts

def get_entry_dicts(entry_submit_dir,entry_stage_dir,entry_name):
    entry_dicts=get_common_dicts(entry_submit_dir,entry_stage_dir)
    entry_dicts['job_descript']=cWDictFile.StrDictFile(entry_submit_dir,cgWConsts.JOB_DESCRIPT_FILE)
    entry_dicts['infosys']=InfoSysDictFile(entry_submit_dir,cgWConsts.INFOSYS_FILE)
    return entry_dicts

################################################
#
# Functions that load dictionaries
#
################################################

# internal, do not use from outside the module
def load_common_dicts(dicts,           # update in place
                      description_el):
    # first submit dir ones (mutable)
    dicts['params'].load()
    dicts['attrs'].load()
    # now the ones keyed in the description
    dicts['signature'].load(fname=description_el.vals2['signature'])
    dicts['file_list'].load(fname=description_el.vals2['file_list'])
    file_el=dicts['file_list']
    # all others are keyed in the file_list
    dicts['consts'].load(fname=file_el[cWConsts.CONSTS_FILE][0])
    dicts['vars'].load(fname=file_el[cgWConsts.VARS_FILE][0])
    dicts['untar_cfg'].load(fname=file_el[cWConsts.UNTAR_CFG_FILE][0])

def load_main_dicts(main_dicts): # update in place
    main_dicts['glidein'].load()
    # summary_signature has keys for description
    main_dicts['summary_signature'].load()
    # load the description
    main_dicts['description'].load(fname=main_dicts['summary_signature']['main'][1])
    # all others are keyed in the description
    main_dicts['after_file_list'].load(fname=main_dicts['description'].vals2['after_file_list'])
    load_common_dicts(main_dicts,main_dicts['description'])

def load_entry_dicts(entry_dicts,                   # update in place
                     entry_name,summary_signature): 
    try:
        entry_dicts['infosys'].load()
    except RuntimeError:
         pass # ignore errors, this is optional
    entry_dicts['job_descript'].load()
    # load the description (name from summary_signature)
    entry_dicts['description'].load(fname=summary_signature[cgWConsts.get_entry_stage_dir("",entry_name)][1])
    # all others are keyed in the description
    load_common_dicts(entry_dicts,entry_dicts['description'])

############################################################
#
# Functions that create data out of the existing dictionary
#
############################################################

def refresh_description(dicts): # update in place
    description_dict=dicts['description']
    description_dict.add(dicts['signature'].get_fname(),"signature",allow_overwrite=True)
    for k in ('file_list','after_file_list'):
        if dicts.has_key(k):
            description_dict.add(dicts[k].get_fname(),k,allow_overwrite=True)

def refresh_file_list(dicts,is_main, # update in place
                      files_set_readonly=True,files_reset_changed=True):
    entry_str="_ENTRY"
    if is_main:
        entry_str=""
    file_dict=dicts['file_list']
    file_dict.add(cWConsts.CONSTS_FILE,(dicts['consts'].get_fname(),"regular","TRUE","CONSTS%s_FILE"%entry_str,dicts['consts'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)
    file_dict.add(cgWConsts.VARS_FILE,(dicts['vars'].get_fname(),"regular","TRUE","CONDOR_VARS%s_FILE"%entry_str,dicts['vars'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)
    file_dict.add(cWConsts.UNTAR_CFG_FILE,(dicts['untar_cfg'].get_fname(),"regular","TRUE","UNTAR_CFG%s_FILE"%entry_str,dicts['untar_cfg'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)

# dictionaries must have been written to disk before using this
def refresh_signature(dicts): # update in place
    signature_dict=dicts['signature']
    for k in ('consts','vars','untar_cfg','file_list','after_file_list','description'):
        if dicts.has_key(k):
            signature_dict.add_from_file(dicts[k].get_filepath(),allow_overwrite=True)
    # add signatures of all the files linked in the lists
    for k in ('file_list','after_file_list'):
        if dicts.has_key(k):
            filedict=dicts[k]
            for fname in filedict.get_immutable_files():
                signature_dict.add_from_file(os.path.join(filedict.dir,fname),allow_overwrite=True)
    

################################################
#
# Functions that save dictionaries
#
################################################


# internal, do not use from outside the module
def save_common_dicts(dicts,     # will update in place, too
                      is_main,
                     set_readonly=True):
    # make sure decription is up to date
    refresh_description(dicts)
    # save the immutable ones
    for k in ('description',):
        dicts[k].save(set_readonly=set_readonly)
    # Load files into the file list
    # 'consts','untar_cfg','vars' will be loaded
    refresh_file_list(dicts,is_main)
    # save files in the file lists
    for k in ('file_list','after_file_list'):
        if dicts.has_key(k):
            dicts[k].save_files(allow_overwrite=True)
    # then save the lists
    for k in ('file_list','after_file_list'):
        if dicts.has_key(k):
            dicts[k].save(set_readonly=set_readonly)
    # calc and save the signatues
    refresh_signature(dicts)
    dicts['signature'].save(set_readonly=set_readonly)

    #finally save the mutable one(s)
    dicts['params'].save(set_readonly=set_readonly)
    dicts['attrs'].save(set_readonly=set_readonly)

# must be invoked after all the entries have been saved
def save_main_dicts(main_dicts, # will update in place, too
                    set_readonly=True):
    main_dicts['glidein'].save(set_readonly=set_readonly)
    save_common_dicts(main_dicts,True,set_readonly=set_readonly)
    summary_signature=main_dicts['summary_signature']
    summary_signature.add_from_file(key="main",filepath=main_dicts['signature'].get_filepath(),fname2=main_dicts['description'].get_fname(),allow_overwrite=True)
    summary_signature.save(set_readonly=set_readonly)


def save_entry_dicts(entry_dicts,                   # will update in place, too
                     entry_name,summary_signature,  # update in place
                     set_readonly=True):
    entry_dicts['infosys'].save(set_readonly=set_readonly)
    entry_dicts['job_descript'].save(set_readonly=set_readonly)
    save_common_dicts(entry_dicts,False,set_readonly=set_readonly)
    summary_signature.add_from_file(key=cgWConsts.get_entry_stage_dir("",entry_name),filepath=entry_dicts['signature'].get_filepath(),fname2=entry_dicts['description'].get_fname(),allow_overwrite=True)

################################################
#
# Functions that reuse dictionaries
#
################################################

def reuse_simple_dict(dicts,other_dicts,key,compare_keys=None):
    if dicts[key].is_equal(other_dicts[key],compare_dir=True,compare_fname=False,compare_keys=compare_keys):
        # if equal, just use the old one, and mark it as unchanged and readonly
        dicts[key]=copy.deepcopy(other_dicts[key])
        dicts[key].changed=False
        dicts[key].set_readonly(True)
        return True
    else:
        return False

def reuse_file_dict(dicts,other_dicts,key):
    dicts[key].reuse(other_dicts[key])
    return reuse_simple_dict(dicts,other_dicts,key)

def reuse_common_dicts(dicts, other_dicts,is_main,all_reused):
    # save the immutable ones
    # check simple dictionaries
    for k in ('consts','untar_cfg','vars'):
        all_reused=reuse_simple_dict(dicts,other_dicts,k) and all_reused
    # since the file names may have changed, refresh the file_list    
    refresh_file_list(dicts,is_main)
    # check file-based dictionaries
    for k in ('file_list','after_file_list'):
        if dicts.has_key(k):
            all_reused=reuse_file_dict(dicts,other_dicts,k) and all_reused

    if all_reused:
        # description and signature track other files
        # so they change iff the others change
        for k in ('description','signature'):
            dicts[k]=copy.deepcopy(other_dicts[k])
            dicts[k].changed=False
            dicts[k].set_readonly(True)
            
    # check the mutable ones
    for k in ('attrs','params'):
        reuse_simple_dict(dicts,other_dicts,k)

    return all_reused

def reuse_main_dicts(main_dicts, other_main_dicts):
    reuse_simple_dict(main_dicts, other_main_dicts,'glidein')
    all_reused=reuse_common_dicts(main_dicts, other_main_dicts,True,True)
    # will not try to reuse the summary_signature... being in submit_dir
    # can be rewritten and it is not worth the pain to try to prevent it
    return all_reused

def reuse_entry_dicts(entry_dicts, other_entry_dicts,entry_name):
    reuse_simple_dict(entry_dicts, other_entry_dicts,'job_descript')
    reuse_simple_dict(entry_dicts, other_entry_dicts,'infosys')
    all_reused=reuse_common_dicts(entry_dicts, other_entry_dicts,False,True)
    return all_reused

################################################
#
# Handle dicts as Classes
#
################################################

class proxyDirSupport(cWDictFile.chmodDirSupport):
    def __init__(self,proxy_dir):
        cWDictFile.chmodDirSupport.__init__(self,proxy_dir,0700,'proxy')

################################################
#
# This Class contains the main dicts
#
################################################

class glideinMainDicts(cWDictFile.fileMainDicts):
    def __init__(self,
                 work_dir,stage_dir,
                 workdir_name):
        cWDictFile.fileMainDicts.__init__(self,work_dir,stage_dir,workdir_name)
        proxy_dir=os.path.join(self.work_dir,'client_proxies')
        self.add_dir_obj(proxyDirSupport(proxy_dir))
    
    ######################################
    # Redefine methods needed by parent
    def load(self):
        load_main_dicts(self.dicts)

    def save(self,set_readonly=True):
        save_main_dicts(self.dicts,set_readonly=set_readonly)

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        cWDictFile.fileMainDicts.reuse(self,other)
        reuse_main_dicts(self.dicts,other.dicts)

    ####################
    # Internal
    ####################

    # Child must overwrite this
    def get_main_dicts(self):
        return get_main_dicts(self.work_dir,self.stage_dir)
    
        
################################################
#
# This Class contains the entry dicts
#
################################################

class glideinEntryDicts(cWDictFile.fileSubDicts):
    ######################################
    # Redefine methods needed by parent
    def load(self):
        load_entry_dicts(self.dicts,self.sub_name,self.summary_signature)

    def save(self,set_readonly=True):
        save_entry_dicts(self.dicts,self.sub_name,self.summary_signature,set_readonly=set_readonly)

    def save_final(self,set_readonly=True):
        pass # nothing to do
    
    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        cWDictFile.fileSubDicts.reuse(self,other)
        reuse_entry_dicts(self.dicts,other.dicts,self.sub_name)

    ####################
    # Internal
    ####################

    def get_sub_work_dir(self,base_dir):
        return cgWConsts.get_entry_submit_dir(base_dir,self.sub_name)
    
    def get_sub_stage_dir(self,base_dir):
        return cgWConsts.get_entry_stage_dir(base_dir,self.sub_name)
    
    def get_sub_dicts(self):
        return get_entry_dicts(self.work_dir,self.stage_dir,self.sub_name)
    
    def reuse_nocheck(self):
        reuse_entry_dicts(self.dicts,other.dicts,self.sub_name)
        
################################################
#
# This Class contains both the main and
# the entry dicts
#
################################################

class glideinDicts(cWDictFile.fileDicts):
    def __init__(self,work_dir,stage_dir,entry_list=[],workdir_name='submit'):
        cWDictFile.fileDicts.__init__(work_dir,stage_dir,entry_list,workdir_name)

    ###########
    # PRIVATE
    ###########

    ######################################
    # Redefine methods needed by parent
    def new_MainDicts(self):
        return glideinMainDicts(self.work_dir,self.stage_dir,self.workdir_name)

    def new_SubDicts(self,sub_name):
        return glideinEntryDicts(self.work_dir,self.stage_dir,sub_name,self.main_dicts.get_summary_signature(),self.workdir_name)

    def get_sub_name_from_sub_stage_dir(self,sign_key):
        return cgWConsts.get_entry_name_from_entry_stage_dir(sign_key)
    
