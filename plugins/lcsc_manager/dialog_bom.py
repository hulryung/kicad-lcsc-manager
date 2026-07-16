"""BOM import dialog for LCSC Manager.

Lets the user pick which parsed BOM entries to import, choose what to import
(symbol / footprint / 3D model), then batch-imports them with a progress
dialog and a final summary. The heavy lifting lives in ``bom.bom_parser`` and
``bom.bom_importer``; this module is only the wx glue.
"""
import threading

import wx

from .bom.bom_importer import BomImporter, BomImportOptions
from .utils.logger import get_logger

logger = get_logger("dialog_bom")


class BomImportDialog(wx.Dialog):
    """Preview parsed BOM entries and batch-import the selected ones."""

    def __init__(self, parent, parse_result, api_client, library_manager,
                 default_options=(True, True, True), source_name=""):
        super().__init__(
            parent,
            title="Import BOM",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.parse_result = parse_result
        self.api_client = api_client
        self.library_manager = library_manager
        self.source_name = source_name

        self._progress = None
        self._cancel_event = threading.Event()

        self._create_ui(default_options)
        self.SetSize((760, 560))
        self.SetMinSize((640, 440))
        self.CenterOnParent()

    # -- UI ------------------------------------------------------------------

    def _create_ui(self, default_options):
        main = wx.BoxSizer(wx.VERTICAL)

        # Summary line
        r = self.parse_result
        info = "{n} unique part(s) detected".format(n=r.part_count)
        if self.source_name:
            info = "{src} — {info}".format(src=self.source_name, info=info)
        if r.skipped_rows:
            info += "   ·   {s} row(s) skipped (no LCSC part #)".format(s=r.skipped_rows)
        header = wx.StaticText(self, label=info)
        f = header.GetFont()
        f = f.Bold()
        header.SetFont(f)
        main.Add(header, 0, wx.ALL, 10)

        for w in r.warnings:
            wl = wx.StaticText(self, label="⚠ " + w)
            wl.SetForegroundColour(wx.Colour(180, 120, 0))
            main.Add(wl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Parts list with per-row checkboxes
        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_HRULES)
        self._has_checks = hasattr(self.list, "EnableCheckBoxes")
        if self._has_checks:
            self.list.EnableCheckBoxes(True)
        self.list.InsertColumn(0, "LCSC", width=90)
        self.list.InsertColumn(1, "Qty", width=50)
        self.list.InsertColumn(2, "Designators", width=200)
        self.list.InsertColumn(3, "Comment", width=140)
        self.list.InsertColumn(4, "Footprint", width=140)

        for idx, entry in enumerate(r.entries):
            self.list.InsertItem(idx, entry.lcsc_id)
            self.list.SetItem(idx, 1, str(entry.quantity))
            self.list.SetItem(idx, 2, ", ".join(entry.designators))
            self.list.SetItem(idx, 3, entry.comment)
            self.list.SetItem(idx, 4, entry.footprint)
            if self._has_checks:
                self.list.CheckItem(idx, True)
        main.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        if self._has_checks:
            sel_row = wx.BoxSizer(wx.HORIZONTAL)
            all_btn = wx.Button(self, label="Select all")
            none_btn = wx.Button(self, label="Select none")
            all_btn.Bind(wx.EVT_BUTTON, lambda e: self._check_all(True))
            none_btn.Bind(wx.EVT_BUTTON, lambda e: self._check_all(False))
            sel_row.Add(all_btn, 0, wx.RIGHT, 5)
            sel_row.Add(none_btn, 0)
            main.Add(sel_row, 0, wx.LEFT | wx.TOP, 10)

        # Import options
        opt_box = wx.StaticBoxSizer(wx.HORIZONTAL, self, "Import")
        self.cb_symbol = wx.CheckBox(self, label="Symbol")
        self.cb_footprint = wx.CheckBox(self, label="Footprint")
        self.cb_3d = wx.CheckBox(self, label="3D model")
        self.cb_symbol.SetValue(default_options[0])
        self.cb_footprint.SetValue(default_options[1])
        self.cb_3d.SetValue(default_options[2])
        opt_box.Add(self.cb_symbol, 0, wx.ALL, 5)
        opt_box.Add(self.cb_footprint, 0, wx.ALL, 5)
        opt_box.Add(self.cb_3d, 0, wx.ALL, 5)
        main.Add(opt_box, 0, wx.EXPAND | wx.ALL, 10)

        # Buttons
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.AddStretchSpacer()
        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Close")
        self.import_btn = wx.Button(self, wx.ID_OK, "Import")
        self.import_btn.Bind(wx.EVT_BUTTON, self._on_import)
        btn_row.Add(cancel_btn, 0, wx.RIGHT, 8)
        btn_row.Add(self.import_btn, 0)
        main.Add(btn_row, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main)

    def _check_all(self, value):
        for idx in range(self.list.GetItemCount()):
            self.list.CheckItem(idx, value)

    def _selected_entries(self):
        entries = self.parse_result.entries
        if not self._has_checks:
            return list(entries)
        return [entries[i] for i in range(self.list.GetItemCount())
                if self.list.IsItemChecked(i)]

    # -- Import flow ---------------------------------------------------------

    def _on_import(self, event):
        selected = self._selected_entries()
        if not selected:
            wx.MessageBox("Select at least one part to import.",
                          "Nothing selected", wx.OK | wx.ICON_WARNING)
            return

        options = BomImportOptions(
            import_symbol=self.cb_symbol.GetValue(),
            import_footprint=self.cb_footprint.GetValue(),
            import_3d=self.cb_3d.GetValue(),
        )
        if not any([options.import_symbol, options.import_footprint, options.import_3d]):
            wx.MessageBox("Select at least one of Symbol / Footprint / 3D model.",
                          "No import options", wx.OK | wx.ICON_WARNING)
            return

        self._cancel_event.clear()
        self._total = len(selected)
        self._progress = wx.GenericProgressDialog(
            "Importing BOM",
            "Starting…" + " " * 40,
            maximum=self._total,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME,
        )

        importer = BomImporter(self.api_client, self.library_manager)
        self._last_options = options  # for summary wording
        thread = threading.Thread(
            target=self._run_import,
            args=(importer, selected, options),
            daemon=True,
        )
        thread.start()

    def _run_import(self, importer, entries, options):
        summary = importer.import_entries(
            entries, options,
            progress_cb=self._progress_cb,
            should_cancel=self._cancel_event.is_set,
        )
        wx.CallAfter(self._on_import_done, summary)

    def _progress_cb(self, index, total, lcsc_id, phase):
        # Called from the worker thread — marshal onto the GUI thread.
        wx.CallAfter(self._update_progress, index, total, lcsc_id, phase)

    def _update_progress(self, index, total, lcsc_id, phase):
        if not self._progress:
            return
        if phase == "done":
            return
        verb = "Fetching" if phase == "fetching" else "Importing"
        msg = "{verb} {lcsc}  ({i}/{n})".format(
            verb=verb, lcsc=lcsc_id, i=index + 1, n=total)
        cont, _ = self._progress.Update(min(index, total), msg)
        if not cont and not self._cancel_event.is_set():
            self._cancel_event.set()
            # Acknowledge the abort immediately — the worker only stops at
            # its next cancellation checkpoint, which can take a while if a
            # network call is mid-flight.
            self._progress.Update(
                min(index, total),
                "Cancelling — finishing the current part…")

    def _on_import_done(self, summary):
        if self._progress:
            self._progress.Destroy()
            self._progress = None

        # Untick rows that imported so a follow-up Import in this dialog
        # continues with just the remaining parts.
        if self._has_checks and summary.imported:
            done = {r.lcsc_id for r in summary.imported}
            for idx, entry in enumerate(self.parse_result.entries):
                if entry.lcsc_id in done:
                    self.list.CheckItem(idx, False)

        self._show_summary(summary)

        # Close only on a clean, complete run. After a cancel, a rate-limit
        # stop, or failures, stay open so the user can adjust and retry
        # without re-selecting the BOM file.
        complete = (summary.imported and not summary.failed
                    and not summary.cancelled and not summary.not_attempted)
        if complete:
            self.EndModal(wx.ID_OK)

    def _show_summary(self, summary):
        lines = []
        ok = summary.imported
        failed = summary.failed
        lines.append("Imported {n} part(s).".format(n=len(ok)))
        if failed:
            lines.append("Failed:   {n} part(s).".format(n=len(failed)))
        if summary.cancelled:
            lines.append("(Cancelled before finishing.)")
        if summary.rate_limited:
            lines.append("")
            lines.append("EasyEDA started rate-limiting requests, so the "
                         "batch was stopped early.")
        if summary.not_attempted:
            lines.append("Not attempted: {n} part(s) — they stay ticked; "
                         "wait a bit and click Import again to continue."
                         .format(n=len(summary.not_attempted)))
        lines.append("")

        if failed:
            lines.append("Failures:")
            for r in failed:
                lines.append("  {id}: {err}".format(id=r.lcsc_id, err=r.error))
            lines.append("")

        options = getattr(self, "_last_options", None)
        if ok and (options is None or options.import_symbol):
            lines.append("Reopen the schematic editor for imported symbols "
                         "to appear.")

        dlg = _SummaryDialog(self, "BOM import complete", "\n".join(lines))
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()


class _SummaryDialog(wx.Dialog):
    """Simple scrollable, read-only text summary."""

    def __init__(self, parent, title, text):
        super().__init__(parent, title=title,
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        sizer = wx.BoxSizer(wx.VERTICAL)
        txt = wx.TextCtrl(
            self, value=text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP)
        txt.SetMinSize((520, 320))
        sizer.Add(txt, 1, wx.EXPAND | wx.ALL, 10)
        btns = self.CreateStdDialogButtonSizer(wx.OK)
        sizer.Add(btns, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizerAndFit(sizer)
        self.CenterOnParent()
