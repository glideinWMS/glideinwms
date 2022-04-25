<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

# Run pycodestyle in a SL7 container

This runs pycodestyle using the GlideinWMS CI scripts (runtest.sh).

## Inputs

There are no inputs. it is using the PYVER env variable (Python version)
if set. Default `"3.6"`

## Outputs

Outputs are set within the entrypoint script using "::set-output"

### `warnings`

The number of warnings returned by pycodestyle.

## Example usage

uses: ./.github/actions/pycodestyle-in-sl7-docker
id: pycodestyle
