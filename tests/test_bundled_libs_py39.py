"""Regression tests for issue #15: the bundled lib/ packages must stay
importable on the oldest supported KiCad Python (KiCad 9 = Python 3.9).

Two guards:
1. Version guard — urllib3 2.7.0 dropped Python 3.9; the vendored copy must
   stay on a 3.9-compatible line until KiCad 9 support is dropped.
2. Interpreter smoke test — when KiCad's own Python is present on this
   machine, actually import the bundled stack with it (skipped elsewhere).

Run with: python3 tests/test_bundled_libs_py39.py
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
LIB = REPO / "plugins" / "lcsc_manager" / "lib"

KICAD_PYTHON = Path(
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework"
    "/Versions/Current/bin/python3"
)


def _bundled_version(pkg: str, *candidates: str) -> str:
    for name in candidates:
        p = LIB / pkg / name
        if p.exists():
            m = re.search(r'__version__\s*=\s*(?:version\s*=\s*)?["\']([^"\']+)',
                          p.read_text(encoding="utf-8"))
            if m:
                return m.group(1)
    raise AssertionError(f"could not find version for bundled {pkg}")


def test_bundled_urllib3_supports_py39():
    """urllib3 >= 2.7 requires Python >= 3.10 (runtime `bytes | str` unions)
    and breaks every KiCad 9 install. Bump this bound only together with
    MIN_PYTHON in scripts/bundle-dependencies.sh."""
    version = _bundled_version("urllib3", "_version.py")
    major, minor = (int(x) for x in version.split(".")[:2])
    assert (major, minor) < (2, 7), (
        f"bundled urllib3 {version} dropped Python 3.9 support — "
        f"re-run scripts/bundle-dependencies.sh (it pins --python-version)"
    )
    print(f"test_bundled_urllib3_supports_py39: PASS (urllib3 {version})")


def test_bundled_requests_supports_py39():
    """requests 2.33+ dropped Python 3.9; stay on a 3.9-compatible line."""
    version = _bundled_version("requests", "__version__.py")
    major, minor = (int(x) for x in version.split(".")[:2])
    assert (major, minor) <= (2, 32), (
        f"bundled requests {version} may not support Python 3.9 — "
        f"re-run scripts/bundle-dependencies.sh"
    )
    print(f"test_bundled_requests_supports_py39: PASS (requests {version})")


def test_bundler_pins_python_version():
    """The bundler must resolve for the minimum supported Python, or a
    future re-run silently reintroduces incompatible versions."""
    script = (REPO / "scripts" / "bundle-dependencies.sh").read_text(encoding="utf-8")
    assert "--python-version" in script, (
        "scripts/bundle-dependencies.sh lost its --python-version pin (issue #15)"
    )
    print("test_bundler_pins_python_version: PASS")


def test_bundled_stack_imports_on_kicad_python():
    """Import the bundled requests stack with KiCad's own (3.9) Python."""
    if not KICAD_PYTHON.exists():
        print("test_bundled_stack_imports_on_kicad_python: SKIP (no KiCad python)")
        return
    code = (
        f"import sys; sys.path.insert(0, {str(LIB)!r}); "
        "import requests, urllib3; "
        "assert 'lcsc_manager' in requests.__file__; "
        "print(sys.version.split()[0], requests.__version__, urllib3.__version__)"
    )
    result = subprocess.run([str(KICAD_PYTHON), "-c", code],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, (
        f"bundled stack failed on KiCad python:\n{result.stderr}"
    )
    print("test_bundled_stack_imports_on_kicad_python: PASS "
          f"({result.stdout.strip()})")


if __name__ == "__main__":
    test_bundled_urllib3_supports_py39()
    test_bundled_requests_supports_py39()
    test_bundler_pins_python_version()
    test_bundled_stack_imports_on_kicad_python()
    print("\nAll bundled-lib tests passed.")
