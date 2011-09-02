#!/usr/bin/env python

import sys
import os
import pwd
import grp
import stat

import common

class PrivilegeSeparation:
    def __init__(self, condor_location, factory_obj, frontend_objs, frontend_users_dict):
        self.condor_location = condor_location
        self.factory = factory_obj
        self.frontends = frontend_objs
        #-- dictionary of frontends and local unix account --
        self.frontend_users_dict = frontend_users_dict

        # -- config file is hard-coded in Condor.  It cannot be changed --
        self.config_file = "/etc/condor/privsep_config"

        # -- condor switchboard that must have setuid ----
        self.switchboard_bin = os.path.join(self.condor_location, 'sbin/condor_root_switchboard')
        # -- users and groups ----
        self.factory_user = self.factory.username()
        self.factory_groups = None
        self.frontend_groups = {}
        self.frontend_users = []

        self.validate_before_condor_install()

    def validate_before_condor_install(self):
        common.logit("Privilege separation validation starting")
        if os.getuid() != 0:
            common.logerr("You must install as root user to use privilege separation.")
        self.validate_frontends()
        self.validate_users()
        self.validate_client_files()
        common.logit("Privilege separation validation complete\n")

    def validate_client_files(self):
        common.logit("""Privilege separation requires root-only write permissions (drwxr-xr-x) for 
full path to client files: """)
        dirs = [ self.factory.client_log_dir(), self.factory.client_proxy_dir(), ]
        for dir_name in dirs:
            common.logit("client directory: %s" % dir_name)
            while dir_name != "/":
                common.logit("   validating %s" % dir_name)
                if not os.path.exists(dir_name):
                    dir_name = os.path.dirname(dir_name)
                    continue
                if not os.path.isdir(dir_name):
                    common.logerr("This is not a directory: %s" % dir_name)
                if os.stat(dir_name)[4] != 0:
                    common.logerr("Group is not root: %s" % dir_name)
                if os.stat(dir_name)[5] != 0:
                    common.logerr("Owner is not root: %s" % dir_name)
                if not common.has_permissions(dir_name, "USR", ["R", "W", "X", ]):
                    common.logerr("Incorrect 'owner' permissions: %s" % dir)
                if not common.has_permissions(dir_name, "GRP", ["R", "X", ]) or common.has_permissions(dir_name, "GRP", ["W", ]):
                    common.logerr("Incorrect 'group' permissions: %s" % dir)
                if not common.has_permissions(dir_name, "OTH", ["R", "X", ]) or common.has_permissions(dir_name, "OTH", ["W", ]):
                    common.logerr("Incorrect 'other' permissions: %s" % dir_name)
                dir_name = os.path.dirname(dir_name)

    def config_data(self):
        data = """
valid-caller-uids = %(factory_user)s 
valid-caller-gids = %(factory_groups)s 
valid-target-uids = %(client_uids)s 
valid-target-gids = %(client_gids)s 
valid-dirs = %(client_log_dir)s 
valid-dirs = %(client_proxy_dir)s 
procd-executable = %(procd)s
""" % { "factory_user"     : self.factory_user,
        "factory_groups"   : self.factory_groups,
        "client_uids"      : " : ".join(self.frontend_users),
        "client_gids"      : " : ".join(self.frontend_groups.keys()),
        "client_log_dir"   : self.factory.client_log_dir(),
        "client_proxy_dir" : self.factory.client_proxy_dir(),
        "procd"    : os.path.join(self.condor_location, 'sbin/condor_procd'),
       }
        return data

    def condor_config_data(self):
        data = """
#########################################################
## Make the factory user a condor superuser.
## This is needed by the factory damemons in privsep mode
## and it also makes the administration easier.
#########################################################
QUEUE_SUPER_USERS = $(QUEUE_SUPER_USERS), %s
""" % self.factory_user
        return data

    def validate_frontends(self):
        common.logit("... validating frontend data")
        #--- frontend check to insure they are in ini file(s) ---
        frontend_inis = []
        service_names = self.frontend_users_dict.keys()
        for obj in self.frontends:
            frontend_inis.append(obj.service_name())
        service_names.sort()
        frontend_inis.sort()
        if service_names != frontend_inis:
            msg = """The service_names of VOFrontends in your ini file do not match 
those in your frontend_users attribute of the WMSCollector ini file:  
  frontend_users = %s 
  frontend inis  = %s""" % (self.frontend_users_dict, frontend_inis)
            common.logerr(msg)

    def validate_users(self):
        common.logit("... validating frontend user data")
        #--- factory ---
        user_valid = True
        try:
            self.factory_groups = self.get_groups(self.factory_user)
        except Exception:
            user_valid = False
            common.logit("ERROR: Factory user (%s) account not created" % self.factory_user)
        #--- frontends user check ---
        for service_name in self.frontend_users_dict.keys():
            user = self.frontend_users_dict[service_name]
            self.frontend_users.append(user)
            try:
                group = self.get_groups(user)
            except:
                user_valid = False
                common.logit("ERROR: for frontend(%s), user (%s) account not created" % (service_name, user))
                continue
            if not self.frontend_groups.has_key(group):
                self.frontend_groups[group] = []
            # multiple users may share  the same group, so group them together
            self.frontend_groups[group].append(user)
        if user_valid == False:
            common.logerr("One or more errors have occurred. Please correct them.")

    def get_groups(self, user):
        try:
            groups = grp.getgrgid(pwd.getpwnam(user)[3])[0]
        except Exception:
            raise
        return groups

    def update(self):
        common.logit("\n--- Privilege Separation is in effect ---\nThe following directories/files are being created to support this.")
        #-- some validation on the condor install ---
        if not os.path.isdir(self.condor_location):
            common.logerr("The CONDOR_LOCATION specified does not exist: %s" % self.condor_location)
        #--- check for Condor switchboard ---
        if not os.path.isfile(self.switchboard_bin):
            common.logerr("Privilege separation binary (%s) does not exist. Do you have the right version of Condor?" % self.switchboard_bin)
        if os.stat(self.switchboard_bin)[stat.ST_UID] != 0:
            common.logerr("Privilege separation binary (%s) must be owned by root!" % self.switchboard_bin)
        #-- create the config file ---
        common.logit("... creating condor config file: %s" % (self.config_file))
        if not os.path.isdir(os.path.dirname(self.config_file)):
            os.mkdir(os.path.dirname(self.config_file))
        common.write_file("w", 0644, self.config_file, self.config_data())
        #-- setuid on swtichboard ---
        common.logit("... changing permissions on %s to %s" % (self.switchboard_bin, "04755"))
        os.chmod(self.switchboard_bin, 04755)
        #-- create factory directories ---
        #-- factory dirs done in Factory install --
        # self.factory.create_factory_dirs(self.factory.username(),0755)
        self.create_factory_client_dirs('root', 0755)
        common.logit("--- End of updates for Privilege Separation.--- ")

    def create_factory_client_dirs(self, owner, perm):
        dirs = [self.factory.client_log_dir(), self.factory.client_proxy_dir(), ]
        for dir_name in dirs:
            common.logit("... checking factory client directory: %s" % dir_name)
            if os.path.isdir(dir_name):
                if len(os.listdir(dir_name)) > 0:
                    common.ask_continue("This directory must be empty.  Can we delete the contents")
                    common.remove_dir_contents(dir_name)
            common.make_directory(dir_name, owner, perm)

    def remove(self):
        if not os.path.isfile(self.config_file):
            return
        if os.getuid() != 0:
            common.logit("\nA privilege separation config file exists but you are not root user\n so we cannot remove it at this time.")
            yn = common.ask_yn("Do you want to proceed")
            if yn == "n":
                common.logerr("Terminating at your request")

### end of class ###

##########################################
def main():
    try:
        import WMSCollector
        import Factory
        import VOFrontend
        wms = WMSCollector.WMSCollector("../weigand.ini")
        factory = Factory.Factory("../weigand.ini")
        frontend = VOFrontend.VOFrontend("../weigand.ini")
        privsep = PrivilegeSeparation(wms.condor_location(), factory, [frontend, ], {"vo_cms":"vo_cms"})
        privsep.validate_frontends()
    except KeyboardInterrupt:
        common.logit("\n... looks like you aborted this script... bye.")
        return 1
    except EOFError:
        common.logit("\n... looks like you aborted this script... bye.")
        return 1
    except common.WMSerror:
        print
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())

