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

"""
LangGraph Tool wrappers for documentation agents

Simplified to 2 core tools:
1. read_file - Read file content with optional line range
2. search_code - Search keywords in code files with context
3. execute_sql - Execute SQL queries against StarRocks (optional)
"""

from typing import List, Optional
from pathlib import Path
from loguru import logger

from langchain_core.tools import tool

from docsagent.tools.file_reader import FileReader, read_file_lines
from docsagent.tools.code_search import CodeFileSearch


# ============================================================================
# Tool 1: Read File Content
# ============================================================================

@tool
def read_file(
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None
) -> str:
    """
    Read content from a file. Can read entire file or specific line range.
    
    When to use:
    - Read source code files to understand implementation
    - Extract specific sections after getting line numbers from search
    - Get file content for documentation generation
    
    Args:
        file_path: Absolute path to the file
        start_line: Optional starting line (1-indexed). If None, read from beginning
        end_line: Optional ending line (1-indexed, inclusive). If None, read to end
        
    Returns:
        File content with line numbers
        
    Examples:
        Read entire file:
        >>> read_file('/path/to/Config.java')
        
        Read specific lines:
        >>> read_file('/path/to/Config.java', start_line=10, end_line=30)
        
        Read from line 50 to end:
        >>> read_file('/path/to/file.py', start_line=50)
    """
    try:
        # Get file info first
        path_obj = Path(file_path)
        if not path_obj.exists():
            return f"Error: File not found: {file_path}"
        
        reader = FileReader()
        info = reader.get_file_info(file_path)
        
        # Determine actual line range
        actual_start = start_line if start_line else 1
        actual_end = end_line
        
        # Read content with line numbers
        content = reader.read_lines_with_numbers(
            file_path=file_path,
            start_line=actual_start,
            end_line=actual_end
        )
        
        if not content:
            return f"File is empty or requested lines are out of range"
        
        # Add header with file info
        header = f"=== File: {path_obj.name} ===\n"
        header += f"=== Total lines: {info['line_count']} | "
        if end_line:
            header += f"Showing: {actual_start}-{end_line} ===\n\n"
        else:
            header += f"Showing: {actual_start}-{info['line_count']} ===\n\n"
        
        return header + content
        
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return f"Error: {str(e)}"


# ============================================================================
# Tool 2: Search Code
# ============================================================================

@tool
def search_code(
    keywords: List[str],
    file_paths: List[str],
    context_lines: int = 3
) -> str:
    """
    Search for keywords in code files and return matches with surrounding context.
    
    When to use:
    - Find where a class/function/variable is defined
    - Locate specific code patterns (e.g., annotations, keywords)
    - Discover usage examples
    - Get file paths and line numbers for further reading
    
    Args:
        keywords: Keywords to search (e.g., ['ConfigBase', '@ConfigParam'])
        file_paths: File or directory paths to search in
        context_lines: Number of lines before/after match to show (default: 3)
        
    Returns:
        Formatted search results with file paths, line numbers, and context
        
    Tips:
    - Use specific keywords to reduce results
    - After finding matches, use read_file() to read full implementation
    - Default shows top 10 matches per keyword
        
    Examples:
        Search for class definition:
        >>> search_code(['class ConfigBase'], ['/path/to/code'])
        
        Search for annotations:
        >>> search_code(['@ConfigParam'], ['/path/to/Config.java'])
        
        Search with more context:
        >>> search_code(['init'], ['/path/to/'], context_lines=5)
    """
    try:
        if not file_paths:
            return "Error: file_paths is required"
        
        # Create searcher
        searcher = CodeFileSearch(code_paths=file_paths)
        
        # Perform search with context
        results = searcher.search_with_context(
            keywords=keywords,
            context_lines=context_lines,
            max_matches_per_keyword=10  # Fixed at 10 to avoid overwhelming output
        )
        
        if not results:
            return f"No matches found for: {', '.join(keywords)}"
        
        # Format results concisely
        output = []
        total_matches = sum(r.total_matches for r in results.values())
        output.append(f"Found {total_matches} matches for {len(keywords)} keyword(s)\n")
        
        for keyword, search_result in results.items():
            output.append(f"\n{'='*60}")
            output.append(f"Keyword: '{keyword}'")
            output.append(f"Matches: {search_result.total_matches} (showing {len(search_result.matches)})")
            output.append('='*60)
            
            for i, match in enumerate(search_result.matches, 1):
                output.append(f"\n[{i}] {match.file_path}:{match.line_number}")
                output.append('-' * 40)
                
                # Show context before
                if match.context_before:
                    for j, line in enumerate(match.context_before):
                        line_num = match.line_number - len(match.context_before) + j
                        output.append(f"  {line_num:4d} | {line}")
                
                # Show matching line (highlighted with >>>)
                output.append(f">>>{match.line_number:4d} | {match.line_content}")
                
                # Show context after
                if match.context_after:
                    for j, line in enumerate(match.context_after):
                        line_num = match.line_number + j + 1
                        output.append(f"  {line_num:4d} | {line}")
                
                output.append('')
        
        # Add suggestion for next step
        output.append("\nTip: Use read_file(file_path, start_line, end_line) to read more context")
        
        return '\n'.join(output)
        
    except Exception as e:
        logger.error(f"Error searching code: {e}")
        return f"Error: {str(e)}"


# ============================================================================
# Utility: Get all tools
# ============================================================================

def get_code_reading_tools() -> List:
    """
    Get simplified code reading tools for LangGraph agents
    
    Returns:
        List of 2 essential tools: [read_file, search_code]
        
    Usage:
        >>> from docsagent.agents.tools import get_code_reading_tools
        >>> tools = get_code_reading_tools()
        >>> # Bind to LLM: llm.bind_tools(tools)
    """
    return [
        search_code,  # Put search first - most commonly used for discovery
        read_file     # Then read for detailed content
    ]


def get_starrocks_tools(
    test_connection: bool = True
):
    """
    Get StarRocks database tools for querying runtime information (READ-ONLY)
    
    Only returns tools if connection test succeeds (when test_connection=True).
    This prevents registering tools that will fail at runtime.
    
    NOTE: Only SELECT queries are supported for safety.
    
    Args:
        host: StarRocks host (if None, will use config)
        port: StarRocks port (if None, will use config)
        user: Database user (if None, will use config)
        password: Database password (if None, will use config)
        test_connection: Whether to test connection before returning tools
    
    Returns:
        List with execute_sql tool if connection succeeds, empty list otherwise
        
    Usage:
        >>> from docsagent.agents.tools import get_starrocks_tools
        >>> # Auto-detect from config and test connection
        >>> tools = get_starrocks_tools()
        >>> # Skip connection test (not recommended)
        >>> tools = get_starrocks_tools(test_connection=False)
    """
    from docsagent.tools.sr_client import (
        execute_sql,
        test_connection as test_sr_connection
    )
    
    # Test connection before registering tools
    if test_connection:
        from docsagent.config import config
        if not test_sr_connection(config.SR_HOST, config.SR_PORT, config.SR_USER, config.SR_PASSWORD):
            if config.MUST_USE_SR_CLIENT:
                logger.error(
                    f"StarRocks connection test failed ({config.SR_HOST}:{config.SR_PORT}). "
                    "StarRocks tools are required but cannot connect."
                )
                exit(-1)

            logger.warning(
                f"StarRocks connection test failed ({config.SR_HOST}:{config.SR_PORT}). "
                "StarRocks tools will not be registered."
            )
            return []

        logger.debug(f"StarRocks connection test succeeded ({config.SR_HOST}:{config.SR_PORT})")
    
    return [execute_sql]


def get_all_tools(include_starrocks: bool = False, test_sr_connection: bool = True):
    """
    Get all available tools for agents
    
    Args:
        include_starrocks: Whether to include StarRocks database tools
        test_sr_connection: Whether to test StarRocks connection before including tools
        
    Returns:
        List of all tools (only includes StarRocks tools if connection succeeds)
        
    Usage:
        >>> from docsagent.agents.tools import get_all_tools
        >>> # Include StarRocks tools if connection works
        >>> tools = get_all_tools(include_starrocks=True)
        >>> # Force include even if connection fails (not recommended)
        >>> tools = get_all_tools(include_starrocks=True, test_sr_connection=False)
    """
    tools = get_code_reading_tools()
    
    if include_starrocks:
        sr_tools = get_starrocks_tools(test_connection=test_sr_connection)
        if sr_tools:
            tools.extend(sr_tools)
        elif test_sr_connection:
            logger.debug("Continuing without StarRocks tools")
    
    return tools
