"""Batch import orchestration for BOM files.

Given a list of :class:`~lcsc_manager.bom.bom_parser.BomEntry` objects, this
fetches each component and imports it via the existing single-part import
path (``LibraryManager.import_component``), reporting progress and a summary.

The orchestration is kept independent of wx so it can be unit-tested with
fake api/library objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ..api.lcsc_api import LCSCRateLimitError
from ..utils.logger import get_logger

logger = get_logger("bom_importer")

# progress_cb(index, total, lcsc_id, phase) where phase in
# {"fetching", "importing", "done"}.
ProgressCallback = Callable[[int, int, str, str], None]
CancelCallback = Callable[[], bool]


@dataclass
class BomImportOptions:
    import_symbol: bool = True
    import_footprint: bool = True
    import_3d: bool = True


@dataclass
class PartImportResult:
    lcsc_id: str
    success: bool
    symbol: bool = False
    footprint: bool = False
    model_3d: bool = False
    error: str = ""


@dataclass
class BomImportSummary:
    results: List[PartImportResult] = field(default_factory=list)
    cancelled: bool = False
    # True when the batch was stopped early because the API started
    # rate-limiting; hammering the remaining parts would only prolong it.
    rate_limited: bool = False
    # LCSC ids that were never attempted (batch stopped early).
    not_attempted: List[str] = field(default_factory=list)

    @property
    def imported(self) -> List[PartImportResult]:
        return [r for r in self.results if r.success]

    @property
    def failed(self) -> List[PartImportResult]:
        return [r for r in self.results if not r.success]


class BomImporter:
    """Import a list of parsed BOM entries into the project libraries."""

    def __init__(self, api_client, library_manager):
        self.api_client = api_client
        self.library_manager = library_manager

    def import_entries(
        self,
        entries,
        options: BomImportOptions,
        progress_cb: Optional[ProgressCallback] = None,
        should_cancel: Optional[CancelCallback] = None,
    ) -> BomImportSummary:
        summary = BomImportSummary()
        total = len(entries)

        for i, entry in enumerate(entries):
            if should_cancel is not None and should_cancel():
                summary.cancelled = True
                summary.not_attempted = [e2.lcsc_id for e2 in entries[i:]]
                break

            lcsc_id = entry.lcsc_id
            if progress_cb is not None:
                progress_cb(i, total, lcsc_id, "fetching")

            # Fetch component data.
            try:
                info = self.api_client.search_component(lcsc_id)
            except LCSCRateLimitError as e:
                # The API is throttling — every further part would burn a
                # minute of retries and prolong the throttle. Stop the batch
                # and tell the user to retry later.
                logger.warning(f"BOM: rate limited at {lcsc_id}: {e}")
                summary.results.append(
                    PartImportResult(lcsc_id, False,
                                     error="Rate limited by EasyEDA")
                )
                summary.rate_limited = True
                summary.not_attempted = [e2.lcsc_id for e2 in entries[i + 1:]]
                break
            except Exception as e:  # network / API errors must not abort the batch
                logger.warning(f"BOM: fetch failed for {lcsc_id}: {e}")
                summary.results.append(
                    PartImportResult(lcsc_id, False, error=f"Fetch failed: {e}")
                )
                continue

            if not info or not info.get("easyeda_data"):
                summary.results.append(
                    PartImportResult(
                        lcsc_id, False,
                        error="No symbol/footprint in EasyEDA's library "
                              "(the part may still exist in the LCSC catalog)")
                )
                continue

            # Re-check cancellation between the fetch and import phases —
            # the fetch can take tens of seconds under throttling, and this
            # bounds how long an Abort takes to be honored.
            if should_cancel is not None and should_cancel():
                summary.cancelled = True
                summary.not_attempted = [e2.lcsc_id for e2 in entries[i:]]
                break

            # Import into libraries (reuse the single-part path).
            if progress_cb is not None:
                progress_cb(i, total, lcsc_id, "importing")
            try:
                result = self.library_manager.import_component(
                    easyeda_data=info["easyeda_data"],
                    component_info=info,
                    import_symbol=options.import_symbol,
                    import_footprint=options.import_footprint,
                    import_3d=options.import_3d,
                )
            except Exception as e:
                logger.error(f"BOM: import failed for {lcsc_id}: {e}", exc_info=True)
                summary.results.append(
                    PartImportResult(lcsc_id, False, error=f"Import failed: {e}")
                )
                continue

            part = PartImportResult(
                lcsc_id=lcsc_id,
                success=bool(result.get("success")),
                symbol=result.get("symbol") is not None,
                footprint=result.get("footprint") is not None,
                model_3d=result.get("model_3d") is not None,
            )
            if not part.success and result.get("errors"):
                part.error = "; ".join(str(x) for x in result["errors"])
            summary.results.append(part)

        if progress_cb is not None:
            progress_cb(total, total, "", "done")

        return summary
