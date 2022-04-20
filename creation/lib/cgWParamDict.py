from __future__ import absolute_import
from __future__ import print_function
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Glidein creation module
#   Classes and functions needed to handle dictionary files
#   created out of the parameter object
#

import os, os.path, shutil, string
import sys
import glob
from . import cgWDictFile, cWDictFile
from . import cgWCreate
from . import cgWConsts, cWConsts
from . import factoryXmlConfig
from . import cWExpand

#
# see the note in add_file_unparsed def below to understand
# why this is commented out for now
#
#from cWParamDict import is_true, add_file_unparsed

from glideinwms.lib import pubCrypto
from glideinwms.lib.util import str2bool
#from factoryXmlConfig import EntrySetElement

class UnconfiguredScheddError(Exception):

    def __init__(self, schedd):
        self.schedd = schedd
        self.err_str = "Schedd '%s' used by one or more entries is not configured." % (schedd)

    def __str__(self):
        return repr(self.err_str)


################################################
#
# This Class contains the main dicts
#
################################################

class glideinMainDicts(cgWDictFile.glideinMainDicts):
    def __init__(self, conf, workdir_name):
        submit_dir = conf.get_submit_dir()
        stage_dir = conf.get_stage_dir()
        monitor_dir = conf.get_monitor_dir()
        log_dir = conf.get_log_dir()
        client_log_dirs = conf.get_client_log_dirs()
        client_proxy_dirs = conf.get_client_proxy_dirs()
        cgWDictFile.glideinMainDicts.__init__(self, submit_dir, stage_dir, workdir_name,
                                              log_dir,
                                              client_log_dirs, client_proxy_dirs)
        self.monitor_dir = monitor_dir
        self.add_dir_obj(cWDictFile.monitorWLinkDirSupport(self.monitor_dir, self.work_dir))
        self.monitor_jslibs_dir = os.path.join(self.monitor_dir, 'jslibs')
        self.add_dir_obj(cWDictFile.simpleDirSupport(self.monitor_jslibs_dir, "monitor"))
        self.monitor_images_dir = os.path.join(self.monitor_dir, 'images')
        self.add_dir_obj(cWDictFile.simpleDirSupport(self.monitor_images_dir, "monitor"))
        self.enable_expansion = str2bool(conf.get('enable_attribute_expansion', 'False'))
        self.conf = conf
        self.active_sub_list = []
        self.disabled_sub_list = []
        self.monitor_jslibs = []
        self.monitor_images = []
        self.monitor_htmls = []

    def populate(self, other=None):
        # put default files in place first
        # Why placeholder and right after the file? error_gen, error_augment, setup_script, should be removed?
        self.dicts['file_list'].add_placeholder('error_gen.sh', allow_overwrite=True)
        self.dicts['file_list'].add_placeholder('error_augment.sh', allow_overwrite=True)
        self.dicts['file_list'].add_placeholder('setup_script.sh', allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.CONSTS_FILE, allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.VARS_FILE, allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE, allow_overwrite=True)  # this one must be loaded before any tarball
        self.dicts['file_list'].add_placeholder(cWConsts.GRIDMAP_FILE, allow_overwrite=True)  # this one must be loaded before setup_x509.sh is run
        # TODO: remove. these files are in the lists below, non need for defaults
        # self.dicts['file_list'].add_placeholder('singularity_lib.sh', allow_overwrite=True)  # this one must be loaded before singularity_setup.sh and any singularity wrapper are run
        # self.dicts['file_list'].add_placeholder('singularity_wrapper.sh', allow_overwrite=True)  # this one must be loaded after singularity_setup.sh and before any script running in singularity

        # Load system files
        for file_name in ('error_gen.sh', 'error_augment.sh', 'parse_starterlog.awk', 'advertise_failure.helper',
                          'condor_config', 'condor_config.multi_schedd.include',
                          'condor_config.dedicated_starter.include', 'condor_config.check.include',
                          'condor_config.monitor.include', 'glidein_lib.sh', 'singularity_lib.sh'):
            self.dicts['file_list'].add_from_file(file_name,
                                                  cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(file_name), 'regular'),
                                                  os.path.join(cgWConsts.WEB_BASE_DIR, file_name))
        self.dicts['description'].add("condor_config", "condor_config")
        self.dicts['description'].add("condor_config.multi_schedd.include", "condor_config_multi_include")
        self.dicts['description'].add("condor_config.dedicated_starter.include", "condor_config_main_include")
        self.dicts['description'].add("condor_config.monitor.include", "condor_config_monitor_include")
        self.dicts['description'].add("condor_config.check.include", "condor_config_check_include")
        self.dicts['vars'].load(cgWConsts.WEB_BASE_DIR, 'condor_vars.lst', change_self=False, set_not_changed=False)

        #
        # Note:
        #  We expect the condor platform info to be coming in as parameters
        #  as FE provided consts file is not available at this time
        #

        # add the basic standard params
        self.dicts['params'].add("GLIDEIN_Report_Failed", 'NEVER')
        self.dicts['params'].add("CONDOR_OS", 'default')
        self.dicts['params'].add("CONDOR_ARCH", 'default')
        self.dicts['params'].add("CONDOR_VERSION", 'default')

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('setup_script.sh', 'cat_consts.sh', 'condor_platform_select.sh', 'singularity_wrapper.sh'):
            self.dicts['file_list'].add_from_file(script_name,
                                                  cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(script_name), 'exec'),
                                                  os.path.join(cgWConsts.WEB_BASE_DIR, script_name))

        #load condor tarballs
        # only one will be downloaded in the end... based on what condor_platform_select.sh decides
        condor_tarballs = self.conf.get_child_list(u'condor_tarballs')

        prev_tar_dir_map = {}
        if other is not None and 'CondorTarballDirMap' in other.main_dicts.dicts['glidein']:
            prev_tar_dir_map = eval(other.main_dicts.dicts['glidein']['CondorTarballDirMap'])

        tar_dir_map = {}

        for condor_idx in range(len(condor_tarballs)):
            condor_el=condor_tarballs[condor_idx]

            # condor_el now is a combination of csv version+os+arch
            # Get list of valid tarballs for this condor_el
            # Register the tarball, but make download conditional to cond_name

            condor_el_valid_tarballs = get_valid_condor_tarballs([condor_el])
            condor_fname = cWConsts.insert_timestr(cgWConsts.CONDOR_FILE % condor_idx)
            condor_fd = None

            if u'tar_file' in condor_el:
                # Condor tarball available. Just add it to the list of tarballs
                # with every possible condor_platform string
                condor_tarfile = condor_el[u'tar_file']
            # already built this tarball, just reuse it
            elif condor_el[u'base_dir'] in prev_tar_dir_map:
                condor_tarfile = prev_tar_dir_map[condor_el[u'base_dir']]
                tar_dir_map[condor_el[u'base_dir']] = condor_tarfile
            else:
                # Create a new tarball as usual
                condor_fd = cgWCreate.create_condor_tar_fd(condor_el[u'base_dir'])
                tar_dir_map[condor_el[u'base_dir']] = os.path.join(self.dicts['file_list'].dir, condor_fname)

            for tar in condor_el_valid_tarballs:
                condor_platform = "%s-%s-%s" % (tar['version'], tar['os'],
                                                tar['arch'])
                cond_name = "CONDOR_PLATFORM_%s" % condor_platform
                condor_platform_fname = cgWConsts.CONDOR_FILE % condor_platform

                if condor_fd is None:
                    # tar file exists. Just use it
                    self.dicts['file_list'].add_from_file(
                        condor_platform_fname,
                        cWDictFile.FileDictFile.make_val_tuple(condor_fname, 'untar',
                                                               cond_download=cond_name,
                                                               config_out=cgWConsts.CONDOR_ATTR),
                        condor_tarfile
                    )
                else:
                    # This is addition of new tarfile
                    # Need to rewind fd every time
                    condor_fd.seek(0)
                    self.dicts['file_list'].add_from_fd(
                        condor_platform_fname,
                        cWDictFile.FileDictFile.make_val_tuple(condor_fname, 'untar',
                                                               cond_download=cond_name,
                                                               config_out=cgWConsts.CONDOR_ATTR),
                        condor_fd
                    )

                self.dicts['untar_cfg'].add(condor_platform_fname,
                                            cgWConsts.CONDOR_DIR)
                # Add cond_name in the config, so that it is known
                # But leave it disabled by default
                self.dicts['consts'].add(cond_name, "0",
                                         allow_overwrite=False)
            if condor_fd is not None:
                condor_fd.close()

        self.dicts['glidein'].add('CondorTarballDirMap', str(tar_dir_map))

        #
        # Note:
        #  We expect the collector info to be coming in as parameter
        #  as FE consts file is not available at this time
        #

        # add the basic standard params
        self.dicts['params'].add("GLIDEIN_Collector", 'Fake')

        # add the factory monitoring collector parameter, if any collectors are defined
        # this is purely a factory thing
        factory_monitoring_collector=calc_monitoring_collectors_string(self.conf.get_child_list(u'monitoring_collectors'))
        if factory_monitoring_collector is not None:
            self.dicts['params'].add('GLIDEIN_Factory_Collector', str(factory_monitoring_collector))
        populate_gridmap(self.conf, self.dicts['gridmap'])

        file_list_scripts = ['collector_setup.sh',
                             'create_temp_mapfile.sh',
                             'gwms-python',
                             cgWConsts.CONDOR_STARTUP_FILE]
        # These are right after the entry, before some VO scripts. The order in the following list is important
        at_file_list_scripts = ['singularity_setup.sh',
                                'condor_chirp']
        # The order in the following list is important
        after_file_list_scripts = ['check_proxy.sh',
                                   'create_mapfile.sh',
                                   'validate_node.sh',
                                   'setup_network.sh',
                                   'java_setup.sh',
                                   'glidein_memory_setup.sh',
                                   'glidein_cpus_setup.sh',  # glidein_cpus_setup.sh must be before smart_partitionable.sh
                                   'glidein_sitewms_setup.sh',
                                   'script_wrapper.sh',
                                   'smart_partitionable.sh',
                                   'cvmfs_setup.sh',
                                   'cvmfs_umount.sh']
        # Only execute scripts once
        duplicate_scripts = list(set(file_list_scripts).intersection(after_file_list_scripts))
        duplicate_scripts += list(set(file_list_scripts).intersection(at_file_list_scripts))
        duplicate_scripts += list(set(at_file_list_scripts).intersection(after_file_list_scripts))
        if duplicate_scripts:
            raise RuntimeError("Duplicates found in the list of files to execute '%s'" % ','.join(duplicate_scripts))

        # Load more system scripts
        for script_name in file_list_scripts:
            self.dicts['file_list'].add_from_file(script_name,
                                                  cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(script_name), 'exec'),
                                                  os.path.join(cgWConsts.WEB_BASE_DIR, script_name))

        # Add the x509 setup script. It is periodical since it will refresh the pilot as well
        x509script = 'setup_x509.sh'
        self.dicts['file_list'].add_from_file(x509script,
                                              cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(x509script), 'exec', 60, 'NOPREFIX'),
                                              os.path.join(cgWConsts.WEB_BASE_DIR, x509script))

        # Add the drainer script
        drain_script = "check_wn_drainstate.sh"
        self.dicts['file_list'].add_from_file(drain_script,
                                              cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(drain_script), 'exec', 60, 'NOPREFIX'),
                                              os.path.join(cgWConsts.WEB_BASE_DIR, drain_script))

        # Add the MJF script
        mjf_script = "mjf_setparams.sh"
        self.dicts['file_list'].add_from_file(mjf_script,
                                              cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(mjf_script), 'exec', 1800, 'MJF_'),
                                              os.path.join(cgWConsts.WEB_BASE_DIR, mjf_script))

        # Add pychirp
        pychirp_tarball = "htchirp.tar.gz"
        self.dicts['file_list'].add_from_file(pychirp_tarball,
                                              cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(pychirp_tarball), 'untar'),
                                              os.path.join(cgWConsts.WEB_BASE_DIR, pychirp_tarball))
        self.dicts['untar_cfg'].add(pychirp_tarball, "lib/python/htchirp")

        # Add cvmfsexec
        cvmfsexec_utils = "cvmfs_utils.tar.gz"
        self.dicts["file_list"].add_from_file(
            cvmfsexec_utils,
            cWDictFile.FileDictFile.make_val_tuple(
                cWConsts.insert_timestr(cvmfsexec_utils), "untar", cond_download="GLIDEIN_USE_CVMFSEXEC"
            ),
            os.path.join(cgWConsts.WEB_BASE_DIR, cvmfsexec_utils),
        )
        self.dicts["untar_cfg"].add(cvmfsexec_utils, "cvmfs_utils")

        # adding cvmfsexec distribution tarballs to the default list of uploads
        # NOTE: the distribution tarballs are created during factory reconfig or upgrade
        dist_select_script = "cvmfsexec_platform_select.sh"
        self.dicts["file_list"].add_from_file(
            dist_select_script,
            cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(dist_select_script), "exec"),
            os.path.join(cgWConsts.WEB_BASE_DIR, dist_select_script),
        )

        # get the location of the tarballs created during reconfig/upgrade
        distros_loc = os.path.abspath("/tmp/cvmfsexec_pkg/tarballs")
        distros = os.listdir(distros_loc)
        for cvmfsexec_idx in range(len(distros)):  # TODO: os.scandir() is more efficient with python 3.x
            distro_info = distros[cvmfsexec_idx].split("_")
            distro_arch = (distro_info[3] + "_" + distro_info[4]).split(".")[0]
            # register the tarball, but make download conditional to cond_name
            cvmfsexec_fname = cWConsts.insert_timestr(cgWConsts.CVMFSEXEC_DISTRO_FILE % cvmfsexec_idx)

            platform = f"{distro_info[1]}-{distro_info[2]}-{distro_arch}"
            cvmfsexec_cond_name = "CVMFSEXEC_PLATFORM_%s" % platform
            cvmfsexec_platform_fname = cgWConsts.CVMFSEXEC_DISTRO_FILE % platform

            self.dicts["file_list"].add_from_file(
                cvmfsexec_platform_fname,
                cWDictFile.FileDictFile.make_val_tuple(
                    cvmfsexec_fname, "untar", cond_download=cvmfsexec_cond_name, config_out=cgWConsts.CVMFSEXEC_ATTR
                ),
                os.path.join(distros_loc, distros[cvmfsexec_idx]),
            )

            self.dicts["untar_cfg"].add(cvmfsexec_platform_fname, cgWConsts.CVMFSEXEC_DIR)
            # Add cond_name in the config, so that it is known
            # But leave it disabled by default
            self.dicts["consts"].add(cvmfsexec_cond_name, "0", allow_overwrite=False)
        # end of "Add cvmfsexec" block

        # make sure condor_startup does not get executed ahead of time under normal circumstances
        # but must be loaded early, as it also works as a reporting script in case of error
        self.dicts['description'].add(cgWConsts.CONDOR_STARTUP_FILE, "last_script")

        # At this point in the glideins, condor_advertise should be able to
        # talk to the FE collector

        # put user files in stage
        for file in self.conf.get_child_list(u'files'):
            add_file_unparsed(file, self.dicts, True)

        # put user attributes into config files
        for attr in self.conf.get_child_list(u'attrs'):
            # ignore attributes that need expansion in the global section
            if str(attr.get_val()).find('$') == -1 or not self.enable_expansion:  # does not need to be expanded
                add_attr_unparsed(attr, self.dicts, "main")

        # add additional system scripts
        for script_name in at_file_list_scripts:
            self.dicts['at_file_list'].add_from_file(script_name,
                                                     cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(script_name), 'exec'),
                                                     os.path.join(cgWConsts.WEB_BASE_DIR, script_name))
        for script_name in after_file_list_scripts:
            self.dicts['after_file_list'].add_from_file(script_name,
                                                        cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(script_name), 'exec'),
                                                        os.path.join(cgWConsts.WEB_BASE_DIR, script_name))

        # populate complex files
        populate_factory_descript(self.work_dir, self.dicts['glidein'],
                                  self.active_sub_list, self.disabled_sub_list,
                                  self.conf)
        populate_frontend_descript(self.dicts['frontend_descript'], self.conf)

        # populate the monitor files
        javascriptrrd_dir = self.conf.get_child(u'monitor')[u'javascriptRRD_dir']
        for mfarr in ((cgWConsts.WEB_BASE_DIR, 'factory_support.js'),
                      (javascriptrrd_dir, 'javascriptrrd.wlibs.js')):
            mfdir, mfname=mfarr
            parent_dir = self.find_parent_dir(mfdir, mfname)
            mfobj=cWDictFile.SimpleFile(parent_dir, mfname)
            mfobj.load()
            self.monitor_jslibs.append(mfobj)

        for mfarr in ((cgWConsts.WEB_BASE_DIR, 'factoryRRDBrowse.html'),
                      (cgWConsts.WEB_BASE_DIR, 'factoryRRDEntryMatrix.html'),
                      (cgWConsts.WEB_BASE_DIR, 'factoryStatus.html'),
                      (cgWConsts.WEB_BASE_DIR, 'factoryLogStatus.html'),
                      (cgWConsts.WEB_BASE_DIR, 'factoryCompletedStats.html'),
                      (cgWConsts.WEB_BASE_DIR, 'factoryStatusNow.html'),
                      (cgWConsts.WEB_BASE_DIR, 'factoryEntryStatusNow.html')):
            mfdir, mfname=mfarr
            mfobj=cWDictFile.SimpleFile(mfdir, mfname)
            mfobj.load()
            self.monitor_htmls.append(mfobj)

        # add the index page and its images
        mfobj=cWDictFile.SimpleFile(cgWConsts.WEB_BASE_DIR + '/factory/', 'index.html')
        mfobj.load()
        self.monitor_htmls.append(mfobj)
        for imgfile in ('factoryCompletedStats.png',
                        'factoryEntryStatusNow.png',
                        'factoryLogStatus.png',
                        'factoryRRDBrowse.png',
                        'factoryRRDEntryMatrix.png',
                        'factoryStatus.png',
                        'factoryStatusNow.png'):
            mfobj=cWDictFile.SimpleFile(cgWConsts.WEB_BASE_DIR + '/factory/images/', imgfile)
            mfobj.load()
            self.monitor_images.append(mfobj)

        # populate the monitor configuration file
        #populate_monitor_config(self.work_dir,self.dicts['glidein'],params)

    def find_parent_dir(self, search_path, name):
        """ Given a search path, determine if the given file exists
            somewhere in the path.
            Returns: if found. returns the parent directory
                     if not found, raises an Exception
        """
        for root, dirs, files in os.walk(search_path, topdown=True):
            for file_name in files:
                if file_name == name:
                    return root
        raise RuntimeError("Unable to find %(file)s in %(dir)s path" % { "file": name,  "dir": search_path, })

    # reuse as much of the other as possible
    def reuse(self, other):             # other must be of the same class
        if self.monitor_dir != other.monitor_dir:
            print("WARNING: main monitor base_dir has changed, stats may be lost: '%s'!='%s'" % (self.monitor_dir, other.monitor_dir))
        return cgWDictFile.glideinMainDicts.reuse(self, other)

    def save(self, set_readonly=True):
        cgWDictFile.glideinMainDicts.save(self, set_readonly)
        self.save_pub_key()
        self.save_monitor()
        self.save_monitor_config(self.work_dir, self.dicts['glidein'])

    ########################################
    # INTERNAL
    ########################################

    def save_pub_key(self):
        sec_el = self.conf.get_child(u'security')
        if u'pub_key' not in sec_el:
            pass # nothing to do
        elif sec_el[u'pub_key']=='RSA':
            rsa_key_fname=os.path.join(self.work_dir, cgWConsts.RSA_KEY)

            if not os.path.isfile(rsa_key_fname):
                # create the key only once

                # touch the file with correct flags first
                # I have no way to do it in  RSAKey class
                fd=os.open(rsa_key_fname, os.O_CREAT, 0o600)
                os.close(fd)

                key_obj=pubCrypto.RSAKey()
                key_obj.new(int(sec_el[u'key_length']))
                key_obj.save(rsa_key_fname)
        else:
            raise RuntimeError("Invalid value for security.pub_key(%s), must be either None or RSA"%sec_el[u'pub_key'])

    def save_monitor(self):
        for fobj in self.monitor_jslibs:
            fobj.save(dir=self.monitor_jslibs_dir, save_only_if_changed=False)
        for fobj in self.monitor_images:
            fobj.save(dir=self.monitor_images_dir, save_only_if_changed=False)
        for fobj in self.monitor_htmls:
            fobj.save(dir=self.monitor_dir, save_only_if_changed=False)
        return

    ###################################
    # Create the monitor config file
    def save_monitor_config(self, work_dir, glidein_dict):
        monitor_config_file = os.path.join(self.conf.get_monitor_dir(), cgWConsts.MONITOR_CONFIG_FILE)
        monitor_config_line = []

        monitor_config_fd = open(monitor_config_file, 'w')
        monitor_config_line.append("<monitor_config>")
        monitor_config_line.append("  <entries>")
        try:
            try:
                for entry in self.conf.get_entries():
                    if eval(entry[u'enabled'], {}, {}):
                        monitor_config_line.append("    <entry name=\"%s\">" % entry.getName())
                        monitor_config_line.append("      <monitorgroups>")
                        for group in entry.get_child_list(u'monitorgroups'):
                            monitor_config_line.append("        <monitorgroup group_name=\"%s\">" % group[u'group_name'])
                            monitor_config_line.append("        </monitorgroup>")

                        monitor_config_line.append("      </monitorgroups>")
                        monitor_config_line.append("    </entry>")

                monitor_config_line.append("  </entries>")
                monitor_config_line.append("</monitor_config>")

                for line in monitor_config_line:
                    monitor_config_fd.write(line + "\n")
            except IOError as e:
                raise RuntimeError("Error writing into file %s"%monitor_config_file)
        finally:
            monitor_config_fd.close()


################################################
#
# This Class contains the entry and entry set dicts
#
################################################

class glideinEntryDicts(cgWDictFile.glideinEntryDicts):
    def __init__(self, conf, sub_name,
                 summary_signature, workdir_name):
        self.conf=conf
        self.entry_name=sub_name
        submit_dir = conf.get_submit_dir()
        stage_dir = conf.get_stage_dir()
        monitor_dir = conf.get_monitor_dir()
        log_dir = conf.get_log_dir()
        client_log_dirs = conf.get_client_log_dirs()
        client_proxy_dirs = conf.get_client_proxy_dirs()
        cgWDictFile.glideinEntryDicts.__init__(self, submit_dir, stage_dir, sub_name, summary_signature, workdir_name,
                                               log_dir, client_log_dirs, client_proxy_dirs)

        self.enable_expansion = str2bool(conf.get('enable_attribute_expansion', 'False'))
        self.monitor_dir=cgWConsts.get_entry_monitor_dir(monitor_dir, sub_name)
        self.add_dir_obj(cWDictFile.monitorWLinkDirSupport(self.monitor_dir, self.work_dir))

    def erase(self):
        cgWDictFile.glideinEntryDicts.erase(self)
        for entry in self.conf.get_entries():
            if entry.getName()==self.entry_name:
                break
        else:
            # This happens when old_dictionary contains something (e.g.: entries are removed from the conf)
            entry = None
        if entry and isinstance(entry, factoryXmlConfig.EntrySetElement):
            self.dicts['condor_jdl'] = []
            for sub_entry in entry.get_subentries():
                self.dicts['condor_jdl'].append(cgWCreate.GlideinSubmitDictFile(self.work_dir,
                                                os.path.join(self.work_dir, cgWConsts.SUBMIT_FILE_ENTRYSET % sub_entry.getName())))
        else:
            self.dicts['condor_jdl'] = [cgWCreate.GlideinSubmitDictFile(self.work_dir, cgWConsts.SUBMIT_FILE)]

    def load(self):
        cgWDictFile.glideinEntryDicts.load(self)
        for cj in self.dicts['condor_jdl']:
            cj.load()

    def save_final(self,set_readonly=True):
        sub_stage_dir = cgWConsts.get_entry_stage_dir("", self.sub_name)

        # Let's remove the job.condor single entry file (in case the entry_set has the same name of an old entry)
        if len(self.dicts['condor_jdl']) > 1:
            fname = os.path.join(self.work_dir, cgWConsts.SUBMIT_FILE)
            if os.path.isfile(fname):
                os.remove(fname)

        for cj in self.dicts['condor_jdl']:
            cj.finalize(self.summary_signature['main'][0], self.summary_signature[sub_stage_dir][0],
                        self.summary_signature['main'][1],self.summary_signature[sub_stage_dir][1])
            cj.save(set_readonly=set_readonly)

    def populate(self, entry, schedd, main_dicts):
        """Populate the entry dictionary

        Args:
            entry:
            schedd:
            main_dicts:

        Returns:

        """
        # put default files in place first
        self.dicts['file_list'].add_placeholder(cWConsts.CONSTS_FILE, allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.VARS_FILE, allow_overwrite=True)
        self.dicts['file_list'].add_placeholder(cWConsts.UNTAR_CFG_FILE, allow_overwrite=True) # this one must be loaded before any tarball

        # follow by the blacklist file
        file_name=cWConsts.BLACKLIST_FILE
        self.dicts['file_list'].add_from_file(file_name,
                                              cWDictFile.FileDictFile.make_val_tuple(file_name, 'nocache', config_out='BLACKLIST_FILE'),
                                              os.path.join(cgWConsts.WEB_BASE_DIR, file_name))

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ('cat_consts.sh', "check_blacklist.sh"):
            self.dicts['file_list'].add_from_file(script_name,
                                                  cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(script_name), 'exec'),
                                                  os.path.join(cgWConsts.WEB_BASE_DIR, script_name))

        #load system files
        self.dicts['vars'].load(cgWConsts.WEB_BASE_DIR, 'condor_vars.lst.entry', change_self=False, set_not_changed=False)

        # put user files in stage
        for user_file in entry.get_child_list(u'files'):
            add_file_unparsed(user_file, self.dicts, True)

        # Add attribute for voms

        entry_attrs = entry.get_child_list(u'attrs')

        # Insert the global values that need to be expanded and had been skipped in the global section
        # will be in the entry section now
        for attr in self.conf.get_child_list(u'attrs'):
            if str(attr.get_val()).find('$') != -1 and self.enable_expansion:
                if not (attr[u'name'] in [i[u'name'] for i in entry_attrs]):
                    add_attr_unparsed(attr, self.dicts, self.sub_name)
                # else the entry value will override it later on (here below)

        # put user attributes into config files
        for attr in entry_attrs:
            add_attr_unparsed(attr, self.dicts, self.sub_name)

        # put standard attributes into config file
        # override anything the user set
        config = entry.get_child(u'config')
        restrictions = config.get_child(u'restrictions')
        submit = config.get_child(u'submit')
        for dtype in ('attrs', 'consts'):
            self.dicts[dtype].add("GLIDEIN_Gatekeeper", entry[u'gatekeeper'], allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_GridType", entry[u'gridtype'], allow_overwrite=True)
            # MERGENOTE:
            # GLIDEIN_REQUIRE_VOMS publishes an attribute so that users
            # without VOMS proxies can avoid sites that require VOMS proxies
            # using the normal Condor Requirements string.
            self.dicts[dtype].add("GLIDEIN_REQUIRE_VOMS", restrictions[u'require_voms_proxy'], allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_TrustDomain", entry[u'trust_domain'], allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_SupportedAuthenticationMethod", entry[u'auth_method'], allow_overwrite=True)
            if u'rsl' in entry:
                self.dicts[dtype].add('GLIDEIN_GlobusRSL', entry[u'rsl'], allow_overwrite=True)
            if u'bosco_dir' in entry:
                self.dicts[dtype].add('GLIDEIN_BoscoDir', entry[u'bosco_dir'], allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_SlotsLayout", submit[u'slots_layout'], allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_WorkDir", entry[u'work_dir'], allow_overwrite=True)
            self.dicts[dtype].add("GLIDEIN_Verbosity", entry[u'verbosity'], allow_overwrite=True)
            if u'proxy_url' in entry:
                self.dicts[dtype].add("GLIDEIN_ProxyURL", entry[u'proxy_url'], allow_overwrite=True)

        summed_attrs={}
        if self.enable_expansion:
            # we now have all the attributes... do the expansion
            # first, let's merge the attributes
            for d in (main_dicts['attrs'], self.dicts['attrs']):
                for k in d.keys:
                    # if the same key is in both global and entry (i.e. local), entry wins
                    summed_attrs[k] = d[k]

            for dname in ('attrs','consts','params'):
                for attr_name in self.dicts[dname].keys:
                    if ((type(self.dicts[dname][attr_name]) in (type('a'), type(u'a'))) and
                        (self.dicts[dname][attr_name].find('$') != -1)):
                        self.dicts[dname].add(attr_name,
                                              cWExpand.expand_DLR(self.dicts[dname][attr_name], summed_attrs),
                                              allow_overwrite=True)

        self.dicts['vars'].add_extended("GLIDEIN_REQUIRE_VOMS", "boolean", restrictions[u'require_voms_proxy'], None, False, True, True)

        # populate infosys
        for infosys_ref in entry.get_child_list(u'infosys_refs'):
            self.dicts['infosys'].add_extended(infosys_ref[u'type'], infosys_ref[u'server'], infosys_ref[u'ref'], allow_overwrite=True)

        # populate monitorgroups
        for monitorgroup in entry.get_child_list(u'monitorgroups'):
            self.dicts['mongroup'].add_extended(monitorgroup[u'group_name'], allow_overwrite=True)

        # populate complex files
        populate_job_descript(self.work_dir, self.dicts['job_descript'], self.conf.num_factories,
                              self.sub_name, entry, schedd, summed_attrs, self.enable_expansion)

        # Now that we have the EntrySet fill the condor_jdl for its entries
        if isinstance(entry, factoryXmlConfig.EntrySetElement):
            for subentry in entry.get_child_list(u'entries'):
                entry.select(subentry)
                # Find subentry
                for cj in self.dicts[u'condor_jdl']:
                    cj_entryname = cj.fname.split('.')[1]
                    if cj_entryname==subentry.getName():
                        cj.populate(cgWConsts.STARTUP_FILE, self.sub_name, self.conf, entry)
                        break
                entry.select(None)
        else:
            ################################################################################################################
            # This is the original function call:
            #
            # self.dicts['condor_jdl'].populate(cgWConsts.STARTUP_FILE,
            #                                   params.factory_name,params.glidein_name,self.sub_name,
            #                                   sub_params.gridtype,sub_params.gatekeeper, sub_params.rsl, sub_params.auth_method,
            #                                   params.web_url,sub_params.proxy_url,sub_params.work_dir,
            #                                   params.submit.base_client_log_dir, sub_params.submit.submit_attrs)
            #
            # Almost all of the parameters are attributes of params and/or sub_params.  Instead of maintaining an ever
            # increasing parameter list for this function, lets just pass params, sub_params, and the 2 other parameters
            # to the function and call it a day.
            ################################################################################################################
            self.dicts[u'condor_jdl'][0].populate(cgWConsts.STARTUP_FILE, self.sub_name, self.conf, entry)

    # reuse as much of the other as possible
    def reuse(self, other):             # other must be of the same class
        if self.monitor_dir != other.monitor_dir:
            print("WARNING: entry monitor base_dir has changed, stats may be lost: '%s'!='%s'" % (self.monitor_dir, other.monitor_dir))
        return cgWDictFile.glideinEntryDicts.reuse(self, other)


################################################
#
# This Class contains both the main, the entry,
# and the entry set dicts
#
################################################

class glideinDicts(cgWDictFile.glideinDicts):
    def __init__(self, conf,
                 sub_list=None):  # if None, get it from params
        if sub_list is None:
            sub_list = [e.getName() for e in conf.get_entries()]

        self.conf = conf
        submit_dir = conf.get_submit_dir()
        stage_dir = conf.get_stage_dir()
        monitor_dir = conf.get_monitor_dir()
        log_dir = conf.get_log_dir()
        client_log_dirs = conf.get_client_log_dirs()
        client_proxy_dirs = conf.get_client_proxy_dirs()
        cgWDictFile.glideinDicts.__init__(self, submit_dir, stage_dir, log_dir, client_log_dirs, client_proxy_dirs, sub_list)

        self.monitor_dir = monitor_dir
        self.active_sub_list = []
        self.enable_expansion = str2bool(conf.get('enable_attribute_expansion', 'False'))

        return

    def populate(self, other=None):  # will update params (or self.params)
        self.main_dicts.populate(other)
        self.active_sub_list = self.main_dicts.active_sub_list

        schedds = self.conf[u'schedd_name'].split(u',')
        schedd_counts = {}
        for s in schedds:
            schedd_counts[s] = 0

        prev_entries = {}

        # count all schedds we will reuse and keep track of the entries
        if other is not None:
            for entry in self.conf.get_entries():
                entry_name = entry.getName()
                if entry_name in other.sub_dicts:
                    schedd = other.sub_dicts[entry_name]['job_descript']['Schedd']
                    if schedd in schedd_counts:
                        prev_entries[entry_name] = schedd
                        # always reuse the old schedd but only count it against us if the entry is active
                        if eval(entry[u'enabled']):
                            schedd_counts[schedd] += 1

        # now that we have the counts, populate with the best schedd
        for entry in self.conf.get_entries():
            entry_name = entry.getName()
            if entry_name in prev_entries:
                schedd = prev_entries[entry_name]
            else:
                # pick the schedd with the lowest count
                schedd = sorted(schedd_counts, key=schedd_counts.get)[0]
                # only count it against us if new entry is active
                if eval(entry[u'enabled']):
                    schedd_counts[schedd] += 1
            self.sub_dicts[entry_name].populate(entry, schedd, self.main_dicts.dicts)
            # MM5345 self.sub_dicts[entry_name].populate(self.main_dicts.dicts, other)

        validate_condor_tarball_attrs(self.conf)

    # reuse as much of the other as possible
    def reuse(self, other):             # other must be of the same class
        if self.monitor_dir != other.monitor_dir:
            print("WARNING: monitor base_dir has changed, stats may be lost: '%s'!='%s'" % (self.monitor_dir, other.monitor_dir))
        return cgWDictFile.glideinDicts.reuse(self, other)

    ###########
    # PRIVATE
    ###########

    ######################################
    def sortit(self, unsorted_dict):
        """ A temporary method for sorting a dictionary based on
            the value of the dictionary item.  In python 2.4+,
            a 'key' arguement can be used in the 'sort' and 'sorted'
            functions.  This is not available in python 2.3.4/SL4
            platforms.
            Returns a sorted list of the dictionary items based on
            their value.
        """
        d = {}
        i = 0
        for key in unsorted_dict.keys():
            d[i] = (key, unsorted_dict[key])
            i = i + 1
        temp_list = sorted([ (x[1][1], x[0]) for x in d.items() ])
        sortedList = []
        for (tmp, key) in temp_list:
            sortedList.append(d[key][0])
        return sortedList

    ######################################
    # Redefine methods needed by parent
    def new_MainDicts(self):
        return glideinMainDicts(self.conf, self.workdir_name)

    def new_SubDicts(self, sub_name):
        return glideinEntryDicts(self.conf, sub_name,
                                 self.main_dicts.get_summary_signature(), self.workdir_name)


############################################################
#
# P R I V A T E - Do not use
#
############################################################

#############################################
# Add a user file residing in the stage area
# file as described by Params.file_defaults
#
# !!! NOTE !!! keep using this function in factory. Until
# FE code is updated to use new xml parsing we can't use
# the common cWParamDict version
#
# is_factory is just a dummy placeholder to make the transition easier later
def add_file_unparsed(user_file, dicts, is_factory):
    absfname = user_file['absfname']

    if 'relfname' not in user_file:
        relfname = os.path.basename(absfname)  # defualt is the final part of absfname
    else:
        relfname = user_file['relfname']

    is_const = eval(user_file['const'])
    is_executable = eval(user_file['executable'])
    is_wrapper = eval(user_file['wrapper'])
    do_untar = eval(user_file['untar'])

    prefix = user_file['prefix']

    period_value = int(user_file['period'])

    file_list_idx = 'file_list'
    if 'after_entry' in user_file:
        if eval(user_file['after_entry']):
            file_list_idx = 'after_file_list'

    if is_executable:  # a script
        dicts[file_list_idx].add_from_file(relfname,
                                           cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname), 'exec', period_value, prefix),
                                           absfname)
    elif is_wrapper:  # a source-able script for the wrapper
        dicts[file_list_idx].add_from_file(relfname,
                                           cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname), 'wrapper'),
                                           absfname)
    elif do_untar:  # a tarball
        untar_opts = user_file.get_child('untar_options')
        if u'dir' in untar_opts:
            wnsubdir = untar_opts['dir']
        else:
            wnsubdir = string.split(relfname, '.', 1)[0]  # default is relfname up to the first .

        if 'absdir_outattr' in untar_opts:
            config_out = untar_opts['absdir_outattr']
        else:
            config_out = 'FALSE'
        cond_attr = untar_opts['cond_attr']

        dicts[file_list_idx].add_from_file(relfname,
                                           cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname),
                                                                                  'untar',
                                                                                  cond_download=cond_attr,
                                                                                  config_out=config_out),
                                           absfname)
        dicts['untar_cfg'].add(relfname, wnsubdir)
    else:  # not executable nor tarball => simple file
        if is_const:
            val = 'regular'
            dicts[file_list_idx].add_from_file(relfname,
                                               cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname), val),
                                               absfname)
        else:
            val = 'nocache'
            dicts[file_list_idx].add_from_file(relfname,
                                               cWDictFile.FileDictFile.make_val_tuple(relfname, val),
                                               absfname)  # no timestamp if it can be modified


#######################
# Register an attribute
# attr_obj as described by Params.attr_defaults
def add_attr_unparsed(attr, dicts, description):
    try:
        add_attr_unparsed_real(attr, dicts)
    except RuntimeError as e:
        raise RuntimeError("Error parsing attr %s[%s]: %s" % (description, attr[u'name'], str(e)))


def validate_attribute(attr_name, attr_val):
    """Check the attribute value is valid. Otherwise throw RuntimeError"""
    if not attr_name or not attr_val:
        return
    # Consider adding a common one in cWParamDict
    # Series of if/elif sections validating the attributes
    if attr_name == "GLIDEIN_SINGULARITY_REQUIRE":
        if attr_val.lower == 'true':
            raise RuntimeError("Invalid value for GLIDEIN_SINGULARITY_REQUIRE: use REQUIRED or REQUIRED_GWMS instead of True")
        if attr_val not in ('REQUIRED_GWMS', 'NEVER', 'OPTIONAL', 'PREFERRED', 'REQUIRED'):
            raise RuntimeError("Invalid value for GLIDEIN_SINGULARITY_REQUIRE: %s not in REQUIRED_GWMS, NEVER, OPTIONAL, PREFERRED, REQUIRED." %
                               attr_val)


def add_attr_unparsed_real(attr, dicts):
    attr_name = attr[u'name']
    do_publish = eval(attr[u'publish'], {}, {})
    is_parameter = eval(attr[u'parameter'], {}, {})
    is_const = eval(attr[u'const'], {}, {})
    attr_val = attr.get_val()

    validate_attribute(attr_name, attr_val)

    # Validation of consistent combinations od publish, parameter and const has been removed somewhere after
    #  63e06efb33ba0bdbd2df6509e50c6e02d42c482c
    #  dicts['attrs'] instead of dicts['consts'] was populated when both do_publish and is_parameter are fales
    #  (and is_const is true)
    if do_publish:  # publish in factory ClassAd
        if is_parameter:  # but also push to glidein
            if is_const:
                dicts['attrs'].add(attr_name, attr_val)
                dicts['consts'].add(attr_name, attr_val)
            else:
                dicts['params'].add(attr_name, attr_val)
        else:  # only publish
            dicts['attrs'].add(attr_name, attr_val)
            dicts['consts'].add(attr_name, attr_val)
    else:  # do not publish, only to glidein
        dicts['consts'].add(attr_name, attr_val)

    do_glidein_publish = eval(attr[u'glidein_publish'], {}, {})
    do_job_publish = eval(attr[u'job_publish'], {}, {})

    if do_glidein_publish or do_job_publish:
            # need to add a line only if will be published
            if attr_name in dicts['vars']:
                # already in the var file, check if compatible
                attr_var_el = dicts['vars'][attr_name]
                attr_var_type = attr_var_el[0]
                if (((attr[u'type'] == "int") and (attr_var_type != 'I')) or
                    ((attr[u'type'] == "expr") and (attr_var_type == 'I')) or
                    ((attr[u'type'] == "string") and (attr_var_type == 'I'))):
                    raise RuntimeError("Types not compatible (%s,%s)" % (attr[u'type'], attr_var_type))
                attr_var_export = attr_var_el[4]
                if do_glidein_publish and (attr_var_export == 'N'):
                    raise RuntimeError("Cannot force glidein publishing")
                attr_var_job_publish = attr_var_el[5]
                if do_job_publish and (attr_var_job_publish == '-'):
                    raise RuntimeError("Cannot force job publishing")
            else:
                dicts['vars'].add_extended(attr_name, attr[u'type'], None, None, False,
                                           do_glidein_publish, do_job_publish)


##################################
# Used in populate_factory_descript for compatibility with Python 2.4
def iter_to_dict(dictObject):
    """Traverses a iterable (DictMixin) recursively to convert to proper dict any nested classes"""
    newDict = {}
    try:
        for prop, val in dictObject.iteritems():
            newDict[prop] = iter_to_dict(val)
        return newDict
    except AttributeError:
        return dictObject


###################################
# Create the glidein descript file
def populate_factory_descript(work_dir, glidein_dict,
                              active_sub_list,        # will be modified
                              disabled_sub_list,        # will be modified
                              conf):

        down_fname = os.path.join(work_dir, 'glideinWMS.downtimes')

        sec_el = conf.get_child(u'security')
        sub_el = conf.get_child(u'submit')
        mon_foot_el = conf.get_child(u'monitor_footer')
        if u'factory_collector' in conf:
            glidein_dict.add('FactoryCollector', conf[u'factory_collector'])
        else:
            glidein_dict.add('FactoryCollector', None)
        glidein_dict.add('FactoryName', conf[u'factory_name'])
        glidein_dict.add('GlideinName', conf[u'glidein_name'])
        glidein_dict.add('WebURL', conf.get_web_url())
        glidein_dict.add('PubKeyType', sec_el[u'pub_key'])
        glidein_dict.add('OldPubKeyGraceTime', sec_el[u'reuse_oldkey_onstartup_gracetime'])
        glidein_dict.add('MonitorUpdateThreadCount', conf.get_child(u'monitor')[u'update_thread_count'])
        glidein_dict.add('RemoveOldCredFreq', sec_el[u'remove_old_cred_freq'])
        glidein_dict.add('RemoveOldCredAge', sec_el[u'remove_old_cred_age'])
        del active_sub_list[:]  # clean

        for entry in conf.get_entries():
            if eval(entry[u'enabled'], {}, {}):
                active_sub_list.append(entry.getName())
            else:
                disabled_sub_list.append(entry.getName())

        glidein_dict.add('Entries', string.join(active_sub_list, ','))
        glidein_dict.add('AdvertiseWithTCP', conf[u'advertise_with_tcp'])
        glidein_dict.add('AdvertiseWithMultiple', conf[u'advertise_with_multiple'])
        glidein_dict.add('LoopDelay', conf[u'loop_delay'])
        glidein_dict.add('AdvertisePilotAccounting', conf[u'advertise_pilot_accounting'])
        glidein_dict.add('AdvertiseDelay', conf[u'advertise_delay'])
        glidein_dict.add('RestartAttempts', conf[u'restart_attempts'])
        glidein_dict.add('RestartInterval', conf[u'restart_interval'])
        glidein_dict.add('EntryParallelWorkers', conf[u'entry_parallel_workers'])

        glidein_dict.add('RecoverableExitcodes', conf[u'recoverable_exitcodes'])
        glidein_dict.add('LogDir', conf.get_log_dir())
        glidein_dict.add('ClientLogBaseDir', sub_el[u'base_client_log_dir'])
        glidein_dict.add('ClientProxiesBaseDir', sub_el[u'base_client_proxies_dir'])
        glidein_dict.add('DowntimesFile', down_fname)

        glidein_dict.add('MonitorDisplayText', mon_foot_el[u'display_txt'])
        glidein_dict.add('MonitorLink', mon_foot_el[u'href_link'])

        monitoring_collectors = calc_primary_monitoring_collectors(conf.get_child_list(u'monitoring_collectors'))
        if monitoring_collectors is not None:
            glidein_dict.add('PrimaryMonitoringCollectors', str(monitoring_collectors))

        log_retention = conf.get_child(u'log_retention')
        for lel in (("job_logs", 'JobLog'), ("summary_logs", 'SummaryLog'), ("condor_logs", 'CondorLog')):
            param_lname, str_lname = lel
            for tel in (("max_days", 'MaxDays'), ("min_days", 'MinDays'), ("max_mbytes", 'MaxMBs')):
                param_tname, str_tname = tel
                glidein_dict.add('%sRetention%s' % (str_lname, str_tname), log_retention.get_child(param_lname)[param_tname])

        # convert to list of dicts so that str() below gives expected results
        proc_logs = []
        for pl in log_retention.get_child_list(u'process_logs'):
            try:
                di_pl = dict(pl)
            except ValueError:
                # For compatibility with Python 2.4 (DictMixin)
                di_pl = iter_to_dict(pl)
            proc_logs.append(di_pl)
        glidein_dict.add('ProcessLogs', str(proc_logs))


#######################
def populate_job_descript(work_dir, job_descript_dict, num_factories,
                          sub_name, entry, schedd,
                          attrs_dict, enable_expansion):
    """
    Modifies the job_descript_dict to contain the factory configuration values.

    Args:
        work_dir (str): location of entry files
        job_descript_dict (dict): contains the values of the job.descript file
        num_factories:
        sub_name (str): entry name
        entry:
        schedd:
        attrs_dict (dict): dictionary of attributes
        enable_expansion (bool): whether or not expand the attribute values with a $ in them

    Returns:

    """

    down_fname = os.path.join(work_dir, 'glideinWMS.downtimes')

    config = entry.get_child(u'config')
    max_jobs = config.get_child(u'max_jobs')
    num_factories = int(max_jobs.get('num_factories', num_factories))  # prefer entry settings

    job_descript_dict.add('EntryName', sub_name)
    job_descript_dict.add('GridType', entry[u'gridtype'])
    job_descript_dict.add('Gatekeeper', entry[u'gatekeeper'])
    job_descript_dict.add('AuthMethod', entry[u'auth_method'])
    job_descript_dict.add('TrustDomain', entry[u'trust_domain'])
    if u'vm_id' in entry:
        job_descript_dict.add('EntryVMId', entry[u'vm_id'])
    if u'vm_type' in entry:
        job_descript_dict.add('EntryVMType', entry[u'vm_type'])
    if u'rsl' in entry:
        job_descript_dict.add('GlobusRSL', entry[u'rsl'])
    if u'bosco_dir' in entry:
        job_descript_dict.add('BoscoDir', entry[u'bosco_dir'])
    job_descript_dict.add('Schedd', schedd)
    job_descript_dict.add('StartupDir', entry[u'work_dir'])
    if u'proxy_url' in entry:
        job_descript_dict.add('ProxyURL', entry[u'proxy_url'])
    job_descript_dict.add('Verbosity', entry[u'verbosity'])
    job_descript_dict.add('DowntimesFile', down_fname)
    per_entry = max_jobs.get_child(u'per_entry')
    job_descript_dict.add('PerEntryMaxGlideins', int(per_entry[u'glideins'])//num_factories)
    job_descript_dict.add('PerEntryMaxIdle', int(per_entry[u'idle'])//num_factories)
    job_descript_dict.add('PerEntryMaxHeld', int(per_entry[u'held'])//num_factories)
    def_per_fe = max_jobs.get_child(u'default_per_frontend')
    job_descript_dict.add('DefaultPerFrontendMaxGlideins', int(def_per_fe[u'glideins'])//num_factories)
    job_descript_dict.add('DefaultPerFrontendMaxIdle', int(def_per_fe[u'idle'])//num_factories)
    job_descript_dict.add('DefaultPerFrontendMaxHeld', int(def_per_fe[u'held'])//num_factories)
    submit = config.get_child(u'submit')
    job_descript_dict.add('MaxSubmitRate', submit[u'max_per_cycle'])
    job_descript_dict.add('SubmitCluster', submit[u'cluster_size'])
    job_descript_dict.add('SubmitSlotsLayout', submit[u'slots_layout'])
    job_descript_dict.add('SubmitSleep', submit[u'sleep'])
    remove = config.get_child(u'remove')
    job_descript_dict.add('MaxRemoveRate', remove[u'max_per_cycle'])
    job_descript_dict.add('RemoveSleep', remove[u'sleep'])
    release = config.get_child(u'release')
    job_descript_dict.add('MaxReleaseRate', release[u'max_per_cycle'])
    job_descript_dict.add('ReleaseSleep', release[u'sleep'])
    restrictions = config.get_child(u'restrictions')
    job_descript_dict.add('RequireVomsProxy', restrictions[u'require_voms_proxy'])

    # Job submit file pick algorithm. Only present for metasites, will be Default otherwise
    if 'entry_selection' in config.children:
        entry_selection = config.children.get('entry_selection')
        job_descript_dict.add("EntrySelectionAlgorithm", entry_selection.get("algorithm_name", "Default"))  # Keeping "Default" although not necessary

    # Add the frontend specific job limits to the job.descript file
    max_held_frontend = ""
    max_idle_frontend = ""
    max_glideins_frontend = ""
    for per_fe in entry.get_child(u'config').get_child(u'max_jobs').get_child_list(u'per_frontends'):
        frontend_name = per_fe[u'name']
        max_held_frontend += frontend_name + ";" + str(int(per_fe[u'held'])//num_factories) + ","
        max_idle_frontend += frontend_name + ";" + str(int(per_fe[u'idle'])//num_factories) + ","
        max_glideins_frontend += frontend_name + ";" + str(int(per_fe[u'glideins'])//num_factories) + ","
    job_descript_dict.add("PerFrontendMaxGlideins", max_glideins_frontend[:-1])
    job_descript_dict.add("PerFrontendMaxHeld", max_held_frontend[:-1])
    job_descript_dict.add("PerFrontendMaxIdle", max_idle_frontend[:-1])

    #  If the configuration has a non-empty frontend_allowlist
    #  then create a white list and add all the frontends:security_classes
    #  to it.
    white_mode = "Off"
    allowed_vos = ""
    allowed_fes = entry.get_child_list(u'allow_frontends')
    if len(allowed_fes) > 0:
        white_mode = "On"
    for allowed_fe in allowed_fes:
        allowed_vos = allowed_vos + allowed_fe[u'name'] + ":" + allowed_fe[u'security_class'] + ","
    job_descript_dict.add("WhitelistMode", white_mode)
    job_descript_dict.add("AllowedVOs", allowed_vos[:-1])

    if enable_expansion:
        # finally, expand as needed
        for attr_name in job_descript_dict.keys:
            job_descript_dict.add(attr_name,
                                  cWExpand.expand_DLR(job_descript_dict[attr_name], attrs_dict),
                                  allow_overwrite=True)

#        # Submit attributes are a bit special, since they need to be serialized, so we will deal with them explicitly
#        submit_attrs = {}
#        for attr in submit.get_child_list(u'submit_attrs'):
#            expkey = cWExpand.expand_DLR(attr[u'name'], attrs_dict)
##            expel = cWExpand.expand_DLR(attr.get_val(), attrs_dict)  # attr[u'value'] instead?
#            expel = cWExpand.expand_DLR(attr[u'value'], attrs_dict)  # attr[u'value'] instead?
#            submit_attrs[expkey] = expel
#
#        job_descript_dict.add('SubmitAttrs', repr(submit_attrs))


###################################
# Create the frontend descript file
def populate_frontend_descript(frontend_dict,     # will be modified
                               conf):
    for fe_el in conf.get_child(u'security').get_child_list(u'frontends'):
        fe_name = fe_el[u'name']

        ident = fe_el['identity']
        maps = {}
        for sc_el in fe_el.get_child_list(u'security_classes'):
            sc_name = sc_el[u'name']
            username = sc_el['username']
            maps[sc_name] = username

        frontend_dict.add(fe_name, {'ident': ident, 'usermap': maps})


#####################################################
# Populate gridmap to be used by the glideins
def populate_gridmap(conf, gridmap_dict):
    collector_dns = []
    for el in conf.get_child_list(u'monitoring_collectors'):
        dn = el[u'DN']
        if not (dn in collector_dns):  # skip duplicates
            collector_dns.append(dn)
            gridmap_dict.add(dn, 'fcollector%i' % len(collector_dns))

    # TODO: We should also have a Factory DN, for ease of debugging
    #       None available now, but we should add it


#####################
# Simply copy a file
def copy_file(infile, outfile):
    try:
        shutil.copy2(infile, outfile)
    except IOError as e:
        raise RuntimeError("Error copying %s in %s: %s" % (infile, outfile, e))


###############################################
# Validate CONDOR_OS CONDOR_ARCH CONDOR_VERSION

def validate_condor_tarball_attrs(conf):
    valid_tarballs = get_valid_condor_tarballs(conf.get_child_list(u'condor_tarballs'))

    common_version = None
    common_os = None
    common_arch = None

    for attr in conf.get_child_list(u'attrs'):
        if attr[u'name'] == u'CONDOR_VERSION':
            common_version = attr[u'value']
        elif attr[u'name'] == u'CONDOR_OS':
            common_os = attr[u'value']
        elif attr[u'name'] == u'CONDOR_ARCH':
            common_arch = attr[u'value']
        if common_version is not None and common_os is not None and common_arch is not None:
            break

    if common_version is None:
        common_version = "default"
    if common_os is None:
        common_os = "default"
    if common_arch is None:
        common_arch = "default"

    # Check the configuration for every entry and entry set
    for entry in conf.get_entries():
        my_version = None
        my_os = None
        my_arch = None
        match_found = False

        for attr in entry.get_child_list(u'attrs'):
            if attr[u'name'] == u'CONDOR_VERSION':
                my_version = attr[u'value']
            elif attr[u'name'] == u'CONDOR_OS':
                my_os = attr[u'value']
            elif attr[u'name'] == u'CONDOR_ARCH':
                my_arch = attr[u'value']
            if my_version is not None and my_os is not None and my_arch is not None:
                break

        if my_version is None:
            my_version = common_version
        if my_os is None:
            my_os = common_os
        if my_arch is None:
            my_arch = common_arch

        # If either os or arch is auto, handle is carefully
        if ((my_os == "auto") and (my_arch == "auto")):
            for tar in valid_tarballs:
                if (tar['version'] == my_version):
                    match_found = True
                    break
        elif (my_os == "auto"):
            for tar in valid_tarballs:
                if ((tar['version'] == my_version) and (tar['arch'] == my_arch)):
                    match_found = True
                    break
        elif (my_arch == "auto"):
            for tar in valid_tarballs:
                if ((tar['version'] == my_version) and (tar['os'] == my_os)):
                    match_found = True
                    break
        else:
            tarball = { 'version': my_version,
                        'os'     : my_os,
                        'arch'   : my_arch
                      }
            if tarball in valid_tarballs:
                match_found = True

        if match_found == False:
            raise RuntimeError("Condor (version=%s, os=%s, arch=%s) for entry %s could not be resolved from <glidein><condor_tarballs>...</condor_tarballs></glidein> configuration." % (my_version, my_os, my_arch, entry[u'name']))


####################################################
# Extract valid CONDOR_OS CONDOR_ARCH CONDOR_VERSION

def old_get_valid_condor_tarballs(params):
    valid_tarballs = []

    for t in params.condor_tarballs:
        tarball = { 'version': t['version'],
                    'os'     : t['os'],
                    'arch'   : t['arch']
                  }
        valid_tarballs.append(tarball)
    return valid_tarballs


def get_valid_condor_tarballs(condor_tarballs):
    valid_tarballs = []
    tarball_matrix = []

    for tar in condor_tarballs:
        # Each condor_tarball entry is a comma-separated list of possible
        # version, os, arch this tarball can be used
        version = tar['version'].split(',')
        os = tar['os'].split(',')
        arch = tar['arch'].split(',')

        # Generate the combinations (version x os x arch)
        matrix = list(itertools_product(version, os, arch))

        for tup in matrix:
            tarball = { 'version': tup[0].strip(),
                        'os'     : tup[1].strip(),
                        'arch'   : tup[2].strip()
                      }
            valid_tarballs.append(tarball)
    return valid_tarballs


def itertools_product(*args, **kwds):
    """
    itertools.product() from Python 2.6
    """

    pools = map(tuple, args) * kwds.get('repeat', 1)
    result = [[]]
    for pool in pools:
        result = [x+[y] for x in result for y in pool]
    for prod in result:
        yield tuple(prod)


#####################################################
# Returns a string usable for GLIDEIN_Factory_Collector
# Returns None if there are no collectors defined
def calc_monitoring_collectors_string(collectors):
    collector_nodes = {}
    monitoring_collectors = []

    for el in collectors:
        if el[u'group'] not in collector_nodes:
            collector_nodes[el[u'group']] = {'primary': [], 'secondary': []}
        if eval(el[u'secondary']):
            cWDictFile.validate_node(el[u'node'])
            collector_nodes[el[u'group']]['secondary'].append(el[u'node'])
        else:
            cWDictFile.validate_node(el[u'node'])
            collector_nodes[el[u'group']]['primary'].append(el[u'node'])

    for group in collector_nodes.keys():
        if len(collector_nodes[group]['secondary']) > 0:
            monitoring_collectors.append(string.join(collector_nodes[group]['secondary'], ","))
        else:
            monitoring_collectors.append(string.join(collector_nodes[group]['primary'], ","))

    if len(monitoring_collectors) == 0:
        return None
    else:
        return string.join(monitoring_collectors, ";")


# Returns a string listing the primary monitoring collectors
# Returns None if there are no collectors defined
def calc_primary_monitoring_collectors(collectors):
    collector_nodes = {}

    for el in collectors:
        if not eval(el[u'secondary']):
            # only consider the primary collectors
            cWDictFile.validate_node(el[u'node'])
            # we only expect one per group
            if el[u'group'] in collector_nodes:
                raise RuntimeError("Duplicate primary monitoring collector found for group %s" % el[u'group'])
            collector_nodes[el[u'group']] = el[u'node']

    if len(collector_nodes) == 0:
        return None
    else:
        return string.join(collector_nodes.values(), ",")

