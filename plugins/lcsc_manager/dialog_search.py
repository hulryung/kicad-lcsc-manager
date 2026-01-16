"""
Advanced Search Dialog for LCSC Manager

Provides component search with multiple parameters and preview functionality.
"""
import wx
from typing import Dict, Any, Optional, List
from pathlib import Path

from .api.lcsc_api import get_api_client, LCSCAPIError
from .library.library_manager import LibraryManager
from .utils.logger import get_logger
from .preview import SymbolPreviewRenderer, FootprintPreviewRenderer, Model3DPreviewRenderer

logger = get_logger()


class LCSCManagerSearchDialog(wx.Dialog):
    """Advanced search dialog with component preview"""

    def __init__(self, parent, project_path: str):
        """
        Initialize advanced search dialog

        Args:
            parent: Parent window
            project_path: Path to KiCad project
        """
        super().__init__(
            parent,
            title="LCSC Manager - Component Search",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )

        self.project_path = Path(project_path)
        self.api_client = get_api_client()
        self.library_manager = LibraryManager(self.project_path)

        # Preview renderers
        self.symbol_renderer = SymbolPreviewRenderer()
        self.footprint_renderer = FootprintPreviewRenderer()
        self.model_3d_renderer = Model3DPreviewRenderer()

        # Data storage
        self.search_results = []  # List of search result dicts
        self.selected_component = None  # Currently selected component
        self.current_page = 1  # Pagination
        self.preview_cache = {}  # Cache previews by uuid

        # Create UI
        self._create_ui()

        # Set size and center
        self.SetSize((1100, 700))
        self.CenterOnParent()

    def _create_ui(self):
        """Create the user interface"""
        # Main vertical sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(self, label="Search and Import LCSC Components")
        font = title.GetFont()
        font.PointSize += 2
        font = font.Bold()
        title.SetFont(font)
        main_sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        # Separator
        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Search form
        search_panel = self._create_search_panel()
        main_sizer.Add(search_panel, 0, wx.EXPAND | wx.ALL, 10)

        # Splitter window for results and preview
        splitter = wx.SplitterWindow(self, style=wx.SP_3D | wx.SP_LIVE_UPDATE)
        splitter.SetMinimumPaneSize(300)

        # Left panel: Results list
        left_panel = self._create_results_panel(splitter)

        # Right panel: Preview
        right_panel = self._create_preview_panel(splitter)

        # Split horizontally (left/right)
        splitter.SplitVertically(left_panel, right_panel, 450)

        main_sizer.Add(splitter, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Import options
        options_panel = self._create_import_options_panel()
        main_sizer.Add(options_panel, 0, wx.EXPAND | wx.ALL, 10)

        # Buttons
        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        import_btn = wx.FindWindowById(wx.ID_OK, self)
        import_btn.SetLabel("Import Selected")
        import_btn.Bind(wx.EVT_BUTTON, self._on_import)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)

    def _create_search_panel(self):
        """Create search form panel"""
        panel = wx.Panel(self)
        sizer = wx.StaticBoxSizer(wx.VERTICAL, panel, "Search Filters")

        # Create grid sizer for inputs (2 rows, 4 columns)
        input_sizer = wx.FlexGridSizer(rows=2, cols=4, vgap=5, hgap=10)
        input_sizer.AddGrowableCol(1)
        input_sizer.AddGrowableCol(3)

        # Component name
        input_sizer.Add(wx.StaticText(panel, label="Name:"),
                       0, wx.ALIGN_CENTER_VERTICAL)
        self.name_input = wx.TextCtrl(panel, size=(150, -1), style=wx.TE_PROCESS_ENTER)
        self.name_input.SetHint("e.g., RP2040, STM32")
        self.name_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        input_sizer.Add(self.name_input, 1, wx.EXPAND)

        # Value
        input_sizer.Add(wx.StaticText(panel, label="Value:"),
                       0, wx.ALIGN_CENTER_VERTICAL)
        self.value_input = wx.TextCtrl(panel, size=(150, -1), style=wx.TE_PROCESS_ENTER)
        self.value_input.SetHint("e.g., 10uF, 10k")
        self.value_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        input_sizer.Add(self.value_input, 1, wx.EXPAND)

        # Package
        input_sizer.Add(wx.StaticText(panel, label="Package:"),
                       0, wx.ALIGN_CENTER_VERTICAL)
        self.package_input = wx.TextCtrl(panel, size=(150, -1), style=wx.TE_PROCESS_ENTER)
        self.package_input.SetHint("e.g., 0603, SOT23")
        self.package_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        input_sizer.Add(self.package_input, 1, wx.EXPAND)

        # Manufacturer
        input_sizer.Add(wx.StaticText(panel, label="Manufacturer:"),
                       0, wx.ALIGN_CENTER_VERTICAL)
        self.manufacturer_input = wx.TextCtrl(panel, size=(150, -1), style=wx.TE_PROCESS_ENTER)
        self.manufacturer_input.SetHint("e.g., Samsung, TI")
        self.manufacturer_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        input_sizer.Add(self.manufacturer_input, 1, wx.EXPAND)

        sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Search button
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_btn = wx.Button(panel, label="Search")
        search_btn.Bind(wx.EVT_BUTTON, self._on_search)
        btn_sizer.Add(search_btn, 0, wx.ALIGN_RIGHT)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_results_panel(self, parent):
        """Create results list panel"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Label
        label = wx.StaticText(panel, label="Search Results")
        sizer.Add(label, 0, wx.ALL, 5)

        # Results list
        self.results_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES | wx.LC_VRULES
        )

        # Columns
        self.results_list.InsertColumn(0, "LCSC ID", width=100)
        self.results_list.InsertColumn(1, "Name", width=200)
        self.results_list.InsertColumn(2, "Package", width=80)
        self.results_list.InsertColumn(3, "Manufacturer", width=150)

        # Bind selection event
        self.results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_result_selected)
        self.results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_result_activated)

        sizer.Add(self.results_list, 1, wx.EXPAND | wx.ALL, 5)

        # Load more button
        self.load_more_btn = wx.Button(panel, label="Load More Results")
        self.load_more_btn.Bind(wx.EVT_BUTTON, self._on_load_more)
        self.load_more_btn.Enable(False)
        sizer.Add(self.load_more_btn, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_preview_panel(self, parent):
        """Create preview panel with tabs"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Label
        label = wx.StaticText(panel, label="Component Preview")
        sizer.Add(label, 0, wx.ALL, 5)

        # Notebook for tabs
        self.preview_notebook = wx.Notebook(panel)

        # Symbol preview tab
        symbol_panel = wx.Panel(self.preview_notebook)
        symbol_sizer = wx.BoxSizer(wx.VERTICAL)
        self.symbol_preview = wx.StaticBitmap(symbol_panel)
        symbol_sizer.Add(self.symbol_preview, 1, wx.ALIGN_CENTER | wx.ALL, 10)
        symbol_panel.SetSizer(symbol_sizer)
        self.preview_notebook.AddPage(symbol_panel, "Symbol")

        # Footprint preview tab
        footprint_panel = wx.Panel(self.preview_notebook)
        footprint_sizer = wx.BoxSizer(wx.VERTICAL)
        self.footprint_preview = wx.StaticBitmap(footprint_panel)
        footprint_sizer.Add(self.footprint_preview, 1, wx.ALIGN_CENTER | wx.ALL, 10)
        footprint_panel.SetSizer(footprint_sizer)
        self.preview_notebook.AddPage(footprint_panel, "Footprint")

        # 3D model preview tab
        model_3d_panel = wx.Panel(self.preview_notebook)
        model_3d_sizer = wx.BoxSizer(wx.VERTICAL)
        self.model_3d_preview = wx.StaticBitmap(model_3d_panel)
        model_3d_sizer.Add(self.model_3d_preview, 1, wx.ALIGN_CENTER | wx.ALL, 10)
        model_3d_panel.SetSizer(model_3d_sizer)
        self.preview_notebook.AddPage(model_3d_panel, "3D Model")

        sizer.Add(self.preview_notebook, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_import_options_panel(self):
        """Create import options panel"""
        panel = wx.Panel(self)
        sizer = wx.StaticBoxSizer(wx.HORIZONTAL, panel, "Import Options")

        self.import_symbol_cb = wx.CheckBox(panel, label="Import Symbol")
        self.import_symbol_cb.SetValue(True)
        sizer.Add(self.import_symbol_cb, 0, wx.ALL, 5)

        self.import_footprint_cb = wx.CheckBox(panel, label="Import Footprint")
        self.import_footprint_cb.SetValue(True)
        sizer.Add(self.import_footprint_cb, 0, wx.ALL, 5)

        self.import_3d_cb = wx.CheckBox(panel, label="Import 3D Model")
        self.import_3d_cb.SetValue(True)
        sizer.Add(self.import_3d_cb, 0, wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _on_search(self, event):
        """Handle search button click"""
        # Get search parameters
        name = self.name_input.GetValue().strip()
        value = self.value_input.GetValue().strip()
        package = self.package_input.GetValue().strip()
        manufacturer = self.manufacturer_input.GetValue().strip()

        # Check if at least one parameter provided
        if not any([name, value, package, manufacturer]):
            wx.MessageBox(
                "Please enter at least one search parameter.",
                "No Search Terms",
                wx.OK | wx.ICON_WARNING
            )
            return

        # Reset pagination
        self.current_page = 1
        self.search_results = []

        # Perform search
        self._perform_search(name, value, package, manufacturer, self.current_page)

    def _perform_search(self, name, value, package, manufacturer, page):
        """Perform the actual search"""
        try:
            # Show progress
            self.results_list.DeleteAllItems()
            wx.BeginBusyCursor()

            # Call API
            results = self.api_client.advanced_search(
                component_name=name,
                value=value,
                package=package,
                manufacturer=manufacturer,
                page=page
            )

            wx.EndBusyCursor()

            if not results:
                wx.MessageBox(
                    "No components found. Try different search terms.",
                    "No Results",
                    wx.OK | wx.ICON_INFORMATION
                )
                return

            # Store results
            self.search_results.extend(results)

            # Populate list
            self._populate_results_list()

            # Enable "Load More" if we got full page of results
            if len(results) >= 20:  # Assuming 20 per page
                self.load_more_btn.Enable(True)
            else:
                self.load_more_btn.Enable(False)

        except LCSCAPIError as e:
            wx.EndBusyCursor()
            wx.MessageBox(
                f"Search failed: {str(e)}",
                "Search Error",
                wx.OK | wx.ICON_ERROR
            )
        except Exception as e:
            wx.EndBusyCursor()
            logger.error(f"Search error: {e}", exc_info=True)
            wx.MessageBox(
                f"An error occurred: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR
            )

    def _populate_results_list(self):
        """Populate results list with search results"""
        for result in self.search_results:
            index = self.results_list.GetItemCount()

            # Get data from result
            lcsc_id = result.get("lcsc", {}).get("number", result.get("uuid", ""))
            title = result.get("title", "Unknown")
            package = result.get("package", "")

            # Try to extract package from title or description
            if not package:
                # EasyEDA results might have package in different field
                desc = result.get("description", "")
                if desc:
                    package = desc.split()[-1] if desc else ""

            manufacturer = ""  # EasyEDA search results don't always have manufacturer

            # Insert row
            self.results_list.InsertItem(index, lcsc_id)
            self.results_list.SetItem(index, 1, title)
            self.results_list.SetItem(index, 2, package)
            self.results_list.SetItem(index, 3, manufacturer)

            # Store full result data
            self.results_list.SetItemData(index, index)

    def _on_load_more(self, event):
        """Load more search results"""
        self.current_page += 1

        # Get current search parameters
        name = self.name_input.GetValue().strip()
        value = self.value_input.GetValue().strip()
        package = self.package_input.GetValue().strip()
        manufacturer = self.manufacturer_input.GetValue().strip()

        self._perform_search(name, value, package, manufacturer, self.current_page)

    def _on_result_selected(self, event):
        """Handle result selection - load previews"""
        index = event.GetIndex()
        if index < 0 or index >= len(self.search_results):
            return

        # Get selected result
        result = self.search_results[index]
        self.selected_component = result

        # Load previews
        self._load_previews(result)

    def _on_result_activated(self, event):
        """Handle double-click - import directly"""
        self._on_import(event)

    def _load_previews(self, result):
        """Load and display previews for selected component"""
        try:
            # Get LCSC ID (stored as 'uuid' in search results)
            lcsc_id = result.get("uuid") or result.get("lcsc", {}).get("number")
            if not lcsc_id:
                logger.warning("No LCSC ID in result")
                return

            # Check cache
            if lcsc_id in self.preview_cache:
                cached = self.preview_cache[lcsc_id]
                self._display_previews(
                    cached['symbol'],
                    cached['footprint'],
                    cached['model_3d']
                )
                return

            # Fetch complete component data using LCSC ID
            wx.BeginBusyCursor()
            component_data = self.api_client.search_component(lcsc_id)
            wx.EndBusyCursor()

            if not component_data:
                logger.warning(f"Failed to fetch component data for {lcsc_id}")
                return

            # Extract EasyEDA data from component
            easyeda_data = component_data.get("easyeda_data")
            if not easyeda_data:
                logger.warning(f"No EasyEDA data for {lcsc_id}")
                return

            # Render previews
            symbol_bitmap = self.symbol_renderer.render(easyeda_data)
            footprint_bitmap = self.footprint_renderer.render(easyeda_data)
            model_3d_bitmap = self.model_3d_renderer.render(easyeda_data)

            # Cache
            self.preview_cache[lcsc_id] = {
                'symbol': symbol_bitmap,
                'footprint': footprint_bitmap,
                'model_3d': model_3d_bitmap,
                'easyeda_data': easyeda_data,
                'component_data': component_data
            }

            # Display
            self._display_previews(symbol_bitmap, footprint_bitmap, model_3d_bitmap)

        except Exception as e:
            wx.EndBusyCursor()
            logger.error(f"Failed to load previews: {e}", exc_info=True)

    def _display_previews(self, symbol_bitmap, footprint_bitmap, model_3d_bitmap):
        """Display preview bitmaps"""
        if symbol_bitmap:
            self.symbol_preview.SetBitmap(symbol_bitmap)
        if footprint_bitmap:
            self.footprint_preview.SetBitmap(footprint_bitmap)
        if model_3d_bitmap:
            self.model_3d_preview.SetBitmap(model_3d_bitmap)

        self.Layout()

    def _on_import(self, event):
        """Handle import button click"""
        if not self.selected_component:
            wx.MessageBox(
                "Please select a component from the search results.",
                "No Selection",
                wx.OK | wx.ICON_WARNING
            )
            return

        # Get import options
        import_symbol = self.import_symbol_cb.GetValue()
        import_footprint = self.import_footprint_cb.GetValue()
        import_3d = self.import_3d_cb.GetValue()

        if not any([import_symbol, import_footprint, import_3d]):
            wx.MessageBox(
                "Please select at least one import option.",
                "No Options Selected",
                wx.OK | wx.ICON_WARNING
            )
            return

        try:
            # Get LCSC ID
            lcsc_id = self.selected_component.get("uuid") or self.selected_component.get("lcsc", {}).get("number")

            if not lcsc_id:
                wx.MessageBox(
                    "No LCSC ID found for selected component.",
                    "Import Error",
                    wx.OK | wx.ICON_ERROR
                )
                return

            # Check if we have cached data
            if lcsc_id in self.preview_cache:
                easyeda_data = self.preview_cache[lcsc_id]['easyeda_data']
                component_info = self.preview_cache[lcsc_id]['component_data']
            else:
                # Fetch complete component data
                wx.BeginBusyCursor()
                component_info = self.api_client.search_component(lcsc_id)
                wx.EndBusyCursor()

                if not component_info:
                    wx.MessageBox(
                        "Failed to fetch component data.",
                        "Import Error",
                        wx.OK | wx.ICON_ERROR
                    )
                    return

                easyeda_data = component_info.get("easyeda_data")
                if not easyeda_data:
                    wx.MessageBox(
                        "No EasyEDA data available for this component.",
                        "Import Error",
                        wx.OK | wx.ICON_ERROR
                    )
                    return

            # Show progress dialog
            progress = wx.ProgressDialog(
                "Importing Component",
                "Importing component files...",
                maximum=100,
                parent=self,
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
            )

            try:
                # Import component
                result = self.library_manager.import_component(
                    easyeda_data=easyeda_data,
                    component_info=component_info,
                    import_symbol=import_symbol,
                    import_footprint=import_footprint,
                    import_3d=import_3d
                )

                progress.Update(100)
                progress.Destroy()

                # Show success message
                success_msg = "Component imported successfully!\n\n"
                if result.get("symbol"):
                    success_msg += f"✓ Symbol\n"
                if result.get("footprint"):
                    success_msg += f"✓ Footprint\n"
                if result.get("model_3d"):
                    success_msg += f"✓ 3D Model\n"

                wx.MessageBox(
                    success_msg,
                    "Import Successful",
                    wx.OK | wx.ICON_INFORMATION
                )

                # Close dialog
                self.EndModal(wx.ID_OK)

            except Exception as e:
                progress.Destroy()
                raise

        except Exception as e:
            wx.EndBusyCursor()
            logger.error(f"Import failed: {e}", exc_info=True)
            wx.MessageBox(
                f"Import failed: {str(e)}",
                "Import Error",
                wx.OK | wx.ICON_ERROR
            )
