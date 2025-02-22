# Big Files in GlideinWMS

This folder and `../build/bigfiles/bigfiles.sh` are a rudimentary system for handling of big files
for the GlideinWMS project. git-LFS and git-annex offer more features but would not be as widely
supported or add more complications and this is a best fit for the project's needs.

Files in the repository will be symbolic links pointing to files in this directory tree.
Use relative paths because the root path of the repository will probably be different.
Only the last version of the files is kept, older versions may be available in backups if needed,
these files are not unde version control.
Whenever an update is needed contact GlideinWMS release managers to update the big files archive
and provide the new version.
The files should not be added to git, only the symbolic link to the relative path.

The archive is available on the Web:
https://glideinwms.fnal.gov/downloads/glideinwms-bigfiles-latest.tgz

Whenever releasing the software or doing other operations involving one or more of the referred files
you will have to download the big files archive.

Use `../build/bigfiles/bigfiles.sh -pv` or perform it manually:

```bash
wget https://glideinwms.fnal.gov/downloads/glideinwms-bigfiles-latest.tgz
tar xvzf glideinwms-bigfiles-latest.tgz
```

bigfiles.sh can help with may bigfiles operations, including updates and packaging,
`./build/bigfiles/bigfiles.sh -h` for a full description of the command:

```
bigfiles.sh [options]
  Runs the test form COMMAND on the current glideinwms subdirectory, as is or checking out a branch from the repository.
 Options:
  -h          print this message
  -v          verbose
  -d REPO_DIR GlideinWMS repository root directory (default: trying to guess, otherwise '.')
  -p          pull: download and unpack the big files to the bigfiles directory if not already there
  -P          push: compress the big files
  -s SERVER   upload to SERVER via scp the bundled big files (ignored it -P is not specified)
  -u          update (download and unpack even if files are already there). Used with -r and -p
  -r          replace the symbolic links with the linked linked to files in the bigfiles directory
              and write a list of replaced files to BF_LIST. Big files are downloaded if not in the bigfiles directory
  -R          copy the big files (from BF_LIST) to the bigfiles directory and replace the big files with the
              symbolic links to the bigfiles directory
  -b BF_LIST  big files list (default: REPO_DIR/bigfiles/bigfiles_list.txt)
 Examples:
  ./bifiles.sh -p           Use this before running unit tests or packaging the software, to pull the big files
  ./bifiles.sh -pr          Use this if you plan to edit a big file in place. Will pull and replace the symbolic links
                            w/ the actual file
  ./bifiles.sh -PR          Use this before committing if you used ./bifiles.sh -pr. Will make sure that the big file
                            is replaced with the proper link. Remember to send the archive with the new
                            big files ($TARNAME) to a GlideinWMS librarian
```

REMEMBER NOT TO ADD THE FILES IN THIS DIRECTORY TO GIT (.gitignore is already set up accordingly)!
