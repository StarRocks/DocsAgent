"""VariablesExtractor: Extract variable items from Java source code"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from docsagent import config
from docsagent.core import ItemExtractor
from docsagent.domains.models import VariableItem
from docsagent.tools.code_search import CodeFileSearch


class VariablesExtractor(ItemExtractor):
    """
    Extract variable items from StarRocks source.
    
    Uses ExtractorMixin to provide:
    - extract(): Standard extraction flow
    - load_meta(): Meta file loading
    - _get_source_code_paths(): File scanning
    - _should_process_file(): File filtering
    
    Only implements:
    - _get_default_code_paths(): Variables-specific paths
    - _extract_all_items(): Variables-specific extraction logic
    - get_statistics(): Statistics calculation
    """
    
    def __init__(self, code_paths: List[str] = None):
        """Initialize the variables extractor"""
        self.supported_extensions = {'.java', '.h', '.cpp', '.hpp'}
        self.meta_path = Path(config.META_DIR) / "variables.meta"
        self.code_paths = code_paths or self._get_source_code_paths()
        Path(self.meta_path).parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"VariablesExtractor initialized: {len(self.code_paths)} code files")
    
    def _get_default_code_paths(self) -> List[str]:
        """Get default variables code scanning paths (FE + BE)"""
        starrocks_dir = Path(config.STARROCKS_HOME)
        config_paths = [
            "fe/fe-core/src/main/java/com/starrocks/",
            "be/src/"
        ]
        
        full_paths = [str(starrocks_dir / path) for path in config_paths]
        return full_paths
    
    def _extract_config_items(self, file_path: str) -> List[VariableItem]:
        """Extract configuration items from Java files using regex (simple and reliable)"""
        # Skip non-Java files
        if 'variable' not in file_path.lower():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Quick check if file contains @VarAttr annotations
            if "@VarAttr" not in content or "@VariableMgr.VarAttr" not in content:
                return []

            logger.debug(f"Processing file: {file_path}")
            return self._extract_with_regex(content, file_path)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            
        return []
    
    def _extract_with_regex(self, content: str, file_path: str) -> List[VariableItem]:
        pass
    
    
    def _extract_all_items(self, force_search_code: bool = False) -> List[VariableItem]:
        """Scan all files and extract variable items (required by ExtractorMixin)"""
        sources_files = self.code_paths

        all_items: List[VariableItem] = []
        
        for file_path in sources_files:
            try:
                var_items = self._extract_config_items(file_path)
                all_items.extend(var_items)
                
                if var_items:
                    logger.info(f"Found {len(var_items)} variable items in {file_path}")
                else:
                    logger.debug(f"No variable items found in {file_path}")
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

        # Search for code usages if configured
        if force_search_code:
            search_keywords = [k.name for k in all_items]
            search_results = CodeFileSearch(self.code_paths).search(search_keywords)
            
            for item in all_items:
                if item.name in search_results:
                    item.useLocations = search_results[item.name]

        logger.info(f"Total variable items found: {len(all_items)}")
        return all_items
    
    def get_statistics(self, items: List[VariableItem]) -> dict:
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
