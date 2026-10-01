"""
Safe edits to a KiCad symbol library file (.kicad_sym).

The library holds every symbol the user has imported, and usually symbols
they have edited since, so edits here are deliberately conservative:

- a file that isn't a symbol library, or can't be parsed, is never written
  to (it used to be emptied);
- importing a part again replaces its symbol instead of adding a second
  copy;
- two different parts never share a symbol name;
- writes go to a temporary file that atomically replaces the library.

Kept free of wx/pcbnew imports so it can be unit-tested outside KiCad.
"""
import re
import threading
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from ..utils.files import atomic_write_text

# Imports run on worker threads (the search dialog's, the BOM dialog's), and
# each one reads the library, changes it and writes it back.
LOCK = threading.RLock()

_HEADER = "(kicad_symbol_lib"
_STRING = r'"(?:[^"\\]|\\.)*"'
# Strings first, so parentheses and quotes inside them aren't counted.
_TOKEN = re.compile(_STRING + r'|[()"]')
_SYMBOL_HEAD = re.compile(r'\(symbol\s+"((?:[^"\\]|\\.)*)"')
_LCSC_PROPERTY = re.compile(r'\(property\s+"LCSC"\s+"((?:[^"\\]|\\.)*)"')


class SymbolLibraryError(Exception):
    """The file exists but isn't a symbol library we can safely edit."""


def untouched_message(error: Exception) -> str:
    """What to tell the user when a library was refused."""
    return (f"{error}. The file was left as it is; fix or move it, or choose "
            f"another symbol library under Settings.")


class Symbol(NamedTuple):
    name: str
    lcsc_id: str        # its "LCSC" property, "" if it has none
    start: int          # span of the (symbol ...) form in the library text
    end: int


def _unescape(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


def _scan(text: str, what: str) -> Tuple[List[Symbol], int]:
    """The top-level symbols of a library text and the index of the
    library's closing parenthesis."""
    if not text.lstrip().startswith(_HEADER):
        raise SymbolLibraryError(f"{what} is not a KiCad symbol library")
    symbols: List[Symbol] = []
    depth = 0
    current = None          # (name, start) of the top-level symbol being read
    close = -1
    for match in _TOKEN.finditer(text):
        token = match.group()
        if token == "(":
            if close >= 0:
                raise SymbolLibraryError(f"{what} has content after the library ends")
            depth += 1
            if depth == 2:
                head = _SYMBOL_HEAD.match(text, match.start())
                current = (_unescape(head.group(1)), match.start()) if head else None
        elif token == ")":
            if depth == 2 and current is not None:
                name, start = current
                body = text[start:match.end()]
                lcsc = _LCSC_PROPERTY.search(body)
                symbols.append(Symbol(name, _unescape(lcsc.group(1)) if lcsc else "",
                                      start, match.end()))
                current = None
            depth -= 1
            if depth < 0:
                raise SymbolLibraryError(f"{what} has unbalanced parentheses")
            if depth == 0:
                close = match.start()
        elif token == '"':
            raise SymbolLibraryError(f"{what} has an unterminated string")
    if depth != 0 or close < 0:
        raise SymbolLibraryError(f"{what} has unbalanced parentheses")
    return symbols, close


def _read(library_path: Path) -> Optional[str]:
    """The library's text, or None when there's no library yet (no file, or
    an empty one)."""
    if not library_path.exists():
        return None
    text = library_path.read_text(encoding="utf-8-sig")     # tolerate a BOM
    return text if text.strip() else None


def list_symbols(library_path: Path) -> List[Symbol]:
    """The symbols in a library; [] if it doesn't exist yet.

    Raises:
        SymbolLibraryError: the file isn't a parseable symbol library.
    """
    text = _read(library_path)
    if text is None:
        return []
    return _scan(text, str(library_path))[0]


def choose_symbol_name(library_path: Path, wanted: str, lcsc_id: str) -> str:
    """The name to store a part's symbol under.

    - The part is already in the library: its current name, so the import
      replaces it and schematics that use it keep working.
    - `wanted` is free: `wanted`.
    - `wanted` belongs to another part (two parts with the same description,
      say a 0402 and a 0603 resistor): `wanted` plus the LCSC number.
    """
    symbols = list_symbols(library_path)
    if lcsc_id:
        for symbol in symbols:
            if symbol.lcsc_id == lcsc_id:
                return symbol.name
    taken: Dict[str, str] = {s.name: s.lcsc_id for s in symbols}
    if wanted not in taken:
        return wanted
    candidate = f"{wanted}_{lcsc_id}" if lcsc_id else f"{wanted}_2"
    number = 2
    while candidate in taken and taken[candidate] != lcsc_id:
        number += 1
        candidate = f"{wanted}_{lcsc_id}_{number}" if lcsc_id else f"{wanted}_{number}"
    return candidate


def put_symbol(library_path: Path, symbol_library_text: str) -> str:
    """Add the symbol in `symbol_library_text` (a complete one-symbol
    library, as the converter produces) to the library at `library_path`,
    replacing any symbol of the same name.

    Returns:
        "created" (new library), "added" or "replaced".

    Raises:
        SymbolLibraryError: the existing file isn't a parseable symbol
            library. It is left exactly as it was.
    """
    new_symbols, _ = _scan(symbol_library_text, "the converted symbol")
    if len(new_symbols) != 1:
        raise SymbolLibraryError(
            f"expected one converted symbol, got {len(new_symbols)}")
    new = new_symbols[0]
    block = symbol_library_text[new.start:new.end]

    with LOCK:
        library_path.parent.mkdir(parents=True, exist_ok=True)
        text = _read(library_path)
        if text is None:
            atomic_write_text(library_path, symbol_library_text)
            return "created"

        symbols, close = _scan(text, str(library_path))
        same = [s for s in symbols if s.name == new.name]
        if same:
            # Replace the first; drop any further copies (older versions
            # appended a duplicate on every re-import).
            pieces = []
            position = 0
            for index, symbol in enumerate(same):
                pieces.append(text[position:symbol.start])
                if index == 0:
                    pieces.append(block)
                else:
                    pieces[-1] = pieces[-1].rstrip(" \t\n")
                position = symbol.end
            pieces.append(text[position:])
            atomic_write_text(library_path, "".join(pieces))
            return "replaced"

        head = text[:close].rstrip(" \t\n")
        atomic_write_text(library_path, f"{head}\n  {block}\n{text[close:]}")
        return "added"
