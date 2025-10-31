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

"""GitPersister for system variables documentation"""

from pathlib import Path
from typing import Dict
from loguru import logger

from docsagent.core.git_persister import GitPersister
from docsagent import config


class VariablesGitPersister(GitPersister):
    """
    GitPersister for system variables documentation.
    
    Handles copying generated variables docs to StarRocks repository
    and creating commits/PRs.
    """
    
    def __init__(self):
        super().__init__(domain="variables")
    
    def get_file_mappings(self) -> Dict[str, str]:
        """
        Get file mappings for system variables documentation.
        
        Returns:
            Dict mapping source paths to target paths in StarRocks repo
        
        TODO: Update these mappings to match actual StarRocks documentation structure.
              Current mappings are placeholders and need to be configured.
        """
        output_dir = Path(config.DOCS_OUTPUT_DIR)
        
        mappings = {}
        
        # TODO: Configure actual target paths in StarRocks repository
        for lang in config.TARGET_LANGS:
            source_file = output_dir / lang / "System_variable.md"
            
            # Placeholder target path - needs to be configured
            target_path = f"docs/{lang}/sql-reference/System_variable.md"
            
            if source_file.exists():
                mappings[str(source_file)] = target_path
            else:
                logger.warning(f"Source file not found: {source_file}")
        
        if not mappings:
            logger.warning(
                "No file mappings generated for variables. "
                "Please configure target paths in get_file_mappings()."
            )
        
        return mappings
