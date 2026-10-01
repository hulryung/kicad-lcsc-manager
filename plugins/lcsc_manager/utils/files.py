"""
File helpers shared by everything that writes into the user's libraries.

Kept free of wx/pcbnew imports so it can be unit-tested outside KiCad.
"""
import os
from pathlib import Path


def atomic_write_text(path: Path, text: str) -> None:
    """Write text to path so that a crash or a full disk can't leave a
    half-written file: the text goes to a temporary file next to it, which
    then replaces path in one step."""
    tmp = path.with_name(path.name + ".lcsc_manager.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def sexpr_escape(value) -> str:
    """Escape a value for use inside a quoted string of a KiCad
    S-expression file ("..."). Without this, a part description such as
    `10k "thick film"` ends the string early and KiCad can no longer load
    the file it was written into."""
    text = "" if value is None else str(value)
    return (text.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\r\n", "\\n")
                .replace("\n", "\\n")
                .replace("\r", "\\n"))
