"""Tests for skills.local.adapters.

Note: Orphan adapters (CitationVerifyAdapter, EthicsAdapter, WritingQualityAdapter)
were removed in cleanup-dead-code-orphans change. Only LiteratureSearchAdapter
and AcademicWriterAdapter remain (they are wired in orchestrator_builder.py).
Tests for the wired adapters live in the orchestrator integration tests.
"""
