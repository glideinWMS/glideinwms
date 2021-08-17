Big files utilities
===================

`bigfiles.sh` helps managing big files hosted on an external web server.
Files are handled as symbolic links for the Git repository.
Links can be replaced with the actual file and back when editing or
other operations requiring the full files are needed.

Before operation that may need the file (editing it, run unit tests, make a release),
the big files should be retrieved. There are 2 options: download them to populate the dangling link 
(`bigfiles.sh -p`, sufficient for unit test and other operations that follow links) 
or download them and replace the links with the actual files 
(`bigfiles.sh -pr`, when symlinks are insuffucient).
Before any operation involving Git, e.g. commits or merges, the links should be put back 
in place (`bigfiles.sh -R`).

GlideinWMS CI has been modified to invoke bigfiles.sh automatically: 
the bigfiles directory will be left populated after running any CI test.
The ReleaseManager script `osg-release.sh` has beem modified as well to 
build an archive, the tar ball for the RPM, including the big files 
(requested tag + bigfiles). If you do that manually you'll have to use 
`bigfiles -pr` before tar-ing the files.

There are some git hooks and uptilities to manage them. This could automate
the management of big files and make it completely transparent for the developers,
but they are incomplete. Git does not support a `pre-ceckout` hook and that would be 
needed to handle correctly some use cases 
(e.g. a checkout followed by another checkout).

There is a wrapper for git: `bigfiles-git` that inpercepts the bigfiles push and pull commands
and runs the commands to put back the links and replace them with files
respectively before and after each git command.

