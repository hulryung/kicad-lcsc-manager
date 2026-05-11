"""
SettingsDialog — edit LCSC Manager library paths at global or project scope.

Layout (top-down):
    [ 4 path fields, each with a value-source badge ]
    [ Preview block: resolved paths + existence indicators ]
    [ Scope radio: Global / This project only ]
    [ Warning label: changes apply to future imports only ]
    [ Save / Reset this scope / Cancel buttons ]

The dialog does not mutate the config until Save is clicked. Preview is
recomputed from the in-dialog values on every keystroke.
"""
from pathlib import Path
from typing import Dict, Optional

import wx

from .utils.config import Config, PATH_KEYS


FIELD_LABELS = {
    "library_path": "Library root path:",
    "symbol_lib_name": "Symbol file name:",
    "footprint_lib_name": "Footprint folder:",
    "model_3d_path": "3D model folder:",
}


class SettingsDialog(wx.Dialog):
    """Modal dialog to configure LCSC library paths."""

    def __init__(self, parent, config: Config, project_path: Optional[Path]):
        super().__init__(
            parent,
            title="LCSC Manager — Settings",
            size=(820, 540),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.config = config
        self.project_path = project_path

        # Map of key → (wx.TextCtrl, wx.StaticText badge)
        self.field_controls: Dict[str, tuple] = {}
        self.preview_labels: Dict[str, wx.StaticText] = {}
        self.preview_status: Dict[str, wx.StaticText] = {}

        self._build_ui()
        # Default scope: project if a project is open, else global.
        self._set_scope("project" if project_path else "global")

    # ─── UI construction ────────────────────────────────────────────

    def _build_ui(self) -> None:
        main = wx.BoxSizer(wx.VERTICAL)

        # Fields panel
        grid = wx.FlexGridSizer(rows=len(PATH_KEYS), cols=3, hgap=8, vgap=6)
        grid.AddGrowableCol(1, 1)

        for key in PATH_KEYS:
            label = wx.StaticText(self, label=FIELD_LABELS[key])
            ctrl = wx.TextCtrl(self)
            ctrl.Bind(wx.EVT_TEXT, self._on_value_change)
            badge = wx.StaticText(self, label="[default]")
            badge.SetForegroundColour(wx.Colour(120, 120, 120))

            grid.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND)
            grid.Add(badge, 0, wx.ALIGN_CENTER_VERTICAL)
            self.field_controls[key] = (ctrl, badge)

        main.Add(grid, 0, wx.ALL | wx.EXPAND, 12)

        # Preview block
        preview_box = wx.StaticBox(self, label="Preview")
        pv_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)

        # Use a 3-column FlexGrid so long paths flex on the middle column
        # instead of getting clipped by a fixed Wrap() width.
        pv_grid = wx.FlexGridSizer(rows=3, cols=3, hgap=8, vgap=4)
        pv_grid.AddGrowableCol(1, 1)

        for key, title in (
            ("symbol_lib", "Symbol library:"),
            ("footprint_lib", "Footprint library:"),
            ("model_3d_dir", "3D models:"),
        ):
            title_lbl = wx.StaticText(self, label=title)
            title_lbl.SetMinSize((130, -1))
            path_lbl = wx.StaticText(self, label="—")
            status_lbl = wx.StaticText(self, label="")
            status_lbl.SetMinSize((90, -1))

            pv_grid.Add(title_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            pv_grid.Add(path_lbl, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
            pv_grid.Add(status_lbl, 0, wx.ALIGN_CENTER_VERTICAL)

            self.preview_labels[key] = path_lbl
            self.preview_status[key] = status_lbl

        pv_sizer.Add(pv_grid, 1, wx.EXPAND | wx.ALL, 4)

        main.Add(pv_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)

        # Scope radio
        scope_box = wx.StaticBox(self, label="Scope")
        scope_sizer = wx.StaticBoxSizer(scope_box, wx.VERTICAL)

        self.radio_global = wx.RadioButton(
            self, label="Global (all projects)", style=wx.RB_GROUP
        )
        self.radio_project = wx.RadioButton(
            self, label="This project only"
        )
        self.radio_global.Bind(wx.EVT_RADIOBUTTON, self._on_scope_change)
        self.radio_project.Bind(wx.EVT_RADIOBUTTON, self._on_scope_change)
        if self.project_path is None:
            self.radio_project.Enable(False)
            self.radio_project.SetLabel("This project only (no project open)")

        scope_sizer.Add(self.radio_global, 0, wx.ALL, 4)
        scope_sizer.Add(self.radio_project, 0, wx.ALL, 4)
        main.Add(scope_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)

        # Warning
        warn = wx.StaticText(
            self,
            label="⚠ Changes apply to future imports only. "
                  "Existing libraries are not moved automatically.",
        )
        warn.SetForegroundColour(wx.Colour(150, 90, 0))
        warn.Wrap(600)
        main.Add(warn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        # Buttons
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.reset_btn = wx.Button(self, label="Reset this scope")
        self.reset_btn.Bind(wx.EVT_BUTTON, self._on_reset)
        btn_row.Add(self.reset_btn, 0)
        btn_row.AddStretchSpacer()

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        btn_row.Add(cancel_btn, 0, wx.RIGHT, 6)

        self.save_btn = wx.Button(self, wx.ID_OK, "Save")
        self.save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        btn_row.Add(self.save_btn, 0)

        main.Add(btn_row, 0, wx.ALL | wx.EXPAND, 12)

        self.SetSizer(main)
        self.Layout()

    # ─── state ──────────────────────────────────────────────────────

    def _current_scope(self) -> str:
        return "project" if self.radio_project.GetValue() else "global"

    def _set_scope(self, scope: str) -> None:
        if scope == "project" and self.project_path is not None:
            self.radio_project.SetValue(True)
        else:
            self.radio_global.SetValue(True)
        self._reload_fields_from_scope()

    def _reload_fields_from_scope(self) -> None:
        """Populate text fields with the value resolved *as seen from the
        current scope*. Global view never inherits Project values; Project
        view inherits Global → Default."""
        scope = self._current_scope()
        for key in PATH_KEYS:
            ctrl, _ = self.field_controls[key]
            value, _src = self.config.resolve_for_scope_view(key, scope)
            ctrl.ChangeValue(str(value) if value is not None else "")
        self._refresh_all()

    # ─── event handlers ─────────────────────────────────────────────

    def _on_scope_change(self, event):
        self._reload_fields_from_scope()

    def _on_value_change(self, event):
        self._refresh_all()

    def _on_reset(self, event):
        scope = self._current_scope()
        msg = (
            f"Reset {scope} settings to defaults?\n\n"
            + ("This will delete .lcsc_manager.json from the project."
               if scope == "project"
               else "This will overwrite your global config with defaults.")
        )
        confirm = wx.MessageBox(msg, "Confirm reset",
                                wx.YES_NO | wx.ICON_QUESTION, self)
        if confirm != wx.YES:
            return
        try:
            self.config.clear_scope(scope, self.project_path)
        except Exception as e:
            wx.MessageBox(f"Reset failed: {e}", "Error", wx.OK | wx.ICON_ERROR, self)
            return
        self._reload_fields_from_scope()

    def _on_save(self, event):
        values, errors = self._collect_values()
        if errors:
            wx.MessageBox(
                "Please fix the following errors:\n\n"
                + "\n".join(f"• {FIELD_LABELS[k]} {msg}" for k, msg in errors.items()),
                "Invalid input",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return
        try:
            self.config.save_scope(self._current_scope(), values, self.project_path)
        except Exception as e:
            wx.MessageBox(f"Save failed: {e}", "Error", wx.OK | wx.ICON_ERROR, self)
            return
        self.EndModal(wx.ID_OK)

    # ─── value collection / preview ────────────────────────────────

    def _collect_values(self) -> tuple:
        """Return (values_dict, errors_dict). Errors maps key→message."""
        values: Dict[str, str] = {}
        errors: Dict[str, str] = {}
        for key in PATH_KEYS:
            ctrl, _ = self.field_controls[key]
            raw = ctrl.GetValue().strip()
            if not raw:
                errors[key] = "must not be empty."
            elif raw.startswith("/") or raw.startswith("~"):
                errors[key] = "must be a project-relative path (no leading / or ~)."
            elif ".." in Path(raw).parts:
                errors[key] = "must not contain '..'."
            values[key] = raw
        return values, errors

    def _refresh_all(self) -> None:
        values, errors = self._collect_values()
        self._refresh_badges()
        self._refresh_preview(values, errors)
        self._refresh_save_button(errors)

    def _refresh_badges(self) -> None:
        """Update [scope] badge per field.

        [edited]                 — user typed a value that differs from what
                                   this scope currently stores
        [scope]                  — value comes from this scope's own storage
        [source → scope]         — value is inherited from a lower layer and
                                   would be written into `scope` on Save
        """
        scope = self._current_scope()
        for key in PATH_KEYS:
            ctrl, badge = self.field_controls[key]
            current = ctrl.GetValue().strip()
            stored = self.config.get_scope_values(scope).get(key)
            if stored is not None and current != str(stored):
                badge.SetLabel("[edited]")
                badge.SetForegroundColour(wx.Colour(150, 90, 0))
                continue
            _value, source = self.config.resolve_for_scope_view(key, scope)
            if source == scope:
                badge.SetLabel(f"[{scope}]")
                badge.SetForegroundColour(wx.Colour(0, 110, 0))
            else:
                badge.SetLabel(f"[{source} → {scope}]")
                badge.SetForegroundColour(wx.Colour(120, 120, 120))

    def _refresh_preview(self, values: Dict[str, str],
                         errors: Dict[str, str]) -> None:
        scope = self._current_scope()
        # Global view: paths apply to *every* project, so show the
        #              ${KIPRJMOD} template form rather than a specific
        #              absolute path.
        # Project view: show the absolute path resolved against the
        #               currently open project.
        show_template = (scope == "global") or (self.project_path is None)

        if show_template:
            root = values.get("library_path", "")
            sym = values.get("symbol_lib_name", "")
            fp = values.get("footprint_lib_name", "")
            m3 = values.get("model_3d_path", "")
            templates = {
                "symbol_lib": f"${{KIPRJMOD}}/{root}/symbols/{sym}",
                "footprint_lib": f"${{KIPRJMOD}}/{root}/{fp}",
                "model_3d_dir": f"${{KIPRJMOD}}/{root}/{m3}",
            }
            for k, lbl in self.preview_labels.items():
                lbl.SetLabel(templates[k] if not errors else "—")
                self.preview_status[k].SetLabel("")
        else:
            resolved = Config.resolve_paths(values, self.project_path)
            for k, lbl in self.preview_labels.items():
                p = resolved.get(k)
                if errors or p is None:
                    lbl.SetLabel("—")
                    self.preview_status[k].SetLabel("")
                else:
                    lbl.SetLabel(str(p))
                    if p.exists():
                        self.preview_status[k].SetLabel("✓ exists")
                        self.preview_status[k].SetForegroundColour(wx.Colour(0, 110, 0))
                    else:
                        self.preview_status[k].SetLabel("(will create)")
                        self.preview_status[k].SetForegroundColour(wx.Colour(120, 120, 120))
        self.Layout()

    def _refresh_save_button(self, errors: Dict[str, str]) -> None:
        self.save_btn.Enable(not errors)
