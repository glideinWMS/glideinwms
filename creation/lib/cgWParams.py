import os
import copy
import sys
import os.path
import string
import socket
import traceback
sys.path.append("../lib")
import xmlParse
import xml.parsers.expat
import xmlFormat
import condorExe

class SubParams:
    def __init__(self,data):
        self.data=data

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
                if type(defel)==type({}):
                    # subdictionary
                    self[k].validate(defel,"%s.%s"%(path_text,k))
                else:
                    # final element
                    defvalue,ktype,txt,subdef=defel

                    if type(defvalue)==type({}):
                        # dictionary el elements
                        data_el=self[k]
                        for data_subkey in data_el.keys():
                            data_el[data_subkey].validate(subdef,"%s.%s.%s"%(path_text,k,data_subkey))
                    elif type(defvalue)==type([]):
                        # list of elements
                        if type(self.data[k])==type({}):
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
            if type(defel)==type({}):
                # subdictionary
                if not self.data.has_key(k):
                    self.data[k]={} # first create empty, if does not exist

                # then, set defaults on all elements of subdictionary
                self[k].use_defaults(defel)
            else:
                # final element
                defvalue,ktype,txt,subdef=defel

                if type(defvalue)==type({}):
                    # dictionary el elements
                    if not self.data.has_key(k):
                        self.data[k]={} # no elements yet, set and empty dictionary
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
        if type(el)==type({}):
            return SubParams(el)
        elif type(el)==type([]):
            outlst=[]
            for k in el:
                if type(k)==type({}):
                    outlst.append(SubParams(k))
                else:
                    outlst.append(k)
            return outlst
        else:
            return el
        

class Params:
    def __init__(self,argv):
        self.attr_defaults={"value":(None,"Value","Value of the attribute (string)",None),
                            "publish":("True","Bool","Should it be published by the factory?",None),
                            "parameter":("True","Bool","Should it be a parameter for the glidein?",None),
                            "glidein_publish":("False","Bool","Should it be published by the glidein? (Used only if parameter is True.)",None),
                            "job_publish":("False","Bool","Should the glidein publish it to the job? (Used only if parameter is True.)",None),
                            "const":("True","Bool","Should it be constant? (Else it can be overriden by the frontend. Used only if parameter is True.)",None),
                            "type":("string","string|int","What kind on data is value.",None)}

        self.file_defaults={"absfname":(None,"fname","File name on the local disk.",None),
                            "relfname":(None,"fname","Name of the file once it gets to the worker node. (defaults to the last part of absfname)",None),
                            "const":("True","Bool","Will the file be constant? If True, the file will be signed. If False, it can be modified at any time and will not be cached.",None),
                            "executable":("False",'Bool','Is this an executable that needs to be run in the glidein?',None),
                            "untar":("False",'Bool','Do I need to untar it? ',None),
                            "untar_options":{"cond_attr":(None,"attrname","If defined, the attribute name used at runtime to determine if the file should be untarred or not.",None),
                                             "dir":(None,"dirname","Subdirectory in which to untar. (defaults to relname up to first .)",None),
                                             "absdir_outattr":(None,"attrname",'Attribute to be set to the abs dir name where the tarball was unpacked. Will be defined only if untar effectively done. (Not defined if None)',None)}}
        
        
        sub_defaults={'attrs':({},'Dictionary of attributes',"Each attribute entry contains",self.attr_defaults),
                      'files':([],'List of files',"Each file entry contains",self.file_defaults)}
        self.entry_defaults={"gatekeeper":(None,'gatekeeper', 'Grid gatekeeper/resource',None),
                             "gridtype":('gt2','grid_type','Condor Grid type',None),
                             "rsl":(None,'RSL','Globus RSL option',None),
                             'schedd_name':(None,"ScheddName","Which schedd to use (Overrides the global one if specified)",None),
                             "work_dir":(".",".|Condor|OSG","Where to start glidein",None),
                             'proxy_url':(None,'proxy_url',"Squid cache to use",None),
                             "attrs":sub_defaults['attrs'],
                             "files":sub_defaults['files']}
        
        self.defaults={"factory_name":(socket.gethostname(),'ID', 'Factory name',None),
                       "glidein_name":(None,'ID', 'Glidein name',None),
                       'schedd_name':("schedd_glideins@%s"%socket.gethostname(),"ScheddName","Which schedd to use, can be a comma separated list",None),
                       "submit":{"base_dir":(os.environ["HOME"],"base_dir","Submit base dir",None)},
                       "stage":{"base_dir":("/var/www/html/glidefactory/stage","base_dir","Stage base dir",None),
                                "web_base_url":("http://%s/glidefactory/stage"%socket.gethostname(),'base_url','Base Web server URL',None),
                                "use_symlink":("True","Bool","Can I symlink stage dir from submit dir?",None)},
                       "monitor":{"base_dir":("/var/www/html/glidefactory/stage","base_dir","Monitoring base dir",None)},
                       "condor":{"tar_file":(None,"fname","Tarball containing condor binaries (overrides base_dir if defined)",None),
                                 "base_dir":(find_condor_base_dir(),"base_dir","Condor distribution base dir (used only if tar_file undefined)",None)},
                       "attrs":sub_defaults['attrs'],
                       "files":sub_defaults['files'],
                       "entries":({},"Dictionary of entries","Each entry contains",self.entry_defaults)}
                       
                       
        # support dir
        self.src_dir=os.path.join(os.getcwd(),"web_base")

        try:
            if len(argv)<2:
                raise RuntimeError, "Missing config file"

            if argv[1]=="-help":
                raise RuntimeError,"\nA config file will contain:\n%s\n\nThe config file will be in XML format."%self.get_description("  ")
                
            self.load_file(argv[1])
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
        xmlFormat.DEFAULT_LISTS_PARAMS={'files':{'el_name':'file','subtypes_params':{'class':{}}}}
        xmlFormat.DEFAULT_DICTS_PARAMS={'attrs':{'el_name':'attr','subtypes_params':{'class':{}}},'entries':{'el_name':'entry','subtypes_params':{'class':{}}}}
        out=xmlFormat.class2string(self.data,'glidein')
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
            self.data=xmlParse.xmlfile2dict(fname)
        except xml.parsers.expat.ExpatError, e:
            raise RuntimeError, "XML error parsing config file: %s"%e
        self.subparams=SubParams(self.data)
        return

    def __getattr__(self,name):
        return self.subparams.__getattr__(name)

    def usage(self):
        print "Usage: create_glidein cfg_fname|-help"

    #save into a file
    #The file should be usable for reload
    def save_into_file(self,fname):
        fd=open(fname,"w")
        try:
            fd.write(self.get_xml())
        finally:
            fd.close()
        return
    

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
        if type(el)!=type({}):
            defvalue,ktype,txt,subdef=el
            if subdef==None:
                final_keys.append(k)
    # put simple elements first
    for k in keys:
        el=defaults[k]
        if type(el)==type({}):
            final_keys.append(k)
        else:
            defvalue,ktype,txt,subdef=el
            if subdef!=None:
                final_keys.append(k)

    for k in final_keys:
        el=defaults[k]
        if type(el)==type({}):  #sub-dictionary
            outstrarr.append("%s%s:"%(indent,k)+"\n"+defdict2string(el,indent+"\t",width))
        else:
            #print el
            defvalue,ktype,txt,subdef=el
            wrap_indent=indent+string.ljust("",len("%s(%s) - "%(k,ktype)))
            if subdef!=None:
                if type(defvalue)==type({}):
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
# $Id: cgWParams.py,v 1.2 2007/10/12 21:22:56 sfiligoi Exp $
#
# Log:
#  $Log: cgWParams.py,v $
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
