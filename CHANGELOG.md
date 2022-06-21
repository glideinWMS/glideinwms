# Glideinwms Changelog for V3_7_7  (Python2) Series

## Changes since last release

- glideins can self-install cvmfs file system in their running containers if desired

- support for running apptainer (formerly singularity) including advertising containersw_XXXX variables

- glideins  look for and transfer CE supplied IDTOKENS from startup  directory to the glideins credential directory for later use.

- new parameter for frontend.xml  security `idtokens_lifetime` controls the lifetime of frontend generated IDTOKENS.  Default value for
  lifetime is 24 hours, as in previous releases.

- new parameter for frontend.xml groups, `CONTINUE_IF_NO_PROXY` .  If set to 'True' and the frontend group has a SCITOKEN credential
  but no grid_proxy, the frontend  group can successfully request glideins  from factory entries with auth_method='grid_proxy'

## Bug fixes

- unbalanced parens in condor submission files no longer  occur in Bosco entries.  A unit test was  created to check for correct submission file grammer for different types of factory entries.

    
