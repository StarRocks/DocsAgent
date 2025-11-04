## 🔧 Development Guide

### Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/DocsAgent.git
cd DocsAgent

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Run with development config
python -m docsagent.main --config conf/dev.conf -e -t functions
```

### Directory Structure

```
DocsAgent/
├── conf/                   # Configuration files
│   ├── agent.conf          # Main config (user-created)
│   └── example.conf        # Example config template
├── src/docsagent/          # Source code
│   ├── main.py             # CLI entry point
│   ├── config.py           # Pydantic-based config management
│   ├── core/               # Core framework
│   │   ├── protocols.py    # DocumentableItem Protocol
│   │   ├── pipeline.py     # Generic DocGenerationPipeline[T]
│   │   ├── version_extractor.py  # Version tracking base class
│   │   └── __init__.py     
│   ├── domains/            # Domain implementations
│   │   ├── models.py       # ConfigItem, FunctionItem, VariableItem
│   │   ├── factory.py      # Pipeline factory
│   │   ├── fe_config/      # FE config domain
│   │   │   ├── extractor.py
│   │   │   ├── generator.py
│   │   │   ├── persister.py
│   │   │   ├── git_persister.py
│   │   │   └── version_extractor.py  # FE config version tracking
│   │   ├── be_config/      # BE config domain (same structure)
│   │   ├── variables/      # Variables domain (same structure)
│   │   └── functions/      # Functions domain (same structure)
│   ├── docs_extract/       # Metadata extraction
│   │   ├── config_meta_extract.py
│   │   ├── function_meta_extract.py
│   │   └── variables_meta_extract.py
│   ├── agents/             # LLM Agents (LangGraph)
│   │   ├── config_doc_agent.py
│   │   ├── functions_agent.py
│   │   ├── variables_agent.py
│   │   ├── translation_agent.py
│   │   ├── llm.py          # LLM wrapper
│   │   └── tools.py        # Agent tools
│   ├── tools/              # Utilities
│   │   ├── code_search.py  # Hyperscan regex search
│   │   ├── code_tools.py   # Code manipulation
│   │   ├── file_reader.py  # File operations
│   │   ├── git_operator.py # Git wrapper (enhanced for version tracking)
│   │   └── sr_client.py    # StarRocks MySQL client
│   └── docs_module/        # Documentation templates
│       ├── en/
│       ├── zh/
│       └── ja/
├── meta/                   # Extracted metadata
│   ├── be_config.meta
│   ├── fe_config.meta
│   ├── variables.meta
│   ├── be_config.version   # BE config version cache
│   ├── fe_config.version   # FE config version cache
│   ├── variables.version   # Variables version cache
│   ├── functions/          # Individual function meta files
│   └── logs/
├── output/                 # Generated documentation
│   ├── en/
│   ├── zh/
│   └── ja/
├── logs/                   # Application logs
└── tests/                  # Unit tests
```

### Adding New Document Types

DocsAgent's Protocol-based design makes it easy to add new document types. Follow these steps:

#### 1. Define Data Model

Implement the `DocumentableItem` protocol in `domains/models.py`:

```python
from dataclasses import dataclass, field
from typing import Dict, List, Any
from docsagent.core.protocols import DocumentableItem

@dataclass
class MyNewItem:
    """Your new document type"""
    name: str
    description: str = ""
    # Add domain-specific fields
    some_field: str = ""
    
    # Required by DocumentableItem protocol
    documents: Dict[str, str] = field(default_factory=dict)
    version: List[str] = field(default_factory=list)  # Version tracking support
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'some_field': self.some_field,
            'documents': self.documents,
            'version': self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MyNewItem':
        return cls(**data)
```

#### 2. Create Domain Directory

Create `src/docsagent/domains/mynewtype/` with these modules:

**a) extractor.py** - Extract metadata from source code
```python
from typing import List
from docsagent.domains.models import MyNewItem

class MyNewExtractor:
    """Extract MyNewItem from source code"""
    
    def extract(self, source_path: str) -> List[MyNewItem]:
        """
        Parse source code and extract metadata.
        Can use tree-sitter, regex, or any parsing method.
        """
        items = []
        # Your extraction logic here
        return items
```

**b) generator.py** - Generate documentation with LLM
```python
from docsagent.agents.llm import create_llm
from docsagent.domains.models import MyNewItem

class MyNewGenerator:
    """Generate documentation for MyNewItem"""
    
    def __init__(self):
        self.llm = create_llm()
    
    def generate(self, item: MyNewItem, lang: str) -> str:
        """Generate documentation in specified language"""
        # Include version info in prompt
        version_info = ", ".join(item.version) if item.version else "-"
        prompt = f"""Generate documentation for {item.name}
        Introduced in: {version_info}
        ..."""
        return self.llm.invoke(prompt)
```

**c) persister.py** - Save documentation to files
```python
from pathlib import Path
from typing import List
from docsagent.domains.models import MyNewItem

class MyNewPersister:
    """Save MyNewItem documentation"""
    
    def save(self, items: List[MyNewItem], output_dir: Path, lang: str):
        """Save documentation to output directory"""
        target_dir = output_dir / lang / "mynewtype"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        for item in items:
            if lang in item.documents:
                file_path = target_dir / f"{item.name}.md"
                file_path.write_text(item.documents[lang], encoding='utf-8')
```

**d) git_persister.py** - Optional Git integration
```python
from docsagent.domains.mynewtype.persister import MyNewPersister
from docsagent.tools.git_operator import GitOperator

class MyNewGitPersister(MyNewPersister):
    """Git-enabled persister"""
    
    def __init__(self, git_operator: GitOperator):
        super().__init__()
        self.git_operator = git_operator
```

**e) version_extractor.py** - Version tracking (optional but recommended)
```python
from pathlib import Path
from docsagent.core.version_extractor import BaseVersionExtractor
from docsagent.config import config

class MyNewVersionExtractor(BaseVersionExtractor):
    """Version tracker for MyNewItem"""
    
    def __init__(self):
        """Initialize with config from settings"""
        super().__init__(
            repo_path=config.STARROCKS_HOME,
            source_files=["path/to/your/source/files.ext"],
            version_file=Path(config.META_DIR) / "mynewtype.version",
            item_identifier_field="name"  # or other identifier field
        )
    
    def _extract_all_items_from_content(self, content: str) -> set:
        """
        Extract all item names from file content.
        
        This is called once per file per tag during version tracking.
        Use efficient batch extraction (regex, AST parsing, etc.)
        
        Returns:
            Set of item names found in content
        """
        item_names = set()
        # Your extraction logic here (regex, AST, etc.)
        # Example: pattern = re.compile(r'your_pattern')
        # for match in pattern.finditer(content):
        #     item_names.add(match.group(1))
        return item_names
```

#### 3. Add to Factory

Update `domains/factory.py`:

```python
def create_mynewtype_pipeline():
    """Create MyNewType documentation pipeline"""
    from docsagent.domains.mynewtype.extractor import MyNewExtractor
    from docsagent.domains.mynewtype.generator import MyNewGenerator
    from docsagent.domains.mynewtype.persister import MyNewPersister
    from docsagent.domains.mynewtype.git_persister import MyNewGitPersister
    from docsagent.domains.mynewtype.version_extractor import MyNewVersionExtractor
    from docsagent.core.pipeline import DocGenerationPipeline
    from docsagent.agents.translation_agent import TranslationAgent
    
    extractor = MyNewExtractor()
    generator = MyNewGenerator()
    persister = MyNewPersister()
    translation_agent = TranslationAgent()
    
    # Create version extractor (optional)
    version_extractor = MyNewVersionExtractor()
    
    pipeline = DocGenerationPipeline(
        extractor=extractor,
        doc_generator=generator,
        translation_agent=translation_agent,
        persister=persister,
        git_persister=MyNewGitPersister(),
        version_extractor=version_extractor,  # Inject version extractor
        item_type_name="mynewtype",
    )
    
    return pipeline
```

#### 4. Update CLI

Add your new type to `main.py`:

```python
parser.add_argument(
    '-t', '--type',
    choices=['fe_config', 'be_config', 'variables', 'functions', 'mynewtype'],
    help='Document type'
)
```

### Core Components

#### Pipeline (`core/pipeline.py`)

Generic 3-stage pipeline for all document types:

```python
class DocGenerationPipeline(Generic[T]):
    """
    Stage 1: Extract metadata from source code
    Stage 2: Generate docs with LLM (with optional version tracking)
    Stage 3: Persist to files or git
    """
    def run(self, track_new: bool = False):
        items = self.extractor.extract()
        
        # Optional: Track versions for new items
        if self.version_extractor and track_new:
            self.version_extractor.update_item_versions(items, track_new)
        
        self.generator.generate(items)
        self.persister.persist(items)
```

#### Protocols (`core/protocols.py`)

Duck typing for flexible document types:

```python
@runtime_checkable
class DocumentableItem(Protocol):
    name: str
    documents: Dict[str, str]
    version: List[str]  # Optional version tracking
    
    def to_dict(self) -> Dict: ...
    def from_dict(cls, data: Dict) -> Self: ...
```

#### Version Tracker (`core/version_extractor.py`)

Optional version tracking via git tag scanning:
- Batch processing with set operations (400+ items/sec)
- Caches results in `.version` files
- Smart version display filtering (3 rules)
- Tracks across recent 5 branches

Implement `_extract_all_items_from_content()` for your domain.

#### Domain Models (`domains/models.py`)

Data classes for each document type:

```python
@dataclass
class ConfigItem:
    name: str
    value: str
    default_value: str
    catalog: str
    documents: Dict[str, str] = field(default_factory=dict)
    version: List[str] = field(default_factory=list)  # Version tracking

@dataclass
class FunctionItem:
    name: str
    syntax: str
    catalog: str
    documents: Dict[str, str] = field(default_factory=dict)
    version: List[str] = field(default_factory=list)
```

#### Agents (`agents/`)

LangGraph-based LLM agents with tool support:
- **ConfigDocAgent**: Generate config documentation with code search
- **FunctionsAgent**: Generate function docs with SQL validation
- **VariablesAgent**: Generate variable documentation
- **TranslationAgent**: Translate docs to target languages

Each agent includes version info in prompts when available.

#### Factory (`domains/factory.py`)

Creates domain-specific pipelines with all dependencies:

```python
def create_fe_config_pipeline() -> DocGenerationPipeline[ConfigItem]:
    return DocGenerationPipeline(
        extractor=FEConfigExtractor(),
        generator=FEConfigGenerator(),
        persister=FEConfigPersister(),
        version_extractor=FEConfigVersionExtractor()  # Optional
    )
```

### Tech Stack

| Category              | Technology              | Purpose                           |
| --------------------- | ----------------------- | --------------------------------- |
| **Code Parsing**      | tree-sitter             | Parse Java/C++/Python source code |
|                       | tree-sitter-languages   | Multi-language grammar support    |
| **Pattern Matching**  | Hyperscan               | High-performance regex engine     |
| **LLM Framework**     | LangGraph               | Agent workflow orchestration      |
|                       | LangChain               | LLM toolchain and abstractions    |
|                       | langchain-openai        | OpenAI integration                |
|                       | langchain[anthropic]    | Anthropic/Claude integration      |
|                       | langchain[google-genai] | Google Gemini integration         |
| **Config Management** | pydantic-settings       | Type-safe configuration           |
| **Git Operations**    | GitPython               | Git repository interaction        |
| **Database**          | mysql-connector-python  | StarRocks SQL validation          |
| **Networking**        | httpx[socks]            | HTTP client with proxy support    |
| **Logging**           | loguru                  | Beautiful and powerful logging    |
| **Package Manager**   | Poetry                  | Dependency management             |

### Key Design Patterns

1. **Protocol Pattern**: Structural subtyping for `DocumentableItem`
2. **Pipeline Pattern**: 3-stage flow (Extract → Generate → Persist)
3. **Factory Pattern**: Domain-specific pipeline creation
4. **Agent Pattern**: LangGraph-based LLM agents with tools
5. **Strategy Pattern**: Different extractors/generators per domain

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Code Guidelines

- **Language**: Use English for code comments and docstrings
- **Style**: Follow PEP 8 (enforced by formatters)
- **Types**: Add type annotations for all function signatures
- **Tests**: Write unit tests for new features
- **Documentation**: Update README and docstrings
- **Commits**: Use clear, descriptive commit messages

### Project Guidelines

- Follow the Protocol-based design pattern
- Keep domains independent (no cross-domain imports)
- Use the generic pipeline for all document types
- Add logging with loguru for debugging
- Handle errors gracefully with informative messages
