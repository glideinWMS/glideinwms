<!--
SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
SPDX-License-Identifier: Apache-2.0
-->

# Plugins

Plugins are used to define plugins for GlideinWMS. Plugins can be used to extend the functionality of GlideinWMS by adding new features or modifying existing ones.

Files in this directory are deployed at `/etc/gwms-frontend/plugin.d` may be loaded by the Frontend according to the configuration.

## Generators

Generators are plugings used to generate content at runtime during the Frontend workflow. GlideinWMS provides a set of built-in generators, and you can also create your own custom generators.

### Usage

GlideinWMS currently supports the usage of generators for secutiry credentials and parameters. Here are a couple of examples of how to use generators in your configuration files:

#### Credential Generator Example

```xml
<credential
    absfname="RoundRobinGenerator"
    purpose="payload"
    security_class="frontend"
    trust_domain="grid"
    type="generator"
    context="{'items': ['cred1', 'cred2', 'cred3'], 'type': 'text'}"
/>
```

#### Parameter Generator Example

```xml
<parameter
    name="VMId"
    value="RoundRobinGenerator"
    type="generator"
    context="{'items': ['vm1', 'vm2', 'vm3'], 'type': 'string'}"
/>
```

Note that credential and parameter generators are specified in the same way as their static counterparts, but there are a few key differences:

- Credential `absfname` and parameter `value` attributes are used to specify the generator plugin to be used. GlideinWMS will look for a generator class, or a plugin module name within its `PYTHON_PATH` to load and execute. Typically, generators are stored in `/etc/gwms-frontend/plugin.d` which is included in the `PYTHON_PATH` by default. Alternatively, you can specify the full path to the plugin file in the `absfname` or `value` attributes.
- The `context` attribute is used to pass a dictionary of parameters to the generator plugin. The content of this dictionary will depend on the specific generator being used. The `type` key is used to specify the type of credential or parameter being generated.
- The `type` attribute is set to `generator` to indicate that the credential or parameter is generated at runtime.

### Custom Generators

You can define your own generators using the GlideinWMS Generators framework. Here is a simple example of a custom generator plugin that returns a random string from a list of items:

```python
import random
from typing import Any

from glideinwms.lib.generators import export_generator, Generator, GeneratorError


class RandomGenerator(Generator[Any]):
    """Random generator"""

    def generate(self, **kwargs) -> Any:
        items = self.context.get("items", [])
        if not items:
            raise GeneratorError("No items provided for generation")
        return random.choice(items)

export_generator(RandomGenerator)
```

Key points to note:

- The custom generator class should inherit from `glideinwms.lib.generators.Generator`. This is an abstract base class that requires the implementation of a `generate` method, which should return the generated value.
- `self.context` is a dictionary that contains the context passed from the configuration file. This attribute is loaded at the base class constructor.
- `kwargs` is used to retrieve runtime parameters provided by the Frontend. The arguments currently supported are `elementDescript`, `glidein_el`, `group_name`, `trust_domain`, `entry`, and `logger`.
- The `export_generator` function is used to register the custom generator with the GlideinWMS Generators framework. You can define as many classes as you need in a single plugin file, but only one of them should be exported.
- The module name is determined by the filename of the plugin. For example, if the plugin is saved as `RandomGenerator.py`, the module name will be `RandomGenerator`. The exported class name does not affect the module name. To use this module in you configuration file, you could specify `RandomGenerator`, `RandomGenerator.py`, or `/path/to/generator/RandomGenerator.py` in the `absfname` or `value` attributes.

### Legacy Generators

The new GlideinWMS Generators framework supports legacy generators that use the callout interface. The built-in `LegacyGenerator` works as an adapter that allows you to use existing callout-based generators with the new framework. Here is an example of how to use a legacy generator in your configuration file:

```xml
<credential
    absfname="LegacyGenerator"
    purpose="payload"
    security_class="frontend"
    trust_domain="grid"
    type="generator"
    context="{'callout': 'example_callout.py', 'type': 'scitoken', 'kwargs': {'param1': 'value1', 'param2': 'value2'}}"
/>
```

Key points to note:

- The `callout` key in the `context` dictionary specifies the path to the legacy callout script. As in `absfname` and `value` attributes, you can specify the full path to the script if it is not in `PYTHON_PATH`.
- If your legacy generator requires additional parameters, you can include them by adding a `kwargs` key to the `context` dictionary.
