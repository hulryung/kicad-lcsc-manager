"""
SettingsDialog — edit LCSC Manager library paths at global or project scope.

Layout (top-down):
    [ Library location: inside each project / one shared folder + Browse ]
    [ 4 path fields, each with a value-source badge ]
    [ Preview block: resolved paths + existence indicators ]
    [ Scope radio: Global / This project only, + override notice ]
    [ Warning label: changes apply to future imports only ]
    [ Save / Reset this scope / Cancel buttons ]

The dialog does not mutate the config until Save is clicked. Preview is
recomputed from the in-dialog values on every keystroke.
"""
from pathlib import Path
from typing import Dict, Optional

import wx

from .utils.config import (Config, PATH_KEYS, LAYERED_KEYS, LOCATION_PROJECT,
                           LOCATION_SHARED, expand_path_vars,
                           validate_path_value, validate_shared_path)


FIELD_LABELS = {
    "library_path": "Library root path:",
    "symbol_lib_name": "Symbol file name:",
    "footprint_lib_name": "Footprint folder:",
    "model_3d_path": "3D model folder:",
    "library_location": "Library location:",
    "shared_library_path": "Shared folder:",
}


class SettingsDialog(wx.Dialog):
    """Modal dialog to configure LCSC library paths."""

    def __init__(self, parent, config: Config, project_path: Optional[Path]):
        super().__init__(
            parent,
            title="LCSC Manager — Settings",
            size=(840, 720),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.config = config
        self.project_path = project_path

        # Map of key → (wx.TextCtrl, wx.StaticText badge)
        self.field_controls: Dict[str, tuple] = {}
        self.preview_labels: Dict[str, wx.StaticText] = {}
        self.preview_status: Dict[str, wx.StaticText] = {}

        self._build_ui()
        # Open on the scope that actually supplies the settings in effect.
        # Always opening on "This project only" made a Global save look lost
        # when the dialog was reopened, and invited a project Save that then
        # shadowed Global (issue #20).
        self._set_scope(self.config.default_edit_scope(project_path is not None))

    # ─── UI construction ────────────────────────────────────────────

    def _build_ui(self) -> None:
        main = wx.BoxSizer(wx.VERTICAL)

        # Where the libraries live. Separate from the scope radio below,
        # which only decides where these *settings* are stored (issue #20).
        loc_box = wx.StaticBox(self, label="Library location")
        loc_sizer = wx.StaticBoxSizer(loc_box, wx.VERTICAL)
        muted = wx.Colour(100, 100, 100)

        self.radio_loc_project = wx.RadioButton(
            self, label="Inside each project", style=wx.RB_GROUP)
        loc_sizer.Add(self.radio_loc_project, 0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
        loc_project_hint = wx.StaticText(
            self, label="Every project keeps its own copy under the library "
                        "root path below — easy to commit along with the project.")
        loc_project_hint.SetForegroundColour(muted)
        loc_sizer.Add(loc_project_hint, 0, wx.LEFT, 28)

        self.radio_loc_shared = wx.RadioButton(
            self, label="One shared folder for all projects")
        loc_sizer.Add(self.radio_loc_shared, 0, wx.LEFT | wx.RIGHT | wx.TOP, 4)

        shared_row = wx.BoxSizer(wx.HORIZONTAL)
        shared_row.AddSpacer(24)  # line up under the radio label
        self.shared_path_ctrl = wx.TextCtrl(self)
        self.shared_path_ctrl.SetHint("e.g. ~/KiCad/lcsc, C:\\KiCadLibs\\lcsc or ${MY_LIBS}/lcsc")
        self.shared_path_ctrl.Bind(wx.EVT_TEXT, self._on_value_change)
        shared_row.Add(self.shared_path_ctrl, 1, wx.EXPAND)
        self.shared_browse_btn = wx.Button(self, label="Browse…")
        self.shared_browse_btn.Bind(wx.EVT_BUTTON, self._on_browse_shared)
        shared_row.Add(self.shared_browse_btn, 0, wx.LEFT, 6)
        loc_sizer.Add(shared_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)
        loc_shared_hint = wx.StaticText(
            self, label="Registered in KiCad's global library tables, so every "
                        "project can use it. The folder is always saved to "
                        "Global — it is a location on this computer.")
        loc_shared_hint.SetForegroundColour(muted)
        loc_shared_hint.Wrap(740)
        loc_sizer.Add(loc_shared_hint, 0, wx.LEFT | wx.TOP, 28)
        loc_sizer.AddSpacer(4)

        for radio in (self.radio_loc_project, self.radio_loc_shared):
            radio.Bind(wx.EVT_RADIOBUTTON, self._on_location_change)
        main.Add(loc_sizer, 0, wx.ALL | wx.EXPAND, 12)

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

        main.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)

        # Preview block
        preview_box = wx.StaticBox(self, label="Preview")
        pv_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)

        # Use a 3-column FlexGrid so long paths flex on the middle column
        # instead of getting clipped by a fixed Wrap() width.
        pv_grid = wx.FlexGridSizer(rows=4, cols=3, hgap=8, vgap=4)
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

        reg_title = wx.StaticText(self, label="Registered in:")
        reg_title.SetMinSize((130, -1))
        self.registered_label = wx.StaticText(self, label="—")
        pv_grid.Add(reg_title, 0, wx.ALIGN_CENTER_VERTICAL)
        pv_grid.Add(self.registered_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        pv_grid.Add(wx.StaticText(self, label=""), 0)

        pv_sizer.Add(pv_grid, 1, wx.EXPAND | wx.ALL, 4)

        main.Add(pv_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)

        # Scope radio. This picks where the *settings* are stored — it does not
        # move the libraries anywhere; "Global" read as "one shared folder"
        # otherwise (issue #20).
        scope_box = wx.StaticBox(self, label="Save these settings to")
        scope_sizer = wx.StaticBoxSizer(scope_box, wx.VERTICAL)

        self.radio_global = wx.RadioButton(
            self, label="Global — the default for every project",
            style=wx.RB_GROUP
        )
        self.radio_project = wx.RadioButton(
            self, label="This project only — overrides Global for this project"
        )
        self.radio_global.Bind(wx.EVT_RADIOBUTTON, self._on_scope_change)
        self.radio_project.Bind(wx.EVT_RADIOBUTTON, self._on_scope_change)
        if self.project_path is None:
            self.radio_project.Enable(False)
            self.radio_project.SetLabel("This project only (no project open)")

        scope_sizer.Add(self.radio_global, 0, wx.ALL, 4)
        scope_sizer.Add(self.radio_project, 0, wx.ALL, 4)

        # Explains what a Save in the current scope will actually do for the
        # open project — above all, when a project override makes Global
        # changes have no effect here.
        self.scope_notice = wx.StaticText(self, label="")
        scope_sizer.Add(self.scope_notice, 0, wx.ALL | wx.EXPAND, 4)
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
        location, _src = self.config.resolve_for_scope_view("library_location", scope)
        if location == LOCATION_SHARED:
            self.radio_loc_shared.SetValue(True)
        else:
            self.radio_loc_project.SetValue(True)
        # Global-only: the same folder whichever scope is being edited.
        self.shared_path_ctrl.ChangeValue(self.config.get("shared_library_path") or "")
        self._refresh_all()

    def _current_location(self) -> str:
        return LOCATION_SHARED if self.radio_loc_shared.GetValue() else LOCATION_PROJECT

    # ─── event handlers ─────────────────────────────────────────────

    def _on_scope_change(self, event):
        self._reload_fields_from_scope()

    def _on_value_change(self, event):
        self._refresh_all()

    def _on_location_change(self, event):
        self._refresh_all()

    def _on_browse_shared(self, event):
        start = self.shared_path_ctrl.GetValue().strip()
        start = expand_path_vars(start) if start else str(Path.home())
        with wx.DirDialog(self, "Choose the shared library folder",
                          defaultPath=start,
                          style=wx.DD_DEFAULT_STYLE) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.shared_path_ctrl.SetValue(dlg.GetPath())

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
        scope = self._current_scope()
        layered = {k: values[k] for k in LAYERED_KEYS}
        try:
            if scope == "project":
                self.config.save_project_settings(layered, self.project_path)
            else:
                self.config.save_global_settings(layered)
            # A folder on this computer, so it always lives in Global.
            self.config.save_global_settings(
                {"shared_library_path": values["shared_library_path"]})
        except Exception as e:
            wx.MessageBox(f"Save failed: {e}", "Error", wx.OK | wx.ICON_ERROR, self)
            return

        if scope == "global" and self.project_path is not None:
            self._offer_to_drop_project_overrides()
        self.EndModal(wx.ID_OK)

    def _offer_to_drop_project_overrides(self) -> None:
        """After a Global save, point out project overrides that stop it from
        applying here, and offer to remove them (issue #20)."""
        keys = self.config.project_override_keys()
        if not keys:
            return
        fields = "\n".join(f"• {FIELD_LABELS[k].rstrip(':')}" for k in keys)
        answer = wx.MessageBox(
            "Saved to Global.\n\n"
            "This project has its own settings (.lcsc_manager.json) that take "
            f"precedence over Global here:\n\n{fields}\n\n"
            "Remove them so this project follows Global?",
            "Project overrides Global",
            wx.YES_NO | wx.ICON_QUESTION,
            self,
        )
        if answer == wx.YES:
            try:
                self.config.clear_scope("project", self.project_path)
            except Exception as e:
                wx.MessageBox(f"Could not remove project settings: {e}",
                              "Error", wx.OK | wx.ICON_ERROR, self)

    # ─── value collection / preview ────────────────────────────────

    def _collect_values(self) -> tuple:
        """Return (values_dict, errors_dict). Errors maps key→message."""
        values: Dict[str, str] = {}
        errors: Dict[str, str] = {}
        location = self._current_location()
        for key in PATH_KEYS:
            ctrl, _ = self.field_controls[key]
            raw = ctrl.GetValue().strip()
            # The project library root is unused for a shared folder.
            if not (key == "library_path" and location == LOCATION_SHARED):
                error = validate_path_value(key, raw)
                if error:
                    errors[key] = error
            values[key] = raw
        values["library_location"] = location
        shared = self.shared_path_ctrl.GetValue().strip()
        values["shared_library_path"] = shared
        if location == LOCATION_SHARED:
            error = validate_shared_path(shared)
            if error:
                errors["shared_library_path"] = error
        return values, errors

    def _refresh_all(self) -> None:
        values, errors = self._collect_values()
        shared = values["library_location"] == LOCATION_SHARED
        self.field_controls["library_path"][0].Enable(not shared)
        self.shared_path_ctrl.Enable(shared)
        self.shared_browse_btn.Enable(shared)
        self._refresh_badges()
        self._refresh_scope_notice()
        self._refresh_preview(values, errors)
        self._refresh_save_button(errors)

    def _refresh_badges(self) -> None:
        """Update [scope] badge per field.

        [edited]         — user typed a value that differs from what this
                           scope currently stores
        [scope]          — value comes from this scope's own storage
        [from source]    — value is inherited from a lower layer; Save leaves
                           it inherited unless it is changed
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
                badge.SetLabel(f"[from {source}]")
                badge.SetForegroundColour(wx.Colour(120, 120, 120))

    def _refresh_scope_notice(self) -> None:
        """Say what Save does in the current scope for the open project."""
        scope = self._current_scope()
        overridden = self.config.project_override_keys() if self.project_path else []
        if scope == "global" and overridden:
            fields = ", ".join(FIELD_LABELS[k].rstrip(":").lower() for k in overridden)
            text = ("⚠ This project overrides Global for: " + fields +
                    ". Global changes won't affect this project until those "
                    "overrides are removed.")
            colour = wx.Colour(150, 90, 0)
        elif scope == "project":
            text = ("Only values that differ from Global are stored for this "
                    "project; the rest keep following Global.")
            colour = wx.Colour(100, 100, 100)
        else:
            text = ""
            colour = wx.Colour(100, 100, 100)
        self.scope_notice.SetLabel(text)
        self.scope_notice.SetForegroundColour(colour)
        self.scope_notice.Wrap(740)

    def _refresh_preview(self, values: Dict[str, str],
                         errors: Dict[str, str]) -> None:
        scope = self._current_scope()
        # Global view: paths apply to *every* project, so show the
        #              ${KIPRJMOD} template form rather than a specific
        #              absolute path.
        # Project view: show the absolute path resolved against the
        #               currently open project.
        shared = values.get("library_location") == LOCATION_SHARED
        # A shared folder is the same for every project, so it can always be
        # shown as a real path.
        show_template = not shared and (scope == "global" or self.project_path is None)
        self.registered_label.SetLabel(
            "KiCad's global library tables (every project)" if shared
            else "each project's own library tables")

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
