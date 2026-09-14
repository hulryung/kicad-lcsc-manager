#!/usr/bin/env python3
"""
Update metadata files for KiCad PCM custom repository.

This script records a release's packages in metadata.json and packages.json
(one version entry per build; see pcm_builds.py) and refreshes
repository.json. It works on the files in the current directory.

Usage:
    python scripts/update-metadata.py <version> <package.zip>...

Example:
    python scripts/update-metadata.py 0.9.0 release/kicad-lcsc-manager-0.9.0.zip \\
        release/kicad-lcsc-manager-1.9.0-ipc.zip
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pcm_builds import builds_for, parse_version, release_entry, sha256_of, version_clashes


def release_entries(version: str, packages):
    """One entry per build of the release, from its zip. Every build must be
    there, and nothing else."""
    builds = builds_for(version)
    given = {Path(p).name: Path(p) for p in packages}
    expected = [b.zip_name for b in builds]
    if sorted(given) != sorted(expected):
        raise ValueError(f"v{version} is published as {expected}; got {sorted(given)}")
    for path in given.values():
        if not path.is_file():
            raise ValueError(f"package file not found: {path}")
    return [release_entry(b, given[b.zip_name]) for b in builds]


def record(versions: list, entries: list) -> list:
    """versions with entries added: an entry for a version already listed
    replaces it in place, new ones go first, newest first. A version already
    listed for the other runtime is refused."""
    clashes = version_clashes(entries, versions)
    if clashes:
        raise ValueError("; ".join(clashes))
    result = list(versions)
    new = []
    for entry in entries:
        for i, old in enumerate(result):
            if old["version"] == entry["version"]:
                result[i] = entry
                break
        else:
            new.append(entry)
    new.sort(key=lambda e: parse_version(e["version"]), reverse=True)
    return new + result


VERSION_LISTS = {
    "metadata.json": lambda data: data["versions"],
    "packages.json": lambda data: data["packages"][0]["versions"],
}


def update_version_lists(entries) -> None:
    """Record the entries in metadata.json and packages.json: both or
    neither (raises ValueError before writing anything)."""
    updated = {}
    for name, get_versions in VERSION_LISTS.items():
        data = json.loads(Path(name).read_text(encoding="utf-8"))
        versions = get_versions(data)
        versions[:] = record(versions, entries)
        updated[name] = data
    for name, data in updated.items():
        Path(name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"✓ Updated {name}")


def update_repository_json() -> None:
    """Point repository.json at the new packages.json."""
    repository_file = Path("repository.json")
    repo = json.loads(repository_file.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    repo["packages"]["sha256"] = sha256_of(Path("packages.json"))
    repo["packages"]["update_time_utc"] = now.strftime("%Y-%m-%d %H:%M:%S")
    repo["packages"]["update_timestamp"] = int(now.timestamp())
    repository_file.write_text(json.dumps(repo, indent=2) + "\n", encoding="utf-8")
    print(f"✓ Updated {repository_file}")


def main(argv) -> int:
    if len(argv) < 3:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    version = argv[1]
    try:
        entries = release_entries(version, argv[2:])
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    for name in ("metadata.json", "packages.json", "repository.json"):
        if not Path(name).exists():
            print(f"ERROR: {name} not found", file=sys.stderr)
            return 1

    for entry in entries:
        print(f"v{version}: {entry['version']} ({entry['runtime']}) "
              f"sha256 {entry['download_sha256']}, {entry['download_size']} bytes")
    try:
        update_version_lists(entries)
    except ValueError as e:
        print(f"ERROR: v{version} can't be published: {e}", file=sys.stderr)
        return 1
    update_repository_json()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
