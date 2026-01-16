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


class OverwriteConfirmDialog(wx.Dialog):
    """Dialog to confirm overwriting existing files"""

    def __init__(self, parent, existing_files: Dict[str, bool], component_name: str):
        """
        Initialize overwrite confirmation dialog

        Args:
            parent: Parent window
            existing_files: Dictionary of existing file flags
            component_name: Name of component being imported
        """
        super().__init__(
            parent,
            title="Confirm Overwrite",
            size=(400, 300),
            style=wx.DEFAULT_DIALOG_STYLE
        )

        self.existing_files = existing_files
        self.overwrite_choices = {}

        self._create_ui(component_name)
        self.Centre()

    def _create_ui(self, component_name: str):
        """Create the dialog UI"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Warning message
        warning_text = wx.StaticText(
            self,
            label=f"The following files already exist for {component_name}.\nSelect which files to overwrite:"
        )
        main_sizer.Add(warning_text, 0, wx.ALL | wx.EXPAND, 10)

        # Separator
        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        main_sizer.AddSpacer(10)

        # Checkboxes for each existing file
        checkbox_panel = wx.Panel(self)
        checkbox_sizer = wx.BoxSizer(wx.VERTICAL)

        if self.existing_files.get("symbol"):
            self.overwrite_choices["symbol"] = wx.CheckBox(checkbox_panel, label="Overwrite Symbol")
            self.overwrite_choices["symbol"].SetValue(True)
            checkbox_sizer.Add(self.overwrite_choices["symbol"], 0, wx.ALL, 5)

        if self.existing_files.get("footprint"):
            self.overwrite_choices["footprint"] = wx.CheckBox(checkbox_panel, label="Overwrite Footprint")
            self.overwrite_choices["footprint"].SetValue(True)
            checkbox_sizer.Add(self.overwrite_choices["footprint"], 0, wx.ALL, 5)

        if self.existing_files.get("3d_wrl") or self.existing_files.get("3d_step"):
            self.overwrite_choices["3d"] = wx.CheckBox(checkbox_panel, label="Overwrite 3D Model")
            self.overwrite_choices["3d"].SetValue(True)
            checkbox_sizer.Add(self.overwrite_choices["3d"], 0, wx.ALL, 5)

        checkbox_panel.SetSizer(checkbox_sizer)
        main_sizer.Add(checkbox_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()

        ok_btn = wx.Button(self, wx.ID_OK, "Overwrite")
        ok_btn.SetDefault()
        button_sizer.AddButton(ok_btn)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel Import")
        button_sizer.AddButton(cancel_btn)

        button_sizer.Realize()
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)
        self.Layout()

    def GetOverwriteChoices(self) -> Dict[str, bool]:
        """
        Get user's overwrite choices

        Returns:
            Dictionary with overwrite flags for symbol, footprint, 3d
        """
        return {
            key: checkbox.GetValue()
            for key, checkbox in self.overwrite_choices.items()
        }


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
        self.lcsc_input.SetHint("e.g., C2040 or c2040")
        self.lcsc_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        self.lcsc_input.Bind(wx.EVT_CHAR, self._on_char)
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

    def _on_char(self, event):
        """Handle character input in LCSC ID field"""
        keycode = event.GetKeyCode()

        # Check for Enter key
        if keycode == wx.WXK_RETURN or keycode == wx.WXK_NUMPAD_ENTER:
            # Trigger search
            self._on_search(event)
        else:
            # Allow normal character processing
            event.Skip()

    def _on_search(self, event):
        """Handle search button click or Enter key"""
        lcsc_id = self.lcsc_input.GetValue().strip().upper()  # Convert to uppercase

        if not lcsc_id:
            wx.MessageBox(
                "Please enter an LCSC part number",
                "Input Required",
                wx.OK | wx.ICON_WARNING
            )
            return

        # Update the input field with uppercase version
        self.lcsc_input.SetValue(lcsc_id)

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

                # Manufacturer info
                manufacturer = component.get('manufacturer', 'N/A')
                manufacturer_part = component.get('manufacturer_part', '')
                if manufacturer_part:
                    info.append(f"Manufacturer: {manufacturer} ({manufacturer_part})")
                else:
                    info.append(f"Manufacturer: {manufacturer}")

                info.append(f"Package: {component.get('package', 'N/A')}")

                # JLCPCB Part Class
                jlcpcb_class = component.get('jlcpcb_class', '')
                if jlcpcb_class:
                    info.append(f"JLCPCB Class: {jlcpcb_class}")

                # Description (if different from name)
                description = component.get('description', '')
                if description and description != component.get('name'):
                    info.append(f"Description: {description}")

                # Stock info
                stock = component.get('stock', 0)
                if stock > 0:
                    info.append(f"Stock: {stock:,} units")

                # Pricing
                prices = component.get('price', [])
                if prices and isinstance(prices, list) and len(prices) > 0:
                    info.append("\nPricing (per unit):")
                    for price_tier in prices[:5]:  # Show first 5 tiers
                        if isinstance(price_tier, dict):
                            qty_start = price_tier.get('qty', 0)
                            qty_max = price_tier.get('qty_max')
                            price = price_tier.get('price', 0)

                            # Format quantity range
                            if qty_max is None:
                                qty_range = f"{qty_start:,}+"
                            else:
                                qty_range = f"{qty_start:,}-{qty_max:,}"

                            info.append(f"  {qty_range}: ${price:.4f}")

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
        lcsc_id = self.lcsc_input.GetValue().strip().upper()  # Convert to uppercase

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

            progress.Update(20, "Preparing component data...")

            # Use already searched component data instead of fetching again
            # This avoids potential JLCPCB API failures on second call
            complete_data = self.component_data

            # Ensure we have datasheet - if not, try to fetch complete data
            if not complete_data.get('datasheet'):
                logger.info("No datasheet in cached data, fetching complete data...")
                fetched_data = self.api_client.get_component_complete(lcsc_id)
                if fetched_data and fetched_data.get('datasheet'):
                    complete_data = fetched_data

            # Check for existing files
            existing_files = self._check_existing_files(complete_data)
            has_existing = any([
                existing_files.get("symbol") and import_symbol,
                existing_files.get("footprint") and import_footprint,
                (existing_files.get("3d_wrl") or existing_files.get("3d_step")) and import_3d
            ])

            if has_existing:
                # Temporarily hide progress dialog
                progress.Hide()

                # Show overwrite confirmation dialog
                component_name = complete_data.get("name", lcsc_id)
                confirm_dialog = OverwriteConfirmDialog(self, existing_files, component_name)
                result = confirm_dialog.ShowModal()

                if result == wx.ID_CANCEL:
                    # User cancelled
                    confirm_dialog.Destroy()
                    progress.Destroy()
                    logger.info("Import cancelled by user (existing files)")
                    return

                # Get user's overwrite choices
                overwrite_choices = confirm_dialog.GetOverwriteChoices()
                confirm_dialog.Destroy()

                # Update import flags based on user choices
                if not overwrite_choices.get("symbol", True):
                    import_symbol = False
                if not overwrite_choices.get("footprint", True):
                    import_footprint = False
                if not overwrite_choices.get("3d", True):
                    import_3d = False

                # Show progress dialog again
                progress.Show()

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
                    message_parts.append(f"✓ 3D Model")

                # Only show warnings if any
                if results.get("errors"):
                    message_parts.append("\nWarnings:")
                    for error in results["errors"]:
                        message_parts.append(f"  - {error}")

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

    def _check_existing_files(self, component_info: Dict[str, Any]) -> Dict[str, bool]:
        """
        Check if component files already exist

        Args:
            component_info: Component metadata

        Returns:
            Dictionary with exists flags for symbol, footprint, 3d_model
        """
        lib_path = self.config.get_library_path(self.project_path)
        lcsc_id = component_info.get("lcsc_id", "")
        package = component_info.get("package", "Unknown")
        symbol_name = component_info.get("description", component_info.get("name", ""))

        exists = {
            "symbol": False,
            "footprint": False,
            "3d_wrl": False,
            "3d_step": False,
        }

        # Check symbol - need to parse the library file
        symbol_file = lib_path / "symbols" / "lcsc_imported.kicad_sym"
        if symbol_file.exists():
            try:
                with open(symbol_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Look for symbol definition with this name
                    # Format: (symbol "RP2040" ...
                    if f'(symbol "{symbol_name}"' in content:
                        exists["symbol"] = True
            except Exception as e:
                logger.warning(f"Failed to check symbol file: {e}")
                # If we can't parse it, assume it might exist
                exists["symbol"] = True

        # Check footprint - footprints are separate files
        footprint_name = package.replace(" ", "_").replace(".", "_")
        footprint_name = (footprint_name
                          .replace("/", "{slash}")
                          .replace("\\", "{backslash}")
                          .replace("<", "{lt}")
                          .replace(">", "{gt}")
                          .replace(":", "{colon}")
                          .replace('"', "{dblquote}"))
        footprint_name = f"{lcsc_id}_{footprint_name}"
        footprint_file = lib_path / "footprints.pretty" / f"{footprint_name}.kicad_mod"
        exists["footprint"] = footprint_file.exists()

        # Check 3D models - separate files
        model_dir = lib_path / "3dmodels"
        exists["3d_wrl"] = (model_dir / f"{lcsc_id}.wrl").exists()
        exists["3d_step"] = (model_dir / f"{lcsc_id}.step").exists()

        return exists

    def GetLCSCId(self) -> str:
        """
        Get the entered LCSC ID

        Returns:
            LCSC part number
        """
        return self.lcsc_input.GetValue().strip()
