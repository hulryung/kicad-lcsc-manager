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
    km.Pad.LAYERS_THT = ["*.Cu", "*.Paste", "*.Mask"]
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

# Defensive: if an earlier test file in the same process tried to import
# footprint_handlers without KicadModTree available, Python cached the
# failed import as sys.modules[...] = None. Clear those sentinels so our
# stub-backed re-import can succeed. Harmless when the cache is clean.
for _cached in (
    "lcsc_manager.converters.jlc2kicad.footprint_handlers",
    "lcsc_manager.converters.jlc2kicad",
    "lcsc_manager.converters.footprint_converter",
):
    if sys.modules.get(_cached) is None and _cached in sys.modules:
        del sys.modules[_cached]

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


def test_pad_number_empty_parens():
    """Empty parens '()' must become empty string, not literal '()'."""
    assert _normalize_pad_number("()") == ""
    assert _normalize_pad_number("  ()  ") == ""
    print("test_pad_number_empty_parens: PASS")


def test_pad_number_nested_parens():
    """Nested parens — outermost span wins (documented behaviour)."""
    assert _normalize_pad_number("A(B(1))") == "B(1)"
    print("test_pad_number_nested_parens: PASS")


def test_via_becomes_thru_hole_pad():
    """h_VIA should emit a plated THT Pad (not NPTH) and update the bbox."""
    # Position (20, 30) mils, diameter=40, drill_radius=15.
    data = ["20", "30", "40", "gnd", "15", "via_id"]
    mod = FakeKicadMod()
    info = FakeFootprintInfo()

    fh.h_VIA(data, mod, info)

    assert len(mod.appended) == 1, f"expected 1 pad, got {len(mod.appended)}"
    pad = mod.appended[0]
    kw = pad._kw
    assert kw.get("type") == fh.Pad.TYPE_THT, \
        f"expected TYPE_THT (plated), got {kw.get('type')}"
    assert kw.get("shape") == fh.Pad.SHAPE_CIRCLE, f"shape wrong: {kw.get('shape')}"
    assert kw.get("layers") == fh.Pad.LAYERS_THT, \
        f"expected LAYERS_THT, got {kw.get('layers')}"
    size = kw.get("size")
    assert size is not None and size > 0, f"size wrong: {size}"
    assert abs(size - 40 / 3.937) < 0.01, f"size expected ~40/3.937, got {size}"
    drill = kw.get("drill")
    assert drill is not None and drill > 0, f"drill wrong: {drill}"
    assert abs(drill - 30 / 3.937) < 0.01, f"drill expected ~30/3.937, got {drill}"

    # Bounding box should have expanded to include via center at (20,30) mils = ~(5.08, 7.62) mm
    expected_x = 20 / 3.937
    expected_y = 30 / 3.937
    assert abs(info.max_X - expected_x) < 0.01, f"max_X not updated: {info.max_X}"
    assert abs(info.max_Y - expected_y) < 0.01, f"max_Y not updated: {info.max_Y}"
    print("test_via_becomes_thru_hole_pad: PASS")


def test_layer_correspondance_top_assembly():
    """Layer 13 = TopAssembly → F.Fab (was wrongly B.Fab)."""
    assert fh.layer_correspondance["13"] == "F.Fab", \
        f"layer 13 wrong: {fh.layer_correspondance['13']}"
    print("test_layer_correspondance_top_assembly: PASS")


def test_layer_correspondance_bottom_assembly():
    """Layer 14 = BottomAssembly → B.Fab (was wrongly F.CrtYd)."""
    assert fh.layer_correspondance["14"] == "B.Fab"
    print("test_layer_correspondance_bottom_assembly: PASS")


def test_layer_correspondance_document():
    """Layer 12 = Document → Cmts.User (was wrongly F.Fab)."""
    assert fh.layer_correspondance["12"] == "Cmts.User"
    print("test_layer_correspondance_document: PASS")


def test_layer_correspondance_mechanical():
    """Layer 15 = Mechanical → Dwgs.User (was wrongly B.CrtYd)."""
    assert fh.layer_correspondance["15"] == "Dwgs.User"
    print("test_layer_correspondance_mechanical: PASS")


def test_layer_correspondance_component_shape():
    """Layer 99 = Component Shape (LIBBODY) → F.CrtYd (was User.1)."""
    assert fh.layer_correspondance["99"] == "F.CrtYd"
    print("test_layer_correspondance_component_shape: PASS")


def test_layer_correspondance_lead_shape():
    """Layer 100 = Lead Shape → F.Fab (was User.2)."""
    assert fh.layer_correspondance["100"] == "F.Fab"
    print("test_layer_correspondance_lead_shape: PASS")


def test_layer_correspondance_polarity():
    """Layer 101 = Component Polarity → F.SilkS (was User.3)."""
    assert fh.layer_correspondance["101"] == "F.SilkS"
    print("test_layer_correspondance_polarity: PASS")


def test_layer_correspondance_no_user_layers():
    """After the upstream alignment no EasyEDA layer should map to User.N."""
    user_mappings = [
        (k, v) for k, v in fh.layer_correspondance.items()
        if v.startswith("User.")
    ]
    assert not user_mappings, f"unexpected User.* mappings: {user_mappings}"
    print("test_layer_correspondance_no_user_layers: PASS")


def test_solid_region_layer_99_still_imported():
    """SOLIDREGION on layer 99 (component shape) is allowed AND goes to F.CrtYd."""
    data = ["99", "id_99", "M 0 0 L 100 0 L 100 50 L 0 50 Z", "solid"]
    mod = FakeKicadMod()
    info = FakeFootprintInfo()
    fh.h_SOLIDREGION(data, mod, info)
    assert len(mod.appended) == 1, \
        f"expected 1 polygon on layer 99, got {len(mod.appended)}"
    poly = mod.appended[0]
    layer = poly._kw.get("layer") if hasattr(poly, "_kw") else None
    assert layer == "F.CrtYd", f"layer 99 should map to F.CrtYd, got {layer!r}"
    print("test_solid_region_layer_99_still_imported: PASS")


def test_solid_region_layer_100_skipped():
    """SOLIDREGION on layer 100 (decorative lead shape) must be dropped."""
    data = ["100", "id_100", "M 0 0 L 100 0 L 100 50 L 0 50 Z", "solid"]
    mod = FakeKicadMod()
    info = FakeFootprintInfo()
    fh.h_SOLIDREGION(data, mod, info)
    assert len(mod.appended) == 0, \
        f"layer 100 should be skipped, got {len(mod.appended)} polygons"
    print("test_solid_region_layer_100_skipped: PASS")


def test_solid_region_layer_101_skipped():
    """SOLIDREGION on layer 101 (decorative polarity marker) must be dropped."""
    data = ["101", "id_101", "M 0 0 L 100 0 L 100 50 L 0 50 Z", "solid"]
    mod = FakeKicadMod()
    info = FakeFootprintInfo()
    fh.h_SOLIDREGION(data, mod, info)
    assert len(mod.appended) == 0, \
        f"layer 101 should be skipped, got {len(mod.appended)} polygons"
    print("test_solid_region_layer_101_skipped: PASS")


def test_solid_region_npth_still_edge_cuts():
    """npth region_type still routes to Edge.Cuts regardless of layer."""
    # npth on a non-allowed layer (5) should STILL be imported to Edge.Cuts
    data = ["5", "id_npth", "M 0 0 L 100 0 L 100 50 L 0 50 Z", "npth"]
    mod = FakeKicadMod()
    info = FakeFootprintInfo()
    fh.h_SOLIDREGION(data, mod, info)
    assert len(mod.appended) == 1, \
        f"npth SOLIDREGION should produce 1 polygon, got {len(mod.appended)}"
    # Check the layer on the emitted Polygon
    poly = mod.appended[0]
    # Our FakeKicadMod stub captures kwargs in _kw
    layer = poly._kw.get("layer") if hasattr(poly, "_kw") else None
    assert layer == "Edge.Cuts", f"npth layer wrong: {layer}"
    print("test_solid_region_npth_still_edge_cuts: PASS")


if __name__ == "__main__":
    test_solid_region_handles_h_v_commands()
    test_solid_region_ignores_lowercase_commands()
    test_pad_number_bare_number()
    test_pad_number_parenthesized()
    test_pad_number_empty()
    test_pad_number_empty_parens()
    test_pad_number_nested_parens()
    test_via_becomes_thru_hole_pad()
    test_layer_correspondance_top_assembly()
    test_layer_correspondance_bottom_assembly()
    test_layer_correspondance_document()
    test_layer_correspondance_mechanical()
    test_layer_correspondance_component_shape()
    test_layer_correspondance_lead_shape()
    test_layer_correspondance_polarity()
    test_layer_correspondance_no_user_layers()
    test_solid_region_layer_99_still_imported()
    test_solid_region_layer_100_skipped()
    test_solid_region_layer_101_skipped()
    test_solid_region_npth_still_edge_cuts()
    print("\nFootprint handler patch tests passed.")
