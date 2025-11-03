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

"""Version extractor for FE configuration items"""

import re
from pathlib import Path

from docsagent.core.version_extractor import BaseVersionExtractor
from docsagent.config import config


class FEConfigVersionExtractor(BaseVersionExtractor):
    """
    Version tracker for FE configuration items.
    
    Matches Java field definitions with @ConfField annotation:
        @ConfField
        public static int log_roll_size_mb = 1024;
    """
    
    def __init__(self):
        """Initialize FE config version extractor with config from settings."""
        super().__init__(
            repo_path=config.STARROCKS_HOME,
            source_files=["fe/fe-core/src/main/java/com/starrocks/common/Config.java"],
            version_file=Path(config.META_DIR) / "fe_config.version",
            item_identifier_field="name"
        )
    
    def _extract_all_items_from_content(self, content: str) -> set:
        """
        Extract all FE config names from Config.java content.
        
        This is much faster than checking each item individually.
        Uses the same pattern as FEConfigExtractor to ensure consistency.
        
        Args:
            content: File content
        
        Returns:
            Set of config names found
        """
        # Pattern to extract all @ConfField annotated fields
        # Same pattern as FEConfigExtractor._extract_with_regex
        pattern = re.compile(
            r'@ConfField\s*(?:\([^)]*\))?\s*'  # @ConfField with optional parameters
            r'(?:@\w+(?:\([^)]*\))?\s*)*'  # Skip other annotations like @Deprecated
            r'(?:(?:public|protected|private|static|final|transient|volatile|synchronized|native|strictfp)\s+)*'  # All modifiers
            r'[\w\[\]<>,\s]+?\s+'  # Type (including generics, arrays)
            r'(\w+)\s*'  # Field name (capture group)
            r'=\s*'  # Assignment
            r'[^;]+;',  # Default value until semicolon
            re.MULTILINE | re.DOTALL
        )
        
        # Extract all field names
        field_names = set()
        for match in pattern.finditer(content):
            field_name = match.group(1)
            field_names.add(field_name)
        
        return field_names
