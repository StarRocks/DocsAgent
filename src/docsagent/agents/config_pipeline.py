"""
DocGenerationPipeline: Orchestrate the entire documentation generation workflow
"""
import re
from pathlib import Path
from typing import List
from loguru import logger

from docsagent.agents.config_doc_agent import ConfigDocAgent
from docsagent.agents.translation_agent import TranslationAgent
from docsagent.code_extract.fe_config_parser import FEConfigParser
from docsagent.models import ConfigItem


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
        config_source: str, 
        output_dir: str,
        limit: int = None
    ):
        """
        Run the complete documentation generation pipeline
        
        Args:
            config_source: Path to source code directory or file
            output_dir: Directory to save generated documentation
            limit: Optional limit on number of configs to process (for testing)
        """
        logger.info("=" * 60)
        logger.info("Starting Documentation Generation Pipeline")
        logger.info("=" * 60)
        
        # Step 1: Extract configs
        logger.info("\n[Step 1/5] Extracting configuration items...")
        configs = self.extract_configs(config_source, limit=limit)
        logger.info(f"✓ Extracted {len(configs)} configuration items")
        
        # Step 2: Generate English documentation
        logger.info("\n[Step 2/5] Generating English documentation...")
        en_docs = self.generate_docs_batch(configs)
        logger.info(f"✓ Generated {len(en_docs)} English documents")
        
        # Step 3: Batch translate (using separator method)
        logger.info("\n[Step 3/5] Translating documents...")
        zh_docs = self.translate_docs_batch(en_docs, target_lang='zh', use_separator=True)
        logger.info(f"✓ Chinese translation completed ({len(zh_docs)} docs)")
        
        ja_docs = self.translate_docs_batch(en_docs, target_lang='ja', use_separator=True)
        logger.info(f"✓ Japanese translation completed ({len(ja_docs)} docs)")
        
        # Step 4: Organize into Markdown (can now handle incremental updates)
        logger.info("\n[Step 4/5] Organizing Markdown documents...")
        en_markdown = self.organize_markdown(en_docs, configs)
        zh_markdown = self.organize_markdown(zh_docs, configs)
        ja_markdown = self.organize_markdown(ja_docs, configs)
        logger.info(f"✓ Organized complete documents")
        
        # Step 5: Save outputs
        logger.info("\n[Step 5/5] Saving output files...")
        self.save_outputs(output_dir, en_markdown, zh_markdown, ja_markdown)
        logger.info(f"✓ Files saved to {output_dir}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Pipeline completed successfully!")
        logger.info("=" * 60)
    
    def extract_configs(
        self, 
        config_source: str,
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
        parser = FEConfigParser(code_paths=[config_source])
        
        # Get source files
        source_files = parser._get_source_code_paths()
        
        # Extract all configs
        all_configs = parser.extract_all_configs(source_files)
        
        # Apply limit if specified
        if limit and limit > 0:
            all_configs = all_configs[:limit]
            logger.info(f"Limited to {limit} configs for testing")
        
        return all_configs
    
    def generate_docs_batch(self, configs: List[ConfigItem]) -> List[str]:
        """
        Generate English documentation for all config items
        
        Args:
            configs: List of ConfigItem objects
        
        Returns:
            List of generated English documentation strings
        """
        docs = []
        total = len(configs)
        
        for i, config in enumerate(configs, 1):
            logger.info(f"  Generating doc {i}/{total}: {config.name}")
            
            try:
                doc = self.doc_agent.generate(config)
                docs.append(doc)
            except Exception as e:
                logger.error(f"  Failed to generate doc for {config.name}: {e}")
                # Add fallback doc
                docs.append(f"## {config.name}\n\nDocumentation generation failed.")
        
        return docs
    
    def organize_markdown(
        self, 
        docs: List[str], 
        configs: List[ConfigItem]
    ) -> str:
        """
        Organize individual documentation into a complete Markdown document
        
        Args:
            docs: List of documentation strings
            configs: List of ConfigItem objects (for generating TOC)
        
        Returns:
            Complete Markdown document with TOC
        """
        # Generate Table of Contents
        toc = self._generate_toc(configs)
        
        # Title
        title = "# StarRocks Configuration Reference\n\n"
        
        # Metadata
        metadata = f"*Generated documentation for {len(configs)} configuration items*\n\n"
        
        # TOC section
        toc_section = "## Table of Contents\n\n" + toc + "\n\n"
        
        # Separator
        separator = "---\n\n"
        
        # Configuration details
        details_header = "## Configuration Details\n\n"
        
        # Join all docs with separators
        content = "\n\n---\n\n".join(docs)
        
        # Combine all parts
        full_doc = title + metadata + toc_section + separator + details_header + content
        
        return full_doc
    
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
        en_docs: List[str], 
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
        if not en_docs:
            return []
        
        if use_separator:
            logger.info(f"Batch translating {len(en_docs)} docs with separator method")
            return self._translate_with_separators(en_docs, target_lang)
        else:
            logger.info(f"Batch translating {len(en_docs)} docs individually")
            return [self.translation_agent.translate(doc, target_lang) for doc in en_docs]
    
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
    
    def save_outputs(
        self, 
        output_dir: str, 
        en_markdown: str, 
        zh_markdown: str, 
        ja_markdown: str
    ):
        """
        Save documentation files to output directory
        
        Args:
            output_dir: Output directory path
            en_markdown: English documentation
            zh_markdown: Chinese documentation
            ja_markdown: Japanese documentation
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save English
        en_file = output_path / "config_reference_en.md"
        en_file.write_text(en_markdown, encoding='utf-8')
        logger.info(f"  ✓ Saved: {en_file}")
        
        # Save Chinese
        zh_file = output_path / "config_reference_zh.md"
        zh_file.write_text(zh_markdown, encoding='utf-8')
        logger.info(f"  ✓ Saved: {zh_file}")
        
        # Save Japanese
        ja_file = output_path / "config_reference_ja.md"
        ja_file.write_text(ja_markdown, encoding='utf-8')
        logger.info(f"  ✓ Saved: {ja_file}")
