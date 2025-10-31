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

"""BEConfigExtractor: Extract config items from C++ source code"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from docsagent import config
from docsagent.core.protocols import ItemExtractor
from docsagent.domains.models import ConfigItem
from docsagent.tools.code_search import CodeFileSearch
from docsagent.tools import code_tools


class BEConfigExtractor(ItemExtractor):
    """
    Extract config items from StarRocks BE source.
    
    Uses ExtractorMixin to provide:
    - extract(): Standard extraction flow
    - load_meta(): Meta file loading
    - _get_source_code_paths(): File scanning
    - _should_process_file(): File filtering
    
    Only implements:
    - _get_default_code_paths(): BE-specific paths
    - _extract_all_items(): BE-specific extraction logic
    - get_statistics(): Statistics calculation
    """
    item_class = ConfigItem  # Item type for deserialization
    
    def __init__(self, code_paths: List[str] = None):
        """Initialize the BE config extractor"""
        self.supported_extensions = {'.h', '.hpp', '.cc', '.cpp'}
        self.meta_path = Path(config.META_DIR) / "be_config.meta"
        self.code_paths = code_paths or self._get_source_code_paths()
        Path(self.meta_path).parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"BEConfigExtractor initialized: {len(self.code_paths)} code files")
    
    def _get_default_code_paths(self) -> List[str]:
        """Get default BE code scanning paths"""
        starrocks_dir = Path(config.STARROCKS_HOME)
        config_paths = [
            "be/src/",
        ]
        
        full_paths = [str(starrocks_dir / path) for path in config_paths]
        return full_paths
    
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
            comment = code_tools.extract_cstyle_comment_before_position(content, match.start())
            
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
                catalog=None,
                version=None
            )
            
            items.append(item)
        
        return items

    def _extract_all_items(self, **kwargs) -> List[ConfigItem]:
        """Scan all files and extract config items (required by ExtractorMixin)"""
        sources_files = self.code_paths

        all_items: List[ConfigItem] = []
        
        for file_path in sources_files:
            try:
                config_items = self._extract_config_items(file_path)
                all_items.extend(config_items)
                
                if config_items:
                    logger.debug(f"Found {len(config_items)} config items in {file_path}")
                else:
                    logger.debug(f"No config items found in {file_path}")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")

        # Load existing metadata and merge
        exists_metas = {}
        for meta in self.load_meta():
            exists_metas[meta.name] = meta

        for meta in all_items:
            if meta.name in exists_metas:
                meta.useLocations = exists_metas[meta.name].useLocations
                meta.documents = exists_metas[meta.name].documents
                meta.catalog = exists_metas[meta.name].catalog
                meta.version = exists_metas[meta.name].version

        # Search for code usages if configured
        if 'force_search_code' in kwargs and kwargs['force_search_code']:
            search_keywords = ["config::" + k.name for k in all_items]
            code_search = CodeFileSearch(self.code_paths, file_filter=lambda f: f.suffix in ['.cpp', '.h', '.hpp'])
            search_results = code_search.search(search_keywords)

            for item in all_items:
                if "config::" + item.name in search_results:
                    item.useLocations = search_results["config::" + item.name]

        logger.debug(f"Total config items found: {len(all_items)}")
        return all_items
    
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
