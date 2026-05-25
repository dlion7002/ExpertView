"""Bootstrap smoke test: the `expertview` package must be importable.

Replaced by real coverage in Task 2 (schema round-trips) and beyond. Kept now so
`uv run pytest` exits 0 — `pytest` exits 5 when zero tests are collected, which
fails CI under `set -e`.
"""

import expertview


def test_package_importable() -> None:
    assert expertview is not None
