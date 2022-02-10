<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

Useful ansible playbooks and other scripts go here.

migrate_factory.yml - upgrades or downgrades a gwms-factory
usage:

ansible-playbook migrate_factory.yml -l factory_hostname [-e dir=upgrade|downgrade] [-e repo=osgrepo]
default for dir is upgrade
default for repo is osg


migrate_frontend.yml - upgrades or downgrades a gwms-frontend
usage:
ansible-playbook migrate_frontend.yml -l frontend_hostname [-e dir=upgrade|downgrade] [-e repo=osgrepo]
default for dir is upgrade
default for repo is osg

factory_hostname and frontend_hostname must be listed in an 'inventory' file

example usage:

[dbox@fermicloud073 ansible]$ cat inventory
fermicloud349.fnal.gov
fermicloud063.fnal.gov

[dbox@fermicloud073 ansible]$ ssh fermicloud349.fnal.gov yum list glideinwms-vofrontend
Loaded plugins: langpacks, priorities
164 packages excluded due to repository priority protections
Installed Packages
glideinwms-vofrontend.noarch               3.6.2-1.osg35.el7                @osg
Available Packages
glideinwms-vofrontend.noarch               3.6.5-1.osg35.el7                osg

[dbox@fermicloud073 ansible]$ ansible-playbook migrate_frontend.yml -l fermicloud349.fnal.gov -e repo=osg-upcoming-development

PLAY [gwms vofrontend migration playbook] ************************************************************************************

TASK [Gathering Facts] *******************************************************************************************************
ok: [fermicloud349.fnal.gov]

TASK [stop condor] ***********************************************************************************************************
changed: [fermicloud349.fnal.gov]

TASK [stop frontend] *********************************************************************************************************
changed: [fermicloud349.fnal.gov]

TASK [archive condor logs] ***************************************************************************************************
changed: [fermicloud349.fnal.gov]

TASK [archive frontend logs] **************************************************************************************************
changed: [fermicloud349.fnal.gov]

TASK [yum upgrade glideinwms-vofrontend] **************************************************************************************
changed: [fermicloud349.fnal.gov]

TASK [start condor] ***********************************************************************************************************
changed: [fermicloud349.fnal.gov]

TASK [gwms-frontend upgrade] ***************************************************************************************************
changed: [fermicloud349.fnal.gov]

TASK [start gwms-frontend] *****************************************************************************************************
changed: [fermicloud349.fnal.gov]

TASK [bounce condor] ***********************************************************************************************************
changed: [fermicloud349.fnal.gov]

TASK [bounce gwms-frontend] *****************************************************************************************************
changed: [fermicloud349.fnal.gov]

PLAY RECAP *********************************************************************************************************************
fermicloud349.fnal.gov     : ok=11   changed=10   unreachable=0    failed=0    skipped=0    rescued=0    ignored=0


[dbox@fermicloud073 ansible]$ ssh fermicloud349.fnal.gov yum list glideinwms-vofrontend
Loaded plugins: langpacks, priorities
164 packages excluded due to repository priority protections
Installed Packages
glideinwms-vofrontend.noarch  3.7.1-0.9.rc9.osgup.el7  @osg-upcoming-development
[dbox@fermicloud073 ansible]$
