# Third-party code notices

This plugin distribution bundles or derives from the following third-party
projects. Their copyright and licenses are preserved per their terms.

## easyeda2kicad.py (AGPL-3.0)

A subset of [uPesy/easyeda2kicad.py](https://github.com/uPesy/easyeda2kicad.py)
v1.0.1 is vendored under `plugins/lcsc_manager/vendor/easyeda2kicad/`,
covering the EasyEDA footprint importer and the KiCad footprint exporter.
This code is licensed under **AGPL-3.0** and remains under AGPL-3.0 in this
distribution. The original `LICENSE` file is preserved alongside the
vendored sources.

- Source: https://github.com/uPesy/easyeda2kicad.py
- Version vendored: 1.0.1
- License: AGPL-3.0
- License text: `plugins/lcsc_manager/vendor/easyeda2kicad/LICENSE`

The footprint conversion pipeline (parsing the raw EasyEDA JSON to a
KiCad `.kicad_mod` file) is delegated to this vendored code. Other parts
of the plugin (LCSC API client, UI dialogs, symbol/3D-model converters)
remain under the plugin's MIT license.

Because AGPL-3.0 source is bundled here, *modifications you make to the
vendored code* must be made available under AGPL-3.0 if you redistribute
this plugin. The plugin as a whole can continue to be distributed because
AGPL-3.0 permits aggregation with MIT-licensed code; just keep the
vendored files' license intact.

## JLC2KiCad_lib (AGPL-3.0)

Symbol-conversion handlers under
`plugins/lcsc_manager/converters/jlc2kicad/` were originally adapted from
[TousstNicolas/JLC2KiCad_lib](https://github.com/TousstNicolas/JLC2KiCad_lib).
This is AGPL-3.0 derived code; the same redistribution terms apply.
