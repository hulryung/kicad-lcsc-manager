"""
The two builds each release publishes to KiCad's Plugin and Content Manager
(#19), and how they're put together. Used by build-packages.py,
update-metadata.py and assemble-ipc-plugin.py.

A tag vX.Y.Z makes
  - the SWIG build, version X.Y.Z, for KiCad 9 and 10, and
  - the IPC build, version (X+1).Y.Z, for KiCad 11 and its 10.99 nightlies.
Both come from the same code. KiCad finds a package version by its version
string alone (installing, updating and the compatibility check all look it
up that way), so the two builds can't share one. The IPC build is the same
release with the major number raised by one.
"""
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO / "plugins" / "lcsc_manager"
IPC_DIR = REPO / "ipc"
ROOT_METADATA = REPO / "metadata.json"
PACKAGES_JSON = REPO / "packages.json"
IPC_FILES = ("plugin.json", "requirements.txt")
DOWNLOADS = "https://github.com/hulryung/kicad-lcsc-manager/releases/download"
IGNORED = ("__pycache__", "*.pyc", ".DS_Store", ".pytest_cache", "*.egg-info")

_RELEASE = re.compile(r"^(\d{1,4})\.(\d{1,4})\.(\d{1,6})$")    # the PCM's version pattern
_VERSION_LINE = re.compile(r'^__version__ = "[^"]*"$', re.M)


def parse_version(text: str):
    match = _RELEASE.match(text)
    if not match:
        raise ValueError(f"not a release version (X.Y.Z): {text!r}")
    return tuple(int(part) for part in match.groups())


@dataclass(frozen=True)
class Build:
    runtime: str                    # "swig" or "ipc"
    version: str                    # this build's version in the PCM
    release: str                    # the tag it's built from, without the "v"
    kicad_version: str              # oldest KiCad it runs on
    kicad_version_max: Optional[str] = None

    @property
    def zip_name(self) -> str:
        suffix = "-ipc" if self.runtime == "ipc" else ""
        return f"kicad-lcsc-manager-{self.version}{suffix}.zip"

    @property
    def download_url(self) -> str:
        return f"{DOWNLOADS}/v{self.release}/{self.zip_name}"

    def version_entry(self) -> dict:
        """The build's entry in a PCM versions list, minus the download fields
        (which is what goes in the package's own metadata.json)."""
        entry = {"version": self.version, "status": "stable",
                 "runtime": self.runtime, "kicad_version": self.kicad_version}
        if self.kicad_version_max:
            entry["kicad_version_max"] = self.kicad_version_max
        return entry


def builds_for(release: str) -> List[Build]:
    major, minor, patch = parse_version(release)
    return [
        # KiCad 11 has no SWIG API. (It treats any SWIG plugin as incompatible
        # anyway; the maximum says so to older KiCads too.)
        Build("swig", release, release, "9.0", "10.99"),
        # 10.99 is KiCad 11's nightlies. KiCad 10 could run this build as well,
        # but it would then take over from the SWIG build there, and that one
        # doesn't need the API server switched on.
        Build("ipc", f"{major + 1}.{minor}.{patch}", release, "10.99"),
    ]


def version_clashes(entries, published) -> List[str]:
    """Entries whose version is already published for the other runtime.
    With the IPC build at major + 1, a later tag with a raised major number
    (v1.9.0 after v0.9.0) would publish its SWIG build under the version of
    an earlier IPC build, and KiCad would mix the two up."""
    def runtime(entry):
        return entry.get("runtime", "swig")     # KiCad's default, and older entries'
    runtime_of = {v["version"]: runtime(v) for v in published}
    return [f"{e['version']} is already taken by a published {runtime_of[e['version']].upper()} "
            f"build (this is the {runtime(e).upper()} build)"
            for e in entries
            if e["version"] in runtime_of and runtime_of[e["version"]] != runtime(e)]


# ─── the IPC plugin folder ────────────────────────────────────────────

def missing_files(folder: Path) -> List[str]:
    """Files the folder's plugin.json refers to that aren't there."""
    config = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
    wanted = set()
    for action in config["actions"]:
        wanted.add(action["entrypoint"])
        wanted.update(action.get("icons-light", []))
        wanted.update(action.get("icons-dark", []))
    return sorted(p for p in wanted if not (folder / p).is_file())


def assemble_ipc_plugin(dest: Path, package_dir: Path = PACKAGE_DIR,
                        ipc_dir: Path = IPC_DIR) -> Path:
    """The plugin package plus ipc/plugin.json and ipc/requirements.txt."""
    if dest.exists():
        raise FileExistsError(f"{dest} already exists; remove it first")
    shutil.copytree(package_dir, dest, ignore=shutil.ignore_patterns(*IGNORED))
    for name in IPC_FILES:
        shutil.copy2(ipc_dir / name, dest / name)
    missing = missing_files(dest)
    if missing:
        shutil.rmtree(dest)
        raise ValueError("plugin.json refers to missing files: " + ", ".join(missing))
    return dest


# ─── package zips ─────────────────────────────────────────────────────

def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def installed_size(zip_path: Path) -> int:
    """Bytes the PCM extracts: everything under plugins/ and resources/."""
    with zipfile.ZipFile(zip_path) as zf:
        return sum(info.file_size for info in zf.infolist()
                   if info.filename.startswith(("plugins/", "resources/")))


def release_entry(build: Build, zip_path: Path) -> dict:
    """The build's full entry for metadata.json and packages.json."""
    entry = build.version_entry()
    entry.update(download_url=build.download_url,
                 download_sha256=sha256_of(zip_path),
                 download_size=zip_path.stat().st_size,
                 install_size=installed_size(zip_path))
    return entry


def package_metadata(build: Build, root_metadata: Path = ROOT_METADATA) -> dict:
    """The zip's metadata.json: the package fields of the repository's
    metadata.json, with just this build's version."""
    data = json.loads(root_metadata.read_text(encoding="utf-8"))
    data = {key: value for key, value in data.items() if key != "versions"}
    data["versions"] = [build.version_entry()]
    return data


def stamp_version(init_py: Path, version: str) -> None:
    text, count = _VERSION_LINE.subn(f'__version__ = "{version}"',
                                     init_py.read_text(encoding="utf-8"))
    if count != 1:
        raise ValueError(f"expected one __version__ line in {init_py}, found {count}")
    init_py.write_text(text, encoding="utf-8")


def check_package(build: Build, zip_path: Path) -> None:
    """Raise ValueError listing whatever is wrong with a built zip."""
    problems = []
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        junk = sorted(n for n in names if "__pycache__/" in n or n.endswith((".pyc", ".DS_Store")))
        if junk:
            problems.append(f"bytecode or Finder files: {junk[:5]}")
        for required in ("metadata.json", "resources/icon.png", "plugins/__init__.py"):
            if required not in names:
                problems.append(f"no {required}")
        if not any(n.startswith("plugins/lib/") for n in names):
            problems.append("no bundled dependencies (plugins/lib/)")
        if "metadata.json" in names:
            versions = json.loads(zf.read("metadata.json"))["versions"]
            if versions != [build.version_entry()]:
                problems.append(f"metadata.json versions are {versions}")
        if "plugins/__init__.py" in names:
            init = zf.read("plugins/__init__.py").decode("utf-8")
            if f'__version__ = "{build.version}"' not in init:
                problems.append(f"plugins/__init__.py doesn't say version {build.version}")
        if build.runtime == "ipc":
            if "plugins/requirements.txt" not in names:
                problems.append("no plugins/requirements.txt")
            if "plugins/plugin.json" not in names:
                problems.append("no plugins/plugin.json")
            else:
                config = json.loads(zf.read("plugins/plugin.json"))
                for action in config["actions"]:
                    files = [action["entrypoint"], *action.get("icons-light", []),
                             *action.get("icons-dark", [])]
                    problems += [f"plugin.json refers to missing {f}"
                                 for f in files if f"plugins/{f}" not in names]
        else:
            # plugin.json would switch the SWIG plugin off (see __init__.py).
            problems += [f"SWIG build contains plugins/{f}" for f in IPC_FILES
                         if f"plugins/{f}" in names]
    if problems:
        raise ValueError(f"{zip_path.name}: " + "; ".join(problems))


def _write_zip(folder: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(folder).as_posix())


def build_package(build: Build, outdir: Path, package_dir: Path = PACKAGE_DIR,
                  ipc_dir: Path = IPC_DIR, root_metadata: Path = ROOT_METADATA) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        plugins = stage / "plugins"
        if build.runtime == "ipc":
            assemble_ipc_plugin(plugins, package_dir, ipc_dir)
        else:
            shutil.copytree(package_dir, plugins, ignore=shutil.ignore_patterns(*IGNORED))
        stamp_version(plugins / "__init__.py", build.version)
        (stage / "resources").mkdir()
        shutil.copy2(package_dir / "plugin_resources" / "icon.png", stage / "resources" / "icon.png")
        (stage / "metadata.json").write_text(
            json.dumps(package_metadata(build, root_metadata), indent=2) + "\n", encoding="utf-8")
        zip_path = outdir / build.zip_name
        _write_zip(stage, zip_path)
    check_package(build, zip_path)
    return zip_path


def build_packages(release: str, outdir: Path, package_dir: Path = PACKAGE_DIR,
                   ipc_dir: Path = IPC_DIR, root_metadata: Path = ROOT_METADATA,
                   packages_json: Path = PACKAGES_JSON) -> List[Dict]:
    """Build every zip for a release into outdir and describe them in
    outdir/builds.json."""
    builds = builds_for(release)
    # Checked again on the latest main when the entries are recorded; this is
    # to stop a bad tag before its GitHub release is created.
    if packages_json.exists():
        published = json.loads(packages_json.read_text(encoding="utf-8"))["packages"][0]["versions"]
        clashes = version_clashes([b.version_entry() for b in builds], published)
        if clashes:
            raise ValueError(f"v{release} can't be published: " + "; ".join(clashes))
    lib = package_dir / "lib"
    if not lib.is_dir() or not any(lib.iterdir()):
        raise ValueError(f"{lib} is empty; run scripts/bundle-dependencies.sh first")
    outdir.mkdir(parents=True, exist_ok=True)
    described = []
    for build in builds:
        zip_path = build_package(build, outdir, package_dir, ipc_dir, root_metadata)
        described.append(dict(release_entry(build, zip_path), zip=zip_path.name))
    (outdir / "builds.json").write_text(json.dumps(described, indent=2) + "\n", encoding="utf-8")
    return described
