"""
Tests that FootprintConverter emits 3D model references using the
configured model_uri_base AND the on-disk filename convention.

The 3D model files are saved by Model3DConverter as ``<lcsc_id>.wrl`` /
``<lcsc_id>.step``. The footprint's ``(model ...)`` reference must therefore
point at ``<model_uri_base>/<lcsc_id>.wrl`` — not the EasyEDA model title,
which upstream easyeda2kicad uses by default. (regression: issue #5)

Run with: python3 tests/test_footprint_converter_3d_uri.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.converters.footprint_converter import FootprintConverter


# EasyEDA model title deliberately differs from the LCSC id so a reference
# built from the title (the upstream default) is visibly wrong.
MODEL_TITLE = "DP9-TH_ZHOUR_DP-9P"
LCSC_ID = "C3020658"
PACKAGE = "DP9-TH"


def _minimal_easyeda_data() -> dict:
    """Smallest EasyEDA API payload that yields a footprint with a 3D model.

    Only the fields EasyedaFootprintImporter actually reads are present:
    a ``c_para`` with package + 3DModel, a head origin, and a single
    SVGNODE carrying the 3D model attrs (title/uuid/c_origin/z/c_rotation).
    """
    svgnode = "SVGNODE~" + json.dumps(
        {
            "attrs": {
                "uuid": "0123456789abcdef0123456789abcdef",
                "title": MODEL_TITLE,
                "c_origin": "0,0",
                "z": "0",
                "c_rotation": "0,0,0",
            }
        }
    )
    return {
        "lcsc": {"number": LCSC_ID},
        "SMT": False,
        "description": "test part",
        "packageDetail": {
            "title": MODEL_TITLE,
            "dataStr": {
                "head": {
                    "x": 0,
                    "y": 0,
                    "c_para": {"package": PACKAGE, "3DModel": MODEL_TITLE},
                },
                "canvas": "",
                "shape": [svgnode],
            },
        },
    }


def test_default_uri_matches_legacy_path():
    fc = FootprintConverter()
    assert fc.model_uri_base == "${KIPRJMOD}/libs/lcsc/3dmodels"
    print("test_default_uri_matches_legacy_path: PASS")


def test_custom_uri_is_stored_without_trailing_slash():
    fc = FootprintConverter(model_uri_base="${KIPRJMOD}/assets/lcsc/3d/")
    assert fc.model_uri_base == "${KIPRJMOD}/assets/lcsc/3d"
    print("test_custom_uri_is_stored_without_trailing_slash: PASS")


def test_convert_references_3d_model_by_lcsc_id():
    """The (model ...) line must use <uri>/<lcsc_id>.wrl, matching the file
    Model3DConverter writes — never the EasyEDA model title."""
    fc = FootprintConverter(model_uri_base="${KIPRJMOD}/assets/lcsc/3d")
    out = fc.convert(
        _minimal_easyeda_data(),
        {"lcsc_id": LCSC_ID, "package": PACKAGE},
    )

    expected = f"${{KIPRJMOD}}/assets/lcsc/3d/{LCSC_ID}.wrl"
    assert expected in out, (
        f"expected 3D reference {expected!r} not found.\n"
        f"footprint model lines: "
        f"{[ln for ln in out.splitlines() if '(model' in ln or '.wrl' in ln]}"
    )
    # The title-based name must NOT leak into the reference.
    assert f"{MODEL_TITLE}.wrl" not in out, (
        f"3D reference still uses the EasyEDA title {MODEL_TITLE!r} "
        f"instead of the on-disk lcsc_id filename"
    )
    # The legacy hardcoded path must not appear either.
    assert "/libs/lcsc/3dmodels/" not in out
    print("test_convert_references_3d_model_by_lcsc_id: PASS")


if __name__ == "__main__":
    test_default_uri_matches_legacy_path()
    test_custom_uri_is_stored_without_trailing_slash()
    test_convert_references_3d_model_by_lcsc_id()
    print("\nAll footprint_converter 3D URI tests passed.")
