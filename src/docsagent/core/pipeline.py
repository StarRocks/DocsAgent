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
Generic documentation generation pipeline.

This module provides a reusable pipeline for generating multi-language
documentation for any type of documentable item (configs, functions, variables, etc.).

The pipeline handles:
- Item extraction from source
- Document generation (via LLM or templates)
- Multi-language translation with smart routing
- Batch processing for efficiency
- File organization and persistence

Key Features:
- Type-safe with generic type parameter T
- Dependency injection for flexibility
- Smart translation routing (ZH→EN→Others or EN→Others)
- Batch translation with separator method
- Extensible via protocols

Usage:
    pipeline = DocGenerationPipeline(
        extractor=MyExtractor(),
        doc_generator=MyGenerator(),
        translation_agent=TranslationAgent(),
        persister=MyPersister()
    )
    
    pipeline.run(
        source='/path/to/source',
        output_dir='/path/to/output',
        target_langs=['en', 'zh', 'ja']
    )
"""

from typing import TypeVar, Generic, List, Dict, Optional, Any, Callable
from pathlib import Path
from loguru import logger

from docsagent.core.protocols import (
    DocumentableItem,
    ItemExtractor,
    DocGenerator,
    DocPersister,
)
from docsagent.core.git_persister import GitPersister
from docsagent.core.version_extractor import BaseVersionExtractor
from docsagent.agents.translation_agent import TranslationAgent
from docsagent.tools import stats


# Type variable bound to DocumentableItem
T = TypeVar('T', bound=DocumentableItem)

# Separator for batch translation
DEFAULT_SEPARATOR = "<!-- ITEM_SEP_{index} -->"
DEFAULT_BATCH_SIZE = 10


class DocGenerationPipeline(Generic[T]):
    """
    Generic pipeline for multi-language documentation generation.
    
    This pipeline orchestrates the entire documentation workflow:
    1. Extract items from source
    2. Analyze existing documentation status
    3. Generate missing documentation
    4. Translate to target languages (smart routing)
    5. Save organized output files
    
    The pipeline is type-safe and works with any item type that implements
    the DocumentableItem protocol.
    
    Attributes:
        extractor: Item extractor (from source code, files, etc.)
        doc_generator: Documentation generator (typically LLM-based)
        translation_agent: Translation service
        persister: File persistence handler
        item_type_name: Human-readable name for logging
    """
    
    def __init__(
        self,
        extractor: ItemExtractor[T],
        doc_generator: Optional[DocGenerator[T]] = None,
        translation_agent: Optional[TranslationAgent] = None,
        persister: Optional[DocPersister[T]] = None,
        git_persister: Optional[GitPersister] = None,
        version_extractor: Optional[BaseVersionExtractor] = None,  # Version extractor (optional)
        item_type_name: str = "item",
    ):
        """
        Initialize the pipeline with dependency injection.
        
        Args:
            extractor: Item extractor (required)
            doc_generator: Doc generator (optional if items have docs)
            translation_agent: Translation service (default: create new)
            persister: File persister (optional, uses simple default)
            git_persister: GitPersister instance (optional)
            version_extractor: Version extractor (optional, for version tracking)
            item_type_name: Name for logging (e.g., "config", "function")
        """
        self.extractor = extractor
        self.doc_generator = doc_generator
        self.translation_agent = translation_agent or TranslationAgent()
        self.persister = persister
        self.git_persister = git_persister
        self.version_extractor = version_extractor
        self.item_type_name = item_type_name
        
        logger.info(f"Initialized DocGenerationPipeline for {item_type_name}s")
    
    # ============ Core Pipeline Methods ============
    
    def run(
        self,
        output_dir: str,
        target_langs: List[str] = None,
        force_search_code: bool = False,
        ignore_miss_usage: bool = True,
        only_meta: bool = False,
        without_llm: bool = False,
        limit: Optional[int] = None,
        auto_commit: bool = False,
        create_pr: bool = False,
        name_filter: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the complete documentation generation pipeline.
        
        Workflow:
        1. Extract items from source
        2. Analyze and group by documentation status
        3. Generate docs for items without any (optional)
        4. Process items with Chinese: ZH → EN → Others
        5. Process items with English only: EN → Others
        6. Save all documentation files
        7. Execute git operations (optional)
        """
        if target_langs is None:
            target_langs = ['en', 'zh']
        
        # Pipeline start
        limit_info = f" | Limit: {limit}" if limit else ""
        logger.info(f"Starting {self.item_type_name} Pipeline | Languages: {', '.join(target_langs)}{limit_info}")
        
        # Step 1: Extract items
        logger.info(f"[1/6] Extracting {self.item_type_name}s...")
        items = self.extractor.extract(force_search_code, ignore_miss_usage, **kwargs)
        logger.info(f"  ✓ Extracted {len(items)} items")
        
        # Record meta items count
        stats.record_meta_items(len(items))
        
        if name_filter:
            items = [it for it in items if name_filter == it.name]
            
        ignore_metas = self._read_ignore_meta()
        if ignore_metas:
            items = [it for it in items if it.name not in ignore_metas]
            logger.info(f"  ✓ After ignore meta: {len(items)} items remain")
        
        # Step 1.5: Update item versions (track new if requested, or load from cache)
        if self.version_extractor:
            track_new = kwargs.get('track_version', False)
            self.version_extractor.update_item_versions(items, track_new=track_new)
        
        # Step 2: Analyze and group
        logger.info(f"[2/6] Analyzing documents...")
        groups = self.analyze_and_group(items)
        logger.info(f"  ✓ Groups: zh={len(groups['has_zh'])}, en={len(groups['has_en_only'])}, none={len(groups['has_neither'])}")
        
        if only_meta:
            logger.info("  ⊘ Diff mode: skipping generation and translation")
            return self._build_stats(items, groups, target_langs)

        if not without_llm:
            # Apply limit to items that need processing
            if limit:
                needs_processing = groups['has_zh'] + groups['has_en_only'] + groups['has_neither']
                total_needs_processing = len(needs_processing)
                
                if limit < total_needs_processing:
                    # Take first 'limit' items that need processing
                    limited_items = []
                    for item in needs_processing:
                        if len(limited_items) >= limit:
                            break
                        if len(item.documents) < len(target_langs):
                            limited_items.append(item)
                    
                    limited_names = {item.name for item in limited_items}
                    
                    # Update groups to only include limited items
                    groups['has_zh'] = [item for item in groups['has_zh'] if item.name in limited_names]
                    groups['has_en_only'] = [item for item in groups['has_en_only'] if item.name in limited_names]
                    groups['has_neither'] = [item for item in groups['has_neither'] if item.name in limited_names]
                    
                    logger.info(f"  After limit {limit}/{total_needs_processing}: zh={len(groups['has_zh'])}, en={len(groups['has_en_only'])}, none={len(groups['has_neither'])}")
                    logger.info("  Choose items: " + ", ".join(sorted(limited_names)))
            # Step 3: Generate for items without docs
            if groups['has_neither']:
                if self.doc_generator is None:
                    logger.warning(f"[3/6] Skipped: no doc_generator provided")
                else:
                    logger.info(f"[3/6] Generating {len(groups['has_neither'])} docs...")
                    self._generate_for_missing(groups['has_neither'])
                    # Move to has_en_only group (assuming we generate in English)
                    groups['has_en_only'].extend(groups['has_neither'])
                    groups['has_neither'] = []
                    logger.info(f"  ✓ Generation completed")
            else:
                logger.info(f"[3/6] Skipped: all items have one doc at least")
            
            # Step 4: Process items with Chinese (ZH → EN → Others)
            if groups['has_zh']:
                logger.info(f"[4/6] Translating {len(groups['has_zh'])} items (zh→en→others)...")
                self.process_with_zh(groups['has_zh'], target_langs)
                logger.info(f"  ✓ Chinese-based translation completed")
            else:
                logger.info(f"[4/6] Skipped: no Chinese docs")
            
            # Step 5: Process items with English only (EN → Others)
            if groups['has_en_only']:
                logger.info(f"[5/6] Translating {len(groups['has_en_only'])} items (en→others)...")
                self.process_with_en(groups['has_en_only'], target_langs)
                logger.info(f"  ✓ English-based translation completed")
            else:
                logger.info(f"[5/6] Skipped: no English-only docs")
        
        # Step 6: Save results
        logger.info(f"[6/6] Saving {len(items)} items to {output_dir}...")
        self.persister.save(items, output_dir, target_langs, **kwargs)
        logger.info(f"  ✓ Saved to {output_dir}")
        
        # Step 7: Git operations (optional)
        if auto_commit or create_pr:
            logger.info(f"[7/7] Git operations...")
            success = self.git_persister.execute(languages=target_langs, auto_commit=auto_commit, create_pr=create_pr)
            logger.info(f"  ✓ Git {'committed' if success else 'skipped'}")
        
        logger.info("=" * 60)
        logger.info(f"✅ Pipeline completed - processed {len(items)} items")
        logger.info("=" * 60)
        
        return self._build_stats(items, groups, target_langs)
    
    # ============ Analysis and Grouping ============
    
    def analyze_and_group(self, items: List[T]) -> Dict[str, List[T]]:
        """
        Analyze and group items by documentation status.
        
        Groups items into 3 categories:
        - has_zh: Items with Chinese documentation
        - has_en_only: Items with English but no Chinese
        - has_neither: Items without Chinese or English
        
        This grouping determines the translation strategy:
        - has_zh: ZH → EN → Others
        - has_en_only: EN → Others
        - has_neither: Generate → Translate
        
        Args:
            items: List of items to analyze
        
        Returns:
            Dict with keys 'has_zh', 'has_en_only', 'has_neither'
        """
        groups = {
            'has_zh': [],
            'has_en_only': [],
            'has_neither': []
        }
        
        for item in items:
            # Clean up empty docs
            item.documents = {k: v for k, v in item.documents.items() if v and v.strip() != ""}
            
            docs = item.documents
            has_zh = 'zh' in docs and docs['zh'].strip() != ""
            has_en = 'en' in docs and docs['en'].strip() != ""
            
            if has_zh:
                groups['has_zh'].append(item)
            elif has_en:
                groups['has_en_only'].append(item)
            else:
                groups['has_neither'].append(item)
        
        logger.debug(f"Grouped {self.item_type_name}s: "
                    f"{len(groups['has_zh'])} with ZH, "
                    f"{len(groups['has_en_only'])} with EN only, "
                    f"{len(groups['has_neither'])} with neither")
        
        return groups
    
    # ============ Document Generation ============
    
    def _generate_for_missing(self, items: List[T]) -> None:
        """
        Generate documentation for items without any docs.
        
        Args:
            items: Items without documentation
        """
        if not self.doc_generator:
            logger.warning("Cannot generate: no doc_generator provided")
            return
        
        total = len(items)
        generated_count = 0
        
        for i, item in enumerate(items, 1):
            logger.info(f"  Generating doc {i}/{total}: {item.name}")
            
            try:
                doc = self.doc_generator.generate(item)
                item.documents['en'] = doc  # Default to English
                generated_count += 1
            except Exception as e:
                logger.error(f"  Failed to generate doc for {item.name}: {e}")
                # Add fallback doc
                item.documents['en'] = f"## {item.name}\n\nDocumentation generation failed."
        
        logger.info(f"  Generated {generated_count}/{total} new documents")
    
    # ============ Translation Processing ============
    
    def process_with_zh(self, items: List[T], target_langs: List[str]) -> None:
        """
        Process items with Chinese documentation.
        
        Translation path: ZH → EN → Other languages
        
        Steps:
        1. Translate ZH → EN (if EN is missing)
        2. Translate EN → other target languages
        
        Args:
            items: Items with Chinese documentation
            target_langs: Target languages to generate
        """
        if not items:
            return
        
        logger.debug(f"[Processing {len(items)} items with Chinese docs]")
        
        # Step 1: Ensure all items have English (ZH → EN)
        if 'en' in target_langs:
            self.translate_and_update(
                items=items,
                source_lang='zh',
                target_lang='en'
            )
        
        # Step 2: Translate EN → other languages
        for lang in target_langs:
            if lang in ['zh', 'en']:
                continue  # Skip Chinese and English
            
            self.translate_and_update(
                items=items,
                source_lang='en',
                target_lang=lang
            )
    
    def process_with_en(self, items: List[T], target_langs: List[str]) -> None:
        """
        Process items with English documentation (but no Chinese).
        
        Translation path: EN → All other languages
        
        Args:
            items: Items with English but no Chinese
            target_langs: Target languages to generate
        """
        if not items:
            return
        
        logger.debug(f"[Processing {len(items)} items with English docs only]")
        
        # Translate EN → all other target languages
        for lang in target_langs:
            if lang == 'en':
                continue  # Already have English
            
            self.translate_and_update(
                items=items,
                source_lang='en',
                target_lang=lang
            )
    
    def translate_and_update(
        self,
        items: List[T],
        source_lang: str,
        target_lang: str,
        batch_size: int = DEFAULT_BATCH_SIZE
    ) -> None:
        """
        Batch translate documents and update items in place.
        
        Uses the separator method for consistent batch translation.
        Only translates items missing target language documentation.
        
        Args:
            items: List of items to translate
            source_lang: Source language code (e.g., 'en', 'zh')
            target_lang: Target language code (e.g., 'ja', 'zh')
            batch_size: Number of items per batch
        """
        # Filter items that need translation
        items_need_translation = [
            item for item in items
            if target_lang not in item.documents
            or not item.documents[target_lang]
        ]
        
        if not items_need_translation:
            logger.debug(f"  All items already have {target_lang}")
            return
        
        logger.debug(f"  Translating {len(items_need_translation)} docs: {source_lang} → {target_lang}")
        for item in items_need_translation:
            stats.record_translated_item(item.name)
        
        # Extract source language documents
        source_docs = [item.documents[source_lang] for item in items_need_translation]
        
        # Batch translate with separator method
        try:
            translated_docs = self._translate_with_separators(
                docs=source_docs,
                target_lang=target_lang,
                batch_size=batch_size
            )
            
            # Update item documents
            for item, translated_doc in zip(items_need_translation, translated_docs):
                item.documents[target_lang] = translated_doc

            logger.info(f"  ✓ Updated {len(translated_docs)} {self.item_type_name}s with {target_lang} documents")
        except Exception as e:
            logger.error(f"  Translation failed for {source_lang} → {target_lang}: {e}")
            logger.warning(f"  Skipping translation for {len(items_need_translation)} items")
            # Do not update documents, just skip this translation
    
    # ============ Batch Translation with Separators ============
    
    def _translate_with_separators(
        self,
        docs: List[str],
        target_lang: str,
        batch_size: int = DEFAULT_BATCH_SIZE
    ) -> List[str]:
        """
        Translate multiple docs using separator method for consistency.
        
        The separator method combines multiple documents with unique markers,
        translates them in one LLM call, then splits the result. This ensures:
        - Consistent terminology across documents
        - Fewer LLM API calls
        - Better context for translation
        
        Args:
            docs: List of documents to translate
            target_lang: Target language code
            batch_size: Maximum number of docs per batch
        
        Returns:
            List of translated documents (same order as input)
        """
        if not docs:
            return []
        
        # If docs count is within batch size, process as single batch
        if len(docs) <= batch_size:
            return self._translate_single_batch(docs, target_lang)
        
        # Split into batches
        logger.debug(f"Processing {len(docs)} docs in batches of {batch_size}")
        all_translated = []
        
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(docs) + batch_size - 1) // batch_size
            
            logger.debug(f"  Batch {batch_num}/{total_batches} ({len(batch)} docs)")
            translated_batch = self._translate_single_batch(batch, target_lang)
            all_translated.extend(translated_batch)
        
        return all_translated
    
    def _translate_single_batch(self, docs: List[str], target_lang: str) -> List[str]:
        """
        Translate a single batch of documents.
        
        Args:
            docs: List of documents (within batch size limit)
            target_lang: Target language code
        
        Returns:
            List of translated documents
        """
        if not docs:
            return []
        
        # Combine with separators
        separators = [DEFAULT_SEPARATOR.format(index=i) for i in range(len(docs))]
        combined_text = ""
        for doc, sep in zip(docs, separators):
            combined_text += doc + "\n\n" + sep + "\n\n"
        
        # Translate combined text
        translated_combined = self.translation_agent.translate(
            text=combined_text,
            target_lang=target_lang
        )
        
        # Split by separators
        translated_docs = []
        parts = translated_combined.split(DEFAULT_SEPARATOR.format(index=0))
        
        if len(parts) > 1:
            translated_docs.append(parts[0].strip())
            
            for i in range(1, len(docs)):
                sep = DEFAULT_SEPARATOR.format(index=i)
                parts = parts[i].split(sep) if i < len(parts) else ['']
                translated_docs.append(parts[0].strip())
        else:
            # Fallback: split by double newlines
            logger.warning("Separator split failed, using fallback method")
            translated_docs = [doc.strip() for doc in translated_combined.split('\n\n\n') if doc.strip()]
        
        # Validate count
        if len(translated_docs) != len(docs):
            logger.warning(f"Translation count mismatch: expected {len(docs)}, got {len(translated_docs)}")
            # Pad or trim
            while len(translated_docs) < len(docs):
                translated_docs.append(docs[len(translated_docs)])
            translated_docs = translated_docs[:len(docs)]
        
        return translated_docs
    
    # ============ Statistics ============
    
    def _build_stats(
        self,
        items: List[T],
        groups: Dict[str, List[T]],
        target_langs: List[str]
    ) -> Dict[str, Any]:
        """Build statistics dictionary."""
        return {
            'total': len(items),
            'processed': {
                'has_zh': len(groups['has_zh']),
                'has_en_only': len(groups['has_en_only']),
                'generated': len(groups['has_neither'])
            },
            'languages': target_langs,
            'item_type': self.item_type_name
        }

    def _read_ignore_meta(self) -> List[str]:
        from ..config import config
        ignore_file = Path(config.META_DIR) / 'ignore.meta'
        if not ignore_file.exists():
            return []
        
        with ignore_file.open('r', encoding='utf-8') as f:
            ignores = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Loaded {len(ignores)} ignore patterns from {ignore_file}")
        return ignores

__all__ = ['DocGenerationPipeline', 'DEFAULT_SEPARATOR', 'DEFAULT_BATCH_SIZE']
