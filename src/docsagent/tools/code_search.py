#!/usr/bin/env python3

import os
import re
from collections import defaultdict

from pathlib import Path
from typing import Dict, List, Set
from loguru import logger


class CodeFileSearch:
    def __init__(self, code_paths: List[str] = None):
        """Initialize the code file searcher"""
        self.code_paths = code_paths
        # Pre-compile regex pattern for better performance
        self._compiled_patterns = {}

    def search(self, keyworks: List[str]) -> Dict[str, List[str]]:
        """Search for keywords in the code paths"""
        if not self.code_paths:
            logger.error("No code paths provided for searching.")
            return {}

        # Pre-compile all keyword patterns
        self._compile_patterns(keyworks)
        
        # Build combined pattern for fast initial filtering
        combined_pattern = self._build_combined_pattern(keyworks)

        results = defaultdict(list)
        file_count = 0
        
        for code_path in self.code_paths:
            if not os.path.exists(code_path):
                logger.warning(f"Code path does not exist: {code_path}")
                continue

            logger.debug(f"Searching in code path: {code_path}")
            for root, dirs, files in os.walk(code_path):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix not in ['.java', '.cpp', '.h', '.hpp']:
                        continue
                    
                    file_count += 1
                    found_keywords = self._search_file(file_path, keyworks, combined_pattern)
                    
                    # Build result dict: {keyword: [file_paths]}
                    for keyword in found_keywords:
                        results[keyword].append(str(file_path))
        
        logger.info(f"Searched {file_count} files, found {len(results)} keywords")
        return dict(results)
    
    def _compile_patterns(self, keywords: List[str]):
        """Pre-compile regex patterns for keywords"""
        if self._compiled_patterns:
            return  # Already compiled
        
        for keyword in keywords:
            try:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                self._compiled_patterns[keyword] = re.compile(pattern)
            except re.error as e:
                logger.warning(f"Failed to compile pattern for keyword '{keyword}': {e}")
    
    def _build_combined_pattern(self, keywords: List[str]) -> re.Pattern:
        """Build a combined regex pattern for fast initial filtering"""
        # Escape all keywords and join with OR
        escaped_keywords = [re.escape(kw) for kw in keywords]
        combined = r'\b(' + '|'.join(escaped_keywords) + r')\b'
        return re.compile(combined)
    
    def _search_file(self, file_path: Path, keywords: List[str], combined_pattern: re.Pattern) -> Set[str]:
        """Search for keywords in a single file using optimized approach"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Fast initial check: if no keywords found, skip detailed search
            if not combined_pattern.search(content):
                return set()
            
            # Detailed search: find which specific keywords match
            found_keywords = set()
            for keyword in keywords:
                pattern = self._compiled_patterns.get(keyword)
                if pattern and pattern.search(content):
                    found_keywords.add(keyword)
                    logger.debug(f"Found keyword '{keyword}' in {file_path}")
            
            return found_keywords
            
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return set()