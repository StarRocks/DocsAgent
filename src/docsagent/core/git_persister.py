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

"""Base GitPersister for committing documentation to external repository"""

from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger

from docsagent.tools.git_operator import GitOperator
from docsagent import config


class GitPersister:
    """
    Base class for Git operations in documentation pipeline.
    
    Handles the git commit and PR creation workflow after documentation generation.
    Each domain can extend this to provide domain-specific file mappings.
    """
    
    def __init__(self, domain: str):
        """
        Initialize GitPersister.
        
        Args:
            domain: Domain name (e.g., 'fe_config', 'be_config', 'functions')
        """
        self.domain = domain
        self.git_operator: Optional[GitOperator] = None
        
        logger.debug(f"GitPersister initialized: domain={domain}")
    
    def execute(self, languages: List[str], auto_commit: bool = False, create_pr: bool = False) -> bool:
        """
        Execute git operations: commit, push, and create PR.
        
        Args:
            languages: List of languages that were updated
            auto_commit: Whether to automatically commit changes
            create_pr: Whether to create a Pull Request (implies push to remote)
        
        Returns:
            True if operations succeeded (or skipped), False on error
        """
        if not auto_commit:
            logger.info("Git commit disabled, skipping git operations")
            return True
        
        # Initialize git operator
        self.git_operator = GitOperator(
            repo_path=config.STARROCKS_HOME,
            github_token=config.GITHUB_TOKEN,
            github_repo=config.GITHUB_REPO if config.GITHUB_REPO else None
        )
        
        # Validate repository
        if not self.git_operator.validate_repository():
            logger.warning("Git operations skipped: invalid repository")
            return True  # Not an error, just skip
        
        try:
            # Create branch
            branch_name = self.git_operator.create_branch(self.domain)
            logger.info(f"Created branch: {branch_name}")
            
            # Get file mappings (domain-specific)
            file_mappings = self.get_file_mappings()
            
            if not file_mappings:
                logger.warning("No file mappings defined, skipping commit")
                return True
            
            # Copy files and commit
            success, changed_files = self.git_operator.copy_and_commit(
                file_mappings=file_mappings,
                domain=self.domain,
                languages=languages
            )
            
            if not success:
                logger.error("Failed to commit changes")
                return False
            
            if not changed_files:
                logger.info("Created Pull Request: No files were modified, skipping PR creation")
                return True
            
            logger.info(f"Committed {len(changed_files)} modified file(s)")
            
            # Create PR if enabled (this implies push)
            if create_pr:
                # First push to remote
                if not self.git_operator.push():
                    logger.error("Failed to push changes")
                    return False
                logger.info("Pushed changes to remote")
                
                # Then create PR
                pr_url = self._create_pull_request(branch_name, changed_files, languages)
                if pr_url:
                    logger.info(f"Created Pull Request: {pr_url}")
                else:
                    logger.warning("Failed to create Pull Request")
            else:
                logger.info("PR creation disabled, changes committed locally only")
            
            return True
            
        except Exception as e:
            logger.error(f"Git operations failed: {e}")
            return False
        
        finally:
            # Cleanup: return to original branch
            if self.git_operator:
                self.git_operator.cleanup()
    
    def get_file_mappings(self) -> Dict[str, str]:
        """
        Get file mappings for this domain.
        
        Returns:
            Dict mapping source paths to target paths in StarRocks repo
            {source_absolute_path: target_relative_path}
        
        Note:
            This method should be overridden by domain-specific persisters.
            
        TODO: Implement file mapping configuration for each domain.
              For now, returns empty dict as a placeholder.
        """
        logger.warning(
            f"get_file_mappings() not implemented for domain '{self.domain}'. "
            "Override this method to provide domain-specific mappings."
        )
        return {}
    
    def _create_pull_request(
        self,
        branch_name: str,
        changed_files: List[str],
        languages: List[str]
    ) -> Optional[str]:
        """
        Create a Pull Request with auto-generated title and body.
        
        Args:
            branch_name: Name of the branch
            changed_files: List of changed files
            languages: List of languages updated
        
        Returns:
            PR URL if successful, None otherwise
        """
        if not self.git_operator:
            return None
        
        # Generate PR title
        lang_str = ", ".join(languages)
        title = f"[Doc] docs({self.domain}): update {lang_str} documentation"
        
        # Generate PR body
        body = self._generate_pr_body(changed_files, languages)
        
        return self.git_operator.create_pull_request(
            title=title,
            body=body,
            base="main",
            head=branch_name
        )
    
    def _generate_pr_body(self, changed_files: List[str], languages: List[str]) -> str:
        """
        Generate Pull Request description.
        
        Args:
            changed_files: List of changed files
            languages: List of languages updated
        
        Returns:
            Formatted PR body
        """
        body = f"""
## Why I'm doing:

## What I'm doing:        

This PR updates the {self.domain} documentation for the following languages:
- {', '.join(languages)}

### Changed Files
"""
        for file in changed_files:
            body += f"- `{file}`\n"
        
        body += """
### Generated by DocsAgent

This documentation was automatically generated by DocsAgent.

Please review the changes and merge if they look correct.

## What type of PR is this:

- [ ] BugFix
- [ ] Feature
- [ ] Enhancement
- [ ] Refactor
- [ ] UT
- [x] Doc
- [ ] Tool

Does this PR entail a change in behavior?

- [ ] Yes, this PR will result in a change in behavior.
- [x] No, this PR will not result in a change in behavior.

If yes, please specify the type of change:

- [ ] Interface/UI changes: syntax, type conversion, expression evaluation, display information
- [ ] Parameter changes: default values, similar parameters but with different default values
- [ ] Policy changes: use new policy to replace old one, functionality automatically enabled
- [ ] Feature removed
- [ ] Miscellaneous: upgrade & downgrade compatibility, etc.

## Checklist:

- [ ] I have added test cases for my bug fix or my new feature
- [ ] This pr needs user documentation (for new or modified features or behaviors)
  - [ ] I have added documentation for my new feature or new function
- [ ] This is a backport pr

## Bugfix cherry-pick branch check:
- [x] I have checked the version labels which the pr will be auto-backported to the target branch
  - [ ] 4.0
  - [ ] 3.5
  - [ ] 3.4
  - [ ] 3.3
"""
        
        return body
