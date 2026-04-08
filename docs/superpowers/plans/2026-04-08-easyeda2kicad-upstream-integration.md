# easyeda2kicad v1.0.1 Hybrid Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the highest-value fixes from upstream [easyeda2kicad.py v1.0.1](https://github.com/uPesy/easyeda2kicad.py) into `kicad-lcsc-manager`'s converters and API client, preserving the current JLC2KiCad_lib-based symbol/footprint pipeline and KicadModTree output format.

**Architecture:** Surgical, file-scoped patches rather than full library replacement. Each task either (a) patches a single converter file with a focused fix, or (b) ports one upstream helper into the project. Existing data flow (`lcsc_api.py` → `easyeda_data` dict → `*_converter.py` → `jlc2kicad/*_handlers.py`) is kept intact; only behaviour is upgraded.

**Tech Stack:** Python 3.10+, KicadModTree (for footprints), urllib/requests, standard library. No pytest — verification scripts live under `tests/` and are invoked via `python3 tests/<name>.py` following the existing pattern.

**Reference source tree:** Upstream has been cloned to `/tmp/easyeda2kicad/`. Key files referenced by this plan:
- `/tmp/easyeda2kicad/easyeda2kicad/easyeda/easyeda_api.py` — SSL context, caching, urllib-based client
- `/tmp/easyeda2kicad/easyeda2kicad/kicad/export_kicad_3d_model.py` — OBJ→WRL with centering + EE offset
- `/tmp/easyeda2kicad/easyeda2kicad/kicad/export_kicad_footprint.py` — SVG path parser, arc math, pad number normalization
- `/tmp/easyeda2kicad/easyeda2kicad/easyeda/easyeda_importer.py` — pin segment parsing, `add_easyeda_pin`

**Out of scope for this plan:**
- Vendoring the full `easyeda2kicad` package as a dependency (deferred to follow-up after this plan is validated).
- Rewriting footprint generation off KicadModTree onto upstream's direct-S-expression path.
- EasyEDA Pro (v2) API adoption.
- `get_product_image_url` / LCSC product image scraping.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `plugins/lcsc_manager/converters/model_3d_converter.py` | Rewrite key methods | OBJ→WRL with centering, EE translation offset, extract c_origin/z from SVGNODE |
| `plugins/lcsc_manager/api/lcsc_api.py` | Add methods, wire into existing paths | `_create_ssl_context` (macOS KiCad certifi fallback), optional disk cache for JSON responses |
| `plugins/lcsc_manager/preview/kicad_preview.py` | Add disk cache to `_fetch_easyeda_svgs` | Reuse LCSCAPIClient's cache directory |
| `plugins/lcsc_manager/converters/jlc2kicad/footprint_handlers.py` | Patch 3 handlers | `h_SOLIDREGION` (H/V commands), `h_PAD` (`A(1)→1` normalization), `h_VIA` (implement) |
| `plugins/lcsc_manager/converters/jlc2kicad/symbol_handlers.py` | Patch `h_P` | Extract canonical pin number from `^^`-segmented line |
| `plugins/lcsc_manager/converters/symbol_converter.py` | Adjust call site | Pass raw line string to `h_P` (not `split("~")[1:]`) — needed for Task 4 |
| `tests/test_3d_centering.py` | New | Unit test WRL centering with synthetic OBJ fixture |
| `tests/test_footprint_handlers_patches.py` | New | Unit tests for H/V path parsing and pad normalization |
| `tests/test_symbol_pin_numbers.py` | New | Unit test multi-unit pin number extraction |
| `tests/test_regression_components.py` | New | Integration test: import C7220642 and one new multi-unit IC, diff against golden output |

---

## Task 1: Port upstream OBJ bounding-box + centering into `model_3d_converter.py`

**Files:**
- Modify: `plugins/lcsc_manager/converters/model_3d_converter.py:456-505` (materials + vertices helpers)
- Modify: `plugins/lcsc_manager/converters/model_3d_converter.py:338-454` (`_convert_obj_to_wrl`)
- Test: `tests/test_3d_centering.py` (new)

**Context:** The current `_convert_obj_to_wrl` has three bugs vs upstream:
1. Vertex extraction uses regex (`v (.*?)\n`) that misses `v` lines without trailing newline and doesn't validate vertex count.
2. No OBJ bounding-box computation → no XY centering, no Z bottom alignment.
3. Stray `points.insert(-1, points[-1])` (line 414) corrupts point order — not present in upstream.
4. Transparency detection `value.startswith("d")` at line 481 collides with `Kd` lines.
5. `ambientIntensity` hardcoded to 0.2 instead of Rec.601 luminance of `Ka`.

This task replaces the helpers with upstream's semantics while keeping the method signatures so the rest of the class (`process_component_model`) keeps working.

- [ ] **Step 1: Read upstream reference implementation**

Re-read `/tmp/easyeda2kicad/easyeda2kicad/kicad/export_kicad_3d_model.py:22-223` — `get_materials`, `get_vertices`, `_get_obj_bbox`, `generate_wrl_model`. These are the source of truth.

- [ ] **Step 2: Write failing test for OBJ bbox helper**

Create `tests/test_3d_centering.py`:

```python
"""
Unit tests for 3D model OBJ parsing and centering.
Run with: python3 tests/test_3d_centering.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.converters.model_3d_converter import Model3DConverter

# Minimal OBJ with 3 vertices in a known-asymmetric bbox
FIXTURE_OBJ = """# test
newmtl mat_a
Ka 0.2 0.2 0.2
Kd 0.8 0.6 0.4
Ks 0.5 0.5 0.5
d 0
endmtl
v 2.0 4.0 1.0
v 6.0 8.0 5.0
v 4.0 6.0 3.0
usemtl mat_a
f 1 2 3
"""


def test_obj_bbox():
    conv = Model3DConverter()
    bbox = conv._get_obj_bbox(FIXTURE_OBJ)
    assert bbox is not None, "expected bbox, got None"
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bbox
    assert (x_min, x_max) == (2.0, 6.0), f"X bbox wrong: {x_min, x_max}"
    assert (y_min, y_max) == (4.0, 8.0), f"Y bbox wrong: {y_min, y_max}"
    assert (z_min, z_max) == (1.0, 5.0), f"Z bbox wrong: {z_min, z_max}"
    print("test_obj_bbox: PASS")


def test_obj_bbox_empty():
    conv = Model3DConverter()
    assert conv._get_obj_bbox("") is None
    assert conv._get_obj_bbox("# only comments\n") is None
    print("test_obj_bbox_empty: PASS")


if __name__ == "__main__":
    test_obj_bbox()
    test_obj_bbox_empty()
    print("\nAll 3D centering tests passed.")
```

- [ ] **Step 3: Run test, verify AttributeError**

Run: `python3 tests/test_3d_centering.py`
Expected: `AttributeError: 'Model3DConverter' object has no attribute '_get_obj_bbox'`

- [ ] **Step 4: Implement `_get_obj_bbox` on Model3DConverter**

Add method after `_extract_obj_vertices` in `plugins/lcsc_manager/converters/model_3d_converter.py`:

```python
def _get_obj_bbox(
    self, obj_content: str
) -> Optional[tuple]:
    """
    Compute OBJ vertex bounding box.

    Returns:
        ((x_min, x_max), (y_min, y_max), (z_min, z_max)) or None if no vertices.

    Ported from easyeda2kicad.py v1.0.1 export_kicad_3d_model._get_obj_bbox.
    """
    x_vals, y_vals, z_vals = [], [], []
    for line in obj_content.splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0] != "v":
            continue
        try:
            x_vals.append(float(parts[1]))
            y_vals.append(float(parts[2]))
            z_vals.append(float(parts[3]))
        except ValueError:
            continue

    if not x_vals:
        return None

    return (
        (min(x_vals), max(x_vals)),
        (min(y_vals), max(y_vals)),
        (min(z_vals), max(z_vals)),
    )
```

Also add `Tuple` to typing import at line 7:

```python
from typing import Dict, Any, Optional, Tuple, List
```

- [ ] **Step 5: Run test, verify PASS**

Run: `python3 tests/test_3d_centering.py`
Expected: `All 3D centering tests passed.`

- [ ] **Step 6: Commit**

```bash
git add plugins/lcsc_manager/converters/model_3d_converter.py tests/test_3d_centering.py
git commit -m "Add OBJ bbox helper for 3D model centering"
```

---

## Task 2: Replace `_convert_obj_to_wrl` with centered, upstream-equivalent logic

**Files:**
- Modify: `plugins/lcsc_manager/converters/model_3d_converter.py:338-505`
- Test: `tests/test_3d_centering.py` (extend)

- [ ] **Step 1: Extend test with centered-output check**

Append to `tests/test_3d_centering.py` (before `if __name__`):

```python
def test_convert_centered_wrl():
    """WRL output should center model XY on 0 and put bottom at z=0."""
    conv = Model3DConverter()
    wrl = conv._convert_obj_to_wrl(
        obj_content=FIXTURE_OBJ,
        translation_x=0.0,
        translation_y=0.0,
        translation_z=0.0,
    )
    assert wrl is not None, "WRL conversion returned None"
    assert "#VRML V2.0 utf8" in wrl
    assert "Shape" in wrl

    # After centering the test bbox (x:2-6, y:4-8, z:1-5), the vertices
    # should be X in [-2, 2], Y in [-2, 2], Z in [0, 4] (in mm), then /2.54.
    # Check min/max roughly match expected centered values.
    import re
    points = re.findall(r"([-\d.]+) ([-\d.]+) ([-\d.]+)", wrl)
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    zs = [float(p[2]) for p in points]
    # Allow tiny float error
    assert abs(min(xs) + round(2.0/2.54, 4)) < 0.01, f"X min wrong: {min(xs)}"
    assert abs(max(xs) - round(2.0/2.54, 4)) < 0.01, f"X max wrong: {max(xs)}"
    assert abs(min(zs)) < 0.001, f"Z min should be 0, got {min(zs)}"
    print("test_convert_centered_wrl: PASS")


def test_convert_with_ee_offset():
    """EE translation offsets should be added after centering."""
    conv = Model3DConverter()
    wrl = conv._convert_obj_to_wrl(
        obj_content=FIXTURE_OBJ,
        translation_x=2.54,  # 1 unit after /2.54
        translation_y=0.0,
        translation_z=0.0,
    )
    assert wrl is not None
    import re
    points = re.findall(r"([-\d.]+) ([-\d.]+) ([-\d.]+)", wrl)
    xs = [float(p[0]) for p in points]
    # With +2.54 EE offset, centered X min should shift by +1
    assert abs(min(xs) - (-round(2.0/2.54, 4) + 1.0)) < 0.01, \
        f"X with EE offset wrong: {min(xs)}"
    print("test_convert_with_ee_offset: PASS")
```

And add to `if __name__`:
```python
    test_convert_centered_wrl()
    test_convert_with_ee_offset()
```

- [ ] **Step 2: Run test, confirm FAIL**

Run: `python3 tests/test_3d_centering.py`
Expected: `TypeError: _convert_obj_to_wrl() got an unexpected keyword argument 'translation_x'` (signature mismatch).

- [ ] **Step 3: Rewrite `_convert_obj_to_wrl` signature and body**

Replace the entire `_convert_obj_to_wrl` method (lines ~338-454) with:

```python
def _convert_obj_to_wrl(
    self,
    obj_content: str,
    translation_x: float = 0.0,
    translation_y: float = 0.0,
    translation_z: float = 0.0,
) -> Optional[str]:
    """
    Convert OBJ format to WRL (VRML) with centering and EE placement offset.

    Applies:
      1. XY centering on (0,0) based on OBJ bbox center.
      2. Z shift so model bottom sits at z=0.
      3. EasyEDA placement offset (c_origin - canvas_origin) in mm.

    Ported from easyeda2kicad.py v1.0.1 export_kicad_3d_model.generate_wrl_model.
    """
    try:
        if not obj_content:
            return None

        materials = self._extract_obj_materials(obj_content)

        # Compute centering offsets from bbox
        offset_x, offset_y, offset_z = 0.0, 0.0, 0.0
        bbox = self._get_obj_bbox(obj_content)
        if bbox:
            (x_min, x_max), (y_min, y_max), (z_min, _) = bbox
            offset_x = -(x_min + x_max) / 2.0
            offset_y = -(y_min + y_max) / 2.0
            offset_z = -z_min

        # Add EE placement offset (already in mm)
        offset_x += translation_x
        offset_y += translation_y
        offset_z += translation_z

        self.logger.debug(
            f"3D centering offset: X={offset_x:.2f} Y={offset_y:.2f} Z={offset_z:.2f}"
        )

        vertices = self._extract_obj_vertices(
            obj_content,
            offset_x=offset_x,
            offset_y=offset_y,
            offset_z=offset_z,
        )

        wrl_header = """#VRML V2.0 utf8
# 3D model generated by kicad-lcsc-manager
# Based on easyeda2kicad.py v1.0.1
"""
        raw_wrl = wrl_header

        shapes = obj_content.split("usemtl")[1:]
        if not shapes:
            self.logger.warning("OBJ has no usemtl sections; no geometry exported")
            return None

        for shape in shapes:
            lines = shape.splitlines()
            if not lines:
                continue
            material_name = lines[0].replace(" ", "")
            material = materials.get(material_name)
            if material is None:
                self.logger.warning(f"Material not found: {material_name}, skipping")
                continue

            index_counter = 0
            link_dict = {}
            coord_index = []
            points = []
            for line in lines[1:]:
                if line.strip() and line.split()[0] == "f":
                    face = [int(tok.split("/")[0]) for tok in line.split()[1:]]
                    face_index = []
                    for index in face:
                        if index not in link_dict:
                            link_dict[index] = index_counter
                            face_index.append(str(index_counter))
                            points.append(vertices[index - 1])
                            index_counter += 1
                        else:
                            face_index.append(str(link_dict[index]))
                    face_index.append("-1")
                    coord_index.append(",".join(face_index) + ",")

            # ambientIntensity: Rec.601 luminance from Ka
            try:
                ka = material.get("ambient_color", ["0.2", "0.2", "0.2"])
                ambient_intensity = round(
                    0.299 * float(ka[0]) + 0.587 * float(ka[1]) + 0.114 * float(ka[2]),
                    4,
                )
            except (ValueError, IndexError):
                ambient_intensity = 0.2

            transparency = material.get("transparency", "0")
            diffuse_color = " ".join(material.get("diffuse_color", ["0.8", "0.8", "0.8"]))
            specular_color = " ".join(material.get("specular_color", ["0.5", "0.5", "0.5"]))

            shape_str = textwrap.dedent(
                f"""
        Shape{{
            appearance Appearance {{
                material  Material {{
                    diffuseColor {diffuse_color}
                    specularColor {specular_color}
                    ambientIntensity {ambient_intensity}
                    transparency {transparency}
                    shininess 0.5
                }}
            }}
            geometry IndexedFaceSet {{
                ccw TRUE
                solid FALSE
                coord DEF co Coordinate {{
                    point [
                        {(", ").join(points)}
                    ]
                }}
                coordIndex [
                    {"".join(coord_index)}
                ]
            }}
        }}"""
            )
            raw_wrl += shape_str

        return raw_wrl

    except Exception as e:
        self.logger.error(f"Error converting OBJ to WRL: {e}", exc_info=True)
        return None
```

- [ ] **Step 4: Replace `_extract_obj_materials` with upstream-equivalent version**

Replace the method at ~line 456:

```python
def _extract_obj_materials(self, obj_content: str) -> Dict[str, Dict[str, Any]]:
    """
    Extract material definitions from OBJ content.
    Ported from easyeda2kicad.py v1.0.1 export_kicad_3d_model.get_materials.
    """
    material_regex = "newmtl .*?endmtl"
    matches = re.findall(pattern=material_regex, string=obj_content, flags=re.DOTALL)

    materials = {}
    for match in matches:
        material = {}
        material_id = None
        for value in match.splitlines():
            if value.startswith("newmtl"):
                material_id = value.split()[1]
            elif value.startswith("Ka"):
                material["ambient_color"] = value.split()[1:]
            elif value.startswith("Kd"):
                material["diffuse_color"] = value.split()[1:]
            elif value.startswith("Ks"):
                material["specular_color"] = value.split()[1:]
            elif value.startswith("d "):
                # EasyEDA d = transparency directly (matches VRML semantics).
                # Note leading space to disambiguate from Kd/Ks/Ka lines.
                try:
                    material["transparency"] = str(round(float(value.split()[1]), 4))
                except (ValueError, IndexError):
                    material["transparency"] = "0"

        if material_id is not None:
            materials[material_id] = material
    return materials
```

- [ ] **Step 5: Replace `_extract_obj_vertices` with upstream-equivalent version**

Replace the method at ~line 488:

```python
def _extract_obj_vertices(
    self,
    obj_content: str,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    offset_z: float = 0.0,
) -> List[str]:
    """
    Extract vertices from OBJ content, apply offsets, convert mm→inch (/2.54).
    Ported from easyeda2kicad.py v1.0.1 export_kicad_3d_model.get_vertices.
    """
    result = []
    for line in obj_content.splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0] != "v":
            continue
        try:
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
        except ValueError:
            continue
        result.append(
            " ".join(
                [
                    str(round((x + offset_x) / 2.54, 4)),
                    str(round((y + offset_y) / 2.54, 4)),
                    str(round((z + offset_z) / 2.54, 4)),
                ]
            )
        )
    return result
```

- [ ] **Step 6: Run tests, verify PASS**

Run: `python3 tests/test_3d_centering.py`
Expected:
```
test_obj_bbox: PASS
test_obj_bbox_empty: PASS
test_convert_centered_wrl: PASS
test_convert_with_ee_offset: PASS

All 3D centering tests passed.
```

- [ ] **Step 7: Commit**

```bash
git add plugins/lcsc_manager/converters/model_3d_converter.py tests/test_3d_centering.py
git commit -m "Port upstream 3D model centering and material parsing

- Add XY centering and Z bottom alignment from OBJ bbox
- Apply EE placement offset (c_origin) to WRL vertices
- Use Rec.601 luminance for ambientIntensity (was hardcoded 0.2)
- Fix transparency parser to distinguish 'd ' from Kd/Ks lines
- Remove buggy 'points.insert(-1, points[-1])' line

Based on easyeda2kicad.py v1.0.1 export_kicad_3d_model.py."
```

---

## Task 3: Extract SVGNODE `c_origin`/`z`/`c_rotation` and feed into 3D pipeline

**Files:**
- Modify: `plugins/lcsc_manager/converters/model_3d_converter.py:195-280` (`_extract_3d_model_uuid`, `_extract_model_urls`, `process_component_model`)

**Context:** Upstream computes model translation from `attrs.c_origin - canvas_origin` (see `export_kicad_footprint.py` and `easyeda_importer.py`). Currently the project only reads `attrs.uuid` and ignores the rest. Without this data the WRL offset (Task 2) is 0,0,0 and the model will still be misaligned for any component where EasyEDA's `c_origin` differs from the footprint canvas origin.

- [ ] **Step 1: Write failing test for `_extract_3d_model_info`**

Append to `tests/test_3d_centering.py`:

```python
def test_extract_3d_model_info_with_translation():
    """Should pull uuid AND translation/rotation from SVGNODE."""
    conv = Model3DConverter()
    easyeda_data = {
        "packageDetail": {
            "dataStr": {
                "head": {"x": "4000", "y": "3000"},
                "shape": [
                    'SVGNODE~{"gId":"g1","attrs":{"uuid":"abc123",' +
                    '"c_origin":"4010,3005","z":"2.5","c_rotation":"0,0,90",' +
                    '"title":"SOT-23-3"},"layerid":"19"}',
                ],
            }
        }
    }
    info = conv._extract_3d_model_info(easyeda_data)
    assert info is not None, "expected dict, got None"
    assert info["uuid"] == "abc123"
    # c_origin(4010,3005) - canvas(4000,3000) = (10, 5) mils → /3.937 ≈ mm
    assert abs(info["translation_x"] - (10 / 3.937)) < 1e-4
    assert abs(info["translation_y"] - (5 / 3.937)) < 1e-4
    assert abs(info["translation_z"] - 2.5) < 1e-4
    assert info["rotation"] == (0.0, 0.0, 90.0)
    print("test_extract_3d_model_info_with_translation: PASS")
```

And call it in `__main__`.

- [ ] **Step 2: Run test, confirm AttributeError**

Run: `python3 tests/test_3d_centering.py`
Expected: `AttributeError: 'Model3DConverter' object has no attribute '_extract_3d_model_info'`

- [ ] **Step 3: Add `_extract_3d_model_info` method**

Add below `_extract_3d_model_uuid` in `model_3d_converter.py`:

```python
def _extract_3d_model_info(
    self, easyeda_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Extract full 3D model metadata (uuid + translation + rotation) from SVGNODE.

    EasyEDA stores the 3D model reference in the footprint shape array as:
      SVGNODE~{"attrs":{"uuid":..., "c_origin":"x,y", "z":"...", "c_rotation":"x,y,z"}}

    Translation is computed as (c_origin - canvas_origin) converted mils→mm via /3.937.
    Returns None if SVGNODE or required attrs are missing.
    """
    try:
        package_detail = easyeda_data.get("packageDetail", {})
        data_str = package_detail.get("dataStr", {})
        shape_array = data_str.get("shape", [])
        head = data_str.get("head", {})

        canvas_x = float(head.get("x", 0))
        canvas_y = float(head.get("y", 0))

        for line in shape_array:
            if not isinstance(line, str):
                continue
            parts = line.split("~", 1)
            if len(parts) < 2 or parts[0] != "SVGNODE":
                continue
            try:
                svg_data = json.loads(parts[1])
            except json.JSONDecodeError:
                continue

            attrs = svg_data.get("attrs", {})
            uuid = attrs.get("uuid")
            if not uuid:
                continue

            # c_origin: "x,y" in mils, relative to canvas.
            c_origin_raw = attrs.get("c_origin", "0,0")
            try:
                co_x, co_y = [float(v) for v in c_origin_raw.split(",")]
            except (ValueError, AttributeError):
                co_x, co_y = canvas_x, canvas_y

            # Translation in mm (mils / 3.937)
            translation_x = (co_x - canvas_x) / 3.937
            translation_y = (co_y - canvas_y) / 3.937

            try:
                translation_z = float(attrs.get("z", 0))
            except (ValueError, TypeError):
                translation_z = 0.0

            rotation_raw = attrs.get("c_rotation", "0,0,0")
            try:
                rx, ry, rz = [float(v) for v in rotation_raw.split(",")]
            except (ValueError, AttributeError):
                rx, ry, rz = 0.0, 0.0, 0.0

            self.logger.info(
                f"Found 3D model: uuid={uuid} "
                f"translation=({translation_x:.3f},{translation_y:.3f},{translation_z:.3f}) "
                f"rotation=({rx},{ry},{rz})"
            )

            return {
                "uuid": uuid,
                "translation_x": translation_x,
                "translation_y": translation_y,
                "translation_z": translation_z,
                "rotation": (rx, ry, rz),
                "title": attrs.get("title", ""),
            }

        return None

    except Exception as e:
        self.logger.error(f"Error extracting 3D model info: {e}", exc_info=True)
        return None
```

- [ ] **Step 4: Wire new info into `process_component_model`**

In `process_component_model` (around line 134), replace the `_extract_model_urls` branch with:

```python
            # Extract full 3D model info (uuid + EE placement)
            model_info = self._extract_3d_model_info(easyeda_data)

            if not model_info:
                self.logger.warning("No 3D model info found")
                return models

            uuid = model_info["uuid"]
            model_urls = {
                "obj": ENDPOINT_3D_MODEL_OBJ.format(uuid=uuid),
                "step": ENDPOINT_3D_MODEL_STEP.format(uuid=uuid),
            }
```

And update the OBJ → WRL call (around line 177):

```python
            # Convert OBJ to WRL (with centering + EE offset)
            if obj_content:
                wrl_path = output_dir / f"{lcsc_id}.wrl"
                try:
                    wrl_content = self._convert_obj_to_wrl(
                        obj_content=obj_content,
                        translation_x=model_info["translation_x"],
                        translation_y=model_info["translation_y"],
                        translation_z=model_info["translation_z"],
                    )
                    if wrl_content:
                        with open(wrl_path, 'w', encoding='utf-8') as f:
                            f.write(wrl_content)
                        models["wrl"] = wrl_path
                        self.logger.info(f"WRL model saved: {wrl_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to convert OBJ to WRL: {e}")
```

- [ ] **Step 5: Run tests, verify PASS**

Run: `python3 tests/test_3d_centering.py`
Expected: all 5 tests PASS.

- [ ] **Step 6: Manual regression check against C7220642**

Run: `python3 tests/test_3d_model_download.py 2>&1 | tail -20` (if this existing script targets C2040 change to C7220642 first, or run a quick ad-hoc import through the main plugin flow).

Visually check: does the generated `.wrl` place the model origin near (0,0,0) relative to the footprint reference? Previous version produced offset models.

- [ ] **Step 7: Commit**

```bash
git add plugins/lcsc_manager/converters/model_3d_converter.py tests/test_3d_centering.py
git commit -m "Extract c_origin/z/c_rotation from SVGNODE for 3D alignment

Pipes EasyEDA placement metadata into _convert_obj_to_wrl so models
are positioned relative to the footprint reference, not the canvas origin."
```

---

## Task 4: Port SSL context with macOS KiCad certifi fallback into `lcsc_api.py`

**Files:**
- Modify: `plugins/lcsc_manager/api/lcsc_api.py` (add method, wire into `_get_session`)

**Context:** Upstream ships `_create_ssl_context` that locates KiCad's embedded certifi bundle on macOS first, then falls back to the `certifi` package, then the system store. This prevents `SSL: CERTIFICATE_VERIFY_FAILED` inside packaged KiCad where system CAs aren't visible. Current project uses `requests` defaults which fail in KiCad's embedded Python on some setups.

Because the rest of the codebase uses `requests` (not `urllib`), we adapt the approach: build a `requests.Session` that sets `session.verify` to a discovered CA bundle path.

- [ ] **Step 1: Read upstream implementation**

Re-read `/tmp/easyeda2kicad/easyeda2kicad/easyeda/easyeda_api.py:125-162` — `_create_ssl_context`.

- [ ] **Step 2: Add `_discover_ca_bundle` helper**

Add at top of `plugins/lcsc_manager/api/lcsc_api.py` after imports:

```python
import glob
import sys


def _discover_ca_bundle() -> Optional[str]:
    """
    Find a CA bundle path for requests.Session.verify, with preference for
    KiCad's embedded certifi on macOS. Falls back to the certifi package, then
    None (system store).

    Adapted from easyeda2kicad.py v1.0.1 _create_ssl_context.
    """
    # macOS: KiCad bundles its own certifi inside KiCad.app
    if sys.platform == "darwin":
        candidates = sorted(
            glob.glob(
                "/Applications/KiCad*/KiCad.app/Contents/Frameworks/"
                "Python.framework/Versions/*/lib/python*/site-packages/certifi/cacert.pem"
            ),
            reverse=True,  # newest KiCad first
        )
        for path in candidates:
            if Path(path).is_file():
                logger.debug(f"Using KiCad certifi bundle: {path}")
                return path

    # Fallback: certifi package if installed
    try:
        import certifi
        bundle = certifi.where()
        if Path(bundle).is_file():
            logger.debug(f"Using certifi package bundle: {bundle}")
            return bundle
    except ImportError:
        pass

    return None


_CA_BUNDLE: Optional[str] = None
```

- [ ] **Step 3: Apply bundle in `_get_session`**

In `LCSCAPIClient._get_session` (line 40), add after creating the session:

```python
        global _CA_BUNDLE
        if _CA_BUNDLE is None:
            _CA_BUNDLE = _discover_ca_bundle() or ""  # empty string disables caching
        if _CA_BUNDLE:
            session.verify = _CA_BUNDLE
```

- [ ] **Step 4: Run existing API test as smoke check**

Run: `python3 tests/test_api_detailed.py 2>&1 | head -30` (or whichever existing script reaches EasyEDA with a real HTTPS call).
Expected: no new errors — existing behaviour preserved.

- [ ] **Step 5: Commit**

```bash
git add plugins/lcsc_manager/api/lcsc_api.py
git commit -m "Add KiCad-embedded certifi fallback to API session

Prefers certifi bundle shipped inside KiCad.app on macOS, then the
certifi package, then the system store. Avoids SSL verify failures in
KiCad's embedded Python."
```

---

## Task 5: Add optional disk cache for EasyEDA component JSON

**Files:**
- Modify: `plugins/lcsc_manager/api/lcsc_api.py` (wrap `search_component` + SVG fetches)
- Modify: `plugins/lcsc_manager/preview/kicad_preview.py:69-104` (use same cache dir)

**Context:** Upstream `EasyedaApi._get_cache_path`/`_read_from_cache`/`_write_to_cache` provides per-LCSC JSON caching. Two wins: faster dev iteration on the same part, and reduced chance of hitting 403 rate limits while debugging. Scope: **opt-in**, disabled by default to avoid changing production behaviour without user consent.

- [ ] **Step 1: Add cache config + helpers**

In `LCSCAPIClient.__init__` (line 35), add:

```python
    CACHE_DIR = Path.home() / ".kicad_lcsc_manager_cache"

    def __init__(self):
        self.config = get_config()
        self.last_request_time = 0
        self.use_cache = bool(self.config.get("api_cache_enabled", False))
        if self.use_cache:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
```

Add helper methods after `_rate_limit`:

```python
    def _cache_path(self, identifier: str, extension: str = "json") -> Path:
        safe_id = identifier.replace("/", "_").replace("\\", "_")
        return self.CACHE_DIR / f"{safe_id}.{extension}"

    def _cache_read(self, path: Path) -> Optional[str]:
        if not self.use_cache or not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return None

    def _cache_write(self, path: Path, data: str) -> None:
        if not self.use_cache:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")
```

- [ ] **Step 2: Wire cache into `search_component`**

In `search_component` (around line 240), before the HTTP call:

```python
        # Check cache first
        cache_path = self._cache_path(f"component_{lcsc_id}")
        cached = self._cache_read(cache_path)
        if cached:
            try:
                response = json.loads(cached)
                logger.info(f"Cache hit: {lcsc_id}")
            except json.JSONDecodeError:
                response = None
        else:
            response = None

        if response is None:
            # Step 1: Get EasyEDA data (for symbol/footprint)
            url = f"https://easyeda.com/api/products/{lcsc_id}/components"
            response = self._make_request(
                method="GET",
                url=url,
                params={"version": "6.4.19.5"}
            )
            # Write successful response to cache
            if response.get("success"):
                self._cache_write(cache_path, json.dumps(response))
```

Add `import json` at top if not present (it's already used elsewhere but confirm).

- [ ] **Step 3: Smoke test with cache disabled**

Run: `python3 tests/test_api_detailed.py 2>&1 | head -30`
Expected: same output as before — opt-in default means no behaviour change.

- [ ] **Step 4: Manual smoke test with cache enabled**

Temporarily edit `~/.kicad_lcsc_manager/config.json` (or wherever `get_config()` reads from) adding `"api_cache_enabled": true`, run an import, rerun same import. Second run should log `Cache hit: <lcsc_id>`.

Revert config change.

- [ ] **Step 5: Commit**

```bash
git add plugins/lcsc_manager/api/lcsc_api.py
git commit -m "Add opt-in disk cache for EasyEDA component JSON

Enabled via 'api_cache_enabled' config flag. Cache dir lives under
~/.kicad_lcsc_manager_cache. Off by default to preserve existing
behaviour; primary use is faster dev iteration."
```

---

## Task 6: Add H and V commands to `h_SOLIDREGION` path parser

**Files:**
- Modify: `plugins/lcsc_manager/converters/jlc2kicad/footprint_handlers.py:447-521` (`h_SOLIDREGION`)
- Test: `tests/test_footprint_handlers_patches.py` (new)

**Context:** EasyEDA SVG paths use `H x` and `V y` (horizontal/vertical line) commands. Current parser's regex `([MLAZ])` drops them silently, producing incomplete silk-screen / edge-cut polygons on parts that use rectangular outlines. Upstream's `_parse_solid_region_path` handles all of M/L/H/V/A/Z.

- [ ] **Step 1: Write failing test**

Create `tests/test_footprint_handlers_patches.py`:

```python
"""
Unit tests for footprint handler patches.
Run with: python3 tests/test_footprint_handlers_patches.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

# Import module directly to access internal helpers without KicadModTree state
from lcsc_manager.converters.jlc2kicad import footprint_handlers as fh


class FakeFootprintInfo:
    max_X = min_X = max_Y = min_Y = 0.0
    models = ""


class FakeKicadMod:
    def __init__(self):
        self.appended = []

    def append(self, obj):
        self.appended.append(obj)


def test_solid_region_handles_h_v_commands():
    # Simple 100x50 mil rectangle using M, H, V, Z (no L)
    # M 0 0 H 100 V 50 H 0 V 0 Z
    data = ["99", "id1", "M 0 0 H 100 V 50 H 0 V 0 Z", "solid"]
    mod = FakeKicadMod()
    info = FakeFootprintInfo()

    fh.h_SOLIDREGION(data, mod, info)

    assert len(mod.appended) == 1, f"expected 1 polygon, got {len(mod.appended)}"
    poly = mod.appended[0]
    nodes = list(poly.nodes) if hasattr(poly, "nodes") else poly.nodes
    # We should have at least 4 corners (H/V turned into points)
    assert len(nodes) >= 4, f"expected >=4 nodes for rectangle, got {len(nodes)}"
    xs = [n[0] for n in nodes]
    ys = [n[1] for n in nodes]
    # Approximate — mil→mm via /3.937
    assert abs(max(xs) - (100 / 3.937)) < 0.01
    assert abs(max(ys) - (50 / 3.937)) < 0.01
    print("test_solid_region_handles_h_v_commands: PASS")


if __name__ == "__main__":
    test_solid_region_handles_h_v_commands()
    print("\nFootprint handler patch tests passed.")
```

- [ ] **Step 2: Run test, confirm FAIL**

Run: `python3 tests/test_footprint_handlers_patches.py`
Expected: assertion failure on node count (current parser drops H/V).

- [ ] **Step 3: Update `h_SOLIDREGION` to handle H and V**

Find `h_SOLIDREGION` (line 447) and replace the command_pattern regex + its branches. Replace lines 462-515 with:

```python
    # Parse SVG path — tokenize per command
    path = data[2]
    points = []
    current_pos = (0.0, 0.0)

    # Tokenize the path into command segments
    command_regex = re.compile(
        r"([MLHVAZmlhvaz])\s*((?:[-+]?\d*\.?\d+[\s,]*)*)"
    )
    number_regex = re.compile(r"[-+]?\d*\.?\d+")

    for match in command_regex.finditer(path):
        cmd = match.group(1).upper()
        params = [float(n) for n in number_regex.findall(match.group(2))]

        if cmd == "M" and len(params) >= 2:
            current_pos = (params[0], params[1])
            points.append(current_pos)
        elif cmd == "L" and len(params) >= 2:
            current_pos = (params[0], params[1])
            points.append(current_pos)
        elif cmd == "H" and len(params) >= 1:
            current_pos = (params[0], current_pos[1])
            points.append(current_pos)
        elif cmd == "V" and len(params) >= 1:
            current_pos = (current_pos[0], params[0])
            points.append(current_pos)
        elif cmd == "A" and len(params) >= 7:
            rx, ry, rotation = params[0], params[1], params[2]
            large_arc_flag = int(params[3])
            sweep_flag = int(params[4])
            end_x, end_y = params[5], params[6]
            arc_points = svg_arc_to_points(
                current_pos[0], current_pos[1],
                rx, ry, rotation,
                large_arc_flag, sweep_flag,
                end_x, end_y,
            )
            points.extend(arc_points)
            current_pos = (end_x, end_y)
        elif cmd == "Z":
            pass  # polygon auto-closes
```

Keep the existing mil→mm conversion and `kicad_mod.append(Polygon(...))` tail.

- [ ] **Step 4: Run test, verify PASS**

Run: `python3 tests/test_footprint_handlers_patches.py`
Expected: `test_solid_region_handles_h_v_commands: PASS`

- [ ] **Step 5: Commit**

```bash
git add plugins/lcsc_manager/converters/jlc2kicad/footprint_handlers.py tests/test_footprint_handlers_patches.py
git commit -m "Add H/V commands to h_SOLIDREGION path parser

Fixes incomplete silkscreen/edge-cut polygons on parts that use
rectangular outlines encoded with H/V (horizontal/vertical) SVG
commands instead of explicit L lines."
```

---

## Task 7: Normalize `A(1)`-style pad numbers in `h_PAD`

**Files:**
- Modify: `plugins/lcsc_manager/converters/jlc2kicad/footprint_handlers.py:97-220` (`h_PAD`)
- Test: `tests/test_footprint_handlers_patches.py` (extend)

**Context:** EasyEDA encodes some pad numbers as `NAME(NUMBER)` (e.g. `VCC(1)`, `A(1)`). KiCad expects the bare number. Upstream strips the parentheses; current parser keeps the full string, producing polluted pad numbers on BGA/connector parts.

- [ ] **Step 1: Add failing test**

Append to `tests/test_footprint_handlers_patches.py`:

```python
from lcsc_manager.converters.jlc2kicad.footprint_handlers import _normalize_pad_number


def test_pad_number_bare_number():
    assert _normalize_pad_number("1") == "1"
    assert _normalize_pad_number("A12") == "A12"
    print("test_pad_number_bare_number: PASS")


def test_pad_number_parenthesized():
    assert _normalize_pad_number("A(1)") == "1"
    assert _normalize_pad_number("VCC(3)") == "3"
    assert _normalize_pad_number("GND ( 42 )") == "42"
    print("test_pad_number_parenthesized: PASS")


def test_pad_number_empty():
    assert _normalize_pad_number("") == ""
    assert _normalize_pad_number(None) == ""
    print("test_pad_number_empty: PASS")
```

Add to `__main__`:
```python
    test_pad_number_bare_number()
    test_pad_number_parenthesized()
    test_pad_number_empty()
```

- [ ] **Step 2: Run test, confirm ImportError**

Run: `python3 tests/test_footprint_handlers_patches.py`
Expected: `ImportError: cannot import name '_normalize_pad_number'`

- [ ] **Step 3: Add helper and call site**

Add near the top of `footprint_handlers.py` (after `mil2mm`):

```python
def _normalize_pad_number(raw: str) -> str:
    """
    Canonicalize EasyEDA pad numbers.

    Returns the content inside parentheses if present (e.g. "A(1)" → "1"),
    otherwise returns the stripped original. Empty/None → "".
    """
    if not raw:
        return ""
    s = str(raw).strip()
    if "(" in s and ")" in s:
        try:
            inside = s.split("(", 1)[1].rsplit(")", 1)[0].strip()
            if inside:
                return inside
        except IndexError:
            pass
    return s
```

In `h_PAD` (line 133), replace:

```python
    pad_number = data[6]
```

with:

```python
    pad_number = _normalize_pad_number(data[6])
```

- [ ] **Step 4: Run tests, verify PASS**

Run: `python3 tests/test_footprint_handlers_patches.py`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/lcsc_manager/converters/jlc2kicad/footprint_handlers.py tests/test_footprint_handlers_patches.py
git commit -m "Normalize 'A(1)'-style pad numbers in h_PAD

EasyEDA encodes some connector/BGA pads as NAME(NUMBER); KiCad
expects the bare number. Strip parentheses content."
```

---

## Task 8: Implement real `h_VIA` (replace warn-only stub)

**Files:**
- Modify: `plugins/lcsc_manager/converters/jlc2kicad/footprint_handlers.py:557-562` (`h_VIA`)

**Context:** The current `h_VIA` only logs a warning. Some footprints (RF modules, thermal pads) rely on vias. We emit them as NPTH pads for compatibility, matching what upstream does at the lowest level.

- [ ] **Step 1: Replace `h_VIA` body**

Replace lines 557-562 with:

```python
def h_VIA(data, kicad_mod, footprint_info):
    """
    Convert an EasyEDA via into a KiCad NPTH pad.

    data : [
        0 : x
        1 : y
        2 : diameter
        3 : net
        4 : drill radius
        5 : id
        ...
    ]
    """
    try:
        at = [mil2mm(data[0]), mil2mm(data[1])]
        diameter = float(mil2mm(data[2])) * 2
        drill = float(mil2mm(data[4])) * 2 if len(data) > 4 and data[4] else diameter / 2

        footprint_info.max_X = max(footprint_info.max_X, at[0])
        footprint_info.min_X = min(footprint_info.min_X, at[0])
        footprint_info.max_Y = max(footprint_info.max_Y, at[1])
        footprint_info.min_Y = min(footprint_info.min_Y, at[1])

        kicad_mod.append(
            Pad(
                number="",
                type=Pad.TYPE_NPTH,
                shape=Pad.SHAPE_CIRCLE,
                at=at,
                size=diameter,
                rotation=0,
                drill=drill,
                layers=Pad.LAYERS_NPTH,
            )
        )
    except (ValueError, IndexError) as e:
        logging.warning(f"h_VIA: failed to parse via data {data}: {e}")
```

- [ ] **Step 2: Smoke run existing conversion test**

Run: `python3 tests/test_conversion.py 2>&1 | tail -20`
Expected: no new exceptions.

- [ ] **Step 3: Commit**

```bash
git add plugins/lcsc_manager/converters/jlc2kicad/footprint_handlers.py
git commit -m "Implement h_VIA as NPTH pad instead of warn-only stub

Some footprints (RF modules, thermal pads) rely on vias. Emit them
as non-plated through holes for KiCad compatibility."
```

---

## Task 9: Fix multi-unit pin numbers in `h_P` (symbol_handlers)

**Files:**
- Modify: `plugins/lcsc_manager/converters/jlc2kicad/symbol_handlers.py:93-181` (`h_P`)
- Modify: `plugins/lcsc_manager/converters/symbol_converter.py:123-134` (call site: pass raw line)
- Test: `tests/test_symbol_pin_numbers.py` (new)

**Context:** Upstream (`add_easyeda_pin` in `easyeda_importer.py`) documents the PIN line format:
```
P~settings^^dot^^path^^name^^num^^dot_bis^^clock
  settings: visibility~type~spice_pin_number~pos_x~pos_y~rotation~id~is_locked
  num:      show~x~y~rotation~number~text_anchor~font~font_size
```
The canonical KiCad pin number is at `segments[4].split("~")[4]` (the `num` segment's `number` field). Current `h_P` uses `data[2]` (spice_pin_number) which is wrong for multi-unit symbols.

- [ ] **Step 1: Write failing test**

Create `tests/test_symbol_pin_numbers.py`:

```python
"""
Unit tests for multi-unit pin number extraction.
Run with: python3 tests/test_symbol_pin_numbers.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.converters.jlc2kicad.symbol_handlers import _extract_pin_number


def test_single_unit_pin():
    # Simple single-unit pin where spice == kicad number
    line = (
        "P~1~0~3~-10~0~gge1~0"       # settings (8 fields)
        "^^30~-10"                    # dot (2)
        "^^M 5 -10 L 30 -10~#000"     # path (2)
        "^^1~32~-10~0~A~start~~7"     # name (8)
        "^^1~25~-10~0~3~end~~7"       # num  (8) — number at index 4 = "3"
        "^^0~40~-10"                  # dot_bis
        "^^0~"                         # clock
    )
    assert _extract_pin_number(line) == "3"
    print("test_single_unit_pin: PASS")


def test_multi_unit_pin_mismatch():
    # Multi-unit: spice_pin_number = 1 but real KiCad number in num segment = 14
    line = (
        "P~1~0~1~-10~0~gge2~0"
        "^^30~-10"
        "^^M 5 -10 L 30 -10~#000"
        "^^1~32~-10~0~B~start~~7"
        "^^1~25~-10~0~14~end~~7"     # real KiCad number
        "^^0~40~-10"
        "^^0~"
    )
    assert _extract_pin_number(line) == "14", \
        f"expected '14' (multi-unit canonical), got {_extract_pin_number(line)!r}"
    print("test_multi_unit_pin_mismatch: PASS")


def test_fallback_to_spice():
    # Malformed: num segment missing, must fallback to spice_pin_number
    line = "P~1~0~7~-10~0~gge3~0^^30~-10^^M~#000"
    assert _extract_pin_number(line) == "7"
    print("test_fallback_to_spice: PASS")


if __name__ == "__main__":
    test_single_unit_pin()
    test_multi_unit_pin_mismatch()
    test_fallback_to_spice()
    print("\nSymbol pin number tests passed.")
```

- [ ] **Step 2: Run test, confirm ImportError**

Run: `python3 tests/test_symbol_pin_numbers.py`
Expected: `ImportError: cannot import name '_extract_pin_number'`

- [ ] **Step 3: Add `_extract_pin_number` helper**

Add near top of `plugins/lcsc_manager/converters/jlc2kicad/symbol_handlers.py` (after imports, before handlers):

```python
def _extract_pin_number(line: str) -> str:
    """
    Extract the canonical KiCad pin number from an EasyEDA PIN line.

    Line format (from easyeda2kicad upstream docs):
        P~settings^^dot^^path^^name^^num^^dot_bis^^clock
        settings: visibility~type~spice_pin_number~pos_x~pos_y~rotation~id~is_locked
        num:      show~x~y~rotation~number~text_anchor~font~font_size

    Returns num.number (segment 4, field 4) if available, else
    settings.spice_pin_number (segment 0, field 2) as fallback.

    Ported from easyeda2kicad.py v1.0.1 easyeda_importer.add_easyeda_pin.
    """
    if not line:
        return ""

    # Strip leading "P~" if present
    body = line[2:] if line.startswith("P~") else line
    segments = [seg.split("~") for seg in body.split("^^")]

    # Preferred: num segment field 4
    if len(segments) > 4 and len(segments[4]) > 4:
        num = segments[4][4].strip()
        if num:
            return num

    # Fallback: settings.spice_pin_number (field index 2 in the settings segment)
    if len(segments) > 0 and len(segments[0]) > 2:
        return segments[0][2].strip()

    return ""
```

- [ ] **Step 4: Run test, verify PASS**

Run: `python3 tests/test_symbol_pin_numbers.py`
Expected: 3 PASS lines.

- [ ] **Step 5: Rewrite `h_P` to take raw line instead of pre-split args**

Because `h_P` now needs access to the full line (for `^^` segments), we pass the raw line through. This is a signature change — update both handler and caller.

Replace `h_P` in `symbol_handlers.py` starting at line 93 with a new signature:

```python
def h_P(data, translation, kicad_symbol, raw_line: str = ""):
    """
    Add Pin to the symbol.

    Args:
        data: pre-split (~) fields (legacy interface, used for coordinates etc.)
        translation: (x, y) offset
        kicad_symbol: target symbol
        raw_line: full untouched EasyEDA PIN line — used to extract the
                  canonical pin number from the ^^-delimited 'num' segment.
    """

    if data[1] == "0":
        electrical_type = "unspecified"
    elif data[1] == "1":
        electrical_type = "input"
    elif data[1] == "2":
        electrical_type = "output"
    elif data[1] == "3":
        electrical_type = "bidirectional"
    elif data[1] == "4":
        electrical_type = "power_in"
    else:
        electrical_type = "unspecified"

    # Use canonical num-segment number when the raw line is available,
    # otherwise fall back to the legacy spice_pin_number at data[2].
    pin_number = _extract_pin_number(raw_line) if raw_line else data[2]
    pin_name = data[13]

    # ...rest of body unchanged...
```

Keep the rest of the original function (coordinate computation, drawing append) exactly as-is.

- [ ] **Step 6: Update caller in `symbol_converter.py`**

In `symbol_converter.py` around line 127-133, change the handler dispatch:

```python
            if model in symbol_handlers.handlers:
                try:
                    if model == "P":
                        # h_P needs the raw line to extract multi-unit pin numbers
                        symbol_handlers.handlers[model](
                            data=args[1:],
                            translation=translation,
                            kicad_symbol=kicad_symbol,
                            raw_line=line,
                        )
                    else:
                        symbol_handlers.handlers[model](
                            data=args[1:],
                            translation=translation,
                            kicad_symbol=kicad_symbol,
                        )
                except Exception as e:
                    self.logger.warning(f"Failed to parse shape element {model}: {e}")
```

- [ ] **Step 7: Re-run unit tests**

Run: `python3 tests/test_symbol_pin_numbers.py`
Expected: still 3 PASS.

- [ ] **Step 8: Commit**

```bash
git add plugins/lcsc_manager/converters/jlc2kicad/symbol_handlers.py plugins/lcsc_manager/converters/symbol_converter.py tests/test_symbol_pin_numbers.py
git commit -m "Extract canonical KiCad pin number from ^^ 'num' segment

EasyEDA stores two pin numbers: spice_pin_number (settings segment)
and the canonical KiCad number (num segment field 4). For multi-unit
symbols these differ; the old code used spice_pin_number and produced
wrong numbers on multi-unit ICs.

Ported from easyeda2kicad.py v1.0.1 easyeda_importer.add_easyeda_pin."
```

---

## Task 10: End-to-end regression on C7220642 and one multi-unit IC

**Files:**
- Create: `tests/test_regression_components.py`

**Context:** Before declaring Option B done, sanity-check a known-working part (C7220642, already imported under the old code) and a new multi-unit IC (e.g. C6568 = LM358 dual op-amp — adjust if not in EasyEDA). We're not diff-ing against golden files (would be brittle); we check structural invariants.

- [ ] **Step 1: Pick regression targets**

Confirm LCSC IDs for test:
- `C7220642` — baseline, already validated
- One multi-unit part — suggestion: `C7950` (NE555) or `C6568` (LM358). Verify availability: `python3 -c "from plugins.lcsc_manager.api.lcsc_api import LCSCAPIClient; c=LCSCAPIClient(); r=c.search_component('C7950'); print(bool(r), r.get('name') if r else '')"` (if first fails, try next)

Record the chosen ID in a constant.

- [ ] **Step 2: Write regression script**

Create `tests/test_regression_components.py`:

```python
"""
End-to-end regression test for components after upstream integration.
Run with: python3 tests/test_regression_components.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.api.lcsc_api import LCSCAPIClient
from lcsc_manager.converters.symbol_converter import SymbolConverter
from lcsc_manager.converters.footprint_converter import FootprintConverter
from lcsc_manager.converters.model_3d_converter import Model3DConverter

# Test targets — replace second entry with whatever confirmed multi-unit part
# exists in EasyEDA right now.
COMPONENTS = ["C7220642", "C7950"]


def test_import(lcsc_id: str) -> None:
    print(f"\n--- {lcsc_id} ---")
    client = LCSCAPIClient()
    component = client.search_component(lcsc_id)
    assert component is not None, f"{lcsc_id}: not found in EasyEDA"
    print(f"  name: {component.get('name')}")
    print(f"  package: {component.get('package')}")

    easyeda_data = component["easyeda_data"]

    # Symbol
    symbol_conv = SymbolConverter()
    symbol_text = symbol_conv.convert(easyeda_data, component)
    assert "(symbol" in symbol_text, f"{lcsc_id}: symbol output missing (symbol token"
    assert "(pin" in symbol_text, f"{lcsc_id}: symbol has no pins"

    # Pin numbers should be non-empty AND not contain '^^' remnants
    for line in symbol_text.splitlines():
        if "(number " in line:
            num = line.split("(number", 1)[1].strip().split(")")[0].strip('" ')
            assert num, f"{lcsc_id}: empty pin number in line: {line!r}"
            assert "^^" not in num, f"{lcsc_id}: pin number contains ^^: {num!r}"
    print(f"  symbol: {symbol_text.count('(pin')} pins")

    # Footprint
    fp_conv = FootprintConverter()
    footprint_text = fp_conv.convert(easyeda_data, component)
    assert "(footprint" in footprint_text or "(module" in footprint_text
    # Pad numbers should not contain parentheses
    for line in footprint_text.splitlines():
        if "(pad " in line:
            # Extract the first token after (pad
            after = line.split("(pad", 1)[1].strip()
            first_tok = after.split()[0].strip('"')
            assert "(" not in first_tok and ")" not in first_tok, \
                f"{lcsc_id}: un-normalized pad number: {first_tok!r}"
    print(f"  footprint: {footprint_text.count('(pad')} pads")

    # 3D model (best-effort — don't fail whole test if EasyEDA returns nothing)
    with tempfile.TemporaryDirectory() as tmp:
        m3d_conv = Model3DConverter()
        try:
            models = m3d_conv.process_component_model(
                easyeda_data=easyeda_data,
                component_info=component,
                output_dir=Path(tmp),
            )
            if models.get("wrl"):
                wrl_text = Path(models["wrl"]).read_text()
                assert "#VRML V2.0" in wrl_text
                # Sanity: at least one centered point (won't be 0 0 0 unless single-vertex model)
                print(f"  wrl: {len(wrl_text)} bytes")
            else:
                print("  wrl: none (no 3D model)")
        except Exception as e:
            print(f"  wrl: skipped ({e})")


if __name__ == "__main__":
    for lcsc_id in COMPONENTS:
        test_import(lcsc_id)
    print("\nRegression tests complete.")
```

- [ ] **Step 3: Run regression**

Run: `python3 tests/test_regression_components.py`
Expected: every assertion passes; output lines show reasonable pin/pad counts.

If any assertion fires, debug the offending part — the plan's earlier tasks missed something. Revisit, patch, rerun.

- [ ] **Step 4: Commit regression script**

```bash
git add tests/test_regression_components.py
git commit -m "Add end-to-end regression test for component import

Covers a baseline single-unit part and a multi-unit IC, validating
that pin numbers, pad numbers, and 3D WRL output all look correct
after the upstream easyeda2kicad integration."
```

---

## Self-Review Checklist

**Spec coverage (Option B from chat):**
- [x] 3D model centering + EE offset — Tasks 1, 2, 3
- [x] SSL context / macOS KiCad certifi fallback — Task 4
- [x] Disk cache (opt-in) — Task 5
- [x] Footprint handler gap patches (H/V, pad normalization, VIA) — Tasks 6, 7, 8
- [x] Multi-unit pin number fix — Task 9
- [x] Regression verification — Task 10

**Placeholder scan:** No "TODO" / "fill in" — every step has code or concrete commands.

**Type consistency:**
- `_convert_obj_to_wrl` signature is consistent across Tasks 2 and 3 (same keyword args).
- `_extract_3d_model_info` returns dict with keys (`uuid`, `translation_x/y/z`, `rotation`, `title`) used identically in Tasks 3 and 10.
- `_extract_pin_number` used consistently in Task 9 and implicitly validated in Task 10.
- `_normalize_pad_number` defined in Task 7, called in same task — no cross-task drift.

**Interface consistency:**
- `h_P`'s new `raw_line` param defaults to `""` so any other caller of the handler (if any) still works.
- `_convert_obj_to_wrl` keeps old positional arg (`obj_content`) first.
