#!/usr/bin/env python3
"""
Run the test suite: every tests/test_*.py, each as its own process (they are
plain scripts that stop at the first failed assertion).

Usage:
    python3 scripts/run-tests.py              the offline tests
    python3 scripts/run-tests.py --network    also the ones that call LCSC/EasyEDA
    python3 scripts/run-tests.py symbol ipc   only tests whose name contains a word

Run scripts/bundle-dependencies.sh once first (it fills plugins/lcsc_manager/lib).
Tests that need KiCad's own Python or kicad-cli skip themselves where KiCad
isn't installed. The release workflow and CI run this script, so a release
can't be built from a tree whose tests fail.
"""
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TESTS = REPO / "tests"

# These talk to LCSC/EasyEDA, so they can fail for reasons outside the code.
NETWORK = {"test_regression_components", "test_footprint_matches_upstream"}
TIMEOUT = 600


def select(words, network):
    names = sorted(p.stem for p in TESTS.glob("test_*.py"))
    if not network:
        names = [n for n in names if n not in NETWORK]
    if words:
        names = [n for n in names if any(w in n for w in words)]
    return names


def run(name):
    """(ok, passed, skipped, seconds, tail of the output on failure)"""
    started = time.time()
    try:
        done = subprocess.run([sys.executable, "-B", str(TESTS / f"{name}.py")],
                              cwd=REPO, capture_output=True, text=True, timeout=TIMEOUT)
        output, code = done.stdout + done.stderr, done.returncode
    except subprocess.TimeoutExpired as e:
        output = f"{e.stdout or ''}{e.stderr or ''}\ntimed out after {TIMEOUT} s"
        code = -1
    lines = output.splitlines()
    passed = sum(": PASS" in line for line in lines)
    skipped = sum(": SKIP" in line for line in lines)
    tail = [line for line in lines if " - lcsc_manager" not in line][-15:]
    return code == 0, passed, skipped, time.time() - started, "\n".join(tail)


def main(argv):
    network = "--network" in argv
    words = [a for a in argv[1:] if not a.startswith("-")]
    names = select(words, network)
    if not names:
        print("no tests match", file=sys.stderr)
        return 2
    if not any((REPO / "plugins" / "lcsc_manager" / "lib").glob("requests")):
        print("plugins/lcsc_manager/lib is empty: run scripts/bundle-dependencies.sh first",
              file=sys.stderr)
        return 2
    failed, total, total_skipped = [], 0, 0
    for name in names:
        ok, passed, skipped, seconds, tail = run(name)
        total += passed
        total_skipped += skipped
        note = f", {skipped} skipped" if skipped else ""
        print(f"{'ok  ' if ok else 'FAIL'} {name:<36} {passed:>3} passed{note}  ({seconds:.1f}s)",
              flush=True)
        if not ok:
            failed.append(name)
            print("\n".join("     " + line for line in tail.splitlines()), flush=True)
    print(f"\n{len(names) - len(failed)}/{len(names)} test files passed, "
          f"{total} tests, {total_skipped} skipped")
    if failed:
        print("failed: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
