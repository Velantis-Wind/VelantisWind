# Bundled safe XML parser

Subset of **defusedxml 0.7.1**, source: https://github.com/tiran/defusedxml/tree/v0.7.1

Copyright (c) 2013 Christian Heimes. Licensed under the Python Software
Foundation License Version 2, reproduced in LICENSE.

To keep VelantisWind self-contained without modifying QGIS's shared Python
environment, only the ElementTree parser and its common helpers are bundled.
The unused global monkey-patching helper was omitted from the subset.
The vendored ElementTree parser accepts harmless DOCTYPE / DTD declarations
seen in some OpenWind and WAsP turbine files. The WTG and OWTG importers
explicitly forbid entity declarations and external reference resolution.
Accepting a DTD does not imply expanding entities or fetching external resources.

Changes relative to upstream 0.7.1: minimal __init__ without global monkey
patching, omitted unused _apply_defusing helper, annotated Bandit exclusions on
stdlib imports and secured parser handoff. This package is under the
VelantisWind._vendor namespace so it cannot conflict with other QGIS plugins.
