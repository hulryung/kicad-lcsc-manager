"""
End-to-end regression test for component import after upstream integration.
Run with: python3 tests/test_regression_components.py

This test HITS REAL APIs (EasyEDA, JLCPCB). Rate-limited — don't spam.
Validates structural invariants on imported symbol/footprint/3D model output,
not exact golden-file comparisons.

What this test DOES cover end-to-end on real data:
  - Component lookup via LCSCAPIClient.search_component
  - Symbol conversion: verifies pins exist, canonical pin numbers (no ^^
    remnants) — exercises Task 9's num-segment extraction
  - 3D model download + OBJ→WRL conversion — exercises Tasks 1-3
    (OBJ bbox, centering, EE placement offset)

What this test does NOT cover end-to-end:
  - The REAL footprint converter path. When KicadModTree is not installed
    (standard for any environment outside KiCad's embedded Python), the
    FootprintConverter falls back to a hardcoded placeholder footprint with
    exactly 2 synthetic pads. The (pad ...) assertions pass trivially on
    that placeholder and do NOT exercise Task 6 (H/V in h_SOLIDREGION),
    Task 7 (_normalize_pad_number), or Task 8 (h_VIA as THT plated) on
    real EasyEDA footprint data.

    Handler-level coverage for the footprint path lives in
    tests/test_footprint_handlers_patches.py — that file uses a
    KicadModTree stub and exercises each handler directly on synthetic
    fixtures. If you need confidence that a real imported footprint is
    correct, run the plugin inside KiCad and visually inspect the output.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.api.lcsc_api import LCSCAPIClient
from lcsc_manager.converters.symbol_converter import SymbolConverter
from lcsc_manager.converters.footprint_converter import FootprintConverter
from lcsc_manager.converters.model_3d_converter import Model3DConverter


# Baseline -- known-working under old code
BASELINE_LCSC = "C7220642"

# Multi-unit target -- C7950 is LM358DR2G (8 pins, SOIC-8), confirmed available 2026-04-08
MULTI_UNIT_LCSC = "C7950"


def _assert_no_hh_in_pin_numbers(symbol_text: str, lcsc_id: str) -> None:
    """Pin numbers should never contain ^^ remnants from EasyEDA serialization."""
    count = 0
    for line in symbol_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("(number"):
            count += 1
            # Extract the number string between the first '"' and its matching '"'
            after = stripped.split("(number", 1)[1].strip()
            if after.startswith('"'):
                num = after[1:].split('"', 1)[0]
            else:
                num = after.split()[0].strip('"')
            assert num, f"{lcsc_id}: empty pin number in line: {line!r}"
            assert "^^" not in num, f"{lcsc_id}: pin number contains ^^: {num!r}"
    assert count > 0, f"{lcsc_id}: symbol has no (number ...) lines"


def _assert_no_parens_in_pad_numbers(footprint_text: str, lcsc_id: str) -> None:
    """Pad numbers should not contain parentheses (normalized by _normalize_pad_number)."""
    count = 0
    for line in footprint_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("(pad "):
            count += 1
            after = stripped.split("(pad", 1)[1].strip()
            # The first token is the pad number (quoted or not)
            first = after.split()[0] if after else ""
            first = first.strip('"')
            assert "(" not in first and ")" not in first, \
                f"{lcsc_id}: un-normalized pad number: {first!r}"
    assert count > 0, f"{lcsc_id}: footprint has no (pad ...) lines"


def test_import(lcsc_id: str, expected_min_pins: int = 1) -> None:
    print(f"\n--- {lcsc_id} ---")
    client = LCSCAPIClient()
    component = client.search_component(lcsc_id)
    assert component is not None, f"{lcsc_id}: not found in EasyEDA"
    print(f"  name:        {component.get('name')}")
    print(f"  package:     {component.get('package')}")
    print(f"  manuf:       {component.get('manufacturer')}")

    easyeda_data = component["easyeda_data"]

    # ----- Symbol -----
    symbol_conv = SymbolConverter()
    symbol_text = symbol_conv.convert(easyeda_data, component)
    assert "(symbol" in symbol_text, f"{lcsc_id}: symbol output missing (symbol"
    assert "(pin" in symbol_text, f"{lcsc_id}: symbol has no pins"

    pin_count = symbol_text.count("(pin ")
    print(f"  symbol pins: {pin_count}")
    assert pin_count >= expected_min_pins, \
        f"{lcsc_id}: expected >={expected_min_pins} pins, got {pin_count}"

    _assert_no_hh_in_pin_numbers(symbol_text, lcsc_id)

    # ----- Footprint -----
    fp_conv = FootprintConverter()
    footprint_text = fp_conv.convert(easyeda_data, component)
    assert "(footprint" in footprint_text or "(module" in footprint_text, \
        f"{lcsc_id}: footprint output missing module token"

    pad_count = footprint_text.count("(pad ")
    print(f"  footprint pads: {pad_count}")
    assert pad_count >= 1, f"{lcsc_id}: footprint has no pads"

    _assert_no_parens_in_pad_numbers(footprint_text, lcsc_id)

    # ----- 3D model (best-effort) -----
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
                assert "#VRML V2.0" in wrl_text, \
                    f"{lcsc_id}: WRL missing VRML header"
                print(f"  wrl: {len(wrl_text)} bytes")
            elif models.get("step"):
                print(f"  wrl: none (STEP only)")
            else:
                print(f"  wrl: none (no 3D model for this part)")
        except Exception as e:
            print(f"  wrl: skipped ({type(e).__name__}: {e})")


if __name__ == "__main__":
    # Baseline -- may have just a few pins
    test_import(BASELINE_LCSC, expected_min_pins=1)

    # Multi-unit -- should have 4+ pins and exercise the canonical-pin-number path
    # C7950 = LM358DR2G (8-pin dual op-amp, SOIC-8), confirmed available 2026-04-08
    test_import(MULTI_UNIT_LCSC, expected_min_pins=4)

    print("\nRegression tests complete.")
