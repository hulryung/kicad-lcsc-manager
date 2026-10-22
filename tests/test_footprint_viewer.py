"""
The footprint detail viewer's data layer (footprint_viewer.py): EasyEDA
units, pad snap points, OBJ parsing and the page payload. Offline.

Run with: python3 tests/test_footprint_viewer.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.footprint_viewer import (   # noqa: E402
    EASYEDA_UNIT_MM, extract_pads, footprint_origin, initial_view,
    mesh_payload, parse_obj_mesh, svg_viewbox, to_js_json, viewer_html,
    viewer_payload,
)

TEMPLATE = Path(__file__).parent.parent / "plugins" / "lcsc_manager" / \
    "plugin_resources" / "footprint_viewer.html"

# A PAD line as EasyEDA sends it (C2040, pad 57 = the exposed pad) and a
# round pad without a points list.
RECT_PAD = ("PAD~RECT~3984.252~3012.9925~12.2047~12.2047~1~~57~0~3978.1494 3006.8904 "
            "3990.3542 3006.8904 3990.3542 3019.0952 3978.1494 3019.0952~0~gge12204~0~~Y~0~0~0.1969~3")
ROUND_PAD = "PAD~ELLIPSE~3990~3000~4~4~11~~A1~1.2~~90~gge1~0~~Y~0~0~0~"

COMPONENT = {"easyeda_data": {"packageDetail": {"dataStr": {
    "head": {"x": 3984.252, "y": 3012.9925},
    "shape": [RECT_PAD, ROUND_PAD, "TRACK~1~3~~1 2 3 4~gge2~0", 42],
}}}}

OBJ = """v 0 0 0
v 2 0 0
v 2 2 0
v 0 2 0
v 1 1 1
newmtl 1
Ka 0.1 0.1 0.1
Kd 0.8 0.2 0.2
d 0.0
endmtl
newmtl 2
Kd 0.2 0.2 0.9
d 0.5
endmtl
usemtl 1
f 1// 2// 3// 4//
usemtl 2
f 1// 2// 5//
f -3// -2// -1//
"""


def test_units_and_origin():
    assert abs(EASYEDA_UNIT_MM - 0.254) < 1e-12          # 10 mil
    assert footprint_origin(COMPONENT) == {"x": 3984.252, "y": 3012.9925}
    assert footprint_origin(None) is None
    assert footprint_origin({"easyeda_data": {}}) is None
    print("test_units_and_origin: PASS")


def test_pads_give_snap_points():
    pads = extract_pads(COMPONENT)
    assert [p["number"] for p in pads] == ["57", "A1"], pads
    rect, rnd = pads
    assert rect["cx"] == 3984.252 and rect["w"] == 12.2047
    assert len(rect["points"]) == 4 and rect["points"][0] == [3978.1494, 3006.8904]
    # The exposed pad of an LQFN-56 is 3.1 mm square.
    assert abs(rect["w"] * EASYEDA_UNIT_MM - 3.1) < 0.001
    # No points list: four edge midpoints, rotated by the pad's rotation.
    assert len(rnd["points"]) == 4
    xs = sorted(round(p[0], 6) for p in rnd["points"])
    ys = sorted(round(p[1], 6) for p in rnd["points"])
    assert xs == [3988, 3990, 3990, 3992] and ys == [2998, 3000, 3000, 3002], (xs, ys)
    assert extract_pads(None) == []
    print("test_pads_give_snap_points: PASS")


def test_obj_parsing():
    mesh = parse_obj_mesh(OBJ)
    assert mesh is not None
    assert len(mesh["vertices"]) == 15
    # The quad is fanned into two triangles, then two more faces follow.
    assert mesh["faces"] == [0, 1, 2, 0, 2, 3, 0, 1, 4, 2, 3, 4], mesh["faces"]
    assert [(g["start"], g["count"]) for g in mesh["groups"]] == [(0, 2), (2, 2)]
    assert mesh["groups"][0]["color"] == [0.8, 0.2, 0.2] and mesh["groups"][0]["alpha"] == 1.0
    assert mesh["groups"][1]["alpha"] == 0.5                  # d is transparency
    assert mesh["bbox"] == [[0, 2], [0, 2], [0, 1]]
    assert parse_obj_mesh("") is None
    assert parse_obj_mesh("v 0 0 0\nv 1 0 0\nf 1// 2// 9//\n") is None   # index out of range
    print("test_obj_parsing: PASS")


def test_model_placement_matches_the_wrl():
    mesh = parse_obj_mesh(OBJ)
    info = {"translation_x": 0.5, "translation_y": -0.25, "translation_z": 0.1,
            "rotation": (0.0, 0.0, 90.0), "title": "T"}
    pl = mesh_payload(mesh, info)["placement"]
    # Centred on the XY bbox (centre 1,1), bottom to z=0, plus the offset.
    assert pl["tx"] == -1 + 0.5 and pl["ty"] == -1 - 0.25 and pl["tz"] == 0.1
    assert (pl["rx"], pl["ry"], pl["rz"]) == (0.0, 0.0, 270.0)     # KiCad negates
    assert mesh_payload(mesh, None)["placement"]["tx"] == -1
    print("test_model_placement_matches_the_wrl: PASS")


def test_initial_view_and_viewbox():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="13mm" viewBox="3958 2987.8 51.4 50.3"></svg>'
    assert svg_viewbox(svg) == {"x": 3958, "y": 2987.8, "w": 51.4, "h": 50.3}
    v = initial_view(svg, {"x": 3968, "y": 2997.8, "width": 31.4, "height": 30.3})
    assert abs(v["w"] - 31.4 * 1.3) < 1e-9 and abs(v["x"] - (3968 - 31.4 * 0.15)) < 1e-9
    assert initial_view(svg, None) == svg_viewbox(svg)          # falls back to the SVG
    assert initial_view("", {"width": 0}) == {"x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0}
    print("test_initial_view_and_viewbox: PASS")


def test_page_payload_and_template():
    template = TEMPLATE.read_text(encoding="utf-8")
    svg = '<svg viewBox="0 0 10 10"><text></text></svg><script>x</script>'
    payload = viewer_payload("C2040", "RP2040", svg, None, COMPONENT, None, "loading")
    assert payload["origin"] == {"x": 3984.252, "y": 3012.9925}
    assert len(payload["pads"]) == 2 and payload["model_status"] == "loading"
    html = viewer_html(template, payload)
    assert "/*__DATA__*/null" not in html
    # A "</script>" inside the SVG must not end the page's script element.
    assert html.count("</script>") == template.count("</script>")
    assert "<\\/script>" in to_js_json(svg)
    for hook in ("window.lcscSetModel", "window.lcscSetModelStatus", "window.lcscDebug"):
        assert hook in template, hook
    try:
        viewer_html("<html></html>", payload)
    except ValueError:
        pass
    else:
        raise AssertionError("a template without the data slot must be refused")
    print("test_page_payload_and_template: PASS")


if __name__ == "__main__":
    test_units_and_origin()
    test_pads_give_snap_points()
    test_obj_parsing()
    test_model_placement_matches_the_wrl()
    test_initial_view_and_viewbox()
    test_page_payload_and_template()
    print("\nAll footprint viewer tests passed.")
