"""
Tests that the API layer distinguishes transient rate-limiting from a
component genuinely missing from EasyEDA — so the UI can show actionable
messages instead of one confusing "not found" for both. (issue #7)

Offline / deterministic: the network session and time.sleep are mocked.

Run with: python3 tests/test_api_error_classification.py
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

import lcsc_manager  # noqa: F401  puts the bundled requests on sys.path
import requests

from lcsc_manager.api.lcsc_api import (
    LCSCAPIClient,
    LCSCAPIError,
    LCSCRateLimitError,
)


def _session_returning_403() -> MagicMock:
    """Mock session whose every request 403s (EasyEDA's rate-limit code)."""
    resp = MagicMock()
    resp.status_code = 403
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=resp
    )
    sess = MagicMock()
    sess.request.return_value = resp
    return sess


def test_rate_limit_is_a_subclass_of_api_error():
    # Callers that only catch LCSCAPIError must still catch rate-limit errors.
    assert issubclass(LCSCRateLimitError, LCSCAPIError)
    print("test_rate_limit_is_a_subclass_of_api_error: PASS")


def test_persistent_403_raises_rate_limit_error():
    """After exhausting retries on 403, _make_request raises the typed
    LCSCRateLimitError — not a generic LCSCAPIError."""
    client = LCSCAPIClient()
    with patch.object(
        LCSCAPIClient, "_get_session", return_value=_session_returning_403()
    ), patch("lcsc_manager.api.lcsc_api.time.sleep"):
        try:
            client._make_request(
                "GET", "https://easyeda.com/api/products/C1/components"
            )
        except LCSCRateLimitError:
            print("test_persistent_403_raises_rate_limit_error: PASS")
        else:
            raise AssertionError("expected LCSCRateLimitError on persistent 403")


def test_search_component_preserves_rate_limit_type():
    """search_component must not re-wrap a rate-limit error as a plain
    LCSCAPIError, or the UI can't tell 'try again' from 'no such part'."""
    client = LCSCAPIClient()
    with patch.object(
        LCSCAPIClient, "_cache_read", return_value=None
    ), patch.object(
        LCSCAPIClient,
        "_make_request",
        side_effect=LCSCRateLimitError("rate limited"),
    ):
        try:
            client.search_component("C12345")
        except LCSCRateLimitError:
            print("test_search_component_preserves_rate_limit_type: PASS")
        except LCSCAPIError as e:
            raise AssertionError(
                f"rate-limit type lost — re-wrapped as plain LCSCAPIError: {e}"
            )


def test_genuine_missing_part_returns_none():
    """A 200 response with success=False (part absent from EasyEDA, e.g.
    C6056597) yields None — distinct from the rate-limit raise above."""
    client = LCSCAPIClient()
    with patch.object(
        LCSCAPIClient, "_cache_read", return_value=None
    ), patch.object(
        LCSCAPIClient, "_make_request", return_value={"success": False}
    ):
        assert client.search_component("C6056597") is None
    print("test_genuine_missing_part_returns_none: PASS")


if __name__ == "__main__":
    test_rate_limit_is_a_subclass_of_api_error()
    test_persistent_403_raises_rate_limit_error()
    test_search_component_preserves_rate_limit_type()
    test_genuine_missing_part_returns_none()
    print("\nAll API error-classification tests passed.")
