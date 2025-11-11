#!/usr/bin/env python3
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


import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Set, Tuple, Optional, NamedTuple
from loguru import logger

import hyperscan


class SearchMatch(NamedTuple):
    """Single search match result"""
    file_path: str
    line_number: int
    line_content: str
    context_before: List[str] = []
    context_after: List[str] = []


class SearchResult(NamedTuple):
    """Search result for a keyword"""
    keyword: str
    matches: List[SearchMatch]
    total_matches: int


class CodeFileSearch:
    def __init__(
        self, 
        code_paths: List[str] = None, 
        file_filter: Optional[Callable[[Path], bool]] = None,
        dir_filter: Optional[Callable[[Path], bool]] = None
    ):
        """
        Initialize the code file searcher
        
        Args:
            code_paths: List of paths to search in
            file_suffix: (Deprecated) List of file suffixes, use file_filter instead
            file_filter: Callable that takes a file Path and returns True to include
            dir_filter: Callable that takes a dir Path and returns True to include
        
        Examples:
            # Use file_suffix (old way)
            searcher = CodeFileSearch(
                code_paths=['/path'],
                file_suffix=['.java', '.cpp']
            )
            
            # Use lambda filter (new way)
            searcher = CodeFileSearch(
                code_paths=['/path'],
                file_filter=lambda f: f.suffix in ['.java', '.cpp'],
                dir_filter=lambda d: d.name not in ['build', 'target', '.git']
            )
        """
        self.code_paths = code_paths
        
        # File filter
        self.file_filter = file_filter if file_filter is not None else lambda f: f.suffix in ['.java', '.cpp', '.h', '.hpp', '.cc']
        self.file_filter = file_filter if file_filter is not None else lambda f: True

        # Directory filter (default: include all)
        self.dir_filter = dir_filter if dir_filter is not None else lambda d: True
        
        # Hyperscan database
        self._hs_database = None
        self._hs_keyword_map = {}  # Map pattern ID to keyword

    def search(self, keyworks: List[str]) -> Dict[str, List[str]]:
        """Search for keywords in the code paths (legacy method)
        
        Returns:
            Dict mapping keyword to list of "file_path:line_number" strings
            
        Note: Use search_with_context() for richer results
        """
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
                if self.file_filter(path_obj):
                    file_count += 1
                    keyword_line_map = self._search_file(path_obj, keyworks)
                    for keyword, line_numbers in keyword_line_map.items():
                        for line_num in line_numbers:
                            results[keyword].append(f"{str(path_obj)}:{line_num}")
                else:
                    logger.debug(f"Skipping file (filtered out): {code_path}")
                continue
            
            # Handle directory path
            logger.debug(f"Searching in code path: {code_path}")
            for root, dirs, files in os.walk(code_path):
                root_path = Path(root)
                for file in files:
                    file_path = root_path / file
                    
                    # Check if file should be included
                    if not self.dir_filter(root_path) or not self.file_filter(file_path):
                        continue
                    
                    file_count += 1
                    keyword_line_map = self._search_file(file_path, keyworks)
                    
                    # Build result dict: {keyword: [file_path:line_number]}
                    for keyword, line_numbers in keyword_line_map.items():
                        for line_num in line_numbers:
                            results[keyword].append(f"{str(file_path)}:{line_num}")
        
        logger.debug(f"Searched {file_count} files, found {len(results)} keywords")
        return dict(results)
    
    def search_with_context(
        self, 
        keywords: List[str],
        context_lines: int = 3,
        max_matches_per_keyword: int = 100
    ) -> Dict[str, SearchResult]:
        """Search for keywords with context lines
        
        Args:
            keywords: List of keywords to search for
            context_lines: Number of lines before/after to include (default: 3)
            max_matches_per_keyword: Maximum matches to return per keyword (default: 100)
            
        Returns:
            Dict mapping keyword to SearchResult containing matches with context
            
        Examples:
            >>> searcher = CodeFileSearch(code_paths=['/path/to/code'])
            >>> results = searcher.search_with_context(['ConfigBase', 'init_db'])
            >>> for keyword, result in results.items():
            ...     print(f"{keyword}: {result.total_matches} matches")
            ...     for match in result.matches[:5]:
            ...         print(f"  {match.file_path}:{match.line_number}")
        """
        if not self.code_paths:
            logger.error("No code paths provided for searching.")
            return {}

        # Compile Hyperscan patterns
        self._compile_hyperscan_patterns(keywords)

        # Store matches: {keyword: [SearchMatch]}
        keyword_matches = defaultdict(list)
        file_count = 0
        
        for code_path in self.code_paths:
            if not os.path.exists(code_path):
                logger.warning(f"Code path does not exist: {code_path}")
                continue

            path_obj = Path(code_path)
            
            # Handle file path directly
            if path_obj.is_file():
                if self.file_filter(path_obj):
                    file_count += 1
                    self._search_file_with_context(
                        path_obj, keywords, context_lines, keyword_matches, max_matches_per_keyword
                    )
                else:
                    logger.debug(f"Skipping file (filtered out): {code_path}")
                continue
            
            # Handle directory path
            logger.debug(f"Searching in code path: {code_path}")
            for root, dirs, files in os.walk(code_path):
                root_path = Path(root)
                for file in files:
                    file_path = root_path / file
                    
                    # Check if file should be included
                    if not self.dir_filter(root_path) or not self.file_filter(file_path):
                        continue
                    
                    file_count += 1
                    self._search_file_with_context(
                        file_path, keywords, context_lines, keyword_matches, max_matches_per_keyword
                    )
        
        # Convert to SearchResult objects
        results = {}
        for keyword, matches in keyword_matches.items():
            results[keyword] = SearchResult(
                keyword=keyword,
                matches=matches[:max_matches_per_keyword],
                total_matches=len(matches)
            )
        
        logger.debug(
            f"Searched {file_count} files, found {len(results)} keywords "
            f"with {sum(r.total_matches for r in results.values())} total matches"
        )
        return results
    
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
            logger.debug(f"Compiled {len(patterns)} patterns with Hyperscan")
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
    
    def _search_file_with_context(
        self,
        file_path: Path,
        keywords: List[str],
        context_lines: int,
        keyword_matches: Dict[str, List[SearchMatch]],
        max_matches_per_keyword: int
    ) -> None:
        """Search for keywords in a file and collect matches with context
        
        Args:
            file_path: Path to the file to search
            keywords: List of keywords to search for
            context_lines: Number of lines before/after to include
            keyword_matches: Dict to store matches (modified in place)
            max_matches_per_keyword: Stop searching for a keyword after this many matches
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Get line numbers where keywords appear
            content = ''.join(lines)
            keyword_line_map = self._search_with_hyperscan(content, file_path)
            
            # For each keyword and its matching lines
            for keyword, line_numbers in keyword_line_map.items():
                # Check if already have enough matches
                if len(keyword_matches[keyword]) >= max_matches_per_keyword:
                    continue
                
                for line_num in line_numbers:
                    # Stop if reached max matches
                    if len(keyword_matches[keyword]) >= max_matches_per_keyword:
                        break
                    
                    # Get context (convert to 0-indexed)
                    line_idx = line_num - 1
                    start_idx = max(0, line_idx - context_lines)
                    end_idx = min(len(lines), line_idx + context_lines + 1)
                    
                    # Extract context lines
                    context_before = [line.rstrip('\n') for line in lines[start_idx:line_idx]]
                    line_content = lines[line_idx].rstrip('\n')
                    context_after = [line.rstrip('\n') for line in lines[line_idx + 1:end_idx]]
                    
                    # Create match object
                    match = SearchMatch(
                        file_path=str(file_path),
                        line_number=line_num,
                        line_content=line_content,
                        context_before=context_before,
                        context_after=context_after
                    )
                    
                    keyword_matches[keyword].append(match)
            
        except Exception as e:
            logger.warning(f"Error searching file {file_path}: {e}")