"""FunctionMetaExtract: Extract function items from individual function documentation files

This module provides functionality to parse SQL function documentation files
in multiple languages (en, ja, zh) and extract function metadata into 
structured FunctionItem objects with aggregated multilingual documentation.

Key differences from config/variable extractors:
1. Each file contains ONE function (not multiple items)
2. Catalog is derived from directory structure
3. Format varies significantly between functions
4. Extraction is "best effort" - we save full document even if parsing fails

Usage:
    # As a script
    python function_meta_extract.py
    
    # As a module
    from docsagent.docs_extract.function_meta_extract import FunctionMetaExtract
    
    # Extract from multiple language files and aggregate
    extractor = FunctionMetaExtract()
    functions = extractor.extract()
    
    # Get statistics
    stats = extractor.get_statistics(functions)
    print(f"Total: {stats['total']}, By catalog: {stats['by_catalog']}")

Features:
    - Scans directory structure to discover all function files
    - Derives catalog/module from directory path
    - Aggregates functions from en, ja, zh documentation
    - Uses English version for metadata when available
    - Stores complete language-specific content in documents field
    - Best-effort extraction of signature, parameters, return type
    - Handles various documentation formats gracefully
    - Saves/loads from JSON format
"""
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger

from docsagent.config import config
from docsagent.domains.models import FunctionItem


class FunctionMetaExtract:
    """Extract function items from individual function documentation files"""
    
    SUPPORTED_LANGS = ['en', 'ja', 'zh']
    PRIMARY_LANG = 'en'  # Use English as primary source for metadata
    
    def __init__(self):
        """Initialize the extractor."""
        # Default paths
        self.docs_dir = Path(config.STARROCKS_HOME) / "docs"
        self.meta_dir = Path(config.META_DIR) / "functions"
        self.functions_doc_path = "sql-reference/sql-functions"
    
    def _discover_function_files(self, lang_dir: Path) -> List[Tuple[str, str, Path]]:
        """
        Discover all function markdown files in a language directory.
        
        Args:
            lang_dir: Path to language directory (e.g., docs/en)
            
        Returns:
            List of tuples: (catalog, module, file_path)
        """
        functions_dir = lang_dir / self.functions_doc_path
        if not functions_dir.exists():
            logger.warning(f"Functions directory not found: {functions_dir}")
            return []
        
        discovered = []
        
        # Scan for function category directories
        for category_dir in functions_dir.iterdir():
            if not category_dir.is_dir():
                continue
            
            category_name = category_dir.name
            
            # Use directory name directly as catalog
            catalog = category_name
            
            # Determine module type (aggregate, window, etc.)
            if 'aggregate' in category_name:
                module = 'Aggregate'
            elif 'window' in category_name:
                module = 'Window'
            elif 'table' in category_name:
                module = 'Table'
            else:
                module = 'Scalar'
            
            # Find all .md files in this category
            for md_file in category_dir.glob('*.md'):
                if md_file.name.upper() not in ['README.MD', 'INDEX.MD']:
                    discovered.append((catalog, module, md_file))
        
        logger.info(f"Discovered {len(discovered)} function files in {lang_dir}")
        return discovered
    
    def _extract_and_aggregate(self) -> List[FunctionItem]:
        """
        Extract functions from all language files and aggregate them.
        
        Uses English version as the primary source for metadata.
        Aggregates documentation content from all languages.
        
        Returns:
            List of FunctionItem objects with multilingual documentation
        """
        logger.info(f"Extracting functions from {self.docs_dir}")
        
        # Discover function files for each language
        all_funcs_by_lang = {}
        
        for lang in self.SUPPORTED_LANGS:
            lang_dir = self.docs_dir / lang
            if not lang_dir.exists():
                logger.warning(f"Language directory not found: {lang_dir}")
                continue
            
            logger.info(f"Processing {lang} version")
            discovered = self._discover_function_files(lang_dir)
            
            # Extract each function
            functions = []
            for catalog, module, file_path in discovered:
                try:
                    func_item = self._extract_single_function(
                        file_path, lang, catalog, module
                    )
                    if func_item:
                        functions.append(func_item)
                except Exception as e:
                    logger.error(f"Error extracting {file_path}: {e}")
            
            all_funcs_by_lang[lang] = functions
            logger.info(f"Extracted {len(functions)} functions from {lang}")
        
        if not all_funcs_by_lang:
            logger.error("No language files found")
            return []
        
        # Use English as primary source if available
        if self.PRIMARY_LANG in all_funcs_by_lang:
            primary_funcs = all_funcs_by_lang[self.PRIMARY_LANG]
        else:
            # Fall back to any available language
            primary_funcs = next(iter(all_funcs_by_lang.values()))
            logger.warning(f"Primary language {self.PRIMARY_LANG} not found, using fallback")
        
        # Create a mapping from name to function for each language
        funcs_by_name = {}
        for lang, funcs_list in all_funcs_by_lang.items():
            funcs_by_name[lang] = {f.name: f for f in funcs_list}
        
        # Aggregate: use primary language metadata, combine documentation
        aggregated = []
        for primary_func in primary_funcs:
            func_name = primary_func.name
            
            # Start with primary version metadata
            aggregated_func = FunctionItem(
                name=primary_func.name,
                alias=primary_func.alias,
                signature=primary_func.signature,
                catalog=primary_func.catalog,
                module=primary_func.module,
                implement_fns=primary_func.implement_fns,
                testCases=primary_func.testCases,
                documents={},
                version=primary_func.version,
                useLocations=primary_func.useLocations
            )
            
            # Aggregate documents from all languages
            for lang in self.SUPPORTED_LANGS:
                if lang in funcs_by_name and func_name in funcs_by_name[lang]:
                    lang_func = funcs_by_name[lang][func_name]
                    if lang in lang_func.documents:
                        aggregated_func.documents[lang] = lang_func.documents[lang]
            
            aggregated.append(aggregated_func)
        
        logger.info(f"Aggregated {len(aggregated)} functions with {len(all_funcs_by_lang)} languages")
        return aggregated
    
    def _extract_single_function(
        self, 
        file_path: Path, 
        lang: str,
        catalog: str,
        module: str
    ) -> Optional[FunctionItem]:
        """
        Extract a single function from a markdown file.
        
        Args:
            file_path: Path to the function markdown file
            lang: Language code
            catalog: Function category (e.g., 'String', 'Math')
            module: Function module type (e.g., 'Scalar', 'Aggregate')
            
        Returns:
            FunctionItem or None if extraction failed
        """
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return None
        
        # Read file content
        content = file_path.read_text(encoding='utf-8')
        
        # Extract function name from filename (without .md extension)
        func_name = file_path.stem
        
        logger.debug(f"Extracting function: {func_name} from {file_path}")
        
        # Try to extract structured information (best effort)
        signature = self._extract_signature(content)
        alias = self._extract_aliases(content, func_name)  # Pass func_name
        version = self._extract_version(content)
        
        # Create FunctionItem with full document content
        return FunctionItem(
            name=func_name,
            alias=alias,
            signature=signature,
            catalog=catalog,
            module=module,
            implement_fns=[],  # Will be filled from source code analysis
            testCases=[],  # Will be filled from test discovery
            documents={lang: content.strip()},
            version=version,
            useLocations=[]  # Will be filled from source code analysis
        )
    
    def _extract_signature(self, content: str) -> List[str]:
        """
        Extract function signature(s) from documentation.
        
        Looks for code blocks after "语法" / "Syntax" / "文法" section.
        
        Returns:
            List of signature strings
        """
        signatures = []
        
        # Pattern to find syntax/signature section
        syntax_patterns = [
            r'##\s+语法\s*\n',  # Chinese
            r'##\s+Syntax\s*\n',  # English
            r'##\s+文法\s*\n',  # Japanese
        ]
        
        for pattern in syntax_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                # Extract content after the heading until next heading or end
                start = match.end()
                # Find next ## heading
                next_heading = re.search(r'\n##\s+', content[start:])
                if next_heading:
                    section_content = content[start:start + next_heading.start()]
                else:
                    section_content = content[start:]
                
                # Extract code blocks
                code_blocks = re.findall(
                    r'```(?:\w+)?\n(.+?)\n```',
                    section_content,
                    re.DOTALL
                )
                
                for block in code_blocks:
                    # Clean up and split multiple signatures
                    lines = [line.strip() for line in block.strip().split('\n') if line.strip()]
                    signatures.extend(lines)
                
                break
        
        return signatures
    
    def _extract_aliases(self, content: str, primary_name: str) -> List[str]:
        """
        Extract function aliases from documentation.
        
        Looks for multiple function names in the title (e.g., "# pow, power, dpow, fpow").
        
        Args:
            content: The document content
            primary_name: The primary function name (from filename)
            
        Returns:
            List of alias names (excluding the primary name)
        """
        aliases = []
        
        # Look for the first heading (# function_name)
        # Pattern: # name1, name2, name3
        title_pattern = r'^#\s+(.+?)$'
        
        for line in content.split('\n')[:20]:  # Check first 20 lines
            match = re.match(title_pattern, line.strip())
            if match:
                title_text = match.group(1).strip()
                
                # Split by comma to get multiple names
                names = [name.strip() for name in title_text.split(',')]
                
                # If we found multiple names, treat others as aliases
                if len(names) > 1:
                    for name in names:
                        # Clean up the name (remove extra spaces, parentheses, etc.)
                        clean_name = re.sub(r'[^\w_]', '', name).lower()
                        if clean_name and clean_name != primary_name.lower():
                            if name.strip() not in aliases:
                                aliases.append(name.strip())
                
                break  # Found the first heading, stop
        
        return aliases
    
    def _extract_version(self, content: str) -> List[str]:
        """
        Extract version information from documentation.
        
        Looks for patterns like:
        - "从 2.4 版本开始"
        - "Since v3.0"
        - "Introduced in v2.5"
        """
        versions = []
        
        # Pattern for version mentions
        version_patterns = [
            r'从\s+([vV]?\d+\.\d+(?:\.\d+)?)\s*版本开始',  # Chinese
            r'[Ss]ince\s+([vV]?\d+\.\d+(?:\.\d+)?)',  # English
            r'[Ii]ntroduced\s+in\s+([vV]?\d+\.\d+(?:\.\d+)?)',  # English
            r'v?(\d+\.\d+(?:\.\d+)?)\s*から',  # Japanese
        ]
        
        for pattern in version_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Normalize version format (ensure it starts with 'v')
                version = match if match.startswith('v') or match.startswith('V') else f'v{match}'
                if version not in versions:
                    versions.append(version)
        
        return versions
    
    def save_to_json(self, functions: List[FunctionItem], meta_dir: Path):
        """
        Save extracted functions to a JSON file.
        
        Args:
            functions: List of FunctionItem objects
            output_file: Path to output JSON file
        """
        # output_path = Path(output_file)
        # output_path.parent.mkdir(parents=True, exist_ok=True)
        
        
        # # Convert to dict
        # data = [func.to_dict() for func in functions]
        
        # # Save to JSON
        # with output_path.open('w', encoding='utf-8') as f:
        #     json.dump(data, f, ensure_ascii=False, indent=2)
        
        meta_dir.mkdir(parents=True, exist_ok=True)
        
        for func in functions:
            func_file = meta_dir / f"{func.name}.json"
            with func_file.open('w', encoding='utf-8') as f:
                json.dump(func.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(functions)} functions to {meta_dir}")
    
    def get_statistics(self, functions: List[FunctionItem]) -> Dict[str, any]:
        """
        Get statistics about the extracted functions.
        
        Args:
            functions: List of FunctionItem objects
            
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total': len(functions),
            'by_catalog': {},
            'by_module': {},
            'with_signature': 0,
            'with_version': 0,
            'with_alias': 0,
            'lang_coverage': {},
        }
        
        for func in functions:
            # Count by catalog
            stats['by_catalog'][func.catalog] = stats['by_catalog'].get(func.catalog, 0) + 1
            
            # Count by module
            stats['by_module'][func.module] = stats['by_module'].get(func.module, 0) + 1
            
            # Count functions with signatures
            if func.signature:
                stats['with_signature'] += 1
            
            # Count functions with version info
            if func.version:
                stats['with_version'] += 1
            
            # Count functions with aliases
            if func.alias:
                stats['with_alias'] += 1
            
            # Count language coverage
            for lang in func.documents:
                stats['lang_coverage'][lang] = stats['lang_coverage'].get(lang, 0) + 1
        
        return stats
    
    def extract(self) -> List[FunctionItem]:
        """Extract all functions."""
        logger.info("=" * 60)
        logger.info("Extracting SQL Function Items")
        logger.info("=" * 60)
        
        # Check if docs_dir exists
        if not self.docs_dir.exists():
            logger.warning(f"Cannot find docs directory at: {self.docs_dir}")
            return []
        
        # Multi-language mode
        logger.info(f"Using multi-language mode from: {self.docs_dir}")
        functions = self._extract_and_aggregate()
        
        # Log statistics
        stats = self.get_statistics(functions)
        logger.info(f"Total: {stats['total']} | With signatures: {stats['with_signature']} | With versions: {stats['with_version']}")
        
        # Log catalog distribution
        if functions:
            catalog_str = ' | '.join([f"{cat}: {count}" for cat, count in sorted(stats['by_catalog'].items())])
            logger.info(f"By Catalog: {catalog_str}")
            
            module_str = ' | '.join([f"{mod}: {count}" for mod, count in sorted(stats['by_module'].items())])
            logger.info(f"By Module: {module_str}")
            
            # Log language coverage
            langs_str = ' | '.join([f"{lang}: {count}" for lang, count in sorted(stats['lang_coverage'].items())])
            logger.info(f"Languages: {langs_str}")
        
        # Log samples
        for i, func in enumerate(functions[:3], 1):
            langs = ','.join(sorted(func.documents.keys()))
            sig_preview = func.signature[0][:50] + '...' if func.signature and func.signature[0] else 'N/A'
            logger.debug(f"Sample {i}: {func.name} ({func.catalog}/{func.module}) [{langs}]")
            logger.debug(f"  Signature: {sig_preview}")
        
        # Save to JSON
        self.save_to_json(functions, str(self.meta_dir))
        logger.info(f"Saved to: {self.meta_dir}")
        
        return functions
