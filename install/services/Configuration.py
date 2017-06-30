#!/usr/bin/python

import common
#-----
import re
import os
import string
import sys
import time
import traceback
import ConfigParser
import StringIO

import inspect

#### Class Configuration ############################
class Configuration:

  def __init__ (self, fileName):
    self.cp       = None 
    self.inifile = fileName 

    #-- check for duplicate sections in config file --
    self.check_for_duplicate_sections()

    try:
      #-- check version of parser to use ---
      if sys.version_info[0] >= 2 and sys.version_info[1] >= 3:
        self.cp = ConfigParser.SafeConfigParser()
      else:
        self.cp = ConfigParser.ConfigParser()
      #-- read the ini file ---
      real_fp = open(self.inifile, 'r')
      string_fp = StringIO.StringIO(real_fp.read())
      self.cp.readfp(string_fp, self.inifile)
    except Exception as e:
      common.logerr("%s" % e)

    #-- additional check for syntax errors --
    self.syntax_check()


  #----------------
  def syntax_check(self):
    """ Checks for some syntax errors in ini config file. """
    for section in self.sections():
      for option in self.options(section):
        value = self.option_value(section, option)
        if "\n" in value:
          line = string.split(value, "\n")
          common.logerr("Section [%s]: this line starts with whitespace ( %s)\n       Please remove the leading space or comment (;) the line." % (section, line[1]))

  #----------------
  def __str__ (self):
    result = []
    result.append('<Configuration from %s>' % self.inifile)
    for section in self.sections():
      result.append('[%s]' % section)
      for option in self.options(section):
        value = self.option_value(section, option)
        result.append('    %-25s %s' % (option, value))
    return '\n'.join(result)

  #----------------
  def check_for_duplicate_sections(self):
    """ Check for duplicate sections in a config file ignoring commented ones. 
        In addition, checks to verify there is no whitespace preceding or
        appending the section name in brackets as the ini parser does not
        validate for this.
    """
    if (self.inifile == "") or (self.inifile is None):
      common.logerr("System error: config file name is empty")
    try:
      fp = open(self.inifile, 'r')
    except:
      common.logerr("Problem reading ini file: %s" % sys.exc_info()[1])
    sections = {}    # used to keep track of sections
    duplicates = []  # used to identify duplicates
    for line in fp.readlines():
      newline = line.strip()
      if len(newline) == 0:
        continue
      if newline[0] != "[":
        continue
      #--- see if it is a section ---
      match = re.search('\[(.*)\]', newline)
      if match:
        section = match.group(1).lower().strip()
        if section in sections:
          duplicates.append(section)
          continue
        sections[section] = True
    if (len(duplicates) != 0 ):
      common.logerr("Duplicate sections in %s - %s" % (self.inifile, duplicates))

  #----------------
  def validate_section(self, section, valid_option_list):
    if not self.has_section(section):
      common.logerr("Section (%s) does not exist in ini file (%s)" % (section, self.inifile))
    errors = [] 
    for option in valid_option_list:
      if self.has_option(section, option):
        continue
      errors.append(option)
    if len(errors) > 0:
      common.logerr("These options are not defined in the %s section of the ini file: %s" % (section, errors))

  #----------------
  def section_options(self):
    result = []
    for section in self.sections():
      result.append('[%s]' % section)
      for option in self.options(section):
        result.append('    %-25s' % (option))
    return '\n'.join(result)

  #----------------
  def filename(self):
    return self.inifile

  #----------------
  def sections(self):
    sections = sorted(self.cp.sections())
    return sections

  #----------------
  def options(self, section):
    options = sorted(self.cp.options(section))
    return options

  #----------------
  def option_value(self, section, option):
    """ Due they way python os.path.basename/dirname work, we cannot let a
        pathname end in a '/' or we may see inconsistent results.  So we
        are stripping all option values of trailing '/'s.
    """
    value = ""
    if self.has_option(section, option):
      try:
        value = self.cp.get(section, option)
      except Exception as e:
        common.logerr("ini file error: %s" % e.__str__())
      #-- cannot let paths end in a '/' --
      while len(value) > 0 and value[len(value)-1] == "/":
        value = value[0:len(value)-1].strip()
    return value

  #----------------
  def has_section(self, section):
    return self.cp.has_section(section)
  #----------------
  def has_option(self, section, option):
    return self.cp.has_option(section, option)
  #----------------
  def delete_section(self, section):
    self.cp.remove_section(section)
    return 

#### Exceptions #####################################
class ConfigurationError(Exception):
  pass
class UsageError(Exception):
  pass


#####################################################
#---------------------
#---- Functions ------
#---------------------
def compare_ini_files (file_1, file_2, no_local_settings):
  try:
    print "Comparing ini files: %s / %s" % (file_1, file_2)
    ini_1 = Configuration(file_1)
    ini_2 = Configuration(file_2)
    rtn = 0
    #--- remove the Local Settings section conditionally ---
    if ( no_local_settings ):
      ini_1.delete_section("Local Settings")
      ini_2.delete_section("Local Settings")
    print "... Checking section information:"
    if ( ini_1.sections() == ini_2.sections() ):
      print "... sections are identical"
    else:
      print "... WARNING: section information differs"
      compare_sections(ini_1, ini_2)
      compare_sections(ini_2, ini_1)
      rtn = 1
    print
    print "... Checking section/object information:"
    if ( ini_1.section_options() ==  ini_2.section_options() ):
      print "... all section/objects are identical"
    else:
      print "... WARNING: section/object information differs"
      compare_options(ini_1, ini_2)
      compare_options(ini_2, ini_1)
      rtn = 1
  except:
    raise 
  return rtn  

#--------------------------------
def compare_sections(ini1, ini2):
  print """
... Sections     in %s 
       NOT FOUND in %s""" % (ini1.filename(), ini2.filename())
  for section in ini1.sections(): 
    if ( ini2.has_section(section) ):
      continue
    else:
      print "    %s" % (section)

#--------------------------------
def compare_options(ini1, ini2):
  print """
... Section/objects in %s 
          NOT FOUND in %s""" % (ini1.filename(), ini2.filename())
  for section in ini1.sections():
    for option in ini1.options(section): 
      ## if (section == "SE CHANGEME"):
      ##   if (option == "enable"):
      ##     print section,option
      if ( ini2.has_option(section, option) == False):
        print "    %-20s/%s" % (section, option)
 
#--------------------------------
def usage(pgm):
  print
  print "Usage: " + pgm + " --compare file1 file2"
  print "       " + pgm + " --show-options file"
  print "       " + pgm + " --show-values file"
  print "       " + pgm + " --validate file"
  print "       " + pgm + " --help | -h "
  print """
   compare .......... Shows the differences between the 
                      section/objects (not values) of the 2 ini files
                        returns 0 if identical
                        returns 1 if any differences
   show-options ...... Shows the section/objects for the ini file
   show-values ....... Shows the section/objects/values for the ini file
   validate .......... Verifies the ini file has no syntax errors

   Full path to the files must be specified unless this is executed
   in the directory in which they reside.

"""

#----------------------------------
def run_unit_tests(pgm):
  try:
    dir="./testdata/"
    tests = {
"no arguments": [1, pgm],
"not enough arguments": [1, pgm, "--validate"],
"not enough arguments": [1, pgm, "--compare"],
"invalid argument": [1, pgm, "--bad-arg", dir+"non-existent-file"],

##  validate ###
"validate: good ini": [0, pgm, "--validate", dir+"config-good.ini"],
"validate: bad ini": [1, pgm, "--validate", dir+"config-bad.ini"],
"validate: no ini": [1, pgm, "--validate", dir+"non-existent-file"],
"duplicates": [1, pgm, "--validate", dir+"config-w-dup-sections.ini"],

##  compare ###
"compare: no difference": [0, pgm, "--compare", dir+"config-good.ini", dir+"config-good.ini"],
"compare: differences": [1, pgm, "--compare", dir+"config-good.ini", dir+"config-good-different.ini"],
"compare: no ini": [1, pgm, "--validate", dir+"non-existent-file"],
"duplicates": [1, pgm, "--compare", dir+"config-good.ini config-w-dup-sections.ini"],

##  show-options ###
"show-options": [0, pgm, "--show-options", dir+"config-good.ini"],
"show-options: bad ini": [1, pgm, "--show-options", dir+"config-bad.ini"],
"show-options: no ini": [1, pgm, "--show-options", dir+"non-existent-file"],
"duplicates": [1, pgm, "--show-options", dir+"config-w-dup-sections.ini"],

##  show-values ###
"show-values": [0, pgm, "--show-values", dir+"config-good.ini"],
"show-values: bad ini": [1, pgm, "--show-values", dir+"config-bad.ini"],
"show-values: no ini": [1, pgm, "--show-values", dir+"non-existent-file"],
"duplicates": [1, pgm, "--show-values", dir+"config-w-dup-sections.ini"],
    }
    #---- run tests -----
    n=0
    for test in tests.keys():
      n = n + 1
      args = tests[test]
      expected_rtn = args[0]
      print "-----------------------------------------------------------------"
      print "-- Test %d: %s" % (n, test)
      print "--   ", args[1:]
      print "--    Expected return code: %s" % expected_rtn
      rtn = main(args[1:])
      print "-- Return code: %s" % rtn
      if ( rtn == expected_rtn ):
        print "-- Test %d: %s - SUCCESSFUL" % (n, test)
        print "-----------------------------------------------------------------"
      else:
        raise ConfigurationError("-- Test %d: %s - FAILED" % (n, test))
  except:
    raise 
  print "**********## All %d tests passed ***************" % n

#--------------------
def validate_args(opts, expected_args):
  if ( len(opts) < expected_args ):
    raise UsageError("Insufficient number of arguments for option selected")
#---------------------
def show_line():
    x = traceback.extract_tb(sys.exc_info()[2])
    z = x[len(x)-1]
    return "%s line %s" % (z[2], z[1])
  
############################# Main Program ##############################

def main(opts=None):
  try:
      #--- process command line arguments ---
      ##print len(opts)
      validate_args(opts, 2)
      opt = opts[1]
      if (opt == "-h") or (opt == "--help"):
        usage(opts[0]);return 1
      elif (opt == "--compare") or (opt == "-compare"):
        validate_args(opts, 4)
        return compare_ini_files(opts[2], opts[3], False)
      elif (opt == "--compare-no-local") or (opt == "-compare-no-local"):
        validate_args(opts, 4)
        return compare_ini_files(opts[2], opts[3], True)
      elif (opt == "--show-options") or (opt == "-show-options"):
        validate_args(opts, 3)
        ini = Configuration(opts[2])
        print ini.section_options()
      elif (opt == "--show-values") or (opt == "-show-values"):
        validate_args(opts, 3)
        ini = Configuration(opts[2])
        print ini
        validate_args(opts, 3)
      elif (opt == "--validate") or (opt == "-validate"):
        ini = Configuration(opts[2])
        print "... configuration ini file has no syntax errors"
      elif (opt == "--test") or (opt == "-test"):
        run_unit_tests(opts[0])
      else:
        raise UsageError("Invalid command line option")
  except ConfigurationError as e:
    print;print "Configuration ERROR: %s" % e;return 1
  except UsageError as e:
    usage(opts[0])
    print "Usage ERROR: %s" % e;return 1
  except Exception as e:
    print;print "Exception ERROR: %s - %s" % (show_line(), e);return 1
  return 0

#--------------------------
if __name__ == '__main__':
  sys.exit(main(sys.argv))


