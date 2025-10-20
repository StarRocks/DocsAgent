# StarRocks Docs Agent Guidelines
## 1. Background
- devlopment doc: dev.cn.md

## 2. Directory Structure
```
./
├── conf                                # Configuration files
│   ├── agent.conf                      # default configuration
│   └── example.conf
├── meta                                # Output Metadata files
│   ├── agg_func
│   ├── fe_config.meta
│   ├── scalar_func
│   ├── version
│   └── window_func
├── output                              # Generated documentation files
│   ├── en
│   ├── ja
│   └── zh
├── pyproject.toml                      # Poetry configuration file
├── src                                 # Source code directory
│   └── docsagent
│       ├── agents                      # Agents implementations
│       │   ├── config_doc_agent.py
│       │   ├── llm.py
│       │   └── translation_agent.py
│       ├── config.py
│       ├── core                        # Core components, pipeline framework
│       │   ├── __init__.py
│       │   ├── pipeline.py
│       │   └── protocols.py
│       ├── docs_module                 # Documentation modules
│       │   ├── en
│       │   ├── ja
│       │   └── zh
│       ├── domains                      # Domain-specific modules  
│       │   ├── be_config                # BE Config
│       │   │   ├── extractor.py
│       │   │   ├── generator.py
│       │   │   ├── __init__.py
│       │   │   └── persister.py
│       │   ├── factory.py
│       │   ├── fe_config               # FE Config
│       │   │   ├── extractor.py
│       │   │   ├── generator.py
│       │   │   ├── __init__.py
│       │   │   └── persister.py
│       │   ├── __init__.py
│       │   └── models.py
│       ├── main.py
│       └── tools                       # Utility tools
│           ├── code_search.py
│           └── variables_parser.py
└── tests
```

## 3. Development Environment
use poetry to manage python environment, with the following python libs:

```
tree-sitter 
tree-sitter-java 
tree-sitter-python 
tree-sitter-cpp

litellm
langgraph
gitpython
loguru
```

## 4. Copilot Rules
* use chinese to answer
* use english comments in code
* don't generate any explain document if I don't request
* project use poetry to manage python environment, should run `poetry shell` when can't found libraries