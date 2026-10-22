"""
Data for the footprint detail viewer (plugin_resources/footprint_viewer.html).

The viewer shows EasyEDA's own footprint drawing at any zoom, measures
point-to-point distances on it, and renders the part's 3D model on top of
the footprint. This module turns what the plugin already has (the preview
SVG, the EasyEDA footprint data, the OBJ model) into the JSON the page
reads. It is free of wx so the tests can exercise it anywhere.

Units. EasyEDA's canvas unit is 10 mil, so the preview SVG's viewBox and
the PAD coordinates are in units of 0.254 mm; the OBJ model is in mm. The
footprint's origin on the canvas is `dataStr.head.x/y`. Screen Y points
down in the SVG and up in the model, like KiCad's board space, so the page
flips Y when it places the model over the drawing.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

EASYEDA_UNIT_MM = 0.254          # one canvas unit (10 mil) in mm

# How the page expects the payload (`DATA`):
#   lcsc_id, title: strings for the heading
#   unit_mm: EASYEDA_UNIT_MM
#   svg: the footprint SVG (its own viewBox is the drawing's extent)
#   view: {x, y, w, h} viewBox to open with (canvas units)
#   origin: {x, y} footprint origin on the canvas, or null
#   pads: [{number, cx, cy, w, h, points: [[x, y], ...]}] (canvas units)
#   model: null, or the dict from mesh_payload()
#   model_status: "none" | "loading" | "ready" | "failed"


def svg_viewbox(svg: str) -> Optional[Dict[str, float]]:
    """The viewBox of an SVG document as {x, y, w, h}, or None."""
    m = re.search(r'viewBox="\s*([-\d.eE+]+)[\s,]+([-\d.eE+]+)[\s,]+([-\d.eE+]+)[\s,]+([-\d.eE+]+)\s*"', svg)
    if not m:
        return None
    try:
        x, y, w, h = (float(v) for v in m.groups())
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    return {"x": x, "y": y, "w": w, "h": h}


def initial_view(svg: str, bbox: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """The viewBox the page opens with: EasyEDA's bbox with 15% padding,
    else the SVG's own viewBox, else a default square."""
    if bbox:
        try:
            x, y = float(bbox.get("x", 0)), float(bbox.get("y", 0))
            w, h = float(bbox.get("width", 0)), float(bbox.get("height", 0))
            if w > 0 and h > 0:
                px, py = w * 0.15, h * 0.15
                return {"x": x - px, "y": y - py, "w": w + 2 * px, "h": h + 2 * py}
        except (TypeError, ValueError):
            pass
    vb = svg_viewbox(svg)
    if vb:
        return vb
    return {"x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0}


def footprint_data_str(component_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """`easyeda_data.packageDetail.dataStr` of a search_component() result,
    or {} when any level is missing."""
    try:
        return ((component_data or {}).get("easyeda_data") or {}) \
            .get("packageDetail", {}).get("dataStr", {}) or {}
    except AttributeError:
        return {}


def footprint_origin(component_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """The footprint's origin on the EasyEDA canvas, {x, y}, or None."""
    head = footprint_data_str(component_data).get("head") or {}
    try:
        return {"x": float(head["x"]), "y": float(head["y"])}
    except (KeyError, TypeError, ValueError):
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def extract_pads(component_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The footprint's pads, for snapping the ruler to and for hover info.

    EasyEDA PAD lines: PAD~shape~cx~cy~w~h~layer~net~number~hole_r~points~rotation~id~…
    (canvas units). `points` lists the polygon corners of RECT/POLYGON pads
    ("x y x y …"); for round and oval pads the four edge midpoints are
    derived from the size and rotation instead."""
    import math
    pads = []
    for line in footprint_data_str(component_data).get("shape") or []:
        if not isinstance(line, str) or not line.startswith("PAD~"):
            continue
        f = line.split("~")
        if len(f) < 9:
            continue
        cx, cy = _safe_float(f[2]), _safe_float(f[3])
        w, h = _safe_float(f[4]), _safe_float(f[5])
        number = f[8]
        points: List[List[float]] = []
        raw = f[10].split() if len(f) > 10 else []
        if len(raw) >= 4 and len(raw) % 2 == 0:
            try:
                points = [[float(raw[i]), float(raw[i + 1])] for i in range(0, len(raw), 2)]
            except ValueError:
                points = []
        if not points and w > 0 and h > 0:
            rot = math.radians(_safe_float(f[11]) if len(f) > 11 else 0.0)
            c, s = math.cos(rot), math.sin(rot)
            for dx, dy in ((w / 2, 0), (-w / 2, 0), (0, h / 2), (0, -h / 2)):
                points.append([cx + dx * c - dy * s, cy + dx * s + dy * c])
        pads.append({
            "number": number, "cx": cx, "cy": cy, "w": w, "h": h,
            "shape": f[1], "points": points,
        })
    return pads


# ---------------------------------------------------------------- OBJ model

def parse_obj_mesh(obj_text: str) -> Optional[Dict[str, Any]]:
    """An EasyEDA OBJ (mm, materials inline) as an indexed triangle mesh:

        {"vertices": [x, y, z, …], "faces": [i, j, k, …],
         "groups": [{"color": [r, g, b], "alpha": a, "start": n, "count": m}],
         "bbox": [[xmin, xmax], [ymin, ymax], [zmin, zmax]]}

    `start`/`count` index faces (triangles). Polygons with more than three
    corners are fanned. Returns None when there are no faces."""
    if not obj_text:
        return None
    vertices: List[float] = []
    faces: List[int] = []
    groups: List[Dict[str, Any]] = []
    materials: Dict[str, Dict[str, Any]] = {}
    group: Optional[Dict[str, Any]] = None
    in_mtl: Optional[str] = None

    def material(mat_id: str) -> Dict[str, Any]:
        m = materials.get(mat_id) or {}
        color = m.get("color") or [0.6, 0.6, 0.6]
        return {"color": color, "alpha": m.get("alpha", 1.0)}

    for line in obj_text.splitlines():
        parts = line.split()
        if not parts:
            continue
        tag = parts[0]
        if tag == "v" and len(parts) >= 4:
            try:
                vertices.extend((float(parts[1]), float(parts[2]), float(parts[3])))
            except ValueError:
                continue
        elif tag == "f":
            idx = []
            for p in parts[1:]:
                try:
                    i = int(p.split("/")[0])
                except ValueError:
                    idx = []
                    break
                idx.append(i - 1 if i > 0 else len(vertices) // 3 + i)
            if len(idx) < 3:
                continue
            if group is None:
                group = {"start": len(faces) // 3, "count": 0, **material("")}
                groups.append(group)
            for k in range(1, len(idx) - 1):
                faces.extend((idx[0], idx[k], idx[k + 1]))
                group["count"] += 1
        elif tag == "usemtl" and len(parts) > 1:
            mat = material(parts[1])
            if group is None or group["count"] or group["color"] != mat["color"]:
                group = {"start": len(faces) // 3, "count": 0, **mat}
                groups.append(group)
        elif tag == "newmtl" and len(parts) > 1:
            in_mtl = parts[1]
            materials[in_mtl] = {}
        elif in_mtl is not None:
            if tag == "Kd" and len(parts) >= 4:
                try:
                    materials[in_mtl]["color"] = [
                        min(1.0, max(0.0, float(v))) for v in parts[1:4]]
                except ValueError:
                    pass
            elif tag == "d" and len(parts) >= 2:
                # EasyEDA writes d as transparency (0 = opaque), as VRML does.
                materials[in_mtl]["alpha"] = 1.0 - min(1.0, max(0.0, _safe_float(parts[1])))
            elif tag == "endmtl":
                in_mtl = None
    if not faces:
        return None
    n = len(vertices) // 3
    if any(i < 0 or i >= n for i in faces):
        return None
    xs, ys, zs = vertices[0::3], vertices[1::3], vertices[2::3]
    return {
        "vertices": [round(v, 4) for v in vertices],
        "faces": faces,
        "groups": [g for g in groups if g["count"]],
        "bbox": [[min(xs), max(xs)], [min(ys), max(ys)], [min(zs), max(zs)]],
    }


def mesh_payload(mesh: Dict[str, Any], model_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The mesh plus where it sits over the footprint, the way the WRL the
    plugin writes is placed: centred on its XY bounding box, bottom at z=0,
    then moved by EasyEDA's placement offset (mm). Rotation is EasyEDA's
    c_rotation, which the footprint exporter hands to KiCad negated."""
    info = model_info or {}
    (x0, x1), (y0, y1), (z0, _) = mesh["bbox"]
    rot = info.get("rotation") or (0.0, 0.0, 0.0)
    return {
        "vertices": mesh["vertices"],
        "faces": mesh["faces"],
        "groups": mesh["groups"],
        "bbox": mesh["bbox"],
        "placement": {
            "tx": -(x0 + x1) / 2.0 + float(info.get("translation_x", 0.0)),
            "ty": -(y0 + y1) / 2.0 + float(info.get("translation_y", 0.0)),
            "tz": -z0 + float(info.get("translation_z", 0.0)),
            "rx": (360 - float(rot[0])) % 360,
            "ry": (360 - float(rot[1])) % 360,
            "rz": (360 - float(rot[2])) % 360,
        },
        "title": info.get("title", ""),
    }


# ---------------------------------------------------------------- the page

def viewer_payload(lcsc_id: str, title: str, svg: str,
                   bbox: Optional[Dict[str, Any]] = None,
                   component_data: Optional[Dict[str, Any]] = None,
                   model: Optional[Dict[str, Any]] = None,
                   model_status: str = "none") -> Dict[str, Any]:
    """Everything the page needs, as one JSON-able dict."""
    return {
        "lcsc_id": lcsc_id,
        "title": title or "",
        "unit_mm": EASYEDA_UNIT_MM,
        "svg": svg or "",
        "view": initial_view(svg or "", bbox),
        "origin": footprint_origin(component_data),
        "pads": extract_pads(component_data),
        "model": model,
        "model_status": model_status,
    }


def to_js_json(value: Any) -> str:
    """JSON that is safe inside a <script> element and a JS string."""
    return json.dumps(value, separators=(",", ":")).replace("</", "<\\/")


def viewer_html(template: str, payload: Dict[str, Any]) -> str:
    """The page with `payload` in place of the template's data slot."""
    slot = "/*__DATA__*/null"
    if slot not in template:
        raise ValueError("footprint_viewer.html has no data slot")
    return template.replace(slot, to_js_json(payload), 1)
