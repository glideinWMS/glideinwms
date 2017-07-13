#!/usr/bin/env python

from __future__ import print_function
import sys
import os.path
import string
import time
import stat
import shutil
import getpass
import pwd
import socket
import re
import glideinwms.lib.subprocessSupport

#--------------------------
class WMSerror(Exception):
  pass 
#--------------------------
def logit(message):
   print(message)
#--------------------------
def logerr(message):
   logit("ERROR: %s" % message)
   raise WMSerror(Exception)
#--------------------------
def logwarn(message):
   logit("Warning: %s" % message)

#--------------------------
def write_file(mode,perm,filename,data,SILENT=False):
  if mode == "w":
    if not SILENT:
      logit("    writing: %s" % filename)
    make_backup(filename, SILENT)
  elif mode == "a":
    if not SILENT:
      logit("Appending to file: %s" % filename)
  else:
    logerr("Internal error in accessing write_file method: Invalid mode(%s)" % mode)
  fd = open(filename, mode)
  try:
    try:    
      fd.write(data)
    except Exception as e:
      logerr("Problem writing %s: %s" % (filename, e))
  finally:
    fd.close()
  os.chmod(filename, perm) 

#--------------------------
def make_directory(dirname, owner, perm):
  if os.path.isdir(dirname):
    if not_writeable(dirname):
      logerr("Directory (%s) exists but is not writable by user %s" % (dirname, owner))
    return  # we done.. all is ok
  #-- create it but check entire path ---
  logit("... creating directory: %s" % dirname)
  dirs = [dirname,]  # directories we need to create
  dir = dirname
  while dir != "/":
    parent_dir = os.path.dirname(dir)
    if os.path.isdir(parent_dir):
      break
    dirs.append(parent_dir)
    dir = parent_dir
  dirs.reverse()
  for dir in dirs:
    if not_writeable(parent_dir):
      logerr("""Cannot create directory because of permissions/ownership of parent dir:
  %(parent_dir)s""" % { "parent_dir" : parent_dir})
    try:
      os.makedirs(dir)
      os.chmod(dir, perm)
      uid = pwd.getpwnam(owner)[2]
      gid = pwd.getpwnam(owner)[3]
      os.chown(dir, uid, gid)
    except:
      logerr("""Failed to create or set permissions/ownership(%(owner)s) on directory: 
  %(dir)s""" % { "owner" : owner, "dir" :dir})
  return
  
#--------------------------
def remove_dir_contents(dirname):
  if len(dirname) == 0:
    logerr("""System error: an empty argument was supplied to the 
common.remove_dir_contents method.  This will result deleting all files on 
this node.  Not something you really want to do""")
  cmd = "rm -rf %s/*" % dirname
  try:
    stdout = glideinwms.lib.subprocessSupport.iexe_cmd(cmd, useShell=True)
  except glideinwms.lib.subprocessSupport.CalledProcessError as e:
    logerr("""Problem deleting files in %s
%s""" % (dirname, e))
  logit("Files in %s  deleted" % dirname)
  
#--------------------------
def not_writeable(dirname):
  test_fname=os.path.join(dirname, "test.txt")
  try:
    fd=open(test_fname, "w")
    fd.close()
    os.unlink(test_fname)
  except:
    return True
  return False

#--------------------------
def has_permissions(dir, level, perms):
  result = True
  mode =  stat.S_IMODE(os.lstat(dir)[stat.ST_MODE])
  for perm in perms:
    if mode & getattr(stat, "S_I"+perm+level):
      continue
    result = False
    break
  return result

#--------------------------
def remove_dir_path(dirname):
  if os.path.isdir(dirname):
    shutil.rmtree(dirname)
    logit( "... directory removed: %s" % dirname)
  else:
    logit( "... directory does not exist: %s" % dirname)

#--------------------------
def make_backup(filename,SILENT=False):
  if os.path.isfile(filename):
    save_dir = "%s/saved.%s"  % (os.path.dirname(filename), day_suffix())
    if not os.path.exists(save_dir):
      os.mkdir(save_dir)
    backup = "%(save_dir)s/%(time)s-%(filename)s" % \
                 { "save_dir": save_dir,
                   "filename": os.path.basename(filename),
                   "time": time_suffix(), 
                 }
    shutil.copy2(filename, backup)
    if not SILENT:
      logit( "    backup created: %s" % (backup))
  #else:
  #  logit( "    no backup required, file does not exist: %s" % (filename))

#--------------------------
def time_suffix():
  return time.strftime("%Y%m%d_%H%M", time.localtime())
def day_suffix():
  return time.strftime("%Y%m%d", time.localtime())


#--------------------------------------
def run_script(script):
  """ Runs a script using subsystemSupport module. """
  logit("... running: %s" % script)
  try:
    stdout = glideinwms.lib.subprocessSupport.iexe_cmd(script, useShell=True)
  except glideinwms.lib.subprocessSupport.CalledProcessError as e:
    logerr("""Script failed with non-zero return code
%s """ % e )


#--------------------------------------
def cron_append(lines,tmp_dir='/tmp'):
  """ Append a line to the crontab for a user."""
  logit("\n... adding %i lines to %s's crontab" % (len(lines), getpass.getuser()))
  tmp_fname="%s/tmp_%s_%s.tmp"%(tmp_dir, os.getpid(), time.time())
  try:
    cmd = "crontab -l >%s" % tmp_fname
    stdout = glideinwms.lib.subprocessSupport.iexe_cmd(cmd, useShell=True)
    fd=open(tmp_fname, 'a')
    try:
      for line in lines:
        fd.writelines(line)
    finally:
      fd.close()
    stdout = glideinwms.lib.subprocessSupport.iexe_cmd("cat %s" % tmp_fname)
    logit(stdout)
    stdout = glideinwms.lib.subprocessSupport.iexe_cmd("crontab %s" % tmp_fname)
  finally:
    if os.path.isfile(tmp_fname):
      os.unlink(tmp_fname)
  logit("\n... %s's crontab updated" % (getpass.getuser()))

#--------------------------------------
def find_fullpath(search_path, name):
  """ Given a search path, determine if the given file/directory exists 
      somewhere in the path.
      Returns: if not found. returns None
               if found. returns the full path/name
  """
  for root, dirs, files in os.walk(search_path, topdown=True):
    if os.path.basename(root) == name:
      return root
    for dir in dirs:
      if dir == name:
        return os.path.join(root, dir, name)
    for file in files:
      if file == name:
        return os.path.join(root, file)
  return None
    
#--------------------------------------
def module_exists(module_name):
  cmd = "python -c 'import %s' >/dev/null 2>&1" % module_name
  try:
    glideinwms.lib.subprocessSupport.iexe_cmd(cmd, useShell=True)
  except glideinwms.lib.subprocessSupport.CalledProcessError as e:
    return False
  return True

#--------------------------------
def validate_install_type(type):
  logit("... validating install_type: %s" % type)
  types = ["rpm", "tarball",]
  if type not in types:
    logerr("Invalid install_type. Valid values are: %s)" % (types))


#--------------------------------
def validate_email(email):
  logit("... validating condor_email_address: %s" % email)
  if email.find('@')<0:
    logerr("Invalid email address (%s)" % (email))

#--------------------------------
def validate_install_location(dir):
  logit("... validating install_location: %s" % dir)
  install_user = pwd.getpwuid(os.getuid())[0]
  make_directory(dir, install_user, 0o755)

#--------------------------------
def ask_yn(question):
  while True:
    yn = input("%s? (y/n): " % (question))
    if yn.strip() == "y" or yn.strip() == "n":
      break
    logit("... just 'y' or 'n' please")
  return yn.strip()

#--------------------------------
def ask_continue(question):
  while True:
    yn = input("%s? (y/n): " % (question))
    if yn.strip() == "y" or yn.strip() == "n":
      break
    logit("... just 'y' or 'n' please")
  if yn.strip() == "n":
    raise KeyboardInterrupt

#--------------------------------
def validate_hostname(node,additional_msg=""):
  logit("... validating hostname: %s" % node)
  if node != socket.getfqdn():
    logerr("""The hostname option (%(hostname)s) shows a different host. 
      This is %(thishost)s.
      %(msg)s """ % { "hostname": node,
                      "thishost": socket.getfqdn(),
                      "msg": additional_msg,})

#--------------------------------
def validate_user(user):
  logit("... validating username: %s" % user)
  try:
    x = pwd.getpwnam(user)
  except:
    logerr("User account (%s) does not exist. Either create it or specify a different user." % (user))

#--------------------------------
def validate_installer_user(user):
  logit("... validating installer_user: %s" % user)
  install_user = pwd.getpwuid(os.getuid())[0]
  if user != install_user:
    logerr("You are installing as user(%s).\n       The ini file says it should be user(%s)." % (install_user, user))

#--------------------------------
def validate_gsi_for_proxy(dn_to_validate,proxy,real_user=None):
  if real_user == None:
    install_user = pwd.getpwuid(os.getuid())[0]
  else:
    install_user = real_user
  #-- check proxy ---
  logit("... validating x509_proxy: %s" % proxy)
  if not os.path.isfile(proxy):
    logerr("""x509_proxy (%(proxy)s)
not found or has wrong permissions/ownership.""" % \
  {  "proxy":  proxy,
     "owner": install_user,})
  #-- check dn ---
  logit("... validating x509_gsi_dn: %s" % dn_to_validate)
  dn_in_file = get_gsi_dn("proxy", proxy, install_user)
  if dn_in_file != dn_to_validate:
    logerr("""The DN of the x509_proxy option does not match the x509_gsi_dn 
option value in your ini file:
  x509_gsi_dn: %(dn_to_validate)s
x509_proxy DN: %(dn_in_file)s
This may cause a problem in other services.
You should reinstall any services already complete.""" % \
    { "dn_in_file": dn_in_file,
      "dn_to_validate": dn_to_validate,})

#--------------------------------
def validate_gsi_for_cert(dn_to_validate, cert, key):
  install_user = pwd.getpwuid(os.getuid())[0]
  #-- check cert ---
  logit("... validating x509_cert: %s" % cert)
  if not os.path.isfile(cert):
    logerr("""x509_cert (%(cert)s)
not found or has wrong permissions/ownership.""" % \
       {  "cert":  cert, 
          "owner": install_user,})
  #-- check key ---
  logit("... validating x509_key: %s" % key)
  if not os.path.isfile(key):
    logerr("""x509_key (%(key)s)
not found or has wrong permissions/ownership.""" % \
        {  "key":  key, 
          "owner": install_user,})
  #-- check dn ---
  logit("... validating x509_gsi_dn: %s" % dn_to_validate)
  dn_in_file = get_gsi_dn("cert", cert)
  if dn_in_file != dn_to_validate:
    logerr("""The DN of the x509_cert option does not match the x509_gsi_dn 
option value in your ini file:
  x509_gsi_dn: %(dn_to_validate)s
 x509_cert DN: %(dn_in_file)s
This may cause a problem in other services.
You should reinstall any services already complete.""" % \
    { "dn_in_file": dn_in_file, 
      "dn_to_validate": dn_to_validate,})

#--------------------------------
def get_gsi_dn(type,filename,real_user=None):
  """ Returns the 'identity' of the user for a certificate
      or proxy.  Using openssl, If it is a proxy, use the -issuer argument.
      If a certificate, use the -subject argument.
  """
  if real_user == None:
    install_user = pwd.getpwuid(os.getuid())[0]
  else:
    install_user = real_user
  if type == "proxy":
    arg = "-issuer"
    if not os.path.isfile(filename):
      logerr("""Proxy (%(filename)s)
not found or has wrong permissions/ownership.
The proxy has to be owned by %(user)s and have 600 permissions.
Or you could be trying to perform this as the wrong user.
""" % { "filename": filename, "user": install_user,} )
  elif type == "cert":
    arg = "-subject"
  else:
    logerr("Invalid type (%s). Must be either 'cert' or 'proxy'." % type)

  if not os.path.isfile(filename):
    logerr("%s '%s' not found" % (type, filename))
  if os.stat(filename).st_uid != pwd.getpwnam(install_user)[2]:
    logerr("""The %(type)s specified (%(filename)s)
has to be owned by user %(user)s  
Or you could be  trying to perform this as the wrong user.
""" % { "type": type, "filename": filename, "user": install_user,})

  #-- read the cert/proxy --
  dn_blob   = glideinwms.lib.subprocessSupport.iexe_cmd("openssl x509 %s -noout -in %s" % (arg, filename))
  if dn_blob is None:
    logerr("Failed to read %s from %s" % (arg, filename))
  if len(dn_blob) == 0:
    logerr("Failed to read %s from %s" % (arg, filename))
  #-- parse out the DN --
  i = dn_blob.find("= ")
  if i < 0:
    logerr("Failed to extract DN from %s '%s'." % (arg, filename))
  dn_blob = dn_blob[i+2:] # remove part before identity
  my_dn   = dn_blob[:dn_blob.find('\n')] # keep only the part until the newline
  return my_dn

#----------------------------
def mapfile_entry(dn, name):
  if len(dn) == 0 or len(name) == 0:
    return ""
  return """GSI "^%(dn)s$" %(name)s
""" % { "dn": re.escape(dn), "name": name,}

#----------------------------
def check_for_value(option, value):
  if len(value) == 0:
    logerr("""The %s option is not populated and is required to proceed.""" % option)

#----------------------------
def not_an_integer(value):
  try:
    nbr = int(value)
  except:
    return True
  return False

#----------------------------
def url_is_valid(url):
  try:
    ress_ip=socket.gethostbyname(url)
  except:
    return False
  return True

#----------------------------
def wget_is_valid(location):
  cmd = "wget --quiet --spider %s" % location
  try:
    glideinwms.lib.subprocessSupport.iexe_cmd(cmd, useShell=True)
  except glideinwms.lib.subprocessSupport.CalledProcessError as e:
    return False
  return True


#------------------
def indent(level):
  indent = ""
  while len(indent) < (level * 2):
    indent = indent + "  "
  return indent

#------------------
def start_service(glidein_src, service, inifile):
  """ Generic method for asking if service is to be started and 
      starting it if requested. 
  """
  argDict = { "WMSCollector": "wmscollector",
              "Factory": "factory",
              "UserCollector": "usercollector",
              "Submit": "submit",
              "VOFrontend": "vofrontend",
            }
  cmd ="%(glidein_src)s/install/manage-glideins --start %(service)s --ini %(inifile)s" % \
           { "inifile": inifile,
             "service": argDict[service],
             "glidein_src": glidein_src, 
           }
  time.sleep(3)
  logit("")
  logit("You will need to have the %(service)s service running if you intend\nto install the other glideinWMS components." % { "service" : service })
  yn = ask_yn("... would you like to start it now")
  if yn == "y":
     run_script(cmd)
  else:
    logit("\nTo start the %(service)s you can run:\n %(cmd)s" % \
           { "cmd": cmd,
             "service": service,
           })

#######################################
if __name__ == '__main__':
  print("Starting some tests")
  #ans = ask_continue("kldsjfklj")
  #print ans
  #sys.exit(0)
  try:
    print("Testing make_directory")
    owner = pwd.getpwuid(os.getuid())[0]
    perm = 0o755
    testdir = "/opt/testdir/testdir1/testdir2/testdir3"
    print("... %s" % testdir)
    make_directory(testdir, owner, perm=True)
    if not os.path.isdir(testdir):
      print("FAILED")
    print("PASSED")
    os.rmdir(testdir)

    print("Testing make_backup")
    make_directory(testdir, owner, perm)
    filename = "%s/%s" % (testdir, __file__)
    shutil.copy(__file__, filename)
    make_backup(filename)
    glideinwms.lib.subprocessSupport.iexe_cmd("rm -f %s*" % filename, useShell=True)
    os.rmdir(testdir)
    os.rmdir(os.path.dirname(testdir))
    print("... PASSED")

  except Exception as e:
    print("FAILED test")
    print(e)
    sys.exit(1)
  print("PASSED all tests")
  sys.exit(0)






