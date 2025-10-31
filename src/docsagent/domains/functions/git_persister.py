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

"""GitPersister for SQL functions documentation"""

from pathlib import Path
from typing import Dict
from loguru import logger

from docsagent.core.git_persister import GitPersister
from docsagent import config


class FunctionsGitPersister(GitPersister):
    """
    GitPersister for SQL functions documentation.
    
    Handles copying generated function docs to StarRocks repository
    and creating commits/PRs.
    
    Note: Functions documentation may have complex directory structures
          with multiple files organized by function categories.
    """
    
    def __init__(self):
        super().__init__(domain="functions")
    
    def get_file_mappings(self) -> Dict[str, str]:
        """
        Get file mappings for SQL functions documentation.
        
        Returns:
            Dict mapping source paths to target paths in StarRocks repo
        
        TODO: Implement recursive directory mapping for function categories.
              Functions are organized in subdirectories like:
              - like-predicate-functions/
              - string-functions/
              - date-time-functions/
              etc.
        
        Example structure:
            output/zh/functions/string-functions/REGEXP.md
            → docs/zh/sql-reference/sql-functions/string-functions/REGEXP.md
        """
        output_dir = Path(config.DOCS_OUTPUT_DIR)
        
        mappings = {}
        
        # TODO: Configure actual target paths and implement recursive mapping
        # This requires iterating through function category directories
        # and mapping each function file individually
        
        for lang in config.TARGET_LANGS:
            functions_dir = output_dir / lang / "functions"
            
            if not functions_dir.exists():
                logger.warning(f"Functions directory not found: {functions_dir}")
                continue
            
            # Recursively find all markdown files
            for func_file in functions_dir.rglob("*.md"):
                # Get relative path from functions directory
                rel_path = func_file.relative_to(functions_dir)
                
                # Placeholder target path - needs to be configured
                target_path = f"docs/{lang}/sql-reference/sql-functions/{rel_path}"
                
                mappings[str(func_file)] = target_path
        
        if not mappings:
            logger.warning(
                "No file mappings generated for functions. "
                "Please configure target paths in get_file_mappings()."
            )
        
        return mappings
