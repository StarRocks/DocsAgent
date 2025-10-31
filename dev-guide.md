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
│   │   └── __init__.py     
│   ├── domains/            # Domain implementations
│   │   ├── models.py       # ConfigItem, FunctionItem, VariableItem
│   │   ├── factory.py      # Pipeline factory
│   │   ├── fe_config/      # FE config domain
│   │   │   ├── extractor.py
│   │   │   ├── generator.py
│   │   │   ├── persister.py
│   │   │   └── git_persister.py
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
│   │   ├── git_operator.py # Git wrapper
│   │   └── sr_client.py    # StarRocks MySQL client
│   └── docs_module/        # Documentation templates
│       ├── en/
│       ├── zh/
│       └── ja/
├── meta/                   # Extracted metadata
│   ├── be_config.meta
│   ├── variables.meta
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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'some_field': self.some_field,
            'documents': self.documents
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MyNewItem':
        return cls(**data)
```

#### 2. Create Domain Directory

Create `src/docsagent/domains/mynewtype/` with four modules:

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
        prompt = f"Generate documentation for {item.name}..."
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

#### 3. Add to Factory

Update `domains/factory.py`:

```python
def create_pipeline(doc_type: str):
    """Factory function to create pipelines"""
    if doc_type == 'mynewtype':
        from docsagent.domains.mynewtype.extractor import MyNewExtractor
        from docsagent.domains.mynewtype.generator import MyNewGenerator
        from docsagent.domains.mynewtype.persister import MyNewPersister
        
        return {
            'extractor': MyNewExtractor(),
            'generator': MyNewGenerator(),
            'persister': MyNewPersister()
        }
    # ... other types
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

That's it! Your new document type will now work with the entire pipeline.

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
