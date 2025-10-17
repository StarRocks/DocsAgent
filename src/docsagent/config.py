import os
from pathlib import Path
from typing import Dict, Optional


def load_config_from_file(config_path: Optional[str] = None) -> Dict[str, str]:
    if config_path is None:
        possible_paths = [
            Path(__file__).parent.parent.parent / "conf" / "agent.conf",
            Path.cwd() / "conf" / "agent.conf",
        ]
        
        for path in possible_paths:
            if path.exists():
                config_path = str(path)
                break
    
    config = {}
    
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    config[key] = value
    
    return config


_config = load_config_from_file()

STARROCKS_HOME = os.environ.get('STARROCKS_HOME', _config.get('STARROCKS_HOME', ''))
DOCS_OUTPUT_DIR = os.environ.get('DOCS_OUTPUT_DIR', _config.get('DOCS_OUTPUT_DIR', './docs/output'))

LLM_MODEL = os.environ.get('LLM_MODEL', _config.get('LLM_MODEL', 'openai:gpt-3.5-turbo'))
LLM_API_KEY = os.environ.get('LLM_API_KEY', _config.get('LLM_API_KEY', ''))
LLM_URL = os.environ.get('LLM_URL', _config.get('LLM_URL', ''))
LLM_PROVIDER = os.environ.get('LLM_PROVIDER', _config.get('LLM_PROVIDER', 'openai'))

LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', _config.get('LLM_TEMPERATURE', '0.1')))
LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', _config.get('LLM_MAX_TOKENS', '500')))

META_CONFIG_DIR = None
FORCE_RESEARCH_CODE = False
TARGET_LANGS = ['en', 'zh', 'ja']

def reload_config(config_path: Optional[str] = None):
    global STARROCKS_HOME, LLM_MODEL, LLM_API_KEY, LLM_URL, LLM_PROVIDER, LLM_TEMPERATURE, LLM_MAX_TOKENS
    global DOCS_OUTPUT_DIR, META_CONFIG_DIR, FORCE_RESEARCH_CODE, SRC_LANG, TARGET_LANGS, _config
    _config = load_config_from_file(config_path)
    
    STARROCKS_HOME = os.environ.get('STARROCKS_HOME', _config.get('STARROCKS_HOME', ''))
    DOCS_OUTPUT_DIR = os.environ.get('DOCS_OUTPUT_DIR', _config.get('DOCS_OUTPUT_DIR', './docs/output'))
        
    LLM_MODEL = os.environ.get('LLM_MODEL', _config.get('LLM_MODEL', 'openai:gpt-3.5-turbo'))
    LLM_API_KEY = os.environ.get('LLM_API_KEY', _config.get('LLM_API_KEY', ''))
    LLM_URL = os.environ.get('LLM_URL', _config.get('LLM_URL', ''))
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', _config.get('LLM_PROVIDER', 'openai'))
    
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', _config.get('LLM_TEMPERATURE', '0.1')))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', _config.get('LLM_MAX_TOKENS', '500')))
    
    META_CONFIG_DIR = DOCS_OUTPUT_DIR + "/config/"
    FORCE_RESEARCH_CODE = _config.get('FORCE_RESEARCH_CODE', 'false').lower() == 'true'
    
    TARGET_LANGS = _config.get('TARGET_LANGS', 'en,zh,ja').split(',')