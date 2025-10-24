"""Git operations for committing and pushing documentation changes"""

import os
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from git import Repo, InvalidGitRepositoryError
from loguru import logger


class GitOperator:
    """
    Git operations wrapper for documentation updates.
    
    Handles:
    - Branch creation and management
    - File copying and committing
    - Pushing to remote
    - GitHub Pull Request creation via API
    """
    
    def __init__(self, repo_path: str, github_token: Optional[str] = None,
                 github_repo: Optional[str] = None):
        """
        Initialize GitOperator.
        
        Args:
            repo_path: Path to the git repository (e.g., STARROCKS_HOME)
            github_token: GitHub personal access token (required for PR creation)
            github_repo: GitHub repository in format 'owner/repo' (e.g., 'StarRocks/starrocks')
                        If not provided, will try to auto-detect from git remote URL
        """
        self.repo_path = Path(repo_path)
        self.github_token = github_token
        self.repo: Optional[Repo] = None
        self.current_branch: Optional[str] = None
        self._github_repo: Optional[str] = github_repo  # Manual config or auto-detect
        
        logger.debug(f"GitOperator initialized: repo_path={repo_path}")
    
    def validate_repository(self) -> bool:
        """
        Check if the path is a valid git repository.
        
        Returns:
            True if valid git repository, False otherwise
        """
        if not self.repo_path.exists():
            logger.warning(f"Repository path does not exist: {self.repo_path}")
            return False
        
        try:
            self.repo = Repo(self.repo_path)
            logger.debug(f"Valid git repository found: {self.repo_path}")
            return True
        except InvalidGitRepositoryError:
            logger.warning(f"Not a git repository: {self.repo_path}")
            return False
    
    def _get_github_repo(self) -> Optional[str]:
        """
        Get GitHub repository in 'owner/repo' format.
        
        Priority:
        1. Use manually configured github_repo if provided
        2. Auto-detect from git remote URL
        
        Returns:
            Repository in format 'owner/repo' (e.g., 'StarRocks/starrocks')
            or None if not a GitHub repository
        """
        # Return cached value if already determined
        if self._github_repo:
            logger.debug(f"Using configured GitHub repository: {self._github_repo}")
            return self._github_repo
        
        if not self.repo:
            return None
        
        try:
            # Get origin remote URL
            origin = self.repo.remote('origin')
            url = origin.url
            
            # Parse GitHub URL
            # Supports both HTTPS and SSH formats:
            # - https://github.com/StarRocks/starrocks.git
            # - git@github.com:StarRocks/starrocks.git
            
            if 'github.com' not in url:
                logger.warning(f"Remote URL is not a GitHub repository: {url}")
                return None
            
            # Extract owner/repo
            if url.startswith('https://'):
                # https://github.com/owner/repo.git
                parts = url.replace('https://github.com/', '').replace('.git', '').split('/')
            elif url.startswith('git@'):
                # git@github.com:owner/repo.git
                parts = url.replace('git@github.com:', '').replace('.git', '').split('/')
            else:
                logger.warning(f"Unsupported GitHub URL format: {url}")
                return None
            
            if len(parts) >= 2:
                self._github_repo = f"{parts[0]}/{parts[1]}"
                logger.debug(f"Detected GitHub repository: {self._github_repo}")
                return self._github_repo
            
            logger.warning(f"Could not parse GitHub repository from URL: {url}")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get GitHub repository info: {e}")
            return None
    
    def create_branch(self, domain: str, base_branch: str = "main") -> str:
        """
        Create and checkout a new branch for documentation updates.
        
        Args:
            domain: Domain name (e.g., 'fe_config', 'functions')
            base_branch: Base branch to create from (default: 'main')
        
        Returns:
            Branch name created
        
        Raises:
            RuntimeError: If branch creation fails
        """
        if not self.repo:
            raise RuntimeError("Repository not initialized. Call validate_repository() first.")
        
        # Generate branch name: docs/update-{domain}-{timestamp}
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"docs/update-{domain}-{timestamp}"
        
        try:
            # Ensure we're on the base branch and it's up to date
            if base_branch not in self.repo.heads:
                logger.warning(f"Base branch '{base_branch}' not found, using current branch")
            else:
                self.repo.heads[base_branch].checkout()
                logger.debug(f"Checked out base branch: {base_branch}")
            
            # Create new branch
            new_branch = self.repo.create_head(branch_name)
            new_branch.checkout()
            
            self.current_branch = branch_name
            logger.debug(f"Created and checked out branch: {branch_name}")
            
            return branch_name
            
        except Exception as e:
            logger.error(f"Failed to create branch: {e}")
            raise RuntimeError(f"Branch creation failed: {e}")
    
    def copy_and_commit(
        self, 
        file_mappings: Dict[str, str], 
        domain: str,
        languages: Optional[List[str]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Copy files according to mapping and create a commit.
        
        Args:
            file_mappings: Dict mapping source paths to target paths
                          {source_relative_path: target_relative_path}
            domain: Domain name for commit message
            languages: List of languages updated (for commit message)
        
        Returns:
            Tuple of (success: bool, changed_files: List[str])
        
        Note:
            File mappings should be provided by domain-specific persister.
            TODO: Implement file mapping configuration in domain persisters.
        """
        if not self.repo:
            raise RuntimeError("Repository not initialized")
        
        changed_files = []
        
        try:
            # Copy files according to mapping
            for source_rel, target_rel in file_mappings.items():
                source_path = Path(source_rel).resolve()
                target_path = self.repo_path / target_rel
                
                if not source_path.exists():
                    logger.warning(f"Source file not found, skipping: {source_path}")
                    continue
                
                # Create target directory if needed
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                import shutil
                shutil.copy2(source_path, target_path)
                changed_files.append(str(target_rel))
                logger.debug(f"Copied: {source_rel} -> {target_rel}")
            
            if not changed_files:
                logger.warning("No files were copied, skipping commit")
                return False, []
            
            # Stage changed files
            self.repo.index.add(changed_files)
            
            # Generate commit message
            commit_message = self._generate_commit_message(domain, changed_files, languages)
            
            # Commit
            self.repo.index.commit(commit_message)
            logger.debug(f"Created commit with {len(changed_files)} file(s)")
            
            return True, changed_files
            
        except Exception as e:
            logger.error(f"Failed to copy and commit files: {e}")
            return False, []
    
    def _generate_commit_message(
        self, 
        domain: str, 
        changed_files: List[str],
        languages: Optional[List[str]] = None
    ) -> str:
        """
        Generate commit message.
        
        Args:
            domain: Domain name
            changed_files: List of changed file paths
            languages: List of languages updated
        
        Returns:
            Formatted commit message
        """
        lang_str = ", ".join(languages) if languages else "multiple languages"
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        message = f"""docs({domain}): update {lang_str} documentation

Updated {len(changed_files)} file(s):
"""
        for file in changed_files:
            message += f"- {file}\n"
        
        message += f"\nGenerated by DocsAgent on {date_str}"
        
        return message
    
    def push(self, remote: str = "origin") -> bool:
        """
        Push current branch to remote.
        
        Args:
            remote: Remote name (default: 'origin')
        
        Returns:
            True if push succeeded, False otherwise
        """
        if not self.repo or not self.current_branch:
            logger.error("No branch to push")
            return False
        
        try:
            # Push to remote
            origin = self.repo.remote(remote)
            origin.push(self.current_branch)
            
            logger.info(f"Pushed branch '{self.current_branch}' to {remote}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to push: {e}")
            return False
    
    def create_pull_request(
        self,
        title: str,
        body: str,
        base: str = "main",
        head: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a Pull Request on GitHub.
        
        Args:
            title: PR title
            body: PR description
            base: Base branch (default: 'main')
            head: Head branch (default: current_branch)
        
        Returns:
            PR URL if successful, None otherwise
        
        Requires:
            - github_token to be set
            - Repository must be a GitHub repository
        """
        if not self.github_token:
            logger.error("GitHub token not provided, cannot create PR")
            return None
        
        # Auto-detect GitHub repository
        github_repo = self._get_github_repo()
        if not github_repo:
            logger.error("Could not determine GitHub repository from remote URL")
            return None
        
        head_branch = head or self.current_branch
        if not head_branch:
            logger.error("No branch specified for PR")
            return None
        
        try:
            # Get the authenticated user's login to construct proper head reference
            user_api_url = "https://api.github.com/user"
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            user_response = requests.get(user_api_url, headers=headers)
            user_response.raise_for_status()
            user_login = user_response.json().get("login")
            
            # For cross-repository PRs (from fork), head format should be "username:branch"
            # For same-repository PRs, just use "branch"
            # Check if current repo is a fork by comparing with target repo
            try:
                origin_url = self.repo.remote('origin').url
                if user_login and user_login.lower() not in github_repo.lower().split('/')[0].lower():
                    # This is likely a fork, use "username:branch" format
                    head_ref = f"{user_login}:{head_branch}"
                    logger.debug(f"Using cross-fork head reference: {head_ref}")
                else:
                    # Same repository, just use branch name
                    head_ref = head_branch
                    logger.debug(f"Using same-repo head reference: {head_ref}")
            except Exception as e:
                logger.warning(f"Could not determine fork status, using username:branch format: {e}")
                head_ref = f"{user_login}:{head_branch}" if user_login else head_branch
            
            # GitHub API endpoint
            api_url = f"https://api.github.com/repos/{github_repo}/pulls"
            
            data = {
                "title": title,
                "body": body,
                "head": head_ref,
                "base": base
            }
            
            logger.debug(f"Creating PR with data: {data}")
            
            # Create PR
            response = requests.post(api_url, json=data, headers=headers)
            response.raise_for_status()
            
            pr_data = response.json()
            pr_url = pr_data.get("html_url")
            
            logger.info(f"Created Pull Request: {pr_url}")
            return pr_url
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create PR: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None
    
    def cleanup(self, return_to_branch: str = "main"):
        """
        Cleanup: return to original branch.
        
        Args:
            return_to_branch: Branch to checkout after operations
        """
        if not self.repo:
            return
        
        try:
            if return_to_branch in self.repo.heads:
                self.repo.heads[return_to_branch].checkout()
                logger.debug(f"Returned to branch: {return_to_branch}")
        except Exception as e:
            logger.warning(f"Failed to cleanup: {e}")
