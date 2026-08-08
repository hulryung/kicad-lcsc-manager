"""Import-session bookkeeping shared by the search and basic dialogs.

The dialogs stay open after a successful import (issue #16) so several parts
can be added in one visit. This tracks what has landed so far and builds the
wording both dialogs show, so a running tally and the "reopen the schematic
editor" hint stay consistent between them.

Kept free of wx imports so it can be unit-tested outside KiCad.
"""
from typing import List

# Shown once per session, after the first import that actually wrote a symbol.
# KiCad caches symbol libraries at editor start, so a newly imported symbol
# only shows up after a reopen — but repeating that on every import of a
# multi-part session is noise.
REOPEN_HINT = ("Reopen the schematic editor for imported symbols to appear "
               "in the library.")

# How many part numbers the status line lists before eliding the oldest ones.
MAX_LISTED = 6


class ImportSession:
    """Records the parts imported while a dialog stays open."""

    def __init__(self):
        self.imported_ids: List[str] = []
        self._reopen_hint_shown = False

    def record(self, lcsc_id: str, imported_symbol: bool = False) -> bool:
        """Record one successful import.

        Args:
            lcsc_id: Part number to show in the status line (may be empty).
            imported_symbol: True if this import wrote a symbol.

        Returns:
            True when the caller should append REOPEN_HINT to its result
            message — i.e. this is the session's first symbol import.
        """
        # Re-importing a part (say, with different options) shouldn't inflate
        # the tally or list it twice.
        if lcsc_id and lcsc_id not in self.imported_ids:
            self.imported_ids.append(lcsc_id)

        if imported_symbol and not self._reopen_hint_shown:
            self._reopen_hint_shown = True
            return True
        return False

    @property
    def count(self) -> int:
        """Number of distinct parts imported this session."""
        return len(self.imported_ids)

    def status_text(self) -> str:
        """Label for the dialog's session line; empty before the first import."""
        if not self.imported_ids:
            return ""

        shown = self.imported_ids[-MAX_LISTED:]
        listed = ", ".join(shown)
        if len(self.imported_ids) > len(shown):
            listed = "… " + listed
        return "Imported this session ({n}): {ids}".format(
            n=len(self.imported_ids), ids=listed)
