# -*- coding: utf-8 -*-
"""Iraqi Flora Encyclopedia — programmatic taxa management library."""

from .manager import FloraManager
from .errors import FloraError, NotFoundError, ValidationError, DuplicateError

__all__ = [
    "FloraManager",
    "FloraError",
    "NotFoundError",
    "ValidationError",
    "DuplicateError",
]

__version__ = "1.0.0"
