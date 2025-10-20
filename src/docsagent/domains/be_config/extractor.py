"""BEConfigExtractor: Extract config items from C++ source code"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from docsagent import config
from docsagent.domains.models import ConfigItem
from docsagent.tools.code_search import CodeFileSearch


class BEConfigExtractor:
    """Extract config items from StarRocks BE source (implements ItemExtractor protocol)"""
    
    def __init__(self, code_paths: List[str] = None):
        """Initialize the config extractor (regex-based, simple and reliable)"""
        self.supported_extensions = {'.h', '.hpp', '.cc', '.cpp'}
        self.meta_path = Path(config.META_DIR) / "be_config.meta"
        self.code_paths = code_paths or self._get_source_code_paths()
        Path(self.meta_path).parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"BEConfigExtractor initialized: {len(self.code_paths)} code files")
    
    def _get_default_code_paths(self) -> List[str]:
        """Get default code scanning paths - focus on config-related directories"""
        starrocks_dir = Path(config.STARROCKS_HOME)
        # Focus on config-related paths
        config_paths = [
            "be/src/",
        ]
        
        full_paths = [str(starrocks_dir / path) for path in config_paths]
        return full_paths
    
    def _get_source_code_paths(self) -> List[Path]:
        """Scan and collect all C++ source files from default paths"""
        codes = []
        for code_path in self._get_default_code_paths():
            if not os.path.exists(code_path):
                logger.warning(f"Code path does not exist: {code_path}")
                continue
                
            logger.info(f"Scanning code path: {code_path}")
            
            for root, dirs, files in os.walk(code_path):
                for file in files:
                    file_path = Path(root) / file
                    
                    logger.debug(f"Checking file: {file_path}")
                    
                    if not self._should_process_file(file_path):
                        logger.debug(f"Skipping file: {file_path}")
                        continue

                    codes.append(str(file_path))
        return codes

    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed (exclude test code)"""
        if file_path.suffix not in self.supported_extensions:
            return False
        
        # Skip test directories and files conservatively
        parts_lower = [p.lower() for p in file_path.parts]
        if any(p in {'test', 'tests'} for p in parts_lower):
            return False
        # Common test file naming
        name_lower = file_path.name.lower()
        if name_lower.endswith('test') or name_lower.startswith('test'):
            return False
        
        return True
    
    def _extract_config_items(self, file_path: str) -> List[ConfigItem]:
        """Extract configuration items from C++ files using regex (simple and reliable)"""
        # Skip non-C++ files
        if 'config' not in file_path.lower():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Quick check if file contains CONF_ macros
            if "CONF_" not in content:
                return []

            logger.debug(f"Processing file: {file_path}")
            return self._extract_with_regex(content, file_path)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            
        return []
    
    def _extract_with_regex(self, content: str, file_path: str) -> List[ConfigItem]:
        """Extract config items using regex pattern matching
        
        Matches patterns like:
        CONF_Int32(be_port, "9060");
        CONF_mString(sys_log_level, "INFO");
        CONF_Bool(enable_https, "false");
        CONF_String_enum(brpc_connection_type, "single", "single,pooled,short");
        CONF_Alias(be_http_port, webserver_port);
        
        Where CONF_Type or CONF_mType (mutable) followed by (name, "value");
        """
        items: List[ConfigItem] = []
        
        # Pattern 1: Standard CONF_* macros with quoted default value
        # Captures: 1) mutable flag (m), 2) field type, 3) field name, 4) default value
        standard_pattern = re.compile(
            r'CONF_(m)?'  # CONF_ with optional 'm' for mutable
            r'(\w+)\s*'  # Type (Int32, String, Bool, etc.)
            r'\(\s*'  # Opening parenthesis
            r'(\w+)\s*,\s*'  # Field name followed by comma
            r'"([^"]*)"\s*'  # Default value in quotes
            r'(?:,\s*"[^"]*")?\s*'  # Optional third parameter (for String_enum)
            r'\)',  # Closing parenthesis
            re.MULTILINE
        )
        
        # Pattern 2: CONF_Alias(new_name, old_name) - no quotes
        alias_pattern = re.compile(
            r'CONF_Alias\s*'  # CONF_Alias
            r'\(\s*'  # Opening parenthesis
            r'(\w+)\s*,\s*'  # New name (alias)
            r'(\w+)\s*'  # Old name (target)
            r'\)',  # Closing parenthesis
            re.MULTILINE
        )
        
        # Type mapping for better readability
        type_mapping = {
            'Int16': 'short',
            'Int32': 'int',
            'Int64': 'long',
            'Bool': 'boolean',
            'String': 'string',
            'Strings': 'string[]',
            'String_enum': 'string',  # enum string type
            'Double': 'double',
        }
        
        name_alias: map = {}
        # Extract CONF_Alias configs
        for match in alias_pattern.finditer(content):
            alias_name = match.group(1).strip()
            target_name = match.group(2).strip()
            
            line_number = content[:match.start()].count('\n') + 1
            name_alias[target_name] = alias_name
            logger.debug(f"Found alias config: {alias_name} -> {target_name} at line {line_number}")
                    
        
        # Extract standard CONF_* configs
        for match in standard_pattern.finditer(content):
            is_mutable = match.group(1) is not None  # Check if 'm' prefix exists
            field_type = match.group(2).strip()
            field_name = match.group(3).strip()
            default_value = match.group(4).strip()
            
            # Extract comment before this match
            comment = self._extract_comment_before_position(content, match.start())
            
            # Get line number
            line_number = content[:match.start()].count('\n') + 1
            
            readable_type = type_mapping.get(field_type, field_type)
            
            if field_type == 'string_enum':
                readable_type = 'string'  # Adjust type for enum strings
                enums = match.group(5).strip()  # Enum options (not stored here)
                default_value = default_value  + f' (options: {enums})'
                 
            alias_name = name_alias.get(field_name, None)
            if alias_name:
                field_name = alias_name
                logger.debug(f"Found config item: {field_name}, alias: {alias_name} at line {line_number}")
            else:
                logger.debug(f"Found config item: {field_name} at line {line_number}")

            item = ConfigItem(
                name=field_name,
                type=readable_type,
                defaultValue=default_value,
                comment=comment,
                isMutable="true" if is_mutable else "false",
                scope="BE",
                useLocations=[],
                documents={},
                define=f"{str(file_path)}:{line_number}",
                catalog=None
            )
            
            items.append(item)
        
        return items
    
    
    def _extract_comment_before_position(self, content: str, position: int) -> str:
        """Extract comment (C++Doc, block comment, or line comment) before given position
        
        Looks backwards from position to find:
        - /** ... */ (C++Doc)
        - /* ... */ (block comment)
        - // ... (line comment)
        """
        # Get text before the position
        before_text = content[:position]
        
        # Look for C++Doc comment /** ... */
        javadoc_pattern = re.compile(r'/\*\*\s*(.*?)\s*\*/', re.DOTALL)
        javadoc_matches = list(javadoc_pattern.finditer(before_text))
        if javadoc_matches:
            last_match = javadoc_matches[-1]
            # Check if comment is close to position (within 100 chars of whitespace/newlines)
            gap = before_text[last_match.end():].strip()
            if len(gap) < 100 or not gap:
                comment_text = last_match.group(1)
                # Clean up C++Doc formatting (* at start of lines)
                lines = comment_text.split('\n')
                cleaned_lines = [line.lstrip('* ').strip() for line in lines]
                return ' '.join(line for line in cleaned_lines if line)
        
        # Look for block comment /* ... */
        block_pattern = re.compile(r'/\*\s*(.*?)\s*\*/', re.DOTALL)
        block_matches = list(block_pattern.finditer(before_text))
        if block_matches:
            last_match = block_matches[-1]
            gap = before_text[last_match.end():].strip()
            if len(gap) < 100 or not gap:
                return last_match.group(1).strip()
        
        # Look for line comment //
        line_comment_pattern = re.compile(r'//\s*(.*)$', re.MULTILINE)
        line_matches = list(line_comment_pattern.finditer(before_text))
        if line_matches:
            # Get last few line comments (might be multiple consecutive lines)
            last_comments = []
            for match in reversed(line_matches[-5:]):  # Check last 5 line comments
                gap = before_text[match.end():].strip()
                if len(gap) < 100 or not gap or (last_comments and match.end() > len(before_text) - 200):
                    last_comments.insert(0, match.group(1).strip())
                else:
                    break
            if last_comments:
                return ' '.join(last_comments)
        
        return ""

    def _extract_all_configs(self, limit: Optional[int] = None) -> List[ConfigItem]:
        """Scan all files in code paths and extract config items"""
        sources_files = self.code_paths

        all_config_items: List[ConfigItem] = []
        
        for file_path in sources_files:
            try:
                config_items = self._extract_config_items(file_path)
                all_config_items.extend(config_items)
                
                if config_items:
                    logger.info(f"Found {len(config_items)} config items in {file_path}")
                else:
                    logger.debug(f"No config items found in {file_path}")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")

        # Load existing metadata and merge
        exists_metas = {}
        for meta in self.load_meta_configs():
            exists_metas[meta.name] = meta

        # all_config_items = all_config_items[:limit] if limit is not None else all_config_items
        for meta in all_config_items:
            if meta.name in exists_metas:
                meta.useLocations = exists_metas[meta.name].useLocations
                meta.documents = exists_metas[meta.name].documents
                meta.catalog = exists_metas[meta.name].catalog

        # Search for code usages if configured
        if config.FORCE_RESEARCH_CODE:
            search_keywords = [k.name for k in all_config_items]
            search_results = CodeFileSearch(self.code_paths).search(search_keywords)
            
            for item in all_config_items:
                if item.name in search_results:
                    item.useLocations = search_results[item.name]

        logger.info(f"Total config items found: {len(all_config_items)}")
        return all_config_items

    def load_meta_configs(self) -> List[ConfigItem]:
        """Load config items from saved JSON file"""
        if not os.path.exists(self.meta_path):
            logger.info(f"Config meta file does not exist: {self.meta_path}")
            return []
        
        try:
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            configs = [ConfigItem.from_dict(item) for item in data]
            logger.info(f"Loaded {len(configs)} config items from {self.meta_path}")
            return configs
        except Exception as e:
            logger.error(f"Failed to load configs from {self.meta_path}: {e}")
            return []
    
    def extract(self, limit: Optional[int] = None, **kwargs) -> List[ConfigItem]:
        """Extract config items from source code (implements ItemExtractor protocol)"""
        logger.info("Starting extraction...")
        
        configs = self._extract_all_configs(limit)
        
        if limit is not None:
            configs = configs[:limit]
        
        stats = self.get_statistics(configs)
        logger.info(f"Extracted {len(configs)} items: {stats}")
        
        return configs
    
    def get_statistics(self, items: List[ConfigItem]) -> dict:
        """Calculate basic statistics"""
        stats = {
            "total": len(items),
            "by_scope": {},
            "by_mutability": {"mutable": 0, "immutable": 0},
            "with_docs": {"zh": 0, "en": 0, "ja": 0},
        }
        
        for item in items:
            stats["by_scope"][item.scope] = stats["by_scope"].get(item.scope, 0) + 1
            
            if item.isMutable.lower() == "true":
                stats["by_mutability"]["mutable"] += 1
            else:
                stats["by_mutability"]["immutable"] += 1
            
            for lang in ["zh", "en", "ja"]:
                if lang in item.documents and item.documents[lang]:
                    stats["with_docs"][lang] += 1
        
        return stats
