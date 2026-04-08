"""
Unit tests for footprint handler patches.
Run with: python3 tests/test_footprint_handlers_patches.py
"""
import sys
import types
from pathlib import Path

# Stub KicadModTree so handler module can be imported without KiCad
if "KicadModTree" not in sys.modules:
    km = types.ModuleType("KicadModTree")
    for name in [
        "Arc", "Circle", "Line", "Pad", "RectFill", "RectLine",
        "Text", "Vector2D", "Footprint", "KicadFileHandler", "Translation", "Model",
    ]:
        setattr(km, name, type(name, (), {"__init__": lambda self, **kw: setattr(self, "_kw", kw)}))
    # Pad needs some class attrs used by h_PAD
    km.Pad.TYPE_THT = "thru_hole"
    km.Pad.TYPE_SMT = "smd"
    km.Pad.TYPE_NPTH = "np_thru_hole"
    km.Pad.SHAPE_OVAL = "oval"
    km.Pad.SHAPE_RECT = "rect"
    km.Pad.SHAPE_CIRCLE = "circle"
    km.Pad.SHAPE_CUSTOM = "custom"
    km.Pad.LAYERS_THT = ["*.Cu", "*.Mask"]
    km.Pad.LAYERS_SMT = ["F.Cu", "F.Mask", "F.Paste"]
    km.Pad.LAYERS_NPTH = ["*.Cu", "*.Mask"]
    # Polygon needs nodes accessible
    class Polygon:
        def __init__(self, **kw):
            self.nodes = kw.get("nodes", [])
            self._kw = kw
    km.Polygon = Polygon
    sys.modules["KicadModTree"] = km

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
    """M+H+V+Z should produce a closed rectangle, not just 2 points."""
    # Simple 100x50 mil rectangle using M, H, V, Z (no L)
    # Path: M 0 0 H 100 V 50 H 0 V 0 Z
    data = ["99", "id1", "M 0 0 H 100 V 50 H 0 V 0 Z", "solid"]
    mod = FakeKicadMod()
    info = FakeFootprintInfo()

    fh.h_SOLIDREGION(data, mod, info)

    assert len(mod.appended) == 1, f"expected 1 polygon, got {len(mod.appended)}"
    poly = mod.appended[0]
    nodes = list(poly.nodes) if hasattr(poly, "nodes") else poly.nodes
    # We should have at least 4 corners (H/V turned into points)
    assert len(nodes) >= 4, f"expected >=4 nodes for rectangle, got {len(nodes)}"

    # Extract x/y from either (x,y) tuples or KicadModTree Vector-like objects
    def xy(n):
        if isinstance(n, (tuple, list)):
            return float(n[0]), float(n[1])
        return float(n.x), float(n.y)

    pts = [xy(n) for n in nodes]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    # Approximate — mil→mm via /3.937
    assert abs(max(xs) - (100 / 3.937)) < 0.01, f"max X wrong: {max(xs)}"
    assert abs(max(ys) - (50 / 3.937)) < 0.01, f"max Y wrong: {max(ys)}"
    assert abs(min(xs)) < 0.01, f"min X wrong: {min(xs)}"
    assert abs(min(ys)) < 0.01, f"min Y wrong: {min(ys)}"
    print("test_solid_region_handles_h_v_commands: PASS")


def test_solid_region_ignores_lowercase_commands():
    """Lowercase relative commands are not matched by the regex (matches upstream)."""
    # Lowercase h should NOT be parsed — only the M absolute at the start.
    data = ["99", "id_lc", "M 0 0 h 100 v 50 z", "solid"]
    mod = FakeKicadMod()
    info = FakeFootprintInfo()

    fh.h_SOLIDREGION(data, mod, info)

    # Should get either no polygon (fewer than 3 points after filtering) or
    # a degenerate single-point polygon. Most importantly, the lowercase h/v
    # must NOT produce additional points as if they were absolute.
    if mod.appended:
        poly = mod.appended[0]
        nodes = list(poly.nodes) if hasattr(poly, "nodes") else poly.nodes
        # At most 1 point (the M); definitely no (100/3.937, 0) or similar
        def xy(n):
            if isinstance(n, (tuple, list)):
                return float(n[0]), float(n[1])
            return float(n.x), float(n.y)
        pts = [xy(n) for n in nodes]
        # If any point has X close to 100/3.937 we've got the bug back
        for x, y in pts:
            assert abs(x - (100 / 3.937)) > 0.1, \
                f"lowercase h was treated as absolute: point {(x, y)}"
    print("test_solid_region_ignores_lowercase_commands: PASS")


if __name__ == "__main__":
    test_solid_region_handles_h_v_commands()
    test_solid_region_ignores_lowercase_commands()
    print("\nFootprint handler patch tests passed.")
