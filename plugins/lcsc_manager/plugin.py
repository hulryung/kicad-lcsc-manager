"""
Main LCSC Manager Plugin implementation
"""
import pcbnew
import wx
import os
from pathlib import Path
from .utils.logger import get_logger
from .utils.config import get_config

logger = get_logger()


class LCSCManagerPlugin(pcbnew.ActionPlugin):
    """
    KiCad Action Plugin for managing LCSC/JLCPCB components
    """

    def defaults(self):
        """
        Set plugin defaults (name, description, icon)
        """
        self.name = "LCSC Manager"
        self.category = "Library"
        self.description = "Import components from LCSC/EasyEDA and JLCPCB"
        self.show_toolbar_button = True

        # Store icon path for both light and dark modes
        icon_path = Path(__file__).parent / "plugin_resources" / "icon.png"
        self._icon_path = str(icon_path) if icon_path.exists() else ""

        logger.info("LCSC Manager Plugin initialized")

    def GetIconFileName(self, dark):
        """
        Return icon file name for light/dark mode

        Args:
            dark: True for dark mode icon, False for light mode icon

        Returns:
            Path to icon file
        """
        # For now, use the same icon for both modes
        # In the future, we could provide separate icons
        return self._icon_path

    def Run(self):
        """
        Execute plugin action (called when toolbar button is clicked)
        """
        try:
            logger.info("LCSC Manager Plugin started")

            # Get current board
            board = pcbnew.GetBoard()
            if not board:
                logger.error("No board loaded")
                self._show_error("No board loaded. Please open a PCB file first.")
                return

            # Get project path
            board_path = board.GetFileName()
            if not board_path:
                logger.error("Board not saved")
                self._show_error("Please save your board first.")
                return

            project_path = Path(board_path)
            logger.info(f"Project path: {project_path}")

            # Show dialog
            self._show_dialog(project_path)

        except Exception as e:
            logger.error(f"Plugin execution failed: {e}", exc_info=True)
            self._show_error(f"Plugin error: {str(e)}")

    def _show_dialog(self, project_path: Path):
        """
        Show the main plugin dialog

        Args:
            project_path: Path to the current KiCad project
        """
        try:
            # Try to import advanced search dialog first. Catch any
            # import-time failure, not just ImportError: e.g. a missing
            # wx.html2 raises ImportError, but a bundled dependency that is
            # incompatible with KiCad's Python raises TypeError instead —
            # both should degrade gracefully rather than error out.
            advanced_dialog_cls = None
            try:
                from .dialog_search import LCSCManagerSearchDialog
                advanced_dialog_cls = LCSCManagerSearchDialog
            except Exception as e:
                logger.warning(f"Advanced search dialog not available: {e!r}")
                logger.info("Falling back to simple dialog")
                # Tell the user *in the GUI* why they only get the basic
                # dialog and how to fix it — a console-only warning is
                # invisible when KiCad is launched from a desktop menu
                # (issues #6, #14). Shown once per KiCad session.
                self._notify_degraded_mode(e)

            if advanced_dialog_cls is not None:
                # Create and show advanced search dialog. Runtime errors here
                # are NOT swallowed into the fallback — they propagate to the
                # outer handler like before.
                dialog = advanced_dialog_cls(None, str(project_path))
                try:
                    result = dialog.ShowModal()

                    if result == wx.ID_OK:
                        logger.info("Dialog completed successfully")
                    else:
                        logger.info("Dialog cancelled")
                finally:
                    dialog.Destroy()
                return

            # Fallback to basic dialog. Its import shares modules with the
            # advanced dialog (api client → bundled requests), so it can fail
            # for the same non-ImportError reasons — degrade to the last-
            # resort prompt instead of dead-ending in the generic handler.
            try:
                from .dialog import LCSCManagerDialog
            except Exception as e:
                logger.error(f"Basic dialog not available either: {e!r}")
                self._show_simple_dialog(project_path)
                return

            # Create and show dialog
            dialog = LCSCManagerDialog(None, project_path)
            try:
                result = dialog.ShowModal()

                if result == wx.ID_OK:
                    logger.info("Dialog completed successfully")
                else:
                    logger.info("Dialog cancelled")
            finally:
                dialog.Destroy()

        except ImportError as e:
            logger.error(f"Failed to import dialog: {e}")
            # Last resort: simple input dialog
            self._show_simple_dialog(project_path)
        except Exception as e:
            logger.error(f"Dialog error: {e}", exc_info=True)
            self._show_error(f"Dialog error: {str(e)}")

    # Class-level so the notice appears once per KiCad session, not on
    # every plugin launch.
    _degraded_notice_shown = False

    def _notify_degraded_mode(self, exc: BaseException):
        """Show a GUI notice explaining why the advanced dialog is unavailable."""
        if LCSCManagerPlugin._degraded_notice_shown:
            return
        LCSCManagerPlugin._degraded_notice_shown = True
        try:
            from .utils.deps import describe_dialog_import_error
            wx.MessageBox(
                describe_dialog_import_error(exc),
                "LCSC Manager — Limited Mode",
                wx.OK | wx.ICON_WARNING
            )
        except Exception as e:
            # Never let the notice itself break the fallback path.
            logger.error(f"Failed to show degraded-mode notice: {e}")

    def _show_simple_dialog(self, project_path: Path):
        """
        Show a simple input dialog as fallback

        Args:
            project_path: Path to the current KiCad project
        """
        try:
            import wx

            # Simple text input dialog
            dlg = wx.TextEntryDialog(
                None,
                "Enter LCSC Part Number (e.g., C2040):",
                "LCSC Manager",
                ""
            )

            if dlg.ShowModal() == wx.ID_OK:
                lcsc_id = dlg.GetValue().strip()
                if lcsc_id:
                    logger.info(f"User entered LCSC ID: {lcsc_id}")
                    self._import_component(lcsc_id, project_path)
                else:
                    logger.warning("No LCSC ID entered")

            dlg.Destroy()

        except Exception as e:
            logger.error(f"Simple dialog error: {e}", exc_info=True)
            self._show_error(f"Error: {str(e)}")

    def _import_component(self, lcsc_id: str, project_path: Path):
        """
        Import a component from LCSC

        Args:
            lcsc_id: LCSC part number
            project_path: Path to the current KiCad project
        """
        try:
            import wx

            # Show progress dialog
            progress = wx.ProgressDialog(
                "LCSC Manager",
                f"Importing component {lcsc_id}...",
                maximum=100,
                parent=None,
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
            )

            progress.Update(10, "Fetching component data...")

            # Real import via the same path the dialogs use. Imported lazily:
            # this last-resort prompt is typically reached because imports
            # are broken, so failures here must be reported, not faked.
            from .api.lcsc_api import get_api_client
            from .library.library_manager import LibraryManager

            component = get_api_client().search_component(lcsc_id)
            if not component or not component.get("easyeda_data"):
                progress.Destroy()
                self._show_error(
                    f"{lcsc_id} has no symbol/footprint in EasyEDA's library, "
                    f"so it can't be imported (the part may still exist in "
                    f"the LCSC catalog)."
                )
                return

            progress.Update(50, "Converting component...")
            results = LibraryManager(project_path).import_component(
                easyeda_data=component["easyeda_data"],
                component_info=component,
            )

            progress.Update(100, "Done!")
            progress.Destroy()

            if results.get("success"):
                wx.MessageBox(
                    f"Component {lcsc_id} imported successfully!\n\n"
                    f"Library location:\n{project_path.parent / 'libs' / 'lcsc'}",
                    "Success",
                    wx.OK | wx.ICON_INFORMATION
                )
                logger.info(f"Component {lcsc_id} imported successfully")
            else:
                errors = "\n".join(results.get("errors", ["Unknown error"]))
                self._show_error(f"Import failed:\n\n{errors}")

        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            self._show_error(f"Import failed: {str(e)}")

    def _show_error(self, message: str):
        """
        Show error message dialog

        Args:
            message: Error message to display
        """
        try:
            import wx
            wx.MessageBox(
                message,
                "LCSC Manager Error",
                wx.OK | wx.ICON_ERROR
            )
        except Exception as e:
            logger.error(f"Failed to show error dialog: {e}")
            print(f"ERROR: {message}")
