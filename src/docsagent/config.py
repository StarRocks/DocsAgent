import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """
    Application configuration using Pydantic BaseSettings.
    
    Configuration priority (highest to lowest):
    1. Environment variables
    2. Configuration file (conf/agent.conf)
    3. Default values defined here
    
    To add a new configuration:
    1. Add a field with type annotation and default value here
    2. (Optional) Add the value in conf/agent.conf
    
    Example:
        NEW_FEATURE: bool = False
        NEW_TIMEOUT: int = 30
    """
    
    # StarRocks source code configuration
    STARROCKS_HOME: str = ''
    
    # Output configuration
    DOCS_OUTPUT_DIR: str = Field(default_factory=lambda: str(Path(__file__).parent.parent.parent / 'output'))
    
    META_DIR: str = Field(default_factory=lambda: str(Path(__file__).parent.parent.parent / 'meta'))
    
    # LLM configuration
    LLM_MODEL: str = 'openai:gpt-3.5-turbo'
    LLM_API_KEY: str = ''
    LLM_URL: str = ''
    LLM_PROVIDER: str = 'openai'
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 5000
    
    # Processing configuration
    TARGET_LANGS: List[str] = Field(default=['en', 'zh', 'ja'])
    
    # Logging configuration
    LOG_DIR: str = Field(default_factory=lambda: str(Path(__file__).parent.parent.parent / 'logs'))
    LOG_LEVEL: str = 'INFO'
    
    # StarRocks Client configuration
    SR_HOST: str = 'localhost'
    SR_PORT: int = 9030
    SR_USER: str = 'root'
    SR_PASSWORD: str = ''
    SR_DATABASE: str = ''
    
    MUST_USE_SR_CLIENT: bool = False  # Whether StarRocks client is required
    
    # Git and GitHub configuration
    GITHUB_TOKEN: str = ''  # GitHub personal access token for creating PRs
    GITHUB_REPO: str = 'StarRocks/starrocks'  # GitHub repository in format 'owner/repo' (e.g., 'StarRocks/starrocks')
    
    
    @property
    def DOCS_MODULE_DIR(self) -> Path:
        """Computed property for docs module directory"""
        return Path(__file__).parent / 'docs_module'
    
    # Field validators
    @field_validator('TARGET_LANGS', mode='before')
    @classmethod
    def parse_target_langs(cls, v):
        """Parse TARGET_LANGS from comma-separated string or list"""
        if isinstance(v, str):
            return [lang.strip() for lang in v.split(',')]
        return v
    
    @field_validator('FORCE_RESEARCH_CODE', mode='before')
    @classmethod
    def parse_bool(cls, v):
        """Parse boolean from string"""
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on')
        return v
    
    model_config = SettingsConfigDict(
        env_file=None,  # We'll handle config file loading manually
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore',  # Ignore extra fields in config file
    )
    
    @classmethod
    def load_from_file(cls, config_path: Optional[str] = None) -> 'AppConfig':
        """
        Load configuration from file and environment variables.
        
        Args:
            config_path: Path to config file. If None, will search in default locations.
            
        Returns:
            AppConfig instance
        """
        if config_path is None:
            possible_paths = [
                Path(__file__).parent.parent.parent / "conf" / "agent.conf",
                Path.cwd() / "conf" / "agent.conf",
            ]
            
            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break
        
        # Load config file manually
        config_dict = {}
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
                        
                        # Remove quotes
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        config_dict[key] = value
        
        # Merge with environment variables (env vars take precedence)
        # Check each field defined in the model
        for field_name in cls.model_fields.keys():
            env_value = os.environ.get(field_name)
            if env_value is not None:
                config_dict[field_name] = env_value
        
        # Create instance with merged values
        return cls(**config_dict)


# Global configuration instance
config = AppConfig.load_from_file()

def reload_config(config_path: Optional[str] = None):
    """
    Reload configuration from file.
    
    Args:
        config_path: Path to config file. If None, will search in default locations.
    """
    global config
    config = AppConfig.load_from_file(config_path)


# Magic method for backward compatibility
# This allows `from config import LLM_MODEL` to work automatically
def __getattr__(name: str):
    """
    Automatically expose config attributes as module-level variables.
    This eliminates the need to manually list each config variable.
    """
    if hasattr(config, name):
        return getattr(config, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")