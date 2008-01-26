#######################################################
#
# Glidein creation module
# Classes and functions needed to handle dictionary files
#
#######################################################

import os,os.path,shutil,string,popen2,copy
import sets,cStringIO
import cgWConsts

########################################
#
# File dictionary classes
#
########################################

class DictFile:
    def __init__(self,dir,fname,sort_keys=False,order_matters=False,
                 fname_idx=None):      # if none, use fname
        self.dir=dir
        self.fname=fname
        if fname_idx==None:
            fname_idx=fname
        self.fname_idx=fname_idx
        
        if sort_keys and order_matters:
            raise RuntimeError,"Cannot preserve the order and sort the keys" 
        self.sort_keys=sort_keys
        self.order_matters=order_matters

        self.is_readonly=False
        self.changed=True
        
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

    def get_filepath(self):
        return os.path.join(self.dir,self.fname)

    def erase(self):
        self.keys=[]
        self.vals={}
        self.changed=True
        
    def set_readonly(self,readonly=True):
        self.is_readonly=readonly


    def add(self,key,val,allow_overwrite=False):
        if key in self.keys:
            if self.vals[key]==val:
                return # already exists, nothing to do

        if self.is_readonly:
            raise RuntimeError, "Trying to modify a readonly object!"
        
        if key in self.keys:
            if not allow_overwrite:
                raise RuntimeError, "Key '%s' already exists"%key
            elif not self.is_compatible(self.vals[key],val):
                raise RuntimeError, "Key '%s': Value %s not compatible with old value %s"%(key,val,self.vals[key])
            if self.vals[key]==val:
                return # nothing to do
        else:
            self.keys.append(key)
        self.vals[key]=val
        self.changed=True
        
    def remove(self,key,fail_if_missing=False):
        if not (key in self.keys):
            if not fail_if_missing:
                raise RuntimeError, "Key '%s' does not exist"%key
            else:
                return # nothing to do

        self.keys.remove(key)
        del self.vals[key]
        self.changed=True

    def save(self, dir=None, fname=None,        # if dir and/or fname are not specified, use the defaults specified in __init__
             sort_keys=None,set_readonly=True,reset_changed=True,
             save_only_if_changed=True,
             want_comments=True): 
        if save_only_if_changed and (not self.changed):
            return # no change -> don't save

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
            self.save_into_fd(fd,sort_keys,set_readonly,reset_changed,want_comments)
        finally:
            fd.close()

        return

    def save_into_fd(self, fd,
                     sort_keys=None,set_readonly=True,reset_changed=True,
                     want_comments=True):
        if sort_keys==None:
            sort_keys=self.sort_keys

        header=self.file_header(want_comments)
        if header!=None:
            fd.write("%s\n"%header)
        if sort_keys:
            keys=self.keys[0:]
            keys.sort()
        else:
            keys=self.keys
        for k in keys:
            fd.write("%s\n"%self.format_val(k,want_comments))
        footer=self.file_footer(want_comments)
        if footer!=None:
            fd.write("%s\n"%footer)

        if set_readonly:
            self.set_readonly(True)

        if reset_changed:
            self.changed=False
        return

    def save_into_str(self,
                      sort_keys=None,set_readonly=True,reset_changed=True,
                      want_comments=True):
        fd=cStringIO.StringIO()
        self.save_into_fd(fd,sort_keys,set_readonly,reset_changed,want_comments)
        fd.seek(0)
        data=fd.read()
        fd.close()
        return data
    
    def load(self, dir=None, fname=None,
             change_self=True,        # if dir and/or fname are not specified, use the defaults specified in __init__, if they are, and change_self is True, change the self.
             erase_first=True,        # if True, delete old content first
             set_not_changed=True):   # if True, set self.changed to False
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
            try:
                self.load_from_fd(fd,erase_first,set_not_changed)
            except RuntimeError, e:
                raise RuntimeError, "File %s: %s"%(filepath,str(e))
        finally:
            fd.close()

        if change_self:
            self.dir=dir
            self.fname=fname

        return

    def load_from_fd(self, fd,
                     erase_first=True,        # if True, delete old content first
                     set_not_changed=True):   # if True, set self.changed to False
        if erase_first:
            self.erase()

        lines=fd.readlines()

        idx=0
        for line in lines:
            idx+=1
            if line[-1]=='\n':
                # strip newline
                line=line[:-1]
            try:
                self.parse_val(line)
            except RuntimeError, e:
                raise RuntimeError, "Line %i: %s"%(idx,str(e))

        if set_not_changed:
            self.changed=False # the memory copy is now same as the one on disk
        return

    def load_from_str(self, data,
                      erase_first=True,        # if True, delete old content first
                      set_not_changed=True):   # if True, set self.changed to False
        fd=cStringIO.StringIO()
        fd.write(data)
        fd.seek(0)
        try:
            self.load_from_fd(fd,erase_first,set_not_changed)
        except RuntimeError, e:
            raise RuntimeError, "Memory buffer: %s"%(filepath,str(e))
        fd.close()
        return        
        
    def is_equal(self,other,         # other must be of the same class
                 compare_dir=False,compare_fname=False,
                 compare_keys=None): # if None, use order_matters
        if compare_dir and (self.dir!=other.dir):
            return False
        if compare_fname and (self.fname!=other.fname):
            return False
        if compare_keys==None:
            compare_keys=self.order_matters
        if compare_keys and (self.keys!=other.keys):
            return False
        res=(self.save_into_str(sort_keys=None,set_readonly=False,reset_changed=False,want_comments=False)==other.save_into_str(sort_keys=None,set_readonly=False,reset_changed=False,want_comments=False))
        return res

    # PRIVATE
    def is_compatible(self,old_val,new_val):
        return True # everything is compatible
    
    def file_header(self,want_comments):
        if want_comments:
            return "# File: %s\n#"%self.fname
        else:
            return None
    
    def file_footer(self,want_comments):
        return None # no footer
    
    def format_val(self,key,want_comments):
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
    def __init__(self,dir,fname,sort_keys=False,order_matters=False,
                 fname_idx=None):      # if none, use fname
        DictFile.__init__(self,dir,fname,sort_keys,order_matters,fname_idx)
        self.keys2=[]
        self.vals2={}

    def has_key2(self,key):
        return key in self.keys2

    def get_val2(self,key):
        return self.vals2[key]

    def erase(self):
        DictFile.erase(self)
        self.keys2=[]
        self.vals2={}

    def add(self,key,val,allow_overwrite=False):
        if key in self.keys:
            if self.vals[key]==val:
                return # already exists, nothing to do

        if self.is_readonly:
            raise RuntimeError, "Trying to modify a readonly object!"
        
        if key in self.keys:
            old_val=self.vals[key]
            if not allow_overwrite:
                raise RuntimeError, "Key '%s' already exists"%key
            elif not self.is_compatible(old_val,val):
                raise RuntimeError, "Key '%s': Value %s not compatible with old value %s"%(key,val,old_val)
            if old_val==val:
                return # nothing to be changed
            # the second key changed, need to delete the old one
            self.keys2.remove(old_val)
            del self.vals2[old_val]
        else:
            self.keys.append(key)
        self.vals[key]=val

        if val in self.keys2:
            old_key=self.vals2[val]
            if not allow_overwrite:
                raise RuntimeError, "Value '%s' already exists"%val
            elif not self.is_compatible2(old_key,key):
                raise RuntimeError, "Value '%s': Key %s not compatible with old key %s"%(val,key,old_key)
            #if old_key==key: # no need to change again, would have hit the check above
            #    return # nothing to be changed
            # the first key changed, need to delete the old one
            self.keys.remove(old_key)
            del self.vals[old_key]
        else:
            self.keys2.append(val)
        self.vals2[val]=key
        self.changed=True
    
    def remove(self,key,fail_if_missing=False):
        if not (key in self.keys):
            if not fail_if_missing:
                raise RuntimeError, "Key '%s' does not exist"%key
            else:
                return # nothing to do

        val=self.vals[key]

        self.keys.remove(key)
        del self.vals[key]
        self.keys2.remove(val)
        del self.vals2[val]
        self.changed=True

    def is_equal(self,other,         # other must be of the same class
                 compare_dir=False,compare_fname=False,
                 compare_keys=None): # if None, use order_matters
        if compare_dir and (self.dir!=other.dir):
            return False
        if compare_fname and (self.fname!=other.fname):
            return False
        if compare_keys==None:
            compare_keys=self.order_matters
        if compare_keys and ((self.keys!=other.keys) or (self.keys2!=other.keys2)):
            return False
        res=(self.save_into_str(sort_keys=None,set_readonly=False,reset_changed=False,want_comments=False)==other.save_into_str(sort_keys=None,set_readonly=False,reset_changed=False,want_comments=False))
        return res
        
    # PRIVATE
    def is_compatible2(self,old_val2,new_val2):
        return True # everything is compatible


# descriptions
class DescriptionDictFile(DictFileTwoKeys):
    def format_val(self,key,want_comments):
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
    
##############################
# Execute a command in a shell
def exe_cmd(cmd):
    childout, childin, childerr = popen2.popen3(cmd)
    childin.close()
    tempOut = childout.readlines()
    childout.close()
    tempErr = childerr.readlines()
    childerr.close()
    if (len(tempErr)!=0):
        raise RuntimeError, "Error running '%s'\n%s"%(cmd,tempErr)
    return tempOut
#################################
# Calculate SHA1 for the file
def calc_sha1(filepath):
    # older versions of python don't support sha1 natively :(
    try:
        sha1=string.split(exe_cmd("sha1sum %s"%filepath)[0])[0]
    except RuntimeError, e:
        raise RuntimeError, "Error calculating SHA1 for %s: %s"%(filepath,e)
    return sha1
##################################

# signatures
class SHA1DictFile(DictFile):
    def add_from_file(self,filepath,allow_overwrite=False,
                      key=None): # if key==None, use basefname
        sha1=calc_sha1(filepath)
        if key==None:
            key=os.path.basename(filepath)
        self.add(key,sha1,allow_overwrite)

    def format_val(self,key,want_comments):
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
# values are (sha1,fname2)
class SummarySHA1DictFile(DictFile):
    def add(self,key,val,allow_overwrite=False):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val
        if len(val)!=2:
            raise RuntimeError, "Values '%s' not (sha1,fname)"%val
        return DictFile.add(self,key,val,allow_overwrite)

    def add_from_file(self,filepath,
                      fname2=None, # if fname2==None, use basefname
                      allow_overwrite=False,
                      key=None):   # if key==None, use basefname
        sha1=calc_sha1(filepath)
        if key==None:
            key=os.path.basename(filepath)        
        if fname2==None:
            fname2=os.path.basename(filepath)        
        DictFile.add(self,key,(sha1,fname2),allow_overwrite)

    def format_val(self,key,want_comments):
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

# file list
# also hold the content of the file as the last entry in vals
class SimpleFileDictFile(DictFile):
    def get_immutable_files(self):
        return self.keys # keys are files, and all are immutable in this implementation

    def add(self,key, # key is filename in this case
            val,allow_overwrite=False):
        return self.add_from_file(key,val,os.path.join(self.dir,key),allow_overwrite)

    def add_from_str(self,key,val,
                    data, 
                    allow_overwrite=False):
        # make it generic for use by children
        if not (type(val) in (type(()),type([]))):
            DictFile.add(self,key,(val,data),allow_overwrite)
        else:
            DictFile.add(self,key,tuple(val)+(data,),allow_overwrite)

    def add_from_fd(self,key,val,
                    fd, # open file object that has a read() method
                    allow_overwrite=False):
        data=fd.read()
        self.add_from_str(key,val,data,allow_overwrite)

    def add_from_file(self,key,val,
                      filepath,
                      allow_overwrite=False):
        try:
            fd=open(filepath,"r")
        except IOError,e:
            raise RuntimeError,"Could not open file %s"%filepath
        try:
            self.add_from_fd(key,val,fd,allow_overwrite)
        finally:
            fd.close()

    def format_val(self,key,want_comments):
        if self.vals[key][0]!=None:
            return "%s %s"%(key,self.vals[key][0])
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

    def save_files(self,allow_overwrite=False):
        for key in self.keys:
            fname=self.get_file_fname(key)
            fdata=self.vals[key][-1]
            filepath=os.path.join(self.dir,fname)
            if (not allow_overwrite) and os.path.exists(filepath):
                raise RuntimeError,"File %s already exists"%filepath
            try:
                fd=open(filepath,"w")
            except IOError,e:
                raise RuntimeError,"Could not create file %s"%filepath
            try:
                try:
                    fd.write(fdata)
                except IOError,e:
                    raise RuntimeError,"Error writing into file %s"%filepath
            finally:
                fd.close()

    def get_file_fname(self,key):
        return key

# file list
# This one contains (real_fname,cache/exec,cond_download,config_out)
# cache/exec should be one of: regular, nocache, exec, untar
# cond_download has a special value of TRUE
# config_out has a special value of FALSE
class FileDictFile(SimpleFileDictFile):
    def add_placeholder(self,key,allow_overwrite=True):
        DictFile.add(self,key,("","","","",""),allow_overwrite)

    def is_placeholder(self,key):
        return (self[key][0]=="") # empty real_fname can only be a placeholder

    def add(self,key,
            val,     # will if len(val)==5, use the last one as data, else load from val[0]
            allow_overwrite=False,
            allow_overwrite_placeholder=True):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val

        if self.is_placeholder(key) and allow_overwrite_placeholder:
            allow_overwrite=True # since the other functions know nothing about placeholders, need to force overwrite
        
        if len(val)==5:
            return self.add_from_str(key,val[:4],val[4],allow_overwrite)
        elif len(val)==4:
            return self.add_from_file(key,val,os.path.join(self.dir,val[0]),allow_overwrite)
        else:
            raise RuntimeError, "Values '%s' not (real_fname,cache/exec,cond_download,config_out)"%val

    def format_val(self,key,want_comments):
        return "%s %s %s %s %s"%(key,self.vals[key][0],self.vals[key][1],self.vals[key][2],self.vals[key][3])

    def parse_val(self,line):
        if line[0]=='#':
            return # ignore comments
        arr=line.split(None,4)
        if len(arr)==0:
            return # empty line
        if len(arr[0])==0:
            return # empty key

        if len(arr)!=5:
            raise RuntimeError,"Not a valid file line (expected 5, found %i elements): '%s'"%(len(arr),line)

        return self.add(arr[0],arr[1:])

    def get_file_fname(self,key):
        return self.vals[key][0]

    def get_immutable_files(self):
        mkeys=[]
        for k in self.keys:
            val=self.vals[k][1]
            if (val!="nocache"):
                mkeys.append(self.vals[k][0]) # file name is not the key, but the first entry
            
        return mkeys

    def reuse(self,other,
              compare_dir=False,compare_fname=False,
              compare_files_fname=False):
        if compare_dir and (self.dir!=other.dir):
            return # nothing to do, different dirs
        if compare_fname and (self.fname!=other.fname):
            return # nothing to do, different fnames

        for k in self.keys:
            if k in other.keys:
                # the other has the same key, check if they are the same
                if compare_files_fname:
                    is_equal=(self.vals[k]==other.vals[k])
                else: # ignore file name (first element)
                    is_equal=(self.vals[k][1:]==other.vals[k][1:])

                if is_equal:
                    self.vals[k]=copy.deepcopy(other.vals[k])
                # else they are different and there is nothing to be done
                    
        return
            
# will convert values into python format before writing them out
class ReprDictFile(DictFile):
    def format_val(self,key,want_comments):
        return "%s \t%s"%(key,repr(self.vals[key]))

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
        return self.add(key,eval(val))

# will hold only strings
class StrDictFile(DictFile):
    def add(self,key,val,allow_overwrite=False):
        DictFile.add(self,key,str(val),allow_overwrite)

# values are (Type,Default,CondorName,Required,Export,UserName)
class VarsDictFile(DictFile):
    def is_compatible(self,old_val,new_val):
        return ((old_val[0]==new_val[0]) and (old_val[4]==new_val[4]))# at least the type and the export must be preserved
    
    def file_header(self,want_comments):
        if want_comments:
            return ("# VarName               Type    Default         CondorName                     Req.     Export  UserName           \n"+
                    "#                       S=Quote - = No Default  + = VarName                             Condor   - = Do not export \n"+
                    "#                                                                                                + = Use VarName   \n"+
                    "#                                                                                                @ = Use CondorName\n"
                    "###################################################################################################################")
        else:
            return None

    def add(self,key,val,allow_overwrite=0):
        if not (type(val) in (type(()),type([]))):
            raise RuntimeError, "Values '%s' not a list or tuple"%val
        if len(val)!=6:
            raise RuntimeError, "Values '%s' not (Type,Default,CondorName,Required,Export,UserName)"%str(val)
        if not (val[0] in ('C','S','I')):
            raise RuntimeError,"Invalid var type '%s', should be either C, S or I in val: %s"%(val[1],str(val))
        for i,t in ((3,"Required"),(4,"Export")):
            if not (val[i] in ('Y','N')):
                raise RuntimeError,"Invalid var %s '%s', should be either Y or N in val: %s"%(t,val[i],str(val))

        return DictFile.add(self,key,val,allow_overwrite)

    def add_extended(self,key,
                     is_string,
                     val_default, # None or False==No default (i.e. -)
                     condor_name, # if None or false, Varname (i.e. +)
                     required,
                     export_condor,
                     user_name,   # If None or false, do not export (i.e. -)
                                  # if True, set to VarName (i.e. +)
                     allow_overwrite=0):
        if is_string:
            type_str='S'
        else:
            type_str='I'
            
        if (val_default==None) or (val_default==False):
            val_default='-'
            
        if (condor_name==None) or (condor_name==False):
            condor_name="+"
            
        if required:
            req_str='Y'
        else:
            req_str='N'
            
        if export_condor:
            export_condor_str='Y'
        else:
            export_condor_str='N'

        if (user_name==None) or (user_name==False):
            user_name='-'
        elif user_name==True:
            user_name='+'
            
        self.add(key,(type_str,val_default,condor_name,req_str,export_condor_str,user_name),allow_overwrite)
        
    def format_val(self,key,want_comments):
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


class CondorJDLDictFile(DictFile):
    def __init__(self,dir,fname,sort_keys=False,order_matters=False,jobs_in_cluster=None,
                 fname_idx=None):      # if none, use fname
        DictFile.__init__(self,dir,fname,sort_keys,order_matters,fname_idx)
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
            return DictFile.is_equal(other,compare_dir,compare_fname,compare_keys)
        else:
            return False

################################################
#
# Functions that create default dictionaries
#
################################################

# internal, do not use from outside the module
def get_common_dicts(submit_dir,stage_dir):
    common_dicts={'attrs':ReprDictFile(submit_dir,cgWConsts.ATTRS_FILE),
                  'description':DescriptionDictFile(stage_dir,cgWConsts.insert_timestr(cgWConsts.DESCRIPTION_FILE),fname_idx=cgWConsts.DESCRIPTION_FILE),
                  'consts':StrDictFile(stage_dir,cgWConsts.insert_timestr(cgWConsts.CONSTS_FILE),fname_idx=cgWConsts.CONSTS_FILE),
                  'params':ReprDictFile(submit_dir,cgWConsts.PARAMS_FILE),
                  'vars':VarsDictFile(stage_dir,cgWConsts.insert_timestr(cgWConsts.VARS_FILE),fname_idx=cgWConsts.VARS_FILE),
                  'untar_cfg':StrDictFile(stage_dir,cgWConsts.insert_timestr(cgWConsts.UNTAR_CFG_FILE),fname_idx=cgWConsts.UNTAR_CFG_FILE),
                  'file_list':FileDictFile(stage_dir,cgWConsts.insert_timestr(cgWConsts.FILE_LISTFILE),fname_idx=cgWConsts.FILE_LISTFILE),
                  "signature":SHA1DictFile(stage_dir,cgWConsts.insert_timestr(cgWConsts.SIGNATURE_FILE),fname_idx=cgWConsts.SIGNATURE_FILE)}
    refresh_description(common_dicts)
    return common_dicts

def get_main_dicts(submit_dir,stage_dir):
    main_dicts=get_common_dicts(submit_dir,stage_dir)
    main_dicts['summary_signature']=SummarySHA1DictFile(submit_dir,cgWConsts.SUMMARY_SIGNATURE_FILE)
    main_dicts['glidein']=StrDictFile(submit_dir,cgWConsts.GLIDEIN_FILE)
    return main_dicts

def get_entry_dicts(entry_submit_dir,entry_stage_dir,entry_name):
    entry_dicts=get_common_dicts(entry_submit_dir,entry_stage_dir)
    entry_dicts['job_descript']=StrDictFile(entry_submit_dir,cgWConsts.JOB_DESCRIPT_FILE)
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
    dicts['consts'].load(fname=file_el[cgWConsts.CONSTS_FILE][0])
    dicts['vars'].load(fname=file_el[cgWConsts.VARS_FILE][0])
    dicts['untar_cfg'].load(fname=file_el[cgWConsts.UNTAR_CFG_FILE][0])

def load_main_dicts(main_dicts): # update in place
    main_dicts['glidein'].load()
    # summary_signature has keys for description
    main_dicts['summary_signature'].load()
    # load the description
    main_dicts['description'].load(fname=main_dicts['summary_signature']['main'][1])
    # all others are keyed in the description
    load_common_dicts(main_dicts,main_dicts['description'])

def load_entry_dicts(entry_dicts,                   # update in place
                     entry_name,summary_signature): 
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
    description_dict.add(dicts['file_list'].get_fname(),"file_list",allow_overwrite=True)

def refresh_file_list(dicts,is_main, # update in place
                      files_set_readonly=True,files_reset_changed=True):
    entry_str="_ENTRY"
    if is_main:
        entry_str=""
    file_dict=dicts['file_list']
    file_dict.add(cgWConsts.CONSTS_FILE,(dicts['consts'].get_fname(),"regular","TRUE","CONSTS%s_FILE"%entry_str,dicts['consts'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)
    file_dict.add(cgWConsts.VARS_FILE,(dicts['vars'].get_fname(),"regular","TRUE","CONDOR_VARS%s_FILE"%entry_str,dicts['vars'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)
    file_dict.add(cgWConsts.UNTAR_CFG_FILE,(dicts['untar_cfg'].get_fname(),"regular","TRUE","UNTAR_CFG%s_FILE"%entry_str,dicts['untar_cfg'].save_into_str(set_readonly=files_set_readonly,reset_changed=files_reset_changed)),allow_overwrite=True)

# dictionaries must have been written to disk before using this
def refresh_signature(dicts): # update in place
    signature_dict=dicts['signature']
    for k in ('consts','vars','untar_cfg','file_list','description'):
        signature_dict.add_from_file(dicts[k].get_filepath(),allow_overwrite=True)
    # add signatures of all the files linked in the lists
    for k in ('file_list',):
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
    for k in ('file_list',):
        dicts[k].save_files(allow_overwrite=True)
    # then save the lists
    for k in ('file_list',):
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
    all_reused=reuse_file_dict(dicts,other_dicts,'file_list') and all_reused

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
    all_reused=reuse_common_dicts(entry_dicts, other_entry_dicts,False,True)
    return all_reused

################################################
#
# Handle dicts as Classes
#
################################################

# internal, do not use directly from outside the module
class glideinCommonDicts:
    def __init__(self):
        self.dicts=None
        self.submit_dir=None
        self.stage_dir=None
        raise RuntimeError, "glideinCommonDicts should never be directly used"
        
    def keys(self):
        return self.dicts.keys()

    def has_key(self,key):
        return self.dicts.has_key(key)

    def __getitem__(self,key):
        return self.dicts[key]        

    def set_readonly(self,readonly=True):
        for el in self.dicts.values():
            el.set_readonly(readonly)

    def create_dirs(self):
        try:
            os.mkdir(self.submit_dir)
            try:
                os.mkdir(os.path.join(self.submit_dir,'log'))
                os.mkdir(self.stage_dir)
            except:
                shutil.rmtree(self.submit_dir)
                raise
        except OSError,e:
            raise RuntimeError,"Failed to create dir: %s"%e

    def delete_dirs(self):
        shutil.rmtree(self.submit_dir)
        shutil.rmtree(self.stage_dir)


class glideinMainDicts(glideinCommonDicts):
    def __init__(self,submit_dir,stage_dir):
        self.submit_dir=submit_dir
        self.stage_dir=stage_dir
        self.erase()

    def get_summary_signature(self): # you can discover most of the other things from this
        return self.dicts['summary_signature']

    def erase(self):
        self.dicts=get_main_dicts(self.submit_dir,self.stage_dir)
    
    def load(self):
        load_main_dicts(self.dicts)

    def save(self,set_readonly=True):
        save_main_dicts(self.dicts,set_readonly=set_readonly)

    def is_equal(self,other,             # other must be of the same class
                 compare_submit_dir=False,compare_stage_dir=False,
                 compare_fnames=False): 
        if compare_submit_dir and (self.submit_dir!=other.submit_dir):
            return False
        if compare_stage_dir and (self.stage_dir!=other.stage_dir):
            return False
        for k in self.dicts.keys():
            if not self.dicts[k].is_equal(other.dicts[k],compare_dir=False,compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.submit_dir!=other.submit_dir:
            raise RuntimeError,"Cannot change main submit base_dir! '%s'!='%s'"%(self.submit_dir,other.submit_dir)
        if self.stage_dir!=other.stage_dir:
            raise RuntimeError,"Cannot change main stage base_dir! '%s'!='%s'"%(self.stage_dir,other.stage_dir)

        reuse_main_dicts(self.dicts,other.dicts)
        
class glideinEntryDicts(glideinCommonDicts):
    def __init__(self,
                 glidein_main_dicts, # must be an instance of glideinMainDicts
                 entry_name):
        self.entry_name=entry_name
        self.glidein_main_dicts=glidein_main_dicts
        self.submit_dir=cgWConsts.get_entry_submit_dir(glidein_main_dicts.submit_dir,entry_name)
        self.stage_dir=cgWConsts.get_entry_stage_dir(glidein_main_dicts.stage_dir,entry_name)
        self.erase()

    def erase(self):
        self.dicts=get_entry_dicts(self.submit_dir,self.stage_dir,self.entry_name)
    
    def load(self): #will use glidein_main_dicts data, so it must be loaded first
        load_entry_dicts(self.dicts,self.entry_name,self.glidein_main_dicts.get_summary_signature())

    def save(self,set_readonly=True):
        save_entry_dicts(self.dicts,self.entry_name,self.glidein_main_dicts.get_summary_signature(),set_readonly=set_readonly)

    def save_final(self,set_readonly=True):
        pass # not needed here, but may be needed by children
    
    def is_equal(self,other,             # other must be of the same class
                 compare_entry_name=False,
                 compare_glidein_main_dicts=False, # if set to True, will do a complete check on the related objects
                 compare_fnames=False): 
        if compare_entry_name and (self.entry_name!=other.entry_name):
            return False
        if compare_glidein_main_dicts and (self.glidein_main_dicts.is_equal(other.glidein_main_dicts,compare_submit_dir=True,compare_stage_dir=True,compare_fnames=compare_fnames)):
            return False
        for k in self.dicts.keys():
            if not self.dicts[k].is_equal(other.dicts[k],compare_dir=False,compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.submit_dir!=other.submit_dir:
            raise RuntimeError,"Cannot change entry submit base_dir! '%s'!='%s'"%(self.submit_dir,other.submit_dir)
        if self.stage_dir!=other.stage_dir:
            raise RuntimeError,"Cannot change entry stage base_dir! '%s'!='%s'"%(self.stage_dir,other.stage_dir)

        reuse_entry_dicts(self.dicts,other.dicts,self.entry_name)
        
################################################
#
# This Class contains both the main and
# the entry dicts
#
################################################

class glideinDicts:
    def __init__(self,submit_dir,stage_dir,entry_list=[]):
        self.submit_dir=submit_dir
        self.stage_dir=stage_dir
        self.main_dicts=glideinMainDicts(self.submit_dir,self.stage_dir)
        self.entry_list=entry_list[:]
        self.entry_dicts={}
        for entry_name in entry_list:
            self.entry_dicts[entry_name]=glideinEntryDicts(self.main_dicts,entry_name)
        return

    def set_readonly(self,readonly=True):
        self.main_dicts.set_readonly(readonly)
        for el in self.entry_dicts.values():
            el.set_readonly(readonly)

    def erase(self,destroy_old_entries=True): # if false, the entry names will be preserved
        self.main_dicts.erase()
        if destroy_old_entries:
            self.entry_list=[]
            self.entry_dicts={}
        else:
            for entry_name in self.entry_list:
                self.entry_dicts[entry_name].erase()
        return

    def load(self,destroy_old_entries=True): # if false, overwrite the entries you load, but leave the others as they are
        self.main_dicts.load()
        if destroy_old_entries:
            self.entry_list=[]
            self.entry_dicts={}
        # else just leave as it is, will rewrite just the loaded ones

        for sign_key in self.main_dicts.get_summary_signature().keys:
            if sign_key!='main': # main is special, not an entry
                entry_name=cgWConsts.get_entry_name_from_entry_stage_dir(sign_key)
                if not(entry_name in self.entry_list):
                    self.entry_list.append(entry_name)
                self.entry_dicts[entry_name]=self.new_entry(entry_name)
                self.entry_dicts[entry_name].load()



    def save(self,set_readonly=True):
        for entry_name in self.entry_list:
            self.entry_dicts[entry_name].save(set_readonly=set_readonly)
        self.main_dicts.save(set_readonly=set_readonly)
        for entry_name in self.entry_list:
            self.entry_dicts[entry_name].save_final(set_readonly=set_readonly)
   
    def create_dirs(self):
        self.main_dicts.create_dirs()
        try:
            for entry_name in self.entry_list:
                self.entry_dicts[entry_name].create_dirs()
        except:
            self.main_dicts.delete_dirs() # this will clean up also any created entries
            raise
        
    def delete_dirs(self):
        self.main_dicts.delete_dirs() # this will clean up also all entries

    def is_equal(self,other,             # other must be of the same class
                 compare_submit_dir=False,compare_stage_dir=False,
                 compare_fnames=False): 
        if compare_submit_dir and (self.submit_dir!=other.submit_dir):
            return False
        if compare_stage_dir and (self.stage_dir!=other.stage_dir):
            return False
        if not self.main_dicts.is_equal(other.main_dicts,compare_submit_dir=False,compare_stage_dir=False,compare_fnames=compare_fnames):
            return False
        my_entries=self.entry_list[:]
        other_entries=other.entry_list[:]
        if len(my_entries)!=len(other_entries):
            return False

        my_entries.sort()
        other_entries.sort()
        if my_entries!=other_entries: # need to be in the same order to make a comparison
            return False
        
        for k in my_entries:
            if not self.entry_dicts[k].is_equal(other.entry_dicts[k],compare_entry_name=False,
                                                compare_glidein_main_dicts=False,compare_fname=compare_fnames):
                return False
        return True

    # reuse as much of the other as possible
    def reuse(self,other):             # other must be of the same class
        if self.submit_dir!=other.submit_dir:
            raise RuntimeError,"Cannot change submit base_dir! '%s'!='%s'"%(self.submit_dir,other.submit_dir)
        if self.stage_dir!=other.stage_dir:
            raise RuntimeError,"Cannot change stage base_dir! '%s'!='%s'"%(self.stage_dir,other.stage_dir)

        # compare main dictionaires
        self.main_dicts.reuse(other.main_dicts)

        # compare entry dictionaires
        for k in self.entry_list:
            if k in other.entry_list:
                self.entry_dicts[k].reuse(other.entry_dicts[k])
            else:
                # nothing to reuse, but must create dir
                self.entry_dicts[k].create_dirs()

    ###########
    # PRIVATE
    ###########

    # return a new entry object
    def new_entry(self,entry_name):
        return glideinEntryDicts(self.main_dicts,entry_name)
    
###########################################################
#
# CVS info
#
# $Id: cgWDictFile.py,v 1.80 2008/01/26 02:10:56 sfiligoi Exp $
#
# Log:
#  $Log: cgWDictFile.py,v $
#  Revision 1.80  2008/01/26 02:10:56  sfiligoi
#  Allow overwrite of placeholders
#
#  Revision 1.79  2008/01/25 21:45:35  sfiligoi
#  Move the grid-mapfile before setup_x509.sh; this added the remove method to DictFile and is_placeholder to FileDictFile
#
#  Revision 1.78  2007/12/31 15:37:03  sfiligoi
#  Properly handle partial evaluation of booleans
#
#  Revision 1.77  2007/12/31 15:33:48  sfiligoi
#  Fix bug
#
#  Revision 1.76  2007/12/28 20:46:21  sfiligoi
#  Implement reuse of description and signature.
#
#  Revision 1.75  2007/12/26 15:31:11  sfiligoi
#  Add support for new entries in reuse
#
#  Revision 1.74  2007/12/26 11:27:47  sfiligoi
#  Add want_comments
#
#  Revision 1.72  2007/12/26 11:11:36  sfiligoi
#  Compare on saved string
#
#  Revision 1.70  2007/12/26 10:06:37  sfiligoi
#  Allow updates with identical values on readonly objects
#
#  Revision 1.68  2007/12/26 09:53:42  sfiligoi
#  Improve file_list reuse
#
#  Revision 1.66  2007/12/26 09:16:51  sfiligoi
#  Improve reuse
#
#  Revision 1.65  2007/12/22 20:53:20  sfiligoi
#  Add missing module
#
#  Revision 1.64  2007/12/22 20:48:14  sfiligoi
#  consts, untar_cfg and vars dicts now get saved via file_list
#
#  Revision 1.63  2007/12/22 20:33:35  sfiligoi
#  Add string load/save
#
#  Revision 1.62  2007/12/21 21:16:04  sfiligoi
#  Add fname_idx to Dict.__init__
#
#  Revision 1.61  2007/12/21 21:06:56  sfiligoi
#  Add load_from_str and save_into_str
#
#  Revision 1.58  2007/12/21 18:46:33  sfiligoi
#  Add save_into_fd and load_from_fd
#
#  Revision 1.54  2007/12/21 12:14:09  sfiligoi
#  Load now uses file_list
#
#  Revision 1.53  2007/12/20 16:42:14  sfiligoi
#  Update reuse
#
#  Revision 1.52  2007/12/17 21:50:17  sfiligoi
#  Fix untar cfg handling
#
#  Revision 1.51  2007/12/17 20:50:28  sfiligoi
#  Move subsystems into the file_list and add untar_cfg
#
#  Revision 1.50  2007/12/17 20:32:02  sfiligoi
#  Add a deafult header to all files, this way we don't have empty files
#
#  Revision 1.48  2007/12/17 15:57:39  sfiligoi
#  Fix get_immutable_files
#
#  Revision 1.46  2007/12/14 22:46:33  sfiligoi
#  Temporary fix for special file handling
#
#  Revision 1.42  2007/12/14 22:28:08  sfiligoi
#  Change file_list format and remove script_list (merged into file_list now)
#
#  Revision 1.41  2007/12/14 18:35:43  sfiligoi
#  First steps toward reuse, and fixed CondorJDLDictFile.is_equal
#
#  Revision 1.39  2007/12/14 16:28:53  sfiligoi
#  Move directory creation into the Dict classes
#
#  Revision 1.38  2007/12/14 14:36:11  sfiligoi
#  Make saving optional if the dictionary has not been changed
#
#  Revision 1.35  2007/12/13 23:26:20  sfiligoi
#  Get attributes out of stage and only into submit
#
#  Revision 1.33  2007/12/13 20:18:15  sfiligoi
#  Add CondorJDLDictFile class, add set_readonly to save, and add glideinEntryDicts.save_final
#
#  Revision 1.31  2007/12/12 00:07:30  sfiligoi
#  Add glidein and job_descript dictionaries
#
#  Revision 1.30  2007/12/11 23:47:52  sfiligoi
#  Rename entry_dirs to have local scope
#
#  Revision 1.29  2007/12/11 23:31:47  sfiligoi
#  Create entry_dirs in a single place
#
#  Revision 1.28  2007/12/11 23:03:01  sfiligoi
#  Add entry order in glideins and make erase more general
#
#  Revision 1.27  2007/12/11 19:16:06  sfiligoi
#  Simplify attribute handling
#
#  Revision 1.23  2007/12/10 21:23:15  sfiligoi
#  Move sha1 calculations at the final stage
#
#  Revision 1.22  2007/12/10 19:47:06  sfiligoi
#  Move file list maintenance to the proper place
#
#  Revision 1.21  2007/12/10 19:38:18  sfiligoi
#  Put file handling in cgWDictFile
#
#  Revision 1.20  2007/12/03 23:57:27  sfiligoi
#  Properly initialize file_list
#
#  Revision 1.16  2007/12/03 21:52:13  sfiligoi
#  Move sha1 calculations into ...SHA1DictFile.add_from_file
#
#  Revision 1.15  2007/12/03 21:41:40  sfiligoi
#  Implement the save methods, add sha1 calculation and fix DictFileTwoKeys.add
#
#  Revision 1.14  2007/12/03 20:15:00  sfiligoi
#  Change create_description in refresh_description and use it
#
#  Revision 1.13  2007/12/03 19:49:20  sfiligoi
#  Added create_description, plus a little bit of cleanup
#
#  Revision 1.2  2007/11/27 19:58:51  sfiligoi
#  Move dicts initialization into cgWDictFile and entry subdir definition in cgWConsts
#
#  Revision 1.1  2007/10/25 22:28:27  sfiligoi
#  FIle dictionary classes
#
#
###########################################################
