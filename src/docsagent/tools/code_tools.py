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

import re
from typing import Dict


def extract_cstyle_comment_before_position(content: str, position: int) -> str:
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


def parse_equals_pair(params_str: str) -> Dict[str, str]:
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