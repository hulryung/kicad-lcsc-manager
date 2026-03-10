"""
Advanced Search Dialog for LCSC Manager

Provides component search with multiple parameters and preview functionality.
"""
import wx
import wx.html2
import threading
import requests
from typing import Dict, Any, Optional, List
from pathlib import Path

from .api.lcsc_api import get_api_client, LCSCAPIError
from .library.library_manager import LibraryManager
from .utils.logger import get_logger

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

        # EasyEDA SVG API
        self.EASYEDA_SVG_URL = "https://easyeda.com/api/products/{lcsc_id}/svgs"
        self._svg_cache: Dict[str, Optional[List]] = {}

        # Data storage
        self.search_results = []  # List of search result dicts
        self.selected_component = None  # Currently selected component
        self.current_page = 1  # Pagination
        self.preview_cache = {}  # Cache previews by uuid

        # Async preview loading
        self.preview_thread = None  # Current preview loading thread
        self.preview_thread_id = 0  # Counter to track preview requests

        # Create UI
        self._create_ui()

        # Set size and center
        self.SetSize((1400, 900))
        self.SetMinSize((1200, 800))
        self.CenterOnParent()

        # Focus search input and allow ESC to close
        self.name_input.SetFocus()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

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

        # Split horizontally (left/right) - balanced split for good visibility
        splitter.SplitVertically(left_panel, right_panel, 700)

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

        # Create horizontal sizer for inputs
        input_sizer = wx.FlexGridSizer(rows=1, cols=4, vgap=5, hgap=10)
        input_sizer.AddGrowableCol(1)

        # Search (supports name, value, LCSC ID)
        input_sizer.Add(wx.StaticText(panel, label="Search:"),
                       0, wx.ALIGN_CENTER_VERTICAL)
        self.name_input = wx.TextCtrl(panel, size=(200, -1), style=wx.TE_PROCESS_ENTER)
        self.name_input.SetHint("Name, value, or LCSC ID (e.g., RP2040, 10uF, C2040)")
        self.name_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        input_sizer.Add(self.name_input, 1, wx.EXPAND)

        # Package (optional)
        input_sizer.Add(wx.StaticText(panel, label="Package:"),
                       0, wx.ALIGN_CENTER_VERTICAL)
        self.package_input = wx.TextCtrl(panel, size=(120, -1), style=wx.TE_PROCESS_ENTER)
        self.package_input.SetHint("e.g., 0603, SOT23, LQFN (optional)")
        self.package_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        input_sizer.Add(self.package_input, 0, wx.EXPAND)

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

        # Columns - adjusted widths to fit all info without scrolling
        self.results_list.InsertColumn(0, "LCSC ID", width=70)
        self.results_list.InsertColumn(1, "Name", width=200)
        self.results_list.InsertColumn(2, "Package", width=80)
        self.results_list.InsertColumn(3, "Price", width=70)
        self.results_list.InsertColumn(4, "Stock", width=70)
        self.results_list.InsertColumn(5, "Type", width=70)

        # Bind selection and sort events
        self.results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_result_selected)
        self.results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_result_activated)
        self.results_list.Bind(wx.EVT_LIST_COL_CLICK, self._on_column_click)

        # Track sort column and direction
        self.sort_column = -1
        self.sort_reverse = False

        sizer.Add(self.results_list, 1, wx.EXPAND | wx.ALL, 5)

        # Load more button
        self.load_more_btn = wx.Button(panel, label="Load More Results")
        self.load_more_btn.Bind(wx.EVT_BUTTON, self._on_load_more)
        self.load_more_btn.Enable(False)
        sizer.Add(self.load_more_btn, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_preview_panel(self, parent):
        """Create preview panel with tabs using WebView for SVG display"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Label
        label = wx.StaticText(panel, label="Component Preview")
        sizer.Add(label, 0, wx.ALL, 5)

        # Notebook for tabs
        self.preview_notebook = wx.Notebook(panel)

        # Symbol preview tab - WebView
        symbol_panel = wx.Panel(self.preview_notebook)
        symbol_sizer = wx.BoxSizer(wx.VERTICAL)
        self.symbol_webview = wx.html2.WebView.New(symbol_panel)
        self.symbol_webview.SetMinSize((400, 400))
        symbol_sizer.Add(self.symbol_webview, 1, wx.EXPAND | wx.ALL, 5)
        symbol_panel.SetSizer(symbol_sizer)
        self.preview_notebook.AddPage(symbol_panel, "Symbol")

        # Footprint preview tab - WebView
        footprint_panel = wx.Panel(self.preview_notebook)
        footprint_sizer = wx.BoxSizer(wx.VERTICAL)
        self.footprint_webview = wx.html2.WebView.New(footprint_panel)
        self.footprint_webview.SetMinSize((400, 400))
        footprint_sizer.Add(self.footprint_webview, 1, wx.EXPAND | wx.ALL, 5)
        footprint_panel.SetSizer(footprint_sizer)
        self.preview_notebook.AddPage(footprint_panel, "Footprint")

        # Specifications tab
        specs_panel = wx.Panel(self.preview_notebook)
        specs_sizer = wx.BoxSizer(wx.VERTICAL)
        self.specs_text = wx.TextCtrl(
            specs_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.TE_WORDWRAP
        )
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.specs_text.SetFont(font)
        specs_sizer.Add(self.specs_text, 1, wx.EXPAND | wx.ALL, 10)
        specs_panel.SetSizer(specs_sizer)
        self.preview_notebook.AddPage(specs_panel, "Specifications")

        sizer.Add(self.preview_notebook, 1, wx.EXPAND | wx.ALL, 5)

        # Initialize with empty content
        self._set_webview_svg(self.symbol_webview, None, "Select a component")
        self._set_webview_svg(self.footprint_webview, None, "Select a component")

        panel.SetSizer(sizer)
        return panel

    def _fit_svg_viewbox(self, svg_content: str, bbox: Optional[Dict] = None) -> str:
        """Adjust SVG viewBox to fit content tightly using bbox data"""
        import re

        if bbox:
            x = bbox.get("x", 0)
            y = bbox.get("y", 0)
            w = bbox.get("width", 100)
            h = bbox.get("height", 100)
            # Add 10% padding
            pad_x = w * 0.1
            pad_y = h * 0.1
            new_viewbox = f"{x - pad_x} {y - pad_y} {w + pad_x * 2} {h + pad_y * 2}"
            # Replace or add viewBox
            if re.search(r'viewBox="[^"]*"', svg_content):
                svg_content = re.sub(r'viewBox="[^"]*"', f'viewBox="{new_viewbox}"', svg_content)
            else:
                svg_content = svg_content.replace('<svg ', f'<svg viewBox="{new_viewbox}" ', 1)

        return svg_content

    def _strip_svg_size(self, svg_content: str) -> str:
        """Remove width/height attributes from SVG so viewBox controls aspect ratio and CSS controls size"""
        import re
        # Remove width="..." and height="..." from the opening <svg> tag
        svg_content = re.sub(r'(<svg\b[^>]*?)\s+width="[^"]*"', r'\1', svg_content)
        svg_content = re.sub(r'(<svg\b[^>]*?)\s+height="[^"]*"', r'\1', svg_content)
        return svg_content

    def _svg_to_html(self, svg_content: Optional[str], placeholder_msg: str = "") -> str:
        """Wrap SVG content in HTML for WebView display"""
        if svg_content:
            body = self._strip_svg_size(svg_content)
        else:
            body = f'<p style="color:#999;font-size:14px;">{placeholder_msg}</p>'

        return f'''<!DOCTYPE html>
<html><head><style>
  html, body {{
    margin: 0; padding: 0; width: 100%; height: 100%;
    display: flex; align-items: center; justify-content: center;
    background: #fff; overflow: hidden;
    font-family: -apple-system, sans-serif;
  }}
  svg {{
    max-width: 95%; max-height: 95%;
    width: 95%; height: auto;
  }}
</style></head>
<body>{body}</body></html>'''

    def _set_webview_svg(self, webview, svg_content: Optional[str],
                         placeholder_msg: str = "", bbox: Optional[Dict] = None):
        """Set SVG content on a WebView widget, fitting viewBox to bbox if provided"""
        if svg_content and bbox:
            svg_content = self._fit_svg_viewbox(svg_content, bbox)
        html = self._svg_to_html(svg_content, placeholder_msg)
        webview.SetPage(html, "")

    def _on_char_hook(self, event):
        """Handle key events before child widgets - ESC closes dialog"""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

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
        search_text = self.name_input.GetValue().strip()
        package = self.package_input.GetValue().strip()

        # Check if at least search text is provided
        if not search_text:
            wx.MessageBox(
                "Please enter a search term.",
                "No Search Term",
                wx.OK | wx.ICON_WARNING
            )
            return

        # Reset pagination
        self.current_page = 1
        self.search_results = []

        # Perform search
        self._perform_search(search_text, package, self.current_page)

    def _perform_search(self, search_text, package, page):
        """Perform the actual search"""
        # Show progress
        self.results_list.DeleteAllItems()
        wx.BeginBusyCursor()
        try:
            # Call API - pass search_text as component_name, package as filter
            results = self.api_client.advanced_search(
                component_name=search_text,
                value="",  # Empty
                package=package,
                manufacturer="",  # Empty
                page=page
            )

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
            wx.MessageBox(
                f"Search failed: {str(e)}",
                "Search Error",
                wx.OK | wx.ICON_ERROR
            )
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            wx.MessageBox(
                f"An error occurred: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR
            )
        finally:
            if wx.IsBusy():
                wx.EndBusyCursor()

    def _populate_results_list(self):
        """Populate results list with search results"""
        for result in self.search_results:
            index = self.results_list.GetItemCount()

            # Get data from result
            lcsc_id = result.get("lcsc", {}).get("number", result.get("uuid", ""))
            title = result.get("title", "Unknown")
            package = result.get("package", "")
            price = result.get("price", 0)
            stock_count = result.get("stockCount", 0)
            library_type = result.get("libraryType", "")

            # Format price
            price_str = f"${price:.4f}" if price > 0 else "-"

            # Format stock count
            if stock_count > 10000:
                stock_str = f"{stock_count//1000}k+"
            elif stock_count > 0:
                stock_str = str(stock_count)
            else:
                stock_str = "0"

            # Insert row
            self.results_list.InsertItem(index, lcsc_id)
            self.results_list.SetItem(index, 1, title)
            self.results_list.SetItem(index, 2, package)
            self.results_list.SetItem(index, 3, price_str)
            self.results_list.SetItem(index, 4, stock_str)
            self.results_list.SetItem(index, 5, library_type)

            # Store full result data
            self.results_list.SetItemData(index, index)

    def _on_column_click(self, event):
        """Handle column header click for sorting"""
        col = event.GetColumn()

        # Toggle sort direction if clicking same column
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        # Sort results
        self._sort_results(col, self.sort_reverse)

        # Refresh display
        self.results_list.DeleteAllItems()
        self._populate_results_list()

    def _sort_results(self, col, reverse=False):
        """Sort search results by column"""
        # Define sort keys for each column
        def get_sort_key(result):
            if col == 0:  # LCSC ID
                return result.get("lcsc", {}).get("number", "")
            elif col == 1:  # Name
                return result.get("title", "").lower()
            elif col == 2:  # Package
                return result.get("package", "").lower()
            elif col == 3:  # Price
                return result.get("price", 0)
            elif col == 4:  # Stock
                return result.get("stockCount", 0)
            elif col == 5:  # Type
                # Sort Basic before Extended
                lib_type = result.get("libraryType", "")
                return 0 if lib_type == "Basic" else 1 if lib_type == "Extended" else 2
            return ""

        self.search_results.sort(key=get_sort_key, reverse=reverse)

    def _on_load_more(self, event):
        """Load more search results"""
        self.current_page += 1

        # Get current search parameters
        search_text = self.name_input.GetValue().strip()
        package = self.package_input.GetValue().strip()

        self._perform_search(search_text, package, self.current_page)

    def _on_result_selected(self, event):
        """Handle result selection - load previews asynchronously"""
        index = event.GetIndex()
        if index < 0 or index >= len(self.search_results):
            return

        # Get selected result
        result = self.search_results[index]
        self.selected_component = result

        # Increment thread ID to invalidate previous requests
        self.preview_thread_id += 1
        current_thread_id = self.preview_thread_id

        # Show loading placeholder immediately
        self._display_previews(None, None, "Loading component information...",
                               placeholder_msg="Loading...")

        # Load previews in background thread
        thread = threading.Thread(
            target=self._load_previews_async,
            args=(result, current_thread_id),
            daemon=True
        )
        thread.start()
        self.preview_thread = thread

    def _on_result_activated(self, event):
        """Handle double-click - import directly"""
        self._on_import(event)

    def _fetch_easyeda_svgs(self, lcsc_id: str) -> Optional[List]:
        """Fetch pre-rendered SVGs from EasyEDA API (cached)"""
        if lcsc_id in self._svg_cache:
            return self._svg_cache[lcsc_id]

        try:
            url = self.EASYEDA_SVG_URL.format(lcsc_id=lcsc_id)
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                              'AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'application/json',
            })
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                self._svg_cache[lcsc_id] = None
                return None

            result = data.get("result", [])
            self._svg_cache[lcsc_id] = result
            return result

        except Exception as e:
            logger.warning(f"Failed to fetch EasyEDA SVGs: {e}")
            self._svg_cache[lcsc_id] = None
            return None

    def _load_previews_async(self, result, thread_id):
        """Load SVG previews and component data independently (runs in background thread)"""
        try:
            lcsc_id = result.get("uuid") or result.get("lcsc", {}).get("number")
            if not lcsc_id:
                logger.warning("No LCSC ID in result")
                return

            if thread_id != self.preview_thread_id:
                return

            # Check cache - show immediately if available
            if lcsc_id in self.preview_cache:
                cached = self.preview_cache[lcsc_id]
                if thread_id == self.preview_thread_id:
                    wx.CallAfter(
                        self._display_previews,
                        cached.get('symbol_svg'),
                        cached.get('footprint_svg'),
                        cached.get('specs', ''),
                        symbol_bbox=cached.get('symbol_bbox'),
                        footprint_bbox=cached.get('footprint_bbox')
                    )
                return

            # Step 1: Fetch SVGs (fast) and display immediately
            svgs = self._fetch_easyeda_svgs(lcsc_id)

            if thread_id != self.preview_thread_id:
                return

            symbol_svg = None
            footprint_svg = None
            symbol_bbox = None
            footprint_bbox = None
            if svgs:
                for entry in svgs:
                    if entry.get("docType") == 2:
                        symbol_svg = entry.get("svg")
                        symbol_bbox = entry.get("bbox")
                    elif entry.get("docType") == 4:
                        footprint_svg = entry.get("svg")
                        footprint_bbox = entry.get("bbox")

            # Show SVG previews right away (before waiting for component data)
            symbol_msg = "" if symbol_svg else ("Not available in EasyEDA" if not svgs else "No symbol preview")
            footprint_msg = "" if footprint_svg else ("Not available in EasyEDA" if not svgs else "No footprint preview")

            if thread_id == self.preview_thread_id:
                wx.CallAfter(
                    self._display_previews,
                    symbol_svg, footprint_svg, "Loading specifications...",
                    placeholder_msg=symbol_msg,
                    footprint_placeholder=footprint_msg,
                    symbol_bbox=symbol_bbox,
                    footprint_bbox=footprint_bbox
                )

            # Step 2: Fetch component data (slow - involves rate-limited API calls)
            component_data = self.api_client.search_component(lcsc_id)

            if thread_id != self.preview_thread_id:
                return

            specs_text = self._format_specifications(component_data) if component_data else ""
            if not svgs and not component_data:
                specs_text = f"Component {lcsc_id} not found in EasyEDA database."

            # Cache everything
            self.preview_cache[lcsc_id] = {
                'symbol_svg': symbol_svg,
                'footprint_svg': footprint_svg,
                'symbol_bbox': symbol_bbox,
                'footprint_bbox': footprint_bbox,
                'specs': specs_text,
                'component_data': component_data
            }

            # Update specs (SVGs already displayed)
            if thread_id == self.preview_thread_id:
                wx.CallAfter(self._update_specs, specs_text)

        except Exception as e:
            logger.error(f"Failed to load previews: {e}", exc_info=True)
            error_text = f"Failed to load component information:\n\n{str(e)}"
            if thread_id == self.preview_thread_id:
                wx.CallAfter(
                    self._display_previews, None, None, error_text,
                    placeholder_msg="Load failed"
                )

    def _format_specifications(self, component_data: Dict[str, Any]) -> str:
        """Format component data as detailed specifications text"""
        specs = []

        # Header
        specs.append("=" * 60)
        specs.append("COMPONENT SPECIFICATIONS")
        specs.append("=" * 60)
        specs.append("")

        # Basic Information
        specs.append("BASIC INFORMATION")
        specs.append("-" * 60)
        specs.append(f"LCSC ID:              {component_data.get('lcsc_id', 'N/A')}")
        specs.append(f"Name:                 {component_data.get('name', 'N/A')}")
        specs.append(f"Manufacturer:         {component_data.get('manufacturer', 'N/A')}")
        specs.append(f"Manufacturer Part:    {component_data.get('manufacturer_part', 'N/A')}")
        specs.append(f"Package:              {component_data.get('package', 'N/A')}")
        specs.append(f"Description:          {component_data.get('description', 'N/A')}")
        specs.append(f"Category:             {component_data.get('category', 'N/A')}")
        specs.append("")

        # JLCPCB Information
        specs.append("JLCPCB INFORMATION")
        specs.append("-" * 60)
        specs.append(f"Part Class:           {component_data.get('jlcpcb_class', 'N/A')}")
        smt_status = "SMT" if component_data.get('smt', False) else "Through-hole"
        specs.append(f"Mounting Type:        {smt_status}")
        specs.append(f"Stock:                {component_data.get('stock', 0):,}")
        specs.append("")

        # Pricing Information
        specs.append("PRICING")
        specs.append("-" * 60)
        prices = component_data.get('price', [])
        if prices:
            for price_tier in prices:
                qty = price_tier.get('qty', 0)
                qty_max = price_tier.get('qty_max')
                price = price_tier.get('price', 0)

                if qty_max:
                    qty_range = f"{qty}-{qty_max}"
                else:
                    qty_range = f"{qty}+"

                specs.append(f"  {qty_range:>15}:  ${price:.4f}")
        else:
            specs.append("  No pricing information available")
        specs.append("")

        # Additional Parameters (from c_para in easyeda_data)
        easyeda_data = component_data.get('easyeda_data', {})
        if easyeda_data and 'dataStr' in easyeda_data and 'head' in easyeda_data['dataStr']:
            c_para = easyeda_data['dataStr']['head'].get('c_para', {})

            # Filter out already displayed parameters
            excluded_keys = {
                'name', 'Manufacturer', 'Manufacturer Part', 'package',
                'pre', 'JLCPCB Part Class', 'Supplier', 'Supplier Part'
            }

            additional_params = {k: v for k, v in c_para.items() if k not in excluded_keys and v}

            if additional_params:
                specs.append("ADDITIONAL SPECIFICATIONS")
                specs.append("-" * 60)
                for key, value in sorted(additional_params.items()):
                    # Format key to be more readable
                    formatted_key = key.replace('_', ' ').title()
                    specs.append(f"{formatted_key:>25}: {value}")
                specs.append("")

        # Links
        specs.append("LINKS")
        specs.append("-" * 60)
        datasheet = component_data.get('datasheet', '')
        if datasheet:
            specs.append(f"Datasheet:            {datasheet}")

        url = component_data.get('url', '')
        if url:
            specs.append(f"LCSC Product Page:    {url}")
        else:
            lcsc_id = component_data.get('lcsc_id', '')
            if lcsc_id:
                specs.append(f"LCSC Product Page:    https://www.lcsc.com/product-detail/{lcsc_id}.html")

        specs.append("")
        specs.append("=" * 60)

        return "\n".join(specs)

    def _display_previews(self, symbol_svg, footprint_svg, specs_text=None,
                          placeholder_msg="", footprint_placeholder="",
                          symbol_bbox=None, footprint_bbox=None):
        """Display SVG previews and specifications"""
        fp_msg = footprint_placeholder or placeholder_msg
        self._set_webview_svg(self.symbol_webview, symbol_svg, placeholder_msg, bbox=symbol_bbox)
        self._set_webview_svg(self.footprint_webview, footprint_svg, fp_msg, bbox=footprint_bbox)

        if specs_text is not None:
            self.specs_text.SetValue(specs_text)

        self.preview_notebook.Layout()
        self.Layout()
        self.Refresh()

    def _update_specs(self, specs_text: str):
        """Update only the specifications text (called when component data finishes loading)"""
        self.specs_text.SetValue(specs_text)

    def _on_import(self, event):
        """Handle import button click - runs fetch+import in background thread"""
        if not self.selected_component:
            wx.MessageBox(
                "Please select a component from the search results.",
                "No Selection",
                wx.OK | wx.ICON_WARNING
            )
            return

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

        lcsc_id = self.selected_component.get("uuid") or self.selected_component.get("lcsc", {}).get("number")
        if not lcsc_id:
            wx.MessageBox(
                "No LCSC ID found for selected component.",
                "Import Error",
                wx.OK | wx.ICON_ERROR
            )
            return

        # Show progress dialog
        self._import_progress = wx.GenericProgressDialog(
            "Importing Component",
            f"Fetching component data for {lcsc_id}...\n\n\n\n",
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT
        )
        self._import_progress.SetSize((400, -1))

        # Run import in background thread
        thread = threading.Thread(
            target=self._import_async,
            args=(lcsc_id, import_symbol, import_footprint, import_3d),
            daemon=True
        )
        thread.start()

    def _import_async(self, lcsc_id, import_symbol, import_footprint, import_3d):
        """Fetch component data and import in background thread"""
        try:
            # Get component data from cache or fetch
            component_info = None
            if lcsc_id in self.preview_cache:
                component_info = self.preview_cache[lcsc_id].get('component_data')

            if not component_info:
                component_info = self.api_client.search_component(lcsc_id)

            if not component_info:
                wx.CallAfter(self._import_finish,
                             False, "Failed to fetch component data.")
                return

            easyeda_data = component_info.get("easyeda_data")
            if not easyeda_data:
                wx.CallAfter(self._import_finish,
                             False, "No EasyEDA data available for this component.")
                return

            wx.CallAfter(self._import_progress_update, 30, "Importing component files...")

            # Import component
            result = self.library_manager.import_component(
                easyeda_data=easyeda_data,
                component_info=component_info,
                import_symbol=import_symbol,
                import_footprint=import_footprint,
                import_3d=import_3d
            )

            # Build result message
            lines = ["Import completed!\n"]
            if result.get("symbol"):
                lines.append("Symbol: OK")
            if result.get("footprint"):
                lines.append("Footprint: OK")
            if result.get("model_3d"):
                lines.append("3D Model: OK")

            notifications = result.get("notifications", [])
            if notifications:
                lines.append("")
                lines.extend(notifications)
            lines.append("\nReopen schematic editor for symbols to appear.")

            wx.CallAfter(self._import_finish, True, "\n".join(lines))

        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            wx.CallAfter(self._import_finish, False, f"Import failed:\n{str(e)}")

    def _import_progress_update(self, value, message):
        """Update progress dialog (called on main thread)"""
        if self._import_progress:
            self._import_progress.Update(value, message)

    def _import_finish(self, success, message):
        """Show final result inside the progress dialog (called on main thread)"""
        if self._import_progress:
            # Update to 100% with result message, user clicks OK to dismiss
            self._import_progress.Update(100, message)
            self._import_progress.Destroy()
            self._import_progress = None

        if success:
            self.EndModal(wx.ID_OK)
