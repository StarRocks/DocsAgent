#!/usr/bin/env python3
"""
Core abstractions for the DocsAgent system.

This package provides the foundational protocols and generic implementations
that enable flexible, extensible documentation generation for multiple item types.
"""

from .protocols import (
    DocumentableItem,
    ItemExtractor,
    DocGenerator,
    DocPersister,
)
from .pipeline import (
    DocGenerationPipeline,
    DEFAULT_SEPARATOR,
    DEFAULT_BATCH_SIZE,
)

__all__ = [
    'DocumentableItem',
    'ItemExtractor',
    'DocGenerator',
    'DocPersister',
    'DocGenerationPipeline',
    'DEFAULT_SEPARATOR',
    'DEFAULT_BATCH_SIZE',
]
