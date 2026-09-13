"""
Safe, idempotent edits to KiCad library tables (sym-lib-table / fp-lib-table).

Used to register the shared LCSC library in KiCad's *global* tables, which
every project reads. Those files belong to KiCad and back every library the
user has, so edits here are deliberately conservative:

- only a file that already looks like the right kind of table is touched;
- an entry with our nickname that someone else created is never modified;
- the first edit of an existing file leaves a one-time backup beside it;
- writes go to a temporary file that atomically replaces the table.

Kept free of wx/pcbnew imports so it can be unit-tested outside KiCad.
"""
import os
import re
import shutil
from pathlib import Path

# Written into the descr of entries we create, so we can recognise — and
# later update — our own rows without ever touching the user's.
OWNER_TAG = "LCSC Manager"

BACKUP_SUFFIX = ".lcsc_manager.bak"

_HEADERS = {"sym": "sym_lib_table", "fp": "fp_lib_table"}
_STRING = r'"((?:[^"\\]|\\.)*)"'
_NAME_RE = re.compile(r"^\s*\(lib\s+\(name\s+" + _STRING + r"\)")
_URI_RE = re.compile(r"\(uri\s+" + _STRING + r"\)")
_DESCR_RE = re.compile(r"\(descr\s+" + _STRING + r"\)")

ADDED = "added"
PRESENT = "present"
UPDATED = "updated"
CONFLICT = "conflict"


class LibTableError(Exception):
    """The table exists but isn't something we can safely edit."""


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _unescape(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


def _entry_line(nickname: str, uri: str, descr: str) -> str:
    return (f'\t(lib (name "{_escape(nickname)}") (type "KiCad") '
            f'(uri "{_escape(uri)}") (options "") (descr "{_escape(descr)}"))\n')


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".lcsc_manager.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def ensure_lib_entry(table_path: Path, kind: str, nickname: str, uri: str,
                     descr: str) -> str:
    """
    Make sure `table_path` maps `nickname` to `uri`.

    Args:
        table_path: the sym-lib-table or fp-lib-table file
        kind: "sym" or "fp"
        nickname: library nickname
        uri: library URI, written verbatim (may contain ${VARS})
        descr: description; OWNER_TAG is prepended if missing

    Returns:
        ADDED     — a new row was written (or the table was created)
        PRESENT   — a row with this nickname and URI already exists
        UPDATED   — our own row pointed elsewhere and now points at `uri`
        CONFLICT  — a row with this nickname exists that we didn't create;
                    left untouched

    Raises:
        LibTableError: the file exists but isn't a table of this kind, or our
                       row can't be edited safely.
    """
    header = _HEADERS[kind]
    if not descr.startswith(OWNER_TAG):
        descr = f"{OWNER_TAG} {descr}"

    if not table_path.exists():
        table_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(table_path, f"({header}\n\t(version 7)\n"
                                  f"{_entry_line(nickname, uri, descr)})\n")
        return ADDED

    text = table_path.read_text(encoding="utf-8")
    if not text.lstrip().startswith("(" + header):
        raise LibTableError(f"{table_path} is not a {header}")

    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        match = _NAME_RE.match(line)
        if not match or _unescape(match.group(1)) != nickname:
            continue
        uri_match = _URI_RE.search(line)
        if uri_match is None:
            raise LibTableError(
                f"the {nickname} row in {table_path} spans several lines")
        if _unescape(uri_match.group(1)) == uri:
            return PRESENT
        descr_match = _DESCR_RE.search(line)
        if not descr_match or OWNER_TAG not in _unescape(descr_match.group(1)):
            return CONFLICT
        _backup_once(table_path)
        new_line = (line[:uri_match.start(1)] + _escape(uri)
                    + line[uri_match.end(1):])
        lines[index] = new_line
        _atomic_write(table_path, "".join(lines))
        return UPDATED

    close = text.rstrip().rfind(")")
    if close < 0:
        raise LibTableError(f"{table_path} has no closing parenthesis")
    body = text[:close].rstrip("\n\t ") + "\n"
    _backup_once(table_path)
    _atomic_write(table_path,
                  body + _entry_line(nickname, uri, descr) + text[close:].lstrip())
    return ADDED


def _backup_once(table_path: Path) -> None:
    """Keep a copy of the table as it was before our first edit."""
    backup = table_path.with_name(table_path.name + BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(table_path, backup)


def read_lib_uri(table_path: Path, nickname: str):
    """Return the URI a table maps `nickname` to, or None."""
    if not table_path.exists():
        return None
    for line in table_path.read_text(encoding="utf-8").splitlines():
        match = _NAME_RE.match(line)
        if match and _unescape(match.group(1)) == nickname:
            uri_match = _URI_RE.search(line)
            return _unescape(uri_match.group(1)) if uri_match else None
    return None
