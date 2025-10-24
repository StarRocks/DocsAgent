#!/usr/bin/env python3
"""
Core protocols for the DocsAgent documentation generation system.

These protocols define the minimal interface contracts that any documentable
item type must implement. Using Protocol instead of ABC allows for duck typing
and minimal coupling - existing classes can implement these interfaces without
explicit inheritance.

Design Philosophy:
- Protocol over Inheritance: Leverage Python's structural subtyping
- Minimal Contract: Only require essential fields and methods
- Type Safety: Use @runtime_checkable for both static and runtime validation
- Extensibility: Easy to add new document types without modifying core code
"""

import json
import os
from pathlib import Path
from typing import Protocol, TypeVar, Dict, Any, List, Optional, runtime_checkable
from abc import abstractmethod
from loguru import logger

@runtime_checkable
class DocumentableItem(Protocol):
    """
    Protocol for any item that can be documented in multiple languages.
    
    This is the core abstraction that enables the generic pipeline to work
    with different item types (configs, functions, variables, etc.).
    
    Minimal Contract:
    - name: Unique identifier for the item
    - documents: Dict mapping language codes to documentation content
    - to_dict/from_dict: Serialization support for persistence
    
    Example implementations:
    - ConfigItem: FE/BE configuration parameters
    - FunctionItem: Function signatures and docstrings
    - VariableItem: Session/system variables
    """
    
    @property
    def name(self) -> str:
        """
        Unique identifier for the item.
        
        This is used for:
        - Logging and error reporting
        - Filename generation
        - Deduplication
        
        Returns:
            str: Unique name (e.g., 'max_connections', 'calculate_total')
        """
        ...
    
    @property
    def documents(self) -> Dict[str, str]:
        """
        Multi-language documentation content.
        
        Keys are ISO 639-1 language codes ('en', 'zh', 'ja', etc.)
        Values are the documentation text (typically Markdown)
        
        The pipeline uses this to:
        - Determine which items need translation
        - Store generated/translated documentation
        - Group items by documentation status
        
        Returns:
            Dict[str, str]: Language code -> documentation content
            
        Example:
            {
                'zh': '配置项说明...',
                'en': 'Configuration description...',
                'ja': '設定項目の説明...'
            }
        """
        ...
        
    @property
    def useLocations(self) -> List[str]:
        """
        List of code locations where the item is used.
        
        Each location is typically a file path with line number(s).
        This information is useful for:
        - Contextual documentation generation
        - Usage analysis and statistics
        - Cross-referencing in docs
        
        Returns:
            List[str]: List of usage locations (e.g., ['src/config.py:45', 'src/main.py:102'])
        """
        ...
        
    @property
    def version(self) -> List[str]:
        """
        Version when the item was introduced.
        """
        ...
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the item to a dictionary.
        
        Used for:
        - Saving to JSON meta files
        - Caching item state
        - Debugging and inspection
        
        Returns:
            Dict[str, Any]: Dictionary representation of the item
            
        Note:
            Should include all fields needed to reconstruct the item
            via from_dict()
        """
        ...
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentableItem':
        """
        Deserialize the item from a dictionary.
        
        Used for:
        - Loading from JSON meta files
        - Restoring cached state
        - Test data construction
        
        Args:
            data: Dictionary representation of the item
            
        Returns:
            DocumentableItem: Reconstructed item instance
            
        Note:
            Should be the inverse of to_dict()
        """
        ...


# Type variable bound to DocumentableItem for generic implementations
T = TypeVar('T', bound=DocumentableItem)


@runtime_checkable
class ItemExtractor(Protocol[T]):
    """
    Protocol for extracting documentable items from a source.
    
    This class provides both:
    1. Protocol interface (abstract methods that must be implemented)
    2. Default implementations (concrete methods for common patterns)
    
    The extractor is responsible for:
    - Parsing source code, files, or databases
    - Creating item instances with metadata
    - Loading and merging existing documentation
    
    Subclass must implement:
    - _get_default_code_paths(): Return default paths to scan
    - _extract_all_items(): Domain-specific extraction logic
    - get_statistics(): Calculate statistics
    
    Subclass must provide attributes:
    - item_class: The DocumentableItem class to instantiate (e.g., ConfigItem, VariableItem)
    - meta_path: Path to meta file
    - supported_extensions: Set of file extensions to process
    - code_paths: List of file paths to process
    """
    
    # Required attributes (to be set by subclass)
    item_class: type = None  # Must be set to the concrete item class (e.g., ConfigItem)
    meta_path: Path = None
    supported_extensions: set = set()
    code_paths: List[str] = []
    
    # ===== Default implementations (provided by Protocol) =====
    
    def extract(
        self,
        force_search_code: bool = False,
        ignore_miss_usage: bool = True,
        **kwargs
    ) -> List[T]:
        """
        Extract items with standard flow: extraction, filtering, limiting.
        
        Default implementation:
        1. Call _extract_all_items() to extract
        2. Filter items without usage (if ignore_miss_usage=False)
        3. Apply limit
        4. Log statistics
        
        Args:
            limit: Optional limit on number of items to extract
            force_search_code: If True, force code usage search
            ignore_miss_usage: If False, filter out items without usage locations
            **kwargs: Extractor-specific options
        
        Returns:
            List[T]: List of extracted items with metadata
        """
        logger.info("Starting extraction...")
        
        kwargs['force_search_code'] = force_search_code
        # Extract all items (with meta merging)
        items = self._extract_all_items(**kwargs)
        
        # Filter items without usage (if configured)
        if ignore_miss_usage:
            original_count = len(items)
            items = [
                item for item in items 
                if item.useLocations is not None and len(item.useLocations) > 0
            ]
            filtered = original_count - len(items)
            if filtered > 0:
                logger.warning(f"Filtered {filtered} items without usage")
        
        # Log statistics
        stats = self.get_statistics(items) if hasattr(self, 'get_statistics') else {}
        logger.info(f"Extracted {len(items)} items: {stats}")
        
        return items
    
    def load_meta(self) -> List[T]:
        """
        Load items from meta JSON file.
        
        Default implementation with error handling:
        1. Check if meta file exists
        2. Parse JSON
        3. Deserialize items using _item_from_dict()
        4. Handle errors gracefully
        
        Returns:
            List[T]: Loaded items, or empty list if file doesn't exist
        """
        if not self.meta_path or not self.meta_path.exists():
            logger.info(f"Meta file does not exist: {self.meta_path}")
            return []
        
        try:
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            items = [self._item_from_dict(item) for item in data]
            logger.info(f"Loaded {len(items)} items from {self.meta_path}")
            return items
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in meta file: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load from {self.meta_path}: {e}")
            return []
    
    def _get_source_code_paths(self) -> List[Path]:
        """
        Scan and collect all source files from default paths.
        
        Default implementation:
        1. Get default paths from _get_default_code_paths()
        2. Walk directory tree
        3. Filter files using _should_process_file()
        4. Return list of file paths
        
        Returns:
            List[Path]: List of source file paths to process
        """
        codes = []
        for code_path in self._get_default_code_paths():
            if not os.path.exists(code_path):
                logger.warning(f"Code path does not exist: {code_path}")
                continue
                
            logger.info(f"Scanning code path: {code_path}")
            
            for root, dirs, files in os.walk(code_path):
                for file in files:
                    file_path = Path(root) / file
                    
                    logger.debug(f"Checking file: {file_path}")
                    
                    if not self._should_process_file(file_path):
                        logger.debug(f"Skipping file: {file_path}")
                        continue

                    codes.append(str(file_path))
        return codes

    def _should_process_file(self, file_path: Path) -> bool:
        """
        Check if a file should be processed.
        
        Default implementation filters out:
        - Files with unsupported extensions
        - Test directories
        - Test files
        
        Subclass can override to add custom filtering.
        
        Args:
            file_path: Path to check
            
        Returns:
            bool: True if file should be processed
        """
        if file_path.suffix not in self.supported_extensions:
            return False
        
        # Skip test directories and files conservatively
        parts_lower = [p.lower() for p in file_path.parts]
        if any(p in {'test', 'tests'} for p in parts_lower):
            return False
        # Common test file naming
        name_lower = file_path.name.lower()
        if name_lower.endswith('test') or name_lower.startswith('test'):
            return False
        
        return True
    
    def _item_from_dict(self, data: Dict[str, Any]) -> T:
        """
        Deserialize item from dictionary.
        
        Default implementation uses self.item_class.from_dict(data).
        Subclass can override for custom deserialization.
        
        Args:
            data: Dictionary representation of item
            
        Returns:
            T: Reconstructed item instance
            
        Raises:
            AttributeError: If item_class is not set on the subclass
        """
        if not hasattr(self, 'item_class') or self.item_class is None:
            raise AttributeError(
                f"{self.__class__.__name__} must set 'item_class' attribute "
                f"(e.g., item_class = ConfigItem)"
            )
        return self.item_class.from_dict(data)
    
    # ===== Abstract methods (must be implemented by subclass) =====
    
    @abstractmethod
    def _get_default_code_paths(self) -> List[str]:
        """
        Get default code scanning paths.
        
        Subclass must implement to return domain-specific paths.
        
        Returns:
            List[str]: List of directory paths to scan
            
        Example:
            def _get_default_code_paths(self) -> List[str]:
                return [
                    "/path/to/fe/source",
                    "/path/to/be/source",
                ]
        """
        ...

    @abstractmethod
    def _extract_all_items(self, **kwargs) -> List[T]:
        """
        Extract all items from source.
        
        Subclass must implement domain-specific extraction logic:
        1. Scan source files
        2. Extract items
        3. Load existing meta and merge (documents, useLocations, catalog)
        4. Optionally search code for usage locations
        
        Args:
            force_search_code: If True, search code for usage locations
            
        Returns:
            List[T]: Extracted items with merged metadata
            
        Example:
            def _extract_all_items(self, force_search_code=False) -> List[ConfigItem]:
                all_items = []
                
                # Extract from files
                for file_path in self.code_paths:
                    items = self._extract_from_file(file_path)
                    all_items.extend(items)
                
                # Merge with existing meta
                exists_metas = {m.name: m for m in self.load_meta()}
                for item in all_items:
                    if item.name in exists_metas:
                        item.documents = exists_metas[item.name].documents
                        item.useLocations = exists_metas[item.name].useLocations
                
                return all_items
        """
        ...

    @abstractmethod
    def get_statistics(self, items: List[T]) -> dict:
        """
        Calculate statistics for extracted items.
        
        Subclass must implement to provide meaningful statistics.
        
        Args:
            items: List of items to analyze
            
        Returns:
            dict: Statistics dictionary
            
        Example:
            def get_statistics(self, items: List[ConfigItem]) -> dict:
                return {
                    "total": len(items),
                    "by_scope": {"FE": 100, "BE": 50},
                    "with_docs": {"zh": 80, "en": 40},
                }
        """
        ...


@runtime_checkable
class DocGenerator(Protocol[T]):
    """
    Protocol for generating documentation for a single item.
    
    The generator is typically powered by:
    - LLM-based agents (e.g., ConfigDocAgent using LangGraph)
    - Template-based generation
    - Rule-based generation from metadata
    
    The generator focuses on creating the initial documentation
    (usually in Chinese or English). Translation is handled separately
    by TranslationAgent.
    """
    
    def generate(
        self,
        item: T,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate documentation for a single item.
        
        Args:
            item: The item to document
            
            context: Optional additional context for generation
                    Examples:
                    - related_items: Related items for cross-references
                    - style_guide: Documentation style preferences
                    - examples: Example documentation to mimic
                    - metadata: Project-specific metadata
        
        Returns:
            str: Generated documentation text (typically Markdown)
            
        Raises:
            ValueError: If item is invalid or missing required fields
            RuntimeError: If generation fails (e.g., LLM timeout)
            
        Example:
            generator = FEConfigDocGenerator()
            doc = generator.generate(
                item=config_item,
                context={'style': 'technical'}
            )
            
        Note:
            - Should be idempotent (same input -> same output)
            - Should handle errors gracefully
            - Should be relatively fast (will be called in batch)
        """
        ...


@runtime_checkable
class DocPersister(Protocol[T]):
    """
    Protocol for saving generated documentation to files.
    
    This class provides both:
    1. Protocol interface (abstract methods that must be implemented)
    2. Default implementations (concrete methods for common patterns)
    
    The persister handles:
    - Organizing items into a directory structure
    - Formatting documentation (e.g., Markdown with frontmatter)
    - Generating multi-language output files
    - Creating indexes and navigation
    - Saving metadata to JSON files
    
    Subclass must implement:
    - _save_documents(): Domain-specific document saving logic
    
    Subclass must provide attributes:
    - meta_path: Path to meta file for saving metadata
    """
    
    # Required attributes (to be set by subclass)
    meta_path: Path = None
    
    # ===== Default implementations (provided by Protocol) =====
    
    def save(
        self,
        items: List[T],
        output_dir: str,
        target_langs: List[str],
        **kwargs
    ) -> None:
        """
        Save generated documentation to the file system.
        
        Default implementation:
        1. Validate items are not empty
        2. Save metadata to JSON file via _save_meta()
        3. Save documents via _save_documents() (abstract method)
        4. Log success
        
        Args:
            items: List of items with generated documentation
            output_dir: Root directory for output files
            target_langs: Target languages to save (e.g., ['en', 'zh', 'ja'])
            **kwargs: Persister-specific options
        
        Returns:
            None
        """
        if not items:
            logger.warning("No items to save")
            return
        
        logger.info(f"Saving {len(items)} items → {output_dir} [{', '.join(target_langs)}]")
        
        # Save metadata
        self._save_meta(items)
        
        # Save documents (domain-specific implementation)
        self._save_documents(items, output_dir, target_langs)
        
        logger.info(f"Saved {len(items)} items")
    
    def _save_meta(self, items: List[T]) -> None:
        """
        Save metadata in JSON format.
        
        Default implementation:
        1. Serialize items to dict via to_dict()
        2. Write to meta_path as JSON
        3. Handle errors gracefully
        
        Args:
            items: List of items to save
            
        Returns:
            None
        """
        logger.info(f"Saving metadata → {self.meta_path}")
        
        try:
            data = [item.to_dict() for item in items]
            self.meta_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.meta_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(items)} items to {self.meta_path}")
        except Exception as e:
            logger.error(f"Failed to save metadata to {self.meta_path}: {e}")
        
        logger.info("Metadata saved")
    
    # ===== Abstract methods (must be implemented by subclass) =====
    
    @abstractmethod
    def _save_documents(
        self,
        items: List[T],
        output_dir: str,
        target_langs: List[str]
    ) -> None:
        """
        Save documentation files for all languages.
        
        Subclass must implement domain-specific document saving logic:
        1. Organize items (e.g., by catalog, module, etc.)
        2. Generate documentation for each language
        3. Apply templates
        4. Write to output files
        
        Args:
            items: List of items with generated documentation
            output_dir: Root directory for output files
            target_langs: Target languages to save
            
        Returns:
            None
            
        Example:
            def _save_documents(self, items, output_dir, target_langs):
                # Organize items by catalog
                catalogs = self._organize_by_catalog(items)
                
                # Generate docs for each language
                for lang in target_langs:
                    content = ""
                    for catalog, items in catalogs.items():
                        content += f"## {catalog}\\n\\n"
                        for item in items:
                            if lang in item.documents:
                                content += item.documents[lang] + "\\n\\n"
                    
                    # Apply template and save
                    self._apply_template_and_save(content, lang, output_dir)
        """
        ...


# Export type variable for use in other modules
__all__ = [
    'DocumentableItem',
    'ItemExtractor',
    'DocGenerator',
    'DocPersister',
    'T',
]
