"""Unit tests for issue #17: search results lost the LCSC part number when
JLCPCB returned a slug-less urlSuffix, which blanked the LCSC ID column and
made "Import Selected" refuse to start.

Run with: python3 tests/test_issue17_search_lcsc_id.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.api.lcsc_api import LCSCAPIClient

PLUGIN_DIR = Path(__file__).parent.parent / "plugins" / "lcsc_manager"


def _client_returning(components):
    """An API client whose JLCPCB search returns the given raw component list."""
    client = LCSCAPIClient()
    client._make_request = lambda **kwargs: {
        "code": 200,
        "data": {"componentPageInfo": {"list": components}},
    }
    return client


def _component(**overrides):
    comp = {
        "urlSuffix": "RaspberryPi-RP2040/C2040",
        "componentCode": "C2040",
        "componentModelEn": "RP2040",
        "componentSpecificationEn": "LQFN-56",
        "componentLibraryType": "expand",
        "stockCount": 100,
        "componentPrices": [{"productPrice": 0.8}],
    }
    comp.update(overrides)
    return comp


def test_slugged_url_suffix_still_works():
    """The long-standing "Brand-Model/CXXXX" shape must keep resolving."""
    client = _client_returning([_component()])
    result = client.search_jlcpcb("RP2040")[0]
    assert result["lcsc"]["number"] == "C2040", result
    assert result["uuid"] == "C2040", result
    print("test_slugged_url_suffix_still_works: PASS")


def test_bare_url_suffix_resolves():
    """The #17 case: urlSuffix is just the code, with no slug and no slash.
    The old `if "/" in url_suffix` guard turned this into an empty id."""
    client = _client_returning([_component(
        urlSuffix="C5142652",
        componentCode="C5142652",
        componentModelEn="CM8V-T1A-32.768KHZ-9PF-20PPM-TA-QC",
    )])
    result = client.search_jlcpcb("CM8V-T1A-32.768KHZ-9PF-20PPM")[0]
    assert result["lcsc"]["number"] == "C5142652", result
    assert result["uuid"] == "C5142652", result
    print("test_bare_url_suffix_resolves: PASS")


def test_component_code_wins_over_url_suffix():
    """componentCode carries the part number verbatim, so it is preferred."""
    client = _client_returning([_component(
        urlSuffix="Some-Brand/ignored", componentCode="C123456")])
    result = client.search_jlcpcb("whatever")[0]
    assert result["lcsc"]["number"] == "C123456", result
    print("test_component_code_wins_over_url_suffix: PASS")


def test_missing_component_code_falls_back_to_suffix():
    """If the field ever disappears, the suffix still yields the id."""
    for suffix, expected in (("Brand-Model/C777", "C777"), ("C888", "C888")):
        client = _client_returning([_component(urlSuffix=suffix,
                                               componentCode=None)])
        result = client.search_jlcpcb("q")[0]
        assert result["lcsc"]["number"] == expected, (suffix, result)
    print("test_missing_component_code_falls_back_to_suffix: PASS")


def test_no_id_anywhere_yields_empty_not_crash():
    """Neither field present: an empty id is fine, an exception is not —
    the dialog guards on the empty string."""
    client = _client_returning([_component(urlSuffix=None, componentCode=None)])
    result = client.search_jlcpcb("q")[0]
    assert result["lcsc"]["number"] == "", result
    print("test_no_id_anywhere_yields_empty_not_crash: PASS")


def test_preview_reports_a_missing_part_number():
    """A result with no part number must replace the 'Loading...' placeholder
    instead of leaving the preview spinning forever.
    (Full import needs wx, so inspect the source instead.)"""
    src = (PLUGIN_DIR / "dialog_search.py").read_text(encoding="utf-8")
    guard = src.split("if not lcsc_id:")[1][:900]
    assert "_display_previews" in guard, \
        "the empty-id branch returns without clearing 'Loading...'"
    assert "No LCSC part number" in guard, guard
    print("test_preview_reports_a_missing_part_number: PASS")


def test_extraction_does_not_require_a_slash():
    """Regression guard on the exact expression that caused #17."""
    src = (PLUGIN_DIR / "api" / "lcsc_api.py").read_text(encoding="utf-8")
    assert 'if "/" in url_suffix else ""' not in src, \
        "slash-only extraction is back; slug-less urlSuffix will blank the id"
    assert 'comp.get("componentCode")' in src
    print("test_extraction_does_not_require_a_slash: PASS")


if __name__ == "__main__":
    test_slugged_url_suffix_still_works()
    test_bare_url_suffix_resolves()
    test_component_code_wins_over_url_suffix()
    test_missing_component_code_falls_back_to_suffix()
    test_no_id_anywhere_yields_empty_not_crash()
    test_preview_reports_a_missing_part_number()
    test_extraction_does_not_require_a_slash()
    print("\nAll issue-17 tests passed.")
