# -*- coding: utf-8 -*-
"""Iraqi Flora Encyclopedia — programmatic taxa management library."""

from .manager import FloraManager
from .errors import FloraError, NotFoundError, ValidationError, DuplicateError
from .search import SchemaAwareSearch, SearchQuery, summarize_taxon
from .auth import AuthStore, auth_store, AuthError

__all__ = [
    "FloraManager",
    "FloraError",
    "NotFoundError",
    "ValidationError",
    "DuplicateError",
    "SchemaAwareSearch",
    "SearchQuery",
    "summarize_taxon",
    "AuthStore",
    "auth_store",
    "AuthError",
]

__version__ = "1.2.0"
