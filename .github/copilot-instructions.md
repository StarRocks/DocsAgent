# StarRocks Docs Agent Guidelines
## 1. Background & Core Concept
- **Purpose**: Automated documentation generation system for StarRocks
- **Core Flow**: Code Extraction → Meta Generation → LLM Documentation → Translation → Git PR
- **Supported Types**: FE/BE Config, Session/Global Variables, Functions (Scalar/Aggregate/Window)
- **Architecture**: Pipeline-based with Protocol design pattern (duck typing)

## 2. Directory Structure
```
./
├── conf                                # Configuration files
│   ├── agent.conf                      # default configuration
│   └── example.conf
├── meta                                # Output Metadata files
│   ├── be_config.meta                  # BE configuration metadata
│   ├── variables.meta                  # Variables metadata
│   ├── functions                       # Function metadata files
│   └── logs
├── output                              # Generated documentation files
│   ├── en
│   ├── ja
│   └── zh
├── pyproject.toml                      # Poetry configuration file
├── src                                 # Source code directory
│   └── docsagent
│       ├── agents                      # Agents implementations
│       │   ├── config_doc_agent.py     # Config documentation agent
│       │   ├── functions_agent.py      # Functions agent
│       │   ├── variables_agent.py      # Variables agent
│       │   ├── translation_agent.py    # Translation agent
│       │   ├── llm.py                  # LLM wrapper
│       │   └── tools.py                # Agent tools
│       ├── config.py                   # Configuration management
│       ├── core                        # Core components, pipeline framework
│       │   ├── __init__.py
│       │   ├── pipeline.py
│       │   └── protocols.py
│       ├── docs_extract                # Documentation extraction modules
│       │   ├── config_meta_extract.py  # Config metadata extraction
│       │   ├── function_meta_extract.py # Function metadata extraction
│       │   └── variables_meta_extract.py # Variables metadata extraction
│       ├── docs_module                 # Documentation modules
│       │   ├── en
│       │   ├── ja
│       │   └── zh
│       ├── domains                     # Domain-specific modules  
│       │   ├── be_config               # BE Config
│       │   │   ├── extractor.py
│       │   │   ├── generator.py
│       │   │   ├── persister.py
│       │   │   └── git_persister.py
│       │   ├── fe_config               # FE Config
│       │   │   ├── extractor.py
│       │   │   ├── generator.py
│       │   │   ├── persister.py
│       │   │   └── git_persister.py
│       │   ├── functions               # Functions domain
│       │   │   ├── extractor.py
│       │   │   ├── generator.py
│       │   │   ├── persister.py
│       │   │   └── git_persister.py
│       │   ├── variables               # Variables domain
│       │   │   ├── extractor.py
│       │   │   ├── generator.py
│       │   │   ├── persister.py
│       │   │   └── git_persister.py
│       │   ├── factory.py              # Domain factory
│       │   └── models.py               # Domain models
│       ├── main.py                     # Main entry point
│       └── tools                       # Utility tools
│           ├── code_search.py          # Code search utilities
│           ├── code_tools.py           # Code manipulation tools
│           ├── file_reader.py          # File reading utilities
│           ├── git_operator.py         # Git operations
│           └── sr_client.py            # StarRocks client
└── tests
```

## 3. Development Environment
use poetry to manage python environment, with the following python libs:

```
# Tree-sitter for code parsing
tree-sitter>=0.25.2
tree-sitter-python>=0.25.0
tree-sitter-languages>=1.10.2

# LLM & AI frameworks
langgraph>=1.0.2
langchain>=1.0.0
langchain-openai>=1.0.0
langchain[anthropic]>=1.0.0
langchain[google-genai]>=1.0.0

# Utilities
gitpython>=3.1.45
loguru>=0.7.3
httpx[socks]>=0.28.1
pydantic-settings>=2.11.0
socksio>=1.0.0
hyperscan>=0.7.26
mysql-connector-python>=9.5.0
requests>=2.32.5
```

## 4. Core Architecture & Design Patterns

### 4.1 Pipeline Pattern
Each domain (fe_config, be_config, variables, functions) follows a 3-stage pipeline:
1. **Extractor**: Parse source code → Extract metadata → Save to `meta/`
2. **Generator**: Load metadata → LLM generation → Multi-language docs
3. **Persister**: Save to `output/` or commit to git (with optional PR)

### 4.2 Protocol-based Design
- `DocumentableItem` Protocol: Core abstraction for all documentable items
- Uses structural subtyping (duck typing) instead of inheritance
- Key methods: `name`, `documents`, `to_dict()`, `from_dict()`

### 4.3 Domain Factory
- `domains/factory.py`: Creates appropriate Extractor/Generator/Persister for each type
- Supports: 'fe_config', 'be_config', 'variables', 'functions'

### 4.4 Key Data Models (domains/models.py)
- **ConfigItem**: Configuration parameters with catalog/scope/mutable/default_value
- **FunctionItem**: Function signatures with catalog/syntax/examples/related
- **VariableItem**: Variables with type/scope/default/session_level
- **VALID_CATALOGS**: Predefined categories for docs organization

## 5. CLI Usage & Main Entry
Main command: `python -m docsagent.main [options]`

Key arguments:
- `-e, --extract`: Extract metadata from source code
- `-g, --generate`: Generate documentation with LLM
- `-t, --type`: Choose type (fe_config/be_config/variables/functions)
- `-m, --meta`: Print metadata without generating docs
- `--git-ci`: Commit changes to git
- `--git-pr`: Create pull request
- `-f, --force-search`: Force code search for usage examples
- `-l, --limit`: Limit number of items to process

Examples:
```bash
# Extract + Generate FE config docs
python -m docsagent.main -e -g -t fe_config

# Generate functions docs with git PR
python -m docsagent.main -g -t functions --git-ci --git-pr

# Extract BE config metadata only
python -m docsagent.main -e -t be_config
```

## 6. Configuration Management (config.py)
Uses Pydantic BaseSettings with priority: ENV vars > conf file > defaults

Key configs:
- `STARROCKS_HOME`: Source code repository path
- `LLM_MODEL/API_KEY/URL`: LLM configuration
- `TARGET_LANGS`: ['en', 'zh', 'ja']
- `META_DIR/DOCS_OUTPUT_DIR`: Input/output directories
- `SR_HOST/PORT/USER/PASSWORD`: StarRocks DB for SQL validation

## 7. Copilot Rules
* use chinese to answer
* use english comments in code
* don't generate any explain document if I don't request!!!
* project use poetry to manage python environment, should run `poetry shell` when can't found libraries