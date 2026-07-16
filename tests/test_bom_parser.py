"""Unit tests for BOM parsing and batch-import orchestration.

Run with: python3 tests/test_bom_parser.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.bom.bom_parser import parse_bom, BomParseError, BomEntry
from lcsc_manager.bom.bom_importer import BomImporter, BomImportOptions


def _write(tmp: Path, name: str, content: str, encoding: str = "utf-8") -> Path:
    p = tmp / name
    p.write_bytes(content.encode(encoding))
    return p


def test_jlcpcb_csv():
    """Standard JLCPCB BOM: dedup, designator/qty aggregation, skip no-LCSC."""
    csv = (
        "Comment,Designator,Footprint,LCSC Part #\n"
        "10uF,\"C1,C2\",0603,C15850\n"
        "0.1uF,\"C3,C4,C5\",0402,C1525\n"
        "RP2040,U1,QFN-56,C2040\n"
        ",TP1,TestPoint,\n"                 # no LCSC -> skipped
        "100R,R1,0603,C25804\n"
        "10uF,C6,0603,C15850\n"             # duplicate LCSC -> merged
    )
    with tempfile.TemporaryDirectory() as d:
        result = parse_bom(_write(Path(d), "bom.csv", csv))

    ids = [e.lcsc_id for e in result.entries]
    assert ids == ["C15850", "C1525", "C2040", "C25804"], ids
    assert result.lcsc_column == "LCSC Part #", result.lcsc_column
    assert result.skipped_rows == 1, result.skipped_rows

    c15850 = result.entries[0]
    assert c15850.designators == ["C1", "C2", "C6"], c15850.designators
    assert c15850.quantity == 3, c15850.quantity
    assert c15850.comment == "10uF", c15850.comment
    assert c15850.footprint == "0603", c15850.footprint
    print("test_jlcpcb_csv: PASS")


def test_semicolon_and_bom_and_variant_header():
    """Semicolon delimiter, UTF-8 BOM, and 'LCSC Part Number' header variant."""
    csv = (
        "﻿Value;Reference;Package;LCSC Part Number\n"
        "1k;R1;0603;C21190\n"
        "1k;R2;0603;C21190\n"
    )
    with tempfile.TemporaryDirectory() as d:
        result = parse_bom(_write(Path(d), "bom.csv", csv))

    assert len(result.entries) == 1, result.entries
    e = result.entries[0]
    assert e.lcsc_id == "C21190"
    assert e.designators == ["R1", "R2"], e.designators
    assert e.quantity == 2, e.quantity
    print("test_semicolon_and_bom_and_variant_header: PASS")


def test_value_based_detection_no_lcsc_header():
    """No 'LCSC' header -> auto-detect the column by value pattern."""
    csv = (
        "Comment,Designator,Footprint,Supplier Part\n"
        "10uF,C1,0603,C15850\n"
        "100R,R1,0603,C25804\n"
    )
    with tempfile.TemporaryDirectory() as d:
        result = parse_bom(_write(Path(d), "bom.csv", csv))

    ids = sorted(e.lcsc_id for e in result.entries)
    assert ids == ["C15850", "C25804"], ids
    assert result.warnings, "expected a warning about auto-detection"
    print("test_value_based_detection_no_lcsc_header: PASS")


def test_footprint_not_mistaken_for_lcsc():
    """A 'C0603'-style footprint must not be picked as the LCSC column."""
    csv = (
        "Comment,Designator,Footprint,LCSC\n"
        "10uF,C1,C0603,C15850\n"           # Footprint 'C0603' looks LCSC-ish
        "100R,R1,C0402,C25804\n"
    )
    with tempfile.TemporaryDirectory() as d:
        result = parse_bom(_write(Path(d), "bom.csv", csv))

    ids = sorted(e.lcsc_id for e in result.entries)
    assert ids == ["C15850", "C25804"], ids
    assert result.lcsc_column == "LCSC", result.lcsc_column
    print("test_footprint_not_mistaken_for_lcsc: PASS")


def test_no_lcsc_column_raises():
    csv = "Comment,Designator,Footprint\n10uF,C1,0603\n"
    with tempfile.TemporaryDirectory() as d:
        try:
            parse_bom(_write(Path(d), "bom.csv", csv))
        except BomParseError as e:
            assert "LCSC" in str(e)
            print("test_no_lcsc_column_raises: PASS")
            return
    raise AssertionError("expected BomParseError")


def test_metadata_rows_above_header():
    """Header not on row 0 (some exports prepend notes)."""
    csv = (
        "My Project BOM export\n"
        "Generated 2026-07-14\n"
        "\n"
        "Comment,Designator,Footprint,LCSC Part #\n"
        "10uF,C1,0603,C15850\n"
    )
    with tempfile.TemporaryDirectory() as d:
        result = parse_bom(_write(Path(d), "bom.csv", csv))
    assert [e.lcsc_id for e in result.entries] == ["C15850"]
    print("test_metadata_rows_above_header: PASS")


# --- importer orchestration -------------------------------------------------

class _FakeApi:
    def __init__(self, known):
        self.known = known           # set of lcsc ids that "exist"
        self.calls = []

    def search_component(self, lcsc_id):
        self.calls.append(lcsc_id)
        if lcsc_id in self.known:
            return {"lcsc_id": lcsc_id, "easyeda_data": {"stub": True}}
        return None


class _FakeLib:
    def __init__(self):
        self.imported = []

    def import_component(self, easyeda_data, component_info,
                         import_symbol, import_footprint, import_3d):
        self.imported.append(component_info["lcsc_id"])
        return {
            "symbol": "Sym" if import_symbol else None,
            "footprint": "Fp" if import_footprint else None,
            "model_3d": {"wrl": "x"} if import_3d else None,
            "success": True,
            "errors": [],
        }


def test_importer_happy_and_missing():
    entries = [BomEntry("C1"), BomEntry("C2"), BomEntry("C3")]
    api = _FakeApi(known={"C1", "C3"})
    lib = _FakeLib()
    importer = BomImporter(api, lib)

    summary = importer.import_entries(entries, BomImportOptions())

    assert [r.lcsc_id for r in summary.imported] == ["C1", "C3"], summary.imported
    assert [r.lcsc_id for r in summary.failed] == ["C2"], summary.failed
    # Must NOT claim the part is missing from LCSC — only EasyEDA CAD is absent
    assert "EasyEDA" in summary.failed[0].error
    assert "may still exist" in summary.failed[0].error, summary.failed[0].error
    assert lib.imported == ["C1", "C3"], lib.imported
    print("test_importer_happy_and_missing: PASS")


def test_importer_cancel():
    entries = [BomEntry(f"C{i}") for i in range(5)]
    api = _FakeApi(known={f"C{i}" for i in range(5)})
    importer = BomImporter(api, _FakeLib())

    # Cancel after the first part is processed.
    state = {"n": 0}

    def should_cancel():
        return state["n"] >= 1

    def progress_cb(i, total, lcsc, phase):
        if phase == "importing":
            state["n"] += 1

    summary = importer.import_entries(entries, BomImportOptions(),
                                      progress_cb=progress_cb,
                                      should_cancel=should_cancel)
    assert summary.cancelled is True
    assert len(summary.results) == 1, summary.results
    print("test_importer_cancel: PASS")


def test_title_row_with_lcsc_is_not_header():
    """A title row containing 'LCSC' must not hijack header detection."""
    csv = (
        "LCSC BOM Export - MyProject\n"
        "Comment,Designator,Footprint,LCSC Part #\n"
        "10uF,C1,0603,C15850\n"
        "100R,R1,0603,C25804\n"
    )
    with tempfile.TemporaryDirectory() as d:
        result = parse_bom(_write(Path(d), "bom.csv", csv))
    ids = [e.lcsc_id for e in result.entries]
    assert ids == ["C15850", "C25804"], ids
    assert result.entries[0].designators == ["C1"], result.entries[0]
    print("test_title_row_with_lcsc_is_not_header: PASS")


def test_mpn_in_lcsc_column_not_extracted():
    """'STM32C011F4' / '1C2040X' must be skipped, not become C011 / C2040."""
    csv = (
        "Comment,Designator,Footprint,LCSC\n"
        "mcu,U1,QFN,STM32C011F4\n"
        "odd,U2,QFN,1C2040X\n"
        "100R,R1,0603,C25804\n"
        "note,U3,QFN,C2040 (RP2040)\n"     # standalone token still extracts
    )
    with tempfile.TemporaryDirectory() as d:
        result = parse_bom(_write(Path(d), "bom.csv", csv))
    ids = [e.lcsc_id for e in result.entries]
    assert ids == ["C25804", "C2040"], ids
    assert result.skipped_rows == 2, result.skipped_rows
    print("test_mpn_in_lcsc_column_not_extracted: PASS")


def test_headerless_id_list_keeps_all_parts():
    """A bare list of part numbers must not lose its first row to header
    detection."""
    csv = "C2040\nC25804\nC1525\n"
    with tempfile.TemporaryDirectory() as d:
        result = parse_bom(_write(Path(d), "bom.csv", csv))
    ids = [e.lcsc_id for e in result.entries]
    assert ids == ["C2040", "C25804", "C1525"], ids
    print("test_headerless_id_list_keeps_all_parts: PASS")


def test_importer_rate_limit_aborts_batch():
    """A rate-limited fetch must stop the batch and record the tail as
    not-attempted instead of hammering every remaining part."""
    from lcsc_manager.api.lcsc_api import LCSCRateLimitError

    class _ThrottlingApi(_FakeApi):
        def search_component(self, lcsc_id):
            if lcsc_id == "C2":
                self.calls.append(lcsc_id)
                raise LCSCRateLimitError("throttled")
            return super().search_component(lcsc_id)

    entries = [BomEntry("C1"), BomEntry("C2"), BomEntry("C3"), BomEntry("C4")]
    api = _ThrottlingApi(known={"C1", "C3", "C4"})
    importer = BomImporter(api, _FakeLib())

    summary = importer.import_entries(entries, BomImportOptions())

    assert summary.rate_limited is True
    assert [r.lcsc_id for r in summary.imported] == ["C1"], summary.imported
    assert [r.lcsc_id for r in summary.failed] == ["C2"], summary.failed
    assert summary.not_attempted == ["C3", "C4"], summary.not_attempted
    assert api.calls == ["C1", "C2"], api.calls  # C3/C4 never hammered
    print("test_importer_rate_limit_aborts_batch: PASS")


if __name__ == "__main__":
    test_jlcpcb_csv()
    test_semicolon_and_bom_and_variant_header()
    test_value_based_detection_no_lcsc_header()
    test_footprint_not_mistaken_for_lcsc()
    test_no_lcsc_column_raises()
    test_metadata_rows_above_header()
    test_title_row_with_lcsc_is_not_header()
    test_mpn_in_lcsc_column_not_extracted()
    test_headerless_id_list_keeps_all_parts()
    test_importer_happy_and_missing()
    test_importer_cancel()
    test_importer_rate_limit_aborts_batch()
    print("\nAll BOM tests passed.")
