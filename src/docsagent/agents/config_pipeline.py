"""
DocGenerationPipeline: Orchestrate the entire documentation generation workflow
"""
import re
from pathlib import Path
from typing import List
from loguru import logger
from collections import defaultdict
from string import Template

from docsagent.agents.config_doc_agent import ConfigDocAgent
from docsagent.agents.translation_agent import TranslationAgent
from docsagent.code_extract.fe_config_parser import FEConfigParser
from docsagent.models import ConfigItem
from docsagent.models import CATALOGS_LANGS
from docsagent.config import DOCS_MODULE_DIR

# Separator for combining multiple documents
DEFAULT_SEPARATOR = "<!-- CONFIG_SEP_{index} -->"

# Maximum number of docs to translate in one batch
DEFAULT_BATCH_SIZE = 10  # Adjust based on average doc length and LLM token limit


class ConfigGenerationPipeline:
    """
    Main pipeline for generating multi-language configuration documentation
    
    Workflow:
        1. Extract configs from source code
        2. Generate English documentation (batch)
        3. Organize into complete Markdown
        4. Translate to Chinese and Japanese
        5. Save output files
    """
    
    def __init__(
        self, 
        doc_agent: ConfigDocAgent = None,
        translation_agent: TranslationAgent = None
    ):
        """
        Initialize the documentation generation pipeline
        
        Args:
            doc_agent: ConfigDocAgent instance (default: create new)
            translation_agent: TranslationAgent instance (default: create new)
        """
        self.doc_agent = doc_agent or ConfigDocAgent()
        self.translation_agent = translation_agent or TranslationAgent()
        logger.info("DocGenerationPipeline initialized")
    
    def run(
        self, 
        output_dir: str,
        target_langs: List[str] = None,
        limit: int = None
    ):
        """
        Run the complete documentation generation pipeline with smart translation
        
        Translation strategy:
        - Has Chinese: ZH → EN → Other languages
        - Has English only: EN → Other languages  
        - Has neither: Generate EN → Other languages
        
        Args:
            config_source: Path to source code directory or file
            output_dir: Directory to save generated documentation
            target_langs: Target languages (default: ['en', 'zh', 'ja'])
            limit: Optional limit on number of configs to process (for testing)
        """
        if target_langs is None:
            target_langs = ['en', 'zh', 'ja']
        
        logger.info("=" * 60)
        logger.info("Starting Documentation Generation Pipeline")
        logger.info(f"Target languages: {', '.join(target_langs)}")
        logger.info("=" * 60)
        
        # Step 1: Extract configs
        logger.info("[Step 1/6] Extracting configuration items...")
        configs = self.extract_configs(limit=limit)
        logger.info(f"✓ Extracted {len(configs)} configuration items")
        
        # Step 2: Analyze and group by document status
        logger.info("[Step 2/6] Analyzing existing documents...")
        groups = self.analyze_and_group_configs(configs)
        logger.info(f"  • Has Chinese: {len(groups['has_zh'])} configs")
        logger.info(f"  • Has English only: {len(groups['has_en_only'])} configs")
        logger.info(f"  • Has neither: {len(groups['has_neither'])} configs")
        
        # Step 3: Generate English for configs without any docs
        if groups['has_neither']:
            logger.info(f"[Step 3/6] Generating English for {len(groups['has_neither'])} configs...")
            self.generate_docs_batch(groups['has_neither'], target_lang='en')
            # Move to has_en_only group
            groups['has_en_only'].extend(groups['has_neither'])
            groups['has_neither'] = []
            logger.info("✓ English generation completed")
        else:
            logger.info("[Step 3/6] All configs have existing documents, skipping generation")
        
        # Step 4: Process configs with Chinese (priority: ZH → EN → Others)
        if groups['has_zh']:
            logger.info(f"[Step 4/6] Processing configs with Chinese documentation...")
            self.process_configs_with_zh(groups['has_zh'], target_langs)
            logger.info("✓ Chinese-based translation completed")
        else:
            logger.info("[Step 4/6] No configs with Chinese docs, skipping")
        
        # Step 5: Process configs with English only (EN → Others)
        if groups['has_en_only']:
            logger.info(f"[Step 5/6] Processing configs with English documentation...")
            self.process_configs_with_en(groups['has_en_only'], target_langs)
            logger.info("✓ English-based translation completed")
        else:
            logger.info("[Step 5/6] No configs with English-only docs, skipping")
        
        # Step 6: Save all languages
        logger.info("[Step 6/6] Saving output files...")
        self.save_documents(configs, output_dir, target_langs)
        logger.info(f"✓ Files saved to {output_dir}")
        
        # Optional: Persist configs for incremental updates
        self.save_meta(configs)
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Pipeline completed successfully!")
        logger.info("=" * 60)
    
    def extract_configs(
        self, 
        limit: int = None
    ) -> List[ConfigItem]:
        """
        Extract configuration items from source code
        
        Args:
            config_source: Path to source code directory
            limit: Optional limit on number of configs (for testing)
        
        Returns:
            List of ConfigItem objects
        """
        parser = FEConfigParser()
        
        # Extract all configs
        all_configs = parser.extract_all_configs()
        
        # Apply limit if specified
        if limit and limit > 0:
            all_configs = all_configs[:limit]
            logger.info(f"Limited to {limit} configs for testing")
        
        return all_configs
    
    def analyze_and_group_configs(
        self, 
        configs: List[ConfigItem]
    ) -> dict:
        """
        Analyze and group configs by document status
        
        Groups configs into 3 categories based on existing documents:
        - has_zh: Configs with Chinese documentation
        - has_en_only: Configs with English but no Chinese
        - has_neither: Configs without Chinese or English
        
        Args:
            configs: List of ConfigItem objects
        
        Returns:
            Dict with keys: 'has_zh', 'has_en_only', 'has_neither'
        """
        groups = {
            'has_zh': [],
            'has_en_only': [],
            'has_neither': []
        }
        
        for config in configs:
            has_zh = 'zh' in config.documents and config.documents['zh']
            has_en = 'en' in config.documents and config.documents['en']
            
            if has_zh:
                groups['has_zh'].append(config)
            elif has_en:
                groups['has_en_only'].append(config)
            else:
                groups['has_neither'].append(config)
        
        logger.debug(f"Grouped configs: {len(groups['has_zh'])} with ZH, "
                    f"{len(groups['has_en_only'])} with EN only, "
                    f"{len(groups['has_neither'])} with neither")
        
        return groups
    
    def generate_docs_batch(
        self, 
        configs: List[ConfigItem],
        target_lang: str = 'en'
    ) -> None:
        """
        Generate documentation for config items and update config.documents directly
        
        Args:
            configs: List of ConfigItem objects
            target_lang: Target language for generation (default: 'en')
        
        Note:
            - Directly updates config.documents[target_lang]
            - Skips configs that already have documents for target_lang
            - No return value (modifies configs in place)
        """
        total = len(configs)
        generated_count = 0
        
        for i, config in enumerate(configs, 1):
            # Skip if already has document for this language
            if target_lang in config.documents and config.documents[target_lang]:
                logger.debug(f"  Skipping {config.name} (already has {target_lang})")
                continue
            
            logger.info(f"  Generating {target_lang} doc {i}/{total}: {config.name}")
            
            try:
                doc = self.doc_agent.generate(config)
                config.documents[target_lang] = doc
                generated_count += 1
            except Exception as e:
                logger.error(f"  Failed to generate doc for {config.name}: {e}")
                # Add fallback doc
                config.documents[target_lang] = f"## {config.name}\n\nDocumentation generation failed."
        
        logger.info(f"  Generated {generated_count}/{total} new {target_lang} documents")
    
    def translate_and_update_docs(
        self,
        configs: List[ConfigItem],
        source_lang: str,
        target_lang: str
    ) -> None:
        """
        Batch translate documents and update config.documents directly
        
        Args:
            configs: List of ConfigItem objects
            source_lang: Source language code (e.g., 'en', 'zh')
            target_lang: Target language code (e.g., 'ja', 'zh')
        
        Note:
            - Only translates configs missing target_lang documents
            - Uses separator method for batch translation
            - Directly updates config.documents[target_lang]
        """
        # Filter configs that need translation
        configs_need_translation = [
            config for config in configs
            if target_lang not in config.documents 
            or not config.documents[target_lang]
        ]
        
        if not configs_need_translation:
            logger.info(f"  All configs already have {target_lang}, skipping")
            return
        
        logger.info(f"  Translating {len(configs_need_translation)} docs: {source_lang} → {target_lang}")
        
        # Extract source language documents
        source_docs = [config.documents[source_lang] for config in configs_need_translation]
        
        # Batch translate
        translated_docs = self.translate_docs_batch(
            docs=source_docs,
            target_lang=target_lang,
            use_separator=True
        )
        
        # Update config.documents
        for config, translated_doc in zip(configs_need_translation, translated_docs):
            config.documents[target_lang] = translated_doc
        
        logger.info(f"  ✓ Updated {len(translated_docs)} configs with {target_lang} documents")
    
    def process_configs_with_zh(
        self,
        configs: List[ConfigItem],
        target_langs: List[str]
    ) -> None:
        """
        Process configs with Chinese documentation
        
        Translation path: ZH → EN → Other languages
        
        Steps:
        1. Translate ZH → EN (if EN is missing)
        2. Translate EN → other target languages
        
        Args:
            configs: Configs with Chinese documentation
            target_langs: Target languages to generate
        """
        if not configs:
            return
        
        logger.info(f"[Processing {len(configs)} configs with Chinese docs]")
        
        # Step 1: Ensure all configs have English (ZH → EN)
        if 'en' in target_langs:
            self.translate_and_update_docs(
                configs=configs,
                source_lang='zh',
                target_lang='en'
            )
        
        # Step 2: Translate EN → other languages
        for lang in target_langs:
            if lang in ['zh', 'en']:
                continue  # Skip Chinese and English
            
            self.translate_and_update_docs(
                configs=configs,
                source_lang='en',
                target_lang=lang
            )
    
    def process_configs_with_en(
        self,
        configs: List[ConfigItem],
        target_langs: List[str]
    ) -> None:
        """
        Process configs with English documentation (but no Chinese)
        
        Translation path: EN → All other languages
        
        Args:
            configs: Configs with English but no Chinese
            target_langs: Target languages to generate
        """
        if not configs:
            return
        
        logger.info(f"\n[Processing {len(configs)} configs with English docs only]")
        
        # Translate EN → all other target languages
        for lang in target_langs:
            if lang == 'en':
                continue  # Already have English
            
            self.translate_and_update_docs(
                configs=configs,
                source_lang='en',
                target_lang=lang
            )
    
    def _generate_toc(self, configs: List[ConfigItem]) -> str:
        """
        Generate table of contents from config items
        
        Args:
            configs: List of ConfigItem objects
        
        Returns:
            Markdown TOC string
        """
        toc_lines = []
        
        for config in configs:
            name = config.name
            # Create anchor link (GitHub style)
            anchor = name.lower().replace('_', '-')
            toc_lines.append(f"- [{name}](#{anchor})")
        
        return "\n".join(toc_lines)
    
    def translate_docs(self, en_markdown: str, target_lang: str) -> str:
        """
        Translate English documentation to target language
        
        Args:
            en_markdown: English Markdown documentation
            target_lang: Target language code ('zh' or 'ja')
        
        Returns:
            Translated Markdown documentation
        """
        return self.translation_agent.translate(en_markdown, target_lang=target_lang)
    
    def translate_docs_batch(
        self, 
        docs: List[str], 
        target_lang: str,
        use_separator: bool = True
    ) -> List[str]:
        """
        Batch translate multiple documents
        
        Args:
            en_docs: List of English documentation strings
            target_lang: Target language code ('zh' or 'ja')
            use_separator: If True, combine docs with separators for consistent translation
        
        Returns:
            List of translated documentation strings (same order as input)
        """
        if not docs:
            return []
        
        if use_separator:
            logger.info(f"Batch translating {len(docs)} docs with separator method")
            return self._translate_with_separators(docs, target_lang)
        else:
            logger.info(f"Batch translating {len(docs)} docs individually")
            return [self.translation_agent.translate(doc, target_lang) for doc in docs]
    
    def _translate_with_separators(
        self, 
        docs: List[str], 
        target_lang: str,
        batch_size: int = DEFAULT_BATCH_SIZE
    ) -> List[str]:
        """
        Translate multiple docs using separator method for consistency
        
        Splits docs into batches to avoid token limits and improve reliability.
        
        Steps:
        1. Split docs into batches
        2. For each batch:
           a. Combine docs with indexed separators
           b. Translate combined text (one LLM call per batch)
           c. Split by separators to get individual translations
        3. Validate and return all translations
        
        Args:
            docs: List of documents to translate
            target_lang: Target language code
            batch_size: Maximum number of docs per batch
        """
        if not docs:
            return []
        
        # If docs count is within batch size, use original logic
        if len(docs) <= batch_size:
            return self._translate_single_batch(docs, target_lang)
        
        # Split into batches
        logger.info(f"Splitting {len(docs)} docs into batches of {batch_size}")
        all_translated = []
        
        for batch_idx in range(0, len(docs), batch_size):
            batch = docs[batch_idx:batch_idx + batch_size]
            batch_num = batch_idx // batch_size + 1
            total_batches = (len(docs) + batch_size - 1) // batch_size
            
            logger.info(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} docs)")
            
            try:
                translated_batch = self._translate_single_batch(batch, target_lang)
                all_translated.extend(translated_batch)
            except Exception as e:
                logger.error(f"  Batch {batch_num} failed: {e}, falling back to individual translation")
                # Fallback: translate each doc in failed batch individually
                for doc in batch:
                    translated = self.translation_agent.translate(doc, target_lang)
                    all_translated.append(translated)
        
        # Final validation
        if len(all_translated) != len(docs):
            logger.error(
                f"Final count mismatch: expected {len(docs)}, got {len(all_translated)}. "
                f"This should not happen!"
            )
        
        logger.info(f"✓ Successfully translated all {len(all_translated)} docs")
        return all_translated
    
    def _translate_single_batch(
        self,
        docs: List[str],
        target_lang: str
    ) -> List[str]:
        """
        Translate a single batch of docs using separator method
        
        This is the core translation logic for one batch.
        """
        # Step 1: Combine with separators
        combined, separator_pattern = self._combine_docs_with_separators(docs)
        logger.debug(f"  Combined {len(docs)} docs into {len(combined)} chars")
        
        # Step 2: Translate (preserve markers)
        try:
            translated_combined = self.translation_agent.translate(
                combined, 
                target_lang, 
                preserve_markers=True
            )
            logger.debug(f"  Translation result: {len(translated_combined)} chars")
        except Exception as e:
            logger.error(f"  Combined translation failed: {e}, falling back to individual translation")
            return [self.translation_agent.translate(doc, target_lang) for doc in docs]
        
        # Step 3: Split by separators
        translated_docs = self._split_by_separators(translated_combined, separator_pattern, len(docs))
        
        # Step 4: Validate
        if len(translated_docs) != len(docs):
            logger.warning(
                f"  Translation split mismatch: expected {len(docs)}, got {len(translated_docs)}. "
                f"Falling back to individual translation."
            )
            return [self.translation_agent.translate(doc, target_lang) for doc in docs]
        
        logger.debug(f"  ✓ Batch translated successfully")
        return translated_docs
    
    def _combine_docs_with_separators(self, docs: List[str]) -> tuple[str, str]:
        """
        Combine multiple docs with indexed separators
        
        Returns:
            (combined_text, separator_pattern)
        """
        parts = []
        
        for i, doc in enumerate(docs):
            parts.append(doc.strip())
            
            # Add separator between docs (not after last one)
            if i < len(docs) - 1:
                separator = DEFAULT_SEPARATOR.format(index=i)
                parts.append(f"\n\n{separator}\n\n")
        
        combined = "".join(parts)
        
        # Pattern for splitting (matches any index)
        separator_pattern = DEFAULT_SEPARATOR.replace("{index}", r"\d+")
        
        return combined, separator_pattern
    
    def _split_by_separators(
        self, 
        text: str, 
        separator_pattern: str, 
        expected_count: int
    ) -> List[str]:
        """
        Split text by separator pattern
        
        Args:
            text: Combined translated text
            separator_pattern: Regex pattern to match separators
            expected_count: Expected number of documents
        
        Returns:
            List of split documents
        """
        # Remove newlines around pattern for cleaner matching
        pattern = r'\s*' + separator_pattern + r'\s*'
        
        # Split by pattern
        parts = re.split(pattern, text)
        
        # Clean up parts
        cleaned_parts = [part.strip() for part in parts if part.strip()]
        
        logger.debug(f"Split result: {len(cleaned_parts)} parts from {expected_count} expected")
        
        return cleaned_parts
    
    def save_documents(
        self,
        configs: List[ConfigItem],
        output_dir: str,
        target_langs: List[str]
    ) -> None:
        """
        Save documentation for all target languages
        
        Extracts documents from config.documents and organizes into Markdown files
        
        Args:
            configs: List of ConfigItem objects with populated documents
            output_dir: Directory to save output files
            target_langs: Languages to save
        """

        target_docs = {k: "" for k in target_langs}

        catalogs = defaultdict(list)
        for config in configs:
            catalogs[config.catalog].append(config)

        for lang in target_langs:
            for catalog in CATALOGS_LANGS:
                # Process each catalog if needed
                if catalog not in catalogs:
                    continue
                
                target_docs[lang] += f"### {CATALOGS_LANGS[catalog][lang]}\n\n"
                for config in sorted(catalogs[catalog]):
                    mk = config.documents.get(lang, '')
                    target_docs[lang] += mk + "\n\n"

            # Save file
            tmpl = Template(open(DOCS_MODULE_DIR / lang / "FE_configuration.md", encoding='utf-8').read())
            output = tmpl.substitute(outputs=target_docs[lang])
            
            output_path = Path(output_dir) / lang / "FE_configuration.md"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding='utf-8')
            logger.info(f"  ✓ Saved {lang}: {output_path}")
    
    def save_meta(
        self,
        configs: List[ConfigItem]
    ) -> None:
        parser = FEConfigParser()
        parser.save_meta_configs(configs=configs)
        
        logger.info(f"  ✓ Persisted {len(configs)} configs")