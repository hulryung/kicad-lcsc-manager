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
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent
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
    for name in ("update-metadata.py", "publish-metadata.sh"):
        shutil.copy(REPO / "scripts" / name, dev / "scripts" / name)
    git(dev, "add", "-A")
    git(dev, "commit", "--quiet", "-m", "seed")
    git(dev, "push", "--quiet", "origin", "HEAD:main")
    package = root / "pkg.zip"
    package.write_bytes(os.urandom(2048))
    return root, dev, package


def publish(dev, version, package, **env):
    return subprocess.run(["bash", SCRIPT, version, str(package)], cwd=dev,
                          env=dict(ENV, **env), capture_output=True, text=True)


def origin_file(root, name):
    return git(root / "origin.git", "show", f"main:{name}")


def served_versions(root):
    return [v["version"] for v in
            json.loads(origin_file(root, "packages.json"))["packages"][0]["versions"]]


def test_publishes_on_top_of_main():
    root, dev, package = _fixture()
    run = publish(dev, "9.9.1", package)
    assert run.returncode == 0, run.stderr
    assert served_versions(root)[0] == "9.9.1"
    entry = json.loads(origin_file(root, "packages.json"))["packages"][0]["versions"][0]
    assert entry["download_sha256"] == hashlib.sha256(package.read_bytes()).hexdigest()
    repo_json = json.loads(origin_file(root, "repository.json"))
    assert repo_json["packages"]["sha256"] == hashlib.sha256(
        (origin_file(root, "packages.json") + "\n").encode()).hexdigest()
    assert git(root / "origin.git", "log", "-1", "--format=%s", "main") == \
        "Update metadata for release v9.9.1"
    print("test_publishes_on_top_of_main: PASS")


def test_tag_behind_main_keeps_mains_entries():
    """The v0.7.1 case: main got the previous release's metadata commit after
    the tag was cut from an older commit."""
    root, dev, package = _fixture()
    tagged = git(dev, "rev-parse", "HEAD")
    older = root / "older.zip"
    older.write_bytes(b"previous release")
    assert publish(dev, "9.9.0", older).returncode == 0     # main moves on
    git(dev, "checkout", "--quiet", "--detach", tagged)      # the lagging tag
    run = publish(dev, "9.9.1", package)
    assert run.returncode == 0, run.stderr
    assert served_versions(root)[:2] == ["9.9.1", "9.9.0"], served_versions(root)
    print("test_tag_behind_main_keeps_mains_entries: PASS")


def test_retries_when_the_push_is_rejected():
    root, dev, package = _fixture()
    hook = root / "origin.git" / "hooks" / "pre-receive"
    marker = root / "reject-once"
    marker.write_text("")
    hook.write_text(f'#!/bin/bash\nif [ -e "{marker}" ]; then rm "{marker}"; exit 1; fi\n')
    hook.chmod(0o755)
    run = publish(dev, "9.9.1", package)
    assert run.returncode == 0, run.stderr
    assert "attempt 1/5 was rejected" in run.stderr, run.stderr
    assert served_versions(root)[0] == "9.9.1"
    print("test_retries_when_the_push_is_rejected: PASS")


def test_fails_loudly_when_it_cannot_publish():
    root, dev, package = _fixture()
    hook = root / "origin.git" / "hooks" / "pre-receive"
    hook.write_text("#!/bin/bash\nexit 1\n")
    hook.chmod(0o755)
    before = git(root / "origin.git", "rev-parse", "main")
    run = publish(dev, "9.9.1", package, PUBLISH_ATTEMPTS="2")
    assert run.returncode != 0, "a failed publish must fail the workflow step"
    assert "::error::Could not publish v9.9.1" in run.stderr, run.stderr
    assert git(root / "origin.git", "rev-parse", "main") == before
    print("test_fails_loudly_when_it_cannot_publish: PASS")


def test_rerun_for_the_same_release_is_a_noop():
    root, dev, package = _fixture()
    assert publish(dev, "9.9.1", package).returncode == 0
    head = git(root / "origin.git", "rev-parse", "main")
    run = publish(dev, "9.9.1", package)
    assert run.returncode == 0, run.stderr
    assert "nothing to publish" in run.stdout, run.stdout
    assert git(root / "origin.git", "rev-parse", "main") == head
    print("test_rerun_for_the_same_release_is_a_noop: PASS")


def test_leaves_no_worktree_or_changes_behind():
    root, dev, package = _fixture()
    publish(dev, "9.9.1", package)
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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll publish-metadata tests passed.")
