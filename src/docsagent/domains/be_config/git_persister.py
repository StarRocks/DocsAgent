"""GitPersister for BE configuration documentation"""

from pathlib import Path
from typing import Dict
from loguru import logger

from docsagent.core.git_persister import GitPersister
from docsagent import config


class BEConfigGitPersister(GitPersister):
    """
    GitPersister for BE configuration documentation.
    
    Handles copying generated BE config docs to StarRocks repository
    and creating commits/PRs.
    """
    
    def __init__(self):
        super().__init__(domain="be_config")
    
    def get_file_mappings(self) -> Dict[str, str]:
        """
        Get file mappings for BE configuration documentation.
        
        Returns:
            Dict mapping source paths to target paths in StarRocks repo
        
        TODO: Update these mappings to match actual StarRocks documentation structure.
              Current mappings are placeholders and need to be configured.
        """
        output_dir = Path(config.DOCS_OUTPUT_DIR)
        
        mappings = {}
        
        # TODO: Configure actual target paths in StarRocks repository
        for lang in config.TARGET_LANGS:
            source_file = output_dir / lang / "BE_configuration.md"
            
            # Placeholder target path - needs to be configured
            target_path = f"docs/{lang}/administration/management/BE_configuration.md"
            
            if source_file.exists():
                mappings[str(source_file)] = target_path
            else:
                logger.warning(f"Source file not found: {source_file}")
        
        if not mappings:
            logger.warning(
                "No file mappings generated for BE config. "
                "Please configure target paths in get_file_mappings()."
            )
        
        return mappings
