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

from typing import Protocol, TypeVar, Dict, Any, List, Optional, runtime_checkable


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
    
    The extractor is responsible for:
    - Parsing source code, files, or databases
    - Creating item instances with metadata
    - Optionally loading existing documentation
    
    Different item types have different extraction strategies:
    - ConfigItem: Parse Java/C++ config classes with tree-sitter
    - FunctionItem: Parse function signatures and docstrings
    - VariableItem: Parse variable declarations and comments
    """
    
    def extract(
        self,
        source: str,
        limit: Optional[int] = None,
        **kwargs
    ) -> List[T]:
        """
        Extract items from the specified source.
        
        Args:
            source: Source location (file path, directory, URL, etc.)
                    Interpretation depends on the specific extractor:
                    - FEConfigExtractor: Path to Java source directory
                    - FunctionExtractor: Path to Python/Java source files
                    - VariableExtractor: Path to config files
            
            limit: Optional limit on number of items to extract
                   Useful for:
                   - Testing with a small sample
                   - Incremental processing
                   - Performance tuning
            
            **kwargs: Extractor-specific options
                     Examples:
                     - file_pattern: Glob pattern for files
                     - recursive: Whether to search recursively
                     - include_private: Whether to include private items
        
        Returns:
            List[T]: List of extracted items with metadata
            
        Raises:
            FileNotFoundError: If source doesn't exist
            ValueError: If source format is invalid
            
        Example:
            extractor = FEConfigExtractor()
            configs = extractor.extract(
                source='/path/to/fe/conf',
                limit=10,
                recursive=True
            )
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
    
    The persister handles:
    - Organizing items into a directory structure
    - Formatting documentation (e.g., Markdown with frontmatter)
    - Generating multi-language output files
    - Creating indexes and navigation
    
    Different item types may have different organization strategies:
    - ConfigItem: Group by catalog (Logging, Server, etc.)
    - FunctionItem: Group by module/class
    - VariableItem: Group by scope (session, system, etc.)
    """
    
    def save(
        self,
        items: List[T],
        output_dir: str,
        languages: List[str],
        **kwargs
    ) -> None:
        """
        Save generated documentation to the file system.
        
        Args:
            items: List of items with generated documentation
            
            output_dir: Root directory for output files
                       Structure is typically:
                       {output_dir}/
                         {lang}/
                           {category}/
                             {item_name}.md
            
            languages: Target languages to save
                      e.g., ['en', 'zh', 'ja']
                      Only items with documentation in these languages
                      will be saved
            
            **kwargs: Persister-specific options
                     Examples:
                     - organize_by: Grouping strategy ('catalog', 'module', etc.)
                     - format: Output format ('markdown', 'html', 'json')
                     - include_meta: Whether to include metadata files
                     - template: Custom template for formatting
        
        Returns:
            None
            
        Raises:
            OSError: If output directory cannot be created/written
            ValueError: If items have missing documentation for specified languages
            
        Example:
            persister = ConfigPersister()
            persister.save(
                items=configs,
                output_dir='./output/docs',
                languages=['en', 'zh'],
                organize_by='catalog'
            )
            
        Side Effects:
            - Creates directories as needed
            - Overwrites existing files
            - May create additional index/navigation files
            
        Note:
            - Should be atomic (all or nothing if possible)
            - Should create directories automatically
            - Should handle filesystem errors gracefully
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
