"""FEConfigExtractor: Extract config items from Java source code"""

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


class FEConfigExtractor(ItemExtractor):
    item_class = ConfigItem  # Item type for deserialization
    
    def __init__(self, code_paths: List[str] = None):
        """Initialize the config extractor (regex-based, simple and reliable)"""
        self.supported_extensions = {'.java'}
        self.meta_path = Path(config.META_DIR) / "fe_config.meta"
        self.code_paths = code_paths or self._get_source_code_paths()
        Path(self.meta_path).parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"FEConfigExtractor initialized: {len(self.code_paths)} code files")
    
    def _get_default_code_paths(self) -> List[str]:
        """Get default code scanning paths - focus on config-related directories"""
        starrocks_dir = Path(config.STARROCKS_HOME)
        # Focus on config-related paths
        config_paths = [
            "fe/fe-core/src/main/java/com/starrocks/",
        ]
        
        full_paths = [str(starrocks_dir / path) for path in config_paths]
        return full_paths
    
    def _extract_config_items(self, file_path: str) -> List[ConfigItem]:
        """Extract configuration items from Java files using regex (simple and reliable)"""
        # Skip non-Java files
        if not file_path.lower().endswith('config.java'):
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Quick check if file contains @ConfField annotations
            if "@ConfField" not in content:
                return []

            logger.debug(f"Processing file: {file_path}")
            return self._extract_with_regex(content, file_path)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            
        return []
    
    def _extract_with_regex(self, content: str, file_path: str) -> List[ConfigItem]:
        """Extract config items using regex pattern matching
        
        Matches patterns like:
        @ConfField
        public static int log_roll_size_mb = 1024;
        
        @ConfField(mutable = false, comment = "description")
        public static String sys_log_format = "plaintext";
        """
        items: List[ConfigItem] = []
        
        # Pattern to match @ConfField annotation followed by static field declaration
        # Captures: 1) annotation params (optional), 2) field type, 3) field name, 4) default value
        pattern = re.compile(
            r'@ConfField\s*(?:\(([^)]*)\))?\s*'  # @ConfField with optional parameters
            r'(?:@\w+(?:\([^)]*\))?\s*)*'  # Skip other annotations like @Deprecated
            r'(?:public|private|protected)?\s*'  # Optional access modifier
            r'static\s+'  # Must have static
            r'(?:final\s+)?'  # Optional final
            r'([\w\[\]<>,\s]+?)\s+'  # Type (including generics, arrays)
            r'(\w+)\s*'  # Field name
            r'=\s*'  # Assignment
            r'([^;]+);',  # Default value until semicolon
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(content):
            annotation_params_str = match.group(1) or ""
            field_type = match.group(2).strip()
            field_name = match.group(3).strip()
            default_value = match.group(4).strip()
            
            # Parse annotation parameters
            params = code_tools.parse_equals_pair(annotation_params_str)
            
            # Extract comment before this match
            comment = code_tools.extract_cstyle_comment_before_position(content, match.start())
            
            # Get line number
            line_number = content[:match.start()].count('\n') + 1
            
            item = ConfigItem(
                name=field_name,
                type=field_type,
                defaultValue=default_value,
                comment=params.get("comment", comment),
                isMutable=params.get("mutable", "false"),
                scope="FE",
                useLocations=[],
                documents={},
                define=f"{str(file_path)}:{line_number}",
                catalog=None,
                version=None
            )
            
            logger.debug(f"Found config item: {field_name} at line {line_number}")
            items.append(item)
        
        return items

    def _extract_all_items(self, **kwargs) -> List[ConfigItem]:
        """Scan all files in code paths and extract config items"""
        sources_files = self.code_paths

        all_items: List[ConfigItem] = []
        
        for file_path in sources_files:
            try:
                config_items = self._extract_config_items(file_path)
                all_items.extend(config_items)
                
                if config_items:
                    logger.info(f"Found {len(config_items)} config items in {file_path}")
                else:
                    logger.debug(f"No config items found in {file_path}")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")

        # Load existing metadata and merge
        exists_metas = {}
        for meta in self.load_meta():
            exists_metas[meta.name] = meta

        # all_config_items = all_config_items[:limit] if limit is not None else all_config_items
        for meta in all_items:
            if meta.name in exists_metas:
                meta.useLocations = exists_metas[meta.name].useLocations
                meta.documents = exists_metas[meta.name].documents
                meta.catalog = exists_metas[meta.name].catalog
                meta.version = exists_metas[meta.name].version

        # Search for code usages if configured
        if 'force_search_code' in kwargs and kwargs['force_search_code']:
            search_keywords = [k.name for k in all_items]
            search_results = CodeFileSearch(self.code_paths).search(search_keywords)
            
            for item in all_items:
                if item.name in search_results:
                    item.useLocations = search_results[item.name]

        logger.info(f"Total config items found: {len(all_items)}")
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
