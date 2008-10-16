import os
import copy
import sys
import os.path
import string
import socket
import types
import traceback
import xmlParse
import xml.parsers.expat
import xmlFormat
import condorExe

class SubParams:
    def __init__(self,data):
        self.data=data

    def __eq__(self,other):
        if other==None:
            return False
        if not isinstance(other,SubParams):
            return False
        return self.data==other.data

    # make data elements look like class attributes
    def __getattr__(self,name):
        return self.get_el(name)

    # make data elements look like a dictionary
    def keys(self):
        return self.data.keys()
    def has_key(self,name):
        return self.data.has_key(name)
    def __getitem__(self,name):
        return self.get_el(name)    
    def __repr__(self):
        return str(self.data)
    def __str__(self):
        return str(self.data)

    #
    # PROTECTED
    #

    # validate input against bae template (i.e. the defaults)
    def validate(self,base,path_text):
        for k in self.data.keys():
            if not base.has_key(k):
                # element not in base, report
                raise RuntimeError, "Unknown parameter %s.%s"%(path_text,k)
            else:
                # verify subelements, if any
                defel=base[k]
                if isinstance(defel,xmlParse.OrderedDict):
                    # subdictionary
                    self[k].validate(defel,"%s.%s"%(path_text,k))
                else:
                    # final element
                    defvalue,ktype,txt,subdef=defel

                    if isinstance(defvalue,xmlParse.OrderedDict):
                        # dictionary el elements
                        data_el=self[k]
                        for data_subkey in data_el.keys():
                            data_el[data_subkey].validate(subdef,"%s.%s.%s"%(path_text,k,data_subkey))
                    elif type(defvalue)==type([]):
                        # list of elements
                        if isinstance(self.data[k],xmlParse.OrderedDict):
                            if len(self.data[k].keys())==0:
                                self.data[k]=[]  #XML does not know if an empty list is a dictionary or not.. fix this

                        mylist=self[k]
                        if type(mylist)!=type([]):
                            raise RuntimeError, "Parameter %s.%s not a list: %s %s"%(path_text,k,type(mylist),mylist)
                        for data_el in mylist:
                            data_el.validate(subdef,"%s.*.%s"%(path_text,k))
                    else:
                        # a simple value
                        pass #nothing to be done

    # put default values where there is nothing
    def use_defaults(self,defaults):
        for k in defaults.keys():
            defel=defaults[k]
            if isinstance(defel,xmlParse.OrderedDict):
                # subdictionary
                if not self.data.has_key(k):
                    self.data[k]=xmlParse.OrderedDict() # first create empty, if does not exist

                # then, set defaults on all elements of subdictionary
                self[k].use_defaults(defel)
            else:
                # final element
                defvalue,ktype,txt,subdef=defel

                if isinstance(defvalue,xmlParse.OrderedDict):
                    # dictionary el elements
                    if not self.data.has_key(k):
                        self.data[k]=xmlParse.OrderedDict() # no elements yet, set and empty dictionary
                    else:
                        # need to set defaults on all elements in the dictionary
                        data_el=self[k]
                        for data_subkey in data_el.keys():
                            data_el[data_subkey].use_defaults(subdef)
                elif type(defvalue)==type([]):
                    # list of elements
                    if not self.data.has_key(k):
                        self.data[k]=[] # no elements yet, set and empty list
                    else:
                        # need to set defaults on all elements in the list
                        mylist=self[k]
                        for data_el in self[k]:
                            data_el.use_defaults(subdef)
                else:
                    # a simple value
                    if not self.data.has_key(k):
                        self.data[k]=copy.deepcopy(defvalue)
                    # else nothing to do, already set

            

    #
    # PRIVATE
    #
    def get_el(self,name):
        el=self.data[name]
        if isinstance(el,xmlParse.OrderedDict):
            return SubParams(el)
        elif type(el)==type([]):
            outlst=[]
            for k in el:
                if isinstance(k,xmlParse.OrderedDict):
                    outlst.append(SubParams(k))
                else:
                    outlst.append(k)
            return outlst
        else:
            return el

class Params:
    def __init__(self,usage_prefix,src_dir,argv):
        self.usage_prefix=usage_prefix
        self.attr_defaults=xmlParse.OrderedDict()
        self.attr_defaults["value"]=(None,"Value","Value of the attribute (string)",None)
        self.attr_defaults["publish"]=("True","Bool","Should it be published by the factory?",None)
        self.attr_defaults["parameter"]=("True","Bool","Should it be a parameter for the glidein?",None)
        self.attr_defaults["glidein_publish"]=("False","Bool","Should it be published by the glidein? (Used only if parameter is True.)",None)
        self.attr_defaults["job_publish"]=("False","Bool","Should the glidein publish it to the job? (Used only if parameter is True.)",None)
        self.attr_defaults["const"]=("True","Bool","Should it be constant? (Else it can be overriden by the frontend. Used only if parameter is True.)",None)
        self.attr_defaults["type"]=("string","string|int","What kind on data is value.",None)

        self.file_defaults=xmlParse.OrderedDict()
        self.file_defaults["absfname"]=(None,"fname","File name on the local disk.",None)
        self.file_defaults["relfname"]=(None,"fname","Name of the file once it gets to the worker node. (defaults to the last part of absfname)",None)
        self.file_defaults["const"]=("True","Bool","Will the file be constant? If True, the file will be signed. If False, it can be modified at any time and will not be cached.",None)
        self.file_defaults["executable"]=("False",'Bool','Is this an executable that needs to be run in the glidein?',None)
        self.file_defaults["wrapper"]=("False",'Bool','Is this a wrapper script that needs to be sourced in the glidein job wrapper?',None)
        self.file_defaults["after_entry"]=("False",'Bool','Should this file be loaded after the entry ones?',None)
        self.file_defaults["untar"]=("False",'Bool','Do I need to untar it? ',None)

        self.infosys_defaults=xmlParse.OrderedDict()
        self.infosys_defaults["type"]=(None,"RESS|BDII","Type of information system",None)
        self.infosys_defaults["server"]=(None,"host","Location of the infosys server",None)
        self.infosys_defaults["ref"]=(None,"id","Referenced for the entry point in the infosys",None)


        untar_defaults=xmlParse.OrderedDict()
        untar_defaults["cond_attr"]=("TRUE","attrname","If not the special value TRUE, the attribute name used at runtime to determine if the file should be untarred or not.",None)
        untar_defaults["dir"]=(None,"dirname","Subdirectory in which to untar. (defaults to relname up to first .)",None)
        untar_defaults["absdir_outattr"]=(None,"attrname",'Attribute to be set to the abs dir name where the tarball was unpacked. Will be defined only if untar effectively done. (Not defined if None)',None)
        self.file_defaults["untar_options"]=untar_defaults

        downtimes_defaults=xmlParse.OrderedDict({"absfname":(None,"fname","File containing downtime information",None)})

        entry_config_defaults=xmlParse.OrderedDict()

        entry_config_max_jobs_defaults=xmlParse.OrderedDict()
        entry_config_max_jobs_defaults["running"]=('10000',"nr","Maximum number of concurrent glideins (per frontend) that can be submitted.",None)
        entry_config_max_jobs_defaults["idle"]=('2000',"nr","Maximum number of idle glideins (per frontend) allowed.",None)
        entry_config_max_jobs_defaults["held"]=('1000',"nr","Maximum number of held glideins (per frontend) before forcing the cleanup.",None)
        entry_config_defaults['max_jobs']=entry_config_max_jobs_defaults
        
        entry_config_queue_defaults=xmlParse.OrderedDict()
        entry_config_queue_defaults["max_per_cycle"]=['100',"nr","Maximum number of jobs affected per cycle.",None]
        entry_config_queue_defaults["sleep"]=['0.2',"seconds","Sleep between interactions with the schedd.",None]

        entry_config_defaults['submit']=copy.deepcopy(entry_config_queue_defaults)
        entry_config_defaults['submit']['cluster_size']=['10',"nr","Max number of jobs submitted in a single transaction.",None]
        entry_config_defaults['remove']=copy.deepcopy(entry_config_queue_defaults)
        entry_config_defaults['remove']['max_per_cycle'][0]='5'
        entry_config_defaults['release']=copy.deepcopy(entry_config_queue_defaults)
        entry_config_defaults['release']['max_per_cycle'][0]='20'


        # not exported and order does not matter, can stay a regular dictionary
        sub_defaults={'attrs':(xmlParse.OrderedDict(),'Dictionary of attributes',"Each attribute entry contains",self.attr_defaults),
                      'files':([],'List of files',"Each file entry contains",self.file_defaults),
                      'infosys_refs':([],'List of information system references',"Each reference points to this entry",self.infosys_defaults)}
        
        
        self.entry_defaults=xmlParse.OrderedDict()
        self.entry_defaults["gatekeeper"]=(None,'gatekeeper', 'Grid gatekeeper/resource',None)
        self.entry_defaults["gridtype"]=('gt2','grid_type','Condor Grid type',None)
        self.entry_defaults["rsl"]=(None,'RSL','Globus gt2 RSL option',None)
        self.entry_defaults['schedd_name']=(None,"ScheddName","Which schedd to use (Overrides the global one if specified)",None)
        self.entry_defaults["work_dir"]=(".",".|Condor|OSG|TMPDIR","Where to start glidein",None)
        self.entry_defaults['proxy_url']=(None,'proxy_url',"Squid cache to use",None)
        self.entry_defaults['verbosity']=('std','std|nodebug|fast',"Verbosity level and timeout setting",None)
        self.entry_defaults["enabled"]=("True","Bool","Is this entry enabled?",None)
        self.entry_defaults["config"]=entry_config_defaults
        self.entry_defaults["attrs"]=sub_defaults['attrs']
        self.entry_defaults["files"]=copy.deepcopy(sub_defaults['files'])
        del self.entry_defaults["files"][3]["after_entry"] # this is the entry, so after entry does not make sense
        self.entry_defaults["infosys_refs"]=sub_defaults['infosys_refs']
        self.entry_defaults["downtimes"]=downtimes_defaults
        
        self.defaults=xmlParse.OrderedDict()
        self.defaults["factory_name"]=(socket.gethostname(),'ID', 'Factory name',None)
        self.defaults["glidein_name"]=(None,'ID', 'Glidein name',None)
        self.defaults['schedd_name']=("schedd_glideins@%s"%socket.gethostname(),"ScheddName","Which schedd to use, can be a comma separated list",None)
        self.defaults["submit"]=xmlParse.OrderedDict({"base_dir":(os.environ["HOME"],"base_dir","Submit base dir",None)})

        self.defaults['loop_delay']=('60','seconds', 'Number of seconds between iterations',None)
        self.defaults['advertise_delay']=('5','NR', 'Advertize evert NR loops',None)

        stage_defaults=xmlParse.OrderedDict()
        stage_defaults["base_dir"]=("/var/www/html/glidefactory/stage","base_dir","Stage base dir",None)
        stage_defaults["web_base_url"]=("http://%s/glidefactory/stage"%socket.gethostname(),'base_url','Base Web server URL',None)
        stage_defaults["use_symlink"]=("True","Bool","Can I symlink stage dir from submit dir?",None)
        self.defaults["stage"]=stage_defaults

        monitor_default=xmlParse.OrderedDict()
        monitor_default["base_dir"]=("/var/www/html/glidefactory/stage","base_dir","Monitoring base dir",None)
        monitor_default["want_split_terminated_graphs"]=("True","Bool","Should create split terminated log graphs (CPU intensive)?",None)
        
        self.defaults["monitor"]=monitor_default
        
        security_default=xmlParse.OrderedDict()
        security_default["pub_key"]=("None","None|RSA","Type of public key system used for secure message passing",None)
        security_default["key_length"]=("2048","bits","Key length in bits",None)
        
        self.defaults["security"]=security_default
        
        condor_defaults=xmlParse.OrderedDict()
        condor_defaults["tar_file"]=(None,"fname","Tarball containing condor binaries (overrides base_dir if defined)",None)
        condor_defaults["base_dir"]=(find_condor_base_dir(),"base_dir","Condor distribution base dir (used only if tar_file undefined)",None)
        self.defaults["condor"]=condor_defaults

        self.defaults["downtimes"]=downtimes_defaults

        self.defaults["attrs"]=sub_defaults['attrs']
        self.defaults["files"]=sub_defaults['files']
        self.defaults["entries"]=(xmlParse.OrderedDict(),"Dictionary of entries","Each entry contains",self.entry_defaults)
                       
        # support dir
        self.src_dir=src_dir

        try:
            if len(argv)<2:
                raise RuntimeError, "Missing config file"

            if argv[1]=="-help":
                raise RuntimeError,"\nA config file will contain:\n%s\n\nThe config file will be in XML format."%self.get_description("  ")
                
            self.cfg_name=argv[1]
            self.load_file(self.cfg_name)
            # create derived values
            self.derive()
        except RuntimeError, e:
            raise RuntimeError,"%s\n\n%s"%(self.usage(),e)
        pass

    def derive(self):
        self.subparams.validate(self.defaults,"glidein")

        # glidein name does not have a reasonable default
        if self.glidein_name==None:
            raise RuntimeError, "Missing glidein name"

        # make a copy of the loaded data, so that I can always tell what was derived and what was not
        self.org_data=copy.deepcopy(self.data)

        self.subparams.use_defaults(self.defaults)

        #print self.org_data
        #print "\n\n",self.data
        #
        #if self.gatekeeper==None:
        #    self.usage()
        #    raise RuntimeError, "Missing gatekeeper"
        # 
        #if self.condor_base_dir==None:
        #    raise RuntimeError, "Missing condor base dir"
        
        glidein_subdir="glidein_%s"%self.glidein_name
        self.stage_dir=os.path.join(self.stage.base_dir,glidein_subdir)
        self.monitor_dir=os.path.join(self.monitor.base_dir,glidein_subdir)
        self.submit_dir=os.path.join(self.submit.base_dir,glidein_subdir)
        self.web_url=os.path.join(self.stage.web_base_url,glidein_subdir)

    def get_xml(self):
        old_default_ignore_nones=xmlFormat.DEFAULT_IGNORE_NONES
        old_default_lists_params=xmlFormat.DEFAULT_LISTS_PARAMS
        old_default_dicts_params=xmlFormat.DEFAULT_DICTS_PARAMS
        xmlFormat.DEFAULT_IGNORE_NONES=True
        # these are used internally, do not need to be ordered
        xmlFormat.DEFAULT_LISTS_PARAMS={'files':{'el_name':'file','subtypes_params':{'class':{}}},
                                        'infosys_refs':{'el_name':'infosys_ref','subtypes_params':{'class':{}}}}
        xmlFormat.DEFAULT_DICTS_PARAMS={'attrs':{'el_name':'attr','subtypes_params':{'class':{}}},'entries':{'el_name':'entry','subtypes_params':{'class':{}}}}
        # hack needed to make xmlFormat to properly do the formating
        old_DictType=types.DictType
        types.DictType=type(xmlParse.OrderedDict())
        out=xmlFormat.class2string(self.data,'glidein')
        types.DictType=old_DictType
        xmlFormat.DEFAULT_IGNORE_NONES=old_default_ignore_nones
        xmlFormat.DEFAULT_LISTS_PARAMS=old_default_lists_params
        xmlFormat.DEFAULT_DICTS_PARAMS=old_default_dicts_params
        return out


    def get_description(self,indent="",width=80):
        return defdict2string(self.defaults,indent,width)


    #load from a file
    #one element per line
    # -opt val
    def load_file(self,fname):
        if fname=="-":
            fname=sys.stdin
        try:
            self.data=xmlParse.xmlfile2dict(fname,use_ord_dict=True)
        except xml.parsers.expat.ExpatError, e:
            raise RuntimeError, "XML error parsing config file: %s"%e
        except IOError, e:
            raise RuntimeError, "Config file error: %s"%e
        self.subparams=SubParams(self.data)
        return

    def __eq__(self,other):
        if other==None:
            return False
        if not isinstance(other,Params):
            return False
        return self.subparams==other.subparams

    def __getattr__(self,name):
        return self.subparams.__getattr__(name)

    def usage(self):
        return "Usage: %s cfg_fname|-help"%self.usage_prefix

    #save into a file
    #The file should be usable for reload
    def save_into_file(self,fname):
        fd=open(fname,"w")
        try:
            fd.write(self.get_xml())
            fd.write("\n")
        finally:
            fd.close()
        return
    
    #save into a file (making a backup)
    #The file should be usable for reload
    def save_into_file_wbackup(self,fname):
        # rewrite config file (write tmp file first)
        tmp_name="%s.tmp"%fname
        try:
            os.unlink(tmp_name)
        except:
            pass # just protect
        self.save_into_file(tmp_name)

        # also save old one with backup name
        backup_name="%s~"%fname
        try:
            os.unlink(backup_name)
        except:
            pass # just protect
        try:
            os.rename(fname,backup_name)
        except:
            pass # just protect
        
        # finally rename to the proper name
        os.rename(tmp_name,fname)

# return attribute value in the proper python format
def extract_attr_val(attr_obj):
    if (not attr_obj.type in ("string","int")):
        raise RuntimeError, "Wrong attribute type '%s', must be either 'int' or 'string'"%attr_obj.type

    if attr_obj.type=="string":
        return str(attr_obj.value)
    else:
        return int(attr_obj.value)


############################################################
#
# P R I V A T E - Do not use
# 
############################################################

#######################################################
# Wrap a text string to a fixed length
def col_wrap(text,width,indent):
    short_text,next_char=shorten_text(text,width)
    if len(short_text)!=len(text): # was shortened
        #print short_text
        org_short_text=short_text[0:]
        # make sure you are not breaking words.
        while not (next_char in ('',' ','\t')):
            if len(short_text)==0:
                # could not break on word boundary, leave as is
                short_text=org_short_text
                break
            next_char=short_text[-1]
            short_text=short_text[:-1]
        
        if len(short_text)<=len(indent):
            # too short, just split as it was
            short_text=org_short_text

        # calc next lines
        subtext=col_wrap(indent+text[len(short_text):].lstrip(' \t'),width,indent)
        # glue
        return short_text+"\n"+subtext
    else:
        return text

# shorten text, make sure you properly account tabs
# return (shorten text,next char)
def shorten_text(text,width):
    count=0
    idx=0
    for c in text:
        if count>=width:
             return (text[:idx],c)
        if c=='\t':
            count=((count+8)/8)*8 #round to neares mult of 8
            if count>width:
                return (text[:idx],c)
            idx=idx+1
        else:
            count=count+1
            idx=idx+1
        
    return (text[:idx],'')

##################################################
# convert defualts to a string
def defdict2string(defaults,indent,width=80):
    outstrarr=[]

    keys=defaults.keys()
    keys.sort()

    final_keys=[]
    # put simple elements first
    for k in keys:
        el=defaults[k]
        if not isinstance(el,xmlParse.OrderedDict):
            defvalue,ktype,txt,subdef=el
            if subdef==None:
                final_keys.append(k)
    # put simple elements first
    for k in keys:
        el=defaults[k]
        if isinstance(el,xmlParse.OrderedDict):
            final_keys.append(k)
        else:
            defvalue,ktype,txt,subdef=el
            if subdef!=None:
                final_keys.append(k)

    for k in final_keys:
        el=defaults[k]
        if isinstance(el,xmlParse.OrderedDict):  #sub-dictionary
            outstrarr.append("%s%s:"%(indent,k)+"\n"+defdict2string(el,indent+"\t",width))
        else:
            #print el
            defvalue,ktype,txt,subdef=el
            wrap_indent=indent+string.ljust("",len("%s(%s) - "%(k,ktype)))
            if subdef!=None:
                if isinstance(defvalue,xmlParse.OrderedDict):
                    dict_subdef=copy.deepcopy(subdef)
                    dict_subdef["name"]=(None,"name","Name",None)
                    outstrarr.append(col_wrap("%s%s(%s) - %s:"%(indent,k,ktype,txt),width,wrap_indent)+"\n"+defdict2string(dict_subdef,indent+"\t",width))
                else:
                    outstrarr.append(col_wrap("%s%s(%s) - %s:"%(indent,k,ktype,txt),width,wrap_indent)+"\n"+defdict2string(subdef,indent+"\t",width))
            else:
                outstrarr.append(col_wrap("%s%s(%s) - %s [%s]"%(indent,k,ktype,txt,defvalue),width,wrap_indent))
    return string.join(outstrarr,"\n")
    
#####################################
# try to find out the base condor dir
def find_condor_base_dir():
    if condorExe.condor_bin_path==None:
        return None
    else:
        return os.path.dirname(condorExe.condor_bin_path)

###########################################################
#
# CVS info
#
# $Id: cgWParams.py,v 1.37 2008/10/16 17:28:56 sfiligoi Exp $
#
# Log:
#  $Log: cgWParams.py,v $
#  Revision 1.37  2008/10/16 17:28:56  sfiligoi
#  Make public key optional
#
#  Revision 1.36  2008/08/18 22:21:27  sfiligoi
#  Fix typo
#
#  Revision 1.35  2008/08/18 22:19:37  sfiligoi
#  Add params.security.pub_key
#
#  Revision 1.34  2008/08/06 16:44:42  sfiligoi
#  Add rate and sleep config options
#
#  Revision 1.33  2008/08/05 20:38:55  sfiligoi
#  Add WantSplitTermMonitorGraphs
#
#  Revision 1.28  2008/08/05 18:03:51  sfiligoi
#  Add max_jobs, max_idle and max_held to the parameters
#
#  Revision 1.27  2008/08/05 17:59:06  sfiligoi
#  Add max_jobs, max_idle and max_held to the parameters
#
#  Revision 1.26  2008/07/29 18:49:44  sfiligoi
#  Add entry verbosity
#
#  Revision 1.23  2008/07/28 17:44:42  sfiligoi
#  Add after_entry option to file
#
#  Revision 1.22  2008/07/24 18:04:25  sfiligoi
#  Add final newline to the XML file when saving
#
#  Revision 1.21  2008/07/23 16:43:27  sfiligoi
#  Remove a spurious print
#
#  Revision 1.20  2008/07/23 16:37:33  sfiligoi
#  Slight change in syntax
#
#  Revision 1.19  2008/07/23 16:03:49  sfiligoi
#  Add infosys_refs
#
#  Revision 1.18  2008/07/21 15:42:42  sfiligoi
#  Add support for rewriting the config file
#
#  Revision 1.17  2008/07/16 15:47:15  sfiligoi
#  Improve error handling
#
#  Revision 1.16  2008/07/15 20:49:46  sfiligoi
#  Improve usage printout
#
#  Revision 1.15  2008/07/10 19:21:17  sfiligoi
#  Make it executable from any disk location
#
#  Revision 1.14  2008/07/10 18:57:47  sfiligoi
#  Move all path changes out of the libraries
#
#  Revision 1.13  2008/07/07 17:55:07  sfiligoi
#  Add support for downtimes files
#
#  Revision 1.12  2008/07/03 18:24:56  sfiligoi
#  Put loop_delay and advertise_delay into the XML
#
#  Revision 1.11  2008/07/03 18:04:13  sfiligoi
#  Document TMPDIR
#
#  Revision 1.10  2007/12/28 20:48:20  sfiligoi
#  Add enabled to entry and use it to tell the factory which entries to use.
#
#  Revision 1.9  2007/12/12 00:51:27  sfiligoi
#  Implement equality method
#
#  Revision 1.8  2007/12/11 19:16:06  sfiligoi
#  Simplify attribute handling
#
#  Revision 1.7  2007/12/11 18:07:30  sfiligoi
#  Use the special value as the default for cond_attr
#
#  Revision 1.6  2007/12/05 21:48:09  sfiligoi
#  Temporary hack to make xmlFormat to work with OrderedDict
#
#  Revision 1.5  2007/12/05 21:02:26  sfiligoi
#  Fix type comparisons
#
#  Revision 1.4  2007/12/05 20:38:00  sfiligoi
#  User OrderedDict
#
#  Revision 1.3  2007/10/12 21:41:45  sfiligoi
#  Proper error message handling
#
#  Revision 1.2  2007/10/12 21:22:56  sfiligoi
#  Remove the use of sys.exit
#
#  Revision 1.1  2007/10/12 19:25:11  sfiligoi
#  Moved to the lib subdir
#
#  Revision 1.3  2007/10/12 19:18:48  sfiligoi
#  Move find_condor_base_dir to the right place
#
#  Revision 1.2  2007/10/12 19:08:24  sfiligoi
#  Add log
#
#
###########################################################
