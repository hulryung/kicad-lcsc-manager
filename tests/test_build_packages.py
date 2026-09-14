"""Tests for the release packages (#19). One tag, vX.Y.Z, makes two zips
(scripts/pcm_builds.py, build-packages.py):

    SWIG build  X.Y.Z      KiCad 9 and 10
    IPC build   (X+1).Y.Z  KiCad 11 and its 10.99 nightlies

and update-metadata.py records one PCM entry for each. The version numbers
differ because KiCad finds a package version by its version string alone.

The zips are built from a copy of the plugin package with a stand-in lib/,
so the bundled dependencies aren't needed.

Run with: python3 tests/test_build_packages.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pcm_builds
from pcm_builds import builds_for

# KiCad's PCM schema (pcm.v1 and v2, "PackageVersion"), which KiCad checks
# packages.json and a package's own metadata.json against.
PCM_VERSION = re.compile(r"^\d{1,4}(\.\d{1,4}(\.\d{1,6})?)?$")
PCM_KICAD_VERSION = re.compile(r"^\d{1,2}(\.\d{1,2}(\.\d{1,2})?)?$")
PCM_VERSION_KEYS = {"version", "version_epoch", "download_url", "download_sha256",
                    "download_size", "install_size", "status", "platforms", "runtime",
                    "kicad_version", "kicad_version_max", "keep_on_update"}


def _kicad_tuple(text, fill):
    """How PLUGIN_CONTENT_MANAGER::PreparePackage reads a version bound:
    missing parts are 0 for the minimum and 999 for the maximum."""
    parts = [int(p) for p in text.split(".")]
    return tuple(parts + [fill] * (3 - len(parts)))


def compatible(entry, kicad):
    """KiCad's compatibility rule for a plugin version. Builds from master
    (10.99 and 11) also turn down every SWIG plugin (UsesSWIGRuntime)."""
    if _kicad_tuple(entry["kicad_version"], 0) > kicad:
        return False
    if "kicad_version_max" in entry and _kicad_tuple(entry["kicad_version_max"], 999) < kicad:
        return False
    if kicad >= (10, 99, 0) and entry.get("runtime", "swig") == "swig":
        return False
    return True


def _package_copy():
    """The plugin package with a small stand-in for the bundled lib/."""
    folder = Path(tempfile.mkdtemp()) / "lcsc_manager"
    shutil.copytree(pcm_builds.PACKAGE_DIR, folder,
                    ignore=shutil.ignore_patterns("lib", *pcm_builds.IGNORED))
    (folder / "lib" / "requests").mkdir(parents=True)
    (folder / "lib" / "requests" / "__init__.py").write_text("")
    (folder / "__pycache__").mkdir(exist_ok=True)             # must not be shipped
    (folder / "__pycache__" / "x.cpython-39.pyc").write_bytes(b"\0")
    return folder


def _build(release="0.9.0", package=None, **options):
    out = Path(tempfile.mkdtemp())
    described = pcm_builds.build_packages(release, out, package_dir=package or _package_copy(),
                                          **options)
    return out, {b["runtime"]: b for b in described}


# ─── versions ─────────────────────────────────────────────────────────

def test_one_release_two_builds_with_their_own_versions():
    swig, ipc = builds_for("0.9.0")
    assert (swig.runtime, swig.version, ipc.runtime, ipc.version) == ("swig", "0.9.0", "ipc", "1.9.0")
    assert swig.zip_name == "kicad-lcsc-manager-0.9.0.zip", "keeps the existing download name"
    assert ipc.zip_name == "kicad-lcsc-manager-1.9.0-ipc.zip"
    for build in (swig, ipc):
        assert build.download_url.endswith(f"/releases/download/v0.9.0/{build.zip_name}")
    assert builds_for("0.10.3")[1].version == "1.10.3"
    for bad in ("0.9", "v0.9.0", "0.9.0-rc1", "1.2.3.4", ""):
        try:
            builds_for(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} must be rejected")
    print("test_one_release_two_builds_with_their_own_versions: PASS")


def test_each_kicad_gets_exactly_one_build():
    entries = [b.version_entry() for b in builds_for("0.9.0")]
    for entry in entries:
        assert PCM_VERSION.match(entry["version"])
        assert PCM_KICAD_VERSION.match(entry["kicad_version"])
        assert PCM_KICAD_VERSION.match(entry.get("kicad_version_max", "0"))
        assert entry["runtime"] in ("swig", "ipc") and entry["status"] == "stable"
        assert set(entry) <= PCM_VERSION_KEYS
    for kicad, runtime in [((9, 0, 0), "swig"), ((9, 0, 7), "swig"), ((10, 0, 6), "swig"),
                           ((10, 99, 0), "ipc"), ((11, 0, 0), "ipc"), ((11, 1, 2), "ipc")]:
        offered = [e["runtime"] for e in entries if compatible(e, kicad)]
        assert offered == [runtime], (kicad, offered)
    assert not any(compatible(e, (8, 0, 9)) for e in entries), "KiCad 8 isn't supported"
    print("test_each_kicad_gets_exactly_one_build: PASS")


def test_a_version_is_never_reused_for_the_other_runtime():
    """v0.9.0 publishes 1.9.0 as its IPC build; a later v1.9.0 would publish
    its SWIG build as 1.9.0 too, and KiCad would mix the two up. The build
    and the metadata update both refuse that; rebuilding the same release is
    fine."""
    published = [b.version_entry() for b in builds_for("0.9.0")]
    assert pcm_builds.version_clashes([b.version_entry() for b in builds_for("0.9.0")], published) == []
    [clash] = pcm_builds.version_clashes([b.version_entry() for b in builds_for("1.9.0")], published)
    assert "1.9.0 is already taken by a published IPC build (this is the SWIG build)" in clash, clash
    # Entries written before the runtime field existed count as SWIG.
    assert pcm_builds.version_clashes([builds_for("0.7.0")[1].version_entry()],
                                      [{"version": "1.7.0"}]) != []

    packages = Path(tempfile.mkdtemp()) / "packages.json"
    packages.write_text(json.dumps({"packages": [{"versions": published}]}))
    try:
        pcm_builds.build_packages("1.9.0", Path(tempfile.mkdtemp()),
                                  package_dir=_package_copy(), packages_json=packages)
    except ValueError as e:
        assert "v1.9.0 can't be published" in str(e)
    else:
        raise AssertionError("the build must stop a clashing release before it's made")
    pcm_builds.build_packages("0.9.0", Path(tempfile.mkdtemp()),
                              package_dir=_package_copy(), packages_json=packages)
    # The repository's own history is clash-free and has no duplicates.
    versions = json.loads((REPO / "packages.json").read_text())["packages"][0]["versions"]
    assert len({v["version"] for v in versions}) == len(versions)
    print("test_a_version_is_never_reused_for_the_other_runtime: PASS")


# ─── the zips ─────────────────────────────────────────────────────────

def test_builds_both_zips_with_their_own_metadata():
    package = _package_copy()
    source_init = (package / "__init__.py").read_text()
    out, built = _build(package=package)
    assert (package / "__init__.py").read_text() == source_init, \
        "versions are stamped into the zips, not the source"
    root = json.loads((REPO / "metadata.json").read_text(encoding="utf-8"))
    for runtime, build in built.items():
        zip_path = out / build["zip"]
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            meta = json.loads(zf.read("metadata.json"))
            init = zf.read("plugins/__init__.py").decode()
        # The package fields come from the repository's metadata.json.
        assert {k: v for k, v in meta.items() if k != "versions"} == \
            {k: v for k, v in root.items() if k != "versions"}
        [entry] = meta["versions"]
        assert entry == {k: v for k, v in build.items()
                         if k not in ("zip", "download_url", "download_sha256",
                                      "download_size", "install_size")}
        assert entry["runtime"] == runtime
        assert f'__version__ = "{entry["version"]}"' in init
        assert "resources/icon.png" in names and "plugins/lib/requests/__init__.py" in names
        assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
        assert build["download_sha256"] == pcm_builds.sha256_of(zip_path)
        assert build["download_size"] == zip_path.stat().st_size
        assert build["install_size"] > build["download_size"] // 2
    with zipfile.ZipFile(out / built["ipc"]["zip"]) as zf:
        names = set(zf.namelist())
        assert {"plugins/plugin.json", "plugins/requirements.txt", "plugins/ipc_main.py",
                "plugins/plugin_resources/icon-24.png"} <= names
    with zipfile.ZipFile(out / built["swig"]["zip"]) as zf:
        names = set(zf.namelist())
        assert "plugins/plugin.py" in names
        assert "plugins/plugin.json" not in names, "it would switch the SWIG plugin off"
        assert "plugins/requirements.txt" not in names
    listed = json.loads((out / "builds.json").read_text())
    assert [b["zip"] for b in listed] == [built["swig"]["zip"], built["ipc"]["zip"]]
    print("test_builds_both_zips_with_their_own_metadata: PASS")


def test_zips_unpack_the_way_the_pcm_installs_them():
    """The PCM extracts plugins/ and resources/ into folders named after the
    identifier; KiCad 11 then finds plugin.json at the plugin folder's root."""
    out, built = _build()
    identifier = json.loads((REPO / "metadata.json").read_text())["identifier"]
    for runtime, build in built.items():
        third_party = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(out / build["zip"]) as zf:
            for name in zf.namelist():
                top, _, rest = name.partition("/")
                if top in ("plugins", "resources") and rest:      # pcm_task_manager.cpp
                    target = third_party / top / identifier.replace(".", "_") / rest
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(name))
        plugin = third_party / "plugins" / identifier.replace(".", "_")
        assert (plugin / "__init__.py").is_file()
        assert (plugin / "plugin.json").is_file() == (runtime == "ipc")
        if runtime == "ipc":
            assert pcm_builds.missing_files(plugin) == []
    print("test_zips_unpack_the_way_the_pcm_installs_them: PASS")


def test_a_bad_zip_is_refused():
    """check_package runs on every build; each of these must fail it."""
    out, built = _build()
    swig, ipc = builds_for("0.9.0")

    def rewrite(src, dst, drop=(), add=None, change=None):
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
            for item in zin.infolist():
                if item.filename in drop:
                    continue
                data = zin.read(item.filename)
                if change and item.filename in change:
                    data = change[item.filename](data)
                zout.writestr(item, data)
            for name, data in (add or {}).items():
                zout.writestr(name, data)
        return dst

    tmp = Path(tempfile.mkdtemp())
    cases = [
        (swig, rewrite(out / swig.zip_name, tmp / "a.zip", add={"plugins/plugin.json": "{}"}), "SWIG build contains"),
        (swig, rewrite(out / swig.zip_name, tmp / "b.zip", add={"plugins/x/__pycache__/y.pyc": ""}), "bytecode"),
        (swig, rewrite(out / swig.zip_name, tmp / "c.zip",
                       drop=[n for n in zipfile.ZipFile(out / swig.zip_name).namelist()
                             if n.startswith("plugins/lib/")]), "bundled dependencies"),
        (ipc, rewrite(out / ipc.zip_name, tmp / "d.zip", drop=["plugins/ipc_main.py"]), "missing ipc_main.py"),
        (ipc, rewrite(out / ipc.zip_name, tmp / "e.zip", drop=["plugins/requirements.txt"]), "requirements.txt"),
        (ipc, rewrite(out / ipc.zip_name, tmp / "f.zip",
                      change={"plugins/__init__.py": lambda d: d.replace(b"1.9.0", b"0.9.0")}), "version 1.9.0"),
        (ipc, out / swig.zip_name, "metadata.json versions"),
    ]
    for build, zip_path, expected in cases:
        try:
            pcm_builds.check_package(build, zip_path)
        except ValueError as e:
            assert expected in str(e), (expected, str(e))
            continue
        raise AssertionError(f"{zip_path.name} should fail with {expected!r}")
    pcm_builds.check_package(swig, out / swig.zip_name)       # the real ones pass
    pcm_builds.check_package(ipc, out / ipc.zip_name)
    print("test_a_bad_zip_is_refused: PASS")


def test_build_needs_the_bundled_dependencies():
    package = _package_copy()
    shutil.rmtree(package / "lib")
    try:
        pcm_builds.build_packages("0.9.0", Path(tempfile.mkdtemp()), package_dir=package)
    except ValueError as e:
        assert "bundle-dependencies.sh" in str(e)
        print("test_build_needs_the_bundled_dependencies: PASS")
        return
    raise AssertionError("building without lib/ must fail")


def test_command_line():
    run = subprocess.run([sys.executable, str(SCRIPTS / "build-packages.py"), "0.9"],
                         capture_output=True, text=True)
    assert run.returncode != 0 and "not a release version" in run.stderr, run.stderr
    print("test_command_line: PASS")


# ─── update-metadata.py ───────────────────────────────────────────────

def _metadata_copy():
    folder = Path(tempfile.mkdtemp())
    for name in ("metadata.json", "packages.json", "repository.json"):
        shutil.copy(REPO / name, folder / name)
    return folder


def _update(folder, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / "update-metadata.py"), *map(str, args)],
                          cwd=folder, capture_output=True, text=True)


def test_update_metadata_records_both_builds():
    out, built = _build()
    folder = _metadata_copy()
    lists = (("packages.json", lambda d: d["packages"][0]["versions"]),
             ("metadata.json", lambda d: d["versions"]))
    before = {name: get(json.loads((folder / name).read_text())) for name, get in lists}
    zips = [out / built["swig"]["zip"], out / built["ipc"]["zip"]]
    run = _update(folder, "0.9.0", *zips)
    assert run.returncode == 0, run.stderr
    for name, get in lists:
        versions = get(json.loads((folder / name).read_text()))
        assert [v["version"] for v in versions[:2]] == ["1.9.0", "0.9.0"], name
        assert versions[2:] == before[name], f"{name}: earlier releases must stay as they were"
        for entry, build in zip(versions[:2], (built["ipc"], built["swig"])):
            assert entry == {k: v for k, v in build.items() if k != "zip"}, (entry, build)
            assert set(entry) <= PCM_VERSION_KEYS
    repo = json.loads((folder / "repository.json").read_text())
    assert repo["packages"]["sha256"] == pcm_builds.sha256_of(folder / "packages.json")
    # Again with the same zips: nothing changes, nothing is duplicated.
    snapshot = (folder / "packages.json").read_text()
    assert _update(folder, "0.9.0", *zips).returncode == 0
    assert (folder / "packages.json").read_text() == snapshot
    print("test_update_metadata_records_both_builds: PASS")


def test_update_metadata_wants_the_whole_release():
    out, built = _build()
    folder = _metadata_copy()
    snapshot = (folder / "packages.json").read_text()
    for args in (["0.9.0", out / built["swig"]["zip"]],                     # IPC build missing
                 ["0.9.1", out / built["swig"]["zip"], out / built["ipc"]["zip"]]):  # wrong release
        run = _update(folder, *args)
        assert run.returncode != 0 and "is published as" in run.stderr, run.stderr
    assert (folder / "packages.json").read_text() == snapshot
    print("test_update_metadata_wants_the_whole_release: PASS")


def test_record_keeps_history_and_order():
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location("update_metadata", SCRIPTS / "update-metadata.py")
    um = module_from_spec(spec)
    spec.loader.exec_module(um)
    old = [{"version": "0.8.1"}, {"version": "0.8.0"}]          # no runtime: SWIG
    def release(n):
        return [{"version": "0.9.0", "runtime": "swig", "n": n},
                {"version": "1.9.0", "runtime": "ipc", "n": n}]
    assert [v["version"] for v in um.record(old, release(1))] == ["1.9.0", "0.9.0", "0.8.1", "0.8.0"]
    again = um.record(um.record(old, release(1)), release(2))
    assert [(v["version"], v.get("n")) for v in again] == \
        [("1.9.0", 2), ("0.9.0", 2), ("0.8.1", None), ("0.8.0", None)]
    print("test_record_keeps_history_and_order: PASS")


def test_update_metadata_refuses_a_clash_and_writes_nothing():
    out, built = _build("0.9.0")
    folder = _metadata_copy()
    assert _update(folder, "0.9.0", out / built["swig"]["zip"], out / built["ipc"]["zip"]).returncode == 0
    before = {n: (folder / n).read_text() for n in ("metadata.json", "packages.json")}
    out2, built2 = _build("1.9.0", packages_json=Path(tempfile.mkdtemp()) / "none.json")
    run = _update(folder, "1.9.0", out2 / built2["swig"]["zip"], out2 / built2["ipc"]["zip"])
    assert run.returncode != 0 and "already taken by a published IPC build" in run.stderr, run.stderr
    assert {n: (folder / n).read_text() for n in before} == before, "both files or neither"
    print("test_update_metadata_refuses_a_clash_and_writes_nothing: PASS")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll package build tests passed.")
