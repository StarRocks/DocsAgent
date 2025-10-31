#!/usr/bin/env python3
# Copyright 2021-present StarRocks, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
from .git_persister import GitPersister

__all__ = [
    # Protocols
    'DocumentableItem',
    'ItemExtractor',
    'DocGenerator',
    'DocPersister',
    # Pipeline
    'DocGenerationPipeline',
    'DEFAULT_SEPARATOR',
    'DEFAULT_BATCH_SIZE',
    # Git
    'GitPersister',
]
