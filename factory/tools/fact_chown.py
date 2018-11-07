from __future__ import print_function

import os
import sys
import grp
import pwd
import logging
import tarfile
import argparse
import subprocess
from contextlib import closing  # python 2.6 tarfile does not support with

import htcondor
from glideinwms.creation.lib import factoryXmlConfig

def parse_opts():
    """ Parse the command line options for this command
    """
    description = 'Change the ownership of frontend directories to the specified user\n\n'

    parser = argparse.ArgumentParser(
        description=description)

    parser.add_argument(
        '--user', type=str, action='store', dest='user',
        help='User to use when chowning the files')

    parser.add_argument(
        '--group', type=str, action='store', dest='group',
        help='Group to use when cowning the files')

    parser.add_argument(
        '--backup', action='store_true', dest='backup',
        default=False,
        help='Back up the directories into the cwd before chwon everything')

    parser.add_argument(
        '--debug', action='store_true', dest='debug',
        default=False,
        help='Enable debug logging')

    parser.add_argument(
        '--test', action='store_true', dest='test',
        default=False,
        help='Run the script but do not change permissions')

    options = parser.parse_args()

    if options.user is None:
        logging.error('Missing required option "--user"')
        sys.exit(1)

    if options.group is None:
        logging.error('Missing required option "--group"')
        sys.exit(1)

    # Initialize logging
    if options.debug:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    return options


def backup_dir(output_filename, source_dir):
    """ Backup the directory "source_dir" into "output_filename"
    """
    with closing(tarfile.open(output_filename, "w:gz")) as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


def mychown(path, uid, gid, fuid, test):
    """ Change the owner id of "path" to "uid":"gid". Before doing that
        check if the current owner of the file is "fuid". If not print a warning
        If "test: is set don't chown but just print a message
    """
    cid = os.stat(path).st_uid  # current id
    if cid != fuid:
        logging.warning("Not changing %s since it's owner id is not %s" % (path, fuid))
    if test:
        logging.info("Test mode: not changing %s" % path)
    else:
        os.chown(path, uid, gid)


def chown_dir(path, uid, gid, fuid, test):
    """ Recursively go through the direcotry "path" and change the permission
        of its files to "uid":"gid". Before doing that check if the current
        owner of the file is fuid.
        If "test: is set don't chown but just print a message
    """
    mychown(path, uid, gid, fuid, test)
    for dirpath, dirnames, filenames in os.walk(path):
        for dname in dirnames:
            mychown(os.path.join(dirpath, dname), uid, gid, fuid, test)
            pass
        for fname in filenames:
            mychown(os.path.join(dirpath, fname), uid, gid, fuid, test)
            pass


def fix_jobqueue(jobqueue_file, user, test):
    """ Replace the username in the condor job_queue file to user
    """

    if test:
        logging.info("Test mode: not fixing %s" % jobqueue_file)
    else:
        cmd = 'sed -i.bk -e \'s/103 \([-0-9.]*\) Owner ".*"/103 \\1 Owner "\'%s\'"/\' %s' % (user, jobqueue_file)
        subprocess.call(cmd, shell=True)


def main():
    """ The main
    """
    options = parse_opts()

    # Factory side
    conf_file = '/etc/gwms-factory/glideinWMS.xml' #TODO
    logging.info('Loading configuration file %s' % conf_file)
    conf = factoryXmlConfig.parse(conf_file)
    uid = pwd.getpwnam(options.user).pw_uid
    gid = grp.getgrnam(options.group)[2]

    dir_dicts = [ conf.get_client_log_dirs(), conf.get_client_proxy_dirs() ]

    for client_dir_dict in dir_dicts:
        for fe_user, fe_client_dir in client_dir_dict.items():
            logging.info('Working on %s: changing ownership from %s to %s' % (fe_client_dir, fe_user, options.user))
            if options.backup:
                logging.info('Backing it up in the current directory first')
                backup_dir(fe_user + '.tar.gz', fe_client_dir)
            fuid = pwd.getpwnam(fe_user).pw_uid
            chown_dir(fe_client_dir, uid, gid, fuid, options.test)

    # Condor side
    spooldir = htcondor.param['SPOOL']
    if not 'JOBQUEUE' in htcondor.param:
        jobqueue_file = os.path.join(spooldir, 'job_queue.log')
    fix_jobqueue(jobqueue_file, options.user, options.test)
    fix_jobqueue(jobqueue_file, options.user, False)
    for i in xrange(1,9):
        try:
            jobqueue_file = htcondor.param['SCHEDD.SCHEDDGLIDEINS%s.JOB_QUEUE_LOG' % i]
        except KeyError:
            logging.warning("Cannot find 'SCHEDD.SCHEDDGLIDEINS%s.JOB_QUEUE_LOG'. Skipping it." % i)
        fix_jobqueue(jobqueue_file, options.user, options.test)


if __name__ == '__main__':
    main()
