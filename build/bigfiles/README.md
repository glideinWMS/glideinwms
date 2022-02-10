<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

Big files utilities
===================

`bigfiles.sh` helps managing big files hosted on an external web server.
Files are handled as symbolic links for the Git repository.
Links can be replaced with the actual file and back when editing or
other operations requiring the full files are needed.

Before an operation that may need the file (editing it, run unit tests, make a release),
the big files should be retrieved. There are 2 options: download them to populate the dangling link
(`bigfiles.sh -p`, sufficient for unit test and other operations that follow links)
or download them and replace the links with the actual files
(`bigfiles.sh -pr`, when symlinks are insuffucient).
Before any operation involving Git, e.g. commits or merges, the links should be put back
in place (`bigfiles.sh -R`).

To ease the management of big files, it is recommended to use the
wrapper for git: `bigfiles-git`. Just add it to the PATH with
something like `export PATH="$PWD:$PATH"`
and use it all the times instead of the `git`
command, so the bigfiles will be handled for you.
You can also create an alias (`alias git=bigfiles-git`).
This command intercepts the `bigfiles push`, `pull` and `stop`
commands or runs the git commands
(everything else) by wrapping
them around bigfiles commands to put back the links and
replace them with files respectively before and after
each git command. Simply use `bigfile-git` instead of each git
command and `bigfile-git bigfiles stop` command to stop
using the wrapper and go back to use directly git commands.

GlideinWMS CI has been modified to invoke bigfiles.sh automatically:
the bigfiles directory will be left populated after running any CI test.
The ReleaseManager script `osg-release.sh` has beem modified as well to
build an archive, the tar ball for the RPM, including the big files
(requested tag + bigfiles). If you do that manually, e.g. using
`release.py`, you'll have to use `bigfiles -pr`
before tar-ing the files.

There are some git hooks and utilities to manage them. This could automate
the management of big files and make it completely transparent for the developers,
but they are incomplete. Git does not support a `pre-ceckout` hook and that would be
needed to handle correctly some use cases
(e.g. a checkout followed by another checkout).
