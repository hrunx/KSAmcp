"""Shared error types for MCP tools."""

from __future__ import annotations


class SourceConfigError(Exception):
    """Raised when a source definition is invalid or missing."""


class PreviewError(Exception):
    """Raised when a resource preview cannot be generated."""
