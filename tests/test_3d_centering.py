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
