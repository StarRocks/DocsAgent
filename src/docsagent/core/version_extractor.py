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

"""
Base version extractor for tracking when config items were first introduced.

This module provides the base class for version tracking across different
item types (FE/BE configs, variables, functions).

Uses duck typing (no ABC) to maintain consistency with the project's protocol design.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from docsagent.tools.git_operator import GitOperator


class BaseVersionExtractor:
    """
    Base class for version tracking.
    
    Tracks when configuration items were first introduced in each branch.
    
    Workflow:
    1. Group tags by branch (3.0, 3.1, 3.2, 3.3)
    2. For each branch, find first version where item appears
    3. Store raw version data (branch → first_version mapping)
    4. Version file format:
       {
         "metadata": {
           "git_version": "a3f5b2c",
           "source_files": ["path/to/Config.java", "path/to/Other.java"],
           "maintained_branches": ["3.0", "3.1", "3.2", "3.3"]
         },
         "versions": {
           "item_name": {
             "3.0": "3.0.11",
             "3.1": "3.1.1",
             "3.2": "3.2.5"
           }
         }
       }
    
    Subclasses should implement:
        _extract_all_items_from_content(content) -> set
    """
    
    def __init__(
        self,
        repo_path: str,
        source_files: List[str],
        version_file: Path,
        item_identifier_field: str = "name"
    ):
        """
        Initialize version extractor.
        
        Args:
            repo_path: Path to git repository (STARROCKS_HOME)
            source_files: List of relative paths to source files from repo root
            version_file: Path to version cache file (.version)
            item_identifier_field: Field name used to identify items (default: "name")
        """
        self.git_op = GitOperator(repo_path)
        if not self.git_op.validate_repository():
            raise RuntimeError(f"Invalid git repository: {repo_path}")
        
        # Support both single file (str) and multiple files (list)
        if isinstance(source_files, str):
            self.source_files = [source_files]
        else:
            self.source_files = source_files
        
        self.version_file = version_file
        self.item_identifier_field = item_identifier_field
        
        # Ensure version file directory exists
        self.version_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"VersionExtractor initialized: {len(self.source_files)} source files")
    
    def _extract_all_items_from_content(self, content: str) -> set:
        """
        Extract all item names from file content.
        
        Subclasses must implement this to batch extract all items.
        This is the core method for batch processing.
        
        Args:
            content: File content
        
        Returns:
            Set of item names found in content
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _extract_all_items_from_content()"
        )
    
    def track_versions(self, items: List[any]) -> Dict[str, Dict[str, str]]:
        """
        Track versions for a list of items.
        
        Args:
            items: List of items to track (must have name/show attribute)
        
        Returns:
            Dict mapping item_name → {branch: version}
            
        Example:
            {
              "enable_xxx": {"3.0": "3.0.11", "3.1": "3.1.1", "3.2": "3.2.5"},
              "another_config": {"3.2": "3.2.0", "3.3": "3.3.0"}
            }
        """
        logger.info(f"Tracking versions for {len(items)} items...")
        
        # Load existing cache
        cached_data = self.load_version_file()
        cached_versions = cached_data.get("versions", {})
        
        # Filter items that need tracking
        items_to_track = []
        item_names_to_track = []
        for item in items:
            item_name = self._get_item_identifier(item)
            if item_name not in cached_versions:
                items_to_track.append(item)
                item_names_to_track.append(item_name)
        
        if not items_to_track:
            logger.info("All items already cached")
            return cached_versions
        
        logger.info(f"Tracking {len(items_to_track)} new items...")
        
        # Get all release tags and group by branch
        tags = self.git_op.get_release_tags()
        branches = self._group_tags_by_branch(tags)
        
        logger.info(f"Found {len(branches)} branches: {list(branches.keys())}")
        logger.info(f"Processing in batch mode (optimized)...")
        
        # Batch process all items
        new_versions = self._find_first_versions_batch(item_names_to_track, branches)
        
        # Log results
        found_count = sum(1 for v in new_versions.values() if v)
        logger.info(f"  ✓ Found version info for {found_count}/{len(items_to_track)} items")
        
        # Merge with cached data
        cached_versions.update(new_versions)
        
        # Save updated cache
        self._save_version_file(cached_versions, list(branches.keys()))
        
        logger.info(f"Version tracking completed: {len(new_versions)} new items tracked")
        return cached_versions
    
    def _get_item_identifier(self, item: any) -> str:
        """
        Get identifier for an item.
        
        Default uses the configured field (usually 'name'),
        but can be overridden for special cases (e.g., Variables use 'show')
        """
        return getattr(item, self.item_identifier_field)
    
    def update_item_versions(self, items: List[any], track_new: bool = False) -> int:
        """
        Update items with version information.
        
        This is the main entry point for version management. It:
        1. Loads existing version data from cache file
        2. Optionally tracks new items if track_new=True
        3. Computes display versions using filtering rules
        4. Updates each item's version field
        
        Args:
            items: List of items to update (must have name/show attribute)
            track_new: If True, track versions for items not in cache
        
        Returns:
            Number of items updated with version info
        """
        # Load version data (from cache or track new)
        if track_new:
            version_data_map = self.track_versions(items)
        else:
            cached_data = self.load_version_file()
            version_data_map = cached_data.get("versions", {})
        
        if not version_data_map:
            logger.debug("No version data available")
            return 0
        
        # Prepare version data structure for display computation
        version_data = {
            "metadata": {
                "maintained_branches": list(self._get_maintained_branches(version_data_map))
            },
            "versions": version_data_map
        }
        
        # Get item names
        item_names = [self._get_item_identifier(item) for item in items]
        
        # Compute display versions
        display_versions = self.get_display_versions_for_items(
            version_data=version_data,
            item_names=item_names
        )
        
        # Update items
        updated_count = 0
        for item in items:
            item_name = self._get_item_identifier(item)
            if item_name in display_versions:
                display_list = display_versions[item_name]
                if display_list:
                    item.version = display_list
                    updated_count += 1
            
            if item.version is None:
                item.version = []
        logger.info(f"  ✓ Updated {updated_count}/{len(items)} items with version info")
        return updated_count
    
    def _get_maintained_branches(self, version_data_map: Dict[str, Dict[str, str]]) -> List[str]:
        """
        Extract maintained branches from version data.
        
        Args:
            version_data_map: Dict of item_name → {branch: version}
        
        Returns:
            Sorted list of unique branches
        """
        branches = set()
        for item_versions in version_data_map.values():
            branches.update(item_versions.keys())
        return sorted(branches, key=lambda b: [int(x) for x in b.split('.')])
    
    def _group_tags_by_branch(self, tags: List[str], keep_recent: int = 5) -> Dict[str, List[str]]:
        """
        Group tags by branch (x.y) and keep only recent branches.
        
        Args:
            tags: List of version tags like ['3.0.0', '3.0.1', '3.1.0', ...]
            keep_recent: Number of recent major branches to keep (default: 5)
        
        Returns:
            Dict of branch → sorted tags (only recent branches)
            {
              "3.2": ["3.2.0", "3.2.1", ...],
              "3.3": [...],
              "3.4": [...],
              "3.5": [...],
              "4.0": [...]
            }
        """
        branches = {}
        
        for tag in tags:
            parts = tag.split('.')
            if len(parts) >= 2:
                branch = f"{parts[0]}.{parts[1]}"
                if branch not in branches:
                    branches[branch] = []
                branches[branch].append(tag)
        
        # Sort tags within each branch
        for branch in branches:
            branches[branch].sort(key=lambda v: [int(x) for x in v.split('.')])
        
        # Keep only the most recent N branches
        sorted_branches = sorted(branches.keys(), key=lambda b: [int(x) for x in b.split('.')])
        if len(sorted_branches) > keep_recent:
            recent_branches = sorted_branches[-keep_recent:]
            branches = {b: branches[b] for b in recent_branches}
            logger.info(f"Filtered to recent {keep_recent} branches: {recent_branches}")
        
        return branches
    
    def _find_first_versions_batch(
        self,
        item_names: List[str],
        branches: Dict[str, List[str]]
    ) -> Dict[str, Dict[str, str]]:
        """
        Batch process: Find first version for multiple items across branches.
        
        Optimized approach using set operations:
        1. For each tag, extract all item names once
        2. Use set intersection to find matching items
        3. No repeated regex matching per item
        
        Args:
            item_names: List of item identifiers to track
            branches: Branch → tags mapping
        
        Returns:
            Dict of item_name → {branch → first_version}
            {
              "item1": {"3.0": "3.0.11", "3.1": "3.1.1"},
              "item2": {"3.1": "3.1.0", "3.2": "3.2.5"}
            }
        """
        # Initialize result structure: {item_name: {branch: first_version}}
        results = {name: {} for name in item_names}
        
        # Track which items still need to be found in each branch
        pending_items = {branch: set(item_names) for branch in branches.keys()}
        
        # Process by branch → tag → file
        for branch, tags in sorted(branches.items()):
            logger.debug(f"  Processing branch {branch} with {len(tags)} tags...")
            
            for tag in tags:
                if not pending_items[branch]:
                    # All items found in this branch
                    break
                
                # Extract items from all source files at this tag
                items_in_tag = set()
                for source_file in self.source_files:
                    content = self.git_op.get_file_at_tag(tag, source_file)
                    
                    if not content:
                        continue
                    
                    # Extract all items from content once (fast!)
                    try:
                        extracted_items = self._extract_all_items_from_content(content)
                        items_in_tag.update(extracted_items)
                    except Exception as e:
                        logger.warning(f"Failed to extract items from {source_file}@{tag}: {e}")
                        continue
                
                # Find intersection with pending items (set operation is very fast)
                found_items = pending_items[branch] & items_in_tag
                
                if found_items:
                    # Record first version for found items
                    for item_name in found_items:
                        results[item_name][branch] = tag
                    
                    # Remove from pending
                    pending_items[branch] -= found_items
                    
                    logger.debug(f"    {branch}@{tag}: found {len(found_items)} items")
                
                if not pending_items[branch]:
                    break
            
            if pending_items[branch]:
                logger.debug(f"  Branch {branch}: {len(pending_items[branch])} items not found in any tag")
        
        return results
    
    def load_version_file(self) -> Dict:
        """
        Load version data from file.
        
        Returns:
            {
              "metadata": {...},
              "versions": {item_name: {branch: version}}
            }
        """
        if not self.version_file.exists():
            logger.debug(f"Version file not found: {self.version_file}")
            return {"metadata": {}, "versions": {}}
        
        try:
            with open(self.version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Loaded version cache: {len(data.get('versions', {}))} items")
            return data
        except Exception as e:
            logger.warning(f"Failed to load version file: {e}")
            return {"metadata": {}, "versions": {}}
    
    def _save_version_file(self, versions: Dict[str, Dict[str, str]], maintained_branches: List[str]):
        """
        Save version data to file.
        
        Args:
            versions: Item versions mapping
            maintained_branches: List of maintained branches
        """
        data = {
            "metadata": {
                "git_version": self.git_op.get_current_version(),
                "source_files": self.source_files,
                "maintained_branches": maintained_branches
            },
            "versions": versions
        }
        
        try:
            with open(self.version_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved version cache: {len(versions)} items to {self.version_file}")
        except Exception as e:
            logger.error(f"Failed to save version file: {e}")
            raise
    
    @staticmethod
    def compute_display_versions(branch_versions: Dict[str, str], maintained_branches: Optional[List[str]] = None) -> List[str]:
        """
        Compute display versions from raw branch→version mapping.
        
        Filtering rules:
        1. If all maintained branches have the config, only show the lowest branch
        2. If config exists in consecutive branches up to the highest, exclude the highest
        3. Otherwise, show all branches where config exists
        
        Examples:
            {"3.0": "3.0.0", "3.1": "3.1.0", "3.2": "3.2.0", "3.3": "3.3.0"}
            → ["3.0.0"]  (all branches have it, show only earliest)
            
            {"3.0": "3.0.11", "3.1": "3.1.1", "3.2": "3.2.5", "3.3": "3.3.0"}
            → ["3.0.11", "3.1.1", "3.2.5"]  (backported, exclude highest 3.3.0)
            
            {"3.2": "3.2.5", "3.3": "3.3.0"}
            → ["3.2.5"]  (consecutive to highest, exclude 3.3.0)
            
            {"3.2": "3.2.0"}
            → ["3.2.0"]  (single branch)
            
            {"3.3": "3.3.0"}
            → ["3.3.0"]  (only highest branch)
        
        Args:
            branch_versions: Dict of branch → first_version
                            e.g., {"3.0": "3.0.11", "3.1": "3.1.1"}
            maintained_branches: List of all maintained branches (optional)
                                If not provided, inferred from branch_versions
        
        Returns:
            List of versions to display, sorted by branch
        """
        if not branch_versions:
            return []
        
        if len(branch_versions) == 1:
            return list(branch_versions.values())
        
        # Sort branches by version number
        sorted_branches = sorted(
            branch_versions.keys(),
            key=lambda b: [int(x) for x in b.split('.')]
        )
        
        # Infer maintained branches if not provided
        if maintained_branches is None:
            maintained_branches = sorted_branches
        else:
            # Sort maintained branches
            maintained_branches = sorted(
                maintained_branches,
                key=lambda b: [int(x) for x in b.split('.')]
            )
        
        highest_branch = sorted_branches[-1]
        highest_maintained = maintained_branches[-1] if maintained_branches else highest_branch
        
        # Rule 1: If all maintained branches have the config, only show the earliest
        if len(sorted_branches) == len(maintained_branches) and set(sorted_branches) == set(maintained_branches):
            # All branches have it, return only the first version
            return [branch_versions[sorted_branches[0]]]
        
        # Rule 2: If config exists in consecutive branches up to the highest maintained branch
        # Check if the actual branches are consecutive (no gaps between them)
        if highest_branch == highest_maintained:
            # Check if sorted_branches are consecutive in the maintained_branches list
            is_consecutive = True
            for i in range(len(sorted_branches) - 1):
                current_idx = maintained_branches.index(sorted_branches[i])
                next_idx = maintained_branches.index(sorted_branches[i + 1])
                if next_idx - current_idx != 1:
                    is_consecutive = False
                    break
            
            if is_consecutive:
                # Consecutive to highest, exclude the highest branch
                return [branch_versions[b] for b in sorted_branches[:-1]]
        
        # Rule 3: Otherwise, show all
        return [branch_versions[b] for b in sorted_branches]
    
    def get_display_versions_for_items(
        self,
        version_data: Optional[Dict] = None,
        item_names: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:
        """
        Compute display versions for given items.

        Args:
            item_names: List of item names to get versions for. If None, process all items.
            version_data: Optional pre-loaded version data dict with structure:
                {
                  "metadata": {"maintained_branches": ["3.0", "3.1", ...]},
                  "versions": {item_name: {branch: first_version}}
                }
                If not provided, it will be loaded from self.version_file.

        Returns:
            Dict mapping item_name → display_versions
            e.g., {"enable_xxx": ["3.0.11", "3.1.1", "3.2.5"]}
        """
        # Allow caller to pass in-memory version_data (avoids re-reading the file)
        if version_data is None:
            version_data = self.load_version_file()

        raw_versions = version_data.get("versions", {})
        maintained_branches = version_data.get("metadata", {}).get("maintained_branches")

        result: Dict[str, List[str]] = {}

        items_to_process = item_names if item_names else list(raw_versions.keys())

        for item_name in items_to_process:
            if item_name in raw_versions:
                branch_versions = raw_versions[item_name]
                display_versions = self.compute_display_versions(branch_versions, maintained_branches)
                result[item_name] = display_versions
            else:
                result[item_name] = []

        return result
