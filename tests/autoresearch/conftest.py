"""Autoresearch test configuration.

Exclude scripts (baseline_*.py, test_real_installer.py) from pytest collection.
They use sys.exit() which crashes the test runner.
"""

collect_ignore_glob = ["baseline_*"]
collect_ignore = ["test_real_installer.py", "test_installer_features.py"]
