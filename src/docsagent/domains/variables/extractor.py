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

"""VariablesExtractor: Extract variable items from Java source code"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from docsagent import config
from docsagent.core import ItemExtractor
from docsagent.domains.models import VariableItem
from docsagent.tools import code_tools
from docsagent.tools.code_search import CodeFileSearch


class VariablesExtractor(ItemExtractor):
    """
    Extract variable items from StarRocks source.
    
    Uses ExtractorMixin to provide:
    - extract(): Standard extraction flow
    - load_meta(): Meta file loading
    - _get_source_code_paths(): File scanning
    - _should_process_file(): File filtering
    
    Only implements:
    - _get_default_code_paths(): Variables-specific paths
    - _extract_all_items(): Variables-specific extraction logic
    - get_statistics(): Statistics calculation
    """
    item_class = VariableItem  # Item type for deserialization
    
    def __init__(self, code_paths: List[str] = None):
        """Initialize the variables extractor"""
        self.supported_extensions = {'.java', '.h', '.cpp', '.hpp'}
        self.meta_path = Path(config.META_DIR) / "variables.meta"
        self.code_paths = code_paths or self._get_source_code_paths()
        Path(self.meta_path).parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"VariablesExtractor initialized: {len(self.code_paths)} code files")
    
    def _get_default_code_paths(self) -> List[str]:
        """Get default variables code scanning paths (FE + BE)"""
        starrocks_dir = Path(config.STARROCKS_HOME)
        config_paths = [
            "fe/fe-core/src/main/java/com/starrocks/",
            "be/src/"
        ]
        
        full_paths = [str(starrocks_dir / path) for path in config_paths]
        return full_paths
    
    def _extract_variables(self, file_path: str) -> List[VariableItem]:
        """Extract configuration items from Java files using regex (simple and reliable)"""
        # Skip non-Java files
        if 'variable.java' not in file_path.lower():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Quick check if file contains @VarAttr annotations
            if "@VarAttr" not in content and "@VariableMgr.VarAttr" not in content:
                return []

            logger.debug(f"Processing file: {file_path}")
            items = self._extract_with_regex(content, file_path)
            
            logger.info(f"Extracted {len(items)} variable items from {file_path}")
            for i in items:
                logger.debug(f"  - {i.show} (type: {i.type}, default: {i.defaultValue})")
            
            return items
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            
        return []
    
    def _extract_with_regex(self, content: str, file_path: str) -> List[VariableItem]:
        """Extract variable items using regex pattern matching"""
        items = []
        
        # Pattern to match @VarAttr or @VariableMgr.VarAttr annotations with field declaration
        # Captures: annotation + field declaration
        # Supports: multi-line annotations, all Java field modifiers in any order
        # Java field modifiers: access(public/protected/private), static, final, transient, volatile, synchronized, native, strictfp
        pattern = r'@(?:VariableMgr\.)?VarAttr\s*\([^)]*\)\s*(?:(?:public|protected|private|static|final|transient|volatile|synchronized|native|strictfp)\s+)*(\w+(?:<[^>]+>)?)\s+(\w+)\s*=\s*([^;]+);'
        
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            try:
                full_match = match.group(0)
                var_type = match.group(1).strip()
                var_name = match.group(2).strip()
                var_default = match.group(3).strip()
                
                # Extract annotation parameters
                anno_match = re.search(r'@(?:VariableMgr\.)?VarAttr\s*\(([^)]+)\)', full_match)
                if not anno_match:
                    continue
                    
                # Parse annotation parameters
                params = code_tools.parse_equals_pair(anno_match.group(1))

                name = self._extract_param_value(params, 'name', content)
                show = self._extract_param_value(params, 'show', content)
                flag = self._extract_param_value(params, 'flag', content)
                
                # Determine display name: show > name > alias
                display_name = show if show else name
                
                # Check if invisible
                is_invisible = 'INVISIBLE' in flag if flag else False
                
                # Extract comment (look for comment above the annotation)
                comment = code_tools.extract_cstyle_comment_before_position(content, match.start())
                
                # Create VariableItem
                item = VariableItem(
                    name=var_name,
                    show=display_name,
                    type=var_type,
                    defaultValue=var_default,
                    comment=comment,
                    invisible=is_invisible,
                    scope= "Global" if 'global' in file_path.lower() else "Session",
                    useLocations=[],
                    documents={}
                )
                
                items.append(item)
                logger.debug(f"Extracted variable: {item.name} (type: {item.type}, default: {item.defaultValue})")
                
            except Exception as e:
                logger.warning(f"Failed to parse variable at position {match.start()}: {e}")
                continue
        
        return items
    
    def _extract_param_value(self, anno_params: dict[str:str], param_name: str, full_content: str) -> str:
        """
        Extract parameter value from annotation parameters.
        Handles both string literals and constant references.
        
        Args:
            anno_params: The annotation parameters string
            param_name: The parameter name to extract (e.g., 'name', 'alias', 'show')
            full_content: Full file content for constant lookup
            
        Returns:
            The parameter value or empty string if not found
        """
        value = anno_params.get(param_name, "")
        # If it's not a quoted string, it might be a constant reference
        if not (value.startswith('"') or value.startswith("'")):
            # Look up the constant value in the file
            constant_value = self._lookup_constant(value, full_content)
            return constant_value if constant_value else value
        
        # Remove quotes
        return value.strip('"\'')
    
    def _lookup_constant(self, constant_name: str, content: str) -> str:
        """
        Look up a constant value in the file content.
        
        Args:
            constant_name: The constant name to look up
            content: The file content
            
        Returns:
            The constant value or empty string if not found
        """
        # Pattern to match: [modifiers] String CONSTANT_NAME = "value";
        # Supports all Java field modifiers in any order
        pattern = rf'(?:(?:public|protected|private|static|final|transient|volatile|synchronized|native|strictfp)\s+)*String\s+{constant_name}\s*=\s*["\']([^"\']+)["\']'
        match = re.search(pattern, content)
        
        if match:
            return match.group(1)
        return ""
    
    def _extract_all_items(self, **kwargs) -> List[VariableItem]:
        """Scan all files and extract variable items (required by ExtractorMixin)"""
        sources_files = self.code_paths

        all_items: List[VariableItem] = []
        
        for file_path in sources_files:
            try:
                var_items = self._extract_variables(file_path)
                all_items.extend(var_items)
                
                if var_items:
                    logger.debug(f"Found {len(var_items)} variable items in {file_path}")
                else:
                    logger.debug(f"No variable items found in {file_path}")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                
        # Load existing metadata and merge
        exists_metas = {}
        for meta in self.load_meta():
            exists_metas[meta.show] = meta

        for meta in all_items:
            if meta.show in exists_metas:
                meta.useLocations = exists_metas[meta.show].useLocations
                meta.documents = exists_metas[meta.show].documents
                meta.version = exists_metas[meta.show].version
            
        # Search for code usages if configured
        if 'force_search_code' in kwargs and kwargs['force_search_code']:
            logger.debug("Searching for variable usage locations...")
            
            # Build keyword mapping: keyword -> variable name
            keyword_to_item = {}
            all_keywords = []
            
            for item in all_items:
                keywords = self._generate_search_keywords(item)
                for keyword in keywords:
                    keyword_to_item[keyword] = item.name
                    all_keywords.append(keyword)
            
            logger.debug(f"Searching for {len(all_keywords)} keywords across {len(all_items)} variables...")
            
            # Search for all keywords
            code_search = CodeFileSearch(self.code_paths, file_filter=lambda f: f.suffix in ['.java'])
            search_results = code_search.search(all_keywords)

            # Aggregate results by variable name
            usage_by_var = {}
            for keyword, locations in search_results.items():
                if keyword in keyword_to_item:
                    var_name = keyword_to_item[keyword]
                    if var_name not in usage_by_var:
                        usage_by_var[var_name] = []
                    usage_by_var[var_name].extend(locations)
            
            # Update items with usage locations (remove duplicates)
            for item in all_items:
                if item.name in usage_by_var:
                    item.useLocations = list(set(usage_by_var[item.name]))

        logger.debug(f"Total variable items found: {len(all_items)}")
        return all_items
    
    def _generate_search_keywords(self, item: VariableItem) -> List[str]:
        """
        Generate search keywords for a variable item.
        
        Strategy:
        1. Try to find actual setter/getter method names from source code
        2. Fallback to generated names based on variable name
        
        Includes:
        - Direct variable name reference
        - Setter method (actual or generated)
        - Getter method (actual or generated)
        - Underscore naming convention
        
        Args:
            item: The variable item
            
        Returns:
            List of search keywords
        """
        keywords = []
        var_name = item.name
        
        # 1. Direct reference: Variable.variableName
        keywords.append(f"Variable.{var_name}")
        
        # 2. Try to find actual setter/getter methods from source code
        actual_methods = self._find_actual_methods(var_name)
        
        if actual_methods:
            # Use actual method names found in source
            keywords.extend(actual_methods)
            logger.debug(f"Found actual methods for {var_name}: {actual_methods}")
        else:
            # Fallback: Generate method names based on variable name
            camel_case = self._to_camel_case(var_name, capitalize_first=True)
            
            # Setter method: setVariableName
            keywords.append(f"set{camel_case}")
            
            # Getter method: getVariableName or isVariableName (for boolean)
            if item.type.lower() == 'boolean':
                keywords.append(f"is{camel_case}")
            keywords.append(f"get{camel_case}")
        
        # 3. Underscore naming: variable_name
        keywords.append(self._to_snake_case(var_name))
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(keywords))
    
    def _to_camel_case(self, name: str, capitalize_first: bool = False) -> str:
        """Convert variable name to camelCase"""
        if '_' in name:
            # Convert snake_case to camelCase
            parts = name.split('_')
            if capitalize_first:
                return ''.join(p.capitalize() for p in parts)
            else:
                return parts[0] + ''.join(p.capitalize() for p in parts[1:])
        else:
            # Already camelCase
            if capitalize_first and name:
                return name[0].upper() + name[1:]
            return name
    
    def _to_snake_case(self, name: str) -> str:
        """Convert camelCase to snake_case"""
        if '_' in name:
            # Already snake_case
            return name.lower()
        
        # Insert underscore before uppercase letters
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result.append('_')
            result.append(char.lower())
        return ''.join(result)
    
    def _find_actual_methods(self, var_name: str) -> List[str]:
        """
        Find actual setter/getter method names for a variable from source code.
        
        Strategy:
        1. Use simple line-based search instead of complex regex
        2. Look for patterns like "this.varName =" and "return this.varName"
        3. Extract method name from the method signature above
        
        Example:
        - Variable field: private boolean cboJSONV2Rewrite
        - Setter: public void setEnableJSONV2Rewrite(...) { this.cboJSONV2Rewrite = ...; }
        - Getter: public boolean isEnableJSONV2Rewrite() { return this.cboJSONV2Rewrite; }
        
        Args:
            var_name: The Java field name (e.g., cboJSONV2Rewrite)
            
        Returns:
            List of actual method names found, or empty list if not found
        """
        method_names = []
        
        for file_path in self.code_paths:
            if 'variable.java' not in file_path.lower():
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Search line by line for variable references
                for i, line in enumerate(lines):
                    # Check for setter pattern: this.varName = 
                    if f'this.{var_name}' in line and '=' in line:
                        method_name = self._extract_method_name_backward(lines, i)
                        if method_name and method_name not in method_names:
                            method_names.append(method_name)
                            logger.debug(f"Found setter for {var_name}: {method_name}")
                    
                    # Check for getter pattern: return this.varName or return varName
                    if 'return' in line and (f'this.{var_name}' in line or f' {var_name};' in line or f' {var_name} ' in line):
                        method_name = self._extract_method_name_backward(lines, i)
                        if method_name and method_name not in method_names:
                            method_names.append(method_name)
                            logger.debug(f"Found getter for {var_name}: {method_name}")
                    
            except Exception as e:
                logger.debug(f"Error searching methods for {var_name} in {file_path}: {e}")
                continue
        
        return method_names
    
    def _extract_method_name_backward(self, lines: List[str], start_line: int) -> Optional[str]:
        """
        Extract method name by searching backward from a given line.
        
        Looks for the nearest method signature like:
        - public void methodName(...)
        - public Type methodName(...)
        
        Args:
            lines: All lines of the file
            start_line: Line index to start searching backward from
            
        Returns:
            Method name if found, None otherwise
        """
        # Search backward up to 20 lines (should cover most method signatures)
        for i in range(start_line, max(0, start_line - 20), -1):
            line = lines[i].strip()
            
            # Look for public method signature
            # Pattern: public <returnType> methodName(...)
            method_match = re.match(r'public\s+(?:\w+(?:<[^>]+>)?)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', line)
            if method_match:
                return method_match.group(1)
        
        return None
    
    def get_statistics(self, items: List[VariableItem]) -> dict:
        """Calculate basic statistics"""
        stats = {
            "total": len(items),
            "by_scope": {},
            "by_invisible": {"visible": 0, "invisible": 0},
            "with_docs": {"zh": 0, "en": 0, "ja": 0},
        }
        
        for item in items:
            stats["by_scope"][item.scope] = stats["by_scope"].get(item.scope, 0) + 1
            
            if item.invisible:
                stats["by_invisible"]["invisible"] += 1
            else:
                stats["by_invisible"]["visible"] += 1
            
            for lang in ["zh", "en", "ja"]:
                if lang in item.documents and item.documents[lang]:
                    stats["with_docs"][lang] += 1
        
        return stats
