# -*- coding: utf-8 -*-
"""Domain errors for flora management."""


class FloraError(Exception):
    """Base error for flora operations."""


class NotFoundError(FloraError):
    """Taxon not found."""


class ValidationError(FloraError):
    """Taxon fails schema / business rules."""


class DuplicateError(FloraError):
    """Duplicate id or scientific name."""
