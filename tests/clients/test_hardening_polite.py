import os
import pytest
from unittest.mock import MagicMock, patch
from clients.crossref import CrossrefClient

def test_crossref_polite_env_var(monkeypatch):
    monkeypatch.setenv("CROSSREF_POLITE_EMAIL", "env@example.com")
    client = CrossrefClient()
    assert client.email == "env@example.com"

def test_crossref_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("CROSSREF_POLITE_EMAIL", "env@example.com")
    client = CrossrefClient(email="explicit@example.com")
    assert client.email == "explicit@example.com"
