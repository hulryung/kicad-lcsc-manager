"""
GUI Dialog for LCSC Manager Plugin
"""
import wx
from pathlib import Path
from typing import Optional, Dict, Any
from .utils.logger import get_logger
from .utils.config import get_config
from .api.lcsc_api import get_api_client, LCSCAPIError
from .library.library_manager import LibraryManager

logger = get_logger()


class LCSCManagerDialog(wx.Dialog):
    """
    Main dialog for LCSC Manager plugin
    """

    def __init__(self, parent, project_path: Path):
        """
        Initialize dialog

        Args:
            parent: Parent window
            project_path: Path to current KiCad project
        """
        super().__init__(
            parent,
            title="LCSC Manager - Import Components",
            size=(700, 550),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )

        self.project_path = project_path
        self.config = get_config()
        self.api_client = get_api_client()
        self.library_manager = LibraryManager(project_path)

        # Store component data from search
        self.component_data: Optional[Dict[str, Any]] = None

        self._create_ui()
        self.Centre()

        logger.info("Dialog initialized")

    def _create_ui(self):
        """Create the user interface"""
        # Main vertical sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title and description
        title_label = wx.StaticText(
            self,
            label="Import components from LCSC/EasyEDA and JLCPCB"
        )
        title_font = title_label.GetFont()
        title_font.PointSize += 2
        title_font = title_font.Bold()
        title_label.SetFont(title_font)
        main_sizer.Add(title_label, 0, wx.ALL | wx.EXPAND, 10)

        # Separator
        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        main_sizer.AddSpacer(10)

        # Search section
        search_box = wx.StaticBox(self, label="Search Component")
        search_sizer = wx.StaticBoxSizer(search_box, wx.VERTICAL)

        # LCSC ID input
        lcsc_panel = wx.Panel(self)
        lcsc_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        lcsc_label = wx.StaticText(lcsc_panel, label="LCSC Part Number:")
        lcsc_panel_sizer.Add(lcsc_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.lcsc_input = wx.TextCtrl(lcsc_panel, size=(200, -1))
        self.lcsc_input.SetHint("e.g., C2040")
        lcsc_panel_sizer.Add(self.lcsc_input, 1, wx.EXPAND)

        search_btn = wx.Button(lcsc_panel, label="Search")
        search_btn.Bind(wx.EVT_BUTTON, self._on_search)
        lcsc_panel_sizer.Add(search_btn, 0, wx.LEFT, 10)

        lcsc_panel.SetSizer(lcsc_panel_sizer)
        search_sizer.Add(lcsc_panel, 0, wx.EXPAND | wx.ALL, 10)

        main_sizer.Add(search_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        main_sizer.AddSpacer(10)

        # Component info section
        info_box = wx.StaticBox(self, label="Component Information")
        info_sizer = wx.StaticBoxSizer(info_box, wx.VERTICAL)

        self.info_text = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            size=(-1, 200)
        )
        self.info_text.SetValue("Enter an LCSC part number and click Search to view component details.")

        info_sizer.Add(self.info_text, 1, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(info_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        main_sizer.AddSpacer(10)

        # Options section
        options_box = wx.StaticBox(self, label="Import Options")
        options_sizer = wx.StaticBoxSizer(options_box, wx.VERTICAL)

        self.import_symbol_cb = wx.CheckBox(self, label="Import Symbol")
        self.import_symbol_cb.SetValue(True)
        options_sizer.Add(self.import_symbol_cb, 0, wx.ALL, 5)

        self.import_footprint_cb = wx.CheckBox(self, label="Import Footprint")
        self.import_footprint_cb.SetValue(True)
        options_sizer.Add(self.import_footprint_cb, 0, wx.ALL, 5)

        self.import_3d_cb = wx.CheckBox(self, label="Import 3D Model")
        self.import_3d_cb.SetValue(True)
        options_sizer.Add(self.import_3d_cb, 0, wx.ALL, 5)

        main_sizer.Add(options_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        main_sizer.AddSpacer(10)

        # Library path info
        lib_path = self.config.get_library_path(self.project_path)
        lib_info = wx.StaticText(
            self,
            label=f"Components will be saved to: {lib_path}"
        )
        lib_info.SetForegroundColour(wx.Colour(100, 100, 100))
        main_sizer.Add(lib_info, 0, wx.ALL | wx.EXPAND, 10)

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()

        import_btn = wx.Button(self, wx.ID_OK, "Import")
        import_btn.Bind(wx.EVT_BUTTON, self._on_import)
        button_sizer.AddButton(import_btn)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(cancel_btn)

        button_sizer.Realize()
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)
        self.Layout()

    def _on_search(self, event):
        """Handle search button click"""
        lcsc_id = self.lcsc_input.GetValue().strip()

        if not lcsc_id:
            wx.MessageBox(
                "Please enter an LCSC part number",
                "Input Required",
                wx.OK | wx.ICON_WARNING
            )
            return

        logger.info(f"Searching for component: {lcsc_id}")

        # Show searching message
        self.info_text.SetValue(f"Searching for {lcsc_id}...")
        wx.GetApp().Yield()  # Update UI

        try:
            # Search for component using API
            component = self.api_client.search_component(lcsc_id)

            if component:
                self.component_data = component

                # Format component info for display
                info = []
                info.append(f"LCSC Part Number: {component.get('lcsc_id', 'N/A')}")
                info.append(f"Name: {component.get('name', 'N/A')}")
                info.append(f"Description: {component.get('description', 'N/A')}")
                info.append(f"Manufacturer: {component.get('manufacturer', 'N/A')}")
                info.append(f"Package: {component.get('package', 'N/A')}")
                info.append(f"Category: {component.get('category', 'N/A')}")

                # Stock info
                stock = component.get('stock', 0)
                info.append(f"Stock: {stock:,}")

                # Pricing
                prices = component.get('price', [])
                if prices and isinstance(prices, list):
                    info.append("\nPricing:")
                    for price_tier in prices[:3]:  # Show first 3 tiers
                        if isinstance(price_tier, dict):
                            qty = price_tier.get('qty', 0)
                            price = price_tier.get('price', 0)
                            info.append(f"  {qty}+ units: ${price:.4f}")

                # Datasheet
                datasheet = component.get('datasheet')
                if datasheet:
                    info.append(f"\nDatasheet: {datasheet}")

                self.info_text.SetValue("\n".join(info))

            else:
                self.component_data = None
                self.info_text.SetValue(
                    f"Component {lcsc_id} not found.\n\n"
                    f"Please check:\n"
                    f"- The part number is correct\n"
                    f"- The component exists in LCSC database\n"
                    f"- Your internet connection is working"
                )

        except LCSCAPIError as e:
            self.component_data = None
            logger.error(f"API error: {e}")
            wx.MessageBox(
                f"Search failed: {str(e)}\n\n"
                f"This might be due to:\n"
                f"- Network connectivity issues\n"
                f"- API rate limiting\n"
                f"- Server unavailability",
                "Search Error",
                wx.OK | wx.ICON_ERROR
            )
            self.info_text.SetValue("Search failed. See error message.")

        except Exception as e:
            self.component_data = None
            logger.error(f"Unexpected error: {e}", exc_info=True)
            wx.MessageBox(
                f"Unexpected error: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR
            )
            self.info_text.SetValue("Search failed with unexpected error.")

    def _on_import(self, event):
        """Handle import button click"""
        lcsc_id = self.lcsc_input.GetValue().strip()

        if not lcsc_id:
            wx.MessageBox(
                "Please enter an LCSC part number",
                "Input Required",
                wx.OK | wx.ICON_WARNING
            )
            return

        # Get import options
        import_symbol = self.import_symbol_cb.GetValue()
        import_footprint = self.import_footprint_cb.GetValue()
        import_3d = self.import_3d_cb.GetValue()

        if not (import_symbol or import_footprint or import_3d):
            wx.MessageBox(
                "Please select at least one import option",
                "Selection Required",
                wx.OK | wx.ICON_WARNING
            )
            return

        logger.info(
            f"Importing {lcsc_id}: "
            f"symbol={import_symbol}, footprint={import_footprint}, 3d={import_3d}"
        )

        # Show progress dialog
        progress = wx.ProgressDialog(
            "Importing Component",
            f"Fetching data for {lcsc_id}...",
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT
        )

        try:
            # Fetch component data if not already searched
            if not self.component_data or self.component_data.get('lcsc_id') != lcsc_id:
                progress.Update(10, "Fetching component data...")
                self.component_data = self.api_client.search_component(lcsc_id)

                if not self.component_data:
                    progress.Destroy()
                    wx.MessageBox(
                        f"Component {lcsc_id} not found. Please search first.",
                        "Component Not Found",
                        wx.OK | wx.ICON_ERROR
                    )
                    return

            progress.Update(20, "Fetching complete component data...")

            # Get complete component data (including EasyEDA data if available)
            complete_data = self.api_client.get_component_complete(lcsc_id)
            if not complete_data:
                complete_data = self.component_data

            # Extract EasyEDA data (will be empty dict if not available)
            easyeda_data = complete_data.get('easyeda_data', {})

            progress.Update(30, "Importing to library...")

            # Import using library manager
            results = self.library_manager.import_component(
                easyeda_data=easyeda_data,
                component_info=complete_data,
                import_symbol=import_symbol,
                import_footprint=import_footprint,
                import_3d=import_3d
            )

            progress.Update(100, "Finalizing...")
            wx.MilliSleep(300)

            progress.Destroy()

            # Show results
            if results["success"]:
                message_parts = [f"Component {lcsc_id} imported successfully!"]

                if results.get("symbol"):
                    message_parts.append(f"✓ Symbol: {results['symbol']}")
                if results.get("footprint"):
                    message_parts.append(f"✓ Footprint: {results['footprint']}")
                if results.get("model_3d"):
                    models = results['model_3d']
                    if isinstance(models, dict):
                        message_parts.append(f"✓ 3D Models: {', '.join(models.keys())}")
                    else:
                        message_parts.append(f"✓ 3D Model: {models}")

                lib_path = self.config.get_library_path(self.project_path)
                message_parts.append(f"\nComponents saved to:\n{lib_path}")

                if results.get("errors"):
                    message_parts.append("\nWarnings:")
                    for error in results["errors"]:
                        message_parts.append(f"  - {error}")

                message_parts.append("\nNote: Current implementation uses placeholder converters.")
                message_parts.append("For production use, integrate with easyeda2kicad library")
                message_parts.append("or implement full EasyEDA format parsing.")

                wx.MessageBox(
                    "\n".join(message_parts),
                    "Import Successful",
                    wx.OK | wx.ICON_INFORMATION
                )

                # Close dialog
                self.EndModal(wx.ID_OK)
            else:
                error_message = "\n".join(results.get("errors", ["Unknown error"]))
                wx.MessageBox(
                    f"Import failed:\n\n{error_message}",
                    "Import Failed",
                    wx.OK | wx.ICON_ERROR
                )

        except Exception as e:
            progress.Destroy()
            logger.error(f"Import failed: {e}", exc_info=True)
            wx.MessageBox(
                f"Import failed: {str(e)}",
                "Import Error",
                wx.OK | wx.ICON_ERROR
            )

    def GetLCSCId(self) -> str:
        """
        Get the entered LCSC ID

        Returns:
            LCSC part number
        """
        return self.lcsc_input.GetValue().strip()
