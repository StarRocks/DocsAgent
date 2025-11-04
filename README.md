# DocsAgent

An LLM-powered documentation automation tool for StarRocks that automatically extracts metadata from source code and generates multi-language technical documentation.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Poetry](https://img.shields.io/badge/Poetry-Dependency%20Management-blueviolet.svg)](https://python-poetry.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

## ✨ Features

- 🚀 **Automated Extraction**: Automatically extract metadata for configs, variables, and functions from StarRocks source code
- 🤖 **Intelligent Generation**: LLM-powered generation of descriptions, parameter explanations, and usage examples
- 🌍 **Multi-language Support**: Support for Chinese, English, and Japanese with intelligent translation routing
- 📝 **Consistent Styling**: Aligned with official StarRocks documentation style
- 🔧 **Extensible Architecture**: Generic Protocol-based Pipeline design for easy extension
- 🛠️ **Tool-Enhanced**: Integrated code search tools for more accurate context
- 📦 **Version Tracking**: Automatically track when configs/variables/functions were first introduced across branches

## 📋 Supported Document Types

| Type             | Description                                     | Status |
| ---------------- | ----------------------------------------------- | ------ |
| FE Config        | Frontend configuration documentation            | ✅      |
| BE Config        | Backend configuration documentation             | ✅      |
| System Variables | Session/Global variables documentation          | ✅      |
| SQL Functions    | Scalar/Aggregate/Window functions documentation | ✅      |

## 🏗️ Architecture

### Design Philosophy

DocsAgent adopts a **Protocol-based Pipeline architecture** that emphasizes:
- **Duck Typing**: Using Python Protocols instead of inheritance for flexibility
- **Generic Pipeline**: Type-safe pipeline that works with any `DocumentableItem`
- **Domain Separation**: Each document type (config/variable/function) is a separate domain
- **3-Stage Flow**: Extractor → Generator → Persister pattern for all domains

### Workflow

```mermaid
graph TB
    A[Source Code] --> B[Extractor]
    B --> |Meta JSON| C[Meta Files]
    C --> D[Version Tracker]
    D --> |Version Info| E[Generator]
    E --> |LLM| F[English Docs]
    F --> G[Translation Agent]
    G --> |LLM| H[Multi-language Docs]
    H --> I[Persister]
    I --> J[Git Commit]
    J --> K[Create PR]
    
    subgraph "Stage 1: Extraction"
        A
        B
        C
        D
    end
    
    subgraph "Stage 2: Generation"
        E
        F
        G
        H
    end
    
    subgraph "Stage 3: Persistence"
        I
        J
        K
    end
```

## 🚀 Quick Start

### Requirements

- Python 3.10+
- Poetry (package manager)
- StarRocks source code (for metadata extraction)
- LLM API key (OpenAI/Anthropic/Google)

### Installation

```bash
# Clone the repository
git clone https://github.com/StarRocks/DocsAgent.git
cd DocsAgent

# Install dependencies
# `brew install poetry` on mac, or similar on other OS may be needed
pip install poetry

# Activate virtual environment
# the two ways:
# 1. manual source the poetry env
# 2. install shell plugin, using poetry shell 
$(poetry env activate)
# poetry shell


# Install DocsAgent
poetry install
```

### Configuration

Create configuration file from template:

```bash
cp conf/example.conf conf/agent.conf
```

Key configuration options:

```ini
# StarRocks source code path (required)
STARROCKS_HOME=/path/to/starrocks

# LLM configuration
# e.g:
#  openai:gpt-4
#  anthropic:claude-3-sonnet-20240229
#  google:gemini-pro
LLM_MODEL=openai:gpt-4o-mini
LLM_API_KEY=your_api_key

# need config if llm isn't OpenAI/Gemini/Claude
# LLM_URL=https://api.openai.com/v1 
# LLM_PROVIDER=openai
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=5000

# Output configuration
DOCS_OUTPUT_DIR=./output
META_DIR=./meta
TARGET_LANGS=["en", "zh", "ja"]

# StarRocks client (for SQL validation)
SR_HOST=localhost
SR_PORT=9030
SR_USER=root
SR_PASSWORD=

# Logging
LOG_DIR=./logs
LOG_LEVEL=INFO

# Git and GitHub configuration
GITHUB_TOKEN=  # GitHub personal access token for creating PRs
GITHUB_REPO=StarRocks/starrocks  # GitHub repository in format 'owner/repo' (e.g., 'StarRocks/starrocks')
```

> **Note**: Configuration priority is: Environment variables > Config file > Defaults

### Basic Usage

### Command Line Arguments

| Argument                  | Description                                             |
| ------------------------- | ------------------------------------------------------- |
| `-e, --extract`           | Extract metadata from source code                       |
| `-g, --generate`          | Generate documentation                                  |
| `-m, --meta`              | Generate metadata without generating docs               |
| `-t, --type`              | Document type (fe_config/be_config/variables/functions) |
| `--config`                | Configuration file path                                 |
| `-f, --force_search_code` | Force code re-search and update the item's usage        |
| `-i, --ignore_miss_usage` | Ignore variable/config when missing usage in code       |
| `-wl, --without-llm`      | Run without LLM (use existing docs)                     |
| `-l, --limit`             | Limit number of items to process                        |
| `--ci`                    | Enable Git commit                                       |
| `--pr`                    | Enable Pull Request creation                            |
| `-tv, --track-version`    | Track versions for items (first-time use)           |

### Usage Examples

```bash
# Incremental Mode: 
# 1. Extract meta from documents first, to compute the meta for calculate increments (keep the exists docs)
# 2. Generate documents

# Full Mode:
# 1. Generate docuemnts without extract meta from documents

# Example
# FE/BE configs increments
# 1. Extract FE config meta from documentation
python -m docsagent.main -e -t fe_config

# 2. Generate FE config documentation and create git pr 
python -m docsagent.main -g -t fe_config --track-version --pr

# FE/BE configs full
# 1. Generate FE config documentation with limit and create git pr 
python -m docsagent.main -g -t fe_config -l 10 --track-version --pr

# Variables
# 1. Extract Variables meta from documentation
python -m docsagent.main -e -t variables

# 2. Generate Variables documentation
python -m docsagent.main -g -t variables -tv --ci

# Functions
# 1. Extract Functions meta from documentation
python -m docsagent.main -e -t variables

# 2. Generate Functions documentation without llm generate
python -m docsagent.main -g -t variables -tv -wl
```

## 🔧 Development Guide
For detailed usage, see [dev-guide.md](dev-guide.md)

## 📊 Output Examples

### Generated Documentation

Documentation is generated in Markdown format with proper formatting:

```markdown
## enable_materialized_view

- **Type**: Boolean
- **Default**: true
- **Introduced in**: v3.2.0
- **Description**: Whether to enable materialized view feature...
```

### Metadata Files

Metadata stored in `meta/` directory:

```json
// meta/fe_config.meta
{
  "items": [
    {
      "name": "enable_materialized_view",
      "type": "boolean",
      "default_value": "true",
      "version": ["v3.2.0"],
      "catalog": "query-engine",
      "documents": {
        "en": "...",
        "zh": "...",
        "ja": "..."
      }
    }
  ]
}
```

### Version File Structure

Version tracking results cached in `meta/*.version`:

```json
{
  "metadata": {
    "git_version": "a3f5b2c",
    "maintained_branches": ["3.2", "3.3", "3.4", "3.5", "4.0"]
  },
  "versions": {
    "enable_materialized_view": {
      "3.2": "3.2.0",
      "3.3": "3.3.0",
      "3.4": "3.4.0"
    }
  }
}
```

### Directory Structure of Output
```
output/
├── en/                                 # English documentation
│   ├── FE_configuration.md             # FE config consolidated
│   ├── BE_configuration.md             # BE config consolidated
│   ├── System_variable.md              # Variables consolidated
│   └── functions/                      # Function docs
│       ├── array-functions/
│       │   ├── array_append.md
│       │   └── array_concat.md
│       ├── string-functions/
│       │   ├── concat.md
│       │   └── substring.md
│       └── mathematical-functions/
│           ├── abs.md
│           └── sqrt.md
├── zh/                                 # Chinese documentation (same structure)
│   ├── FE_configuration.md
│   └── functions/
│       └── ...
└── ja/                                 # Japanese documentation (same structure)
    ├── FE_configuration.md
    └── functions/
        └── ...
```

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details
