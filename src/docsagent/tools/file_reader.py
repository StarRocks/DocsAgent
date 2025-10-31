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
File content reader tool for reading specific lines from files
"""

from pathlib import Path
from typing import Optional, List
from loguru import logger


class FileReader:
    """Read specific lines from files"""
    
    def __init__(self):
        """Initialize file reader"""
        pass
    
    def read_lines(
        self, 
        file_path: str, 
        start_line: int = 1, 
        end_line: Optional[int] = None,
        encoding: str = 'utf-8'
    ) -> str:
        """
        Read specific lines from a file
        
        Args:
            file_path: Path to the file to read
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (1-indexed, inclusive). If None, read to end of file
            encoding: File encoding (default: utf-8)
            
        Returns:
            String containing the requested lines
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If line numbers are invalid
            
        Examples:
            >>> reader = FileReader()
            >>> content = reader.read_lines('/path/to/file.py', 10, 20)
            >>> content = reader.read_lines('/path/to/file.py', 1)  # Read all lines
        """
        file_path_obj = Path(file_path)
        
        # Validate file exists
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path_obj.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        # Validate line numbers
        if start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {start_line}")
        
        if end_line is not None and end_line < start_line:
            raise ValueError(f"end_line ({end_line}) must be >= start_line ({start_line})")
        
        try:
            with open(file_path_obj, 'r', encoding=encoding, errors='ignore') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            
            # Adjust indices (convert to 0-indexed)
            start_idx = start_line - 1
            end_idx = end_line if end_line is None else end_line
            
            # Handle out of range
            if start_idx >= total_lines:
                logger.warning(
                    f"start_line ({start_line}) exceeds file length ({total_lines})"
                )
                return ""
            
            # Extract requested lines
            if end_idx is None:
                selected_lines = lines[start_idx:]
            else:
                selected_lines = lines[start_idx:end_idx]
            
            result = ''.join(selected_lines)
            
            logger.debug(
                f"Read {len(selected_lines)} lines from {file_path} "
                f"(lines {start_line}-{end_idx or total_lines})"
            )
            
            return result
            
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading {file_path}: {e}")
            # Retry with binary mode
            try:
                with open(file_path_obj, 'r', encoding='latin-1') as f:
                    lines = f.readlines()
                start_idx = start_line - 1
                end_idx = end_line if end_line is None else end_line
                selected_lines = lines[start_idx:end_idx] if end_idx else lines[start_idx:]
                return ''.join(selected_lines)
            except Exception as retry_error:
                logger.error(f"Failed to read file with fallback encoding: {retry_error}")
                raise
                
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise
    
    def read_lines_with_numbers(
        self,
        file_path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
        encoding: str = 'utf-8'
    ) -> str:
        """
        Read specific lines from a file with line numbers prepended
        
        Args:
            file_path: Path to the file to read
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (1-indexed, inclusive)
            encoding: File encoding (default: utf-8)
            
        Returns:
            String with line numbers prepended to each line
            
        Examples:
            >>> reader = FileReader()
            >>> content = reader.read_lines_with_numbers('/path/to/file.py', 10, 20)
            # Output:
            # 10: import os
            # 11: import sys
            # ...
        """
        content = self.read_lines(file_path, start_line, end_line, encoding)
        
        if not content:
            return content
        
        lines = content.splitlines()
        numbered_lines = []
        
        for i, line in enumerate(lines):
            line_num = start_line + i
            numbered_lines.append(f"{line_num}: {line}")
        
        return '\n'.join(numbered_lines)
    
    def get_file_info(self, file_path: str) -> dict:
        """
        Get basic information about a file
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dict with file info: {
                'path': str,
                'size': int,
                'line_count': int,
                'exists': bool
            }
        """
        file_path_obj = Path(file_path)
        
        info = {
            'path': str(file_path_obj.absolute()),
            'exists': file_path_obj.exists(),
            'size': 0,
            'line_count': 0
        }
        
        if not file_path_obj.exists():
            return info
        
        try:
            info['size'] = file_path_obj.stat().st_size
            
            with open(file_path_obj, 'r', encoding='utf-8', errors='ignore') as f:
                info['line_count'] = sum(1 for _ in f)
                
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
        
        return info


# Convenience function for direct usage
def read_file_lines(
    file_path: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    with_line_numbers: bool = False,
    encoding: str = 'utf-8'
) -> str:
    """
    Convenience function to read lines from a file
    
    Args:
        file_path: Path to the file
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (1-indexed, inclusive)
        with_line_numbers: Whether to prepend line numbers
        encoding: File encoding
        
    Returns:
        File content as string
        
    Examples:
        >>> content = read_file_lines('/path/to/file.py', 10, 20)
        >>> content = read_file_lines('/path/to/file.py', 1, with_line_numbers=True)
    """
    reader = FileReader()
    
    if with_line_numbers:
        return reader.read_lines_with_numbers(file_path, start_line, end_line, encoding)
    else:
        return reader.read_lines(file_path, start_line, end_line, encoding)
