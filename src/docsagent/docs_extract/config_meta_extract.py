"""ConfigMetaExtract: Extract config items from FE_configuration.md and BE_configuration.md

This module provides functionality to parse FE/BE configuration documentation files
in multiple languages (en, ja, zh) and extract configuration items into 
structured ConfigItem objects with aggregated multilingual documentation.

Usage:
    # As a script
    python config_meta_extract.py
    
    # As a module
    from docsagent.docs_extract.config_meta_extract import ConfigMetaExtract
    
    # Extract from multiple language files and aggregate
    extractor = ConfigMetaExtract()
    fe_configs = extractor.extract_fe()
    be_configs = extractor.extract_be()
    
    # Get statistics
    stats = extractor.get_statistics(fe_configs)
    print(f"Total: {stats['total']}, Mutable: {stats['by_mutable']['true']}")

Features:
    - Parses markdown format config documentation in multiple languages
    - Aggregates configs from en, ja, zh documentation
    - Uses English version for metadata (name, type, default, mutable)
    - Stores language-specific content in documents field
    - Extracts config name, type, default value, mutable status, description
    - Handles both FE and BE configurations
    - Extracts version information and catalog
    - Converts to ConfigItem domain model
    - Saves/loads from JSON format
"""
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger

from docsagent.config import config
from docsagent.domains.models import ConfigItem, CATALOGS_LANGS, get_default_catalog


class ConfigMetaExtract:
    """Extract config items from FE/BE configuration documentation in multiple languages"""
    
    SUPPORTED_LANGS = ['en', 'ja', 'zh']
    PRIMARY_LANG = 'en'  # Use English as primary source for metadata
    
    @staticmethod
    def _remove_html_comments(content: str) -> str:
        """Remove HTML comments from markdown content
        
        Args:
            content: Raw markdown content
            
        Returns:
            Content with HTML comments removed
        """
        return re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    
    def __init__(self):
        """Initialize the extractor."""
        # Default paths
        self.docs_dir = Path(config.STARROCKS_HOME) / "docs"
        self.meta_dir = Path(config.META_DIR)
        self.fe_output_file = self.meta_dir / "fe_config.meta"
        self.be_output_file = self.meta_dir / "be_config.meta"
        self.fe_doc_path = "/administration/management/FE_configuration.md"
        self.be_doc_path = "/administration/management/BE_configuration.md"
    
    def _extract_and_aggregate(self, doc_path: str, scope: str) -> List[ConfigItem]:
        """
        Extract configs from all language files and aggregate them.
        
        Uses English version as the primary source for metadata.
        Aggregates documentation content from all languages.
        
        Args:
            doc_path: Relative path to the documentation file
            scope: "FE" or "BE"
        
        Returns:
            List of ConfigItem objects with multilingual documentation
        """
        logger.info(f"Extracting {scope} configs from {self.docs_dir}")
        
        # Extract from each language
        all_configs_by_lang = {}
        for lang in self.SUPPORTED_LANGS:
            lang_file = self.docs_dir / lang / doc_path.lstrip('/')
            if lang_file.exists():
                logger.info(f"Extracting from {lang} version")
                all_configs_by_lang[lang] = self._extract_single(str(lang_file), lang, scope)
            else:
                logger.warning(f"File not found: {lang_file}")
        
        if not all_configs_by_lang:
            logger.error("No language files found")
            return []
        
        # Use English as primary source
        if self.PRIMARY_LANG not in all_configs_by_lang:
            logger.error(f"Primary language {self.PRIMARY_LANG} not found")
            return []
        
        primary_configs = all_configs_by_lang[self.PRIMARY_LANG]
        
        # Create a mapping from name to config for each language
        configs_by_name = {}
        for lang, configs_list in all_configs_by_lang.items():
            configs_by_name[lang] = {c.name: c for c in configs_list}
        
        # Aggregate: use English metadata, combine documentation
        aggregated = []
        for primary_config in primary_configs:
            config_name = primary_config.name
            
            # Start with English version metadata
            aggregated_config = ConfigItem(
                name=primary_config.name,
                type=primary_config.type,
                defaultValue=primary_config.defaultValue,
                comment=primary_config.comment,
                isMutable=primary_config.isMutable,
                scope=primary_config.scope,
                define=primary_config.define,
                documents={},
                catalog=primary_config.catalog,
                version=primary_config.version,
                useLocations=primary_config.useLocations
            )
            
            # Aggregate documents from all languages
            for lang in self.SUPPORTED_LANGS:
                if lang in configs_by_name and config_name in configs_by_name[lang]:
                    lang_config = configs_by_name[lang][config_name]
                    if lang in lang_config.documents:
                        aggregated_config.documents[lang] = lang_config.documents[lang]
            
            aggregated.append(aggregated_config)
        
        logger.info(f"Aggregated {len(aggregated)} {scope} configs with {len(all_configs_by_lang)} languages")
        return aggregated
    
    def _extract_single(self, md_file: str, lang: str, scope: str) -> List[ConfigItem]:
        """Extract configs from a single language file."""
        md_path = Path(md_file)
        if not md_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {md_file}")
        
        logger.info(f"Extracting {scope} configs from {md_file} (lang: {lang})")
        content = md_path.read_text(encoding='utf-8')
        
        # Remove HTML comments
        content = self._remove_html_comments(content)
        
        # Find config parameters section
        # For FE: "Understand FE parameters" / "FE 参数描述"
        # For BE: "Understand BE parameters" / "BE 参数描述"
        section_patterns = [
            r'##\s+Understand\s+' + scope + r'\s+[Pp]arameters?\n',  # English: "Understand FE/BE parameters"
            r'##\s+' + scope + r'\s+[Pp]arameter.*[Dd]escription.*\n',  # English alternative
            r'##\s+' + scope + r'\s+参数描述\n',  # Chinese
            r'##\s+' + scope + r'\s+.*パラメータ.*説明.*\n',  # Japanese
        ]
        
        configs = []
        start_pos = None
        
        for pattern in section_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                start_pos = match.end()
                logger.debug(f"Found section with pattern: {pattern}")
                break
        
        if start_pos is None:
            logger.warning(f"Could not find parameter description section in {md_file}")
            return []
        
        # Extract configs section by section
        config_section = content[start_pos:]
        configs = self._parse_configs_by_catalog(config_section, lang, scope)
        
        logger.info(f"Extracted {len(configs)} {scope} configs from {lang}")
        return configs
    
    def _parse_configs_by_catalog(self, section: str, lang: str, scope: str) -> List[ConfigItem]:
        """Parse config section organized by catalogs (### headings)."""
        configs = []
        
        # Split by catalog headings (### or ####)
        catalog_pattern = r'\n(#{3,5})\s+(.+?)\n'
        parts = re.split(catalog_pattern, section)
        
        current_catalog = get_default_catalog()  # Default catalog
        
        # Iterate through the parts: [text_before_first_heading, level1, title1, content1, level2, title2, content2, ...]
        i = 1  # Skip the first part (content before first heading)
        while i < len(parts):
            if i + 2 >= len(parts):
                break
                
            heading_level = parts[i]
            heading_text = parts[i + 1].strip()
            content = parts[i + 2] if i + 2 < len(parts) else ""
            
            # Level 3 headings are catalogs
            if len(heading_level) == 3:
                current_catalog = self._normalize_catalog(heading_text, lang)
                logger.debug(f"Found catalog: {heading_text} -> {current_catalog}")
            
            # Level 5 headings are config items
            elif len(heading_level) == 5:
                config_name = heading_text.strip()
                logger.debug(f"Found config item: {config_name}")
                try:
                    if config_item := self._parse_config_block(
                        config_name, content, lang, scope, current_catalog
                    ):
                        configs.append(config_item)
                except Exception as e:
                    logger.error(f"Error parsing config {config_name}: {e}")
            
            i += 3  # Move to next heading (level, title, content)
        
        return configs
    
    def _normalize_catalog(self, catalog_text: str, lang: str) -> str:
        """Normalize catalog name to English standard name."""
        # Try to match with known catalogs
        for standard_name, translations in CATALOGS_LANGS.items():
            for trans_lang, trans_text in translations.items():
                if catalog_text.lower().strip() == trans_text.lower().strip():
                    return standard_name
        
        # Return default if no match
        logger.warning(f"Unknown catalog: {catalog_text} (lang: {lang}), using default")
        return get_default_catalog()
    
    def _parse_config_block(
        self, 
        config_name: str, 
        block: str, 
        lang: str, 
        scope: str,
        catalog: str
    ) -> Optional[ConfigItem]:
        """Parse a single config block."""
        if not block.strip():
            return None
        
        # Extract properties from bullet points
        props = self._extract_properties(block)
        
        # Get multilingual properties with fallbacks
        default_value = (
            props.get('Default') or props.get('默认值') or 
            props.get('デフォルト') or props.get('デフォルト値', '')
        )
        
        data_type = (
            props.get('Type') or props.get('类型') or 
            props.get('タイプ') or props.get('型', 'String')
        )
        
        # Extract mutable status
        is_mutable = self._extract_mutable_status(props, lang)
        
        description = (
            props.get('Description') or props.get('描述') or 
            props.get('说明') or props.get('説明', '')
        )
        
        unit = props.get('Unit') or props.get('单位') or props.get('単位', '')
        
        introduced = (
            props.get('Introduced in') or props.get('引入版本') or 
            props.get('導入バージョン', '')
        )
        
        # Build comment
        comment = description
        if unit and unit not in ['-', '']:
            comment = f"{description} Unit: {unit}" if description else f"Unit: {unit}"
        
        return ConfigItem(
            name=config_name,
            type=data_type,
            defaultValue=default_value,
            comment=comment,
            isMutable=is_mutable,
            scope=scope,
            define="",  # Will be filled from source code parsing
            documents={lang: block.strip()},
            catalog=catalog,
            version=[introduced] if introduced else [],
            useLocations=[]
        )
    
    def _extract_mutable_status(self, props: Dict[str, str], lang: str) -> str:
        """Extract whether config is mutable (dynamic)."""
        # Try different property names
        mutable_keys = [
            'Is dynamic', '是否动态', 'Dynamic', 
            'ダイナミック', '動的', 'Mutable'
        ]
        
        for key in mutable_keys:
            if key in props:
                value = props[key].lower()
                # Check for positive indicators
                if any(indicator in value for indicator in ['yes', '是', 'true', 'はい']):
                    return "true"
                # Check for negative indicators
                elif any(indicator in value for indicator in ['no', '否', 'false', 'いいえ']):
                    return "false"
        
        # Default to false (static) if not found
        return "false"
    
    def _extract_properties(self, block: str) -> Dict[str, str]:
        """Extract properties from bullet points (- **PropertyName**: Value)."""
        properties = {}
        
        # Pattern for markdown list items with bold property names
        pattern = r'[-*]\s+(?:\*\*|__)?([^*_:]+?)(?:\*\*|__)?[:：]\s*(.+?)(?=\n[-*]\s+(?:\*\*|__)?[^*_:]+?(?:\*\*|__)?[:：]|\n\n|\Z)'
        
        for match in re.finditer(pattern, block, re.DOTALL):
            prop_name = match.group(1).strip()
            prop_value = ' '.join(match.group(2).strip().split())  # Clean whitespace
            properties[prop_name] = prop_value
        
        return properties
    
    def save_to_json(self, configs: List[ConfigItem], output_file: str):
        """
        Save extracted configs to a JSON file.
        
        Args:
            configs: List of ConfigItem objects
            output_file: Path to output JSON file
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict
        data = [cfg.to_dict() for cfg in configs]
        
        # Save to JSON
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(configs)} configs to {output_file}")
    
    def get_statistics(self, configs: List[ConfigItem]) -> Dict[str, any]:
        """
        Get statistics about the extracted configs.
        
        Args:
            configs: List of ConfigItem objects
            
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total': len(configs),
            'by_scope': {},
            'by_type': {},
            'by_catalog': {},
            'by_mutable': {},
            'with_version': 0,
            'with_default': 0,
        }
        
        for cfg in configs:
            # Count by scope
            stats['by_scope'][cfg.scope] = stats['by_scope'].get(cfg.scope, 0) + 1
            
            # Count by type
            stats['by_type'][cfg.type] = stats['by_type'].get(cfg.type, 0) + 1
            
            # Count by catalog
            stats['by_catalog'][cfg.catalog] = stats['by_catalog'].get(cfg.catalog, 0) + 1
            
            # Count by mutable status
            stats['by_mutable'][cfg.isMutable] = stats['by_mutable'].get(cfg.isMutable, 0) + 1
            
            # Count configs with version info
            if cfg.version:
                stats['with_version'] += 1
            
            # Count configs with default value
            if cfg.defaultValue:
                stats['with_default'] += 1
        
        return stats
    
    def extract_fe(self) -> List[ConfigItem]:
        """Extract FE configuration items."""
        logger.info("=" * 60)
        logger.info("Extracting FE Configuration Items")
        logger.info("=" * 60)
        
        # Check if docs_dir exists and has subdirectories
        if not self.docs_dir.exists() or not (self.docs_dir / "en").exists():
            logger.warning(f"Cannot find docs directory at: {self.docs_dir}")
            return []
        
        # Multi-language mode
        logger.info(f"Using multi-language mode from: {self.docs_dir}")
        configs = self._extract_and_aggregate(self.fe_doc_path, "FE")
        
        # Log statistics
        stats = self.get_statistics(configs)
        logger.info(f"Total: {stats['total']} | Mutable: {stats['by_mutable'].get('true', 0)} | Static: {stats['by_mutable'].get('false', 0)}")
        
        # Log catalog distribution
        if configs:
            catalog_str = ' | '.join([f"{cat}: {count}" for cat, count in sorted(stats['by_catalog'].items())])
            logger.info(f"Catalogs: {catalog_str}")
            
            # Log language coverage
            lang_coverage = {lang: sum(1 for c in configs if lang in c.documents) for lang in self.SUPPORTED_LANGS}
            langs_str = ' | '.join([f"{lang}: {count}" for lang, count in sorted(lang_coverage.items()) if count > 0])
            logger.info(f"Languages: {langs_str}")
        
        # Log samples
        for i, cfg in enumerate(configs[:3], 1):
            default = cfg.defaultValue[:30] + '...' if len(cfg.defaultValue) > 30 else cfg.defaultValue
            langs = ','.join(sorted(cfg.documents.keys()))
            logger.debug(f"Sample {i}: {cfg.name} ({cfg.catalog}) [{langs}] = {default}")
        
        # Save to JSON
        self.save_to_json(configs, str(self.fe_output_file))
        logger.info(f"Saved to: {self.fe_output_file}")
        
        return configs
    
    def extract_be(self) -> List[ConfigItem]:
        """Extract BE configuration items."""
        logger.info("=" * 60)
        logger.info("Extracting BE Configuration Items")
        logger.info("=" * 60)
        
        # Check if docs_dir exists and has subdirectories
        if not self.docs_dir.exists() or not (self.docs_dir / "en").exists():
            logger.warning(f"Cannot find docs directory at: {self.docs_dir}")
            return []
        
        # Multi-language mode
        logger.info(f"Using multi-language mode from: {self.docs_dir}")
        configs = self._extract_and_aggregate(self.be_doc_path, "BE")
        
        # Log statistics
        stats = self.get_statistics(configs)
        logger.info(f"Total: {stats['total']} | Mutable: {stats['by_mutable'].get('true', 0)} | Static: {stats['by_mutable'].get('false', 0)}")
        
        # Log catalog distribution
        if configs:
            catalog_str = ' | '.join([f"{cat}: {count}" for cat, count in sorted(stats['by_catalog'].items())])
            logger.info(f"Catalogs: {catalog_str}")
            
            # Log language coverage
            lang_coverage = {lang: sum(1 for c in configs if lang in c.documents) for lang in self.SUPPORTED_LANGS}
            langs_str = ' | '.join([f"{lang}: {count}" for lang, count in sorted(lang_coverage.items()) if count > 0])
            logger.info(f"Languages: {langs_str}")
        
        # Log samples
        for i, cfg in enumerate(configs[:3], 1):
            default = cfg.defaultValue[:30] + '...' if len(cfg.defaultValue) > 30 else cfg.defaultValue
            langs = ','.join(sorted(cfg.documents.keys()))
            logger.debug(f"Sample {i}: {cfg.name} ({cfg.catalog}) [{langs}] = {default}")
        
        # Save to JSON
        self.save_to_json(configs, str(self.be_output_file))
        logger.info(f"Saved to: {self.be_output_file}")
        
        return configs
