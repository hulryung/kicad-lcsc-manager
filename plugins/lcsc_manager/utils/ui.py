"""
Small wx helpers shared by the dialogs: colours that stay readable in dark
mode, and window sizes that fit the screen.

`clamp_size` is free of wx so it can be unit-tested; the rest imports wx
when called.
"""
from typing import Tuple

Size = Tuple[int, int]

# (light theme, dark theme). The light values are the ones the dialogs
# always used; on a dark window background they were close to unreadable.
_STATUS_COLOURS = {
    "ok":    ((0, 110, 0), (120, 205, 120)),
    "info":  ((20, 80, 160), (125, 175, 245)),
    "warn":  ((150, 90, 0), (235, 175, 80)),
    "muted": ((100, 100, 100), (170, 170, 170)),
}


def is_dark() -> bool:
    """Whether the system (and so KiCad's dialogs) uses a dark theme."""
    import wx
    try:
        return bool(wx.SystemSettings.GetAppearance().IsDark())
    except Exception:
        # Older wx: judge by the window background itself.
        colour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        return (colour.Red() + colour.Green() + colour.Blue()) / 3 < 128


def status_colour(kind: str):
    """A text colour for "ok", "info", "warn" or "muted" that is readable on
    the current theme's background."""
    import wx
    light, dark = _STATUS_COLOURS[kind]
    return wx.Colour(*(dark if is_dark() else light))


def clamp_size(size: Size, min_size: Size, area: Size,
               margin: int = 40) -> Tuple[Size, Size]:
    """Shrink a window's size and minimum size to what fits in `area` (the
    usable part of the screen), keeping `margin` pixels free.

    Returns:
        (size, min_size), with min_size never larger than size
    """
    limit = (max(200, area[0] - margin), max(200, area[1] - margin))
    fitted = (min(size[0], limit[0]), min(size[1], limit[1]))
    fitted_min = (min(min_size[0], fitted[0]), min(min_size[1], fitted[1]))
    return fitted, fitted_min


def fit_to_screen(window, size: Size, min_size: Size) -> None:
    """Give a dialog its preferred size, or less on a small screen. A fixed
    1400x900 with a 1200x800 minimum put the buttons off-screen on a
    1366x768 laptop, where they couldn't be reached."""
    import wx
    index = wx.Display.GetFromWindow(window)
    if index == wx.NOT_FOUND:
        parent = window.GetParent()
        index = wx.Display.GetFromWindow(parent) if parent else wx.NOT_FOUND
    display = wx.Display(index if index != wx.NOT_FOUND else 0)
    area = display.GetClientArea()
    fitted, fitted_min = clamp_size(size, min_size, (area.width, area.height))
    window.SetMinSize(fitted_min)
    window.SetSize(fitted)
