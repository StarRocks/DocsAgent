#!/usr/bin/env python3

import os
import re

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from loguru import logger


class CodeFileSearch:
    def __init__(self, code_paths: List[str] = None):
        """Initialize the code file searcher"""
        self.code_paths = code_paths

    def search(self, keyworks: List[str]) -> Dict[str, List[str]]:
        """Search for keywords in the code paths"""
        if not self.code_paths:
            logger.error("No code paths provided for searching.")
            return {}

        results = {}
        for code_path in self.code_paths:
            if not os.path.exists(code_path):
                logger.warning(f"Code path does not exist: {code_path}")
                continue

            logger.debug(f"Searching in code path: {code_path}")
            for root, dirs, files in os.walk(code_path):
                for file in files:
                    file_path = Path(root) / file
                    results.update(self._serach_file(file_path, keyworks))
        return results
    
    def _serach_file(self, file_path: Path, keywords: List[str]) -> Dict[str, List[str]]:
        """Search for keywords in a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self._search_by_keywords(content, keywords) 
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
        return []

    def _search_by_keywords(self, content: str, keywords: List[str]) -> Dict[str, List[str]]:
        """Search for keywords in a single file"""
        found_keywords = []
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', content):
                found_keywords.append(keyword)
                logger.debug(f"Found keyword '{keyword}' in content")
                
        return found_keywords