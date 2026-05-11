"""
Validate that our FootprintConverter produces the same .kicad_mod text
as upstream easyeda2kicad.py for a real component.

These tests touch the network (LCSC API). Run with:
    python3 tests/test_footprint_matches_upstream.py

The comparison is deliberately *narrow*: we only allow specific known
deltas (footprint name, generator string, 3D-model URI). Anything else
that differs is a regression — either upstream changed, or our
post-processing drifted.
"""
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.api.lcsc_api import LCSCAPIClient
from lcsc_manager.converters.footprint_converter import FootprintConverter
from lcsc_manager.vendor.easyeda2kicad.easyeda.easyeda_importer import (
    EasyedaFootprintImporter,
)
from lcsc_manager.vendor.easyeda2kicad.kicad.export_kicad_footprint import (
    ExporterFootprintKicad,
)


# Each entry: (LCSC ID, expected pad count, package name fragment)
# Spans through-hole, SMD, multi-pad signal+mount mixed.
TEST_COMPONENTS = [
    ("C2939726", 5, "SW-TH_SS12D07VG4"),  # Domigome's reproducer (3 signal + 2 mount THT)
    ("C25804", 2, "0603"),                # generic 0603 chip resistor
]


def _ours(client: LCSCAPIClient, lcsc_id: str) -> tuple:
    """Return (text, raw_data, component_info) for our pipeline."""
    comp = client.search_component(lcsc_id)
    assert comp is not None, f"{lcsc_id}: search returned None"
    raw = comp["easyeda_data"]
    fc = FootprintConverter()
    text = fc.convert(raw, comp)
    return text, raw, comp


def _upstream(raw, lcsc_id, model_uri="${KIPRJMOD}/libs/lcsc/3dmodels") -> str:
    """Run upstream import + export directly, returning the .kicad_mod text."""
    ee = EasyedaFootprintImporter(easyeda_cp_cad_data=raw).output
    exp = ExporterFootprintKicad(footprint=ee)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, f"{ee.info.name}.kicad_mod")
        exp.export(footprint_full_path=out, model_3d_path=model_uri, model_3d_extension="wrl")
        return open(out, encoding="utf-8").read()


def _normalize_for_diff(text: str) -> str:
    """Strip the known intentional deltas so a true diff stays small.

    Allowed deltas (each documented inline):
      - The opening `(module …)` line names a different package_lib and
        package_name (we use our LCSC_ID_PACKAGE scheme).
      - The `(fp_text value …)` line repeats the same package_name.
    """
    text = re.sub(
        r"\(module\s+\S+\s+\(layer\s+F\.Cu\)\s+\(tedit\s+\S+\)",
        "(module <NORMALIZED> (layer F.Cu) (tedit <NORMALIZED>)",
        text,
    )
    text = re.sub(
        r"\(fp_text value\s+\S+\s+",
        "(fp_text value <NORMALIZED> ",
        text,
    )
    # Pad numbers: we normalize "VCC(3)" → "3"; tolerate either form when
    # the underlying number is the same.
    text = re.sub(
        r'\(pad\s+"?[^"\s]*\((\d+)\)"?\s+',
        r"(pad \1 ",
        text,
    )
    return text


def test_component(client: LCSCAPIClient, lcsc_id: str, expected_pads: int,
                   package_fragment: str) -> None:
    print(f"\n--- {lcsc_id} ({package_fragment}) ---")
    ours, raw, _comp = _ours(client, lcsc_id)
    theirs = _upstream(raw, lcsc_id)

    # Sanity: pad counts match expectations
    our_pads = ours.count("(pad ")
    their_pads = theirs.count("(pad ")
    assert our_pads == expected_pads, (
        f"{lcsc_id}: our pad count {our_pads} != expected {expected_pads}"
    )
    assert their_pads == expected_pads, (
        f"{lcsc_id}: upstream pad count {their_pads} != expected {expected_pads}"
    )

    # Normalized output must match upstream byte-for-byte
    ours_n = _normalize_for_diff(ours)
    theirs_n = _normalize_for_diff(theirs)
    if ours_n != theirs_n:
        import difflib
        diff = list(difflib.unified_diff(
            theirs_n.splitlines(keepends=True),
            ours_n.splitlines(keepends=True),
            fromfile="upstream",
            tofile="ours",
            n=2,
        ))
        sys.stdout.write("".join(diff[:60]))
        raise AssertionError(
            f"{lcsc_id}: output diverges from upstream (see diff above)"
        )

    # Spot-check the package_lib rewrite landed
    assert "(module kicad_lcsc_manager:" in ours, (
        f"{lcsc_id}: missing kicad_lcsc_manager: package_lib token"
    )
    print(f"  ✓ {our_pads} pads, output matches upstream after normalization")


if __name__ == "__main__":
    client = LCSCAPIClient()
    for lcsc_id, expected_pads, frag in TEST_COMPONENTS:
        test_component(client, lcsc_id, expected_pads, frag)
    print("\nAll upstream-comparison tests passed.")
