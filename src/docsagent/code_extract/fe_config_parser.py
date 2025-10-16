#!/usr/bin/env python3

import os
import re

from pathlib import Path
from typing import Dict, List, Any
from loguru import logger

from docsagent import config
from docsagent.code_extract.code_search import CodeFileSearch


class FEConfigParser:
    def __init__(self, code_paths: List[str] = None):
        """Initialize the FE config parser (regex-based, simple and reliable)"""
        self.code_paths = code_paths or self._get_default_code_paths()
        self.supported_extensions = {'.java'}


    def _get_default_code_paths(self) -> List[str]:
        """Get default code scanning paths - focus on config-related directories"""
        starrocks_dir = Path(config.STARROCKS_HOME)
        # Focus on config-related paths
        config_paths = [
            "fe/fe-core/src/main/java/com/starrocks/",
        ]
        
        full_paths = [str(starrocks_dir / path) for path in config_paths]
        return full_paths
    
    def _get_source_code_paths(self) -> List[str]:
        codes = []
        for code_path in self.code_paths:
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
                    
                    codes.append(file_path)
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
        if name_lower.endswith('test.java') or name_lower.startswith('test'):
            return False
        
        return True
    
    def _extract_config_items(self, file_path: str) -> List[Dict[str, Any]]:
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
    
    def _extract_with_regex(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract config items using regex pattern matching
        
        Matches patterns like:
        @ConfField
        public static int log_roll_size_mb = 1024;
        
        @ConfField(mutable = false, comment = "description")
        public static String sys_log_format = "plaintext";
        """
        items: List[Dict[str, Any]] = []
        
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
            params = self._parse_annotation_params(annotation_params_str)
            
            # Extract comment before this match
            comment = self._extract_comment_before_position(content, match.start())
            
            # Get line number
            line_number = content[:match.start()].count('\n') + 1
            
            item = {
                "name": field_name,
                "type": field_type,
                "defaultValue": default_value,
                "comment": params.get("comment", comment),
                "isMutable": params.get("mutable", "false"),
                "scope": "FE",
                "useLocations": [],
                "documents": "",
                "file_path": str(file_path),
                "line_number": line_number,
            }
            
            logger.debug(f"Found config item: {field_name} at line {line_number}")
            items.append(item)
        
        return items
    
    def _parse_annotation_params(self, params_str: str) -> Dict[str, str]:
        """Parse annotation parameters like 'mutable = false, comment = "text"'
        
        Returns dict with parameter names and values (strings with quotes removed)
        """
        params = {}
        if not params_str:
            return params
        
        # Pattern to match key=value pairs
        # Handles: key = "value", key = 'value', key = true, key = false, key = 123
        param_pattern = re.compile(r'(\w+)\s*=\s*(["\']?)([^,]*?)\2(?:,|$)')
        
        for match in param_pattern.finditer(params_str):
            key = match.group(1).strip()
            value = match.group(3).strip()
            params[key] = value
        
        return params
    
    def _extract_comment_before_position(self, content: str, position: int) -> str:
        """Extract comment (JavaDoc, block comment, or line comment) before given position
        
        Looks backwards from position to find:
        - /** ... */ (JavaDoc)
        - /* ... */ (block comment)
        - // ... (line comment)
        """
        # Get text before the position
        before_text = content[:position]
        
        # Look for JavaDoc comment /** ... */
        javadoc_pattern = re.compile(r'/\*\*\s*(.*?)\s*\*/', re.DOTALL)
        javadoc_matches = list(javadoc_pattern.finditer(before_text))
        if javadoc_matches:
            last_match = javadoc_matches[-1]
            # Check if comment is close to position (within 100 chars of whitespace/newlines)
            gap = before_text[last_match.end():].strip()
            if len(gap) < 100 or not gap:
                comment_text = last_match.group(1)
                # Clean up JavaDoc formatting (* at start of lines)
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

    def extract_all_configs(self, sources_files: list[str]) -> List[Dict[str, Any]]:
        """Scan all files in code paths and extract config items"""
        all_config_items = []
        
        for file_path in sources_files:
            try:
                config_items = self._extract_config_items(file_path)
                for item in config_items:
                    item["file_path"] = file_path
                all_config_items.extend(config_items)
                
                if config_items:
                    logger.info(f"Found {len(config_items)} config items in {file_path}")
                else:
                    logger.debug(f"No config items found in {file_path}")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")


        search_keywords = [k['name'] for k in all_config_items]
        serach_results = CodeFileSearch(self.code_paths).search(search_keywords)
        
        for item in all_config_items:
            if item['name'] in serach_results:
                item['useLocations'] = serach_results[item['name']]

        logger.info(f"Total config items found: {len(all_config_items)}")
        return all_config_items