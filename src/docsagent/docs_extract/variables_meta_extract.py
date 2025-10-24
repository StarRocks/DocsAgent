"""VariablesMetaExtract: Extract variable items from System_variable.md

This module provides functionality to parse System_variable.md documentation files
in multiple languages (en, ja, zh) and extract session/global variables into 
structured VariableItem objects with aggregated multilingual documentation.

Usage:
    # As a script
    python variables_meta_extract.py [docs_dir] [output_json_file]
    
    # As a module
    from docsagent.docs_extract.variables_meta_extract import VariablesMetaExtract
    
    # Extract from multiple language files and aggregate
    extractor = VariablesMetaExtract("tests/docs")
    variables = extractor.extract_and_aggregate()
    extractor.save_to_json(variables, "output.json")
    
    # Get statistics
    stats = extractor.get_statistics(variables)
    print(f"Total: {stats['total']}, Global: {stats['by_scope']['Global']}")

Features:
    - Parses markdown format variable documentation in multiple languages
    - Aggregates variables from en, ja, zh documentation
    - Uses English version for metadata (name, type, default, scope)
    - Stores language-specific content in documents field
    - Extracts variable name, type, default value, scope, description
    - Handles both Global and Session variables
    - Extracts version information
    - Converts to VariableItem domain model
    - Saves/loads from JSON format
"""
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from docsagent.config import config
from docsagent.domains.models import VariableItem


class VariablesMetaExtract:
    """Extract variable items from System_variable.md documentation in multiple languages"""
    
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
        """
        Initialize the extractor.
        
        Args:
            docs_dir: Path to docs directory containing en/ja/zh subdirectories
                     Each should have System_variable.md
        """
        # Default paths
        self.docs_dir = Path(config.STARROCKS_HOME) / "docs"
        self.output_file = Path(config.META_DIR) / "variables.meta"
        self.doc_path = "/sql-reference/System_variable.md"
    
    def _extract_and_aggregate(self) -> List[VariableItem]:
        """
        Extract variables from all language files and aggregate them.
        
        Uses English version as the primary source for metadata.
        Aggregates documentation content from all languages.
        
        Returns:
            List of VariableItem objects with multilingual documentation
        """
        logger.info(f"Extracting variables from {self.docs_dir}")
        
        # Extract from each language
        all_vars_by_lang = {}
        for lang in self.SUPPORTED_LANGS:
            lang_file = self.docs_dir / lang / self.doc_path.lstrip('/')
            if lang_file.exists():
                logger.debug(f"Extracting from {lang} version")
                all_vars_by_lang[lang] = self._extract_single(str(lang_file), lang)
            else:
                logger.warning(f"File not found: {lang_file}")
        
        if not all_vars_by_lang:
            logger.error("No language files found")
            return []
        
        # Use English as primary source
        if self.PRIMARY_LANG not in all_vars_by_lang:
            logger.error(f"Primary language {self.PRIMARY_LANG} not found")
            return []
        
        primary_vars = all_vars_by_lang[self.PRIMARY_LANG]
        
        # Create a mapping from name to variable for each language
        vars_by_name = {}
        for lang, vars_list in all_vars_by_lang.items():
            vars_by_name[lang] = {v.name: v for v in vars_list}
        
        # Aggregate: use English metadata, combine documentation
        aggregated = []
        for primary_var in primary_vars:
            var_name = primary_var.name
            
            # Start with English version metadata
            aggregated_var = VariableItem(
                name=primary_var.name,
                show=primary_var.show,
                type=primary_var.type,
                defaultValue=primary_var.defaultValue,
                comment=primary_var.comment,
                invisible=primary_var.invisible,
                scope=primary_var.scope,
                documents={},
                version=primary_var.version,
                useLocations=primary_var.useLocations
            )
            
            # Aggregate documents from all languages
            for lang in self.SUPPORTED_LANGS:
                if lang in vars_by_name and var_name in vars_by_name[lang]:
                    lang_var = vars_by_name[lang][var_name]
                    if lang in lang_var.documents:
                        aggregated_var.documents[lang] = lang_var.documents[lang]
            
            aggregated.append(aggregated_var)
        
        logger.info(f"Aggregated {len(aggregated)} variables with {len(all_vars_by_lang)} languages")
        return aggregated
    
    def _extract_single(self, md_file: str, lang: str = 'en') -> List[VariableItem]:
        """Extract variables from a single language file."""
        md_path = Path(md_file)
        if not md_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {md_file}")
        
        logger.info(f"Extracting variables from {md_file} (lang: {lang})")
        content = md_path.read_text(encoding='utf-8')
        
        # Remove HTML comments
        content = self._remove_html_comments(content)
        
        # Find variables section with multi-language support
        section_patterns = [
            r'##\s+Descriptions of variables\s*\n',  # English
            r'##\s+変数の説明\s*\n',  # Japanese
            r'##\s+支持的变量\s*\n',  # Chinese
        ]
        
        for pattern in section_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                start_pos = match.end()
                variables_section = content[start_pos:]
                # Stop at next ## heading
                next_section = re.search(r'\n##\s+', variables_section)
                if next_section:
                    variables_section = variables_section[:next_section.start()]
                
                variables = self._parse_variables_section(variables_section, lang)
                logger.info(f"Extracted {len(variables)} variables from {lang}")
                return variables
        
        logger.warning(f"Could not find variables section in {md_file}")
        return []
    
    def _parse_variables_section(self, section: str, lang: str = 'en') -> List[VariableItem]:
        """Parse variables section and extract individual variables."""
        variables = []
        variable_blocks = re.split(r'\n###\s+', section)
        
        for block in variable_blocks[1:]:  # Skip first split (section header)
            try:
                if variable := self._parse_variable_block(block, lang):
                    variables.append(variable)
            except Exception as e:
                logger.error(f"Error parsing variable block: {e}")
        
        return variables
    
    def _parse_variable_block(self, block: str, lang: str = 'en') -> Optional[VariableItem]:
        """Parse a single variable block."""
        if not (lines := block.strip().split('\n')):
            return None
        
        # Extract variable name and scope from first line
        name_match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\((global|session|全局|会话)\))?', lines[0].strip())
        if not name_match:
            logger.warning(f"Could not extract variable name from: {lines[0]}")
            return None
        
        name = name_match.group(1)
        scope_marker = name_match.group(2)
        scope = "Global" if scope_marker and scope_marker.lower() in ['global', '全局'] else "Session"
        
        # Extract properties from bullet points
        props = self._extract_properties(block)
        
        # Get multilingual properties with fallbacks
        description = props.get('Description') or props.get('description') or props.get('描述') or props.get('说明', '')
        default_value = props.get('Default') or props.get('default') or props.get('默认值', '')
        data_type = props.get('Data type') or props.get('Type') or props.get('类型') or props.get('数据类型', 'String')
        introduced = props.get('Introduced in') or props.get('introduced in') or props.get('引入版本', '')
        unit = props.get('Unit') or props.get('单位', '')
        
        # Build comment
        comment = description
        if unit:
            comment = f"{description} Unit: {unit}" if description else f"Unit: {unit}"
        
        # Reconstruct the full document with ### heading
        full_doc = f"### {block.strip()}"
        
        return VariableItem(
            name=name,
            show=name,
            type=data_type,
            defaultValue=default_value,
            comment=comment,
            invisible=False,
            scope=scope,
            documents={lang: full_doc},
            version=[introduced] if introduced else [],
            useLocations=[]
        )
    
    def _extract_properties(self, block: str) -> Dict[str, str]:
        """Extract properties from bullet points (* **PropertyName**: Value)."""
        properties = {}
        pattern = r'\*\s+\*\*([^*:]+)\*\*:\s*(.+?)(?=\n\*\s+\*\*|\n\n|\Z)'
        
        for match in re.finditer(pattern, block, re.DOTALL):
            prop_name = match.group(1).strip()
            prop_value = ' '.join(match.group(2).strip().split())  # Clean whitespace
            properties[prop_name] = prop_value
        
        return properties
    
    def save_to_json(self, variables: List[VariableItem], output_file: str):
        """
        Save extracted variables to a JSON file.
        
        Args:
            variables: List of VariableItem objects
            output_file: Path to output JSON file
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict
        data = [var.to_dict() for var in variables]
        
        # Save to JSON
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(variables)} variables to {output_file}")
    
    def get_statistics(self, variables: List[VariableItem]) -> Dict[str, any]:
        """
        Get statistics about the extracted variables.
        
        Args:
            variables: List of VariableItem objects
            
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total': len(variables),
            'by_scope': {},
            'by_type': {},
            'with_version': 0,
            'with_default': 0,
        }
        
        for var in variables:
            # Count by scope
            stats['by_scope'][var.scope] = stats['by_scope'].get(var.scope, 0) + 1
            
            # Count by type
            stats['by_type'][var.type] = stats['by_type'].get(var.type, 0) + 1
            
            # Count variables with version info
            if var.version:
                stats['with_version'] += 1
            
            # Count variables with default value
            if var.defaultValue:
                stats['with_default'] += 1
        
        return stats

    def extract(self):

        # Check if docs_dir exists and has subdirectories
        if self.docs_dir.exists() and (self.docs_dir / "en").exists():
            # Multi-language mode
            logger.info(f"Using multi-language mode from: {self.docs_dir}")
            variables = self._extract_and_aggregate()
        else:
            logger.warning(f"Cannot find docs directory at: {self.docs_dir}")
            return 
        
        # Log statistics
        stats = self.get_statistics(variables)
        logger.info(f"Total: {stats['total']} | Global: {stats['by_scope'].get('Global', 0)} | Session: {stats['by_scope'].get('Session', 0)}")
        
        # Log language coverage
        if variables:
            lang_coverage = {lang: sum(1 for v in variables if lang in v.documents) for lang in ['en', 'ja', 'zh']}
            langs_str = ' | '.join([f"{lang}: {count}" for lang, count in sorted(lang_coverage.items()) if count > 0])
            logger.info(f"Languages: {langs_str}")
        
        # Log samples
        for i, var in enumerate(variables[:3], 1):
            default = var.defaultValue[:20] + '...' if len(var.defaultValue) > 20 else var.defaultValue
            langs = ','.join(sorted(var.documents.keys()))
            logger.debug(f"Sample {i}: {var.name} ({var.scope}) [{langs}] = {default}")
        
        # Save to JSON
        self.save_to_json(variables, str(self.output_file))
        logger.info(f"Saved to: {self.output_file}")
        
        return variables
