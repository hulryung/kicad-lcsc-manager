"""
The footprint detail window: EasyEDA's footprint drawing at any zoom, a
ruler for point-to-point distances (snapping to pad centres and corners),
and the part's 3D model standing on the footprint.

The page itself is plugin_resources/footprint_viewer.html; this dialog
feeds it (see footprint_viewer.py for the payload) and fetches the 3D
model in the background, pushing it into the page when it arrives.
"""
import json
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import wx

from .footprint_viewer import (
    mesh_payload, parse_obj_mesh, viewer_html, viewer_payload, to_js_json,
)
from .utils.logger import get_logger
from .utils.ui import fit_to_screen

try:
    import wx.html2
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

logger = get_logger()

TEMPLATE_PATH = Path(__file__).parent / "plugin_resources" / "footprint_viewer.html"


def new_webview(parent):
    """A WebView for the viewer page. On Windows wx defaults to the old
    Internet Explorer engine, which has no WebGL; ask for Edge (WebView2)
    when it is there. Returns None when no WebView backend is available."""
    if not HAS_WEBVIEW:
        return None
    backend = wx.html2.WebViewBackendDefault
    edge = getattr(wx.html2, "WebViewBackendEdge", None)
    try:
        if edge and wx.html2.WebView.IsBackendAvailable(edge):
            backend = edge
    except Exception:
        pass
    try:
        return wx.html2.WebView.New(parent, backend=backend)
    except Exception as e:
        logger.warning(f"WebView backend unavailable: {e}")
        return None


class FootprintDetailDialog(wx.Dialog):
    """Opened from the search dialog's footprint preview.

    Args:
        lcsc_id, title: for the heading
        svg, bbox: the footprint preview as fetched from EasyEDA
        component_data: search_component() result if already loaded
        get_component_data: fetches it when it was not (runs in a thread)
        mesh_cache: dict shared across openings, uuid -> parsed mesh
    """

    def __init__(self, parent, lcsc_id: str, title: str, svg: str,
                 bbox: Optional[Dict[str, Any]] = None,
                 component_data: Optional[Dict[str, Any]] = None,
                 get_component_data: Optional[Callable[[], Optional[Dict[str, Any]]]] = None,
                 mesh_cache: Optional[Dict[str, Dict[str, Any]]] = None):
        super().__init__(parent, title=f"Footprint — {lcsc_id}" + (f"  {title}" if title else ""),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.lcsc_id = lcsc_id
        self.part_title = title or ""
        self.svg = svg
        self.bbox = bbox
        self.component_data = component_data
        self._get_component_data = get_component_data
        self._mesh_cache = mesh_cache if mesh_cache is not None else {}
        self._closing = False
        self._page_has_part_data = component_data is not None

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.webview = new_webview(self)
        if self.webview is None:
            note = wx.StaticText(self, label=(
                "The footprint viewer needs the wxPython WebView backend, "
                "which is not available here."))
            sizer.Add(note, 1, wx.ALL | wx.ALIGN_CENTER, 20)
        else:
            sizer.Add(self.webview, 1, wx.EXPAND)
        self.SetSizer(sizer)
        fit_to_screen(self, (1100, 800), (640, 480))
        self.CenterOnParent()
        # No Esc-to-close here: inside the page Esc clears the ruler.
        self.Bind(wx.EVT_CLOSE, self._on_close)

        if self.webview is not None:
            self._set_page(model=None, status="loading")
            threading.Thread(target=self._load_model, daemon=True).start()

    # ------------------------------------------------------------ the page

    def _set_page(self, model: Optional[Dict[str, Any]], status: str):
        payload = viewer_payload(self.lcsc_id, self.part_title, self.svg, self.bbox,
                                 self.component_data, model, status)
        self._page_has_part_data = self.component_data is not None
        try:
            template = TEMPLATE_PATH.read_text(encoding="utf-8")
            html = viewer_html(template, payload)
        except Exception as e:
            logger.error(f"Footprint viewer page could not be built: {e}", exc_info=True)
            html = f"<html><body><p>The footprint viewer could not be built: {e}</p></body></html>"
        self.webview.SetPage(html, "")

    def _run_script(self, script: str) -> bool:
        """Run JS in the page; False when this wx can't or the page refused."""
        run = getattr(self.webview, "RunScript", None)
        if run is None:
            return False
        try:
            result = run(script)
        except Exception as e:
            logger.debug(f"RunScript failed: {e}")
            return False
        if isinstance(result, tuple):       # wxPython returns (ok, value)
            return bool(result[0])
        return bool(result)

    # ------------------------------------------------------------ the model

    def _load_model(self):
        """Background: find the part's 3D model, download and parse it."""
        model = None
        status = "none"
        try:
            if self.component_data is None and self._get_component_data is not None:
                self.component_data = self._get_component_data()
            easyeda = (self.component_data or {}).get("easyeda_data") or {}
            from .converters.model_3d_converter import (
                ENDPOINT_3D_MODEL_OBJ, Model3DConverter)
            converter = Model3DConverter()
            info = converter._extract_3d_model_info(easyeda) if easyeda else None
            if info:
                status = "failed"
                mesh = self._mesh_cache.get(info["uuid"])
                if mesh is None:
                    obj = converter._download_obj(ENDPOINT_3D_MODEL_OBJ.format(uuid=info["uuid"]))
                    mesh = parse_obj_mesh(obj or "")
                    if mesh:
                        self._mesh_cache[info["uuid"]] = mesh
                if mesh:
                    model = mesh_payload(mesh, info)
                    status = "ready"
        except Exception as e:
            logger.warning(f"3D model for {self.lcsc_id} not shown: {e}")
            status = "failed"
        wx.CallAfter(self._model_loaded, model, status)

    def _model_loaded(self, model: Optional[Dict[str, Any]], status: str):
        if self._closing or self.webview is None:
            return
        if not self._page_has_part_data and self.component_data is not None:
            # The page opened before the pad data was known: rebuild it so the
            # ruler can snap and the origin is right.
            self._set_page(model, status)
            return
        if model is not None:
            if self._run_script(f"window.lcscSetModel({to_js_json(model)}); true"):
                return
        elif self._run_script(f"window.lcscSetModelStatus({json.dumps(status)}); true"):
            return
        self._set_page(model, status)      # no RunScript on this wx

    # ------------------------------------------------------------ closing

    def _on_close(self, event):
        self._closing = True
        if self.IsModal():
            self.EndModal(wx.ID_CLOSE)
        else:
            self.Destroy()
