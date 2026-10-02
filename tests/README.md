# Tests

Every `test_*.py` here is a plain script with assertions; it prints
`<test name>: PASS` per test and stops at the first failure.

```bash
./scripts/bundle-dependencies.sh        # once: fills plugins/lcsc_manager/lib
python3 scripts/run-tests.py            # all offline tests
python3 scripts/run-tests.py symbol     # only files whose name contains "symbol"
python3 scripts/run-tests.py --network  # also the two that call LCSC/EasyEDA
python3 tests/test_symbol_library.py    # one file, with its full output
```

CI runs `scripts/run-tests.py` on every push and pull request (Python 3.9
and a current one), and the release workflow runs it before building the
packages.

- **Offline tests** need nothing but the repository. A few also drive
  KiCad's own Python or `kicad-cli` when KiCad is installed and print `SKIP`
  where it isn't; see [TESTING.md](../TESTING.md).
- **Network tests** (`test_regression_components.py`,
  `test_footprint_matches_upstream.py`) import real parts, so they can fail
  for reasons outside the code. They run only with `--network`.
- `fake_kicad_api.py` isn't a test: it stands in for KiCad's API server when
  trying the KiCad 11 build without KiCad (TESTING.md).

Tests never touch your real KiCad or LCSC Manager settings: they use
temporary folders and a sandboxed `KICAD_CONFIG_HOME`.
