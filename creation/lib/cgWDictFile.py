#######################################################
#
# Glidein creation module
# Classes and functions needed to handle dictionary files
#
#######################################################

import os.path
import cgWConsts

########################################
#
# File dictionary classes
#
########################################

class DictFile:
    def __init__(self,dir,fname,sort_keys=False):
        self.dir=dir
        self.fname=fname
        self.sort_keys=sort_keys

        self.is_readonly=False
        
        self.keys=[]
        self.vals={}

    def has_key(self,key):
        return key in self.keys

    def __getitem__(self,key):
        return self.vals[key]

    def get_fname(self):
        return self.fname

    def get_dir(self):
        return self.dir

    def erase(self):
        self.keys=[]
        self.vals={}
        
    def set_readonly(self,readonly=True):
        self.is_readonly=readonly


    def add(self,key,val,allow_overwrite=False):
        if self.is_readonly:
            raise RuntimeError, "Trying to modify a readonly object!"
        
        if key in self.keys:
            if not allow_overwrite:
                raise RuntimeError, "Key '%s' already exists"%key
            elif not self.is_compatible(self.vals[key],val):
                raise RuntimeError, "Key '%s': Value %s not compatible with old value %s"%(key,val,self.vals[key])
        else:
            self.keys.append(key)
        self.vals[key]=val

    def save(self, dir=None, fname=None,sort_keys=None): # if dir and/or fname are not specified, use the defaults specified in __init__
        if dir==None:
            dir=self.dir
        if fname==None:
            fname=self.fname
        if sort_keys==None:
            sort_keys=self.sort_keys


        filepath=os.path.join(dir,fname)
        try:
            fd=open(filepath,"w")
        except IOError,e:
            raise RuntimeError, "Error creating %s: %s"%(filepath,e)
        try:
            header=self.file_header()
            if header!=None:
                fd.write("%s\n"%header)
            if sort_keys:
                keys=self.keys[0:]
                keys.sort()
            else:
                keys=self.keys
            for k in keys:
                fd.write("%s\n"%self.format_val(k))
        finally:
            fd.close()
        return

    def load(self, dir=None, fname=None): # if dir and/or fname are not specified, use the defaults specified in __init__, if they are, change the self.
        if dir==None:
            dir=self.dir
        if fname==None:
            fname=self.fname

        filepath=os.path.join(dir,fname)
        try:
            fd=open(filepath,"r")
        except IOError,e:
            raise RuntimeError, "Error opening %s: %s"%(filepath,e)
        try:
            lines=fd.readlines()
        finally:
            fd.close()

        idx=0
        for line in lines:
            idx+=1
            if line[-1]=='\n':
                # strip newline
                line=line[:-1]
            try:
                self.parse_val(line)
            except RuntimeError, e:
                raise RuntimeError, "File %s, line %i:%s"%(filepath,idx,str(e))

        self.dir=dir
        self.fname=fname
        return

    # PRIVATE
    def is_compatible(self,old_val,new_val):
        return True # everything is compatible
    
    def file_header(self):
        return None # no header
    
    def format_val(self,key):
        return "%s \t%s"%(key,self.vals[key])

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,1)
        if len(arr)==0:
            return # empty line
        if len(arr[0])==0:
            return # empty key

        key=arr[0]
        if len(arr)==1:
            val=''
        else:
            val=arr[1]
        return self.add(key,val)

class DictFileTwoKeys(DictFile): # both key and val are keys
    def __init__(self,dir,fname,sort_keys=False):
        DictFile.__init__(self,dir,fname,sort_keys)
        self.keys2=[]
        self.vals2={}

    def has_key2(self,key):
        return key in self.keys2

    def get_val2(self,key):
        return self.vals2[key]

    def add(self,key,val,allow_overwrite=False):
        if self.is_readonly:
            raise RuntimeError, "Trying to modify a readonly object!"
        
        if key in self.keys:
            if not allow_overwrite:
                raise RuntimeError, "Key '%s' already exists"%key
            elif not self.is_compatible(self.vals[key],val):
                raise RuntimeError, "Key '%s': Value %s not compatible with old value %s"%(key,val,self.vals[key])
        else:
            self.keys.append(key)

        if val in self.keys2:
            if not allow_overwrite:
                raise RuntimeError, "Value '%s' already exists"%val
            elif not self.is_compatible2(self.vals2[val],key):
                raise RuntimeError, "Value '%s': Key %s not compatible with old key %s"%(val,key,self.vals2[val])
        else:
            self.keys2.append(val)

        self.vals[key]=val
        self.vals2[val]=key
    
    # PRIVATE
    def is_compatible2(self,old_val2,new_val2):
        return True # everything is compatible


# descriptions
class DescriptionDictFile(DictFileTwoKeys):
    def format_val(self,key):
        return "%s \t%s"%(self.vals[key],key)

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,1)
        if len(arr)==0:
            return # empty line
        if len(arr)!=2:
            raise RuntimeError,"Not a valid description line: '%s'"%line

        return self.add(arr[1],arr[0])
    
# signatures
class SHA1DictFile(DictFile):
    def format_val(self,key):
        return "%s  %s"%(self.vals[key],key)

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,1)
        if len(arr)==0:
            return # empty line
        if len(arr)!=2:
            raise RuntimeError,"Not a valid SHA1 line: '%s'"%line

        return self.add(arr[1],arr[0])
    
# summary signatures
# values are (sha1,fname)
class SummarySHA1DictFile(DictFile):
    def add(self,key,val,allow_overwrite=False):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val
        if len(val)!=2:
            raise RuntimeError, "Values '%s' not (sha1,fname)"%val
        return DictFile.add(self,key,val,allow_overwrite)

    def format_val(self,key):
        return "%s  %s  %s"%(self.vals[key][0],self.vals[key][1],key)

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,2)
        if len(arr)==0:
            return # empty line
        if len(arr)!=3:
            raise RuntimeError,"Not a valid summary signature line (expected 4, found %i elements): '%s'"%(len(arr),line)

        key=arr[2]
        return self.add(key,(arr[0],arr[1]))

# file_list
class FileDictFile(DictFile):
    def format_val(self,key):
        if self.vals[key]!=None:
            return "%s %s"%(key,self.vals[key])
        else:
            return key

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,1)
        if len(arr)==0:
            return # empty line
        if len(arr[0])==0:
            return # empty key

        key=arr[0]
        if len(arr)==1:
            val=None
        else:
            val=arr[1]
        return self.add(key,val)

# subsystem
# values are (config_check,wnsubdir,config_out)
class SubsystemDictFile(DictFile):
    def add(self,key,val,allow_overwrite=False):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val
        if len(val)!=3:
            raise RuntimeError, "Values '%s' not (config_check,wnsubdir,config_out)"%val
        return DictFile.add(self,key,val,allow_overwrite)

    def format_val(self,key):
        return "%s %s %s %s"%(self.vals[key][0],self.vals[key][1],key,self.vals[key][2])# condor_vars

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,3)
        if len(arr)==0:
            return # empty line
        if len(arr)!=4:
            raise RuntimeError,"Not a valid subsystem line (expected 4, found %i elements): '%s'"%(len(arr),line)

        key=arr[2]
        return self.add(key,(arr[0],arr[1],arr[3]))

# values are (Type,Default,CondorName,Required,Export,UserName)
class VarsDictFile(DictFile):
    def is_compatible(self,old_val,new_val):
        return ((old_val[0]==new_val[0]) and (old_val[4]==new_val[4]))# at least the type and the export must be preserved
    
    def file_header(self):
        return ("# VarName               Type    Default         CondorName                     Req.     Export  UserName           \n"+
                "#                       S=Quote - = No Default  + = VarName                             Condor   - = Do not export \n"+
                "#                                                                                                + = Use VarName   \n"+
                "#                                                                                                @ = Use CondorName\n"
                "###################################################################################################################")

    def add(self,key,val,allow_overwrite=0):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val
        if len(val)!=6:
            raise RuntimeError, "Values '%s' not (Type,Default,CondorName,Required,Export,UserName)"%val
        if not (val[0] in ('C','S','I')):
            raise RuntimeError,"Invalid var type '%s', should be either C, S or I in val: %s"%(val[1],val)
        for i,t in ((3,"Required"),(4,"Export")):
            if not (val[i] in ('Y','N')):
                raise RuntimeError,"Invalid var %s '%s', should be either Y or N in val: %s"%(t,val[i],val)

        return DictFile.add(self,key,val,allow_overwrite)

    def format_val(self,key):
        return "%s \t%s \t%s \t\t%s \t%s \t%s \t%s"%(key,self.vals[key][0],self.vals[key][1],self.vals[key][2],self.vals[key][3],self.vals[key][4],self.vals[key][5])
        

    def parse_val(self,line):
        if len(line)==0:
            return #ignore emoty lines
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,6)
        if len(arr)==0:
            return # empty line
        if len(arr)!=7:
            raise RuntimeError,"Not a valid var line (expected 7, found %i elements): '%s'"%(len(arr),line)

        key=arr[0]
        return self.add(key,arr[1:])


################################################
#
# Functions that create default dictionaries
#
################################################

def get_main_dicts(submit_dir,stage_dir):
    main_dicts={'summary_signature':SummarySHA1DictFile(submit_dir,cgWConsts.SUMMARY_SIGNATURE_FILE),
                'attrs':DictFile(stage_dir,cgWConsts.ATTRS_FILE),
                'description':DescriptionDictFile(stage_dir,cgWConsts.DESCRIPTION_FILE),
                'consts':DictFile(stage_dir,cgWConsts.CONSTS_FILE),
                'params':DictFile(submit_dir,cgWConsts.PARAMS_FILE),
                'vars':VarsDictFile(stage_dir,cgWConsts.VARS_FILE),
                'file_list':FileDictFile(stage_dir,cgWConsts.FILE_LISTFILE),
                'script_list':FileDictFile(stage_dir,cgWConsts.SCRIPT_LISTFILE),
                'subsystem_list':SubsystemDictFile(stage_dir,cgWConsts.SUBSYSTEM_LISTFILE),
                "signature":SHA1DictFile(stage_dir,cgWConsts.SIGNATURE_FILE)}
    return main_dicts

def get_entry_dicts(submit_dir,stage_dir,entry_name):
    entry_submit_dir=cgWConsts.get_entry_submit_dir(submit_dir,entry_name)
    entry_stage_dir=cgWConsts.get_entry_stage_dir(stage_dir,entry_name)
    entry_dicts={'attrs':DictFile(entry_stage_dir,cgWConsts.ATTRS_FILE),
                 'description':DescriptionDictFile(entry_stage_dir,cgWConsts.DESCRIPTION_FILE),
                 'consts':DictFile(entry_stage_dir,cgWConsts.CONSTS_FILE),
                 'params':DictFile(entry_submit_dir,cgWConsts.PARAMS_FILE),
                 'vars':VarsDictFile(entry_stage_dir,cgWConsts.VARS_FILE),
                 'file_list':FileDictFile(entry_stage_dir,cgWConsts.FILE_LISTFILE),
                 'script_list':FileDictFile(entry_stage_dir,cgWConsts.SCRIPT_LISTFILE),
                 'subsystem_list':SubsystemDictFile(entry_stage_dir,cgWConsts.SUBSYSTEM_LISTFILE),
                 "signature":SHA1DictFile(entry_stage_dir,cgWConsts.SIGNATURE_FILE)}
    return entry_dicts

################################################
#
# Functions that load dictionaries
#
################################################

def load_main_dicts(main_dicts): # update in place
    # first submit dir ones (mutable)
    main_dicts['params'].load()
    # summary_signature has keys for description
    main_dicts['summary_signature'].load()
    # load the description
    main_dicts['description'].load(fname=main_dicts['summary_signature']['main'][1])
    # all others are keyed in the description
    main_dicts['signature'].load(fname=main_dicts['description'].vals2['signature'])
    main_dicts['attrs'].load(fname=main_dicts['description'].vals2['attrs_file'])
    main_dicts['consts'].load(fname=main_dicts['description'].vals2['consts_file'])
    main_dicts['vars'].load(fname=main_dicts['description'].vals2['condor_vars'])
    main_dicts['file_list'].load(fname=main_dicts['description'].vals2['file_list'])
    main_dicts['script_list'].load(fname=main_dicts['description'].vals2['script_list'])
    main_dicts['subsystem_list'].load(fname=main_dicts['description'].vals2['subsystem_list'])
    

def load_entry_dicts(entry_dicts,entry_name,summary_signature): # update in place
    # first submit dir ones (mutable)
    entry_dicts['params'].load()
    # load the description (name from summary_signature)
    entry_dicts['description'].load(summary_signature[entry_name][1])
    # all others are keyed in the description
    entry_dicts['signature'].load(fname=entry_dicts['description'].vals2['signature'])
    entry_dicts['attrs'].load(fname=entry_dicts['description'].vals2['attrs_file'])
    entry_dicts['consts'].load(fname=entry_dicts['description'].vals2['consts_file'])
    entry_dicts['vars'].load(fname=entry_dicts['description'].vals2['condor_vars'])
    entry_dicts['file_list'].load(fname=entry_dicts['description'].vals2['file_list'])
    entry_dicts['script_list'].load(fname=entry_dicts['description'].vals2['script_list'])
    entry_dicts['subsystem_list'].load(fname=entry_dicts['description'].vals2['subsystem_list'])
    

###########################################################
#
# CVS info
#
# $Id: cgWDictFile.py,v 1.4 2007/11/28 19:54:50 sfiligoi Exp $
#
# Log:
#  $Log: cgWDictFile.py,v $
#  Revision 1.4  2007/11/28 19:54:50  sfiligoi
#  Add load_entry_dicts
#
#  Revision 1.3  2007/11/28 19:45:19  sfiligoi
#  Add load_main_dicts
#
#  Revision 1.2  2007/11/27 19:58:51  sfiligoi
#  Move dicts initialization into cgWDictFile and entry subdir definition in cgWConsts
#
#  Revision 1.1  2007/10/25 22:28:27  sfiligoi
#  FIle dictionary classes
#
#
###########################################################
