"""Tests for scripts/publish-metadata.sh, the release workflow's metadata
step, against real git repositories (a bare "origin" and clones).

The step used to push the tag's tree with `git push origin HEAD:main || echo
"Nothing to push"`: when the tag lagged behind main (v0.7.1), the push was
rejected, the run still went green, and the PCM never listed the release.

Run with: python3 tests/test_publish_metadata.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from pcm_builds import builds_for

SCRIPT = "scripts/publish-metadata.sh"
ENV = dict(os.environ, PUBLISH_RETRY_DELAY="0",
           GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, check=check,
                          capture_output=True, text=True).stdout.strip()


def _fixture():
    """origin.git (bare) + dev clone holding the real metadata and scripts."""
    root = Path(tempfile.mkdtemp())
    git(root, "init", "--quiet", "--bare", "-b", "main", "origin.git")
    git(root, "clone", "--quiet", "origin.git", "dev")
    dev = root / "dev"
    (dev / "scripts").mkdir()
    for name in ("metadata.json", "packages.json", "repository.json"):
        shutil.copy(REPO / name, dev / name)
    for name in ("update-metadata.py", "publish-metadata.sh", "pcm_builds.py"):
        shutil.copy(REPO / "scripts" / name, dev / "scripts" / name)
    git(dev, "add", "-A")
    git(dev, "commit", "--quiet", "-m", "seed")
    git(dev, "push", "--quiet", "origin", "HEAD:main")
    return root, dev, packages(root, "9.9.1")


def packages(root, release):
    """Stand-in zips for every build of a release, named as the workflow
    names them (the SWIG X.Y.Z and the IPC (X+1).Y.Z build)."""
    folder = Path(tempfile.mkdtemp(dir=root))
    zips = []
    for build in builds_for(release):
        path = folder / build.zip_name
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("plugins/__init__.py", os.urandom(64).hex())
        zips.append(path)
    return zips


def publish(dev, version, zips, **env):
    return subprocess.run(["bash", SCRIPT, version, *map(str, zips)], cwd=dev,
                          env=dict(ENV, **env), capture_output=True, text=True)


def origin_file(root, name):
    return git(root / "origin.git", "show", f"main:{name}")


def served_versions(root):
    return [v["version"] for v in
            json.loads(origin_file(root, "packages.json"))["packages"][0]["versions"]]


def test_publishes_on_top_of_main():
    root, dev, zips = _fixture()
    run = publish(dev, "9.9.1", zips)
    assert run.returncode == 0, run.stderr
    assert served_versions(root)[:2] == ["10.9.1", "9.9.1"]
    ipc, swig = json.loads(origin_file(root, "packages.json"))["packages"][0]["versions"][:2]
    for entry, zip_path in ((swig, zips[0]), (ipc, zips[1])):
        assert entry["download_sha256"] == hashlib.sha256(zip_path.read_bytes()).hexdigest()
        assert entry["download_url"].endswith(f"/v9.9.1/{zip_path.name}")
    assert (swig["runtime"], ipc["runtime"]) == ("swig", "ipc")
    repo_json = json.loads(origin_file(root, "repository.json"))
    assert repo_json["packages"]["sha256"] == hashlib.sha256(
        (origin_file(root, "packages.json") + "\n").encode()).hexdigest()
    assert git(root / "origin.git", "log", "-1", "--format=%s", "main") == \
        "Update metadata for release v9.9.1"
    print("test_publishes_on_top_of_main: PASS")


def test_tag_behind_main_keeps_mains_entries():
    """The v0.7.1 case: main got the previous release's metadata commit after
    the tag was cut from an older commit."""
    root, dev, zips = _fixture()
    tagged = git(dev, "rev-parse", "HEAD")
    assert publish(dev, "9.9.0", packages(root, "9.9.0")).returncode == 0   # main moves on
    git(dev, "checkout", "--quiet", "--detach", tagged)      # the lagging tag
    run = publish(dev, "9.9.1", zips)
    assert run.returncode == 0, run.stderr
    assert served_versions(root)[:4] == ["10.9.1", "9.9.1", "10.9.0", "9.9.0"], served_versions(root)
    print("test_tag_behind_main_keeps_mains_entries: PASS")


def test_the_tags_own_update_script_writes_the_entries():
    """The entries belong with the code that built the packages. A newer
    main whose update-metadata.py can't handle this release mustn't matter."""
    root, dev, zips = _fixture()
    other = root / "other"
    git(root, "clone", "--quiet", "origin.git", str(other))
    (other / "scripts" / "update-metadata.py").write_text("raise SystemExit(3)\n")
    git(other, "commit", "--quiet", "-am", "main's script changes")
    git(other, "push", "--quiet", "origin", "HEAD:main")
    run = publish(dev, "9.9.1", zips)
    assert run.returncode == 0, run.stderr
    assert served_versions(root)[:2] == ["10.9.1", "9.9.1"]
    print("test_the_tags_own_update_script_writes_the_entries: PASS")


def test_refuses_an_incomplete_release():
    root, dev, zips = _fixture()
    before = git(root / "origin.git", "rev-parse", "main")
    run = publish(dev, "9.9.1", zips[:1], PUBLISH_ATTEMPTS="1")
    assert run.returncode != 0, "publishing only the SWIG build must fail"
    assert git(root / "origin.git", "rev-parse", "main") == before
    print("test_refuses_an_incomplete_release: PASS")


def test_retries_when_the_push_is_rejected():
    root, dev, zips = _fixture()
    hook = root / "origin.git" / "hooks" / "pre-receive"
    marker = root / "reject-once"
    marker.write_text("")
    hook.write_text(f'#!/bin/bash\nif [ -e "{marker}" ]; then rm "{marker}"; exit 1; fi\n')
    hook.chmod(0o755)
    run = publish(dev, "9.9.1", zips)
    assert run.returncode == 0, run.stderr
    assert "attempt 1/5 was rejected" in run.stderr, run.stderr
    assert served_versions(root)[:2] == ["10.9.1", "9.9.1"]
    print("test_retries_when_the_push_is_rejected: PASS")


def test_fails_loudly_when_it_cannot_publish():
    root, dev, zips = _fixture()
    hook = root / "origin.git" / "hooks" / "pre-receive"
    hook.write_text("#!/bin/bash\nexit 1\n")
    hook.chmod(0o755)
    before = git(root / "origin.git", "rev-parse", "main")
    run = publish(dev, "9.9.1", zips, PUBLISH_ATTEMPTS="2")
    assert run.returncode != 0, "a failed publish must fail the workflow step"
    assert "::error::Could not publish v9.9.1" in run.stderr, run.stderr
    assert git(root / "origin.git", "rev-parse", "main") == before
    print("test_fails_loudly_when_it_cannot_publish: PASS")


def test_rerun_for_the_same_release_is_a_noop():
    root, dev, zips = _fixture()
    assert publish(dev, "9.9.1", zips).returncode == 0
    head = git(root / "origin.git", "rev-parse", "main")
    run = publish(dev, "9.9.1", zips)
    assert run.returncode == 0, run.stderr
    assert "nothing to publish" in run.stdout, run.stdout
    assert git(root / "origin.git", "rev-parse", "main") == head
    print("test_rerun_for_the_same_release_is_a_noop: PASS")


def test_leaves_no_worktree_or_changes_behind():
    root, dev, zips = _fixture()
    publish(dev, "9.9.1", zips)
    assert len(git(dev, "worktree", "list").splitlines()) == 1
    assert git(dev, "status", "--porcelain") == ""
    print("test_leaves_no_worktree_or_changes_behind: PASS")


def test_workflow_no_longer_swallows_failures():
    wf = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert '|| echo "Nothing to push"' not in wf
    assert '|| echo "No changes to commit"' not in wf
    assert "./scripts/publish-metadata.sh" in wf
    assert "name: Update packages.json" not in wf, \
        "metadata must be updated on main by the script, not in the tag's tree"
    assert 'grep -i pycache || echo' not in wf, "the pycache check must fail the run"
    assert "concurrency:" in wf
    print("test_workflow_no_longer_swallows_failures: PASS")


def test_workflow_ships_both_builds():
    """The release builds, uploads and records both zips through the
    scripts, so a local ./scripts/package.sh build matches a release."""
    wf = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "python3 scripts/build-packages.py" in wf
    assert "files: release/*.zip" in wf
    assert './scripts/publish-metadata.sh "${{ steps.version.outputs.version }}" release/*.zip' in wf
    assert '"kicad_version": "9.0"' not in wf, "package metadata comes from metadata.json"
    assert 'sed -i "s/__version__' not in wf, "each zip gets its own version stamped in"
    package_sh = (REPO / "scripts" / "package.sh").read_text(encoding="utf-8")
    assert "scripts/build-packages.py" in package_sh
    print("test_workflow_ships_both_builds: PASS")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll publish-metadata tests passed.")
