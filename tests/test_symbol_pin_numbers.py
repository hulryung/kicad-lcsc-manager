"""
Unit tests for multi-unit pin number extraction.
Run with: python3 tests/test_symbol_pin_numbers.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.converters.jlc2kicad.symbol_handlers import _extract_pin_number


def test_single_unit_pin():
    """Simple single-unit pin where spice and canonical numbers agree."""
    # Segment layout: settings^^dot^^path^^name^^num^^dot_bis^^clock
    # settings = visibility~type~spice_pin_number~pos_x~pos_y~rotation~id~is_locked
    # num      = show~x~y~rotation~number~text_anchor~font~font_size
    line = (
        "P~1~0~3~-10~0~0~gge1~0"       # settings (9 fields incl leading P)
        "^^30~-10"                      # dot
        "^^M 5 -10 L 30 -10~#000"       # path
        "^^1~32~-10~0~A~start~~7"       # name
        "^^1~25~-10~0~3~end~~7"         # num — number at index 4 = "3"
        "^^0~40~-10"                    # dot_bis
        "^^0~"                          # clock
    )
    assert _extract_pin_number(line) == "3"
    print("test_single_unit_pin: PASS")


def test_multi_unit_pin_mismatch():
    """Multi-unit: spice_pin_number=1 but canonical KiCad number=14."""
    line = (
        "P~1~0~1~-10~0~0~gge2~0"
        "^^30~-10"
        "^^M 5 -10 L 30 -10~#000"
        "^^1~32~-10~0~B~start~~7"
        "^^1~25~-10~0~14~end~~7"        # canonical number = 14
        "^^0~40~-10"
        "^^0~"
    )
    result = _extract_pin_number(line)
    assert result == "14", f"expected '14' (multi-unit canonical), got {result!r}"
    print("test_multi_unit_pin_mismatch: PASS")


def test_fallback_to_spice():
    """Malformed line: num segment missing — fall back to spice_pin_number."""
    line = "P~1~0~7~-10~0~0~gge3~0^^30~-10^^M~#000"
    assert _extract_pin_number(line) == "7"
    print("test_fallback_to_spice: PASS")


def test_whitespace_num_falls_back_to_spice():
    """num-segment number field is whitespace — should fall back to spice."""
    line = (
        "P~1~0~9~-10~0~0~gge9~0"        # spice_pin_number = 9
        "^^30~-10"                       # dot
        "^^M 5 -10 L 30 -10~#000"        # path
        "^^1~32~-10~0~A~start~~7"        # name
        "^^1~25~-10~0~   ~end~~7"        # num — number field is whitespace only
        "^^0~40~-10"                     # dot_bis
        "^^0~"                           # clock
    )
    result = _extract_pin_number(line)
    assert result == "9", f"expected '9' (fallback to spice), got {result!r}"
    print("test_whitespace_num_falls_back_to_spice: PASS")


if __name__ == "__main__":
    test_single_unit_pin()
    test_multi_unit_pin_mismatch()
    test_fallback_to_spice()
    test_whitespace_num_falls_back_to_spice()
    print("\nSymbol pin number tests passed.")
