"""
Tests that FootprintConverter emits 3D model references using the
configured model_uri_base, not a hardcoded path.

Run with: python3 tests/test_footprint_converter_3d_uri.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.converters.footprint_converter import FootprintConverter


def test_default_uri_matches_legacy_path():
    fc = FootprintConverter()
    assert fc.model_uri_base == "${KIPRJMOD}/libs/lcsc/3dmodels"
    print("test_default_uri_matches_legacy_path: PASS")


def test_custom_uri_is_stored_without_trailing_slash():
    fc = FootprintConverter(model_uri_base="${KIPRJMOD}/assets/lcsc/3d/")
    assert fc.model_uri_base == "${KIPRJMOD}/assets/lcsc/3d"
    print("test_custom_uri_is_stored_without_trailing_slash: PASS")


def test_placeholder_footprint_uses_configured_uri():
    fc = FootprintConverter(model_uri_base="${KIPRJMOD}/assets/lcsc/3d")
    out = fc._create_placeholder_footprint(
        footprint_name="C123_SOT23",
        description="test",
        package="SOT23",
        lcsc_id="C123",
    )
    # The legacy hardcoded path must not appear
    assert "/libs/lcsc/3dmodels/" not in out
    # The configured base does appear, with the lcsc_id appended
    assert "${KIPRJMOD}/assets/lcsc/3d/C123.wrl" in out
    print("test_placeholder_footprint_uses_configured_uri: PASS")


if __name__ == "__main__":
    test_default_uri_matches_legacy_path()
    test_custom_uri_is_stored_without_trailing_slash()
    test_placeholder_footprint_uses_configured_uri()
    print("\nAll footprint_converter 3D URI tests passed.")
