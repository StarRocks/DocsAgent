"""Test new Pydantic-based configuration system"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from docsagent.config import config, AppConfig, reload_config


def test_basic_config_loading():
    """Test basic configuration loading"""
    print("=" * 60)
    print("Test 1: Basic Configuration Loading")
    print("=" * 60)
    
    print(f"✓ STARROCKS_HOME: {config.STARROCKS_HOME}")
    print(f"✓ DOCS_OUTPUT_DIR: {config.DOCS_OUTPUT_DIR}")
    print(f"✓ LLM_MODEL: {config.LLM_MODEL}")
    print(f"✓ LLM_TEMPERATURE: {config.LLM_TEMPERATURE} (type: {type(config.LLM_TEMPERATURE).__name__})")
    print(f"✓ LLM_MAX_TOKENS: {config.LLM_MAX_TOKENS} (type: {type(config.LLM_MAX_TOKENS).__name__})")
    print(f"✓ TARGET_LANGS: {config.TARGET_LANGS} (type: {type(config.TARGET_LANGS).__name__})")
    print(f"✓ FORCE_RESEARCH_CODE: {config.FORCE_RESEARCH_CODE} (type: {type(config.FORCE_RESEARCH_CODE).__name__})")
    print()


def test_computed_properties():
    """Test computed properties"""
    print("=" * 60)
    print("Test 2: Computed Properties")
    print("=" * 60)
    
    print(f"✓ META_CONFIG_DIR: {config.META_DIR}")
    print(f"✓ DOCS_MODULE_DIR: {config.DOCS_MODULE_DIR}")
    print()


def test_type_validation():
    """Test type validation and conversion"""
    print("=" * 60)
    print("Test 3: Type Validation")
    print("=" * 60)
    
    # Test that types are correct
    assert isinstance(config.LLM_TEMPERATURE, float), "LLM_TEMPERATURE should be float"
    assert isinstance(config.LLM_MAX_TOKENS, int), "LLM_MAX_TOKENS should be int"
    assert isinstance(config.TARGET_LANGS, list), "TARGET_LANGS should be list"
    assert isinstance(config.FORCE_RESEARCH_CODE, bool), "FORCE_RESEARCH_CODE should be bool"
    
    print("✓ All type validations passed!")
    print()


def test_backward_compatibility():
    """Test backward compatibility with module-level imports"""
    print("=" * 60)
    print("Test 4: Backward Compatibility")
    print("=" * 60)
    
    from docsagent.config import LLM_MODEL, LLM_TEMPERATURE, TARGET_LANGS
    
    print(f"✓ Module-level LLM_MODEL: {LLM_MODEL}")
    print(f"✓ Module-level LLM_TEMPERATURE: {LLM_TEMPERATURE}")
    print(f"✓ Module-level TARGET_LANGS: {TARGET_LANGS}")
    print("✓ Backward compatibility maintained!")
    print()


def test_env_override():
    """Test environment variable override"""
    print("=" * 60)
    print("Test 5: Environment Variable Override")
    print("=" * 60)
    
    # Set an environment variable
    os.environ['LLM_TEMPERATURE'] = '0.8'
    os.environ['NEW_TEST_CONFIG'] = 'from_env'
    
    # Reload config
    test_config = AppConfig.load_from_file()
    
    print(f"✓ LLM_TEMPERATURE from env: {test_config.LLM_TEMPERATURE}")
    assert test_config.LLM_TEMPERATURE == 0.8, "Env var should override config file"
    
    # Clean up
    del os.environ['LLM_TEMPERATURE']
    if 'NEW_TEST_CONFIG' in os.environ:
        del os.environ['NEW_TEST_CONFIG']
    
    print("✓ Environment variable override works!")
    print()


def test_reload_config():
    """Test config reload functionality"""
    print("=" * 60)
    print("Test 6: Config Reload")
    print("=" * 60)
    
    original_model = config.LLM_MODEL
    reload_config()
    
    from docsagent.config import LLM_MODEL
    print(f"✓ Original model: {original_model}")
    print(f"✓ After reload: {LLM_MODEL}")
    print("✓ Config reload works!")
    print()


def demo_adding_new_config():
    """Demo: How to add a new configuration"""
    print("=" * 60)
    print("Demo: Adding New Configuration")
    print("=" * 60)
    print("""
To add a new configuration, just add one line in config.py:

    class AppConfig(BaseSettings):
        # ... existing configs
        NEW_CACHE_ENABLED: bool = False      # ← Add this!
        NEW_CACHE_TTL: int = 3600            # ← And this!
        NEW_API_ENDPOINT: str = 'https://...' # ← Or this!

Then in conf/agent.conf:
    NEW_CACHE_ENABLED=true
    NEW_CACHE_TTL=7200
    NEW_API_ENDPOINT=https://api.example.com

That's it! No need to:
  ❌ Write os.environ.get(...)
  ❌ Add to reload_config()
  ❌ Handle type conversion manually
  ❌ Repeat code 3 times

Benefits:
  ✓ Type safety with IDE autocomplete
  ✓ Automatic env var override
  ✓ Built-in validation
  ✓ Much less code!
    """)


if __name__ == '__main__':
    try:
        test_basic_config_loading()
        test_computed_properties()
        test_type_validation()
        test_backward_compatibility()
        test_env_override()
        test_reload_config()
        demo_adding_new_config()
        
        print("=" * 60)
        print("🎉 All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
