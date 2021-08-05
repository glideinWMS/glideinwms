This is a rudimentary handling of big files

Files in the repository will be symbolic links pointing to files in this directory tree.
Use relative paths because the root path of the repository will probably be different.
Only the last version of the files is kept, older versions may be available in backups if needed, these files are not unde version control.
Whenever an update is needed contact GlideinWMS release managers to update the big files archive and provide the new version.
The files should not be added to git, only the symbolic link to the relative path.

The archive is available on the Web:
https://glideinwms.fnal.gov/downloads/glideinwms-bigfiles-latest.tgz

Whenever releasing the software or doing other operations involving one or more of the referred files
you will have to download the big files archive.

Use ../build/bigfiles/bigfiles.sh -pv or perform it manually:
wget https://glideinwms.fnal.gov/downloads/glideinwms-bigfiles-latest.tgz
tar xvzf glideinwms-bigfiles-latest.tgz

bigfiles.sh can help with may bigfiles operations, including updates and packaging,
./build/bigfiles/bigfiles.sh -h for a full list

REMEBER NOT TO ADD THE FILES IN THIS DIRECTORY TO GIT!
