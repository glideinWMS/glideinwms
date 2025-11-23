<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

GlideinWMS Frontend run-time directory

This is also $HOME for the frontend user.
These files are needed for the Frontend execution and several are modified dynamically:

-   web-area Web accessible area containing the stage, monitor and cred sub-directory. The first must be accessed via http for better caching, for the others https is preferred
-   web-base contains copies of most scripts
-   work-dir contains the status of a running Frontend
-   cred.d contains generated credentials like
    -   keys.d managed keys to sign scitokens
    -   passwords.d managed HTCondor password to sign idtokens
    -   tokens.d generated scitokens and idtokens
