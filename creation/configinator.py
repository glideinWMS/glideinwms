#!/usr/bin/python
'''
Script to grab a glideinWMS.xml from a git repository and
merge it into an existing configuration using clone_glidein
'''

import getopt
import os
import shutil
import subprocess
import sys
import tempfile

STARTUP_DIR = os.path.abspath(sys.path[0])
sys.path.append(os.path.join(STARTUP_DIR, "../.."))

import glideinwms.creation.clone_glidein

USAGE = "Usage: configinator.py [options]\n" \
        "Options: \n" \
        "  -x [file path to glideinWMS.xml, required]\n" \
        "  -o [output file (default: out.xml)]\n" \
        "  -r [Git remote repository, required]\n" \
        "  -c [Git remote branch (default: master)]\n" \
        "  -h, --help  show this help\n"

def run_cmd(cmd):
    ''' Run a simple command and raise RuntimeError for
    non-zero return codes. '''

    proc = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = proc.communicate()
    if proc.wait():
        raise RuntimeError("failed: %s\n%s\n%s" % (cmd, out, err))

def get_from_gitrepo(gitdir, git_repo, git_branch):
    ''' Do a fresh clone and checkout from a git repository '''
    cwd = os.getcwd()
    os.chdir(gitdir)
    run_cmd('git clone %s .' % git_repo)
    run_cmd('git checkout %s' % git_branch)
    os.chdir(cwd)

def main(argv):
    ''' Main body '''

    config_xml = ''
    git_repo = ''
    git_branch = 'master'
    out = 'out.xml'

    try:
        opts, _ = getopt.getopt(argv, "hc:x:r:o:", ["help"])
    except getopt.GetoptError:
        print "Unrecognized or incomplete input arguments."
        print USAGE
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print USAGE
            sys.exit()
        elif opt == '-x':
            config_xml = arg
        elif opt == '-r':
            git_repo = arg
        elif opt == '-c':
            git_branch = arg
        elif opt == '-o':
            out = arg
        else:
            print "Unrecognized input arguments."
            print USAGE
            sys.exit(2)

    # Validate arg exists
    if config_xml == '':
        print "No configuration file was provided. "
        print USAGE
        sys.exit(2)
    else:
        if not os.path.isfile(config_xml):
            print "Config file '%s' does not exist." % config_xml
            sys.exit(2)

    if git_repo == '':
        print "No remote git repository was provided. "
        print USAGE
        sys.exit(2)

    gitdir = tempfile.mkdtemp()
    try:
        get_from_gitrepo(gitdir, git_repo, git_branch)
        args = "clone_glidein -out %s -other %s/entries.xml %s" % \
               (out, gitdir, config_xml)
        args = args.split()
        glideinwms.creation.clone_glidein.load(args)
    except Exception, ex:
        shutil.rmtree(gitdir)
        raise ex

    shutil.rmtree(gitdir)

if __name__ == "__main__":
    main(sys.argv[1:])

