"""Smoke test: the package imports cleanly. Real tests added per-phase."""

import adc_winered


def test_package_imports() -> None:
    assert adc_winered.__version__
