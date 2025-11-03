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

"""Version extractor for Variables (Session/Global Variables)"""

import re
from pathlib import Path

from docsagent.core.version_extractor import BaseVersionExtractor
from docsagent.config import config


class VariablesVersionExtractor(BaseVersionExtractor):
    """
    Version tracker for StarRocks variables (Session and Global).
    
    Matches Java field definitions with @VarAttr annotation:
        @VarAttr(name = "query_timeout", show = "query_timeout")
        public int queryTimeoutS = 300;
    
    Uses 'show' field as identifier (preferred display name in docs).
    """
    
    def __init__(self):
        """Initialize variables version extractor with config from settings."""
        super().__init__(
            repo_path=config.STARROCKS_HOME,
            source_files=[
                "fe/fe-core/src/main/java/com/starrocks/qe/SessionVariable.java",
                "fe/fe-core/src/main/java/com/starrocks/qe/GlobalVariable.java"
            ],
            version_file=Path(config.META_DIR) / "variables.version",
            item_identifier_field="show"  # Use 'show' field instead of 'name'
        )
    
    def _extract_all_items_from_content(self, content: str) -> set:
        """
        Extract all variable show names from content.
        
        This is much faster than checking each item individually.
        Extracts the 'show' parameter value from @VarAttr annotations.
        
        Args:
            content: File content
        
        Returns:
            Set of variable show names found
        """
        show_names = set()
        
        # First, build a map of constants to their string values
        # Pattern: [modifiers] String CONSTANT_NAME = "value";
        # Supports all Java field modifiers in any order (consistent with extractor)
        constant_map = {}
        constant_pattern = re.compile(
            r'(?:(?:public|protected|private|static|final|transient|volatile|synchronized|native|strictfp)\s+)*String\s+(\w+)\s*=\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )
        for match in constant_pattern.finditer(content):
            constant_name = match.group(1)
            constant_value = match.group(2)
            constant_map[constant_name] = constant_value
        
        # Pattern to extract show parameter from @VarAttr annotations
        # Matches: @VarAttr(...show = "value"...) or @VarAttr(...show = CONSTANT...)
        pattern = re.compile(
            r'@(?:VariableMgr\.)?VarAttr\s*\(([^)]+)\)',  # Capture annotation parameters
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(content):
            params_str = match.group(1)
            
            # Extract show parameter value (can be string literal or constant reference)
            show_match = re.search(r'show\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\w+))', params_str)
            if show_match:
                if show_match.group(1):
                    # Double-quoted string literal
                    show_name = show_match.group(1)
                    show_names.add(show_name)
                elif show_match.group(2):
                    # Single-quoted string literal
                    show_name = show_match.group(2)
                    show_names.add(show_name)
                elif show_match.group(3):
                    # Constant reference - resolve it
                    constant_ref = show_match.group(3)
                    if constant_ref in constant_map:
                        show_name = constant_map[constant_ref]
                        show_names.add(show_name)
            else:
                # If no show parameter, try to extract name parameter as fallback
                name_match = re.search(r'name\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\w+))', params_str)
                if name_match:
                    if name_match.group(1):
                        name_value = name_match.group(1)
                        show_names.add(name_value)
                    elif name_match.group(2):
                        name_value = name_match.group(2)
                        show_names.add(name_value)
                    elif name_match.group(3):
                        constant_ref = name_match.group(3)
                        if constant_ref in constant_map:
                            name_value = constant_map[constant_ref]
                            show_names.add(name_value)
        
        return show_names
