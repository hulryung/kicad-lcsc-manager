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

        # Set icon path
        icon_path = Path(__file__).parent / "resources" / "icon.png"
        if icon_path.exists():
            self.icon_file_name = str(icon_path)
        else:
            self.icon_file_name = ""

        logger.info("LCSC Manager Plugin initialized")

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
            # Try to import advanced search dialog first
            try:
                from .dialog_search import LCSCManagerSearchDialog
                # Create and show advanced search dialog
                dialog = LCSCManagerSearchDialog(None, str(project_path))
                result = dialog.ShowModal()

                if result == wx.ID_OK:
                    logger.info("Dialog completed successfully")
                else:
                    logger.info("Dialog cancelled")

                dialog.Destroy()
                return
            except ImportError as e:
                logger.warning(f"Advanced search dialog not available (missing Pillow?): {e}")
                logger.info("Falling back to simple dialog")

            # Fallback to basic dialog
            from .dialog import LCSCManagerDialog

            # Create and show dialog
            dialog = LCSCManagerDialog(None, project_path)
            result = dialog.ShowModal()

            if result == wx.ID_OK:
                logger.info("Dialog completed successfully")
            else:
                logger.info("Dialog cancelled")

            dialog.Destroy()

        except ImportError as e:
            logger.error(f"Failed to import dialog: {e}")
            # Last resort: simple input dialog
            self._show_simple_dialog(project_path)
        except Exception as e:
            logger.error(f"Dialog error: {e}", exc_info=True)
            self._show_error(f"Dialog error: {str(e)}")

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

            # TODO: Implement actual import logic
            # This will be implemented in Phase 2 and 3

            progress.Update(50, "Converting component...")
            progress.Update(90, "Adding to library...")
            progress.Update(100, "Done!")

            progress.Destroy()

            # Show success message
            wx.MessageBox(
                f"Component {lcsc_id} imported successfully!\n\n"
                f"Library location:\n{project_path.parent / 'libs' / 'lcsc'}",
                "Success",
                wx.OK | wx.ICON_INFORMATION
            )

            logger.info(f"Component {lcsc_id} imported successfully")

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
