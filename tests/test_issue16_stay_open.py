"""Unit tests for issue #16: the import dialogs stay open after adding a part
so several components can be searched for and imported in one visit.

Run with: python3 tests/test_issue16_stay_open.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.utils.session import ImportSession, REOPEN_HINT, MAX_LISTED

PLUGIN_DIR = Path(__file__).parent.parent / "plugins" / "lcsc_manager"


def test_status_text_empty_before_any_import():
    session = ImportSession()
    assert session.count == 0
    assert session.status_text() == ""
    print("test_status_text_empty_before_any_import: PASS")


def test_records_parts_in_order():
    session = ImportSession()
    session.record("C2040")
    session.record("C14663")
    assert session.count == 2
    text = session.status_text()
    assert text == "Imported this session (2): C2040, C14663", text
    print("test_records_parts_in_order: PASS")


def test_reimport_does_not_inflate_tally():
    """Re-importing a part (e.g. with different options) must not list it
    twice or bump the count."""
    session = ImportSession()
    session.record("C2040")
    session.record("C2040")
    assert session.count == 1, session.imported_ids
    assert session.status_text().endswith("(1): C2040"), session.status_text()
    print("test_reimport_does_not_inflate_tally: PASS")


def test_long_session_elides_oldest():
    """A long session must not stretch the label past the dialog width."""
    session = ImportSession()
    for i in range(MAX_LISTED + 3):
        session.record("C{n}".format(n=i))
    text = session.status_text()
    assert "…" in text, text
    assert text.startswith(
        "Imported this session ({n}): …".format(n=MAX_LISTED + 3)), text
    # Newest kept, oldest elided.
    assert "C{n}".format(n=MAX_LISTED + 2) in text, text
    assert "C0," not in text, text
    print("test_long_session_elides_oldest: PASS")


def test_reopen_hint_shown_once_per_session():
    """The 'reopen the schematic editor' note is useful once; repeating it on
    every import of a multi-part session is noise."""
    session = ImportSession()
    assert session.record("C2040", imported_symbol=True) is True
    assert session.record("C14663", imported_symbol=True) is False
    assert session.record("C25804", imported_symbol=True) is False
    print("test_reopen_hint_shown_once_per_session: PASS")


def test_reopen_hint_requires_a_symbol():
    """Footprint/3D-only imports don't need a schematic-editor reload, and
    must not consume the one-shot hint either."""
    session = ImportSession()
    assert session.record("C2040", imported_symbol=False) is False
    assert session.count == 1
    # A later symbol import still gets the hint.
    assert session.record("C14663", imported_symbol=True) is True
    print("test_reopen_hint_requires_a_symbol: PASS")


def test_hint_text_mentions_the_schematic_editor():
    assert "schematic editor" in REOPEN_HINT
    print("test_hint_text_mentions_the_schematic_editor: PASS")


def _dialog_source(name):
    return (PLUGIN_DIR / name).read_text(encoding="utf-8")


def test_dialogs_do_not_end_themselves_after_an_import():
    """Regression guard for #16: a successful import must never close the
    dialog. Both dialogs may only end via the conditional _close_dialog().
    (Full import needs wx, so inspect the source instead.)"""
    for name in ("dialog.py", "dialog_search.py"):
        src = _dialog_source(name)
        assert "EndModal(wx.ID_OK)" not in src, \
            "{n} still closes unconditionally after import".format(n=name)
        assert "def _close_dialog" in src, name
        assert ("EndModal(wx.ID_OK if self.session.count else wx.ID_CANCEL)"
                in src), name
    print("test_dialogs_do_not_end_themselves_after_an_import: PASS")


def test_dialogs_track_the_session():
    """Both dialogs must feed the shared session tracker so their status line
    and the one-shot reopen hint stay in sync."""
    for name in ("dialog.py", "dialog_search.py"):
        src = _dialog_source(name)
        assert "ImportSession" in src, name
        assert "self.session.record(" in src, name
        assert "self.session.status_text()" in src, name

    # No dialog may carry its own copy of the reopen wording — a second copy
    # would drift, and the hint could then be shown twice per session.
    for name in ("dialog.py", "dialog_search.py", "dialog_bom.py"):
        assert "reopen the schematic editor" not in _dialog_source(name).lower(), name
    print("test_dialogs_track_the_session: PASS")


def test_bom_batch_counts_toward_the_same_tally():
    """Parts imported via 'Import BOM…' must show up in the session line too,
    otherwise it undercounts what the visit actually imported."""
    from lcsc_manager.bom.bom_importer import PartImportResult

    session = ImportSession()
    batch = [PartImportResult("C2040", True, symbol=True),
             PartImportResult("C14663", True, symbol=True)]
    for part in batch:
        session.record(part.lcsc_id, part.symbol)
    session.record("C25804", True)  # a later single-part import

    assert session.count == 3, session.imported_ids
    assert session.status_text().endswith("C2040, C14663, C25804"), \
        session.status_text()

    src = _dialog_source("dialog_search.py")
    assert "dialog.imported_parts" in src, \
        "search dialog no longer folds BOM results into the session"
    print("test_bom_batch_counts_toward_the_same_tally: PASS")


def test_close_button_is_labelled_close():
    """'Cancel' is misleading once imports leave the dialog open."""
    for name in ("dialog.py", "dialog_search.py"):
        src = _dialog_source(name)
        assert 'wx.ID_CANCEL, "Cancel"' not in src, name
        assert '"Close"' in src, name
    print("test_close_button_is_labelled_close: PASS")


if __name__ == "__main__":
    test_status_text_empty_before_any_import()
    test_records_parts_in_order()
    test_reimport_does_not_inflate_tally()
    test_long_session_elides_oldest()
    test_reopen_hint_shown_once_per_session()
    test_reopen_hint_requires_a_symbol()
    test_hint_text_mentions_the_schematic_editor()
    test_dialogs_do_not_end_themselves_after_an_import()
    test_dialogs_track_the_session()
    test_bom_batch_counts_toward_the_same_tally()
    test_close_button_is_labelled_close()
    print("\nAll issue-16 tests passed.")
