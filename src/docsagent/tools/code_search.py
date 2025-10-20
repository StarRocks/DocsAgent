#!/usr/bin/env python3

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple
from loguru import logger

import hyperscan


class CodeFileSearch:
    def __init__(self, code_paths: List[str] = None):
        """Initialize the code file searcher"""
        self.code_paths = code_paths
        # Hyperscan database
        self._hs_database = None
        self._hs_keyword_map = {}  # Map pattern ID to keyword

    def search(self, keyworks: List[str]) -> Dict[str, List[str]]:
        """Search for keywords in the code paths"""
        if not self.code_paths:
            logger.error("No code paths provided for searching.")
            return {}

        # Compile Hyperscan patterns
        self._compile_hyperscan_patterns(keyworks)

        results = defaultdict(list)
        file_count = 0
        
        for code_path in self.code_paths:
            if not os.path.exists(code_path):
                logger.warning(f"Code path does not exist: {code_path}")
                continue

            path_obj = Path(code_path)
            
            # Handle file path directly
            if path_obj.is_file():
                if path_obj.suffix in ['.java', '.cpp', '.h', '.hpp', '.cc']:
                    file_count += 1
                    keyword_line_map = self._search_file(path_obj, keyworks)
                    for keyword, line_numbers in keyword_line_map.items():
                        for line_num in line_numbers:
                            results[keyword].append(f"{str(path_obj)}:{line_num}")
                else:
                    logger.debug(f"Skipping unsupported file type: {code_path}")
                continue
            
            # Handle directory path
            logger.debug(f"Searching in code path: {code_path}")
            for root, dirs, files in os.walk(code_path):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix not in ['.java', '.cpp', '.h', '.hpp', '.cc']:
                        continue
                    
                    file_count += 1
                    keyword_line_map = self._search_file(file_path, keyworks)
                    
                    # Build result dict: {keyword: [file_path:line_number]}
                    for keyword, line_numbers in keyword_line_map.items():
                        for line_num in line_numbers:
                            results[keyword].append(f"{str(file_path)}:{line_num}")
        
        logger.info(f"Searched {file_count} files, found {len(results)} keywords")
        return dict(results)
    
    def _compile_hyperscan_patterns(self, keywords: List[str]):
        """Compile patterns using Hyperscan for high-performance matching"""
        if self._hs_database is not None:
            return  # Already compiled
        
        patterns = []
        flags = []
        ids = []
        
        for idx, keyword in enumerate(keywords):
            # Create word boundary pattern
            pattern = r'\b' + re.escape(keyword) + r'\b'
            patterns.append(pattern.encode('utf-8'))
            # 0 for default flags, can add hyperscan.HS_FLAG_CASELESS for case-insensitive
            flags.append(0)
            ids.append(idx)
            self._hs_keyword_map[idx] = keyword
        
        try:
            # Compile all patterns into a single database
            self._hs_database = hyperscan.Database()
            self._hs_database.compile(
                expressions=patterns,
                ids=ids,
                elements=len(patterns),
                flags=flags
            )
            logger.info(f"Compiled {len(patterns)} patterns with Hyperscan")
        except Exception as e:
            logger.error(f"Failed to compile Hyperscan database: {e}")
            self._hs_database = None
    
    def _search_file(self, file_path: Path, keywords: List[str]) -> Dict[str, List[int]]:
        """Search for keywords in a single file
        
        Returns:
            Dict mapping keyword to list of line numbers where it appears
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return self._search_with_hyperscan(content, file_path)
            
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return {}
    
    def _search_with_hyperscan(self, content: str, file_path: Path) -> Dict[str, List[int]]:
        """Search using Hyperscan (high performance)
        
        Returns:
            Dict mapping keyword to list of line numbers where it appears
        """
        # Use defaultdict to collect all line numbers for each keyword
        keyword_lines = defaultdict(list)
        
        # Build line offset mapping for line number calculation
        content_bytes = content.encode('utf-8')
        line_starts = [0]  # Line 1 starts at byte 0
        for i, byte in enumerate(content_bytes):
            if byte == ord('\n'):
                line_starts.append(i + 1)
        
        def get_line_number(offset: int) -> int:
            """Convert byte offset to line number (1-indexed)"""
            # Binary search would be more efficient for large files
            for line_num in range(len(line_starts) - 1, -1, -1):
                if offset >= line_starts[line_num]:
                    return line_num + 1  # Convert to 1-indexed
            return 1
        
        def on_match(id, from_offset, to_offset, flags, context):
            """Callback function for Hyperscan matches
            
            Note: In block mode, from_offset is always 0 (start of scan),
                  to_offset is the position immediately after the match
            """
            keyword = self._hs_keyword_map.get(id)
            if keyword:
                # Use to_offset - 1 to get the last character of the match
                line_num = get_line_number(to_offset - 1)
                keyword_lines[keyword].append(line_num)
                logger.debug(f"Found keyword '{keyword}' in {file_path}:{line_num}")
            return None  # Continue scanning
        
        try:
            # Scan content with all patterns at once
            self._hs_database.scan(content_bytes, match_event_handler=on_match)
        except Exception as e:
            logger.error(f"Hyperscan error in {file_path}: {e}")
        
        return dict(keyword_lines)