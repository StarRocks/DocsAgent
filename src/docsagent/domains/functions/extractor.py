"""ScalarFunctionExtractor: Extract scalar function items from Python function definition file"""

import os
import re
import ast
import json

from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger

from docsagent import config
from docsagent.core.protocols import ItemExtractor
from docsagent.domains.models import FunctionItem
from docsagent.tools.code_search import CodeFileSearch
from docsagent.tools import code_tools


class FunctionsExtractor(ItemExtractor):
    item_class = FunctionItem  # Item type for deserialization
    
    def __init__(self, code_paths: List[str] = None):
        """Initialize the function extractor"""
        self.supported_extensions = {'.py', '.cpp', '.h', '.hpp'}
        self.meta_path = Path(config.META_DIR) / "functions/"
        self.code_paths = code_paths or self._get_default_code_paths()
        Path(self.meta_path).mkdir(parents=True, exist_ok=True)
        logger.debug(f"ScalarFunctionExtractor initialized: {len(self.code_paths)} code files")

    def _get_default_code_paths(self) -> List[str]:
        """Get default code scanning paths - focus on function definition files"""
        starrocks_dir = Path(config.STARROCKS_HOME)
        # Focus on function definition file
        config_paths = [
            "be/src/exprs/",
            "gensrc/script/functions.py"
        ]
        
        full_paths = [str(starrocks_dir / path) for path in config_paths]
        return full_paths

    def _extract_function_items(self, file_path: str) -> List[FunctionItem]:
        """Extract and aggregate function items from Python source files
        
        Process:
        1. Parse functions.py to get raw function definitions
        2. Group by backend_fn to identify aliases (same implementation, different names)
        3. Group by name to aggregate overloads (same name, different signatures)
        4. Return aggregated FunctionItem list
        """
        # Skip non-supported files
        if not any(file_path.lower().endswith(ext) for ext in self.supported_extensions):
            return []

        if 'functions.py' not in file_path:
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Quick check if file contains function definitions
            if "vectorized_functions" not in content:
                return []

            logger.debug(f"Processing file: {file_path}")
            
            # Step 1: Parse all raw function definitions
            raw_functions = self._parse_functions_file(content, file_path)
            
            # Step 2 & 3: Aggregate functions (aliases + overloads)
            aggregated_functions = self._aggregate_functions(raw_functions)
            
            logger.info(f"Aggregated {len(raw_functions)} raw functions into {len(aggregated_functions)} items")
            
            return aggregated_functions
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            
        return []
    
    def _parse_functions_file(self, content: str, file_path: str) -> List[FunctionItem]:
        """Parse the functions.py file using AST to extract function definitions
        
        Expected format:
        [function_id, "name", exception_safe, check_overflow, "return_type", ["arg_types"], "backend_fn", ...]
        """
        items: List[FunctionItem] = []
        
        try:
            # Parse Python file using AST
            tree = ast.parse(content)
            
            # Find the vectorized_functions list
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name) and target.id == 'vectorized_functions':
                        continue
                    if not isinstance(node.value, ast.List):
                        continue
                    
                    # Process each function definition
                    for func_def in node.value.elts:
                        if not isinstance(func_def, ast.List):
                            continue
                        
                        item = self._parse_function_definition(func_def, file_path)
                        if item:
                            items.append(item)

        except Exception as e:
            logger.error(f"Failed to parse AST from {file_path}: {e}")
            
        return items
    
    def _aggregate_functions(self, raw_functions: List[FunctionItem]) -> List[FunctionItem]:
        """Aggregate functions by identifying aliases and overloads
        
        Strategy:
        1. Group by backend_fn to find aliases (same implementation, different names)
        2. For each backend_fn group, pick primary name and collect aliases
        3. Group by name to collect all signatures (overloads)
        4. Merge all related information
        
        Args:
            raw_functions: List of raw function items from parsing
            
        Returns:
            List of aggregated FunctionItem with aliases and overloads merged
        """
        from collections import defaultdict
        
        # Step 1: Group by complete implementation signature to identify aliases
        # Functions are aliases only if ALL their implementation functions match
        # (backend_fn, prepare_fn, close_fn)
        impl_groups = defaultdict(list)
        for func in raw_functions:
            # Create a tuple of all implementation functions (normalized to None if not present)
            # This ensures we only group functions with identical implementations
            impl_signature = tuple(func.implement_fns) if func.implement_fns else ()
            if impl_signature:
                impl_groups[impl_signature].append(func)
        
        logger.debug(f"Found {len(impl_groups)} unique implementation signatures")
        
        # Step 2: For each implementation group, identify primary name and aliases
        # Then group by primary name to aggregate overloads
        name_groups = defaultdict(lambda: {
            'signatures': [],
            'aliases': set(),
            'implement_fns': set(),
        })
        
        for impl_signature, funcs in impl_groups.items():
            # Get all unique names for this backend
            names = list(set(f.name for f in funcs))
            
            # Choose primary name (prefer shorter, more common names)
            # Priority: shortest name, then alphabetically first
            primary_name = min(names, key=lambda n: (len(n), n))
            
            # All other names are aliases
            aliases = [n for n in names if n != primary_name]
            
            # Collect all signatures for this backend + name combination
            for func in funcs:
                name_groups[primary_name]['signatures'].extend(func.signature)
                name_groups[primary_name]['aliases'].update(aliases)
                name_groups[primary_name]['implement_fns'].update(func.implement_fns)
        
        # Step 3: Create aggregated FunctionItem objects
        aggregated = []
        for name, data in name_groups.items():
            # Normalize signatures: extract parameter types and return type
            # to avoid duplicates from aliases (ceil, ceiling, dceil all have same param types)
            normalized_sigs = set()
            for sig in data['signatures']:
                # Extract (param_types) -> return_type
                if '(' in sig and ')' in sig and '->' in sig:
                    params = sig.split('(')[1].split(')')[0]
                    ret_type = sig.split('->')[-1].strip()
                    normalized = f"{name}({params}) -> {ret_type}"
                    normalized_sigs.add(normalized)
                else:
                    normalized_sigs.add(sig)
            
            # Deduplicate and sort signatures
            unique_signatures = sorted(list(normalized_sigs))
            
            # Deduplicate aliases and sort
            unique_aliases = sorted(list(data['aliases']))
            
            # Deduplicate implement_fns
            unique_implement_fns = list(set(fn for fn in data['implement_fns'] if fn))
            
            # Determine catalog from function name if not set
            
            item = FunctionItem(
                name=name,
                alias=unique_aliases,
                signature=unique_signatures,
                catalog=None,
                module="Scalar", 
                implement_fns=unique_implement_fns,
                testCases=[],
                useLocations=[],
                documents={},
                version=[]
            )
            
            aggregated.append(item)
        
        # Sort by name for consistency
        aggregated.sort(key=lambda x: x.name)
        
        logger.info(f"Aggregated into {len(aggregated)} unique functions")
        for item in aggregated[:5]:  # Log first 5 as examples
            alias_info = f" (aliases: {', '.join(item.alias)})" if item.alias else ""
            logger.debug(f"  {item.name}{alias_info}: {len(item.signature)} overload(s)")
        
        return aggregated
    
    
    def _parse_function_definition(self, func_node: ast.List, file_path: str) -> Optional[FunctionItem]:
        """Parse a single function definition from AST node
        
        Format: [id, name, exception_safe, check_overflow, return_type, [args], backend_fn, prepare_fn?, close_fn?]
        """
        try:
            elements = func_node.elts
            if len(elements) < 6:
                return None
            
            # Extract basic fields
            # func_id = ast.literal_eval(elements[0]) if isinstance(elements[0], ast.Constant) else None
            func_name = ast.literal_eval(elements[1]) if isinstance(elements[1], ast.Constant) else None
            # exception_safe = ast.literal_eval(elements[2]) if isinstance(elements[2], ast.Constant) else None
            # check_overflow = ast.literal_eval(elements[3]) if isinstance(elements[3], ast.Constant) else None
            return_type = ast.literal_eval(elements[4]) if isinstance(elements[4], ast.Constant) else None
            
            # Extract argument types
            arg_types = []
            if isinstance(elements[5], ast.List):
                for arg in elements[5].elts:
                    if isinstance(arg, ast.Constant):
                        arg_types.append(ast.literal_eval(arg))
            
            # Extract backend function
            #     [15028307, 'array_contains_seq', True, False, 'BOOLEAN', ['ARRAY_DECIMALV2', 'ARRAY_DECIMALV2'], 'ArrayFunctions::array_contains_seq_specific<TYPE_DECIMALV2>', 'ArrayFunctions::array_contains_seq_specific_prepare<TYPE_DECIMALV2>', 'ArrayFunctions::array_contains_seq_specific_close<TYPE_DECIMALV2>'],

            backend_fn = ast.literal_eval(elements[6]) if len(elements) > 6 and isinstance(elements[6], ast.Constant) else None
            backend_fn = backend_fn.split("<")[0].strip() if backend_fn and "<" in backend_fn else backend_fn
            backend_fn = None if backend_fn == "nullptr" else backend_fn
            
            prepare_fn = ast.literal_eval(elements[7]) if len(elements) > 7 and isinstance(elements[7], ast.Constant) else None
            prepare_fn = prepare_fn.split("<")[0].strip() if prepare_fn and "<" in prepare_fn else prepare_fn
            
            close_fn = ast.literal_eval(elements[8]) if len(elements) > 8 and isinstance(elements[8], ast.Constant) else None
            close_fn = close_fn.split("<")[0].strip() if close_fn and "<" in close_fn else close_fn
            
            # Build signature: name(arg1, arg2, ...) -> return_type
            args_str = ", ".join(arg_types) if arg_types else ""
            signature = f"{func_name}({args_str}) -> {return_type}"
            
            # Create FunctionItem (will be aggregated later)
            # Keep all implement functions for later analysis
            implement_fns = [fn for fn in [backend_fn, prepare_fn, close_fn] if fn]
            
            item = FunctionItem(
                name=func_name,
                alias=[],  # Will be determined during aggregation
                signature=[signature],
                catalog="",  # Will be inferred during aggregation
                module="Scalar",  # Default to Scalar
                implement_fns=implement_fns,
                testCases=[],
                useLocations=[],
                documents={},
                version=[]
            )
            
            return item
            
        except Exception as e:
            logger.warning(f"Failed to parse function definition: {e}")
            return None

    def _extract_all_items(self, **kwargs) -> List[FunctionItem]:
        """Scan all files in code paths and extract function items"""
        sources_files = self.code_paths

        all_items: Dict[str, FunctionItem] = {}
        
        for file_path in sources_files:
            try:
                function_items = self._extract_function_items(file_path)
                for item in function_items:
                    key = f"{item.name}"
                    all_items[key] = item
                
                if function_items:
                    logger.info(f"Found {len(function_items)} function items in {file_path}")
                else:
                    logger.debug(f"No function items found in {file_path}")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")

        # Merge with existing metadata
        exists_metas = self.load_meta()
        
        for item in exists_metas:
            if item.name in all_items:
                item.alias = all_items[item.name].alias
                item.signature = all_items[item.name].signature
                item.implement_fns = all_items[item.name].implement_fns
                all_items.pop(item.name)


        for item in all_items.values():
            exists_metas.append(item)           
                
        # Search for code usages if configured
        if 'force_search_code' in kwargs and kwargs['force_search_code']:
            self._search_implementations(exists_metas)

        if 'force_search_test' in kwargs and kwargs['force_search_test']:
            self._search_test_cases(exists_metas)
            
        logger.info(f"Total function items found: {len(exists_metas)}")
        return exists_metas

    def _search_implementations(self, exists_metas: List[FunctionItem]):
        logger.info("Searching for variable usage locations...")
            
        # Build keyword mapping: keyword -> variable name
        keyword_to_item = {}
        all_keywords = []
            
        for item in exists_metas:
            keywords = self._generate_search_keywords(item)
            for keyword in keywords:
                keyword_to_item[keyword] = item.name
                all_keywords.append(keyword)

        logger.info(f"Searching for {len(all_keywords)} keywords across {len(exists_metas)} variables...")

        # Search for all keywords
        code_search = CodeFileSearch(self.code_paths, file_filter=lambda f: f.suffix in ['.h', '.cpp', '.hpp'])
        search_results = code_search.search(all_keywords)

            # Aggregate results by variable name
        usage_by_func = {}
        for keyword, locations in search_results.items():
            if keyword in keyword_to_item:
                func_name = keyword_to_item[keyword]
                if func_name not in usage_by_func:
                    usage_by_func[func_name] = []
                usage_by_func[func_name].extend(locations)
            
            # Update items with usage locations (remove duplicates)
        for item in exists_metas:
            if item.name in usage_by_func:
                item.useLocations = list(set(usage_by_func[item.name]))
    

    def _search_test_cases(self, exists_metas: List[FunctionItem]):
        logger.info("Searching for function implementation locations...")
            
        # Build keyword mapping: keyword -> function name
        keyword_to_item = {}
        all_keywords = []
            
        for item in exists_metas:
            keywords = [item.name]
            keywords += item.alias
            for keyword in keywords:
                keyword_to_item[keyword] = item.name
                all_keywords.append(keyword)

        logger.info(f"Searching for {len(all_keywords)} keywords across {len(exists_metas)} functions...")

        # Search for all keywords
        Path(config.STARROCKS_HOME) / "test" / "sql"
        code_search = CodeFileSearch(self.code_paths, dir_filter=lambda d: 'R' in d.name)
        search_results = code_search.search(all_keywords)

        # Aggregate results by function name
        cases_by_func = {}
        for keyword, locations in search_results.items():
            if keyword in keyword_to_item:
                func_name = keyword_to_item[keyword]
                if func_name not in cases_by_func:
                    cases_by_func[func_name] = []
                cases_by_func[func_name].extend(locations)
            
            # Update items with usage locations (remove duplicates)
        for item in exists_metas:
            if item.name in cases_by_func:
                item.testCases = list(set(cases_by_func[item.name]))[:3]
    
    def _generate_search_keywords(self, item: FunctionItem) -> List[str]:
        keywords = []
        if not item.implement_fns or item.implement_fns == []:
            return []
        
        backend_fn_names = [fn.split("::")[-1] for fn in item.implement_fns if "::" in fn]
        for backend_fn in backend_fn_names:
            keywords.append(backend_fn)
        keywords.append(f"DEFINE_VECTORIZED_FN(${backend_fn_names[0]})")
        return keywords
    
    def load_meta(self) -> List[FunctionItem]:
        if not self.meta_path or not self.meta_path.exists():
            logger.info(f"Meta file does not exist: {self.meta_path}")
            return []
        
        try:
            items = []
            for root, dirs, files in os.walk(self.meta_path):
                for file in files:
                    if file.endswith('.meta'):
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        items.append(self._item_from_dict(data))
            return items
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in meta file: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load from {self.meta_path}: {e}")
            return []

    
    def get_statistics(self, items: List[FunctionItem]) -> dict:
        """Calculate basic statistics"""
        stats = {
            "total": len(items),
            "by_catalog": {},
            "by_module": {},
            "with_docs": {"zh": 0, "en": 0, "ja": 0},
        }
        
        for item in items:
            # Group by catalog
            stats["by_catalog"][item.catalog] = stats["by_catalog"].get(item.catalog, 0) + 1
            
            # Group by module
            stats["by_module"][item.module] = stats["by_module"].get(item.module, 0) + 1
            
            # Count documentation
            for lang in ["zh", "en", "ja"]:
                if lang in item.documents and item.documents[lang]:
                    stats["with_docs"][lang] += 1
        
        return stats
