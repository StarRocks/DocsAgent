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

"""Version extractor for BE configuration items"""

import re
from pathlib import Path

from docsagent.core.version_extractor import BaseVersionExtractor
from docsagent.config import config


class BEConfigVersionExtractor(BaseVersionExtractor):
    """
    Version tracker for BE configuration items.
    
    Matches C++ macro definitions with CONF_ prefix:
        CONF_Int32(be_port, "9060");
        CONF_mString(sys_log_level, "INFO");
        CONF_Alias(be_http_port, webserver_port);
    """
    
    def __init__(self):
        """Initialize BE config version extractor with config from settings."""
        super().__init__(
            repo_path=config.STARROCKS_HOME,
            source_files=["be/src/common/config.h", "be/src/common/config.cpp"],
            version_file=Path(config.META_DIR) / "be_config.version",
            item_identifier_field="name"
        )
    
    def _extract_all_items_from_content(self, content: str) -> set:
        """
        Extract all BE config names from config.h/cpp content.
        
        This is much faster than checking each item individually.
        Uses the same pattern as BEConfigExtractor to ensure consistency.
        
        Args:
            content: File content
        
        Returns:
            Set of config names found
        """
        config_names = set()
        
        # Pattern 1: Standard CONF_* macros
        standard_pattern = re.compile(
            r'CONF_m?'  # CONF_ with optional 'm' for mutable
            r'\w+\s*'  # Type (Int32, String, Bool, etc.)
            r'\(\s*'  # Opening parenthesis
            r'(\w+)\s*,\s*'  # Field name (capture group)
            r'"[^"]*"\s*'  # Default value in quotes
            r'(?:,\s*"[^"]*")?\s*'  # Optional third parameter (for String_enum)
            r'\)',  # Closing parenthesis
            re.MULTILINE
        )
        
        # Pattern 2: CONF_Alias(alias_name, target_name)
        alias_pattern = re.compile(
            r'CONF_Alias\s*'  # CONF_Alias
            r'\(\s*'  # Opening parenthesis
            r'(\w+)\s*,\s*'  # Alias name (capture group 1)
            r'(\w+)\s*'  # Target name (capture group 2)
            r'\)',  # Closing parenthesis
            re.MULTILINE
        )
        
        # Extract standard configs
        for match in standard_pattern.finditer(content):
            field_name = match.group(1)
            config_names.add(field_name)
        
        # Extract aliases - use alias name (first capture group)
        for match in alias_pattern.finditer(content):
            alias_name = match.group(1)
            config_names.add(alias_name)
        
        return config_names
