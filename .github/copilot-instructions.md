# StarRocks Docs Agent Guidelines
## 1. Background
- devlopment doc: dev.cn.md

## 2. Directory Structure
```
docs-agent/
├─ meta/               # JSON Meta
|  ├─ version/
│  ├─ variable/
│  ├─ fe_config/
│  ├─ be_config/
│  ├─ scalar_func/
│  ├─ agg_func/
│  └─ window_func/
├─ src/
|  ├─ code_extract/    # code -> meta
|  ├─ docs_extract/    # docs -> meta
|  ├─ agents/
|  ├─ config/
|  └─ tools/
└─ tests/
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