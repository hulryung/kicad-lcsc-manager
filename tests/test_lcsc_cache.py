"""
Unit tests for LCSC API disk cache (opt-in).
Run with: python3 tests/test_lcsc_cache.py

These tests are offline — they do NOT hit the real API. They stub the cache
directory to a tempdir and exercise _cache_path / _cache_read / _cache_write
directly, then validate opt-in behaviour.
"""
import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from lcsc_manager.api.lcsc_api import LCSCAPIClient


def _make_client_with_cache(enabled: bool, cache_dir: Path) -> LCSCAPIClient:
    """Create a client with a temp cache dir and specified enabled state."""
    # Override the class attribute BEFORE instantiating so __init__ uses it
    LCSCAPIClient.CACHE_DIR = cache_dir
    client = LCSCAPIClient()
    # Override the per-instance flag (config may not have the key set)
    client.use_cache = enabled
    if enabled:
        cache_dir.mkdir(parents=True, exist_ok=True)
    return client


def test_cache_path_sanitizes_identifier():
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client_with_cache(True, Path(tmp))
        # Slashes in identifier must be sanitized
        p = client._cache_path("component/with/slash")
        assert "/" not in p.name, f"slash leaked into cache filename: {p.name}"
        assert p.suffix == ".json"
        print("test_cache_path_sanitizes_identifier: PASS")


def test_cache_read_returns_none_when_disabled():
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client_with_cache(False, Path(tmp))
        path = client._cache_path("C123")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"hello": "world"}')
        result = client._cache_read(path)
        assert result is None, f"expected None when disabled, got {result!r}"
        print("test_cache_read_returns_none_when_disabled: PASS")


def test_cache_read_returns_content_when_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client_with_cache(True, Path(tmp))
        path = client._cache_path("C123")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"hello": "world"}')
        result = client._cache_read(path)
        assert result == '{"hello": "world"}', f"got {result!r}"
        print("test_cache_read_returns_content_when_enabled: PASS")


def test_cache_read_missing_file_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client_with_cache(True, Path(tmp))
        path = client._cache_path("C_missing")
        result = client._cache_read(path)
        assert result is None
        print("test_cache_read_missing_file_returns_none: PASS")


def test_cache_write_noop_when_disabled():
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client_with_cache(False, Path(tmp))
        path = client._cache_path("C123")
        client._cache_write(path, '{"x": 1}')
        assert not path.exists(), f"cache file should not exist when disabled"
        print("test_cache_write_noop_when_disabled: PASS")


def test_cache_write_persists_when_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client_with_cache(True, Path(tmp))
        path = client._cache_path("C123")
        payload = json.dumps({"success": True, "result": {"name": "test"}})
        client._cache_write(path, payload)
        assert path.exists(), "cache file should exist"
        assert path.read_text() == payload
        print("test_cache_write_persists_when_enabled: PASS")


def test_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client_with_cache(True, Path(tmp))
        path = client._cache_path("C_round")
        payload = json.dumps({"success": True, "nested": [1, 2, 3]})
        client._cache_write(path, payload)
        read_back = client._cache_read(path)
        assert read_back == payload
        assert json.loads(read_back)["nested"] == [1, 2, 3]
        print("test_roundtrip: PASS")


if __name__ == "__main__":
    test_cache_path_sanitizes_identifier()
    test_cache_read_returns_none_when_disabled()
    test_cache_read_returns_content_when_enabled()
    test_cache_read_missing_file_returns_none()
    test_cache_write_noop_when_disabled()
    test_cache_write_persists_when_enabled()
    test_roundtrip()
    print("\nAll LCSC cache tests passed.")
