<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

# GlideinWMS

[GlideinWMS](https://glideinwms.fnal.gov/doc.prd/index.html
) development

# Code Documentation

https://glideinwms.fnal.gov/api/

# Developer Workflow

https://cdcvs.fnal.gov/redmine/projects/glideinwms/wiki

# Getting Started with development

NOTE: This project has a pre-commit config.
To install it run `pre-commit install` from the repository root.
You may want to setup automatic notifications for pre-commit enabled
repos: https://pre-commit.com/index.html#automatically-enabling-pre-commit-on-repositories

GlideinWMS code must work w/ Python 3.6+.

You can run manually the CI tests using the scripts in the `build/ci` folder.
Run `./glideinwms/build/ci/runtest.sh -h` for instructions and to list the available tests.
```shell
./glideinwms/build/ci/runtest.sh -i pylint -a
./glideinwms/build/ci/runtest.sh -i pyunittests -a
```

Document your code so we can easily generate API documentation using Sphinx.
Write docstrings in the Google format which is more readable, reasonably compact
and still can be included in the API documentation ([here](https://www.sphinx-doc.org/en/master/usage/extensions/example_google.html#example-google) is an example).


## Licensing compliance

Decison engine is released under the Apache 2.0 license and license compliance is
handled with the [REUSE](http://reuse.software/) tool.
REUSE is installed as development dependency or you can install it manually
(`pip install reuse`). All files should have a license notice:

- to check compliance you can use `reuse lint`. This is the command run also by the pre-commit and CI checks
- you can add on top of new files [SPDX license notices](https://spdx.org/licenses/) like
  ```
  # SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
  # SPDX-License-Identifier: Apache-2.0
  ```
- or let REUSE do that for you (`FILEPATH` is your new file):
  ```
  reuse addheader --year 2009 --copyright="Fermi Research Alliance, LLC" \
    --license="Apache-2.0" --template=compact FILEPATH
  ```
- Files that are not supported and have no comments to add the SPDX notice
  can be added to the `.reuse/dep5` file
- New licenses can be added to the project using `reuse download LCENSEID`. Please
  contact project management if this is needed.


# Building the package

The code is expected to package as an RPM via the `./build/ReleaseManager/release.py` script.
The code is normally built and distributed via the OSG Koji server.


## Using the RPM

Installation instruction for the Frontend and the Factory are
in the [install document](https://glideinwms.fnal.gov/doc.prd/install.html)
and in the linked OSG documents.
