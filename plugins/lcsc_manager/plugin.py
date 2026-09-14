"""
Main LCSC Manager Plugin implementation: the SWIG action plugin (KiCad 9/10).
The IPC plugin's entry point is ipc_main.py; both open the same dialog.
"""
import pcbnew
from pathlib import Path
from .launcher import open_main_dialog, show_error
from .utils.logger import get_logger

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
                show_error("No board loaded. Please open a PCB file first.")
                return

            # Get project path
            board_path = board.GetFileName()
            if not board_path:
                logger.error("Board not saved")
                show_error("Please save your board first.")
                return

            project_path = Path(board_path)
            logger.info(f"Project path: {project_path}")

            # Show dialog
            open_main_dialog(project_path)

        except Exception as e:
            logger.error(f"Plugin execution failed: {e}", exc_info=True)
            show_error(f"Plugin error: {str(e)}")
