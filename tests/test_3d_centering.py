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
Kd 0.7 0.6 0.4
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

    # Extract only the point [...] contents so material color lines don't
    # contaminate the coordinate regex.
    import re
    point_section = re.search(r"point \[(.*?)\]", wrl, re.DOTALL)
    assert point_section is not None, "WRL has no point section"
    coords = re.findall(
        r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
        point_section.group(1),
    )
    assert coords, "no coordinates extracted from point section"
    xs = [float(p[0]) for p in coords]
    ys = [float(p[1]) for p in coords]
    zs = [float(p[2]) for p in coords]
    # X and Y should be centered around 0 (fixture bbox x:2-6 y:4-8).
    assert abs(min(xs) + round(2.0/2.54, 4)) < 0.01, f"X min wrong: {min(xs)}"
    assert abs(max(xs) - round(2.0/2.54, 4)) < 0.01, f"X max wrong: {max(xs)}"
    assert abs(min(ys) + round(2.0/2.54, 4)) < 0.01, f"Y min wrong: {min(ys)}"
    assert abs(max(ys) - round(2.0/2.54, 4)) < 0.01, f"Y max wrong: {max(ys)}"
    # Z should be shifted so bottom sits at 0 (fixture bbox z:1-5).
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
    point_section = re.search(r"point \[(.*?)\]", wrl, re.DOTALL)
    assert point_section is not None
    coords = re.findall(
        r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
        point_section.group(1),
    )
    xs = [float(p[0]) for p in coords]
    # With +2.54 EE offset, centered X min should shift by +1.
    assert abs(min(xs) - (-round(2.0/2.54, 4) + 1.0)) < 0.01, \
        f"X with EE offset wrong: {min(xs)}"
    print("test_convert_with_ee_offset: PASS")


if __name__ == "__main__":
    test_obj_bbox()
    test_obj_bbox_empty()
    test_convert_centered_wrl()
    test_convert_with_ee_offset()
    print("\nAll 3D centering tests passed.")
